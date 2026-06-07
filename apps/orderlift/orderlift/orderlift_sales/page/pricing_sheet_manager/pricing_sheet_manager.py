import json

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, nowdate

from orderlift.menu_access import resolve_current_company


@frappe.whitelist()
def get_pricing_sheet_manager_data(search=None, customer=None, mode=None, attention=None):
    filters = []
    search = (search or "").strip()
    customer = (customer or "").strip()
    mode = (mode or "All").strip()
    attention = (attention or "").strip()
    current_company = _current_company()

    if current_company and _has_custom_company():
        filters.append(["Pricing Sheet", "custom_company", "=", current_company])
    if search:
        filters.append(["Pricing Sheet", "sheet_name", "like", f"%{search}%"])
    if customer and customer != "All":
        filters.append(["Pricing Sheet", "customer", "=", customer])
    if mode and mode != "All":
        filters.append(["Pricing Sheet", "resolved_mode", "=", mode])
    _append_attention_filter(filters, attention)

    fields = [
        "name",
        "sheet_name",
        "customer",
        "sales_person",
        "crm_business_type",
        "crm_segment",
        "resolved_mode",
        "total_buy",
        "total_expenses",
        "total_selling",
        "customs_total_applied",
        "projection_warnings",
        "modified",
        "owner",
    ]
    if _has_custom_company():
        fields.insert(2, "custom_company")

    rows = frappe.get_list(
        "Pricing Sheet",
        filters=filters,
        fields=fields,
        order_by="modified desc",
        limit_page_length=80,
    )

    sheets = [_serialize_row(row) for row in rows]
    return {
        "sheets": sheets,
        "kpis": _get_kpis(current_company),
        "filters": _get_filters(current_company),
        "current_company": current_company,
    }


@frappe.whitelist()
def generate_pricing_sheet_quotation(pricing_sheet):
    if not pricing_sheet:
        frappe.throw(_("Pricing Sheet is required."))
    doc = frappe.get_doc("Pricing Sheet", pricing_sheet)
    doc.check_permission("write")
    doc.save()
    quotation = doc.generate_quotation()
    return {"quotation": quotation}


@frappe.whitelist()
def delete_pricing_sheets(pricing_sheets=None):
    names = _parse_names(pricing_sheets)
    if not names:
        frappe.throw(_("Select at least one Pricing Sheet to delete."))
    deleted = []
    errors = []
    for name in names:
        try:
            doc = frappe.get_doc("Pricing Sheet", name)
            doc.check_permission("delete")
            frappe.delete_doc("Pricing Sheet", name)
            deleted.append(name)
        except Exception as exc:
            errors.append(_("{0}: {1}").format(name, frappe.bold(str(exc))))
    if errors and not deleted:
        frappe.throw("<br>".join(errors))
    return {"deleted": deleted, "errors": errors}


def _parse_names(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = [value]
    else:
        parsed = value
    out = []
    seen = set()
    for name in parsed or []:
        name = (name or "").strip()
        if name and name not in seen:
            out.append(name)
            seen.add(name)
    return out


def _serialize_row(row):
    warnings = (row.projection_warnings or "").strip()
    line_totals = _get_line_totals(row.name)
    total_selling = flt(row.total_selling)
    total_buy = flt(row.total_buy)
    return {
        "name": row.name,
        "sheet_name": row.sheet_name or row.name,
        "custom_company": getattr(row, "custom_company", "") or "",
        "customer": row.customer or "",
        "sales_person": row.sales_person or "",
        "crm_business_type": row.crm_business_type or "",
        "crm_segment": row.crm_segment or "",
        "resolved_mode": row.resolved_mode or "Draft",
        "total_buy": total_buy,
        "total_expenses": flt(row.total_expenses),
        "total_selling": total_selling,
        "discounted_total": flt(line_totals.get("discounted_total") or total_selling),
        "discount_total": flt(line_totals.get("discount_total")),
        "commission_total": flt(line_totals.get("commission_total")),
        "line_count": int(line_totals.get("line_count") or 0),
        "margin_pct": flt(((total_selling - total_buy) / total_selling * 100) if total_selling else 0),
        "customs_total_applied": flt(row.customs_total_applied),
        "warning_count": len([line for line in warnings.splitlines() if line.strip()]),
        "warnings": warnings,
        "modified": row.modified,
        "owner": row.owner or "",
    }


def _get_line_totals(pricing_sheet):
    rows = frappe.db.sql(
        """
        SELECT
            COUNT(*) AS line_count,
            COALESCE(SUM(discounted_sell_total), 0) AS discounted_total,
            COALESCE(SUM(discount_amount), 0) AS discount_total,
            COALESCE(SUM(commission_amount), 0) AS commission_total
        FROM `tabPricing Sheet Item`
        WHERE parent = %s
        """,
        pricing_sheet,
        as_dict=True,
    )
    return rows[0] if rows else {}


def _get_kpis(current_company=None):
    filters = _company_filter_dict(current_company)
    total = frappe.db.count("Pricing Sheet", filters=filters or None)
    this_month_filters = {"creation": [">=", get_first_day(nowdate())]}
    this_month_filters.update(filters)
    this_month = frappe.db.count(
        "Pricing Sheet",
        filters=this_month_filters,
    )
    where_clause = ""
    values = {}
    if current_company and _has_custom_company():
        where_clause = "WHERE custom_company = %(company)s"
        values["company"] = current_company
    totals = frappe.db.sql(
        f"""
        SELECT
            COALESCE(SUM(total_selling), 0) AS total_selling,
            COALESCE(SUM(total_buy), 0) AS total_buy,
            SUM(CASE WHEN projection_warnings IS NOT NULL AND projection_warnings != '' THEN 1 ELSE 0 END) AS warning_sheets
        FROM `tabPricing Sheet`
        {where_clause}
        """,
        values,
        as_dict=True,
    )[0]
    total_selling = flt(totals.total_selling)
    total_buy = flt(totals.total_buy)
    margin_pct = ((total_selling - total_buy) / total_selling * 100) if total_selling else 0
    return {
        "total_sheets": total,
        "sheets_this_month": this_month,
        "total_selling": total_selling,
        "avg_margin_pct": flt(margin_pct),
        "warning_sheets": int(totals.warning_sheets or 0),
    }


def _get_filters(current_company=None):
    filters = {"customer": ["is", "set"]}
    filters.update(_company_filter_dict(current_company))
    customers = frappe.get_list(
        "Pricing Sheet",
        fields=["customer"],
        filters=filters,
        group_by="customer",
        order_by="customer asc",
        pluck="customer",
    )
    return {
        "customers": customers,
        "modes": ["Dynamic", "Static", "Draft"],
    }


def _append_attention_filter(filters, attention):
    if attention == "missing_benchmark":
        filters.append(["Pricing Sheet", "benchmark_policy", "in", ["", None]])
    elif attention == "missing_customs":
        filters.append(["Pricing Sheet", "customs_policy", "in", ["", None]])
    elif attention == "warnings":
        filters.append(["Pricing Sheet", "projection_warnings", "is", "set"])
        filters.append(["Pricing Sheet", "projection_warnings", "!=", ""])


def _current_company():
    return resolve_current_company(user=frappe.session.user)


def _has_custom_company():
    return frappe.db.has_column("Pricing Sheet", "custom_company")


def _company_filter_dict(current_company=None):
    current_company = (current_company or "").strip()
    if current_company and _has_custom_company():
        return {"custom_company": current_company}
    return {}
