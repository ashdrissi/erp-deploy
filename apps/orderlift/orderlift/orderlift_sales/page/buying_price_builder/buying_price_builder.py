from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from orderlift.orderlift_sales.doctype.buying_price_formula_rule.buying_price_formula_rule import serialize_rule
from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import get_latest_item_prices
from orderlift.orderlift_sales.utils.price_list_scope import (
    apply_price_list_company,
    current_company,
    get_item_price_access,
    get_price_lists,
    validate_visible_price_list,
)
from orderlift.orderlift_sales.utils.buying_price_builder import calculate_preview_rows, normalize_formula_rules


PRICING_WRITE_ROLES = {"Orderlift Admin", "Orderlift Business Admin", "Pricing Manager", "Purchase Manager", "System Manager"}


@frappe.whitelist()
def get_builder_payload():
    _require_buying_price_access("read")
    return {
        "current_company": current_company(),
        "price_lists": get_buying_price_lists(),
        "formula_rules": get_formula_rules(),
    }


@frappe.whitelist()
def get_buying_price_lists():
    access = _require_buying_price_access("read")
    allowed = set(access.get("price_lists") or [])
    rows = get_price_lists("buying", fields=["name", "currency"])
    return [{"name": row.name, "currency": row.currency or ""} for row in rows if row.name in allowed]


@frappe.whitelist()
def search_items(query="", source_price_list="", limit=500):
    _require_buying_price_access("read")
    query = (query or "").strip()
    source_price_list = (source_price_list or "").strip()
    if source_price_list:
        source_price_list = _validate_buying_price_list(source_price_list, required=True)
    limit = max(1, min(cint(limit or 500), 500))
    item_rows = _search_item_rows(query, limit)
    return _enrich_item_rows(item_rows, source_price_list)


