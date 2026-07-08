from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from orderlift.orderlift_sales.utils.price_list_scope import (
    BENCHMARK_PRICE_LIST,
    current_company,
    get_item_price_access,
    get_price_list_type,
    validate_price_list_scope,
    validate_visible_price_list,
)
from orderlift.warehouse_access import stock_warehouse_condition


PRICE_TYPE_CONFIG = {
    "buying": {"kind": "buying", "buying": 1, "selling": 0, "label": "Buying"},
    "selling": {"kind": "selling", "buying": 0, "selling": 1, "label": "Selling"},
}

OPTIONAL_ITEM_PRICE_FIELDS = ("brand", "currency", "enabled", "valid_from", "valid_upto", "buying", "selling")
TRANSACTION_ITEM_PRICE_FIELDS = (
    "custom_pricing_builder",
    "custom_source_buying_price_list",
    "custom_benchmark_policy",
    "custom_benchmark_is_fallback",
    "custom_benchmark_rule_label",
    "custom_benchmark_rule_max_discount_percent",
    "custom_fallback_max_discount_percent",
    "custom_policy_max_discount_percent",
)
ITEM_PRICE_CHILD_TABLES = {
    "buying": "custom_buying_item_prices",
    "selling": "custom_selling_item_prices",
}
ITEM_PRICE_MIRROR_DOCTYPES = (
    "Orderlift Item Buying Price",
    "Orderlift Item Selling Price",
)


def apply_item_price_defaults(doc, method=None):
    item_code = (doc.get("item_code") or "").strip()
    if not item_code or not _doc_has_field(doc, "uom") or (doc.get("uom") or "").strip():
        return

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    if stock_uom:
        doc.uom = stock_uom


def mark_direct_builder_price_override(doc, method=None):
    if _skip_direct_builder_override_tracking(doc):
        return
    if not _is_selling_item_price(doc):
        return

    builder_name = (doc.get("custom_pricing_builder") or "").strip()
    if not builder_name or not _doc_has_field(doc, "custom_builder_price_overridden"):
        return
    if not _price_list_rate_changed(doc):
        return

    doc.custom_builder_price_overridden = 1
    flags = getattr(doc, "flags", None)
    if flags is not None:
        flags.orderlift_direct_builder_price_override = True


def sync_builder_override_from_item_price(doc, method=None):
    flags = getattr(doc, "flags", None)
    if not getattr(flags, "orderlift_direct_builder_price_override", False):
        return
    _sync_builder_item_override(doc)


def cleanup_item_price_mirror_rows(doc, method=None):
    item_price = (doc.get("name") or "").strip()
    if not item_price:
        return
    for doctype in ITEM_PRICE_MIRROR_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        frappe.db.delete(doctype, {"item_price": item_price})


def _skip_direct_builder_override_tracking(doc):
    flags = getattr(frappe, "flags", None)
    return bool(
        getattr(flags, "orderlift_pricing_builder_publish", False)
        or getattr(flags, "orderlift_auto_rebuild_item_price", False)
        or getattr(flags, "orderlift_syncing_item_price_tables", False)
        or getattr(doc, "__islocal", False)
    )


def _is_selling_item_price(doc):
    if _doc_has_field(doc, "selling") and cint(doc.get("selling") or 0):
        return True
    if _doc_has_field(doc, "buying") and cint(doc.get("buying") or 0):
        return False
    price_list = (doc.get("price_list") or "").strip()
    if not price_list:
        return False
    try:
        return get_price_list_type(price_list) == "Selling"
    except Exception:
        return False


def _price_list_rate_changed(doc):
    before_getter = getattr(doc, "get_doc_before_save", None)
    before = before_getter() if callable(before_getter) else None
    if not before:
        return False
    return flt(getattr(before, "price_list_rate", 0)) != flt(doc.get("price_list_rate") or 0)


def _sync_builder_item_override(doc):
    builder_name = (doc.get("custom_pricing_builder") or "").strip()
    item_code = (doc.get("item_code") or "").strip()
    if not builder_name or not item_code or flt(doc.get("price_list_rate") or 0) <= 0:
        return
    if not frappe.db.exists("Pricing Builder", builder_name):
        return

    filters = {"parent": builder_name, "item": item_code}
    source_buying_list = (doc.get("custom_source_buying_price_list") or "").strip()
    if source_buying_list:
        filters["buying_list"] = source_buying_list

    rows = frappe.get_all("Pricing Builder Item", filters=filters, fields=["name"], limit_page_length=2)
    if len(rows) != 1:
        return

    frappe.db.set_value(
        "Pricing Builder Item",
        rows[0].name,
        "override_selling_price",
        flt(doc.get("price_list_rate") or 0),
        update_modified=False,
    )


