"""Remove the old 'Orderlift Client User' role from contact@orderlift.net.
No longer needed — restrictions are now triggered by 'Orderlift Admin' role."""
import frappe


def run():
    user = frappe.get_doc("User", "contact@orderlift.net")
    old_roles = [r for r in user.roles if r.role == "Orderlift Client User"]
    if old_roles:
        for r in old_roles:
            user.roles.remove(r)
        user.save(ignore_permissions=True)
        frappe.db.commit()
        print("Removed 'Orderlift Client User' role")
    else:
        print("Role not present, nothing to remove")
    print(f"Current roles: {[r.role for r in user.roles]}")
