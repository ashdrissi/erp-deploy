"""
Jinja Helpers
-------------
Custom Jinja2 filters and functions available in all Print Format
templates and web templates.

Registered in hooks.py under the `jinja` key.
"""

import frappe
from frappe.utils import flt

from orderlift.orderlift_sales.utils.tax_inclusive import quote_item_inclusive_totals


def format_currency_fr(amount, currency=None):
    """
    Format a number as a French-style currency string.
    e.g. 12345.6 → "12 345,60 MAD"
    """
    try:
        amount = float(amount or 0)
        # French number formatting: space as thousands sep, comma as decimal
        formatted = "{:,.2f}".format(amount).replace(",", " ").replace(".", ",")
        return f"{formatted} {currency or frappe.defaults.get_global_default('currency')}"
    except (ValueError, TypeError):
        return f"0,00 {currency or frappe.defaults.get_global_default('currency')}"


def get_quotation_ttc_print_context(doc):
    return get_ttc_print_context(doc)


def get_customer_tax_id(doc):
    """Return the document snapshot, with a master-data fallback for older documents."""
    for fieldname in ("custom_customer_tax_id", "tax_id"):
        value = (doc.get(fieldname) or "").strip()
        if value:
            return value

    quotation_to = (doc.get("quotation_to") or "").strip()
    customer = (doc.get("customer") or "").strip()
    if quotation_to == "Customer":
        customer = (doc.get("party_name") or "").strip()
    if not customer:
        return ""
    return frappe.db.get_value("Customer", customer, "tax_id") or ""


def get_ttc_print_context(doc):
    """Return row and total values for TTC print formats.
    Works for any document with items and taxes child tables."""
    return _build_ttc_print_context(doc)


def _build_ttc_print_context(doc):
    items = list(getattr(doc, "items", None) or [])
    rows_by_name = {}
    rows_by_idx = {}
    row_tax_total = 0.0

    has_template = bool((getattr(doc, "taxes_and_charges", "") or "").strip())

    if has_template and doc.get("taxes"):
        inclusive_totals = quote_item_inclusive_totals(doc)
        for index, row in enumerate(items):
            totals = inclusive_totals[index] if index < len(inclusive_totals) else {}
            tax_amount = flt(totals.get("tax_amount") or _row_value(row, "custom_applied_taxes"))
            unit_ttc = flt(totals.get("unit_incl_tax") or _row_value(row, "custom_pu_ttc") or _row_value(row, "rate"))
            total_ttc = flt(totals.get("total_incl_tax") or _row_value(row, "custom_pt_ttc") or _row_value(row, "amount"))
            row_payload = {"tax": tax_amount, "unit": unit_ttc, "total": total_ttc}
            row_name = (_row_value(row, "name", "") or "").strip()
            if row_name:
                rows_by_name[row_name] = row_payload
            rows_by_idx[str(_row_value(row, "idx", index + 1) or index + 1)] = row_payload
            row_tax_total += tax_amount
    else:
        for index, row in enumerate(items):
            rate = flt(_row_value(row, "rate"))
            qty = flt(_row_value(row, "qty") or 1) or 1
            unit_ttc = rate
            total_ttc = rate * qty
            row_payload = {"tax": 0.0, "unit": unit_ttc, "total": total_ttc}
            row_name = (_row_value(row, "name", "") or "").strip()
            if row_name:
                rows_by_name[row_name] = row_payload
            rows_by_idx[str(_row_value(row, "idx", index + 1) or index + 1)] = row_payload

    total_ht = flt(getattr(doc, "net_total", None) or getattr(doc, "total", None) or 0)
    total_tax = flt(getattr(doc, "total_taxes_and_charges", None) or row_tax_total)
    total_ttc = flt(getattr(doc, "grand_total", None) or total_ht + total_tax)

    if not has_template:
        total_tax = 0.0
        total_ttc = total_ht

    if not total_tax and total_ttc != total_ht:
        total_tax = flt(total_ttc - total_ht)

    return {
        "rows_by_name": rows_by_name,
        "rows_by_idx": rows_by_idx,
        "total_ht": total_ht,
        "total_tax": total_tax,
        "total_ttc": total_ttc or total_ht,
    }


_DOC_PRINT_TITLES = {
    "Sales Order": "BON DE COMMANDE",
    "Delivery Note": "BON DE LIVRAISON",
    "Sales Invoice": "FACTURE DE VENTE",
    "Purchase Order": "BON DE COMMANDE FOURNISSEUR",
    "Purchase Invoice": "FACTURE D'ACHAT",
    "Purchase Receipt": "RECEPTION DE MARCHANDISE",
    "Supplier Quotation": "DEVIS FOURNISSEUR",
}


def get_doc_print_title(doctype):
    return _DOC_PRINT_TITLES.get(doctype, doctype)


def get_print_payment_terms(doc):
    """Return concise, intentional commercial payment terms for print formats."""
    rows = list(getattr(doc, "payment_schedule", None) or [])
    template = (getattr(doc, "payment_terms_template", "") or "").strip()
    if rows and not template:
        has_explicit_terms = any(
            (_row_value(row, "payment_term") or "").strip()
            or (_row_value(row, "description") or "").strip()
            or (_row_value(row, "mode_of_payment") or "").strip()
            for row in rows
        )
        if not has_explicit_terms:
            # ERPNext creates an unlabeled 100% row even when no commercial
            # payment agreement was selected. Do not present that fallback as
            # an agreed customer condition.
            return []

    lines = []
    for row in rows:
        label = _row_value(row, "payment_term") or _row_value(row, "description") or ""
        portion = flt(_row_value(row, "invoice_portion"))
        mode_of_payment = (_row_value(row, "mode_of_payment") or "").strip()
        parts = []
        if label:
            parts.append(str(label))
        if portion:
            parts.append(f"{portion:g}%")
        if mode_of_payment:
            parts.append(f"{frappe._('Mode of Payment')}: {mode_of_payment}")
        if parts:
            lines.append(" - ".join(parts))

    if lines:
        return lines

    return [template] if template else []


def get_print_trade_terms(doc):
    """Return a compact Incoterms/trade-terms line when document fields exist."""
    incoterm = (getattr(doc, "incoterm", "") or "").strip()
    if not incoterm:
        return ""

    place = ""
    for fieldname in ("named_place", "incoterm_location", "custom_incoterm_location", "place_of_supply"):
        value = (getattr(doc, fieldname, "") or "").strip()
        if value:
            place = value
            break
    return f"{incoterm} - {place}" if place else incoterm


def _row_value(row, fieldname, default=None):
    getter = getattr(row, "get", None)
    if callable(getter):
        value = getter(fieldname)
    else:
        value = getattr(row, fieldname, None)
    return default if value is None else value


def get_company_info(company_name):
    """
    Return a dict of company contact fields for use in print format headers.
    Returns empty strings for any missing fields so templates stay clean.
    """
    fields = ["company_name", "phone_no", "email", "website", "tax_id", "default_currency", "country"]
    data = frappe.db.get_value("Company", company_name, fields, as_dict=True) or {}
    return {
        "company_name": data.get("company_name") or company_name or "",
        "phone": data.get("phone_no") or "",
        "email": data.get("email") or "",
        "website": data.get("website") or "",
        "tax_id": data.get("tax_id") or "",
        "currency": data.get("default_currency") or frappe.defaults.get_global_default("currency"),
        "country": data.get("country") or "",
    }


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
