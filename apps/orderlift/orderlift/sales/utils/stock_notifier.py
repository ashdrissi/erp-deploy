"""
Stock Notifier
--------------
Notifies the Stock Manager role when a Sales Order is submitted,
prompting stock reservation validation.

Called via hooks.py doc_events on Sales Order.
"""

import frappe
from frappe import _


def notify_stock_manager(doc, method=None):
    """Send ERPNext notification to Stock Manager on Sales Order submit."""
    stock_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Stock Manager", "parenttype": "User"},
        fields=["parent"],
    )

    for user in stock_managers:
        frappe.publish_realtime(
            "eval_js",
            "frappe.show_alert({message: __('New Sales Order requires stock reservation: "
            + doc.name
            + "'), indicator: 'orange'})",
            user=user.parent,
        )

    # Also create a formal Notification Log
    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": _("Stock Reservation Required: {0}").format(doc.name),
            "for_user": stock_managers[0].parent if stock_managers else frappe.session.user,
            "type": "Alert",
            "document_type": "Sales Order",
            "document_name": doc.name,
        }
    ).insert(ignore_permissions=True)
