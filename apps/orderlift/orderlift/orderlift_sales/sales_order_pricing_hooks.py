from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.orderlift_sales.utils.price_list_scope import can_override_quotation_pricing
from orderlift.sales.utils.pricing_projection import calculate_agent_commission


SOURCE_HEADER_FIELDS = (
    "source_pricing_sheet",
    "custom_delivery_lead_time",
    "custom_opportunity_title",
    "custom_opportunity_owner",
    "custom_presentation_mode",
    "custom_commercial_designation",
    "custom_dimensioning_set",
    "custom_dimensioning_multiplier",
    "custom_dimensioning_inputs_json",
    "custom_site_address_name",
)
SOURCE_TABLE_FIELDS = ("selected_selling_price_lists",)

SOURCE_ITEM_FIELDS = (
    "custom_presentation_role",
    "custom_orderlift_other_charge",
    "custom_dimensioning_set",
    "custom_dimensioning_rule_label",
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
    "source_discount_percent",
    "source_max_discount_percent",
    "source_discount_amount",
    "source_target_margin_percent",
    "source_margin_percent",
    "source_margin_basis",
    "source_base_buy_rate",
    "source_landed_cost",
    "source_commission_rate",
    "source_commission_amount",
    "custom_applied_taxes",
    "custom_pu_ttc",
    "custom_pt_ttc",
)

NATIVE_PRICE_FIELDS = (
    "price_list_rate",
    "base_price_list_rate",
    "rate",
    "base_rate",
    "discount_percentage",
)


def copy_quotation_pricing_snapshot(doc, method=None) -> None:
    if not doc or int(flt(_get(doc, "docstatus"))) == 2:
        return

    source_context = _source_context(doc)
    if not source_context.quotation_by_name:
        return

    override = can_override_quotation_pricing()
    _copy_header_snapshot(doc, source_context.first_quotation, overwrite=True)

    for row in _items(doc):
        source_row = source_context.source_row_for(row)
        if not source_row:
            continue
        _copy_row_snapshot(row, source_row, overwrite=True)
        if not override:
            _restore_row_pricing_from_source(row, source_row)
        _refresh_actual_margin(row)
        _refresh_commission(row, enforce_discount_cap=not override)


def copy_sales_invoice_pricing_context(doc, method=None) -> None:
    if not doc or not _has_field(doc, "selected_selling_price_lists"):
        return

    sales_orders = []
    for row in _items(doc):
        sales_order = (_get(row, "sales_order") or "").strip()
        if sales_order and sales_order not in sales_orders:
            sales_orders.append(sales_order)
    if not sales_orders:
        return

    rows = []
    seen = set()
    for sales_order in sales_orders:
        source_doc = frappe.get_doc("Sales Order", sales_order)
        for source_row in source_doc.get("selected_selling_price_lists") or []:
            price_list = (_get(source_row, "price_list") or "").strip()
            if not price_list or price_list in seen:
                continue
            seen.add(price_list)
            rows.append(source_row)

    _set_table(doc, "selected_selling_price_lists", rows)


