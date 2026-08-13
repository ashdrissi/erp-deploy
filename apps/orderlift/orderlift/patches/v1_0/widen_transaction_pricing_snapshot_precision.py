import frappe


ITEM_DOCTYPES = ("Quotation Item", "Sales Order Item")
CANONICAL_CURRENCY_FIELDS = (
    "source_price_list_sell_rate",
    "source_discount_amount",
    "source_base_buy_rate",
    "source_landed_cost",
    "source_customs_applied",
    "source_commission_amount",
    "custom_applied_taxes",
    "custom_pu_ttc",
    "custom_pt_ttc",
)


def execute():
    for doctype in ITEM_DOCTYPES:
        fields = [
            fieldname
            for fieldname in CANONICAL_CURRENCY_FIELDS
            if frappe.db.has_column(doctype, fieldname)
        ]
        if not fields:
            continue

        definitions = ", ".join(
            f"MODIFY COLUMN `{fieldname}` DECIMAL(21,9) NOT NULL DEFAULT 0"
            for fieldname in fields
        )
        frappe.db.sql_ddl(f"ALTER TABLE `tab{doctype}` {definitions}")
        frappe.clear_cache(doctype=doctype)
