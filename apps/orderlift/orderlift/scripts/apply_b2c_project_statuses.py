from __future__ import annotations

import frappe
from frappe.utils import cint

from orderlift.orderlift_crm.status_config import PROJECT_STATUS_SEEDS


COMPANY = "Orderlift Maroc Installation"
DEFAULT_STATUS = "8. Avance 40% payée"


def run(dry_run: int = 1) -> dict:
    dry_run = cint(dry_run)
    desired = {row["label"] for row in PROJECT_STATUS_SEEDS}
    summary = {
        "dry_run": dry_run,
        "statuses_upserted": len(PROJECT_STATUS_SEEDS),
        "projects_moved_to_default": 0,
        "old_statuses_deleted": [],
        "old_statuses_blocked": [],
    }

    if not dry_run:
        upsert_project_statuses()
        summary["projects_moved_to_default"] = move_projects_to_default(desired)
        summary.update(delete_old_statuses(desired, dry_run=0))
        frappe.db.commit()
    else:
        summary["projects_moved_to_default"] = count_projects_outside_desired(desired)
        summary.update(delete_old_statuses(desired, dry_run=1))
    return summary


def upsert_project_statuses() -> None:
    for row in PROJECT_STATUS_SEEDS:
        name = row["label"]
        doc = frappe.get_doc("Project Status", name) if frappe.db.exists("Project Status", name) else frappe.new_doc("Project Status")
        doc.status_label = name
        if doc.meta.get_field("company"):
            doc.company = row.get("company") or COMPANY
        doc.sequence = row["sequence"]
        doc.color = row["color"]
        doc.is_active = 1
        doc.is_default = row["is_default"]
        doc.applies_distribution = row["distribution"]
        doc.applies_installation = row["installation"]
        if frappe.db.exists("Project Status", name):
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)


def count_projects_outside_desired(desired: set[str]) -> int:
    return frappe.db.count("Project", {"custom_project_status": ["not in", sorted(desired)]})


def move_projects_to_default(desired: set[str]) -> int:
    rows = frappe.get_all(
        "Project",
        filters={"custom_project_status": ["not in", sorted(desired)]},
        fields=["name", "custom_project_status"],
        limit_page_length=0,
    )
    for row in rows:
        frappe.db.set_value("Project", row.name, "custom_project_status", DEFAULT_STATUS, update_modified=False)
    return len(rows)


def delete_old_statuses(desired: set[str], dry_run: int = 1) -> dict:
    deleted = []
    blocked = []
    for status in frappe.get_all("Project Status", pluck="name", limit_page_length=0):
        if status in desired:
            continue
        links = frappe.get_all("Project", filters={"custom_project_status": status}, pluck="name", limit=5)
        if links:
            blocked.append({"status": status, "linked_projects": links})
            continue
        deleted.append(status)
        if not dry_run:
            frappe.delete_doc("Project Status", status, ignore_permissions=True, force=True)
    return {"old_statuses_deleted": deleted, "old_statuses_blocked": blocked}
