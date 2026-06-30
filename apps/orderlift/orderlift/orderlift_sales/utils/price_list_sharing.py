import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from orderlift.orderlift_sales.utils.price_list_scope import (
    BUYING_PRICE_LIST,
    PRICE_LIST_TYPE_FIELD,
    normalize_price_list_type,
)

SHARING_TABLE_FIELD = "custom_price_list_sharing"
SHARED_FROM_FIELD = "custom_is_shared_from"


def validate_sharing_rows(doc, method=None):
    if doc.doctype != "Price List":
        return
    normalize_price_list_type(doc)
    source_type = (getattr(doc, PRICE_LIST_TYPE_FIELD, "") or "").strip()
    if source_type != "Selling":
        if doc.get(SHARING_TABLE_FIELD):
            frappe.throw(_("Only Selling price lists can be shared."))
        return
    owner_company = (getattr(doc, "custom_company", "") or "").strip()
    if not owner_company:
        frappe.throw(_("A company is required before sharing this price list."))
    if _is_shared_list(doc):
        frappe.throw(_("A shared price list cannot be re-shared."))
    rows = doc.get(SHARING_TABLE_FIELD) or []
    seen_companies = set()
    for idx, row in enumerate(rows, start=1):
        target_company = (getattr(row, "company", "") or "").strip()
        if not target_company:
            continue
        if target_company == owner_company:
            frappe.throw(_("Row #{0}: Cannot share with the owning company.").format(idx))
        if target_company in seen_companies:
            frappe.throw(_("Row #{0}: Duplicate company {1}.").format(idx, target_company))
        seen_companies.add(target_company)
        if not frappe.db.exists("Company", target_company):
            frappe.throw(_("Row #{0}: Company {1} does not exist.").format(idx, target_company))


def ensure_shared_price_lists(doc, method=None):
    if doc.doctype != "Price List":
        return
    normalize_price_list_type(doc)
    source_type = (getattr(doc, PRICE_LIST_TYPE_FIELD, "") or "").strip()
    if source_type != "Selling":
        return
    if _is_shared_list(doc):
        return
    owner_company = (getattr(doc, "custom_company", "") or "").strip()
    if not owner_company:
        return
    rows = doc.get(SHARING_TABLE_FIELD) or []
    for row in rows:
        if not cint(getattr(row, "is_active", 0)):
            _deactivate_sharing_row(row)
            continue
        target_company = (getattr(row, "company", "") or "").strip()
        if not target_company:
            continue
        existing_shared = (getattr(row, "shared_price_list", "") or "").strip()
        if existing_shared and frappe.db.exists("Price List", existing_shared):
            _reactivate_shared_list(existing_shared)
            _mirror_item_prices(doc.name, existing_shared)
            _stamp_sync_status(row, "synced")
        else:
            new_shared = _create_shared_price_list(doc, target_company, row)
            if new_shared:
                _stamp_sync_status(row, "created")


def _create_shared_price_list(source_doc, target_company, row):
    source_name = source_doc.name
    shared_name = _shared_list_name(source_name, target_company)

    if frappe.db.exists("Price List", shared_name):
        existing = frappe.get_doc("Price List", shared_name)
        existing.enabled = 1
        setattr(existing, SHARED_FROM_FIELD, source_name)
        setattr(existing, "custom_shared_on", now_datetime())
        setattr(existing, "custom_company", target_company)
        existing.save(ignore_permissions=True)
        _mirror_item_prices(source_name, shared_name)
        row.shared_price_list = shared_name
        row.last_synced_on = now_datetime()
        return shared_name

    shared_list = frappe.new_doc("Price List")
    shared_list.price_list_name = shared_name
    shared_list.currency = getattr(source_doc, "currency", None) or frappe.defaults.get_global_default("currency")
    shared_list.buying = 1
    shared_list.selling = 0
    setattr(shared_list, PRICE_LIST_TYPE_FIELD, BUYING_PRICE_LIST)
    setattr(shared_list, "custom_company", target_company)
    setattr(shared_list, SHARED_FROM_FIELD, source_name)
    setattr(shared_list, "custom_shared_on", now_datetime())
    shared_list.enabled = 1
    shared_list.insert(ignore_permissions=True)

    _mirror_item_prices(source_name, shared_name)

    row.shared_price_list = shared_name
    row.last_synced_on = now_datetime()
    return shared_name


