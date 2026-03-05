import frappe

def execute():
    # 1. Check if Pricing Margin Policy/Rule are really gone
    if frappe.db.exists("DocType", "Pricing Margin Policy"):
        print("ERROR: Pricing Margin Policy doctype still exists!")
        return
        
    print("SUCCESS: Pricing Margin Policy is removed.")

    # 2. Find a test customer and item
    customer = frappe.get_all("Customer", limit=1, pluck="name")
    if not customer:
        print("No customer found for testing.")
        return
    customer = customer[0]

    item = frappe.get_all("Item", filters={"is_sales_item": 1, "disabled": 0}, limit=1, pluck="name")
    if not item:
        print("No item found for testing.")
        return
    item = item[0]
    scenario = frappe.get_all("Pricing Scenario", limit=1, pluck="name")
    if not scenario:
        print("No scenario found for testing.")
        return
    scenario = scenario[0]

    # 3. Create a Pricing Sheet
    sheet = frappe.new_doc("Pricing Sheet")
    sheet.sheet_name = "Test Consolidation Sheet"
    sheet.customer = customer
    sheet.pricing_scenario = scenario
    
    # Intentionally do not set margin_policy, it shouldn't exist anyway.
    # Set the benchmark policy explicitly if default doesn't kick in, but it should.
    
    sheet.append("lines", {
        "item": item,
        "qty": 10
    })

    try:
        sheet.insert(ignore_permissions=True)
        print(f"SUCCESS: Pricing Sheet created - {sheet.name}")
        
        # Check if benchmark policy got applied
        if sheet.applied_benchmark_policy:
            print(f"SUCCESS: Applied Benchmark Policy: {sheet.applied_benchmark_policy}")
        else:
            print("WARNING: No benchmark policy was applied.")

        # Recalculate and trigger the engine
        sheet.recalculate_margins_and_benchmarks()
        sheet.save(ignore_permissions=True)
        print("SUCCESS: Recalculate completed without errors.")
        
        # Verify the line item got some margin or base calculation
        if sheet.lines:
            line = sheet.lines[0]
            print(f"Line Margin %: {line.margin_pct}")
            print(f"Line Benchmark Rule: {line.resolved_benchmark_rule}")
            
    except Exception as e:
        print(f"ERROR: Exception during Pricing Sheet lifecycle: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if sheet.name:
            frappe.delete_doc("Pricing Sheet", sheet.name, ignore_permissions=True, force=True)
            frappe.db.commit()
            print("Cleanup: Deleted test sheet.")
