"""
Main Home Dashboard — server-side data provider.
Aggregates cross-module KPIs from the entire Orderlift ERP.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_days, get_first_day, get_last_day, formatdate


# ── Custom DocType names used across the app ──────────────────────────────────
PRICING_SHEET   = "Pricing Sheet"
BENCHMARK_POL   = "Pricing Benchmark Policy"
CUSTOMS_POL     = "Pricing Customs Policy"
SCENARIO        = "Pricing Scenario"


@frappe.whitelist()
def get_dashboard_data():
    return {
        "user": _get_user_info(),
        "kpis": _get_global_kpis(),
        "recent_activity": _get_recent_activity(),
        "pricing_summary": _get_pricing_summary(),
        "stock_summary": _get_stock_summary(),
        "sales_summary": _get_sales_summary(),
        "alerts": _get_global_alerts(),
        "pending_actions": _get_pending_actions(),
    }


# ── User greeting ─────────────────────────────────────────────────────────────

def _get_user_info():
    user = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_type"], as_dict=True) or {}
    return {
        "full_name": user_doc.get("full_name") or user,
        "today": formatdate(nowdate(), "EEEE, MMMM d, yyyy"),
    }


# ── Global KPIs ───────────────────────────────────────────────────────────────

def _get_global_kpis():
    first_day = get_first_day(nowdate())
    last_day = get_last_day(nowdate())

    # Sales this month
    sales_month = frappe.db.sql(
        """
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE docstatus = 1
          AND transaction_date BETWEEN %s AND %s
        """,
        (first_day, last_day), as_list=True,
    )[0][0]

    # Open quotations
    open_quotes = frappe.db.count("Quotation", {"docstatus": 1, "status": ["not in", ["Ordered", "Cancelled", "Lost"]]})

    # Total stock units
    total_stock = frappe.db.sql(
        "SELECT COALESCE(SUM(actual_qty), 0) FROM `tabBin` WHERE actual_qty > 0",
        as_list=True,
    )[0][0]

    # Stockout alert count
    stockouts = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= 0
        """,
        as_list=True,
    )[0][0]

    # Pending transfers
    pending_transfers = frappe.db.count(
        "Stock Entry",
        {"stock_entry_type": "Material Transfer", "docstatus": 0},
    )

    # Pricing sheets this month
    pricing_sheets = 0
    if frappe.db.table_exists(f"tab{PRICING_SHEET}"):
        pricing_sheets = frappe.db.sql(
            f"""
            SELECT COUNT(*) FROM `tab{PRICING_SHEET}`
            WHERE creation >= %s AND creation <= %s
            """,
            (first_day, last_day), as_list=True,
        )[0][0]

    # Open SAV tickets
    open_tickets = frappe.db.count("Issue", {"status": ["not in", ["Closed", "Resolved"]]})

    return {
        "sales_month": float(flt(sales_month)),
        "open_quotes": int(open_quotes or 0),
        "total_stock": int(flt(total_stock)),
        "stockouts": int(stockouts or 0),
        "pending_transfers": int(pending_transfers or 0),
        "pricing_sheets_month": int(pricing_sheets),
        "open_tickets": int(open_tickets or 0),
    }


# ── Pricing summary ────────────────────────────────────────────────────────────

def _get_pricing_summary():
    result = {
        "total_sheets": 0,
        "benchmark_policies": 0,
        "customs_policies": 0,
        "scenarios": 0,
    }

    for key, doctype in [
        ("total_sheets",       PRICING_SHEET),
        ("benchmark_policies", BENCHMARK_POL),
        ("customs_policies",   CUSTOMS_POL),
        ("scenarios",          SCENARIO),
    ]:
        if frappe.db.table_exists(f"tab{doctype}"):
            result[key] = frappe.db.count(doctype)

    return result


# ── Stock summary ─────────────────────────────────────────────────────────────

