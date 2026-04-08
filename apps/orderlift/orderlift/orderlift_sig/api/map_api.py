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

    conditions = ["(p.custom_latitude IS NOT NULL AND p.custom_latitude != 0)"]
    values = {}

    if filters.get("project_type"):
        conditions.append("p.custom_project_type_ol = %(project_type)s")
        values["project_type"] = filters["project_type"]

    if filters.get("qc_status"):
        conditions.append("p.custom_qc_status = %(qc_status)s")
        values["qc_status"] = filters["qc_status"]

    if filters.get("status"):
        conditions.append("p.status = %(status)s")
        values["status"] = filters["status"]

    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            p.name,
            p.project_name,
            p.status,
            p.customer,
            p.expected_start_date,
            p.expected_end_date,
            p.custom_project_type_ol  AS project_type,
            p.custom_qc_status        AS qc_status,
            p.custom_site_address     AS site_address,
            p.custom_city             AS city,
            p.custom_latitude         AS latitude,
            p.custom_longitude        AS longitude
        FROM `tabProject` p
        WHERE {where}
        ORDER BY p.modified DESC
        LIMIT 500
        """,
        values,
        as_dict=True,
    )
    return rows


@frappe.whitelist(allow_guest=False)
def get_project_qc_summary(project_name: str) -> dict:
    """
    Return QC checklist summary (counts by category + overall status) for a project.
    Used in the map popup detail panel.
    """
    project = frappe.get_doc("Project", project_name)
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
