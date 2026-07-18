from __future__ import annotations

import frappe


STANDARD_TEMPLATE = "50% à la commande / 50% à la livraison"
STANDARD_ROWS = (
    {
        "payment_term": "À la commande",
        "description": "Acompte exigible à la commande.",
        "invoice_portion": 50,
        "due_date_based_on": "Day(s) after invoice date",
        "credit_days": 0,
        "credit_months": 0,
    },
    {
        "payment_term": "À la livraison",
        "description": "Solde exigible à la livraison.",
        "invoice_portion": 50,
        "due_date_based_on": "Day(s) after invoice date",
        "credit_days": 30,
        "credit_months": 0,
    },
)


def after_migrate() -> dict:
    return ensure_standard_payment_terms()


def ensure_standard_payment_terms() -> dict:
    for row in STANDARD_ROWS:
        _ensure_payment_term(row)

    if frappe.db.exists("Payment Terms Template", STANDARD_TEMPLATE):
        template = frappe.get_doc("Payment Terms Template", STANDARD_TEMPLATE)
        action = "updated"
    else:
        template = frappe.new_doc("Payment Terms Template")
        template.template_name = STANDARD_TEMPLATE
        action = "created"

    template.set("terms", [])
    for row in STANDARD_ROWS:
        template.append("terms", dict(row))

    template.save(ignore_permissions=True)
    frappe.db.commit()
    return {"template": STANDARD_TEMPLATE, "action": action, "rows": len(STANDARD_ROWS)}


def _ensure_payment_term(row: dict) -> None:
    name = row["payment_term"]
    if frappe.db.exists("Payment Term", name):
        doc = frappe.get_doc("Payment Term", name)
    else:
        doc = frappe.new_doc("Payment Term")
        doc.payment_term_name = name

    for fieldname in (
        "invoice_portion",
        "due_date_based_on",
        "credit_days",
        "credit_months",
        "description",
    ):
        doc.set(fieldname, row.get(fieldname))
    doc.save(ignore_permissions=True)
