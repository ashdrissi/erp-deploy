"""Commission workflow.

Create commission records from submitted Sales Orders using quotation snapshot data.
Commissions stay Approved after Sales Order confirmation, move to To Pay when linked
Sales Invoices are fully paid, and become Paid only after payout.
"""

from __future__ import annotations

import frappe


def create_sales_order_commissions(doc, method=None):
    """Create or refresh Sales Commission records from a submitted Sales Order."""
    buckets = _build_sales_order_snapshot_commissions(doc)
    if not buckets:
        return

    for payload in buckets:
        existing_name = frappe.db.get_value(
            "Sales Commission",
            {"sales_order": payload["sales_order"], "salesperson": payload["salesperson"], "docstatus": ["<", 2]},
            "name",
        )
        if existing_name:
            commission = frappe.get_doc("Sales Commission", existing_name)
            if commission.status == "Paid":
                continue
            commission.company = payload["company"]
            commission.customer = payload["customer"]
            commission.project = payload["project"]
            commission.commission_rate = payload["commission_rate"]
            commission.base_amount = payload["base_amount"]
            commission.commission_amount = payload["commission_amount"]
            commission.status = "Approved"
            commission.sales_invoice = ""
            commission.save(ignore_permissions=True)
            if commission.docstatus == 0:
                commission.submit()
            continue

        commission = frappe.get_doc(payload)
        commission.insert(ignore_permissions=True)
        commission.submit()


def sync_commissions_from_invoice(doc, method=None):
    """Approve commissions only when linked Sales Order invoices are fully paid."""
    seen_orders = {
        item.sales_order
        for item in (doc.items or [])
        if getattr(item, "sales_order", None)
    }
    for sales_order_name in seen_orders:
        _sync_sales_order_commissions(sales_order_name)


def cancel_commissions(doc, method=None):
    """Re-evaluate linked commissions when an invoice is cancelled."""
    seen_orders = {
        item.sales_order
        for item in (doc.items or [])
        if getattr(item, "sales_order", None)
    }
    for sales_order_name in seen_orders:
        _sync_sales_order_commissions(sales_order_name)


def cancel_sales_order_commissions(doc, method=None):
    """Cancel unpaid commissions when the Sales Order is cancelled."""
    commissions = frappe.get_all(
        "Sales Commission",
        filters={"sales_order": doc.name, "docstatus": 1, "status": ["!", "Paid"]},
        pluck="name",
    )
    for name in commissions:
        frappe.get_doc("Sales Commission", name).cancel()


def _build_sales_order_snapshot_commissions(sales_order):
    results = {}

    for item in sales_order.items or []:
        quotation_item_name = getattr(item, "quotation_item", None)
        if not quotation_item_name:
            continue

        qitem = frappe.db.get_value(
            "Quotation Item",
            quotation_item_name,
            [
                "source_sales_person",
                "source_commission_rate",
                "source_commission_amount",
                "source_discount_amount",
                "qty",
            ],
            as_dict=True,
        ) or {}

        salesperson = qitem.get("source_sales_person")
        commission_amount = float(qitem.get("source_commission_amount") or 0)
        commission_rate = float(qitem.get("source_commission_rate") or 0)
        discount_amount = float(qitem.get("source_discount_amount") or 0)
        quotation_qty = float(qitem.get("qty") or 0)
        order_qty = float(getattr(item, "qty", 0) or 0)
        denominator = quotation_qty or order_qty or 1.0
        factor = order_qty / denominator if denominator else 0
        prorated_commission = commission_amount * factor
        prorated_discount = discount_amount * factor

        if not salesperson or not prorated_commission:
            continue

        key = (sales_order.name, salesperson)
        bucket = results.setdefault(
            key,
            {
                "doctype": "Sales Commission",
                "salesperson": salesperson,
                "sales_order": sales_order.name,
                "sales_invoice": "",
                "project": sales_order.project,
                "customer": sales_order.customer,
                "company": sales_order.company,
                "commission_rate": commission_rate,
                "base_amount": 0.0,
                "commission_amount": 0.0,
                "status": "Approved",
            },
        )
        bucket["base_amount"] += prorated_discount
        bucket["commission_amount"] += prorated_commission

    return list(results.values())


def _sync_sales_order_commissions(sales_order_name):
    invoice_names = frappe.get_all(
        "Sales Invoice Item",
        filters={"sales_order": sales_order_name, "docstatus": 1},
        pluck="parent",
    )
    invoice_names = list(dict.fromkeys(invoice_names))

    if not invoice_names:
        _update_commission_status(sales_order_name, status="Approved", sales_invoice="")
        return

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", invoice_names], "docstatus": 1},
        fields=["name", "outstanding_amount", "posting_date"],
        order_by="posting_date desc, modified desc",
    )
    fully_paid = invoices and all(float(inv.outstanding_amount or 0) <= 0.0001 for inv in invoices)

    if fully_paid:
        latest_invoice = invoices[0].name if invoices else ""
        _update_commission_status(sales_order_name, status="To Pay", sales_invoice=latest_invoice)
        return

    _update_commission_status(sales_order_name, status="Approved", sales_invoice="")


def _update_commission_status(sales_order_name, status, sales_invoice):
    commissions = frappe.get_all(
        "Sales Commission",
        filters={"sales_order": sales_order_name, "docstatus": 1, "status": ["!", "Paid"]},
        pluck="name",
    )
    for name in commissions:
        commission = frappe.get_doc("Sales Commission", name)
        commission.status = status
        commission.sales_invoice = sales_invoice or ""
        commission.save(ignore_permissions=True)
