from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import nowdate

from orderlift.role_capabilities import CAPABILITY_PRIVILEGED_PRICING, role_capability_decision
from orderlift.orderlift_sales.utils.price_list_scope import PRIVILEGED_PRICE_ROLES, can_override_quotation_pricing, validate_visible_price_list


ITEM_PRICE_MAX_DISCOUNT_FIELDS = (
    "custom_pricing_builder",
    "custom_source_buying_price_list",
    "custom_benchmark_policy",
    "custom_benchmark_is_fallback",
    "custom_benchmark_rule_label",
    "custom_benchmark_rule_max_discount_percent",
    "custom_fallback_max_discount_percent",
    "custom_policy_max_discount_percent",
)

ITEM_PRICE_MARGIN_STAMP_FIELDS = (
    "custom_final_margin_percent",
    "custom_last_builder_buy_rate",
    "custom_builder_expense_amount",
    "custom_builder_customs_amount",
    "custom_builder_margin_basis",
    "custom_source_buying_price_list",
    "custom_target_margin_percent",
)

MANUAL_CHARGE_ITEM_CODES = {"OTHER-CHARGES", "TRANSPORTATION-CHARGE"}


@dataclass(frozen=True)
class TrustedPricingSourceResult:
    trusted: bool
    reason: str
    source_doctypes: tuple[str, ...] = ()
    source_documents: tuple[str, ...] = ()


def validate_quotation_price_list(doc, method=None):
    price_lists = _quotation_price_lists(doc)
    _validate_doc_price_lists(price_lists, kind="selling", company=(doc.get("company") or "").strip())
    if not can_override_quotation_pricing():
        _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling", price_lists=price_lists)
    if not price_lists and getattr(doc, "meta", None) and doc.meta.get_field("selling_price_list"):
        doc.selling_price_list = ""


def reprice_quotation_items_from_selected_price_lists(doc) -> None:
    if not doc or int(_flt(getattr(doc, "docstatus", 0))) != 0:
        return
    pricing_override = can_override_quotation_pricing()

    price_lists = _quotation_price_lists(doc)
    if not price_lists:
        return

    item_rows = list(doc.get("items") or [])
    item_codes = sorted({
        (row.get("item_code") or "").strip()
        for row in item_rows
        if (row.get("item_code") or "").strip() and not _is_manual_charge_item(row.get("item_code"))
    })
    if not item_codes:
        return

    price_map = _get_transaction_item_price_map(item_codes, price_lists, kind="selling")
    for row in item_rows:
        item_code = (row.get("item_code") or "").strip()
        if not item_code or _is_manual_charge_item(item_code):
            continue
        prices = price_map.get(item_code) or []
        if not prices:
            continue
        selected_price = _selected_row_price(row, prices)
        current_rate = _flt(row.get("rate"))
        source_list = (row.get("source_selling_price_list") or "").strip()

        if selected_price:
            if not pricing_override and current_rate + 0.000001 < _price_floor(selected_price):
                _apply_price_to_quotation_row(row, selected_price)
            continue

        if not source_list and any(current_rate + 0.000001 >= _price_floor(price) for price in prices):
            continue

        if pricing_override:
            continue
        _apply_price_to_quotation_row(row, prices[0])

    for row in item_rows:
        item_code = (row.get("item_code") or "").strip()
        if not item_code or _is_manual_charge_item(item_code):
            continue
        prices = price_map.get(item_code) or []
        selected_price = _selected_row_price(row, prices)
        if not selected_price:
            if prices:
                for price in prices:
                    if (price.get("custom_pricing_builder") or "").strip():
                        _stamp_margin_on_quotation_row(row, price)
                        break
            continue
        _stamp_margin_on_quotation_row(row, selected_price)


