from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.orderlift_finance.account_governance import get_company_account_map, get_company_cost_center
from orderlift.orderlift_sales.utils.tax_inclusive import sales_tax_template_total_rate


ADVANCE_KEY_SEPARATOR = "::"


@frappe.whitelist()
def get_available_advance_options(customer: str, company: str, sales_orders=None) -> list[dict]:
    customer = (customer or "").strip()
    company = (company or "").strip()
    if not customer or not company:
        return []
    frappe.has_permission("Sales Invoice", "create", throw=True)

    sales_order_names = _normalize_sales_orders(sales_orders)
    options = []
    options.extend(_paid_advance_options(customer, company, sales_order_names))
    options.extend(_scheduled_advance_options(customer, company, sales_order_names))
    return [row for row in options if flt(row.get("available_amount")) > 0]


@frappe.whitelist()
def get_invoice_mode_defaults(company: str | None = None) -> dict:
    company = (company or "").strip()
    if not company:
        return {}
    frappe.has_permission("Sales Invoice", "create", throw=True)
    account_map = get_company_account_map(company, create_missing=False)
    return {
        "income_account": account_map.get("sales_revenue") or "",
        "cost_center": get_company_cost_center(company, create_missing=False) or "",
        "uom": _default_uom(),
    }


@frappe.whitelist()
def build_advance_invoice_payload(
    option,
    amount=None,
    income_account: str | None = None,
    cost_center: str | None = None,
    uom: str | None = None,
    taxes_and_charges: str | None = None,
    sales_order: str | None = None,
) -> dict:
    frappe.has_permission("Sales Invoice", "create", throw=True)
    source = _coerce_dict(option)
    resolved_sales_order = (source.get("sales_order") or sales_order or "").strip()
    available_amount = flt(source.get("available_amount"))
    invoice_amount_ttc = flt(amount if amount not in (None, "") else available_amount)
    if invoice_amount_ttc <= 0:
        frappe.throw(_("Advance invoice amount must be greater than zero."))
    if available_amount and invoice_amount_ttc > available_amount + 0.000001:
        frappe.throw(_("Advance invoice amount cannot exceed the available advance amount."))
    invoice_amount_ht = _amount_excluding_tax(invoice_amount_ttc, taxes_and_charges)

    designation = (source.get("designation") or source.get("label") or _("Advance Invoice")).strip()
    row = _text_invoice_row(
        designation,
        invoice_amount_ht,
        income_account=income_account or source.get("income_account"),
        cost_center=cost_center or source.get("cost_center"),
        uom=uom,
        description=source.get("description") or designation,
        amount_ttc=invoice_amount_ttc,
        sales_order=resolved_sales_order,
    )
    return {
        "row": row,
        "header": {
            "custom_invoice_mode": "Advance",
            "custom_advance_payment_entry": source.get("payment_entry") or "",
            "custom_advance_sales_order": resolved_sales_order,
            "custom_advance_payment_schedule_row": source.get("payment_schedule_row") or "",
        },
    }


@frappe.whitelist()
def build_custom_invoice_payload(
    item_name: str,
    amount,
    income_account: str,
    description: str | None = None,
    cost_center: str | None = None,
    uom: str | None = None,
    sales_order: str | None = None,
) -> dict:
    frappe.has_permission("Sales Invoice", "create", throw=True)
    item_name = (item_name or "").strip()
    if not item_name:
        frappe.throw(_("Designation is required."))
    if flt(amount) <= 0:
        frappe.throw(_("Invoice amount must be greater than zero."))
    income_account = (income_account or "").strip()
    if not income_account:
        frappe.throw(_("Income Account is required."))
    resolved_sales_order = (sales_order or "").strip()
    return {
        "row": _text_invoice_row(
            item_name,
            flt(amount),
            income_account=income_account,
            cost_center=cost_center,
            uom=uom,
            description=description or item_name,
            sales_order=resolved_sales_order,
        ),
        "header": {
            "custom_invoice_mode": "Custom",
            "custom_advance_payment_entry": "",
            "custom_advance_sales_order": resolved_sales_order,
            "custom_advance_payment_schedule_row": "",
        },
    }


def validate_invoice_mode(doc, method=None) -> None:
    mode = (doc.get("custom_invoice_mode") or "").strip()
    if not mode:
        return
    if mode == "Advance":
        _validate_advance_invoice(doc)
    elif mode == "Custom":
        _validate_custom_invoice(doc)


