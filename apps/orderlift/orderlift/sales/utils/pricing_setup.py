import json
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from orderlift.role_capabilities import ROLE_CAPABILITY_FIELD, seed_default_role_capabilities
from orderlift.orderlift_sales.utils.price_list_scope import (
    BENCHMARK_PRICE_LIST,
    BUYING_PRICE_LIST,
    PRICE_LIST_TYPE_FIELD,
    SELLING_PRICE_LIST,
)


DEFAULT_MANUAL_TIER = "New"
DEFAULT_PRICING_TIERS = [DEFAULT_MANUAL_TIER, "Eco", "Intermediaire", "Luxe", "Gold", "Silver", "Bronze"]


def after_migrate():
    _coerce_customer_tier_fields_to_links()
    _coerce_item_material_field_to_link()
    _coerce_customs_material_field_to_link()
    ensure_item_material_records()
    create_custom_fields(
        {
            "Company": [
                {
                    "fieldname": "custom_orderlift_tax_settings_section",
                    "label": "Orderlift Tax Settings",
                    "fieldtype": "Section Break",
                    "insert_after": "default_currency",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_default_sales_taxes_template",
                    "label": "Default Sales Tax Template",
                    "fieldtype": "Link",
                    "options": "Sales Taxes and Charges Template",
                    "insert_after": "custom_orderlift_tax_settings_section",
                    "description": "Default sales tax template used by Orderlift catalogue TTC and pricing previews.",
                },
            ],
            "Role": [
                {
                    "fieldname": ROLE_CAPABILITY_FIELD,
                    "label": "Orderlift Capabilities",
                    "fieldtype": "Small Text",
                    "insert_after": "desk_access",
                    "description": "Newline-separated Orderlift capability keys. Used in shadow mode until orderlift_use_role_capabilities is enabled.",
                },
            ],
            "Customer": [
                {
                    "fieldname": "enable_dynamic_segmentation",
                    "label": "Enable Dynamic Segmentation",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "customer_group",
                    "in_standard_filter": 1,
                    "description": "If enabled, Tier is maintained by segmentation engines.",
                },
                {
                    "fieldname": "tier",
                    "label": "Pricing Tier",
                    "fieldtype": "Link",
                    "options": "Pricing Tier",
                    "default": DEFAULT_MANUAL_TIER,
                    "insert_after": "enable_dynamic_segmentation",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "depends_on": "eval:!doc.enable_dynamic_segmentation",
                    "mandatory_depends_on": "eval:!doc.enable_dynamic_segmentation",
                },
                {
                    "fieldname": "manual_tier",
                    "label": "Manual Tier",
                    "fieldtype": "Link",
                    "options": "Pricing Tier",
                    "default": DEFAULT_MANUAL_TIER,
                    "insert_after": "tier",
                    "in_standard_filter": 1,
                    "hidden": 1,
                    "depends_on": "",
                    "description": "Technical mirror of Tier when dynamic segmentation is disabled.",
                },
                {
                    "fieldname": "tier_last_calculated_on",
                    "label": "Tier Last Calculated On",
                    "fieldtype": "Datetime",
                    "insert_after": "manual_tier",
                    "read_only": 1,
                    "hidden": 1,
                    "depends_on": "eval:doc.enable_dynamic_segmentation==1",
                },
                {
                    "fieldname": "tier_source",
                    "label": "Tier Source",
                    "fieldtype": "Data",
                    "insert_after": "tier_last_calculated_on",
                    "read_only": 1,
                    "hidden": 1,
                },
            ],
            "Prospect": _prospect_tier_fields(insert_after="customer_group"),
            "Lead": _prospect_tier_fields(insert_after="custom_crm_segments"),
            "Item": [
                {
                    "fieldname": "custom_material",
                    "label": "Material",
                    "fieldtype": "Link",
                    "options": "Item Material",
                    "insert_after": "item_group",
                    "in_list_view": 0,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_customs_material",
                    "label": "Douane Material",
                    "fieldtype": "Link",
                    "options": "Douane Material",
                    "insert_after": "customs_tariff_number",
                    "in_standard_filter": 1,
                    "description": "Customs/Douane material from the article workbook. Used by customs policies, separate from Item Material.",
                },
                {
                    "fieldname": "custom_weight_kg",
                    "label": "Weight (kg)",
                    "fieldtype": "Float",
                    "insert_after": "custom_customs_material",
                    "default": "0",
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_volume_m3",
                    "label": "Volume (m3)",
                    "fieldtype": "Float",
                    "insert_after": "custom_weight_kg",
                    "default": "0",
                    "non_negative": 1,
                },
            ],
            "Price List": [
                {
                    "fieldname": PRICE_LIST_TYPE_FIELD,
                    "label": "Price List Type",
                    "fieldtype": "Select",
                    "options": f"{BUYING_PRICE_LIST}\n{SELLING_PRICE_LIST}\n{BENCHMARK_PRICE_LIST}",
                    "insert_after": "currency",
                    "default": SELLING_PRICE_LIST,
                    "reqd": 1,
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "description": "Benchmark is an Orderlift reference type used only in benchmark-aware pricing tools; ERPNext still keeps it natively saveable as a selling list.",
                },
                {
                    "fieldname": "custom_price_list_sharing",
                    "label": "Price List Sharing",
                    "fieldtype": "Table",
                    "options": "Price List Sharing",
                    "insert_after": PRICE_LIST_TYPE_FIELD,
                    "description": "Share this selling price list with other companies. Shared lists appear as buying sources in the target company.",
                },
                {
                    "fieldname": "custom_is_shared_from",
                    "label": "Shared From",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "custom_price_list_sharing",
                    "read_only": 1,
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "description": "Source selling price list that this list mirrors. Populated automatically for shared lists.",
                },
                {
                    "fieldname": "custom_shared_on",
                    "label": "Shared On",
                    "fieldtype": "Datetime",
                    "insert_after": "custom_is_shared_from",
                    "read_only": 1,
                    "hidden": 1,
                    "description": "Date when this list was shared.",
                },
                {
                    "fieldname": "custom_orderlift_builder_section",
                    "label": "Orderlift Builder",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_is_shared_from",
                    "collapsible": 1,
                    "collapsed": 1,
                },
                {
                    "fieldname": "custom_pricing_builder",
                    "label": "Pricing Builder",
                    "fieldtype": "Link",
                    "options": "Pricing Builder",
                    "insert_after": "custom_orderlift_builder_section",
                    "read_only": 1,
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "description": "Builder that last published prices to this selling list.",
                },
                {
                    "fieldname": "custom_auto_rebuild_from_source_buying_prices",
                    "label": "Auto Rebuild from Source Buying Prices",
                    "fieldtype": "Check",
                    "insert_after": "custom_pricing_builder",
                    "default": "0",
                    "description": "When enabled, changes in stamped source buying prices update existing builder-created selling item prices.",
                },
                {
                    "fieldname": "custom_source_buying_price_lists",
                    "label": "Source Buying Price Lists",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_auto_rebuild_from_source_buying_prices",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_last_auto_rebuild_on",
                    "label": "Last Auto Rebuild On",
                    "fieldtype": "Datetime",
                    "insert_after": "custom_source_buying_price_lists",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_last_auto_rebuild_status",
                    "label": "Last Auto Rebuild Status",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_last_auto_rebuild_on",
                    "read_only": 1,
                },
            ],
            "Item Price": [
                {
                    "fieldname": "custom_orderlift_builder_section",
                    "label": "Orderlift Builder",
                    "fieldtype": "Section Break",
                    "insert_after": "price_list_rate",
                    "collapsible": 1,
                    "collapsed": 1,
                },
                {
                    "fieldname": "custom_pricing_builder",
                    "label": "Pricing Builder",
                    "fieldtype": "Link",
                    "options": "Pricing Builder",
                    "insert_after": "custom_orderlift_builder_section",
                    "read_only": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_source_buying_price_list",
                    "label": "Source Buying Price List",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "custom_pricing_builder",
                    "read_only": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_pricing_scenario",
                    "label": "Expenses Policy",
                    "fieldtype": "Link",
                    "options": "Pricing Scenario",
                    "insert_after": "custom_source_buying_price_list",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_customs_policy",
                    "label": "Customs Policy",
                    "fieldtype": "Link",
                    "options": "Pricing Customs Policy",
                    "insert_after": "custom_pricing_scenario",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_benchmark_policy",
                    "label": "Margin & Benchmark Policy",
                    "fieldtype": "Link",
                    "options": "Pricing Benchmark Policy",
                    "insert_after": "custom_customs_policy",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_benchmark_is_fallback",
                    "label": "Benchmark Fallback",
                    "fieldtype": "Check",
                    "insert_after": "custom_benchmark_policy",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_benchmark_rule_label",
                    "label": "Benchmark Rule",
                    "fieldtype": "Data",
                    "insert_after": "custom_benchmark_is_fallback",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_benchmark_rule_max_discount_percent",
                    "label": "Rule Max Discount %",
                    "fieldtype": "Percent",
                    "insert_after": "custom_benchmark_rule_label",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_fallback_max_discount_percent",
                    "label": "Fallback Max Discount %",
                    "fieldtype": "Percent",
                    "insert_after": "custom_benchmark_rule_max_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_policy_max_discount_percent",
                    "label": "Policy Max Discount %",
                    "fieldtype": "Percent",
                    "insert_after": "custom_fallback_max_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_target_margin_percent",
                    "label": "Target Margin %",
                    "fieldtype": "Percent",
                    "insert_after": "custom_policy_max_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_final_margin_percent",
                    "label": "Builder Margin %",
                    "fieldtype": "Percent",
                    "insert_after": "custom_target_margin_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_last_builder_buy_rate",
                    "label": "Last Builder Buy Rate",
                    "fieldtype": "Currency",
                    "insert_after": "custom_final_margin_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_builder_price_overridden",
                    "label": "Builder Price Overridden",
                    "fieldtype": "Check",
                    "insert_after": "custom_last_builder_buy_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_last_builder_rebuild_on",
                    "label": "Last Builder Rebuild On",
                    "fieldtype": "Datetime",
                    "insert_after": "custom_builder_price_overridden",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_builder_expense_amount",
                    "label": "Builder Expense Amount",
                    "fieldtype": "Currency",
                    "insert_after": "custom_last_builder_rebuild_on",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_builder_customs_amount",
                    "label": "Builder Customs Amount",
                    "fieldtype": "Currency",
                    "insert_after": "custom_builder_expense_amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_builder_margin_basis",
                    "label": "Builder Margin Basis",
                    "fieldtype": "Data",
                    "insert_after": "custom_builder_customs_amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_is_shared_from",
                    "label": "Shared From",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "custom_last_builder_rebuild_on",
                    "read_only": 1,
                    "hidden": 1,
                    "description": "Source price list that this item price mirrors. Populated automatically for shared item prices.",
                },
            ],
            "Quotation": [
                {
                    "fieldname": "source_pricing_sheet",
                    "label": "Source Pricing Sheet",
                    "fieldtype": "Link",
                    "options": "Pricing Sheet",
                    "insert_after": "order_type",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "selected_selling_price_lists",
                    "label": "Selling Price Lists",
                    "fieldtype": "Table",
                    "options": "Pricing Sheet Price List Selection",
                    # Anchor before the standard selling_price_list so the table
                    # renders ABOVE the (locked) "Primary Selling Price List".
                    "insert_after": "column_break2",
                }
            ],
            "Sales Order": [
                {
                    "fieldname": "source_pricing_sheet",
                    "label": "Source Pricing Sheet",
                    "fieldtype": "Link",
                    "options": "Pricing Sheet",
                    "insert_after": "order_type",
                    "read_only": 1,
                    "in_standard_filter": 1,
                    "description": "Pricing source inherited from the submitted Quotation.",
                },
                {
                    "fieldname": "selected_selling_price_lists",
                    "label": "Selling Price Lists",
                    "fieldtype": "Table",
                    "options": "Pricing Sheet Price List Selection",
                    "insert_after": "source_pricing_sheet",
                    "read_only": 1,
                    "description": "Selling price lists inherited from the submitted Quotation.",
                },
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
                    "fieldname": "source_pricing_policy",
                    "label": "Source Pricing Policy",
                    "fieldtype": "Link",
                    "options": "Pricing Benchmark Policy",
                    "insert_after": "source_pricing_override",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_percent",
                    "label": "Source Margin Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_pricing_policy",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_basis",
                    "label": "Margin Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_scenario_rule",
                    "label": "Source Scenario Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_basis",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_rule",
                    "label": "Source Margin Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_scenario_rule",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_sales_person",
                    "label": "Source Sales Person",
                    "fieldtype": "Link",
                    "options": "Sales Person",
                    "insert_after": "source_margin_rule",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_geography",
                    "label": "Source Geography",
                    "fieldtype": "Data",
                    "insert_after": "source_sales_person",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_customs_applied",
                    "label": "Source Customs Applied",
                    "fieldtype": "Currency",
                    "insert_after": "source_geography",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_customs_basis",
                    "label": "Source Customs Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_customs_applied",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_selling_price_list",
                    "label": "Selling Price List Used",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "item_code",
                    "in_list_view": 1,
                    "description": "Allowed Selling Price List selected for this item row.",
                },
            ],
            "Sales Order Item": [
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
                    "fieldname": "source_pricing_policy",
                    "label": "Source Pricing Policy",
                    "fieldtype": "Link",
                    "options": "Pricing Benchmark Policy",
                    "insert_after": "source_pricing_override",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_percent",
                    "label": "Source Margin Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_pricing_policy",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_basis",
                    "label": "Margin Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_scenario_rule",
                    "label": "Source Scenario Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_basis",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_margin_rule",
                    "label": "Source Margin Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_scenario_rule",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_sales_person",
                    "label": "Source Sales Person",
                    "fieldtype": "Link",
                    "options": "Sales Person",
                    "insert_after": "source_margin_rule",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_geography",
                    "label": "Source Geography",
                    "fieldtype": "Data",
                    "insert_after": "source_sales_person",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_customs_applied",
                    "label": "Source Customs Applied",
                    "fieldtype": "Currency",
                    "insert_after": "source_geography",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_customs_basis",
                    "label": "Source Customs Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_customs_applied",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_selling_price_list",
                    "label": "Selling Price List Used",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "item_code",
                    "read_only": 1,
                    "in_list_view": 1,
                    "description": "Selling Price List inherited from the source Quotation item.",
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
            "Print Format": [
                {
                    "fieldname": "custom_company",
                    "label": "Company",
                    "fieldtype": "Link",
                    "options": "Company",
                    "insert_after": "module",
                    "description": "Restrict this print format to a specific company.",
                },
            ],
        },
        update=True,
    )
    _sync_existing_price_list_types()
    ensure_customer_pricing_tier_field_visibility()
    _upsert_property_setter(
        "Item",
        "customs_tariff_number",
        "label",
        "Customs Tariff Number (HS code)",
        "Data",
    )
    _upsert_property_setter("Item", "column_break0", "hidden", "1", "Check")
    _upsert_property_setter("Item", "over_delivery_receipt_allowance", "hidden", "1", "Check")
    _upsert_property_setter("Item", "over_billing_allowance", "hidden", "1", "Check")
    _delete_custom_field("Item-custom_item_metrics_column_break")

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Price List")
    frappe.clear_cache(doctype="Item Price")
    frappe.clear_cache(doctype="Customer")
    frappe.clear_cache(doctype="Prospect")
    frappe.clear_cache(doctype="Lead")
    frappe.clear_cache(doctype="Quotation")
    frappe.clear_cache(doctype="Quotation Item")
    frappe.clear_cache(doctype="Sales Order")
    frappe.clear_cache(doctype="Sales Order Item")
    frappe.clear_cache(doctype="Delivery Note Item")
    frappe.clear_cache(doctype="Sales Invoice Item")
    frappe.clear_cache(doctype="Purchase Order Item")
    frappe.clear_cache(doctype="Purchase Invoice Item")
    frappe.clear_cache(doctype="Purchase Receipt Item")
    frappe.clear_cache(doctype="Supplier Quotation Item")
    frappe.clear_cache(doctype="Print Format")
    frappe.clear_cache(doctype="Selling Settings")
    frappe.clear_cache(doctype="Role")
    ensure_quotation_discount_snapshot_fields()
    ensure_quotation_pricing_layout()
    ensure_sales_order_pricing_layout()
    ensure_all_ttc_item_layouts()
    ensure_print_format_company_field_visible()
    ensure_default_pricing_tiers()
    seed_default_role_capabilities()
    ensure_pricing_workspace()


