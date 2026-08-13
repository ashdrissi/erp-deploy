from __future__ import annotations

import frappe

from orderlift.role_capabilities import CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT, user_has_capability


READ_ONLY_PERMISSION_TYPES = {"read", "select", "report", "print", "email"}
WRITE_PERMISSION_TYPES = {"create", "write", "delete", "import", "export", "share"}


def has_other_charge_permission(doc=None, ptype: str | None = None, user: str | None = None, permission_type: str | None = None) -> bool | None:
    permission_type = permission_type or ptype or "read"
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    if permission_type in READ_ONLY_PERMISSION_TYPES:
        return _can_use_saved_other_charges(user)
    if permission_type in WRITE_PERMISSION_TYPES:
        return can_manage_saved_other_charges(user)
    return can_manage_saved_other_charges(user)


def can_manage_saved_other_charges(user: str | None = None) -> bool:
    return user_has_capability(CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT, user=user)


def _can_use_saved_other_charges(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if can_manage_saved_other_charges(user):
        return True
    try:
        return bool(
            frappe.has_permission("Quotation", "read", user=user)
            or frappe.has_permission("Quotation", "create", user=user)
            or frappe.has_permission("Quotation", "write", user=user)
        )
    except Exception:
        return False
