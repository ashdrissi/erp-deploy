"""
Home Page — cross-module Control Tower backend.
Same pattern as stock_dashboard.py and pricing_dashboard.py.
"""
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_days, get_first_day, get_last_day, formatdate

from orderlift.menu_access import user_can_access_menu_key


@frappe.whitelist()
def get_dashboard_data():
    access = _get_access_context()
    return {
        "user":             _get_user_info(),
        "access":           access,
        "kpis":             _get_global_kpis(access),
        "pricing_summary":  _get_pricing_summary(access),
        "pricing_recent":   _get_recent_pricing_items(access),
        "stock_summary":    _get_stock_summary(access),
        "sales_summary":    _get_sales_summary(access),
        "alerts":           _get_global_alerts(access),
        "pending_actions":  _get_pending_actions(access),
        "recent_activity":  _get_recent_activity(access),
    }


def _get_access_context():
    return {
        "pricing": _can_menu("sales.pricing_sheets") or _can_read("Pricing Sheet"),
        "pricing_admin": _can_menu("sales.pricing_dashboard") or _can_read("Pricing Benchmark Policy"),
        "sales": _can_menu("sales.sales_order") or _can_read("Sales Order") or _can_read("Quotation"),
        "finance": _can_menu("finance.sale_financial_dashboard") or _can_read("Sales Invoice"),
        "stock": _can_menu("stock.dashboard") or _can_read("Stock Entry"),
        "logistics": _can_menu("logistics.pipeline") or _can_menu("logistics.container_planning"),
        "purchasing": _can_menu("purchasing.purchase_order") or _can_read("Purchase Order"),
        "crm": _can_menu("crm.crm_dashboard") or _can_read("Opportunity"),
        "b2b": _can_menu("b2b.dashboard"),
        "sav": _can_menu("sav.dashboard") or _can_read("SAV Ticket") or _can_read("Issue"),
        "hr": _can_menu("hr.dashboard"),
        "sig": _can_menu("sig.dashboard"),
    }


def _can_menu(menu_key):
    try:
        return bool(user_can_access_menu_key(menu_key))
    except Exception:
        return False


def _can_read(doctype):
    try:
        return bool(_doctype_exists(doctype) and frappe.has_permission(doctype, "read"))
    except Exception:
        return False


def _permitted_count(doctype, filters=None):
    if not _can_read(doctype):
        return 0
    try:
        return len(frappe.get_list(doctype, filters=filters or {}, pluck="name", limit_page_length=0))
    except Exception:
        return 0


def _get_user_info():
    user = frappe.session.user
    full_name = frappe.db.get_value("User", user, "full_name") or user
    return {
        "full_name": full_name,
        "today": formatdate(nowdate(), "EEEE, MMMM d, yyyy"),
    }


def _get_global_kpis(access):
    first_day = get_first_day(nowdate())
    last_day  = get_last_day(nowdate())

    sales_month = 0
    if access.get("sales"):
        sales_rows = frappe.get_list(
            "Sales Order",
            filters={"docstatus": 1, "transaction_date": ["between", [first_day, last_day]]},
            fields=["grand_total"],
            limit_page_length=0,
        )
        sales_month = sum(flt(row.get("grand_total")) for row in sales_rows)

    open_quotes = 0
    if access.get("sales"):
        open_quotes = _permitted_count(
            "Quotation",
            {"docstatus": 1, "status": ["not in", ["Ordered", "Cancelled", "Lost"]]},
        )

    total_stock = stockouts = pending_transfers = 0
    if access.get("stock") or access.get("logistics"):
        total_stock = frappe.db.sql(
            "SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin` WHERE actual_qty > 0",
            as_list=True,
        )[0][0]
        stockouts = frappe.db.sql(
            "SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b JOIN `tabItem Reorder` ir ON ir.parent=b.item_code AND ir.warehouse=b.warehouse WHERE b.actual_qty <= 0",
            as_list=True,
        )[0][0]
        pending_transfers = _permitted_count("Stock Entry", {"stock_entry_type": "Material Transfer", "docstatus": 0})

    open_tickets = 0
    if access.get("sav"):
        open_tickets = _permitted_count("Issue", {"status": ["not in", ["Closed", "Resolved"]]})

    return {
        "sales_month":       float(flt(sales_month)),
        "open_quotes":       int(open_quotes or 0),
        "total_stock":       int(flt(total_stock)),
        "stockouts":         int(stockouts or 0),
        "pending_transfers": int(pending_transfers or 0),
        "pricing_sheets_month": _permitted_count(
            "Pricing Sheet", {"creation": ["between", [first_day, last_day]]}
        ) if access.get("pricing") else 0,
        "open_tickets":      int(open_tickets or 0),
    }


def _get_pricing_summary(access):
    if not access.get("pricing"):
        return {}
    result = {}
    for key, dt in [
        ("total_sheets",       "Pricing Sheet"),
        ("benchmark_policies", "Pricing Benchmark Policy"),
        ("customs_policies",   "Pricing Customs Policy"),
        ("scenarios",          "Pricing Scenario"),
    ]:
        if key != "total_sheets" and not access.get("pricing_admin"):
            continue
        result[key] = _permitted_count(dt)
    return result