def _mirror_item_prices(source_price_list, target_price_list):
    source_items = frappe.get_all(
        "Item Price",
        filters={"price_list": source_price_list},
        fields=[
            "item_code", "uom", "price_list_rate", "currency",
            "valid_from", "valid_upto", "buying", "selling",
        ],
        limit_page_length=0,
    )
    existing_target = {
        d["item_code"]: d["name"]
        for d in frappe.get_all(
            "Item Price",
            filters={"price_list": target_price_list},
            fields=["name", "item_code"],
            limit_page_length=0,
        )
    }
    created = 0
    updated = 0
    for src in source_items:
        item_code = src["item_code"]
        target_name = existing_target.get(item_code)
        if target_name:
            frappe.db.set_value(
                "Item Price",
                target_name,
                {
                    "price_list_rate": flt(src["price_list_rate"]),
                    "currency": src["currency"],
                    "uom": src["uom"],
                    "valid_from": src.get("valid_from"),
                    "valid_upto": src.get("valid_upto"),
                    "buying": 1,
                    "selling": 0,
                    "modified": now_datetime(),
                },
            )
            updated += 1
        else:
            new_ip = frappe.new_doc("Item Price")
            new_ip.price_list = target_price_list
            new_ip.item_code = item_code
            new_ip.uom = src.get("uom", "Unit")
            new_ip.price_list_rate = flt(src["price_list_rate"])
            new_ip.currency = src.get("currency") or frappe.defaults.get_global_default("currency")
            new_ip.valid_from = src.get("valid_from")
            new_ip.valid_upto = src.get("valid_upto")
            new_ip.buying = 1
            new_ip.selling = 0
            new_ip.insert(ignore_permissions=True)
            created += 1
    return created, updated


def _shared_list_name(source_price_list, target_company):
    safe_pl = source_price_list.replace("`", "")
    safe_co = target_company.replace("`", "")
    candidate = "{} ({})".format(safe_pl, safe_co)
    if not frappe.db.exists("Price List", candidate):
        return candidate
    base = candidate
    counter = 2
    while frappe.db.exists("Price List", candidate):
        candidate = "{} ({} #{})".format(safe_pl, safe_co, counter)
        counter += 1
    return candidate


def sync_shared_item_price(doc, method=None):
    source_price_list = (getattr(doc, "price_list", "") or "").strip()
    if not source_price_list:
        return
    if not _has_column("Price List", SHARING_TABLE_FIELD):
        return

    sharing_rows = frappe.get_all(
        "Price List Sharing",
        filters={
            "parent": source_price_list,
            "is_active": 1,
            "shared_price_list": ["is", "set"],
        },
        fields=["name", "shared_price_list", "company"],
        limit_page_length=0,
    )
    if not sharing_rows:
        return

    item_code = (getattr(doc, "item_code", "") or "").strip()
    if not item_code:
        return

    rate = flt(getattr(doc, "price_list_rate", 0))
    uom = getattr(doc, "uom", None)
    valid_from = getattr(doc, "valid_from", None)
    valid_upto = getattr(doc, "valid_upto", None)
    currency = getattr(doc, "currency", None) or frappe.defaults.get_global_default("currency")

    for share_row in sharing_rows:
        shared_list = share_row["shared_price_list"]
        existing_name = frappe.db.get_value(
            "Item Price",
            {"price_list": shared_list, "item_code": item_code},
            "name",
        )
        if existing_name:
            frappe.db.set_value(
                "Item Price",
                existing_name,
                {
                    "price_list_rate": rate,
                    "currency": currency,
                    "uom": uom,
                    "valid_from": valid_from,
                    "valid_upto": valid_upto,
                    "modified": now_datetime(),
                },
            )
        else:
            new_ip = frappe.new_doc("Item Price")
            new_ip.price_list = shared_list
            new_ip.item_code = item_code
            new_ip.uom = uom
            new_ip.price_list_rate = rate
            new_ip.currency = currency
            new_ip.valid_from = valid_from
            new_ip.valid_upto = valid_upto
            new_ip.buying = 1
            new_ip.selling = 0
            new_ip.insert(ignore_permissions=True)

    if doc.get("price_list"):
        frappe.db.set_value(
            "Price List Sharing",
            {"parent": source_price_list, "shared_price_list": ["is", "set"]},
            {"last_synced_on": now_datetime()},
            update_modified=False,
        )

