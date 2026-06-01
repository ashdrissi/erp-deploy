import frappe
from frappe import _
from frappe.utils import flt

from orderlift.client_portal.utils.access import (
    DEFAULT_CUSTOMER_GROUP,
    _customer_crm_segments,
    _get_policy_name,
    _primary_crm_segment,
    resolve_portal_price,
)


@frappe.whitelist(allow_guest=False)
def get_price(item_code, qty, customer, include_transport=False):
    qty = flt(qty or 0)
    if qty <= 0:
        frappe.throw(_("Quantity must be greater than zero."))
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} does not exist.").format(customer))

    customer_group, customer_company = frappe.db.get_value(
        "Customer", customer, ["customer_group", "custom_company"]
    ) or (None, None)
    customer_group = customer_group or DEFAULT_CUSTOMER_GROUP
    crm_context = _primary_crm_segment(_customer_crm_segments(customer))
    policy_name = _get_policy_name(
        customer_group,
        business_type=crm_context.get("business_type"),
        crm_segment=crm_context.get("crm_segment"),
        company=customer_company,
    )
    if not policy_name:
        frappe.throw(_("No active portal policy exists for this customer's CRM segment."))

    policy = frappe.get_doc("Portal Customer Group Policy", policy_name)
    price = resolve_portal_price(item_code, policy.portal_price_list)
    unit_price = flt(price.rate)
    return {
        "unit_price": unit_price,
        "total_price": unit_price * qty,
        "currency": price.currency or policy.currency or "MAD",
        "business_type": crm_context.get("business_type") or "",
        "crm_segment": crm_context.get("crm_segment") or "",
        "price_list": policy.portal_price_list,
        "transport_cost": 0,
    }
