from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import resolve_current_company


TECHNICAL_LIST_DOCTYPE = "Sales Order Technical List"
REVISION_DOCTYPE = "Sales Order Technical List Revision"
DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 100


@frappe.whitelist()
def get_manager_data(
    search="",
    project="",
    customer="",
    business_type="",
    presence="",
    docstatus="",
    workflow_state="",
    annex_readiness="",
    procurement_readiness="",
    page=1,
    page_length=DEFAULT_PAGE_LENGTH,
):
    company = (resolve_current_company(user=frappe.session.user) or "").strip()
    if not company:
        frappe.throw(_("Select an active company before opening Technical Lists."))

    page = max(cint(page), 1)
    page_length = min(max(cint(page_length) or DEFAULT_PAGE_LENGTH, 1), MAX_PAGE_LENGTH)
    sales_orders = _get_sales_orders(
        company=company,
        search=search,
        project=project,
        customer=customer,
        business_type=business_type,
    )

    # Sales Order is the permission-filtered anchor. Parent and revision queries
    # are limited to records referenced by this readable, company-scoped set.
    technical_lists = _get_technical_lists([row.name for row in sales_orders])
    revisions = _get_revisions(technical_lists.values())
    rows = [
        _serialize_row(row, technical_lists.get(row.name), revisions)
        for row in sales_orders
    ]
    filter_options = _filter_options(sales_orders, rows)
    rows = _apply_related_filters(
        rows,
        presence=presence,
        docstatus=docstatus,
        workflow_state=workflow_state,
        annex_readiness=annex_readiness,
        procurement_readiness=procurement_readiness,
    )

    total = len(rows)
    page_count = max((total + page_length - 1) // page_length, 1)
    page = min(page, page_count)
    start = (page - 1) * page_length
    page_rows = rows[start : start + page_length]
    _attach_permission_safe_actions(page_rows)

    return {
        "rows": page_rows,
        "kpis": _kpis(rows),
        "filters": filter_options,
        "pagination": {
            "page": page,
            "page_length": page_length,
            "total": total,
            "page_count": page_count,
        },
        "current_company": company,
        "technical_list_available": _doctype_exists(TECHNICAL_LIST_DOCTYPE)
        and _doctype_exists(REVISION_DOCTYPE),
    }


@frappe.whitelist()
def create_for_sales_order(sales_order):
    sales_order = (sales_order or "").strip()
    if not sales_order:
        frappe.throw(_("Sales Order is required."))

    company = (resolve_current_company(user=frappe.session.user) or "").strip()
    if not company:
        frappe.throw(_("Select an active company before creating a Technical List."))
    readable = frappe.get_list(
        "Sales Order",
        filters={"name": sales_order, "company": company, "docstatus": 1},
        fields=["name"],
        limit_page_length=1,
    )
    if not readable:
        frappe.throw(_("You cannot create a Technical List for this Sales Order."), frappe.PermissionError)

    from orderlift.orderlift_sig.technical_list import create_for_sales_order as create_technical_list

    result = create_technical_list(sales_order)
    return {"result": result, "route": _route_for_created_result(result)}


def _get_sales_orders(company, search="", project="", customer="", business_type=""):
    meta = frappe.get_meta("Sales Order")
    fieldnames = {field.fieldname for field in meta.fields}
    filters: list[list[Any]] = [
        ["Sales Order", "docstatus", "=", 1],
        ["Sales Order", "company", "=", company],
    ]
    _append_direct_filter(filters, fieldnames, "project", project)
    _append_direct_filter(filters, fieldnames, "customer", customer)
    _append_direct_filter(filters, fieldnames, "custom_crm_business_type", business_type)

    search = (search or "").strip()
    or_filters = []
    if search:
        for fieldname in ("name", "customer", "customer_name", "project", "po_no", "custom_deal_abbreviation"):
            if fieldname == "name" or fieldname in fieldnames:
                or_filters.append(["Sales Order", fieldname, "like", f"%{search}%"])

    fields = ["name", "company", "customer", "project", "transaction_date", "delivery_date", "modified"]
    fields.extend(
        fieldname
        for fieldname in (
            "customer_name",
            "status",
            "workflow_state",
            "custom_crm_business_type",
            "custom_deal_abbreviation",
        )
        if fieldname in fieldnames
    )
    rows = frappe.get_list(
        "Sales Order",
        filters=filters,
        or_filters=or_filters or None,
        fields=fields,
        order_by="modified desc",
        limit_page_length=0,
    )
    from orderlift.orderlift_sig.technical_list import _company_eligibility

    return [row for row in rows if _company_eligibility(row)[0]]


def _append_direct_filter(filters, fieldnames, fieldname, value):
    value = (value or "").strip()
    if value and value != "All" and fieldname in fieldnames:
        filters.append(["Sales Order", fieldname, "=", value])


def _get_technical_lists(sales_order_names):
    if not sales_order_names or not _doctype_exists(TECHNICAL_LIST_DOCTYPE):
        return {}
    rows = frappe.get_list(
        TECHNICAL_LIST_DOCTYPE,
        filters={"sales_order": ["in", sales_order_names]},
        fields=[
            "name",
            "sales_order",
            "current_revision",
            "open_revision",
            "status",
            "required_annex_count",
            "completed_annex_count",
            "is_ready",
            "readiness_summary",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=0,
    )
    return {row.sales_order: row for row in rows}


def _get_revisions(technical_lists):
    if not _doctype_exists(REVISION_DOCTYPE):
        return {}
    revision_names = {
        name
        for row in technical_lists
        for name in (row.open_revision, row.current_revision)
        if name
    }
    if not revision_names:
        return {}
    rows = frappe.get_list(
        REVISION_DOCTYPE,
        filters={"name": ["in", list(revision_names)]},
        fields=[
            "name",
            "technical_list",
            "revision_no",
            "workflow_state",
            "docstatus",
            "is_ready",
            "required_annex_count",
            "completed_annex_count",
            "readiness_summary",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=0,
    )
    return {row.name: row for row in rows}


def _serialize_row(sales_order, technical_list, revisions):
    selected_name = ""
    revision_kind = ""
    if technical_list:
        selected_name = technical_list.open_revision or technical_list.current_revision or ""
        revision_kind = "Open" if technical_list.open_revision else ("Current" if technical_list.current_revision else "")
    revision = revisions.get(selected_name)
    annex = _annex_readiness(revision or technical_list)
    procurement = _procurement_readiness(technical_list, revision, selected_name)
    return {
        "sales_order": sales_order.name,
        "customer": sales_order.get("customer") or "",
        "customer_name": sales_order.get("customer_name") or sales_order.get("customer") or "",
        "project": sales_order.get("project") or "",
        "business_type": sales_order.get("custom_crm_business_type") or "",
        "deal_abbreviation": sales_order.get("custom_deal_abbreviation") or "",
        "order_status": sales_order.get("status") or sales_order.get("workflow_state") or "",
        "transaction_date": sales_order.get("transaction_date"),
        "delivery_date": sales_order.get("delivery_date"),
        "technical_list": technical_list.name if technical_list else "",
        "current_revision": technical_list.current_revision if technical_list else "",
        "open_revision": technical_list.open_revision if technical_list else "",
        "revision": revision.name if revision else "",
        "revision_no": cint(revision.revision_no) if revision else None,
        "revision_kind": revision_kind if revision else "",
        "revision_docstatus": cint(revision.docstatus) if revision else None,
        "workflow_state": revision.workflow_state if revision else "",
        "annex_readiness": annex,
        "procurement_readiness": procurement,
        "readiness_summary": annex["summary"],
        "modified": revision.modified if revision else (technical_list.modified if technical_list else sales_order.modified),
        "available_transitions": [],
        "actions": {},
        "routes": {},
    }


def _annex_readiness(source):
    if not source:
        return {
            "value": "",
            "label": _("Not available"),
            "is_ready": None,
            "required": 0,
            "completed": 0,
            "summary": "",
        }
    required = cint(source.get("required_annex_count"))
    completed = cint(source.get("completed_annex_count"))
    ready = bool(cint(source.get("is_ready")))
    return {
        "value": "1" if ready else "0",
        "label": _("{0}/{1} ready").format(completed, required),
        "is_ready": ready,
        "required": required,
        "completed": completed,
        "summary": source.get("readiness_summary") or "",
    }


def _procurement_readiness(technical_list, revision, selected_name):
    ready = bool(
        technical_list
        and technical_list.current_revision
        and selected_name == technical_list.current_revision
        and revision
        and cint(revision.docstatus) == 1
    )
    return {
        "value": "1" if ready else "0",
        "label": _("Ready") if ready else _("Not ready"),
        "is_ready": ready,
    }


def _apply_related_filters(
    rows,
    presence="",
    docstatus="",
    workflow_state="",
    annex_readiness="",
    procurement_readiness="",
):
    presence = (presence or "").strip().lower()
    docstatus = (docstatus or "").strip()
    workflow_state = (workflow_state or "").strip()
    annex_readiness = (annex_readiness or "").strip()
    procurement_readiness = (procurement_readiness or "").strip()

    def matches(row):
        if presence == "present" and not row["technical_list"]:
            return False
        if presence == "missing" and row["technical_list"]:
            return False
        if docstatus and str(row["revision_docstatus"]) != docstatus:
            return False
        if workflow_state and row["workflow_state"] != workflow_state:
            return False
        if annex_readiness and row["annex_readiness"]["value"] != annex_readiness:
            return False
        if procurement_readiness and row["procurement_readiness"]["value"] != procurement_readiness:
            return False
        return True

    return [row for row in rows if matches(row)]


def _filter_options(sales_orders, rows):
    readiness_options = [
        {"value": "1", "label": _("Ready")},
        {"value": "0", "label": _("Not ready")},
    ]
    return {
        "projects": _unique(row.get("project") for row in sales_orders),
        "customers": _unique(row.get("customer") for row in sales_orders),
        "business_types": _unique(row.get("custom_crm_business_type") for row in sales_orders),
        "docstatuses": [
            {"value": "0", "label": _("Draft")},
            {"value": "1", "label": _("Submitted")},
        ],
        "workflow_states": _unique(row["workflow_state"] for row in rows),
        "annex_readiness": readiness_options,
        "procurement_readiness": readiness_options,
    }


def _kpis(rows):
    return {
        "sales_orders": len(rows),
        "missing_lists": sum(not row["technical_list"] for row in rows),
        "open_revisions": sum(bool(row["open_revision"]) for row in rows),
        "procurement_ready": sum(row["procurement_readiness"]["is_ready"] for row in rows),
    }


def _attach_permission_safe_actions(rows):
    project_names = _unique(row["project"] for row in rows)
    readable_projects = set()
    if project_names:
        readable_projects = set(
            frappe.get_list(
                "Project",
                filters={"name": ["in", project_names]},
                pluck="name",
                limit_page_length=0,
            )
        )
    can_create = _has_permission(TECHNICAL_LIST_DOCTYPE, "create")
    for row in rows:
        row["actions"] = {
            "can_create": bool(can_create and not row["technical_list"]),
            "can_open_revision": bool(row["revision"]),
            "can_open_sales_order": True,
            "can_open_project": bool(row["project"] and row["project"] in readable_projects),
        }
        row["routes"] = {
            "sales_order": ["Form", "Sales Order", row["sales_order"]],
            "project": ["Form", "Project", row["project"]] if row["actions"]["can_open_project"] else [],
            "revision": ["Form", REVISION_DOCTYPE, row["revision"]] if row["revision"] else [],
        }
        if row["revision"]:
            row["available_transitions"] = _available_transitions(row["revision"])


def _available_transitions(revision_name):
    workflow = frappe.db.get_value(
        "Workflow",
        {"document_type": REVISION_DOCTYPE, "is_active": 1},
        "name",
    )
    if not workflow:
        return []
    try:
        from frappe.model.workflow import get_transitions

        doc = frappe.get_doc(REVISION_DOCTYPE, revision_name)
        doc.check_permission("read")
        transitions = get_transitions(doc) or []
        return [
            transition.get("action") if hasattr(transition, "get") else getattr(transition, "action", "")
            for transition in transitions
            if (transition.get("action") if hasattr(transition, "get") else getattr(transition, "action", ""))
        ]
    except Exception:
        return []


def _route_for_created_result(result):
    if not isinstance(result, dict):
        return []
    revision = result.get("revision")
    if isinstance(revision, dict) and revision.get("name"):
        return ["Form", REVISION_DOCTYPE, revision["name"]]
    if result.get("name"):
        return ["Form", TECHNICAL_LIST_DOCTYPE, result["name"]]
    return []


def _doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _unique(values):
    return sorted({str(value).strip() for value in values if value and str(value).strip()})


def _has_permission(doctype, ptype):
    try:
        return bool(frappe.has_permission(doctype, ptype=ptype))
    except Exception:
        return False
