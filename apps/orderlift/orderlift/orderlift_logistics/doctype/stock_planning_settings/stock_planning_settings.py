from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from orderlift.menu_access import resolve_current_company


RESERVATION_MODES = {
    "Manual Alert Only",
    "Create Draft Pick List",
    "Create and Submit Pick List",
}
STOCK_FLOOR_MODES = {"None", "Item Reorder Level"}


class StockPlanningSettings(Document):
    def before_validate(self):
        if not (self.company or "").strip():
            self.company = resolve_current_company(user=frappe.session.user)

    def validate(self):
        if self.reservation_mode not in RESERVATION_MODES:
            frappe.throw(_("Select a valid stock protection action."))
        if self.protected_stock_floor_mode not in STOCK_FLOOR_MODES:
            frappe.throw(_("Select a valid protected stock floor."))
        for fieldname in (
            "reservation_buffer_days",
            "incoming_safety_days",
            "procurement_safety_days",
            "default_procurement_delay_days",
            "alert_days_before_action",
        ):
            if cint(self.get(fieldname)) < 0:
                frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(fieldname)))
        if cint(self.auto_submit_material_request) and not cint(self.auto_create_material_request):
            frappe.throw(_("Enable automatic Material Request creation before enabling submission."))


def get_company_settings(company: str, *, create_default: bool = False):
    company = (company or "").strip()
    if not company:
        return None
    name = frappe.db.get_value("Stock Planning Settings", {"company": company}, "name")
    if name:
        return frappe.get_cached_doc("Stock Planning Settings", name)
    if not create_default:
        return None
    doc = frappe.new_doc("Stock Planning Settings")
    doc.company = company
    doc.enabled = 0
    doc.reservation_mode = "Create Draft Pick List"
    doc.partial_pick_list = 1
    doc.reservation_buffer_days = 15
    doc.rely_on_incoming_stock = 1
    doc.incoming_safety_days = 15
    doc.procurement_safety_days = 7
    doc.default_procurement_delay_days = 0
    doc.protected_stock_floor_mode = "None"
    doc.alert_days_before_action = 3
    doc.insert(ignore_permissions=True)
    return doc


def ensure_company_settings(doc, method=None):
    """Create a disabled planning policy with safe defaults for every new Company."""
    company = (getattr(doc, "name", "") or "").strip()
    if company:
        return get_company_settings(company, create_default=True)
    return None
