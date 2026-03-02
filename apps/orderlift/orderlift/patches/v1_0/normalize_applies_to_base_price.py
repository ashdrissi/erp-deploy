import frappe


def execute():
    _update_child_table("Pricing Scenario Expense")
    _update_child_table("Pricing Margin Rule")
    _update_child_table("Pricing Sheet Scenario Override")
    _update_child_table("Pricing Sheet Line Override")


def _update_child_table(doctype):
    if not frappe.db.exists("DocType", doctype):
        return
    if not frappe.db.has_column(doctype, "applies_to"):
        return
    frappe.db.sql(f"UPDATE `tab{doctype}` SET applies_to='Base Price' WHERE IFNULL(applies_to, '') != 'Base Price'")
