from __future__ import annotations

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt


TARGET_COMPANIES = [
    {"name": "Orderlift", "abbr": "OL", "currency": "MAD", "country": "Morocco", "is_parent": 1},
    {"name": "Orderlift Maroc Distribution", "abbr": "OMD", "currency": "MAD", "country": "Morocco", "parent": "Orderlift", "operating": 1},
    {"name": "Orderlift Maroc Installation", "abbr": "OMI", "currency": "MAD", "country": "Morocco", "parent": "Orderlift", "operating": 1},
    {"name": "Orderlift Turkey", "abbr": "OTR", "currency": "TRY", "country": "Turkey", "parent": "Orderlift", "operating": 1},
]
TARGET_COMPANY_NAMES = {company["name"] for company in TARGET_COMPANIES}
OPERATING_COMPANY_NAMES = {company["name"] for company in TARGET_COMPANIES if company.get("operating")}
TARGET_CURRENCIES = ("MAD", "TRY", "USD")
VAT_RATE = 20
REPORTING_COMPANY_FIELD = "custom_orderlift_reporting_company"
BASE_WAREHOUSE_FIELD = "custom_orderlift_base_warehouse"
VAT_ONLY_FIELD = "custom_orderlift_vat_only"


@frappe.whitelist()
def after_migrate():
    return run(cleanup=0, dry_run=0)


@frappe.whitelist()
def run(cleanup=0, dry_run=0):
    frappe.only_for("System Manager")
    cleanup = cint(cleanup)
    dry_run = cint(dry_run)
    summary = _summary(cleanup=cleanup, dry_run=dry_run)

    _ensure_custom_fields(summary, dry_run=dry_run)
    _ensure_currencies(summary, dry_run=dry_run)
    _ensure_companies(summary, dry_run=dry_run)
    _ensure_main_warehouses(summary, dry_run=dry_run)
    _ensure_vat_templates(summary, dry_run=dry_run)
    if cleanup:
        _cleanup_extra_records(summary, dry_run=dry_run)

    if not dry_run:
        frappe.db.commit()
        for doctype in ["Company", "Warehouse", "Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"]:
            frappe.clear_cache(doctype=doctype)
    return summary


def _summary(cleanup=0, dry_run=0):
    return {
        "cleanup": bool(cleanup),
        "dry_run": bool(dry_run),
        "created": [],
        "updated": [],
        "deleted": [],
        "disabled": [],
        "skipped": [],
        "warnings": [],
    }


def _ensure_custom_fields(summary, dry_run=0):
    fields = {
        "Company": [
            {
                "fieldname": REPORTING_COMPANY_FIELD,
                "label": "Orderlift Reporting Company",
                "fieldtype": "Check",
                "insert_after": "default_currency",
                "default": "0",
                "in_standard_filter": 1,
            }
        ],
        "Warehouse": [
            {
                "fieldname": BASE_WAREHOUSE_FIELD,
                "label": "Orderlift Base Warehouse",
                "fieldtype": "Check",
                "insert_after": "company",
                "default": "0",
                "in_standard_filter": 1,
            }
        ],
        "Sales Taxes and Charges Template": [
            {
                "fieldname": VAT_ONLY_FIELD,
                "label": "Orderlift VAT Only",
                "fieldtype": "Check",
                "insert_after": "company",
                "default": "0",
                "in_standard_filter": 1,
            }
        ],
        "Purchase Taxes and Charges Template": [
            {
                "fieldname": VAT_ONLY_FIELD,
                "label": "Orderlift VAT Only",
                "fieldtype": "Check",
                "insert_after": "company",
                "default": "0",
                "in_standard_filter": 1,
            }
        ],
    }
    if dry_run:
        summary["skipped"].append("custom fields (dry run)")
        return
    create_custom_fields(fields, update=True, ignore_validate=True)
    summary["updated"].append("custom fields for reporting companies, base warehouses, and VAT templates")


def _ensure_currencies(summary, dry_run=0):
    if not _exists("DocType", "Currency"):
        return
    for currency in TARGET_CURRENCIES:
        if _exists("Currency", currency):
            continue
        if dry_run:
            summary["created"].append(f"Currency {currency}")
            continue
        doc = frappe.new_doc("Currency")
        doc.currency_name = currency
        doc.enabled = 1
        doc.insert(ignore_permissions=True)
        summary["created"].append(f"Currency {currency}")


