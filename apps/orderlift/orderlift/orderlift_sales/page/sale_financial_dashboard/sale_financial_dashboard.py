from __future__ import annotations

import json
from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.orderlift_sales import reporting


PAGE_NAME = "sale-financial-dashboard"
PAGE_ROLES = ("Orderlift Admin", "System Manager", "Finance User")


def sync_page_roles() -> dict:
    if not frappe.db.exists("Page", PAGE_NAME):
        return {"skipped": True, "reason": "missing page"}
    page = frappe.get_doc("Page", PAGE_NAME)
    page.set("roles", [])
    for role in PAGE_ROLES:
        if frappe.db.exists("Role", role):
            page.append("roles", {"role": role})
    page.save(ignore_permissions=True)
    frappe.db.commit()
    return {"page": PAGE_NAME, "roles": list(PAGE_ROLES)}


@frappe.whitelist()
def get_dashboard_data(filters: str | dict | None = None):
    frappe.has_permission("Sales Order", "read", throw=True)
    active_filters = _clean_filters(filters)
    companies = reporting.get_reporting_companies()
    company_names = _selected_company_names(companies, active_filters)
    sales_orders = _sales_orders(company_names, active_filters)
    projects = _projects(company_names, active_filters)
    purchase_orders = _purchase_orders(company_names, active_filters)

    return {
        "companies": companies,
        "active_filters": active_filters,
        "filter_options": _filter_options(companies, sales_orders, projects, purchase_orders, active_filters),
        "kpis": _get_kpis(sales_orders, projects, purchase_orders),
        "currency_totals": _currency_totals(sales_orders, purchase_orders),
        "by_business_type": _business_type_summary(sales_orders, projects, purchase_orders),
        "by_segment": _segment_summary(sales_orders, projects, purchase_orders),
        "by_company": _company_summary(companies, sales_orders, projects, purchase_orders),
        "sales_order_statuses": _status_rows(sales_orders, "workflow_status"),
        "project_statuses": _status_rows(projects, "workflow_status"),
        "recent_sales_orders": _recent_sales_orders(sales_orders),
        "recent_projects": _recent_projects(projects),
        "recent_charges": _recent_purchase_orders(purchase_orders),
    }


def _clean_filters(filters: str | dict | None) -> dict:
    if isinstance(filters, str):
        try:
            filters = json.loads(filters or "{}")
        except ValueError:
            filters = {}
    filters = filters or {}
    business_type = (filters.get("business_type") or "").strip()
    if business_type and business_type not in reporting.BUSINESS_TYPE_BUCKETS:
        business_type = ""
    return {
        "company": (filters.get("company") or "").strip(),
        "business_type": business_type,
        "crm_segment": (filters.get("crm_segment") or "").strip(),
        "currency": (filters.get("currency") or "").strip(),
        "sales_status": (filters.get("sales_status") or "").strip(),
        "project_status": (filters.get("project_status") or "").strip(),
        "from_date": (filters.get("from_date") or "").strip(),
        "to_date": (filters.get("to_date") or "").strip(),
        "search": (filters.get("search") or "").strip()[:120],
    }


def _selected_company_names(companies: list[dict], filters: dict) -> set[str]:
    company_names = {row["name"] for row in companies if row.get("name")}
    selected = filters.get("company")
    if selected:
        return {selected} if not company_names or selected in company_names else {"__no_matching_company__"}
    return company_names


