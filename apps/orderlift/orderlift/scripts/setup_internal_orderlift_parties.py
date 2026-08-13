from __future__ import annotations

import frappe

from orderlift.intercompany import ensure_internal_orderlift_parties


@frappe.whitelist()
def run(dry_run: int = 1, companies=None, parent_company: str = "Orderlift") -> dict:
    return ensure_internal_orderlift_parties(
        dry_run=dry_run,
        companies=companies,
        parent_company=parent_company,
    )
