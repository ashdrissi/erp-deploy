from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


CONFIRM_TOKEN = "DELETE_SELECTED_CRM_SALES_DATA"
SAMPLE_LIMIT = 10
TARGET_DOCTYPES = [
    "Sales Order",
    "Quotation",
    "Customer",
    "Prospect",
    "Opportunity",
    "Lead",
]


@frappe.whitelist()
def run(dry_run: int = 1, confirm: str | None = None, delete_pipeline_todos: int = 1, force: int = 0) -> dict:
    """Delete selected CRM/sales records without touching items, pricing, policies, or logistics docs."""
    frappe.only_for("System Manager")
    dry_run = cint(dry_run)
    delete_pipeline_todos = cint(delete_pipeline_todos)
    if not dry_run and confirm != CONFIRM_TOKEN:
        frappe.throw(_("Pass confirm={0} to run the destructive cleanup.").format(CONFIRM_TOKEN))

    result = {
        "dry_run": bool(dry_run),
        "force": bool(cint(force)),
        "confirm_required_for_delete": CONFIRM_TOKEN,
        "target_doctypes": TARGET_DOCTYPES,
        "delete_pipeline_todos": bool(delete_pipeline_todos),
        "before": _describe_targets(delete_pipeline_todos=delete_pipeline_todos),
        "deleted": [],
        "failures": [],
        "after": [],
    }
    if dry_run:
        return result

    if delete_pipeline_todos:
        result["deleted"].append(_delete_pipeline_todos(result["failures"]))

    for doctype in TARGET_DOCTYPES:
        if cint(force):
            result["deleted"].append(_force_delete_doctype_records(doctype, result["failures"]))
        else:
            result["deleted"].append(_delete_doctype_records(doctype, result["failures"]))

    frappe.db.commit()
    frappe.clear_cache()
    result["after"] = _describe_targets(delete_pipeline_todos=delete_pipeline_todos)
    return result


def _describe_targets(delete_pipeline_todos: int = 1) -> list[dict]:
    rows = [_describe_doctype(doctype) for doctype in TARGET_DOCTYPES]
    if delete_pipeline_todos and frappe.db.exists("DocType", "ToDo"):
        rows.append(_describe_pipeline_todos())
    return rows


def _describe_doctype(doctype: str) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "exists": False, "count": 0, "submitted": 0, "sample": []}
    names = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=SAMPLE_LIMIT)
    submitted = 0
    if frappe.get_meta(doctype).get_field("docstatus"):
        submitted = frappe.db.count(doctype, {"docstatus": 1})
    return {
        "doctype": doctype,
        "exists": True,
        "count": frappe.db.count(doctype),
        "submitted": submitted,
        "sample": names,
    }


def _describe_pipeline_todos() -> dict:
    count = frappe.db.count(
        "ToDo",
        {
            "reference_type": ["in", TARGET_DOCTYPES],
            "description": ["like", "%[Orderlift Pipeline]%"],
        },
    )
    sample = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": ["in", TARGET_DOCTYPES],
            "description": ["like", "%[Orderlift Pipeline]%"],
        },
        pluck="name",
        order_by="modified desc",
        limit_page_length=SAMPLE_LIMIT,
    )
    return {"doctype": "ToDo", "scope": "Orderlift pipeline ToDos for selected doctypes", "exists": True, "count": count, "sample": sample}


def _delete_pipeline_todos(failures: list[dict]) -> dict:
    if not frappe.db.exists("DocType", "ToDo"):
        return {"doctype": "ToDo", "exists": False, "deleted": 0}
    names = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": ["in", TARGET_DOCTYPES],
            "description": ["like", "%[Orderlift Pipeline]%"],
        },
        pluck="name",
        limit_page_length=0,
    )
    deleted = 0
    for name in names:
        try:
            frappe.delete_doc("ToDo", name, ignore_permissions=True, force=True)
            deleted += 1
        except Exception as exc:
            failures.append({"doctype": "ToDo", "name": name, "error": str(exc)})
    return {"doctype": "ToDo", "scope": "Orderlift pipeline ToDos for selected doctypes", "exists": True, "attempted": len(names), "deleted": deleted}


def _delete_doctype_records(doctype: str, failures: list[dict]) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "exists": False, "deleted": 0}

    names = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=0)
    deleted = 0
    for name in names:
        try:
            docstatus = frappe.db.get_value(doctype, name, "docstatus") if frappe.get_meta(doctype).get_field("docstatus") else None
            if cint(docstatus) == 1:
                doc = frappe.get_doc(doctype, name)
                doc.cancel()
            frappe.delete_doc(doctype, name, ignore_permissions=True, ignore_doctypes=TARGET_DOCTYPES)
            deleted += 1
        except Exception as exc:
            failures.append({"doctype": doctype, "name": name, "error": str(exc)})

    return {"doctype": doctype, "exists": True, "attempted": len(names), "deleted": deleted}


def _force_delete_doctype_records(doctype: str, failures: list[dict]) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "exists": False, "deleted": 0, "force": True}

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