def _sync_existing_price_list_types():
    if not frappe.db.exists("DocType", "Price List") or not frappe.db.has_column("Price List", PRICE_LIST_TYPE_FIELD):
        return

    rows = frappe.get_all(
        "Price List",
        fields=["name", PRICE_LIST_TYPE_FIELD, "buying", "selling"],
        limit_page_length=0,
    )
    for row in rows:
        explicit = (row.get(PRICE_LIST_TYPE_FIELD) or "").strip()
        if explicit in {BUYING_PRICE_LIST, SELLING_PRICE_LIST, BENCHMARK_PRICE_LIST}:
            target = explicit
        elif row.get("buying"):
            target = BUYING_PRICE_LIST
        elif row.get("selling"):
            target = SELLING_PRICE_LIST
        else:
            target = BENCHMARK_PRICE_LIST
        frappe.db.set_value(
            "Price List",
            row.get("name"),
            {
                PRICE_LIST_TYPE_FIELD: target,
                "buying": 1 if target == BUYING_PRICE_LIST else 0,
                "selling": 1 if target == SELLING_PRICE_LIST else 0,
            },
            update_modified=False,
        )


def ensure_customer_pricing_tier_field_visibility():
    _coerce_customer_tier_fields_to_links()
    tier_field = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": "tier"}, "name")
    if tier_field:
        frappe.db.set_value(
            "Custom Field",
            tier_field,
            {
                "label": "Pricing Tier",
                "fieldtype": "Link",
                "options": "Pricing Tier",
                "default": DEFAULT_MANUAL_TIER,
                "insert_after": "enable_dynamic_segmentation",
                "depends_on": "eval:!doc.enable_dynamic_segmentation",
                "mandatory_depends_on": "eval:!doc.enable_dynamic_segmentation",
                "hidden": 0,
                "read_only": 0,
            },
            update_modified=False,
        )

    manual_field = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": "manual_tier"}, "name")
    if manual_field:
        frappe.db.set_value(
            "Custom Field",
            manual_field,
            {
                "fieldtype": "Link",
                "options": "Pricing Tier",
                "default": DEFAULT_MANUAL_TIER,
                "insert_after": "tier",
                "depends_on": "",
                "hidden": 1,
            },
            update_modified=False,
        )

    for fieldname in ("tier_last_calculated_on", "tier_source"):
        field = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": fieldname}, "name")
        if field:
            frappe.db.set_value("Custom Field", field, {"hidden": 1, "read_only": 1}, update_modified=False)

    for fieldname in (
        "custom_partner_campaign_section",
        "custom_partner_segment",
        "custom_partner_campaign",
        "custom_partner_campaign_target",
    ):
        field = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": fieldname}, "name")
        if field:
            frappe.db.set_value("Custom Field", field, {"hidden": 1, "read_only": 1}, update_modified=False)

    _ensure_customer_field_order()
    frappe.clear_cache(doctype="Customer")


