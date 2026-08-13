from __future__ import annotations

import frappe
from frappe.utils import cint


def reserve_submitted_pick_list(doc, method=None) -> None:
    """Automatically reserve picked Sales Order quantities after Pick List submission."""
    if not doc or cint(doc.get("docstatus")) != 1 or doc.get("purpose") != "Delivery":
        return
    if not cint(frappe.db.get_single_value("Stock Settings", "enable_stock_reservation")):
        return
    if doc.has_unreserved_stock():
        doc.create_stock_reservation_entries(notify=False)


def cancel_pick_list_reservations(doc, method=None) -> None:
    """Cancel open reservations before their Pick List is cancelled."""
    if not doc or doc.get("purpose") != "Delivery":
        return
    if frappe.db.exists(
        "Stock Reservation Entry",
        {
            "docstatus": 1,
            "from_voucher_type": "Pick List",
            "from_voucher_no": doc.name,
        },
    ):
        doc.cancel_stock_reservation_entries(notify=False)
