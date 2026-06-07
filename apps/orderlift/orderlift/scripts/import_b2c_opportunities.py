from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import frappe
from frappe.utils import cint, flt, now_datetime, nowdate


COMPANY = "Orderlift Maroc Installation"
BUSINESS_TYPE = "Installation"
CRM_SEGMENT = "Individu"
TERRITORY = "Morocco"
CONFIRMED_STATUS_PREFIX = "8."
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def run(workbook_path: str, dry_run: int = 1, limit: int | None = None) -> dict:
    dry_run = cint(dry_run)
    rows = parse_workbook(workbook_path)
    if limit:
        rows = rows[: cint(limit)]

    summary = {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "skipped": [],
        "customers": 0,
        "prospects": 0,
        "opportunities_created": 0,
        "opportunities_updated": 0,
        "warnings": [],
    }

    for row in rows:
        ref = clean_text(row.get("Réf Projet"))
        client = clean_text(row.get("Client"))
        if not client or client == "-":
            summary["skipped"].append({"ref": ref, "reason": "missing client"})
            continue

        confirmed = is_confirmed(row)
        party_type = "Customer" if confirmed else "Prospect"
        summary["customers" if confirmed else "prospects"] += 1
        title = build_title(ref, row.get("Projet"), client)

        try:
            party_name = upsert_party(party_type, row, dry_run=dry_run)
            opportunity = upsert_opportunity(party_type, party_name, row, title, dry_run=dry_run)
            if opportunity.get("created"):
                summary["opportunities_created"] += 1
            else:
                summary["opportunities_updated"] += 1
        except Exception as exc:
            summary["warnings"].append({"ref": ref, "client": client, "error": str(exc)})

    if not dry_run:
        frappe.db.commit()
    return summary


def parse_workbook(workbook_path: str) -> list[dict]:
    path = Path(workbook_path)
    with ZipFile(path) as zipped:
        shared = _shared_strings(zipped)
        sheet_path = _sheet_path(zipped, "Suivi_Projet")
        raw_rows = _read_sheet(zipped, sheet_path, shared)
    if not raw_rows:
        return []
    headers = [clean_text(value).replace("\n", " ") for value in raw_rows[0]]
    rows = []
    for raw in raw_rows[1:]:
        if not any(value not in (None, "") for value in raw):
            continue
        rows.append({headers[idx]: raw[idx] if idx < len(raw) else None for idx in range(len(headers))})
    return rows


def upsert_party(party_type: str, row: dict, dry_run: int = 1) -> str:
    client = clean_text(row.get("Client"))
    phone = normalize_phone(row.get("Tél"))
    tier = clean_text(row.get("Catégorie Client"))
    city = clean_text(row.get("Ville / Localisation"))

    if party_type == "Customer":
        name = frappe.db.exists("Customer", client) or frappe.db.get_value("Customer", {"customer_name": client}, "name")
        doc = frappe.get_doc("Customer", name) if name else frappe.new_doc("Customer")
        doc.customer_name = doc.get("customer_name") or client
        doc.customer_type = doc.get("customer_type") or "Individual"
    else:
        name = frappe.db.exists("Prospect", client) or frappe.db.get_value("Prospect", {"company_name": client}, "name")
        doc = frappe.get_doc("Prospect", name) if name else frappe.new_doc("Prospect")
        doc.company_name = doc.get("company_name") or client
        if doc.meta.get_field("company"):
            doc.company = doc.get("company") or COMPANY

    if doc.meta.get_field("customer_group"):
        doc.customer_group = doc.get("customer_group") or _default_customer_group()
    if doc.meta.get_field("territory"):
        doc.territory = _existing_value("Territory", city) or _existing_value("Territory", TERRITORY) or doc.get("territory")
    if tier and tier != "-" and doc.meta.get_field("manual_tier"):
        doc.enable_dynamic_segmentation = 0
        doc.manual_tier = tier
    append_party_segment(doc)

    if dry_run:
        return name or client
    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    if phone:
        upsert_contact(doc.doctype, doc.name, client, phone)
    return doc.name


