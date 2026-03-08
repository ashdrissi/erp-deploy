import frappe


def execute():
    for doctype in [
        "Pricing Scenario Assignment Rule",
        "Pricing Scenario Policy",
        "Market Price Entry",
    ]:
        if not frappe.db.exists("DocType", doctype):
            continue
        try:
            frappe.delete_doc("DocType", doctype, force=1, ignore_missing=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed deleting legacy doctype: {doctype}")