@frappe.whitelist()
def get_items_from_price_lists(price_lists, limit=2000):
    _require_buying_price_access("read")
    price_lists = _clean_list(_parse_payload(price_lists) if isinstance(price_lists, str) else price_lists)
    if not price_lists:
        return []
    for price_list in price_lists:
        _validate_buying_price_list(price_list, required=True)
    limit = max(1, min(cint(limit or 2000), 5000))
    has_enabled = frappe.db.has_column("Item Price", "enabled")
    conditions = ["ip.price_list IN %(price_lists)s"]
    if has_enabled:
        conditions.append("ifnull(ip.enabled, 1) = 1")
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT ip.item_code
        FROM `tabItem Price` ip
        INNER JOIN `tabItem` i ON i.name = ip.item_code
        WHERE {' AND '.join(conditions)}
        ORDER BY ip.item_code ASC
        LIMIT %(limit)s
        """,
        {"price_lists": tuple(price_lists), "limit": limit},
        as_dict=True,
    )
    item_rows = _get_item_rows([row.item_code for row in rows])
    return _enrich_item_rows(item_rows, price_lists[0])


@frappe.whitelist()
def get_formula_rules(enabled_only=1):
    _require_buying_price_access("read")
    filters = {"is_active": 1} if cint(enabled_only) else {}
    names = frappe.get_all(
        "Buying Price Formula Rule",
        filters=filters,
        pluck="name",
        order_by="modified desc",
        limit_page_length=0,
    )
    return [serialize_rule(frappe.get_doc("Buying Price Formula Rule", name)) for name in names]


@frappe.whitelist()
def save_formula_rule(payload):
    _require_pricing_write()
    _require_buying_price_access("write")
    payload = _parse_payload(payload)
    name = (payload.get("docname") or payload.get("doctype_name") or payload.get("name") or "").strip()
    doc = frappe.get_doc("Buying Price Formula Rule", name) if name and frappe.db.exists("Buying Price Formula Rule", name) else frappe.new_doc("Buying Price Formula Rule")
    if not doc.is_new():
        doc.check_permission("write")
    doc.rule_name = (payload.get("rule_name") or payload.get("label") or payload.get("display_name") or "").strip()
    doc.source_item = (payload.get("source") or payload.get("source_item") or "").strip()
    doc.is_active = 1 if cint(payload.get("checked", payload.get("is_active", 1))) else 0
    doc.notes = payload.get("notes") or ""
    doc.set("targets", [])
    for row in payload.get("targets") or []:
        target_item = (row.get("code") or row.get("target_item") or row.get("item_code") or "").strip()
        if not target_item:
            continue
        doc.append(
            "targets",
            {
                "target_item": target_item,
                "adjustment_percent": flt(row.get("pct", row.get("adjustment_percent", 0))),
                "is_active": 1 if cint(row.get("is_active", 1)) else 0,
            },
        )
    doc.save()
    return serialize_rule(doc)


@frappe.whitelist()
def delete_formula_rule(name):
    _require_pricing_write()
    _require_buying_price_access("write")
    name = (name or "").strip()
    if not name or not frappe.db.exists("Buying Price Formula Rule", name):
        frappe.throw(_("Formula rule does not exist."))
    doc = frappe.get_doc("Buying Price Formula Rule", name)
    doc.check_permission("delete")
    frappe.delete_doc("Buying Price Formula Rule", name)
    return {"deleted": name}


@frappe.whitelist()
def calculate_preview(payload):
    _require_buying_price_access("read")
    payload = _parse_payload(payload)
    source_price_list = (payload.get("source_price_list") or payload.get("sourcePriceList") or "").strip()
    _validate_buying_price_list(source_price_list, required=True)
    item_codes = _clean_list(payload.get("item_codes") or payload.get("workingItems") or [])
    item_rows = _get_item_rows(item_codes)
    item_rows = _enrich_item_rows(item_rows, source_price_list)
    manual_prices = payload.get("manual_prices") or payload.get("manualPrices") or {}
    formula_rules = payload.get("formula_rules") or payload.get("formulas") or []
    fixed_percent = payload.get("fixed_percent") or {}
    rows = calculate_preview_rows(
        item_rows,
        manual_prices=manual_prices,
        formula_rules=formula_rules,
        fixed_percent=fixed_percent,
    )
    return {"rows": rows, "warnings": [], "source_price_list": source_price_list}


@frappe.whitelist()
def save_result(payload):
    _require_pricing_write()
    _require_buying_price_access("write")
    payload = _parse_payload(payload)
    save_mode = (payload.get("save_mode") or payload.get("saveMode") or "new").strip().lower()
    target_price_list = (payload.get("target_price_list") or payload.get("target") or "").strip()
    if not target_price_list:
        target_price_list = (payload.get("newPriceList") if save_mode == "new" else payload.get("updatePriceList") or "").strip()
    if not target_price_list:
        frappe.throw(_("Target buying price list is required."))
    target_price_list = _ensure_target_buying_price_list(target_price_list, create=save_mode == "new")
    preview_payload = dict(payload)
    preview_payload["source_price_list"] = payload.get("source_price_list") or payload.get("sourcePriceList")
    preview = calculate_preview(preview_payload)
    currency = frappe.db.get_value("Price List", target_price_list, "currency") or frappe.defaults.get_global_default("currency")

    created = updated = skipped = 0
    warnings = []
    for row in preview.get("rows") or []:
        item_code = (row.get("item_code") or "").strip()
        final_price = flt(row.get("final_price"))
        if not item_code or final_price < 0:
            skipped += 1
            continue
        existing_name = _get_latest_item_price_name(item_code, target_price_list)
        if existing_name:
            doc = frappe.get_doc("Item Price", existing_name)
            doc.price_list_rate = final_price
            _apply_item_price_defaults(doc, item_code, target_price_list, currency)
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc = frappe.new_doc("Item Price")
            doc.item_code = item_code
            doc.price_list = target_price_list
            doc.price_list_rate = final_price
            _apply_item_price_defaults(doc, item_code, target_price_list, currency)
            doc.insert(ignore_permissions=True)
            created += 1

    frappe.db.commit()
    return {
        "price_list": target_price_list,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "warnings": warnings,
        "rows": preview.get("rows") or [],
    }


def _search_item_rows(query, limit):
    has_disabled = frappe.db.has_column("Item", "disabled")
    has_brand = frappe.db.has_column("Item", "brand")
    has_category = frappe.db.has_column("Item", "custom_item_category")
    has_item_price_brand = frappe.db.has_column("Item Price", "brand")
    columns = [
        "i.name AS item_code",
        "i.item_name AS item_name",
        "i.item_group AS item_group",
        "i.stock_uom AS uom",
        "i.brand AS item_brand" if has_brand else "'' AS item_brand",
        "i.custom_item_category AS category" if has_category else "'' AS category",
    ]
    conditions = []
    params = {"limit": limit}
    if has_disabled:
        conditions.append("ifnull(i.disabled, 0) = 0")
    if query:
        params["query"] = f"%{query}%"
        search_terms = [
            "i.name LIKE %(query)s",
            "i.item_name LIKE %(query)s",
            "i.item_group LIKE %(query)s",
        ]
        if has_brand:
            search_terms.append("i.brand LIKE %(query)s")
        if has_category:
            search_terms.append("i.custom_item_category LIKE %(query)s")
        if has_item_price_brand:
            search_terms.append("EXISTS (SELECT 1 FROM `tabItem Price` ip WHERE ip.item_code = i.name AND ip.brand LIKE %(query)s)")
        conditions.append("(" + " OR ".join(search_terms) + ")")
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return frappe.db.sql(
        f"""
        SELECT {', '.join(columns)}
        FROM `tabItem` i
        {where_sql}
        ORDER BY i.name ASC
        LIMIT %(limit)s
        """,
        params,
        as_dict=True,
    )


def _get_item_rows(item_codes):
    item_codes = _clean_list(item_codes)
    if not item_codes:
        return []
    has_brand = frappe.db.has_column("Item", "brand")
    has_category = frappe.db.has_column("Item", "custom_item_category")
    columns = [
        "name AS item_code",
        "item_name",
        "item_group",
        "stock_uom AS uom",
        "brand AS item_brand" if has_brand else "'' AS item_brand",
        "custom_item_category AS category" if has_category else "'' AS category",
    ]
    rows = frappe.db.sql(
        f"""
        SELECT {', '.join(columns)}
        FROM `tabItem`
        WHERE name IN %(item_codes)s
        """,
        {"item_codes": tuple(item_codes)},
        as_dict=True,
    )
    order = {code: idx for idx, code in enumerate(item_codes)}
    return sorted(rows, key=lambda row: order.get(row.item_code, 999999))


def _enrich_item_rows(item_rows, source_price_list):
    item_codes = [row.item_code for row in item_rows]
    price_map = get_latest_item_prices(item_codes, source_price_list, buying=True) if source_price_list else {}
    brand_map = _get_item_price_brand_map(item_codes, source_price_list) if source_price_list else {}
    out = []
    for row in item_rows:
        out.append(
            {
                "item_code": row.item_code,
                "item_name": row.item_name or row.item_code,
                "brand": row.item_brand or brand_map.get(row.item_code) or "",
                "category": row.category or "",
                "item_group": row.item_group or "",
                "uom": row.uom or "",
                "list_price": flt(price_map.get(row.item_code) or 0),
            }
        )
    return out


def _get_item_price_brand_map(item_codes, price_list):
    if not item_codes or not price_list or not frappe.db.has_column("Item Price", "brand"):
        return {}
    rows = frappe.db.sql(
        """
        SELECT item_code, brand
        FROM `tabItem Price`
        WHERE item_code IN %(item_codes)s AND price_list = %(price_list)s AND ifnull(brand, '') != ''
        ORDER BY item_code ASC, modified DESC
        """,
        {"item_codes": tuple(item_codes), "price_list": price_list},
        as_dict=True,
    )
    out = {}
    for row in rows:
        out.setdefault(row.item_code, row.brand)
    return out


def _ensure_target_buying_price_list(price_list_name, create=False):
    if frappe.db.exists("Price List", price_list_name):
        return _validate_buying_price_list(price_list_name, required=True)
    if not create:
        frappe.throw(_("Buying Price List {0} does not exist.").format(price_list_name))
    doc = frappe.new_doc("Price List")
    if hasattr(doc, "price_list_name"):
        doc.price_list_name = price_list_name
    doc.name = price_list_name
    if hasattr(doc, "buying"):
        doc.buying = 1
    if hasattr(doc, "selling"):
        doc.selling = 0
    if hasattr(doc, "enabled"):
        doc.enabled = 1
    if hasattr(doc, "currency"):
        doc.currency = frappe.defaults.get_global_default("currency")
    apply_price_list_company(doc)
    doc.insert(ignore_permissions=True)
    return doc.name


def _validate_buying_price_list(price_list_name, required=False):
    if not price_list_name:
        if required:
            frappe.throw(_("Buying Price List is required."))
        return
    return validate_visible_price_list(price_list_name, kind="buying", required=required)


def _get_latest_item_price_name(item_code, price_list):
    rows = frappe.get_all(
        "Item Price",
        filters={"item_code": item_code, "price_list": price_list},
        fields=["name"],
        order_by="valid_from desc, modified desc" if frappe.db.has_column("Item Price", "valid_from") else "modified desc",
        limit_page_length=1,
    )
    return rows[0].name if rows else None


def _apply_item_price_defaults(doc, item_code, price_list, currency):
    if hasattr(doc, "currency"):
        doc.currency = currency
    if hasattr(doc, "buying"):
        doc.buying = 1
    if hasattr(doc, "selling"):
        doc.selling = 0
    if hasattr(doc, "uom") and not doc.uom:
        doc.uom = frappe.db.get_value("Item", item_code, "stock_uom")
    if hasattr(doc, "valid_from") and not doc.valid_from:
        doc.valid_from = nowdate()
    if frappe.db.has_column("Item Price", "brand") and not getattr(doc, "brand", None):
        doc.brand = _get_item_price_brand_map([item_code], price_list).get(item_code) or ""


def _parse_payload(payload):
    if isinstance(payload, str):
        return json.loads(payload or "{}")
    return payload or {}


def _clean_list(values):
    out = []
    for value in values or []:
        text = (value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _require_pricing_write():
    if frappe.session.user == "Administrator":
        return
    if PRICING_WRITE_ROLES.intersection(set(frappe.get_roles())):
        return
    frappe.throw(_("You do not have permission to manage buying price builder records."), frappe.PermissionError)


def _require_buying_price_access(permission_type="read"):
    access = get_item_price_access("buying")
    if not access.get("permitted"):
        frappe.throw(_("You do not have permission to access buying prices."), frappe.PermissionError)
    frappe.has_permission("Item Price", permission_type, throw=True)
    return access
