import frappe

def fix_contact_user():
    u = frappe.get_doc("User", "contact@orderlift.net")
    # Set default workspace  
    try:
        u.default_workspace = "Main Dashboard"
    except Exception:
        pass
    u.save(ignore_permissions=True)
    frappe.db.commit()
    print("Set default_workspace for contact@orderlift.net")
    
    # Also verify roles
    roles = [r.role for r in u.roles]
    print(f"Roles: {roles}")
