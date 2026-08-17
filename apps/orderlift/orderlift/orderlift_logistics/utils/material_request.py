from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from orderlift.menu_access import resolve_current_company


MANUAL_CHARGE_ITEM_CODES = {"OTHER-CHARGES", "TRANSPORTATION-CHARGE"}


def default_schedule_date(doc, method=None) -> None:
    if not doc:
        return
    from frappe.utils import getdate
    if not doc.get("schedule_date") and doc.get("transaction_date"):
        doc.schedule_date = doc.transaction_date
    for row in doc.get("items") or []:
        if not row.get("schedule_date") and doc.get("schedule_date"):
            row.schedule_date = doc.schedule_date


def clear_price_list_link(doc, method=None) -> None:
    """Keep Material Requests quantity-based and independent from price lists."""
    if not doc:
        return
    if _has_field(doc, "buying_price_list"):
        doc.set("buying_price_list", "")
    for row in doc.get("items") or []:
        if _has_field(row, "price_list_rate"):
            row.set("price_list_rate", 0)


@frappe.whitelist()
def get_material_request_purchase_order_preview(material_requests) -> dict:
    requests, eligible_rows, skipped_rows = _purchase_order_source_rows(material_requests)
    schedule_dates = [getdate(row["schedule_date"]) for row in eligible_rows if row.get("schedule_date")]
    return {
        "company": requests[0].company,
        "material_requests": [doc.name for doc in requests],
        "eligible_rows": len(eligible_rows),
        "skipped_rows": skipped_rows,
        "schedule_date": str(max(schedule_dates)) if schedule_dates else nowdate(),
    }


@frappe.whitelist()
def make_purchase_order_from_material_requests(
    material_requests,
    supplier: str,
    schedule_date: str | None = None,
) -> dict:
    if not frappe.has_permission("Purchase Order", "create"):
        frappe.throw(_("You do not have permission to create Purchase Orders."), frappe.PermissionError)
    supplier = (supplier or "").strip()
    if not supplier or not frappe.db.exists("Supplier", supplier):
        frappe.throw(_("Select a valid Supplier."))

    requests, eligible_rows, skipped_rows = _purchase_order_source_rows(material_requests)
    company = requests[0].company
    supplier_doc = frappe.get_doc("Supplier", supplier)
    supplier_doc.check_permission("read")
    from orderlift.orderlift_sales.utils.purchase_order_pricing import (
        _supplier_allowed_for_company,
        get_supplier_buying_price_lists,
        sync_purchase_order_buying_price_lists,
    )

    if supplier_doc.meta.get_field("custom_company") and not _supplier_allowed_for_company(supplier, company):
        frappe.throw(_("Supplier {0} does not belong to company {1}.").format(supplier, company))
    transaction_date = nowdate()
    requested_schedule_date = str(getdate(schedule_date)) if schedule_date else ""
    company_currency = frappe.db.get_value("Company", company, "default_currency") or ""
    supplier_currency = supplier_doc.default_currency or company_currency

    purchase_order = frappe.new_doc("Purchase Order")
    purchase_order.company = company
    purchase_order.supplier = supplier
    purchase_order.supplier_name = supplier_doc.supplier_name or supplier
    purchase_order.transaction_date = transaction_date
    purchase_order.schedule_date = requested_schedule_date or _latest_schedule_date(eligible_rows) or transaction_date
    purchase_order.currency = supplier_currency
    purchase_order.conversion_rate = _currency_rate(supplier_currency, company_currency, transaction_date)

    item_meta = frappe.get_meta("Purchase Order Item")
    for source in eligible_rows:
        values = {
            "item_code": source["item_code"],
            "item_name": source.get("item_name"),
            "description": source.get("description"),
            "qty": source["remaining_qty"],
            "uom": source.get("uom"),
            "stock_uom": source.get("stock_uom"),
            "conversion_factor": source.get("conversion_factor") or 1,
            "schedule_date": requested_schedule_date or source.get("schedule_date") or purchase_order.schedule_date,
            "warehouse": source.get("warehouse"),
            "project": source.get("project"),
            "sales_order": source.get("sales_order"),
            "sales_order_item": source.get("sales_order_item"),
            "material_request": source["material_request"],
            "material_request_item": source["material_request_item"],
        }
        purchase_order.append(
            "items",
            {key: value for key, value in values.items() if value is not None and item_meta.get_field(key)},
        )

    for index, row in enumerate(
        get_supplier_buying_price_lists(
            supplier,
            company,
            target_currency=supplier_currency,
            reference_date=transaction_date,
        ),
        start=1,
    ):
        purchase_order.append(
            "selected_buying_price_lists",
            {
                "price_list": row["price_list"],
                "source_currency": row.get("source_currency"),
                "exchange_rate": row.get("exchange_rate"),
                "exchange_rate_source": row.get("exchange_rate_source") or "System",
                "sequence": index * 10,
                "is_active": 1,
            },
        )
    sync_purchase_order_buying_price_lists(purchase_order)
    purchase_order.flags.ignore_mandatory = True
    payload = purchase_order.as_dict()
    payload["__islocal"] = 1
    payload["__unsaved"] = 1
    return {
        "doc": payload,
        "material_requests": [doc.name for doc in requests],
        "eligible_rows": len(eligible_rows),
        "skipped_rows": skipped_rows,
    }


