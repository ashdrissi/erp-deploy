from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.scripts import cleanup_business_data


CONFIRM_TOKEN = "DELETE_ORDERLIFT_ITEM_CATALOG"

CATALOG_DELETE_ORDER = [
    "Item Price",
    "Product Bundle",
    "Item",
]


@frappe.whitelist()
def run(
    dry_run: int = 1,
    confirm: str | None = None,
    delete_transactions: int = 1,
    force: int = 0,
    reset_category_sequences: int = 1,
) -> dict:
    """Reset item catalog data before a full reimport.

    Dry-run is enabled by default. Destructive execution requires CONFIRM_TOKEN.
    Transaction cleanup runs first so Item deletion is not blocked by linked documents.
    """
    frappe.only_for("System Manager")

    dry_run = cint(dry_run)
    force = cint(force)
    delete_transactions = cint(delete_transactions)
    reset_category_sequences = cint(reset_category_sequences)

    if not dry_run and confirm != CONFIRM_TOKEN:
        frappe.throw(_("Pass confirm={0} to delete the item catalog.").format(CONFIRM_TOKEN))

    result = {
        "dry_run": bool(dry_run),
        "force": bool(force),
        "delete_transactions": bool(delete_transactions),
        "confirm_required_for_delete": CONFIRM_TOKEN,
        "transaction_cleanup": None,
        "to_delete": _describe_doctypes(CATALOG_DELETE_ORDER),
        "deleted": [],
        "failures": [],
        "category_sequences_reset": 0,
    }

    if dry_run:
        return result

    if delete_transactions:
        result["transaction_cleanup"] = cleanup_business_data.run(
            dry_run=0,
            confirm=cleanup_business_data.CONFIRM_TOKEN,
            keep_customers=0,
            keep_suppliers=1,
            keep_customer_segmentation_engines=1,
            keep_portal_policies=1,
            force=force,
        )

    for doctype in CATALOG_DELETE_ORDER:
        result["deleted"].append(_delete_doctype_records(doctype, result["failures"], force=force))

    if reset_category_sequences and frappe.db.exists("DocType", "Item Category"):
        result["category_sequences_reset"] = frappe.db.count("Item Category")
        frappe.db.sql("UPDATE `tabItem Category` SET current_sequence = 0")

    frappe.db.commit()
    frappe.clear_cache()
    return result


def _describe_doctypes(doctypes: list[str]) -> list[dict]:
    rows = []
    for doctype in doctypes:
        if not frappe.db.exists("DocType", doctype):
            rows.append({"doctype": doctype, "exists": False, "count": 0, "sample": []})
            continue
        rows.append(
            {
                "doctype": doctype,
                "exists": True,
                "count": frappe.db.count(doctype),
                "sample": frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=10),
            }
        )
    return rows


def _delete_doctype_records(doctype: str, failures: list[dict], force: int = 0) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "exists": False, "deleted": 0}

    names = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit_page_length=0)
    deleted = 0
    for name in names:
        try:
            frappe.delete_doc(doctype, name, ignore_permissions=True, force=bool(cint(force)))
            deleted += 1
        except Exception as exc:
            failures.append({"doctype": doctype, "name": name, "error": str(exc)})

    return {"doctype": doctype, "exists": True, "attempted": len(names), "deleted": deleted}