def _sales_orders(company_names: set[str], filters: dict | None = None) -> list[dict]:
    if not reporting.has_doctype("Sales Order"):
        return []
    fields = ["name", "customer", "company", "status", "grand_total", "currency", "modified"]
    for fieldname in ["transaction_date", "custom_orderlift_order_status", "custom_crm_business_type", "custom_crm_segment", "custom_installation_project", "project"]:
        if reporting.has_field("Sales Order", fieldname):
            fields.append(fieldname)
    rows = frappe.get_all(
        "Sales Order",
        filters=_document_filters("Sales Order", company_names, filters, docstatus=1, date_fields=("transaction_date", "modified")),
        fields=fields,
        order_by="modified desc",
        limit_page_length=0,
    )
    out = []
    for row in rows:
        business_type = reporting.sales_order_business_type(row)
        out.append(
            {
                "name": row.get("name"),
                "customer": row.get("customer") or "",
                "company": row.get("company") or "",
                "currency": row.get("currency") or reporting.company_currency(row.get("company")) or "",
                "amount": flt(row.get("grand_total") or 0),
                "business_type": business_type,
                "segment": _segment_value(row.get("custom_crm_segment")),
                "workflow_status": row.get("custom_orderlift_order_status") or row.get("status") or _("No Status"),
                "date": row.get("transaction_date") or row.get("modified"),
                "modified": row.get("modified"),
                "link": f"/app/sales-order/{row.get('name')}",
            }
        )
    return [row for row in out if _matches_filters(row, filters, status_filter="sales_status", search_fields=("name", "customer", "company", "workflow_status"))]


def _projects(company_names: set[str], filters: dict | None = None) -> list[dict]:
    if not reporting.has_doctype("Project"):
        return []
    fields = ["name", "project_name", "customer", "company", "status", "modified"]
    for fieldname in ["expected_start_date", "custom_project_status", "custom_crm_business_type", "custom_crm_segment", "custom_source_opportunity"]:
        if reporting.has_field("Project", fieldname):
            fields.append(fieldname)
    rows = frappe.get_all(
        "Project",
        filters=_document_filters("Project", company_names, filters, docstatus=None, date_fields=("expected_start_date", "modified")),
        fields=fields,
        order_by="modified desc",
        limit_page_length=0,
    )
    out = []
    for row in rows:
        business_type = reporting.normalize_business_type(row.get("custom_crm_business_type"))
        if business_type == "Unassigned" and row.get("custom_source_opportunity"):
            business_type = reporting.opportunity_business_type(row.get("custom_source_opportunity"))
        if business_type == "Unassigned":
            business_type = "Installation"
        out.append(
            {
                "name": row.get("name"),
                "title": row.get("project_name") or row.get("name"),
                "customer": row.get("customer") or "",
                "company": row.get("company") or "",
                "business_type": business_type,
                "segment": _segment_value(row.get("custom_crm_segment")),
                "workflow_status": row.get("custom_project_status") or row.get("status") or _("No Status"),
                "date": row.get("expected_start_date") or row.get("modified"),
                "modified": row.get("modified"),
                "link": f"/app/project/{row.get('name')}",
            }
        )
    return [row for row in out if _matches_filters(row, filters, status_filter="project_status", search_fields=("name", "title", "customer", "company", "workflow_status"), include_currency=False)]


def _purchase_orders(company_names: set[str], filters: dict | None = None) -> list[dict]:
    if not reporting.has_doctype("Purchase Order"):
        return []
    fields = ["name", "supplier", "company", "status", "grand_total", "currency", "modified"]
    for fieldname in ["transaction_date", "project"]:
        if reporting.has_field("Purchase Order", fieldname):
            fields.append(fieldname)
    rows = frappe.get_all(
        "Purchase Order",
        filters=_document_filters("Purchase Order", company_names, filters, docstatus=1, date_fields=("transaction_date", "modified")),
        fields=fields,
        order_by="modified desc",
        limit_page_length=0,
    )
    out = []
    seen = set()
    for row in rows:
        if row.get("name") in seen:
            continue
        seen.add(row.get("name"))
        project_name = reporting.purchase_order_project(row.get("name"), row.get("project"))
        project_context = _project_context(project_name)
        out.append(
            {
                "name": row.get("name"),
                "supplier": row.get("supplier") or "",
                "project": project_name,
                "company": row.get("company") or "",
                "currency": row.get("currency") or reporting.company_currency(row.get("company")) or "",
                "amount": flt(row.get("grand_total") or 0),
                "business_type": project_context.get("business_type") or "Unassigned",
                "segment": project_context.get("segment") or "Unassigned",
                "status": row.get("status") or _("No Status"),
                "date": row.get("transaction_date") or row.get("modified"),
                "modified": row.get("modified"),
                "link": f"/app/purchase-order/{row.get('name')}",
            }
        )
    return [row for row in out if _matches_filters(row, filters, search_fields=("name", "supplier", "project", "company", "status"))]


