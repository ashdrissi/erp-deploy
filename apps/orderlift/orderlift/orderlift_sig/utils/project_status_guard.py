from __future__ import annotations

import frappe
from frappe import _

from orderlift.orderlift_crm.classification import copy_crm_classification


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _project_has_qc(doc) -> bool:
    """Return True if the project has any QC checklist rows."""
    return bool(doc.get("custom_qc_checklist"))


# ---------------------------------------------------------------------------
# Doc event hooks — called from hooks.py
# ---------------------------------------------------------------------------

def before_project_status_change(doc, method=None):
    """
    Called on Project before_save.
    Block status → "Completed" when QC checklist is not fully verified.
    """
    if not _project_has_qc(doc):
        return

    if doc.status == "Completed" and doc.custom_qc_status != "Complete":
        frappe.throw(
            _("Cannot close project <b>{0}</b> — QC checklist is <b>{1}</b>. "
              "All mandatory items must be verified before completion.").format(
                  doc.name, doc.custom_qc_status or "Not Started"
            ),
            title=_("QC Incomplete"),
        )


def on_sales_order_submit(doc, method=None):
    """
    Called on Sales Order on_submit.
    If a linked project exists and its QC status is Blocked,
    post a non-blocking warning on the submitted SO.
    """
    project_name = doc.get("project")
    if not project_name:
        return

    qc_status = frappe.db.get_value("Project", project_name, "custom_qc_status")
    if qc_status == "Blocked":
        frappe.msgprint(
            _("Warning: the linked project <b>{0}</b> has a "
              "<b>Blocked</b> QC status. Please resolve QC issues before "
              "proceeding with delivery.").format(project_name),
            title=_("QC Warning"),
            indicator="orange",
            alert=True,
        )


# ---------------------------------------------------------------------------
# Whitelisted API — create a Project from a Sales Order
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_project_from_sales_order(sales_order_name: str) -> dict:
    """
    Create an ERPNext Project pre-filled with data from a Sales Order.
    Links the project back to the Sales Order through its native project field.

    A Sales Order belongs to only one project. When the order (or its source
    Opportunity) already has a project, no duplicate is created: the existing
    project is returned with a friendly "Project already created" message.

    Returns {"name": project_name, "already_exists": 0|1}.
    """
    frappe.db.sql(
        "SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE",
        (sales_order_name,),
    )
    so = frappe.get_doc("Sales Order", sales_order_name)
    so.check_permission("write")
    frappe.has_permission("Project", ptype="create", throw=True)

    if not so.company:
        frappe.throw(
            _("Sales Order <b>{0}</b> is missing Company, so a project cannot be created.").format(
                so.name
            ),
            title=_("Missing Company"),
        )

    # A Sales Order belongs to only one project: reuse the existing link.
    existing = (so.get("project") or "").strip()
    if not existing:
        opportunity = None
        if project_linkage_available():
            from orderlift.orderlift_crm.project_linkage import (
                _project_for_opportunity,
                sales_order_source_opportunity,
            )

            opportunity = sales_order_source_opportunity(so.name)
            if opportunity:
                existing = _project_for_opportunity(opportunity) or ""
        if existing and project_linkage_available():
            from orderlift.orderlift_crm.project_linkage import (
                link_sales_orders_to_project_as_system,
            )

            link_sales_orders_to_project_as_system(
                existing,
                [{"name": so.name}],
                expected_opportunity=opportunity,
            )
    if existing:
        frappe.msgprint(
            _("Project already created for Sales Order <b>{0}</b>: <b>{1}</b>").format(
                so.name, existing
            ),
            title=_("Project Already Created"),
            indicator="blue",
            alert=True,
        )
        return {"name": existing, "already_exists": 1}

    project = frappe.new_doc("Project")
    project.project_name = "{0} - {1}".format(so.customer, so.name)
    project.company = so.company
    project.customer = so.customer
    if project.meta.get_field("sales_order"):
        project.sales_order = so.name
    project.expected_start_date = so.delivery_date or frappe.utils.today()
    project.status = "Open"
    project.notes = "Auto-created from Sales Order {0}".format(so.name)

    # SIG fields
    project.custom_qc_status = "Not Started"
    copy_crm_classification(so, project)

    # Carry the source opportunity so the project fans out to sibling Sales
    # Orders / Quotations of the same opportunity (see project_linkage).
    opportunity = None
    if project.meta.get_field("custom_source_opportunity"):
        from orderlift.orderlift_crm.project_linkage import sales_order_source_opportunity

        opportunity = sales_order_source_opportunity(so.name)
        if opportunity:
            project.custom_source_opportunity = opportunity

    from orderlift.orderlift_crm.project_linkage import (
        _copy_source_context_to_project,
        link_sales_orders_to_project_as_system,
    )

    _copy_source_context_to_project(so, project)

    project.insert(ignore_permissions=False)

    link_sales_orders_to_project_as_system(
        project,
        [{"name": so.name}],
        expected_opportunity=opportunity,
    )

    frappe.msgprint(
        "Project <b>{0}</b> created successfully.".format(project.name),
        title="Project Created",
        indicator="green",
        alert=True,
    )
    return {"name": project.name, "already_exists": 0}


def project_linkage_available() -> bool:
    """True when the CRM project linkage module is installed (schema present)."""
    return bool(frappe.db.exists("DocType", "Project"))
