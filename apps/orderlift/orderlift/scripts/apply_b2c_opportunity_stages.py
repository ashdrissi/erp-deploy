from __future__ import annotations

from collections import Counter

import frappe
from frappe.utils import cint

from orderlift.orderlift_crm.status_config import OPPORTUNITY_STAGE_SEEDS
from orderlift.scripts.import_b2c_opportunities import clean_text, find_opportunity, parse_workbook


COMPANY = "Orderlift Maroc Installation"
DEFAULT_STAGE = "1. Demande Client"


def run(workbook_path: str, dry_run: int = 1) -> dict:
    dry_run = cint(dry_run)
    rows = parse_workbook(workbook_path)
    desired_stages = {row["label"] for row in OPPORTUNITY_STAGE_SEEDS}
    summary = {
        "dry_run": dry_run,
        "stages_upserted": len(OPPORTUNITY_STAGE_SEEDS),
        "old_stages_deleted": [],
        "old_stages_blocked": [],
        "opportunities_updated": 0,
        "opportunities_skipped": [],
        "stage_counts": {},
    }

    if not dry_run:
        upsert_excel_stages()

    stage_counts = Counter()
    for row in rows:
        ref = clean_text(row.get("Réf Projet"))
        client = clean_text(row.get("Client"))
        if not client or client == "-":
            summary["opportunities_skipped"].append({"ref": ref, "reason": "missing client"})
            continue

        stage = clean_text(row.get("Situation Projet")) or DEFAULT_STAGE
        if stage not in desired_stages:
            summary["opportunities_skipped"].append({"ref": ref, "reason": f"unknown stage: {stage}"})
            continue
        opportunity = find_opportunity(ref)
        if not opportunity:
            summary["opportunities_skipped"].append({"ref": ref, "reason": "opportunity not found"})
            continue

        stage_counts[stage] += 1
        if not dry_run:
            updates = {"sales_stage": stage, "status": "Lost" if stage == "6. Devis rejeté/annulé" else "Open"}
            frappe.db.set_value("Opportunity", opportunity, updates, update_modified=False)
        summary["opportunities_updated"] += 1

    if not dry_run:
        _move_remaining_opportunities_to_default(desired_stages)
        summary.update(delete_old_stages(desired_stages, dry_run=0))
        frappe.db.commit()
    else:
        summary.update(delete_old_stages(desired_stages, dry_run=1))

    summary["stage_counts"] = dict(sorted(stage_counts.items()))
    return summary


def upsert_excel_stages() -> None:
    for row in OPPORTUNITY_STAGE_SEEDS:
        name = row["label"]
        doc = frappe.get_doc("Sales Stage", name) if frappe.db.exists("Sales Stage", name) else frappe.new_doc("Sales Stage")
        doc.stage_name = name
        if doc.meta.get_field("custom_company"):
            doc.custom_company = row.get("company") or COMPANY
        if doc.meta.get_field("custom_sequence"):
            doc.custom_sequence = row["sequence"]
        if doc.meta.get_field("custom_color"):
            doc.custom_color = row["color"]
        if doc.meta.get_field("custom_is_active"):
            doc.custom_is_active = 1
        if doc.meta.get_field("custom_is_default"):
            doc.custom_is_default = row["is_default"]
        if doc.meta.get_field("custom_applies_distribution"):
            doc.custom_applies_distribution = row["distribution"]
        if doc.meta.get_field("custom_applies_installation"):
            doc.custom_applies_installation = row["installation"]
        if frappe.db.exists("Sales Stage", name):
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)


def delete_old_stages(desired_stages: set[str], dry_run: int = 1) -> dict:
    deleted = []
    blocked = []
    for stage in frappe.get_all("Sales Stage", pluck="name", limit_page_length=0):
        if stage in desired_stages:
            continue
        links = frappe.get_all("Opportunity", filters={"sales_stage": stage}, pluck="name", limit=5)
        if links:
            blocked.append({"stage": stage, "linked_opportunities": links})
            continue
        deleted.append(stage)
        if not dry_run:
            frappe.delete_doc("Sales Stage", stage, ignore_permissions=True, force=True)
    return {"old_stages_deleted": deleted, "old_stages_blocked": blocked}


def _move_remaining_opportunities_to_default(desired_stages: set[str]) -> None:
    rows = frappe.get_all(
        "Opportunity",
        filters={"sales_stage": ["not in", sorted(desired_stages)]},
        fields=["name", "sales_stage"],
        limit_page_length=0,
    )
    for row in rows:
        frappe.db.set_value("Opportunity", row.name, {"sales_stage": DEFAULT_STAGE, "status": "Open"}, update_modified=False)