def load_item_price_child_tables(doc, method=None):
    item_code = (doc.get("name") or doc.get("item_code") or "").strip()
    if not item_code or item_code == "AUTO" or not frappe.db.exists("Item", item_code):
        return

    _load_item_stock_snapshot(doc, item_code)

    for price_type, table_field in ITEM_PRICE_CHILD_TABLES.items():
        if not _doc_has_field(doc, table_field):
            continue
        config = _price_type_config(price_type)
        access = get_item_price_access(config["kind"])
        if not access["permitted"]:
            doc.set(table_field, [])
            continue
        allowed = access["price_lists"]
        rows = []
        for row in _get_item_price_rows(item_code, config, allowed):
            rows.append(
                {
                    "item_price": row.get("name") or "",
                    "price_list": row.get("price_list") or "",
                    "price_list_rate": flt(row.get("price_list_rate") or 0),
                    "uom": row.get("uom") or doc.get("stock_uom") or "",
                    "currency": _price_list_currency(row.get("price_list")),
                    "valid_from": row.get("valid_from") or None,
                    "valid_upto": row.get("valid_upto") or None,
                    "brand": row.get("brand") or "",
                }
            )
        doc.set(table_field, rows)


def _load_item_stock_snapshot(doc, item_code: str) -> None:
    table_field = "custom_company_warehouse_stock"
    total_field = "custom_company_stock_total"
    list_total_field = "custom_current_company_stock_qty"
    has_table = _doc_has_field(doc, table_field)
    has_total = _doc_has_field(doc, total_field)
    has_list_total = _doc_has_field(doc, list_total_field)
    if not (has_table or has_total or has_list_total):
        return

    rows = _warehouse_stock_rows(item_code)
    total = sum(flt(row.get("actual_qty") or 0) for row in rows)
    if has_table:
        doc.set(table_field, rows)
    if has_total:
        doc.set(total_field, total)
    if has_list_total:
        doc.set(list_total_field, total)


def sync_item_price_child_tables(doc, method=None):
    item_code = (doc.get("name") or doc.get("item_code") or "").strip()
    if not item_code or item_code == "AUTO" or getattr(frappe.flags, "orderlift_syncing_item_price_tables", False):
        return

    frappe.flags.orderlift_syncing_item_price_tables = True
    try:
        for price_type, table_field in ITEM_PRICE_CHILD_TABLES.items():
            if not _doc_has_field(doc, table_field):
                continue
            config = _price_type_config(price_type)
            access = get_item_price_access(config["kind"])
            if not access["permitted"]:
                # User cannot manage this price kind (e.g. a sales agent and buying
                # prices) — leave existing Item Prices untouched, don't block the save.
                continue
            allowed = access["price_lists"]
            for child in doc.get(table_field) or []:
                price_list = child.get("price_list") or ""
                row = {
                    "name": child.get("item_price") or "",
                    "price_list": price_list,
                    "price_list_rate": child.get("price_list_rate") or 0,
                    "uom": child.get("uom") or doc.get("stock_uom") or "",
                    "currency": _price_list_currency(price_list),
                    "valid_from": child.get("valid_from") or None,
                    "valid_upto": child.get("valid_upto") or None,
                    "brand": child.get("brand") or "",
                    "enabled": 1,
                }
                if not _row_has_values(row):
                    continue
                result = _upsert_item_price_row(item_code, config, row, allowed=allowed)
                item_price = result.get("row", {}).get("name") or ""
                if item_price and child.get("name") and child.get("item_price") != item_price:
                    frappe.db.set_value(child.doctype, child.name, "item_price", item_price, update_modified=False)
    finally:
        frappe.flags.orderlift_syncing_item_price_tables = False


