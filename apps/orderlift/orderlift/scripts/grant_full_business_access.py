"""
Grant Orderlift Admin full CRUD on ALL doctypes except system/build ones.
This is the nuclear option — full business access, zero system access.
"""
import frappe

from orderlift.boot import HIDDEN_DOCTYPES


ROLE = "Orderlift Admin"

# Doctypes that must NEVER be accessible to Orderlift Admin.
# Keep Role readable so users can assign existing roles on the User form.
BLOCKED_DOCTYPES = set(HIDDEN_DOCTYPES) - {"Role"}
BLOCKED_DOCTYPES.update({"Print Style", "DocType Action", "DocType Link", "DocType State"})


def run():
    remove_blocked_docperms()

    # Get every DocType that exists
    all_doctypes = frappe.get_all("DocType", fields=["name", "issingle", "istable", "module"],
                                  filters={"istable": 0})  # skip child tables

    granted = 0
    skipped = 0

    for dt_row in all_doctypes:
        dt = dt_row.name

        # Skip blocked system doctypes
        if dt in BLOCKED_DOCTYPES:
            skipped += 1
            continue

        # Skip if Custom DocPerm already exists for this role
        existing = frappe.db.exists("Custom DocPerm", {
            "parent": dt,
            "role": ROLE,
            "permlevel": 0,
        })

        try:
            meta = frappe.get_meta(dt)
        except Exception:
            skipped += 1
            continue

        is_submittable = meta.is_submittable

        values = {
            "read": 1,
            "write": 1,
            "create": 0 if dt_row.issingle else 1,
            "delete": 0 if dt_row.issingle else 1,
            "report": 1,
            "export": 1,
            "import": 1,
            "share": 1,
            "print": 1,
            "email": 1,
            "submit": 1 if is_submittable else 0,
            "cancel": 1 if is_submittable else 0,
            "amend": 1 if is_submittable else 0,
        }

        try:
            if existing:
                doc = frappe.get_doc("Custom DocPerm", existing)
                for k, v in values.items():
                    setattr(doc, k, v)
                doc.save(ignore_permissions=True)
            else:
                doc = frappe.get_doc({
                    "doctype": "Custom DocPerm",
                    "parent": dt,
                    "parenttype": "DocType",
                    "parentfield": "permissions",
                    "role": ROLE,
                    "permlevel": 0,
                    **values,
                })
                doc.insert(ignore_permissions=True)
            granted += 1
        except Exception as e:
            print(f"  Error on {dt}: {e}")
            skipped += 1

    ensure_role_assignment_access()

    frappe.db.commit()
    frappe.clear_cache()
    print(f"Done: {granted} doctypes granted, {skipped} skipped/blocked")


def ensure_role_assignment_access():
    """Allow Orderlift Admin to assign existing roles on User without opening role setup."""
    ensure_custom_docperm(
        "Role",
        0,
        {
            "read": 1,
            "write": 0,
            "create": 0,
            "delete": 0,
            "report": 1,
            "export": 0,
            "import": 0,
            "share": 0,
            "print": 0,
            "email": 0,
            "submit": 0,
            "cancel": 0,
            "amend": 0,
        },
    )
    ensure_custom_docperm(
        "User",
        1,
        {
            "read": 1,
            "write": 1,
            "create": 0,
            "delete": 0,
            "report": 0,
            "export": 0,
            "import": 0,
            "share": 0,
            "print": 0,
            "email": 0,
            "submit": 0,
            "cancel": 0,
            "amend": 0,
        },
    )


def ensure_custom_docperm(doctype, permlevel, values):
    existing = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": doctype,
            "role": ROLE,
            "permlevel": permlevel,
        },
    )

    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
        for key, value in values.items():
            setattr(doc, key, value)
        doc.save(ignore_permissions=True)
        return

    doc = frappe.get_doc(
        {
            "doctype": "Custom DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": ROLE,
            "permlevel": permlevel,
            **values,
        }
    )
    doc.insert(ignore_permissions=True)


def remove_blocked_docperms():
    for doctype in BLOCKED_DOCTYPES:
        names = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": doctype, "role": ROLE},
            pluck="name",
        )
        for name in names:
            frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True)