def _paid_advance_options(customer: str, company: str, sales_orders: list[str]) -> list[dict]:
    rows = frappe.get_all(
        "Payment Entry",
        filters={
            "docstatus": 1,
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": customer,
            "company": company,
        },
        fields=[
            "name",
            "posting_date",
            "paid_amount",
            "received_amount",
            "unallocated_amount",
            "paid_from_account_currency",
            "paid_to_account_currency",
        ],
        limit_page_length=0,
    )
    options = []
    for row in rows:
        linked_sales_orders = _payment_entry_sales_orders(row.name)
        if sales_orders and linked_sales_orders and not set(sales_orders).intersection(linked_sales_orders):
            continue
        paid_basis = flt(row.unallocated_amount)
        if sales_orders and linked_sales_orders:
            paid_basis = _payment_entry_allocated_to_sales_orders(row.name, sales_orders)
        if paid_basis <= 0:
            continue
        invoiced = _submitted_advance_invoice_total(payment_entry=row.name)
        available = paid_basis - invoiced
        if available <= 0:
            continue
        options.append(
            {
                "key": _advance_key("Payment Entry", row.name, ""),
                "source_type": "Payment Entry",
                "source_label": _("Paid Advance"),
                "payment_entry": row.name,
                "sales_order": next(iter(linked_sales_orders), ""),
                "payment_schedule_row": "",
                "posting_date": str(row.posting_date or ""),
                "reference": row.name,
                "original_amount": paid_basis,
                "invoiced_amount": invoiced,
                "available_amount": available,
                "currency": row.get("paid_to_account_currency") or row.get("paid_from_account_currency") or "",
                "designation": _("Advance Invoice - {0}").format(row.name),
                "description": _("Advance payment received via Payment Entry {0}.").format(row.name),
            }
        )
    return options


def _scheduled_advance_options(customer: str, company: str, sales_orders: list[str]) -> list[dict]:
    if not sales_orders:
        return []
    orders = frappe.get_all(
        "Sales Order",
        filters={"name": ["in", sales_orders], "customer": customer, "company": company, "docstatus": ["!=", 2]},
        fields=["name", "currency", "transaction_date"],
        limit_page_length=0,
    )
    options = []
    for order in orders:
        schedule_rows = frappe.get_all(
            "Payment Schedule",
            filters={"parenttype": "Sales Order", "parent": order.name, "parentfield": "payment_schedule"},
            fields=["name", "payment_term", "due_date", "payment_amount", "outstanding"],
            order_by="idx asc",
            limit_page_length=0,
        )
        for row in schedule_rows:
            scheduled = flt(row.payment_amount or row.outstanding)
            if scheduled <= 0:
                continue
            invoiced = _submitted_advance_invoice_total(sales_order=order.name, payment_schedule_row=row.name)
            available = scheduled - invoiced
            if available <= 0:
                continue
            term = (row.payment_term or _("Scheduled Advance")).strip()
            options.append(
                {
                    "key": _advance_key("Payment Schedule", order.name, row.name),
                    "source_type": "Payment Schedule",
                    "source_label": _("Scheduled Advance"),
                    "payment_entry": "",
                    "sales_order": order.name,
                    "payment_schedule_row": row.name,
                    "posting_date": str(row.due_date or order.transaction_date or ""),
                    "reference": f"{order.name} / {term}",
                    "original_amount": scheduled,
                    "invoiced_amount": invoiced,
                    "available_amount": available,
                    "currency": order.currency or "",
                    "designation": _("Advance Invoice - {0}").format(term),
                    "description": _("Scheduled advance from Sales Order {0}, payment term {1}.").format(order.name, term),
                }
            )
    return options


def _text_invoice_row(
    item_name: str,
    amount: float,
    *,
    income_account: str | None = None,
    cost_center: str | None = None,
    uom: str | None = None,
    description: str | None = None,
    amount_ttc: float | None = None,
    sales_order: str | None = None,
) -> dict:
    amount = flt(amount)
    amount_ttc = flt(amount_ttc if amount_ttc not in (None, "") else amount)
    return {
        "item_code": "",
        "item_name": item_name,
        "description": description or item_name,
        "qty": 1,
        "rate": amount,
        "amount": amount,
        "uom": (uom or _default_uom() or "").strip(),
        "income_account": income_account or "",
        "cost_center": cost_center or "",
        "sales_order": (sales_order or "").strip(),
        "allow_zero_valuation_rate": 1,
        "custom_pu_ttc": amount_ttc,
        "custom_pt_ttc": amount_ttc,
        "custom_applied_taxes": max(amount_ttc - amount, 0),
    }


def _validate_advance_invoice(doc) -> None:
    payment_entry = (doc.get("custom_advance_payment_entry") or "").strip()
    sales_order = (doc.get("custom_advance_sales_order") or "").strip()
    schedule_row = (doc.get("custom_advance_payment_schedule_row") or "").strip()
    if not payment_entry and not (sales_order and schedule_row):
        frappe.throw(_("Advance invoice must reference a Payment Entry or Sales Order payment schedule row."))
    if payment_entry and _submitted_advance_invoice_names(payment_entry=payment_entry, exclude=doc.name):
        frappe.throw(_("Payment Entry {0} is already linked to a submitted advance invoice.").format(payment_entry))
    if sales_order and schedule_row and _submitted_advance_invoice_names(
        sales_order=sales_order,
        payment_schedule_row=schedule_row,
        exclude=doc.name,
    ):
        frappe.throw(_("This Sales Order payment schedule row is already linked to a submitted advance invoice."))
    _validate_text_rows(doc, mode="Advance")