@frappe.whitelist()
def get_item_price_grid(item_code: str, price_type: str) -> dict:
    item_code = _validate_item(item_code, permission_type="read")
    config = _price_type_config(price_type)
    _check_item_price_permission("read")
    if config["kind"] == "buying":
        _assert_price_kind_access(config, permission_type="read")

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or ""
    access = get_item_price_access(config["kind"])
    allowed = access["price_lists"]
    rows = _get_item_price_rows(item_code, config, allowed) if access["permitted"] else []
    return {
        "item_code": item_code,
        "price_type": config["kind"],
        "permitted": access["permitted"],
        "restricted": access["restricted"],
        "stock_uom": stock_uom,
        "price_lists": _price_lists_for(allowed),
        "fields": _available_item_price_fields(),
        "rows": rows,
    }


@frappe.whitelist()
def save_item_price_grid(item_code: str, price_type: str, rows=None) -> dict:
    item_code = _validate_item(item_code, permission_type="read")
    config = _price_type_config(price_type)
    rows = _parse_rows(rows)
    allowed = _allowed_price_lists_or_throw(config)

    summary = {"created": 0, "updated": 0, "skipped": 0, "rows": []}
    for row in rows:
        if not _row_has_values(row):
            summary["skipped"] += 1
            continue
        result = _upsert_item_price_row(item_code, config, row, allowed=allowed)
        summary[result["action"]] += 1
        summary["rows"].append(result["row"])

    return summary


@frappe.whitelist()
def get_quick_price_rows(item_codes=None, price_type="selling", price_list="") -> dict:
    config = _price_type_config(price_type)
    item_codes = _clean_list(_parse_json(item_codes, item_codes or []))
    if not item_codes:
        frappe.throw(_("Select at least one Item."))
    _check_item_price_permission("read")

    access = get_item_price_access(config["kind"])
    if not access["permitted"]:
        frappe.throw(_("You are not allowed to manage {0} prices.").format(config["label"].lower()))

    if price_list:
        price_list = validate_price_list_scope(price_list, kind=config["kind"], required=True)
        _assert_price_list_allowed(price_list, access)

    items = _item_details(item_codes)
    existing = _latest_prices_by_item(item_codes, price_list, config) if price_list else {}
    rows = []
    for item_code in item_codes:
        item = items.get(item_code)
        if not item:
            continue
        current = existing.get(item_code) or {}
        rows.append(
            {
                "name": current.get("name") or "",
                "item_code": item_code,
                "item_name": item.get("item_name") or item_code,
                "stock_uom": item.get("stock_uom") or "",
                "uom": current.get("uom") or item.get("stock_uom") or "",
                "price_list_rate": flt(current.get("price_list_rate") or 0),
                "currency": current.get("currency") or _price_list_currency(price_list),
            }
        )

    return {
        "price_type": config["kind"],
        "price_list": price_list,
        "permitted": access["permitted"],
        "restricted": access["restricted"],
        "price_lists": _price_lists_for(access["price_lists"]),
        "rows": rows,
    }


@frappe.whitelist()
def save_quick_item_prices(price_type="selling", price_list="", rows=None) -> dict:
    config = _price_type_config(price_type)
    price_list = validate_price_list_scope(price_list, kind=config["kind"], required=True)
    rows = _parse_rows(rows)
    if not rows:
        frappe.throw(_("Enter at least one Item Price row."))

    summary = {"created": 0, "updated": 0, "skipped": 0, "rows": []}
    for row in rows:
        item_code = _validate_item(row.get("item_code"), permission_type="read")
        clean = dict(row)
        clean["price_list"] = price_list
        if not _row_has_values(clean):
            summary["skipped"] += 1
            continue
        allowed = _allowed_price_lists_or_throw(config)
        result = _upsert_item_price_row(item_code, config, clean, allowed=allowed)
        summary[result["action"]] += 1
        summary["rows"].append(result["row"])

    return summary


@frappe.whitelist()
def get_item_list_stock_totals(item_codes=None) -> dict:
    item_codes = _clean_list(_parse_json(item_codes, item_codes or []))
    company = (current_company() or "").strip()
    if not item_codes:
        return {"current_company": company, "rows": {}}

    _check_item_permission("read")
    params = {"item_codes": tuple(item_codes), "company": company}
    rows = frappe.db.sql(
        f"""
        SELECT b.item_code, SUM(b.actual_qty) AS stock_qty
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code IN %(item_codes)s
        AND w.company = %(company)s
        {_warehouse_disabled_condition("w")}
        {stock_warehouse_condition("b.warehouse", params)}
        GROUP BY b.item_code
        """,
        params,
        as_dict=True,
    )
    stock_by_item = {row.item_code: flt(row.stock_qty) for row in rows}
    return {
        "current_company": company,
        "rows": {item_code: stock_by_item.get(item_code, 0) for item_code in item_codes},
    }


