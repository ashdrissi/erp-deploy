from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc
from frappe.utils import cint

from orderlift.menu_access import get_company_access_payload, user_can_access_company
from orderlift.orderlift_crm.status_config import STATUS_COLOR_OPTIONS
from orderlift.orderlift_crm.status_checks import get_predefined_status_checks
from orderlift.orderlift_crm.todo_priority import TODO_PRIORITY_OPTIONS, normalize_todo_priority
from orderlift.orderlift_crm.status_workflow import (
    get_legacy_status_groups,
    get_status_meta,
    get_status_usage,
    list_editable_statuses,
    make_company_status_name,
)


@frappe.whitelist()
def get_status_control_data(document_type: str, company: str | None = None) -> dict:
    meta = get_status_meta(document_type)
    company_context = _status_company_context(company)
    selected_company = company_context["selected_company"]
    usage = get_status_usage(document_type, company=selected_company) if selected_company else {}
    statuses = (
        list_editable_statuses(document_type, include_inactive=True, company=selected_company)
        if selected_company
        else []
    )
    users = _enabled_users(selected_company)
    user_labels = {user["name"]: user["label"] for user in users}
    for status in statuses:
        status["usage_count"] = usage.get(status["name"], 0)
        status["assigned_user_label"] = user_labels.get(status.get("assigned_user"), status.get("assigned_user") or "")
    return {
        "document_type": document_type,
        "companies": company_context["companies"],
        "selected_company": selected_company,
        "company_required": not bool(selected_company),
        "field_label": meta["field_label"],
        "page_title": meta["page_title"],
        "status_doctype": meta["status_doctype"],
        "colors": STATUS_COLOR_OPTIONS,
        "todo_priorities": TODO_PRIORITY_OPTIONS,
        "show_flow_fields": meta.get("show_flow_fields", True),
        "allow_create": meta.get("allow_create", True),
        "allow_delete": meta.get("allow_delete", True),
        "allow_rename": meta.get("allow_rename", True),
        "show_auto_close_opportunity": bool(meta.get("auto_close_opportunity_field")),
        "users": users,
        "statuses": statuses,
        "predefined_checks": get_predefined_status_checks(document_type),
        "legacy_statuses": get_legacy_status_groups(document_type),
    }