def sync_sales_order_margin_snapshots(doc, method=None) -> None:
    """Keep transaction profitability separate from ERPNext's native uplift fields.

    Quotation-sourced rows retain their frozen cost and target snapshots while
    their actual margin follows the final Sales Order rate. Standalone privileged
    orders are stamped from their selected selling Item Price.
    """
    if not doc or int(_flt(getattr(doc, "docstatus", 0))) == 2:
        return

    item_rows = list(doc.get("items") or [])
    unresolved = []
    for row in item_rows:
        if _flt(row.get("source_landed_cost")) > 0:
            _recalculate_margin_from_snapshot(row)
        elif (row.get("item_code") or "").strip() and not _is_manual_charge_item(row.get("item_code")):
            unresolved.append(row)

    if not unresolved:
        return

    price_lists = _transaction_price_lists(doc, fieldname="selling_price_list")
    if not price_lists:
        return
    item_codes = sorted({(row.get("item_code") or "").strip() for row in unresolved})
    price_map = _get_transaction_item_price_map(item_codes, price_lists, kind="selling")
    for row in unresolved:
        prices = price_map.get((row.get("item_code") or "").strip()) or []
        selected_price = _selected_row_price(row, prices)
        if not selected_price:
            selected_price = next(
                (price for price in prices if (price.get("custom_pricing_builder") or "").strip()),
                None,
            )
        if selected_price:
            _stamp_margin_on_quotation_row(row, selected_price)


def validate_sales_order_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="selling_price_list", kind="selling")
    if not can_override_quotation_pricing():
        if _has_quotation_pricing_source(doc):
            return
        _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling")


def validate_sales_invoice_price_list(doc, method=None):
    source_result = _trusted_sales_source(doc)
    if source_result.trusted:
        return source_result
    _validate_doc_price_list(doc, fieldname="selling_price_list", kind="selling")
    if not can_override_quotation_pricing():
        _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling")
    return source_result


def validate_delivery_note_price_list(doc, method=None):
    source_result = _trusted_sales_source(doc)
    if source_result.trusted:
        return source_result
    _validate_doc_price_list(doc, fieldname="selling_price_list", kind="selling")
    if not can_override_quotation_pricing():
        _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling")
    return source_result


def validate_purchase_order_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="buying_price_list", kind="buying")
    _validate_transaction_items_priced(doc, fieldname="buying_price_list", kind="buying")


def validate_purchase_invoice_price_list(doc, method=None):
    source_result = _trusted_purchase_source(doc)
    if source_result.trusted:
        return source_result
    _validate_doc_price_list(doc, fieldname="buying_price_list", kind="buying")
    _validate_transaction_items_priced(doc, fieldname="buying_price_list", kind="buying")
    return source_result


def validate_purchase_receipt_price_list(doc, method=None):
    source_result = _trusted_purchase_source(doc)
    if source_result.trusted:
        return source_result
    _validate_doc_price_list(doc, fieldname="buying_price_list", kind="buying")
    _validate_transaction_items_priced(doc, fieldname="buying_price_list", kind="buying")
    return source_result


def _validate_doc_price_list(doc, *, fieldname: str, kind: str):
    if not doc:
        return
    if hasattr(doc, "meta") and getattr(doc.meta, "has_field", None) and not doc.meta.has_field(fieldname):
        return
    value = (getattr(doc, fieldname, "") or "").strip()
    if not value:
        return
    validate_visible_price_list(value, kind=kind, required=True)


def _validate_doc_price_lists(price_lists: list[str], *, kind: str, company: str | None = None) -> None:
    for value in price_lists or []:
        validate_visible_price_list(value, kind=kind, required=True, company=company)


def _validate_transaction_items_priced(doc, *, fieldname: str, kind: str, price_lists: list[str] | None = None) -> None:
    if hasattr(doc, "meta") and getattr(doc.meta, "has_field", None) and not doc.meta.has_field(fieldname):
        return
    price_lists = [value for value in (price_lists or _transaction_price_lists(doc, fieldname=fieldname)) if value]
    item_rows = _transaction_item_rows(doc)
    item_codes = sorted({row["item_code"] for row in item_rows})
    if not item_codes:
        return

    if not price_lists:
        if kind == "selling" and not _has_policy_pricing_source(doc, item_rows):
            frappe.throw(_("Selling Price List is required before adding priced sales items."))
        return

    if _can_bypass_item_price_restriction(kind=kind):
        return

    price_map = _get_transaction_item_price_map(item_codes, price_lists, kind=kind)
    priced = set(price_map)
    missing = [item_code for item_code in item_codes if item_code not in priced]
    if missing:
        label = _("Selling Price List") if kind == "selling" else _("Buying Price List")
        joined_lists = ", ".join(price_lists)
        frappe.throw(_("Items not priced in {0} {1}: {2}").format(label, joined_lists, ", ".join(missing[:10])))
    if kind == "selling":
        _validate_selling_item_rates(item_rows, price_map)


