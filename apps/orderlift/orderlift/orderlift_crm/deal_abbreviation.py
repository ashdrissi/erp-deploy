from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.naming import set_new_name, validate_name
from frappe.utils import cint


DEAL_ABBREVIATION_FIELD = "custom_deal_abbreviation"
DEAL_SOURCE_FIELD = "custom_deal_opportunity"
MIXED_ABBREVIATION = "MIXED"
EDITABLE_DOCTYPES = {"Opportunity", "Sales Order", "Project"}
TARGET_DOCTYPES = (
    "Opportunity",
    "Quotation",
    "Sales Order",
    "Project",
    "Material Request",
    "Request for Quotation",
    "Supplier Quotation",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Delivery Note",
    "Sales Invoice",
    "Stock Entry",
    "Forecast Load Plan",
    "Delivery Trip",
    "Pick List",
    "Quality Inspection",
    "Work Order",
    "SAV Ticket",
)
LIST_VIEW_DOCTYPES = {
    "Opportunity",
    "Quotation",
    "Sales Order",
    "Project",
    "Material Request",
    "Purchase Order",
    "Purchase Receipt",
    "Delivery Note",
    "Sales Invoice",
}
INSERT_AFTER_CANDIDATES = {
    "Opportunity": ("custom_crm_segment", "party_name", "naming_series"),
    "Quotation": ("custom_crm_segment", "opportunity", "party_name"),
    "Sales Order": ("custom_crm_segment", "custom_orderlift_order_status", "customer"),
    "Project": ("custom_crm_segment", "custom_source_opportunity", "project_name"),
    "Material Request": ("material_request_type", "company", "naming_series"),
    "Request for Quotation": ("opportunity", "company", "naming_series"),
    "Supplier Quotation": ("opportunity", "project", "supplier"),
    "Purchase Order": ("project", "supplier", "naming_series"),
    "Purchase Receipt": ("project", "supplier", "naming_series"),
    "Purchase Invoice": ("project", "supplier", "naming_series"),
    "Delivery Note": ("project", "customer", "naming_series"),
    "Sales Invoice": ("project", "customer", "naming_series"),
    "Stock Entry": ("project", "purchase_order", "naming_series"),
    "Forecast Load Plan": ("plan_label", "company", "naming_series"),
    "Delivery Trip": ("custom_forecast_plan", "company", "naming_series"),
    "Pick List": ("material_request", "company", "naming_series"),
    "Quality Inspection": ("reference_name", "reference_type", "naming_series"),
    "Work Order": ("project", "sales_order", "naming_series"),
    "SAV Ticket": ("sales_order", "installation_project", "customer"),
}


def normalize_deal_abbreviation(value: str | None, *, allow_mixed: bool = False) -> str:
    abbreviation = (value or "").strip().upper()
    if not abbreviation:
        return ""
    if abbreviation == MIXED_ABBREVIATION:
        if allow_mixed:
            return abbreviation
        frappe.throw(_("MIXED is reserved for documents linked to multiple deals."))
    if not re.fullmatch(r"[A-Z0-9]{2,12}", abbreviation):
        frappe.throw(_("Deal Abbreviation must contain 2 to 12 uppercase letters or numbers."))
    return abbreviation


def sync_deal_abbreviation(doc, method=None) -> None:
    if not _is_supported_document(doc):
        return

    current = normalize_deal_abbreviation(doc.get(DEAL_ABBREVIATION_FIELD), allow_mixed=True)
    if doc.doctype == "Opportunity":
        doc.set(DEAL_ABBREVIATION_FIELD, normalize_deal_abbreviation(current))
        return

    opportunities = resolve_source_opportunities(doc)
    source_abbreviation = _abbreviation_for_opportunities(opportunities)
    user_changed = _editable_value_changed(doc, current, source_abbreviation)

    if doc.doctype in EDITABLE_DOCTYPES and user_changed:
        if len(opportunities) != 1:
            frappe.throw(
                _("Deal Abbreviation can only be edited when the document is linked to exactly one Opportunity.")
            )
        opportunity = next(iter(opportunities))
        normalized = normalize_deal_abbreviation(current)
        _require_anchor_write_permission(doc)
        _update_opportunity_abbreviation(opportunity, normalized)
        doc.set(DEAL_ABBREVIATION_FIELD, normalized)
        doc.set(DEAL_SOURCE_FIELD, _source_marker(opportunities))
        return

    if opportunities:
        doc.set(DEAL_ABBREVIATION_FIELD, source_abbreviation)
        doc.set(DEAL_SOURCE_FIELD, _source_marker(opportunities))
    else:
        doc.set(DEAL_ABBREVIATION_FIELD, current)
        doc.set(DEAL_SOURCE_FIELD, "")


