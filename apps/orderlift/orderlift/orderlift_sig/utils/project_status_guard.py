from __future__ import annotations

import frappe
from frappe import _


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
    If a linked installation project exists and its QC status is Blocked,
    post a non-blocking warning on the submitted SO.
    """
    project_name = doc.get("custom_installation_project")
    if not project_name:
        return

    qc_status = frappe.db.get_value("Project", project_name, "custom_qc_status")
    if qc_status == "Blocked":
        frappe.msgprint(
            _("Warning: the linked installation project <b>{0}</b> has a "
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
def create_project_from_sales_order(sales_order_name: str) -> str:
    """
    Create an ERPNext Project pre-filled with data from a Sales Order.
    Links the project back to the SO via custom_installation_project.
    Returns the new Project name.
    """
    so = frappe.get_doc("Sales Order", sales_order_name)

    # Prevent duplicate projects
    existing = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_installation_project"
    )
    if existing:
        frappe.throw(
            _("An installation project already exists for this Sales Order: "
              "<b>{0}</b>").format(existing),
            title=_("Duplicate Project"),
        )

    project = frappe.new_doc("Project")
    project.project_name = "Install — {0} — {1}".format(so.customer, so.name)
    project.customer = so.customer
    project.expected_start_date = so.delivery_date or frappe.utils.today()
    project.status = "Open"
    project.notes = "Auto-created from Sales Order {0}".format(so.name)

    # SIG fields
    project.custom_project_type_ol = "New Installation"
    project.custom_qc_status = "Not Started"

    # Copy delivery address if available
    if so.shipping_address_name:
        addr = frappe.db.get_value(
            "Address",
            so.shipping_address_name,
            ["address_line1", "city"],
            as_dict=True,
        )
        if addr:
            project.custom_site_address = addr.get("address_line1", "")
            project.custom_city = addr.get("city", "")

    project.insert(ignore_permissions=False)

    # Back-link on Sales Order
    frappe.db.set_value(
        "Sales Order", sales_order_name,
        "custom_installation_project", project.name
    )

    frappe.msgprint(
        "Installation project <b>{0}</b> created successfully.".format(project.name),
        title="Project Created",
        indicator="green",
        alert=True,
    )
    return project.name
