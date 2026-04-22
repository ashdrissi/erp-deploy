import frappe


def after_migrate():
    """Setup orderlift_logistics module and retire duplicate logistics workspace shell."""
    retire_logistics_hub_workspace()


def retire_logistics_hub_workspace():
    """Retire the standalone Logistics Hub workspace so Main Dashboard owns logistics routes."""
    workspace_name = "Logistics Hub"

    if frappe.db.exists("Workspace", workspace_name):
        frappe.db.set_value(
            "Workspace",
            workspace_name,
            {"public": 0, "is_hidden": 1},
            update_modified=False,
        )

    if frappe.db.exists("Workspace Sidebar", workspace_name):
        frappe.delete_doc("Workspace Sidebar", workspace_name, ignore_permissions=True)
