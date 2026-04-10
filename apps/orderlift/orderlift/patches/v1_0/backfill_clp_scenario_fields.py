"""
Backfill Container Load Plan scenario fields
---------------------------------------------
Sets legacy CLPs to the outbound defaults:
  - flow_scope = Outbound
  - shipping_responsibility = Orderlift
  - source_type = Delivery Note

This ensures existing records remain valid after the new required fields
are added to the Container Load Plan doctype.

Runs once on bench migrate via patches.txt.
"""

import frappe


def execute():
    # Only run if the columns exist (i.e., after the doctype JSON has been synced)
    if not frappe.db.has_column("Container Load Plan", "flow_scope"):
        return

    # Backfill all CLPs that have no flow_scope set yet
    count = frappe.db.sql(
        """
        UPDATE `tabContainer Load Plan`
        SET
            flow_scope = 'Outbound',
            shipping_responsibility = 'Orderlift',
            source_type = 'Delivery Note'
        WHERE
            (flow_scope IS NULL OR flow_scope = '')
        """,
    )

    frappe.db.commit()

    backfilled = frappe.db.count(
        "Container Load Plan",
        filters={"flow_scope": "Outbound"},
    )
    frappe.log_error(
        message=f"Backfilled {backfilled} Container Load Plan(s) to Outbound/Orderlift/Delivery Note defaults.",
        title="CLP Scenario Backfill Complete",
    )
