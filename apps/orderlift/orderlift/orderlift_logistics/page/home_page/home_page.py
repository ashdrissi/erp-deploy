"""
Home Page — cross-module Control Tower backend.
Same pattern as stock_dashboard.py and pricing_dashboard.py.
"""
import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_days, get_first_day, get_last_day, formatdate


@frappe.whitelist()
def get_dashboard_data():
    return {
        "user":             _get_user_info(),
        "kpis":             _get_global_kpis(),
        "pricing_summary":  _get_pricing_summary(),
        "pricing_recent":   _get_recent_pricing_items(),
        "stock_summary":    _get_stock_summary(),
        "sales_summary":    _get_sales_summary(),
        "alerts":           _get_global_alerts(),
        "pending_actions":  _get_pending_actions(),
        "recent_activity":  _get_recent_activity(),
    }


def _get_user_info():
    user = frappe.session.user
    full_name = frappe.db.get_value("User", user, "full_name") or user
    return {
        "full_name": full_name,
        "today": formatdate(nowdate(), "EEEE, MMMM d, yyyy"),
    }


def _get_global_kpis():
    first_day = get_first_day(nowdate())
    last_day  = get_last_day(nowdate())

    sales_month = frappe.db.sql(
        "SELECT COALESCE(SUM(grand_total),0) FROM `tabSales Order` WHERE docstatus=1 AND transaction_date BETWEEN %s AND %s",
        (first_day, last_day), as_list=True,
    )[0][0]

    open_quotes = frappe.db.count("Quotation", {"docstatus": 1, "status": ["not in", ["Ordered", "Cancelled", "Lost"]]})

    total_stock = frappe.db.sql(
        "SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin` WHERE actual_qty > 0", as_list=True,
    )[0][0]

    stockouts = frappe.db.sql(
        "SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b JOIN `tabItem Reorder` ir ON ir.parent=b.item_code AND ir.warehouse=b.warehouse WHERE b.actual_qty <= 0",
        as_list=True,
    )[0][0]

    pending_transfers = frappe.db.count("Stock Entry", {"stock_entry_type": "Material Transfer", "docstatus": 0})
    open_tickets      = frappe.db.count("Issue", {"status": ["not in", ["Closed", "Resolved"]]})

    return {
        "sales_month":       float(flt(sales_month)),
        "open_quotes":       int(open_quotes or 0),
        "total_stock":       int(flt(total_stock)),
        "stockouts":         int(stockouts or 0),
        "pending_transfers": int(pending_transfers or 0),
        "open_tickets":      int(open_tickets or 0),
    }


def _get_pricing_summary():
    result = {}
    for key, dt in [
        ("total_sheets",       "Pricing Sheet"),
        ("builders",           "Pricing Builder"),
        ("benchmark_policies", "Pricing Benchmark Policy"),
        ("customs_policies",   "Pricing Customs Policy"),
        ("scenarios",          "Pricing Scenario"),
    ]:
        result[key] = _safe_count(dt)
    return result


def _get_recent_pricing_items():
    items = []

    if _doctype_exists("Pricing Sheet"):
        for row in frappe.get_all(
            "Pricing Sheet",
            fields=["name", "sheet_name", "modified"],
            order_by="modified desc",
            limit_page_length=3,
        ):
            items.append(
                {
                    "label": row.get("sheet_name") or row.name,
                    "meta": _("Pricing Sheet"),
                    "link": f"/app/pricing-sheet/{row.name}",
                    "modified": row.get("modified"),
                }
            )

    if _doctype_exists("Pricing Scenario"):
        for row in frappe.get_all(
            "Pricing Scenario",
            fields=["name", "scenario_name", "modified"],
            order_by="modified desc",
            limit_page_length=3,
        ):
            items.append(
                {
                    "label": row.get("scenario_name") or row.name,
                    "meta": _("Pricing Scenario"),
                    "link": f"/app/pricing-scenario/{row.name}",
                    "modified": row.get("modified"),
                }
            )

    items.sort(key=lambda x: x.get("modified") or "", reverse=True)
    return items[:6]


def _get_stock_summary():
    warehouses = frappe.db.count("Warehouse", {"disabled": 0, "is_group": 0})
    low_stock  = frappe.db.sql(
        "SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b JOIN `tabItem Reorder` ir ON ir.parent=b.item_code AND ir.warehouse=b.warehouse WHERE b.actual_qty > 0 AND b.actual_qty <= ir.warehouse_reorder_level",
        as_list=True,
    )[0][0]
    total_items = frappe.db.count("Item", {"disabled": 0})
    return {
        "warehouses":      int(warehouses or 0),
        "low_stock_items": int(low_stock or 0),
        "total_items":     int(total_items or 0),
    }


