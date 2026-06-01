from __future__ import annotations

import frappe

from orderlift.company_scope import company_field_for
from orderlift.menu_access import get_allowed_companies, user_can_access_all_companies


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

    company = _company_from_doc(doc)
    if not company:
        if permission_type == "create" and _is_new_doc(doc):
            return True
        return False
    return company in set(get_allowed_companies(user))


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
    return _company_query("Sales Commission", user=user)


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
    return f"{table}.{field} in ({escaped})"


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
