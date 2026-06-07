from __future__ import annotations

import re

import frappe
from frappe.utils import cint, now_datetime, nowdate

from orderlift.orderlift_crm.status_config import OPPORTUNITY_STAGE_SEEDS
from orderlift.scripts.import_b2c_opportunities import (
    _default_customer_group,
    _existing_value,
    clean_text,
    normalize_amount,
    normalize_phone,
    parse_excel_date,
    parse_workbook,
    upsert_contact,
)


TERRITORY = "Morocco"
REFERENCE_PREFIX = "B2B Excel Ref"
DEFAULT_DISTRIBUTION_SEGMENT = "Installateur"
DEFAULT_INSTALLATION_SEGMENT = "Individu"
MISSING_CLIENT_NAME = "Missing Client"
FORCE_SKIP_EXCEL_ROWS = {122, 123, 124, 125, 126, 127, 176, 177, 178, 179, 180}
NO_ITEM_CODE = "no-item"
IMPORT_SELLING_PRICE_LIST = "ORDERLIFT IMPORT MAD"
DISTRIBUTION_COMPANY = "Orderlift Maroc Distribution"
INSTALLATION_COMPANY = "Orderlift Maroc Installation"
PROJECT_STATUS_ADVANCE_PAID = "8. Avance 40% payée"
PROJECT_STATUS_DELIVERED = "11. Marchandise livréeau client"

BUSINESS_CONFIG = {
    "Distribution": {
        "company": DISTRIBUTION_COMPANY,
        "crm_segment": DEFAULT_DISTRIBUTION_SEGMENT,
        "customer_type": "Company",
        "stage_map": {
            "1. Demande Client": "Distribution - 1. Demande Client",
            "2. Prise de mesure en cours": "Distribution - 2. Prise de mesure en cours",
            "3. Envoyée conception": "Distribution - 3. Envoyée conception",
            "4. Devis validé": "Distribution - 4. Devis validé",
            "5. Devis Envoyé": "Distribution - 5. Devis Envoyé",
            "7. Devis en cours de révision/négotiation": "Distribution - 7. Devis en cours de révision/négotiation",
            "8. Devis approuvé par client": "Distribution - 8. Devis approuvé par client",
            "9. Avance payée": "Distribution - 9. Avance payée",
            "13'. 1ère partie livrée": "Distribution - 9. Avance payée",
            "13. Marchandise livrée": "Distribution - 9. Avance payée",
            "payment remain + marchendise livre": "Distribution - 9. Avance payée",
        },
    },
    "Installation": {
        "company": INSTALLATION_COMPANY,
        "crm_segment": DEFAULT_INSTALLATION_SEGMENT,
        "customer_type": "Individual",
        "stage_map": {
            "1. Demande Client": "1. Demande Client",
            "2. Prise de mesure en cours": "2. Prise de mesure en cours",
            "3. Envoyée conception": "2. Envoyé conception",
            "4. Devis validé": "3. Devis validé (interne)",
            "5. Devis Envoyé": "5. Devis Envoyé",
            "6. Devis rejeté/annulé": "6. Devis rejeté/annulé",
            "7. Devis en cours de révision/négotiation": "5'. Suivi 2",
            "8. Devis approuvé par client": "8. Avance 40% payée",
            "9. Avance payée": "8. Avance 40% payée",
            "13'. 1ère partie livrée": "8. Avance 40% payée",
            "13. Marchandise livrée": "8. Avance 40% payée",
            "payment remain + marchendise livre": "8. Avance 40% payée",
        },
    },
}