def _transaction_item_rows(doc) -> list[dict]:
    out = []
    for row in doc.get("items") or []:
        item_code = (row.get("item_code") or "").strip()
        if not item_code or _is_manual_charge_item(item_code):
            continue
        out.append(
            {
                "item_code": item_code,
                "rate": row.get("rate"),
                "idx": row.get("idx"),
                "source_selling_price_list": row.get("source_selling_price_list"),
                "source_gross_sell_rate": row.get("source_gross_sell_rate"),
            }
        )
    return out


def _is_manual_charge_item(item_code: str | None) -> bool:
    return (item_code or "").strip() in MANUAL_CHARGE_ITEM_CODES


def _has_policy_pricing_source(doc, item_rows: list[dict]) -> bool:
    if not (doc.get("source_pricing_sheet") or "").strip():
        return False
    return bool(item_rows) and all(_flt(row.get("source_gross_sell_rate")) > 0 for row in item_rows)


def _has_quotation_pricing_source(doc) -> bool:
    if not doc or getattr(doc, "doctype", "") not in ("", "Sales Order"):
        return False
    item_rows = _transaction_item_rows(doc)
    if not item_rows:
        return False
    for row in doc.get("items") or []:
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            continue
        source_doctype = (row.get("prevdoc_doctype") or "").strip()
        source_docname = (row.get("prevdoc_docname") or "").strip()
        source_detail = (row.get("prevdoc_detail_docname") or "").strip()
        if source_doctype and source_doctype != "Quotation":
            return False
        if not source_docname or not source_detail or _flt(row.get("source_gross_sell_rate")) <= 0:
            return False
    return True


def _has_submitted_sales_order_pricing_source(doc) -> bool:
    return _trusted_sales_source(doc).trusted


def _trusted_sales_source(doc) -> TrustedPricingSourceResult:
    doctype = getattr(doc, "doctype", "")
    if doctype not in {"Sales Invoice", "Delivery Note"}:
        return _untrusted_source(f"{doctype or 'Document'} is not a supported sales target.")
    item_rows = _source_validated_item_rows(doc)
    if not item_rows:
        return _untrusted_source("No priced sales rows were found.")

    sales_orders = {}
    for row in item_rows:
        sales_order = _text(
            _value(row, "sales_order") or _value(row, "against_sales_order")
        )
        sales_order_detail = _text(_value(row, "so_detail"))
        if not sales_order or not sales_order_detail:
            return _untrusted_source("A sales row has no Sales Order source.")
        if sales_order not in sales_orders:
            sales_orders[sales_order] = frappe.get_doc("Sales Order", sales_order)
        source_doc = sales_orders[sales_order]
        if int(_flt(source_doc.get("docstatus"))) != 1:
            return _untrusted_source(f"Sales Order {sales_order} is not submitted.")
        mismatch = _parent_context_mismatch(
            doc,
            source_doc,
            party_field="customer",
            price_list_field="selling_price_list",
        )
        if mismatch:
            return _untrusted_source(f"Sales Order {sales_order}: {mismatch}")
        source_row = _source_document_row(source_doc, sales_order_detail)
        if not source_row:
            return _untrusted_source(
                f"Sales Order row {sales_order_detail} was not found."
            )
        mismatch = _row_context_mismatch(row, source_row)
        if mismatch:
            return _untrusted_source(
                f"Sales Order row {sales_order_detail}: {mismatch}"
            )

    return TrustedPricingSourceResult(
        trusted=True,
        reason="Every sales row matches a submitted Sales Order source.",
        source_doctypes=("Sales Order",),
        source_documents=tuple(sales_orders),
    )


