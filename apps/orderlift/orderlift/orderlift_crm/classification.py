from __future__ import annotations

from contextlib import suppress

import frappe
from frappe.utils import cint


PARTY_DOCTYPES = {"Lead", "Prospect", "Customer"}
BUSINESS_FIELD = "custom_crm_business_type"
SEGMENT_FIELD = "custom_crm_segment"


def sync_quotation_crm_classification(doc, method=None) -> None:
    if not _has_classification_fields(doc):
        return

    if doc.get("opportunity"):
        info = classification_from_document("Opportunity", doc.get("opportunity"))
        if _apply_classification(doc, info):
            return

    party_type = (doc.get("quotation_to") or "").strip()
    party_name = (doc.get("party_name") or "").strip()
    _apply_party_classification(doc, party_type, party_name)


def sync_sales_order_crm_classification(doc, method=None) -> None:
    if not _has_classification_fields(doc):
        return

    for quotation in linked_quotation_names_from_sales_order(doc):
        info = classification_from_document("Quotation", quotation)
        if not (info.get("business_type") or info.get("crm_segment")):
            opportunity = frappe.db.get_value("Quotation", quotation, "opportunity")
            info = classification_from_document("Opportunity", opportunity)
        if _apply_classification(doc, info):
            return

    _apply_party_classification(doc, "Customer", doc.get("customer"))


def sync_project_crm_classification(doc, method=None) -> None:
    if not _has_classification_fields(doc):
        return

    sales_order = (doc.get("sales_order") or "").strip()
    if sales_order:
        if _apply_classification(doc, classification_from_document("Sales Order", sales_order)):
            return

    _apply_party_classification(doc, "Customer", doc.get("customer"))


def copy_crm_classification(source_doc, target_doc, overwrite: bool = False) -> bool:
    if not _has_classification_fields(target_doc):
        return False
    info = {
        "business_type": source_doc.get(BUSINESS_FIELD),
        "crm_segment": source_doc.get(SEGMENT_FIELD),
    }
    return _apply_classification(target_doc, info, overwrite=overwrite)


def classification_from_document(doctype: str | None, name: str | None) -> dict:
    doctype = (doctype or "").strip()
    name = (name or "").strip()
    if not doctype or not name or not frappe.db.exists(doctype, name):
        return {"business_type": "", "crm_segment": ""}
    fields = []
    if _has_field(doctype, BUSINESS_FIELD):
        fields.append(BUSINESS_FIELD)
    if _has_field(doctype, SEGMENT_FIELD):
        fields.append(SEGMENT_FIELD)
    if not fields:
        return {"business_type": "", "crm_segment": ""}
    values = frappe.db.get_value(doctype, name, fields, as_dict=True) or {}
    return {
        "business_type": values.get(BUSINESS_FIELD) or "",
        "crm_segment": values.get(SEGMENT_FIELD) or "",
    }


def party_crm_segments(party_type: str | None, party_name: str | None) -> list[dict]:
    party_type = (party_type or "").strip()
    party_name = (party_name or "").strip()
    if party_type not in PARTY_DOCTYPES or not party_name:
        return []
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return []
    rows = frappe.get_all(
        "CRM Segment Assignment",
        filters={"parenttype": party_type, "parent": party_name},
        fields=["business_type", "segment", "is_primary"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )
    return [
        {
            "business_type": row.get("business_type") or "",
            "crm_segment": row.get("segment") or "",
            "is_primary": cint(row.get("is_primary")),
        }
        for row in rows
        if row.get("business_type") or row.get("segment")
    ]


def primary_party_classification(party_type: str | None, party_name: str | None) -> dict:
    segments = party_crm_segments(party_type, party_name)
    primary = segments[0] if segments else {}
    return {
        "business_type": primary.get("business_type") or "",
        "crm_segment": primary.get("crm_segment") or "",
        "segments": segments,
    }


def linked_quotation_names_from_sales_order(doc) -> list[str]:
    quotation_names = []
    for row in doc.get("items", []) or []:
        quotation = row.get("prevdoc_docname") if hasattr(row, "get") else getattr(row, "prevdoc_docname", None)
        if not quotation or quotation in quotation_names:
            continue
        if frappe.db.exists("Quotation", quotation):
            quotation_names.append(quotation)
    return quotation_names


def _apply_party_classification(doc, party_type: str | None, party_name: str | None) -> bool:
    resolved = primary_party_classification(party_type, party_name)
    return _apply_classification(doc, resolved, valid_segments=resolved.get("segments") or [])


def _apply_classification(
    doc,
    info: dict | None,
    *,
    valid_segments: list[dict] | None = None,
    overwrite: bool = False,
) -> bool:
    info = info or {}
    business_type = (info.get("business_type") or "").strip()
    crm_segment = (info.get("crm_segment") or "").strip()
    if not business_type and not crm_segment:
        return False

    current_business_type = (doc.get(BUSINESS_FIELD) or "").strip()
    current_segment = (doc.get(SEGMENT_FIELD) or "").strip()
    if not overwrite and (current_business_type or current_segment):
        if not valid_segments or _segment_choice_is_valid(current_business_type, current_segment, valid_segments):
            return False

    changed = False
    if doc.meta.get_field(BUSINESS_FIELD) and current_business_type != business_type:
        doc.set(BUSINESS_FIELD, business_type)
        changed = True
    if doc.meta.get_field(SEGMENT_FIELD) and current_segment != crm_segment:
        doc.set(SEGMENT_FIELD, crm_segment)
        changed = True
    return changed


def _segment_choice_is_valid(business_type: str, segment: str, valid_segments: list[dict]) -> bool:
    if not business_type and not segment:
        return False
    for row in valid_segments:
        if business_type and row.get("business_type") != business_type:
            continue
        if segment and row.get("crm_segment") != segment:
            continue
        return True
    return False


def _has_classification_fields(doc) -> bool:
    return bool(doc.meta.get_field(BUSINESS_FIELD) and doc.meta.get_field(SEGMENT_FIELD))


def _has_field(doctype: str, fieldname: str) -> bool:
    with suppress(Exception):
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    return False
