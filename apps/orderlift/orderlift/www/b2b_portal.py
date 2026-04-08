from __future__ import annotations

import frappe


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    context.layout = "full-width"
    context.title = "Orderlift B2B Portal"
    context.is_guest = frappe.session.user == "Guest"
    context.login_url = "/login?redirect-to=/b2b-portal"
    return context