def _trusted_purchase_source(doc) -> TrustedPricingSourceResult:
    doctype = getattr(doc, "doctype", "")
    if doctype not in {"Purchase Receipt", "Purchase Invoice"}:
        return _untrusted_source(
            f"{doctype or 'Document'} is not a supported purchase target."
        )
    item_rows = _source_validated_item_rows(doc)
    if not item_rows:
        return _untrusted_source("No priced purchase rows were found.")

    source_documents = {}
    source_types = []
    for row in item_rows:
        reference = _purchase_source_reference(doctype, row)
        if not reference:
            return _untrusted_source("A purchase row has no submitted source row.")
        source_doctype, source_name, source_detail = reference
        cache_key = (source_doctype, source_name)
        if cache_key not in source_documents:
            source_documents[cache_key] = frappe.get_doc(source_doctype, source_name)
        source_doc = source_documents[cache_key]
        if int(_flt(source_doc.get("docstatus"))) != 1:
            return _untrusted_source(
                f"{source_doctype} {source_name} is not submitted."
            )
        mismatch = _parent_context_mismatch(
            doc,
            source_doc,
            party_field="supplier",
            price_list_field="buying_price_list",
        )
        if mismatch:
            return _untrusted_source(
                f"{source_doctype} {source_name}: {mismatch}"
            )
        source_row = _source_document_row(source_doc, source_detail)
        if not source_row:
            return _untrusted_source(
                f"{source_doctype} row {source_detail} was not found."
            )
        mismatch = _row_context_mismatch(row, source_row)
        if mismatch:
            return _untrusted_source(
                f"{source_doctype} row {source_detail}: {mismatch}"
            )
        if source_doctype not in source_types:
            source_types.append(source_doctype)

    return TrustedPricingSourceResult(
        trusted=True,
        reason="Every purchase row matches a submitted Purchase Order or Purchase Receipt source.",
        source_doctypes=tuple(source_types),
        source_documents=tuple(name for _doctype, name in source_documents),
    )


def _purchase_source_reference(doctype: str, row) -> tuple[str, str, str] | None:
    if doctype == "Purchase Receipt":
        source_name = _text(_value(row, "purchase_order"))
        source_detail = _text(_value(row, "purchase_order_item"))
        if source_name and source_detail:
            return "Purchase Order", source_name, source_detail
        return None

    purchase_receipt = _text(_value(row, "purchase_receipt"))
    receipt_detail = _text(_value(row, "pr_detail"))
    if purchase_receipt or receipt_detail:
        if purchase_receipt and receipt_detail:
            return "Purchase Receipt", purchase_receipt, receipt_detail
        return None

    purchase_order = _text(_value(row, "purchase_order"))
    order_detail = _text(
        _value(row, "po_detail") or _value(row, "purchase_order_item")
    )
    if purchase_order and order_detail:
        return "Purchase Order", purchase_order, order_detail
    return None


def _source_validated_item_rows(doc) -> list:
    return [
        row
        for row in (_value(doc, "items") or [])
        if _text(_value(row, "item_code"))
        and not _is_manual_charge_item(_value(row, "item_code"))
    ]


def _source_document_row(source_doc, detail_name: str):
    for row in _value(source_doc, "items") or []:
        if _text(_value(row, "name")) == detail_name:
            return row
    return None


def _parent_context_mismatch(
    target_doc,
    source_doc,
    *,
    party_field: str,
    price_list_field: str,
) -> str:
    fields = (
        ("company", "company"),
        (party_field, party_field),
        ("currency", "currency"),
        (price_list_field, price_list_field),
    )
    for fieldname, label in fields:
        target_value = _text(_value(target_doc, fieldname))
        source_value = _text(_value(source_doc, fieldname))
        if not target_value or not source_value:
            return f"{label} is missing."
        if target_value != source_value:
            return f"{label} does not match."

    target_conversion = _flt(_value(target_doc, "conversion_rate"))
    source_conversion = _flt(_value(source_doc, "conversion_rate"))
    if target_conversion <= 0 or source_conversion <= 0:
        return "conversion rate is missing."
    if not _numbers_match(target_conversion, source_conversion, tolerance=0.000000001):
        return "conversion rate does not match."
    return ""


