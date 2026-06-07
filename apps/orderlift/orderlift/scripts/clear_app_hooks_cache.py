from __future__ import annotations

import frappe


@frappe.whitelist()
def run():
    frappe.client_cache.delete_value("app_hooks")
    frappe.clear_cache()
    return frappe.get_hooks("app_include_js")
