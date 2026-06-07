from __future__ import annotations

import frappe
from frappe.utils import getdate, nowdate

from orderlift.orderlift_crm.company_business_type import (
    business_type_abbreviation,
    get_single_company_business_type,
    is_business_type_allowed_for_company,
)

DRAFT_TITLE = "Draft Opportunity"
DRAFT_PARTY_TYPE = "Prospect"
DRAFT_PARTY_NAME = "Draft Unassigned Prospect"


def assign_opportunity_name(doc, method=None) -> None:
    business_type = (doc.get("custom_crm_business_type") or get_single_company_business_type(doc.get("company")) or "").strip()
    if not business_type:
        return
    if doc.get("name") and _name_has_business_abbreviation(doc.name):
        return
    doc.name = _next_opportunity_name(business_type)


def apply_opportunity_defaults(doc, method=None) -> None:
    if not doc.get("opportunity_owner"):
        doc.opportunity_owner = frappe.session.user
    if doc.meta.get_field("custom_crm_business_type") and not doc.get("custom_crm_business_type"):
        doc.custom_crm_business_type = get_single_company_business_type(doc.get("company"))
    if doc.get("custom_crm_business_type") and not is_business_type_allowed_for_company(
        doc.get("company"), doc.get("custom_crm_business_type")
    ):
        frappe.throw(
            "Business Type {0} is not attributed to company {1}.".format(
                doc.get("custom_crm_business_type"), doc.get("company")
            )
        )
    if doc.meta.get_field("custom_tier") and not doc.get("custom_tier"):
        doc.custom_tier = _tier_for_opportunity_party(doc)


def _tier_for_opportunity_party(doc) -> str:
    party_type = (doc.get("opportunity_from") or "").strip()
    party_name = (doc.get("party_name") or "").strip()
    if party_type not in {"Customer", "Prospect"} or not party_name or not frappe.db.exists(party_type, party_name):
        return ""
    fields = [field for field in ["manual_tier", "tier"] if frappe.get_meta(party_type).get_field(field)]
    if not fields:
        return ""
    values = frappe.db.get_value(party_type, party_name, fields, as_dict=True) or {}
    return values.get("manual_tier") or values.get("tier") or ""


def _name_has_business_abbreviation(name: str) -> bool:
    parts = (name or "").split("-")
    return len(parts) >= 5 and parts[0] == "CRM" and parts[1] == "OPP" and parts[2].isdigit()


def _next_opportunity_name(business_type: str) -> str:
    year = getdate(nowdate()).year
    prefix = f"CRM-OPP-{year}-{business_type_abbreviation(business_type)}-"
    rows = frappe.get_all(
        "Opportunity",
        filters={"name": ["like", f"{prefix}%"]},
        pluck="name",
        limit_page_length=0,
    )
    max_suffix = 0
    for name in rows:
        suffix = (name or "").rsplit("-", 1)[-1]
        if suffix.isdigit():
            max_suffix = max(max_suffix, int(suffix))
    return f"{prefix}{max_suffix + 1:05d}"


def unlink_prospect_opportunity_rows(doc, method=None) -> None:
    if not is_auto_saved_draft_opportunity(doc):
        return
    cleanup_auto_saved_draft_links(doc)


def is_auto_saved_draft_opportunity(doc) -> bool:
    if not doc or not getattr(doc, "name", None):
        return False
    return (
        int(doc.get("docstatus") or 0) == 0
        and (doc.get("status") or "") == "Open"
        and (doc.get("title") or "") == DRAFT_TITLE
        and (doc.get("opportunity_from") or "") == DRAFT_PARTY_TYPE
        and (doc.get("party_name") or "") == DRAFT_PARTY_NAME
    )


def cleanup_auto_saved_draft_links(doc) -> None:
    if not frappe.db.exists("DocType", "Prospect Opportunity"):
        return
    frappe.db.delete("Prospect Opportunity", {"opportunity": doc.name})
    frappe.db.delete("ToDo", {"reference_type": "Opportunity", "reference_name": doc.name})
    frappe.db.delete("File", {"attached_to_doctype": "Opportunity", "attached_to_name": doc.name})
    frappe.db.delete("Comment", {"reference_doctype": "Opportunity", "reference_name": doc.name})
