import json
import frappe

def run():
    # Read the HTML content
    html_path = '/home/frappe/frappe-bench/apps/orderlift/orderlift/print_formats/orderlift_quotation.html'
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Base print format dictionary
    pf_data = {
        "align_labels_right": 0,
        "custom_format": 1,
        "disabled": 0,
        "doc_type": "Quotation",
        "docstatus": 0,
        "doctype": "Print Format",
        "font": "Default",
        "idx": 0,
        "line_breaks": 0,
        "module": "Orderlift Sales",
        "name": "Orderlift Quotation",
        "print_format_type": "Jinja",
        "show_section_headings": 0,
        "standard": "No",
        "html": html_content
    }

    # Update DB record
    if frappe.db.exists('Print Format', 'Orderlift Quotation'):
        doc = frappe.get_doc('Print Format', 'Orderlift Quotation')
    else:
        doc = frappe.new_doc('Print Format')
        doc.name = 'Orderlift Quotation'

    for k, v in pf_data.items():
        if k not in ['doctype', 'name']:
            doc.set(k, v)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("SUCCESSFULLY UPDATED Orderlift Quotation in DB")