def sync_submitted_deal_abbreviation(doc, method=None) -> None:
    sync_deal_abbreviation(doc, method=method)


def prepare_deal_abbreviation_name(doc, method=None) -> None:
    if not _is_supported_document(doc):
        return
    sync_deal_abbreviation(doc)

    if doc.doctype == "Opportunity":
        from orderlift.orderlift_crm.opportunity_hooks import assign_opportunity_name

        assign_opportunity_name(doc)
        if doc.name:
            doc.flags.name_set = True
        return

    abbreviation = normalize_deal_abbreviation(doc.get(DEAL_ABBREVIATION_FIELD), allow_mixed=True)
    if not abbreviation or abbreviation == "MIXED":
        return
    if doc.get("amended_from") and _uses_amendment_suffix(doc.doctype):
        doc.name = validate_name(doc.doctype, _amended_deal_name(doc, abbreviation))
        doc.flags.name_set = True
        return
    set_new_name(doc)
    if not doc.name or doc.name.endswith(f"~{abbreviation}"):
        return
    doc.name = validate_name(doc.doctype, _deal_suffixed_name(doc, abbreviation))
    doc.flags.name_set = True


def _deal_suffixed_name(doc, abbreviation: str) -> str:
    return f"{doc.name}~{abbreviation}"


def propagate_opportunity_deal_abbreviation(doc, method=None) -> None:
    if not doc or doc.doctype != "Opportunity" or not _has_field(doc, DEAL_ABBREVIATION_FIELD):
        return
    if not _field_changed(doc, DEAL_ABBREVIATION_FIELD):
        return
    abbreviation = normalize_deal_abbreviation(doc.get(DEAL_ABBREVIATION_FIELD))
    propagate_deal_abbreviation_from_opportunity(doc.name, abbreviation)
    # Rename the Opportunity (and any DRAFT downstream docs) so their IDs carry the new
    # ~ABBREV suffix. Deferred to an after-commit background job: renaming the Opportunity
    # during its own save would be re-entrant, and after_commit avoids acting on a rolled
    # back change.
    frappe.enqueue(
        "orderlift.orderlift_crm.deal_abbreviation.rename_deal_chain_for_abbreviation",
        enqueue_after_commit=True,
        queue="short",
        opportunity=doc.name,
        abbreviation=abbreviation,
    )


def rename_deal_chain_for_abbreviation(opportunity: str, abbreviation: str | None = None) -> None:
    """Rename the Opportunity and its DRAFT downstream documents to carry ``~ABBREV``.

    Submitted downstream documents (Sales Order, Material Request, Purchase Order, …) are
    intentionally **not** renamed: ``frappe.rename_doc`` does not rewrite the ``Data``
    ``voucher_no`` references in GL Entry / Stock Ledger Entry, so renaming a submitted
    transaction would break financial/stock traceability. Those keep the propagated
    abbreviation field instead. Idempotent and safe to re-run.
    """
    opportunity = (opportunity or "").strip()
    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        return
    if abbreviation is None:
        abbreviation = frappe.db.get_value("Opportunity", opportunity, DEAL_ABBREVIATION_FIELD) or ""
    abbreviation = normalize_deal_abbreviation(abbreviation)

    # 1) Rename the Opportunity itself (never submitted -> safe). Its link fields and the
    #    downstream `custom_deal_opportunity` markers are repaired by the after_rename hook.
    desired = _reapply_deal_suffix(opportunity, abbreviation)
    if desired != opportunity:
        frappe.rename_doc("Opportunity", opportunity, desired, force=True, show_alert=False)
        frappe.db.commit()
        opportunity = desired

    # 2) Rename DRAFT downstream documents that resolve to this Opportunity.
    for doctype in TARGET_DOCTYPES:
        if doctype == "Opportunity" or not _doctype_has_fields(doctype, DEAL_SOURCE_FIELD):
            continue
        rows = frappe.get_all(
            doctype,
            filters={DEAL_SOURCE_FIELD: ["like", f"%{opportunity}%"], "docstatus": 0},
            fields=["name", DEAL_SOURCE_FIELD],
            limit_page_length=0,
        )
        for row in rows:
            opportunities = _opportunities_from_marker(row.get(DEAL_SOURCE_FIELD))
            if opportunity not in opportunities:
                continue
            doc_abbreviation = _abbreviation_for_opportunities(opportunities)
            # Never fold the synthetic MIXED marker into an ID; leave the name, keep the field.
            if doc_abbreviation == MIXED_ABBREVIATION:
                continue
            desired_name = _reapply_deal_suffix(row.name, doc_abbreviation)
            if desired_name == row.name:
                continue
            try:
                frappe.rename_doc(doctype, row.name, desired_name, force=True, show_alert=False)
                frappe.db.commit()
            except Exception:
                frappe.db.rollback()
                frappe.log_error(
                    title="Deal chain rename failed",
                    message=f"{doctype} {row.name} -> {desired_name}\n{frappe.get_traceback()}",
                )


