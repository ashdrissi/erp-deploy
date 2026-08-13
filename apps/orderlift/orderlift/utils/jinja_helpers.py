"""
Jinja Helpers
-------------
Custom Jinja2 filters and functions available in all Print Format
templates and web templates.

Registered in hooks.py under the `jinja` key.
"""

from html import unescape
import json
import re

import frappe
from frappe.utils import flt

from orderlift.orderlift_sales.utils.tax_inclusive import quote_item_inclusive_totals


MOROCCO_PRINT_COMPANIES = {
    "Orderlift Maroc Distribution",
    "Orderlift Maroc Installation",
}
MOROCCO_PRINT_LEGAL_DETAILS = {
    "legal_name": "ORDER LIFT MOROCCO",
    "legal_address": "Tanja Balia lots méditerrané 475 rue plage Essalam Nr 15 Tanger, Maroc",
    "bank_line": (
        "Attijariwafa Banque - Agence : D.A.M Tanger Tarik Ibn Ziad - "
        "RIB : 007 640 0001735000002530 41"
    ),
    "registration_number": "162443",
    "tax_id": "003698266000073",
    "email": "info@orderlift.net",
}
PHONE_ADDRESS_LABELS = {
    "phone",
    "phone number",
    "mobile",
    "gsm",
    "tel",
    "telephone",
    "téléphone",
}
EMAIL_ADDRESS_LABELS = {"email", "e-mail", "courriel"}


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


def get_commercial_print_context(doc, force_without_details=False):
    """Return print-only rows without changing the transaction's detailed items."""
    items = list(doc.get("items") or []) if hasattr(doc, "get") else list(getattr(doc, "items", None) or [])
    mode = str(doc.get("custom_presentation_mode") or "With details").strip()
    without_details = bool(force_without_details) or mode == "Without details"
    if not without_details:
        return frappe._dict({"items": items, "without_details": False})

    included = [row for row in items if row.get("custom_presentation_role") != "Print separately"]
    separate = [row for row in items if row.get("custom_presentation_role") == "Print separately"]
    if not included:
        return frappe._dict({"items": separate, "without_details": True})

    ttc = _build_ttc_print_context(doc)
    amount_ht = sum(
        flt(row.get("net_amount") if row.get("net_amount") is not None else row.get("amount"))
        for row in included
    )
    amount_ttc = 0.0
    for row in included:
        row_ttc = ttc["rows_by_name"].get(row.name) or ttc["rows_by_idx"].get(str(row.idx or "")) or {}
        amount_ttc += flt(row_ttc.get("total") or row.get("custom_pt_ttc") or row.get("amount"))

    designation = (
        doc.get("custom_commercial_designation")
        or _commercial_presentation_summary_title(doc)
        or "Commercial summary"
    ).strip()
    raw_commercial_qty = flt(doc.get("custom_dimensioning_multiplier") or 1)
    commercial_qty = raw_commercial_qty if raw_commercial_qty > 0 and raw_commercial_qty == int(raw_commercial_qty) else 1
    summary = frappe._dict(
        {
            "name": "__commercial_summary__",
            "idx": 1,
            "item_code": "",
            "item_name": designation,
            "description": "",
            "uom": "Set",
            "stock_uom": "Set",
            "qty": commercial_qty,
            "rate": amount_ht / commercial_qty,
            "amount": amount_ht,
            "net_rate": amount_ht / commercial_qty,
            "net_amount": amount_ht,
            "custom_pu_ttc": amount_ttc / commercial_qty,
            "custom_pt_ttc": amount_ttc,
            "custom_is_commercial_summary": 1,
        }
    )
    return frappe._dict({"items": [summary, *separate], "without_details": True})


def get_quotation_detail_print_context(doc):
    """Return frozen dynamic quotation-detail pages for print formats."""
    from orderlift.quotation_detail_templates import build_print_context

    if str(doc.get("custom_presentation_mode") or "").strip() != "Without details":
        return {"enabled": False, "template": "", "template_name": "", "blocks": []}
    return build_print_context(doc)


