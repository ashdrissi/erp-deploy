import frappe

def create_test_customer():
    cust = frappe.new_doc("Customer")
    cust.customer_name = "Scenario 3 - Customer Paris"
    cust.customer_group = "Commercial"
    cust.territory = "France"
    cust.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"Created: {cust.name}")
    return cust.name
