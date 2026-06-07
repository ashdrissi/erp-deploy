import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import resolve_current_company


def current_company():
    return resolve_current_company(user=frappe.session.user)


def price_list_filters(kind=None, company=None):
    filters = {}
    if _has_column("Price List", "enabled"):
        filters["enabled"] = 1
    if kind == "buying" and _has_column("Price List", "buying"):
        filters["buying"] = 1
    if kind == "selling" and _has_column("Price List", "selling"):
        filters["selling"] = 1
    company = (company or current_company() or "").strip()
    if company and _has_column("Price List", "custom_company"):
        filters["custom_company"] = company
    return filters


def get_price_lists(kind=None, fields=None, company=None):
    fields = fields or ["name"]
    return frappe.get_all(
        "Price List",
        filters=price_list_filters(kind=kind, company=company),
        fields=fields,
        order_by="name asc",
        limit_page_length=0,
    )


def get_price_list_names(kind=None, company=None):
    return frappe.get_all(
        "Price List",
        filters=price_list_filters(kind=kind, company=company),
        pluck="name",
        order_by="name asc",
        limit_page_length=0,
    )


def validate_price_list_scope(price_list_name, kind=None, required=False, company=None):
    price_list_name = (price_list_name or "").strip()
    if not price_list_name:
        if required:
            frappe.throw(_("Price List is required."))
        return ""

    fields = ["name"]
    if kind == "buying" and _has_column("Price List", "buying"):
        fields.append("buying")
    if kind == "selling" and _has_column("Price List", "selling"):
        fields.append("selling")
    if _has_column("Price List", "custom_company"):
        fields.append("custom_company")

    values = frappe.db.get_value("Price List", price_list_name, fields, as_dict=True)
    if not values:
        frappe.throw(_("Price List {0} does not exist.").format(price_list_name))

    if kind == "buying" and "buying" in fields and cint(values.get("buying")) != 1:
        frappe.throw(_("Price List {0} is not a buying price list.").format(price_list_name))
    if kind == "selling" and "selling" in fields and cint(values.get("selling")) != 1:
        frappe.throw(_("Price List {0} is not a selling price list.").format(price_list_name))

    company = (company or current_company() or "").strip()
    if company and "custom_company" in fields and (values.get("custom_company") or "").strip() != company:
        frappe.throw(_("Price List {0} does not belong to company {1}.").format(price_list_name, company))
    return price_list_name


def apply_price_list_company(doc, company=None):
    company = (company or current_company() or "").strip()
    if company and _doc_has_field(doc, "custom_company"):
        setter = getattr(doc, "set", None)
        if callable(setter):
            setter("custom_company", company)
        else:
            setattr(doc, "custom_company", company)


def _has_column(doctype, fieldname):
    checker = getattr(getattr(frappe, "db", None), "has_column", None)
    return bool(checker(doctype, fieldname)) if callable(checker) else False


def _doc_has_field(doc, fieldname):
    meta = getattr(doc, "meta", None)
    has_field = getattr(meta, "has_field", None)
    if callable(has_field):
        return bool(has_field(fieldname))
    return hasattr(doc, fieldname)
