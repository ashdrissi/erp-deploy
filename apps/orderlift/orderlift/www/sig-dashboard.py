from __future__ import annotations

import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/sig-dashboard"
        )
        raise frappe.Redirect

    context.no_cache = 1
    context.show_sidebar = False
    context.layout = "full-width"
    context.title = "Orderlift — SIG Dashboard"
    return context