def _purchase_order_source_rows(material_requests):
    names = frappe.parse_json(material_requests) if isinstance(material_requests, str) else material_requests
    names = list(dict.fromkeys((str(name or "").strip() for name in (names or []))))
    names = [name for name in names if name]
    if not names:
        frappe.throw(_("Select at least one Material Request."))
    if len(names) > 100:
        frappe.throw(_("Select no more than 100 Material Requests at once."))

    active_company = resolve_current_company(user=frappe.session.user)
    requests = []
    eligible_rows = []
    skipped_rows = []
    for name in names:
        doc = frappe.get_doc("Material Request", name)
        doc.check_permission("read")
        if doc.docstatus != 1:
            frappe.throw(_("Material Request {0} must be submitted.").format(name))
        if (doc.company or "").strip() != active_company:
            frappe.throw(_("Material Request {0} is outside your active company.").format(name), frappe.PermissionError)
        if requests and doc.company != requests[0].company:
            frappe.throw(_("All selected Material Requests must belong to the same company."))
        if (doc.material_request_type or "").strip() != "Purchase":
            frappe.throw(_("Material Request {0} is not a Purchase request.").format(name))
        if (doc.status or "").strip() in {"Stopped", "Cancelled", "Completed", "Transferred"}:
            frappe.throw(_("Material Request {0} is not open for purchasing.").format(name))
        requests.append(doc)
        for row in doc.items:
            remaining_qty = max(flt(row.qty) - flt(row.get("ordered_qty")), 0)
            if not row.item_code or remaining_qty <= 0 or row.item_code in MANUAL_CHARGE_ITEM_CODES:
                skipped_rows.append(
                    {
                        "material_request": doc.name,
                        "material_request_item": row.name,
                        "item_code": row.item_code or "",
                        "reason": _("Manual charge, fully ordered, or missing item"),
                    }
                )
                continue
            eligible_rows.append(
                {
                    "material_request": doc.name,
                    "material_request_item": row.name,
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "description": row.description,
                    "remaining_qty": remaining_qty,
                    "uom": row.uom,
                    "stock_uom": row.stock_uom,
                    "conversion_factor": row.conversion_factor,
                    "schedule_date": row.schedule_date or doc.schedule_date,
                    "warehouse": row.warehouse,
                    "project": row.project,
                    "sales_order": row.sales_order,
                    "sales_order_item": row.sales_order_item,
                }
            )
    if not eligible_rows:
        frappe.throw(_("The selected Material Requests have no remaining quantities to order."))
    return requests, eligible_rows, skipped_rows


def _latest_schedule_date(rows) -> str:
    dates = [getdate(row["schedule_date"]) for row in rows if row.get("schedule_date")]
    return str(max(dates)) if dates else ""


def _currency_rate(source_currency: str, target_currency: str, rate_date: str) -> float:
    if not source_currency or not target_currency or source_currency == target_currency:
        return 1.0
    from erpnext.setup.utils import get_exchange_rate

    rate = flt(get_exchange_rate(source_currency, target_currency, rate_date))
    if rate <= 0:
        frappe.throw(
            _("No {0} to {1} exchange rate is available for {2}.").format(
                source_currency,
                target_currency,
                rate_date,
            )
        )
    return rate


def _has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    return bool(meta and meta.get_field(fieldname))
