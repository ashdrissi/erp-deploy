from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


CONFIRM_TOKEN = "DELETE_ORDERLIFT_BUSINESS_DATA"
SAMPLE_LIMIT = 10


KEEP_DOCTYPES = [
    "User",
    "Item",
    "Item Group",
    "UOM",
    "Brand",
    "Item Price",
    "Price List",
    "Product Bundle",
    "Item Packaging Profile",
    "Container Profile",
    "Pricing Customs Policy",
    "Pricing Scenario",
    "Pricing Benchmark Policy",
    "Agent Pricing Rules",
    "Dimensioning Set",
    "Customer Segmentation Engine",
    "Portal Customer Group Policy",
    "CRM Business Type",
    "CRM Segment",
    "Partner Campaign Status",
    "Installation Stage",
    "Sales Stage",
    "Project Status",
    "Orderlift Order Status",
    "QC Checklist Template",
]

DELETE_ORDER = [
    "GL Entry",
    "Payment Ledger Entry",
    "Stock Ledger Entry",
    "Bin",
    "Payment Request",
    "Delivery Trip",
    "Installation Note",
    "Material Request",
    "Supplier Quotation",
    "Payment Entry",
    "Sales Invoice",
    "Purchase Invoice",
    "Delivery Note",
    "Stock Entry",
    "Purchase Receipt",
    "Purchase Order",
    "Sales Order",
    "Quotation",
    "Portal Quote Request",
    "Partner Campaign",
    "SAV Ticket",
    "Task",
    "Project",
    "Project Workflow Case",
    "Forecast Load Plan",
    "Shipment Analysis",
    "Sales Commission",
    "Opportunity",
    "Lead",
    "Prospect",
    "Customer",
    "Contact",
    "Address",
    "Dynamic Link",
]


@frappe.whitelist()
def run(
    dry_run: int = 1,
    confirm: str | None = None,
    keep_customers: int = 0,
    keep_suppliers: int = 1,
    keep_customer_segmentation_engines: int = 1,
    keep_portal_policies: int = 1,
    force: int = 0,
):
    """Clean demo/transactional business data while preserving users, items, and policies.

    Defaults are intentionally conservative: dry-run is on, suppliers are kept because
    buying item prices and article sourcing can still reference them.
    """
    dry_run = cint(dry_run)
    if not dry_run and confirm != CONFIRM_TOKEN:
        frappe.throw(_("Pass confirm={0} to run the destructive cleanup.").format(CONFIRM_TOKEN))

    keep_doctypes = list(KEEP_DOCTYPES)
    delete_doctypes = list(DELETE_ORDER)

    if cint(keep_customers):
        _move_doctype("Customer", delete_doctypes, keep_doctypes)
    if cint(keep_suppliers):
        keep_doctypes.append("Supplier")
    else:
        delete_doctypes.append("Supplier")
    if not cint(keep_customer_segmentation_engines):
        _move_doctype("Customer Segmentation Engine", keep_doctypes, delete_doctypes)
    if not cint(keep_portal_policies):
        _move_doctype("Portal Customer Group Policy", keep_doctypes, delete_doctypes)

    result = {
        "dry_run": bool(dry_run),
        "force": bool(cint(force)),
        "confirm_required_for_delete": CONFIRM_TOKEN,
        "kept": _describe_doctypes(keep_doctypes),
        "to_delete": _describe_doctypes(delete_doctypes),
        "deleted": [],
        "failures": [],
    }

    if dry_run:
        return result

    for doctype in delete_doctypes:
        if cint(force):
            result["deleted"].append(_force_delete_doctype_records(doctype, result["failures"]))
        else:
            result["deleted"].append(_delete_doctype_records(doctype, result["failures"]))

    frappe.db.commit()
    frappe.clear_cache()
    return result


def _move_doctype(doctype: str, source: list[str], target: list[str]) -> None:
    if doctype in source:
        source.remove(doctype)
    if doctype not in target:
        target.append(doctype)


def _describe_doctypes(doctypes: list[str]) -> list[dict]:
    rows = []
    for doctype in doctypes:
        if not frappe.db.exists("DocType", doctype):
            rows.append({"doctype": doctype, "exists": False, "count": 0, "sample": []})
            continue
        names = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=SAMPLE_LIMIT)
        rows.append(
            {
                "doctype": doctype,
                "exists": True,
                "count": frappe.db.count(doctype),
                "sample": names,
            }
        )
    return rows


def _delete_doctype_records(doctype: str, failures: list[dict]) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "exists": False, "deleted": 0}

    names = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=0)
    deleted = 0
    for name in names:
        try:
            docstatus = frappe.db.get_value(doctype, name, "docstatus")
            if cint(docstatus) == 1:
                doc = frappe.get_doc(doctype, name)
                doc.cancel()
            frappe.delete_doc(doctype, name, ignore_permissions=True)
            deleted += 1
        except Exception as exc:
            failures.append({"doctype": doctype, "name": name, "error": str(exc)})

    return {"doctype": doctype, "exists": True, "attempted": len(names), "deleted": deleted}


def _force_delete_doctype_records(doctype: str, failures: list[dict]) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "exists": False, "deleted": 0}

    names = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=0)
    if not names:
        return {"doctype": doctype, "exists": True, "attempted": 0, "deleted": 0, "force": True}

    try:
        _delete_child_rows(doctype, names)
        frappe.db.delete(doctype, {"name": ["in", names]})
        return {"doctype": doctype, "exists": True, "attempted": len(names), "deleted": len(names), "force": True}
    except Exception as exc:
        failures.append({"doctype": doctype, "name": "*", "error": str(exc)})
        return {"doctype": doctype, "exists": True, "attempted": len(names), "deleted": 0, "force": True}


def _delete_child_rows(doctype: str, parent_names: list[str]) -> None:
    meta = frappe.get_meta(doctype)
    for field in meta.get_table_fields():
        child_doctype = field.options
        if not child_doctype or not frappe.db.exists("DocType", child_doctype):
            continue
        child_names = frappe.get_all(
            child_doctype,
            filters={"parenttype": doctype, "parent": ["in", parent_names]},
            pluck="name",
            limit_page_length=0,
        )
        if child_names:
            _delete_child_rows(child_doctype, child_names)
            frappe.db.delete(child_doctype, {"name": ["in", child_names]})