def run(
    workbook_path: str,
    dry_run: int = 1,
    limit: int | None = None,
    distribution_segment: str = DEFAULT_DISTRIBUTION_SEGMENT,
    installation_segment: str = DEFAULT_INSTALLATION_SEGMENT,
    default_business_type: str = "",
) -> dict:
    dry_run = cint(dry_run)
    rows = parse_workbook(workbook_path)
    if limit:
        rows = rows[: cint(limit)]

    segment_by_business_type = {
        "Distribution": clean_text(distribution_segment) or DEFAULT_DISTRIBUTION_SEGMENT,
        "Installation": clean_text(installation_segment) or DEFAULT_INSTALLATION_SEGMENT,
    }
    default_business_type = normalize_business_type(default_business_type)

    summary = {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "skipped": [],
        "customers": 0,
        "prospects": 0,
        "opportunities_created": 0,
        "opportunities_updated": 0,
        "sales_orders_created": 0,
        "sales_orders_updated": 0,
        "projects_created": 0,
        "projects_updated": 0,
        "by_business_type": {},
        "converted_distribution_rows": 0,
        "stage_counts": {},
        "sales_order_status_counts": {},
        "project_status_counts": {},
        "stages_created": 0,
        "stages_created_by_company": {},
        "no_item_created": 0,
        "import_price_list_created": 0,
        "import_item_prices_deleted": 0,
        "warnings": [],
    }

    created_by_company = ensure_sales_stages(dry_run=dry_run)
    summary["stages_created_by_company"] = created_by_company
    summary["stages_created"] = sum(created_by_company.values())
    summary["no_item_created"] = ensure_no_item(dry_run=dry_run)
    summary["import_price_list_created"] = ensure_import_selling_price_list(dry_run=dry_run)

    for excel_row, row in enumerate(rows, start=2):
        row["_excel_row"] = excel_row
        ref = clean_text(row.get("Réf Devis/Projet"))
        client = clean_text(row.get("Client / Societe"))
        if excel_row in FORCE_SKIP_EXCEL_ROWS:
            summary["skipped"].append({"row": excel_row, "ref": ref, "client": client, "reason": "force skipped by operator"})
            continue
        if not ref:
            summary["skipped"].append({"reason": "missing ref", "client": client})
            continue
        if is_lost(row):
            summary["skipped"].append({"ref": ref, "client": client, "reason": "rejected opportunity"})
            continue
        if not client:
            client = MISSING_CLIENT_NAME
            row["Client / Societe"] = MISSING_CLIENT_NAME

        business_type = normalize_business_type(row.get("business type")) or default_business_type
        if not business_type:
            summary["skipped"].append({"ref": ref, "client": client, "reason": "missing business type"})
            continue
        if business_type not in BUSINESS_CONFIG:
            summary["skipped"].append({"ref": ref, "client": client, "reason": f"unsupported business type: {business_type}"})
            continue

        config = BUSINESS_CONFIG[business_type]
        crm_segment = segment_by_business_type[business_type]
        company = config["company"]
        business_summary = summary["by_business_type"].setdefault(
            business_type,
            {"company": company, "crm_segment": crm_segment, "customers": 0, "prospects": 0, "created": 0, "updated": 0},
        )

        raw_stage = clean_text(row.get("Projet Situation"))
        stage = map_sales_stage(raw_stage, business_type)
        stage_key = f"{business_type}: {stage or raw_stage or ''}"
        summary["stage_counts"][stage_key] = summary["stage_counts"].get(stage_key, 0) + 1

        confirmed = is_confirmed(row)
        party_type = "Customer" if confirmed else "Prospect"
        summary["customers" if confirmed else "prospects"] += 1
        business_summary["customers" if confirmed else "prospects"] += 1

        try:
            party_name = upsert_party(party_type, row, business_type, crm_segment=crm_segment, dry_run=dry_run)
            opportunity = upsert_opportunity(party_type, party_name, row, business_type, crm_segment=crm_segment, dry_run=dry_run)
            if opportunity.get("created"):
                summary["opportunities_created"] += 1
                business_summary["created"] += 1
            else:
                summary["opportunities_updated"] += 1
                business_summary["updated"] += 1
            if business_type == "Distribution" and is_converted_distribution(row):
                summary["converted_distribution_rows"] += 1
                downstream = upsert_converted_distribution_docs(
                    opportunity["name"],
                    party_name,
                    row,
                    crm_segment=crm_segment,
                    dry_run=dry_run,
                )
                if downstream["sales_order"].get("created"):
                    summary["sales_orders_created"] += 1
                else:
                    summary["sales_orders_updated"] += 1
                if downstream["project"].get("created"):
                    summary["projects_created"] += 1
                else:
                    summary["projects_updated"] += 1
                so_status = downstream["sales_order"].get("status") or ""
                project_status = downstream["project"].get("status") or ""
                summary["sales_order_status_counts"][so_status] = summary["sales_order_status_counts"].get(so_status, 0) + 1
                summary["project_status_counts"][project_status] = summary["project_status_counts"].get(project_status, 0) + 1
        except Exception as exc:
            summary["warnings"].append({"ref": ref, "client": client, "business_type": business_type, "error": str(exc)})

    summary["import_item_prices_deleted"] = cleanup_import_item_prices(dry_run=dry_run)

    if not dry_run:
        frappe.db.commit()
    return summary