def _strip_deal_suffix(name: str) -> str:
    return re.sub(r"~[A-Z0-9]{2,12}$", "", (name or "").strip())


def _reapply_deal_suffix(name: str, abbreviation: str | None) -> str:
    base = _strip_deal_suffix(name)
    abbreviation = (abbreviation or "").strip().upper()
    return f"{base}~{abbreviation}" if abbreviation else base


def update_renamed_deal_opportunity(doc, method=None, old: str | None = None, new: str | None = None, merge=False) -> None:
    # Frappe invokes after_rename doc_event handlers as (doc, method, old, new, merge).
    if not doc or doc.doctype != "Opportunity" or not old or not new:
        return
    for doctype in TARGET_DOCTYPES:
        if doctype == "Opportunity" or not _doctype_has_fields(doctype, DEAL_SOURCE_FIELD):
            continue
        rows = frappe.get_all(
            doctype,
            filters={DEAL_SOURCE_FIELD: ["like", f"%{old}%"]},
            fields=["name", DEAL_SOURCE_FIELD],
            limit_page_length=0,
        )
        for row in rows:
            opportunities = _opportunities_from_marker(row.get(DEAL_SOURCE_FIELD))
            if old not in opportunities:
                continue
            opportunities.discard(old)
            opportunities.add(new)
            frappe.db.set_value(
                doctype,
                row.name,
                DEAL_SOURCE_FIELD,
                _source_marker(opportunities),
                update_modified=False,
            )


def propagate_deal_abbreviation_from_opportunity(opportunity: str, abbreviation: str | None = None) -> None:
    opportunity = (opportunity or "").strip()
    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        return
    if abbreviation is None:
        abbreviation = frappe.db.get_value("Opportunity", opportunity, DEAL_ABBREVIATION_FIELD) or ""
    abbreviation = normalize_deal_abbreviation(abbreviation)

    for doctype in TARGET_DOCTYPES:
        if doctype == "Opportunity" or not _doctype_has_fields(doctype, DEAL_ABBREVIATION_FIELD, DEAL_SOURCE_FIELD):
            continue
        rows = frappe.get_all(
            doctype,
            filters={DEAL_SOURCE_FIELD: ["like", f"%{opportunity}%"]},
            fields=["name", DEAL_SOURCE_FIELD],
            limit_page_length=0,
        )
        for row in rows:
            if opportunity not in _opportunities_from_marker(row.get(DEAL_SOURCE_FIELD)):
                continue
            target = frappe.get_doc(doctype, row.name)
            opportunities = resolve_source_opportunities(target)
            frappe.db.set_value(
                doctype,
                row.name,
                {
                    DEAL_ABBREVIATION_FIELD: _abbreviation_for_opportunities(opportunities),
                    DEAL_SOURCE_FIELD: _source_marker(opportunities),
                },
                update_modified=False,
            )


def resolve_source_opportunities(doc) -> set[str]:
    return _resolve_source_opportunities(doc, visited=set(), cache={})