@frappe.whitelist()
def get_transaction_stock_snapshot(item_codes=None, company=None) -> dict:
    item_codes = _clean_list(_parse_json(item_codes, item_codes or []))
    company = (company or current_company() or "").strip()
    if not item_codes:
        return {"current_company": company, "rows": [], "totals": {}}

    _check_item_permission("read")
    if not company:
        return {"current_company": "", "rows": [], "totals": {item_code: 0 for item_code in item_codes}}

    params = {"item_codes": tuple(item_codes), "company": company}
    rows = frappe.db.sql(
        f"""
        SELECT
            i.name AS item_code,
            i.item_name AS item_name,
            w.name AS warehouse,
            COALESCE(SUM(b.actual_qty), 0) AS actual_qty
        FROM `tabItem` i
        INNER JOIN `tabWarehouse` w ON w.company = %(company)s
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = w.name
        WHERE i.name IN %(item_codes)s
        {_warehouse_disabled_condition("w")}
        {stock_warehouse_condition("w.name", params)}
        GROUP BY i.name, i.item_name, w.name
        ORDER BY i.name ASC, w.name ASC
        """,
        params,
        as_dict=True,
    )
    totals = {item_code: 0.0 for item_code in item_codes}
    out_rows = []
    for row in rows:
        item_code = row.get("item_code") or ""
        qty = flt(row.get("actual_qty") or 0)
        if item_code in totals:
            totals[item_code] += qty
        out_rows.append(
            {
                "item_code": item_code,
                "item_name": row.get("item_name") or item_code,
                "warehouse": row.get("warehouse") or "",
                "actual_qty": qty,
            }
        )
    return {"current_company": company, "rows": out_rows, "totals": totals}


@frappe.whitelist()
def get_item_stock_snapshot(item_code: str = "") -> dict:
    item_code = _validate_item(item_code, permission_type="read")
    rows = _warehouse_stock_rows(item_code)
    total = sum(flt(row.get("actual_qty") or 0) for row in rows)
    return {
        "item_code": item_code,
        "current_company": (current_company() or "").strip(),
        "rows": rows,
        "total": total,
    }


@frappe.whitelist()
def get_item_list_price_lists() -> dict:
    company = (current_company() or "").strip()
    price_lists = []
    seen = set()
    for kind in ("selling", "buying", "benchmark"):
        access = get_item_price_access(kind)
        if not access["permitted"]:
            continue
        for row in _price_lists_for(access["price_lists"]):
            name = row.get("name") or ""
            if not name or name in seen:
                continue
            seen.add(name)
            price_lists.append({**row, "type": kind})
    return {"current_company": company, "price_lists": price_lists}


@frappe.whitelist()
def get_items_for_price_list(price_list: str = "") -> dict:
    price_list = (price_list or "").strip()
    if not price_list:
        frappe.throw(_("Price List is required."))

    kind = _price_list_kind(price_list)
    price_list = validate_price_list_scope(price_list, kind=kind, required=True)
    access = get_item_price_access(kind)
    if not access["permitted"]:
        frappe.throw(_("You are not allowed to use {0} price lists.").format(kind))
    _assert_price_list_allowed(price_list, access)
    _check_item_permission("read")

    conditions = ["ip.price_list = %(price_list)s"]
    if _doctype_has_column("Item Price", kind):
        conditions.append(f"ifnull(ip.{kind}, 0) = 1")
    if _doctype_has_column("Item Price", "enabled"):
        conditions.append("ifnull(ip.enabled, 1) = 1")
    if _doctype_has_column("Item", "disabled"):
        conditions.append("ifnull(i.disabled, 0) = 0")

    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT ip.item_code
        FROM `tabItem Price` ip
        INNER JOIN `tabItem` i ON i.name = ip.item_code
        WHERE {' AND '.join(conditions)}
        ORDER BY ip.item_code ASC
        """,
        {"price_list": price_list},
        as_dict=True,
    )
    item_codes = [row.item_code for row in rows if row.item_code]
    return {"price_list": price_list, "price_type": kind, "item_codes": item_codes, "count": len(item_codes)}


@frappe.whitelist()
def item_query_for_transaction_price_list(doctype, txt, searchfield, start, page_len, filters=None):
    filters = filters or {}
    price_list = (filters.get("price_list") or "").strip()
    price_lists = _clean_list(_parse_json(filters.get("price_lists"), []))
    kind = (filters.get("price_list_type") or filters.get("kind") or "selling").strip().lower()
    if kind not in {"selling", "buying"}:
        kind = "selling"
    if price_list and price_list not in price_lists:
        price_lists.append(price_list)
    if not price_lists:
        return []
    price_lists = [validate_visible_price_list(value, kind=kind, required=True) for value in price_lists]

    txt = (txt or "").strip()
    start = cint(start)
    page_len = cint(page_len) or 20
    params = {
        "price_lists": tuple(price_lists),
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }
    conditions = ["ip.price_list in %(price_lists)s"]
    if _doctype_has_column("Item Price", kind):
        conditions.append(f"ifnull(ip.{kind}, 0) = 1")
    if _doctype_has_column("Item Price", "enabled"):
        conditions.append("ifnull(ip.enabled, 1) = 1")
    if _doctype_has_column("Item", "disabled"):
        conditions.append("ifnull(i.disabled, 0) = 0")
    if txt:
        conditions.append("(i.name like %(txt)s or i.item_name like %(txt)s)")

    return frappe.db.sql(
        f"""
        SELECT DISTINCT i.name, i.item_name
        FROM `tabItem Price` ip
        INNER JOIN `tabItem` i ON i.name = ip.item_code
        WHERE {' AND '.join(conditions)}
        ORDER BY i.name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        params,
    )


