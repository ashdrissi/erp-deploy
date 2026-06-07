from __future__ import annotations

import frappe

from orderlift.company_scope import business_type_field_for, company_field_for, segments_field_for
from orderlift.menu_access import (
    get_allowed_business_types,
    get_allowed_companies,
    user_can_access_all_business_types,
    user_can_access_all_companies,
)


SEGMENT_ASSIGNMENT_DOCTYPE = "CRM Segment Assignment"


COMPANY_SCOPED_DOCTYPES = [
    "Company",
    "Opportunity",
    "Quotation",
    "Sales Order",
    "Sales Invoice",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Delivery Note",
    "Payment Entry",
    "Stock Entry",
    "Material Request",
    "Request for Quotation",
    "Project",
    "Sales Commission",
    "SAV Ticket",
    "Forecast Load Plan",
    # Company-owned masters / operational records (see orderlift.company_scope).
    "Customer",
    "Supplier",
    "Price List",
    "Prospect",
    "Lead",
    "Pricing Sheet",
    "Pricing Scenario",
    "Pricing Benchmark Policy",
    "Pricing Customs Policy",
    "Customer Segmentation Engine",
    "Partner Campaign",
    "Portal Customer Group Policy",
    "Portal Quote Request",
]

READ_ONLY_PERMISSION_TYPES = {"read", "report", "print", "email"}


def has_company_permission(
    doc,
    ptype: str | None = None,
    user: str | None = None,
    permission_type: str | None = None,
) -> bool | None:
    permission_type = permission_type or ptype
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return True
    if not doc:
        return None

    if getattr(doc, "doctype", None) == "Sales Commission" and not _can_manage_sales_commissions(user):
        if permission_type and permission_type not in READ_ONLY_PERMISSION_TYPES:
            return False
        salesperson = _sales_person_for_user(user)
        if not salesperson or doc.get("salesperson") != salesperson:
            return False

    company = _company_from_doc(doc)
    if not company:
        if permission_type == "create" and _is_new_doc(doc):
            return True
        return False
    if company not in set(get_allowed_companies(user)):
        return False
    return _doc_business_type_allowed(doc, user)


def company_query(user: str | None = None) -> str | None:
    return _company_query("Company", user=user)


def opportunity_query(user: str | None = None) -> str | None:
    return _company_query("Opportunity", user=user)


def quotation_query(user: str | None = None) -> str | None:
    return _company_query("Quotation", user=user)


def sales_order_query(user: str | None = None) -> str | None:
    return _company_query("Sales Order", user=user)


def sales_invoice_query(user: str | None = None) -> str | None:
    return _company_query("Sales Invoice", user=user)


def purchase_order_query(user: str | None = None) -> str | None:
    return _company_query("Purchase Order", user=user)


def purchase_receipt_query(user: str | None = None) -> str | None:
    return _company_query("Purchase Receipt", user=user)


def purchase_invoice_query(user: str | None = None) -> str | None:
    return _company_query("Purchase Invoice", user=user)


def delivery_note_query(user: str | None = None) -> str | None:
    return _company_query("Delivery Note", user=user)


def payment_entry_query(user: str | None = None) -> str | None:
    return _company_query("Payment Entry", user=user)


def stock_entry_query(user: str | None = None) -> str | None:
    return _company_query("Stock Entry", user=user)


def material_request_query(user: str | None = None) -> str | None:
    return _company_query("Material Request", user=user)


def request_for_quotation_query(user: str | None = None) -> str | None:
    return _company_query("Request for Quotation", user=user)


def project_query(user: str | None = None) -> str | None:
    return _company_query("Project", user=user)


def pricing_sheet_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Sheet", user=user)


def customer_query(user: str | None = None) -> str | None:
    return _company_query("Customer", user=user)


def supplier_query(user: str | None = None) -> str | None:
    return _company_query("Supplier", user=user)


def price_list_query(user: str | None = None) -> str | None:
    return _company_query("Price List", user=user)


def prospect_query(user: str | None = None) -> str | None:
    return _company_query("Prospect", user=user)


def lead_query(user: str | None = None) -> str | None:
    return _company_query("Lead", user=user)


def pricing_scenario_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Scenario", user=user)


def pricing_benchmark_policy_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Benchmark Policy", user=user)


def pricing_customs_policy_query(user: str | None = None) -> str | None:
    return _company_query("Pricing Customs Policy", user=user)


def customer_segmentation_engine_query(user: str | None = None) -> str | None:
    return _company_query("Customer Segmentation Engine", user=user)


def partner_campaign_query(user: str | None = None) -> str | None:
    return _company_query("Partner Campaign", user=user)


def portal_customer_group_policy_query(user: str | None = None) -> str | None:
    return _company_query("Portal Customer Group Policy", user=user)


