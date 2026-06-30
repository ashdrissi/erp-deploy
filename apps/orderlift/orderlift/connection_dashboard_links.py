from __future__ import annotations

import frappe
from frappe import _


MAX_ROUTE_NAMES = 500
DYNAMIC_REFERENCE_PAIRS = (
    ("prevdoc_doctype", "prevdoc_docname"),
    ("reference_doctype", "reference_name"),
    ("reference_type", "reference_name"),
    ("against_doctype", "against_docname"),
    ("against_voucher_type", "against_voucher"),
)


@frappe.whitelist()
def get_connection_route(source_doctype: str, source_name: str, target_doctype: str) -> dict:
    source_doctype = (source_doctype or "").strip()
    source_name = (source_name or "").strip()
    target_doctype = (target_doctype or "").strip()

    _validate_doctype(source_doctype)
    _validate_doctype(target_doctype)
    if not source_name or not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("Source document not found."))

    source_doc = frappe.get_doc(source_doctype, source_name)
    source_doc.check_permission("read")
    if not frappe.has_permission(target_doctype, "read"):
        frappe.throw(_("Not permitted to read {0}.").format(_(target_doctype)))

    names = _find_connection_names(source_doc, target_doctype)
    names = _filter_readable_names(target_doctype, names)

    return {
        "source_doctype": source_doctype,
        "source_name": source_name,
        "target_doctype": target_doctype,
        "count": len(names),
        "names": names,
        "route_options": {"name": ["in", names]} if names else {},
        "truncated": len(names) >= MAX_ROUTE_NAMES,
    }


def _validate_doctype(doctype: str) -> None:
    if not doctype or not frappe.db.exists("DocType", doctype):
        frappe.throw(_("Invalid DocType."))


def _find_connection_names(source_doc, target_doctype: str) -> set[str]:
    source_doctype = source_doc.doctype
    source_name = source_doc.name
    target_meta = frappe.get_meta(target_doctype)
    names: set[str] = set()

    names.update(_find_target_direct_links(target_meta, source_doctype, source_name))
    names.update(_find_target_child_links(target_meta, source_doctype, source_name))
    names.update(_find_target_dynamic_pairs(target_meta, source_doctype, source_name))
    names.update(_find_source_links(source_doc, target_doctype))

    return {name for name in names if name}


def _find_target_direct_links(target_meta, source_doctype: str, source_name: str) -> set[str]:
    names: set[str] = set()
    for field in target_meta.fields:
        if field.fieldtype == "Link" and field.options == source_doctype:
            names.update(_pluck_names(target_meta.name, {field.fieldname: source_name}))
            continue
        if field.fieldtype == "Dynamic Link" and field.options and target_meta.get_field(field.options):
            names.update(_pluck_names(target_meta.name, {field.fieldname: source_name, field.options: source_doctype}))
    return names


def _find_target_child_links(target_meta, source_doctype: str, source_name: str) -> set[str]:
    names: set[str] = set()
    for table_field in target_meta.get_table_fields():
        child_doctype = table_field.options
        if not child_doctype:
            continue
        child_meta = frappe.get_meta(child_doctype)
        child_parent_names: set[str] = set()

        for field in child_meta.fields:
            if field.fieldtype == "Link" and field.options == source_doctype:
                child_parent_names.update(_pluck_child_parents(child_doctype, {field.fieldname: source_name}))
                continue
            if field.fieldtype == "Dynamic Link" and field.options and child_meta.get_field(field.options):
                child_parent_names.update(
                    _pluck_child_parents(child_doctype, {field.fieldname: source_name, field.options: source_doctype})
                )

        for doctype_field, name_field in DYNAMIC_REFERENCE_PAIRS:
            if child_meta.get_field(doctype_field) and child_meta.get_field(name_field):
                child_parent_names.update(
                    _pluck_child_parents(child_doctype, {doctype_field: source_doctype, name_field: source_name})
                )

        names.update(_filter_existing_parent_names(target_meta.name, child_parent_names))
    return names


def _find_target_dynamic_pairs(target_meta, source_doctype: str, source_name: str) -> set[str]:
    names: set[str] = set()
    for doctype_field, name_field in DYNAMIC_REFERENCE_PAIRS:
        if target_meta.get_field(doctype_field) and target_meta.get_field(name_field):
            names.update(_pluck_names(target_meta.name, {doctype_field: source_doctype, name_field: source_name}))
    return names


def _find_source_links(source_doc, target_doctype: str) -> set[str]:
    source_meta = frappe.get_meta(source_doc.doctype)
    names: set[str] = set()

    for field in source_meta.fields:
        if field.fieldtype == "Link" and field.options == target_doctype:
            names.add(source_doc.get(field.fieldname))
            continue
        if field.fieldtype == "Dynamic Link" and field.options and source_doc.get(field.options) == target_doctype:
            names.add(source_doc.get(field.fieldname))

    for doctype_field, name_field in DYNAMIC_REFERENCE_PAIRS:
        if source_meta.get_field(doctype_field) and source_meta.get_field(name_field):
            if source_doc.get(doctype_field) == target_doctype:
                names.add(source_doc.get(name_field))

    for table_field in source_meta.get_table_fields():
        child_rows = source_doc.get(table_field.fieldname) or []
        child_meta = frappe.get_meta(table_field.options)
        for row in child_rows:
            for field in child_meta.fields:
                if field.fieldtype == "Link" and field.options == target_doctype:
                    names.add(row.get(field.fieldname))
                    continue
                if field.fieldtype == "Dynamic Link" and field.options and row.get(field.options) == target_doctype:
                    names.add(row.get(field.fieldname))
            for doctype_field, name_field in DYNAMIC_REFERENCE_PAIRS:
                if child_meta.get_field(doctype_field) and child_meta.get_field(name_field):
                    if row.get(doctype_field) == target_doctype:
                        names.add(row.get(name_field))

    return names


def _pluck_names(doctype: str, filters: dict) -> set[str]:
    return set(frappe.get_all(doctype, filters=filters, pluck="name", limit_page_length=MAX_ROUTE_NAMES))


def _pluck_child_parents(child_doctype: str, filters: dict) -> set[str]:
    child_filters = dict(filters)
    child_filters["parent"] = ["is", "set"]
    return set(frappe.get_all(child_doctype, filters=child_filters, pluck="parent", limit_page_length=MAX_ROUTE_NAMES))


def _filter_existing_parent_names(parent_doctype: str, parent_names: set[str]) -> set[str]:
    if not parent_names:
        return set()
    return set(
        frappe.get_all(
            parent_doctype,
            filters={"name": ["in", list(parent_names)[:MAX_ROUTE_NAMES]]},
            pluck="name",
            limit_page_length=MAX_ROUTE_NAMES,
        )
    )


def _filter_readable_names(doctype: str, names: set[str]) -> list[str]:
    if not names:
        return []
    rows = frappe.get_list(
        doctype,
        filters={"name": ["in", list(names)[:MAX_ROUTE_NAMES]]},
        fields=["name"],
        limit_page_length=MAX_ROUTE_NAMES,
    )
    return sorted(row.name for row in rows)
