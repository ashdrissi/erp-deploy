from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_dashboard_data() -> dict:
    """
    Aggregate KPIs and project lists for the SIG dashboard.
    """
    projects = frappe.get_list(
        "Project",
        filters={"status": ["!=", "Cancelled"]},
        fields=["custom_project_type_ol", "custom_qc_status", "custom_latitude"],
        limit_page_length=0,
    )

    total_projects = len(projects)
    open_projects = len(_project_names({"status": "Open"}))
    complete_projects = len(_project_names({"status": "Completed", "custom_qc_status": "Complete"}))
    blocked_qc = len(_project_names({"custom_qc_status": "Blocked", "status": ["!=", "Completed"]}))

    geocoded = sum(1 for row in projects if row.get("custom_latitude") not in (None, 0, 0.0, ""))
    by_type = _group_counts(projects, "custom_project_type_ol", "Unspecified", "project_type")
    by_qc = _group_counts(projects, "custom_qc_status", "Not Started", "qc_status")

    # ── Recent active projects ────────────────────────────────
    recent_projects = _serialize_project_rows(
        frappe.get_list(
            "Project",
            filters={"status": ["not in", ["Cancelled", "Completed"]]},
            fields=[
                "name", "project_name", "status", "customer", "custom_project_type_ol",
                "custom_qc_status", "custom_city", "custom_latitude", "custom_longitude", "modified",
            ],
            order_by="modified desc",
            limit_page_length=20,
        )
    )

    # ── Blocked projects (need attention) ────────────────────
    blocked_projects = _serialize_project_rows(
        frappe.get_list(
            "Project",
            filters={"custom_qc_status": "Blocked", "status": ["not in", ["Cancelled", "Completed"]]},
            fields=[
                "name", "project_name", "status", "customer", "custom_project_type_ol",
                "custom_qc_status", "custom_city", "modified",
            ],
            order_by="modified asc",
            limit_page_length=10,
        )
    )

    return {
        "kpis": {
            "total_projects": total_projects,
            "open_projects": open_projects,
            "complete_projects": complete_projects,
            "blocked_qc": blocked_qc,
            "geocoded": geocoded,
        },
        "by_type": by_type,
        "by_qc": by_qc,
        "recent_projects": recent_projects,
        "blocked_projects": blocked_projects,
    }


def _group_counts(rows: list[dict], source_key: str, default_label: str, output_key: str) -> list[dict]:
    counts: dict[str, int] = {}
    for row in rows:
        value = (row.get(source_key) or "").strip() or default_label
        counts[value] = counts.get(value, 0) + 1

    return [
        {output_key: label, "cnt": count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _project_names(filters: dict) -> list[str]:
    return frappe.get_list("Project", filters=filters, pluck="name", limit_page_length=0)


def _serialize_project_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            "name": row.get("name"),
            "project_name": row.get("project_name"),
            "status": row.get("status"),
            "customer": row.get("customer"),
            "project_type": row.get("custom_project_type_ol"),
            "qc_status": row.get("custom_qc_status"),
            "city": row.get("custom_city"),
            "latitude": row.get("custom_latitude"),
            "longitude": row.get("custom_longitude"),
            "modified": row.get("modified"),
        })
    return out


@frappe.whitelist(allow_guest=False)
def get_qc_checklist(project_name: str) -> dict:
    """
    Return the full QC checklist for a project.
    Used by the mobile QC page.
    """
    project = frappe.get_doc("Project", project_name)
    project.check_permission("read")
    rows = []
    for r in (project.custom_qc_checklist or []):
        rows.append({
            "name":        r.name,
            "item_code":   r.item_code,
            "description": r.description,
            "category":    r.category,
            "is_mandatory": r.is_mandatory,
            "is_verified":  r.is_verified,
            "verified_by":  r.verified_by,
            "verified_on":  str(r.verified_on) if r.verified_on else None,
            "remarks":      r.remarks,
        })

    return {
        "project_name": project.name,
        "project_display": project.project_name,
        "customer": project.customer,
        "qc_status": project.custom_qc_status,
        "city": project.custom_city,
        "project_type": project.custom_project_type_ol,
        "rows": rows,
    }
