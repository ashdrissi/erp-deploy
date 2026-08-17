from __future__ import annotations

import frappe

from orderlift.orderlift_finance import cash_flow


PAGE_NAME = "sale-financial-dashboard"
PAGE_ROLES = ("Orderlift Admin", "System Manager", "Finance User", "Finance Admin")


def sync_page_roles() -> dict:
    if not frappe.db.exists("Page", PAGE_NAME):
        return {"skipped": True, "reason": "missing page"}
    page = frappe.get_doc("Page", PAGE_NAME)
    page.set("roles", [])
    for role in PAGE_ROLES:
        if frappe.db.exists("Role", role):
            page.append("roles", {"role": role})
    page.save(ignore_permissions=True)
    frappe.db.commit()
    return {"page": PAGE_NAME, "roles": list(PAGE_ROLES)}


@frappe.whitelist()
def get_dashboard_data(filters=None):
    frappe.has_permission("Sales Order", "read", throw=True)
    return cash_flow.get_portfolio_data(filters)


@frappe.whitelist()
def get_portfolio_data(filters=None):
    return cash_flow.get_portfolio_data(filters)


@frappe.whitelist()
def get_cash_flow_detail(context_type, context_name, horizon="13_weeks", from_date=None, to_date=None):
    return cash_flow.get_cash_flow_detail(context_type, context_name, horizon, from_date, to_date)


@frappe.whitelist()
def get_customer_performance(filters=None):
    return cash_flow.get_customer_performance(filters)


@frappe.whitelist()
def get_monthly_performance(filters=None):
    return cash_flow.get_monthly_performance(filters)


@frappe.whitelist()
def get_data_quality(filters=None):
    return cash_flow.get_data_quality(filters)
