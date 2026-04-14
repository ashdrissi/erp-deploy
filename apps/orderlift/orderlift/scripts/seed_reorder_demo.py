"""
Seed reorder demo data — creates reorder rules and low stock bins
so the Suggest tab shows meaningful recommendations.

Run: bench --site erp.ecomepivot.com execute scripts.seed_reorder_demo.run
"""
import frappe
from frappe.utils import flt


def run():
    warehouse = "Entrepot Central (Real Stock) - OLM"
    company = "Orderlift Maroc"

    # Get all purchase items
    items = frappe.get_all(
        "Item",
        filters={"disabled": 0, "is_purchase_item": 1},
        fields=["name", "item_name", "stock_uom", "purchase_uom", "min_order_qty"],
        limit_page_length=50,
    )

    if not items:
        print("No purchase items found.")
        return

    # Select up to 15 items
    selected = items[:15]

    # Scenario config: (reorder_level, reorder_qty, actual_stock)
    # Some below reorder level (trigger suggestions), some healthy
    scenarios = [
        # (reorder_level, reorder_qty, actual_qty, label)
        (50, 30, 3, "critically low"),        # trigger! very low
        (40, 25, 8, "low"),                   # trigger! low
        (30, 20, 12, "below reorder"),        # trigger!
        (25, 15, 5, "critical"),              # trigger!
        (20, 10, 2, "very critical"),         # trigger!
        (60, 40, 15, "low stock"),            # trigger!
        (35, 20, 10, "low"),                  # trigger!
        (45, 30, 20, "below level"),          # trigger!
        (100, 50, 25, "very low"),            # trigger!
        (15, 10, 80, "healthy"),              # NOT trigger
        (20, 15, 100, "healthy"),             # NOT trigger
        (30, 20, 50, "adequate"),             # NOT trigger
        (10, 5, 30, "fine"),                  # NOT trigger
        (25, 10, 60, "overstocked"),          # NOT trigger
        (8, 5, 40, "plenty"),                 # NOT trigger
    ]

    for i, item in enumerate(selected):
        scenario = scenarios[i % len(scenarios)]
        reorder_level, reorder_qty, actual_qty, label = scenario

        print(f"  {item.name} ({item.item_name}) — actual={actual_qty}, reorder_level={reorder_level} [{label}]")

        # 1. Add reorder rule to Item
        item_doc = frappe.get_doc("Item", item.name)

        # Check if reorder rule already exists for this warehouse
        existing = False
        for row in (item_doc.reorder_levels or []):
            if row.warehouse == warehouse:
                existing = True
                row.warehouse_reorder_level = reorder_level
                row.warehouse_reorder_qty = reorder_qty
                break

        if not existing:
            item_doc.append("reorder_levels", {
                "warehouse": warehouse,
                "warehouse_reorder_level": reorder_level,
                "warehouse_reorder_qty": reorder_qty,
            })

        item_doc.save(ignore_permissions=True)

        # 2. Create/update Bin with actual_qty
        bin_name = frappe.db.exists("Bin", {"item_code": item.name, "warehouse": warehouse})
        if bin_name:
            bin_doc = frappe.get_doc("Bin", bin_name)
            bin_doc.actual_qty = actual_qty
            bin_doc.stock_value = actual_qty * 10  # dummy value
            bin_doc.save(ignore_permissions=True)
        else:
            bin_doc = frappe.new_doc("Bin")
            bin_doc.item_code = item.name
            bin_doc.warehouse = warehouse
            bin_doc.actual_qty = actual_qty
            bin_doc.stock_value = actual_qty * 10
            bin_doc.insert(ignore_permissions=True)

    frappe.db.commit()

    # Summary
    triggered = sum(1 for s in scenarios[:len(selected)] if s[2] < s[0])
    print(f"\nDone! {triggered} items below reorder level will show in Suggest tab.")
    print(f"  {len(selected) - triggered} items are healthy (won't trigger).")


if __name__ == "__main__":
    run()
