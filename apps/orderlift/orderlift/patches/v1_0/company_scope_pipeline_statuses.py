from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint

from orderlift.menu_access import user_can_access_company
from orderlift.orderlift_crm.status_config import STATUS_COLOR_OPTIONS, STATUS_SOURCES
from orderlift.orderlift_crm.status_workflow import make_company_status_name


SALES_STAGE_CUSTOM_FIELDS = {
    "Sales Stage": [
        {
            "fieldname": "custom_display_label",
            "fieldtype": "Data",
            "label": "Display Label",
            "insert_after": "stage_name",
            "in_list_view": 1,
        },
        {
            "fieldname": "custom_company",
            "fieldtype": "Link",
            "label": "Company",
            "options": "Company",
            "insert_after": "custom_display_label",
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
    ]
}


def execute():
    if not frappe.db.exists("DocType", "Company"):
        return

    create_custom_fields(SALES_STAGE_CUSTOM_FIELDS, update=True)
    companies = _active_companies()
    if not companies:
        return

    for document_type, meta in STATUS_SOURCES.items():
        _clone_statuses_for_companies(document_type, meta, companies)

    _backfill_linked_document_statuses("Opportunity")
    _backfill_linked_document_statuses("Project")
    _backfill_linked_document_statuses("Sales Order")
    frappe.db.commit()


def _clone_statuses_for_companies(document_type: str, meta: dict, companies: list[str]) -> None:
    status_doctype = meta["status_doctype"]
    if not frappe.db.exists("DocType", status_doctype):
        return

    company_field = meta.get("company_field")
    display_label_field = meta.get("display_label_field")
    if not company_field or not _has_column(status_doctype, company_field):
        return

    source_rows = _source_status_rows(meta)
    if not source_rows:
        source_rows = meta.get("seeds") or []

    for company in companies:
        created_names = []
        for row in source_rows:
            display_label = _display_label(row, meta)
            if not display_label:
                continue
            target_name = make_company_status_name(company, display_label)
            values = _status_values(row, meta, company, display_label, target_name)
            existing = frappe.db.exists(status_doctype, target_name)
            if existing:
                _update_status(status_doctype, existing, values)
                created_names.append(existing)
                continue

            doc = frappe.new_doc(status_doctype)
            doc.set(meta["label_field"], target_name)
            if display_label_field and doc.meta.get_field(display_label_field):
                doc.set(display_label_field, display_label)
            doc.set(company_field, company)
            for fieldname, value in values.items():
                if fieldname not in {meta["label_field"], display_label_field, company_field} and doc.meta.get_field(fieldname):
                    doc.set(fieldname, value)
            doc.insert(ignore_permissions=True)
            created_names.append(doc.name)

        _ensure_one_default(meta, company, created_names)


def _source_status_rows(meta: dict) -> list[dict]:
    status_doctype = meta["status_doctype"]
    fields = ["name", meta["label_field"]]
    for fieldname in [
        meta.get("display_label_field"),
        meta.get("company_field"),
        meta.get("sequence_field"),
        meta.get("color_field"),
        meta.get("active_field"),
        meta.get("default_field"),
        meta.get("distribution_field"),
        meta.get("installation_field"),
        meta.get("assigned_user_field"),
        meta.get("todo_priority_field"),
        meta.get("auto_collapse_field"),
        meta.get("required_checks_field"),
        meta.get("confirmation_message_field"),
        meta.get("auto_close_opportunity_field"),
    ]:
        if fieldname and _has_column(status_doctype, fieldname) and fieldname not in fields:
            fields.append(fieldname)
    rows = frappe.get_all(status_doctype, fields=fields, order_by="modified asc", limit_page_length=0)
    company_field = meta.get("company_field")
    return [row for row in rows if not row.get(company_field)]


def _status_values(row: dict, meta: dict, company: str, display_label: str, target_name: str) -> dict:
    seed = _seed_row(meta, display_label)
    values = {
        meta["label_field"]: target_name,
        meta.get("display_label_field"): display_label,
        meta.get("company_field"): company,
        meta["sequence_field"]: cint(seed.get("sequence") or row.get(meta["sequence_field"]) or row.get("sequence") or 100),
        meta["color_field"]: seed.get("color") or row.get(meta["color_field"]) or row.get("color") or STATUS_COLOR_OPTIONS[1],
        meta["active_field"]: 1 if seed else cint(row.get(meta["active_field"]) if meta["active_field"] in row else row.get("is_active", 1)),
        meta["default_field"]: cint(seed.get("is_default") if seed else row.get(meta["default_field"]) if meta["default_field"] in row else row.get("is_default", 0)),
    }
    for key, fallback in [(meta.get("distribution_field"), "distribution"), (meta.get("installation_field"), "installation")]:
        if key:
            values[key] = cint(seed.get(fallback) if seed and fallback in seed else row.get(key) if key in row else row.get(fallback, 1))
    assigned_user_field = meta.get("assigned_user_field")
    if assigned_user_field:
        assigned_user = row.get(assigned_user_field) or ""
        values[assigned_user_field] = assigned_user if assigned_user and user_can_access_company(company, assigned_user) else ""
    for fieldname in [
        meta.get("todo_priority_field"),
        meta.get("auto_collapse_field"),
        meta.get("required_checks_field"),
        meta.get("confirmation_message_field"),
        meta.get("auto_close_opportunity_field"),
    ]:
        if fieldname:
            values[fieldname] = row.get(fieldname) if row.get(fieldname) is not None else ""
    return {fieldname: value for fieldname, value in values.items() if fieldname}


def _seed_row(meta: dict, label: str) -> dict:
    for row in meta.get("seeds") or []:
        if row.get("label") == label:
            return row
    return {}


def _update_status(status_doctype: str, name: str, values: dict) -> None:
    for fieldname, value in values.items():
        if _has_column(status_doctype, fieldname):
            frappe.db.set_value(status_doctype, name, fieldname, value, update_modified=False)


def _ensure_one_default(meta: dict, company: str, status_names: list[str]) -> None:
    if not status_names:
        return
    status_doctype = meta["status_doctype"]
    default_field = meta["default_field"]
    company_field = meta.get("company_field")
    if not _has_column(status_doctype, default_field) or not _has_column(status_doctype, company_field):
        return
    has_default = frappe.db.exists(status_doctype, {company_field: company, default_field: 1})
    if has_default:
        return
    frappe.db.set_value(status_doctype, status_names[0], default_field, 1, update_modified=False)


def _backfill_linked_document_statuses(document_type: str) -> None:
    meta = STATUS_SOURCES[document_type]
    target_doctype = meta["target_doctype"]
    target_field = meta["target_field"]
    if not _has_column(target_doctype, "company") or not _has_column(target_doctype, target_field):
        return
    label_map = _global_status_label_map(meta)
    rows = frappe.get_all(
        target_doctype,
        fields=["name", "company", target_field],
        limit_page_length=0,
    )
    for row in rows:
        current = row.get(target_field)
        company = row.get("company")
        if not current or not company:
            continue
        if current.startswith(f"{company} - "):
            continue
        display_label = label_map.get(current) or current
        next_status = make_company_status_name(company, display_label)
        if frappe.db.exists(meta["status_doctype"], next_status):
            frappe.db.set_value(target_doctype, row.name, target_field, next_status, update_modified=False)


def _global_status_label_map(meta: dict) -> dict[str, str]:
    return {
        row.get("name"): _display_label(row, meta)
        for row in _source_status_rows(meta)
        if row.get("name") and _display_label(row, meta)
    }


def _display_label(row: dict, meta: dict) -> str:
    if "label" in row:
        return row.get("label") or ""
    display_label_field = meta.get("display_label_field")
    label = row.get(display_label_field) if display_label_field else ""
    label = label or row.get(meta["label_field"]) or row.get("name") or ""
    company_field = meta.get("company_field")
    company = row.get(company_field) if company_field else ""
    prefix = f"{company} - "
    return label[len(prefix) :] if company and label.startswith(prefix) else label


def _active_companies() -> list[str]:
    filters = {"disabled": 0} if _has_column("Company", "disabled") else {}
    return frappe.get_all("Company", filters=filters, pluck="name", order_by="name asc", limit_page_length=0)


def _has_column(doctype: str, fieldname: str | None) -> bool:
    if not fieldname:
        return False
    try:
        return bool(frappe.db.has_column(doctype, fieldname))
    except Exception:
        return False
