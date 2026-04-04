"""Finance Dashboard — receivables, payables, payments, and accounting activity."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, nowdate


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_docs": _get_recent_docs(),
        "alerts": _get_alerts(),
        "due_horizon": _get_due_horizon(),
        "accounting_activity": _get_accounting_activity(),
        "cash_collections": _get_cash_collections(),
    }


def _get_kpis():
    first_day = get_first_day(nowdate())

    sales_invoice_count = frappe.db.count("Sales Invoice") if frappe.db.exists("DocType", "Sales Invoice") else 0
    purchase_invoice_count = frappe.db.count("Purchase Invoice") if frappe.db.exists("DocType", "Purchase Invoice") else 0
    payment_entries_month = frappe.db.count(
        "Payment Entry",
        {"posting_date": [">=", first_day], "docstatus": 1},
    ) if frappe.db.exists("DocType", "Payment Entry") else 0
    journal_entries_month = frappe.db.count(
        "Journal Entry",
        {"posting_date": [">=", first_day], "docstatus": 1},
    ) if frappe.db.exists("DocType", "Journal Entry") else 0
    gl_entries_month = frappe.db.count(
        "GL Entry",
        {"posting_date": [">=", first_day]},
    ) if frappe.db.exists("DocType", "GL Entry") else 0

    overdue_receivables = 0
    overdue_payables = 0
    if frappe.db.exists("DocType", "Sales Invoice"):
        overdue_receivables = flt(
            frappe.db.sql(
                """
                SELECT COALESCE(SUM(outstanding_amount), 0)
                FROM `tabSales Invoice`
                WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < CURDATE()
                """,
                as_list=True,
            )[0][0]
        )
    if frappe.db.exists("DocType", "Purchase Invoice"):
        overdue_payables = flt(
            frappe.db.sql(
                """
                SELECT COALESCE(SUM(outstanding_amount), 0)
                FROM `tabPurchase Invoice`
                WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < CURDATE()
                """,
                as_list=True,
            )[0][0]
        )

    return {
        "sales_invoice_count": int(sales_invoice_count or 0),
        "purchase_invoice_count": int(purchase_invoice_count or 0),
        "payment_entries_month": int(payment_entries_month or 0),
        "journal_entries_month": int(journal_entries_month or 0),
        "gl_entries_month": int(gl_entries_month or 0),
        "overdue_receivables": overdue_receivables,
        "overdue_payables": overdue_payables,
    }


def _get_recent_docs():
    rows = []

    def append_docs(doctype, fields, label_field, meta_label, route, limit=4):
        if not frappe.db.exists("DocType", doctype):
            return
        for row in frappe.get_all(
            doctype,
            fields=["name", *fields, "modified"],
            order_by="modified desc",
            limit_page_length=limit,
        ):
            rows.append(
                {
                    "label": row.get(label_field) or row.name,
                    "meta": _(meta_label),
                    "link": f"/app/{route}/{row.name}",
                    "modified": row.get("modified"),
                }
            )

    append_docs("Sales Invoice", ["customer", "status"], "name", "Sales Invoice", "sales-invoice")
    append_docs("Purchase Invoice", ["supplier", "status"], "name", "Purchase Invoice", "purchase-invoice")
    append_docs("Payment Entry", ["party", "payment_type"], "name", "Payment Entry", "payment-entry")
    append_docs("Journal Entry", ["voucher_type"], "name", "Journal Entry", "journal-entry", limit=3)

    rows.sort(key=lambda row: row.get("modified") or "", reverse=True)
    return rows[:10]


def _get_alerts():
    alerts = []

    overdue_sales_count = 0
    overdue_purchase_count = 0
    if frappe.db.exists("DocType", "Sales Invoice"):
        overdue_sales_count = frappe.db.count(
            "Sales Invoice",
            {"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", nowdate()]},
        )
    if overdue_sales_count:
        alerts.append(
            {
                "level": "warn",
                "title": _("{0} overdue receivable invoice(s)").format(overdue_sales_count),
                "message": _("Review outstanding customer invoices and accelerate collections."),
                "link": "/app/sales-invoice",
            }
        )

    if frappe.db.exists("DocType", "Purchase Invoice"):
        overdue_purchase_count = frappe.db.count(
            "Purchase Invoice",
            {"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", nowdate()]},
        )
    if overdue_purchase_count:
        alerts.append(
            {
                "level": "warn",
                "title": _("{0} overdue payable invoice(s)").format(overdue_purchase_count),
                "message": _("Review supplier liabilities and schedule payments."),
                "link": "/app/purchase-invoice",
            }
        )

    if frappe.db.exists("DocType", "Payment Entry") and frappe.db.count("Payment Entry", {"docstatus": 0}):
        alerts.append(
            {
                "level": "info",
                "title": _("Draft payment entries are waiting validation"),
                "message": _("Validate or discard draft payment entries to keep treasury clean."),
                "link": "/app/payment-entry",
            }
        )

    return alerts[:6]


def _get_due_horizon():
    rows = []

    if frappe.db.exists("DocType", "Sales Invoice"):
        rows.extend(
            {
                "label": row.name,
                "party": row.customer,
                "doctype_label": _("Receivable"),
                "due_date": str(row.due_date or ""),
                "amount": flt(row.outstanding_amount or 0),
                "link": f"/app/sales-invoice/{row.name}",
            }
            for row in frappe.get_all(
                "Sales Invoice",
                filters={"docstatus": 1, "outstanding_amount": [">", 0]},
                fields=["name", "customer", "due_date", "outstanding_amount"],
                order_by="due_date asc",
                limit_page_length=6,
            )
        )

    if frappe.db.exists("DocType", "Purchase Invoice"):
        rows.extend(
            {
                "label": row.name,
                "party": row.supplier,
                "doctype_label": _("Payable"),
                "due_date": str(row.due_date or ""),
                "amount": flt(row.outstanding_amount or 0),
                "link": f"/app/purchase-invoice/{row.name}",
            }
            for row in frappe.get_all(
                "Purchase Invoice",
                filters={"docstatus": 1, "outstanding_amount": [">", 0]},
                fields=["name", "supplier", "due_date", "outstanding_amount"],
                order_by="due_date asc",
                limit_page_length=6,
            )
        )

    rows.sort(key=lambda row: row.get("due_date") or "")
    return rows[:8]


def _get_accounting_activity():
    if not frappe.db.exists("DocType", "GL Entry"):
        return []

    rows = frappe.get_all(
        "GL Entry",
        fields=["voucher_type", "posting_date"],
        order_by="posting_date desc, modified desc",
        limit_page_length=500,
    )
    counts = Counter((row.get("voucher_type") or _("Other")) for row in rows)
    return [{"label": label, "value": value} for label, value in counts.most_common(8)]


def _get_cash_collections():
    if not frappe.db.exists("DocType", "Payment Entry"):
        return []

    rows = frappe.get_all(
        "Payment Entry",
        fields=["name", "party", "payment_type", "paid_amount", "reference_date"],
        filters={"docstatus": 1},
        order_by="reference_date desc, modified desc",
        limit_page_length=6,
    )
    return [
        {
            "name": row.name,
            "party": row.party or "",
            "payment_type": row.payment_type or "",
            "paid_amount": flt(row.paid_amount or 0),
            "reference_date": str(row.reference_date or ""),
            "link": f"/app/payment-entry/{row.name}",
        }
        for row in rows
    ]
