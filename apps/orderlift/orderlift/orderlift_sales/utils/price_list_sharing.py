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
PURCHASE_AGENT_RULES_DOCTYPE = "Purchase Agent Rules"
PURCHASE_AGENT_ALLOWED_DOCTYPE = "Purchase Agent Allowed Buying Price List"


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
    _disable_removed_sharing_rows(doc)
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
    existing = _existing_shared_list(source_price_list, target_company)
    if existing:
        return existing
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


def _existing_shared_list(source_price_list, target_company):
    if not frappe.db.has_column("Price List", SHARED_FROM_FIELD) or not frappe.db.has_column("Price List", "custom_company"):
        return ""
    return frappe.db.get_value(
        "Price List",
        {SHARED_FROM_FIELD: source_price_list, "custom_company": target_company},
        "name",
        order_by="enabled desc, modified desc, name asc",
    ) or ""


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
    _retire_purchase_agent_allowances(shared_price_list)


def _retire_purchase_agent_allowances(price_list):
    """Drop the list from Purchase Agent Rules allowances when it stops being shared.

    Every teardown path funnels through disable_shared_price_list, so doing this
    here covers row deactivation, row removal, and Price List deletion. Left
    behind, an active allowance points at a disabled list and later surfaces as
    "The selected Price List is unavailable or not permitted."
    """
    if not price_list or not frappe.db.exists("DocType", PURCHASE_AGENT_ALLOWED_DOCTYPE):
        return
    rows = frappe.db.get_all(
        PURCHASE_AGENT_ALLOWED_DOCTYPE,
        filters={
            "buying_price_list": price_list,
            "parenttype": PURCHASE_AGENT_RULES_DOCTYPE,
            "is_active": 1,
        },
        pluck="name",
    )
    for row in rows:
        frappe.db.set_value(PURCHASE_AGENT_ALLOWED_DOCTYPE, row, "is_active", 0, update_modified=False)


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
    _disable_removed_sharing_rows(doc)


def _disable_removed_sharing_rows(doc):
    before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    if not before:
        return
    rows = doc.get(SHARING_TABLE_FIELD) or []
    original_rows = _sharing_rows_by_name(before)
    current_names = {getattr(r, "name", "") for r in rows if getattr(r, "name", "")}
    for original_name, original_shared in original_rows.items():
        if original_name not in current_names and original_shared:
            disable_shared_price_list(original_shared)


def _sharing_rows_by_name(doc):
    return {
        getattr(row, "name", ""): (getattr(row, "shared_price_list", "") or "").strip()
        for row in (doc.get(SHARING_TABLE_FIELD) or [])
        if getattr(row, "name", "")
    }


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


def resolve_shared_companies_from_price_lists(doc_company: str, selling_price_lists) -> list[str]:
    """Companies linked to the given selling price lists.

    Resolves both directions: companies the selling lists are actively shared to,
    and owner companies of the selling lists mirrored into the stamped source
    buying lists of these selling lists (internal suppliers). Returns the
    deduplicated, sorted companies, excluding the document company.
    """
    doc_company = (doc_company or "").strip()
    price_lists = _clean_names(selling_price_lists)
    if not doc_company or not price_lists:
        return []
    if not _has_column("Price List", "custom_company"):
        return []

    targets = set()
    source_buying = set()
    if frappe.db.exists and frappe.db.exists("DocType", "Price List Sharing"):
        for price_list in price_lists:
            owner = (frappe.db.get_value("Price List", price_list, "custom_company") or "").strip()
            if owner != doc_company:
                continue
            rows = frappe.get_all(
                "Price List Sharing",
                filters={"parent": price_list, "is_active": 1},
                fields=["company"],
                limit_page_length=0,
            )
            for row in rows:
                target = (row.get("company") or "").strip()
                if target and target != doc_company:
                    targets.add(target)
    for price_list in price_lists:
        owner = (frappe.db.get_value("Price List", price_list, "custom_company") or "").strip()
        if owner != doc_company:
            continue
        raw = (frappe.db.get_value("Price List", price_list, "custom_source_buying_price_lists") or "").strip()
        for name in _clean_names(raw.split(",")):
            source_buying.add(name)
    suppliers = resolve_shared_companies_from_buying_price_lists(doc_company, sorted(source_buying))
    return sorted(set(targets) | set(suppliers))


