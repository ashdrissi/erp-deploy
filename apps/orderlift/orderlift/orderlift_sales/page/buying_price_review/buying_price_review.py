from __future__ import annotations

import frappe

from orderlift.orderlift_sales.utils.purchase_order_pricing import (
    get_purchase_order_price_reviews,
    set_purchase_order_price_review_decisions,
)


@frappe.whitelist()
def get_review_data(status="Pending", supplier="", price_list="", item_code=""):
    return get_purchase_order_price_reviews(status=status, supplier=supplier, price_list=price_list, item_code=item_code)


@frappe.whitelist()
def review_selected(decisions, attestation=0):
    return set_purchase_order_price_review_decisions(decisions=decisions, attestation=attestation)
