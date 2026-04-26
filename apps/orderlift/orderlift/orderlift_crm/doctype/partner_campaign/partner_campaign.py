from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class PartnerCampaign(Document):
    def validate(self):
        self._set_defaults()
        self._sync_target_snapshots()
        self._sync_kpis()

    def _set_defaults(self):
        if not self.campaign_date:
            self.campaign_date = today()
        if not self.sales_history_to_date:
            self.sales_history_to_date = self.campaign_date
        if not self.status:
            self.status = "Draft"

    def _sync_target_snapshots(self):
        for row in self.targets or []:
            if not row.party_type or not row.party_name:
                continue
            snapshot = resolve_party_snapshot(row.party_type, row.party_name)
            row.display_name = row.display_name or snapshot.get("display_name")
            row.city = row.city or snapshot.get("city")
            row.business_type = row.business_type or snapshot.get("business_type")
            row.crm_segment = row.crm_segment or snapshot.get("crm_segment")
            row.partner_segment = row.partner_segment or snapshot.get("partner_segment")
            row.last_order_date = row.last_order_date or snapshot.get("last_order_date")

            if not row.target_status:
                row.target_status = get_default_target_status()

    def _sync_kpis(self):
        quotation_names = {row.quotation for row in self.targets or [] if row.quotation}
        sales_order_names = {row.sales_order for row in self.targets or [] if row.sales_order}

        self.opportunity_count = len({row.opportunity for row in self.targets or [] if row.opportunity})
        self.quotation_count = len(quotation_names)
        self.sales_order_count = len(sales_order_names)
        self.quotation_amount = _sum_grand_total("Quotation", quotation_names)
        self.sales_order_amount = _sum_grand_total("Sales Order", sales_order_names)


def resolve_party_snapshot(party_type: str, party_name: str) -> dict:
    if not party_type or not party_name or not frappe.db.exists(party_type, party_name):
        return {}

    if party_type == "Lead":
        row = frappe.db.get_value(
            "Lead",
            party_name,
            ["lead_name", "company_name", "city", "custom_partner_segment"],
            as_dict=True,
        ) or {}
        return {
            "display_name": row.get("company_name") or row.get("lead_name") or party_name,
            "city": row.get("city"),
            "partner_segment": row.get("custom_partner_segment"),
            **_party_primary_crm_segment("Lead", party_name, row.get("custom_partner_segment")),
        }

    if party_type == "Prospect":
        row = frappe.db.get_value(
            "Prospect",
            party_name,
            ["company_name", "territory", "customer_group", "custom_partner_segment"],
            as_dict=True,
        ) or {}
        return {
            "display_name": row.get("company_name") or party_name,
            "city": row.get("territory"),
            "partner_segment": row.get("custom_partner_segment") or row.get("customer_group"),
            **_party_primary_crm_segment("Prospect", party_name, row.get("custom_partner_segment")),
        }

    if party_type == "Customer":
        row = frappe.db.get_value(
            "Customer",
            party_name,
            ["customer_name", "territory", "customer_group", "custom_partner_segment"],
            as_dict=True,
        ) or {}
        return {
            "display_name": row.get("customer_name") or party_name,
            "city": row.get("territory"),
            "partner_segment": row.get("custom_partner_segment") or row.get("customer_group"),
            "last_order_date": _last_sales_order_date(party_name),
            **_party_primary_crm_segment("Customer", party_name, row.get("custom_partner_segment")),
        }

    return {}


def get_default_target_status() -> str | None:
    default_status = frappe.db.get_value("Partner Campaign Status", {"is_default": 1, "is_active": 1}, "name")
    if default_status:
        return default_status
    return frappe.db.get_value("Partner Campaign Status", {"is_active": 1}, "name", order_by="sequence asc")


def _sum_grand_total(doctype: str, names: set[str]) -> float:
    if not names:
        return 0.0
    rows = frappe.get_all(doctype, filters={"name": ["in", list(names)]}, fields=["grand_total"])
    return flt(sum(flt(row.get("grand_total")) for row in rows))


def _last_sales_order_date(customer: str) -> str | None:
    if not customer:
        return None
    return frappe.db.get_value(
        "Sales Order",
        {"customer": customer, "docstatus": ["<", 2]},
        "transaction_date",
        order_by="transaction_date desc",
    )


def validate_target_status(status: str | None) -> str | None:
    if not status:
        return get_default_target_status()
    if not frappe.db.exists("Partner Campaign Status", status):
        frappe.throw(_("Unknown partner campaign status: {0}").format(status))
    return status


def _party_primary_crm_segment(doctype: str, name: str, fallback_segment: str | None = None) -> dict:
    if frappe.db.exists("DocType", "CRM Segment Assignment"):
        row = frappe.get_all(
            "CRM Segment Assignment",
            filters={"parenttype": doctype, "parent": name},
            fields=["business_type", "segment", "is_primary"],
            order_by="is_primary desc, idx asc",
            limit=1,
        )
        if row:
            return {"business_type": row[0].business_type, "crm_segment": row[0].segment}
    business_type, crm_segment = _resolve_legacy_segment(fallback_segment)
    return {"business_type": business_type, "crm_segment": crm_segment}


def _resolve_legacy_segment(segment: str | None) -> tuple[str | None, str | None]:
    if not segment:
        return None, None
    legacy_map = {
        "Grossiste": ("Distribution", "Grossiste"),
        "Distributeur": ("Distribution", "Grossiste"),
        "Revendeur": ("Distribution", "Revendeur"),
        "Installateur": ("Distribution", "Installateur"),
        "Promoteur": ("Installation", "Promoteur"),
        "Particulier": ("Installation", "Individu"),
        "Individu": ("Installation", "Individu"),
    }
    mapped = legacy_map.get(segment)
    if mapped:
        return mapped
    if frappe.db.exists("CRM Segment", segment):
        return frappe.db.get_value("CRM Segment", segment, "business_type"), segment
    return None, None
