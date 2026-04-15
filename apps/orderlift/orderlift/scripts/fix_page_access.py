"""Grant Orderlift Admin read access to the Page doctype so desk pages render."""
import frappe


def run():
    role = "Orderlift Admin"
    doctype = "Page"

    existing = frappe.db.exists("Custom DocPerm", {
        "parent": doctype,
        "role": role,
        "permlevel": 0,
    })

    if existing:
        print(f"Custom DocPerm already exists for {role} on {doctype}")
        return

    perm = frappe.get_doc({
        "doctype": "Custom DocPerm",
        "parent": doctype,
        "parenttype": "DocType",
        "parentfield": "permissions",
        "role": role,
        "permlevel": 0,
        "read": 1,
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
    })
    perm.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    print(f"Granted read on {doctype} to {role}")
