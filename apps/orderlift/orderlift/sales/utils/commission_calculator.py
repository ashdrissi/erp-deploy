"""Commission workflow.

Create commission records from submitted Sales Orders using quotation snapshot data.
Commissions stay Approved after Sales Order confirmation, move to To Pay when linked
Sales Invoices are fully paid, and become Paid only after payout.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

from orderlift.sales.utils.pricing_projection import calculate_agent_commission


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
            commission.flags.orderlift_commission_snapshot_update = True
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


def sync_commissions_from_payment_entry(doc, method=None):
    """Re-evaluate commissions when customer payments are submitted or cancelled."""
    invoice_names = _payment_entry_sales_invoices(doc)
    if not invoice_names:
        return

    sales_orders = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": ["in", invoice_names], "sales_order": ["!=", ""]},
        pluck="sales_order",
    )
    for sales_order_name in dict.fromkeys(name for name in sales_orders if name):
        _sync_sales_order_commissions(sales_order_name)


def reconcile_open_commissions():
    """Safety-net reconciliation for payment/reposting paths that bypass document hooks."""
    sales_orders = frappe.get_all(
        "Sales Commission",
        filters={
            "docstatus": 1,
            "status": ["in", ["Approved", "To Pay"]],
            "sales_order": ["!=", ""],
        },
        pluck="sales_order",
    )
    for sales_order_name in dict.fromkeys(name for name in sales_orders if name):
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
        filters={"sales_order": doc.name, "docstatus": 1, "status": ["!=", "Paid"]},
        pluck="name",
    )
    for name in commissions:
        frappe.get_doc("Sales Commission", name).cancel()


def _build_sales_order_snapshot_commissions(sales_order):
    results = {}

    for item in sales_order.items or []:
        quotation_item_name = getattr(item, "quotation_item", None) or getattr(item, "prevdoc_detail_docname", None)

        qitem = _quotation_item_commission_snapshot(quotation_item_name) if quotation_item_name else {}
        source = qitem or _row_snapshot(item)

        salesperson = source.get("source_sales_person")
        commission_rate = flt(source.get("source_commission_rate") or 0)
        order_qty = flt(getattr(item, "qty", 0) or 0)
        quotation_qty = flt(qitem.get("qty") or 0)
        denominator = quotation_qty or order_qty or 1.0
        factor = order_qty / denominator if denominator else 0
        commission_amount = flt(source.get("source_commission_amount") or 0)
        if commission_amount <= 0:
            recalculated = _calculate_snapshot_commission(source, denominator)
            commission_amount = flt(recalculated.get("commission_amount") or 0)
        prorated_commission = commission_amount * factor
        prorated_discount = _line_discount_amount(
            source.get("source_gross_sell_rate"),
            source.get("source_discounted_sell_rate"),
            order_qty,
        )

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
                "currency": getattr(sales_order, "currency", None) or "",
                "commission_rate": commission_rate,
                "base_amount": 0.0,
                "commission_amount": 0.0,
                "status": "Approved",
            },
        )
        bucket["base_amount"] += prorated_discount
        bucket["commission_amount"] += prorated_commission

    return list(results.values())


def _quotation_item_commission_snapshot(quotation_item_name):
    return frappe.db.get_value(
        "Quotation Item",
        quotation_item_name,
        [
            "source_sales_person",
            "source_commission_rate",
            "source_commission_amount",
            "source_discount_amount",
            "source_gross_sell_rate",
            "source_discounted_sell_rate",
            "source_max_discount_percent",
            "qty",
        ],
        as_dict=True,
    ) or {}


def _row_snapshot(item):
    get = getattr(item, "get", None)

    def value(fieldname, default=0):
        if callable(get):
            return get(fieldname) or default
        return getattr(item, fieldname, default) or default

    return {
        "source_sales_person": value("source_sales_person", ""),
        "source_commission_rate": value("source_commission_rate"),
        "source_commission_amount": value("source_commission_amount"),
        "source_discount_amount": value("source_discount_amount"),
        "source_gross_sell_rate": value("source_gross_sell_rate") or value("price_list_rate"),
        "source_discounted_sell_rate": value("source_discounted_sell_rate") or value("rate"),
        "source_max_discount_percent": value("source_max_discount_percent"),
    }


def _calculate_snapshot_commission(source, qty):
    price_list_unit = flt(source.get("source_gross_sell_rate") or 0)
    actual_unit = flt(source.get("source_discounted_sell_rate") or 0)
    if price_list_unit <= 0 or actual_unit <= 0:
        return {}
    try:
        commission = calculate_agent_commission(
            price_list_unit_price=price_list_unit,
            actual_unit_price=actual_unit,
            qty=qty,
            max_discount_percent=flt(source.get("source_max_discount_percent") or 0),
            commission_rate=flt(source.get("source_commission_rate") or 0),
            enforce_discount_cap=False,
        )
    except ValueError:
        return {}
    return {
        "commission_amount": commission.get("commission_amount") or 0,
        "discount_amount": _line_discount_amount(price_list_unit, actual_unit, qty),
    }


def _line_discount_amount(gross_unit_price, actual_unit_price, qty):
    return max(flt(gross_unit_price) - flt(actual_unit_price), 0) * flt(qty)


def _payment_entry_sales_invoices(payment_entry):
    invoice_names = []
    for reference in getattr(payment_entry, "references", None) or []:
        if getattr(reference, "reference_doctype", None) != "Sales Invoice":
            continue
        name = (getattr(reference, "reference_name", None) or "").strip()
        if name and name not in invoice_names:
            invoice_names.append(name)
    return invoice_names


def _sales_order_is_fully_billed(sales_order_name):
    per_billed = frappe.db.get_value("Sales Order", sales_order_name, "per_billed")
    return flt(per_billed or 0) >= 99.99


def sales_order_commission_eligibility(sales_order_name):
    """Return the persisted payout gate for one submitted Sales Order."""
    if not sales_order_name or not _sales_order_is_fully_billed(sales_order_name):
        return {"eligible": False, "latest_invoice": ""}

    invoice_names = frappe.get_all(
        "Sales Invoice Item",
        filters={"sales_order": sales_order_name, "docstatus": 1},
        pluck="parent",
    )
    invoice_names = list(dict.fromkeys(invoice_names))
    if not invoice_names:
        return {"eligible": False, "latest_invoice": ""}

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", invoice_names], "docstatus": 1},
        fields=["name", "outstanding_amount", "posting_date"],
        order_by="posting_date desc, modified desc",
    )
    fully_paid = bool(invoices) and all(flt(inv.outstanding_amount or 0) <= 0.0001 for inv in invoices)
    return {
        "eligible": fully_paid,
        "latest_invoice": invoices[0].name if fully_paid and invoices else "",
    }


def _sync_sales_order_commissions(sales_order_name):
    eligibility = sales_order_commission_eligibility(sales_order_name)
    if eligibility["eligible"]:
        _update_commission_status(
            sales_order_name,
            status="To Pay",
            sales_invoice=eligibility["latest_invoice"],
        )
        return

    _update_commission_status(sales_order_name, status="Approved", sales_invoice="")


def _update_commission_status(sales_order_name, status, sales_invoice):
    commissions = frappe.get_all(
        "Sales Commission",
        filters={"sales_order": sales_order_name, "docstatus": 1, "status": ["!=", "Paid"]},
        pluck="name",
    )
    for name in commissions:
        commission = frappe.get_doc("Sales Commission", name)
        commission.status = status
        commission.sales_invoice = sales_invoice or ""
        commission.save(ignore_permissions=True)
