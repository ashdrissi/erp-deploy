from __future__ import annotations

import frappe


def business_type_abbreviation(type_name: str | None) -> str:
    return "".join(ch for ch in (type_name or "").strip().lower() if ch.isalnum())[:4] or "type"


def get_company_business_type_names(company: str | None) -> list[str]:
    company = (company or "").strip()
    if not company or not frappe.db.exists("Company", company):
        return []
    if not frappe.get_meta("Company").get_field("custom_crm_business_types"):
        return []
    rows = frappe.get_all(
        "Company Business Type",
        filters={"parenttype": "Company", "parent": company},
        fields=["business_type", "is_default", "idx"],
        order_by="is_default desc, idx asc",
        limit_page_length=0,
    )
    return [row.business_type for row in rows if row.get("business_type")]


def get_company_business_types(company: str | None) -> list[dict]:
    names = get_company_business_type_names(company)
    if not names:
        names = frappe.get_all(
            "CRM Business Type",
            filters={"is_active": 1},
            pluck="name",
            order_by="sequence asc, name asc",
            limit_page_length=0,
        )
    rows = []
    for name in names:
        if not frappe.db.exists("CRM Business Type", name):
            continue
        values = frappe.db.get_value("CRM Business Type", name, ["type_name", "abbreviation", "sequence"], as_dict=True) or {}
        rows.append(
            {
                "name": name,
                "type_name": values.get("type_name") or name,
                "abbreviation": values.get("abbreviation") or business_type_abbreviation(name),
                "sequence": values.get("sequence") or 100,
            }
        )
    return rows


def get_single_company_business_type(company: str | None) -> str:
    names = get_company_business_type_names(company)
    return names[0] if len(names) == 1 else ""


def is_business_type_allowed_for_company(company: str | None, business_type: str | None) -> bool:
    business_type = (business_type or "").strip()
    if not business_type:
        return True
    names = get_company_business_type_names(company)
    return not names or business_type in set(names)


@frappe.whitelist()
def get_company_business_type_payload(company: str | None = None) -> dict:
    rows = get_company_business_types(company)
    configured_names = get_company_business_type_names(company)
    return {
        "business_types": rows,
        "configured_business_types": configured_names,
        "single_business_type": rows[0]["name"] if len(configured_names) == 1 and rows else "",
    }