def _coerce_customer_tier_fields_to_links():
    for doctype in ("Customer", "Prospect", "Lead"):
        for fieldname in ("tier", "manual_tier"):
            field = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
            if field:
                frappe.db.set_value(
                    "Custom Field",
                    field,
                    {"fieldtype": "Link", "options": "Pricing Tier"},
                    update_modified=False,
                )


def ensure_item_material_records():
    if not frappe.db.exists("DocType", "Item Material"):
        return

    materials = {
        "ACIER": ["STEEL"],
        "ALUM": ["ALUMINIUM"],
        "BETON": ["CONCRETE", "BÉTON"],
        "CAOUTCHOUC": ["RUBBER"],
        "CARTE": ["PCB", "ELECTRONIC BOARD"],
        "COMPLET": ["COMPLETE", "ASCENSEUR COMPLET"],
        "CUIVRE": ["COPPER", "CUIVRE (CÂBLE)"],
        "GALVA": ["GALVANISED", "GALVANIZED"],
        "HUILE": ["OIL"],
        "INOX": ["STAINLESS STEEL"],
        "PLASTIQUE": ["PLASTIC", "PVC", "PLASTIQUE / PVC"],
        "VERRE": ["GLASS"],
        "OTHER": [],
        "STEEL": ["LEGACY ACIER"],
        "COPPER": ["LEGACY CUIVRE"],
    }
    for material, aliases in materials.items():
        _ensure_item_material(material, aliases)


