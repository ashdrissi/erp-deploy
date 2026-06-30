from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint


def apply_item_category_defaults(item_doc, method=None):
    category_name = (item_doc.get("custom_item_category") or "").strip()
    if not category_name:
        return

    category = frappe.get_cached_doc("Item Category", category_name)
    category_group = (getattr(category, "item_group", "") or "").strip()
    item_group = (item_doc.get("item_group") or "").strip()
    if category_group and item_group and category_group != item_group:
        frappe.throw(
            _("Item Category {0} belongs to Item Group {1}, not {2}.").format(
                category_name,
                category_group,
                item_group,
            )
        )
    abbreviation = normalize_abbreviation(category.abbreviation)
    item_doc.custom_category_abbreviation = abbreviation

    if item_doc.is_new() and _should_generate_item_code(item_doc):
        item_doc.item_code = get_next_item_code(category_name)


def get_next_item_code(category_name: str) -> str:
    category_name = (category_name or "").strip()
    if not category_name:
        frappe.throw(_("Item Category is required to generate an item code."))
    if not frappe.db.exists("Item Category", category_name):
        frappe.throw(_("Item Category {0} does not exist.").format(category_name))

    row = frappe.db.sql(
        """
        SELECT name, abbreviation, sequence_digits, current_sequence, is_active
        FROM `tabItem Category`
        WHERE name = %s
        FOR UPDATE
        """,
        category_name,
        as_dict=True,
    )
    if not row:
        frappe.throw(_("Item Category {0} does not exist.").format(category_name))

    category = row[0]
    if not cint(category.is_active):
        frappe.throw(_("Item Category {0} is inactive.").format(category_name))

    abbreviation = normalize_abbreviation(category.abbreviation)
    digits = cint(category.sequence_digits or 5)
    next_sequence = cint(category.current_sequence or 0) + 1

    item_code = f"{abbreviation}-{next_sequence:0{digits}d}"
    while frappe.db.exists("Item", item_code):
        next_sequence += 1
        item_code = f"{abbreviation}-{next_sequence:0{digits}d}"

    frappe.db.set_value(
        "Item Category",
        category.name,
        "current_sequence",
        next_sequence,
        update_modified=False,
    )
    return item_code


@frappe.whitelist()
def preview_next_item_code(category_name: str) -> dict:
    category_name = (category_name or "").strip()
    if not category_name:
        return {"item_code": "AUTO", "abbreviation": ""}

    row = frappe.db.get_value(
        "Item Category",
        category_name,
        ["abbreviation", "sequence_digits", "current_sequence", "is_active"],
        as_dict=True,
    )
    if not row:
        frappe.throw(_("Item Category {0} does not exist.").format(category_name))
    if not cint(row.is_active):
        frappe.throw(_("Item Category {0} is inactive.").format(category_name))

    abbreviation = normalize_abbreviation(row.abbreviation)
    digits = cint(row.sequence_digits or 5)
    next_sequence = cint(row.current_sequence or 0) + 1
    item_code = f"{abbreviation}-{next_sequence:0{digits}d}"
    while frappe.db.exists("Item", item_code):
        next_sequence += 1
        item_code = f"{abbreviation}-{next_sequence:0{digits}d}"

    return {"item_code": item_code, "abbreviation": abbreviation, "sequence": next_sequence}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_category_query(doctype, txt, searchfield, start, page_len, filters=None):
    filters = filters or {}
    item_group = (filters.get("item_group") or "").strip()
    params = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }
    conditions = [
        "ifnull(is_active, 1) = 1",
        "ifnull(item_group, '') != ''",
        "(name like %(txt)s or ifnull(category_name, '') like %(txt)s or ifnull(abbreviation, '') like %(txt)s)",
    ]
    if item_group:
        conditions.append("item_group = %(item_group)s")
        params["item_group"] = item_group

    return frappe.db.sql(
        f"""
        SELECT
            name,
            category_name,
            abbreviation
        FROM `tabItem Category`
        WHERE {' AND '.join(conditions)}
        ORDER BY name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        params,
    )


def normalize_abbreviation(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").strip().upper())


def _should_generate_item_code(item_doc) -> bool:
    item_code = (item_doc.get("item_code") or "").strip()
    item_name = (item_doc.get("item_name") or "").strip()
    if not item_code:
        return True
    # ERPNext often copies Item Name into Item Code before server validation.
    # Treat that default copy as not manually entered so category sequencing still applies.
    return item_code.upper() in {"AUTO", "AUTOMATIC", "AUTO-GENERATED"} or bool(item_name and item_code == item_name)
