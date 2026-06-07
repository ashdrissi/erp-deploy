import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder import (
    _get_latest_item_price_name,
    final_selling_price_for_builder_row,
    stamp_item_price_from_builder_row,
    stamp_price_list_from_builder,
)


def run(
    builder: str | None = None,
    price_list: str | None = None,
    dry_run: int = 1,
    update_prices: int = 0,
    enable_auto_rebuild: int = 0,
) -> dict:
    """Backfill source and max-discount stamps for existing builder selling lists.

    This is intentionally update-only for existing selling Item Prices. It never
    creates missing Item Price rows, so old lists are not expanded accidentally.
    """

    dry_run = cint(dry_run) == 1
    update_prices = cint(update_prices) == 1
    enable_auto_rebuild = cint(enable_auto_rebuild) == 1
    builders = _resolve_builders(builder=builder, price_list=price_list)

    summary = {
        "dry_run": 1 if dry_run else 0,
        "update_prices": 1 if update_prices else 0,
        "enable_auto_rebuild": 1 if enable_auto_rebuild else 0,
        "builders": len(builders),
        "price_lists": [],
        "stamped": 0,
        "updated_prices": 0,
        "missing_existing_item_prices": 0,
        "skipped_not_ready": 0,
        "protected_overrides": 0,
        "errors": [],
    }

    for builder_doc in builders:
        _backfill_builder(builder_doc, summary, dry_run, update_prices, enable_auto_rebuild)

    return summary


def _resolve_builders(builder=None, price_list=None):
    builder = (builder or "").strip()
    price_list = (price_list or "").strip()
    if builder:
        if not frappe.db.exists("Pricing Builder", builder):
            frappe.throw(_("Pricing Builder {0} was not found.").format(builder))
        return [frappe.get_doc("Pricing Builder", builder)]

    filters = {}
    if price_list:
        filters["selling_price_list_name"] = price_list
    rows = frappe.get_all(
        "Pricing Builder",
        filters=filters,
        fields=["name"],
        order_by="modified desc",
        limit_page_length=0,
    )
    return [frappe.get_doc("Pricing Builder", row.name) for row in rows]


def _backfill_builder(builder_doc, summary, dry_run, update_prices, enable_auto_rebuild):
    price_list = (builder_doc.selling_price_list_name or "").strip()
    if not price_list:
        summary["errors"].append(_("{0}: no selling price list configured.").format(builder_doc.name))
        return
    if not frappe.db.exists("Price List", price_list):
        summary["errors"].append(_("{0}: Price List {1} was not found.").format(builder_doc.name, price_list))
        return

    try:
        builder_doc.calculate_items()
    except Exception as exc:
        summary["errors"].append(_("{0}: calculation failed: {1}").format(builder_doc.name, exc))
        return

    price_list_result = {
        "builder": builder_doc.name,
        "price_list": price_list,
        "stamped": 0,
        "updated_prices": 0,
        "missing_existing_item_prices": 0,
        "skipped_not_ready": 0,
        "protected_overrides": 0,
    }

    if not dry_run:
        stamp_price_list_from_builder(price_list, builder_doc)
        if enable_auto_rebuild and frappe.db.has_column("Price List", "custom_auto_rebuild_from_source_buying_prices"):
            frappe.db.set_value(
                "Price List",
                price_list,
                "custom_auto_rebuild_from_source_buying_prices",
                1,
                update_modified=False,
            )

    rebuild_time = now_datetime()
    previous_flag = getattr(frappe.flags, "orderlift_auto_rebuild_item_price", False)
    frappe.flags.orderlift_auto_rebuild_item_price = True
    try:
        for row in builder_doc.builder_items or []:
            _backfill_row(
                builder_doc,
                row,
                price_list,
                price_list_result,
                dry_run=dry_run,
                update_prices=update_prices,
                rebuild_time=rebuild_time,
            )
    finally:
        frappe.flags.orderlift_auto_rebuild_item_price = previous_flag

    for key in (
        "stamped",
        "updated_prices",
        "missing_existing_item_prices",
        "skipped_not_ready",
        "protected_overrides",
    ):
        summary[key] += price_list_result[key]
    summary["price_lists"].append(price_list_result)


def _backfill_row(builder_doc, row, price_list, price_list_result, dry_run, update_prices, rebuild_time):
    item_code = (row.item or "").strip()
    if not item_code:
        price_list_result["skipped_not_ready"] += 1
        return
    if (row.status or "").strip() in {"Missing Rule", "Missing Buy Price"}:
        price_list_result["skipped_not_ready"] += 1
        return

    existing_name = _get_latest_item_price_name(item_code, price_list)
    if not existing_name:
        price_list_result["missing_existing_item_prices"] += 1
        return

    final_price = final_selling_price_for_builder_row(row)
    is_override = flt(row.override_selling_price or 0) > 0
    if is_override:
        price_list_result["protected_overrides"] += 1
    if dry_run:
        price_list_result["stamped"] += 1
        if update_prices and not is_override and final_price > 0:
            price_list_result["updated_prices"] += 1
        return

    doc = frappe.get_doc("Item Price", existing_name)
    if update_prices and not is_override and final_price > 0:
        doc.price_list_rate = final_price
        price_list_result["updated_prices"] += 1
    stamp_item_price_from_builder_row(doc, builder_doc.name, row, rebuild_time=rebuild_time)
    doc.save(ignore_permissions=True)
    price_list_result["stamped"] += 1
