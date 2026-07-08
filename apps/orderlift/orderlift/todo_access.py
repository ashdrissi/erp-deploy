from __future__ import annotations

import frappe

from orderlift.role_capabilities import CAPABILITY_TODO_ALL_ACCESS, user_has_capability


def todo_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    if _can_access_all_todos(user):
        return None
    if not user or user == "Guest":
        return "`tabToDo`.name is null"
    return f"`tabToDo`.allocated_to = {frappe.db.escape(user)}"


def has_todo_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool | None:
    user = user or frappe.session.user
    if _can_access_all_todos(user):
        return True
    if not user or user == "Guest":
        return False
    if _is_new_doc(doc):
        return None
    return (getattr(doc, "allocated_to", None) or "") == user


def _can_access_all_todos(user: str | None = None) -> bool:
    return user_has_capability(CAPABILITY_TODO_ALL_ACCESS, user=user)


def _is_new_doc(doc) -> bool:
    try:
        return bool(doc.is_new())
    except Exception:
        return not bool(getattr(doc, "name", None))
