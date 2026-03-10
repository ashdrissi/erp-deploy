"""
Stock & Warehouses Dashboard — server-side data provider.
Queries ERPNext standard doctypes: Warehouse, Bin, Stock Entry,
Item Reorder, Stock Ledger Entry.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_days, get_first_day


@frappe.whitelist()
def get_dashboard_data():
    return {
        "warehouses": _get_warehouse_cards(),
        "kpis": _get_kpis(),
        "critical_stock": _get_critical_stock(),
        "rotation_by_category": _get_rotation_by_category(),
        "alerts": _get_live_alerts(),
        "recent_transfers": _get_recent_transfers(),
        "reorder_queue": _get_reorder_queue(),
    }


# ── Warehouse cards ────────────────────────────────────────────────────────────

def _get_warehouse_cards():
    warehouses = frappe.get_all(
        "Warehouse",
        filters={"disabled": 0, "is_group": 0},
        fields=["name", "warehouse_name", "company", "parent_warehouse"],
        order_by="warehouse_name asc",
        limit=8,
    )

    result = []
    for wh in warehouses:
        # Total stock units in this warehouse
        units_row = frappe.db.sql(
            "SELECT COALESCE(SUM(actual_qty), 0) as qty FROM `tabBin` WHERE warehouse = %s",
            wh.name, as_dict=True,
        )
        total_units = int(flt(units_row[0].qty if units_row else 0))

        # Number of items below reorder level (alerts)
        reorder_alerts = frappe.db.sql(
            """
            SELECT COUNT(*) FROM `tabBin` b
            JOIN `tabItem Reorder` ir ON ir.warehouse = b.warehouse AND ir.parent = b.item_code
            WHERE b.warehouse = %s AND b.actual_qty <= ir.warehouse_reorder_level
            """,
            wh.name, as_list=True,
        )[0][0]

        # In-transit items (bin entries with is_stock_item)
        in_transit = frappe.db.sql(
            """SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin`
               WHERE warehouse LIKE %s AND warehouse LIKE '%%TRANSIT%%'""",
            f"%{wh.company or ''}%", as_list=True,
        )[0][0]

        # Capacity: ratio of items with qty vs total active items
        active_items = frappe.db.count("Bin", {"warehouse": wh.name, "actual_qty": [">", 0]})
        total_items = frappe.db.count("Bin", {"warehouse": wh.name})
        capacity_pct = int((active_items / total_items * 100)) if total_items else 0

        status = "alert" if reorder_alerts >= 5 else "warn" if reorder_alerts > 0 else "ok"

        result.append({
            "name": wh.name,
            "label": wh.warehouse_name,
            "company": wh.company,
            "total_units": total_units,
            "capacity_pct": capacity_pct,
            "alerts": int(reorder_alerts),
            "status": status,
            "in_transit": int(flt(in_transit)),
        })

    return result


# ── KPIs ───────────────────────────────────────────────────────────────────────

def _get_kpis():
    # Total stock units across all warehouses
    total_units_row = frappe.db.sql(
        "SELECT COALESCE(SUM(actual_qty), 0) FROM `tabBin` WHERE actual_qty > 0",
        as_list=True,
    )
    total_units = int(flt(total_units_row[0][0] if total_units_row else 0))

    # Stockout alerts: items with actual_qty = 0 that have a reorder level
    stockout = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= 0
        """,
        as_list=True,
    )[0][0]

    # Low stock: actual_qty > 0 but <= reorder level
    low_stock = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty > 0 AND b.actual_qty <= ir.warehouse_reorder_level
        """,
        as_list=True,
    )[0][0]

    # Items in transit
    in_transit_row = frappe.db.sql(
        "SELECT COALESCE(SUM(actual_qty), 0) FROM `tabBin` WHERE warehouse LIKE '%TRANSIT%'",
        as_list=True,
    )
    in_transit = int(flt(in_transit_row[0][0] if in_transit_row else 0))

    # Avg stock rotation (simplified: total outgoing last 90d / avg stock)
    # Uses Stock Ledger Entry actual_qty changes
    ninety_days_ago = add_days(nowdate(), -90)
    outgoing = frappe.db.sql(
        """
        SELECT COALESCE(ABS(SUM(actual_qty)), 0)
        FROM `tabStock Ledger Entry`
        WHERE actual_qty < 0 AND posting_date >= %s AND is_cancelled = 0
        """,
        ninety_days_ago, as_list=True,
    )
    total_outgoing = flt(outgoing[0][0] if outgoing else 0)
    avg_rotation = round(total_outgoing / max(total_units, 1) * (365 / 90), 1) if total_units else 0

    # Pending transfers
    pending_transfers = frappe.db.count(
        "Stock Entry",
        {"stock_entry_type": "Material Transfer", "docstatus": 0},
    )

    return {
        "total_units": total_units,
        "stockout_alerts": int(stockout),
        "low_stock_items": int(low_stock),
        "avg_rotation": avg_rotation,
        "in_transit": in_transit,
        "pending_transfers": int(pending_transfers),
    }


# ── Critical stock ─────────────────────────────────────────────────────────────

def _get_critical_stock():
    rows = frappe.db.sql(
        """
        SELECT
            b.item_code,
            i.item_name,
            b.warehouse,
            b.actual_qty,
            ir.warehouse_reorder_level as reorder_level,
            ir.warehouse_reorder_qty as reorder_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= ir.warehouse_reorder_level
        ORDER BY (b.actual_qty / GREATEST(ir.warehouse_reorder_level, 1)) ASC
        LIMIT 8
        """,
        as_dict=True,
    )

    result = []
    for r in rows:
        reorder_level = flt(r.reorder_level)
        actual = flt(r.actual_qty)
        pct = int((actual / max(reorder_level, 1)) * 100)
        status = "stockout" if actual <= 0 else "critical" if pct < 30 else "low"
        result.append({
            "item_code": r.item_code,
            "item_name": r.item_name,
            "warehouse": r.warehouse,
            "actual_qty": int(actual),
            "reorder_level": int(reorder_level),
            "pct": min(pct, 100),
            "status": status,
        })

    return result


# ── Rotation by category ───────────────────────────────────────────────────────

def _get_rotation_by_category():
    ninety_days_ago = add_days(nowdate(), -90)

    # Two simple queries + Python-side sort to avoid MariaDB aggregate alias errors.
    # Query 1: total outgoing qty per item group in the last 90 days
    outgoing_rows = frappe.db.sql(
        """
        SELECT i.item_group, ABS(SUM(sle.actual_qty)) AS total_out
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON i.name = sle.item_code
        WHERE sle.actual_qty < 0
          AND sle.posting_date >= %s
          AND sle.is_cancelled = 0
        GROUP BY i.item_group
        """,
        ninety_days_ago, as_dict=True,
    )

    if not outgoing_rows:
        return []

    outgoing_map = {r.item_group: flt(r.total_out) for r in outgoing_rows if flt(r.total_out) > 0}
    if not outgoing_map:
        return []

    groups = list(outgoing_map.keys())
    placeholders = ", ".join(["%s"] * len(groups))

    # Query 2: average actual stock per item group from Bin
    avg_rows = frappe.db.sql(
        f"""
        SELECT i.item_group, AVG(b.actual_qty) AS avg_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.item_group IN ({placeholders})
          AND b.actual_qty > 0
        GROUP BY i.item_group
        """,
        groups, as_dict=True,
    )
    avg_map = {r.item_group: max(flt(r.avg_qty), 1) for r in avg_rows}

    # Compute rotation in Python, sort descending
    result = []
    for group, out in outgoing_map.items():
        avg_stock = avg_map.get(group, 1)
        rotation = round(out / avg_stock * (365 / 90), 1)
        result.append({
            "category": group,
            "rotation": rotation,
            "speed": "fast" if rotation > 6 else "normal" if rotation > 3 else "slow" if rotation > 1 else "dead",
        })

    result.sort(key=lambda x: x["rotation"], reverse=True)
    return result[:7]


# ── Live alerts ────────────────────────────────────────────────────────────────

def _get_live_alerts():
    alerts = []

    # Stockout alerts
    stockouts = frappe.db.sql(
        """
        SELECT b.item_code, i.item_name, b.warehouse, b.actual_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= 0
        ORDER BY b.item_code
        LIMIT 3
        """,
        as_dict=True,
    )
    for s in stockouts:
        alerts.append({
            "level": "error",
            "title": _("STOCKOUT — {0}").format(s.item_name or s.item_code),
            "message": _("{0} · {1} · 0 units remaining").format(s.item_code, s.warehouse),
            "sub": _("Immediate reorder required"),
            "link": f"/app/item/{s.item_code}",
        })

    # Critical stock (below 30% of reorder level)
    critical = frappe.db.sql(
        """
        SELECT b.item_code, i.item_name, b.warehouse, b.actual_qty, ir.warehouse_reorder_level
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty > 0
          AND b.actual_qty <= (ir.warehouse_reorder_level * 0.3)
        LIMIT 2
        """,
        as_dict=True,
    )
    for c in critical:
        alerts.append({
            "level": "warn",
            "title": _("CRITICAL — {0}").format(c.item_name or c.item_code),
            "message": _("{0} · {1} · {2} units (min {3})").format(
                c.item_code, c.warehouse,
                int(flt(c.actual_qty)), int(flt(c.warehouse_reorder_level))
            ),
            "sub": _("Reorder triggered"),
            "link": f"/app/item/{c.item_code}",
        })

    # Pending transfers awaiting validation
    pending = frappe.get_all(
        "Stock Entry",
        filters={"stock_entry_type": "Material Transfer", "docstatus": 0},
        fields=["name", "from_warehouse", "to_warehouse", "posting_date"],
        order_by="modified desc",
        limit=2,
    )
    for p in pending:
        alerts.append({
            "level": "info",
            "title": _("Transfer Pending Validation"),
            "message": _("{0} · {1} → {2}").format(
                p.name,
                p.from_warehouse or "—",
                p.to_warehouse or "—",
            ),
            "sub": _("Awaiting your approval"),
            "link": f"/app/stock-entry/{p.name}",
        })

    return alerts[:8]


# ── Recent transfers ───────────────────────────────────────────────────────────

def _get_recent_transfers():
    rows = frappe.get_all(
        "Stock Entry",
        filters={"stock_entry_type": "Material Transfer"},
        fields=["name", "from_warehouse", "to_warehouse", "posting_date", "docstatus", "total_incoming_value", "modified"],
        order_by="posting_date desc, modified desc",
        limit=8,
    )

    result = []
    for r in rows:
        # Count items
        item_count = frappe.db.count("Stock Entry Detail", {"parent": r.name})
        status = {0: "draft", 1: "submitted", 2: "cancelled"}.get(r.docstatus, "draft")
        result.append({
            "name": r.name,
            "from_warehouse": r.from_warehouse or "—",
            "to_warehouse": r.to_warehouse or "—",
            "item_count": item_count,
            "status": status,
            "date": r.posting_date,
        })

    return result


# ── Reorder queue ──────────────────────────────────────────────────────────────

def _get_reorder_queue():
    rows = frappe.db.sql(
        """
        SELECT
            b.item_code,
            i.item_name,
            b.warehouse,
            b.actual_qty,
            ir.warehouse_reorder_level as reorder_level,
            ir.warehouse_reorder_qty as reorder_qty,
            i.lead_time_days
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= ir.warehouse_reorder_level
        ORDER BY b.actual_qty ASC
        LIMIT 6
        """,
        as_dict=True,
    )

    result = []
    for r in rows:
        actual = int(flt(r.actual_qty))
        level = int(flt(r.reorder_level))
        lead_days = int(flt(r.lead_time_days or 0))
        stockout = actual <= 0
        # Rough days-to-stockout estimation: not possible without consumption rate; placeholder
        result.append({
            "item_code": r.item_code,
            "item_name": r.item_name,
            "warehouse": r.warehouse,
            "actual_qty": actual,
            "reorder_level": level,
            "lead_time_days": lead_days,
            "stockout": stockout,
            "action": "Transfer" if not r.warehouse else "Order",
        })

    return result