@frappe.whitelist()
def get_transaction_item_prices(item_codes=None, price_list="", price_lists=None, price_list_type="selling") -> dict:
    item_codes = _clean_list(_parse_json(item_codes, item_codes or []))
    price_lists = _clean_list(_parse_json(price_lists, price_lists or []))
    if price_list and price_list not in price_lists:
        price_lists.append((price_list or "").strip())
    kind = (price_list_type or "selling").strip().lower()
    if kind not in {"selling", "buying"}:
        kind = "selling"
    if kind == "buying":
        _assert_price_kind_access(PRICE_TYPE_CONFIG["buying"], permission_type="read")
    if not item_codes:
        return {"rows": {}}

    validated_lists = _valid_transaction_price_lists(price_lists, kind=kind)
    if not validated_lists and kind == "selling":
        validated_lists = _current_static_agent_selling_price_lists()
    if not validated_lists:
        return {"rows": {}, "price_lists": []}
    rows = _resolve_transaction_item_prices(item_codes, validated_lists, kind=kind)
    if kind == "selling":
        commission_rate = _current_agent_commission_rate()
        for row in rows.values():
            row["commission_rate"] = commission_rate
    return {"rows": rows, "price_lists": validated_lists}


def _resolve_transaction_item_prices(item_codes: list[str], price_lists: list[str], *, kind: str) -> dict[str, dict]:
    remaining = [item_code for item_code in item_codes if item_code]
    resolved: dict[str, dict] = {}
    for price_list in price_lists or []:
        if not remaining:
            break
        current_rows = _latest_item_prices_by_list(remaining, price_list, kind=kind)
        for item_code, row in current_rows.items():
            if item_code in resolved:
                continue
            resolved[item_code] = {
                "price_list": price_list,
                "price_list_rate": flt(row.get("price_list_rate") or 0),
                "max_discount_percent": _item_price_max_discount_percent(row),
            }
        remaining = [item_code for item_code in remaining if item_code not in resolved]
    return resolved


def _latest_item_prices_by_list(item_codes: list[str], price_list: str, *, kind: str) -> dict[str, dict]:
    if not item_codes or not price_list:
        return {}
    params = {
        "item_codes": tuple(item_codes),
        "price_list": price_list,
        "today": nowdate(),
    }
    conditions = [
        "ip.item_code in %(item_codes)s",
        "ip.price_list = %(price_list)s",
    ]
    if _doctype_has_column("Item Price", kind):
        conditions.append(f"ifnull(ip.{kind}, 0) = 1")
    if _doctype_has_column("Item Price", "enabled"):
        conditions.append("ifnull(ip.enabled, 1) = 1")
    if _doctype_has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if _doctype_has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")
    order_by = "ip.item_code ASC, ip.valid_from DESC, ip.modified DESC" if _doctype_has_column("Item Price", "valid_from") else "ip.item_code ASC, ip.modified DESC"
    fields = ["ip.item_code", "ip.price_list_rate"]
    for fieldname in TRANSACTION_ITEM_PRICE_FIELDS:
        if _doctype_has_column("Item Price", fieldname):
            fields.append(f"ip.{fieldname}")

    rows = frappe.db.sql(
        f"""
        SELECT {', '.join(fields)}
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        """,
        params,
        as_dict=True,
    )
    resolved = {}
    for row in rows:
        if row.item_code not in resolved:
            resolved[row.item_code] = row
    return resolved