def _resolve_source_opportunities(doc, *, visited: set[tuple[str, str]], cache: dict[tuple[str, str], object]) -> set[str]:
    if not doc:
        return set()
    doctype = (getattr(doc, "doctype", None) or _value(doc, "doctype") or "").strip()
    name = (getattr(doc, "name", None) or _value(doc, "name") or "").strip()
    identity = (doctype, name or f"new:{id(doc)}")
    if identity in visited:
        return set()
    visited.add(identity)

    if doctype == "Opportunity":
        return {name} if name and not name.startswith("new-") else set()

    opportunities = set()
    for reference_doctype, reference_name in _upstream_references(doc):
        if reference_doctype == "Opportunity":
            if reference_name and frappe.db.exists("Opportunity", reference_name):
                opportunities.add(reference_name)
            continue
        source = _load_reference(reference_doctype, reference_name, cache)
        if source:
            opportunities.update(_resolve_source_opportunities(source, visited=visited, cache=cache))

    if not opportunities and name and not _document_is_new(doc):
        marker = frappe.db.get_value(doctype, name, DEAL_SOURCE_FIELD) or ""
        opportunities.update(
            opportunity
            for opportunity in _opportunities_from_marker(marker)
            if frappe.db.exists("Opportunity", opportunity)
        )
    return opportunities


def _upstream_references(doc) -> list[tuple[str, str]]:
    doctype = doc.doctype
    references = []

    _append_reference(references, "Opportunity", _value(doc, "opportunity"))
    _append_reference(references, "Opportunity", _value(doc, "custom_source_opportunity"))

    if doctype == "Sales Order":
        for row in _rows(doc, "items"):
            _append_reference(references, "Quotation", _value(row, "prevdoc_docname"))
        _append_reference(references, "Project", _value(doc, "project"))
    elif doctype == "Project":
        _append_reference(references, "Sales Order", _value(doc, "sales_order"))
    elif doctype == "Material Request":
        _append_item_references(references, doc, ("sales_order", "project"))
    elif doctype == "Request for Quotation":
        _append_item_references(references, doc, ("material_request",))
    elif doctype == "Supplier Quotation":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_item_references(
            references,
            doc,
            ("request_for_quotation", "material_request", "sales_order", "project"),
        )
    elif doctype == "Purchase Order":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_item_references(references, doc, ("sales_order", "material_request", "project"))
    elif doctype == "Purchase Receipt":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_item_references(
            references,
            doc,
            ("purchase_order", "material_request", "sales_order", "project"),
        )
    elif doctype == "Purchase Invoice":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_item_references(
            references,
            doc,
            ("purchase_order", "purchase_receipt", "material_request", "project"),
        )
    elif doctype == "Delivery Note":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_item_references(
            references,
            doc,
            ("against_sales_order", "project", "material_request", "purchase_order"),
        )
    elif doctype == "Sales Invoice":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_item_references(
            references,
            doc,
            ("sales_order", "delivery_note", "project", "purchase_order"),
        )
    elif doctype == "Stock Entry":
        _append_reference(references, "Project", _value(doc, "project"))
        _append_reference(references, "Purchase Order", _value(doc, "purchase_order"))
        _append_item_references(references, doc, ("material_request", "project"))
    elif doctype == "Forecast Load Plan":
        for row in _rows(doc, "items"):
            _append_reference(references, _value(row, "source_doctype"), _value(row, "source_name"))
    elif doctype == "Delivery Trip":
        _append_reference(references, "Forecast Load Plan", _value(doc, "custom_forecast_plan"))
        for row in _rows(doc, "delivery_stops"):
            _append_reference(references, "Delivery Note", _value(row, "delivery_note"))
    elif doctype == "Pick List":
        _append_reference(references, "Material Request", _value(doc, "material_request"))
        for row in _rows(doc, "locations"):
            _append_reference(references, "Sales Order", _value(row, "sales_order"))
            _append_reference(references, "Material Request", _value(row, "material_request"))
    elif doctype == "Quality Inspection":
        _append_reference(references, _value(doc, "reference_type"), _value(doc, "reference_name"))
    elif doctype == "Work Order":
        _append_reference(references, "Sales Order", _value(doc, "sales_order"))
        _append_reference(references, "Project", _value(doc, "project"))
        _append_reference(references, "Material Request", _value(doc, "material_request"))
    elif doctype == "SAV Ticket":
        for fieldname, reference_doctype in (
            ("sales_order", "Sales Order"),
            ("delivery_note", "Delivery Note"),
            ("sales_invoice", "Sales Invoice"),
            ("purchase_receipt", "Purchase Receipt"),
            ("installation_project", "Project"),
            ("quality_inspection", "Quality Inspection"),
        ):
            _append_reference(references, reference_doctype, _value(doc, fieldname))

    return _unique_references(references)


