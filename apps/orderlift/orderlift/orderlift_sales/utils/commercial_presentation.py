from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.reference_access import require_reference_use


WITH_DETAILS = "With details"
WITHOUT_DETAILS = "Without details"
INCLUDE_IN_SUMMARY = "Include in commercial summary"
PRINT_SEPARATELY = "Print separately"

HEADER_FIELDS = (
    "custom_presentation_mode",
    "custom_commercial_designation",
    "custom_commercial_presentation_template",
    "custom_commercial_presentation_snapshot",
    "custom_dimensioning_set",
    "custom_dimensioning_multiplier",
    "custom_dimensioning_inputs_json",
)
ITEM_FIELDS = (
    "custom_presentation_role",
    "custom_orderlift_other_charge",
    "custom_dimensioning_set",
    "custom_dimensioning_rule_label",
)


def validate_commercial_presentation(doc, method=None) -> None:
    if not doc or not _has_field(doc, "custom_presentation_mode"):
        return

    mode = normalize_presentation_mode(_get(doc, "custom_presentation_mode"))
    doc.custom_presentation_mode = mode
    designation = (_get(doc, "custom_commercial_designation") or "").strip()
    if mode == WITHOUT_DETAILS and not designation:
        if doc.doctype == "Quotation":
            if int(_get(doc, "docstatus", 0) or 0) and not _has_commercial_presentation_snapshot(doc):
                frappe.throw(_("Save the Commercial Presentation before submitting a Quotation without details."))
        else:
            frappe.throw(_("Commercial Designation is required when Presentation is Without details."))
    if _has_field(doc, "custom_dimensioning_multiplier"):
        doc.custom_dimensioning_multiplier = normalize_dimensioning_multiplier(
            _get(doc, "custom_dimensioning_multiplier")
        )
    if doc.doctype in {"Opportunity", "Quotation"} and (_get(doc, "custom_dimensioning_set") or "").strip():
        require_reference_use(
            "Dimensioning Set",
            _get(doc, "custom_dimensioning_set"),
            filters={"is_active": 1},
            label="Dimensioning Set",
        )

    for row in _items(doc):
        if _has_field(row, "custom_presentation_role"):
            row.custom_presentation_role = normalize_presentation_role(_get(row, "custom_presentation_role"))

    if _has_field(doc, "custom_commercial_total"):
        doc.custom_commercial_total = calculate_commercial_total(doc)


def inherit_commercial_presentation(doc, method=None) -> None:
    if not doc or not _has_field(doc, "custom_presentation_mode"):
        return

    source_docs: dict[tuple[str, str], Any] = {}
    first_source = None
    if doc.doctype == "Quotation":
        opportunity = (_get(doc, "opportunity") or "").strip()
        if opportunity and frappe.db.exists("Opportunity", opportunity):
            first_source = frappe.get_doc("Opportunity", opportunity)
            first_source.check_permission("read")
            source_docs[("Opportunity", opportunity)] = first_source
    for row in _items(doc):
        source_doctype, source_name, source_detail = _source_reference(doc, row)
        if not source_doctype or not source_name:
            continue
        key = (source_doctype, source_name)
        source = source_docs.get(key)
        if source is None:
            if not frappe.db.exists(source_doctype, source_name):
                continue
            source = frappe.get_doc(source_doctype, source_name)
            source.check_permission("read")
            source_docs[key] = source
        first_source = first_source or source
        source_row = _source_item(source, source_detail, row)
        if source_row:
            _copy_fields(source_row, row, ITEM_FIELDS)

    if first_source and _should_copy_header_from_source(doc):
        _copy_fields(first_source, doc, HEADER_FIELDS)
        _inherit_designation_from_source(first_source, doc)


def calculate_commercial_total(doc) -> float:
    total = 0.0
    for row in _items(doc):
        if normalize_presentation_role(_get(row, "custom_presentation_role")) == PRINT_SEPARATELY:
            continue
        total += _row_amount(row)
    return flt(total)


def normalize_presentation_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"without details", "sans details", "sans détails"}:
        return WITHOUT_DETAILS
    return WITH_DETAILS


def normalize_presentation_role(value: Any) -> str:
    return PRINT_SEPARATELY if str(value or "").strip() == PRINT_SEPARATELY else INCLUDE_IN_SUMMARY


