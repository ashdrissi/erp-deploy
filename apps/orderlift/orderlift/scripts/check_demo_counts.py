import frappe

def check_demo():
    doctypes = ["Lead", "Customer", "Supplier", "Quotation", "Sales Order", 
               "Purchase Order", "Purchase Receipt", "Delivery Note", 
               "Forecast Load Plan", "Project", "Pick List", "Stock Entry",
               "Delivery Trip", "QC Checklist Template"]
    for dt in doctypes:
        count = frappe.db.count(dt, {"name": ["like", "Scenario%"]})
        print(f"{dt}: {count}")
