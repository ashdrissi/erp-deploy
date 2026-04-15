from __future__ import annotations

import frappe
from frappe.utils.response import send_private_file


LOGO_ENDPOINT_MARKER = "/api/method/orderlift.logo_api.website_app_logo"


@frappe.whitelist(allow_guest=True)
def website_app_logo():
    """Serve Website Settings.app_logo reliably for Desk and login page users."""
    logo_url = resolve_logo_url()
    if not logo_url:
        frappe.throw("App Logo is not configured in Website Settings.")

    if logo_url.startswith("/private/files/"):
        return send_private_file(logo_url.split("/private", 1)[1])

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = logo_url


def resolve_logo_url() -> str:
    for doctype in ("Website Settings", "Navbar Settings"):
        candidate = frappe.db.get_single_value(doctype, "app_logo") or ""
        if candidate and LOGO_ENDPOINT_MARKER not in candidate:
            return candidate

    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": ["in", ["Website Settings", "Navbar Settings"]],
            "file_name": ["like", "logo.%"],
        },
        fields=["file_url"],
        order_by="modified desc",
    )
    return (files[0].file_url if files else "") or ""
