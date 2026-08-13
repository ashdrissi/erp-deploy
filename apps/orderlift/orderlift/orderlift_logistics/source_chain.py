from __future__ import annotations

from collections import OrderedDict

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


SUPPORTED_DOCTYPES = (
    "Material Request",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
)

STAGES = (
    ("Opportunity", "opportunity"),
    ("Quotation", "quotation"),
    ("Sales Order", "sales_order"),
    ("Material Request", "material_request"),
    ("Purchase Order", "purchase_order"),
    ("Purchase Receipt", "purchase_receipt"),
    ("Purchase Invoice", "purchase_invoice"),
)

CURRENT_STAGE = {doctype: fieldname for doctype, fieldname in STAGES}
MAX_SOURCE_CHAIN_ROWS = 500


def after_migrate():
    ensure_source_chain_fields()


def ensure_source_chain_fields():
    fields = {}
    for doctype in SUPPORTED_DOCTYPES:
        fields[doctype] = [
            {
                "fieldname": "custom_upstream_source_chain_section",
                "label": "Commercial Source Chain",
                "fieldtype": "Section Break",
                "insert_after": "custom_deal_abbreviation",
                "collapsible": 0,
            },
            {
                "fieldname": "custom_upstream_source_chain_html",
                "label": "Commercial Source Chain",
                "fieldtype": "HTML",
                "insert_after": "custom_upstream_source_chain_section",
                "print_hide": 1,
            },
        ]
    create_custom_fields(fields, update=True)


@frappe.whitelist()
def get_upstream_source_chain(doc):
    current_doc = _parse_document(doc)
    doctype = _text(current_doc.get("doctype"))
    name = _text(current_doc.get("name"))
    is_new = bool(current_doc.get("__islocal")) or not name

    if doctype not in SUPPORTED_DOCTYPES:
        frappe.throw(_("Commercial source chains are only available for procurement documents."))

    if is_new:
        frappe.has_permission(doctype, "create", throw=True)
    else:
        frappe.has_permission(doctype, "read", doc=name, throw=True)

    rows = _prepare_rows(current_doc, is_new)
    if len(rows) > MAX_SOURCE_CHAIN_ROWS:
        frappe.throw(_("Commercial source chains support up to {0} item rows.").format(MAX_SOURCE_CHAIN_ROWS))
    _resolve_item_references(rows)
    _resolve_quotation_and_opportunity(rows)
    allowed = _allowed_sources(rows, doctype, name, is_new)
    return _build_response(current_doc, rows, allowed, is_new)


def _parse_document(doc):
    if isinstance(doc, str):
        doc = frappe.parse_json(doc)
    if not isinstance(doc, dict):
        frappe.throw(_("Invalid procurement document."))
    return doc


def _prepare_rows(doc, is_new):
    doctype = _text(doc.get("doctype"))
    document_name = _text(doc.get("name"))
    current_stage = CURRENT_STAGE[doctype]
    rows = []

    for index, item in enumerate(doc.get("items") or [], start=1):
        if not isinstance(item, dict):
            continue
        refs = {
            "purchase_order": _text(item.get("purchase_order")),
            "purchase_order_item": _text(item.get("po_detail") or item.get("purchase_order_item")),
            "purchase_receipt": _text(item.get("purchase_receipt")),
            "purchase_receipt_item": _text(item.get("pr_detail") or item.get("purchase_receipt_item")),
            "material_request": _text(item.get("material_request")),
            "material_request_item": _text(item.get("material_request_item")),
            "sales_order": _text(item.get("sales_order")),
            "sales_order_item": _text(item.get("sales_order_item")),
            "quotation": "",
            "opportunity": "",
        }
        if not is_new and document_name:
            refs[current_stage] = document_name

        rows.append(
            {
                "idx": item.get("idx") or index,
                "item_code": _text(item.get("item_code")),
                "item_name": _text(item.get("item_name")),
                "qty": item.get("qty") or 0,
                "refs": refs,
            }
        )
    return rows


def _resolve_item_references(rows):
    purchase_receipt_items = _rows_by_name(
        "Purchase Receipt Item",
        _values(rows, "purchase_receipt_item"),
        [
            "purchase_order",
            "purchase_order_item",
            "material_request",
            "material_request_item",
            "sales_order",
            "sales_order_item",
        ],
    )
    for row in rows:
        _fill_refs(row["refs"], purchase_receipt_items.get(row["refs"]["purchase_receipt_item"]))

    purchase_order_items = _rows_by_name(
        "Purchase Order Item",
        _values(rows, "purchase_order_item"),
        ["material_request", "material_request_item", "sales_order", "sales_order_item"],
    )
    for row in rows:
        _fill_refs(row["refs"], purchase_order_items.get(row["refs"]["purchase_order_item"]))

    material_request_items = _rows_by_name(
        "Material Request Item",
        _values(rows, "material_request_item"),
        ["sales_order", "sales_order_item"],
    )
    for row in rows:
        _fill_refs(row["refs"], material_request_items.get(row["refs"]["material_request_item"]))


