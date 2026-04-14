import frappe


def after_migrate():
    """Setup orderlift_logistics module and retire duplicate logistics workspace shell."""
    backfill_container_load_plan_defaults()
    retire_logistics_hub_workspace()


def backfill_container_load_plan_defaults():
    """Fill legacy CLP rows created before scenario fields existed."""
    if not frappe.db.exists("DocType", "Container Load Plan"):
        return

    rows = frappe.get_all(
        "Container Load Plan",
        filters={"flow_scope": ["is", "not set"]},
        fields=["name", "flow_scope", "shipping_responsibility", "source_type"],
        limit_page_length=0,
    )

    for row in rows:
        updates = {}
        if not row.flow_scope:
            updates["flow_scope"] = "Outbound"
        if not row.shipping_responsibility:
            updates["shipping_responsibility"] = "Orderlift"
        if not row.source_type:
            updates["source_type"] = "Delivery Note"
        if updates:
            frappe.db.set_value("Container Load Plan", row.name, updates, update_modified=False)


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