def _get_recent_pricing_items(access):
    if not access.get("pricing"):
        return []
    items = []

    if _can_read("Pricing Sheet"):
        for row in frappe.get_list(
            "Pricing Sheet",
            fields=["name", "sheet_name", "modified"],
            order_by="modified desc",
            limit_page_length=3,
        ):
            items.append(
                {
                    "label": row.get("sheet_name") or row.name,
                    "meta": _("Pricing Sheet"),
                    "link": f"/app/pricing-sheet-builder?pricing_sheet={quote(row.name, safe='')}",
                    "modified": row.get("modified"),
                }
            )

    if access.get("pricing_admin") and _can_read("Pricing Scenario"):
        for row in frappe.get_list(
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


def _get_stock_summary(access):
    if not (access.get("stock") or access.get("logistics")):
        return {}
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


def _get_sales_summary(access):
    if not access.get("sales"):
        return {}
    first_day = get_first_day(nowdate())
    last_day  = get_last_day(nowdate())
    orders_month = _permitted_count(
        "Sales Order", {"docstatus": 1, "transaction_date": ["between", [first_day, last_day]]}
    )
    invoices_overdue = 0
    if access.get("finance"):
        invoices_overdue = _permitted_count(
            "Sales Invoice",
            {"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", nowdate()]},
        )
    deliveries_pending = _permitted_count("Delivery Note", {"docstatus": 0}) if access.get("logistics") else 0
    return {
        "orders_month":       int(orders_month or 0),
        "invoices_overdue":   int(invoices_overdue or 0),
        "deliveries_pending": int(deliveries_pending or 0),
    }


def _get_global_alerts(access):
    alerts = []
    stockouts = 0
    if access.get("stock") or access.get("logistics"):
        stockouts = frappe.db.sql(
            "SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b JOIN `tabItem Reorder` ir ON ir.parent=b.item_code AND ir.warehouse=b.warehouse WHERE b.actual_qty<=0",
            as_list=True,
        )[0][0]
    if stockouts:
        alerts.append({
            "level": "error",
            "icon": "alert",
            "title": _("{0} item stockout(s)").format(int(stockouts)),
            "sub": _("Immediate reorder required"),
            "link": "stock-dashboard",
        })

    overdue = 0
    if access.get("finance"):
        overdue = _permitted_count(
            "Sales Invoice",
            {"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", nowdate()]},
        )
    if overdue:
        alerts.append({
            "level": "warn",
            "icon": "invoice",
            "title": _("{0} overdue invoice(s)").format(int(overdue)),
            "sub": _("Follow up with customers"),
            "link": "accounts/sales-invoice?status=Overdue",
        })

    pending_tr = 0
    if access.get("stock"):
        pending_tr = _permitted_count("Stock Entry", {"stock_entry_type": "Material Transfer", "docstatus": 0})
    if pending_tr:
        alerts.append({
            "level": "info",
            "icon": "transfer",
            "title": _("{0} transfer(s) pending validation").format(int(pending_tr)),
            "sub": _("Awaiting approval"),
            "link": "stock-dashboard",
        })

    tickets = _permitted_count("Issue", {"status": ["not in", ["Closed", "Resolved"]]}) if access.get("sav") else 0
    if tickets:
        alerts.append({
            "level": "info",
            "icon": "ticket",
            "title": _("{0} open SAV ticket(s)").format(int(tickets)),
            "sub": _("Check field service queue"),
            "link": "support/issue",
        })

    return alerts[:6]


def _get_pending_actions(access):
    actions = []
    po = 0
    if access.get("purchasing"):
        po = _permitted_count(
            "Purchase Order", {"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]}
        )
    if po:
        actions.append({"title": _("Purchase Receipts Pending"), "value": int(po), "link": "buying/purchase-order?status=To Receive and Bill"})
    expire = 0
    if access.get("sales"):
        expire = _permitted_count(
            "Quotation",
            {
                "docstatus": 1,
                "status": ["not in", ["Ordered", "Cancelled", "Lost"]],
                "valid_till": ["between", [nowdate(), add_days(nowdate(), 3)]],
            },
        )
    if expire:
        actions.append({"title": _("Quotes Expiring Soon"), "value": int(expire), "link": "selling/quotation"})
    draft_se = _permitted_count("Stock Entry", {"docstatus": 0}) if access.get("stock") else 0
    if draft_se:
        actions.append({"title": _("Draft Stock Entries"), "value": int(draft_se), "link": "stock/stock-entry?docstatus=0"})
    return actions


def _get_recent_activity(access):
    activity = []
    if access.get("sales") and _can_read("Sales Order"):
        for r in frappe.get_list(
            "Sales Order",
            filters={"docstatus": 1},
            fields=["name", "customer", "grand_total", "currency", "transaction_date"],
            order_by="creation desc",
            limit=5,
        ):
            activity.append({
                "icon": "order",
                "title": r.name,
                "sub": r.customer,
                "value": f"{r.currency} {flt(r.grand_total):,.0f}",
                "date": str(r.transaction_date),
                "link": f"/app/sales-order/{r.name}",
            })
    if access.get("stock") and _can_read("Stock Entry"):
        for r in frappe.get_list(
            "Stock Entry",
            filters={"docstatus": 1},
            fields=["name", "stock_entry_type", "posting_date"],
            order_by="creation desc",
            limit=3,
        ):
            activity.append({
                "icon": "transfer",
                "title": r.name,
                "sub": r.stock_entry_type,
                "value": "",
                "date": str(r.posting_date),
                "link": f"/app/stock-entry/{r.name}",
            })
    activity.sort(key=lambda x: x.get("date", ""), reverse=True)
    return activity[:8]


def _doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))

