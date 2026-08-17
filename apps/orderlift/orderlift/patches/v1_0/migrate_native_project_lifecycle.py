from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


LEGACY_SALES_ORDER_PROJECT = "custom_installation_project"
LEGACY_PROJECT_TYPE = "custom_project_type_ol"
OPPORTUNITY_PROJECT_TYPE = "custom_project_type"


def execute() -> None:
    _migrate()


def run(dry_run: int = 1) -> dict:
    dry_run = cint(dry_run)
    summary = diagnose()
    if dry_run:
        summary["dry_run"] = 1
        return summary
    _migrate(summary)
    frappe.db.commit()
    summary["dry_run"] = 0
    return summary


def diagnose() -> dict:
    sales_order_conflicts = _rows(
        """
        SELECT name, project, custom_installation_project AS legacy_project
        FROM `tabSales Order`
        WHERE COALESCE(project, '') != ''
          AND COALESCE(custom_installation_project, '') != ''
          AND project != custom_installation_project
        ORDER BY name
        """
        if _has_column("Sales Order", LEGACY_SALES_ORDER_PROJECT)
        else ""
    )
    opportunity_type_conflicts = _rows(
        """
        SELECT name, custom_project_type AS project_type,
               custom_project_type_ol AS legacy_project_type
        FROM `tabOpportunity`
        WHERE COALESCE(custom_project_type, '') != ''
          AND COALESCE(custom_project_type_ol, '') != ''
          AND custom_project_type != custom_project_type_ol
        ORDER BY name
        """
        if _has_column("Opportunity", OPPORTUNITY_PROJECT_TYPE)
        and _has_column("Opportunity", LEGACY_PROJECT_TYPE)
        else ""
    )
    project_type_conflicts = _rows(
        """
        SELECT name, project_type, custom_project_type_ol AS legacy_project_type
        FROM `tabProject`
        WHERE COALESCE(project_type, '') != ''
          AND COALESCE(custom_project_type_ol, '') != ''
          AND project_type != custom_project_type_ol
        ORDER BY name
        """
        if _has_column("Project", LEGACY_PROJECT_TYPE)
        else ""
    )
    return {
        "sales_orders_to_migrate": _count(
            "Sales Order", f"COALESCE(project, '') = '' AND COALESCE({LEGACY_SALES_ORDER_PROJECT}, '') != ''"
        )
        if _has_column("Sales Order", LEGACY_SALES_ORDER_PROJECT)
        else 0,
        "projects_to_migrate": _count(
            "Project", f"COALESCE(project_type, '') = '' AND COALESCE({LEGACY_PROJECT_TYPE}, '') != ''"
        )
        if _has_column("Project", LEGACY_PROJECT_TYPE)
        else 0,
        "opportunities_to_migrate": _count(
            "Opportunity",
            f"COALESCE({OPPORTUNITY_PROJECT_TYPE}, '') = '' AND COALESCE({LEGACY_PROJECT_TYPE}, '') != ''",
        )
        if _has_column("Opportunity", OPPORTUNITY_PROJECT_TYPE)
        and _has_column("Opportunity", LEGACY_PROJECT_TYPE)
        else _count("Opportunity", f"COALESCE({LEGACY_PROJECT_TYPE}, '') != ''")
        if _has_column("Opportunity", LEGACY_PROJECT_TYPE)
        else 0,
        "sales_order_conflicts": sales_order_conflicts,
        "opportunity_type_conflicts": opportunity_type_conflicts,
        "project_type_conflicts_preserved": project_type_conflicts,
        "historical_project_types": _historical_project_types(),
    }


def _migrate(summary: dict | None = None) -> None:
    summary = summary or diagnose()
    blocking = [
        *(summary.get("sales_order_conflicts") or []),
        *(summary.get("opportunity_type_conflicts") or []),
    ]
    if blocking:
        names = ", ".join(row.get("name") for row in blocking[:10])
        frappe.throw(
            "Native Project lifecycle migration found conflicting authoritative values. "
            f"Resolve these records before migrating: {names}"
        )

    _ensure_project_types(summary.get("historical_project_types") or [])
    _ensure_opportunity_project_type_field()

    if _has_column("Sales Order", LEGACY_SALES_ORDER_PROJECT):
        frappe.db.sql(
            f"""
            UPDATE `tabSales Order`
            SET project = {LEGACY_SALES_ORDER_PROJECT}
            WHERE COALESCE(project, '') = ''
              AND COALESCE({LEGACY_SALES_ORDER_PROJECT}, '') != ''
            """
        )
    if _has_column("Project", LEGACY_PROJECT_TYPE):
        frappe.db.sql(
            f"""
            UPDATE `tabProject`
            SET project_type = {LEGACY_PROJECT_TYPE}
            WHERE COALESCE(project_type, '') = ''
              AND COALESCE({LEGACY_PROJECT_TYPE}, '') != ''
            """
        )
    if _has_column("Opportunity", LEGACY_PROJECT_TYPE):
        frappe.db.sql(
            f"""
            UPDATE `tabOpportunity`
            SET {OPPORTUNITY_PROJECT_TYPE} = {LEGACY_PROJECT_TYPE}
            WHERE COALESCE({OPPORTUNITY_PROJECT_TYPE}, '') = ''
              AND COALESCE({LEGACY_PROJECT_TYPE}, '') != ''
            """
        )


def _ensure_opportunity_project_type_field() -> None:
    create_custom_fields(
        {
            "Opportunity": [
                {
                    "fieldname": OPPORTUNITY_PROJECT_TYPE,
                    "label": "Project Type",
                    "fieldtype": "Link",
                    "options": "Project Type",
                    "insert_after": "custom_sig_section",
                    "in_standard_filter": 1,
                }
            ]
        },
        update=True,
    )


def _ensure_project_types(values: list[str]) -> None:
    if not frappe.db.exists("DocType", "Project Type"):
        return
    for value in values:
        if frappe.db.exists("Project Type", value):
            continue
        doc = frappe.new_doc("Project Type")
        doc.project_type = value
        doc.insert(ignore_permissions=True)


def _historical_project_types() -> list[str]:
    values = set()
    for doctype, fieldname in (
        ("Project", LEGACY_PROJECT_TYPE),
        ("Opportunity", LEGACY_PROJECT_TYPE),
        ("QC Checklist Template", "project_type"),
    ):
        if not _has_column(doctype, fieldname):
            continue
        rows = frappe.db.sql(
            f"SELECT DISTINCT `{fieldname}` AS value FROM `tab{doctype}` "
            f"WHERE COALESCE(`{fieldname}`, '') != ''",
            as_dict=True,
        )
        values.update((row.get("value") or "").strip() for row in rows)
    return sorted(value for value in values if value)


def _count(doctype: str, condition: str) -> int:
    rows = frappe.db.sql(f"SELECT COUNT(*) AS count FROM `tab{doctype}` WHERE {condition}", as_dict=True)
    return cint(rows[0].get("count")) if rows else 0


def _rows(query: str) -> list[dict]:
    return frappe.db.sql(query, as_dict=True) if query else []


def _has_column(doctype: str, fieldname: str) -> bool:
    has_column = getattr(frappe.db, "has_column", None)
    return bool(has_column and has_column(doctype, fieldname))