def _validate_custom_invoice(doc) -> None:
    _validate_text_rows(doc, mode="Custom")


def _validate_text_rows(doc, *, mode: str) -> None:
    rows = list(doc.get("items") or [])
    if not rows:
        frappe.throw(_("{0} invoice requires at least one invoice row.").format(mode))
    for row in rows:
        if (row.get("item_code") or "").strip():
            frappe.throw(_("{0} invoice rows must be text-only rows without Item Code.").format(mode))
        if not (row.get("item_name") or "").strip():
            frappe.throw(_("{0} invoice row requires a designation.").format(mode))
        if flt(row.get("amount") or row.get("rate")) <= 0:
            frappe.throw(_("{0} invoice row amount must be greater than zero.").format(mode))
        if not (row.get("uom") or "").strip():
            frappe.throw(_("{0} invoice row requires a UOM.").format(mode))
        if not (row.get("income_account") or "").strip():
            frappe.throw(_("{0} invoice row requires an Income Account.").format(mode))


def _amount_excluding_tax(amount_ttc: float, taxes_and_charges: str | None) -> float:
    tax_rate = sales_tax_template_total_rate((taxes_and_charges or "").strip())
    if tax_rate <= 0:
        return flt(amount_ttc)
    return flt(amount_ttc) / (1 + tax_rate / 100.0)


def _default_uom() -> str:
    for uom in ("Nos", "Unit", "Pce", "Service"):
        if frappe.db.exists("UOM", uom):
            return uom
    return frappe.db.get_value("UOM", {}, "name") or ""


def _payment_entry_sales_orders(payment_entry: str) -> set[str]:
    rows = frappe.get_all(
        "Payment Entry Reference",
        filters={"parent": payment_entry, "parenttype": "Payment Entry", "reference_doctype": "Sales Order"},
        pluck="reference_name",
        limit_page_length=0,
    )
    return {row for row in rows if row}


def _payment_entry_allocated_to_sales_orders(payment_entry: str, sales_orders: list[str]) -> float:
    rows = frappe.get_all(
        "Payment Entry Reference",
        filters={
            "parent": payment_entry,
            "parenttype": "Payment Entry",
            "reference_doctype": "Sales Order",
            "reference_name": ["in", sales_orders],
        },
        fields=["allocated_amount"],
        limit_page_length=0,
    )
    return sum(flt(row.allocated_amount) for row in rows)


def _submitted_advance_invoice_total(
    *,
    payment_entry: str | None = None,
    sales_order: str | None = None,
    payment_schedule_row: str | None = None,
) -> float:
    names = _submitted_advance_invoice_names(
        payment_entry=payment_entry,
        sales_order=sales_order,
        payment_schedule_row=payment_schedule_row,
    )
    if not names:
        return 0.0
    return flt(frappe.db.get_value("Sales Invoice", {"name": ["in", names]}, "sum(grand_total)") or 0)


def _submitted_advance_invoice_names(
    *,
    payment_entry: str | None = None,
    sales_order: str | None = None,
    payment_schedule_row: str | None = None,
    exclude: str | None = None,
) -> list[str]:
    filters = {"docstatus": 1, "custom_invoice_mode": "Advance"}
    if payment_entry:
        filters["custom_advance_payment_entry"] = payment_entry
    if sales_order:
        filters["custom_advance_sales_order"] = sales_order
    if payment_schedule_row:
        filters["custom_advance_payment_schedule_row"] = payment_schedule_row
    names = frappe.get_all("Sales Invoice", filters=filters, pluck="name", limit_page_length=0)
    return [name for name in names if name != exclude]


def _normalize_sales_orders(sales_orders) -> list[str]:
    if isinstance(sales_orders, str):
        try:
            parsed = json.loads(sales_orders)
            sales_orders = parsed
        except ValueError:
            sales_orders = [sales_orders]
    if not sales_orders:
        return []
    return list(dict.fromkeys((str(row or "").strip() for row in sales_orders if str(row or "").strip())))


def _coerce_dict(value) -> dict:
    if isinstance(value, str):
        return json.loads(value or "{}")
    if isinstance(value, dict):
        return value
    return dict(value or {})


def _advance_key(source_type: str, reference: str, row_name: str) -> str:
    return ADVANCE_KEY_SEPARATOR.join([source_type, reference or "", row_name or ""])
