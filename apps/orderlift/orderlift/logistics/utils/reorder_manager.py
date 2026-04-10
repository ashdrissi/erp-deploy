"""
Reorder Manager
---------------
Daily scheduled job that checks stock levels against Item Reorder
thresholds and drafts Purchase Orders for items below minimum stock.

Called via hooks.py scheduler_events (daily).
"""

import frappe
from frappe.utils import nowdate, flt, get_first_day, add_months
from datetime import datetime


def check_reorder_levels():
    """Check all reorder rules and create draft POs where stock is low."""

    # Get all items with reorder rules where stock is below reorder level
    reorder_items = frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            b.warehouse,
            b.actual_qty,
            ir.warehouse_reorder_level as reorder_level,
            ir.warehouse_reorder_qty as reorder_qty,
            i.lead_time_days,
            i.purchase_uom
        FROM `tabBin` b
        JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.actual_qty <= ir.warehouse_reorder_level
            AND i.is_purchase_item = 1
            AND i.disabled = 0
        ORDER BY b.item_code, b.warehouse
    """, as_dict=True)

    if not reorder_items:
        return

    # Group by item to consolidate multiple warehouse reorders
    reorder_map = {}
    for row in reorder_items:
        key = row.item_code
        if key not in reorder_map:
            reorder_map[key] = []
        reorder_map[key].append(row)

    created_pos = []
    skipped_items = []

    for item_code, warehouse_rows in reorder_map.items():
        item_doc = frappe.get_doc("Item", item_code)
        suppliers = item_doc.supplier or []

        if not suppliers:
            skipped_items.append({
                "item_code": item_code,
                "reason": "No supplier configured"
            })
            continue

        # Get preferred supplier
        primary_supplier = suppliers[0].supplier if suppliers else None
        if not primary_supplier:
            skipped_items.append({
                "item_code": item_code,
                "reason": "No supplier configured"
            })
            continue

        # Check if PO already exists for this item (pending or draft)
        existing_po = frappe.db.get_value(
            "Purchase Order Item",
            {
                "item_code": item_code,
                "parent": ("in", [
                    d.name for d in frappe.get_all(
                        "Purchase Order",
                        filters={
                            "supplier": primary_supplier,
                            "docstatus": ("in", [0, 1]),  # Draft or submitted
                            "status": ("!=", "Closed")
                        },
                        fields=["name"]
                    )
                ])
            },
            "parent"
        )

        if existing_po:
            skipped_items.append({
                "item_code": item_code,
                "reason": f"PO {existing_po} already exists"
            })
            continue

        # Calculate total quantity to reorder (across all warehouses)
        total_deficit = 0
        for wh_row in warehouse_rows:
            deficit = flt(wh_row.reorder_qty)  # Use reorder_qty, not level
            total_deficit += deficit

        if total_deficit <= 0:
            skipped_items.append({
                "item_code": item_code,
                "reason": "Calculated quantity is zero"
            })
            continue

        # Create draft Purchase Order
        try:
            po = frappe.new_doc("Purchase Order")
            po.supplier = primary_supplier
            po.company = frappe.db.get_value("Item", item_code, "company") or frappe.defaults.get_default("company")
            po.transaction_date = nowdate()
            po.schedule_date = nowdate()  # Can be adjusted based on lead time

            po.append("items", {
                "item_code": item_code,
                "qty": total_deficit,
                "uom": item_doc.purchase_uom or item_doc.stock_uom,
                "warehouse": warehouse_rows[0].warehouse if warehouse_rows else None,
            })

            po.insert(ignore_permissions=True)
            created_pos.append({
                "po": po.name,
                "item_code": item_code,
                "qty": total_deficit,
                "supplier": primary_supplier
            })
        except Exception as e:
            frappe.log_error(f"Error creating PO for {item_code}: {str(e)}", "Reorder Manager")
            skipped_items.append({
                "item_code": item_code,
                "reason": f"Error: {str(e)[:50]}"
            })

    # Send email digest to procurement team
    _send_reorder_digest(created_pos, skipped_items)


def _send_reorder_digest(created_pos, skipped_items):
    """Send email summary to procurement team."""

    # Get procurement team (users with Stock Manager role)
    stock_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Stock Manager", "parenttype": "User"},
        fields=["parent"]
    )

    if not stock_managers:
        return

    emails = [user.parent for user in stock_managers]

    # Build email content
    html_content = "<h2>Daily Reorder Report</h2>"
    html_content += f"<p>Report Date: {nowdate()}</p>"

    if created_pos:
        html_content += "<h3>✓ Purchase Orders Created</h3>"
        html_content += "<table border='1' cellpadding='5'>"
        html_content += "<tr><th>PO</th><th>Item</th><th>Qty</th><th>Supplier</th></tr>"
        for po in created_pos:
            html_content += f"""
                <tr>
                    <td><a href='/app/purchase-order/{po['po']}'>{po['po']}</a></td>
                    <td>{po['item_code']}</td>
                    <td>{po['qty']}</td>
                    <td>{po['supplier']}</td>
                </tr>
            """
        html_content += "</table>"
    else:
        html_content += "<p><strong>No POs created today.</strong></p>"

    if skipped_items:
        html_content += "<h3>⊗ Skipped Items</h3>"
        html_content += "<table border='1' cellpadding='5'>"
        html_content += "<tr><th>Item</th><th>Reason</th></tr>"
        for item in skipped_items:
            html_content += f"""
                <tr>
                    <td>{item['item_code']}</td>
                    <td>{item['reason']}</td>
                </tr>
            """
        html_content += "</table>"

    html_content += f"<p><em>Total POs created: {len(created_pos)}</em></p>"
    html_content += f"<p><em>Total skipped: {len(skipped_items)}</em></p>"

    frappe.sendmail(
        recipients=emails,
        subject=f"[Daily Reorder] {len(created_pos)} POs created — {nowdate()}",
        message=html_content,
    )