def ensure_sales_stages(dry_run: int = 1) -> dict[str, int]:
    created_by_company = {}
    supported_companies = {config["company"] for config in BUSINESS_CONFIG.values()}
    for row in OPPORTUNITY_STAGE_SEEDS:
        company = row.get("company")
        if company not in supported_companies:
            continue
        if frappe.db.exists("Sales Stage", row["label"]):
            continue
        created_by_company[company] = created_by_company.get(company, 0) + 1
        if dry_run:
            continue
        doc = frappe.new_doc("Sales Stage")
        doc.stage_name = row["label"]
        doc.custom_sequence = row["sequence"]
        doc.custom_color = row["color"]
        doc.custom_is_active = 1
        doc.custom_is_default = row["is_default"]
        doc.custom_applies_distribution = row["distribution"]
        doc.custom_applies_installation = row["installation"]
        doc.custom_company = company
        if doc.meta.get_field("custom_display_label"):
            doc.custom_display_label = row.get("display_label") or ""
        if doc.meta.get_field("custom_todo_priority"):
            doc.custom_todo_priority = row.get("todo_priority") or ""
        doc.insert(ignore_permissions=True)
    return created_by_company


def ensure_no_item(dry_run: int = 1) -> int:
    if frappe.db.exists("Item", NO_ITEM_CODE):
        return 0
    if dry_run:
        return 1
    doc = frappe.new_doc("Item")
    doc.item_code = NO_ITEM_CODE
    doc.item_name = "No Item"
    doc.item_group = _default_item_group()
    doc.stock_uom = _default_uom()
    doc.is_stock_item = 0
    doc.is_sales_item = 1
    doc.is_purchase_item = 0
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return 1


def ensure_import_selling_price_list(dry_run: int = 1) -> int:
    if frappe.db.exists("Price List", IMPORT_SELLING_PRICE_LIST):
        if not dry_run:
            frappe.db.set_value(
                "Price List",
                IMPORT_SELLING_PRICE_LIST,
                {"enabled": 1, "selling": 1, "buying": 0, "currency": "MAD"},
                update_modified=False,
            )
        return 0
    if dry_run:
        return 1
    doc = frappe.new_doc("Price List")
    doc.price_list_name = IMPORT_SELLING_PRICE_LIST
    doc.currency = "MAD"
    doc.enabled = 1
    doc.selling = 1
    doc.buying = 0
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return 1


def cleanup_import_item_prices(dry_run: int = 1) -> int:
    filters = {"item_code": NO_ITEM_CODE, "price_list": IMPORT_SELLING_PRICE_LIST}
    count = frappe.db.count("Item Price", filters)
    if count and not dry_run:
        frappe.db.delete("Item Price", filters)
    return count


def upsert_party(party_type: str, row: dict, business_type: str, crm_segment: str, dry_run: int = 1) -> str:
    config = BUSINESS_CONFIG[business_type]
    client = clean_text(row.get("Client / Societe"))
    phone = normalize_phone(row.get("Tél"))
    city = clean_text(row.get("Ville/Site"))

    if party_type == "Customer":
        name = frappe.db.exists("Customer", client) or frappe.db.get_value("Customer", {"customer_name": client}, "name")
        doc = frappe.get_doc("Customer", name) if name else frappe.new_doc("Customer")
        doc.customer_name = doc.get("customer_name") or client
        doc.customer_type = doc.get("customer_type") or config["customer_type"]
    else:
        name = frappe.db.exists("Prospect", client) or frappe.db.get_value("Prospect", {"company_name": client}, "name")
        doc = frappe.get_doc("Prospect", name) if name else frappe.new_doc("Prospect")
        doc.company_name = doc.get("company_name") or client
        if doc.meta.get_field("company"):
            doc.company = doc.get("company") or config["company"]

    if doc.meta.get_field("customer_group"):
        doc.customer_group = doc.get("customer_group") or _default_customer_group()
    if doc.meta.get_field("territory"):
        doc.territory = _existing_value("Territory", city) or _existing_value("Territory", TERRITORY) or doc.get("territory")
    append_party_segment(doc, business_type, crm_segment)
    normalize_manual_tier_case(doc)

    if dry_run:
        return name or client
    if name:
        try:
            doc.save(ignore_permissions=True)
        except Exception as exc:
            frappe.log_error(f"Skipped existing {doc.doctype} update during B2B import: {exc}", "B2B Opportunity Import")
            return doc.name
    else:
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    if phone:
        upsert_contact(doc.doctype, doc.name, client, phone)
    return doc.name


