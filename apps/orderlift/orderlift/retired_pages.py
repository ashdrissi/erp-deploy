from __future__ import annotations

import frappe
from frappe import _


RETIRED_PAGE_REDIRECTS = {
    "operations-pipeline": "/desk/logistics-pipeline",
    "finance-dashboard": "/desk/sale-financial-dashboard",
    "orderlift-home": "/desk/home-page",
    "pricing-simulator": "/desk/home-page",
}
RETIRED_PAGE_NAMES = frozenset(RETIRED_PAGE_REDIRECTS)


def deny_retired_page(page_name: str) -> None:
    if page_name in RETIRED_PAGE_NAMES:
        frappe.throw(
            _("The {0} page has been retired. Use the current dashboard instead.").format(page_name),
            frappe.PermissionError,
        )