def _ensure_item_material(material_name: str, aliases=None):
    material_name = (material_name or "").strip().upper()
    if not material_name or not frappe.db.exists("DocType", "Item Material"):
        return ""
    aliases = aliases or []
    existing = frappe.db.exists("Item Material", material_name)
    doc = frappe.get_doc("Item Material", existing) if existing else frappe.new_doc("Item Material")
    doc.material_name = material_name
    doc.material_code = material_name
    doc.aliases = ", ".join(sorted(set(alias for alias in aliases if alias)))
    doc.is_active = 1
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return doc.name


def _coerce_item_material_field_to_link():
    field = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": "custom_material"}, "name")
    if field:
        frappe.db.set_value(
            "Custom Field",
            field,
            {"fieldtype": "Link", "options": "Item Material"},
            update_modified=False,
        )


def _coerce_customs_material_field_to_link():
    field = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": "custom_customs_material"}, "name")
    if field:
        frappe.db.set_value(
            "Custom Field",
            field,
            {"fieldtype": "Link", "options": "Douane Material", "label": "Douane Material"},
            update_modified=False,
        )


def _ensure_customer_field_order():
    setter_name = frappe.db.get_value(
        "Property Setter",
        {"doc_type": "Customer", "doctype_or_field": "DocType", "property": "field_order"},
        "name",
    )
    if not setter_name:
        return

    value = frappe.db.get_value("Property Setter", setter_name, "value") or "[]"
    try:
        field_order = json.loads(value)
    except ValueError:
        return

    if not isinstance(field_order, list):
        return

    fields_after_dynamic_toggle = [
        "tier",
        "manual_tier",
        "tier_last_calculated_on",
        "tier_source",
        "custom_crm_classification_section",
        "custom_crm_segments",
        "custom_partner_campaign_section",
        "custom_partner_segment",
        "custom_partner_campaign",
        "custom_partner_campaign_target",
    ]
    fields_to_move = [fieldname for fieldname in fields_after_dynamic_toggle if fieldname in field_order]
    if not fields_to_move or "enable_dynamic_segmentation" not in field_order:
        return

    reordered = [fieldname for fieldname in field_order if fieldname not in fields_to_move]
    insert_at = reordered.index("enable_dynamic_segmentation") + 1
    reordered[insert_at:insert_at] = fields_to_move

    if reordered != field_order:
        frappe.db.set_value(
            "Property Setter",
            setter_name,
            "value",
            json.dumps(reordered),
            update_modified=False,
        )


