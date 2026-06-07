"""Row-level filters for Performance Metric Snapshot.

Admins see everything; everybody else only sees rows whose `user` column matches
their own session user. Mirrors the Employee Training Progress pattern.
"""

from __future__ import annotations

import frappe

from orderlift.orderlift_hr.api.assignment import is_hr_admin


def _admin(user: str | None = None) -> bool:
    return is_hr_admin(user)


def has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if _admin(user):
        return True
    if not doc:
        return True
    return getattr(doc, "user", None) == user


def snapshot_query(user=None):
    user = user or frappe.session.user
    if _admin(user):
        return ""
    safe = frappe.db.escape(user)
    return f"`tabPerformance Metric Snapshot`.`user` = {safe}"