def _document_filters(doctype: str, company_names: set[str], filters: dict | None, docstatus: int | None, date_fields: tuple[str, ...]) -> dict:
    query = {}
    if docstatus is not None and reporting.has_field(doctype, "docstatus"):
        query["docstatus"] = docstatus
    if company_names and reporting.has_field(doctype, "company"):
        query["company"] = ["in", sorted(company_names)]
    date_field = _first_existing_field(doctype, date_fields)
    if date_field and filters:
        from_date = filters.get("from_date")
        to_date = filters.get("to_date")
        if from_date and to_date:
            query[date_field] = ["between", [from_date, to_date]]
        elif from_date:
            query[date_field] = [">=", from_date]
        elif to_date:
            query[date_field] = ["<=", to_date]
    return query


def _matches_filters(row: dict, filters: dict | None, status_filter: str | None = None, search_fields: tuple[str, ...] = (), include_currency: bool = True) -> bool:
    filters = filters or {}
    if filters.get("company") and row.get("company") != filters["company"]:
        return False
    if filters.get("business_type") and reporting.normalize_business_type(row.get("business_type")) != filters["business_type"]:
        return False
    if filters.get("crm_segment") and _segment_value(row.get("segment")) != filters["crm_segment"]:
        return False
    if include_currency and filters.get("currency") and row.get("currency") != filters["currency"]:
        return False
    if status_filter and filters.get(status_filter) and row.get("workflow_status") != filters[status_filter]:
        return False
    search = (filters.get("search") or "").lower()
    if search and not any(search in str(row.get(fieldname) or "").lower() for fieldname in search_fields):
        return False
    return True


def _first_existing_field(doctype: str, fieldnames: tuple[str, ...]) -> str:
    for fieldname in fieldnames:
        if reporting.has_field(doctype, fieldname):
            return fieldname
    return ""


def _project_context(project_name: str | None) -> dict:
    if not project_name or not reporting.has_doctype("Project"):
        return {"business_type": "Unassigned", "segment": "Unassigned"}
    fields = [field for field in ("custom_crm_business_type", "custom_crm_segment", "custom_source_opportunity") if reporting.has_field("Project", field)]
    values = frappe.db.get_value("Project", project_name, fields, as_dict=True) if fields else None
    values = values or {}
    business_type = reporting.normalize_business_type(values.get("custom_crm_business_type"))
    if business_type == "Unassigned" and values.get("custom_source_opportunity"):
        business_type = reporting.opportunity_business_type(values.get("custom_source_opportunity"))
    if business_type == "Unassigned":
        business_type = "Installation"
    return {"business_type": business_type, "segment": _segment_value(values.get("custom_crm_segment"))}


def _get_kpis(sales_orders: list[dict], projects: list[dict], purchase_orders: list[dict]) -> dict:
    completed_projects = len([row for row in projects if str(row.get("workflow_status") or "").lower() in {"completed", "closed"}])
    blocked_projects = len([row for row in projects if "blocked" in str(row.get("workflow_status") or "").lower()])
    return {
        "sales_orders": len(sales_orders),
        "projects": len(projects),
        "completed_projects": completed_projects,
        "blocked_projects": blocked_projects,
        "purchase_orders": len(purchase_orders),
    }


