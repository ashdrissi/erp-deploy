import frappe


SERIALIZED_FIELDS = (
    "type",
    "label",
    "link_type",
    "link_to",
    "child",
    "icon",
    "description",
    "hidden",
    "collapsible",
    "indent",
    "keep_closed",
    "show_arrow",
    "dependencies",
    "only_for",
    "report_ref_doctype",
    "onboard",
    "is_query_report",
)

MY_WORK_ITEMS = [
    {
        "type": "Section Break",
        "label": "My Work",
        "icon": "user-round",
        "child": 0,
    },
    {
        "type": "Link",
        "label": "Notifications",
        "link_type": "DocType",
        "link_to": "Notification Log",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "ToDo",
        "link_type": "DocType",
        "link_to": "ToDo",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Assignments",
        "link_type": "DocType",
        "link_to": "ToDo",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Calendar",
        "link_type": "DocType",
        "link_to": "Event",
        "icon": "dot",
        "child": 1,
    },
]

ADMIN_ITEMS = [
    {
        "type": "Section Break",
        "label": "Administration",
        "icon": "users",
        "child": 0,
    },
    {
        "type": "Link",
        "label": "Users",
        "link_type": "DocType",
        "link_to": "User",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Roles",
        "link_type": "DocType",
        "link_to": "Role",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Role Profiles",
        "link_type": "DocType",
        "link_to": "Role Profile",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "User Permissions",
        "link_type": "DocType",
        "link_to": "User Permission",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Permission Manager",
        "link_type": "Page",
        "link_to": "permission-manager",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Workflow",
        "link_type": "DocType",
        "link_to": "Workflow",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Workflow State",
        "link_type": "DocType",
        "link_to": "Workflow State",
        "icon": "dot",
        "child": 1,
    },
    {
        "type": "Link",
        "label": "Assignment Rule",
        "link_type": "DocType",
        "link_to": "Assignment Rule",
        "icon": "dot",
        "child": 1,
    },
]


def _serialize_item(item):
    data = {}
    for fieldname in SERIALIZED_FIELDS:
        value = getattr(item, fieldname, None)
        if value is not None:
            data[fieldname] = value
    return data


def _remove_by_labels(items, labels):
    label_set = set(labels)
    return [item for item in items if item.get("label") not in label_set]


def _insert_after_label(items, after_label, new_items):
    for index, item in enumerate(items):
        if item.get("label") == after_label:
            return items[: index + 1] + new_items + items[index + 1 :]
    return items + new_items


def ensure_main_dashboard_admin_sections():
    ws = frappe.get_doc("Workspace Sidebar", "Main Dashboard")
    items = [_serialize_item(item) for item in ws.get("items", [])]

    items = _remove_by_labels(items, [item["label"] for item in MY_WORK_ITEMS + ADMIN_ITEMS])
    items = _insert_after_label(items, "Dashboard", MY_WORK_ITEMS)
    items = _insert_after_label(items, "Companies", ADMIN_ITEMS)

    ws.set("items", [])
    for item in items:
        ws.append("items", item)

    ws.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    return {
        "workspace_sidebar": ws.name,
        "items_added": [item["label"] for item in MY_WORK_ITEMS + ADMIN_ITEMS],
    }


def execute():
    ws = frappe.get_doc("Workspace Sidebar", "Main Dashboard")
    
    pricing_labels = [
        "Pricing Operations", "Pricing Builder", "Pricing Sheets", "Pricing Scenarios",
        "Policies & Configs", "Agent Rules", "Segmentation Engine",
        "Benchmark Policy", "Customs Policy", "Margin Policy",
        "Pricing Margin Policy", "Pricing Margin Rule", "Pricing Customs Policy",
        "Pricing Customs Rule", "Pricing Benchmark Source", "Pricing Benchmark Rule",
        "Customer Segmentation Rule", "Pricing Tier Modifier", "Pricing Zone Modifier"
    ]
    
    icon_map = {
        'Customer': 'users',
        'Quotation': 'file-text',
        'Sale Order': 'shopping-cart',
        'Stock Entry': 'truck',
        'Warehouse': 'home',
        'Stock Ledger': 'book',
        'Projected Quantity': 'activity',
        'Item': 'box',
        'Product Bundle': 'layers',
        'Price List': 'list',
        'Item Price': 'tag',
        'Pricing Rule': 'award',
        'Companies': 'briefcase',
        'Logistics Hub Cockpit': 'map-pin',
        'Container Load Plan': 'grid',
        'Container Profile': 'database',
        'Shipment Analysis': 'pie-chart',
        'Hub Logistique': 'navigation',
        'Dashboard': 'dashboard',
        'Sales': 'shopping-cart',
        'Stock Visibility': 'eye',
        'Base Articles': 'box',
        'Logistics': 'truck'
    }

    # 1. Gather existing non-pricing items
    other_items = []
    for item in ws.get("items", []):
        if item.label not in pricing_labels and getattr(item, 'link_to', '') not in pricing_labels:
            new_icon = icon_map.get(item.label) or item.icon
            other_items.append({
                'type': item.type,
                'label': item.label,
                'link_type': item.link_type,
                'link_to': getattr(item, 'link_to', ''),
                'child': item.child,
                'icon': new_icon
            })
            
    # Clear the table entirely
    ws.set("items", [])
    
    # 2. Add back the non-pricing items
    for item in other_items:
        ws.append("items", item)
    
    # 3. Add the Pricing items explicitly at the end
    ws.append('items', {'type': 'Section Break', 'label': 'Pricing Operations', 'child': 0})
    ws.append('items', {'type': 'Link', 'label': 'Pricing Builder', 'link_type': 'DocType', 'link_to': 'Pricing Builder', 'child': 1, 'icon': 'tool'})
    ws.append('items', {'type': 'Link', 'label': 'Pricing Sheets', 'link_type': 'DocType', 'link_to': 'Pricing Sheet', 'child': 1, 'icon': 'file-text'})
    ws.append('items', {'type': 'Link', 'label': 'Pricing Scenarios', 'link_type': 'DocType', 'link_to': 'Pricing Scenario', 'child': 1, 'icon': 'branch'})

    ws.append('items', {'type': 'Section Break', 'label': 'Policies & Configs', 'child': 0})
    ws.append('items', {'type': 'Link', 'label': 'Agent Rules', 'link_type': 'DocType', 'link_to': 'Agent Pricing Rules', 'child': 1, 'icon': 'users'})
    ws.append('items', {'type': 'Link', 'label': 'Segmentation Engine', 'link_type': 'DocType', 'link_to': 'Customer Segmentation Engine', 'child': 1, 'icon': 'target'})
    ws.append('items', {'type': 'Link', 'label': 'Benchmark Policy', 'link_type': 'DocType', 'link_to': 'Pricing Benchmark Policy', 'child': 1, 'icon': 'award'})
    ws.append('items', {'type': 'Link', 'label': 'Customs Policy', 'link_type': 'DocType', 'link_to': 'Pricing Customs Policy', 'child': 1, 'icon': 'shield'})
    ws.append('items', {'type': 'Link', 'label': 'Margin Policy', 'link_type': 'DocType', 'link_to': 'Pricing Margin Policy', 'child': 1, 'icon': 'percentage'})
    ws.save(ignore_permissions=True)
    frappe.db.commit()
    print("Workspace Main Dashboard completely ordered and rebuilt with icons.")
