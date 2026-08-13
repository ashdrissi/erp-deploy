from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import (
    get_all_companies,
    get_allowed_companies,
    resolve_current_company,
    user_can_access_all_companies,
)
from orderlift.orderlift_logistics.doctype.stock_planning_settings.stock_planning_settings import (
    get_company_settings,
)


EDITABLE_FIELDS = (
    "enabled",
    "reservation_mode",
    "partial_pick_list",
    "reservation_buffer_days",
    "rely_on_incoming_stock",
    "incoming_safety_days",
    "procurement_safety_days",
    "default_procurement_delay_days",
    "auto_create_material_request",
    "auto_submit_material_request",
    "protected_stock_floor_mode",
    "alert_days_before_action",
)
CHECK_FIELDS = {
    "enabled",
    "partial_pick_list",
    "rely_on_incoming_stock",
    "auto_create_material_request",
    "auto_submit_material_request",
}
INT_FIELDS = {
    "reservation_buffer_days",
    "incoming_safety_days",
    "procurement_safety_days",
    "default_procurement_delay_days",
    "alert_days_before_action",
}


@frappe.whitelist()
def get_page_data(company: str | None = None) -> dict:
    frappe.has_permission("Stock Planning Settings", "read", throw=True)
    companies = _accessible_companies()
    selected = _selected_company(company, companies)
    for company_name in companies:
        get_company_settings(company_name, create_default=True)
    settings = get_company_settings(selected, create_default=True) if selected else None
    if settings:
        settings.check_permission("read")
    return {
        "companies": companies,
        "selected_company": selected,
        "can_edit": bool(settings and frappe.has_permission("Stock Planning Settings", "write", doc=settings)),
        "settings": _serialize_settings(settings),
    }


@frappe.whitelist()
def save_settings(company: str, values) -> dict:
    companies = _accessible_companies()
    company = _selected_company(company, companies, required=True)
    settings = get_company_settings(company, create_default=True)
    settings.check_permission("write")
    payload = frappe.parse_json(values) if isinstance(values, str) else values
    if not isinstance(payload, dict):
        frappe.throw(_("Settings payload must be an object."))
    for fieldname in EDITABLE_FIELDS:
        if fieldname not in payload:
            continue
        value = payload[fieldname]
        if fieldname in CHECK_FIELDS:
            value = cint(value)
        elif fieldname in INT_FIELDS:
            value = cint(value)
        settings.set(fieldname, value)
    settings.save()
    frappe.clear_document_cache("Stock Planning Settings", settings.name)
    return {
        "company": company,
        "settings": _serialize_settings(settings),
    }


def _accessible_companies() -> list[str]:
    user = frappe.session.user
    companies = get_all_companies() if user_can_access_all_companies(user) else get_allowed_companies(user)
    return sorted(dict.fromkeys((company or "").strip() for company in companies if (company or "").strip()))


def _selected_company(company, companies: list[str], *, required: bool = False) -> str:
    requested = (company or "").strip()
    if requested and requested not in companies:
        frappe.throw(_("Company {0} is outside your allowed company scope.").format(requested), frappe.PermissionError)
    selected = requested or resolve_current_company(user=frappe.session.user, allowed_companies=companies) or (
        companies[0] if companies else ""
    )
    if required and not selected:
        frappe.throw(_("Select a company first."))
    return selected


def _serialize_settings(settings) -> dict:
    if not settings:
        return {}
    return {
        fieldname: settings.get(fieldname)
        for fieldname in ("name", "company", *EDITABLE_FIELDS)
    }
