from __future__ import annotations

import re

import frappe
from frappe.utils import cint

from orderlift.orderlift_logistics.utils.item_sequence import normalize_abbreviation


def run(dry_run: int = 1, limit: int = 0) -> dict:
    """Swap Item.item_group with Item.custom_item_category without changing item codes."""
    dry_run = cint(dry_run)
    limit = cint(limit)
    if not frappe.db.has_column("Item", "custom_item_category"):
        frappe.throw("Item.custom_item_category is required before switching item group/category values.")

    rows = _get_target_items(limit=limit)
    summary = {
        "dry_run": dry_run,
        "items_examined": len(rows),
        "items_to_update": 0,
        "items_updated": 0,
        "missing_item_groups_created": [],
        "missing_item_categories_created": [],
        "item_category_aliases": [],
        "warnings": [],
        "samples": [],
    }

    item_groups = set(frappe.get_all("Item Group", pluck="name", limit_page_length=0))
    item_categories = _get_item_categories()
    category_by_abbreviation = {
        normalize_abbreviation(_row_value(row, "abbreviation")): name
        for name, row in item_categories.items()
        if normalize_abbreviation(_row_value(row, "abbreviation"))
    }

    for row in rows:
        item_code = row.get("name")
        old_group = (row.get("item_group") or "").strip()
        old_category = (row.get("custom_item_category") or "").strip()
        if not old_group or not old_category:
            continue
        if _item_group_matches_item_code_prefix(item_code, old_group, item_categories):
            continue

        new_group = old_category
        new_category = old_group
        if old_group == new_group and old_category == new_category:
            continue

        _ensure_item_group(new_group, item_groups, summary, dry_run=dry_run)
        new_category = _ensure_item_category(
            new_category,
            item_categories,
            category_by_abbreviation,
            summary,
            dry_run=dry_run,
        )
        summary["items_to_update"] += 1
        if len(summary["samples"]) < 25:
            summary["samples"].append(
                {
                    "item_code": item_code,
                    "old_item_group": old_group,
                    "old_category_article": old_category,
                    "new_item_group": new_group,
                    "new_category_article": new_category,
                }
            )

        if not dry_run:
            frappe.db.set_value(
                "Item",
                item_code,
                {
                    "item_group": new_group,
                    "custom_item_category": new_category,
                    "custom_category_abbreviation": _category_abbreviation(new_category, item_categories),
                },
                update_modified=False,
            )
            summary["items_updated"] += 1

    if not dry_run:
        frappe.db.commit()
    return summary


def _get_target_items(limit: int = 0) -> list[dict]:
    query = """
        SELECT name, item_group, custom_item_category
        FROM `tabItem`
        WHERE COALESCE(item_group, '') != ''
          AND COALESCE(custom_item_category, '') != ''
        ORDER BY name
    """
    if limit:
        query += " LIMIT %(limit)s"
        return frappe.db.sql(query, {"limit": limit}, as_dict=True)
    return frappe.db.sql(query, as_dict=True)


def _get_item_categories() -> dict:
    return {
        row.name: row
        for row in frappe.get_all(
            "Item Category",
            fields=["name", "abbreviation", "sequence_digits", "current_sequence"],
            limit_page_length=0,
        )
    }


def _ensure_item_group(name: str, item_groups: set[str], summary: dict, dry_run: int) -> str:
    name = (name or "").strip()
    if not name or name in item_groups:
        return name
    summary["missing_item_groups_created"].append(name)
    item_groups.add(name)
    if not dry_run:
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return name


def _ensure_item_category(
    name: str,
    item_categories: dict,
    category_by_abbreviation: dict,
    summary: dict,
    dry_run: int,
) -> str:
    name = (name or "").strip()
    if not name or name in item_categories:
        return name

    abbreviation = _unique_category_abbreviation(name, category_by_abbreviation)
    if abbreviation != normalize_abbreviation(_category_abbreviation_from_name(name)):
        summary["warnings"].append(
            "Generated unique abbreviation {0} for new Item Category {1}.".format(abbreviation, name)
        )
    summary["missing_item_categories_created"].append({"category": name, "abbreviation": abbreviation})
    item_categories[name] = {
        "name": name,
        "abbreviation": abbreviation,
        "sequence_digits": 5,
        "current_sequence": 0,
    }
    category_by_abbreviation[abbreviation] = name
    if not dry_run:
        doc = frappe.new_doc("Item Category")
        doc.category_name = name
        doc.abbreviation = abbreviation
        doc.sequence_digits = 5
        doc.current_sequence = _max_existing_sequence_for_prefix(abbreviation)
        doc.is_active = 1
        doc.insert(ignore_permissions=True)
        item_categories[name]["current_sequence"] = doc.current_sequence
    return name


def _category_abbreviation(category: str, item_categories: dict) -> str:
    row = item_categories.get(category) or {}
    return normalize_abbreviation(_row_value(row, "abbreviation"))


def _item_group_matches_item_code_prefix(item_code: str, item_group: str, item_categories: dict) -> bool:
    prefix = normalize_abbreviation((item_code or "").split("-", 1)[0])
    if not prefix:
        return False
    return _category_abbreviation(item_group, item_categories) == prefix


def _row_value(row, fieldname: str, default=None):
    if isinstance(row, dict):
        return row.get(fieldname, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(row, fieldname, default)


def _category_abbreviation_from_name(category: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", category or "")
    if not words:
        return "CAT"
    letters = "".join(word[0] for word in words[:4])
    if len(letters) < 3:
        letters = (category or "CAT")[:3]
    return letters


def _unique_category_abbreviation(name: str, category_by_abbreviation: dict) -> str:
    base = normalize_abbreviation(_category_abbreviation_from_name(name)) or "CAT"
    if base not in category_by_abbreviation:
        return base
    suffix = 2
    while True:
        candidate = normalize_abbreviation(f"{base}{suffix}")
        if candidate not in category_by_abbreviation:
            return candidate
        suffix += 1


def _max_existing_sequence_for_prefix(prefix: str) -> int:
    prefix = normalize_abbreviation(prefix)
    if not prefix:
        return 0
    rows = frappe.db.sql(
        """
        SELECT name
        FROM `tabItem`
        WHERE name LIKE %(prefix)s
        """,
        {"prefix": f"{prefix}-%"},
        pluck=True,
    )
    max_sequence = 0
    for item_code in rows or []:
        match = re.search(r"-(\d+)$", item_code or "")
        if match:
            max_sequence = max(max_sequence, cint(match.group(1)))
    return max_sequence
