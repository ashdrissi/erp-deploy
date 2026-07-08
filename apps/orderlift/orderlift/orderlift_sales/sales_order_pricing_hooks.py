from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.orderlift_sales.utils.price_list_scope import can_override_quotation_pricing


SOURCE_HEADER_FIELDS = ("source_pricing_sheet",)
SOURCE_TABLE_FIELDS = ("selected_selling_price_lists",)

SOURCE_ITEM_FIELDS = (
    "source_pricing_sheet_line",
    "source_pricing_scenario",
    "source_pricing_override",
    "source_pricing_policy",
    "source_scenario_rule",
    "source_margin_rule",
    "source_sales_person",
    "source_geography",
    "source_customs_applied",
    "source_customs_basis",
    "source_selling_price_list",
    "source_price_list_sell_rate",
    "source_gross_sell_rate",
    "source_discount_percent",
    "source_max_discount_percent",
    "source_discount_amount",
    "source_discounted_sell_rate",
    "source_margin_percent",
    "source_margin_basis",
    "source_commission_rate",
    "source_commission_amount",
)

NATIVE_PRICE_FIELDS = (
    "item_code",
    "price_list_rate",
    "rate",
    "discount_percentage",
    "net_rate",
)


def copy_quotation_pricing_snapshot(doc, method=None) -> None:
    if not doc or int(flt(_get(doc, "docstatus"))) == 2:
        return

    source_context = _source_context(doc)
    if not source_context.quotation_by_name:
        return

    override = can_override_quotation_pricing()
    _copy_header_snapshot(doc, source_context.first_quotation, overwrite=not override)

    for row in _items(doc):
        source_row = source_context.source_row_for(row)
        if not source_row:
            continue
        _copy_row_snapshot(row, source_row, overwrite=not override)
        if not override:
            _restore_row_pricing_from_source(row, source_row)


def validate_sales_order_source_lock(doc, method=None) -> None:
    if not doc or can_override_quotation_pricing():
        return

    item_rows = _items(doc)
    if not item_rows:
        return

    source_context = _source_context(doc)
    for row in item_rows:
        source_quotation = _row_source_quotation(row)
        source_detail = _row_source_detail(row)
        idx = _get(row, "idx") or "-"
        if not source_quotation or not source_detail:
            frappe.throw(
                _("Sales Orders must be created from a submitted Quotation. Row {0} is missing its source Quotation.").format(idx)
            )
        quote = source_context.quotation_by_name.get(source_quotation)
        if not quote:
            frappe.throw(_("Source Quotation {0} on row {1} was not found.").format(source_quotation, idx))
        if int(flt(_get(quote, "docstatus"))) != 1:
            frappe.throw(_("Source Quotation {0} on row {1} must be submitted before creating a Sales Order.").format(source_quotation, idx))
        source_row = source_context.source_row_for(row)
        if not source_row:
            frappe.throw(_("Source Quotation Item {0} on row {1} was not found.").format(source_detail, idx))
        if (_get(row, "item_code") or "").strip() != (_get(source_row, "item_code") or "").strip():
            frappe.throw(_("Sales Order row {0} item must match the source Quotation item.").format(idx))
        if flt(_get(row, "qty")) > flt(_get(source_row, "qty")) + 0.000001:
            frappe.throw(_("Sales Order row {0} quantity cannot exceed the submitted Quotation quantity.").format(idx))


def validate_sales_order_pricing_locked_to_quotation(doc, method=None) -> None:
    if not doc or can_override_quotation_pricing():
        return

    source_context = _source_context(doc)
    for row in _items(doc):
        source_row = source_context.source_row_for(row)
        if not source_row:
            continue
        idx = _get(row, "idx") or "-"
        for fieldname in ("price_list_rate", "rate", "discount_percentage", "net_rate"):
            if not _has_field(row, fieldname) or not _has_field(source_row, fieldname):
                continue
            if abs(flt(_get(row, fieldname)) - flt(_get(source_row, fieldname))) > 0.000001:
                frappe.throw(_("Sales Order row {0} pricing is locked to its source Quotation.").format(idx))
        expected_amount = flt(_get(row, "rate")) * (flt(_get(row, "qty")) or 1)
        for fieldname in ("amount", "net_amount"):
            if _has_field(row, fieldname) and abs(flt(_get(row, fieldname)) - expected_amount) > 0.01:
                frappe.throw(_("Sales Order row {0} amount must match its source Quotation rate and Sales Order quantity.").format(idx))


def validate_sales_order_item_discount_caps(doc, method=None) -> None:
    if not doc or can_override_quotation_pricing():
        return

    for row in _items(doc):
        if not _has_field(row, "source_discount_percent") or not _has_field(row, "source_max_discount_percent"):
            continue
        discount = flt(_get(row, "source_discount_percent"))
        max_discount = flt(_get(row, "source_max_discount_percent"))
        idx = _get(row, "idx") or "-"
        if discount < 0:
            frappe.throw(_("Pricing Discount % cannot be negative on Sales Order row {0}.").format(idx))
        if discount > max_discount + 0.000001:
            frappe.throw(
                _("Pricing Discount % cannot exceed {0}% for {1} on Sales Order row {2}.").format(
                    max_discount,
                    _get(row, "item_code") or _get(row, "item_name") or "item",
                    idx,
                )
            )
        _validate_row_rate_against_snapshot(row, discount)