@frappe.whitelist()
def save_status(document_type: str, payload: str | dict, company: str | None = None) -> dict:
    data = _loads(payload)
    meta = get_status_meta(document_type)
    status_doctype = meta["status_doctype"]
    label_field = meta["label_field"]
    company = _require_status_company(data.get("company") or company)
    label = (data.get("label") or "").strip()
    if not label:
        frappe.throw(_("Status label is required."))
    internal_label = make_company_status_name(company, label) if meta.get("company_field") else label
    status_value = label if meta.get("fixed_status_values") else internal_label

    current_name = (data.get("docname") or data.get("name") or "").strip()
    if current_name and not frappe.db.exists(status_doctype, current_name):
        frappe.throw(_("Status {0} was not found.").format(current_name))

    if current_name:
        doc = frappe.get_doc(status_doctype, current_name)
        _ensure_doc_company(doc, meta, company)
        if not meta.get("fixed_status_values") and status_value != current_name:
            if not meta.get("allow_rename", True):
                frappe.throw(_("Status {0} cannot be renamed.").format(current_name))
            if frappe.db.exists(status_doctype, internal_label):
                frappe.throw(_("Status {0} already exists for {1}.").format(label, company))
            renamed_name = rename_doc(status_doctype, current_name, internal_label, force=False, merge=False)
            doc = frappe.get_doc(status_doctype, renamed_name)
    else:
        if not meta.get("allow_create", True):
            frappe.throw(_("New statuses cannot be created for {0}.").format(document_type))
        if frappe.db.exists(status_doctype, internal_label):
            frappe.throw(_("Status {0} already exists for {1}.").format(label, company))
        doc = frappe.new_doc(status_doctype)

    setattr(doc, label_field, internal_label)
    _set_if_field(doc, meta.get("display_label_field"), label)
    _set_if_field(doc, meta.get("company_field"), company)
    _set_if_field(doc, meta["sequence_field"], cint(data.get("sequence") or 100))
    _set_if_field(doc, meta["color_field"], data.get("color") or "Blue")
    _set_if_field(doc, meta["active_field"], cint(data.get("is_active", 1)))
    _set_if_field(doc, meta["default_field"], cint(data.get("is_default", 0)))
    _set_if_field(doc, meta.get("distribution_field"), cint(data.get("applies_distribution", 1)))
    _set_if_field(doc, meta.get("installation_field"), cint(data.get("applies_installation", 1)))
    assigned_user = (data.get("assigned_user") or "").strip()
    if assigned_user:
        _validate_enabled_user(assigned_user, company=company)
    assigned_user_field = meta.get("assigned_user_field")
    _set_if_field(doc, assigned_user_field, assigned_user)
    todo_priority = normalize_todo_priority(data.get("todo_priority"))
    _set_if_field(doc, meta.get("todo_priority_field"), todo_priority)
    auto_collapse = cint(data.get("auto_collapse", 0))
    _set_if_field(doc, meta.get("auto_collapse_field"), auto_collapse)
    required_checks = _validate_required_checks(document_type, data.get("required_checks") or [])
    _set_if_field(doc, meta.get("required_checks_field"), json.dumps(required_checks))
    confirmation_message = (data.get("confirmation_message") or "").strip()
    _set_if_field(doc, meta.get("confirmation_message_field"), confirmation_message)
    auto_close_opportunity = cint(data.get("auto_close_opportunity", 0))
    _set_if_field(doc, meta.get("auto_close_opportunity_field"), auto_close_opportunity)

    if doc.is_new():
        doc.insert(ignore_permissions=False)
    else:
        doc.save(ignore_permissions=False)
    _set_db_column_if_available(status_doctype, doc.name, assigned_user_field, assigned_user)
    _set_db_column_if_available(status_doctype, doc.name, meta.get("todo_priority_field"), todo_priority)
    _set_db_column_if_available(status_doctype, doc.name, meta.get("auto_collapse_field"), auto_collapse)
    _set_db_column_if_available(status_doctype, doc.name, meta.get("confirmation_message_field"), confirmation_message)
    _set_db_column_if_available(
        status_doctype,
        doc.name,
        meta.get("auto_close_opportunity_field"),
        auto_close_opportunity,
    )
    _set_db_column_if_available(status_doctype, doc.name, meta.get("display_label_field"), label)
    _set_db_column_if_available(status_doctype, doc.name, meta.get("company_field"), company)

    if cint(data.get("is_default", 0)):
        _clear_default_flag(document_type, doc.name, company)

    _validate_status_safety(document_type, company)

    frappe.db.commit()
    return get_status_control_data(document_type, company=company)


@frappe.whitelist()
def delete_status(document_type: str, status_name: str, company: str | None = None) -> dict:
    meta = get_status_meta(document_type)
    status_doctype = meta["status_doctype"]
    company = _require_status_company(company)
    if not meta.get("allow_delete", True):
        frappe.throw(_("Statuses cannot be deleted for {0}.").format(document_type))
    if not frappe.db.exists(status_doctype, status_name):
        frappe.throw(_("Status {0} was not found.").format(status_name))

    doc = frappe.get_doc(status_doctype, status_name)
    _ensure_doc_company(doc, meta, company)
    usage = get_status_usage(document_type, company=company).get(status_name, 0)
    if usage:
        frappe.throw(_("Status {0} is already used on {1} documents and cannot be deleted.").format(status_name, usage))

    if _field_value(doc, meta["default_field"]):
        frappe.throw(_("Unset the default flag before deleting {0}.").format(status_name))

    doc.delete(ignore_permissions=False)
    _validate_status_safety(document_type, company)
    frappe.db.commit()
    return get_status_control_data(document_type, company=company)