def _prospect_tier_fields(insert_after: str) -> list[dict]:
    return [
        {
            "fieldname": "enable_dynamic_segmentation",
            "label": "Enable Dynamic Segmentation",
            "fieldtype": "Check",
            "default": "0",
            "insert_after": insert_after,
            "in_standard_filter": 1,
            "hidden": 1,
            "description": "If enabled, Tier is maintained by segmentation engines.",
        },
        {
            "fieldname": "tier",
            "label": "Tier",
            "fieldtype": "Link",
            "options": "Pricing Tier",
            "insert_after": "enable_dynamic_segmentation",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "read_only": 1,
            "hidden": 1,
        },
        {
            "fieldname": "manual_tier",
            "label": "Tier",
            "fieldtype": "Link",
            "options": "Pricing Tier",
            "default": DEFAULT_MANUAL_TIER,
            "insert_after": "tier",
            "in_standard_filter": 1,
            "in_list_view": 1,
            "description": "Manually selected from allowed segmentation tiers.",
        },
        {
            "fieldname": "tier_last_calculated_on",
            "label": "Tier Last Calculated On",
            "fieldtype": "Datetime",
            "insert_after": "manual_tier",
            "read_only": 1,
            "depends_on": "eval:doc.enable_dynamic_segmentation==1",
        },
        {
            "fieldname": "tier_source",
            "label": "Tier Source",
            "fieldtype": "Data",
            "insert_after": "tier_last_calculated_on",
            "read_only": 1,
        },
    ]


