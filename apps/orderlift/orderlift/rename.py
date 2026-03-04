import frappe

def execute():
    # Update System Settings App Name
    system_settings = frappe.get_doc("System Settings", "System Settings")
    system_settings.app_name = "Orderlift"
    system_settings.flags.ignore_mandatory = True
    system_settings.save(ignore_permissions=True)
    
    # Update Website Settings Brand (if applicable)
    website_settings = frappe.get_doc("Website Settings", "Website Settings")
    website_settings.app_name = "Orderlift"
    website_settings.brand_html = "Orderlift"
    website_settings.save(ignore_permissions=True)
    
    frappe.db.commit()
