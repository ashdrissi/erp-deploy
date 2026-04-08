from __future__ import annotations

import frappe


def get_context(context):
    # Must be logged in — not for guests
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/project-map"
        )
        raise frappe.Redirect

    context.no_cache = 1
    context.show_sidebar = False
    context.layout = "full-width"
    context.title = "Orderlift — Project Map"
    return context
