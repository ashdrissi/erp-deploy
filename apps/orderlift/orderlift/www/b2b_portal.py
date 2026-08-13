from __future__ import annotations

import frappe


def get_context(context):
    if (
        frappe.session.user not in {"Guest", "Administrator"}
        and frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
    ):
        frappe.redirect("/desk/home-page?sidebar=Main+Dashboard")

    context.no_cache = 1
    context.show_sidebar = False
    context.layout = "full-width"
    context.title = "Orderlift B2B Portal"
    context.is_guest = frappe.session.user == "Guest"
    context.login_url = "/login?redirect-to=/b2b-portal"
    return context