def _ensure_companies(summary, dry_run=0):
    if not _exists("DocType", "Company"):
        return
    for definition in TARGET_COMPANIES:
        name = definition["name"]
        values = {
            "default_currency": definition["currency"],
        }
        if _has_field("Company", "abbr"):
            values["abbr"] = definition["abbr"]
        if _has_field("Company", "country"):
            values["country"] = definition["country"]
        if _has_field("Company", REPORTING_COMPANY_FIELD):
            values[REPORTING_COMPANY_FIELD] = 1
        if _has_field("Company", "parent_company") and definition.get("parent") and _exists("Company", definition["parent"]):
            values["parent_company"] = definition["parent"]
        elif _has_field("Company", "parent_company"):
            values["parent_company"] = ""
        if _has_field("Company", "is_group") and definition.get("is_parent") and not _company_has_transactions(name):
            values["is_group"] = 1

        if _exists("Company", name):
            if dry_run:
                summary["updated"].append(f"Company {name}")
            else:
                frappe.db.set_value("Company", name, values, update_modified=False)
                summary["updated"].append(f"Company {name}")
            continue

        if dry_run:
            summary["created"].append(f"Company {name}")
            continue
        doc = frappe.new_doc("Company")
        doc.company_name = name
        for fieldname, value in values.items():
            setattr(doc, fieldname, value)
        doc.insert(ignore_permissions=True)
        summary["created"].append(f"Company {name}")

    if _has_field("Company", REPORTING_COMPANY_FIELD):
        extra_names = [name for name in frappe.get_all("Company", pluck="name", limit_page_length=0) if name not in TARGET_COMPANY_NAMES]
        if extra_names:
            if dry_run:
                summary["updated"].append(f"unmark {len(extra_names)} non-target companies")
            else:
                for name in extra_names:
                    frappe.db.set_value("Company", name, REPORTING_COMPANY_FIELD, 0, update_modified=False)


def _ensure_main_warehouses(summary, dry_run=0):
    if not _exists("DocType", "Warehouse"):
        return
    for definition in TARGET_COMPANIES:
        if not _exists("Company", definition["name"]):
            summary["warnings"].append(f"Skipped warehouse for missing company {definition['name']}")
            continue
        parent = _ensure_parent_warehouse(definition, summary, dry_run=dry_run)
        target_name = _warehouse_docname("Main Warehouse", definition["abbr"])
        if _exists("Warehouse", target_name):
            if not dry_run:
                values = {"company": definition["name"]}
                if _has_field("Warehouse", BASE_WAREHOUSE_FIELD):
                    values[BASE_WAREHOUSE_FIELD] = 1
                if parent and _has_field("Warehouse", "parent_warehouse"):
                    values["parent_warehouse"] = parent
                frappe.db.set_value("Warehouse", target_name, values, update_modified=False)
            summary["updated"].append(f"Warehouse {target_name}")
            continue
        if dry_run:
            summary["created"].append(f"Warehouse {target_name}")
            continue
        doc = frappe.new_doc("Warehouse")
        doc.warehouse_name = "Main Warehouse"
        doc.company = definition["name"]
        doc.is_group = 0
        if parent and doc.meta.get_field("parent_warehouse"):
            doc.parent_warehouse = parent
        if doc.meta.get_field(BASE_WAREHOUSE_FIELD):
            setattr(doc, BASE_WAREHOUSE_FIELD, 1)
        doc.insert(ignore_permissions=True)
        summary["created"].append(f"Warehouse {doc.name}")


def _ensure_parent_warehouse(definition, summary, dry_run=0):
    target_name = _warehouse_docname("All Warehouses", definition["abbr"])
    if _exists("Warehouse", target_name):
        return target_name
    rows = frappe.get_all(
        "Warehouse",
        filters={"company": definition["name"], "is_group": 1},
        fields=["name"],
        order_by="lft asc",
        limit_page_length=1,
    )
    if rows:
        return rows[0].name
    if dry_run:
        summary["created"].append(f"Warehouse {target_name}")
        return target_name
    doc = frappe.new_doc("Warehouse")
    doc.warehouse_name = "All Warehouses"
    doc.company = definition["name"]
    doc.is_group = 1
    doc.insert(ignore_permissions=True)
    summary["created"].append(f"Warehouse {doc.name}")
    return doc.name


