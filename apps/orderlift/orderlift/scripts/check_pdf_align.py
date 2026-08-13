import frappe, io
from frappe.utils.pdf import get_pdf
from pypdf import PdfReader

def check():
    name = frappe.db.get_value("Quotation", {"docstatus": 1}, "name", order_by="creation desc")
    print("Quotation:", name)
    html = frappe.get_print("Quotation", name, "Orderlift Quotation PU HT - OMD", as_pdf=False)
    pdf_data = get_pdf(html)
    reader = PdfReader(io.BytesIO(pdf_data))
    last_page = reader.pages[-1]

    totals = []
    def visitor(text, cm, tm, font_dict, font_size):
        x = tm[4]
        y = tm[5]
        t = text.strip()
        if t and any(w in t for w in ("Total", "VAT", "MAD", "TTC", "HT")):
            totals.append((x, y, t))

    last_page.extract_text(visitor_text=visitor)

    totals.sort(key=lambda r: (-r[1], r[0]))
    for x, y, t in totals:
        print(f"  x={x:.0f} y={y:.0f} | {t}")