def _validate_row_rate_against_snapshot(row, discount: float) -> None:
    gross_rate = flt(_get(row, "source_gross_sell_rate"))
    if gross_rate <= 0:
        return
    expected_rate = gross_rate * (1 - (discount / 100.0))
    if flt(_get(row, "rate")) + 0.000001 >= expected_rate:
        return
    frappe.throw(
        _("Rate for {0} on Sales Order row {1} is below the inherited pricing policy net rate {2}.").format(
            _get(row, "item_code") or _get(row, "item_name") or "item",
            _get(row, "idx") or "-",
            _format_rate(expected_rate),
        )
    )


class _SourceContext:
    def __init__(self, quotation_by_name: dict[str, object], row_by_key: dict[tuple[str, str], object]):
        self.quotation_by_name = quotation_by_name
        self.row_by_key = row_by_key
        self.first_quotation = next(iter(quotation_by_name.values()), None)

    def source_row_for(self, row):
        source_quotation = _row_source_quotation(row)
        source_detail = _row_source_detail(row)
        if not source_quotation or not source_detail:
            return None
        return self.row_by_key.get((source_quotation, source_detail))


def _source_context(doc) -> _SourceContext:
    quotation_names = []
    for row in _items(doc):
        source_quotation = _row_source_quotation(row)
        if source_quotation and source_quotation not in quotation_names:
            quotation_names.append(source_quotation)

    quotation_by_name = {}
    row_by_key = {}
    for quotation_name in quotation_names:
        quote = frappe.get_doc("Quotation", quotation_name)
        quotation_by_name[quotation_name] = quote
        for quote_row in _items(quote):
            detail_name = (_get(quote_row, "name") or "").strip()
            if detail_name:
                row_by_key[(quotation_name, detail_name)] = quote_row
    return _SourceContext(quotation_by_name, row_by_key)


def _copy_header_snapshot(doc, quotation, *, overwrite: bool) -> None:
    if not quotation:
        return
    for fieldname in SOURCE_HEADER_FIELDS:
        _copy_field(doc, quotation, fieldname, overwrite=overwrite)
    for fieldname in SOURCE_TABLE_FIELDS:
        if not _has_field(doc, fieldname) or not _has_field(quotation, fieldname):
            continue
        if not overwrite and _get(doc, fieldname):
            continue
        _set_table(doc, fieldname, _get(quotation, fieldname) or [])


def _copy_row_snapshot(row, source_row, *, overwrite: bool) -> None:
    for fieldname in SOURCE_ITEM_FIELDS:
        _copy_field(row, source_row, fieldname, overwrite=overwrite)


def _restore_row_pricing_from_source(row, source_row) -> None:
    for fieldname in NATIVE_PRICE_FIELDS:
        _copy_field(row, source_row, fieldname, overwrite=True)
    qty = flt(_get(row, "qty")) or 1
    rate = flt(_get(row, "rate"))
    amount = rate * qty
    _set_if_field(row, "amount", amount)
    _set_if_field(row, "net_amount", amount)


def _copy_field(target, source, fieldname: str, *, overwrite: bool) -> None:
    if not _has_field(target, fieldname) or not _has_field(source, fieldname):
        return
    value = _get(source, fieldname)
    if not overwrite and _has_value(_get(target, fieldname)):
        return
    _set(target, fieldname, value)


def _set_table(doc, fieldname: str, source_rows) -> None:
    excluded = {"doctype", "name", "owner", "creation", "modified", "modified_by", "parent", "parentfield", "parenttype", "docstatus", "idx"}
    setter = getattr(doc, "set", None)
    appender = getattr(doc, "append", None)
    if callable(setter) and callable(appender):
        setter(fieldname, [])
        for source_row in source_rows:
            appender(fieldname, {key: value for key, value in _as_dict(source_row).items() if key not in excluded})
        return
    _set(doc, fieldname, [{key: value for key, value in _as_dict(row).items() if key not in excluded} for row in source_rows])


def _row_source_quotation(row) -> str:
    source_doctype = (_get(row, "prevdoc_doctype") or "").strip()
    if source_doctype and source_doctype != "Quotation":
        return ""
    return (_get(row, "prevdoc_docname") or "").strip()


def _row_source_detail(row) -> str:
    return (_get(row, "prevdoc_detail_docname") or "").strip()


def _items(doc) -> list:
    getter = getattr(doc, "get", None)
    rows = getter("items") if callable(getter) else getattr(doc, "items", None)
    return list(rows or [])


def _get(obj, fieldname: str):
    if isinstance(obj, dict):
        return obj.get(fieldname)
    getter = getattr(obj, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(obj, fieldname, None)


def _set_if_field(obj, fieldname: str, value) -> None:
    if _has_field(obj, fieldname):
        _set(obj, fieldname, value)


def _set(obj, fieldname: str, value) -> None:
    setter = getattr(obj, "set", None)
    if callable(setter):
        setter(fieldname, value)
    elif isinstance(obj, dict):
        obj[fieldname] = value
    else:
        setattr(obj, fieldname, value)


def _has_field(obj, fieldname: str) -> bool:
    meta = getattr(obj, "meta", None)
    getter = getattr(meta, "get_field", None)
    if callable(getter):
        return bool(getter(fieldname))
    has_field = getattr(meta, "has_field", None)
    if callable(has_field):
        return bool(has_field(fieldname))
    if isinstance(obj, dict):
        return True
    return hasattr(obj, fieldname)


def _has_value(value) -> bool:
    return value not in (None, "", [], {})


def _as_dict(row) -> dict:
    if isinstance(row, dict):
        return dict(row)
    converter = getattr(row, "as_dict", None)
    if callable(converter):
        return dict(converter())
    return dict(getattr(row, "__dict__", {}))


def _format_rate(value: float) -> str:
    return f"{flt(value):.2f}".rstrip("0").rstrip(".")