def validate_sales_order_source_lock(doc, method=None) -> None:
    if not doc:
        return

    item_rows = _items(doc)
    if not item_rows:
        return

    source_context = _source_context(doc)
    override = can_override_quotation_pricing()
    for row in item_rows:
        source_quotation = _row_source_quotation(row)
        source_detail = _row_source_detail(row)
        idx = _get(row, "idx") or "-"
        source_row = source_context.source_row_for(row)

        # A pricing manager may create an independent Sales Order, but linking a
        # row to a Quotation must never silently exceed that quotation snapshot.
        # Running this before the override return also replaces ERPNext's
        # rhetorical "Are you making another Sales Order?" limit message with an
        # actionable explanation.
        if source_row and flt(_get(row, "qty")) > flt(_get(source_row, "qty")) + _field_tolerance(
            "qty",
            row,
            source_row,
        ):
            frappe.throw(
                _(
                    "Sales Order row {0} requests {1} of {2}, but the linked Quotation allows {3}. "
                    "Reduce the quantity, update and resubmit the Quotation, or create an independent Sales Order row without a Quotation link for an approved additional sale."
                ).format(
                    idx,
                    _format_quantity(_get(row, "qty")),
                    _get(row, "item_code") or _get(row, "item_name") or "item",
                    _format_quantity(_get(source_row, "qty")),
                )
            )

        if override:
            continue
        if not source_quotation or not source_detail:
            frappe.throw(
                _("Sales Orders must be created from a submitted Quotation. Row {0} is missing its source Quotation.").format(idx)
            )
        quote = source_context.quotation_by_name.get(source_quotation)
        if not quote:
            frappe.throw(_("Source Quotation {0} on row {1} was not found.").format(source_quotation, idx))
        if int(flt(_get(quote, "docstatus"))) != 1:
            frappe.throw(_("Source Quotation {0} on row {1} must be submitted before creating a Sales Order.").format(source_quotation, idx))
        if not source_row:
            frappe.throw(_("Source Quotation Item {0} on row {1} was not found.").format(source_detail, idx))
        if (_get(row, "item_code") or "").strip() != (_get(source_row, "item_code") or "").strip():
            frappe.throw(_("Sales Order row {0} item must match the source Quotation item.").format(idx))


def validate_sales_order_pricing_locked_to_quotation(doc, method=None) -> None:
    if not doc or can_override_quotation_pricing():
        return

    source_context = _source_context(doc)
    for row in _items(doc):
        source_row = source_context.source_row_for(row)
        if not source_row:
            continue
        idx = _get(row, "idx") or "-"
        for fieldname in NATIVE_PRICE_FIELDS:
            if not _has_field(row, fieldname) or not _has_field(source_row, fieldname):
                continue
            if abs(flt(_get(row, fieldname)) - flt(_get(source_row, fieldname))) > _field_tolerance(
                fieldname,
                row,
                source_row,
            ):
                frappe.throw(_("Sales Order row {0} pricing is locked to its source Quotation.").format(idx))
        rate = flt(_get(row, "rate"))
        expected_amount = rate * flt(_get(row, "qty"))
        if _has_field(row, "net_rate") and abs(flt(_get(row, "net_rate")) - rate) > _field_tolerance(
            "net_rate",
            row,
        ):
            frappe.throw(_("Sales Order row {0} unit price must match its Quotation rate.").format(idx))
        for fieldname in ("amount", "net_amount"):
            if _has_field(row, fieldname) and abs(
                flt(_get(row, fieldname)) - _round_for_field(row, fieldname, expected_amount)
            ) > _field_tolerance(fieldname, row):
                frappe.throw(_("Sales Order row {0} amount must match its source Quotation rate and Sales Order quantity.").format(idx))
        base_rate = flt(_get(row, "base_rate"))
        expected_base_amount = base_rate * flt(_get(row, "qty"))
        if _has_field(row, "base_net_rate") and abs(
            flt(_get(row, "base_net_rate")) - base_rate
        ) > _field_tolerance("base_net_rate", row):
            frappe.throw(_("Sales Order row {0} base unit price must match its Quotation rate.").format(idx))
        for fieldname in ("base_amount", "base_net_amount"):
            if _has_field(row, fieldname) and abs(
                flt(_get(row, fieldname)) - _round_for_field(row, fieldname, expected_base_amount)
            ) > _field_tolerance(fieldname, row):
                frappe.throw(_("Sales Order row {0} base amount must match its source Quotation pricing.").format(idx))


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
        if discount > max_discount + _field_tolerance("source_discount_percent", row):
            frappe.throw(
                _("Pricing Discount % cannot exceed {0}% for {1} on Sales Order row {2}.").format(
                    max_discount,
                    _get(row, "item_code") or _get(row, "item_name") or "item",
                    idx,
                )
            )
        _validate_row_rate_against_snapshot(row, discount)