def _commercial_presentation_summary_title(doc) -> str:
    raw = (doc.get("custom_commercial_presentation_snapshot") or "").strip()
    if not raw:
        return ""
    try:
        snapshot = json.loads(raw)
    except Exception:
        return ""
    for block in snapshot.get("blocks") or []:
        if block.get("type") == "Heading" and (block.get("value") or "").strip():
            return (block.get("value") or "").strip()
    return (snapshot.get("template_name") or "").strip()


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


def get_sales_print_context(doc):
    """Resolve commercial print metadata without requiring an Opportunity link.

    Opportunity data is preferred. Direct Quotations/Sales Orders fall back to
    the document owner for the salesperson identity and leave the subject empty.
    """
    source = _sales_print_source(doc)
    opportunity = source.get("opportunity") or ""
    opportunity_values = {}
    if opportunity:
        opportunity_values = (
            frappe.db.get_value(
                "Opportunity",
                opportunity,
                ["title", "opportunity_owner", "owner"],
                as_dict=True,
            )
            or {}
        )

    subject = (
        source.get("custom_opportunity_title")
        or opportunity_values.get("title")
        or ""
    ).strip()
    salesperson_user = (
        source.get("custom_opportunity_owner")
        or opportunity_values.get("opportunity_owner")
        or opportunity_values.get("owner")
        or _row_value(doc, "owner", "")
        or ""
    ).strip()

    user_values = {}
    if salesperson_user:
        user_values = (
            frappe.db.get_value(
                "User",
                salesperson_user,
                ["full_name", "email", "phone", "mobile_no"],
                as_dict=True,
            )
            or {}
        )

    employee_values = {}
    if salesperson_user and not (
        user_values.get("phone")
        or user_values.get("mobile_no")
        or user_values.get("email")
    ):
        employee_values = (
            frappe.db.get_value(
                "Employee",
                {"user_id": salesperson_user, "status": "Active"},
                ["employee_name", "cell_number", "company_email", "personal_email"],
                as_dict=True,
            )
            or {}
        )

    return frappe._dict(
        {
            "subject": subject,
            "opportunity": opportunity,
            "salesperson_user": salesperson_user,
            "salesperson_name": (
                user_values.get("full_name")
                or employee_values.get("employee_name")
                or salesperson_user
            ),
            "salesperson_phone": (
                user_values.get("mobile_no")
                or user_values.get("phone")
                or employee_values.get("cell_number")
                or ""
            ),
            "salesperson_email": (
                user_values.get("email")
                or employee_values.get("company_email")
                or employee_values.get("personal_email")
                or (salesperson_user if "@" in salesperson_user else "")
            ),
            "valid_till": _row_value(doc, "valid_till", ""),
            "delivery_lead_time": (
                _row_value(doc, "custom_delivery_lead_time", "")
                or source.get("custom_delivery_lead_time")
                or ""
            ).strip(),
        }
    )


def get_compact_party_print_context(doc):
    """Return compact address and contact data from ERPNext's HTML snapshot."""
    raw_address = str(_row_value(doc, "address_display", "") or "")
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", raw_address)
    normalized = re.sub(r"(?i)</(?:p|div|li)\s*>", "\n", normalized)
    normalized = re.sub(r"<[^>]+>", "", normalized)

    phone = (
        _row_value(doc, "contact_mobile", "")
        or _row_value(doc, "contact_phone", "")
        or ""
    ).strip()
    email = (_row_value(doc, "contact_email", "") or "").strip()
    address_lines = []

    for raw_line in normalized.splitlines():
        line = unescape(raw_line).strip()
        if not line:
            continue
        label, separator, value = line.partition(":")
        normalized_label = label.strip().casefold()
        if separator and normalized_label in PHONE_ADDRESS_LABELS:
            phone = phone or value.strip()
            continue
        if separator and normalized_label in EMAIL_ADDRESS_LABELS:
            email = email or value.strip()
            continue
        address_lines.append(line)

    return frappe._dict(
        {
            "address_lines": address_lines,
            "phone": phone,
            "email": email,
        }
    )


