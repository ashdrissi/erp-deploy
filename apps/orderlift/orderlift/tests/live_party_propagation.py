from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from orderlift.orderlift_crm.api.pipeline import _customer_for_opportunity_party, prepare_quotation_from_opportunity


def run() -> dict:
    return _run_source("Lead")


def run_prospect() -> dict:
    return _run_source("Prospect")


def run_customer_address() -> dict:
    stamp = now_datetime().strftime("%Y%m%d%H%M%S")
    try:
        customer = frappe.new_doc("Customer")
        customer.customer_name = f"OL Address Test {stamp}"
        customer.customer_type = "Individual"
        customer.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
        customer.custom_company = "Orderlift Maroc Distribution"
        customer.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or ""
        customer.append(
            "custom_crm_segments",
            {"business_type": "Distribution", "segment": "Grossiste", "is_primary": 1},
        )
        customer.insert(ignore_permissions=True)

        address = frappe.new_doc("Address")
        address.address_title = f"OL Customer Address {stamp}"
        address.address_type = "Billing"
        address.address_line1 = "3 Test Customer Street"
        address.city = "Casablanca"
        address.country = "Morocco"
        address.append("links", {"link_doctype": "Customer", "link_name": customer.name})
        address.insert(ignore_permissions=True)

        customer.reload()
        result = {
            "customer": customer.name,
            "address": address.name,
            "customer_primary_address": customer.customer_primary_address,
            "primary_address_display": customer.primary_address,
            "address_is_primary": frappe.db.get_value("Address", address.name, "is_primary_address"),
        }
        assert result["customer_primary_address"] == address.name
        assert result["primary_address_display"]
        assert result["address_is_primary"]
        return result
    finally:
        frappe.db.rollback()


def _run_source(source_type: str) -> dict:
    stamp = now_datetime().strftime("%Y%m%d%H%M%S")
    created = {}
    try:
        company = "Orderlift Maroc Distribution" if source_type == "Lead" else "Orderlift Maroc Installation"
        owner = frappe.db.get_value("Sales Person", {"enabled": 1, "user": ["!=", ""]}, "user") or "Administrator"
        source = _create_source(source_type, stamp, company, owner)
        created[source_type.lower()] = source.name
        contact = _create_contact(stamp, source_type, source.name)
        created["contact"] = contact.name
        billing = _create_address(stamp, source_type, source.name, "Billing", "1 Test Billing Street")
        created["billing"] = billing.name
        shipping = _create_address(stamp, source_type, source.name, "Shipping", "2 Test Shipping Street")
        created["shipping"] = shipping.name
        opportunity = _create_opportunity(source_type, source, company, owner)
        created["opportunity"] = opportunity.name

        customer = _customer_for_opportunity_party(opportunity)
        created["customer"] = customer.name
        mapped = prepare_quotation_from_opportunity(opportunity.name)
        result = {
            "created": created,
            "account_manager": customer.account_manager,
            "sales_team": [(row.sales_person, row.allocated_percentage) for row in customer.sales_team],
            "lineage": [customer.lead_name, customer.prospect_name, customer.opportunity_name],
            "primary_contact": customer.customer_primary_contact,
            "primary_address": customer.customer_primary_address,
            "contact_links": frappe.get_all(
                "Dynamic Link",
                filters={"parenttype": "Contact", "parent": contact.name},
                fields=["link_doctype", "link_name"],
            ),
            "billing_links": frappe.get_all(
                "Dynamic Link",
                filters={"parenttype": "Address", "parent": billing.name},
                fields=["link_doctype", "link_name"],
            ),
            "quotation_party": [mapped.quotation_to, mapped.party_name, mapped.opportunity],
            "quotation_contact": mapped.contact_person,
            "quotation_addresses": [mapped.customer_address, mapped.shipping_address_name],
        }
        _assert_result(result, source_type, owner, contact.name, billing.name, shipping.name, opportunity.name)
        return result
    finally:
        frappe.db.rollback()


def _create_source(source_type: str, stamp: str, company: str, owner: str):
    if source_type == "Prospect":
        prospect = frappe.new_doc("Prospect")
        prospect.company_name = f"OL Test Company {stamp}"
        prospect.prospect_owner = owner
        prospect.company = company
        prospect.industry = frappe.db.get_value("Industry Type", {}, "name") or ""
        prospect.website = "https://example.test"
        prospect.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or ""
        if prospect.meta.get_field("custom_crm_segments"):
            prospect.append(
                "custom_crm_segments",
                {"business_type": "Installation", "segment": "Individu", "is_primary": 1},
            )
        prospect.insert(ignore_permissions=True)
        return prospect

    lead = frappe.new_doc("Lead")
    lead.first_name = f"OL Test {stamp}"
    lead.lead_name = f"OL Test {stamp}"
    lead.company_name = f"OL Test Company {stamp}"
    lead.lead_owner = owner
    if lead.meta.get_field("company"):
        lead.company = company
    lead.industry = frappe.db.get_value("Industry Type", {}, "name") or ""
    lead.website = "https://example.test"
    lead.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or ""
    if lead.meta.get_field("language"):
        lead.language = "en"
    if lead.meta.get_field("custom_crm_segments"):
        lead.append(
            "custom_crm_segments",
            {"business_type": "Distribution", "segment": "Grossiste", "is_primary": 1},
        )
    lead.insert(ignore_permissions=True)
    return lead


def _create_contact(stamp: str, source_type: str, source_name: str):
    contact = frappe.new_doc("Contact")
    contact.first_name = "OL Test Contact"
    contact.email_id = f"ol-test-{stamp}@example.test"
    contact.mobile_no = "+212600000000"
    contact.is_primary_contact = 1
    contact.append("links", {"link_doctype": source_type, "link_name": source_name})
    contact.insert(ignore_permissions=True)
    return contact


def _create_address(stamp: str, source_type: str, source_name: str, address_type: str, address_line1: str):
    address = frappe.new_doc("Address")
    address.address_title = f"OL {address_type} {stamp}"
    address.address_type = address_type
    address.address_line1 = address_line1
    address.city = "Casablanca"
    address.country = "Morocco"
    address.is_primary_address = int(address_type == "Billing")
    address.is_shipping_address = int(address_type == "Shipping")
    address.append("links", {"link_doctype": source_type, "link_name": source_name})
    address.insert(ignore_permissions=True)
    return address


def _create_opportunity(source_type: str, source, company: str, owner: str):
    opportunity = frappe.new_doc("Opportunity")
    opportunity.opportunity_from = source_type
    opportunity.party_name = source.name
    opportunity.customer_name = source.company_name
    opportunity.company = company
    opportunity.opportunity_owner = owner
    opportunity.status = "Open"
    opportunity.opportunity_type = frappe.db.get_value("Opportunity Type", {}, "name") or "Sales"
    opportunity.custom_crm_business_type = "Distribution" if source_type == "Lead" else "Installation"
    opportunity.custom_crm_segment = "Grossiste" if source_type == "Lead" else "Individu"
    opportunity.insert(ignore_permissions=True)
    return opportunity


def _assert_result(result, source_type, owner, contact, billing, shipping, opportunity) -> None:
    assert result["account_manager"] == owner
    assert result["lineage"][0 if source_type == "Lead" else 1]
    assert result["lineage"][2] == opportunity
    assert result["primary_contact"] == contact, result
    assert result["primary_address"] == billing
    assert result["quotation_party"][0] == "Customer"
    assert result["quotation_party"][2] == opportunity
    assert result["quotation_contact"] == contact
    assert result["quotation_addresses"] == [billing, shipping]