def _item_price_max_discount_percent(row) -> float:
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
        if cint(row.get("custom_benchmark_is_fallback") or 0):
            return flt(row.get("custom_fallback_max_discount_percent") or 0)
        return flt(row.get("custom_benchmark_rule_max_discount_percent") or 0)
    return flt(
        row.get("custom_policy_max_discount_percent")
        or row.get("custom_benchmark_rule_max_discount_percent")
        or row.get("custom_fallback_max_discount_percent")
        or 0
    )


def _valid_transaction_price_lists(price_lists: list[str], *, kind: str) -> list[str]:
    out = []
    for value in price_lists or []:
        if kind == "buying":
            price_list = validate_visible_price_list(value, kind=kind, required=True)
        else:
            try:
                price_list = validate_visible_price_list(value, kind=kind, required=True)
            except Exception:
                continue
        if price_list and price_list not in out:
            out.append(price_list)
    return out


def _current_static_agent_selling_price_lists() -> list[str]:
    sales_person = _current_user_sales_person()
    if not sales_person:
        return []
    from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import STATIC_MODE, build_static_context

    context = build_static_context(sales_person=sales_person)
    if (context.get("pricing_mode") or "") != STATIC_MODE:
        return []
    return _valid_transaction_price_lists(context.get("selling_price_lists") or [], kind="selling")


def _current_agent_commission_rate() -> float:
    sales_person = _current_user_sales_person()
    if not sales_person:
        return 0.0
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name")
    if not agent_name:
        return 0.0
    return flt(frappe.db.get_value("Agent Pricing Rules", agent_name, "commission_rate") or 0)


def _current_user_sales_person() -> str:
    if not frappe.db.exists("DocType", "Sales Person") or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": frappe.session.user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def _warehouse_stock_rows(item_code: str) -> list[dict]:
    company = (current_company() or "").strip()
    if not item_code or not company:
        return []
    params = {"item_code": item_code, "company": company}
    rows = frappe.db.sql(
        f"""
        SELECT w.name AS warehouse, COALESCE(SUM(b.actual_qty), 0) AS actual_qty
        FROM `tabWarehouse` w
        LEFT JOIN `tabBin` b ON b.warehouse = w.name AND b.item_code = %(item_code)s
        WHERE w.company = %(company)s
        {_warehouse_disabled_condition("w")}
        {stock_warehouse_condition("w.name", params)}
        GROUP BY w.name
        ORDER BY w.name ASC
        """,
        params,
        as_dict=True,
    )
    return [
        {"warehouse": row.warehouse, "actual_qty": flt(row.actual_qty)}
        for row in rows
        if row.warehouse
    ]


def _warehouse_disabled_condition(alias="w") -> str:
    if not _doctype_has_column("Warehouse", "disabled"):
        return ""
    return f"AND ifnull({alias}.disabled, 0) = 0"


def _get_item_price_rows(item_code: str, config: dict, allowed=None) -> list[dict]:
    fields = ["name", "item_code", "price_list", "price_list_rate", "uom"]
    for fieldname in OPTIONAL_ITEM_PRICE_FIELDS:
        if _doctype_has_column("Item Price", fieldname):
            fields.append(fieldname)

    filters = {"item_code": item_code}
    if allowed is not None:
        if not allowed:
            return []
        filters["price_list"] = ["in", allowed]
    if _doctype_has_column("Item Price", config["kind"]):
        filters[config["kind"]] = 1

    order_by = "price_list asc, valid_from desc, modified desc" if _doctype_has_column("Item Price", "valid_from") else "price_list asc, modified desc"
    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=fields,
        order_by=order_by,
        limit_page_length=0,
    )
    return [_serialize_item_price_row(row) for row in rows]


