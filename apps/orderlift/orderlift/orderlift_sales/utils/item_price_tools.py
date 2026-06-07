from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from orderlift.orderlift_sales.utils.price_list_scope import get_price_lists, validate_price_list_scope


PRICE_TYPE_CONFIG = {
    "buying": {"kind": "buying", "buying": 1, "selling": 0, "label": "Buying"},
    "selling": {"kind": "selling", "buying": 0, "selling": 1, "label": "Selling"},
}

OPTIONAL_ITEM_PRICE_FIELDS = ("brand", "currency", "enabled", "valid_from", "valid_upto", "buying", "selling")


def apply_item_price_defaults(doc, method=None):
    item_code = (doc.get("item_code") or "").strip()
    if not item_code or not _doc_has_field(doc, "uom") or (doc.get("uom") or "").strip():
        return

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    if stock_uom:
        doc.uom = stock_uom


@frappe.whitelist()
def get_item_price_grid(item_code: str, price_type: str) -> dict:
    item_code = _validate_item(item_code, permission_type="read")
    config = _price_type_config(price_type)
    _check_item_price_permission("read")

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or ""
    price_lists = _price_lists(config["kind"])
    rows = _get_item_price_rows(item_code, config)
    return {
        "item_code": item_code,
        "price_type": config["kind"],
        "stock_uom": stock_uom,
        "price_lists": price_lists,
        "fields": _available_item_price_fields(),
        "rows": rows,
    }


@frappe.whitelist()
def save_item_price_grid(item_code: str, price_type: str, rows=None) -> dict:
    item_code = _validate_item(item_code, permission_type="read")
    config = _price_type_config(price_type)
    rows = _parse_rows(rows)

    summary = {"created": 0, "updated": 0, "skipped": 0, "rows": []}
    for row in rows:
        if not _row_has_values(row):
            summary["skipped"] += 1
            continue
        result = _upsert_item_price_row(item_code, config, row)
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

    if price_list:
        price_list = validate_price_list_scope(price_list, kind=config["kind"], required=True)

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
        "price_lists": _price_lists(config["kind"]),
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
        result = _upsert_item_price_row(item_code, config, clean)
        summary[result["action"]] += 1
        summary["rows"].append(result["row"])

    return summary


def _get_item_price_rows(item_code: str, config: dict) -> list[dict]:
    fields = ["name", "item_code", "price_list", "price_list_rate", "uom"]
    for fieldname in OPTIONAL_ITEM_PRICE_FIELDS:
        if _doctype_has_column("Item Price", fieldname):
            fields.append(fieldname)

    filters = {"item_code": item_code}
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


def _upsert_item_price_row(item_code: str, config: dict, row: dict) -> dict:
    price_list = validate_price_list_scope(row.get("price_list"), kind=config["kind"], required=True)
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
    _set_if_field(doc, "currency", (row.get("currency") or "").strip() or _price_list_currency(price_list))
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


def _price_lists(kind: str) -> list[dict]:
    rows = get_price_lists(kind, fields=["name", "currency"])
    default_currency = frappe.defaults.get_global_default("currency") or ""
    return [{"name": row.name, "currency": row.currency or default_currency} for row in rows]


def _price_list_currency(price_list: str | None) -> str:
    price_list = (price_list or "").strip()
    if not price_list:
        return frappe.defaults.get_global_default("currency") or ""
    return frappe.db.get_value("Price List", price_list, "currency") or frappe.defaults.get_global_default("currency") or ""


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