def upsert_opportunity(
    party_type: str,
    party_name: str,
    row: dict,
    business_type: str,
    crm_segment: str,
    dry_run: int = 1,
) -> dict:
    config = BUSINESS_CONFIG[business_type]
    ref = clean_text(row.get("Réf Devis/Projet"))
    existing = find_opportunity(ref, config["company"])
    doc = frappe.get_doc("Opportunity", existing) if existing else frappe.new_doc("Opportunity")
    doc.opportunity_from = party_type
    doc.party_name = party_name
    doc.customer_name = clean_text(row.get("Client / Societe"))
    doc.title = build_title(row, business_type)
    doc.status = "Lost" if is_lost(row) else (doc.get("status") or "Open")
    stage = map_sales_stage(row.get("Projet Situation"), business_type)
    if stage and (dry_run or frappe.db.exists("Sales Stage", stage)):
        doc.sales_stage = stage
    doc.opportunity_type = doc.get("opportunity_type") or "Sales"
    doc.company = config["company"]
    doc.transaction_date = parse_excel_date(row.get("Date devis")) or doc.get("transaction_date") or nowdate()
    if doc.meta.get_field("custom_crm_business_type"):
        doc.custom_crm_business_type = business_type
    if doc.meta.get_field("custom_crm_segment"):
        doc.custom_crm_segment = crm_segment
    if doc.meta.get_field("territory"):
        doc.territory = _existing_value("Territory", TERRITORY) or doc.get("territory")
    if doc.meta.get_field("city"):
        doc.city = clean_text(row.get("Ville/Site"))
    phone = normalize_phone(row.get("Tél"))
    if phone:
        doc.phone = doc.get("phone") or phone
        doc.contact_mobile = doc.get("contact_mobile") or phone
    amount = normalize_amount(row.get("Montant projet Total TTC(MAD)"))
    if amount is not None:
        doc.opportunity_amount = amount
    ensure_reference_note(doc, ref)

    if dry_run:
        return {"name": existing or doc.title, "created": not bool(existing)}
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    add_source_comment(doc.name, row, business_type)
    return {"name": doc.name, "created": not bool(existing)}


def upsert_converted_distribution_docs(
    opportunity: str,
    customer: str,
    row: dict,
    crm_segment: str,
    dry_run: int = 1,
) -> dict:
    project = upsert_installation_project(opportunity, customer, row, crm_segment=crm_segment, dry_run=dry_run)
    sales_order = upsert_distribution_sales_order(
        opportunity,
        customer,
        row,
        project_name=project["name"],
        crm_segment=crm_segment,
        dry_run=dry_run,
    )
    return {"sales_order": sales_order, "project": project}


