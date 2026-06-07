from __future__ import annotations

import frappe

from orderlift.menu_registry import BUSINESS_ROLES


LEGACY_ORDERLIFT_ROLES = {
    "B2B Portal Client",
    "B2B Portal Manager",
    "Finance User",  # kept by BUSINESS_ROLES below
    "Installation Manager",
    "Logistics Manager",
    "Orderlift Accountant",
    "Orderlift Business Admin",
    "Orderlift Client User",
    "Orderlift Commercial",
    "Orderlift Technician",
    "Pricing User",
    "Purchasing User",
    "SAV Manager",
    "SAV User",
    "SIG Manager",
    "SIG Technician",
}


@frappe.whitelist()
def run(dry_run: int = 1) -> dict:
    dry_run = bool(int(dry_run or 0))
    allowed_roles = set(BUSINESS_ROLES)

    role_profiles = frappe.get_all("Role Profile", pluck="name", limit_page_length=0)
    legacy_roles = sorted(
        role
        for role in LEGACY_ORDERLIFT_ROLES
        if role not in allowed_roles and frappe.db.exists("Role", role)
    )

    users_with_profiles = frappe.get_all(
        "User",
        filters={"role_profile_name": ["not in", ["", None]]},
        pluck="name",
        limit_page_length=0,
    )

    if dry_run:
        return {
            "dry_run": True,
            "role_profiles_to_delete": role_profiles,
            "users_to_clear_role_profile": users_with_profiles,
            "legacy_roles_to_delete": legacy_roles,
        }

    for user in users_with_profiles:
        frappe.db.set_value("User", user, "role_profile_name", "", update_modified=False)

    deleted_profiles = []
    for profile in role_profiles:
        frappe.delete_doc("Role Profile", profile, ignore_permissions=True, force=True)
        deleted_profiles.append(profile)

    deleted_roles = []
    skipped_roles = []
    for role in legacy_roles:
        _delete_role_references(role)
        try:
            frappe.delete_doc("Role", role, ignore_permissions=True, force=True)
            deleted_roles.append(role)
        except Exception as exc:
            skipped_roles.append({"role": role, "reason": str(exc)})

    frappe.db.commit()
    frappe.clear_cache()
    return {
        "dry_run": False,
        "cleared_user_role_profiles": users_with_profiles,
        "deleted_role_profiles": deleted_profiles,
        "deleted_legacy_roles": deleted_roles,
        "skipped_legacy_roles": skipped_roles,
        "kept_business_roles": list(BUSINESS_ROLES),
    }


def _delete_role_references(role: str) -> None:
    child_tables = ["Has Role", "DocPerm", "Custom DocPerm"]
    for doctype in child_tables:
        if frappe.db.exists("DocType", doctype) and _has_field(doctype, "role"):
            frappe.db.delete(doctype, {"role": role})

    if frappe.db.exists("DocType", "User Document Type") and _has_field("User Document Type", "role"):
        frappe.db.delete("User Document Type", {"role": role})


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))
