"""Commission workflow.

Create commission records from submitted Sales Orders using quotation snapshot data.
Commissions stay Approved after Sales Order confirmation, move to To Pay when linked
Sales Invoices are fully paid, and become Paid only after payout.
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import flt

from orderlift.orderlift_sales.utils.sales_team import commission_rate, primary_sales_person, team_rows
from orderlift.sales.utils.pricing_projection import calculate_agent_commission


_ALLOWED_LIFECYCLE_TRANSITIONS = {
    ("Approved", "To Pay"),
    ("To Pay", "Approved"),
    ("To Pay", "Paid"),
}


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
            if commission.docstatus == 1:
                # A submitted commission is an immutable commercial snapshot.
                # Replayed Sales Order hooks must not attempt a general save.
                continue
            commission.company = payload["company"]
            commission.customer = payload["customer"]
            commission.project = payload["project"]
            commission.commission_rate = payload["commission_rate"]
            commission.base_amount = payload["base_amount"]
            commission.commission_amount = payload["commission_amount"]
            for fieldname in (
                "custom_contribution_percent",
                "custom_primary_commission_rate",
                "custom_sales_team_snapshot",
            ):
                if commission.meta.get_field(fieldname):
                    commission.set(fieldname, payload.get(fieldname))
            commission.status = "Approved"
            commission.sales_invoice = ""
            commission.flags.orderlift_commission_snapshot_update = True
            commission.save(ignore_permissions=True)
            commission.submit()
            continue

        commission = frappe.get_doc(payload)
        commission.flags.orderlift_commission_snapshot_update = True
        commission.insert(ignore_permissions=True)
        commission.submit()


def sync_commissions_from_invoice(doc, method=None):
    """Approve commissions only when linked Sales Order invoices are fully paid."""
    try:
        seen_orders = {
            item.sales_order
            for item in (doc.items or [])
            if getattr(item, "sales_order", None)
        }
        _sync_sales_orders_safely(seen_orders, source_doc=doc)
    except Exception:
        _log_commission_sync_failure(doc)


def sync_commissions_from_payment_entry(doc, method=None):
    """Re-evaluate commissions when customer payments are submitted or cancelled."""
    try:
        invoice_names = _payment_entry_sales_invoices(doc)
        if not invoice_names:
            return

        sales_orders = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": ["in", invoice_names], "sales_order": ["!=", ""]},
            pluck="sales_order",
        )
        _sync_sales_orders_safely(sales_orders, source_doc=doc)
    except Exception:
        _log_commission_sync_failure(doc)


def reconcile_open_commissions():
    """Safety-net reconciliation for payment/reposting paths that bypass document hooks."""
    try:
        sales_orders = frappe.get_all(
            "Sales Commission",
            filters={
                "docstatus": 1,
                "status": ["in", ["Approved", "To Pay"]],
                "sales_order": ["!=", ""],
            },
            pluck="sales_order",
        )
        _sync_sales_orders_safely(sales_orders, source_doc=None)
    except Exception:
        _log_commission_sync_failure(None)


def cancel_commissions(doc, method=None):
    """Re-evaluate linked commissions when an invoice is cancelled."""
    try:
        seen_orders = {
            item.sales_order
            for item in (doc.items or [])
            if getattr(item, "sales_order", None)
        }
        _sync_sales_orders_safely(seen_orders, source_doc=doc)
    except Exception:
        _log_commission_sync_failure(doc)


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
    if _has_sales_team(sales_order):
        return _build_team_snapshot_commissions(sales_order)

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
        calculated = _calculate_snapshot_commission(source, denominator)
        prorated_commission = flt(calculated.get("commission_amount") or 0) * factor
        prorated_base = flt(calculated.get("base_amount") or 0) * factor

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
        bucket["base_amount"] += prorated_base
        bucket["commission_amount"] += prorated_commission

    return list(results.values())


def _build_team_snapshot_commissions(sales_order):
    """Split the primary salesperson's commission pool across the team."""
    team = team_rows(sales_order)
    primary = primary_sales_person(team)
    if not primary or not team:
        return []

    primary_rate = commission_rate(primary)
    pool_base = 0.0
    pool_amount = 0.0
    for item in sales_order.items or []:
        quotation_item_name = getattr(item, "quotation_item", None) or getattr(item, "prevdoc_detail_docname", None)
        qitem = _quotation_item_commission_snapshot(quotation_item_name) if quotation_item_name else {}
        source = qitem or _row_snapshot(item)
        order_qty = flt(getattr(item, "qty", 0) or 0)
        quotation_qty = flt(qitem.get("qty") or 0)
        denominator = quotation_qty or order_qty or 1.0
        factor = order_qty / denominator if denominator else 0
        source = dict(source)
        source["source_commission_rate"] = primary_rate
        calculated = _calculate_snapshot_commission(source, denominator)
        pool_amount += flt(calculated.get("commission_amount") or 0) * factor
        pool_base += flt(calculated.get("base_amount") or 0) * factor

    if not pool_amount:
        return []

    snapshot = json.dumps(team, sort_keys=True)
    results = []
    for member in team:
        percentage = flt(member.get("allocated_percentage") or 0)
        amount = pool_amount * percentage / 100
        if not amount:
            continue
        results.append(
            {
                "doctype": "Sales Commission",
                "salesperson": member["sales_person"],
                "sales_order": sales_order.name,
                "sales_invoice": "",
                "project": sales_order.project,
                "customer": sales_order.customer,
                "company": sales_order.company,
                "currency": getattr(sales_order, "currency", None) or "",
                "commission_rate": primary_rate,
                "base_amount": pool_base * percentage / 100,
                "commission_amount": amount,
                "status": "Approved",
                "custom_contribution_percent": percentage,
                "custom_primary_commission_rate": primary_rate,
                "custom_sales_team_snapshot": snapshot,
            }
        )
    return results