def upsert_distribution_sales_order(
    opportunity: str,
    customer: str,
    row: dict,
    project_name: str,
    crm_segment: str,
    dry_run: int = 1,
) -> dict:
    ref = clean_text(row.get("Réf Devis/Projet"))
    existing = frappe.db.get_value("Sales Order", {"po_no": _source_po_no(ref), "company": DISTRIBUTION_COMPANY}, "name")
    status = sales_order_status_for_row(row)
    if dry_run:
        return {"name": existing or _source_po_no(ref), "created": not bool(existing), "status": status}

    doc = frappe.get_doc("Sales Order", existing) if existing else frappe.new_doc("Sales Order")
    doc.company = DISTRIBUTION_COMPANY
    doc.customer = customer
    doc.po_no = _source_po_no(ref)
    transaction_date = parse_excel_date(row.get("Date de confirmation")) or parse_excel_date(row.get("Date devis")) or nowdate()
    doc.transaction_date = transaction_date
    if doc.meta.get_field("selling_price_list"):
        doc.selling_price_list = IMPORT_SELLING_PRICE_LIST
    if doc.meta.get_field("price_list_currency"):
        doc.price_list_currency = "MAD"
    if doc.meta.get_field("currency"):
        doc.currency = "MAD"
    if doc.meta.get_field("conversion_rate"):
        doc.conversion_rate = doc.get("conversion_rate") or 1
    if doc.meta.get_field("custom_orderlift_order_status"):
        doc.custom_orderlift_order_status = status
    if doc.meta.get_field("custom_crm_business_type"):
        doc.custom_crm_business_type = "Distribution"
    if doc.meta.get_field("custom_crm_segment"):
        doc.custom_crm_segment = crm_segment
    if doc.meta.get_field("custom_installation_project") and project_name:
        doc.custom_installation_project = project_name
    elif doc.meta.get_field("project") and project_name:
        doc.project = project_name

    if not doc.get("items"):
        doc.append(
            "items",
            {
                "item_code": NO_ITEM_CODE,
                "qty": 1,
                "rate": normalize_amount(row.get("Montant projet Total TTC(MAD)")) or 0,
                "delivery_date": _safe_delivery_date(row, transaction_date),
            },
        )
    doc.run_method("set_missing_values")
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    add_source_comment(doc.name, row, "Distribution Sales Order", reference_doctype="Sales Order")
    return {"name": doc.name, "created": not bool(existing), "status": status}


def upsert_installation_project(
    opportunity: str,
    customer: str,
    row: dict,
    crm_segment: str,
    dry_run: int = 1,
) -> dict:
    ref = clean_text(row.get("Réf Devis/Projet"))
    existing = None
    if frappe.get_meta("Project").get_field("custom_source_opportunity") and not opportunity.startswith(build_title(row, "Distribution")):
        existing = frappe.db.get_value("Project", {"custom_source_opportunity": opportunity}, "name")
    existing = existing or frappe.db.get_value("Project", {"project_name": _source_project_name(ref), "company": INSTALLATION_COMPANY}, "name")
    status = project_status_for_row(row)
    if dry_run:
        return {"name": existing or unique_project_title(row), "created": not bool(existing), "status": status}

    doc = frappe.get_doc("Project", existing) if existing else frappe.new_doc("Project")
    doc.project_name = unique_project_title(row, existing_project=doc.name if existing else None)
    doc.status = "Open"
    doc.company = INSTALLATION_COMPANY
    if doc.meta.get_field("customer") and frappe.db.exists("Customer", customer):
        doc.customer = customer
    if doc.meta.get_field("custom_source_opportunity"):
        doc.custom_source_opportunity = opportunity
    if doc.meta.get_field("custom_project_status"):
        doc.custom_project_status = status
    if doc.meta.get_field("custom_crm_business_type"):
        doc.custom_crm_business_type = "Installation"
    if doc.meta.get_field("custom_crm_segment"):
        doc.custom_crm_segment = DEFAULT_INSTALLATION_SEGMENT
    if doc.meta.get_field("custom_project_type_ol"):
        doc.custom_project_type_ol = "New Installation"
    if doc.meta.get_field("custom_city"):
        doc.custom_city = clean_text(row.get("Ville/Site"))
    confirmation_date = parse_excel_date(row.get("Date de confirmation"))
    if confirmation_date and doc.meta.get_field("expected_start_date"):
        doc.expected_start_date = confirmation_date
    delivery_date = parse_excel_date(row.get("Date de livraison"))
    if delivery_date and doc.meta.get_field("expected_end_date"):
        doc.expected_end_date = delivery_date
    doc.notes = build_downstream_notes(row, existing_notes=doc.get("notes"))

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return {"name": doc.name, "created": not bool(existing), "status": status}


def append_party_segment(doc, business_type: str, crm_segment: str) -> None:
    if not doc.meta.get_field("custom_crm_segments"):
        return
    existing = {(row.get("business_type"), row.get("segment")) for row in doc.get("custom_crm_segments") or []}
    if (business_type, crm_segment) not in existing:
        doc.append("custom_crm_segments", {"business_type": business_type, "segment": crm_segment, "is_primary": 0 if existing else 1})


