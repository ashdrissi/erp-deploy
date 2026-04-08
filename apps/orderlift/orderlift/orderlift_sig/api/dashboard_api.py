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

    geocoded = frappe.db.count(
        "Project",
        filters={
            "custom_latitude": ["not in", ["", None, 0]],
            "status": ["!=", "Cancelled"],
        },
    )

    # ── Projects by type ──────────────────────────────────────
    by_type = frappe.db.sql(
        """
        SELECT COALESCE(custom_project_type_ol, 'Unspecified') AS project_type,
               COUNT(*) AS cnt
        FROM `tabProject`
        WHERE status != 'Cancelled'
        GROUP BY project_type
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )

    # ── Projects by QC status ─────────────────────────────────
    by_qc = frappe.db.sql(
        """
        SELECT COALESCE(custom_qc_status, 'Not Started') AS qc_status,
               COUNT(*) AS cnt
        FROM `tabProject`
        WHERE status != 'Cancelled'
        GROUP BY qc_status
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )

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
