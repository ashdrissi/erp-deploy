from __future__ import annotations

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Whitelisted API methods (called from JS)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def apply_qc_template(project_name: str, template_name: str) -> dict:
    """
    Copy items from QCChecklistTemplate into the Project's custom_qc_checklist
    child table.  Existing rows are replaced so re-applying is safe.

    Returns a dict with the updated QC status.
    """
    project = frappe.get_doc("Project", project_name)
    template = frappe.get_doc("QC Checklist Template", template_name)

    # Replace existing checklist rows
    project.set("custom_qc_checklist", [])
    for tpl_item in template.items:
        project.append("custom_qc_checklist", {
            "item_code": tpl_item.item_code,
            "description": tpl_item.description,
            "category": tpl_item.category,
            "is_mandatory": tpl_item.is_mandatory,
            "is_verified": 0,
        })

    project.custom_qc_template = template_name
    _set_qc_status(project)
    project.save(ignore_permissions=False)

    return {
        "qc_status": project.custom_qc_status,
        "total_items": len(project.custom_qc_checklist),
    }


@frappe.whitelist()
def sync_qc_item_verification(
    project_name: str,
    row_name: str,
    is_verified: int,
    remarks: str | None = None,
) -> dict:
    """
    Toggle is_verified on a single Installation QC Item row and
    recalculate custom_qc_status on the parent Project.

    Returns updated QC status and progress counts.
    """
    project = frappe.get_doc("Project", project_name)

    row = next((r for r in project.custom_qc_checklist if r.name == row_name), None)
    if not row:
        frappe.throw(_("QC item {0} not found on project {1}").format(row_name, project_name))

    _apply_qc_row_state(
        row,
        is_verified=bool(int(is_verified)),
        remarks=remarks,
        user=frappe.session.user,
        timestamp=frappe.utils.now_datetime(),
    )

    _set_qc_status(project)
    project.save(ignore_permissions=False)

    verified = sum(1 for r in project.custom_qc_checklist if r.is_verified)
    total = len(project.custom_qc_checklist)
    return {
        "qc_status": project.custom_qc_status,
        "verified": verified,
        "total": total,
    }


@frappe.whitelist()
def save_qc_checklist(project_name: str, rows: list[dict] | str) -> dict:
    """
    Persist QC checklist verification state and remarks in one transaction.
    Used by the mobile QC page to save the full checklist reliably.
    """
    payload = frappe.parse_json(rows) if isinstance(rows, str) else rows
    if not isinstance(payload, list):
        frappe.throw(_("QC checklist payload must be a list of rows."))

    project = frappe.get_doc("Project", project_name)
    project_rows = {row.name: row for row in (project.custom_qc_checklist or [])}
    timestamp = frappe.utils.now_datetime()
    user = frappe.session.user

    for entry in payload:
        row_name = (entry or {}).get("name")
        if not row_name:
            continue

        row = project_rows.get(row_name)
        if not row:
            frappe.throw(_("QC item {0} not found on project {1}").format(row_name, project_name))

        _apply_qc_row_state(
            row,
            is_verified=bool((entry or {}).get("is_verified")),
            remarks=(entry or {}).get("remarks"),
            user=user,
            timestamp=timestamp,
        )

    _set_qc_status(project)
    project.save(ignore_permissions=False)

    verified = sum(1 for r in project.custom_qc_checklist if r.is_verified)
    total = len(project.custom_qc_checklist)
    return {
        "qc_status": project.custom_qc_status,
        "verified": verified,
        "total": total,
    }


@frappe.whitelist()
def calculate_qc_status(project_name: str) -> str:
    """
    Recalculate and save QC status for a project.
    Returns the new status string.
    """
    project = frappe.get_doc("Project", project_name)
    _set_qc_status(project)
    project.save(ignore_permissions=False)
    return project.custom_qc_status


@frappe.whitelist()
def duplicate_qc_template(source_name: str, new_name: str) -> str:
    """
    Duplicate a QC Checklist Template under a new name.
    Returns the new template name.
    """
    source = frappe.get_doc("QC Checklist Template", source_name)
    new_doc = frappe.copy_doc(source)
    new_doc.template_name = new_name
    new_doc.insert(ignore_permissions=False)
    return new_doc.name


# ---------------------------------------------------------------------------
# Doc event hooks (called from hooks.py)
# ---------------------------------------------------------------------------

def on_project_save(doc, method=None):
    """
    Recalculate QC status whenever the Project is saved.
    No extra save() — Frappe will persist the value in the same transaction.
    """
    _set_qc_status(doc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _set_qc_status(project) -> None:
    """
    Compute custom_qc_status in-place on *project* (no save).

    Rules:
      - No checklist rows → "Not Started"
      - All verified → "Complete"
      - Any mandatory item unverified → "Blocked"
      - Some verified → "In Progress"
      - None verified → "Not Started"
    """
    rows = project.custom_qc_checklist or []
    if not rows:
        project.custom_qc_status = "Not Started"
        return

    total = len(rows)
    verified = sum(1 for r in rows if r.is_verified)
    has_unverified_mandatory = any(r.is_mandatory and not r.is_verified for r in rows)

    if verified == total:
        project.custom_qc_status = "Complete"
    elif has_unverified_mandatory and verified > 0:
        project.custom_qc_status = "Blocked"
    elif verified > 0:
        project.custom_qc_status = "In Progress"
    else:
        project.custom_qc_status = "Not Started"


def _apply_qc_row_state(row, is_verified: bool, remarks: str | None, user: str, timestamp) -> None:
    row.is_verified = int(is_verified)
    row.remarks = (remarks or "").strip()
    if row.is_verified:
        row.verified_by = user
        row.verified_on = timestamp
    else:
        row.verified_by = None
        row.verified_on = None