def portal_quote_request_query(user: str | None = None) -> str | None:
    return _company_query("Portal Quote Request", user=user)


def sales_commission_query(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    base_query = _company_query("Sales Commission", user=user)
    if _can_manage_sales_commissions(user):
        return base_query

    salesperson = _sales_person_for_user(user)
    table = _table_name("Sales Commission")
    if not salesperson:
        own_query = f"{table}.name is null"
    else:
        own_query = f"{table}.salesperson = {frappe.db.escape(salesperson)}"
    return f"({base_query}) and ({own_query})" if base_query else own_query


def sav_ticket_query(user: str | None = None) -> str | None:
    return _company_query("SAV Ticket", user=user)


def forecast_load_plan_query(user: str | None = None) -> str | None:
    return _company_query("Forecast Load Plan", user=user)


def _company_query(doctype: str, user: str | None = None) -> str | None:
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return None

    allowed_companies = get_allowed_companies(user)
    table = _table_name(doctype)
    if not allowed_companies:
        return f"{table}.name is null"

    if doctype == "Company":
        escaped = ", ".join(frappe.db.escape(company) for company in allowed_companies)
        return f"{table}.name in ({escaped})"

    field = company_field_for(doctype)
    if not _has_company_field(doctype, field):
        return f"{table}.name is null"

    escaped = ", ".join(frappe.db.escape(company) for company in allowed_companies)
    company_clause = f"{table}.{field} in ({escaped})"

    bt_clause = _business_type_clause(doctype, user)
    if bt_clause:
        return f"({company_clause}) and ({bt_clause})"
    return company_clause


def _business_type_clause(doctype: str, user: str) -> str | None:
    """SQL fragment restricting a scoped doctype to the user's allowed business types.

    Returns ``None`` when the user is business-type-unrestricted (so company-only
    output is unchanged). Records with no business type set stay visible.
    """
    if user_can_access_all_business_types(user):
        return None
    allowed = get_allowed_business_types(user)
    if not allowed:
        return None

    table = _table_name(doctype)
    escaped = ", ".join(frappe.db.escape(bt) for bt in allowed)

    bt_field = business_type_field_for(doctype)
    if bt_field and _has_company_field(doctype, bt_field):
        column = f"{table}.{bt_field}"
        return f"({column} in ({escaped}) or {column} is null or {column} = '')"

    segments_field = segments_field_for(doctype)
    if segments_field and _has_company_field(doctype, segments_field):
        seg = _table_name(SEGMENT_ASSIGNMENT_DOCTYPE)
        escaped_dt = frappe.db.escape(doctype)
        escaped_field = frappe.db.escape(segments_field)
        base = (
            f"select 1 from {seg} _bt_seg "
            f"where _bt_seg.parent = {table}.name "
            f"and _bt_seg.parenttype = {escaped_dt} "
            f"and _bt_seg.parentfield = {escaped_field}"
        )
        return (
            f"(not exists ({base}) "
            f"or exists ({base} and _bt_seg.business_type in ({escaped})))"
        )

    return None


def _doc_business_type_allowed(doc, user: str) -> bool:
    if user_can_access_all_business_types(user):
        return True
    allowed = set(get_allowed_business_types(user))
    doctype = getattr(doc, "doctype", None)

    bt_field = business_type_field_for(doctype)
    if bt_field:
        value = (doc.get(bt_field) or "").strip() if hasattr(doc, "get") else ""
        return (not value) or value in allowed

    segments_field = segments_field_for(doctype)
    if segments_field and hasattr(doc, "get"):
        business_types = [
            (row.get("business_type") or "").strip()
            for row in (doc.get(segments_field) or [])
        ]
        business_types = [bt for bt in business_types if bt]
        if not business_types:
            return True
        return any(bt in allowed for bt in business_types)

    return True


def _company_from_doc(doc) -> str:
    if getattr(doc, "doctype", None) == "Company":
        return doc.name
    field = company_field_for(getattr(doc, "doctype", None))
    if hasattr(doc, "get"):
        return doc.get(field) or ""
    return getattr(doc, field, "") or ""


def _table_name(doctype: str) -> str:
    return f"`tab{doctype.replace('`', '')}`"


def _has_company_field(doctype: str, field: str = "company") -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(field))
    except Exception:
        return False


def _is_new_doc(doc) -> bool:
    try:
        return bool(doc.is_new())
    except Exception:
        return not bool(getattr(doc, "name", None))


def _can_manage_sales_commissions(user: str) -> bool:
    manager_roles = {"Orderlift Admin", "Sales Manager", "Orderlift Accountant", "System Manager", "Administrator"}
    return bool(manager_roles.intersection(set(frappe.get_roles(user))))


def _sales_person_for_user(user: str) -> str:
    if not frappe.db.exists("DocType", "Sales Person") or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""