def _currency_totals(sales_orders: list[dict], purchase_orders: list[dict]) -> list[dict]:
    totals = reporting.empty_currency_totals()
    for row in sales_orders:
        reporting.add_amount(totals, row.get("currency"), "revenue", row.get("amount"))
    for row in purchase_orders:
        reporting.add_amount(totals, row.get("currency"), "charges", row.get("amount"))
    return reporting.currency_totals_to_rows(totals)


def _business_type_summary(sales_orders: list[dict], projects: list[dict], purchase_orders: list[dict]) -> list[dict]:
    rows = {label: _summary_row(label) for label in reporting.BUSINESS_TYPE_BUCKETS}
    for project in projects:
        rows.setdefault(reporting.normalize_business_type(project.get("business_type")), _summary_row(reporting.normalize_business_type(project.get("business_type"))))["projects"] += 1
    for sales_order in sales_orders:
        row = rows.setdefault(reporting.normalize_business_type(sales_order.get("business_type")), _summary_row(reporting.normalize_business_type(sales_order.get("business_type"))))
        row["sales_orders"] += 1
        reporting.add_amount(row["amounts"], sales_order.get("currency"), "revenue", sales_order.get("amount"))
    for purchase_order in purchase_orders:
        row = rows.setdefault(reporting.normalize_business_type(purchase_order.get("business_type")), _summary_row(reporting.normalize_business_type(purchase_order.get("business_type"))))
        row["purchase_orders"] += 1
        reporting.add_amount(row["amounts"], purchase_order.get("currency"), "charges", purchase_order.get("amount"))
    return [_serialize_summary_row(row) for row in rows.values()]


def _segment_summary(sales_orders: list[dict], projects: list[dict], purchase_orders: list[dict]) -> list[dict]:
    labels = sorted({_segment_value(row.get("segment")) for row in [*sales_orders, *projects, *purchase_orders]})
    rows = {label: _summary_row(label) for label in labels}
    for project in projects:
        rows.setdefault(_segment_value(project.get("segment")), _summary_row(_segment_value(project.get("segment"))))["projects"] += 1
    for sales_order in sales_orders:
        row = rows.setdefault(_segment_value(sales_order.get("segment")), _summary_row(_segment_value(sales_order.get("segment"))))
        row["sales_orders"] += 1
        reporting.add_amount(row["amounts"], sales_order.get("currency"), "revenue", sales_order.get("amount"))
    for purchase_order in purchase_orders:
        row = rows.setdefault(_segment_value(purchase_order.get("segment")), _summary_row(_segment_value(purchase_order.get("segment"))))
        row["purchase_orders"] += 1
        reporting.add_amount(row["amounts"], purchase_order.get("currency"), "charges", purchase_order.get("amount"))
    return [_serialize_summary_row(row) for row in rows.values()]


def _company_summary(companies: list[dict], sales_orders: list[dict], projects: list[dict], purchase_orders: list[dict]) -> list[dict]:
    rows = {company["name"]: _summary_row(company["name"], currency=company.get("currency")) for company in companies}
    for project in projects:
        if project.get("company") in rows:
            rows[project["company"]]["projects"] += 1
    for sales_order in sales_orders:
        if sales_order.get("company") not in rows:
            continue
        row = rows[sales_order["company"]]
        row["sales_orders"] += 1
        reporting.add_amount(row["amounts"], sales_order.get("currency"), "revenue", sales_order.get("amount"))
    for purchase_order in purchase_orders:
        if purchase_order.get("company") not in rows:
            continue
        row = rows[purchase_order["company"]]
        row["purchase_orders"] += 1
        reporting.add_amount(row["amounts"], purchase_order.get("currency"), "charges", purchase_order.get("amount"))
    return [_serialize_summary_row(row) for row in rows.values()]


def _status_rows(rows: list[dict], fieldname: str) -> list[dict]:
    counts = Counter((row.get(fieldname) or _("No Status")) for row in rows)
    return [{"label": label, "value": value} for label, value in counts.most_common(10)]


