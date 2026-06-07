from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import get_allowed_companies, user_can_access_company
from orderlift.orderlift_crm.status_config import STATUS_SOURCES, UNASSIGNED_STATUS
from orderlift.orderlift_crm.todo_priority import normalize_todo_priority


def get_status_meta(document_type: str) -> dict:
    if document_type not in STATUS_SOURCES:
        frappe.throw(_("Unsupported status document type: {0}").format(document_type))
    return STATUS_SOURCES[document_type]


def list_editable_statuses(
    document_type: str,
    include_inactive: bool = False,
    company: str | None = None,
) -> list[dict]:
    meta = get_status_meta(document_type)
    status_doctype = meta["status_doctype"]
    status_meta = frappe.get_meta(status_doctype)
    fields = ["name", meta["label_field"]]
    optional_fields = [
        meta.get("display_label_field"),
        meta.get("company_field"),
        meta["sequence_field"],
        meta["color_field"],
        meta["active_field"],
        meta["default_field"],
        meta.get("distribution_field"),
        meta.get("installation_field"),
        meta.get("assigned_user_field"),
        meta.get("todo_priority_field"),
        meta.get("auto_collapse_field"),
        meta.get("required_checks_field"),
        meta.get("confirmation_message_field"),
        meta.get("auto_close_opportunity_field"),
    ]
    for fieldname in optional_fields:
        if not fieldname:
            continue
        if fieldname not in fields and _status_field_available(status_doctype, status_meta, fieldname):
            fields.append(fieldname)

    filters = {}
    if not include_inactive and status_meta.get_field(meta["active_field"]):
        filters[meta["active_field"]] = 1
    company_field = meta.get("company_field")
    if company and company_field and _status_field_available(status_doctype, status_meta, company_field):
        filters[company_field] = company

    order_fields = []
    if status_meta.get_field(meta["sequence_field"]):
        order_fields.append(f"{meta['sequence_field']} asc")
    if company_field and _status_field_available(status_doctype, status_meta, company_field):
        order_fields.append(f"{company_field} asc")
    order_fields.append(f"{meta['label_field']} asc")
    rows = frappe.get_all(
        status_doctype,
        filters=filters,
        fields=fields,
        order_by=", ".join(order_fields),
        limit_page_length=0,
    )
    statuses = []
    assigned_user_field = meta.get("assigned_user_field")
    todo_priority_field = meta.get("todo_priority_field")
    auto_collapse_field = meta.get("auto_collapse_field")
    required_checks_field = meta.get("required_checks_field")
    confirmation_message_field = meta.get("confirmation_message_field")
    auto_close_opportunity_field = meta.get("auto_close_opportunity_field")
    display_label_field = meta.get("display_label_field")
    fixed_status_values = bool(meta.get("fixed_status_values"))
    for row in rows:
        distribution_field = meta.get("distribution_field")
        installation_field = meta.get("installation_field")
        raw_label = row.get(meta["label_field"]) or row.name
        display_label = row.get(display_label_field) if display_label_field and display_label_field in row else ""
        label = display_label or _strip_company_status_prefix(raw_label, row.get(company_field) if company_field in row else "")
        status_name = label if fixed_status_values else row.name
        statuses.append(
            {
                "name": status_name,
                "docname": row.name,
                "label": label,
                "company": row.get(company_field) if company_field and company_field in row else "",
                "sequence": cint(row.get(meta["sequence_field"]) or 100),
                "color": row.get(meta["color_field"]) or "Blue",
                "is_active": cint(row.get(meta["active_field"]) if meta["active_field"] in row else 1),
                "is_default": cint(row.get(meta["default_field"]) if meta["default_field"] in row else 0),
                "applies_distribution": cint(
                    row.get(distribution_field) if distribution_field and distribution_field in row else 1
                ),
                "applies_installation": cint(
                    row.get(installation_field) if installation_field and installation_field in row else 1
                ),
                "assigned_user": row.get(assigned_user_field) if assigned_user_field and assigned_user_field in row else "",
                "todo_priority": normalize_todo_priority(
                    row.get(todo_priority_field) if todo_priority_field and todo_priority_field in row else ""
                ),
                "auto_collapse": cint(
                    row.get(auto_collapse_field) if auto_collapse_field and auto_collapse_field in row else 0
                ),
                "required_checks": _parse_required_checks(
                    row.get(required_checks_field) if required_checks_field and required_checks_field in row else ""
                ),
                "confirmation_message": (
                    row.get(confirmation_message_field)
                    if confirmation_message_field and confirmation_message_field in row
                    else ""
                )
                or "",
                "auto_close_opportunity": cint(
                    row.get(auto_close_opportunity_field)
                    if auto_close_opportunity_field and auto_close_opportunity_field in row
                    else 0
                ),
            }
        )
    return statuses


