import frappe


def execute():
    signature_rows = frappe.get_all(
        "Orderlift Document Template Field",
        filters={"fieldtype": "Attach", "field_label": ["like", "Signature%"]},
        pluck="name",
        limit_page_length=0,
    )
    for name in signature_rows:
        frappe.db.set_value(
            "Orderlift Document Template Field",
            name,
            "fieldtype",
            "Signature",
            update_modified=False,
        )

    frappe.db.sql(
        """
        update `tabOrderlift Document Template`
        set show_signature_block = 0
        where ifnull(show_signature_block, 0) != 0
        """
    )
