import frappe
from frappe.utils import flt, getdate, nowdate, add_days


@frappe.whitelist()
def get_dashboard_data():
    """Aggregates high-level KPIs from various modules for the Main Control Tower."""

    today = nowdate()
    month_start = getdate(today).replace(day=1)

    # --- SALES MTD ---
    sales_mtd = frappe.db.sql(
        """
        SELECT COALESCE(SUM(base_grand_total), 0)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND posting_date >= %s
        """,
        (month_start,)
    )[0][0] or 0.0

    # Pending quotes (Draft status)
    quotes_pending = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabQuotation` WHERE status = 'Draft'",
    )[0][0] or 0

    # --- STOCK ---
    stock_value = frappe.db.sql(
        "SELECT COALESCE(SUM(stock_value), 0) FROM `tabBin`"
    )[0][0] or 0.0

    # --- LOGISTICS ---
    transfers_pending = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabStock Entry`
        WHERE docstatus = 0 AND stock_entry_type = 'Material Transfer'
        """
    )[0][0] or 0

    # --- SAV ---
    open_tickets = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabIssue`
        WHERE status IN ('Open', 'Replied')
        """
    )[0][0] or 0

    return {
        "stats": {
            "sales_mtd": flt(sales_mtd),
            "quotes_pending": int(quotes_pending),
            "stock_value": flt(stock_value),
            "transfers_pending": int(transfers_pending),
            "open_tickets": int(open_tickets),
        }
    }
