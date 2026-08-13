"""
Stock & Warehouses Dashboard — server-side data provider.
Queries ERPNext standard doctypes: Warehouse, Bin, Stock Entry,
Item Reorder, Stock Ledger Entry.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from orderlift.menu_access import resolve_current_company
from orderlift.orderlift_logistics.utils.stock_rate_review import can_manage_stock_rates
from orderlift.warehouse_access import get_allowed_warehouses


STOCK_OVERVIEW_SORTS = {
    "item_code": "item_code",
    "item_name": "item_name",
    "actual_qty": "actual_qty",
    "available_qty": "available_qty",
    "reserved_qty": "sales_order_reserved_qty",
    "physically_reserved_qty": "physically_reserved_qty",
    "ordered_qty": "ordered_qty",
    "warehouse_count": "warehouse_count",
    "stock_value": "stock_value",
}

MOVEMENT_SORTS = {
    "newest": "sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC",
    "oldest": "sle.posting_date ASC, sle.posting_time ASC, sle.creation ASC",
}


@frappe.whitelist()
def get_dashboard_data(filters=None):
    frappe.has_permission("Bin", "read", throw=True)
    filters = _parse_filters(filters)
    context = _get_stock_context(filters.get("company"))
    stock_planning = _get_stock_demand_planning(context)
    return {
        "context": _client_context(context),
        "warehouses": _get_warehouse_cards(context),
        "item_groups": _get_item_groups(context),
        "kpis": _get_kpis(context),
        "stock_overview": _get_stock_overview(context=context, limit=120),
        "critical_stock": _get_critical_stock(context),
        "rotation_by_category": _get_rotation_by_category(context),
        "alerts": _get_live_alerts(context) + stock_planning.get("alerts", []),
        "recent_transfers": _get_recent_transfers(context),
        "reorder_queue": _get_reorder_queue(context),
        "flagged_items": _get_flagged_items(context),
        "qc_routing": _get_qc_routing_receipts(context),
        "stock_planning": stock_planning,
    }


@frappe.whitelist()
def get_stock_overview(
    search=None,
    warehouse=None,
    item_group=None,
    stock_status=None,
    only_in_stock=1,
    sort_by=None,
    sort_dir=None,
    start=0,
    limit=80,
    filters=None,
):
    frappe.has_permission("Bin", "read", throw=True)
    parsed = _parse_filters(filters)
    context = _get_stock_context(parsed.get("company"))
    rows = _get_stock_overview(
        context=context,
        search=search if search is not None else parsed.get("search"),
        warehouse=warehouse if warehouse is not None else parsed.get("warehouse"),
        item_group=item_group if item_group is not None else parsed.get("item_group"),
        stock_status=stock_status if stock_status is not None else parsed.get("stock_status"),
        only_in_stock=only_in_stock if only_in_stock is not None else parsed.get("only_in_stock"),
        sort_by=sort_by if sort_by is not None else parsed.get("sort_by"),
        sort_dir=sort_dir if sort_dir is not None else parsed.get("sort_dir"),
        start=start,
        limit=limit,
    )
    return {"context": _client_context(context), "rows": rows, "start": cint(start or 0), "limit": cint(limit or 80)}


def _parse_filters(filters) -> dict:
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    return filters if isinstance(filters, dict) else {}


def _get_stock_context(requested_company: str | None = None) -> dict:
    user = frappe.session.user
    company = resolve_current_company(user=user)
    requested_company = (requested_company or "").strip()
    if requested_company and requested_company != company:
        frappe.throw(_("The requested company is not your active company."), frappe.PermissionError)
    allowed_warehouses = set(get_allowed_warehouses(user))
    if not company or not allowed_warehouses:
        return {
            "user": user,
            "company": company,
            "warehouses": [],
            "warehouse_rows": [],
            "can_view_valuation": can_manage_stock_rates(user),
            "can_manage_stock_planning": _can_manage_stock_planning(),
        }
    warehouse_filters = {"disabled": 0, "is_group": 0}
    warehouse_filters["company"] = company
    warehouse_filters["name"] = ["in", sorted(allowed_warehouses)]
    warehouses = frappe.get_all(
        "Warehouse",
        filters=warehouse_filters,
        fields=["name", "warehouse_name", "company", "parent_warehouse"],
        order_by="warehouse_name asc, name asc",
        limit_page_length=0,
    )
    warehouse_names = [row.name for row in warehouses if row.name in allowed_warehouses or not allowed_warehouses]
    return {
        "user": user,
        "company": company,
        "warehouses": warehouse_names,
        "warehouse_rows": warehouses,
        "can_view_valuation": can_manage_stock_rates(user),
        "can_manage_stock_planning": _can_manage_stock_planning(),
    }


def _client_context(context: dict) -> dict:
    return {
        "company": context.get("company") or "",
        "warehouses": context.get("warehouses") or [],
        "can_view_valuation": bool(context.get("can_view_valuation")),
        "can_manage_stock_planning": bool(context.get("can_manage_stock_planning")),
    }


def _can_manage_stock_planning() -> bool:
    return bool(
        frappe.db.exists("DocType", "Stock Planning Settings")
        and frappe.has_permission("Stock Planning Settings", "write")
    )


def _stock_warehouse_condition(field_sql: str, params: dict, context: dict, key: str = "allowed_warehouses") -> str:
    warehouses = context.get("warehouses") or []
    if not warehouses:
        return " AND 1 = 0"
    params[key] = tuple(warehouses)
    return f" AND {field_sql} IN %({key})s"


def _clean_requested_warehouse(warehouse: str | None, context: dict) -> str:
    warehouse = (warehouse or "").strip()
    if not warehouse:
        return ""
    if warehouse not in set(context.get("warehouses") or []):
        frappe.throw(_("Warehouse {0} is outside your active stock scope.").format(warehouse), frappe.PermissionError)
    return warehouse


def _clean_limit(value, default=80, maximum=300) -> int:
    return min(max(cint(value or default), 1), maximum)


def _clean_start(value) -> int:
    return max(cint(value or 0), 0)


def _sort_clause(sort_by: str | None, sort_dir: str | None) -> str:
    field = STOCK_OVERVIEW_SORTS.get((sort_by or "").strip()) or STOCK_OVERVIEW_SORTS["actual_qty"]
    direction = "ASC" if (sort_dir or "").lower() == "asc" else "DESC"
    tie_breaker = ", item_code ASC" if field != "item_code" else ""
    return f"{field} {direction}{tie_breaker}"


def _stock_status_having(stock_status: str | None, only_in_stock=1) -> str:
    status = (stock_status or "").strip()
    if status == "out":
        return "WHERE actual_qty <= 0"
    if status == "reserved":
        return "WHERE actual_qty > 0 AND available_qty <= 0"
    if status == "low":
        return "WHERE actual_qty > 0 AND low_stock_count > 0"
    if status == "all":
        return ""
    return "WHERE actual_qty > 0" if cint(only_in_stock) else ""


def _get_stock_overview(
    context,
    search=None,
    warehouse=None,
    item_group=None,
    stock_status=None,
    only_in_stock=1,
    sort_by=None,
    sort_dir=None,
    start=0,
    limit=80,
):
    limit = min(max(cint(limit or 80), 20), 300)
    conditions = ["i.disabled = 0", "i.is_stock_item = 1"]
    params = {}

    search = (search or "").strip()
    if search:
        conditions.append("(i.name LIKE %(search)s OR i.item_name LIKE %(search)s OR i.item_group LIKE %(search)s)")
        params["search"] = f"%{search}%"

    item_group = (item_group or "").strip()
    if item_group:
        conditions.append("i.item_group = %(item_group)s")
        params["item_group"] = item_group

    warehouse_join = ""
    warehouse = _clean_requested_warehouse(warehouse, context)
    if warehouse:
        warehouse_join = "AND b.warehouse = %(warehouse)s"
        params["warehouse"] = warehouse

    start = _clean_start(start)
    having = _stock_status_having(stock_status, only_in_stock=only_in_stock)
    valuation_columns = "SUM(COALESCE(b.actual_qty, 0) * COALESCE(b.valuation_rate, 0)) AS stock_value"
    order_by = _sort_clause(sort_by, sort_dir)
    rows = frappe.db.sql(
        f"""
        SELECT * FROM (
            SELECT
                i.name AS item_code,
                i.item_name,
                i.item_group,
                i.stock_uom,
                SUM(COALESCE(b.actual_qty, 0)) AS actual_qty,
                SUM(COALESCE(b.projected_qty, 0)) AS projected_qty,
                SUM(COALESCE(b.reserved_qty, 0)) AS sales_order_reserved_qty,
                SUM(COALESCE(b.reserved_stock, 0)) AS physically_reserved_qty,
                SUM(COALESCE(b.ordered_qty, 0)) AS ordered_qty,
                SUM(COALESCE(b.actual_qty, 0)) - SUM(COALESCE(b.reserved_qty, 0)) AS available_qty,
                SUM(CASE WHEN COALESCE(b.actual_qty, 0) <= COALESCE(ir.warehouse_reorder_level, -1) THEN 1 ELSE 0 END) AS low_stock_count,
                COUNT(DISTINCT CASE WHEN COALESCE(b.actual_qty, 0) != 0 THEN b.warehouse END) AS warehouse_count,
                {valuation_columns},
                GROUP_CONCAT(
                    CASE
                        WHEN COALESCE(b.actual_qty, 0) != 0
                        THEN CONCAT(b.warehouse, ': ', ROUND(b.actual_qty, 2))
                    END
                    ORDER BY b.actual_qty DESC SEPARATOR ' · '
                ) AS warehouse_summary
            FROM `tabItem` i
            LEFT JOIN `tabBin` b ON b.item_code = i.name {warehouse_join}
            LEFT JOIN `tabItem Reorder` ir ON ir.parent = i.name AND ir.warehouse = b.warehouse
            WHERE {' AND '.join(conditions)}
            {_stock_warehouse_condition("b.warehouse", params, context)}
            GROUP BY i.name, i.item_name, i.item_group, i.stock_uom
        ) item_stock
        {having}
        ORDER BY {order_by}
        LIMIT {limit} OFFSET {start}
        """,
        params,
        as_dict=True,
    )

    result = []
    for row in rows:
        actual_qty = flt(row.actual_qty)
        available_qty = flt(row.available_qty)
        payload = {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "item_group": row.item_group,
            "stock_uom": row.stock_uom,
            "actual_qty": actual_qty,
            "available_qty": available_qty,
            "reserved_qty": flt(row.sales_order_reserved_qty),
            "sales_order_reserved_qty": flt(row.sales_order_reserved_qty),
            "physically_reserved_qty": flt(row.physically_reserved_qty),
            "ordered_qty": flt(row.ordered_qty),
            "projected_qty": flt(row.projected_qty),
            "warehouse_count": cint(row.warehouse_count),
            "warehouse_summary": row.warehouse_summary or "",
            "status": _stock_row_status(actual_qty, available_qty),
        }
        if context.get("can_view_valuation"):
            payload["stock_value"] = flt(row.stock_value)
            payload["avg_valuation_rate"] = flt(row.stock_value) / actual_qty if actual_qty else 0
        result.append(payload)
    return result


def _stock_row_status(actual_qty, available_qty):
    if flt(actual_qty) <= 0:
        return "out"
    if flt(available_qty) <= 0:
        return "reserved"
    return "available"


def _stock_entry_warehouse_condition(
    params: dict,
    context: dict,
    alias: str = "se",
    detail_alias: str = "sed",
    key: str = "entry_warehouses",
) -> str:
    warehouses = context.get("warehouses") or []
    if not warehouses:
        return " AND 1 = 0"
    params[key] = tuple(warehouses)
    return (
        f" AND ({alias}.from_warehouse IN %({key})s "
        f"OR {alias}.to_warehouse IN %({key})s "
        f"OR EXISTS (SELECT 1 FROM `tabStock Entry Detail` {detail_alias} "
        f"WHERE {detail_alias}.parent = {alias}.name "
        f"AND ({detail_alias}.s_warehouse IN %({key})s OR {detail_alias}.t_warehouse IN %({key})s)))"
    )


def _warehouse_filter_or_empty(context: dict, fieldname: str = "warehouse"):
    warehouses = context.get("warehouses") or []
    if not warehouses:
        return {fieldname: "__no_allowed_warehouse__"}
    return {fieldname: ["in", warehouses]}


# ── Warehouse cards ────────────────────────────────────────────────────────────

def _get_warehouse_cards(context):
    if not context.get("warehouses"):
        return []
    warehouses = context.get("warehouse_rows") or []

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


def _get_item_groups(context):
    params = {}
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT i.item_group
        FROM `tabItem` i
        INNER JOIN `tabBin` b ON b.item_code = i.name
        WHERE i.disabled = 0
          AND i.is_stock_item = 1
          AND i.item_group IS NOT NULL
          AND i.item_group != ''
          {_stock_warehouse_condition("b.warehouse", params, context)}
        ORDER BY i.item_group ASC
        """,
        params,
        as_dict=True,
    )
    return [row.item_group for row in rows]