def _append_item_references(references: list[tuple[str, str]], doc, fieldnames: tuple[str, ...]) -> None:
    doctypes = {
        "against_sales_order": "Sales Order",
        "delivery_note": "Delivery Note",
        "material_request": "Material Request",
        "project": "Project",
        "purchase_order": "Purchase Order",
        "purchase_receipt": "Purchase Receipt",
        "request_for_quotation": "Request for Quotation",
        "sales_order": "Sales Order",
    }
    for row in _rows(doc, "items"):
        for fieldname in fieldnames:
            _append_reference(references, doctypes[fieldname], _value(row, fieldname))


def _append_reference(references: list[tuple[str, str]], doctype: str | None, name: str | None) -> None:
    doctype = (doctype or "").strip()
    name = (name or "").strip()
    if doctype in TARGET_DOCTYPES and name:
        references.append((doctype, name))


def _unique_references(references: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(dict.fromkeys(references))


def _load_reference(doctype: str, name: str, cache: dict[tuple[str, str], object]):
    key = (doctype, name)
    if key in cache:
        return cache[key]
    if not name or not frappe.db.exists(doctype, name):
        cache[key] = None
        return None
    cache[key] = frappe.get_doc(doctype, name)
    return cache[key]


def _abbreviation_for_opportunities(opportunities: set[str]) -> str:
    if not opportunities:
        return ""
    abbreviations = {
        normalize_deal_abbreviation(
            frappe.db.get_value("Opportunity", opportunity, DEAL_ABBREVIATION_FIELD) or ""
        )
        for opportunity in opportunities
    }
    if len(abbreviations) > 1:
        return MIXED_ABBREVIATION
    return next(iter(abbreviations), "")


def _editable_value_changed(doc, current: str, source_abbreviation: str) -> bool:
    if doc.doctype not in EDITABLE_DOCTYPES or doc.doctype == "Opportunity":
        return False
    before = doc.get_doc_before_save() if not doc.is_new() else None
    if before:
        previous = normalize_deal_abbreviation(before.get(DEAL_ABBREVIATION_FIELD), allow_mixed=True)
        return previous != current
    return bool(current and current != source_abbreviation)


def _update_opportunity_abbreviation(opportunity: str, abbreviation: str) -> None:
    opportunity_doc = frappe.get_doc("Opportunity", opportunity)
    if not frappe.has_permission("Opportunity", "read", doc=opportunity_doc):
        frappe.throw(_("You do not have access to the source Opportunity."), frappe.PermissionError)
    current = frappe.db.get_value("Opportunity", opportunity, DEAL_ABBREVIATION_FIELD) or ""
    if normalize_deal_abbreviation(current) == abbreviation:
        return
    frappe.db.set_value(
        "Opportunity",
        opportunity,
        DEAL_ABBREVIATION_FIELD,
        abbreviation,
    )
    propagate_deal_abbreviation_from_opportunity(opportunity, abbreviation)


def ensure_deal_abbreviation_fields() -> None:
    fields_by_doctype = {}
    for doctype in TARGET_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        insert_after = next(
            (fieldname for fieldname in INSERT_AFTER_CANDIDATES[doctype] if meta.get_field(fieldname)),
            "",
        )
        fields = [
            {
                "fieldname": DEAL_ABBREVIATION_FIELD,
                "label": "Deal Abbreviation",
                "fieldtype": "Data",
                "insert_after": insert_after,
                "reqd": 0,
                "read_only": 0 if doctype in EDITABLE_DOCTYPES else 1,
                "allow_on_submit": 1,
                "in_standard_filter": 1,
                "in_list_view": 1 if doctype in LIST_VIEW_DOCTYPES else 0,
                "description": "Short deal identifier propagated from the source Opportunity.",
            }
        ]
        if doctype != "Opportunity":
            fields.append(
                {
                    "fieldname": DEAL_SOURCE_FIELD,
                    "label": "Deal Opportunity",
                    "fieldtype": "Small Text",
                    "insert_after": DEAL_ABBREVIATION_FIELD,
                    "read_only": 1,
                    "hidden": 1,
                    "allow_on_submit": 1,
                    "print_hide": 1,
                }
            )
        fields_by_doctype[doctype] = fields
    create_custom_fields(fields_by_doctype, update=True)
    for doctype in fields_by_doctype:
        frappe.clear_cache(doctype=doctype)


def backfill_deal_abbreviations() -> dict:
    updated = 0
    mixed = 0
    for doctype in TARGET_DOCTYPES:
        if not _doctype_has_fields(doctype, DEAL_ABBREVIATION_FIELD):
            continue
        for name in frappe.get_all(doctype, pluck="name", limit_page_length=0):
            doc = frappe.get_doc(doctype, name)
            if doctype == "Opportunity":
                abbreviation = normalize_deal_abbreviation(doc.get(DEAL_ABBREVIATION_FIELD))
                values = {DEAL_ABBREVIATION_FIELD: abbreviation}
            else:
                opportunities = resolve_source_opportunities(doc)
                abbreviation = _abbreviation_for_opportunities(opportunities)
                values = {
                    DEAL_ABBREVIATION_FIELD: abbreviation,
                    DEAL_SOURCE_FIELD: _source_marker(opportunities),
                }
            current = {fieldname: doc.get(fieldname) or "" for fieldname in values}
            if current == values:
                continue
            frappe.db.set_value(doctype, name, values, update_modified=False)
            updated += 1
            mixed += int(abbreviation == MIXED_ABBREVIATION)
    return {"updated": updated, "mixed": mixed}


def after_migrate() -> dict:
    ensure_deal_abbreviation_fields()
    return backfill_deal_abbreviations()


def _is_supported_document(doc) -> bool:
    return bool(doc and getattr(doc, "doctype", None) in TARGET_DOCTYPES and _has_field(doc, DEAL_ABBREVIATION_FIELD))


def _has_field(doc, fieldname: str) -> bool:
    return bool(getattr(doc, "meta", None) and doc.meta.get_field(fieldname))


def _doctype_has_fields(doctype: str, *fieldnames: str) -> bool:
    if not frappe.db.exists("DocType", doctype):
        return False
    meta = frappe.get_meta(doctype)
    return all(meta.get_field(fieldname) for fieldname in fieldnames)


def _field_changed(doc, fieldname: str) -> bool:
    checker = getattr(doc, "has_value_changed", None)
    return bool(checker(fieldname)) if callable(checker) else True


def _require_anchor_write_permission(doc) -> None:
    if getattr(doc, "flags", None) and getattr(doc.flags, "ignore_permissions", False):
        return
    doc.check_permission("create" if _document_is_new(doc) else "write")


def _document_is_new(doc) -> bool:
    checker = getattr(doc, "is_new", None)
    return bool(checker()) if callable(checker) else not bool(getattr(doc, "name", None))


def _source_marker(opportunities: set[str]) -> str:
    return json.dumps(sorted({value for value in opportunities if value}), separators=(",", ":")) if opportunities else ""


def _opportunities_from_marker(value: str | None) -> set[str]:
    value = (value or "").strip()
    if not value:
        return set()
    if value.startswith("["):
        try:
            parsed = frappe.parse_json(value)
            return {str(item).strip() for item in parsed or [] if str(item).strip()}
        except (TypeError, ValueError):
            return set()
    return {value}


def _uses_amendment_suffix(doctype: str) -> bool:
    rule = frappe.db.get_value(
        "Amended Document Naming Settings",
        {"document_type": doctype},
        "action",
        cache=True,
    ) or frappe.get_single_value("Document Naming Settings", "default_amend_naming")
    return rule != "Default Naming"


def _amended_deal_name(doc, abbreviation: str) -> str:
    source_name = re.sub(r"~[A-Z0-9]{2,12}$", "", (doc.get("amended_from") or "").strip())
    source_amended_from = frappe.db.get_value(doc.doctype, doc.get("amended_from"), "amended_from")
    if source_amended_from:
        prefix, separator, counter = source_name.rpartition("-")
        if separator and counter.isdigit():
            return f"{prefix}-{cint(counter) + 1}~{abbreviation}"
    return f"{source_name}-1~{abbreviation}"


def _rows(doc, fieldname: str) -> list:
    return list(_value(doc, fieldname) or [])


def _value(obj, fieldname: str):
    getter = getattr(obj, "get", None)
    if callable(getter):
        return getter(fieldname)
    if isinstance(obj, dict):
        return obj.get(fieldname)
    return getattr(obj, fieldname, None)
