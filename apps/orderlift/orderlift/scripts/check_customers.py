import frappe

# Check if test customer exists
exists = frappe.db.exists("Customer", {"customer_name": "Test Customer Lyon ABC"})
print(f"Test Customer exists: {exists}")

# Check Scenario customers
for name in ["Scenario 3 - Customer Paris", "Scenario 4 - Customer Lyon"]:
    exists = frappe.db.exists("Customer", {"customer_name": name})
    print(f"{name}: {exists}")
