"""
Stock Analyzer
--------------
Weekly scheduled job that flags slow-moving and overstock items
for visibility in the Analytics dashboards.

Called via hooks.py scheduler_events (weekly).
"""

import frappe
from frappe.utils import add_days, nowdate, flt
from datetime import datetime, timedelta


def flag_slow_moving_items():
    """Identify and tag slow-moving / overstock / dormant items."""

    # Define thresholds
    SLOW_MOVING_DAYS = 90  # No movement in 90+ days
    DORMANT_DAYS = 30  # No movement in 30+ days (zero stock)
    OVERSTOCK_MULTIPLIER = 3  # stock > reorder_qty * 3

    # Get all items with stock
    all_items = frappe.get_all(
        "Item",
        filters={"disabled": 0, "is_stock_item": 1},
        fields=["name", "item_name"],
        limit_page_length=0
    )

    if not all_items:
        return

    flags_to_set = {
        "slow_moving": [],
        "overstock": [],
        "dormant": [],
    }

    for item in all_items:
        item_code = item.name
        flags = _analyze_item(item_code)

        if flags.get("slow_moving"):
            flags_to_set["slow_moving"].append(item_code)
        if flags.get("overstock"):
            flags_to_set["overstock"].append(item_code)
        if flags.get("dormant"):
            flags_to_set["dormant"].append(item_code)

    # Apply flags to items
    _apply_inventory_flags(flags_to_set)

    # Create/update analytics record
    _log_analysis_results(flags_to_set)


def _analyze_item(item_code):
    """Analyze single item for slow-moving, overstock, dormant flags."""

    flags = {
        "slow_moving": False,
        "overstock": False,
        "dormant": False,
    }

    # Get current stock across all warehouses
    total_qty = frappe.db.sql("""
        SELECT COALESCE(SUM(actual_qty), 0) as qty
        FROM `tabBin`
        WHERE item_code = %s
    """, item_code, as_dict=True)[0].qty

    # Check for slow-moving (no movement in 90+ days)
    ninety_days_ago = add_days(nowdate(), -90)
    last_movement = frappe.db.sql("""
        SELECT MAX(posting_date) as last_date
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND is_cancelled = 0
    """, item_code, as_dict=True)[0].last_date

    if last_movement is None or last_movement < ninety_days_ago:
        flags["slow_moving"] = True

    # Check for dormant (zero stock for 30+ days)
    if total_qty <= 0:
        thirty_days_ago = add_days(nowdate(), -30)
        zero_stock_since = frappe.db.sql("""
            SELECT MIN(posting_date) as earliest_zero_date
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s
              AND actual_qty <= 0
              AND is_cancelled = 0
            ORDER BY posting_date DESC
            LIMIT 1
        """, item_code, as_dict=True)

        if zero_stock_since and zero_stock_since[0].earliest_zero_date:
            if zero_stock_since[0].earliest_zero_date < thirty_days_ago:
                flags["dormant"] = True

    # Check for overstock (qty > reorder_qty * 3)
    reorder_qty = frappe.db.sql("""
        SELECT MAX(warehouse_reorder_qty) as max_reorder_qty
        FROM `tabItem Reorder`
        WHERE parent = %s
    """, item_code, as_dict=True)[0].max_reorder_qty

    if reorder_qty and total_qty > (reorder_qty * 3):
        flags["overstock"] = True

    return flags


def _apply_inventory_flags(flags_to_set):
    """Apply custom_inventory_flag to items based on analysis."""

    # First, clear all existing flags
    frappe.db.sql("""
        UPDATE `tabItem`
        SET custom_inventory_flag = NULL
        WHERE custom_inventory_flag IS NOT NULL
    """)

    # Then set new flags (priority: dormant > slow_moving > overstock)
    for item_code in flags_to_set["dormant"]:
        frappe.db.set_value("Item", item_code, "custom_inventory_flag", "Dormant")

    for item_code in flags_to_set["slow_moving"]:
        # Only set if not already dormant
        existing = frappe.db.get_value("Item", item_code, "custom_inventory_flag")
        if not existing:
            frappe.db.set_value("Item", item_code, "custom_inventory_flag", "Slow Moving")

    for item_code in flags_to_set["overstock"]:
        # Only set if not already dormant or slow moving
        existing = frappe.db.get_value("Item", item_code, "custom_inventory_flag")
        if not existing:
            frappe.db.set_value("Item", item_code, "custom_inventory_flag", "Overstock")

    frappe.clear_cache()


