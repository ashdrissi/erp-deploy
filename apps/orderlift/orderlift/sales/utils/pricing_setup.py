import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_material",
                    "label": "Material",
                    "fieldtype": "Select",
                    "options": "STEEL\nGALVA\nINOX\nCOPPER\nOTHER",
                    "insert_after": "item_group",
                    "in_list_view": 0,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_weight_kg",
                    "label": "Weight (kg)",
                    "fieldtype": "Float",
                    "insert_after": "custom_material",
                    "default": "0",
                    "non_negative": 1,
                },
            ],
            "Quotation": [
                {
                    "fieldname": "source_pricing_sheet",
                    "label": "Source Pricing Sheet",
                    "fieldtype": "Link",
                    "options": "Pricing Sheet",
                    "insert_after": "order_type",
                    "read_only": 1,
                    "in_standard_filter": 1,
                }
            ],
        },
        update=True,
    )

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Quotation")