def _validate_row_rate_against_snapshot(row, discount: float) -> None:
    list_rate = flt(_get(row, "source_price_list_sell_rate"))
    if list_rate <= 0:
        return
    expected_rate = list_rate * (1 - (discount / 100.0))
    if flt(_get(row, "rate")) + _field_tolerance("rate", row) >= expected_rate:
        return
    frappe.throw(
        _("Rate for {0} on Sales Order row {1} is below the inherited pricing policy rate {2}.").format(
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
    if _has_field(doc, "tax_id") and _has_field(quotation, "custom_customer_tax_id"):
        _set(doc, "tax_id", _get(quotation, "custom_customer_tax_id") or "")
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
    qty = flt(_get(row, "qty"))
    rate = flt(_get(row, "rate"))
    base_rate = flt(_get(row, "base_rate"))
    amount = rate * qty
    base_amount = base_rate * qty
    _set_if_field(row, "net_rate", _round_for_field(row, "net_rate", rate))
    _set_if_field(row, "base_net_rate", _round_for_field(row, "base_net_rate", base_rate))
    _set_if_field(row, "amount", _round_for_field(row, "amount", amount))
    _set_if_field(row, "net_amount", _round_for_field(row, "net_amount", amount))
    _set_if_field(row, "base_amount", _round_for_field(row, "base_amount", base_amount))
    _set_if_field(row, "base_net_amount", _round_for_field(row, "base_net_amount", base_amount))


def _refresh_actual_margin(row) -> None:
    landed_cost = flt(_get(row, "source_landed_cost"))
    if landed_cost <= 0 or not _has_field(row, "source_margin_percent"):
        return
    base_buy = flt(_get(row, "source_base_buy_rate"))
    rate = flt(_get(row, "rate"))
    basis = (_get(row, "source_margin_basis") or "Base Price").strip() or "Base Price"
    if basis == "Base Price":
        denominator = base_buy
    elif basis == "Sale Price":
        denominator = rate
    else:
        denominator = landed_cost
    margin_percent = ((rate - landed_cost) / denominator * 100.0) if denominator > 0 else 0.0
    _set(row, "source_margin_percent", margin_percent)


def _refresh_commission(row, *, enforce_discount_cap: bool) -> None:
    if not _has_field(row, "source_commission_amount"):
        return
    try:
        commission = calculate_agent_commission(
            price_list_unit_price=flt(_get(row, "source_price_list_sell_rate")),
            actual_unit_price=flt(_get(row, "rate")),
            qty=flt(_get(row, "qty")),
            max_discount_percent=flt(_get(row, "source_max_discount_percent")),
            commission_rate=flt(_get(row, "source_commission_rate")),
            enforce_discount_cap=enforce_discount_cap,
        )
    except ValueError:
        _set(row, "source_commission_amount", 0)
        return
    _set(
        row,
        "source_commission_amount",
        _round_for_field(
            row,
            "source_commission_amount",
            flt(commission.get("commission_amount")),
        ),
    )


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
    return (_get(row, "quotation_item") or _get(row, "prevdoc_detail_docname") or "").strip()


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


def _field_tolerance(fieldname: str, *rows) -> float:
    precisions = []
    for row in rows:
        precision = getattr(row, "precision", None)
        if not callable(precision):
            continue
        try:
            precisions.append(int(precision(fieldname)))
        except (TypeError, ValueError):
            continue
    precision = max(precisions or [9])
    return min(1e-9, 10 ** (-precision))


def _round_for_field(row, fieldname: str, value: float) -> float:
    precision = getattr(row, "precision", None)
    if callable(precision):
        try:
            return flt(value, int(precision(fieldname)))
        except (TypeError, ValueError):
            pass
    return flt(value, 9)


def _as_dict(row) -> dict:
    if isinstance(row, dict):
        return dict(row)
    converter = getattr(row, "as_dict", None)
    if callable(converter):
        return dict(converter())
    return dict(getattr(row, "__dict__", {}))


def _format_rate(value: float) -> str:
    return f"{flt(value):.2f}".rstrip("0").rstrip(".")


def _format_quantity(value: float) -> str:
    return f"{flt(value):.6f}".rstrip("0").rstrip(".")