def normalize_manual_tier_case(doc) -> None:
    if not doc.meta.get_field("manual_tier"):
        return
    manual_tier = clean_text(doc.get("manual_tier"))
    if not manual_tier:
        return
    allowed = frappe.get_all(
        "Customer Segmentation Rule",
        filters={"is_active": 1},
        pluck="designated_segment",
        limit_page_length=0,
    )
    by_lower = {clean_text(value).lower(): clean_text(value) for value in allowed if clean_text(value)}
    canonical = by_lower.get(manual_tier.lower())
    if canonical and canonical != manual_tier:
        doc.manual_tier = canonical


def find_opportunity(ref, company: str) -> str | None:
    ref = clean_text(ref)
    if not ref:
        return None
    for doctype, filters in (
        ("Comment", {"reference_doctype": "Opportunity", "content": ["like", f"%{REFERENCE_PREFIX}: {ref}%"]}),
        ("Comment", {"reference_doctype": "Opportunity", "content": ["like", f"%Excel Ref: {ref}%"]}),
    ):
        opportunity = frappe.db.get_value(doctype, filters, "reference_name")
        if _is_company_opportunity(opportunity, company):
            return opportunity
    if frappe.db.exists("DocType", "CRM Note"):
        opportunity = frappe.db.get_value(
            "CRM Note",
            {"parenttype": "Opportunity", "note": ["like", f"%{REFERENCE_PREFIX}: {ref}%"]},
            "parent",
        )
        if _is_company_opportunity(opportunity, company):
            return opportunity
    return None


def ensure_reference_note(doc, ref: str) -> None:
    if not ref or not doc.meta.get_field("notes"):
        return
    note = f"{REFERENCE_PREFIX}: {ref}"
    for existing in doc.get("notes") or []:
        if note in clean_text(existing.get("note")):
            return
    doc.append("notes", {"note": note, "added_by": frappe.session.user, "added_on": now_datetime()})


def add_source_comment(reference_name: str, row: dict, business_type: str, reference_doctype: str = "Opportunity") -> None:
    parts = [
        f"{REFERENCE_PREFIX}: {clean_text(row.get('Réf Devis/Projet'))}",
        f"Business Type: {business_type}",
        f"Excel Client Ref: {clean_text(row.get('Réf. Client'))}",
        f"Excel Status: {clean_text(row.get('Projet Situation'))}",
        f"Responsible: {clean_text(row.get('Responsible'))}",
        f"Project Name: {clean_text(row.get('Nom projet'))}",
        f"Project Link: {clean_text(row.get('Project details Link'))}",
        f"Quote Link: {clean_text(row.get('Lien Devis'))}",
        f"Payment Remaining: {clean_text(row.get('Paiement restant'))}",
        f"With Installation: {clean_text(row.get('With installation (YES/NO)'))}",
        f"Project Location: {clean_text(row.get('Project Localisation'))}",
        f"Comments: {clean_text(row.get('COMMENTS'))}",
        f"Follow up 1: {clean_text(row.get('Date Follow up 1'))} {clean_text(row.get('Comment Follow up 1'))}",
        f"Follow up 2: {clean_text(row.get('Date Follow up 2'))} {clean_text(row.get('Comment Follow up 2'))}",
    ]
    content = "<br>".join(part for part in parts if not part.endswith(": "))
    if not content:
        return
    if frappe.db.exists("Comment", {"reference_doctype": reference_doctype, "reference_name": reference_name, "content": content}):
        return
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "content": content,
        }
    ).insert(ignore_permissions=True)


def map_sales_stage(status, business_type: str) -> str:
    config = BUSINESS_CONFIG.get(normalize_business_type(business_type))
    if not config:
        return ""
    status = clean_text(status)
    stage_map = config["stage_map"]
    return stage_map.get(status, stage_map.get(_normalize_status_text(status), ""))


def sales_order_status_for_row(row: dict) -> str:
    status = _normalize_status_text(row.get("Projet Situation"))
    if status.startswith("8."):
        return _distribution_order_status("Confirmed")
    if status.startswith("9."):
        return _distribution_order_status("Advance Paid")
    if status.startswith("13'."):
        return _distribution_order_status("Delivering")
    if status.startswith("payment remain"):
        return _distribution_order_status("Final Payment")
    if status.startswith("13."):
        return _distribution_order_status("Delivered")
    return _distribution_order_status("Confirmed")


def project_status_for_row(row: dict) -> str:
    status = _normalize_status_text(row.get("Projet Situation"))
    if status.startswith("13") or status.startswith("payment remain"):
        return PROJECT_STATUS_DELIVERED
    return PROJECT_STATUS_ADVANCE_PAID


