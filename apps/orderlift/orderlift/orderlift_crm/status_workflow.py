from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.orderlift_crm.status_config import STATUS_SOURCES, UNASSIGNED_STATUS


def get_status_meta(document_type: str) -> dict:
    if document_type not in STATUS_SOURCES:
        frappe.throw(_("Unsupported status document type: {0}").format(document_type))
    return STATUS_SOURCES[document_type]


def list_editable_statuses(document_type: str, include_inactive: bool = False) -> list[dict]:
    meta = get_status_meta(document_type)
    status_doctype = meta["status_doctype"]
    status_meta = frappe.get_meta(status_doctype)
    fields = ["name", meta["label_field"]]
    optional_fields = [
        meta["sequence_field"],
        meta["color_field"],
        meta["active_field"],
        meta["default_field"],
        meta["distribution_field"],
        meta["installation_field"],
    ]
    for fieldname in optional_fields:
        if fieldname not in fields and status_meta.get_field(fieldname):
            fields.append(fieldname)

    filters = {}
    if not include_inactive and status_meta.get_field(meta["active_field"]):
        filters[meta["active_field"]] = 1

    order_fields = []
    if status_meta.get_field(meta["sequence_field"]):
        order_fields.append(f"{meta['sequence_field']} asc")
    order_fields.append(f"{meta['label_field']} asc")
    rows = frappe.get_all(
        status_doctype,
        filters=filters,
        fields=fields,
        order_by=", ".join(order_fields),
        limit_page_length=0,
    )
    statuses = []
    for row in rows:
        statuses.append(
            {
                "name": row.name,
                "label": row.get(meta["label_field"]) or row.name,
                "sequence": cint(row.get(meta["sequence_field"]) or 100),
                "color": row.get(meta["color_field"]) or "Blue",
                "is_active": cint(row.get(meta["active_field"]) if meta["active_field"] in row else 1),
                "is_default": cint(row.get(meta["default_field"]) if meta["default_field"] in row else 0),
                "applies_distribution": cint(
                    row.get(meta["distribution_field"]) if meta["distribution_field"] in row else 1
                ),
                "applies_installation": cint(
                    row.get(meta["installation_field"]) if meta["installation_field"] in row else 1
                ),
            }
        )
    return statuses


def get_default_status_name(document_type: str) -> str | None:
    statuses = list_editable_statuses(document_type, include_inactive=False)
    for status in statuses:
        if status["is_default"]:
            return status["name"]
    return statuses[0]["name"] if statuses else None


def get_status_usage(document_type: str) -> dict[str, int]:
    meta = get_status_meta(document_type)
    target_doctype = meta["target_doctype"]
    target_field = meta["target_field"]
    if not frappe.get_meta(target_doctype).get_field(target_field):
        return {}
    rows = frappe.db.sql(
        f"""
        SELECT {target_field} AS status_name, COUNT(*) AS status_count
        FROM `tab{target_doctype}`
        WHERE COALESCE({target_field}, '') != ''
        GROUP BY {target_field}
        """,
        as_dict=True,
    )
    return {row.status_name: cint(row.status_count) for row in rows}


def get_legacy_status_groups(document_type: str) -> list[dict]:
    meta = get_status_meta(document_type)
    document_meta = frappe.get_meta(document_type)
    legacy_groups = []
    legacy_field = document_meta.get_field(meta["legacy_field"])
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
    legacy_value = doc.get(meta["legacy_field"]) if meta.get("legacy_field") else None
    resolved = resolve_status_column(doc.doctype, None, legacy_value=legacy_value)
    if resolved and resolved != UNASSIGNED_STATUS:
        doc.set(target_field, resolved)
        return
    default_name = get_default_status_name(doc.doctype)
    if default_name:
        doc.set(target_field, default_name)
