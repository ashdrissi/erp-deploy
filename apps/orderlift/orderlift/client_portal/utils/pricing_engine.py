"""
Pricing Engine
--------------
Computes the dynamic price for a B2B portal quote line.

Price = f(item base price, client geographic zone, quantity, transport flag)

Exposed as a whitelisted API endpoint so the portal frontend
can call it via AJAX without a page reload.
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_price(item_code, qty, customer, include_transport=False):
    """
    Return the computed unit price for a portal quote line.

    Args:
        item_code (str): ERPNext Item code.
        qty (float): Requested quantity.
        customer (str): ERPNext Customer name (used to resolve pricing zone).
        include_transport (bool): Whether to add local transport cost.

    Returns:
        dict: {unit_price, total_price, currency, zone, transport_cost}
    """
    # Placeholder — full pricing logic implemented in Module 6 (B2B Portal)
    return {
        "unit_price": 0,
        "total_price": 0,
        "currency": "MAD",
        "zone": None,
        "transport_cost": 0,
    }