def upsert_opportunity(party_type: str, party_name: str, row: dict, title: str, dry_run: int = 1) -> dict:
    existing = find_opportunity(row.get("Réf Projet"))
    doc = frappe.get_doc("Opportunity", existing) if existing else frappe.new_doc("Opportunity")
    doc.opportunity_from = party_type
    doc.party_name = party_name
    doc.customer_name = clean_text(row.get("Client"))
    doc.title = title
    doc.status = doc.get("status") or "Open"
    stage = clean_text(row.get("Situation Projet"))
    if stage and frappe.db.exists("Sales Stage", stage):
        doc.sales_stage = stage
        doc.status = "Lost" if stage == "6. Devis rejeté/annulé" else "Open"
    doc.opportunity_type = doc.get("opportunity_type") or "Sales"
    doc.company = COMPANY
    doc.transaction_date = doc.get("transaction_date") or parse_excel_date(row.get("Date 1er contact")) or nowdate()
    if doc.meta.get_field("custom_first_contact_date"):
        doc.custom_first_contact_date = parse_excel_date(row.get("Date 1er contact"))
    if doc.meta.get_field("custom_crm_business_type"):
        doc.custom_crm_business_type = BUSINESS_TYPE
    if doc.meta.get_field("custom_crm_segment"):
        doc.custom_crm_segment = CRM_SEGMENT
    if doc.meta.get_field("territory"):
        doc.territory = _existing_value("Territory", TERRITORY) or doc.get("territory")
    if doc.meta.get_field("city"):
        doc.city = clean_text(row.get("Ville / Localisation"))
    phone = normalize_phone(row.get("Tél"))
    if phone:
        doc.phone = doc.get("phone") or phone
        doc.contact_mobile = doc.get("contact_mobile") or phone
    amount = normalize_amount(row.get("Montant projet Total TTC(MAD)"))
    if amount is not None:
        doc.opportunity_amount = amount
    ensure_reference_note(doc, row)

    if dry_run:
        return {"name": existing or title, "created": not bool(existing)}
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    add_source_comment(doc.name, row)
    return {"name": doc.name, "created": not bool(existing)}


def upsert_contact(party_type: str, party_name: str, display_name: str, phone: str) -> None:
    existing = _contact_for_party(party_type, party_name)
    contact = frappe.get_doc("Contact", existing) if existing else frappe.new_doc("Contact")
    contact.first_name = contact.get("first_name") or display_name
    if contact.meta.get_field("mobile_no"):
        contact.mobile_no = contact.get("mobile_no") or phone
    if contact.meta.get_field("phone"):
        contact.phone = contact.get("phone") or phone
    if not existing:
        contact.append("links", {"link_doctype": party_type, "link_name": party_name})
        contact.insert(ignore_permissions=True)
    else:
        contact.save(ignore_permissions=True)


def append_party_segment(doc) -> None:
    if not doc.meta.get_field("custom_crm_segments"):
        return
    existing = {(row.get("business_type"), row.get("segment")) for row in doc.get("custom_crm_segments") or []}
    if (BUSINESS_TYPE, CRM_SEGMENT) not in existing:
        doc.append("custom_crm_segments", {"business_type": BUSINESS_TYPE, "segment": CRM_SEGMENT, "is_primary": 0 if existing else 1})


def find_opportunity(ref) -> str | None:
    ref = clean_text(ref)
    if not ref:
        return None
    by_title = frappe.db.get_value("Opportunity", {"title": ref}, "name") or frappe.db.get_value(
        "Opportunity",
        {"title": ["like", f"{ref} -%"]},
        "name",
    )
    if by_title:
        return by_title
    by_comment = frappe.db.get_value(
        "Comment",
        {"reference_doctype": "Opportunity", "content": ["like", f"%Excel Ref: {ref}%"]},
        "reference_name",
    )
    if by_comment:
        return by_comment
    if frappe.db.exists("DocType", "CRM Note"):
        return frappe.db.get_value(
            "CRM Note",
            {"parenttype": "Opportunity", "note": ["like", f"%Excel Ref: {ref}%"]},
            "parent",
        )
    return None


def ensure_reference_note(doc, row: dict) -> None:
    ref = clean_text(row.get("Réf Projet"))
    if not ref or not doc.meta.get_field("notes"):
        return
    note = f"Excel Ref: {ref}"
    for existing in doc.get("notes") or []:
        if note in clean_text(existing.get("note")):
            return
    doc.append("notes", {"note": note, "added_by": frappe.session.user, "added_on": now_datetime()})


