import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


RETIRED_CUSTOM_FIELDS = [
    "Delivery Note-custom_assigned_container_load_plan",
    "Delivery Trip-custom_container_load_plan",
]


def after_migrate():
    remove_retired_custom_fields()

    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_packaging_profiles",
                    "label": "Packaging Profiles",
                    "fieldtype": "Table",
                    "options": "Item Packaging Profile",
                    "insert_after": "uoms",
                },
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
                {
                    "fieldname": "custom_inventory_flag",
                    "label": "Inventory Flag",
                    "fieldtype": "Select",
                    "options": "Slow Moving\nOverstock\nDormant",
                    "insert_after": "custom_height_cm",
                    "read_only": 1,
                    "in_standard_filter": 1,
                },
            ],
            # ── Purchase Order: scenario classification ──
            "Purchase Order": [
                {
                    "fieldname": "custom_pricing_alerts_section",
                    "label": "Pricing Alerts",
                    "fieldtype": "Section Break",
                    "insert_after": "items",
                },
                {
                    "fieldname": "custom_pricing_alerts_html",
                    "label": "Pricing Alerts HTML",
                    "fieldtype": "HTML",
                    "insert_after": "custom_pricing_alerts_section",
                },
                {
                    "fieldname": "custom_logistics_section",
                    "label": "Logistics",
                    "fieldtype": "Section Break",
                    "insert_after": "terms",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_flow_scope",
                    "label": "Flow Scope",
                    "fieldtype": "Select",
                    "options": "\nInbound\nDomestic",
                    "insert_after": "custom_logistics_section",
                    "default": "Inbound",
                    "in_standard_filter": 1,
                    "description": "Inbound = import/international procurement. Domestic = local supplier.",
                },
                {
                    "fieldname": "custom_shipping_responsibility",
                    "label": "Shipping Responsibility",
                    "fieldtype": "Select",
                    "options": "\nOrderlift\nCustomer",
                    "insert_after": "custom_flow_scope",
                    "default": "Orderlift",
                    "in_standard_filter": 1,
                },
            ],
            # ── Sales Order: scenario classification ──
            "Sales Order": [
                {
                    "fieldname": "custom_logistics_section",
                    "label": "Logistics",
                    "fieldtype": "Section Break",
                    "insert_after": "terms",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_flow_scope",
                    "label": "Flow Scope",
                    "fieldtype": "Select",
                    "options": "\nDomestic\nOutbound",
                    "insert_after": "custom_logistics_section",
                    "in_standard_filter": 1,
                    "description": "Domestic = local distribution. Outbound = export.",
                },
                {
                    "fieldname": "custom_shipping_responsibility",
                    "label": "Shipping Responsibility",
                    "fieldtype": "Select",
                    "options": "\nOrderlift\nCustomer",
                    "insert_after": "custom_flow_scope",
                    "in_standard_filter": 1,
                },
            ],
            # ── Delivery Note: scenario classification + existing fields ──
            "Delivery Note": [
                {
                    "fieldname": "custom_flow_scope",
                    "label": "Flow Scope",
                    "fieldtype": "Select",
                    "options": "\nInbound\nDomestic\nOutbound",
                    "insert_after": "shipping_address_name",
                    "in_standard_filter": 1,
                    "description": "Inherited from Sales Order. Set manually for domestic dispatch.",
                },
                {
                    "fieldname": "custom_shipping_responsibility",
                    "label": "Shipping Responsibility",
                    "fieldtype": "Select",
                    "options": "\nOrderlift\nCustomer",
                    "insert_after": "custom_flow_scope",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_destination_zone",
                    "label": "Destination Zone",
                    "fieldtype": "Data",
                    "insert_after": "custom_shipping_responsibility",
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
                    "fieldname": "custom_logistics_locked",
                    "label": "Logistics Locked",
                    "fieldtype": "Check",
                    "insert_after": "custom_logistics_status",
                    "read_only": 1,
                    "default": "0",
                },
            ],
            "Purchase Order Item": [
                {
                    "fieldname": "custom_packaging_profile",
                    "label": "Packaging Profile",
                    "fieldtype": "Link",
                    "options": "Item Packaging Profile",
                    "insert_after": "item_code",
                    "in_list_view": 1,
                    "description": "Selected packaging format for purchasing and import. Defaults to item default profile.",
                },
                {
                    "fieldname": "custom_packaging_profile_source",
                    "label": "Packaging Source",
                    "fieldtype": "Select",
                    "options": "\nselected\ndefault\nitem_fallback",
                    "insert_after": "custom_packaging_profile",
                    "read_only": 1,
                    "in_list_view": 1,
                    "description": "How the packaging was resolved for this row.",
                },
                {
                    "fieldname": "custom_packaging_type",
                    "label": "Packaging Type",
                    "fieldtype": "Data",
                    "insert_after": "custom_packaging_uom",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_packaging_uom",
                    "label": "Packaging UOM",
                    "fieldtype": "Data",
                    "insert_after": "custom_packaging_profile_source",
                    "read_only": 1,
                    "fetch_from": "custom_packaging_profile.uom",
                },
                {
                    "fieldname": "custom_units_per_package",
                    "label": "Units Per Package",
                    "fieldtype": "Float",
                    "insert_after": "custom_packaging_uom",
                    "read_only": 1,
                    "fetch_from": "custom_packaging_profile.units_per_package",
                    "default": "1",
                },
                {
                    "fieldname": "custom_package_count",
                    "label": "Package Count",
                    "fieldtype": "Float",
                    "insert_after": "custom_units_per_package",
                    "read_only": 1,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_package_weight_kg",
                    "label": "Weight Per Package (kg)",
                    "fieldtype": "Float",
                    "insert_after": "custom_package_count",
                    "read_only": 1,
                    "fetch_from": "custom_packaging_profile.weight_kg",
                },
                {
                    "fieldname": "custom_package_volume_m3",
                    "label": "Volume Per Package (m3)",
                    "fieldtype": "Float",
                    "insert_after": "custom_package_weight_kg",
                    "read_only": 1,
                    "fetch_from": "custom_packaging_profile.volume_m3",
                },
            ],
            "Purchase Receipt": [
                {
                    "fieldname": "custom_qc_routed",
                    "label": "QC Routed",
                    "fieldtype": "Check",
                    "insert_after": "remarks",
                    "read_only": 1,
                    "default": "0",
                    "description": "Items have been routed to correct warehouse based on QC results",
                },
            ],
            "Buying Settings": [
                {
                    "fieldname": "custom_po_alerts_section",
                    "label": "Purchase Pricing Alerts",
                    "fieldtype": "Section Break",
                    "insert_after": "disable_last_purchase_rate",
                },
                {
                    "fieldname": "custom_stale_purchase_threshold_days",
                    "label": "Stale Purchase Threshold (days)",
                    "fieldtype": "Int",
                    "insert_after": "custom_po_alerts_section",
                    "default": "90",
                    "description": "Days after which a last purchase reference is considered stale.",
                },
                {
                    "fieldname": "custom_supplier_price_lookback_days",
                    "label": "Supplier Price Lookback (days)",
                    "fieldtype": "Int",
                    "insert_after": "custom_stale_purchase_threshold_days",
                    "default": "180",
                    "description": "Only compare other-supplier purchase history within this lookback window.",
                },
                {
                    "fieldname": "custom_better_supplier_min_savings_percent",
                    "label": "Better Supplier Min Savings (%)",
                    "fieldtype": "Percent",
                    "insert_after": "custom_supplier_price_lookback_days",
                    "default": "5",
                    "description": "Minimum savings needed before showing a better supplier alert.",
                },
            ],
            "Stock Entry": [
                {
                    "fieldname": "custom_source_pr",
                    "label": "Source Purchase Receipt",
                    "fieldtype": "Link",
                    "options": "Purchase Receipt",
                    "insert_after": "purchase_receipt_no",
                    "read_only": 1,
                },
            ],
            # ── Delivery Trip: scenario classification + forecast plan link ──
            "Delivery Trip": [
                {
                    "fieldname": "custom_logistics_section",
                    "label": "Logistics",
                    "fieldtype": "Section Break",
                    "insert_after": "driver",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_flow_scope",
                    "label": "Flow Scope",
                    "fieldtype": "Select",
                    "options": "\nDomestic\nOutbound",
                    "insert_after": "custom_logistics_section",
                    "in_standard_filter": 1,
                    "description": "Set automatically from the source delivery flow.",
                },
                {
                    "fieldname": "custom_forecast_plan",
                    "label": "Forecast Plan",
                    "fieldtype": "Link",
                    "options": "Forecast Load Plan",
                    "insert_after": "custom_flow_scope",
                    "read_only": 1,
                    "in_standard_filter": 1,
                },
            ],
        },
        update=True,
    )

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Buying Settings")
    frappe.clear_cache(doctype="Purchase Order")
    frappe.clear_cache(doctype="Sales Order")
    frappe.clear_cache(doctype="Delivery Note")
    frappe.clear_cache(doctype="Purchase Receipt")
    frappe.clear_cache(doctype="Stock Entry")
    frappe.clear_cache(doctype="Delivery Trip")
    retire_logistics_workspace()


def retire_logistics_workspace():
    workspace_name = "Hub Logistique"

    if frappe.db.exists("Workspace", workspace_name):
        frappe.db.set_value(
            "Workspace",
            workspace_name,
            {"public": 0, "is_hidden": 1},
            update_modified=False,
        )

    if frappe.db.exists("Workspace Sidebar", workspace_name):
        frappe.delete_doc("Workspace Sidebar", workspace_name, ignore_permissions=True)


def remove_retired_custom_fields():
    for custom_field_name in RETIRED_CUSTOM_FIELDS:
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.delete_doc("Custom Field", custom_field_name, ignore_permissions=True)
