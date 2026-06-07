import frappe
from frappe.utils import cint, flt, now_datetime

from orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder import (
    final_selling_price_for_builder_row,
    stamp_item_price_from_builder_row,
)


RELEVANT_ITEM_PRICE_FIELDS = (
    "item_code",
    "price_list",
    "price_list_rate",
    "currency",
    "buying",
    "enabled",
    "valid_from",
    "valid_upto",
)


def on_item_price_change(doc, method=None):
    if getattr(frappe.flags, "orderlift_auto_rebuild_item_price", False):
        return
    if not _is_source_buying_price(doc):
        return
    if not _has_relevant_change(doc, method):
        return

    summary = rebuild_from_buying_item_price(doc)
    for price_list, status in (summary.get("price_lists") or {}).items():
        _set_price_list_rebuild_status(price_list, status)


def rebuild_from_buying_item_price(doc):
    item_code = (getattr(doc, "item_code", "") or "").strip()
    source_buying_price_list = (getattr(doc, "price_list", "") or "").strip()
    if not item_code or not source_buying_price_list:
        return {"updated": 0, "skipped": 0, "errors": [], "price_lists": {}}

    targets = _get_target_selling_prices(item_code, source_buying_price_list)
    summary = {"updated": 0, "skipped": 0, "errors": [], "price_lists": {}}
    builder_cache = {}
    calculated_builder_cache = {}
    rebuild_time = now_datetime()

    for target in targets:
        price_list = target.get("price_list")
        if cint(target.get("custom_builder_price_overridden") or 0):
            summary["skipped"] += 1
            summary["price_lists"][price_list] = "Skipped {0}: builder override is protected".format(item_code)
            continue

        builder_name = (target.get("custom_pricing_builder") or target.get("price_list_builder") or "").strip()
        if not builder_name:
            summary["skipped"] += 1
            summary["price_lists"][price_list] = "Skipped {0}: no builder link".format(item_code)
            continue

        try:
            builder = _get_calculated_builder(builder_name, builder_cache, calculated_builder_cache)
            row = _find_builder_row(builder, item_code, source_buying_price_list)
            if not row:
                summary["skipped"] += 1
                summary["price_lists"][price_list] = "Skipped {0}: no matching builder row".format(item_code)
                continue
            if flt(row.override_selling_price or 0) > 0:
                summary["skipped"] += 1
                summary["price_lists"][price_list] = "Skipped {0}: builder override is protected".format(item_code)
                continue
            if (row.status or "").strip() in {"Missing Rule", "Missing Buy Price"}:
                summary["skipped"] += 1
                summary["price_lists"][price_list] = "Skipped {0}: {1}".format(item_code, row.status or "not ready")
                continue

            final_price = final_selling_price_for_builder_row(row)
            if final_price <= 0:
                summary["skipped"] += 1
                summary["price_lists"][price_list] = "Skipped {0}: calculated price is zero".format(item_code)
                continue

            selling_doc = frappe.get_doc("Item Price", target.name)
            selling_doc.price_list_rate = final_price
            stamp_item_price_from_builder_row(selling_doc, builder.name, row, rebuild_time=rebuild_time)
            previous_flag = getattr(frappe.flags, "orderlift_auto_rebuild_item_price", False)
            frappe.flags.orderlift_auto_rebuild_item_price = True
            try:
                selling_doc.save(ignore_permissions=True)
            finally:
                frappe.flags.orderlift_auto_rebuild_item_price = previous_flag
            summary["updated"] += 1
            summary["price_lists"][price_list] = "Updated {0} from {1}: {2}".format(
                item_code,
                source_buying_price_list,
                final_price,
            )
        except Exception as exc:
            summary["errors"].append("{0}: {1}".format(price_list or "-", exc))
            summary["price_lists"][price_list] = "Failed {0}: {1}".format(item_code, exc)

    return summary


