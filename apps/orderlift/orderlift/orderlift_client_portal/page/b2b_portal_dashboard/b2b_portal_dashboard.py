"""Internal B2B Portal dashboard for policies, products, requests, and invited users."""

from __future__ import annotations

from collections import Counter

import frappe
from frappe import _


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_requests": _get_recent_requests(),
        "alerts": _get_alerts(),
        "group_coverage": _get_group_coverage(),
        "request_status": _get_request_status(),
    }


def _get_kpis():
    policies = frappe.db.count("Portal Customer Group Policy") if frappe.db.exists("DocType", "Portal Customer Group Policy") else 0
    products = frappe.db.count("Portal Customer Group Product") if frappe.db.exists("DocType", "Portal Customer Group Product") else 0
    requests_total = frappe.db.count("Portal Quote Request") if frappe.db.exists("DocType", "Portal Quote Request") else 0
    portal_users = frappe.db.count("Has Role", {"role": "B2B Portal Client"}) if frappe.db.exists("DocType", "Has Role") else 0
    pending = frappe.db.count("Portal Quote Request", {"status": ["in", ["Submitted", "Under Review", "Approved"]]}) if frappe.db.exists("DocType", "Portal Quote Request") else 0
    quoted = frappe.db.count("Portal Quote Request", {"status": "Quotation Created"}) if frappe.db.exists("DocType", "Portal Quote Request") else 0
    return {
        "policies": int(policies or 0),
        "products": int(products or 0),
        "requests_total": int(requests_total or 0),
        "portal_users": int(portal_users or 0),
        "pending": int(pending or 0),
        "quoted": int(quoted or 0),
    }


def _get_recent_requests():
    if not frappe.db.exists("DocType", "Portal Quote Request"):
        return []
    return frappe.get_all(
        "Portal Quote Request",
        fields=["name", "customer", "customer_group", "portal_user", "status", "total_amount", "currency", "linked_quotation", "modified"],
        order_by="modified desc",
        limit_page_length=10,
    )


def _get_alerts():
    alerts = []
    if frappe.db.exists("DocType", "Portal Customer Group Policy"):
        empty = frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM `tabPortal Customer Group Policy` p
            WHERE p.enabled = 1
              AND NOT EXISTS (
                SELECT 1 FROM `tabPortal Customer Group Product` i
                WHERE i.parent = p.name AND i.parenttype = 'Portal Customer Group Policy' AND i.enabled = 1
              )
            """,
            as_list=True,
        )[0][0]
        if empty:
            alerts.append({
                "level": "warn",
                "title": _("{0} active portal polic(y/ies) have no products").format(empty),
                "message": _("Customers under those groups will see an empty catalog."),
                "link": "/app/portal-customer-group-policy",
            })

    if frappe.db.exists("DocType", "Portal Quote Request"):
        submitted = frappe.db.count("Portal Quote Request", {"status": "Submitted"})
        if submitted:
            alerts.append({
                "level": "info",
                "title": _("{0} quote request(s) waiting review").format(submitted),
                "message": _("Review submitted portal requests and convert approved ones to quotations."),
                "link": "/app/portal-quote-request",
            })

    return alerts[:6]


def _get_group_coverage():
    if not frappe.db.exists("DocType", "Portal Customer Group Policy"):
        return []
    rows = []
    for policy in frappe.get_all(
        "Portal Customer Group Policy",
        fields=["name", "customer_group", "enabled", "portal_price_list"],
        order_by="modified desc",
        limit_page_length=50,
    ):
        product_count = frappe.db.count(
            "Portal Customer Group Product",
            {"parent": policy.name, "parenttype": "Portal Customer Group Policy", "enabled": 1},
        )
        rows.append({
            "policy": policy.name,
            "customer_group": policy.customer_group,
            "enabled": policy.enabled,
            "portal_price_list": policy.portal_price_list,
            "product_count": product_count,
        })
    return rows


def _get_request_status():
    if not frappe.db.exists("DocType", "Portal Quote Request"):
        return []
    rows = frappe.get_all("Portal Quote Request", fields=["status"], limit_page_length=500)
    counts = Counter((row.get("status") or _("Unspecified")) for row in rows)
    return [{"label": label, "value": value} for label, value in counts.most_common(8)]
