import json
import frappe


def after_migrate():
    """Setup orderlift_logistics module: create workspace and ensure doctypes are ready."""
    ensure_logistics_cockpit_workspace()


def ensure_logistics_cockpit_workspace():
    """Create or update the Logistics Hub Cockpit workspace."""
    workspace_name = "Logistics Hub"
    shortcuts = [
        {"label": "Logistics Hub Cockpit", "type": "Page", "link_to": "logistics-hub-cockpit"},
        {"label": "Container Load Plan", "type": "DocType", "link_to": "Container Load Plan"},
        {"label": "Container Profile", "type": "DocType", "link_to": "Container Profile"},
        {"label": "Shipment Analysis", "type": "DocType", "link_to": "Shipment Analysis"},
        {"label": "Load Plan Shipment", "type": "DocType", "link_to": "Load Plan Shipment"},
    ]

    content = [
        {
            "id": "logistics_header",
            "type": "header",
            "data": {"text": "<span class=\"h4\"><b>Logistics Hub</b></span>", "col": 12},
        },
        {"id": "logistics_spacer", "type": "spacer", "data": {"col": 12}},
    ]

    for idx, shortcut in enumerate(shortcuts, start=1):
        content.append(
            {
                "id": f"logistics_shortcut_{idx}",
                "type": "shortcut",
                "data": {"shortcut_name": shortcut["label"], "col": 4},
            }
        )

    workspace = (
        frappe.get_doc("Workspace", workspace_name)
        if frappe.db.exists("Workspace", workspace_name)
        else frappe.new_doc("Workspace")
    )

    workspace.title = workspace_name
    workspace.label = workspace_name
    workspace.module = "Orderlift Logistics"
    workspace.public = 1
    workspace.is_hidden = 0
    workspace.content = json.dumps(content)
    workspace.set("shortcuts", [])

    for shortcut in shortcuts:
        workspace.append("shortcuts", shortcut)

    workspace.save(ignore_permissions=True)