def normalize_dimensioning_multiplier(value: Any) -> int:
    numeric = flt(1 if value in (None, "") else value)
    multiplier = int(numeric)
    if numeric <= 0 or numeric != multiplier:
        frappe.throw(_("Number of Sets must be a positive whole number."))
    return multiplier


def _has_commercial_presentation_snapshot(doc) -> bool:
    raw = (_get(doc, "custom_commercial_presentation_snapshot") or "").strip()
    if not raw:
        return False
    try:
        snapshot = json.loads(raw)
    except Exception:
        return False
    return bool(snapshot.get("template") and snapshot.get("blocks"))


def resolve_commercial_designation(doc) -> str:
    designation = (_get(doc, "custom_commercial_designation") or "").strip()
    if designation:
        return designation
    return _snapshot_summary_title(doc)


def _snapshot_summary_title(doc) -> str:
    raw = (_get(doc, "custom_commercial_presentation_snapshot") or "").strip()
    if not raw:
        return ""
    try:
        snapshot = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(snapshot, dict):
        return ""
    for block in snapshot.get("blocks") or []:
        if isinstance(block, dict) and block.get("type") == "Heading" and (block.get("value") or "").strip():
            return (block.get("value") or "").strip()
    return (snapshot.get("template_name") or "").strip()


def _source_reference(target_doc, row) -> tuple[str, str, str]:
    if target_doc.doctype == "Quotation":
        return (
            "Opportunity",
            (_get(target_doc, "opportunity") or _get(row, "prevdoc_docname") or "").strip(),
            (_get(row, "prevdoc_detail_docname") or _get(row, "opportunity_item") or "").strip(),
        )
    if target_doc.doctype == "Sales Order":
        return (
            "Quotation",
            (_get(row, "prevdoc_docname") or _get(row, "quotation") or "").strip(),
            (_get(row, "prevdoc_detail_docname") or _get(row, "quotation_item") or "").strip(),
        )
    if target_doc.doctype in {"Delivery Note", "Sales Invoice"}:
        return (
            "Sales Order",
            (_get(row, "against_sales_order") or _get(row, "sales_order") or "").strip(),
            (_get(row, "so_detail") or "").strip(),
        )
    return "", "", ""


def _source_item(source, source_detail: str, target_row):
    rows = list(getattr(source, "items", None) or [])
    if source_detail:
        for row in rows:
            if (_get(row, "name") or "").strip() == source_detail:
                return row
    item_code = (_get(target_row, "item_code") or "").strip()
    matches = [row for row in rows if (_get(row, "item_code") or "").strip() == item_code]
    return matches[0] if len(matches) == 1 else None


def _copy_fields(source, target, fieldnames) -> None:
    for fieldname in fieldnames:
        if not _has_field(source, fieldname) or not _has_field(target, fieldname):
            continue
        value = _get(source, fieldname)
        if value not in (None, ""):
            target.set(fieldname, value)


def _inherit_designation_from_source(source, target) -> None:
    if not _has_field(target, "custom_commercial_designation"):
        return
    if (_get(target, "custom_commercial_designation") or "").strip():
        return
    designation = resolve_commercial_designation(source)
    if designation:
        target.set("custom_commercial_designation", designation)


def _should_copy_header_from_source(doc) -> bool:
    # Opportunity only controls item-level presentation roles. Quotation headers
    # are chosen directly on the Quotation or generated from the Pricing Sheet.
    return doc.doctype != "Quotation"


def _row_amount(row) -> float:
    for fieldname in ("net_amount", "amount", "discounted_sell_total", "final_sell_total"):
        value = _get(row, fieldname)
        if value not in (None, ""):
            return flt(value)
    return flt(_get(row, "rate")) * flt(_get(row, "qty") or 1)


def _items(doc) -> list:
    if hasattr(doc, "get"):
        return list(doc.get("items") or doc.get("lines") or [])
    return list(getattr(doc, "items", None) or getattr(doc, "lines", None) or [])


def _has_field(row, fieldname: str) -> bool:
    meta = getattr(row, "meta", None)
    return bool(meta and meta.get_field(fieldname))


def _get(row, fieldname: str, default=None):
    if hasattr(row, "get"):
        return row.get(fieldname, default)
    return getattr(row, fieldname, default)
