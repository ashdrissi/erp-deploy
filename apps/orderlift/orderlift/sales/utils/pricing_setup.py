import frappe
import json
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_material",
                    "label": "Material",
                    "fieldtype": "Select",
                    "options": "STEEL\nALUM\nGALVA\nINOX\nCOPPER\nOTHER",
                    "insert_after": "item_group",
                    "in_list_view": 0,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_weight_kg",
                    "label": "Weight (kg)",
                    "fieldtype": "Float",
                    "insert_after": "custom_material",
                    "default": "0",
                    "non_negative": 1,
                },
            ],
            "Quotation": [
                {
                    "fieldname": "source_pricing_sheet",
                    "label": "Source Pricing Sheet",
                    "fieldtype": "Link",
                    "options": "Pricing Sheet",
                    "insert_after": "order_type",
                    "read_only": 1,
                    "in_standard_filter": 1,
                }
            ],
            "Quotation Item": [
                {
                    "fieldname": "source_pricing_sheet_line",
                    "label": "Source Pricing Sheet Line",
                    "fieldtype": "Data",
                    "insert_after": "description",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_pricing_scenario",
                    "label": "Source Pricing Scenario",
                    "fieldtype": "Link",
                    "options": "Pricing Scenario",
                    "insert_after": "source_pricing_sheet_line",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_pricing_override",
                    "label": "Source Pricing Override",
                    "fieldtype": "Check",
                    "insert_after": "source_pricing_scenario",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_policy",
                    "label": "Source Margin Policy",
                    "fieldtype": "Link",
                    "options": "Pricing Margin Policy",
                    "insert_after": "source_pricing_override",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_percent",
                    "label": "Source Margin Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_margin_policy",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_customs_applied",
                    "label": "Source Customs Applied",
                    "fieldtype": "Currency",
                    "insert_after": "source_margin_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_customs_basis",
                    "label": "Source Customs Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_customs_applied",
                    "read_only": 1,
                },
            ],
            "Selling Settings": [
                {
                    "fieldname": "custom_pricing_group_line_item",
                    "label": "Pricing Group Line Item",
                    "fieldtype": "Link",
                    "options": "Item",
                    "insert_after": "cust_master_name",
                },
                {
                    "fieldname": "custom_pricing_group_desc_prefix",
                    "label": "Pricing Group Description Prefix",
                    "fieldtype": "Data",
                    "insert_after": "custom_pricing_group_line_item",
                    "default": "Grouped from Pricing Sheet",
                },
            ],
        },
        update=True,
    )

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Quotation")
    frappe.clear_cache(doctype="Quotation Item")
    frappe.clear_cache(doctype="Selling Settings")
    ensure_pricing_workspace()


def ensure_pricing_workspace():
    workspace_name = "Pricing"
    legacy_workspace_name = "Pricing & Quotations"

    if frappe.db.exists("Workspace", legacy_workspace_name) and not frappe.db.exists(
        "Workspace", workspace_name
    ):
        frappe.rename_doc(
            "Workspace",
            legacy_workspace_name,
            workspace_name,
            force=True,
            ignore_permissions=True,
        )

    shortcuts = [
        {"label": "Quotation", "type": "DocType", "link_to": "Quotation"},
        {"label": "Pricing Sheet", "type": "DocType", "link_to": "Pricing Sheet"},
        {"label": "Pricing Scenario", "type": "DocType", "link_to": "Pricing Scenario"},
        {"label": "Margin Policies", "type": "DocType", "link_to": "Pricing Margin Policy"},
        {"label": "Customs Policies", "type": "DocType", "link_to": "Pricing Customs Policy"},
    ]

    content = [
        {
            "id": "pricing_header",
            "type": "header",
            "data": {"text": "<span class=\"h4\"><b>Pricing</b></span>", "col": 12},
        },
        {"id": "pricing_spacer", "type": "spacer", "data": {"col": 12}},
    ]

    for idx, shortcut in enumerate(shortcuts, start=1):
        content.append(
            {
                "id": f"pricing_shortcut_{idx}",
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
    workspace.module = "Selling"
    workspace.public = 1
    workspace.is_hidden = 0
    workspace.content = json.dumps(content)

    workspace.set("shortcuts", [])
    for shortcut in shortcuts:
        workspace.append(
            "shortcuts",
            {
                "label": shortcut["label"],
                "type": shortcut["type"],
                "link_to": shortcut["link_to"],
            },
        )

    workspace.save(ignore_permissions=True)