def add_source_comment(opportunity: str, row: dict) -> None:
    parts = [
        f"Excel Ref: {clean_text(row.get('Réf Projet'))}",
        f"Excel Status: {clean_text(row.get('Situation Projet'))}",
        f"Category: {clean_text(row.get('Catégorie Client'))}",
        f"Responsible: {clean_text(row.get('Responsable suivi'))}",
        f"Project Link: {clean_text(row.get('Project details  Link'))}",
        f"Quote Link: {clean_text(row.get('Lien Devis'))}",
        f"Comments: {clean_text(row.get('COMMENTS'))}",
    ]
    content = "<br>".join(part for part in parts if not part.endswith(": "))
    if not content:
        return
    if frappe.db.exists("Comment", {"reference_doctype": "Opportunity", "reference_name": opportunity, "content": content}):
        return
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Opportunity",
            "reference_name": opportunity,
            "content": content,
        }
    ).insert(ignore_permissions=True)


def is_confirmed(row: dict) -> bool:
    status = clean_text(row.get("Situation Projet"))
    return status.startswith(CONFIRMED_STATUS_PREFIX)


def build_title(ref, project, client=None) -> str:
    project = clean_text(project)
    client = clean_text(client)
    return project or client or clean_text(ref) or "Imported Opportunity"


def clean_text(value) -> str:
    return str(value or "").strip()


def normalize_amount(value) -> float | None:
    text = clean_text(value).replace("\u00a0", "")
    if not text or text == "-":
        return None
    text = text.lower().replace("mad", "").replace("dh", "").strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    return flt(text) if text else None


def normalize_phone(value) -> str:
    text = clean_text(value)
    if not text or text == "-":
        return ""
    text = next((part.strip() for part in re.split(r"[/;,]", text) if part.strip()), text)
    if "E" in text.upper():
        try:
            text = str(int(float(text)))
        except ValueError:
            pass
    text = re.sub(r"[^0-9+ /-]", "", text).strip()
    return text


def parse_excel_date(value) -> str | None:
    text = clean_text(value)
    if not text or text == "-":
        return None
    try:
        number = float(text)
    except ValueError:
        return text if re.match(r"\d{4}-\d{2}-\d{2}$", text) else None
    if number <= 0 or number > 60000:
        return None
    return (datetime(1899, 12, 30) + timedelta(days=number)).date().isoformat()


def _existing_value(doctype: str, value: str) -> str:
    value = clean_text(value)
    return value if value and frappe.db.exists(doctype, value) else ""


def _default_customer_group() -> str:
    for candidate in ["Individual", "Particulier", "Commercial"]:
        if frappe.db.exists("Customer Group", candidate) and not cint(frappe.db.get_value("Customer Group", candidate, "is_group")):
            return candidate
    group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    return group or "All Customer Groups"


def _contact_for_party(party_type: str, party_name: str) -> str | None:
    rows = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": party_type, "link_name": party_name, "parenttype": "Contact"},
        pluck="parent",
        limit=1,
    )
    return rows[0] if rows else None


def _shared_strings(zipped: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zipped.namelist():
        return []
    root = ET.fromstring(zipped.read("xl/sharedStrings.xml"))
    return ["".join(text.text or "" for text in item.findall(".//main:t", NS)) for item in root.findall("main:si", NS)]


def _sheet_path(zipped: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(zipped.read("xl/workbook.xml"))
    rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in ET.fromstring(zipped.read("xl/_rels/workbook.xml.rels"))}
    for sheet in workbook.findall("main:sheets/main:sheet", NS):
        if sheet.attrib.get("name") == sheet_name:
            target = rels[sheet.attrib[f"{{{NS['rel']}}}id"]]
            return "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
    frappe.throw(f"Sheet {sheet_name} was not found")


def _read_sheet(zipped: ZipFile, sheet_path: str, shared: list[str]) -> list[list]:
    root = ET.fromstring(zipped.read(sheet_path))
    rows = []
    for row in root.findall("main:sheetData/main:row", NS):
        values = []
        current_col = 1
        for cell in row.findall("main:c", NS):
            col = _cell_col(cell.attrib.get("r"))
            while col and current_col < col:
                values.append(None)
                current_col += 1
            values.append(_cell_value(cell, shared))
            current_col += 1
        rows.append(values)
    return rows


def _cell_col(ref: str | None) -> int | None:
    match = re.match(r"([A-Z]+)\d+", ref or "")
    if not match:
        return None
    col = 0
    for char in match.group(1):
        col = col * 26 + ord(char) - 64
    return col


def _cell_value(cell, shared: list[str]):
    cell_type = cell.attrib.get("t")
    value = cell.find("main:v", NS)
    inline = cell.find("main:is", NS)
    if cell_type == "s" and value is not None and value.text is not None:
        return shared[int(value.text)]
    if cell_type == "inlineStr" and inline is not None:
        return "".join(text.text or "" for text in inline.findall(".//main:t", NS))
    return value.text if value is not None else None
