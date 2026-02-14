"""
Cost History
------------
Archives the previous cost price into Item Cost History child table
whenever the cost price changes on an Item record.

Called via hooks.py doc_events on Item (before_save).
"""

import frappe


def archive_cost_price(doc, method=None):
    """Append a cost history row when the current cost price changes."""
    if doc.is_new():
        return

    if not frappe.db.has_column("Item", "custom_current_cost_price"):
        return

    previous_cost = frappe.db.get_value(
        "Item", doc.name, "custom_current_cost_price"
    )

    if previous_cost and previous_cost != doc.custom_current_cost_price:
        doc.append(
            "custom_cost_history",
            {
                "date": frappe.utils.today(),
                "cost_price": previous_cost,
                "updated_by": frappe.session.user,
                "notes": "Auto-archived on cost price update",
            },
        )
