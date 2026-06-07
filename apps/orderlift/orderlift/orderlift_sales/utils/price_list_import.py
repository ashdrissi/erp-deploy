from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.company_scope import company_field_for
from orderlift.menu_access import get_allowed_companies, resolve_current_company, user_can_access_company


PRICE_LIST_IMPORT_EXCLUDED_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
    "amended_from",
}

PRICE_LIST_COPY_EXCLUDED_FIELDS = PRICE_LIST_IMPORT_EXCLUDED_FIELDS | {
    "price_list_name",
    "custom_company",
    "company",
    "custom_last_auto_rebuild_on",
    "custom_last_auto_rebuild_status",
}

ITEM_PRICE_COPY_EXCLUDED_FIELDS = PRICE_LIST_IMPORT_EXCLUDED_FIELDS | {"price_list"}


@frappe.whitelist()
def get_price_list_import_context() -> dict:
    user = frappe.session.user
    companies = get_allowed_companies(user)
    current_company = resolve_current_company(user=user, allowed_companies=companies)
    return {
        "companies": companies,
        "current_company": current_company,
        "can_import": len(companies) > 1,
    }


@frappe.whitelist()
def import_price_list_from_existing(
    source_price_list: str,
    target_price_list_name: str,
    target_company: str | None = None,
    copy_item_prices: int = 1,
) -> dict:
    source_price_list = (source_price_list or "").strip()
    target_price_list_name = (target_price_list_name or "").strip()
    target_company = (target_company or "").strip()

    if not source_price_list:
        frappe.throw(_("Select a source Price List."))
    if not target_price_list_name:
        frappe.throw(_("Enter the new Price List name."))
    if not frappe.db.exists("Price List", source_price_list):
        frappe.throw(_("Source Price List {0} was not found.").format(source_price_list))
    if frappe.db.exists("Price List", target_price_list_name):
        frappe.throw(_("Price List {0} already exists. Choose another name.").format(target_price_list_name))

    target_company = _resolve_target_company(target_company)
    source_doc = frappe.get_doc("Price List", source_price_list)
    source_company = _get_doc_company(source_doc)
    if source_company and not user_can_access_company(source_company):
        frappe.throw(_("You do not have access to source company {0}.").format(source_company))

    target_doc = _copy_price_list_doc(source_doc, target_price_list_name, target_company)
    target_doc.insert(ignore_permissions=True)

    item_price_count = 0
    if cint(copy_item_prices):
        item_price_count = _copy_item_prices(source_price_list, target_doc.name)

    return {
        "source_price_list": source_price_list,
        "source_company": source_company,
        "price_list": target_doc.name,
        "target_company": target_company,
        "item_prices_created": item_price_count,
    }


def _resolve_target_company(target_company: str) -> str:
    if target_company:
        if not user_can_access_company(target_company):
            frappe.throw(_("You do not have access to company {0}.").format(target_company))
        return target_company
    company = resolve_current_company()
    if not company:
        frappe.throw(_("Set an active Company before importing a Price List."))
    return company


def _copy_price_list_doc(source_doc, target_price_list_name: str, target_company: str):
    target_doc = frappe.new_doc("Price List")
    _copy_doc_fields(source_doc, target_doc, PRICE_LIST_COPY_EXCLUDED_FIELDS)
    target_doc.price_list_name = target_price_list_name
    if _meta_has_field("Price List", "title"):
        target_doc.title = target_price_list_name
    company_field = company_field_for("Price List")
    if _meta_has_field("Price List", company_field):
        target_doc.set(company_field, target_company)
    if _meta_has_field("Price List", "custom_auto_rebuild_from_source_buying_prices"):
        target_doc.custom_auto_rebuild_from_source_buying_prices = 0
    return target_doc


def _copy_item_prices(source_price_list: str, target_price_list: str) -> int:
    rows = frappe.get_all(
        "Item Price",
        filters={"price_list": source_price_list},
        fields=["name"],
        order_by="item_code asc, valid_from desc, modified desc",
        limit_page_length=0,
    )
    created = 0
    for row in rows:
        source_doc = frappe.get_doc("Item Price", row.name)
        target_doc = frappe.new_doc("Item Price")
        _copy_doc_fields(source_doc, target_doc, ITEM_PRICE_COPY_EXCLUDED_FIELDS)
        target_doc.price_list = target_price_list
        _clear_invalid_item_price_uom(target_doc)
        target_doc.insert(ignore_permissions=True)
        created += 1
    return created


def _copy_doc_fields(source_doc, target_doc, excluded_fields: set[str]) -> None:
    for field in source_doc.meta.fields:
        fieldname = field.fieldname
        if not fieldname or fieldname in excluded_fields:
            continue
        if field.fieldtype in {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table"}:
            continue
        if not target_doc.meta.has_field(fieldname):
            continue
        target_doc.set(fieldname, source_doc.get(fieldname))


def _clear_invalid_item_price_uom(doc) -> None:
    item_code = (doc.get("item_code") or "").strip()
    uom = (doc.get("uom") or "").strip()
    if not item_code or not uom:
        return
    if uom == (frappe.db.get_value("Item", item_code, "stock_uom") or "").strip():
        return
    if frappe.db.exists("UOM Conversion Detail", {"parenttype": "Item", "parent": item_code, "uom": uom}):
        return
    doc.uom = ""


def _get_doc_company(doc) -> str:
    field = company_field_for(doc.doctype)
    if _meta_has_field(doc.doctype, field):
        return (doc.get(field) or "").strip()
    return ""


def _meta_has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False