def _row_context_mismatch(target_row, source_row) -> str:
    target_item = _text(_value(target_row, "item_code"))
    source_item = _text(_value(source_row, "item_code"))
    if not target_item or target_item != source_item:
        return "item code does not match."

    target_uom = _text(_value(target_row, "uom"))
    source_uom = _text(_value(source_row, "uom"))
    if not target_uom or target_uom != source_uom:
        return "UOM does not match."

    target_conversion = _flt(_value(target_row, "conversion_factor"))
    source_conversion = _flt(_value(source_row, "conversion_factor"))
    if target_conversion <= 0 or source_conversion <= 0:
        return "UOM conversion factor is missing."
    if not _numbers_match(target_conversion, source_conversion, tolerance=0.000000001):
        return "UOM conversion factor does not match."

    if not _numbers_match(
        _flt(_value(target_row, "rate")),
        _flt(_value(source_row, "rate")),
        tolerance=_rate_tolerance(target_row, source_row),
    ):
        return "rate does not match."
    return ""


def _rate_tolerance(*rows) -> float:
    precisions = []
    for row in rows:
        precision = getattr(row, "precision", None)
        if callable(precision):
            try:
                precisions.append(int(precision("rate")))
            except (TypeError, ValueError):
                pass
    precision = max(precisions or [6])
    return 0.5 * (10 ** (-precision))


def _numbers_match(left: float, right: float, *, tolerance: float) -> bool:
    return abs(_flt(left) - _flt(right)) <= tolerance


def _value(obj, fieldname: str, default=None):
    if obj is None:
        return default
    getter = getattr(obj, "get", None)
    if callable(getter):
        value = getter(fieldname)
        return default if value is None else value
    return getattr(obj, fieldname, default)


def _text(value) -> str:
    return str(value or "").strip()


def _untrusted_source(reason: str) -> TrustedPricingSourceResult:
    return TrustedPricingSourceResult(trusted=False, reason=reason)


def _item_prices_by_item(rows: list[dict], price_lists: list[str]) -> dict[str, list[dict]]:
    by_key = {}
    for row in rows:
        item_code = row.get("item_code")
        price_list = row.get("price_list")
        if item_code and price_list and (item_code, price_list) not in by_key:
            by_key[(item_code, price_list)] = row

    resolved = {}
    for price_list in price_lists:
        for (item_code, row_price_list), row in by_key.items():
            if row_price_list != price_list:
                continue
            resolved.setdefault(item_code, []).append(row)
    return resolved


def _get_transaction_item_price_map(item_codes: list[str], price_lists: list[str], *, kind: str) -> dict[str, list[dict]]:
    conditions = [
        "ip.price_list in %(price_lists)s",
        "ip.item_code in %(item_codes)s",
    ]
    if frappe.db.has_column("Item Price", kind):
        conditions.append(f"ifnull(ip.{kind}, 0) = 1")
    if frappe.db.has_column("Item Price", "enabled"):
        conditions.append("ifnull(ip.enabled, 1) = 1")
    if frappe.db.has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if frappe.db.has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")
    fields = ["ip.item_code", "ip.price_list", "ip.price_list_rate"]
    for fieldname in ITEM_PRICE_MAX_DISCOUNT_FIELDS:
        if frappe.db.has_column("Item Price", fieldname):
            fields.append(f"ip.{fieldname}")
    for fieldname in ITEM_PRICE_MARGIN_STAMP_FIELDS:
        if frappe.db.has_column("Item Price", fieldname):
            fields.append(f"ip.{fieldname}")
    order_by = "ip.item_code ASC, ip.price_list ASC"
    if frappe.db.has_column("Item Price", "valid_from"):
        order_by += ", ip.valid_from DESC"
    order_by += ", ip.modified DESC"

    rows = frappe.db.sql(
        f"""
        SELECT {', '.join(fields)}
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        """,
        {"price_lists": tuple(price_lists), "item_codes": tuple(item_codes), "today": nowdate()},
        as_dict=True,
    )
    return _item_prices_by_item(rows or [], price_lists)