# ── KPIs ───────────────────────────────────────────────────────────────────────

def _get_kpis(context):
    params = {}
    # Total stock units across all warehouses
    total_units_row = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabBin`
        WHERE actual_qty > 0
        {_stock_warehouse_condition("warehouse", params, context)}
        """,
        params,
        as_list=True,
    )
    total_units = int(flt(total_units_row[0][0] if total_units_row else 0))

    # Stockout alerts: items with actual_qty = 0 that have a reorder level
    stockout = frappe.db.sql(
        f"""
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= 0
        {_stock_warehouse_condition("b.warehouse", params, context, key="stockout_warehouses")}
        """,
        params,
        as_list=True,
    )[0][0]

    # Low stock: actual_qty > 0 but <= reorder level
    low_stock = frappe.db.sql(
        f"""
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty > 0 AND b.actual_qty <= ir.warehouse_reorder_level
        {_stock_warehouse_condition("b.warehouse", params, context, key="low_stock_warehouses")}
        """,
        params,
        as_list=True,
    )[0][0]

    # Items in transit
    in_transit_row = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabBin`
        WHERE warehouse LIKE '%%TRANSIT%%'
        {_stock_warehouse_condition("warehouse", params, context, key="transit_warehouses")}
        """,
        params,
        as_list=True,
    )
    in_transit = int(flt(in_transit_row[0][0] if in_transit_row else 0))

    # Avg stock rotation (simplified: total outgoing last 90d / avg stock)
    # Uses Stock Ledger Entry actual_qty changes
    ninety_days_ago = add_days(nowdate(), -90)
    outgoing = frappe.db.sql(
        f"""
        SELECT COALESCE(ABS(SUM(actual_qty)), 0)
        FROM `tabStock Ledger Entry`
        WHERE actual_qty < 0 AND posting_date >= %(posting_date)s AND is_cancelled = 0
        {_stock_warehouse_condition("warehouse", params, context, key="outgoing_warehouses")}
        """,
        {**params, "posting_date": ninety_days_ago}, as_list=True,
    )
    total_outgoing = flt(outgoing[0][0] if outgoing else 0)
    avg_rotation = round(total_outgoing / max(total_units, 1) * (365 / 90), 1) if total_units else 0

    # Pending transfers
    pending_params = {}
    pending_row = frappe.db.sql(
        f"""
        SELECT COUNT(*) AS count
        FROM `tabStock Entry` se
        WHERE se.stock_entry_type = 'Material Transfer'
        AND se.docstatus = 0
        {_stock_entry_warehouse_condition(pending_params, context, key="pending_warehouses")}
        """,
        pending_params,
        as_dict=True,
    )
    pending_transfers = cint(pending_row[0].count if pending_row else 0)

    return {
        "total_units": total_units,
        "stockout_alerts": int(stockout),
        "low_stock_items": int(low_stock),
        "avg_rotation": avg_rotation,
        "in_transit": in_transit,
        "pending_transfers": int(pending_transfers),
    }


# ── Critical stock ─────────────────────────────────────────────────────────────

def _get_critical_stock(context):
    params = {}
    rows = frappe.db.sql(
        f"""
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
        {_stock_warehouse_condition("b.warehouse", params, context)}
        ORDER BY (b.actual_qty / GREATEST(ir.warehouse_reorder_level, 1)) ASC
        LIMIT 8
        """,
        params,
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

def _get_rotation_by_category(context):
    ninety_days_ago = add_days(nowdate(), -90)
    params = {"ninety_days_ago": ninety_days_ago}

    # Two simple queries + Python-side sort to avoid MariaDB aggregate alias errors.
    # Query 1: total outgoing qty per item group in the last 90 days
    outgoing_rows = frappe.db.sql(
        f"""
        SELECT i.item_group, ABS(SUM(sle.actual_qty)) AS total_out
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON i.name = sle.item_code
        WHERE sle.actual_qty < 0
          AND sle.posting_date >= %(ninety_days_ago)s
          AND sle.is_cancelled = 0
          {_stock_warehouse_condition("sle.warehouse", params, context)}
        GROUP BY i.item_group
        """,
        params, as_dict=True,
    )

    if not outgoing_rows:
        return []

    outgoing_map = {r.item_group: flt(r.total_out) for r in outgoing_rows if flt(r.total_out) > 0}
    if not outgoing_map:
        return []

    groups = list(outgoing_map.keys())
    placeholders = ", ".join(["%s"] * len(groups))

    # Query 2: average actual stock per item group from Bin
    avg_params = {"groups": tuple(groups)}
    avg_rows = frappe.db.sql(
        f"""
        SELECT i.item_group, AVG(b.actual_qty) AS avg_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.item_group IN %(groups)s
          AND b.actual_qty > 0
          {_stock_warehouse_condition("b.warehouse", avg_params, context)}
        GROUP BY i.item_group
        """,
        avg_params, as_dict=True,
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

def _get_live_alerts(context):
    alerts = []
    params = {}

    # Stockout alerts
    stockouts = frappe.db.sql(
        f"""
        SELECT b.item_code, i.item_name, b.warehouse, b.actual_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty <= 0
        {_stock_warehouse_condition("b.warehouse", params, context)}
        ORDER BY b.item_code
        LIMIT 3
        """,
        params,
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
        f"""
        SELECT b.item_code, i.item_name, b.warehouse, b.actual_qty, ir.warehouse_reorder_level
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE b.actual_qty > 0
          AND b.actual_qty <= (ir.warehouse_reorder_level * 0.3)
          {_stock_warehouse_condition("b.warehouse", params, context, key="critical_warehouses")}
        LIMIT 2
        """,
        params,
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
    pending_params = {}
    pending = frappe.db.sql(
        f"""
        SELECT se.name, se.from_warehouse, se.to_warehouse, se.posting_date
        FROM `tabStock Entry` se
        WHERE se.stock_entry_type = 'Material Transfer'
        AND se.docstatus = 0
        {_stock_entry_warehouse_condition(pending_params, context, key="alert_transfer_warehouses")}
        ORDER BY se.modified DESC
        LIMIT 2
        """,
        pending_params,
        as_dict=True,
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

def _get_recent_transfers(context):
    params = {}
    rows = frappe.db.sql(
        f"""
        SELECT se.name, se.from_warehouse, se.to_warehouse, se.posting_date, se.docstatus, se.total_incoming_value, se.modified
        FROM `tabStock Entry` se
        WHERE se.stock_entry_type = 'Material Transfer'
        {_stock_entry_warehouse_condition(params, context, key="recent_transfer_warehouses")}
        ORDER BY se.posting_date DESC, se.modified DESC
        LIMIT 8
        """,
        params,
        as_dict=True,
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

def _get_reorder_queue(context):
    params = {}
    rows = frappe.db.sql(
        f"""
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
        {_stock_warehouse_condition("b.warehouse", params, context)}
        ORDER BY b.actual_qty ASC
        LIMIT 6
        """,
        params,
        as_dict=True,
    )

    result = []
    for r in rows:
        actual = int(flt(r.actual_qty))
        level = int(flt(r.reorder_level))
        lead_days = int(flt(r.lead_time_days or 0))
        stockout = actual <= 0
        suppliers = frappe.get_all(
            "Item Supplier",
            filters={"parent": r.item_code},
            fields=["supplier"],
            limit_page_length=3,
        )
        supplier = suppliers[0].supplier if suppliers else ""
        existing_po = _find_existing_open_po(r.item_code, supplier)

        result.append({
            "item_code": r.item_code,
            "item_name": r.item_name,
            "warehouse": r.warehouse,
            "actual_qty": actual,
            "reorder_level": level,
            "lead_time_days": lead_days,
            "stockout": stockout,
            "supplier": supplier,
            "existing_po": existing_po,
            "action": "Open Draft PO" if existing_po else ("Missing Supplier" if not supplier else "Create PO"),
        })

    return result


def _find_existing_open_po(item_code, supplier):
    if not supplier:
        return ""

    purchase_orders = frappe.get_list(
        "Purchase Order",
        filters={
            "supplier": supplier,
            "docstatus": ["in", [0, 1]],
            "status": ["!=", "Closed"],
        },
        fields=["name"],
        limit_page_length=50,
    )
    if not purchase_orders:
        return ""

    po_names = [row.name for row in purchase_orders]
    return frappe.db.get_value(
        "Purchase Order Item",
        {"item_code": item_code, "parent": ["in", po_names]},
        "parent",
    ) or ""


def _get_stock_demand_planning(context: dict) -> dict:
    company = context.get("company") or ""
    warehouses = set(context.get("warehouses") or [])
    if not company or not frappe.db.exists("DocType", "Stock Demand Plan"):
        return {"enabled": False, "summary": {}, "rows": [], "alerts": []}

    settings = frappe.db.get_value(
        "Stock Planning Settings",
        {"company": company},
        ["name", "enabled", "reservation_mode", "rely_on_incoming_stock"],
        as_dict=True,
    ) or {}
    rows = frappe.get_list(
        "Stock Demand Plan",
        filters={"company": company, "source_cancelled": 0},
        fields=[
            "name",
            "sales_order",
            "customer",
            "item_code",
            "warehouse",
            "stock_uom",
            "required_qty",
            "delivery_date",
            "stock_protection_date",
            "incoming_date",
            "incoming_backup_check_date",
            "physical_available_qty",
            "incoming_allocated_qty",
            "pick_list_qty",
            "reserved_qty",
            "remaining_qty",
            "shortage_qty",
            "planning_status",
            "next_action_date",
            "risk_message",
            "latest_pick_list",
            "latest_material_request",
        ],
        order_by="next_action_date asc, delivery_date asc, creation asc",
        limit_page_length=200,
    )
    rows = [row for row in rows if not row.warehouse or row.warehouse in warehouses]
    summary = {
        "total": len(rows),
        "due": 0,
        "waiting_incoming": 0,
        "partial": 0,
        "shortage": 0,
        "fully_reserved": 0,
    }
    due_statuses = {"Backup Check Due", "Pick List Due", "Procurement Required", "Procurement Late"}
    incoming_statuses = {"Covered by Incoming", "Waiting Incoming"}
    partial_statuses = {"Partially Picked", "Draft Pick List Created"}
    shortage_statuses = {"Incoming Late", "Procurement Late", "Shortage", "Replan Needed"}
    alerts = []
    payload_rows = []
    for row in rows:
        status = row.planning_status or "Not Due"
        if status in due_statuses:
            summary["due"] += 1
        if status in incoming_statuses:
            summary["waiting_incoming"] += 1
        if status in partial_statuses:
            summary["partial"] += 1
        if status in shortage_statuses or flt(row.shortage_qty) > 0:
            summary["shortage"] += 1
        if status == "Fully Reserved":
            summary["fully_reserved"] += 1
        payload = dict(row)
        payload["tone"] = _planning_status_tone(status)
        payload["sales_order_link"] = f"/app/sales-order/{row.sales_order}"
        payload["plan_link"] = f"/app/stock-demand-plan/{row.name}"
        if row.latest_pick_list:
            payload["pick_list_link"] = f"/app/pick-list/{row.latest_pick_list}"
        payload_rows.append(payload)
        if (status in shortage_statuses or status in due_statuses or flt(row.shortage_qty) > 0) and len(alerts) < 5:
            alerts.append(
                {
                    "level": "error" if payload["tone"] == "error" else "warn",
                    "title": _("{0}: {1}").format(status, row.item_code),
                    "message": row.risk_message or _("Confirmed demand requires stock-planning action."),
                    "sub": _("Sales Order {0} · Delivery {1}").format(
                        row.sales_order,
                        row.delivery_date or "-",
                    ),
                    "link": payload["plan_link"],
                }
            )
    return {
        "enabled": bool(cint(settings.get("enabled"))),
        "settings": {
            "name": settings.get("name") or "",
            "reservation_mode": settings.get("reservation_mode") or "",
            "rely_on_incoming_stock": bool(cint(settings.get("rely_on_incoming_stock"))),
        },
        "summary": summary,
        "rows": payload_rows[:20],
        "alerts": alerts,
    }


def _planning_status_tone(status: str) -> str:
    if status in {"Fully Reserved", "Covered by Physical Stock"}:
        return "success"
    if status in {"Covered by Incoming", "Waiting Incoming"}:
        return "info"
    if status in {"Not Due"}:
        return "neutral"
    if status in {"Incoming Late", "Procurement Late", "Shortage", "Replan Needed"}:
        return "error"
    return "warn"


def _get_flagged_items(context):
    params = {}
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT i.name, i.item_name, i.item_group, i.custom_inventory_flag, i.modified
        FROM `tabItem` i
        INNER JOIN `tabBin` b ON b.item_code = i.name
        WHERE i.custom_inventory_flag IS NOT NULL
          AND i.custom_inventory_flag != ''
          {_stock_warehouse_condition("b.warehouse", params, context)}
        ORDER BY i.modified DESC
        LIMIT 8
        """,
        params,
        as_dict=True,
    )
    return [
        {
            "item_code": row.name,
            "item_name": row.item_name,
            "item_group": row.item_group,
            "flag": row.custom_inventory_flag,
            "modified": row.modified,
        }
        for row in rows
    ]


