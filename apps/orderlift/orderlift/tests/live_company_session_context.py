from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import frappe

from orderlift.menu_access import (
    _session_company_cache_key,
    get_all_companies,
    get_company_access_payload,
    get_session_company_context,
    set_session_current_company,
)


DEFAULT_MATRIX_USERS = (
    "Administrator",
    "ashdrissi@gmail.com",
    "orderlift.admin@ecomepivot.com",
    "haitem@orderlift.net",
    "test.user3@orderlift.com",
    "test.user2@orderlift.com",
    "yassine@orderlift.net",
    "audit.salesmanager.20260717@ecomepivot.com",
    "ahmed.orderlift@gmail.com",
)


def run() -> dict:
    companies = get_all_companies()
    if len(companies) < 2:
        return {"skipped": True, "reason": "At least two companies are required"}

    user = "Administrator"
    sid_a = f"orderlift-live-company-a-{uuid4().hex}"
    sid_b = f"orderlift-live-company-b-{uuid4().hex}"
    original_user = frappe.session.user
    original_sid = getattr(frappe.session, "sid", None)
    original_request = getattr(frappe.local, "request", None)
    try:
        frappe.session.user = user
        frappe.session.sid = sid_a
        frappe.local.request = SimpleNamespace(cookies={"sid": sid_a}, method="POST")
        set_session_current_company(companies[0], user=user)

        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        frappe.session.sid = sid_b
        frappe.local.request = SimpleNamespace(cookies={"sid": sid_b}, method="POST")
        set_session_current_company(companies[1], user=user)

        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        frappe.session.sid = sid_a
        frappe.local.request = SimpleNamespace(cookies={"sid": sid_a}, method="GET")
        company_a = get_session_company_context(user=user).get("company")

        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        frappe.session.sid = sid_b
        frappe.local.request = SimpleNamespace(cookies={"sid": sid_b}, method="GET")
        company_b = get_session_company_context(user=user).get("company")

        if company_a != companies[0] or company_b != companies[1]:
            raise AssertionError(f"SID isolation failed: {company_a!r}, {company_b!r}")
        return {
            "passed": True,
            "user": user,
            "sid_a_company": company_a,
            "sid_b_company": company_b,
        }
    finally:
        frappe.cache.delete_value(_session_company_cache_key(sid_a))
        frappe.cache.delete_value(_session_company_cache_key(sid_b))
        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        frappe.session.user = original_user
        frappe.session.sid = original_sid
        frappe.local.request = original_request


def run_user_matrix() -> dict:
    from orderlift.company_access import purchase_order_query, quotation_query, sales_order_query

    rows = []
    for user in DEFAULT_MATRIX_USERS:
        if not frappe.db.exists("User", user):
            rows.append({"user": user, "missing": True})
            continue
        payload = get_company_access_payload(user=user)
        companies = payload.get("companies") or []
        queries = {
            "Quotation": quotation_query(user),
            "Sales Order": sales_order_query(user),
            "Purchase Order": purchase_order_query(user),
        }
        if not companies and any("name is null" not in query for query in queries.values()):
            raise AssertionError(f"Unassigned user received a company query scope: {user}")
        current_company = payload.get("current_company") or ""
        if current_company and current_company not in companies:
            raise AssertionError(f"Invalid preferred/current company for {user}: {payload}")
        if not current_company and len(companies) > 1 and not payload.get("requires_company_selection"):
            raise AssertionError(f"Missing company-selection requirement for {user}: {payload}")
        rows.append(
            {
                "user": user,
                "unrestricted": payload.get("unrestricted"),
                "companies": companies,
                "preferred_company": payload.get("preferred_company"),
                "current_company": current_company,
                "query_mode": "all_allowed" if any(" in (" in query for query in queries.values()) else "single_or_denied",
            }
        )
    return {"passed": True, "rows": rows}


def run_interactive_query_matrix() -> dict:
    from orderlift.company_access import quotation_query, sales_order_query
    from orderlift.menu_access import get_allowed_companies

    original_user = frappe.session.user
    original_sid = getattr(frappe.session, "sid", None)
    original_request = getattr(frappe.local, "request", None)
    rows = []
    cache_keys = []
    try:
        for user in DEFAULT_MATRIX_USERS:
            if not frappe.db.exists("User", user):
                continue
            companies = get_allowed_companies(user)
            if len(companies) < 2:
                continue
            sid = f"orderlift-live-query-{uuid4().hex}"
            cache_keys.append(_session_company_cache_key(sid))
            frappe.session.user = user
            frappe.session.sid = sid
            frappe.local.request = SimpleNamespace(cookies={"sid": sid}, method="GET")
            if hasattr(frappe.local, "orderlift_company_context"):
                delattr(frappe.local, "orderlift_company_context")
            selected = companies[-1]
            set_session_current_company(selected, user=user)
            queries = [quotation_query(user), sales_order_query(user)]
            expected = f".company = {frappe.db.escape(selected)}"
            if any(expected not in query for query in queries):
                raise AssertionError(f"Interactive query did not focus {user} on {selected}: {queries}")
            rows.append({"user": user, "selected_company": selected, "query_mode": "exact_sid"})
        return {"passed": True, "rows": rows}
    finally:
        for key in cache_keys:
            frappe.cache.delete_value(key)
        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        frappe.session.user = original_user
        frappe.session.sid = original_sid
        frappe.local.request = original_request


def run_interactive_write_guard() -> dict:
    from orderlift.company_scope import apply_transaction_company_scope

    user = "test.user2@orderlift.com"
    sid = f"orderlift-live-write-{uuid4().hex}"
    original_user = frappe.session.user
    original_sid = getattr(frappe.session, "sid", None)
    original_request = getattr(frappe.local, "request", None)
    doc = frappe._dict(
        doctype="Purchase Order",
        name="new-purchase-order-orderlift-live",
        company="Orderlift Maroc Installation",
        is_new=lambda: True,
    )
    try:
        frappe.session.user = user
        frappe.session.sid = sid
        frappe.local.request = SimpleNamespace(cookies={"sid": sid}, method="POST")
        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        try:
            apply_transaction_company_scope(doc)
        except frappe.ValidationError as error:
            if "Select an active Company" not in str(error):
                raise
            return {"passed": True, "user": user, "guard": "active_company_required"}
        raise AssertionError("Interactive creation succeeded without an active company")
    finally:
        frappe.cache.delete_value(_session_company_cache_key(sid))
        if hasattr(frappe.local, "orderlift_company_context"):
            delattr(frappe.local, "orderlift_company_context")
        frappe.session.user = original_user
        frappe.session.sid = original_sid
        frappe.local.request = original_request
