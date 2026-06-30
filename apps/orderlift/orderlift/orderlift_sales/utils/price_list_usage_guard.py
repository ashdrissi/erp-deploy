from __future__ import annotations

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
    if can_override_quotation_pricing():
        return

    price_lists = _quotation_price_lists(doc)
    if not price_lists:
        return

    item_rows = list(doc.get("items") or [])
    item_codes = sorted({(row.get("item_code") or "").strip() for row in item_rows if (row.get("item_code") or "").strip()})
    if not item_codes:
        return

    price_map = _get_transaction_item_price_map(item_codes, price_lists, kind="selling")
    for row in item_rows:
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            continue
        prices = price_map.get(item_code) or []
        if not prices:
            continue
        selected_price = _selected_row_price(row, prices)
        current_rate = _flt(row.get("rate"))
        source_list = (row.get("source_selling_price_list") or "").strip()

        if selected_price:
            if current_rate + 0.000001 < _price_floor(selected_price):
                _apply_price_to_quotation_row(row, selected_price)
            continue

        if not source_list and any(current_rate + 0.000001 >= _price_floor(price) for price in prices):
            continue

        _apply_price_to_quotation_row(row, prices[0])

    for row in item_rows:
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
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


def validate_sales_order_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="selling_price_list", kind="selling")
    _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling")


def validate_sales_invoice_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="selling_price_list", kind="selling")
    _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling")


def validate_delivery_note_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="selling_price_list", kind="selling")
    _validate_transaction_items_priced(doc, fieldname="selling_price_list", kind="selling")


def validate_purchase_order_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="buying_price_list", kind="buying")
    _validate_transaction_items_priced(doc, fieldname="buying_price_list", kind="buying")


def validate_purchase_invoice_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="buying_price_list", kind="buying")
    _validate_transaction_items_priced(doc, fieldname="buying_price_list", kind="buying")


def validate_purchase_receipt_price_list(doc, method=None):
    _validate_doc_price_list(doc, fieldname="buying_price_list", kind="buying")
    _validate_transaction_items_priced(doc, fieldname="buying_price_list", kind="buying")


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
        if not item_code:
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


def _has_policy_pricing_source(doc, item_rows: list[dict]) -> bool:
    if not (doc.get("source_pricing_sheet") or "").strip():
        return False
    return bool(item_rows) and all(_flt(row.get("source_gross_sell_rate")) > 0 for row in item_rows)


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
    rate = _flt(row.get("rate"))
    margin_amount = rate - landed_cost
    margin_pct = _compute_margin_pct(margin_amount, margin_basis, buy_price, landed_cost)
    _set_row_value(row, "source_margin_percent", margin_pct)
    _set_row_value(row, "source_margin_basis", margin_basis)


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
