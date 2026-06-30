from __future__ import annotations

import json

import frappe

from orderlift.menu_access import MENU_ACCESS_DOCTYPE, _clean_list, sync_menu_access_rules
from orderlift.menu_registry import iter_menu_items


def menu_page_role_map() -> dict[str, list[str]]:
    """Return additive Page role requirements implied by the central menu registry."""
    page_roles: dict[str, list[str]] = {}
    for item in iter_menu_items():
        if item.get("link_type") != "Page" or not item.get("link_to"):
            continue
        page_name = item["link_to"]
        page_roles.setdefault(page_name, [])
        for role in item.get("roles") or []:
            if role not in page_roles[page_name]:
                page_roles[page_name].append(role)
    return page_roles


def strict_menu_page_role_map() -> dict[str, list[str]]:
    """Return exact Page role requirements for pages that should not preserve stale roles."""
    page_roles: dict[str, list[str]] = {}
    for item in iter_menu_items():
        if not item.get("strict_roles") or item.get("link_type") != "Page" or not item.get("link_to"):
            continue
        page_name = item["link_to"]
        page_roles.setdefault(page_name, [])
        for role in item.get("roles") or []:
            if role not in page_roles[page_name]:
                page_roles[page_name].append(role)
    return page_roles


def run(dry_run: int | str = 0, strict_only: int | str = 0) -> dict:
    dry_run = bool(int(dry_run or 0))
    strict_only = bool(int(strict_only or 0))
    if not dry_run:
        sync_menu_access_rules()
    existing_roles = set(frappe.get_all("Role", pluck="name", limit_page_length=0))
    strict_page_roles = strict_menu_page_role_map()
    page_role_map = strict_page_roles if strict_only else menu_page_role_map()
    summary = {
        "dry_run": dry_run,
        "strict_only": strict_only,
        "checked_pages": 0,
        "checked_menu_rules": 0,
        "missing_pages": [],
        "missing_menu_rules": [],
        "skipped_missing_roles": [],
        "added": [],
        "removed": [],
        "menu_rules_added": [],
        "menu_rules_removed": [],
        "already_present": 0,
        "menu_rules_already_present": 0,
    }

    menu_items = [item for item in iter_menu_items() if not strict_only or item.get("strict_roles")]

    for page_name, wanted_roles in page_role_map.items():
        if not frappe.db.exists("Page", page_name):
            summary["missing_pages"].append(page_name)
            continue

        summary["checked_pages"] += 1
        page = frappe.get_doc("Page", page_name)
        current_roles = {
            row.role
            for row in page.get("roles") or []
            if getattr(row, "role", None)
        }
        changed = False
        if page_name in strict_page_roles:
            wanted_role_set = set(wanted_roles)
            stale_rows = [row for row in page.get("roles") or [] if getattr(row, "role", None) not in wanted_role_set]
            for row in stale_rows:
                summary["removed"].append({"page": page_name, "role": row.role})
                current_roles.discard(row.role)
                if not dry_run:
                    page.remove(row)
                    changed = True
        for role in wanted_roles:
            if role not in existing_roles:
                summary["skipped_missing_roles"].append({"page": page_name, "role": role})
                continue
            if role in current_roles:
                summary["already_present"] += 1
                continue
            summary["added"].append({"page": page_name, "role": role})
            if not dry_run:
                page.append("roles", {"role": role})
                current_roles.add(role)
                changed = True

        if not dry_run and changed:
            page.save(ignore_permissions=True)

    if frappe.db.exists("DocType", MENU_ACCESS_DOCTYPE):
        if dry_run:
            # Keep dry-runs read-only while still reporting missing existing rules.
            existing_rule_keys = set(
                frappe.get_all(MENU_ACCESS_DOCTYPE, pluck="menu_key", limit_page_length=0)
            )
        else:
            existing_rule_keys = set(
                frappe.get_all(MENU_ACCESS_DOCTYPE, pluck="menu_key", limit_page_length=0)
            )

        for item in menu_items:
            menu_key = item["key"]
            if menu_key not in existing_rule_keys:
                summary["missing_menu_rules"].append(menu_key)
                continue

            summary["checked_menu_rules"] += 1
            doc_name = frappe.db.get_value(MENU_ACCESS_DOCTYPE, {"menu_key": menu_key}, "name")
            doc = frappe.get_doc(MENU_ACCESS_DOCTYPE, doc_name)
            current_roles = _clean_list(doc.get("allowed_roles_json"))
            changed = False
            if item.get("strict_roles"):
                wanted_role_set = set(item.get("roles") or [])
                stale_roles = [role for role in current_roles if role not in wanted_role_set]
                if stale_roles:
                    summary["menu_rules_removed"].extend(
                        {"menu_key": menu_key, "role": role} for role in stale_roles
                    )
                    current_roles = [role for role in current_roles if role in wanted_role_set]
                    changed = True
            for role in item.get("roles") or []:
                if role not in existing_roles:
                    summary["skipped_missing_roles"].append({"menu_key": menu_key, "role": role})
                    continue
                if role in current_roles:
                    summary["menu_rules_already_present"] += 1
                    continue
                current_roles.append(role)
                summary["menu_rules_added"].append({"menu_key": menu_key, "role": role})
                changed = True

            if changed and not dry_run:
                doc.allowed_roles_json = json.dumps(current_roles)
                doc.save(ignore_permissions=True)

    if not dry_run:
        frappe.clear_cache()
        frappe.db.commit()
    return summary
