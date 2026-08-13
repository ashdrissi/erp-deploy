from __future__ import annotations

import frappe


def run() -> dict:
    original_user = frappe.session.user
    protected_field = "Lead-custom_partner_campaign"
    try:
        frappe.set_user("ashdrissi@gmail.com")
        doc = frappe.get_doc("Customize Form")
        doc.doc_type = "Lead"
        doc.fetch_to_customize()
        doc.set("fields", [row for row in doc.fields if row.fieldname != "custom_partner_campaign"])
        for row in doc.fields:
            if row.fieldname == "utm_analytics_section":
                row.hidden = 1
        doc.hide_success = 1
        doc.save_customization()
        result = {
            "class": f"{type(doc).__module__}.{type(doc).__name__}",
            "protected_exists": bool(frappe.db.exists("Custom Field", protected_field)),
            "analytics_hidden": int(
                frappe.get_meta("Lead", cached=False).get_field("utm_analytics_section").hidden or 0
            ),
        }
        assert result["class"] == "orderlift.customize_form_guard.OrderliftCustomizeForm"
        assert result["protected_exists"]
        assert result["analytics_hidden"] == 1
        return result
    finally:
        frappe.db.rollback()
        frappe.set_user(original_user)
