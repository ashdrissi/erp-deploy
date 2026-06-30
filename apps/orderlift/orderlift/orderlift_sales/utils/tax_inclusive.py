from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt


def sync_quotation_item_tax_inclusive_fields(doc) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def _sync_doc_item_tax_inclusive_fields(doc) -> None:
    if not getattr(doc, "items", None):
        return
    inclusive_totals = _quote_item_inclusive_totals(doc)
    for row, totals in zip(doc.items or [], inclusive_totals):
        # Round to each field's precision so the value matches what is stored in
        # the DB. Without this, flt() keeps floating-point noise (e.g.
        # 11.856000000000002) that never equals the stored 11.856, so validate is
        # non-idempotent and the form is perpetually "Not Saved" after every save.
        if row.meta.get_field("custom_applied_taxes"):
            row.custom_applied_taxes = flt(totals.get("tax_amount"), row.precision("custom_applied_taxes"))
        if row.meta.get_field("custom_pu_ttc"):
            row.custom_pu_ttc = flt(totals.get("unit_incl_tax"), row.precision("custom_pu_ttc"))
        if row.meta.get_field("custom_pt_ttc"):
            row.custom_pt_ttc = flt(totals.get("total_incl_tax"), row.precision("custom_pt_ttc"))


def sync_sales_order_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def sync_delivery_note_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def sync_sales_invoice_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def sync_purchase_order_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def sync_purchase_invoice_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def sync_purchase_receipt_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def sync_supplier_quotation_tax_inclusive_fields(doc, method=None) -> None:
    _sync_doc_item_tax_inclusive_fields(doc)


def apply_quotation_sales_tax_template(doc) -> None:
    if not doc or not _doc_has_field(doc, "taxes_and_charges"):
        return

    company = (doc.get("company") or "").strip()

    if _party_is_exempt_from_sales_tax(doc):
        _clear_tax_rows(doc)
        if doc.meta.get_field("taxes_and_charges"):
            doc.taxes_and_charges = ""
        _calculate_taxes_and_totals(doc)
        return

    selected_template = (doc.get("taxes_and_charges") or "").strip()

    if not selected_template:
        _clear_tax_rows(doc)
        _calculate_taxes_and_totals(doc)
        return

    _validate_sales_tax_template_company(selected_template, company)
    copied_rows = _copy_sales_tax_template_rows(doc, selected_template)
    if not copied_rows:
        frappe.throw(
            _("Sales Taxes Template {0} has no tax rows. Ask Finance/Admin to configure it.").format(
                selected_template
            )
        )
    _calculate_taxes_and_totals(doc)


def quote_item_inclusive_totals(doc) -> list[dict]:
    return _quote_item_inclusive_totals(doc)


def sync_pricing_sheet_item_tax_inclusive_fields(pricing_sheet) -> None:
    rows = [row for row in (pricing_sheet.lines or []) if row.get("item")]
    if not rows:
        return
    quote = _build_pricing_sheet_preview_quotation(
        pricing_sheet,
        rows,
        taxes_and_charges_template=(pricing_sheet.get("taxes_and_charges_template") or "").strip(),
        allow_blank_customer=True,
    )
    if not quote or not getattr(quote, "items", None):
        for row in rows:
            pu_ht = flt(row.get("discounted_sell_unit_price") or row.get("final_sell_unit_price") or 0)
            pt_ht = flt(row.get("discounted_sell_total") or (pu_ht * flt(row.get("qty") or 1)) or 0)
            _set_sheet_row_ttc(row, 0, pu_ht, pt_ht)
        return

    inclusive_totals = _quote_item_inclusive_totals(quote)
    for row, totals in zip(rows, inclusive_totals):
        _set_sheet_row_ttc(
            row,
            totals.get("tax_amount"),
            totals.get("unit_incl_tax"),
            totals.get("total_incl_tax"),
        )


def build_catalogue_ttc_price_map(item_price_map: dict[str, float | int | None], company: str) -> dict[str, float]:
    template = company_default_sales_taxes_template(company)
    base_prices = {item_code: flt(value) for item_code, value in (item_price_map or {}).items() if value is not None}
    if not base_prices:
        return base_prices
    rate = sales_tax_template_total_rate(template)
    if not rate:
        return base_prices
    return {item_code: flt(value) * (1 + rate / 100.0) for item_code, value in base_prices.items()}


