from __future__ import annotations

import frappe


TARGET_ROLE = "Orderlift Admin"
BYPASS_ROLES = {"System Manager", "Developer"}


def run():
    updated = []
    skipped = []

    users = frappe.get_all(
        "Has Role",
        filters={"role": TARGET_ROLE, "parenttype": "User"},
        pluck="parent",
        limit_page_length=0,
    )

    for user_name in sorted(set(users)):
        if user_name in {"Administrator", "Guest"}:
            skipped.append(user_name)
            continue

        roles = set(frappe.get_roles(user_name))
        if roles.intersection(BYPASS_ROLES):
            skipped.append(user_name)
            continue

        user = frappe.get_doc("User", user_name)
        user.module_profile = None
        user.set("block_modules", [])
        user.save(ignore_permissions=True)
        frappe.db.sql(
            """
            delete from `tabBlock Module`
            where parent=%s and parenttype='User' and parentfield='block_modules'
            """,
            (user.name,),
        )
        updated.append(user_name)

    frappe.db.commit()
    frappe.clear_cache()
    return {"updated": updated, "skipped": skipped}
