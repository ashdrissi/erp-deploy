from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


def apply_company_defaults(doc, method=None):
    """Keep Sales Order accounting/stock defaults aligned with the selected company."""
    company = (doc.get("company") or "").strip()
    if not company:
        return

    cost_center = get_default_cost_center(company)
    warehouse = get_default_warehouse(company)

    if _has_field(doc, "set_warehouse") and _needs_warehouse_replacement(doc.get("set_warehouse"), company):
        if warehouse:
            doc.set_warehouse = warehouse
        elif doc.get("set_warehouse"):
            frappe.throw(_("No default delivery warehouse is configured for {0}.").format(company))

    for row in doc.get("items") or []:
        if _has_field(row, "cost_center") and _needs_cost_center_replacement(row.get("cost_center"), company):
            if not cost_center:
                frappe.throw(_("No default Cost Center is configured for {0}.").format(company))
            row.cost_center = cost_center

        if _has_field(row, "warehouse") and _needs_warehouse_replacement(row.get("warehouse"), company):
            if warehouse:
                row.warehouse = warehouse
            elif row.get("warehouse"):
                frappe.throw(_("No default delivery warehouse is configured for {0}.").format(company))


def get_default_cost_center(company: str) -> str:
    abbr = _company_abbr(company)
    preferred = f"Main - {abbr}" if abbr else ""
    if preferred and _is_valid_cost_center(preferred, company):
        return preferred
    row = frappe.get_all(
        "Cost Center",
        filters={"company": company, "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    return row[0] if row else ""


def get_default_warehouse(company: str) -> str:
    abbr = _company_abbr(company)
    preferred = f"Main Warehouse - {abbr}" if abbr else ""
    if preferred and _is_valid_warehouse(preferred, company):
        return preferred

    filters = {"company": company, "is_group": 0, "disabled": 0}
    if _has_doctype_field("Warehouse", "custom_orderlift_base_warehouse"):
        row = frappe.get_all(
            "Warehouse",
            filters={**filters, "custom_orderlift_base_warehouse": 1},
            pluck="name",
            order_by="name asc",
            limit_page_length=1,
        )
        if row:
            return row[0]

    row = frappe.get_all(
        "Warehouse",
        filters=filters,
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    return row[0] if row else ""


def _needs_cost_center_replacement(cost_center: str | None, company: str) -> bool:
    return not cost_center or not _is_valid_cost_center(cost_center, company)


def _needs_warehouse_replacement(warehouse: str | None, company: str) -> bool:
    return not warehouse or not _is_valid_warehouse(warehouse, company)


def _is_valid_cost_center(cost_center: str | None, company: str) -> bool:
    if not cost_center:
        return False
    row = frappe.db.get_value("Cost Center", cost_center, ["company", "is_group", "disabled"], as_dict=True)
    return bool(row and row.company == company and not cint(row.is_group) and not cint(row.disabled))


def _is_valid_warehouse(warehouse: str | None, company: str) -> bool:
    if not warehouse:
        return False
    row = frappe.db.get_value("Warehouse", warehouse, ["company", "is_group", "disabled"], as_dict=True)
    return bool(row and row.company == company and not cint(row.is_group) and not cint(row.disabled))


def _company_abbr(company: str) -> str:
    return (frappe.db.get_value("Company", company, "abbr") or "").strip()


def _has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    if meta and hasattr(meta, "get_field"):
        return bool(meta.get_field(fieldname))
    return hasattr(doc, fieldname) or bool(getattr(doc, "get", lambda _field: None)(fieldname) is not None)


def _has_doctype_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False
