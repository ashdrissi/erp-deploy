from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import get_allowed_companies, user_can_access_all_companies


def execute(filters=None):
    frappe.has_permission("Sales Invoice", "read", throw=True)
    filters = frappe._dict(filters or {})
    companies = _permitted_companies(filters.get("company"))
    if not companies:
        return _columns(), []

    conditions = ["si.docstatus = 1", "si.company in %(companies)s"]
    values = {"companies": tuple(companies)}
    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = filters.from_date
    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = filters.to_date
    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
        values["customer"] = filters.customer
    if cint(filters.get("outstanding_only")):
        conditions.append("si.outstanding_amount > 0.0001")

    project_expression = _project_expression()
    rows = frappe.db.sql(
        f"""
        select
            si.name as sales_invoice,
            si.posting_date,
            si.due_date,
            si.customer,
            si.customer_name,
            refs.sales_orders,
            refs.projects,
            si.owner,
            payments.payment_modes,
            si.currency,
            si.grand_total,
            si.paid_amount,
            si.outstanding_amount,
            si.status
        from `tabSales Invoice` si
        left join (
            select
                sii.parent,
                group_concat(distinct nullif(sii.sales_order, '') order by sii.sales_order separator ', ') as sales_orders,
                group_concat(distinct nullif({project_expression}, '') order by {project_expression} separator ', ') as projects
            from `tabSales Invoice Item` sii
            left join `tabSales Order` so on so.name = sii.sales_order
            group by sii.parent
        ) refs on refs.parent = si.name
        left join (
            select
                per.reference_name,
                group_concat(distinct nullif(pe.mode_of_payment, '') order by pe.mode_of_payment separator ', ') as payment_modes
            from `tabPayment Entry Reference` per
            inner join `tabPayment Entry` pe on pe.name = per.parent and pe.docstatus = 1
            where per.reference_doctype = 'Sales Invoice'
            group by per.reference_name
        ) payments on payments.reference_name = si.name
        where {' and '.join(conditions)}
        order by si.due_date asc, si.posting_date desc, si.name desc
        """,
        values,
        as_dict=True,
    )
    return _columns(), rows


def _permitted_companies(selected_company: str | None) -> list[str]:
    user = frappe.session.user
    if user_can_access_all_companies(user):
        companies = frappe.get_all("Company", pluck="name")
    else:
        companies = get_allowed_companies(user)
    companies = sorted({name for name in companies if name})
    if selected_company:
        return [selected_company] if selected_company in companies else []
    return companies


def _project_expression() -> str:
    so_meta = frappe.get_meta("Sales Order")
    choices = []
    if frappe.get_meta("Sales Invoice Item").get_field("project"):
        choices.append("sii.project")
    if so_meta.get_field("project"):
        choices.append("so.project")
    if so_meta.get_field("custom_installation_project"):
        choices.append("so.custom_installation_project")
    return f"coalesce({', '.join(choices)}, '')" if choices else "''"


def _columns():
    return [
        {"fieldname": "sales_invoice", "label": _("Sales Invoice"), "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
        {"fieldname": "posting_date", "label": _("Invoice Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "due_date", "label": _("Due Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 170},
        {"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "sales_orders", "label": _("Sales Order(s)"), "fieldtype": "Data", "width": 180},
        {"fieldname": "projects", "label": _("Project(s)"), "fieldtype": "Data", "width": 180},
        {"fieldname": "owner", "label": _("Owner"), "fieldtype": "Link", "options": "User", "width": 170},
        {"fieldname": "payment_modes", "label": _("Payment Mode(s)"), "fieldtype": "Data", "width": 140},
        {"fieldname": "grand_total", "label": _("Invoice Total"), "fieldtype": "Currency", "options": "currency", "width": 125},
        {"fieldname": "paid_amount", "label": _("Paid"), "fieldtype": "Currency", "options": "currency", "width": 115},
        {"fieldname": "outstanding_amount", "label": _("Outstanding"), "fieldtype": "Currency", "options": "currency", "width": 125},
        {"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "width": 90},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 110},
    ]
