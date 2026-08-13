from __future__ import annotations

import frappe


@frappe.whitelist()
def get_item_details(ctx, doc=None, for_validate=False, overwrite_warehouse=True):
    """Call ERPNext item details without native Item Price auto-insert for Purchase Orders."""
    from erpnext.stock.get_item_details import get_item_details as erpnext_get_item_details
    import importlib

    erpnext_item_details_module = importlib.import_module("erpnext.stock.get_item_details")

    guarded_ctx = _copy_payload(ctx)
    insert_item_price = None
    if _is_purchase_order_context(guarded_ctx, doc):
        insert_item_price = getattr(erpnext_item_details_module, "insert_item_price", None)
        for fieldname in ("price_list", "buying_price_list"):
            _set_value(guarded_ctx, fieldname, "")
        _set_value(guarded_ctx, "price_list_currency", _get_value(guarded_ctx, "currency") or "")
        _set_value(guarded_ctx, "plc_conversion_rate", 1)
        erpnext_item_details_module.insert_item_price = _suppress_native_item_price_insert

    try:
        return erpnext_get_item_details(
            guarded_ctx,
            doc=doc,
            for_validate=for_validate,
            overwrite_warehouse=overwrite_warehouse,
        )
    finally:
        if insert_item_price is not None:
            erpnext_item_details_module.insert_item_price = insert_item_price


def _copy_payload(value):
    if isinstance(value, str):
        return frappe.parse_json(value) or {}
    if isinstance(value, dict):
        return dict(value)
    copier = getattr(value, "copy", None)
    if callable(copier):
        return copier()
    return value


def _is_purchase_order_context(ctx, doc=None) -> bool:
    if _get_value(ctx, "doctype") == "Purchase Order" or _get_value(ctx, "parenttype") == "Purchase Order":
        return True
    parsed_doc = frappe.parse_json(doc) if isinstance(doc, str) else doc
    return _get_value(parsed_doc, "doctype") == "Purchase Order"


def _get_value(value, fieldname):
    getter = getattr(value, "get", None)
    return getter(fieldname) if callable(getter) else getattr(value, fieldname, None)


def _set_value(value, fieldname, new_value) -> None:
    if isinstance(value, dict):
        value[fieldname] = new_value
    else:
        setattr(value, fieldname, new_value)


def _suppress_native_item_price_insert(ctx):
    return None
