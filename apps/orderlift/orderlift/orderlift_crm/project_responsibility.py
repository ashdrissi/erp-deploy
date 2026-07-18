from __future__ import annotations

import frappe


def ensure_project_responsibility(doc, method=None) -> None:
    """Keep one explicit project manager and include them in Project Users.

    ERPNext's Project Users table remains the source used by Collect Progress;
    this helper only supplies a clear primary responsible person and keeps the
    native table in sync.
    """
    if not doc or not _has_field(doc, "custom_project_owner"):
        return

    project_owner = (_get(doc, "custom_project_owner") or _get(doc, "owner") or frappe.session.user or "").strip()
    if not project_owner:
        return
    _set(doc, "custom_project_owner", project_owner)

    if not _has_field(doc, "users"):
        return
    existing = {
        (_get(row, "user") or "").strip()
        for row in (_get(doc, "users") or [])
        if (_get(row, "user") or "").strip()
    }
    if project_owner not in existing:
        doc.append("users", {"user": project_owner})


def _has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    getter = getattr(meta, "get_field", None)
    return bool(getter(fieldname)) if callable(getter) else hasattr(doc, fieldname)


def _get(doc, fieldname: str):
    getter = getattr(doc, "get", None)
    return getter(fieldname) if callable(getter) else getattr(doc, fieldname, None)


def _set(doc, fieldname: str, value) -> None:
    setter = getattr(doc, "set", None)
    if callable(setter):
        setter(fieldname, value)
    else:
        setattr(doc, fieldname, value)
