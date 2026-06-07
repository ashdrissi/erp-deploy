from __future__ import annotations

from collections import Counter

import frappe
from frappe.utils import cint

from orderlift.scripts.import_b2c_opportunities import (
    BUSINESS_TYPE,
    COMPANY,
    CRM_SEGMENT,
    clean_text,
    find_opportunity,
    is_confirmed,
    parse_excel_date,
    parse_workbook,
)


PROJECT_STATUS_ADVANCE_PAID = "8. Avance 40% payée"
PROJECT_TYPE = "New Installation"


def run(workbook_path: str, dry_run: int = 1) -> dict:
    dry_run = cint(dry_run)
    rows = parse_workbook(workbook_path)
    summary = {
        "dry_run": dry_run,
        "converted_rows": 0,
        "projects_created": 0,
        "projects_updated": 0,
        "skipped": [],
        "warnings": [],
        "project_status_counts": {},
    }

    ensure_project_status(dry_run=dry_run)
    status_counts = Counter()

    for row in rows:
        ref = clean_text(row.get("Réf Projet"))
        client = clean_text(row.get("Client"))
        if not is_confirmed(row):
            continue
        summary["converted_rows"] += 1
        if not client or client == "-":
            summary["skipped"].append({"ref": ref, "reason": "missing client"})
            continue

        opportunity = find_opportunity(ref)
        if not opportunity:
            summary["skipped"].append({"ref": ref, "reason": "opportunity not found"})
            continue

        try:
            result = upsert_project(opportunity, row, dry_run=dry_run)
            if result.get("created"):
                summary["projects_created"] += 1
            else:
                summary["projects_updated"] += 1
            status_counts[result.get("status") or PROJECT_STATUS_ADVANCE_PAID] += 1
        except Exception as exc:
            summary["warnings"].append({"ref": ref, "client": client, "error": str(exc)})

    if not dry_run:
        frappe.db.commit()
    summary["project_status_counts"] = dict(sorted(status_counts.items()))
    return summary


def upsert_project(opportunity: str, row: dict, dry_run: int = 1) -> dict:
    existing = find_project(opportunity, row)
    doc = frappe.get_doc("Project", existing) if existing else frappe.new_doc("Project")
    opp_doc = frappe.get_doc("Opportunity", opportunity)
    project_name = clean_text(row.get("Projet")) or clean_text(row.get("Réf Projet")) or opp_doc.get("title")

    doc.project_name = project_name
    doc.status = "Open"
    doc.company = COMPANY
    customer = resolve_project_customer(opp_doc)
    if customer and doc.meta.get_field("customer"):
        doc.customer = customer
    if doc.meta.get_field("custom_source_opportunity"):
        doc.custom_source_opportunity = opportunity
    if doc.meta.get_field("custom_project_status"):
        doc.custom_project_status = PROJECT_STATUS_ADVANCE_PAID
    if doc.meta.get_field("custom_crm_business_type"):
        doc.custom_crm_business_type = BUSINESS_TYPE
    if doc.meta.get_field("custom_crm_segment"):
        doc.custom_crm_segment = CRM_SEGMENT
    if doc.meta.get_field("custom_project_type_ol"):
        doc.custom_project_type_ol = PROJECT_TYPE
    if doc.meta.get_field("custom_city"):
        doc.custom_city = clean_text(row.get("Ville / Localisation"))
    confirmation_date = parse_excel_date(row.get("Date de confirmation"))
    if confirmation_date and doc.meta.get_field("expected_start_date"):
        doc.expected_start_date = confirmation_date
    delivery_date = parse_excel_date(row.get("Date de livraison"))
    if delivery_date and doc.meta.get_field("expected_end_date"):
        doc.expected_end_date = delivery_date
    doc.notes = build_project_notes(row, existing_notes=doc.get("notes"))

    if dry_run:
        return {"name": existing or project_name, "created": not bool(existing), "status": PROJECT_STATUS_ADVANCE_PAID}
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return {"name": doc.name, "created": not bool(existing), "status": PROJECT_STATUS_ADVANCE_PAID}


def find_project(opportunity: str, row: dict) -> str | None:
    if frappe.get_meta("Project").get_field("custom_source_opportunity"):
        existing = frappe.db.get_value("Project", {"custom_source_opportunity": opportunity}, "name")
        if existing:
            return existing
    project_name = clean_text(row.get("Projet"))
    if project_name:
        return frappe.db.get_value("Project", {"project_name": project_name, "company": COMPANY}, "name")
    return None


def resolve_project_customer(opportunity_doc) -> str | None:
    if opportunity_doc.get("opportunity_from") == "Customer" and frappe.db.exists("Customer", opportunity_doc.get("party_name")):
        return opportunity_doc.get("party_name")
    return None


def ensure_project_status(dry_run: int = 1) -> None:
    if not frappe.db.exists("DocType", "Project Status") or frappe.db.exists("Project Status", PROJECT_STATUS_ADVANCE_PAID):
        return
    if dry_run:
        return
    doc = frappe.new_doc("Project Status")
    doc.status_label = PROJECT_STATUS_ADVANCE_PAID
    doc.sequence = 10
    doc.color = "Blue"
    doc.is_active = 1
    doc.is_default = 1
    doc.applies_installation = 1
    doc.applies_distribution = 0
    doc.insert(ignore_permissions=True)


def build_project_notes(row: dict, existing_notes: str | None = None) -> str:
    ref = clean_text(row.get("Réf Projet"))
    parts = [
        f"Excel Ref: {ref}",
        f"Excel Opportunity Status: {clean_text(row.get('Situation Projet'))}",
        f"Date de confirmation: {parse_excel_date(row.get('Date de confirmation')) or clean_text(row.get('Date de confirmation'))}",
        f"Date de livraison: {parse_excel_date(row.get('Date de livraison')) or clean_text(row.get('Date de livraison'))}",
        f"Date de chargement Maroc: {parse_excel_date(row.get('Date de chargement Maroc')) or clean_text(row.get('Date de chargement Maroc'))}",
        f"Chargement Client: {parse_excel_date(row.get('Chargement Client')) or clean_text(row.get('Chargement Client'))}",
        f"Type de Paiement: {clean_text(row.get('Type de Paiement (Noir/déclaré)'))}",
        f"Installateur: {clean_text(row.get('Installateur'))}",
        f"Facture 1: {clean_text(row.get('Facture  1 Link (40%)'))}",
        f"Facture 2: {clean_text(row.get('Facture  2 Link (35%)'))}",
        f"Facture 3: {clean_text(row.get('Facture  3 Link (15%)'))}",
        f"Facture 4: {clean_text(row.get('Facture  4 Link (10%)'))}",
        f"Comments: {clean_text(row.get('COMMENTS'))}",
    ]
    source_block = "<br>".join(part for part in parts if not part.endswith(": ") and not part.endswith(": None"))
    existing_notes = existing_notes or ""
    if ref and f"Excel Ref: {ref}" in existing_notes:
        return existing_notes
    return f"{existing_notes}<br><br>{source_block}".strip("<br>") if existing_notes else source_block