def _sales_print_source(doc):
    source = {
        "opportunity": (_row_value(doc, "opportunity", "") or "").strip(),
        "custom_opportunity_title": (
            _row_value(doc, "custom_opportunity_title", "") or ""
        ).strip(),
        "custom_opportunity_owner": (
            _row_value(doc, "custom_opportunity_owner", "") or ""
        ).strip(),
        "custom_delivery_lead_time": (
            _row_value(doc, "custom_delivery_lead_time", "") or ""
        ).strip(),
    }
    if _row_value(doc, "doctype", "") != "Sales Order":
        return source
    if source["opportunity"] and source["custom_opportunity_owner"]:
        return source

    quotation_name = next(
        (
            (_row_value(row, "prevdoc_docname", "") or "").strip()
            for row in (_row_value(doc, "items", []) or [])
            if (_row_value(row, "prevdoc_docname", "") or "").strip()
        ),
        "",
    )
    if not quotation_name:
        return source

    quotation_values = (
        frappe.db.get_value(
            "Quotation",
            quotation_name,
            [
                "opportunity",
                "custom_opportunity_title",
                "custom_opportunity_owner",
                "custom_delivery_lead_time",
            ],
            as_dict=True,
        )
        or {}
    )
    for fieldname in source:
        source[fieldname] = source[fieldname] or quotation_values.get(fieldname) or ""
    return source


def get_ttc_print_context(doc):
    """Return row and total values for TTC print formats.
    Works for any document with items and taxes child tables."""
    return _build_ttc_print_context(doc)


def _build_ttc_print_context(doc):
    items = list(doc.get("items") or []) if hasattr(doc, "get") else list(getattr(doc, "items", None) or [])
    rows_by_name = {}
    rows_by_idx = {}
    row_tax_total = 0.0

    has_template = bool((getattr(doc, "taxes_and_charges", "") or "").strip())

    if has_template and doc.get("taxes"):
        inclusive_totals = quote_item_inclusive_totals(doc)
        for index, row in enumerate(items):
            totals = inclusive_totals[index] if index < len(inclusive_totals) else {}
            qty = flt(_row_value(row, "qty") or 1) or 1
            total_ht = flt(_row_value(row, "net_amount") or _row_value(row, "amount"))
            unit_ht = total_ht / qty
            tax_amount = (
                flt(totals.get("tax_amount"))
                if "tax_amount" in totals
                else flt(_row_value(row, "custom_applied_taxes"))
            )
            total_ttc = total_ht + tax_amount
            unit_ttc = total_ttc / qty
            row_payload = {
                "tax": tax_amount,
                "unit_ht": unit_ht,
                "total_ht": total_ht,
                "unit": unit_ttc,
                "total": total_ttc,
            }
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
            row_payload = {
                "tax": 0.0,
                "unit_ht": rate,
                "total_ht": total_ttc,
                "unit": unit_ttc,
                "total": total_ttc,
            }
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
    info = {
        "company_name": data.get("company_name") or company_name or "",
        "phone": data.get("phone_no") or "",
        "email": data.get("email") or "",
        "website": data.get("website") or "",
        "tax_id": data.get("tax_id") or "",
        "currency": data.get("default_currency") or frappe.defaults.get_global_default("currency"),
        "country": data.get("country") or "",
        "legal_name": "",
        "legal_address": "",
        "bank_line": "",
        "registration_number": "",
    }
    if company_name in MOROCCO_PRINT_COMPANIES:
        info.update(MOROCCO_PRINT_LEGAL_DETAILS)
    return info


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
