from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_dashboard_data() -> dict:
    """
    Aggregate KPIs and project lists for the SIG dashboard.
    """
    # ── KPI counts ────────────────────────────────────────────
    total_projects = frappe.db.count("Project", filters={"status": ["!=", "Cancelled"]})

    open_projects = frappe.db.count("Project", filters={"status": "Open"})

    complete_projects = frappe.db.count(
        "Project",
        filters={"status": "Completed", "custom_qc_status": "Complete"},
    )

    blocked_qc = frappe.db.count(
        "Project",
        filters={"custom_qc_status": "Blocked", "status": ["!=", "Completed"]},
    )

    projects = frappe.get_all(
        "Project",
        filters={"status": ["!=", "Cancelled"]},
        fields=["custom_project_type_ol", "custom_qc_status", "custom_latitude"],
        limit_page_length=0,
    )

    geocoded = sum(1 for row in projects if row.get("custom_latitude") not in (None, 0, 0.0, ""))
    by_type = _group_counts(projects, "custom_project_type_ol", "Unspecified", "project_type")
    by_qc = _group_counts(projects, "custom_qc_status", "Not Started", "qc_status")

    # ── Recent active projects ────────────────────────────────
    recent_projects = frappe.db.sql(
        """
        SELECT
            name, project_name, status, customer,
            custom_project_type_ol  AS project_type,
            custom_qc_status        AS qc_status,
            custom_city             AS city,
            custom_latitude         AS latitude,
            custom_longitude        AS longitude,
            modified
        FROM `tabProject`
        WHERE status NOT IN ('Cancelled', 'Completed')
        ORDER BY modified DESC
        LIMIT 20
        """,
        as_dict=True,
    )

    # ── Blocked projects (need attention) ────────────────────
    blocked_projects = frappe.db.sql(
        """
        SELECT
            name, project_name, status, customer,
            custom_project_type_ol  AS project_type,
            custom_qc_status        AS qc_status,
            custom_city             AS city,
            modified
        FROM `tabProject`
        WHERE custom_qc_status = 'Blocked'
          AND status NOT IN ('Cancelled', 'Completed')
        ORDER BY modified ASC
        LIMIT 10
        """,
        as_dict=True,
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


@frappe.whitelist(allow_guest=False)
def get_qc_checklist(project_name: str) -> dict:
    """
    Return the full QC checklist for a project.
    Used by the mobile QC page.
    """
    project = frappe.get_doc("Project", project_name)
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
