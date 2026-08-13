from __future__ import annotations

import frappe


SALES_ORDER_DOCTYPE = "Sales Order"

COMMERCIAL_PARENT_FIELDS = {
    "base_discount_amount",
    "base_grand_total",
    "base_in_words",
    "base_net_total",
    "base_rounded_total",
    "base_total",
    "base_total_taxes_and_charges",
    "discount_amount",
    "grand_total",
    "in_words",
    "net_total",
    "rounded_total",
    "total",
    "total_commission",
    "total_net_weight",
    "total_taxes_and_charges",
}

COMMERCIAL_PARENT_TEXT_FIELDS = {
    "base_in_words",
    "in_words",
}

COMMERCIAL_ITEM_FIELDS = {
    "amount",
    "base_amount",
    "base_net_amount",
    "base_net_rate",
    "base_price_list_rate",
    "base_rate",
    "base_rate_with_margin",
    "custom_applied_taxes",
    "custom_pt_ttc",
    "custom_pu_ttc",
    "discount_amount",
    "discount_percentage",
    "margin_rate_or_amount",
    "margin_type",
    "net_amount",
    "net_rate",
    "price_list_rate",
    "rate",
    "rate_with_margin",
    "source_base_buy_rate",
    "source_commission_amount",
    "source_commission_rate",
    "source_discount_amount",
    "source_discount_percent",
    "source_landed_cost",
    "source_margin_basis",
    "source_margin_percent",
    "source_max_discount_percent",
    "source_price_list_sell_rate",
    "source_target_margin_percent",
}


def can_view_sales_order_commercial_prices(user: str | None = None) -> bool:
    """Commercial prices follow Sales Order create/edit access, not role names."""
    user = user or getattr(frappe.session, "user", None)
    return _has_sales_order_permission("write", user) or _has_sales_order_permission("create", user)


def redact_sales_order_prices(doc, method=None) -> None:
    """Remove commercial price data before serializing read-only Sales Orders."""
    if not doc or getattr(doc, "doctype", None) != SALES_ORDER_DOCTYPE:
        return
    if can_view_sales_order_commercial_prices():
        return

    for fieldname in COMMERCIAL_PARENT_FIELDS:
        _set_value(doc, fieldname, "" if fieldname in COMMERCIAL_PARENT_TEXT_FIELDS else None)

    for row in _get_value(doc, "items") or []:
        for fieldname in COMMERCIAL_ITEM_FIELDS:
            _set_value(row, fieldname, None)

    # Taxes and payment schedules are monetary detail; read-only operational users
    # should not receive those child rows in the Desk payload.
    for table_field in ("taxes", "payment_schedule"):
        if _get_value(doc, table_field) is not None:
            _set_value(doc, table_field, [])


def _has_sales_order_permission(permission_type: str, user: str | None) -> bool:
    try:
        return bool(frappe.has_permission(SALES_ORDER_DOCTYPE, ptype=permission_type, user=user))
    except Exception:
        return False


def _get_value(target, fieldname: str):
    if hasattr(target, "get"):
        return target.get(fieldname)
    return getattr(target, fieldname, None)


def _set_value(target, fieldname: str, value) -> None:
    if hasattr(target, "set"):
        target.set(fieldname, value)
    elif isinstance(target, dict):
        target[fieldname] = value
    else:
        setattr(target, fieldname, value)
