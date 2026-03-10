import frappe
from frappe.utils import flt, add_days, getdate, nowdate

@frappe.whitelist()
def get_dashboard_data():
    """Aggregates high-level KPIs from various modules for the Main Control Tower."""
    
    today = nowdate()
    thirty_days_ago = add_days(today, -30)
    
    # --- SALES & PRICING ---
    sales_mtd = frappe.db.sql(
        \"\"\"
        SELECT COALESCE(SUM(base_grand_total), 0)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
        AND posting_date >= %s
        \"\"\",
        (getdate(today).replace(day=1),)
    )[0][0] or 0.0

    quotes_pending = frappe.db.count("Quotation", {"status": "Draft", "docstatus": 0})
    
    # --- STOCK & WAREHOUSES ---
    stock_value = frappe.db.sql(
        \"\"\"
        SELECT COALESCE(SUM(stock_value), 0)
        FROM `tabBin`
        \"\"\"
    )[0][0] or 0.0
    
    stock_alerts = frappe.db.count("Item Reorder", {}) # Simplified for now
    
    # --- LOGISTICS & TRANSFERS ---
    transfers_pending = frappe.db.count("Stock Entry", {"docstatus": 0, "stock_entry_type": "Material Transfer"})
    
    # --- CRM & SAV ---
    open_tickets = frappe.db.count("Issue", {"status": ["in", ["Open", "Replied"]], "docstatus": ["<", 2]})

    return {
        "stats": {
            "sales_mtd": flt(sales_mtd),
            "quotes_pending": quotes_pending,
            "stock_value": flt(stock_value),
            "stock_alerts": stock_alerts,
            "transfers_pending": transfers_pending,
            "open_tickets": open_tickets
        },
        "recent_alerts": _get_recent_alerts(),
        "shortcuts": _get_shortcuts()
    }

def _get_recent_alerts():
    # Fetch recent failed integrations, unassigned critical tickets, or stockouts
    alerts = []
    
    # Fake some for now until real logic exists
    stockouts = frappe.db.sql("SELECT item_code FROM `tabBin` WHERE actual_qty <= 0 LIMIT 2", as_dict=True)
    for s in stockouts:
        alerts.append({"type": "stock", "message": f"Item {s.item_code} is out of stock", "level": "critical"})
        
    return alerts

def _get_shortcuts():
    # Will be rendered dynamically on frontend
    return []