def _has_sales_team(sales_order) -> bool:
    getter = getattr(sales_order, "get", None)
    rows = getter("custom_sales_team") if callable(getter) else getattr(sales_order, "custom_sales_team", None)
    return bool(rows)


def _quotation_item_commission_snapshot(quotation_item_name):
    return frappe.db.get_value(
        "Quotation Item",
        quotation_item_name,
        [
            "source_sales_person",
            "source_commission_rate",
            "source_price_list_sell_rate",
            "price_list_rate",
            "rate",
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
        "source_price_list_sell_rate": value("source_price_list_sell_rate"),
        "price_list_rate": value("price_list_rate"),
        "rate": value("rate"),
        "source_max_discount_percent": value("source_max_discount_percent"),
    }


def _calculate_snapshot_commission(source, qty):
    price_list_unit = flt(source.get("source_price_list_sell_rate") or source.get("price_list_rate") or 0)
    actual_unit = flt(source.get("rate") or 0)
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
        "base_amount": commission.get("commission_base_amount") or 0,
    }


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


def _sync_sales_orders_safely(sales_orders, source_doc=None):
    """Sync each order independently so commission repair never blocks accounting."""
    for sales_order_name in dict.fromkeys(name for name in sales_orders if name):
        try:
            _sync_sales_order_commissions(sales_order_name)
        except Exception:
            _log_commission_sync_failure(source_doc, sales_order_name)


def _log_commission_sync_failure(source_doc=None, sales_order_name=""):
    source_doctype = getattr(source_doc, "doctype", None) or "Scheduled Reconciliation"
    source_name = getattr(source_doc, "name", None) or ""
    source_label = " ".join(part for part in (source_doctype, source_name) if part)
    order_label = f" / Sales Order {sales_order_name}" if sales_order_name else ""
    get_traceback = getattr(frappe, "get_traceback", None)
    message = get_traceback() if callable(get_traceback) else "Commission synchronization failed."
    log_error = getattr(frappe, "log_error", None)
    if callable(log_error):
        log_error(
            title=f"Commission sync failed: {source_label}{order_label}",
            message=message,
        )


def transition_commission_lifecycle(
    commission_name,
    status,
    *,
    sales_invoice=None,
    payment_date=None,
    payment_reference=None,
    reason="",
):
    """Persist only controlled lifecycle fields on a submitted commission.

    Ordinary ``save()`` is intentionally not used because Frappe correctly blocks
    general edits to submitted documents. Calculation and ownership fields are
    never accepted by this helper.
    """
    # Lock the current row for the request transaction so an automatic payment
    # reconciliation cannot race with an authorized payout.
    frappe.db.get_value(
        "Sales Commission",
        commission_name,
        "name",
        for_update=True,
    )
    commission = frappe.get_doc("Sales Commission", commission_name)
    if getattr(commission, "docstatus", None) != 1:
        raise ValueError("Commission must be submitted before its lifecycle can change.")

    current_status = getattr(commission, "status", None) or "Approved"
    if current_status == "Paid":
        if status != "Paid":
            raise ValueError("A paid Sales Commission cannot be reverted.")
        return False
    if current_status != status and (current_status, status) not in _ALLOWED_LIFECYCLE_TRANSITIONS:
        raise ValueError(
            f"Sales Commission cannot transition from {current_status} to {status}."
        )

    updates = {"status": status}
    if status == "Approved":
        updates["sales_invoice"] = ""
    elif status == "To Pay":
        if not sales_invoice:
            raise ValueError("A paid Sales Invoice is required before commission payout.")
        updates["sales_invoice"] = sales_invoice
    elif status == "Paid":
        if not payment_date:
            raise ValueError("Payment date is required when marking commission as paid.")
        updates["payment_date"] = payment_date
        updates["payment_reference"] = payment_reference or ""

    changed = {
        fieldname: value
        for fieldname, value in updates.items()
        if getattr(commission, fieldname, None) != value
    }
    if not changed:
        return False

    frappe.db.set_value(
        "Sales Commission",
        commission.name,
        changed,
        update_modified=True,
    )
    for fieldname, value in changed.items():
        setattr(commission, fieldname, value)

    add_comment = getattr(commission, "add_comment", None)
    if callable(add_comment):
        transition = (
            f"Commission lifecycle changed from {current_status} to {status}."
        )
        if reason:
            transition = f"{transition} {reason}"
        try:
            add_comment("Info", transition)
        except Exception:
            _log_commission_sync_failure(commission)
    return True


def _update_commission_status(sales_order_name, status, sales_invoice):
    commissions = frappe.get_all(
        "Sales Commission",
        filters={"sales_order": sales_order_name, "docstatus": 1, "status": ["!=", "Paid"]},
        pluck="name",
    )
    for name in commissions:
        transition_commission_lifecycle(
            name,
            status,
            sales_invoice=sales_invoice or "",
            reason=f"Reconciled from Sales Order {sales_order_name}.",
        )
