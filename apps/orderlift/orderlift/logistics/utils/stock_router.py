"""
Stock Router
------------
After a Purchase Receipt is submitted, routes received items to the
correct warehouse based on quality inspection result:
  - QC passed  → Real Stock warehouse (-REAL)
  - QC failed  → Return warehouse (-RETURN) and notifies supplier

Called via hooks.py doc_events on Purchase Receipt (on_submit).
"""

import frappe


def route_received_stock(doc, method=None):
    """Route received stock to REAL or RETURN warehouse after QC."""
    # Placeholder — full logic implemented in Module 14 (Purchases)
    pass
