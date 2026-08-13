"""
Stock Notifier
--------------
Notifies users with stock-reservation capability when a Sales Order is
submitted, prompting Pick List preparation or direct unreserved delivery.

Called via hooks.py doc_events on Sales Order.
"""

import frappe
from frappe import _

from orderlift.menu_access import user_can_access_company
from orderlift.role_capabilities import CAPABILITY_STOCK_RESERVATION_MANAGEMENT, user_has_capability


def notify_stock_reservation_team(doc, method=None):
    """Notify enabled stock-reservation users who can access this Sales Order company."""
    recipients = get_stock_reservation_recipients(doc.get("company"))
    if not recipients:
        frappe.log_error(
            title="Orderlift stock reservation notification has no recipients",
            message=f"No enabled users with {CAPABILITY_STOCK_RESERVATION_MANAGEMENT} for Sales Order {doc.name} / company {doc.get('company')}",
        )
        return []

    subject = _("Stock Reservation Required: {0}").format(doc.name)
    alert = _(
        "New Sales Order {0}: prepare a Pick List to reserve stock, or deliver directly only from unreserved stock. Review shortages manually."
    ).format(doc.name)
    for user in recipients:
        frappe.publish_realtime(
            "eval_js",
            "frappe.show_alert({message: " + frappe.as_json(alert) + ", indicator: 'orange'})",
            user=user,
        )
        frappe.get_doc(
            {
                "doctype": "Notification Log",
                "subject": subject,
                "for_user": user,
                "type": "Alert",
                "document_type": "Sales Order",
                "document_name": doc.name,
            }
        ).insert(ignore_permissions=True)
    return recipients


def get_stock_reservation_recipients(company: str | None = None) -> list[str]:
    company = (company or "").strip()
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        pluck="name",
        limit_page_length=0,
    )
    recipients = []
    for user in users:
        if user == "Administrator":
            continue
        if not user_has_capability(CAPABILITY_STOCK_RESERVATION_MANAGEMENT, user=user):
            continue
        if company and not user_can_access_company(company, user=user):
            continue
        recipients.append(user)
    return sorted(dict.fromkeys(recipients))


def notify_stock_manager(doc, method=None):
    """Compatibility wrapper for older hook metadata."""
    return notify_stock_reservation_team(doc, method=method)
