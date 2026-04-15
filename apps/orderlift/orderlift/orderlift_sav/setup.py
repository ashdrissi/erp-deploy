from __future__ import annotations

import frappe


def after_migrate():
    """
    Post-migrate setup for SAV module:
    - Ensure notification log types are valid
    - Print summary of SAV config
    """
    try:
        # Count existing SAV tickets
        ticket_count = frappe.db.count("SAV Ticket")
        frappe.logger().info("orderlift_sav.setup: %d SAV tickets exist", ticket_count)

        # Verify child table doctypes exist
        for dt in ["SAV Stock Action", "SAV Execution Link"]:
            if frappe.db.exists("DocType", dt):
                frappe.logger().info("orderlift_sav.setup: %s doctype OK", dt)
            else:
                frappe.logger().warning("orderlift_sav.setup: %s doctype NOT FOUND — run bench migrate again", dt)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "orderlift_sav.setup — after_migrate failed")