def _upsert_item_price_row(item_code: str, config: dict, row: dict, allowed=None) -> dict:
    price_list = validate_price_list_scope(row.get("price_list"), kind=config["kind"], required=True)
    if allowed is not None and price_list not in set(allowed):
        frappe.throw(_("Price List {0} is not allowed for your current company/access.").format(price_list))
    name = (row.get("name") or "").strip()
    action = "updated"
    if name:
        doc = frappe.get_doc("Item Price", name)
        if (doc.get("item_code") or "").strip() != item_code:
            frappe.throw(_("Item Price {0} does not belong to Item {1}.").format(name, item_code))
        doc.check_permission("write")
    else:
        _check_item_price_permission("create")
        existing = _latest_item_price_name(item_code, price_list, config)
        if existing:
            doc = frappe.get_doc("Item Price", existing)
            doc.check_permission("write")
        else:
            doc = frappe.new_doc("Item Price")
            action = "created"

    doc.item_code = item_code
    doc.price_list = price_list
    doc.price_list_rate = flt(row.get("price_list_rate") or 0)
    _set_if_field(doc, "uom", (row.get("uom") or "").strip() or frappe.db.get_value("Item", item_code, "stock_uom") or "")
    _set_if_field(doc, "currency", _price_list_currency(price_list))
    _set_if_field(doc, "valid_from", row.get("valid_from") or None)
    _set_if_field(doc, "valid_upto", row.get("valid_upto") or None)
    _set_if_field(doc, "brand", (row.get("brand") or "").strip())
    if _doc_has_field(doc, "enabled"):
        doc.enabled = 1 if cint(row.get("enabled", 1)) else 0
    if _doc_has_field(doc, "buying"):
        doc.buying = config["buying"]
    if _doc_has_field(doc, "selling"):
        doc.selling = config["selling"]

    apply_item_price_defaults(doc)
    if doc.is_new():
        doc.insert()
    else:
        doc.save()
    return {"action": action, "row": _serialize_item_price_doc(doc)}


def _latest_item_price_name(item_code: str, price_list: str, config: dict) -> str:
    filters = {"item_code": item_code, "price_list": price_list}
    if _doctype_has_column("Item Price", config["kind"]):
        filters[config["kind"]] = 1
    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=["name"],
        order_by="valid_from desc, modified desc" if _doctype_has_column("Item Price", "valid_from") else "modified desc",
        limit_page_length=1,
    )
    return rows[0].name if rows else ""


def _latest_prices_by_item(item_codes: list[str], price_list: str, config: dict) -> dict:
    if not item_codes or not price_list:
        return {}
    fields = ["name", "item_code", "price_list_rate", "uom"]
    for fieldname in ("currency", "valid_from"):
        if _doctype_has_column("Item Price", fieldname):
            fields.append(fieldname)
    filters = {"item_code": ["in", item_codes], "price_list": price_list}
    if _doctype_has_column("Item Price", config["kind"]):
        filters[config["kind"]] = 1
    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=fields,
        order_by="item_code asc, valid_from desc, modified desc" if _doctype_has_column("Item Price", "valid_from") else "item_code asc, modified desc",
        limit_page_length=0,
    )
    out = {}
    for row in rows:
        out.setdefault(row.item_code, dict(row))
    return out


def _serialize_item_price_row(row) -> dict:
    return {
        "name": row.get("name") or "",
        "item_code": row.get("item_code") or "",
        "price_list": row.get("price_list") or "",
        "price_list_rate": flt(row.get("price_list_rate") or 0),
        "uom": row.get("uom") or "",
        "currency": row.get("currency") or _price_list_currency(row.get("price_list")),
        "valid_from": row.get("valid_from") or "",
        "valid_upto": row.get("valid_upto") or "",
        "brand": row.get("brand") or "",
        "enabled": 1 if cint(row.get("enabled", 1)) else 0,
    }


def _serialize_item_price_doc(doc) -> dict:
    return _serialize_item_price_row({fieldname: doc.get(fieldname) for fieldname in ["name", "item_code", "price_list", "price_list_rate", "uom", "currency", "valid_from", "valid_upto", "brand", "enabled"]})


def _item_details(item_codes: list[str]) -> dict:
    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_name", "stock_uom"],
        limit_page_length=0,
    )
    return {row.name: {"item_name": row.item_name, "stock_uom": row.stock_uom} for row in rows}