def company_default_sales_taxes_template(company: str) -> str:
    company = (company or "").strip()
    if not company or not frappe.db.exists("DocType", "Sales Taxes and Charges Template"):
        return ""
    configured = ""
    if frappe.db.has_column("Company", "custom_default_sales_taxes_template"):
        configured = (frappe.db.get_value("Company", company, "custom_default_sales_taxes_template") or "").strip()
    if configured and _sales_tax_template_valid_for_company(configured, company):
        return configured
    rows = frappe.get_all(
        "Sales Taxes and Charges Template",
        filters={"company": company, "disabled": 0},
        fields=["name", "is_default"],
        order_by="is_default desc, modified desc, name asc",
        limit_page_length=1,
    )
    return rows[0].name if rows else ""


def company_default_sales_tax_rate(company: str) -> float:
    return sales_tax_template_total_rate(company_default_sales_taxes_template(company))


def sales_tax_template_total_rate(template_name: str) -> float:
    template_name = (template_name or "").strip()
    if not template_name or not frappe.db.exists("Sales Taxes and Charges Template", template_name):
        return 0.0
    rows = frappe.get_all(
        "Sales Taxes and Charges",
        filters={"parent": template_name, "parenttype": "Sales Taxes and Charges Template"},
        fields=["charge_type", "rate"],
        limit_page_length=0,
    )
    return flt(
        sum(
            flt(row.get("rate") or 0)
            for row in rows
            if (row.get("charge_type") or "") != "Actual"
        )
    )


def _sales_tax_template_valid_for_company(template_name: str, company: str) -> bool:
    values = frappe.db.get_value(
        "Sales Taxes and Charges Template",
        template_name,
        ["company", "disabled"],
        as_dict=True,
    )
    if not values:
        return False
    template_company = (values.get("company") or "").strip()
    return not flt(values.get("disabled") or 0) and (not template_company or template_company == company)


def _set_sheet_row_ttc(row, tax_amount, unit_incl_tax, total_incl_tax) -> None:
    # Round to field precision to keep validate idempotent (see _sync_doc_item_tax_inclusive_fields).
    if row.meta.get_field("custom_applied_taxes"):
        row.custom_applied_taxes = flt(tax_amount, row.precision("custom_applied_taxes"))
    if row.meta.get_field("custom_pu_ttc"):
        row.custom_pu_ttc = flt(unit_incl_tax, row.precision("custom_pu_ttc"))
    if row.meta.get_field("custom_pt_ttc"):
        row.custom_pt_ttc = flt(total_incl_tax, row.precision("custom_pt_ttc"))


def _build_pricing_sheet_preview_quotation(pricing_sheet, rows, taxes_and_charges_template="", allow_blank_customer=False):
    customer = (pricing_sheet.get("customer") or "").strip()
    company = (pricing_sheet.get("custom_company") or pricing_sheet._resolve_company_for_quotation() or "").strip()
    if not company or (not allow_blank_customer and not customer):
        return None

    quote = frappe.new_doc("Quotation")
    quote.company = company
    quote.quotation_to = "Customer"
    quote.party_name = customer
    quote.customer_name = frappe.db.get_value("Customer", customer, "customer_name") if customer else "Catalogue Preview"
    if quote.meta.get_field("ignore_pricing_rule"):
        quote.ignore_pricing_rule = 1
    if taxes_and_charges_template and quote.meta.get_field("taxes_and_charges"):
        quote.taxes_and_charges = taxes_and_charges_template
    apply_price_list = getattr(pricing_sheet, "_apply_quotation_price_list", None)
    if callable(apply_price_list):
        apply_price_list(quote)
    if not allow_blank_customer:
        _run_if_exists(quote, "set_missing_values")

    for row in rows:
        qty = flt(row.get("qty") or 0) or 1
        rate = flt(row.get("discounted_sell_unit_price") or row.get("final_sell_unit_price") or 0)
        quote.append(
            "items",
            {
                "item_code": row.get("item"),
                "qty": qty,
                "rate": rate,
                "price_list_rate": rate,
                "amount": rate * qty,
                "net_rate": rate,
                "net_amount": rate * qty,
                "description": row.get("item_name") or row.get("item") or "",
                "ignore_pricing_rule": 1,
            },
        )

    if not allow_blank_customer:
        _run_if_exists(quote, "set_missing_values")
    apply_quotation_sales_tax_template(quote)
    return quote


def _run_if_exists(doc, method_name: str) -> None:
    method = getattr(doc, method_name, None)
    if callable(method):
        method()


def _calculate_taxes_and_totals(doc) -> None:
    _run_if_exists(doc, "calculate_taxes_and_totals")


def _clear_tax_rows(doc) -> None:
    setter = getattr(doc, "set", None)
    if callable(setter):
        setter("taxes", [])
    else:
        doc.taxes = []


