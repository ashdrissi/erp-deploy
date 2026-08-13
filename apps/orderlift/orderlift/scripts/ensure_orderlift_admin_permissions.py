from __future__ import annotations

import frappe
from frappe.utils import cint

from orderlift.company_access import ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES
from orderlift.scripts.setup_startup_roles import ORDERLIFT_ADMIN_PERMISSIONS


ROLE = "Orderlift Admin"
READ_ONLY_DOCTYPE_PERMISSION = {"read": 1, "report": 1, "print": 1, "email": 1}
ADMIN_DOCTYPE_PERMISSIONS = ORDERLIFT_ADMIN_PERMISSIONS
PROTECTED_DOCTYPES = {
    "Assignment Rule",
    "Custom DocPerm",
    "DocPerm",
    "DocType",
    "Error Log",
    "Role",
    "User",
    "User Permission",
    "Workflow",
    "Workflow State",
}


@frappe.whitelist()
def run(dry_run: int = 1, exact_normalization: int = 0) -> dict:
    frappe.only_for("System Manager")
    dry_run = cint(dry_run)
    exact_normalization = cint(exact_normalization)
    results = {
        "dry_run": bool(dry_run),
        "exact_normalization": bool(exact_normalization),
        "custom_docperms": [],
    }
    if not frappe.db.exists("Role", ROLE):
        return {**results, "skipped": f"Role {ROLE} does not exist"}

    for doctype, permissions in ADMIN_DOCTYPE_PERMISSIONS.items():
        if doctype in PROTECTED_DOCTYPES:
            continue
        if frappe.db.exists("DocType", doctype):
            _ensure_custom_docperm(
                doctype,
                ROLE,
                _permission_flags_for_doctype(doctype, permissions),
                results,
                dry_run=dry_run,
                overwrite=exact_normalization,
            )

    if not dry_run:
        frappe.db.commit()
        frappe.clear_cache()
    return results


def _ensure_custom_docperm(
    doctype: str,
    role: str,
    values: dict,
    results: dict,
    *,
    dry_run: int = 0,
    overwrite: int = 0,
) -> None:
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    existing = frappe.db.exists("Custom DocPerm", filters)
    if existing:
        action = "updated" if overwrite else "exists"
        if overwrite and not dry_run:
            frappe.db.set_value("Custom DocPerm", existing, values)
    else:
        action = "created"
        if not dry_run:
            doc = frappe.get_doc(
                {
                    "doctype": "Custom DocPerm",
                    "parent": doctype,
                    "parenttype": "DocType",
                    "parentfield": "permissions",
                    "role": role,
                    "permlevel": 0,
                    **values,
                }
            )
            doc.insert(ignore_permissions=True)
    results["custom_docperms"].append({"doctype": doctype, "role": role, "action": action})


def _with_default_flags(values: dict) -> dict:
    defaults = {
        "read": 0,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "select": 0,
    }
    flags = {**defaults, **values}
    return flags


def _permission_flags_for_doctype(doctype: str, values: dict) -> dict:
    flags = _with_default_flags(values)
    if doctype in ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES:
        flags["share"] = 0
        flags["if_owner"] = 0
    return flags


def _ensure_has_role(parenttype: str, parent: str, role: str, results: dict) -> None:
    filters = {"parenttype": parenttype, "parent": parent, "role": role}
    if frappe.db.exists("Has Role", filters):
        action = "exists"
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Has Role",
                "parenttype": parenttype,
                "parent": parent,
                "parentfield": "roles",
                "role": role,
            }
        )
        doc.insert(ignore_permissions=True)
        action = "created"
    results["report_roles"].append({"parenttype": parenttype, "parent": parent, "role": role, "action": action})


def _ensure_field_property_setter(
    doctype: str,
    fieldname: str,
    property: str,
    property_type: str,
    value,
    results: dict,
) -> None:
    filters = {"doc_type": doctype, "field_name": fieldname, "property": property}
    existing = frappe.db.get_value("Property Setter", filters, "name")
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocField"
    setter.field_name = fieldname
    setter.property = property
    setter.property_type = property_type
    setter.value = str(value)
    if existing:
        setter.save(ignore_permissions=True)
        action = "updated"
    else:
        setter.insert(ignore_permissions=True)
        action = "created"
    results["property_setters"].append(
        {"doctype": doctype, "fieldname": fieldname, "property": property, "action": action}
    )
