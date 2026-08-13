"""
Scope existing suppliers to Orderlift Maroc Distribution
--------------------------------------------------------
Suppliers used to be shared across all companies. With supplier company-scoping
now enabled, every existing supplier is assigned to the "Orderlift Maroc
Distribution" company (product-owner decision), overriding the legacy default
assignment (most were auto-set to the parent "Orderlift" company).

Going forward, new suppliers take their creator's active company via
``orderlift.company_scope.apply_company_scope``. This patch only fixes the
pre-existing rows and is idempotent.

Runs once on bench migrate via patches.txt.
"""

import frappe

TARGET_COMPANY = "Orderlift Maroc Distribution"


def execute():
    # The custom_company column pre-dates scoping (legacy field); guard anyway so a
    # fresh site that has not yet synced the field is skipped (it has no suppliers).
    if not frappe.db.has_column("Supplier", "custom_company"):
        return
    if not frappe.db.exists("Company", TARGET_COMPANY):
        frappe.log_error(
            message=f"Company {TARGET_COMPANY!r} not found; suppliers left unscoped.",
            title="Supplier Scope Backfill Skipped",
        )
        return

    updated = frappe.db.sql(
        """
        UPDATE `tabSupplier`
        SET `custom_company` = %s
        WHERE COALESCE(`custom_company`, '') != %s
        """,
        (TARGET_COMPANY, TARGET_COMPANY),
    )
    frappe.db.commit()

    total = frappe.db.count("Supplier", filters={"custom_company": TARGET_COMPANY})
    frappe.log_error(
        message=f"Assigned all suppliers to {TARGET_COMPANY}; {total} now scoped there.",
        title="Supplier Scope Backfill Complete",
    )
