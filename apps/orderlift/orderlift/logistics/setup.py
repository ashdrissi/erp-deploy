import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_volume_m3",
                    "label": "Volume (m3)",
                    "fieldtype": "Float",
                    "insert_after": "custom_weight_kg",
                    "default": "0",
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_length_cm",
                    "label": "Length (cm)",
                    "fieldtype": "Float",
                    "insert_after": "custom_volume_m3",
                    "default": "0",
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_width_cm",
                    "label": "Width (cm)",
                    "fieldtype": "Float",
                    "insert_after": "custom_length_cm",
                    "default": "0",
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_height_cm",
                    "label": "Height (cm)",
                    "fieldtype": "Float",
                    "insert_after": "custom_width_cm",
                    "default": "0",
                    "non_negative": 1,
                },
            ],
            "Delivery Note": [
                {
                    "fieldname": "custom_destination_zone",
                    "label": "Destination Zone",
                    "fieldtype": "Data",
                    "insert_after": "shipping_address_name",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_total_weight_kg",
                    "label": "Total Weight (kg)",
                    "fieldtype": "Float",
                    "insert_after": "custom_destination_zone",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_total_volume_m3",
                    "label": "Total Volume (m3)",
                    "fieldtype": "Float",
                    "insert_after": "custom_total_weight_kg",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_recommended_container",
                    "label": "Recommended Container",
                    "fieldtype": "Link",
                    "options": "Container Profile",
                    "insert_after": "custom_total_volume_m3",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_limiting_factor",
                    "label": "Limiting Factor",
                    "fieldtype": "Select",
                    "options": "weight\nvolume\nboth",
                    "insert_after": "custom_recommended_container",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_logistics_status",
                    "label": "Logistics Status",
                    "fieldtype": "Select",
                    "options": "ok\nincomplete_data\nno_container_found\nover_capacity\ncancelled",
                    "insert_after": "custom_limiting_factor",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_assigned_container_load_plan",
                    "label": "Assigned Container Load Plan",
                    "fieldtype": "Link",
                    "options": "Container Load Plan",
                    "insert_after": "custom_logistics_status",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_logistics_locked",
                    "label": "Logistics Locked",
                    "fieldtype": "Check",
                    "insert_after": "custom_assigned_container_load_plan",
                    "read_only": 1,
                    "default": "0",
                },
            ],
        },
        update=True,
    )

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Delivery Note")
    ensure_logistics_workspace()


def ensure_logistics_workspace():
    workspace_name = "Hub Logistique"
    shortcuts = [
        {"label": "Container Load Plan", "type": "DocType", "link_to": "Container Load Plan"},
        {"label": "Container Profile", "type": "DocType", "link_to": "Container Profile"},
        {"label": "Shipment Analysis", "type": "DocType", "link_to": "Shipment Analysis"},
        {"label": "Delivery Note", "type": "DocType", "link_to": "Delivery Note"},
    ]

    content = [
        {
            "id": "logistics_header",
            "type": "header",
            "data": {"text": "<span class=\"h4\"><b>Hub Logistique</b></span>", "col": 12},
        },
        {"id": "logistics_spacer", "type": "spacer", "data": {"col": 12}},
    ]

    for idx, shortcut in enumerate(shortcuts, start=1):
        content.append(
            {
                "id": f"logistics_shortcut_{idx}",
                "type": "shortcut",
                "data": {"shortcut_name": shortcut["label"], "col": 3},
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