def _get_qc_routing_receipts(context):
    filters = _warehouse_filter_or_empty(context, "set_warehouse")
    if context.get("company"):
        filters["company"] = context.get("company")
    receipts = frappe.get_list(
        "Purchase Receipt",
        filters=filters,
        fields=["name", "supplier", "posting_date", "custom_qc_routed", "docstatus", "set_warehouse"],
        order_by="posting_date desc, modified desc",
        limit_page_length=8,
    )

    has_source_pr = frappe.db.has_column("Stock Entry", "custom_source_pr")
    result = []
    for row in receipts:
        transfer_count = 0
        if has_source_pr:
            transfer_count = frappe.db.count("Stock Entry", {"custom_source_pr": row.name})

        result.append(
            {
                "name": row.name,
                "supplier": row.supplier,
                "posting_date": row.posting_date,
                "warehouse": row.set_warehouse,
                "qc_routed": bool(row.custom_qc_routed),
                "transfer_count": transfer_count,
                "status": {0: "draft", 1: "submitted", 2: "cancelled"}.get(row.docstatus, "draft"),
            }
        )

    return result


@frappe.whitelist()
def get_item_stock_details(item_code, warehouse=None, from_date=None, to_date=None, limit=30, filters=None):
    frappe.has_permission("Bin", "read", throw=True)
    frappe.has_permission("Stock Ledger Entry", "read", throw=True)
    parsed = _parse_filters(filters)
    context = _get_stock_context(parsed.get("company"))
    item_code = _validate_item(item_code)
    warehouse = _clean_requested_warehouse(warehouse or parsed.get("warehouse"), context)

    breakdown = _get_item_warehouse_breakdown(item_code, context, warehouse=warehouse)
    movements = _get_stock_movements(
        context,
        item_code=item_code,
        warehouse=warehouse,
        from_date=from_date or parsed.get("from_date"),
        to_date=to_date or parsed.get("to_date"),
        limit=limit,
    )
    item = frappe.db.get_value("Item", item_code, ["name", "item_name", "item_group", "stock_uom"], as_dict=True) or {}
    totals = _stock_totals(breakdown, can_view_valuation=context.get("can_view_valuation"))
    return {
        "context": _client_context(context),
        "item": dict(item),
        "summary": totals,
        "warehouses": breakdown,
        "movements": movements,
    }