def _apply_price_to_quotation_row(row, price: dict) -> None:
    gross_rate = _flt(price.get("price_list_rate"))
    max_discount = _item_price_max_discount_percent(price)
    discount = _flt(row.get("source_discount_percent") or row.get("discount_percentage") or 0)
    if discount < 0:
        discount = 0.0
    if discount > max_discount:
        discount = max_discount
    qty = _flt(row.get("qty") or 1) or 1
    net_rate = gross_rate * (1 - (discount / 100.0))

    values = {
        "price_list_rate": gross_rate,
        "rate": net_rate,
        "amount": net_rate * qty,
        "discount_percentage": discount,
        "source_selling_price_list": price.get("price_list") or "",
        "source_price_list_sell_rate": gross_rate,
        "source_gross_sell_rate": gross_rate,
        "source_max_discount_percent": max_discount,
        "source_discount_percent": discount,
        "source_discount_amount": gross_rate - net_rate,
        "source_discounted_sell_rate": net_rate,
    }
    for fieldname, value in values.items():
        _set_row_value(row, fieldname, value)
    _stamp_margin_on_quotation_row(row, price)


def _set_row_value(row, fieldname: str, value) -> None:
    if not _row_has_field(row, fieldname):
        return
    setter = getattr(row, "set", None)
    if callable(setter):
        setter(fieldname, value)
    elif isinstance(row, dict):
        row[fieldname] = value
    else:
        setattr(row, fieldname, value)


def _row_has_field(row, fieldname: str) -> bool:
    meta = getattr(row, "meta", None)
    getter = getattr(meta, "get_field", None)
    if callable(getter):
        return bool(getter(fieldname))
    return True


def _stamp_margin_on_quotation_row(row, item_price: dict) -> None:
    builder_name = (item_price.get("custom_pricing_builder") or "").strip()
    if not builder_name:
        return
    buy_price = _flt(item_price.get("custom_last_builder_buy_rate"))
    expenses = _flt(item_price.get("custom_builder_expense_amount"))
    customs = _flt(item_price.get("custom_builder_customs_amount"))
    margin_basis = (item_price.get("custom_builder_margin_basis") or "").strip() or "Base Price"
    landed_cost = buy_price + expenses + customs
    _set_row_value(row, "source_target_margin_percent", _flt(item_price.get("custom_target_margin_percent")))
    _set_row_value(row, "source_base_buy_rate", buy_price)
    _set_row_value(row, "source_landed_cost", landed_cost)
    _set_row_value(row, "source_margin_basis", margin_basis)
    _set_row_value(row, "source_pricing_policy", (item_price.get("custom_benchmark_policy") or "").strip())
    _recalculate_margin_from_snapshot(row)


def _recalculate_margin_from_snapshot(row) -> None:
    landed_cost = _flt(row.get("source_landed_cost"))
    if landed_cost <= 0:
        return
    rate = _flt(row.get("rate"))
    margin_pct = _compute_margin_pct(
        rate - landed_cost,
        row.get("source_margin_basis"),
        _flt(row.get("source_base_buy_rate")),
        landed_cost,
    )
    _set_row_value(row, "source_margin_percent", margin_pct)


def _compute_margin_pct(margin_amount, margin_basis, base_unit, landed_cost):
    amount = _flt(margin_amount)
    basis = (margin_basis or "Base Price").strip() or "Base Price"
    if basis == "Base Price":
        denominator = _flt(base_unit)
    elif basis == "Sale Price":
        denominator = _flt(landed_cost) + amount
    else:
        denominator = _flt(landed_cost)
    if denominator <= 0:
        return 0.0
    return (amount / denominator) * 100.0