def sync_shared_item_price_on_trash(doc, method=None):
    source_price_list = (getattr(doc, "price_list", "") or "").strip()
    item_code = (getattr(doc, "item_code", "") or "").strip()
    if not source_price_list or not item_code:
        return
    if not _has_column("Price List", SHARING_TABLE_FIELD):
        return

    sharing_rows = frappe.get_all(
        "Price List Sharing",
        filters={
            "parent": source_price_list,
            "is_active": 1,
            "shared_price_list": ["is", "set"],
        },
        fields=["shared_price_list"],
        limit_page_length=0,
    )
    for share_row in sharing_rows:
        existing = frappe.db.get_value(
            "Item Price",
            {"price_list": share_row["shared_price_list"], "item_code": item_code},
            "name",
        )
        if existing:
            frappe.delete_doc("Item Price", existing, ignore_permissions=True, force=True)


def disable_shared_price_list(shared_price_list):
    if not frappe.db.exists("Price List", shared_price_list):
        return
    frappe.db.set_value("Price List", shared_price_list, "enabled", 0)


def _deactivate_sharing_row(row):
    shared_list = (getattr(row, "shared_price_list", "") or "").strip()
    if shared_list and frappe.db.exists("Price List", shared_list):
        disable_shared_price_list(shared_list)
    row.shared_price_list = ""
    row.last_synced_on = ""
    row.last_sync_status = "deactivated"


def _reactivate_shared_list(shared_price_list):
    if not frappe.db.exists("Price List", shared_price_list):
        return
    frappe.db.set_value("Price List", shared_price_list, "enabled", 1)


def _stamp_sync_status(row, status):
    frappe.db.set_value(
        "Price List Sharing",
        row.name,
        {"last_synced_on": now_datetime(), "last_sync_status": status},
        update_modified=False,
    )
    row.last_synced_on = now_datetime()
    row.last_sync_status = status


def handle_sharing_rows_deletion(doc, method=None):
    if doc.doctype != "Price List":
        return
    if _is_shared_list(doc):
        return
    rows = doc.get(SHARING_TABLE_FIELD) or []
    original_rows = _get_original_sharing_rows(doc.name)
    current_names = {getattr(r, "name", "") for r in rows if getattr(r, "name", "")}
    for original_name, original_shared in original_rows.items():
        if original_name not in current_names and original_shared:
            disable_shared_price_list(original_shared)


def _get_original_sharing_rows(price_list_name):
    if not frappe.db.table_exists("tabPrice List Sharing"):
        return {}
    rows = frappe.get_all(
        "Price List Sharing",
        filters={"parent": price_list_name},
        fields=["name", "shared_price_list"],
        limit_page_length=0,
    )
    return {r["name"]: (r.get("shared_price_list") or "").strip() for r in rows}


def _is_shared_list(doc):
    return bool((getattr(doc, SHARED_FROM_FIELD, "") or "").strip())


def _has_column(doctype, fieldname):
    checker = getattr(getattr(frappe, "db", None), "has_column", None)
    return bool(checker(doctype, fieldname)) if callable(checker) else False


def on_price_list_trash(doc, method=None):
    if doc.doctype != "Price List":
        return
    if _is_shared_list(doc):
        return
    rows = doc.get(SHARING_TABLE_FIELD) or []
    for row in rows:
        shared_list = (getattr(row, "shared_price_list", "") or "").strip()
        if shared_list:
            disable_shared_price_list(shared_list)


def on_sharing_row_trash(doc, method=None):
    if doc.doctype != "Price List Sharing":
        return
    shared_list = (getattr(doc, "shared_price_list", "") or "").strip()
    if shared_list and frappe.db.exists("Price List", shared_list):
        disable_shared_price_list(shared_list)
