import frappe
from frappe import _
from frappe.utils import flt

from orderlift.client_portal.utils.access import resolve_portal_price


@frappe.whitelist(allow_guest=False)
def get_price(item_code, qty, customer, include_transport=False):
    qty = flt(qty or 0)
    if qty <= 0:
        frappe.throw(_("Quantity must be greater than zero."))
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} does not exist.").format(customer))

    customer_group = frappe.db.get_value("Customer", customer, "customer_group")
    policy_name = frappe.db.get_value(
        "Portal Customer Group Policy",
        {"customer_group": customer_group, "enabled": 1},
        "name",
    )
    if not policy_name:
        frappe.throw(_("No active portal policy exists for customer group {0}.").format(customer_group))

    policy = frappe.get_doc("Portal Customer Group Policy", policy_name)
    price = resolve_portal_price(item_code, policy.portal_price_list)
    unit_price = flt(price.rate)
    return {
        "unit_price": unit_price,
        "total_price": unit_price * qty,
        "currency": price.currency or policy.currency or "MAD",
        "customer_group": customer_group,
        "price_list": policy.portal_price_list,
        "transport_cost": 0,
    }
