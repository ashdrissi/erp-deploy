from __future__ import annotations

import frappe
from frappe import _


def require_reference_select(doctype: str) -> None:
    """Require permission to use a DocType as a reference without granting View."""
    frappe.has_permission(doctype, ptype="select", throw=True)


def require_reference_use(
    doctype: str,
    name: str | None,
    *,
    filters: dict | list | None = None,
    label: str | None = None,
    required: bool = True,
) -> str:
    clean_name = (name or "").strip()
    if not clean_name:
        if required:
            _throw_unavailable(label or doctype)
        return ""

    require_reference_select(doctype)
    permitted = frappe.get_list(
        doctype,
        filters={"name": clean_name},
        pluck="name",
        limit_page_length=1,
    )
    if not permitted or not frappe.has_permission(doctype, ptype="select", doc=clean_name):
        _throw_unavailable(label or doctype)
    if filters and not frappe.db.exists(doctype, _with_name_filter(filters, clean_name)):
        _throw_unavailable(label or doctype)
    return permitted[0]


def get_reference_doc_for_use(
    doctype: str,
    name: str | None,
    *,
    filters: dict | list | None = None,
    label: str | None = None,
):
    permitted_name = require_reference_use(doctype, name, filters=filters, label=label)
    return frappe.get_doc(doctype, permitted_name)


def get_reference_options(
    doctype: str,
    *,
    fields: list[str] | tuple[str, ...],
    filters: dict | list | None = None,
    order_by: str | None = None,
    limit: int = 1000,
) -> list:
    """Return narrow option data after applying native select and row-level scope."""
    require_reference_select(doctype)
    permitted_names = frappe.get_list(
        doctype,
        pluck="name",
        limit_page_length=0,
    )
    if not permitted_names:
        return []
    return frappe.get_all(
        doctype,
        filters=_with_names_filter(filters, permitted_names),
        fields=list(fields),
        order_by=order_by,
        limit_page_length=limit,
    )


def _with_name_filter(filters: dict | list | None, name: str):
    if isinstance(filters, dict):
        return {**filters, "name": name}
    return [*(filters or []), ["name", "=", name]]


def _with_names_filter(filters: dict | list | None, names: list[str]):
    if isinstance(filters, dict):
        return {**filters, "name": ["in", names]}
    return [*(filters or []), ["name", "in", names]]


def _throw_unavailable(label: str) -> None:
    frappe.throw(
        _("The selected {0} is unavailable or not permitted.").format(_(label)),
        frappe.PermissionError,
    )
