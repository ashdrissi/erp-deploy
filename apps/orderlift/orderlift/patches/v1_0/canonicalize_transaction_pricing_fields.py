import frappe


LEGACY_FIELDS = ("source_gross_sell_rate", "source_discounted_sell_rate")
ITEM_DOCTYPES = ("Quotation Item", "Sales Order Item")


def execute():
    for doctype in ITEM_DOCTYPES:
        _backfill_list_reference(doctype)
        _remove_legacy_metadata(doctype)
        frappe.clear_cache(doctype=doctype)


def _backfill_list_reference(doctype: str) -> None:
    if not frappe.db.has_column(doctype, "source_price_list_sell_rate"):
        return
    legacy_expression = "source_gross_sell_rate" if frappe.db.has_column(
        doctype, "source_gross_sell_rate"
    ) else "0"
    frappe.db.sql(
        f"""
        UPDATE `tab{doctype}`
        SET source_price_list_sell_rate = COALESCE(
            NULLIF({legacy_expression}, 0),
            NULLIF(price_list_rate, 0),
            rate,
            0
        )
        WHERE IFNULL(source_price_list_sell_rate, 0) = 0
        """
    )


def _remove_legacy_metadata(doctype: str) -> None:
    for fieldname in LEGACY_FIELDS:
        for name in frappe.get_all(
            "Property Setter",
            filters={
                "doc_type": doctype,
                "field_name": fieldname,
            },
            pluck="name",
            limit_page_length=0,
        ):
            frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)

        for name in frappe.get_all(
            "Custom Field",
            filters={"dt": doctype, "fieldname": fieldname},
            pluck="name",
            limit_page_length=0,
        ):
            # Deleting Custom Field records lets Frappe own schema cleanup; this
            # patch intentionally does not issue DROP COLUMN statements.
            frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
