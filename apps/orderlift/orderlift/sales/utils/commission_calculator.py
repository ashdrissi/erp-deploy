"""
Commission Calculator
---------------------
Creates and cancels Sales Commission records when a Sales Invoice
is submitted or cancelled.

Called via hooks.py doc_events on Sales Invoice.
"""

import frappe


def create_commissions(doc, method=None):
    """Create Sales Commission records on Sales Invoice submission."""
    sales_order_name = doc.items[0].sales_order if doc.items else None
    if not sales_order_name:
        return

    sales_order = frappe.get_doc("Sales Order", sales_order_name)
    salesperson = sales_order.get("custom_salesperson") or None
    if not salesperson:
        return

    commission_rate = frappe.db.get_value(
        "Sales Person", salesperson, "custom_commission_rate"
    ) or 0

    if not commission_rate:
        return

    commission_amount = doc.net_total * (commission_rate / 100)

    commission = frappe.get_doc(
        {
            "doctype": "Sales Commission",
            "salesperson": salesperson,
            "sales_order": sales_order_name,
            "sales_invoice": doc.name,
            "project": sales_order.project,
            "commission_rate": commission_rate,
            "commission_amount": commission_amount,
            "status": "Pending",
        }
    )
    commission.insert(ignore_permissions=True)


def cancel_commissions(doc, method=None):
    """Cancel linked Sales Commission records when invoice is cancelled."""
    commissions = frappe.get_all(
        "Sales Commission",
        filters={"sales_invoice": doc.name, "status": ["!=", "Paid"]},
        fields=["name"],
    )
    for row in commissions:
        frappe.db.set_value("Sales Commission", row.name, "status", "Cancelled")
