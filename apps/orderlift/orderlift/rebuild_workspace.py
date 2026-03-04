import frappe

def execute():
    ws = frappe.get_doc("Workspace Sidebar", "Main Dashboard")
    
    pricing_labels = [
        "Pricing Dashboard", "Pricing Operations", "Pricing Sheets", "Pricing Scenarios", 
        "Market Prices", "Policies & Configs", "Agent Rules", "Segmentation Engine",
        "Benchmark Policy", "Customs Policy", "Margin Policy", "Scenario Policy",
        "Pricing Margin Policy", "Pricing Margin Rule", "Pricing Customs Policy",
        "Pricing Customs Rule", "Pricing Benchmark Source", "Pricing Benchmark Rule",
        "Customer Segmentation Rule", "Pricing Tier Modifier", "Pricing Zone Modifier"
    ]
    
    # 1. Gather existing non-pricing items
    other_items = []
    for item in ws.get("items", []):
        if item.label not in pricing_labels and getattr(item, 'link_to', '') not in pricing_labels:
            other_items.append({
                'type': item.type,
                'label': item.label,
                'link_type': item.link_type,
                'link_to': getattr(item, 'link_to', ''),
                'child': item.child,
                'icon': item.icon
            })
            
    # Clear the table entirely
    ws.set("items", [])
    
    # 2. Add back the non-pricing items
    for item in other_items:
        ws.append("items", item)
    
    # 3. Add the Pricing items explicitly at the end
    ws.append('items', {'type': 'Link', 'label': 'Pricing Dashboard', 'link_type': 'Page', 'link_to': 'pricing-dashboard', 'child': 0, 'icon': 'chart-line'})
    
    ws.append('items', {'type': 'Section Break', 'label': 'Pricing Operations', 'child': 0})
    ws.append('items', {'type': 'Link', 'label': 'Pricing Sheets', 'link_type': 'DocType', 'link_to': 'Pricing Sheet', 'child': 1, 'icon': 'file-text'})
    ws.append('items', {'type': 'Link', 'label': 'Pricing Scenarios', 'link_type': 'DocType', 'link_to': 'Pricing Scenario', 'child': 1, 'icon': 'branch'})
    ws.append('items', {'type': 'Link', 'label': 'Market Prices', 'link_type': 'DocType', 'link_to': 'Market Price Entry', 'child': 1, 'icon': 'money-coins'})

    ws.append('items', {'type': 'Section Break', 'label': 'Policies & Configs', 'child': 0})
    ws.append('items', {'type': 'Link', 'label': 'Agent Rules', 'link_type': 'DocType', 'link_to': 'Agent Pricing Rules', 'child': 1, 'icon': 'users'})
    ws.append('items', {'type': 'Link', 'label': 'Segmentation Engine', 'link_type': 'DocType', 'link_to': 'Customer Segmentation Engine', 'child': 1, 'icon': 'target'})
    ws.append('items', {'type': 'Link', 'label': 'Benchmark Policy', 'link_type': 'DocType', 'link_to': 'Pricing Benchmark Policy', 'child': 1, 'icon': 'award'})
    ws.append('items', {'type': 'Link', 'label': 'Customs Policy', 'link_type': 'DocType', 'link_to': 'Pricing Customs Policy', 'child': 1, 'icon': 'shield'})
    ws.append('items', {'type': 'Link', 'label': 'Margin Policy', 'link_type': 'DocType', 'link_to': 'Pricing Margin Policy', 'child': 1, 'icon': 'percentage'})
    ws.append('items', {'type': 'Link', 'label': 'Scenario Policy', 'link_type': 'DocType', 'link_to': 'Pricing Scenario Policy', 'child': 1, 'icon': 'workflow'})

    ws.save(ignore_permissions=True)
    frappe.db.commit()
    print("Workspace Main Dashboard completely ordered and rebuilt.")