def ensure_quotation_discount_snapshot_fields():
    create_custom_fields(
        {
            "Pricing Sheet": [
                {
                    "fieldname": "custom_stock_snapshot_section",
                    "label": "Stock by Warehouse",
                    "fieldtype": "Section Break",
                    "insert_after": "lines",
                    "collapsible": 1,
                    "collapsed": 1,
                    "description": "Read-only stock by allowed warehouse for items in this Pricing Sheet company.",
                },
                {
                    "fieldname": "custom_warehouse_stock_snapshot",
                    "label": "Stock by Warehouse",
                    "fieldtype": "Table",
                    "options": "Orderlift Transaction Warehouse Stock",
                    "insert_after": "custom_stock_snapshot_section",
                    "read_only": 1,
                },
            ],
            "Pricing Sheet Item": [
                {
                    "fieldname": "custom_current_company_stock_qty",
                    "label": "Stock (Allowed Warehouses)",
                    "fieldtype": "Float",
                    "insert_after": "qty",
                    "read_only": 1,
                    "in_list_view": 1,
                    "description": "Current total stock in allowed warehouses for the document company.",
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "discounted_sell_total",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
            ],
            "Quotation": [
                {
                    "fieldname": "custom_stock_snapshot_section",
                    "label": "Stock by Warehouse",
                    "fieldtype": "Section Break",
                    "insert_after": "items",
                    "collapsible": 1,
                    "collapsed": 1,
                    "description": "Read-only stock by allowed warehouse for items in this Quotation company.",
                },
                {
                    "fieldname": "custom_warehouse_stock_snapshot",
                    "label": "Stock by Warehouse",
                    "fieldtype": "Table",
                    "options": "Orderlift Transaction Warehouse Stock",
                    "insert_after": "custom_stock_snapshot_section",
                    "read_only": 1,
                },
            ],
            "Quotation Item": [
                {
                    "fieldname": "custom_current_company_stock_qty",
                    "label": "Stock (Allowed Warehouses)",
                    "fieldtype": "Float",
                    "insert_after": "qty",
                    "read_only": 1,
                    "in_list_view": 1,
                    "description": "Current total stock in allowed warehouses for the document company.",
                },
                {
                    "fieldname": "source_price_list_sell_rate",
                    "label": "PU List HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_selling_price_list",
                    "read_only": 1,
                    "description": "Original unit price from the resolved selling price list.",
                },
                {
                    "fieldname": "source_gross_sell_rate",
                    "label": "PU HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_price_list_sell_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_percent",
                    "label": "Remise %",
                    "fieldtype": "Percent",
                    "insert_after": "source_gross_sell_rate",
                },
                {
                    "fieldname": "source_max_discount_percent",
                    "label": "Source Max Discount Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_amount",
                    "label": "Remise HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_max_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discounted_sell_rate",
                    "label": "PU HT net",
                    "fieldtype": "Currency",
                    "insert_after": "source_discount_amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_commission_rate",
                    "label": "Source Commission Rate",
                    "fieldtype": "Percent",
                    "insert_after": "source_discounted_sell_rate",
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_commission_amount",
                    "label": "Source Commission Amount",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC net",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC net",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Sales Order Item": [
                {
                    "fieldname": "source_price_list_sell_rate",
                    "label": "PU List HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_selling_price_list",
                    "read_only": 1,
                    "description": "Original unit price inherited from the source Quotation item.",
                },
                {
                    "fieldname": "source_gross_sell_rate",
                    "label": "PU HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_price_list_sell_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_percent",
                    "label": "Remise %",
                    "fieldtype": "Percent",
                    "insert_after": "source_gross_sell_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_max_discount_percent",
                    "label": "Source Max Discount Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_amount",
                    "label": "Remise HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_max_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discounted_sell_rate",
                    "label": "PU HT net",
                    "fieldtype": "Currency",
                    "insert_after": "source_discount_amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_commission_rate",
                    "label": "Source Commission Rate",
                    "fieldtype": "Percent",
                    "insert_after": "source_discounted_sell_rate",
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_commission_amount",
                    "label": "Source Commission Amount",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC net",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC net",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Delivery Note Item": [
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Sales Invoice Item": [
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Purchase Order Item": [
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Purchase Invoice Item": [
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Purchase Receipt Item": [
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
            "Supplier Quotation Item": [
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                },
            ],
        },
        update=True,
        ignore_validate=True,
    )


def ensure_quotation_pricing_layout():
    for fieldname in ("apply_discount_on", "additional_discount_percentage", "discount_amount"):
        _upsert_property_setter("Quotation", fieldname, "hidden", "1", "Check")
        _upsert_property_setter("Quotation", fieldname, "in_list_view", "0", "Check")
    if frappe.get_meta("Quotation").get_field("additional_info_section"):
        anchor = "source_pricing_sheet" if frappe.get_meta("Quotation").get_field("source_pricing_sheet") else "order_type"
        _upsert_property_setter("Quotation", "additional_info_section", "insert_after", anchor, "Data")
    if frappe.get_meta("Quotation").get_field("selling_price_list"):
        _upsert_property_setter("Quotation", "selling_price_list", "label", "Primary Selling Price List", "Data")
        # Primary is derived from the "Selling Price Lists" table (lowest active
        # sequence), so lock the field. The table renders above it (the table's
        # insert_after = column_break2 places it just before this standard field).
        _upsert_property_setter("Quotation", "selling_price_list", "read_only", "1", "Check")
    if frappe.get_meta("Quotation").get_field("source_pricing_sheet"):
        _upsert_property_setter("Quotation", "source_pricing_sheet", "read_only", "0", "Check")

    quotation_item_hidden_fields = [
        "price_list_rate",
        "rate",
        "discount_percentage",
        "discount_amount",
        "rate_with_margin",
        "margin_type",
        "margin_rate_or_amount",
        "source_pricing_sheet_line",
        "source_pricing_scenario",
        "source_pricing_override",
        "source_pricing_policy",
        "source_scenario_rule",
        "source_margin_rule",
        "source_sales_person",
        "source_geography",
        "source_customs_applied",
        "source_customs_basis",
        "source_margin_basis",
        "source_margin_percent",
    ]
    for fieldname in quotation_item_hidden_fields:
        if not frappe.get_meta("Quotation Item").get_field(fieldname):
            continue
        _upsert_property_setter("Quotation Item", fieldname, "hidden", "1", "Check")
        _upsert_property_setter("Quotation Item", fieldname, "in_list_view", "0", "Check")
        if fieldname in {"price_list_rate", "rate"}:
            _upsert_property_setter("Quotation Item", fieldname, "read_only", "1", "Check")

    quotation_item_visible_fields = [
        ("source_discount_percent", "Remise %"),
        ("source_selling_price_list", "Selling Price List Used"),
        ("source_price_list_sell_rate", "PU List HT"),
        ("source_gross_sell_rate", "PU HT"),
        ("source_max_discount_percent", "Max Discount %"),
        ("source_discount_amount", "Remise HT"),
        ("source_discounted_sell_rate", "PU HT net"),
        ("source_commission_rate", "Commission %"),
        ("source_commission_amount", "Commission Amount"),
        ("custom_applied_taxes", "Applied Taxes"),
        ("custom_pu_ttc", "PU TTC net"),
        ("custom_pt_ttc", "PT TTC net"),
    ]
    for fieldname, label in quotation_item_visible_fields:
        if not frappe.get_meta("Quotation Item").get_field(fieldname):
            continue
        _upsert_property_setter("Quotation Item", fieldname, "label", label, "Data")
        _upsert_property_setter("Quotation Item", fieldname, "hidden", "0", "Check")
        _upsert_property_setter("Quotation Item", fieldname, "in_list_view", "1", "Check")
    if frappe.get_meta("Quotation Item").get_field("source_discount_percent"):
        _upsert_property_setter("Quotation Item", "source_discount_percent", "read_only", "0", "Check")
    if frappe.get_meta("Quotation Item").get_field("source_gross_sell_rate"):
        _upsert_property_setter("Quotation Item", "source_gross_sell_rate", "read_only", "0", "Check")
    for fieldname in ("source_discount_amount", "custom_pu_ttc"):
        if frappe.get_meta("Quotation Item").get_field(fieldname):
            _upsert_property_setter("Quotation Item", fieldname, "read_only", "0", "Check")
    if frappe.get_meta("Quotation Item").get_field("source_discounted_sell_rate"):
        _upsert_property_setter("Quotation Item", "source_discounted_sell_rate", "read_only", "1", "Check")
    quotation_item_currency_precision_fields = (
        "source_price_list_sell_rate",
        "source_gross_sell_rate",
        "source_discount_amount",
        "source_discounted_sell_rate",
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
    )
    for fieldname in quotation_item_currency_precision_fields:
        if frappe.get_meta("Quotation Item").get_field(fieldname):
            _upsert_property_setter("Quotation Item", fieldname, "precision", "2", "Data")
    if frappe.get_meta("Quotation Item").get_field("amount"):
        _upsert_property_setter("Quotation Item", "amount", "label", "PT HT net", "Data")


def ensure_sales_order_pricing_layout():
    if frappe.get_meta("Sales Order").get_field("source_pricing_sheet"):
        _upsert_property_setter("Sales Order", "source_pricing_sheet", "read_only", "1", "Check")
    if frappe.get_meta("Sales Order").get_field("selected_selling_price_lists"):
        _upsert_property_setter("Sales Order", "selected_selling_price_lists", "read_only", "1", "Check")

    sales_order_item_hidden_fields = [
        "source_pricing_sheet_line",
        "source_pricing_scenario",
        "source_pricing_override",
        "source_pricing_policy",
        "source_scenario_rule",
        "source_margin_rule",
        "source_sales_person",
        "source_geography",
        "source_customs_applied",
        "source_customs_basis",
    ]
    for fieldname in sales_order_item_hidden_fields:
        if not frappe.get_meta("Sales Order Item").get_field(fieldname):
            continue
        _upsert_property_setter("Sales Order Item", fieldname, "hidden", "1", "Check")
        _upsert_property_setter("Sales Order Item", fieldname, "in_list_view", "0", "Check")

    sales_order_item_visible_fields = [
        ("source_selling_price_list", "Selling Price List Used"),
        ("source_price_list_sell_rate", "PU List HT"),
        ("source_gross_sell_rate", "PU HT"),
        ("source_discount_percent", "Remise %"),
        ("source_margin_basis", "Margin Basis"),
        ("source_margin_percent", "Margin %"),
        ("source_max_discount_percent", "Max Discount %"),
        ("source_discount_amount", "Remise HT"),
        ("source_discounted_sell_rate", "PU HT net"),
        ("source_commission_rate", "Commission %"),
        ("source_commission_amount", "Commission Amount"),
        ("custom_applied_taxes", "Applied Taxes"),
        ("custom_pu_ttc", "PU TTC net"),
        ("custom_pt_ttc", "PT TTC net"),
    ]
    for fieldname, label in sales_order_item_visible_fields:
        if not frappe.get_meta("Sales Order Item").get_field(fieldname):
            continue
        _upsert_property_setter("Sales Order Item", fieldname, "label", label, "Data")
        _upsert_property_setter("Sales Order Item", fieldname, "hidden", "0", "Check")
        _upsert_property_setter("Sales Order Item", fieldname, "in_list_view", "1", "Check")
        if fieldname not in {"custom_pu_ttc"}:
            _upsert_property_setter("Sales Order Item", fieldname, "read_only", "1", "Check")

    sales_order_item_currency_precision_fields = (
        "source_price_list_sell_rate",
        "source_gross_sell_rate",
        "source_discount_amount",
        "source_discounted_sell_rate",
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
    )
    for fieldname in sales_order_item_currency_precision_fields:
        if frappe.get_meta("Sales Order Item").get_field(fieldname):
            _upsert_property_setter("Sales Order Item", fieldname, "precision", "2", "Data")
    if frappe.get_meta("Sales Order Item").get_field("amount"):
        _upsert_property_setter("Sales Order Item", "amount", "label", "PT HT net", "Data")


_TTC_ITEM_DOCTYPES = [
    "Sales Order Item",
    "Delivery Note Item",
    "Sales Invoice Item",
    "Purchase Order Item",
    "Purchase Invoice Item",
    "Purchase Receipt Item",
    "Supplier Quotation Item",
]


def ensure_all_ttc_item_layouts():
    for item_doctype in _TTC_ITEM_DOCTYPES:
        _ensure_ttc_item_layout(item_doctype)
        frappe.clear_cache(doctype=item_doctype)


def _ensure_ttc_item_layout(item_doctype):
    ttc_fields = [
        ("custom_pu_ttc", "PU TTC"),
        ("custom_applied_taxes", "Applied Taxes"),
        ("custom_pt_ttc", "PT TTC"),
    ]
    for fieldname, label in ttc_fields:
        if not frappe.get_meta(item_doctype).get_field(fieldname):
            continue
        _upsert_property_setter(item_doctype, fieldname, "label", label, "Data")
        _upsert_property_setter(item_doctype, fieldname, "hidden", "0", "Check")
        _upsert_property_setter(item_doctype, fieldname, "in_list_view", "1", "Check")


def ensure_print_format_company_field_visible():
    if not frappe.get_meta("Print Format").get_field("custom_company"):
        return
    _upsert_property_setter("Print Format", "custom_company", "hidden", "0", "Check")
    _upsert_property_setter("Print Format", "custom_company", "in_list_view", "1", "Check")


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
        )

    shortcuts = [
        {"label": "Sheet Builder", "type": "Page", "link_to": "pricing-sheet-builder"},
        {"label": "Pricing Sheets", "type": "Page", "link_to": "pricing-sheet-manager"},
        {"label": "Quotation", "type": "DocType", "link_to": "Quotation"},
        {"label": "Pricing Tiers", "type": "DocType", "link_to": "Pricing Tier"},
        {"label": "Pricing Scenario", "type": "DocType", "link_to": "Pricing Scenario"},
        {"label": "Pricing Policies", "type": "DocType", "link_to": "Pricing Benchmark Policy"},
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


def ensure_default_pricing_tiers():
    if not frappe.db.exists("DocType", "Pricing Tier"):
        return

    tier_names = list(DEFAULT_PRICING_TIERS)
    for doctype, fieldname in (
        ("Pricing Tier Modifier", "tier"),
        ("Customer Segmentation Rule", "designated_segment"),
    ):
        if not frappe.db.exists("DocType", doctype):
            continue
        for value in frappe.get_all(doctype, pluck=fieldname, limit_page_length=0):
            tier_name = (value or "").strip()
            if tier_name and tier_name not in tier_names:
                tier_names.append(tier_name)

    for sequence, tier_name in enumerate(tier_names, start=1):
        if frappe.db.exists("Pricing Tier", tier_name):
            doc = frappe.get_doc("Pricing Tier", tier_name)
        else:
            doc = frappe.new_doc("Pricing Tier")
            doc.tier_name = tier_name
        doc.sequence = sequence * 10
        if tier_name == DEFAULT_MANUAL_TIER:
            doc.sequence = 1
        doc.is_active = 1 if doc.get("is_active") is None else doc.is_active
        if tier_name == DEFAULT_MANUAL_TIER:
            doc.is_active = 1
        doc.save(ignore_permissions=True)


def _upsert_property_setter(doctype: str, fieldname: str, property_name: str, value, property_type: str):
    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "field_name": fieldname, "property": property_name},
        "name",
    )
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocField"
    setter.field_name = fieldname
    setter.property = property_name
    setter.property_type = property_type
    setter.value = value
    if existing:
        setter.save(ignore_permissions=True)
    else:
        setter.insert(ignore_permissions=True)


def _delete_custom_field(name: str):
    if frappe.db.exists("Custom Field", name):
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
