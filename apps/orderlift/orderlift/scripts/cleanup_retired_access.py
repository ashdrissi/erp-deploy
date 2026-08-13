from __future__ import annotations

import json

import frappe
from frappe.utils import cint

from orderlift.menu_access import SUPPORTING_PAGE_MENU_KEYS
from orderlift.menu_registry import iter_menu_items
from orderlift.startup_roles import RETIRED_BUSINESS_ROLES


@frappe.whitelist()
def run(dry_run: int = 1) -> dict:
    """Remove compiled grants owned by retired roles without changing user assignments."""
    frappe.only_for("System Manager")
    dry_run = bool(cint(dry_run))
    active_roles = set(frappe.get_all("Role", pluck="name", limit_page_length=0))
    invalid_roles = RETIRED_BUSINESS_ROLES | {
        role for role in _menu_role_references() if role != "All" and role not in active_roles
    }
    result = {
        "dry_run": dry_run,
        "custom_docperms": [],
        "page_report_roles": [],
        "menu_references": [],
    }

    for row in frappe.get_all(
        "Custom DocPerm",
        filters={"role": ["in", sorted(RETIRED_BUSINESS_ROLES)]},
        fields=["name", "parent", "role"],
        limit_page_length=0,
    ):
        result["custom_docperms"].append({"name": row.name, "doctype": row.parent, "role": row.role})
        if not dry_run:
            frappe.delete_doc("Custom DocPerm", row.name, ignore_permissions=True)

    managed_targets = _managed_targets()
    for row in frappe.get_all(
        "Has Role",
        filters={"parenttype": ["in", ["Page", "Report"]], "role": ["in", sorted(RETIRED_BUSINESS_ROLES)]},
        fields=["name", "parenttype", "parent", "role"],
        limit_page_length=0,
    ):
        if row.parent not in managed_targets.get(row.parenttype, set()):
            continue
        result["page_report_roles"].append(
            {"name": row.name, "parenttype": row.parenttype, "parent": row.parent, "role": row.role}
        )
        if not dry_run:
            frappe.delete_doc("Has Role", row.name, ignore_permissions=True)

    for row in frappe.get_all(
        "Orderlift Menu Access Rule",
        fields=["name", "menu_key", "allowed_roles_json", "denied_roles_json"],
        limit_page_length=0,
    ):
        updates = {}
        for fieldname in ("allowed_roles_json", "denied_roles_json"):
            roles = _clean_json_list(row.get(fieldname))
            kept = [role for role in roles if role not in invalid_roles]
            removed = [role for role in roles if role not in kept]
            result["menu_references"].extend(
                {"menu_key": row.menu_key, "field": fieldname, "role": role}
                for role in removed
            )
            if removed:
                updates[fieldname] = json.dumps(kept)
        if updates and not dry_run:
            frappe.db.set_value("Orderlift Menu Access Rule", row.name, updates)

    if not dry_run:
        frappe.clear_cache()
        frappe.db.commit()
    return result


def _managed_targets() -> dict[str, set[str]]:
    targets = {"Page": set(SUPPORTING_PAGE_MENU_KEYS), "Report": set()}
    for item in iter_menu_items():
        link_type = item.get("link_type")
        link_to = item.get("link_to")
        if link_type in targets and link_to:
            targets[link_type].add(link_to)
    return targets


def _menu_role_references() -> set[str]:
    roles = set()
    for row in frappe.get_all(
        "Orderlift Menu Access Rule",
        fields=["allowed_roles_json", "denied_roles_json"],
        limit_page_length=0,
    ):
        roles.update(_clean_json_list(row.get("allowed_roles_json")))
        roles.update(_clean_json_list(row.get("denied_roles_json")))
    return roles


def _clean_json_list(value) -> list[str]:
    try:
        values = json.loads(value or "[]")
    except (TypeError, ValueError):
        values = []
    return list(dict.fromkeys((value or "").strip() for value in values if (value or "").strip()))
