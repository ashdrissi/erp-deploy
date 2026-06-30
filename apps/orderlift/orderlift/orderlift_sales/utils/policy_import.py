from __future__ import annotations

import frappe
from frappe import _

from orderlift.company_scope import company_field_for
from orderlift.menu_access import get_allowed_companies, resolve_current_company, user_can_access_company


SUPPORTED_POLICY_DOCTYPES = {"Pricing Benchmark Policy", "Pricing Customs Policy"}

POLICY_IMPORT_EXCLUDED_FIELDS = {
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

POLICY_COPY_EXCLUDED_FIELDS = POLICY_IMPORT_EXCLUDED_FIELDS | {"policy_name", "company", "custom_company"}


@frappe.whitelist()
def get_policy_import_context(policy_doctype: str) -> dict:
    policy_doctype = _validate_policy_doctype(policy_doctype)
    user = frappe.session.user
    companies = get_allowed_companies(user)
    current_company = resolve_current_company(user=user, allowed_companies=companies)
    return {
        "policy_doctype": policy_doctype,
        "companies": companies,
        "current_company": current_company,
        "can_import": bool(companies),
    }


@frappe.whitelist()
def import_policy_from_existing(
    policy_doctype: str,
    source_policy: str,
    target_policy_name: str,
    target_company: str | None = None,
) -> dict:
    policy_doctype = _validate_policy_doctype(policy_doctype)
    source_policy = (source_policy or "").strip()
    target_policy_name = (target_policy_name or "").strip()
    target_company = (target_company or "").strip()

    if not source_policy:
        frappe.throw(_("Select a source policy."))
    if not target_policy_name:
        frappe.throw(_("Enter the new policy name."))
    if not frappe.db.exists(policy_doctype, source_policy):
        frappe.throw(_("Source policy {0} was not found.").format(source_policy))
    if frappe.db.exists(policy_doctype, {"policy_name": target_policy_name}):
        frappe.throw(_("Policy {0} already exists. Choose another name.").format(target_policy_name))

    target_company = _resolve_target_company(target_company)
    source_doc = frappe.get_doc(policy_doctype, source_policy)
    source_company = _get_doc_company(source_doc)
    if source_company and not user_can_access_company(source_company):
        frappe.throw(_("You do not have access to source company {0}.").format(source_company))

    target_doc = _copy_policy_doc(source_doc, target_policy_name, target_company)
    target_doc.insert(ignore_permissions=True)

    return {
        "policy_doctype": policy_doctype,
        "source_policy": source_policy,
        "source_company": source_company,
        "policy": target_doc.name,
        "policy_name": target_doc.policy_name,
        "target_company": target_company,
    }


def _validate_policy_doctype(policy_doctype: str) -> str:
    policy_doctype = (policy_doctype or "").strip()
    if policy_doctype not in SUPPORTED_POLICY_DOCTYPES:
        frappe.throw(_("Policy import is not available for {0}.").format(policy_doctype or "-"))
    return policy_doctype


def _resolve_target_company(target_company: str) -> str:
    if target_company:
        if not user_can_access_company(target_company):
            frappe.throw(_("You do not have access to company {0}.").format(target_company))
        return target_company
    company = resolve_current_company()
    if not company:
        frappe.throw(_("Set an active Company before importing a policy."))
    return company


def _copy_policy_doc(source_doc, target_policy_name: str, target_company: str):
    target_doc = frappe.new_doc(source_doc.doctype)
    _copy_doc_fields(source_doc, target_doc, POLICY_COPY_EXCLUDED_FIELDS)
    target_doc.policy_name = target_policy_name
    company_field = company_field_for(source_doc.doctype)
    if _meta_has_field(source_doc.doctype, company_field):
        target_doc.set(company_field, target_company)
    return target_doc


def _copy_doc_fields(source_doc, target_doc, excluded_fields: set[str]) -> None:
    for field in source_doc.meta.fields:
        fieldname = field.fieldname
        if not fieldname or fieldname in excluded_fields:
            continue
        if field.fieldtype in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}:
            continue
        if not target_doc.meta.has_field(fieldname):
            continue
        if field.fieldtype == "Table":
            _copy_child_table(source_doc, target_doc, fieldname)
            continue
        target_doc.set(fieldname, source_doc.get(fieldname))


def _copy_child_table(source_doc, target_doc, fieldname: str) -> None:
    for source_row in source_doc.get(fieldname) or []:
        target_row = target_doc.append(fieldname, {})
        _copy_doc_fields(source_row, target_row, POLICY_IMPORT_EXCLUDED_FIELDS)


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
