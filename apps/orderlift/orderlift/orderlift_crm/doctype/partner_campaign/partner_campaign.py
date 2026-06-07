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
        action_type = self.get("campaign_action_type") or self.default_channel or "WhatsApp"
        if self.default_channel in {"Visit", "Other"} and not self.get("campaign_action_type"):
            action_type = self.default_channel
        if self.meta.get_field("campaign_action_type"):
            self.campaign_action_type = action_type
        if action_type in {"Email", "WhatsApp", "Call"}:
            self.default_channel = action_type
        elif action_type in {"Visit", "Other"}:
            self.default_channel = ""
        if not self.whatsapp_mode:
            self.whatsapp_mode = "Manual Click-to-Chat"
        elif self.whatsapp_mode == "Automated API":
            self.whatsapp_mode = "Custom Webhook"
        if not self.whatsapp_template_language:
            self.whatsapp_template_language = "fr"
        if not (self.visit_subject or "").strip() and (self.visit_email_subject or "").strip():
            self.visit_subject = self.visit_email_subject
        if not (self.visit_agenda or "").strip():
            self.visit_agenda = _first_text(
                self.visit_call_script,
                self.visit_whatsapp_text,
                self.visit_email_body,
            )

    def _sync_target_snapshots(self):
        for row in self.targets or []:
            if not row.party_type or not row.party_name:
                continue
            snapshot = resolve_party_snapshot(row.party_type, row.party_name)
            row.display_name = row.display_name or snapshot.get("display_name")
            row.city = row.city or snapshot.get("city")
            row.contact = row.contact or snapshot.get("contact")
            row.contact_person_name = row.contact_person_name or snapshot.get("contact_person_name")
            row.email = row.email or snapshot.get("email")
            row.mobile_no = row.mobile_no or snapshot.get("mobile_no")
            row.business_type = row.business_type or snapshot.get("business_type")
            row.crm_segment = row.crm_segment or snapshot.get("crm_segment")
            row.partner_segment = row.partner_segment or snapshot.get("partner_segment")
            row.last_contact_date = clean_date_value(row.last_contact_date)
            row.last_outreach_date = clean_date_value(row.last_outreach_date)
            row.visit_date = clean_date_value(row.visit_date)
            row.last_order_date = clean_date_value(row.last_order_date) or clean_date_value(snapshot.get("last_order_date"))

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
            ["lead_name", "company_name", "city", "custom_partner_segment", "email_id", "mobile_no", "phone"],
            as_dict=True,
        ) or {}
        contact = _linked_contact_snapshot("Lead", party_name)
        return {
            "display_name": row.get("company_name") or row.get("lead_name") or party_name,
            "city": row.get("city"),
            "partner_segment": row.get("custom_partner_segment"),
            "contact": contact.get("contact"),
            "contact_person_name": contact.get("contact_person_name") or row.get("lead_name"),
            "email": row.get("email_id") or contact.get("email"),
            "mobile_no": row.get("mobile_no") or row.get("phone") or contact.get("mobile_no"),
            **_party_primary_crm_segment("Lead", party_name, row.get("custom_partner_segment")),
        }

    if party_type == "Prospect":
        row = frappe.db.get_value(
            "Prospect",
            party_name,
            ["company_name", "territory", "custom_partner_segment"],
            as_dict=True,
        ) or {}
        contact = _linked_contact_snapshot("Prospect", party_name)
        return {
            "display_name": row.get("company_name") or party_name,
            "city": row.get("territory"),
            "partner_segment": row.get("custom_partner_segment"),
            "contact": contact.get("contact"),
            "contact_person_name": contact.get("contact_person_name"),
            "email": contact.get("email"),
            "mobile_no": contact.get("mobile_no"),
            **_party_primary_crm_segment("Prospect", party_name),
        }

    if party_type == "Customer":
        row = frappe.db.get_value(
            "Customer",
            party_name,
            ["customer_name", "territory", "custom_partner_segment", "customer_primary_contact"],
            as_dict=True,
        ) or {}
        contact = _contact_snapshot(row.get("customer_primary_contact")) or _linked_contact_snapshot("Customer", party_name)
        return {
            "display_name": row.get("customer_name") or party_name,
            "city": row.get("territory"),
            "partner_segment": row.get("custom_partner_segment"),
            "contact": contact.get("contact"),
            "contact_person_name": contact.get("contact_person_name"),
            "email": contact.get("email"),
            "mobile_no": contact.get("mobile_no"),
            "last_order_date": _last_sales_order_date(party_name),
            **_party_primary_crm_segment("Customer", party_name),
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


def clean_date_value(value):
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value
    clean = str(value).strip()
    if clean in {"", "-", "--", "—", "None", "none", "NULL", "null"}:
        return None
    return clean


def _first_text(*values: str | None) -> str:
    for value in values:
        clean = (value or "").strip()
        if clean:
            return clean
    return ""


def _linked_contact_snapshot(party_type: str, party_name: str) -> dict:
    if not party_type or not party_name or not frappe.db.exists("DocType", "Dynamic Link"):
        return {}
    contacts = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Contact", "link_doctype": party_type, "link_name": party_name},
        pluck="parent",
        limit_page_length=1,
    )
    return _contact_snapshot(contacts[0]) if contacts else {}


def _contact_snapshot(contact: str | None) -> dict:
    if not contact or not frappe.db.exists("Contact", contact):
        return {}
    row = frappe.db.get_value(
        "Contact",
        contact,
        ["first_name", "last_name", "email_id", "mobile_no", "phone"],
        as_dict=True,
    ) or {}
    contact_name = " ".join([part for part in [row.get("first_name"), row.get("last_name")] if part]).strip()
    return {
        "contact": contact,
        "contact_person_name": contact_name or contact,
        "email": row.get("email_id"),
        "mobile_no": row.get("mobile_no") or row.get("phone"),
    }


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
    return {"business_type": None, "crm_segment": None}


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
