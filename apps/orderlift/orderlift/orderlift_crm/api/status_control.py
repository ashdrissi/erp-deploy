from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc
from frappe.utils import cint

from orderlift.orderlift_crm.status_config import STATUS_COLOR_OPTIONS
from orderlift.orderlift_crm.status_workflow import (
    get_legacy_status_groups,
    get_status_meta,
    get_status_usage,
    list_editable_statuses,
)


@frappe.whitelist()
def get_status_control_data(document_type: str) -> dict:
    meta = get_status_meta(document_type)
    usage = get_status_usage(document_type)
    statuses = list_editable_statuses(document_type, include_inactive=True)
    for status in statuses:
        status["usage_count"] = usage.get(status["name"], 0)
    return {
        "document_type": document_type,
        "field_label": meta["field_label"],
        "page_title": meta["page_title"],
        "status_doctype": meta["status_doctype"],
        "colors": STATUS_COLOR_OPTIONS,
        "statuses": statuses,
        "legacy_statuses": get_legacy_status_groups(document_type),
    }


@frappe.whitelist()
def save_status(document_type: str, payload: str | dict) -> dict:
    data = _loads(payload)
    meta = get_status_meta(document_type)
    status_doctype = meta["status_doctype"]
    label_field = meta["label_field"]
    label = (data.get("label") or "").strip()
    if not label:
        frappe.throw(_("Status label is required."))

    current_name = (data.get("name") or "").strip()
    if current_name and not frappe.db.exists(status_doctype, current_name):
        frappe.throw(_("Status {0} was not found.").format(current_name))

    if current_name:
        doc = frappe.get_doc(status_doctype, current_name)
        if label != current_name:
            if frappe.db.exists(status_doctype, label):
                frappe.throw(_("Status {0} already exists.").format(label))
            renamed_name = rename_doc(status_doctype, current_name, label, force=False, merge=False)
            doc = frappe.get_doc(status_doctype, renamed_name)
    else:
        if frappe.db.exists(status_doctype, label):
            frappe.throw(_("Status {0} already exists.").format(label))
        doc = frappe.new_doc(status_doctype)

    setattr(doc, label_field, label)
    _set_if_field(doc, meta["sequence_field"], cint(data.get("sequence") or 100))
    _set_if_field(doc, meta["color_field"], data.get("color") or "Blue")
    _set_if_field(doc, meta["active_field"], cint(data.get("is_active", 1)))
    _set_if_field(doc, meta["default_field"], cint(data.get("is_default", 0)))
    _set_if_field(doc, meta["distribution_field"], cint(data.get("applies_distribution", 1)))
    _set_if_field(doc, meta["installation_field"], cint(data.get("applies_installation", 1)))

    if doc.is_new():
        doc.insert(ignore_permissions=False)
    else:
        doc.save(ignore_permissions=False)

    if cint(data.get("is_default", 0)):
        _clear_default_flag(document_type, doc.name)

    _validate_status_safety(document_type)

    frappe.db.commit()
    return get_status_control_data(document_type)


@frappe.whitelist()
def delete_status(document_type: str, status_name: str) -> dict:
    meta = get_status_meta(document_type)
    status_doctype = meta["status_doctype"]
    if not frappe.db.exists(status_doctype, status_name):
        frappe.throw(_("Status {0} was not found.").format(status_name))

    usage = get_status_usage(document_type).get(status_name, 0)
    if usage:
        frappe.throw(_("Status {0} is already used on {1} documents and cannot be deleted.").format(status_name, usage))

    doc = frappe.get_doc(status_doctype, status_name)
    if _field_value(doc, meta["default_field"]):
        frappe.throw(_("Unset the default flag before deleting {0}.").format(status_name))

    doc.delete(ignore_permissions=False)
    _validate_status_safety(document_type)
    frappe.db.commit()
    return get_status_control_data(document_type)


def _clear_default_flag(document_type: str, keep_name: str):
    meta = get_status_meta(document_type)
    status_meta = frappe.get_meta(meta["status_doctype"])
    default_field = meta["default_field"]
    if not status_meta.get_field(default_field):
        return
    for row in frappe.get_all(meta["status_doctype"], fields=["name", default_field], limit_page_length=0):
        if row.name == keep_name or not cint(row.get(default_field)):
            continue
        doc = frappe.get_doc(meta["status_doctype"], row.name)
        setattr(doc, default_field, 0)
        doc.save(ignore_permissions=True)


def _validate_status_safety(document_type: str) -> None:
    statuses = list_editable_statuses(document_type, include_inactive=True)
    active = [status for status in statuses if cint(status.get("is_active"))]
    if not active:
        frappe.throw(_("At least one active status is required for {0}.").format(document_type))
    if not [status for status in active if cint(status.get("is_default"))]:
        frappe.throw(_("At least one active default status is required for {0}.").format(document_type))


def _set_if_field(doc, fieldname: str, value):
    if doc.meta.get_field(fieldname):
        doc.set(fieldname, value)


def _field_value(doc, fieldname: str):
    if not doc.meta.get_field(fieldname):
        return None
    return doc.get(fieldname)


def _loads(payload: str | dict) -> dict:
    if isinstance(payload, str):
        return json.loads(payload or "{}")
    return payload or {}