def _parse_required_checks(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(check) for check in value if check]
    try:
        data = json.loads(value)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(check) for check in data if check]


def _status_field_available(status_doctype: str, status_meta, fieldname: str) -> bool:
    if status_meta.get_field(fieldname):
        return True
    has_column = getattr(frappe.db, "has_column", None)
    return bool(has_column and has_column(status_doctype, fieldname))


def get_default_status_name(document_type: str, company: str | None = None) -> str | None:
    statuses = list_editable_statuses(document_type, include_inactive=False, company=company)
    for status in statuses:
        if status["is_default"]:
            return status["name"]
    return statuses[0]["name"] if statuses else None


def get_status_usage(document_type: str, company: str | None = None) -> dict[str, int]:
    meta = get_status_meta(document_type)
    target_doctype = meta["target_doctype"]
    target_field = meta["target_field"]
    if not frappe.get_meta(target_doctype).get_field(target_field):
        return {}
    where = [f"COALESCE({target_field}, '') != ''"]
    params = []
    if company and frappe.get_meta(target_doctype).get_field("company"):
        where.append("company = %s")
        params.append(company)
    rows = frappe.db.sql(
        f"""
        SELECT {target_field} AS status_name, COUNT(*) AS status_count
        FROM `tab{target_doctype}`
        WHERE {' AND '.join(where)}
        GROUP BY {target_field}
        """,
        tuple(params),
        as_dict=True,
    )
    return {row.status_name: cint(row.status_count) for row in rows}


def get_legacy_status_groups(document_type: str) -> list[dict]:
    meta = get_status_meta(document_type)
    document_meta = frappe.get_meta(document_type)
    legacy_groups = []
    legacy_fieldname = meta.get("legacy_field")
    legacy_field = document_meta.get_field(legacy_fieldname) if legacy_fieldname else None
    if legacy_field and getattr(legacy_field, "options", None):
        values = [value for value in (legacy_field.options or "").split("\n") if value]
        legacy_groups.append({"label": meta["legacy_label"], "values": values})
    legacy_groups.append({"label": _("Docstatus"), "values": ["Draft", "Submitted", "Cancelled"]})
    return legacy_groups


def resolve_status_column(
    document_type: str,
    primary_status: str | None,
    legacy_status: str | None = None,
    statuses: list[dict] | None = None,
) -> str:
    statuses = statuses or list_editable_statuses(document_type, include_inactive=False)
    active_names = {status["name"] for status in statuses if status.get("is_active")}
    if primary_status in active_names:
        return primary_status
    if legacy_status in active_names:
        return legacy_status
    return UNASSIGNED_STATUS


def ensure_primary_status(doc, method=None):
    if doc.doctype not in STATUS_SOURCES:
        return
    meta = get_status_meta(doc.doctype)
    target_field = meta["target_field"]
    if not doc.meta.get_field(target_field):
        return
    if doc.get(target_field):
        return
    try:
        default_name = get_default_status_name(doc.doctype, company=doc.get("company"))
    except TypeError:
        default_name = get_default_status_name(doc.doctype)
    if default_name:
        doc.set(target_field, default_name)


def make_company_status_name(company: str | None, label: str) -> str:
    label = (label or "").strip()
    company = (company or "").strip()
    return f"{company} - {label}" if company else label


def can_access_status_company(company: str | None, user: str | None = None) -> bool:
    company = (company or "").strip()
    if not company:
        return False
    return user_can_access_company(company, user=user)


def first_allowed_company(user: str | None = None) -> str:
    companies = get_allowed_companies(user)
    return companies[0] if companies else ""


def _strip_company_status_prefix(label: str, company: str | None) -> str:
    company = (company or "").strip()
    prefix = f"{company} - "
    if company and label.startswith(prefix):
        return label[len(prefix) :]
    return label
