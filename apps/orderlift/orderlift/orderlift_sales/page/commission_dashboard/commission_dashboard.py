"""Commission Dashboard backend API."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate


@frappe.whitelist()
def get_dashboard_data():
    rows = _get_commission_rows()
    return {"rows": rows}


@frappe.whitelist()
def update_commission(name, status=None, payout_state=None, payment_reference=None, notes=None):
    commission = frappe.get_doc("Sales Commission", name)
    if commission.docstatus != 1:
        frappe.throw(_("Commission must be submitted before it can be updated."))
    if commission.status == "Cancelled":
        frappe.throw(_("Cancelled commissions cannot be updated from the dashboard."))

    next_status = _normalize_status(status or commission.status)
    payout_state = (payout_state or "").strip()

    if payout_state == "Paid":
        next_status = "Paid"
    elif payout_state == "Unpaid" and next_status == "Paid":
        next_status = "To Pay"

    if next_status == "Paid":
        if notes is not None:
            commission.notes = notes or ""
            commission.save(ignore_permissions=True)
            commission.reload()
        if commission.status != "Paid" or payment_reference is not None:
            commission.mark_as_paid(payment_reference=payment_reference or commission.payment_reference)
            commission.reload()
        if notes is not None and commission.notes != (notes or ""):
            commission.notes = notes or ""
            commission.save(ignore_permissions=True)
    else:
        commission.status = next_status
        commission.payment_date = None
        if payment_reference is not None:
            commission.payment_reference = payment_reference or ""
        if notes is not None:
            commission.notes = notes or ""
        commission.save(ignore_permissions=True)

    return {"ok": True, "row": _build_commission_row(frappe.get_doc("Sales Commission", name), _get_sales_order_payment_map([commission.sales_order]), _get_salesperson_quote_counts())}


def _get_commission_rows():
    if not frappe.db.exists("DocType", "Sales Commission"):
        return []

    commissions = frappe.get_all(
        "Sales Commission",
        filters={"docstatus": 1},
        fields=[
            "name",
            "salesperson",
            "salesperson_name",
            "customer",
            "customer_name",
            "sales_order",
            "sales_invoice",
            "status",
            "commission_amount",
            "payment_reference",
            "payment_date",
            "notes",
            "posting_date",
        ],
        order_by="posting_date desc, modified desc",
        limit_page_length=2000,
    )
    order_map = _get_sales_order_payment_map([row.sales_order for row in commissions if row.sales_order])
    quote_counts = _get_salesperson_quote_counts()
    return [_build_commission_row(row, order_map, quote_counts) for row in commissions]


def _build_commission_row(row, order_map, quote_counts):
    order_info = order_map.get(row.sales_order or "", {})
    status = _normalize_status(row.status)
    salesperson = row.salesperson or ""
    customer = row.customer_name or row.customer or ""
    agent = row.salesperson_name or salesperson
    return {
        "name": row.name,
        "agent": agent,
        "salesperson": salesperson,
        "quotation_count": int(quote_counts.get(salesperson, 0)),
        "customer": customer,
        "sales_order": row.sales_order or "",
        "sales_invoice": row.sales_invoice or order_info.get("latest_invoice") or "",
        "status": status,
        "payout_state": "Paid" if status == "Paid" else "Unpaid",
        "commission_amount": flt(row.commission_amount or 0),
        "payment_reference": row.payment_reference or "",
        "payment_date": str(row.payment_date or ""),
        "note": row.notes or "",
        "order_paid": bool(order_info.get("is_paid")),
        "order_completed": bool(order_info.get("is_completed")),
        "order_delayed": bool(order_info.get("is_delayed")),
    }


def _get_salesperson_quote_counts():
    if not frappe.db.exists("DocType", "Quotation") or not frappe.db.has_column("Quotation Item", "source_sales_person"):
        return {}

    rows = frappe.db.sql(
        """
        SELECT qi.source_sales_person AS salesperson, COUNT(DISTINCT qi.parent) AS quote_count
        FROM `tabQuotation Item` qi
        INNER JOIN `tabQuotation` q ON q.name = qi.parent
        WHERE q.docstatus = 1 AND COALESCE(qi.source_sales_person, '') != ''
        GROUP BY qi.source_sales_person
        """,
        as_dict=True,
    )
    return {row.salesperson: int(row.quote_count or 0) for row in rows}


def _get_sales_order_payment_map(order_names):
    order_names = [name for name in set(order_names or []) if name]
    if not order_names or not frappe.db.exists("DocType", "Sales Order"):
        return {}

    orders = frappe.get_all(
        "Sales Order",
        filters={"name": ["in", order_names], "docstatus": 1},
        fields=["name", "transaction_date"],
    )
    by_order = {
        row.name: {
            "latest_invoice": "",
            "is_paid": False,
            "is_completed": False,
            "is_delayed": bool(row.transaction_date and getdate(row.transaction_date) < getdate(add_days(nowdate(), -14))),
            "has_invoice": False,
        }
        for row in orders
    }

    invoice_rows = frappe.db.sql(
        """
        SELECT sii.sales_order, si.name AS sales_invoice, si.outstanding_amount, si.due_date, si.posting_date
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1 AND sii.sales_order IN %(order_names)s
        ORDER BY si.posting_date DESC, si.modified DESC
        """,
        {"order_names": tuple(order_names)},
        as_dict=True,
    )

    grouped = defaultdict(list)
    for row in invoice_rows:
        grouped[row.sales_order].append(row)

    for sales_order, invoices in grouped.items():
        target = by_order.setdefault(sales_order, {"latest_invoice": "", "is_paid": False, "is_completed": False, "is_delayed": False, "has_invoice": False})
        target["has_invoice"] = True
        target["latest_invoice"] = invoices[0].sales_invoice if invoices else ""
        outstanding = [flt(inv.outstanding_amount or 0) for inv in invoices]
        fully_paid = invoices and all(value <= 0.0001 for value in outstanding)
        target["is_paid"] = bool(fully_paid)
        target["is_completed"] = bool(fully_paid)
        target["is_delayed"] = any(
            flt(inv.outstanding_amount or 0) > 0.0001 and inv.due_date and getdate(inv.due_date) < getdate(nowdate())
            for inv in invoices
        )

    return by_order


def _normalize_status(status):
    status = (status or "").strip()
    if status == "Pending":
        return "Approved"
    return status or "Approved"