def _party_is_exempt_from_sales_tax(doc) -> bool:
    party_type = (doc.get("quotation_to") or "").strip()
    party_name = (doc.get("party_name") or "").strip()
    if not party_type or not party_name:
        return False
    if not frappe.db.exists(party_type, party_name):
        return False
    if not frappe.db.has_column(party_type, "exempt_from_sales_tax"):
        return False
    return bool(frappe.db.get_value(party_type, party_name, "exempt_from_sales_tax"))


def _copy_sales_tax_template_rows(doc, template_name: str) -> int:
    template = frappe.get_doc("Sales Taxes and Charges Template", template_name)
    source_rows = list(template.get("taxes") or [])
    _clear_tax_rows(doc)
    excluded = {
        "doctype",
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "parent",
        "parentfield",
        "parenttype",
        "docstatus",
        "idx",
    }
    for source in source_rows:
        values = {key: value for key, value in source.as_dict().items() if key not in excluded}
        doc.append("taxes", values)
    return len(source_rows)


def _doc_has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    getter = getattr(meta, "get_field", None)
    return bool(getter(fieldname)) if callable(getter) else True


def _validate_sales_tax_template_company(template_name: str, company: str) -> None:
    if not template_name:
        return
    values = frappe.db.get_value(
        "Sales Taxes and Charges Template",
        template_name,
        ["company", "disabled"],
        as_dict=True,
    )
    if not values:
        frappe.throw(_("Sales Taxes Template {0} does not exist.").format(template_name))
    template_company = (values.get("company") or "").strip()
    if flt(values.get("disabled") or 0):
        frappe.throw(_("Sales Taxes Template {0} is disabled.").format(template_name))
    if company and template_company and template_company != company:
        frappe.throw(_("Sales Taxes Template {0} does not belong to company {1}.").format(template_name, company))


def _quote_item_inclusive_totals(doc) -> list[dict]:
    items = list(doc.items or [])
    if not items:
        return []

    totals_by_item_code = {}
    has_item_wise_detail = False
    for tax in doc.get("taxes") or []:
        detail = _loads(getattr(tax, "item_wise_tax_detail", None))
        if not detail:
            continue
        has_item_wise_detail = True
        for item_code, value in detail.items():
            tax_amount = _detail_tax_amount(value)
            totals_by_item_code[item_code] = flt(totals_by_item_code.get(item_code)) + flt(tax_amount)

    tax_by_row_name = {}
    if has_item_wise_detail:
        rows_by_item_code = {}
        for row in items:
            rows_by_item_code.setdefault(row.item_code, []).append(row)
        for item_code, grouped_rows in rows_by_item_code.items():
            total_tax = flt(totals_by_item_code.get(item_code))
            base_total = sum(flt(row.net_amount or row.amount) for row in grouped_rows) or 0
            allocated = 0.0
            for index, row in enumerate(grouped_rows):
                row_total = flt(row.net_amount or row.amount)
                if index == len(grouped_rows) - 1:
                    row_tax = total_tax - allocated
                elif total_tax and base_total:
                    row_tax = total_tax * (row_total / base_total)
                    allocated += row_tax
                else:
                    row_tax = 0.0
                tax_by_row_name[row.name] = flt(row_tax)
    else:
        for row in items:
            tax_by_row_name[row.name] = _fallback_row_tax(row)

    totals = []
    for row in items:
        line_total = flt(row.net_amount or row.amount)
        tax_total = flt(tax_by_row_name.get(row.name))
        qty = flt(row.qty) or 1
        total_incl_tax = line_total + tax_total
        totals.append(
            {
                "tax_amount": tax_total,
                "unit_incl_tax": total_incl_tax / qty if qty else total_incl_tax,
                "total_incl_tax": total_incl_tax,
            }
        )
    return totals


def _detail_tax_amount(value) -> float:
    if isinstance(value, (list, tuple)):
        return flt(value[1] if len(value) > 1 else value[0])
    if isinstance(value, dict):
        return flt(value.get("tax_amount") or value.get("amount") or value.get("tax") or 0)
    return flt(value)


def _fallback_row_tax(row) -> float:
    item_tax_rate = _loads(getattr(row, "item_tax_rate", None))
    if not item_tax_rate:
        return 0.0
    total_rate = sum(flt(rate) for rate in item_tax_rate.values()) if isinstance(item_tax_rate, dict) else 0.0
    return flt(row.net_amount or row.amount) * total_rate / 100.0 if total_rate else 0.0


def _loads(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}