def _resolve_quotation_and_opportunity(rows):
    sales_order_items = _rows_by_name(
        "Sales Order Item",
        _values(rows, "sales_order_item"),
        ["parent", "prevdoc_docname"],
    )
    for row in rows:
        refs = row["refs"]
        source_item = sales_order_items.get(refs["sales_order_item"])
        if not source_item:
            continue
        refs["sales_order"] = refs["sales_order"] or _text(source_item.get("parent"))
        refs["quotation"] = refs["quotation"] or _text(source_item.get("prevdoc_docname"))

    quotations = _rows_by_name("Quotation", _values(rows, "quotation"), ["opportunity"])
    for row in rows:
        refs = row["refs"]
        quotation = quotations.get(refs["quotation"])
        if quotation:
            refs["opportunity"] = _text(quotation.get("opportunity"))


def _rows_by_name(doctype, names, fields):
    names = sorted({name for name in names if name})
    if not names:
        return {}
    rows = frappe.db.get_all(
        doctype,
        filters={"name": ["in", names]},
        fields=["name", *fields],
    )
    return {row.get("name"): row for row in rows}


def _fill_refs(refs, source):
    if not source:
        return
    for fieldname in (
        "purchase_order",
        "purchase_order_item",
        "purchase_receipt",
        "purchase_receipt_item",
        "material_request",
        "material_request_item",
        "sales_order",
        "sales_order_item",
    ):
        refs[fieldname] = refs[fieldname] or _text(source.get(fieldname))


def _values(rows, fieldname):
    return {row["refs"].get(fieldname) for row in rows if row["refs"].get(fieldname)}


def _allowed_sources(rows, current_doctype, current_name, is_new):
    allowed = {}
    for doctype, fieldname in STAGES:
        names = _values(rows, fieldname)
        if not names:
            allowed[doctype] = set()
            continue
        if not frappe.has_permission(doctype, "read"):
            allowed[doctype] = set()
            continue
        try:
            allowed[doctype] = set(
                frappe.get_list(
                    doctype,
                    filters={"name": ["in", sorted(names)]},
                    pluck="name",
                    limit_page_length=len(names),
                )
            )
        except getattr(frappe, "PermissionError", PermissionError):
            # The source chain is informative only. Return a restricted stage
            # instead of failing the parent procurement form.
            allowed[doctype] = set()
    if not is_new and current_name:
        allowed.setdefault(current_doctype, set()).add(current_name)
    return allowed


def _build_response(doc, rows, allowed, is_new):
    groups = OrderedDict()
    manual_rows = []
    current_stage = CURRENT_STAGE[_text(doc.get("doctype"))]

    for row in rows:
        if not _has_upstream_reference(row["refs"], current_stage):
            manual_rows.append(_row_summary(row))
            continue

        key = tuple(row["refs"].get(fieldname) or "" for _doctype, fieldname in STAGES)
        group = groups.setdefault(
            key,
            {
                "rows": [],
                "stages": _stages_for_refs(row["refs"], allowed),
            },
        )
        group["rows"].append(_row_summary(row))

    group_list = list(groups.values())
    restricted = any(
        stage.get("restricted")
        for group in group_list
        for stage in group["stages"]
    )
    partial = any(
        not any(stage["doctype"] == "Sales Order" and stage["documents"] for stage in group["stages"])
        for group in group_list
    )

    return {
        "schema_version": 1,
        "source": {
            "doctype": doc.get("doctype"),
            "name": "" if is_new else doc.get("name"),
            "is_new": is_new,
        },
        "state": _response_state(group_list, manual_rows, restricted, partial),
        "summary": {
            "row_count": len(rows),
            "linked_row_count": sum(len(group["rows"]) for group in group_list),
            "manual_row_count": len(manual_rows),
            "group_count": len(group_list),
        },
        "groups": group_list,
        "manual_rows": manual_rows,
        "warnings": _warnings(manual_rows, restricted, partial),
    }


def _has_upstream_reference(refs, current_stage):
    return any(refs.get(fieldname) for _doctype, fieldname in STAGES if fieldname != current_stage)


def _stages_for_refs(refs, allowed):
    stages = []
    for doctype, fieldname in STAGES:
        name = refs.get(fieldname)
        if not name:
            continue
        if name in allowed.get(doctype, set()):
            stages.append({"doctype": doctype, "documents": [{"name": name}]})
        else:
            # The source identifier is useful for traceability, but an inaccessible
            # document must never become a navigable link or expose its title/data.
            stages.append({"doctype": doctype, "documents": [{"name": name}], "restricted": 1})
    return stages


def _row_summary(row):
    return {
        "idx": row["idx"],
        "item_code": row["item_code"],
        "item_name": row["item_name"],
        "qty": row["qty"],
    }


def _response_state(groups, manual_rows, restricted, partial):
    if not groups:
        return "manual"
    if manual_rows or len(groups) > 1:
        return "mixed"
    if restricted:
        return "restricted"
    if partial:
        return "partial"
    return "linked"


def _warnings(manual_rows, restricted, partial):
    warnings = []
    if manual_rows:
        warnings.append(_("Some item rows have no upstream commercial source."))
    if restricted:
        warnings.append(_("Some upstream sources are restricted."))
    if partial:
        warnings.append(_("Some source chains cannot be resolved back to a Sales Order."))
    return warnings


def _text(value):
    return str(value or "").strip()
