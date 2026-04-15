"""One-off script to configure contact@orderlift.net with client shell lockdown."""
import frappe


def run():
    user = frappe.get_doc("User", "contact@orderlift.net")

    # Add "Orderlift Client User" role to activate JS lockdown
    has_client_role = any(r.role == "Orderlift Client User" for r in user.roles)
    if not has_client_role:
        user.append("roles", {"role": "Orderlift Client User"})
        print("Added Orderlift Client User role")
    else:
        print("Already has Orderlift Client User role")

    # Set landing page
    user.default_workspace = "Main Dashboard"
    user.redirect_url = "/desk/home-page?sidebar=Main+Dashboard"
    user.save(ignore_permissions=True)
    frappe.db.commit()

    user.reload()
    print(f"User roles: {[r.role for r in user.roles]}")
    print(f"default_workspace: {user.default_workspace}")
    print(f"redirect_url: {user.redirect_url}")
    print("Done!")
