import json
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from orderlift.role_capabilities import ROLE_CAPABILITY_FIELD, migrate_legacy_pipeline_assignment_capabilities
from orderlift.startup_roles import ORDERLIFT_BUSINESS_GRANTS_FIELD, ORDERLIFT_MANAGED_ROLE_FIELD
from orderlift.orderlift_sales.utils.price_list_scope import (
    BENCHMARK_PRICE_LIST,
    BUYING_PRICE_LIST,
    PRICE_LIST_TYPE_FIELD,
    SELLING_PRICE_LIST,
)


DEFAULT_MANUAL_TIER = "New"
DEFAULT_PRICING_TIERS = [DEFAULT_MANUAL_TIER, "Eco", "Intermediaire", "Luxe", "Gold", "Silver", "Bronze"]


def _commercial_presentation_header_fields(read_only=False, insert_after="items"):
    return [
        {
            "fieldname": "custom_presentation_mode",
            "label": "Presentation",
            "fieldtype": "Select",
            "options": "With details\nWithout details",
            "default": "With details",
            "insert_after": insert_after,
            "read_only": 1 if read_only else 0,
        },
        {
            "fieldname": "custom_commercial_designation",
            "label": "Commercial Designation",
            "fieldtype": "Small Text",
            "insert_after": "custom_presentation_mode",
            "read_only": 1 if read_only else 0,
        },
        {
            "fieldname": "custom_commercial_total",
            "label": "Commercial Summary Total",
            "fieldtype": "Currency",
            "insert_after": "custom_commercial_designation",
            "read_only": 1,
        },
        {
            "fieldname": "custom_dimensioning_set",
            "label": "Dimensioning Set",
            "fieldtype": "Link",
            "options": "Dimensioning Set",
            "insert_after": "custom_commercial_total",
            "read_only": 1 if read_only else 0,
        },
        {
            "fieldname": "custom_dimensioning_multiplier",
            "label": "Number of Sets",
            "fieldtype": "Int",
            "default": "1",
            "insert_after": "custom_dimensioning_set",
            "read_only": 1 if read_only else 0,
            "non_negative": 1,
        },
        {
            "fieldname": "custom_dimensioning_inputs_json",
            "label": "Dimensioning Inputs JSON",
            "fieldtype": "Code",
            "options": "JSON",
            "insert_after": "custom_dimensioning_multiplier",
            "read_only": 1 if read_only else 0,
            "hidden": 1,
        },
    ]


def _commercial_presentation_item_fields(insert_after="description"):
    return [
        {
            "fieldname": "custom_presentation_role",
            "label": "Presentation Role",
            "fieldtype": "Select",
            "options": "Include in commercial summary\nPrint separately",
            "default": "Include in commercial summary",
            "insert_after": insert_after,
            "read_only": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "custom_dimensioning_set",
            "label": "Dimensioning Set",
            "fieldtype": "Link",
            "options": "Dimensioning Set",
            "insert_after": "custom_presentation_role",
            "read_only": 1,
            "hidden": 1,
        },
        {
            "fieldname": "custom_dimensioning_rule_label",
            "label": "Dimensioning Rule",
            "fieldtype": "Data",
            "insert_after": "custom_dimensioning_set",
            "read_only": 1,
            "hidden": 1,
        },
        {
            "fieldname": "custom_orderlift_other_charge",
            "label": "Orderlift Other Charge",
            "fieldtype": "Check",
            "insert_after": "custom_dimensioning_rule_label",
            "read_only": 1,
            "hidden": 1,
            "print_hide": 1,
        },
    ]


def _normalize_dimensioning_rule_metadata():
    if not frappe.db.exists("DocType", "Dimensioning Set Item Rule"):
        return
    meta = frappe.get_meta("Dimensioning Set Item Rule")
    if not meta.has_field("rule_group_title"):
        return
    rows = frappe.get_all(
        "Dimensioning Set Item Rule",
        filters={"parenttype": "Dimensioning Set", "parentfield": "item_rules"},
        fields=[
            "name",
            "parent",
            "rule_group",
            "rule_group_title",
            "rule_label",
            "display_group",
            "condition_mode",
            "condition_formula",
            "condition_rules_json",
            "quantity_mode",
            "qty_formula",
        ],
        order_by="parent, idx",
        limit_page_length=0,
    )
    titles = {}
    for row in rows:
        key = (row.parent, (row.rule_group or row.name).strip())
        label = (row.rule_label or "").strip()
        display_group = (row.display_group or "").strip()
        title = (row.rule_group_title or "").strip()
        if not title and label and not label.lower().startswith("new "):
            title = label
        if not title and display_group and display_group.lower() not in {"ungrouped", "workbook", "dimensionnement"}:
            title = display_group
        if not title:
            title = f"Rule {(row.rule_group or row.name).strip()}"
        titles.setdefault(key, title)
    for row in rows:
        key = (row.parent, (row.rule_group or row.name).strip())
        updates = {}
        if (row.rule_group_title or "").strip() != titles[key]:
            updates["rule_group_title"] = titles[key]
        if (row.condition_formula or "").strip() and not (row.condition_rules_json or "").strip() and row.condition_mode != "formula":
            updates["condition_mode"] = "formula"
        if (row.qty_formula or "").strip() and row.quantity_mode != "formula":
            updates["quantity_mode"] = "formula"
        if updates:
            frappe.db.set_value("Dimensioning Set Item Rule", row.name, updates, update_modified=False)


def _mark_existing_access_command_center_roles():
    if not frappe.get_meta("Role").get_field(ORDERLIFT_MANAGED_ROLE_FIELD):
        return
    if not frappe.db.exists("DocType", "Comment"):
        return

    role_names = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Role",
            "comment_type": "Info",
            "content": ["like", "%Access Command Center role creation%"],
        },
        pluck="reference_name",
        limit_page_length=0,
    )
    for role_name in set(role_names):
        role = frappe.db.get_value(
            "Role",
            role_name,
            ["is_custom", ORDERLIFT_MANAGED_ROLE_FIELD],
            as_dict=True,
        )
        if role and role.is_custom and not role.get(ORDERLIFT_MANAGED_ROLE_FIELD):
            frappe.db.set_value("Role", role_name, ORDERLIFT_MANAGED_ROLE_FIELD, 1, update_modified=False)