def normalize_business_type(value) -> str:
    value = _normalize_status_text(value).lower()
    if value in {"distribution", "dist"}:
        return "Distribution"
    if value in {"installation", "install", "inst"}:
        return "Installation"
    return ""


def is_confirmed(row: dict) -> bool:
    status = _normalize_status_text(row.get("Projet Situation"))
    return status.startswith("8.") or status.startswith("9.") or status.startswith("13") or status.startswith("payment remain")


def is_converted_distribution(row: dict) -> bool:
    return is_confirmed(row)


def is_lost(row: dict) -> bool:
    return _normalize_status_text(row.get("Projet Situation")).startswith("6.")


def build_title(row: dict, business_type: str = "Distribution") -> str:
    project = project_title(row, fallback="")
    client = clean_text(row.get("Client / Societe"))
    city = clean_text(row.get("Ville/Site"))
    if project:
        return project
    return " - ".join(part for part in [client, city] if part) or project or "Imported Opportunity"


def project_title(row: dict, fallback: str | None = None) -> str:
    title = clean_text(row.get("Nom projet"))
    if title:
        return title
    if fallback is not None:
        return clean_text(fallback)
    ref = clean_text(row.get("Réf Devis/Projet"))
    return _source_project_name(ref) if ref else "Imported Project"


def unique_project_title(row: dict, existing_project: str | None = None) -> str:
    title = project_title(row)
    existing = frappe.db.get_value("Project", {"project_name": title}, "name")
    if not existing or existing == existing_project:
        return title
    ref = clean_text(row.get("Réf Devis/Projet"))
    return f"{title} ({ref})" if ref else title


def _normalize_status_text(value) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip()


def _source_po_no(ref: str) -> str:
    return f"B2B-{clean_text(ref)}"


def _distribution_order_status(label: str) -> str:
    return f"{DISTRIBUTION_COMPANY} - {label}"


def _source_project_name(ref: str) -> str:
    return f"B2B Installation - {clean_text(ref)}"


def _default_item_group() -> str:
    if frappe.db.exists("Item Group", "Autres"):
        return "Autres"
    return frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"


def _default_uom() -> str:
    for candidate in ["Nos", "Unit", "PCE"]:
        if frappe.db.exists("UOM", candidate):
            return candidate
    return frappe.db.get_value("UOM", {}, "name") or "Nos"


def _safe_delivery_date(row: dict, transaction_date: str) -> str:
    delivery_date = parse_excel_date(row.get("Date de livraison"))
    if not delivery_date or not re.match(r"\d{4}-\d{2}-\d{2}$", delivery_date):
        return transaction_date
    if delivery_date < transaction_date:
        return transaction_date
    return delivery_date


def build_downstream_notes(row: dict, existing_notes: str | None = None) -> str:
    ref = clean_text(row.get("Réf Devis/Projet"))
    parts = [
        f"{REFERENCE_PREFIX}: {ref}",
        f"Excel Status: {clean_text(row.get('Projet Situation'))}",
        f"Date de confirmation: {parse_excel_date(row.get('Date de confirmation')) or clean_text(row.get('Date de confirmation'))}",
        f"Date de livraison: {parse_excel_date(row.get('Date de livraison')) or clean_text(row.get('Date de livraison'))}",
        f"Date de chargement Maroc: {parse_excel_date(row.get('Date de chargement Maroc')) or clean_text(row.get('Date de chargement Maroc'))}",
        f"Chargement Client: {parse_excel_date(row.get('Chargement Client')) or clean_text(row.get('Chargement Client'))}",
        f"Project Name: {clean_text(row.get('Nom projet'))}",
        f"Comments: {clean_text(row.get('COMMENTS'))}",
    ]
    source_block = "<br>".join(part for part in parts if not part.endswith(": ") and not part.endswith(": None"))
    existing_notes = existing_notes or ""
    if ref and f"{REFERENCE_PREFIX}: {ref}" in existing_notes:
        return existing_notes
    return f"{existing_notes}<br><br>{source_block}".strip("<br>") if existing_notes else source_block


def _is_company_opportunity(opportunity: str | None, company: str) -> bool:
    return bool(opportunity and frappe.db.get_value("Opportunity", opportunity, "company") == company)
