"""
Commission Calculator
---------------------
Creates and cancels Sales Commission records when a Sales Invoice
is submitted or cancelled.

Called via hooks.py doc_events on Sales Invoice.
"""

import frappe


def create_commissions(doc, method=None):
    """Create Sales Commission records on Sales Invoice submission.

    Handles invoices linked to multiple Sales Orders by collecting
    all unique SOs and creating one commission per salesperson per SO.
    """
    # Collect unique Sales Orders referenced in this invoice
    seen_orders = set()
    for item in doc.items:
        so_name = getattr(item, "sales_order", None)
        if so_name and so_name not in seen_orders:
            seen_orders.add(so_name)

    if not seen_orders:
        return

    for sales_order_name in seen_orders:
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        salesperson = sales_order.get("custom_salesperson") or None
        if not salesperson:
            continue

        commission_rate = frappe.db.get_value(
            "Sales Person", salesperson, "custom_commission_rate"
        ) or 0

        if not commission_rate:
            continue

        # Sum only the line totals that belong to this Sales Order
        so_total = sum(
            item.net_amount
            for item in doc.items
            if getattr(item, "sales_order", None) == sales_order_name
        )
        commission_amount = so_total * (commission_rate / 100)

        commission = frappe.get_doc(
            {
                "doctype": "Sales Commission",
                "salesperson": salesperson,
                "sales_order": sales_order_name,
                "sales_invoice": doc.name,
                "project": sales_order.project,
                "customer": sales_order.customer,
                "company": doc.company,
                "commission_rate": commission_rate,
                "base_amount": so_total,
                "commission_amount": commission_amount,
                "status": "Pending",
            }
        )
        commission.insert(ignore_permissions=True)
        commission.submit()


def cancel_commissions(doc, method=None):
    """Cancel linked Sales Commission records when invoice is cancelled.

    Only cancels commissions that haven't been paid yet.
    Uses proper doctype cancel flow for submitted documents.
    """
    commissions = frappe.get_all(
        "Sales Commission",
        filters={
            "sales_invoice": doc.name,
            "docstatus": 1,
            "status": ["!=", "Paid"],
        },
        fields=["name"],
    )
    for row in commissions:
        commission = frappe.get_doc("Sales Commission", row.name)
        commission.cancel()
