from __future__ import annotations

import frappe

from orderlift.menu_access import LEGACY_PREFERRED_COMPANY_DEFAULT_KEY


def execute():
    frappe.db.delete(
        "DefaultValue",
        {"defkey": LEGACY_PREFERRED_COMPANY_DEFAULT_KEY},
    )