def _get_target_selling_prices(item_code, source_buying_price_list):
    required = [
        ("Price List", "custom_auto_rebuild_from_source_buying_prices"),
        ("Price List", "custom_pricing_builder"),
        ("Item Price", "custom_source_buying_price_list"),
        ("Item Price", "custom_pricing_builder"),
    ]
    if not all(_has_column(doctype, fieldname) for doctype, fieldname in required):
        return []

    price_list_filters = {
        "custom_auto_rebuild_from_source_buying_prices": 1,
        "custom_pricing_builder": ["!=", ""],
    }
    if _has_column("Price List", "selling"):
        price_list_filters["selling"] = 1
    if _has_column("Price List", "enabled"):
        price_list_filters["enabled"] = 1

    price_lists = frappe.get_all(
        "Price List",
        filters=price_list_filters,
        fields=["name", "custom_pricing_builder"],
        limit_page_length=0,
    )
    if not price_lists:
        return []

    builder_by_price_list = {row.name: row.custom_pricing_builder for row in price_lists}
    filters = {
        "item_code": item_code,
        "price_list": ["in", list(builder_by_price_list)],
        "custom_source_buying_price_list": source_buying_price_list,
    }
    if _has_column("Item Price", "selling"):
        filters["selling"] = 1
    if _has_column("Item Price", "buying"):
        filters["buying"] = 0

    fields = ["name", "price_list", "custom_pricing_builder"]
    if _has_column("Item Price", "custom_builder_price_overridden"):
        fields.append("custom_builder_price_overridden")
    rows = frappe.get_all("Item Price", filters=filters, fields=fields, limit_page_length=0)
    out = []
    for row in rows:
        data = dict(row)
        data["price_list_builder"] = builder_by_price_list.get(row.price_list) or ""
        out.append(frappe._dict(data))
    return out


def _get_calculated_builder(builder_name, builder_cache, calculated_builder_cache):
    if builder_name in calculated_builder_cache:
        return calculated_builder_cache[builder_name]
    if builder_name not in builder_cache:
        builder_cache[builder_name] = frappe.get_doc("Pricing Builder", builder_name)
    builder = builder_cache[builder_name]
    builder.calculate_items()
    calculated_builder_cache[builder_name] = builder
    return builder


def _find_builder_row(builder, item_code, source_buying_price_list):
    for row in builder.builder_items or []:
        if (row.item or "").strip() != item_code:
            continue
        if (row.buying_list or "").strip() != source_buying_price_list:
            continue
        return row
    return None


def _set_price_list_rebuild_status(price_list, status):
    if not price_list or not _has_column("Price List", "custom_last_auto_rebuild_status"):
        return
    values = {"custom_last_auto_rebuild_status": (status or "")[:1000]}
    if _has_column("Price List", "custom_last_auto_rebuild_on"):
        values["custom_last_auto_rebuild_on"] = now_datetime()
    frappe.db.set_value("Price List", price_list, values, update_modified=False)


def _is_source_buying_price(doc):
    price_list = (getattr(doc, "price_list", "") or "").strip()
    if not price_list:
        return False
    if _has_column("Item Price", "buying"):
        return cint(getattr(doc, "buying", 0) or 0) == 1
    if _has_column("Price List", "buying"):
        return cint(frappe.db.get_value("Price List", price_list, "buying") or 0) == 1
    return False


def _has_relevant_change(doc, method=None):
    if (method or "").strip() == "after_insert":
        return True
    before_getter = getattr(doc, "get_doc_before_save", None)
    before = before_getter() if callable(before_getter) else None
    if not before:
        return True
    for fieldname in RELEVANT_ITEM_PRICE_FIELDS:
        if getattr(before, fieldname, None) != getattr(doc, fieldname, None):
            return True
    return False


def _has_column(doctype, fieldname):
    checker = getattr(frappe.db, "has_column", None)
    if not callable(checker):
        return True
    return checker(doctype, fieldname)