def _validate_selling_item_rates(item_rows: list[dict], price_map: dict[str, list[dict]]) -> None:
    for row in item_rows:
        prices = price_map.get(row["item_code"]) or []
        if not prices:
            continue
        current_rate = _flt(row.get("rate"))
        selected_price = _selected_row_price(row, prices)
        if (row.get("source_selling_price_list") or "").strip() and not selected_price:
            frappe.throw(
                _("Item {0} on row {1} is not priced in selected Selling Price List {2}.").format(
                    row["item_code"],
                    row.get("idx") or "-",
                    row.get("source_selling_price_list") or "",
                )
            )
        if selected_price:
            _throw_if_below_price_floor(row, current_rate, selected_price)
            continue
        if any(current_rate + 0.000001 >= _price_floor(price) for price in prices):
            continue
        best_price = min(prices, key=_price_floor)
        _throw_if_below_price_floor(row, current_rate, best_price)


def _selected_row_price(row: dict, prices: list[dict]) -> dict | None:
    selected_list = (row.get("source_selling_price_list") or "").strip()
    if not selected_list:
        return None
    return next((price for price in prices if (price.get("price_list") or "").strip() == selected_list), None)


def _throw_if_below_price_floor(row: dict, current_rate: float, price: dict) -> None:
    minimum_rate = _price_floor(price)
    if current_rate + 0.000001 >= minimum_rate:
        return
    frappe.throw(
        _("Rate for {0} on row {1} is below the allowed net rate {2} from Selling Price List {3}.").format(
            row["item_code"],
            row.get("idx") or "-",
            _format_money(minimum_rate),
            price.get("price_list") or "",
        )
    )


def _price_floor(price: dict) -> float:
    list_rate = _flt(price.get("price_list_rate"))
    max_discount = _item_price_max_discount_percent(price)
    return list_rate * (1 - (max_discount / 100.0))


def _item_price_max_discount_percent(row: dict) -> float:
    has_builder_stamp = any(
        row.get(fieldname) not in (None, "")
        for fieldname in (
            "custom_pricing_builder",
            "custom_source_buying_price_list",
            "custom_benchmark_policy",
            "custom_benchmark_rule_label",
        )
    )
    if has_builder_stamp:
        if int(_flt(row.get("custom_benchmark_is_fallback"))):
            return _flt(row.get("custom_fallback_max_discount_percent"))
        return _flt(row.get("custom_benchmark_rule_max_discount_percent"))
    return _flt(
        row.get("custom_policy_max_discount_percent")
        or row.get("custom_benchmark_rule_max_discount_percent")
        or row.get("custom_fallback_max_discount_percent")
        or 0
    )


def _flt(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _format_money(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _transaction_price_lists(doc, *, fieldname: str) -> list[str]:
    rows = getattr(doc, "selected_selling_price_lists", None) or []
    active_rows = [row for row in rows if (row.get("price_list") or "").strip() and int(row.get("is_active") or 0) == 1]
    active_rows = sorted(active_rows, key=lambda row: (int(row.get("sequence") or 0) or 999999, row.get("idx") or 0))
    price_lists = []
    for row in active_rows:
        price_list = (row.get("price_list") or "").strip()
        if price_list and price_list not in price_lists:
            price_lists.append(price_list)
    primary = (getattr(doc, fieldname, "") or "").strip()
    if primary and primary not in price_lists:
        price_lists.append(primary)
    return price_lists


def _quotation_price_lists(doc) -> list[str]:
    rows = getattr(doc, "selected_selling_price_lists", None) or []
    active_rows = [row for row in rows if (row.get("price_list") or "").strip() and int(row.get("is_active") or 0) == 1]
    active_rows = sorted(active_rows, key=lambda row: (int(row.get("sequence") or 0) or 999999, row.get("idx") or 0))
    price_lists = []
    for row in active_rows:
        price_list = (row.get("price_list") or "").strip()
        if price_list and price_list not in price_lists:
            price_lists.append(price_list)
    return price_lists


def _can_bypass_item_price_restriction(kind: str | None = None) -> bool:
    user = frappe.session.user
    if user == "Administrator":
        return True
    if (kind or "").strip().lower() == "selling":
        return False
    roles = set(frappe.get_roles(user) or [])
    return role_capability_decision(
        CAPABILITY_PRIVILEGED_PRICING,
        bool(roles & PRIVILEGED_PRICE_ROLES),
        user=user,
        roles=roles,
        context="can_bypass_item_price_restriction",
    )
