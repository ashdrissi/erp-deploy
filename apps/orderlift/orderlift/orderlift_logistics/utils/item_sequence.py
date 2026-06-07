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