def _clear_default_flag(document_type: str, keep_name: str, company: str):
    meta = get_status_meta(document_type)
    status_meta = frappe.get_meta(meta["status_doctype"])
    default_field = meta["default_field"]
    if not status_meta.get_field(default_field):
        return
    filters = {}
    company_field = meta.get("company_field")
    if company_field and status_meta.get_field(company_field):
        filters[company_field] = company
    for row in frappe.get_all(meta["status_doctype"], filters=filters, fields=["name", default_field], limit_page_length=0):
        if row.name == keep_name or not cint(row.get(default_field)):
            continue
        doc = frappe.get_doc(meta["status_doctype"], row.name)
        setattr(doc, default_field, 0)
        doc.save(ignore_permissions=True)


def _validate_status_safety(document_type: str, company: str) -> None:
    statuses = list_editable_statuses(document_type, include_inactive=True, company=company)
    active = [status for status in statuses if cint(status.get("is_active"))]
    if not active:
        frappe.throw(_("At least one active status is required for {0}.").format(document_type))
    if not [status for status in active if cint(status.get("is_default"))]:
        frappe.throw(_("At least one active default status is required for {0}.").format(document_type))


def _enabled_users(company: str | None = None) -> list[dict]:
    rows = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name"],
        order_by="full_name asc, name asc",
        limit_page_length=0,
    )
    users = []
    for row in rows:
        if company and not user_can_access_company(company, user=row.name):
            continue
        users.append({"name": row.name, "label": row.full_name or row.name})
    return users


def _validate_enabled_user(user: str, company: str | None = None) -> None:
    if not frappe.db.exists("User", user):
        frappe.throw(_("User {0} was not found.").format(user))
    if not cint(frappe.db.get_value("User", user, "enabled")):
        frappe.throw(_("User {0} is disabled.").format(user))
    if company and not user_can_access_company(company, user=user):
        frappe.throw(_("User {0} cannot access company {1}.").format(user, company))


def _status_company_context(company: str | None = None) -> dict:
    payload = get_company_access_payload(requested_company=company)
    companies = payload.get("companies") or []
    selected_company = payload.get("current_company") or ""
    if selected_company and selected_company not in companies and user_can_access_company(selected_company):
        companies = [selected_company, *companies]
    return {"companies": companies, "selected_company": selected_company}


def _require_status_company(company: str | None) -> str:
    company = (company or "").strip()
    if not company:
        frappe.throw(_("Select a company before editing statuses."))
    if not user_can_access_company(company):
        frappe.throw(_("You do not have access to company {0}.").format(company))
    return company


def _ensure_doc_company(doc, meta: dict, company: str) -> None:
    company_field = meta.get("company_field")
    if not company_field or not doc.meta.get_field(company_field):
        return
    current_company = doc.get(company_field)
    if current_company and current_company != company:
        frappe.throw(_("Status {0} belongs to company {1}.").format(doc.name, current_company))


def _validate_required_checks(document_type: str, checks) -> list[str]:
    if not checks:
        return []
    allowed = {check["key"] for check in get_predefined_status_checks(document_type)}
    if not allowed:
        return []
    clean_checks = []
    for check in checks:
        check = (check or "").strip()
        if not check:
            continue
        if check not in allowed:
            frappe.throw(_("Unsupported required check: {0}").format(check))
        if check not in clean_checks:
            clean_checks.append(check)
    return clean_checks


def _set_if_field(doc, fieldname: str | None, value):
    if not fieldname:
        return
    if doc.meta.get_field(fieldname):
        doc.set(fieldname, value)


def _set_db_column_if_available(doctype: str, name: str, fieldname: str | None, value) -> None:
    if not fieldname:
        return
    has_column = getattr(frappe.db, "has_column", None)
    if not has_column or not has_column(doctype, fieldname):
        return
    frappe.db.set_value(doctype, name, fieldname, value if value not in ("", None) else None, update_modified=False)


def _field_value(doc, fieldname: str):
    if not doc.meta.get_field(fieldname):
        return None
    return doc.get(fieldname)


def _loads(payload: str | dict) -> dict:
    if isinstance(payload, str):
        return json.loads(payload or "{}")
    return payload or {}
