from __future__ import annotations

import frappe

from orderlift.patches.v1_0.migrate_native_project_lifecycle import (
    LEGACY_PROJECT_TYPE,
    LEGACY_SALES_ORDER_PROJECT,
    diagnose,
)


def execute() -> None:
    summary = diagnose()
    if summary.get("sales_order_conflicts") or summary.get("sales_orders_to_migrate"):
        frappe.throw("Cannot retire custom_installation_project before all Sales Orders match native project.")
    if summary.get("opportunity_type_conflicts") or summary.get("opportunities_to_migrate"):
        frappe.throw("Cannot retire the Opportunity legacy Project Type before all values are migrated.")
    if summary.get("projects_to_migrate"):
        frappe.throw("Cannot retire the Project legacy Project Type before all values are migrated.")

    _delete_custom_field("Sales Order", LEGACY_SALES_ORDER_PROJECT)
    _delete_custom_field("Opportunity", LEGACY_PROJECT_TYPE)

    if summary.get("project_type_conflicts_preserved"):
        _retire_custom_field("Project", LEGACY_PROJECT_TYPE, "Legacy Project Type (Historical)")
    else:
        _delete_custom_field("Project", LEGACY_PROJECT_TYPE)


def _delete_custom_field(doctype: str, fieldname: str) -> None:
    name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
    if name:
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


def _retire_custom_field(doctype: str, fieldname: str, label: str) -> None:
    name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
    if not name:
        return
    doc = frappe.get_doc("Custom Field", name)
    doc.label = label
    doc.hidden = 1
    doc.read_only = 1
    doc.in_list_view = 0
    doc.in_standard_filter = 0
    doc.save(ignore_permissions=True)
