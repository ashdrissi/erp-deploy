from __future__ import annotations

import frappe
from frappe.utils import cint


TARGET_USER_ROLES = {
    "ashdrissi@gmail.com": ["System Manager"],
    "taha@orderlift.net": ["Orderlift Admin"],
    "sara@orderlift.net": ["Orderlift Admin"],
    "imad@orderlift.net": ["Orderlift Admin"],
    "haitem@orderlift.net": ["Sales User"],
    "yassine@orderlift.net": ["Sales User"],
    "ahmed.orderlift@gmail.com": ["Sales User"],
    "bilalorderlift@gmail.com": ["Sales User", "Purchase User", "Stock User"],
    "orderlift.admin@ecomepivot.com": ["Orderlift Admin"],
    "ashdrissi1@gmail.com": [],
}
IMPLICIT_ROLES = {"All", "Desk User", "Guest"}


@frappe.whitelist()
def run(dry_run: int = 1) -> dict:
    """Normalize the approved named users without changing User Permission scopes."""
    frappe.only_for("System Manager")
    dry_run = bool(cint(dry_run))
    result = {
        "dry_run": dry_run,
        "users": [],
        "missing_users": [],
        "missing_sales_person_mappings": [],
    }

    for user_name, desired_roles in TARGET_USER_ROLES.items():
        if not frappe.db.exists("User", user_name):
            result["missing_users"].append(user_name)
            continue
        user = frappe.get_doc("User", user_name)
        current_roles = [row.role for row in user.get("roles") or [] if getattr(row, "role", None)]
        implicit_roles = [role for role in current_roles if role in IMPLICIT_ROLES]
        next_roles = list(dict.fromkeys([*implicit_roles, *desired_roles]))
        current_profile = (user.get("role_profile_name") or "").strip()
        row = {
            "user": user_name,
            "current_roles": current_roles,
            "desired_roles": list(desired_roles),
            "added_roles": [role for role in desired_roles if role not in current_roles],
            "removed_roles": [role for role in current_roles if role not in next_roles],
            "cleared_role_profile": current_profile,
            "changed": current_roles != next_roles or bool(current_profile),
        }
        result["users"].append(row)

        if "Sales User" in desired_roles and not _sales_person_for_user(user_name):
            result["missing_sales_person_mappings"].append(user_name)

        if dry_run or not row["changed"]:
            continue
        user.set("roles", [])
        for role in next_roles:
            user.append("roles", {"role": role})
        user.role_profile_name = ""
        user.save(ignore_permissions=True)
        _remove_unapproved_persisted_roles(user_name, set(next_roles))

    if not dry_run:
        frappe.clear_cache()
        frappe.db.commit()
    return result


def _sales_person_for_user(user: str) -> str:
    if not frappe.db.exists("DocType", "Sales Person"):
        return ""
    if hasattr(frappe.db, "has_column") and not frappe.db.has_column("Sales Person", "user"):
        return ""
    return frappe.db.get_value("Sales Person", {"user": user}, "name") or ""


def _remove_unapproved_persisted_roles(user: str, approved_roles: set[str]) -> None:
    rows = frappe.get_all(
        "Has Role",
        filters={"parenttype": "User", "parent": user},
        fields=["name", "role"],
        limit_page_length=0,
    )
    for row in rows:
        if row.role not in approved_roles:
            frappe.delete_doc("Has Role", row.name, ignore_permissions=True)
