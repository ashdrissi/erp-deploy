"""One-shot script to update the Orderlift Quotation print format from the JSON fixture."""
import json
import frappe

def run():
    with open("/home/frappe/frappe-bench/apps/orderlift/orderlift/print_formats/orderlift_quotation.json") as f:
        data = json.load(f)
    
    name = data["name"]
    if frappe.db.exists("Print Format", name):
        doc = frappe.get_doc("Print Format", name)
        doc.html = data["html"]
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        print(f"SUCCESS: Updated {name} (html length: {len(data['html'])})")
    else:
        print(f"NOT FOUND: {name}")