def _log_analysis_results(flags_to_set):
    """Create a record of the analysis for historical tracking."""

    # Check if Stock Analysis Log doctype exists, if not create simple log
    analysis_log = {
        "doctype": "Stock Analysis Log" if frappe.db.exists("DocType", "Stock Analysis Log") else "Event Log",
        "event": "Stock Analysis",
        "reference_doctype": "Item",
        "message": f"""
Stock Analysis Report — {nowdate()}

Slow Moving Items: {len(flags_to_set['slow_moving'])}
  {', '.join(flags_to_set['slow_moving'][:10])}

Overstock Items: {len(flags_to_set['overstock'])}
  {', '.join(flags_to_set['overstock'][:10])}

Dormant Items: {len(flags_to_set['dormant'])}
  {', '.join(flags_to_set['dormant'][:10])}
        """.strip()
    }

    try:
        frappe.get_doc(analysis_log).insert(ignore_permissions=True)
    except Exception:
        # If doctype doesn't exist, just skip logging
        frappe.log_error(
            f"Stock Analysis completed: {len(flags_to_set['slow_moving'])} slow-moving, "
            f"{len(flags_to_set['overstock'])} overstock, {len(flags_to_set['dormant'])} dormant",
            "Stock Analyzer"
        )

    # Send email to analytics team
    _send_analysis_report(flags_to_set)


def _send_analysis_report(flags_to_set):
    """Send weekly analysis report to procurement/analytics team."""

    # Get analytics team (Stock Manager role)
    stock_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Stock Manager", "parenttype": "User"},
        fields=["parent"]
    )

    if not stock_managers:
        return

    emails = [user.parent for user in stock_managers]

    # Build email content
    html_content = "<h2>Weekly Stock Analysis Report</h2>"
    html_content += f"<p>Report Date: {nowdate()}</p>"

    # Dormant items
    if flags_to_set["dormant"]:
        html_content += "<h3>🔴 Dormant Items (Zero Stock for 30+ Days)</h3>"
        html_content += "<ul>"
        for item_code in flags_to_set["dormant"][:20]:
            html_content += f"<li><a href='/app/item/{item_code}'>{item_code}</a></li>"
        html_content += "</ul>"
        if len(flags_to_set["dormant"]) > 20:
            html_content += f"<p><em>... and {len(flags_to_set['dormant']) - 20} more</em></p>"

    # Slow-moving items
    if flags_to_set["slow_moving"]:
        html_content += "<h3>🟡 Slow-Moving Items (No Movement for 90+ Days)</h3>"
        html_content += "<ul>"
        for item_code in flags_to_set["slow_moving"][:20]:
            html_content += f"<li><a href='/app/item/{item_code}'>{item_code}</a></li>"
        html_content += "</ul>"
        if len(flags_to_set["slow_moving"]) > 20:
            html_content += f"<p><em>... and {len(flags_to_set['slow_moving']) - 20} more</em></p>"

    # Overstock items
    if flags_to_set["overstock"]:
        html_content += "<h3>🔵 Overstock Items (Qty > Reorder Qty × 3)</h3>"
        html_content += "<ul>"
        for item_code in flags_to_set["overstock"][:20]:
            html_content += f"<li><a href='/app/item/{item_code}'>{item_code}</a></li>"
        html_content += "</ul>"
        if len(flags_to_set["overstock"]) > 20:
            html_content += f"<p><em>... and {len(flags_to_set['overstock']) - 20} more</em></p>"

    # Summary
    html_content += "<hr><h3>Summary</h3>"
    html_content += f"<p>Dormant: {len(flags_to_set['dormant'])} items</p>"
    html_content += f"<p>Slow-Moving: {len(flags_to_set['slow_moving'])} items</p>"
    html_content += f"<p>Overstock: {len(flags_to_set['overstock'])} items</p>"

    frappe.sendmail(
        recipients=emails,
        subject=f"[Weekly Stock Analysis] {len(flags_to_set['dormant'])} dormant, "
                f"{len(flags_to_set['slow_moving'])} slow-moving, "
                f"{len(flags_to_set['overstock'])} overstock — {nowdate()}",
        message=html_content,
    )