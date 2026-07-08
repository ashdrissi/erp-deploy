from __future__ import annotations

import frappe
from frappe.utils import cint

from orderlift.menu_registry import BUSINESS_ROLES
from orderlift.orderlift.page.access_command_center.access_command_center import (
    BASE_PERMISSION_ROLE,
    GENERAL_PERMISSION_DOCTYPES,
)


PERMISSION_FIELDS = (
    "select",
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "import",
    "export",
    "print",
    "email",
    "share",
    "if_owner",
)


@frappe.whitelist()
def run(dry_run: int | bool = 1) -> dict:
    """Move admin-facing general permissions from native All into explicit business roles."""
    frappe.only_for("System Manager")
    dry_run = bool(cint(dry_run))
    roles = _existing_business_roles()
    doctypes = _existing_general_doctypes()
    result = {
        "dry_run": dry_run,
        "roles": roles,
        "doctypes": doctypes,
        "role_docperms": [],
        "neutralized_all": [],
        "skipped": [],
    }

    for doctype in doctypes:
        all_flags = _effective_role_flags(doctype, BASE_PERMISSION_ROLE)
        if not _has_any_flag(all_flags):
            result["skipped"].append({"doctype": doctype, "reason": "No active All permission"})
            continue

        for role in roles:
            existing_flags = _effective_role_flags(doctype, role)
            next_flags = _merge_flags(existing_flags, all_flags)
            action = _upsert_custom_docperm(doctype, role, next_flags, dry_run=dry_run)
            result["role_docperms"].append({"doctype": doctype, "role": role, "action": action, "flags": _active_flags(next_flags)})

        action = _upsert_custom_docperm(doctype, BASE_PERMISSION_ROLE, _zero_flags(), dry_run=dry_run)
        result["neutralized_all"].append({"doctype": doctype, "role": BASE_PERMISSION_ROLE, "action": action})

    if not dry_run:
        frappe.clear_cache()
        frappe.db.commit()
    return result


def _existing_business_roles() -> list[str]:
    return [role for role in BUSINESS_ROLES if role != BASE_PERMISSION_ROLE and frappe.db.exists("Role", role)]


def _existing_general_doctypes() -> list[str]:
    return sorted(doctype for doctype in GENERAL_PERMISSION_DOCTYPES if frappe.db.exists("DocType", doctype))


def _effective_role_flags(doctype: str, role: str) -> dict:
    custom = _first_permission_row("Custom DocPerm", doctype, role)
    standard = _first_permission_row("DocPerm", doctype, role)
    return _flags(custom or standard or {})


def _first_permission_row(permission_doctype: str, doctype: str, role: str) -> dict:
    rows = frappe.get_all(
        permission_doctype,
        filters={"parent": doctype, "role": role, "permlevel": 0},
        fields=["name", *PERMISSION_FIELDS],
        order_by="modified desc",
        limit_page_length=1,
    )
    return rows[0] if rows else {}


def _flags(row: dict) -> dict:
    return {field: 1 if cint((row or {}).get(field)) else 0 for field in PERMISSION_FIELDS}


def _merge_flags(*flag_sets: dict) -> dict:
    return {field: 1 if any(cint((flags or {}).get(field)) for flags in flag_sets) else 0 for field in PERMISSION_FIELDS}


def _zero_flags() -> dict:
    return {field: 0 for field in PERMISSION_FIELDS}


def _has_any_flag(flags: dict) -> bool:
    return any(cint(flags.get(field)) for field in PERMISSION_FIELDS)


def _active_flags(flags: dict) -> list[str]:
    return [field for field in PERMISSION_FIELDS if cint(flags.get(field))]


def _upsert_custom_docperm(doctype: str, role: str, flags: dict, dry_run: bool = True) -> str:
    if role != BASE_PERMISSION_ROLE:
        flags = {**flags, "if_owner": 0}
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    doc_name = frappe.db.exists("Custom DocPerm", filters)
    if dry_run:
        return "would_update" if doc_name else "would_create"

    if doc_name:
        doc = frappe.get_doc("Custom DocPerm", doc_name)
        action = "updated"
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 0,
            }
        )
        action = "created"

    for field in PERMISSION_FIELDS:
        setattr(doc, field, cint(flags.get(field)))
    if doc_name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return action
