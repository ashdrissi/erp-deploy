"""
Jinja Helpers
-------------
Custom Jinja2 filters and functions available in all Print Format
templates and web templates.

Registered in hooks.py under the `jinja` key.
"""

import frappe


def format_currency_fr(amount, currency="MAD"):
    """
    Format a number as a French-style currency string.
    e.g. 12345.6 → "12 345,60 MAD"
    """
    try:
        amount = float(amount or 0)
        # French number formatting: space as thousands sep, comma as decimal
        formatted = "{:,.2f}".format(amount).replace(",", " ").replace(".", ",")
        return f"{formatted} {currency}"
    except (ValueError, TypeError):
        return f"0,00 {currency}"


def get_company_address(company_name):
    """
    Return the primary address of a company as a formatted string.
    Used in PDF print format headers.

    Frappe addresses use a Dynamic Link child table, so we query
    via the `Dynamic Link` doctype to find the address record.
    """
    address_links = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Address",
            "link_doctype": "Company",
            "link_name": company_name,
        },
        fields=["parent"],
    )

    if not address_links:
        return ""

    # Prefer the primary address; fall back to the first one found
    address_name = None
    for link in address_links:
        is_primary = frappe.db.get_value("Address", link.parent, "is_primary_address")
        if is_primary:
            address_name = link.parent
            break

    if not address_name:
        address_name = address_links[0].parent

    address = frappe.get_doc("Address", address_name)
    parts = filter(None, [
        address.address_line1,
        address.address_line2,
        address.city,
        address.country,
    ])
    return ", ".join(parts)
