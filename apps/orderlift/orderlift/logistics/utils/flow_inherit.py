"""
Flow Inherit
-------------
Inherits logistics scenario fields (flow_scope, shipping_responsibility)
from source documents to downstream documents.

Currently supports:
  - Sales Order → Delivery Note (on DN before_save)

Called via hooks.py doc_events on Delivery Note (before_save).
"""

import frappe


def inherit_flow_from_sales_order(doc, method=None):
    """On Delivery Note save, inherit flow_scope and shipping_responsibility
    from the linked Sales Order if the DN fields are still blank.

    Only populates if:
      - DN has no flow_scope set yet
      - DN has at least one item linked to a Sales Order
      - The linked SO has flow_scope set
    """
    if not doc or doc.get("custom_flow_scope"):
        return  # Already set — don't override manual selection

    so_name = _find_linked_sales_order(doc)
    if not so_name:
        return

    so_fields = frappe.db.get_value(
        "Sales Order",
        so_name,
        ["custom_flow_scope", "custom_shipping_responsibility"],
        as_dict=True,
    )
    if not so_fields:
        return

    if so_fields.custom_flow_scope:
        doc.custom_flow_scope = so_fields.custom_flow_scope
    if so_fields.custom_shipping_responsibility:
        doc.custom_shipping_responsibility = so_fields.custom_shipping_responsibility


def _find_linked_sales_order(doc):
    """Find the first Sales Order linked via DN items."""
    for item in doc.items or []:
        if item.against_sales_order:
            return item.against_sales_order
    return None
