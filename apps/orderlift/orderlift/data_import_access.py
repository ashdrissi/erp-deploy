from __future__ import annotations

import frappe
from frappe.utils import cint


@frappe.whitelist()
def get_importable_doctypes(
    doctype: str | None = None,
    txt: str | None = None,
    searchfield: str | None = None,
    start: int = 0,
    page_len: int = 20,
    filters=None,
) -> list[list[str]]:
    """Return only parent DocTypes the current user can actually import."""
    frappe.has_permission("Data Import", "read", throw=True)
    txt = (txt or "").strip()
    candidates = frappe.get_all(
        "DocType",
        filters={
            "allow_import": 1,
            "istable": 0,
            "name": ["like", f"%{txt}%"],
        },
        fields=["name", "module"],
        order_by="name asc",
        limit_page_length=0,
    )
    allowed = [
        [row.get("name"), row.get("module") or ""]
        for row in candidates
        if frappe.has_permission(row.get("name"), "import")
    ]
    start = max(cint(start), 0)
    page_len = min(max(cint(page_len), 1), 100)
    return allowed[start : start + page_len]