def _ensure_vat_templates(summary, dry_run=0):
    for company in TARGET_COMPANIES:
        if not company.get("operating") or not _exists("Company", company["name"]):
            continue
        for doctype, prefix in [
            ("Sales Taxes and Charges Template", "Sales"),
            ("Purchase Taxes and Charges Template", "Purchase"),
        ]:
            if not _exists("DocType", doctype):
                continue
            template_title = f"VAT {VAT_RATE}% {prefix} - {company['name']}"
            template_name = _tax_template_docname(template_title, company["abbr"])
            account = _get_or_create_tax_account(company, summary, dry_run=dry_run)
            if not account:
                summary["warnings"].append(f"Skipped {template_title}: no tax account parent found")
                continue
            existing = _tax_template_name(doctype, template_name, template_title, company["name"])
            if existing:
                if not dry_run:
                    doc = frappe.get_doc(doctype, existing)
                    _apply_vat_template(doc, company["name"], account)
                    doc.save(ignore_permissions=True)
                summary["updated"].append(existing)
                continue
            if dry_run:
                summary["created"].append(template_title)
                continue
            doc = frappe.new_doc(doctype)
            doc.title = template_title
            if doc.meta.get_field("company"):
                doc.company = company["name"]
            _apply_vat_template(doc, company["name"], account)
            doc.insert(ignore_permissions=True)
            summary["created"].append(doc.name)


def _apply_vat_template(doc, company: str, account: str):
    if doc.meta.get_field("company"):
        doc.company = company
    if doc.meta.get_field("is_default"):
        doc.is_default = 1
    if doc.meta.get_field(VAT_ONLY_FIELD):
        setattr(doc, VAT_ONLY_FIELD, 1)
    doc.set("taxes", [])
    doc.append(
        "taxes",
        {
            "charge_type": "On Net Total",
            "account_head": account,
            "description": f"VAT {VAT_RATE}%",
            "rate": VAT_RATE,
        },
    )


def _get_or_create_tax_account(company, summary, dry_run=0):
    company_name = company["name"]
    existing = frappe.get_all(
        "Account",
        filters={"company": company_name, "account_type": "Tax", "is_group": 0},
        fields=["name"],
        limit_page_length=1,
    ) if _exists("DocType", "Account") else []
    if existing:
        return existing[0].name
    parent = _tax_parent_account(company_name)
    if not parent:
        return ""
    account_name = "VAT 20%"
    full_name = f"{account_name} - {company['abbr']}"
    if _exists("Account", full_name):
        return full_name
    if dry_run:
        summary["created"].append(f"Account {full_name}")
        return full_name
    doc = frappe.new_doc("Account")
    doc.account_name = account_name
    doc.company = company_name
    doc.parent_account = parent
    doc.account_type = "Tax"
    doc.root_type = frappe.db.get_value("Account", parent, "root_type") or "Liability"
    doc.report_type = "Balance Sheet"
    doc.insert(ignore_permissions=True)
    summary["created"].append(f"Account {doc.name}")
    return doc.name


def _tax_parent_account(company_name: str) -> str:
    if not _exists("DocType", "Account"):
        return ""
    preferred = frappe.get_all(
        "Account",
        filters={"company": company_name, "is_group": 1, "account_name": ["like", "%Duties and Taxes%"]},
        fields=["name"],
        limit_page_length=1,
    )
    if preferred:
        return preferred[0].name
    fallback = frappe.get_all(
        "Account",
        filters={"company": company_name, "is_group": 1, "root_type": "Liability"},
        fields=["name"],
        order_by="lft desc",
        limit_page_length=1,
    )
    return fallback[0].name if fallback else ""