def _get_stock_summary():
    warehouses = frappe.db.count("Warehouse", {"disabled": 0, "is_group": 0})

    low_stock = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty > 0 AND b.actual_qty <= ir.warehouse_reorder_level
        """,
        as_list=True,
    )[0][0]

    total_items = frappe.db.count("Item", {"disabled": 0})

    return {
        "warehouses": int(warehouses or 0),
        "low_stock_items": int(low_stock or 0),
        "total_items": int(total_items or 0),
    }


# ── Sales summary ─────────────────────────────────────────────────────────────

def _get_sales_summary():
    first_day = get_first_day(nowdate())
    last_day = get_last_day(nowdate())

    orders_month = frappe.db.count(
        "Sales Order",
        {"docstatus": 1, "transaction_date": ["between", [first_day, last_day]]},
    )

    invoices_overdue = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < %s
        """,
        nowdate(), as_list=True,
    )[0][0]

    deliveries_pending = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabDelivery Note`
        WHERE docstatus = 0
        """,
        as_list=True,
    )[0][0]

    return {
        "orders_month": int(orders_month or 0),
        "invoices_overdue": int(invoices_overdue or 0),
        "deliveries_pending": int(deliveries_pending or 0),
    }


# ── Global alerts ──────────────────────────────────────────────────────────────

def _get_global_alerts():
    alerts = []

    # Stockouts
    stockout_count = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= 0
        """,
        as_list=True,
    )[0][0]
    if stockout_count:
        alerts.append({
            "level": "error",
            "icon": "alert",
            "title": _(f"{int(stockout_count)} Item Stockout(s)"),
            "sub": _("Immediate reorder required"),
            "link": "stock-dashboard",
        })

    # Overdue invoices
    overdue = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSales Invoice` WHERE docstatus=1 AND outstanding_amount > 0 AND due_date < %s",
        nowdate(), as_list=True,
    )[0][0]
    if overdue:
        alerts.append({
            "level": "warn",
            "icon": "invoice",
            "title": _(f"{int(overdue)} Overdue Invoice(s)"),
            "sub": _("Follow up with customers"),
            "link": "accounts/sales-invoice?status=Overdue",
        })

    # Pending transfers
    pending_tr = frappe.db.count("Stock Entry", {"stock_entry_type": "Material Transfer", "docstatus": 0})
    if pending_tr:
        alerts.append({
            "level": "info",
            "icon": "transfer",
            "title": _(f"{int(pending_tr)} Transfer(s) Pending Validation"),
            "sub": _("Awaiting approval"),
            "link": "stock-dashboard",
        })

    # Open SAV tickets
    tickets = frappe.db.count("Issue", {"status": ["not in", ["Closed", "Resolved"]]})
    if tickets:
        alerts.append({
            "level": "info",
            "icon": "ticket",
            "title": _(f"{int(tickets)} Open SAV Ticket(s)"),
            "sub": _("Check field service queue"),
            "link": "support/issue",
        })

    return alerts[:6]


# ── Pending actions for the logged-in user ────────────────────────────────────

def _get_pending_actions():
    actions = []
    user = frappe.session.user

    # Purchase orders to receive
    po_to_receive = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabPurchase Order`
        WHERE docstatus = 1 AND status IN ('To Receive and Bill', 'To Receive')
        """,
        as_list=True,
    )[0][0]
    if po_to_receive:
        actions.append({
            "title": _("Purchase Receipts Pending"),
            "value": int(po_to_receive),
            "link": "buying/purchase-order?status=To Receive and Bill",
        })

    # Quotations expiring in 3 days
    expire_soon = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabQuotation`
        WHERE docstatus = 1
          AND status NOT IN ('Ordered','Cancelled','Lost')
          AND valid_till BETWEEN %s AND %s
        """,
        (nowdate(), add_days(nowdate(), 3)), as_list=True,
    )[0][0]
    if expire_soon:
        actions.append({
            "title": _("Quotes Expiring Soon"),
            "value": int(expire_soon),
            "link": "selling/quotation",
        })

    # Draft stock entries
    draft_se = frappe.db.count("Stock Entry", {"docstatus": 0})
    if draft_se:
        actions.append({
            "title": _("Draft Stock Entries"),
            "value": int(draft_se),
            "link": "stock/stock-entry?docstatus=0",
        })

    return actions


# ── Recent activity ─────────────────────────────────────────────────────────────

def _get_recent_activity():
    activity = []

    # Recent Sales Orders
    recent_orders = frappe.get_all(
        "Sales Order",
        filters={"docstatus": 1},
        fields=["name", "customer", "grand_total", "currency", "transaction_date"],
        order_by="creation desc",
        limit=5,
    )
    for r in recent_orders:
        activity.append({
            "type": "order",
            "icon": "order",
            "title": r.name,
            "sub": r.customer,
            "value": f"{r.currency} {flt(r.grand_total):,.0f}",
            "date": r.transaction_date,
            "link": f"/app/sales-order/{r.name}",
        })

    # Recent Stock Entries
    recent_entries = frappe.get_all(
        "Stock Entry",
        filters={"docstatus": 1},
        fields=["name", "stock_entry_type", "posting_date"],
        order_by="creation desc",
        limit=3,
    )
    for r in recent_entries:
        activity.append({
            "type": "stock",
            "icon": "transfer",
            "title": r.name,
            "sub": r.stock_entry_type,
            "value": "",
            "date": r.posting_date,
            "link": f"/app/stock-entry/{r.name}",
        })

    # Sort by date descending, limit 8
    activity.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    return activity[:8]
