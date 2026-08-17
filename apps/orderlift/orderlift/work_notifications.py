from __future__ import annotations

import frappe


@frappe.whitelist()
def get_work_counts() -> dict:
    user = frappe.session.user
    if not user or user == "Guest":
        return {"open_todos": 0, "unread_notifications": 0}

    return {
        "open_todos": frappe.db.count("ToDo", {"status": "Open", "allocated_to": user}),
        "unread_notifications": frappe.db.count("Notification Log", {"read": 0, "for_user": user}),
    }