def _cleanup_extra_records(summary, dry_run=0):
    _cleanup_extra_tax_templates(summary, dry_run=dry_run)
    _cleanup_extra_warehouses(summary, dry_run=dry_run)
    _cleanup_extra_companies(summary, dry_run=dry_run)


def _cleanup_extra_tax_templates(summary, dry_run=0):
    targets = {
        _tax_template_docname(f"VAT {VAT_RATE}% {prefix} - {company['name']}", company["abbr"])
        for company in TARGET_COMPANIES
        if company.get("operating")
        for prefix in ["Sales", "Purchase"]
    }
    for doctype in ["Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"]:
        if not _exists("DocType", doctype):
            continue
        for name in frappe.get_all(doctype, pluck="name", limit_page_length=0):
            if name in targets:
                continue
            _delete_or_disable(doctype, name, summary, dry_run=dry_run)


def _cleanup_extra_warehouses(summary, dry_run=0):
    if not _exists("DocType", "Warehouse"):
        return
    keep = set()
    for definition in TARGET_COMPANIES:
        if definition.get("operating"):
            keep.add(_warehouse_docname("All Warehouses", definition["abbr"]))
            keep.add(_warehouse_docname("Main Warehouse", definition["abbr"]))
    for name in frappe.get_all("Warehouse", pluck="name", limit_page_length=0):
        if name in keep:
            continue
        _delete_or_disable("Warehouse", name, summary, dry_run=dry_run)


def _cleanup_extra_companies(summary, dry_run=0):
    if not _exists("DocType", "Company"):
        return
    if _has_field("Company", "parent_company") and not dry_run:
        for definition in TARGET_COMPANIES:
            parent = definition.get("parent") if definition.get("operating") else ""
            if _exists("Company", definition["name"]):
                frappe.db.set_value("Company", definition["name"], "parent_company", parent or "", update_modified=False)
        for name in frappe.get_all("Company", pluck="name", limit_page_length=0):
            if name in TARGET_COMPANY_NAMES:
                continue
            children = frappe.get_all("Company", filters={"parent_company": name}, pluck="name", limit_page_length=0)
            for child in children:
                frappe.db.set_value("Company", child, "parent_company", "Orderlift" if child in TARGET_COMPANY_NAMES and child != "Orderlift" else "", update_modified=False)
    for name in frappe.get_all("Company", pluck="name", limit_page_length=0):
        if name in TARGET_COMPANY_NAMES:
            continue
        _delete_or_disable("Company", name, summary, dry_run=dry_run)


def _delete_or_disable(doctype: str, name: str, summary, dry_run=0):
    if dry_run:
        summary["deleted"].append(f"{doctype} {name}")
        return
    try:
        frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
        summary["deleted"].append(f"{doctype} {name}")
    except Exception as exc:
        if _has_field(doctype, "disabled"):
            frappe.db.set_value(doctype, name, "disabled", 1, update_modified=False)
            summary["disabled"].append(f"{doctype} {name}")
        else:
            summary["warnings"].append(f"Skipped {doctype} {name}: {exc}")


def _company_has_transactions(company: str) -> bool:
    if not company or not _exists("Company", company):
        return False
    for doctype in ["GL Entry", "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice", "Stock Ledger Entry"]:
        if _exists("DocType", doctype) and _has_field(doctype, "company") and frappe.db.exists(doctype, {"company": company}):
            return True
    return False


def _warehouse_docname(warehouse_name: str, abbr: str) -> str:
    return f"{warehouse_name} - {abbr}"


def _tax_template_docname(title: str, abbr: str) -> str:
    return f"{title} - {abbr}"


def _tax_template_name(doctype: str, docname: str, title: str, company: str) -> str:
    if _exists(doctype, docname):
        return docname
    filters = {"title": title}
    if _has_field(doctype, "company"):
        filters["company"] = company
    return frappe.db.get_value(doctype, filters, "name") or ""


def _exists(doctype: str, name=None) -> bool:
    return bool(frappe.db.exists(doctype, name))


def _has_field(doctype: str, fieldname: str) -> bool:
    if not _exists("DocType", doctype):
        return False
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def as_json(cleanup=0, dry_run=1):
    return json.dumps(run(cleanup=cleanup, dry_run=dry_run), indent=2, default=str)