def _price_lists_for(price_lists) -> list[dict]:
    names = [name for name in (price_lists or []) if name]
    if not names:
        return []
    rows = frappe.get_all(
        "Price List",
        filters={"name": ["in", names]},
        fields=["name", "currency"],
        order_by="name asc",
        limit_page_length=0,
    )
    default_currency = frappe.defaults.get_global_default("currency") or ""
    return [{"name": row.name, "currency": row.currency or default_currency} for row in rows]


def _price_list_currency(price_list: str | None) -> str:
    price_list = (price_list or "").strip()
    if not price_list:
        return frappe.defaults.get_global_default("currency") or ""
    return frappe.db.get_value("Price List", price_list, "currency") or frappe.defaults.get_global_default("currency") or ""


def _price_list_kind(price_list: str) -> str:
    fields = ["name"]
    if _doctype_has_column("Price List", "custom_price_list_type"):
        fields.append("custom_price_list_type")
    if _doctype_has_column("Price List", "selling"):
        fields.append("selling")
    if _doctype_has_column("Price List", "buying"):
        fields.append("buying")
    values = frappe.db.get_value("Price List", price_list, fields, as_dict=True)
    if not values:
        frappe.throw(_("Price List {0} does not exist.").format(price_list))
    if get_price_list_type(values=values) == BENCHMARK_PRICE_LIST:
        return "benchmark"
    if cint(values.get("selling")) == 1:
        return "selling"
    if cint(values.get("buying")) == 1:
        return "buying"
    frappe.throw(_("Price List {0} must be a buying or selling price list.").format(price_list))


def _price_type_config(price_type: str) -> dict:
    key = (price_type or "").strip().lower()
    if key in {"sale", "sales"}:
        key = "selling"
    if key not in PRICE_TYPE_CONFIG:
        frappe.throw(_("Price type must be Buying or Selling."))
    return PRICE_TYPE_CONFIG[key]


def _available_item_price_fields() -> dict:
    return {fieldname: _doctype_has_column("Item Price", fieldname) for fieldname in OPTIONAL_ITEM_PRICE_FIELDS}


def _validate_item(item_code: str, permission_type: str = "read") -> str:
    item_code = (item_code or "").strip()
    if not item_code:
        frappe.throw(_("Item is required."))
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} does not exist.").format(item_code))
    doc = frappe.get_doc("Item", item_code)
    doc.check_permission(permission_type)
    return item_code


def _check_item_price_permission(permission_type: str) -> None:
    frappe.has_permission("Item Price", permission_type, throw=True)


def _check_item_permission(permission_type: str) -> None:
    checker = getattr(frappe, "has_permission", None)
    if callable(checker):
        checker("Item", permission_type, throw=True)


def _allowed_price_lists_or_throw(config: dict) -> list[str]:
    return _assert_price_kind_access(config, permission_type="write")


def _assert_price_kind_access(config: dict, permission_type: str = "read") -> list[str]:
    access = get_item_price_access(config["kind"])
    if not access["permitted"]:
        frappe.throw(_("You are not allowed to manage {0} prices.").format(config["label"].lower()))
    _check_item_price_permission(permission_type)
    return access["price_lists"]


def _assert_price_list_allowed(price_list: str, access: dict) -> None:
    if price_list and price_list not in set(access.get("price_lists") or []):
        frappe.throw(_("Price List {0} is not allowed for your current company/access.").format(price_list))


def _row_has_values(row: dict) -> bool:
    return bool((row.get("price_list") or "").strip())


def _set_if_field(doc, fieldname: str, value) -> None:
    if _doc_has_field(doc, fieldname):
        doc.set(fieldname, value)


def _doc_has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    has_field = getattr(meta, "has_field", None)
    if callable(has_field):
        return bool(has_field(fieldname))
    return hasattr(doc, fieldname)


def _doctype_has_column(doctype: str, fieldname: str) -> bool:
    checker = getattr(getattr(frappe, "db", None), "has_column", None)
    return bool(checker(doctype, fieldname)) if callable(checker) else False


def _parse_rows(rows) -> list[dict]:
    parsed = _parse_json(rows, rows or [])
    if not isinstance(parsed, list):
        frappe.throw(_("Rows payload must be a list."))
    return [row for row in parsed if isinstance(row, dict)]


def _parse_json(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value or "")
        except ValueError:
            return default
    return value if value is not None else default


def _clean_list(values) -> list[str]:
    out = []
    for value in values or []:
        text = (value or "").strip()
        if text and text not in out:
            out.append(text)
    return out
