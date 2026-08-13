from __future__ import annotations

import json

import frappe

from orderlift.menu_access import (
    MENU_ACCESS_DOCTYPE,
    SUPPORTING_PAGE_MENU_KEYS,
    _clean_list,
    sync_menu_access_rules,
)
from orderlift.menu_registry import iter_menu_items, menu_item_by_key
from orderlift.startup_roles import ORDERLIFT_MANAGED_ROLE_FIELD


def menu_page_role_map() -> dict[str, list[str]]:
    """Return exact Page role requirements implied by the central menu registry."""
    page_roles: dict[str, list[str]] = {}
    for item in iter_menu_items():
        if item.get("link_type") != "Page" or not item.get("link_to"):
            continue
        page_name = item["link_to"]
        page_roles.setdefault(page_name, [])
        for role in item.get("roles") or []:
            if role not in page_roles[page_name]:
                page_roles[page_name].append(role)
        if "System Manager" not in page_roles[page_name]:
            page_roles[page_name].append("System Manager")
    return page_roles


def strict_menu_page_role_map() -> dict[str, list[str]]:
    """All registry-managed Pages use authoritative role rows."""
    roles = menu_page_role_map()
    for page_name, menu_key in SUPPORTING_PAGE_MENU_KEYS.items():
        item = menu_item_by_key(menu_key) or {}
        page_roles = list(item.get("roles") or [])
        if "System Manager" not in page_roles:
            page_roles.append("System Manager")
        roles[page_name] = page_roles
    return roles


def menu_report_role_map() -> dict[str, list[str]]:
    """Return exact Report role requirements implied by the central registry."""
    report_roles: dict[str, list[str]] = {}
    for item in iter_menu_items():
        if item.get("link_type") != "Report" or not item.get("link_to"):
            continue
        report_name = item["link_to"]
        report_roles.setdefault(report_name, [])
        for role in [*(item.get("roles") or []), "System Manager"]:
            if role not in report_roles[report_name]:
                report_roles[report_name].append(role)
    return report_roles


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
        "checked_reports": 0,
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

    if not strict_only:
        summary["authoritative_grants"] = True
        if not dry_run:
            from orderlift.orderlift.page.access_command_center.access_command_center import (
                ensure_managed_role_grant_snapshots,
                reconcile_business_menu_access,
                sync_business_import_support_permissions,
            )

            ensure_managed_role_grant_snapshots()
            sync_business_import_support_permissions()
            reconcile_business_menu_access()
            frappe.clear_cache()
            frappe.db.commit()
        return summary

    menu_items = [
        item
        for item in iter_menu_items()
        if not strict_only or (item.get("link_type") == "Page" and item.get("link_to"))
    ]

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
        if strict_only and page_name in strict_page_roles:
            wanted_role_set = set(wanted_roles)
            stale_rows = [
                row
                for row in page.get("roles") or []
                if getattr(row, "role", None) not in wanted_role_set
                and not _is_managed_custom_role(getattr(row, "role", None))
            ]
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

    for report_name, wanted_roles in menu_report_role_map().items():
        if not frappe.db.exists("Report", report_name):
            continue
        summary["checked_reports"] += 1
        report = frappe.get_doc("Report", report_name)
        current_roles = {
            row.role
            for row in report.get("roles") or []
            if getattr(row, "role", None)
        }
        wanted_role_set = set(wanted_roles)
        changed = False
        for row in [
            row
            for row in report.get("roles") or []
            if getattr(row, "role", None) not in wanted_role_set
            and not _is_managed_custom_role(getattr(row, "role", None))
        ]:
            summary["removed"].append({"report": report_name, "role": row.role})
            if not dry_run:
                report.remove(row)
                changed = True
        for role in wanted_roles:
            if role not in existing_roles:
                summary["skipped_missing_roles"].append({"report": report_name, "role": role})
                continue
            if role in current_roles:
                summary["already_present"] += 1
                continue
            summary["added"].append({"report": report_name, "role": role})
            if not dry_run:
                report.append("roles", {"role": role})
                changed = True
        if not dry_run and changed:
            report.save(ignore_permissions=True)

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
            wanted_role_set = set(item.get("roles") or [])
            stale_roles = [
                role
                for role in current_roles
                if role not in wanted_role_set and not _is_managed_custom_role(role)
            ]
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
        from orderlift.orderlift.page.access_command_center.access_command_center import (
            ensure_managed_role_grant_snapshots,
            reconcile_business_menu_access,
            sync_business_import_support_permissions,
        )

        ensure_managed_role_grant_snapshots()
        sync_business_import_support_permissions()
        reconcile_business_menu_access()
        frappe.clear_cache()
        frappe.db.commit()
    return summary


def _is_managed_custom_role(role: str | None) -> bool:
    if not role or not frappe.db.exists("Role", role):
        return False
    try:
        return bool(
            frappe.db.get_value(
                "Role",
                role,
                ["is_custom", ORDERLIFT_MANAGED_ROLE_FIELD],
                as_dict=True,
            ).get(ORDERLIFT_MANAGED_ROLE_FIELD)
        )
    except Exception:
        return False
