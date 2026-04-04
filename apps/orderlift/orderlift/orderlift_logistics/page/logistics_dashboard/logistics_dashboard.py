"""
Logistics Dashboard — premium landing page for procurement and delivery operations.
Matches the dedicated dashboard pattern used by pricing and stock pages.
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, nowdate


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_docs": _get_recent_docs(),
        "alerts": _get_alerts(),
    }


def _get_kpis():
    first_day = get_first_day(nowdate())

    purchase_orders_to_receive = frappe.db.count(
        "Purchase Order",
        {"docstatus": 1, "status": ["in", ["To Receive", "To Receive and Bill"]]},
    )
    submitted_material_requests = frappe.db.count(
        "Material Request",
        {"docstatus": 1, "status": ["not in", ["Stopped", "Cancelled"]]},
    )
    purchase_receipts_month = frappe.db.count(
        "Purchase Receipt",
        {"docstatus": 1, "posting_date": [">=", first_day]},
    )
    draft_delivery_notes = frappe.db.count("Delivery Note", {"docstatus": 0})
    draft_transfers = frappe.db.count(
        "Stock Entry",
        {"stock_entry_type": "Material Transfer", "docstatus": 0},
    )
    active_suppliers = frappe.db.count("Supplier", {"disabled": 0})

    active_load_plans = 0
    if frappe.db.exists("DocType", "Container Load Plan"):
        active_load_plans = frappe.db.count(
            "Container Load Plan",
            {"status": ["not in", ["Completed", "Cancelled"]]},
        )

    return {
        "purchase_orders_to_receive": int(purchase_orders_to_receive or 0),
        "submitted_material_requests": int(submitted_material_requests or 0),
        "purchase_receipts_month": int(purchase_receipts_month or 0),
        "draft_delivery_notes": int(draft_delivery_notes or 0),
        "draft_transfers": int(draft_transfers or 0),
        "active_suppliers": int(active_suppliers or 0),
        "active_load_plans": int(active_load_plans or 0),
    }


def _get_recent_docs():
    docs = []

    def append_rows(doctype, fields, label_field, meta_label, route, limit=4):
        for row in frappe.get_all(
            doctype,
            fields=["name", *fields, "modified"],
            order_by="modified desc",
            limit_page_length=limit,
        ):
            docs.append(
                {
                    "label": row.get(label_field) or row.name,
                    "meta": _(meta_label),
                    "link": f"/app/{route}/{row.name}",
                    "modified": row.get("modified"),
                }
            )

    append_rows("Purchase Order", ["supplier"], "name", "Purchase Order", "purchase-order")
    append_rows("Material Request", ["material_request_type"], "name", "Material Request", "material-request")
    append_rows("Purchase Receipt", ["supplier"], "name", "Purchase Receipt", "purchase-receipt", limit=3)
    append_rows("Delivery Note", ["customer"], "name", "Delivery Note", "delivery-note", limit=3)

    if frappe.db.exists("DocType", "Container Load Plan"):
        append_rows(
            "Container Load Plan",
            ["container_profile", "status"],
            "name",
            "Container Load Plan",
            "container-load-plan",
            limit=3,
        )

    docs.sort(key=lambda row: row.get("modified") or "", reverse=True)
    return docs[:10]


def _get_alerts():
    alerts = []

    po_to_receive = frappe.db.count(
        "Purchase Order",
        {"docstatus": 1, "status": ["in", ["To Receive", "To Receive and Bill"]]},
    )
    if po_to_receive:
        alerts.append(
            {
                "level": "warn",
                "title": _("{0} purchase order(s) waiting receipt").format(po_to_receive),
                "message": _("Receive supplier deliveries to keep stock and logistics flows current."),
                "link": "/app/purchase-order",
            }
        )

    mr_pending = frappe.db.count(
        "Material Request",
        {"docstatus": 1, "status": ["not in", ["Stopped", "Cancelled"]]},
    )
    if mr_pending:
        alerts.append(
            {
                "level": "info",
                "title": _("{0} submitted material request(s) active").format(mr_pending),
                "message": _("Review sourcing and convert the pending requests into procurement actions."),
                "link": "/app/material-request",
            }
        )

    draft_delivery = frappe.db.count("Delivery Note", {"docstatus": 0})
    if draft_delivery:
        alerts.append(
            {
                "level": "warn",
                "title": _("{0} draft delivery note(s)").format(draft_delivery),
                "message": _("Validate outbound deliveries so shipment operations stay current."),
                "link": "/app/delivery-note",
            }
        )

    draft_transfers = frappe.db.count(
        "Stock Entry",
        {"stock_entry_type": "Material Transfer", "docstatus": 0},
    )
    if draft_transfers:
        alerts.append(
            {
                "level": "info",
                "title": _("{0} transfer(s) pending validation").format(draft_transfers),
                "message": _("Review warehouse moves before they block downstream dispatching."),
                "link": "/app/stock-entry?stock_entry_type=Material+Transfer",
            }
        )

    if frappe.db.exists("DocType", "Container Load Plan"):
        stale_load_plans = frappe.db.count(
            "Container Load Plan",
            {
                "status": ["not in", ["Completed", "Cancelled"]],
                "departure_date": ["<", add_days(nowdate(), -1)],
            },
        )
        if stale_load_plans:
            alerts.append(
                {
                    "level": "warn",
                    "title": _("{0} load plan(s) look stale").format(stale_load_plans),
                    "message": _("Review active containers whose departure date has already passed."),
                    "link": "/app/container-load-plan",
                }
            )

    return alerts[:6]