def _get_sales_summary():
    first_day = get_first_day(nowdate())
    last_day  = get_last_day(nowdate())
    orders_month      = frappe.db.count("Sales Order", {"docstatus": 1, "transaction_date": ["between", [first_day, last_day]]})
    invoices_overdue  = frappe.db.sql("SELECT COUNT(*) FROM `tabSales Invoice` WHERE docstatus=1 AND outstanding_amount>0 AND due_date<%s", nowdate(), as_list=True)[0][0]
    deliveries_pending = frappe.db.sql("SELECT COUNT(*) FROM `tabDelivery Note` WHERE docstatus=0", as_list=True)[0][0]
    return {
        "orders_month":       int(orders_month or 0),
        "invoices_overdue":   int(invoices_overdue or 0),
        "deliveries_pending": int(deliveries_pending or 0),
    }


def _get_global_alerts():
    alerts = []
    stockouts = frappe.db.sql(
        "SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b JOIN `tabItem Reorder` ir ON ir.parent=b.item_code AND ir.warehouse=b.warehouse WHERE b.actual_qty<=0",
        as_list=True,
    )[0][0]
    if stockouts:
        alerts.append({"level": "error", "icon": "alert", "title": f"{int(stockouts)} item stockout(s)", "sub": "Immediate reorder required", "link": "stock-dashboard"})

    overdue = frappe.db.sql("SELECT COUNT(*) FROM `tabSales Invoice` WHERE docstatus=1 AND outstanding_amount>0 AND due_date<%s", nowdate(), as_list=True)[0][0]
    if overdue:
        alerts.append({"level": "warn", "icon": "invoice", "title": f"{int(overdue)} overdue invoice(s)", "sub": "Follow up with customers", "link": "accounts/sales-invoice?status=Overdue"})

    pending_tr = frappe.db.count("Stock Entry", {"stock_entry_type": "Material Transfer", "docstatus": 0})
    if pending_tr:
        alerts.append({"level": "info", "icon": "transfer", "title": f"{int(pending_tr)} transfer(s) pending validation", "sub": "Awaiting approval", "link": "stock-dashboard"})

    tickets = frappe.db.count("Issue", {"status": ["not in", ["Closed", "Resolved"]]})
    if tickets:
        alerts.append({"level": "info", "icon": "ticket", "title": f"{int(tickets)} open SAV ticket(s)", "sub": "Check field service queue", "link": "support/issue"})

    return alerts[:6]


def _get_pending_actions():
    actions = []
    po = frappe.db.sql("SELECT COUNT(*) FROM `tabPurchase Order` WHERE docstatus=1 AND status IN ('To Receive and Bill','To Receive')", as_list=True)[0][0]
    if po:
        actions.append({"title": "Purchase Receipts Pending", "value": int(po), "link": "buying/purchase-order?status=To Receive and Bill"})
    expire = frappe.db.sql("SELECT COUNT(*) FROM `tabQuotation` WHERE docstatus=1 AND status NOT IN ('Ordered','Cancelled','Lost') AND valid_till BETWEEN %s AND %s", (nowdate(), add_days(nowdate(), 3)), as_list=True)[0][0]
    if expire:
        actions.append({"title": "Quotes Expiring Soon", "value": int(expire), "link": "selling/quotation"})
    draft_se = frappe.db.count("Stock Entry", {"docstatus": 0})
    if draft_se:
        actions.append({"title": "Draft Stock Entries", "value": int(draft_se), "link": "stock/stock-entry?docstatus=0"})
    return actions


def _get_recent_activity():
    activity = []
    for r in frappe.get_all("Sales Order", filters={"docstatus": 1}, fields=["name", "customer", "grand_total", "currency", "transaction_date"], order_by="creation desc", limit=5):
        activity.append({"icon": "order", "title": r.name, "sub": r.customer, "value": f"{r.currency} {flt(r.grand_total):,.0f}", "date": str(r.transaction_date), "link": f"/app/sales-order/{r.name}"})
    for r in frappe.get_all("Stock Entry", filters={"docstatus": 1}, fields=["name", "stock_entry_type", "posting_date"], order_by="creation desc", limit=3):
        activity.append({"icon": "transfer", "title": r.name, "sub": r.stock_entry_type, "value": "", "date": str(r.posting_date), "link": f"/app/stock-entry/{r.name}"})
    activity.sort(key=lambda x: x.get("date", ""), reverse=True)
    return activity[:8]


def _doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _safe_count(doctype):
    if not _doctype_exists(doctype):
        return 0
    try:
        return int(frappe.db.count(doctype) or 0)
    except Exception:
        return 0