def after_migrate():
    _coerce_customer_tier_fields_to_links()
    _coerce_item_material_field_to_link()
    _coerce_customs_material_field_to_link()
    _fix_stale_pricing_margin_policy_fields()
    _normalize_dimensioning_rule_metadata()
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
                {
                    "fieldname": "custom_default_purchase_taxes_template",
                    "label": "Default Purchase Tax Template",
                    "fieldtype": "Link",
                    "options": "Purchase Taxes and Charges Template",
                    "insert_after": "custom_default_sales_taxes_template",
                    "description": "Default purchase tax template used by Orderlift purchase orders.",
                },
            ],
            "Role": [
                {
                    "fieldname": ORDERLIFT_BUSINESS_GRANTS_FIELD,
                    "label": "Orderlift Business Grants",
                    "fieldtype": "Long Text",
                    "insert_after": ORDERLIFT_MANAGED_ROLE_FIELD,
                    "hidden": 1,
                    "description": "Internal source of truth for Access Command Center business feature grants.",
                },
                {
                    "fieldname": ORDERLIFT_MANAGED_ROLE_FIELD,
                    "label": "Orderlift Managed Role",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "desk_access",
                    "hidden": 1,
                    "description": "Marks custom business roles managed through Access Command Center.",
                },
                {
                    "fieldname": ROLE_CAPABILITY_FIELD,
                    "label": "Orderlift Capabilities",
                    "fieldtype": "Small Text",
                    "insert_after": ORDERLIFT_MANAGED_ROLE_FIELD,
                    "hidden": 1,
                    "description": "Internal storage for the Orderlift capability picker.",
                },
                {
                    "fieldname": "custom_orderlift_capabilities_picker",
                    "label": "Orderlift Capabilities",
                    "fieldtype": "HTML",
                    "insert_after": ROLE_CAPABILITY_FIELD,
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
            "Sales Person": [
                {
                    "fieldname": "user",
                    "label": "User",
                    "fieldtype": "Link",
                    "options": "User",
                    "insert_after": "enabled",
                    "in_standard_filter": 1,
                    "description": "Orderlift user mapped to this Sales Person for pricing, access, and commission ownership.",
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
            "Opportunity": [
                {
                    "fieldname": "custom_sales_team_section",
                    "label": "Sales Team",
                    "fieldtype": "Section Break",
                    "insert_after": "opportunity_owner",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_sales_team",
                    "label": "Sales Team",
                    "fieldtype": "Table",
                    "options": "Orderlift Sales Team Member",
                    "insert_after": "custom_sales_team_section",
                },
                {
                    "fieldname": "custom_dimensioning_set",
                    "label": "Dimensioning Set",
                    "fieldtype": "Link",
                    "options": "Dimensioning Set",
                    "insert_after": "custom_sales_team",
                },
                {
                    "fieldname": "custom_dimensioning_multiplier",
                    "label": "Number of Sets",
                    "fieldtype": "Int",
                    "default": "1",
                    "insert_after": "custom_dimensioning_set",
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_dimensioning_inputs_json",
                    "label": "Dimensioning Inputs JSON",
                    "fieldtype": "Code",
                    "options": "JSON",
                    "insert_after": "custom_dimensioning_multiplier",
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_dimensioning_tool",
                    "label": "Dimensioning Tool",
                    "fieldtype": "HTML",
                    "insert_after": "custom_dimensioning_inputs_json",
                },
            ],
            "Opportunity Item": [
                {
                    "fieldname": "custom_presentation_role",
                    "label": "Presentation Role",
                    "fieldtype": "Select",
                    "options": "Include in commercial summary\nPrint separately",
                    "default": "Include in commercial summary",
                    "insert_after": "description",
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_dimensioning_set",
                    "label": "Dimensioning Set",
                    "fieldtype": "Link",
                    "options": "Dimensioning Set",
                    "insert_after": "custom_presentation_role",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_dimensioning_rule_label",
                    "label": "Dimensioning Rule",
                    "fieldtype": "Data",
                    "insert_after": "custom_dimensioning_set",
                    "read_only": 1,
                    "hidden": 1,
                },
            ],
            "Quotation": [
                {
                    "fieldname": "custom_sales_team_section",
                    "label": "Sales Team",
                    "fieldtype": "Section Break",
                    "insert_after": "commission_sales_person",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_sales_team",
                    "label": "Sales Team",
                    "fieldtype": "Table",
                    "options": "Orderlift Sales Team Member",
                    "insert_after": "custom_sales_team_section",
                },
                {
                    "fieldname": "custom_delivery_lead_time",
                    "label": "Delivery Lead Time",
                    "fieldtype": "Data",
                    "insert_after": "valid_till",
                    "description": "Commercial delivery commitment, for example: 4–6 weeks after confirmation.",
                },
                {
                    "fieldname": "custom_customer_tax_id",
                    "label": "ICE / Tax ID",
                    "fieldtype": "Data",
                    "insert_after": "customer_name",
                    "read_only": 1,
                    "print_hide": 1,
                    "description": "Customer ICE / Tax ID snapshot used on this Quotation and its print formats.",
                },
                {
                    "fieldname": "source_pricing_sheet",
                    "label": "Source Pricing Sheet",
                    "fieldtype": "Link",
                    "options": "Pricing Sheet",
                    "insert_after": "order_type",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_opportunity_title",
                    "label": "Opportunity Title",
                    "fieldtype": "Data",
                    "insert_after": "opportunity",
                    "read_only": 1,
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_opportunity_owner",
                    "label": "Opportunity Owner",
                    "fieldtype": "Link",
                    "options": "User",
                    "insert_after": "custom_opportunity_title",
                    "read_only": 1,
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "commission_sales_person",
                    "label": "Commission Salesperson",
                    "fieldtype": "Link",
                    "options": "Sales Person",
                    "insert_after": "source_pricing_sheet",
                    "in_standard_filter": 1,
                    "print_hide": 1,
                    "description": "Automatically assigned and locked for sales users. Managers may choose any enabled Sales Person or leave it blank for no commission.",
                },
                {
                    "fieldname": "selected_selling_price_lists",
                    "label": "Selling Price Lists",
                    "fieldtype": "Table",
                    "options": "Pricing Sheet Price List Selection",
                    # Anchor before the standard selling_price_list so the table
                    # renders ABOVE the (locked) "Primary Selling Price List".
                    "insert_after": "column_break2",
                },
                {
                    "fieldname": "custom_other_charges",
                    "label": "Other Charges",
                    "fieldtype": "Table",
                    "options": "Orderlift Quotation Other Charge",
                    "insert_after": "items",
                    "description": "Managed quotation charges that print separately and sync into hidden accounting item rows.",
                },
                {
                    "fieldname": "custom_presentation_mode",
                    "label": "Presentation",
                    "fieldtype": "Select",
                    "options": "With details\nWithout details",
                    "default": "With details",
                    "insert_after": "source_pricing_sheet",
                },
                {
                    "fieldname": "custom_commercial_designation",
                    "label": "Commercial Designation",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_presentation_mode",
                    "depends_on": "eval:doc.custom_presentation_mode=='Without details'",
                    "description": "Legacy fallback. New without-details quotations use Commercial Presentation Template instead.",
                },
                {
                    "fieldname": "custom_commercial_total",
                    "label": "Commercial Summary Total",
                    "fieldtype": "Currency",
                    "insert_after": "custom_commercial_designation",
                    "read_only": 1,
                    "depends_on": "eval:doc.custom_presentation_mode=='Without details'",
                },
                {
                    "fieldname": "custom_dimensioning_set",
                    "label": "Dimensioning Set",
                    "fieldtype": "Link",
                    "options": "Dimensioning Set",
                    "insert_after": "custom_commercial_total",
                },
                {
                    "fieldname": "custom_dimensioning_multiplier",
                    "label": "Number of Sets",
                    "fieldtype": "Int",
                    "default": "1",
                    "insert_after": "custom_dimensioning_set",
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_dimensioning_inputs_json",
                    "label": "Dimensioning Inputs JSON",
                    "fieldtype": "Code",
                    "options": "JSON",
                    "insert_after": "custom_dimensioning_multiplier",
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_dimensioning_tool",
                    "label": "Dimensioning Tool",
                    "fieldtype": "HTML",
                    "insert_after": "custom_dimensioning_inputs_json",
                },
                {
                    "fieldname": "custom_commercial_presentation_template",
                    "label": "Commercial Presentation Template",
                    "fieldtype": "Link",
                    "options": "Orderlift Quotation Detail Template",
                    "insert_after": "custom_dimensioning_tool",
                    "print_hide": 1,
                    "description": "Manual template selected for the dynamic quotation detail pages.",
                },
                {
                    "fieldname": "custom_commercial_presentation_editor",
                    "label": "Commercial Presentation Editor",
                    "fieldtype": "HTML",
                    "insert_after": "custom_commercial_presentation_template",
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_commercial_presentation_snapshot",
                    "label": "Commercial Presentation Snapshot",
                    "fieldtype": "Long Text",
                    "insert_after": "custom_commercial_presentation_editor",
                    "hidden": 1,
                    "print_hide": 1,
                    "description": "Frozen JSON rendered in submitted quotation PDFs.",
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_sales_team_section",
                    "label": "Sales Team",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_opportunity_owner",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_sales_team",
                    "label": "Sales Team",
                    "fieldtype": "Table",
                    "options": "Orderlift Sales Team Member",
                    "insert_after": "custom_sales_team_section",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_delivery_lead_time",
                    "label": "Delivery Lead Time",
                    "fieldtype": "Data",
                    "insert_after": "delivery_date",
                    "description": "Commercial delivery commitment inherited from the Quotation or entered on a direct Sales Order.",
                },
                {
                    "fieldname": "custom_opportunity_title",
                    "label": "Opportunity Title",
                    "fieldtype": "Data",
                    "insert_after": "custom_delivery_lead_time",
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_opportunity_owner",
                    "label": "Opportunity Owner",
                    "fieldtype": "Link",
                    "options": "User",
                    "insert_after": "custom_opportunity_title",
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
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
                {
                    "fieldname": "custom_presentation_mode",
                    "label": "Presentation",
                    "fieldtype": "Select",
                    "options": "With details\nWithout details",
                    "default": "With details",
                    "insert_after": "selected_selling_price_lists",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_commercial_designation",
                    "label": "Commercial Designation",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_presentation_mode",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_commercial_total",
                    "label": "Commercial Summary Total",
                    "fieldtype": "Currency",
                    "insert_after": "custom_commercial_designation",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_dimensioning_set",
                    "label": "Dimensioning Set",
                    "fieldtype": "Link",
                    "options": "Dimensioning Set",
                    "insert_after": "custom_commercial_total",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_dimensioning_multiplier",
                    "label": "Number of Sets",
                    "fieldtype": "Int",
                    "default": "1",
                    "insert_after": "custom_dimensioning_set",
                    "read_only": 1,
                    "non_negative": 1,
                },
                {
                    "fieldname": "custom_dimensioning_inputs_json",
                    "label": "Dimensioning Inputs JSON",
                    "fieldtype": "Code",
                    "options": "JSON",
                    "insert_after": "custom_dimensioning_multiplier",
                    "read_only": 1,
                    "hidden": 1,
                },
            ],
            "Quotation Item": [
                {
                    "fieldname": "custom_presentation_role",
                    "label": "Presentation Role",
                    "fieldtype": "Select",
                    "options": "Include in commercial summary\nPrint separately",
                    "default": "Include in commercial summary",
                    "insert_after": "description",
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_dimensioning_set",
                    "label": "Dimensioning Set",
                    "fieldtype": "Link",
                    "options": "Dimensioning Set",
                    "insert_after": "custom_presentation_role",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_dimensioning_rule_label",
                    "label": "Dimensioning Rule",
                    "fieldtype": "Data",
                    "insert_after": "custom_dimensioning_set",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_orderlift_other_charge",
                    "label": "Orderlift Other Charge",
                    "fieldtype": "Check",
                    "insert_after": "custom_dimensioning_rule_label",
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
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
                    "fieldname": "source_target_margin_percent",
                    "label": "Target Policy Margin %",
                    "fieldtype": "Percent",
                    "insert_after": "source_pricing_policy",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_margin_percent",
                    "label": "Actual Margin %",
                    "fieldtype": "Percent",
                    "insert_after": "source_target_margin_percent",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_margin_basis",
                    "label": "Margin Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_percent",
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_base_buy_rate",
                    "label": "Base Buy Rate",
                    "fieldtype": "Currency",
                    "insert_after": "source_margin_basis",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_landed_cost",
                    "label": "Loaded Cost",
                    "fieldtype": "Currency",
                    "insert_after": "source_base_buy_rate",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_scenario_rule",
                    "label": "Source Scenario Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_landed_cost",
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
                    "print_hide": 1,
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
                    "precision": 9,
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
                    "fieldname": "custom_presentation_role",
                    "label": "Presentation Role",
                    "fieldtype": "Select",
                    "options": "Include in commercial summary\nPrint separately",
                    "default": "Include in commercial summary",
                    "insert_after": "description",
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_dimensioning_set",
                    "label": "Dimensioning Set",
                    "fieldtype": "Link",
                    "options": "Dimensioning Set",
                    "insert_after": "custom_presentation_role",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_dimensioning_rule_label",
                    "label": "Dimensioning Rule",
                    "fieldtype": "Data",
                    "insert_after": "custom_dimensioning_set",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_orderlift_other_charge",
                    "label": "Orderlift Other Charge",
                    "fieldtype": "Check",
                    "insert_after": "custom_dimensioning_rule_label",
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
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
                    "fieldname": "source_target_margin_percent",
                    "label": "Target Policy Margin %",
                    "fieldtype": "Percent",
                    "insert_after": "source_pricing_policy",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_margin_percent",
                    "label": "Actual Margin %",
                    "fieldtype": "Percent",
                    "insert_after": "source_target_margin_percent",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_margin_basis",
                    "label": "Margin Basis",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_percent",
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_base_buy_rate",
                    "label": "Base Buy Rate",
                    "fieldtype": "Currency",
                    "insert_after": "source_margin_basis",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_landed_cost",
                    "label": "Loaded Cost",
                    "fieldtype": "Currency",
                    "insert_after": "source_base_buy_rate",
                    "precision": 9,
                    "read_only": 1,
                    "permlevel": 2,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_scenario_rule",
                    "label": "Source Scenario Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_landed_cost",
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
                    "print_hide": 1,
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
                    "precision": 9,
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
            "Delivery Note": _commercial_presentation_header_fields(read_only=True, insert_after="items"),
            "Sales Invoice": [
                {
                    "fieldname": "custom_invoice_mode",
                    "label": "Invoice Mode",
                    "fieldtype": "Select",
                    "options": "\nItems\nAdvance\nCustom",
                    "insert_after": "customer",
                    "read_only": 1,
                    "hidden": 1,
                    "description": "Orderlift invoice builder mode selected on the Sales Invoice form.",
                },
                {
                    "fieldname": "custom_advance_payment_entry",
                    "label": "Advance Payment Entry",
                    "fieldtype": "Link",
                    "options": "Payment Entry",
                    "insert_after": "custom_invoice_mode",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_advance_sales_order",
                    "label": "Advance Sales Order",
                    "fieldtype": "Link",
                    "options": "Sales Order",
                    "insert_after": "custom_advance_payment_entry",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_advance_payment_schedule_row",
                    "label": "Advance Payment Schedule Row",
                    "fieldtype": "Data",
                    "insert_after": "custom_advance_sales_order",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "selected_selling_price_lists",
                    "label": "Selling Price Lists",
                    "fieldtype": "Table",
                    "options": "Pricing Sheet Price List Selection",
                    "insert_after": "items",
                    "read_only": 1,
                    "description": "Selling price lists inherited from linked Sales Orders.",
                },
                *_commercial_presentation_header_fields(read_only=True, insert_after="selected_selling_price_lists"),
            ],
            "Delivery Note Item": _commercial_presentation_item_fields(insert_after="description"),
            "Sales Invoice Item": _commercial_presentation_item_fields(insert_after="description"),
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
    _mark_existing_access_command_center_roles()
    migrate_legacy_pipeline_assignment_capabilities()
    from orderlift.orderlift.page.access_command_center.access_command_center import (
        ensure_managed_role_baselines,
        sync_business_import_support_permissions,
    )

    ensure_managed_role_baselines()
    sync_business_import_support_permissions()
    _sync_existing_price_list_types()
    ensure_customer_pricing_tier_field_visibility()
    ensure_tax_id_labels()
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
    _remove_opportunity_commercial_presentation_header_fields()
    _upsert_property_setter("Opportunity", "custom_dimensioning_multiplier", "hidden", "0", "Check")
    _delete_custom_field("Item-custom_item_metrics_column_break")

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Price List")
    frappe.clear_cache(doctype="Item Price")
    frappe.clear_cache(doctype="Customer")
    frappe.clear_cache(doctype="Prospect")
    frappe.clear_cache(doctype="Lead")
    frappe.clear_cache(doctype="Opportunity")
    frappe.clear_cache(doctype="Opportunity Item")
    frappe.clear_cache(doctype="Quotation")
    frappe.clear_cache(doctype="Quotation Item")
    frappe.clear_cache(doctype="Sales Order")
    frappe.clear_cache(doctype="Sales Order Item")
    frappe.clear_cache(doctype="Delivery Note")
    frappe.clear_cache(doctype="Delivery Note Item")
    frappe.clear_cache(doctype="Sales Invoice")
    frappe.clear_cache(doctype="Sales Invoice Item")
    frappe.clear_cache(doctype="Purchase Order")
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
    ensure_sales_invoice_pricing_layout()
    ensure_sales_invoice_mode_fields()
    ensure_purchase_order_pricing_layout()
    ensure_commission_field_cleanup()
    ensure_margin_snapshot_permissions()
    ensure_all_ttc_item_layouts()
    ensure_canonical_pricing_precision()
    ensure_print_format_company_field_visible()
    ensure_default_pricing_tiers()
    ensure_default_other_charges()
    ensure_pricing_workspace()
    backfill_quotation_opportunity_snapshots()
    backfill_sales_team_rows()
    ensure_buying_price_review_page_roles()


def ensure_tax_id_labels():
    """Use one Morocco-friendly label for the standard ERPNext tax fields."""
    tax_id_fields = (
        ("Company", "tax_id"),
        ("Customer", "tax_id"),
        ("Supplier", "tax_id"),
        ("Sales Order", "tax_id"),
        ("Delivery Note", "tax_id"),
    )
    for doctype, fieldname in tax_id_fields:
        if not frappe.get_meta(doctype).get_field(fieldname):
            continue
        _upsert_property_setter(doctype, fieldname, "label", "ICE / Tax ID", "Data")
        frappe.clear_cache(doctype=doctype)
    sales_invoice_labels = (
        ("tax_id", "Customer ICE / Tax ID"),
        ("company_tax_id", "Company ICE / Tax ID"),
    )
    for fieldname, label in sales_invoice_labels:
        if not frappe.get_meta("Sales Invoice").get_field(fieldname):
            continue
        _upsert_property_setter("Sales Invoice", fieldname, "label", label, "Data")
    frappe.clear_cache(doctype="Sales Invoice")


def backfill_quotation_opportunity_snapshots():
    required_columns = ["opportunity", "custom_opportunity_title", "custom_opportunity_owner"]
    if not all(frappe.db.has_column("Quotation", fieldname) for fieldname in required_columns):
        return
    if not frappe.db.has_column("Opportunity", "opportunity_owner"):
        return
    frappe.db.sql(
        """
        update `tabQuotation` q
        inner join `tabOpportunity` o on o.name = q.opportunity
        set
            q.custom_opportunity_title = coalesce(o.title, ''),
            q.custom_opportunity_owner = coalesce(nullif(o.opportunity_owner, ''), o.owner, '')
        where coalesce(q.opportunity, '') != ''
        """
    )
    frappe.db.sql(
        """
        update `tabQuotation`
        set custom_opportunity_title = '', custom_opportunity_owner = ''
        where coalesce(opportunity, '') = ''
        """
    )


def backfill_sales_team_rows():
    """Backfill new team snapshots without changing submitted commercial history."""
    if not frappe.db.exists("DocType", "Orderlift Sales Team Member"):
        return

    from orderlift.orderlift_sales.utils.sales_team import (
        TEAM_DOCTYPE,
        TEAM_FIELD,
        _linked_team,
        commission_enabled,
        sales_person_for_user,
    )

    def add_rows(doctype, name, rows):
        if not rows or frappe.db.exists(
            TEAM_DOCTYPE,
            {"parent": name, "parenttype": doctype, "parentfield": TEAM_FIELD},
        ):
            return
        for index, row in enumerate(rows, start=1):
            salesperson = (row.get("sales_person") or "").strip()
            if not salesperson or not commission_enabled(salesperson):
                continue
            child = frappe.new_doc(TEAM_DOCTYPE)
            child.parent = name
            child.parenttype = doctype
            child.parentfield = TEAM_FIELD
            child.idx = index
            child.sales_person = salesperson
            child.allocated_percentage = row.get("allocated_percentage") or 100
            child.is_primary = row.get("is_primary") or (1 if index == 1 else 0)
            child.insert(ignore_permissions=True)

    opportunities = frappe.get_all(
        "Opportunity",
        fields=["name", "opportunity_owner", "owner"],
        limit_page_length=0,
    )
    for row in opportunities:
        salesperson = sales_person_for_user(row.opportunity_owner or row.owner)
        if salesperson and commission_enabled(salesperson):
            add_rows("Opportunity", row.name, [{"sales_person": salesperson, "allocated_percentage": 100, "is_primary": 1}])

    quotations = frappe.get_all(
        "Quotation",
        filters={},
        fields=["name", "opportunity", "source_pricing_sheet", "commission_sales_person"],
        limit_page_length=0,
    )
    for row in quotations:
        team = _linked_team("Pricing Sheet", row.source_pricing_sheet)
        team = team or _linked_team("Opportunity", row.opportunity)
        if not team and row.commission_sales_person:
            team = [{"sales_person": row.commission_sales_person, "allocated_percentage": 100, "is_primary": 1}]
        add_rows("Quotation", row.name, team)

    sales_orders = frappe.get_all(
        "Sales Order",
        filters={"docstatus": 0},
        fields=["name"],
        limit_page_length=0,
    )
    for row in sales_orders:
        quotation = frappe.db.get_value(
            "Sales Order Item",
            {"parent": row.name, "prevdoc_docname": ["!=", ""]},
            "prevdoc_docname",
        )
        team = _linked_team("Quotation", quotation)
        add_rows("Sales Order", row.name, team)


def ensure_buying_price_review_page_roles():
    page_name = "buying-price-review"
    if not frappe.db.exists("Page", page_name):
        return
    wanted = ("Orderlift Admin", "System Manager", "Purchase Manager")
    page = frappe.get_doc("Page", page_name)
    current = {row.role for row in page.get("roles") or [] if row.get("role")}
    if set(wanted).issubset(current):
        return
    page.set("roles", [])
    for role in wanted:
        page.append("roles", {"role": role})
    page.save(ignore_permissions=True)


def _fix_stale_pricing_margin_policy_fields():
    for doctype in ("Quotation Item", "Sales Order Item"):
        field = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": "source_margin_policy"}, "name")
        if field:
            frappe.db.set_value("Custom Field", field, "options", "Pricing Benchmark Policy", update_modified=False)


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
            "Sales Commission": [
                {
                    "fieldname": "custom_contribution_percent",
                    "label": "Team Contribution %",
                    "fieldtype": "Percent",
                    "insert_after": "commission_rate",
                    "read_only": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_primary_commission_rate",
                    "label": "Primary Commission Rate",
                    "fieldtype": "Percent",
                    "insert_after": "custom_contribution_percent",
                    "read_only": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_sales_team_snapshot",
                    "label": "Sales Team Snapshot",
                    "fieldtype": "Long Text",
                    "insert_after": "notes",
                    "read_only": 1,
                    "hidden": 1,
                },
            ],
            "Pricing Sheet": [
                {
                    "fieldname": "custom_opportunity_owner",
                    "label": "Opportunity Owner",
                    "fieldtype": "Link",
                    "options": "User",
                    "insert_after": "sales_person",
                    "read_only": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_sales_team_section",
                    "label": "Sales Team",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_opportunity_owner",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_sales_team",
                    "label": "Sales Team",
                    "fieldtype": "Table",
                    "options": "Orderlift Sales Team Member",
                    "insert_after": "custom_sales_team_section",
                },
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
                    "insert_after": "sell_total",
                    "read_only": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "read_only": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "read_only": 1,
                    "precision": 9,
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
                    "precision": 9,
                    "read_only": 1,
                    "description": "Original unit price from the resolved selling price list.",
                },
                {
                    "fieldname": "source_discount_percent",
                    "label": "Remise %",
                    "fieldtype": "Percent",
                    "insert_after": "source_price_list_sell_rate",
                    "precision": 9,
                },
                {
                    "fieldname": "source_max_discount_percent",
                    "label": "Source Max Discount Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_discount_percent",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_amount",
                    "label": "Remise unitaire HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_max_discount_percent",
                    "precision": 9,
                    "read_only": 1,
                    "description": "Discount amount per unit relative to PU List HT.",
                },
                {
                    "fieldname": "source_commission_rate",
                    "label": "Source Commission Rate",
                    "fieldtype": "Percent",
                    "insert_after": "source_discount_amount",
                    "precision": 9,
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_commission_amount",
                    "label": "Source Commission Amount",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_rate",
                    "precision": 9,
                    "read_only": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_amount",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "precision": 9,
                    "read_only": 1,
                },
            ],
            "Sales Order Item": [
                {
                    "fieldname": "source_price_list_sell_rate",
                    "label": "PU List HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_selling_price_list",
                    "precision": 9,
                    "read_only": 1,
                    "description": "Original unit price inherited from the source Quotation item.",
                },
                {
                    "fieldname": "source_discount_percent",
                    "label": "Remise %",
                    "fieldtype": "Percent",
                    "insert_after": "source_price_list_sell_rate",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "source_max_discount_percent",
                    "label": "Source Max Discount Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_discount_percent",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_amount",
                    "label": "Remise unitaire HT",
                    "fieldtype": "Currency",
                    "insert_after": "source_max_discount_percent",
                    "precision": 9,
                    "read_only": 1,
                    "description": "Per-unit discount inherited from the source Quotation item.",
                },
                {
                    "fieldname": "source_commission_rate",
                    "label": "Source Commission Rate",
                    "fieldtype": "Percent",
                    "insert_after": "source_discount_amount",
                    "precision": 9,
                    "read_only": 1,
                    "hidden": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "source_commission_amount",
                    "label": "Source Commission Amount",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_rate",
                    "precision": 9,
                    "read_only": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_pu_ttc",
                    "label": "PU TTC",
                    "fieldtype": "Currency",
                    "insert_after": "source_commission_amount",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_applied_taxes",
                    "label": "Applied Taxes",
                    "fieldtype": "Currency",
                    "insert_after": "custom_pu_ttc",
                    "precision": 9,
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_pt_ttc",
                    "label": "PT TTC",
                    "fieldtype": "Currency",
                    "insert_after": "custom_applied_taxes",
                    "precision": 9,
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
            "Purchase Order": [
                {
                    "fieldname": "custom_buying_sources_section",
                    "label": "Buying Sources",
                    "fieldtype": "Section Break",
                    "insert_after": "buying_price_list",
                    "collapsible": 1,
                },
                {
                    "fieldname": "selected_buying_price_lists",
                    "label": "Buying Price Lists",
                    "fieldtype": "Table",
                    "options": "Pricing Sheet Price List Selection",
                    "insert_after": "custom_buying_sources_section",
                    "description": "Ordered active buying lists used to load the best valid supplier price per item.",
                },
                {
                    "fieldname": "custom_buying_price_update_summary",
                    "label": "Buying Price Update Summary",
                    "fieldtype": "Small Text",
                    "insert_after": "selected_buying_price_lists",
                    "read_only": 1,
                    "hidden": 1,
                },
            ],
            "Purchase Order Item": [
                {
                    "fieldname": "custom_source_buying_price_list",
                    "label": "Buying Price List Used",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "price_list_rate",
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_source_item_price",
                    "label": "Source Item Price",
                    "fieldtype": "Link",
                    "options": "Item Price",
                    "insert_after": "custom_source_buying_price_list",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_lock_buying_price_source",
                    "label": "Lock Buying Price Source",
                    "fieldtype": "Check",
                    "insert_after": "custom_source_item_price",
                    "default": "0",
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_source_buying_rate",
                    "label": "List price",
                    "fieldtype": "Currency",
                    "options": "custom_loaded_buying_currency",
                    "insert_after": "custom_lock_buying_price_source",
                    "read_only": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_loaded_buying_rate",
                    "label": "Loaded Buying Rate",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "insert_after": "custom_source_buying_rate",
                    "read_only": 1,
                    "precision": 9,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_loaded_buying_currency",
                    "label": "Loaded Buying Currency",
                    "fieldtype": "Link",
                    "options": "Currency",
                    "insert_after": "custom_loaded_buying_rate",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_loaded_buying_uom",
                    "label": "Loaded Buying UOM",
                    "fieldtype": "Link",
                    "options": "UOM",
                    "insert_after": "custom_loaded_buying_currency",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_variance_amount",
                    "label": "Negotiated Variance",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "insert_after": "custom_loaded_buying_uom",
                    "read_only": 1,
                    "precision": 9,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_price_variance_percent",
                    "label": "Negotiated Variance %",
                    "fieldtype": "Percent",
                    "insert_after": "custom_price_variance_amount",
                    "read_only": 1,
                    "precision": 9,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_update_price_list_on_submit",
                    "label": "Update Buying Price List on Submit",
                    "fieldtype": "Check",
                    "insert_after": "custom_price_variance_percent",
                    "default": "0",
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_update_decision",
                    "label": "Price Update Decision",
                    "fieldtype": "Select",
                    "options": "\nPending\nApproved\nSkipped\nNo Change",
                    "insert_after": "custom_update_price_list_on_submit",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_update_log",
                    "label": "Buying Price Change Log",
                    "fieldtype": "Link",
                    "options": "Buying Price Change Log",
                    "insert_after": "custom_price_update_decision",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_reviewed_by",
                    "label": "Price Reviewed By",
                    "fieldtype": "Link",
                    "options": "User",
                    "insert_after": "custom_price_update_log",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_reviewed_on",
                    "label": "Price Reviewed On",
                    "fieldtype": "Datetime",
                    "insert_after": "custom_price_reviewed_by",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_reviewed_rate",
                    "label": "Reviewed Negotiated Rate",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "insert_after": "custom_price_reviewed_on",
                    "read_only": 1,
                    "hidden": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_price_reviewed_loaded_rate",
                    "label": "Reviewed Loaded Rate",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "insert_after": "custom_price_reviewed_rate",
                    "read_only": 1,
                    "hidden": 1,
                    "precision": 9,
                },
                {
                    "fieldname": "custom_price_reviewed_source_buying_price_list",
                    "label": "Reviewed Source Buying Price List",
                    "fieldtype": "Link",
                    "options": "Price List",
                    "insert_after": "custom_price_reviewed_loaded_rate",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_reviewed_source_currency",
                    "label": "Reviewed Source Currency",
                    "fieldtype": "Link",
                    "options": "Currency",
                    "insert_after": "custom_price_reviewed_source_buying_price_list",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_price_review_attestation",
                    "label": "Price Update Attested",
                    "fieldtype": "Check",
                    "insert_after": "custom_price_reviewed_source_currency",
                    "read_only": 1,
                    "hidden": 1,
                },
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
    if frappe.get_meta("Quotation").get_field("custom_commercial_designation"):
        _upsert_property_setter("Quotation", "custom_commercial_designation", "mandatory_depends_on", "", "Data")
        custom_field = frappe.db.exists(
            "Custom Field",
            {"dt": "Quotation", "fieldname": "custom_commercial_designation"},
        )
        if custom_field:
            frappe.db.set_value("Custom Field", custom_field, "mandatory_depends_on", "")

    quotation_item_hidden_fields = [
        "price_list_rate",
        "base_price_list_rate",
        "discount_percentage",
        "discount_amount",
        "net_rate",
        "net_amount",
        "base_net_rate",
        "base_net_amount",
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
    ]
    for fieldname in quotation_item_hidden_fields:
        if not frappe.get_meta("Quotation Item").get_field(fieldname):
            continue
        _upsert_property_setter("Quotation Item", fieldname, "hidden", "1", "Check")
        _upsert_property_setter("Quotation Item", fieldname, "in_list_view", "0", "Check")
        if fieldname in {"price_list_rate", "base_price_list_rate"}:
            _upsert_property_setter("Quotation Item", fieldname, "read_only", "1", "Check")

    quotation_item_visible_fields = [
        ("rate", "PU HT"),
        ("amount", "PT HT"),
        ("source_selling_price_list", "Selling Price List Used"),
        ("source_price_list_sell_rate", "PU List HT"),
        ("source_discount_percent", "Remise %"),
        ("source_max_discount_percent", "Max Discount %"),
        ("source_discount_amount", "Remise unitaire HT"),
        ("source_target_margin_percent", "Target Policy Margin %"),
        ("source_margin_percent", "Actual Margin %"),
        ("source_margin_basis", "Margin Basis"),
        ("source_base_buy_rate", "Base Buy Rate"),
        ("source_landed_cost", "Loaded Cost"),
        ("source_commission_rate", "Commission %"),
        ("source_commission_amount", "Commission Amount"),
        ("custom_applied_taxes", "Applied Taxes"),
        ("custom_pu_ttc", "PU TTC"),
        ("custom_pt_ttc", "PT TTC"),
    ]
    for fieldname, label in quotation_item_visible_fields:
        if not frappe.get_meta("Quotation Item").get_field(fieldname):
            continue
        _upsert_property_setter("Quotation Item", fieldname, "label", label, "Data")
        _upsert_property_setter("Quotation Item", fieldname, "hidden", "0", "Check")
        _upsert_property_setter("Quotation Item", fieldname, "in_list_view", "1", "Check")
    for fieldname in ("rate", "source_discount_percent", "source_discount_amount"):
        if frappe.get_meta("Quotation Item").get_field(fieldname):
            _upsert_property_setter("Quotation Item", fieldname, "read_only", "0", "Check")
    quotation_item_derived_fields = (
        "amount",
        "source_price_list_sell_rate",
        "source_max_discount_percent",
        "source_base_buy_rate",
        "source_landed_cost",
        "source_commission_rate",
        "source_commission_amount",
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
    )
    for fieldname in quotation_item_derived_fields:
        if frappe.get_meta("Quotation Item").get_field(fieldname):
            _upsert_property_setter("Quotation Item", fieldname, "read_only", "1", "Check")
    if frappe.get_meta("Quotation Item").get_field("custom_applied_taxes"):
        _upsert_property_setter("Quotation Item", "custom_applied_taxes", "in_list_view", "0", "Check")


def ensure_sales_order_pricing_layout():
    _ensure_transaction_party_header_order(
        "Sales Order",
        ("customer_name", "customer", "tax_id"),
        "is_subcontracted",
    )
    for fieldname in ("customer_name", "customer", "tax_id"):
        if frappe.get_meta("Sales Order").get_field(fieldname):
            _upsert_property_setter("Sales Order", fieldname, "hidden", "0", "Check")
    if frappe.get_meta("Sales Order").get_field("is_subcontracted"):
        _upsert_property_setter("Sales Order", "is_subcontracted", "hidden", "1", "Check")
    if frappe.get_meta("Sales Order").get_field("source_pricing_sheet"):
        _upsert_property_setter("Sales Order", "source_pricing_sheet", "read_only", "1", "Check")
    if frappe.get_meta("Sales Order").get_field("selected_selling_price_lists"):
        _upsert_property_setter("Sales Order", "selected_selling_price_lists", "read_only", "1", "Check")

    sales_order_item_hidden_fields = [
        "price_list_rate",
        "base_price_list_rate",
        "discount_percentage",
        "discount_amount",
        "net_rate",
        "net_amount",
        "base_net_rate",
        "base_net_amount",
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
    ]
    for fieldname in sales_order_item_hidden_fields:
        if not frappe.get_meta("Sales Order Item").get_field(fieldname):
            continue
        _upsert_property_setter("Sales Order Item", fieldname, "hidden", "1", "Check")
        _upsert_property_setter("Sales Order Item", fieldname, "in_list_view", "0", "Check")

    sales_order_item_visible_fields = [
        ("rate", "PU HT"),
        ("amount", "PT HT"),
        ("source_selling_price_list", "Selling Price List Used"),
        ("source_price_list_sell_rate", "PU List HT"),
        ("source_discount_percent", "Remise %"),
        ("source_margin_basis", "Margin Basis"),
        ("source_target_margin_percent", "Target Policy Margin %"),
        ("source_margin_percent", "Actual Margin %"),
        ("source_base_buy_rate", "Base Buy Rate"),
        ("source_landed_cost", "Loaded Cost"),
        ("source_max_discount_percent", "Max Discount %"),
        ("source_discount_amount", "Remise unitaire HT"),
        ("source_commission_rate", "Commission %"),
        ("source_commission_amount", "Commission Amount"),
        ("custom_applied_taxes", "Applied Taxes"),
        ("custom_pu_ttc", "PU TTC"),
        ("custom_pt_ttc", "PT TTC"),
    ]
    for fieldname, label in sales_order_item_visible_fields:
        if not frappe.get_meta("Sales Order Item").get_field(fieldname):
            continue
        _upsert_property_setter("Sales Order Item", fieldname, "label", label, "Data")
        _upsert_property_setter("Sales Order Item", fieldname, "hidden", "0", "Check")
        _upsert_property_setter("Sales Order Item", fieldname, "in_list_view", "1", "Check")
    if frappe.get_meta("Sales Order Item").get_field("rate"):
        _upsert_property_setter("Sales Order Item", "rate", "read_only", "1", "Check")
    for fieldname, _label in sales_order_item_visible_fields:
        if fieldname == "rate" or not frappe.get_meta("Sales Order Item").get_field(fieldname):
            continue
        _upsert_property_setter("Sales Order Item", fieldname, "read_only", "1", "Check")
    for fieldname in ("source_selling_price_list", "custom_applied_taxes", "source_margin_basis"):
        if frappe.get_meta("Sales Order Item").get_field(fieldname):
            _upsert_property_setter("Sales Order Item", fieldname, "in_list_view", "0", "Check")


def ensure_sales_invoice_pricing_layout():
    _ensure_transaction_party_header_order(
        "Sales Invoice",
        ("customer_name", "customer", "tax_id"),
        "custom_invoice_mode",
    )
    if frappe.get_meta("Sales Invoice").get_field("selected_selling_price_lists"):
        _upsert_property_setter("Sales Invoice", "selected_selling_price_lists", "read_only", "1", "Check")
    for fieldname in ("ignore_pricing_rule", "pricing_rules"):
        if frappe.get_meta("Sales Invoice").get_field(fieldname):
            _upsert_property_setter("Sales Invoice", fieldname, "hidden", "1", "Check")
    if frappe.get_meta("Sales Invoice").get_field("company_tax_id"):
        _upsert_property_setter("Sales Invoice", "company_tax_id", "hidden", "1", "Check")
    for fieldname in ("contact_mobile", "contact_email"):
        if frappe.get_meta("Sales Invoice").get_field(fieldname):
            _upsert_property_setter("Sales Invoice", fieldname, "hidden", "0", "Check")
    for fieldname in (
        "scan_barcode",
        "last_scanned_warehouse",
        "update_stock",
        "set_warehouse",
        "set_target_warehouse",
    ):
        if frappe.get_meta("Sales Invoice").get_field(fieldname):
            _upsert_property_setter("Sales Invoice", fieldname, "hidden", "1", "Check")
    for fieldname in ("incoming_rate", "allow_zero_valuation_rate"):
        if frappe.get_meta("Sales Invoice Item").get_field(fieldname):
            _upsert_property_setter("Sales Invoice Item", fieldname, "hidden", "1", "Check")


def _ensure_transaction_party_header_order(doctype: str, fields_to_move: tuple[str, ...], before_field: str) -> None:
    meta = frappe.get_meta(doctype)
    fieldnames = [df.fieldname for df in meta.fields if df.fieldname]
    movable = [fieldname for fieldname in fields_to_move if fieldname in fieldnames]
    if not movable or before_field not in fieldnames:
        return

    setter_name = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "doctype_or_field": "DocType", "property": "field_order"},
        "name",
    )
    if setter_name:
        value = frappe.db.get_value("Property Setter", setter_name, "value") or "[]"
        try:
            field_order = json.loads(value)
        except (TypeError, ValueError):
            field_order = []
    else:
        field_order = fieldnames

    if not isinstance(field_order, list):
        field_order = fieldnames
    for fieldname in fieldnames:
        if fieldname not in field_order:
            field_order.append(fieldname)

    reordered = [fieldname for fieldname in field_order if fieldname not in movable]
    try:
        insert_at = reordered.index(before_field)
    except ValueError:
        return
    for fieldname in reversed(movable):
        reordered.insert(insert_at, fieldname)
    if reordered == field_order:
        return

    _upsert_doctype_property_setter(doctype, "field_order", json.dumps(reordered), "Data")
    frappe.clear_cache(doctype=doctype)


def ensure_sales_invoice_mode_fields():
    create_custom_fields(
        {
            "Sales Invoice": [
                {
                    "fieldname": "custom_invoice_mode",
                    "label": "Invoice Mode",
                    "fieldtype": "Select",
                    "options": "\nItems\nAdvance\nCustom",
                    "insert_after": "customer",
                    "read_only": 1,
                    "hidden": 1,
                    "description": "Orderlift invoice builder mode selected on the Sales Invoice form.",
                },
                {
                    "fieldname": "custom_advance_payment_entry",
                    "label": "Advance Payment Entry",
                    "fieldtype": "Link",
                    "options": "Payment Entry",
                    "insert_after": "custom_invoice_mode",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_advance_sales_order",
                    "label": "Advance Sales Order",
                    "fieldtype": "Link",
                    "options": "Sales Order",
                    "insert_after": "custom_advance_payment_entry",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_advance_payment_schedule_row",
                    "label": "Advance Payment Schedule Row",
                    "fieldtype": "Data",
                    "insert_after": "custom_advance_sales_order",
                    "read_only": 1,
                    "hidden": 1,
                },
            ],
        },
        update=True,
    )
    frappe.clear_cache(doctype="Sales Invoice")


def ensure_purchase_order_pricing_layout():
    if frappe.get_meta("Purchase Order").get_field("currency_and_price_list"):
        _upsert_property_setter("Purchase Order", "currency_and_price_list", "label", "Currency", "Data")
    for fieldname in ("buying_price_list", "price_list_currency", "plc_conversion_rate"):
        if frappe.get_meta("Purchase Order").get_field(fieldname):
            _upsert_property_setter("Purchase Order", fieldname, "hidden", "1", "Check")
    if frappe.get_meta("Purchase Order").get_field("buying_price_list"):
        _upsert_property_setter("Purchase Order", "buying_price_list", "read_only", "1", "Check")
    if frappe.get_meta("Purchase Order").get_field("custom_buying_sources_section"):
        _upsert_property_setter(
            "Purchase Order",
            "custom_buying_sources_section",
            "insert_after",
            "supplier",
            "Data",
        )

    visible_fields = (
        ("rate", "PU HT"),
        ("custom_source_buying_price_list", "Buying Price List Used"),
        ("custom_source_buying_rate", "List price"),
        ("custom_loaded_buying_rate", "Loaded Buying Rate"),
        ("custom_price_variance_amount", "Negotiated Variance"),
        ("custom_price_variance_percent", "Negotiated Variance %"),
        ("custom_pu_ttc", "PU TTC"),
        ("custom_pt_ttc", "PT TTC"),
    )
    for fieldname, label in visible_fields:
        if not frappe.get_meta("Purchase Order Item").get_field(fieldname):
            continue
        _upsert_property_setter("Purchase Order Item", fieldname, "label", label, "Data")
        _upsert_property_setter("Purchase Order Item", fieldname, "hidden", "0", "Check")
        _upsert_property_setter("Purchase Order Item", fieldname, "in_list_view", "1", "Check")
    if frappe.get_meta("Purchase Order Item").get_field("price_list_rate"):
        _upsert_property_setter("Purchase Order Item", "price_list_rate", "hidden", "1", "Check")
        _upsert_property_setter("Purchase Order Item", "price_list_rate", "in_list_view", "0", "Check")
    for fieldname, label in (
        ("custom_loaded_buying_currency", "Source Currency"),
        ("custom_loaded_buying_uom", "Source UOM"),
    ):
        if frappe.get_meta("Purchase Order Item").get_field(fieldname):
            _upsert_property_setter("Purchase Order Item", fieldname, "label", label, "Data")
    for fieldname in (
        "price_list_rate",
        "custom_source_buying_rate",
        "custom_loaded_buying_rate",
        "custom_price_variance_amount",
        "custom_price_variance_percent",
        "custom_pu_ttc",
        "custom_pt_ttc",
    ):
        if frappe.get_meta("Purchase Order Item").get_field(fieldname):
            _upsert_property_setter("Purchase Order Item", fieldname, "read_only", "1", "Check")


def ensure_commission_field_cleanup():
    """Hide legacy native commission ownership fields superseded by the team."""
    for doctype, fieldname in (
        ("Customer", "account_manager"),
        ("Customer", "sales_team_section_break"),
        ("Sales Person", "commission_rate"),
        ("Quotation", "commission_sales_person"),
        ("Sales Order", "sales_team_section_break"),
    ):
        if frappe.get_meta(doctype).get_field(fieldname):
            _upsert_property_setter(doctype, fieldname, "hidden", "1", "Check")
    for doctype in ("Pricing Sheet", "Quotation", "Sales Order"):
        if frappe.get_meta(doctype).get_field("custom_opportunity_owner"):
            _upsert_property_setter(doctype, "custom_opportunity_owner", "hidden", "0", "Check")
            _upsert_property_setter(doctype, "custom_opportunity_owner", "read_only", "1", "Check")
            frappe.clear_cache(doctype=doctype)


def ensure_margin_snapshot_permissions():
    """Expose permlevel-2 profitability snapshots only to pricing administrators."""
    privileged_roles = ("Orderlift Admin", "Pricing Configuration", "System Manager")
    for doctype in ("Quotation", "Sales Order"):
        for role in privileged_roles:
            if not frappe.db.exists("Role", role):
                continue
            filters = {"parent": doctype, "role": role, "permlevel": 2}
            existing = frappe.db.exists("Custom DocPerm", filters)
            permission = frappe.get_doc("Custom DocPerm", existing) if existing else frappe.new_doc("Custom DocPerm")
            permission.parent = doctype
            permission.parenttype = "DocType"
            permission.parentfield = "permissions"
            permission.role = role
            permission.permlevel = 2
            permission.read = 1
            permission.write = 0
            if existing:
                permission.save(ignore_permissions=True)
            else:
                permission.insert(ignore_permissions=True)


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
        _upsert_property_setter(item_doctype, fieldname, "read_only", "1", "Check")


def ensure_canonical_pricing_precision():
    transaction_native_currency_fields = (
        "price_list_rate",
        "base_price_list_rate",
        "rate",
        "base_rate",
        "amount",
        "base_amount",
        "net_rate",
        "net_amount",
        "base_net_rate",
        "base_net_amount",
        "rate_with_margin",
        "margin_rate_or_amount",
        "discount_amount",
        "base_discount_amount",
    )
    retained_snapshot_currency_fields = (
        "source_price_list_sell_rate",
        "source_discount_amount",
        "source_base_buy_rate",
        "source_landed_cost",
        "source_customs_applied",
        "source_commission_amount",
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
    )
    fields_by_doctype = {
        "Item Price": (
            "price_list_rate",
            "custom_last_builder_buy_rate",
            "custom_builder_expense_amount",
            "custom_builder_customs_amount",
        ),
        "Quotation Item": transaction_native_currency_fields + retained_snapshot_currency_fields,
        "Sales Order Item": transaction_native_currency_fields + retained_snapshot_currency_fields,
        "Delivery Note Item": transaction_native_currency_fields + (
            "custom_applied_taxes",
            "custom_pu_ttc",
            "custom_pt_ttc",
        ),
        "Sales Invoice Item": transaction_native_currency_fields + (
            "custom_applied_taxes",
            "custom_pu_ttc",
            "custom_pt_ttc",
        ),
        "Sales Commission": ("base_amount", "commission_amount"),
    }

    for doctype, fieldnames in fields_by_doctype.items():
        meta = frappe.get_meta(doctype)
        for fieldname in fieldnames:
            field = meta.get_field(fieldname)
            if not field or getattr(field, "fieldtype", "") != "Currency":
                continue
            _upsert_property_setter(doctype, fieldname, "precision", "9", "Int")
        frappe.clear_cache(doctype=doctype)

    percent_fields_by_doctype = {
        "Quotation Item": (
            "discount_percentage",
            "source_discount_percent",
            "source_max_discount_percent",
            "source_target_margin_percent",
            "source_margin_percent",
            "source_commission_rate",
        ),
        "Sales Order Item": (
            "discount_percentage",
            "source_discount_percent",
            "source_max_discount_percent",
            "source_target_margin_percent",
            "source_margin_percent",
            "source_commission_rate",
        ),
        "Sales Commission": ("commission_rate",),
    }
    for doctype, fieldnames in percent_fields_by_doctype.items():
        meta = frappe.get_meta(doctype)
        for fieldname in fieldnames:
            field = meta.get_field(fieldname)
            if field and getattr(field, "fieldtype", "") == "Percent":
                _upsert_property_setter(doctype, fieldname, "precision", "9", "Int")
        frappe.clear_cache(doctype=doctype)

    for doctype in ("Quotation Item", "Sales Order Item", "Delivery Note Item", "Sales Invoice Item"):
        meta = frappe.get_meta(doctype)
        for fieldname, label in (("rate", "PU HT"), ("amount", "PT HT")):
            if meta.get_field(fieldname):
                _upsert_property_setter(doctype, fieldname, "label", label, "Data")
        for fieldname, label in (("net_rate", "PU HT"), ("net_amount", "PT HT")):
            if not meta.get_field(fieldname):
                continue
            _upsert_property_setter(doctype, fieldname, "label", label, "Data")
            _upsert_property_setter(doctype, fieldname, "hidden", "1", "Check")
            _upsert_property_setter(doctype, fieldname, "in_list_view", "0", "Check")


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


def ensure_default_other_charges():
    if not frappe.db.exists("DocType", "Orderlift Other Charge"):
        return
    if frappe.db.exists("Orderlift Other Charge", "Other Charges"):
        return

    doc = frappe.new_doc("Orderlift Other Charge")
    doc.charge_name = "Other Charges"
    doc.description = "Other Charges"
    doc.default_uom = _first_existing_value("UOM", ("Nos", "Unit", "Pce", "Service"))
    doc.default_rate = 0
    doc.item_code = "OTHER-CHARGES" if frappe.db.exists("Item", "OTHER-CHARGES") else ""
    doc.insert(ignore_permissions=True)


def _first_existing_value(doctype: str, names: tuple[str, ...]) -> str:
    for name in names:
        if frappe.db.exists(doctype, name):
            return name
    return ""


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


def _upsert_doctype_property_setter(doctype: str, property_name: str, value, property_type: str):
    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "doctype_or_field": "DocType", "property": property_name},
        "name",
    )
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocType"
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


def _remove_opportunity_commercial_presentation_header_fields():
    for fieldname in (
        "custom_presentation_mode",
        "custom_commercial_designation",
        "custom_commercial_total",
        "custom_commercial_presentation_template",
        "custom_commercial_presentation_snapshot",
    ):
        _delete_custom_field(f"Opportunity-{fieldname}")