def resolve_shared_companies_from_buying_price_lists(doc_company: str, buying_price_lists) -> list[str]:
    """Owner companies of the selling price lists shared into the buying lists.

    A buying price list owned by doc_company with `custom_is_shared_from` set
    mirrors a selling price list owned by another company — the internal
    supplier. Returns the deduplicated, sorted supplier companies.
    """
    doc_company = (doc_company or "").strip()
    price_lists = _clean_names(buying_price_lists)
    if not doc_company or not price_lists:
        return []
    if not _has_column("Price List", "custom_company") or not _has_column("Price List", SHARED_FROM_FIELD):
        return []

    suppliers = set()
    for price_list in price_lists:
        values = frappe.db.get_value(
            "Price List",
            price_list,
            ["custom_company", SHARED_FROM_FIELD],
            as_dict=True,
        ) or {}
        if (values.get("custom_company") or "").strip() != doc_company:
            continue
        source_list = (values.get(SHARED_FROM_FIELD) or "").strip()
        if not source_list:
            continue
        owner = (frappe.db.get_value("Price List", source_list, "custom_company") or "").strip()
        if owner and owner != doc_company:
            suppliers.add(owner)
    return sorted(suppliers)


def resolve_shared_stock_companies(doc) -> list[str]:
    """Sharing-linked companies whose stock appears in the shared-company preview.

    Collects selling price lists (targets of sharing rows) and buying price lists
    (owner companies of the mirrored selling lists) from the document, then
    returns the union of both directions.
    """
    if not doc:
        return []
    company = (doc.get("company") if hasattr(doc, "get") else getattr(doc, "company", "")) or ""
    company = (company or "").strip()
    selling_lists = set()
    buying_lists = set()
    selection = doc.get("selected_selling_price_lists") if hasattr(doc, "get") else getattr(doc, "selected_selling_price_lists", [])
    for row in selection or []:
        name = (row.get("price_list") if hasattr(row, "get") else getattr(row, "price_list", "")) or ""
        if (name or "").strip():
            selling_lists.add(name.strip())
    primary = doc.get("selling_price_list") if hasattr(doc, "get") else getattr(doc, "selling_price_list", "")
    if (primary or "").strip():
        selling_lists.add(primary.strip())
    buying_selection = doc.get("selected_buying_price_lists") if hasattr(doc, "get") else getattr(doc, "selected_buying_price_lists", [])
    for row in buying_selection or []:
        name = (row.get("price_list") if hasattr(row, "get") else getattr(row, "price_list", "")) or ""
        if (name or "").strip():
            buying_lists.add(name.strip())
    doc_buying = doc.get("buying_price_list") if hasattr(doc, "get") else getattr(doc, "buying_price_list", "")
    if (doc_buying or "").strip():
        buying_lists.add(doc_buying.strip())
    doc_buying_rows = doc.get("custom_source_buying_price_lists") if hasattr(doc, "get") else getattr(doc, "custom_source_buying_price_lists", [])
    for row in doc_buying_rows or []:
        name = (row.get("price_list") if hasattr(row, "get") else getattr(row, "price_list", "")) or ""
        if (name or "").strip():
            buying_lists.add(name.strip())
    items = doc.get("items") if hasattr(doc, "get") else getattr(doc, "items", [])
    if not items:
        items = doc.get("lines") if hasattr(doc, "get") else getattr(doc, "lines", [])
    for row in items or []:
        sell_name = (row.get("source_selling_price_list") if hasattr(row, "get") else getattr(row, "source_selling_price_list", "")) or ""
        if (sell_name or "").strip():
            selling_lists.add(sell_name.strip())
        buy_name = (row.get("custom_source_buying_price_list") if hasattr(row, "get") else getattr(row, "custom_source_buying_price_list", "")) or ""
        if (buy_name or "").strip():
            buying_lists.add(buy_name.strip())

    companies = set(
        resolve_shared_companies_from_price_lists(company, sorted(selling_lists))
        + resolve_shared_companies_from_buying_price_lists(company, sorted(buying_lists))
    )
    return sorted(companies)


def _clean_names(values) -> list[str]:
    result = []
    for value in values or []:
        clean = str(value or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result
