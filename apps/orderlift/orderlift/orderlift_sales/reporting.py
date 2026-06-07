from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt


BUSINESS_TYPE_BUCKETS = ("Distribution", "Installation", "Maintenance", "Unassigned")
REPORTING_COMPANY_FIELD = "custom_orderlift_reporting_company"


def has_doctype(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))


def has_field(doctype: str, fieldname: str) -> bool:
    if not has_doctype(doctype):
        return False
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def normalize_business_type(value: str | None) -> str:
    value = (value or "").strip()
    return value if value in {"Distribution", "Installation", "Maintenance"} else "Unassigned"


def margin_percent(revenue, charges) -> float:
    revenue = flt(revenue or 0)
    if not revenue:
        return 0.0
    return round(((revenue - flt(charges or 0)) / revenue) * 100, 2)


def empty_currency_totals() -> dict[str, dict]:
    return defaultdict(lambda: {"currency": "", "revenue": 0.0, "charges": 0.0, "margin": 0.0, "margin_pct": 0.0})


def add_amount(totals: dict, currency: str | None, key: str, amount) -> None:
    currency = (currency or "").strip() or "Unspecified"
    row = totals[currency]
    row["currency"] = currency
    row[key] = flt(row.get(key) or 0) + flt(amount or 0)
    _refresh_margin(row)


def currency_totals_to_rows(totals: dict) -> list[dict]:
    rows = []
    for currency in sorted(totals):
        row = dict(totals[currency])
        _refresh_margin(row)
        rows.append(row)
    return rows


def get_reporting_companies() -> list[dict]:
    if not has_doctype("Company"):
        return []

    fields = ["name", "default_currency"]
    if has_field("Company", "abbr"):
        fields.append("abbr")
    filters = {}
    if has_field("Company", REPORTING_COMPANY_FIELD):
        filters[REPORTING_COMPANY_FIELD] = 1
    if has_field("Company", "disabled"):
        filters["disabled"] = 0

    rows = frappe.get_all("Company", filters=filters, fields=fields, order_by="name asc", limit_page_length=0)
    return [
        {
            "name": row.get("name"),
            "abbr": row.get("abbr") or "",
            "currency": row.get("default_currency") or "",
        }
        for row in rows
        if row.get("name")
    ]


def reporting_company_names() -> set[str]:
    return {row["name"] for row in get_reporting_companies()}


def company_currency(company: str | None) -> str:
    if not company or not has_doctype("Company"):
        return ""
    return frappe.db.get_value("Company", company, "default_currency") or ""


def project_business_type(project_name: str | None) -> str:
    if not project_name or not has_doctype("Project"):
        return "Unassigned"
    fields = []
    for fieldname in ["custom_crm_business_type", "custom_source_opportunity"]:
        if has_field("Project", fieldname):
            fields.append(fieldname)
    values = frappe.db.get_value("Project", project_name, fields, as_dict=True) if fields else None
    values = values or {}
    if values.get("custom_crm_business_type"):
        return normalize_business_type(values.get("custom_crm_business_type"))
    opportunity = values.get("custom_source_opportunity")
    if opportunity:
        return opportunity_business_type(opportunity)
    return "Installation"


def opportunity_business_type(opportunity: str | None) -> str:
    if not opportunity or not has_doctype("Opportunity") or not has_field("Opportunity", "custom_crm_business_type"):
        return "Unassigned"
    return normalize_business_type(frappe.db.get_value("Opportunity", opportunity, "custom_crm_business_type"))


def sales_order_business_type(row) -> str:
    if row.get("custom_crm_business_type"):
        return normalize_business_type(row.get("custom_crm_business_type"))
    project_name = row.get("custom_installation_project") or row.get("project")
    if project_name:
        return project_business_type(project_name)
    return "Distribution"


def purchase_order_project(po_name: str | None, direct_project: str | None = None) -> str:
    if direct_project:
        return direct_project
    if not po_name or not has_doctype("Purchase Order Item") or not has_field("Purchase Order Item", "project"):
        return ""
    rows = frappe.get_all(
        "Purchase Order Item",
        filters={"parent": po_name, "project": ["not in", ["", None]]},
        fields=["project"],
        limit_page_length=1,
    )
    return rows[0].get("project") if rows else ""


def summarize_currency_rows(amounts: list[dict]) -> str:
    if not amounts:
        return "0"
    return " · ".join(f"{row.get('currency') or ''} {flt(row.get('revenue') or row.get('amount') or 0):,.0f}" for row in amounts)


def _refresh_margin(row: dict) -> None:
    row["revenue"] = flt(row.get("revenue") or 0)
    row["charges"] = flt(row.get("charges") or 0)
    row["margin"] = row["revenue"] - row["charges"]
    row["margin_pct"] = margin_percent(row["revenue"], row["charges"])
