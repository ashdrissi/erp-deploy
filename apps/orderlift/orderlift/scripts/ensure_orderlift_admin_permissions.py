from __future__ import annotations

import frappe

from orderlift.company_access import ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES


ROLE = "Orderlift Admin"
READ_ONLY_DOCTYPE_PERMISSION = {"read": 1, "report": 1, "print": 1, "email": 1}
ADMIN_DOCTYPE_PERMISSIONS = {
    "Company": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 1, "share": 0, "print": 1, "email": 1},
    "Data Import": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 0, "import": 0, "share": 0, "print": 1, "email": 0},
    "User": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 0, "print": 0, "email": 1},
    "Role": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 0, "print": 0, "email": 0},
    "User Permission": {"read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 0, "print": 1, "email": 0},
    "Workflow": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 1, "share": 0, "print": 1, "email": 0},
    "Workflow State": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 1, "share": 0, "print": 1, "email": 0},
    "Assignment Rule": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 1, "share": 0, "print": 1, "email": 0},
    "Orderlift Menu Access Rule": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 0},
    "Item": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Item Price": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Price List": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Pricing Builder": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Pricing Sheet": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Pricing Scenario": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Pricing Customs Policy": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Pricing Benchmark Policy": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "CRM Business Type": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 0},
    "CRM Segment": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 0},
    "Partner Segment": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 0},
    "Installation Stage": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 0},
    "Item Category": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "import": 1, "share": 1, "print": 1, "email": 1},
    "Partner Campaign": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 0, "print": 1, "email": 1},
    "Partner Campaign Target": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 0, "print": 1, "email": 1},
    "Partner Campaign Status": {"read": 1, "select": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 0},
    "Performance Metric": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Performance Metric Snapshot": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Performance Profile": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Training Level": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Training Module": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Training Quiz": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Training Quiz Attempt": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
    "Training Quiz Question": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "import": 0, "share": 1, "print": 1, "email": 1},
}
ADDITIONAL_DOCTYPE_PERMISSIONS = {
    "Sales User": {
        "Appraisal Cycle": READ_ONLY_DOCTYPE_PERMISSION,
    },
}
FIELD_PROPERTY_SETTERS = [
    {
        "doctype": "Appraisal Cycle",
        "fieldname": "company",
        "property": "ignore_user_permissions",
        "property_type": "Check",
        "value": 1,
    },
]
ADMIN_PAGES = ["status-control", "access-command-center", "permission-manager"]


@frappe.whitelist()
def run() -> dict:
    frappe.only_for("System Manager")
    results = {
        "custom_docperms": [],
        "report_roles": [],
        "property_setters": [],
    }
    if not frappe.db.exists("Role", ROLE):
        return {**results, "skipped": f"Role {ROLE} does not exist"}

    if frappe.db.exists("DocType", "Item Reorder"):
        _ensure_custom_docperm(
            "Item Reorder",
            ROLE,
            {
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 0,
                "report": 1,
                "export": 1,
                "import": 0,
                "share": 0,
                "print": 1,
                "email": 0,
                "submit": 0,
                "cancel": 0,
                "amend": 0,
            },
            results,
        )

    for doctype, permissions in ADMIN_DOCTYPE_PERMISSIONS.items():
        if frappe.db.exists("DocType", doctype):
            _ensure_custom_docperm(doctype, ROLE, _permission_flags_for_doctype(doctype, permissions), results)

    for role, doctype_permissions in ADDITIONAL_DOCTYPE_PERMISSIONS.items():
        if not frappe.db.exists("Role", role):
            continue
        for doctype, permissions in doctype_permissions.items():
            if frappe.db.exists("DocType", doctype):
                _ensure_custom_docperm(doctype, role, _permission_flags_for_doctype(doctype, permissions), results)

    for setter in FIELD_PROPERTY_SETTERS:
        if frappe.db.exists("DocType", setter["doctype"]):
            _ensure_field_property_setter(results=results, **setter)

    for page in ADMIN_PAGES:
        if frappe.db.exists("Page", page):
            _ensure_has_role("Page", page, ROLE, results)

    if frappe.db.exists("Report", "Sales Payment Summary"):
        _ensure_has_role("Report", "Sales Payment Summary", ROLE, results)

    frappe.db.commit()
    frappe.clear_cache()
    return results


def _ensure_custom_docperm(doctype: str, role: str, values: dict, results: dict) -> None:
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    existing = frappe.db.exists("Custom DocPerm", filters)
    if existing:
        frappe.db.set_value("Custom DocPerm", existing, values)
        action = "updated"
    else:
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
        action = "created"
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
