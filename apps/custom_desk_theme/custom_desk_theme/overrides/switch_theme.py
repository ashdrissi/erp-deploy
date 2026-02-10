import frappe


@frappe.whitelist()
def switch_theme(theme):
    # Extend the core allowed themes.
    if theme in ["Dark", "Light", "Automatic", "Custom"]:
        frappe.db.set_value("User", frappe.session.user, "desk_theme", theme)
