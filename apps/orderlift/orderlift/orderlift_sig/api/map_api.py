from __future__ import annotations

import frappe


@frappe.whitelist(allow_guest=False)
def get_map_projects(filters: dict | str | None = None) -> list[dict]:
    """
    Return all projects that have geocoordinates, with SIG custom fields.
    Used by the /project-map web page.

    Optional filters dict keys:
      project_type  — matches custom_project_type_ol
      qc_status     — matches custom_qc_status
      status        — matches ERPNext Project.status
    """
    filters = frappe.parse_json(filters) if filters else {}
    if not isinstance(filters, dict):
        filters = {}

    project_filters = [["Project", "custom_latitude", "is", "set"], ["Project", "custom_latitude", "!=", 0]]

    if filters.get("project_type"):
        project_filters.append(["Project", "custom_project_type_ol", "=", filters["project_type"]])

    if filters.get("qc_status"):
        project_filters.append(["Project", "custom_qc_status", "=", filters["qc_status"]])

    if filters.get("status"):
        project_filters.append(["Project", "status", "=", filters["status"]])

    rows = frappe.get_list(
        "Project",
        filters=project_filters,
        fields=[
            "name", "project_name", "status", "customer", "expected_start_date", "expected_end_date",
            "custom_project_type_ol", "custom_qc_status", "custom_site_address", "custom_city",
            "custom_latitude", "custom_longitude",
        ],
        order_by="modified desc",
        limit_page_length=500,
    )
    return [
        {
            "name": row.get("name"),
            "project_name": row.get("project_name"),
            "status": row.get("status"),
            "customer": row.get("customer"),
            "expected_start_date": row.get("expected_start_date"),
            "expected_end_date": row.get("expected_end_date"),
            "project_type": row.get("custom_project_type_ol"),
            "qc_status": row.get("custom_qc_status"),
            "site_address": row.get("custom_site_address"),
            "city": row.get("custom_city"),
            "latitude": row.get("custom_latitude"),
            "longitude": row.get("custom_longitude"),
        }
        for row in rows
    ]


@frappe.whitelist(allow_guest=False)
def get_project_qc_summary(project_name: str) -> dict:
    """
    Return QC checklist summary (counts by category + overall status) for a project.
    Used in the map popup detail panel.
    """
    project = frappe.get_doc("Project", project_name)
    project.check_permission("read")
    rows = project.custom_qc_checklist or []

    total = len(rows)
    verified = sum(1 for r in rows if r.is_verified)
    mandatory_unverified = sum(1 for r in rows if r.is_mandatory and not r.is_verified)

    by_category: dict[str, dict] = {}
    for r in rows:
        cat = r.category or "Other"
        if cat not in by_category:
            by_category[cat] = {"total": 0, "verified": 0}
        by_category[cat]["total"] += 1
        if r.is_verified:
            by_category[cat]["verified"] += 1

    return {
        "project_name": project_name,
        "qc_status": project.custom_qc_status,
        "total": total,
        "verified": verified,
        "mandatory_unverified": mandatory_unverified,
        "pct": round((verified / total * 100) if total else 0),
        "by_category": by_category,
    }
