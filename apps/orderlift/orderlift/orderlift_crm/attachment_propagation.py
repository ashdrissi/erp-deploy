from __future__ import annotations

import frappe


def copy_opportunity_attachments_to_quotation(doc, method=None) -> None:
    opportunity = (doc.get("opportunity") or "").strip()
    if not opportunity:
        return
    copy_attachments("Opportunity", opportunity, doc.doctype, doc.name)


def copy_quotation_attachments_to_sales_order(doc, method=None) -> None:
    for quotation in _source_quotations(doc):
        copy_attachments("Quotation", quotation, doc.doctype, doc.name)


def copy_sales_order_attachments_to_downstream(doc, method=None) -> None:
    for sales_order in _source_sales_orders(doc):
        copy_attachments("Sales Order", sales_order, doc.doctype, doc.name)


def copy_attachments(source_doctype: str, source_name: str, target_doctype: str, target_name: str) -> int:
    if not (source_doctype and source_name and target_doctype and target_name):
        return 0
    if source_doctype == target_doctype and source_name == target_name:
        return 0
    source_files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": source_doctype, "attached_to_name": source_name, "is_folder": 0},
        fields=["name", "file_name", "file_url", "is_private", "folder", "content_hash"],
        limit_page_length=0,
        order_by="creation asc",
    )
    copied = 0
    for source in source_files:
        if _target_has_file(target_doctype, target_name, source):
            continue
        file_doc = frappe.new_doc("File")
        file_doc.file_name = source.get("file_name")
        file_doc.file_url = source.get("file_url")
        file_doc.is_private = source.get("is_private") or 0
        file_doc.folder = source.get("folder") or "Home/Attachments"
        file_doc.is_folder = 0
        file_doc.attached_to_doctype = target_doctype
        file_doc.attached_to_name = target_name
        if file_doc.meta.get_field("content_hash") and source.get("content_hash"):
            file_doc.content_hash = source.get("content_hash")
        file_doc.insert(ignore_permissions=True)
        copied += 1
    return copied


def _target_has_file(target_doctype: str, target_name: str, source: dict) -> bool:
    filters = {
        "attached_to_doctype": target_doctype,
        "attached_to_name": target_name,
        "is_folder": 0,
    }
    file_url = source.get("file_url")
    if file_url and frappe.db.exists("File", {**filters, "file_url": file_url}):
        return True
    file_name = source.get("file_name")
    if file_name and frappe.db.exists("File", {**filters, "file_name": file_name}):
        return True
    return False


def _source_quotations(doc) -> list[str]:
    names = [
        (row.get("prevdoc_docname") or "").strip()
        for row in doc.get("items") or []
        if (row.get("prevdoc_docname") or "").strip()
    ]
    return [name for name in dict.fromkeys(names) if frappe.db.exists("Quotation", name)]


def _source_sales_orders(doc) -> list[str]:
    fieldname = "against_sales_order" if getattr(doc, "doctype", None) == "Delivery Note" else "sales_order"
    names = [
        (row.get(fieldname) or "").strip()
        for row in doc.get("items") or []
        if (row.get(fieldname) or "").strip()
    ]
    return [name for name in dict.fromkeys(names) if frappe.db.exists("Sales Order", name)]
