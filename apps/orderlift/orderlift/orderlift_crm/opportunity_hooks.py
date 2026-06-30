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


def sync_opportunity_assignment_todo(doc, method=None) -> None:
    if not doc or not getattr(doc, "name", None):
        return
    assigned_user = (doc.get("opportunity_owner") or "").strip()
    if not assigned_user:
        return

    from orderlift.orderlift_crm.api import pipeline

    existing = pipeline._find_open_pipeline_todo("Opportunity", doc.name)
    if existing:
        return
    pipeline._assign_pipeline_document(
        "Opportunity",
        doc.name,
        assigned_user,
        doc.get("sales_stage") or None,
    )


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


def cleanup_opportunity_delete_links(doc, method=None) -> None:
    cleanup_prospect_opportunity_rows(doc)
    cleanup_partner_campaign_opportunity_links(doc)
    if not is_auto_saved_draft_opportunity(doc):
        return
    cleanup_auto_saved_draft_links(doc)


def unlink_prospect_opportunity_rows(doc, method=None) -> None:
    cleanup_opportunity_delete_links(doc, method=method)


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
    cleanup_prospect_opportunity_rows(doc)
    frappe.db.delete("ToDo", {"reference_type": "Opportunity", "reference_name": doc.name})
    frappe.db.delete("File", {"attached_to_doctype": "Opportunity", "attached_to_name": doc.name})
    frappe.db.delete("Comment", {"reference_doctype": "Opportunity", "reference_name": doc.name})


def cleanup_prospect_opportunity_rows(doc) -> None:
    if not doc or not getattr(doc, "name", None):
        return
    if not frappe.db.exists("DocType", "Prospect Opportunity"):
        return
    frappe.db.delete("Prospect Opportunity", {"opportunity": doc.name})


def cleanup_partner_campaign_opportunity_links(doc) -> None:
    if not doc or not getattr(doc, "name", None):
        return
    if not frappe.db.exists("DocType", "Partner Campaign Target"):
        return
    if not frappe.db.has_column("Partner Campaign Target", "opportunity"):
        return

    campaigns = frappe.get_all(
        "Partner Campaign Target",
        filters={"opportunity": doc.name},
        pluck="parent",
        limit_page_length=0,
    )
    frappe.db.sql(
        """
        UPDATE `tabPartner Campaign Target`
        SET opportunity = NULL
        WHERE opportunity = %s
        """,
        (doc.name,),
    )
    refresh_partner_campaign_opportunity_counts(campaigns)


def cleanup_quotation_delete_links(doc, method=None) -> None:
    cleanup_partner_campaign_quotation_links(doc)


def cleanup_partner_campaign_quotation_links(doc) -> None:
    if not doc or not getattr(doc, "name", None):
        return
    if not frappe.db.exists("DocType", "Partner Campaign Target"):
        return
    if not frappe.db.has_column("Partner Campaign Target", "quotation"):
        return

    campaigns = frappe.get_all(
        "Partner Campaign Target",
        filters={"quotation": doc.name},
        pluck="parent",
        limit_page_length=0,
    )
    frappe.db.sql(
        """
        UPDATE `tabPartner Campaign Target`
        SET quotation = NULL
        WHERE quotation = %s
        """,
        (doc.name,),
    )
    refresh_partner_campaign_quotation_rollups(campaigns)


def refresh_partner_campaign_opportunity_counts(campaigns) -> None:
    campaigns = sorted({campaign for campaign in campaigns or [] if campaign})
    if not campaigns or not frappe.db.exists("DocType", "Partner Campaign"):
        return
    if not frappe.db.has_column("Partner Campaign", "opportunity_count"):
        return
    for campaign in campaigns:
        count = frappe.db.count("Partner Campaign Target", {"parent": campaign, "opportunity": ["!=", ""]})
        frappe.db.set_value("Partner Campaign", campaign, "opportunity_count", count, update_modified=False)


def refresh_partner_campaign_quotation_rollups(campaigns) -> None:
    campaigns = sorted({campaign for campaign in campaigns or [] if campaign})
    if not campaigns or not frappe.db.exists("DocType", "Partner Campaign"):
        return
    has_count = frappe.db.has_column("Partner Campaign", "quotation_count")
    has_amount = frappe.db.has_column("Partner Campaign", "quotation_amount")
    if not (has_count or has_amount):
        return

    for campaign in campaigns:
        quotation_names = frappe.get_all(
            "Partner Campaign Target",
            filters={"parent": campaign, "quotation": ["!=", ""]},
            pluck="quotation",
            limit_page_length=0,
        )
        values = {}
        if has_count:
            values["quotation_count"] = len(set(quotation_names or []))
        if has_amount:
            values["quotation_amount"] = _sum_quotation_grand_total(quotation_names)
        if values:
            frappe.db.set_value("Partner Campaign", campaign, values, update_modified=False)


def _sum_quotation_grand_total(quotation_names) -> float:
    names = sorted({name for name in quotation_names or [] if name})
    if not names:
        return 0.0
    rows = frappe.get_all(
        "Quotation",
        filters={"name": ["in", names], "docstatus": ["<", 2]},
        fields=["grand_total"],
        limit_page_length=0,
    )
    return sum(float(row.get("grand_total") or 0) for row in rows)