@frappe.whitelist()
def get_stock_movement_history(filters=None, start=0, limit=80):
    frappe.has_permission("Stock Ledger Entry", "read", throw=True)
    filters = _parse_filters(filters)
    context = _get_stock_context(filters.get("company"))
    rows = _get_stock_movements(
        context,
        item_code=(filters.get("item_code") or "").strip(),
        warehouse=(filters.get("warehouse") or "").strip(),
        voucher_type=(filters.get("voucher_type") or "").strip(),
        direction=(filters.get("direction") or "").strip(),
        search=(filters.get("search") or "").strip(),
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date"),
        sort=(filters.get("sort") or "newest"),
        start=start,
        limit=limit,
    )
    return {"context": _client_context(context), "rows": rows, "start": _clean_start(start), "limit": _clean_limit(limit)}


@frappe.whitelist()
def get_stock_entry_history(filters=None, start=0, limit=50):
    frappe.has_permission("Stock Entry", "read", throw=True)
    filters = _parse_filters(filters)
    context = _get_stock_context(filters.get("company"))
    start = _clean_start(start)
    limit = _clean_limit(limit, default=50, maximum=150)
    params = {}
    conditions = ["1 = 1"]
    if context.get("company"):
        conditions.append("se.company = %(company)s")
        params["company"] = context.get("company")
    if filters.get("stock_entry_type"):
        conditions.append("se.stock_entry_type = %(stock_entry_type)s")
        params["stock_entry_type"] = filters.get("stock_entry_type")
    if filters.get("docstatus") not in (None, ""):
        conditions.append("se.docstatus = %(docstatus)s")
        params["docstatus"] = cint(filters.get("docstatus"))
    if filters.get("from_date"):
        conditions.append("se.posting_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    if filters.get("to_date"):
        conditions.append("se.posting_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    warehouse = _clean_requested_warehouse(filters.get("warehouse"), context)
    if warehouse:
        conditions.append(
            "(se.from_warehouse = %(warehouse)s OR se.to_warehouse = %(warehouse)s "
            "OR EXISTS (SELECT 1 FROM `tabStock Entry Detail` filter_sed WHERE filter_sed.parent = se.name "
            "AND (filter_sed.s_warehouse = %(warehouse)s OR filter_sed.t_warehouse = %(warehouse)s)))"
        )
        params["warehouse"] = warehouse
    search = (filters.get("search") or "").strip()
    if search:
        conditions.append("(se.name LIKE %(search)s OR se.stock_entry_type LIKE %(search)s OR se.purpose LIKE %(search)s)")
        params["search"] = f"%{search}%"

    rows = frappe.db.sql(
        f"""
        SELECT
            se.name,
            se.company,
            se.stock_entry_type,
            se.purpose,
            se.posting_date,
            se.posting_time,
            se.docstatus,
            se.from_warehouse,
            se.to_warehouse,
            COUNT(sed.name) AS item_count,
            SUM(COALESCE(sed.transfer_qty, sed.qty, 0)) AS total_qty,
            SUM(COALESCE(sed.amount, 0)) AS total_value
        FROM `tabStock Entry` se
        LEFT JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE {' AND '.join(conditions)}
        {_stock_entry_warehouse_condition(params, context, detail_alias="sed", key="history_entry_warehouses")}
        GROUP BY se.name, se.company, se.stock_entry_type, se.purpose, se.posting_date, se.posting_time,
                 se.docstatus, se.from_warehouse, se.to_warehouse
        ORDER BY se.posting_date DESC, se.posting_time DESC, se.modified DESC
        LIMIT {limit} OFFSET {start}
        """,
        params,
        as_dict=True,
    )
    return {"context": _client_context(context), "rows": [_stock_entry_row(row, context) for row in rows]}


@frappe.whitelist()
def get_stock_entry_details(stock_entry):
    frappe.has_permission("Stock Entry", "read", throw=True)
    context = _get_stock_context()
    stock_entry = (stock_entry or "").strip()
    if not stock_entry or not frappe.db.exists("Stock Entry", stock_entry):
        frappe.throw(_("Stock Entry {0} was not found.").format(stock_entry or ""))
    header = frappe.db.get_value(
        "Stock Entry",
        stock_entry,
        ["name", "company", "stock_entry_type", "purpose", "posting_date", "posting_time", "docstatus", "from_warehouse", "to_warehouse"],
        as_dict=True,
    )
    if context.get("company") and header.company != context.get("company"):
        frappe.throw(_("Stock Entry {0} is outside your active company.").format(stock_entry), frappe.PermissionError)
    params = {"stock_entry": stock_entry}
    rows = frappe.db.sql(
        f"""
        SELECT item_code, item_name, s_warehouse, t_warehouse, qty, transfer_qty, uom, stock_uom,
               basic_rate, amount, valuation_rate
        FROM `tabStock Entry Detail`
        WHERE parent = %(stock_entry)s
        {_stock_entry_detail_warehouse_condition(params, context)}
        ORDER BY idx ASC
        """,
        params,
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Stock Entry {0} has no rows in your warehouse scope.").format(stock_entry), frappe.PermissionError)
    payload_rows = []
    for row in rows:
        payload = {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "s_warehouse": row.s_warehouse,
            "t_warehouse": row.t_warehouse,
            "qty": flt(row.qty),
            "transfer_qty": flt(row.transfer_qty),
            "uom": row.uom,
            "stock_uom": row.stock_uom,
        }
        if context.get("can_view_valuation"):
            payload.update({"basic_rate": flt(row.basic_rate), "amount": flt(row.amount), "valuation_rate": flt(row.valuation_rate)})
        payload_rows.append(payload)
    header_payload = _stock_entry_row(header, context)
    header_payload["item_count"] = len(payload_rows)
    header_payload["total_qty"] = sum(flt(row.get("transfer_qty") or row.get("qty")) for row in payload_rows)
    if context.get("can_view_valuation"):
        header_payload["total_value"] = sum(flt(row.get("amount")) for row in payload_rows)
    return {"context": _client_context(context), "header": header_payload, "rows": payload_rows}


def _validate_item(item_code: str | None) -> str:
    item_code = (item_code or "").strip()
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("A valid Item is required."))
    return item_code


def _get_item_warehouse_breakdown(item_code: str, context: dict, warehouse: str = "") -> list[dict]:
    params = {"item_code": item_code}
    extra = ""
    if warehouse:
        extra = " AND b.warehouse = %(warehouse)s"
        params["warehouse"] = warehouse
    rows = frappe.db.sql(
        f"""
        SELECT b.warehouse, w.warehouse_name, b.actual_qty, b.projected_qty, b.reserved_qty,
               b.reserved_stock, b.ordered_qty, b.valuation_rate
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code = %(item_code)s
          {extra}
          {_stock_warehouse_condition("b.warehouse", params, context)}
        ORDER BY b.actual_qty DESC, b.warehouse ASC
        """,
        params,
        as_dict=True,
    )
    result = []
    for row in rows:
        actual_qty = flt(row.actual_qty)
        reserved_qty = flt(row.reserved_qty)
        payload = {
            "warehouse": row.warehouse,
            "warehouse_name": row.warehouse_name,
            "actual_qty": actual_qty,
            "available_qty": actual_qty - reserved_qty,
            "sales_order_reserved_qty": reserved_qty,
            "physically_reserved_qty": flt(row.reserved_stock),
            "ordered_qty": flt(row.ordered_qty),
            "projected_qty": flt(row.projected_qty),
        }
        if context.get("can_view_valuation"):
            valuation_rate = flt(row.valuation_rate)
            payload.update({"valuation_rate": valuation_rate, "stock_value": valuation_rate * actual_qty})
        result.append(payload)
    return result


def _stock_totals(rows: list[dict], can_view_valuation=False) -> dict:
    total = {
        "actual_qty": sum(flt(row.get("actual_qty")) for row in rows),
        "available_qty": sum(flt(row.get("available_qty")) for row in rows),
        "sales_order_reserved_qty": sum(flt(row.get("sales_order_reserved_qty")) for row in rows),
        "physically_reserved_qty": sum(flt(row.get("physically_reserved_qty")) for row in rows),
        "ordered_qty": sum(flt(row.get("ordered_qty")) for row in rows),
        "projected_qty": sum(flt(row.get("projected_qty")) for row in rows),
        "warehouse_count": len(rows),
    }
    if can_view_valuation:
        stock_value = sum(flt(row.get("stock_value")) for row in rows)
        total["stock_value"] = stock_value
        total["avg_valuation_rate"] = stock_value / total["actual_qty"] if total["actual_qty"] else 0
    return total


def _get_stock_movements(
    context: dict,
    item_code: str = "",
    warehouse: str = "",
    voucher_type: str = "",
    direction: str = "",
    search: str = "",
    from_date=None,
    to_date=None,
    sort: str = "newest",
    start=0,
    limit=80,
) -> list[dict]:
    params = {}
    conditions = ["sle.is_cancelled = 0"]
    if item_code:
        item_code = _validate_item(item_code)
        conditions.append("sle.item_code = %(item_code)s")
        params["item_code"] = item_code
    warehouse = _clean_requested_warehouse(warehouse, context)
    if warehouse:
        conditions.append("sle.warehouse = %(warehouse)s")
        params["warehouse"] = warehouse
    if voucher_type:
        conditions.append("sle.voucher_type = %(voucher_type)s")
        params["voucher_type"] = voucher_type
    if direction == "in":
        conditions.append("sle.actual_qty > 0")
    elif direction == "out":
        conditions.append("sle.actual_qty < 0")
    if search:
        conditions.append("(sle.item_code LIKE %(search)s OR sle.voucher_no LIKE %(search)s OR sle.warehouse LIKE %(search)s)")
        params["search"] = f"%{search}%"
    if from_date:
        conditions.append("sle.posting_date >= %(from_date)s")
        params["from_date"] = from_date
    if to_date:
        conditions.append("sle.posting_date <= %(to_date)s")
        params["to_date"] = to_date
    rows = frappe.db.sql(
        f"""
        SELECT sle.item_code, i.item_name, sle.warehouse, sle.posting_date, sle.posting_time,
               sle.voucher_type, sle.voucher_no, sle.actual_qty, sle.qty_after_transaction,
               sle.valuation_rate, sle.stock_value_difference, sle.stock_value
        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabItem` i ON i.name = sle.item_code
        WHERE {' AND '.join(conditions)}
          {_stock_warehouse_condition("sle.warehouse", params, context)}
        ORDER BY {MOVEMENT_SORTS.get(sort) or MOVEMENT_SORTS["newest"]}
        LIMIT {_clean_limit(limit, maximum=300)} OFFSET {_clean_start(start)}
        """,
        params,
        as_dict=True,
    )
    return [_stock_movement_row(row, context) for row in rows]


def _stock_movement_row(row, context: dict) -> dict:
    payload = {
        "item_code": row.item_code,
        "item_name": row.item_name,
        "warehouse": row.warehouse,
        "posting_date": row.posting_date,
        "posting_time": row.posting_time,
        "voucher_type": row.voucher_type,
        "voucher_no": row.voucher_no,
        "actual_qty": flt(row.actual_qty),
        "qty_after_transaction": flt(row.qty_after_transaction),
    }
    if context.get("can_view_valuation"):
        payload.update(
            {
                "valuation_rate": flt(row.valuation_rate),
                "stock_value_difference": flt(row.stock_value_difference),
                "stock_value": flt(row.stock_value),
            }
        )
    return payload


def _stock_entry_detail_warehouse_condition(params: dict, context: dict, key: str = "entry_detail_warehouses") -> str:
    warehouses = context.get("warehouses") or []
    if not warehouses:
        return " AND 1 = 0"
    params[key] = tuple(warehouses)
    return f" AND (s_warehouse IN %({key})s OR t_warehouse IN %({key})s)"


def _stock_entry_row(row, context: dict) -> dict:
    payload = {
        "name": row.name,
        "company": row.company,
        "stock_entry_type": row.stock_entry_type,
        "purpose": row.purpose,
        "posting_date": row.posting_date,
        "posting_time": row.posting_time,
        "docstatus": cint(row.docstatus),
        "status": {0: "draft", 1: "submitted", 2: "cancelled"}.get(cint(row.docstatus), "draft"),
        "from_warehouse": row.from_warehouse,
        "to_warehouse": row.to_warehouse,
        "item_count": cint(row.get("item_count") if hasattr(row, "get") else 0),
        "total_qty": flt(row.get("total_qty") if hasattr(row, "get") else 0),
    }
    if context.get("can_view_valuation"):
        payload["total_value"] = flt(row.get("total_value") if hasattr(row, "get") else 0)
    return payload