def _recent_sales_orders(sales_orders: list[dict]) -> list[dict]:
    rows = _sort_recent(sales_orders)[:8]
    return [
        {
            "label": row.get("name"),
            "meta": " · ".join(part for part in [row.get("customer"), row.get("company"), row.get("workflow_status")] if part),
            "amount": flt(row.get("amount") or 0),
            "currency": row.get("currency") or "",
            "link": row.get("link") or f"/app/sales-order/{row.get('name')}",
        }
        for row in rows
    ]


def _recent_projects(projects: list[dict]) -> list[dict]:
    rows = _sort_recent(projects)[:8]
    return [
        {
            "label": row.get("title") or row.get("name"),
            "meta": " · ".join(part for part in [row.get("customer"), row.get("company"), row.get("workflow_status")] if part),
            "link": row.get("link") or f"/app/project/{row.get('name')}",
        }
        for row in rows
    ]


def _recent_purchase_orders(purchase_orders: list[dict]) -> list[dict]:
    rows = _sort_recent(purchase_orders)[:8]
    return [
        {
            "label": row.get("name"),
            "meta": " · ".join(part for part in [row.get("supplier"), row.get("company"), row.get("status")] if part),
            "amount": flt(row.get("amount") or 0),
            "currency": row.get("currency") or "",
            "link": row.get("link") or f"/app/purchase-order/{row.get('name')}",
        }
        for row in rows
    ]


def _sort_recent(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: str(row.get("modified") or row.get("date") or ""), reverse=True)


def _limited_recent(doctype: str, company_names: set[str], fields: list[str]) -> list:
    if not reporting.has_doctype(doctype):
        return []
    filters = {}
    if reporting.has_field(doctype, "docstatus"):
        filters["docstatus"] = ["<", 2]
    if company_names and reporting.has_field(doctype, "company"):
        filters["company"] = ["in", sorted(company_names)]
    return frappe.get_all(
        doctype,
        filters=filters,
        fields=["name", *[field for field in fields if reporting.has_field(doctype, field)]],
        order_by="modified desc",
        limit_page_length=6,
    )


def _summary_row(label: str, currency: str | None = None) -> dict:
    return {
        "label": label,
        "currency": currency or "",
        "projects": 0,
        "sales_orders": 0,
        "purchase_orders": 0,
        "amounts": reporting.empty_currency_totals(),
    }


def _serialize_summary_row(row: dict) -> dict:
    return {
        "label": row["label"],
        "currency": row.get("currency") or "",
        "projects": row.get("projects") or 0,
        "sales_orders": row.get("sales_orders") or 0,
        "purchase_orders": row.get("purchase_orders") or 0,
        "amounts": reporting.currency_totals_to_rows(row.get("amounts") or {}),
    }


def _filter_options(companies: list[dict], sales_orders: list[dict], projects: list[dict], purchase_orders: list[dict], filters: dict) -> dict:
    return {
        "companies": companies,
        "business_types": list(reporting.BUSINESS_TYPE_BUCKETS),
        "segments": _option_values([row.get("segment") for row in [*sales_orders, *projects, *purchase_orders]], filters.get("crm_segment")),
        "currencies": _option_values([row.get("currency") for row in [*sales_orders, *purchase_orders]], filters.get("currency")),
        "sales_order_statuses": _option_values([row.get("workflow_status") for row in sales_orders], filters.get("sales_status")),
        "project_statuses": _option_values([row.get("workflow_status") for row in projects], filters.get("project_status")),
    }


def _option_values(values: list, selected: str | None = None) -> list[str]:
    options = sorted({str(value or "").strip() for value in values if str(value or "").strip()})
    selected = (selected or "").strip()
    if selected and selected not in options:
        options.insert(0, selected)
    return options


def _segment_value(value: str | None) -> str:
    return (value or "").strip() or "Unassigned"
