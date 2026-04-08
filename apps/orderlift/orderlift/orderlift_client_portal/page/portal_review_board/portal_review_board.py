from __future__ import annotations

import frappe
from orderlift.client_portal.api import get_review_queue, get_review_request_detail


@frappe.whitelist()
def get_board_data():
    return {
        "queue": get_review_queue(),
    }


@frappe.whitelist()
def get_request(name: str):
    return get_review_request_detail(name)
