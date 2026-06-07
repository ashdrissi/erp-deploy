import frappe
import json
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


DEFAULT_MANUAL_TIER = "New"
DEFAULT_PRICING_TIERS = [DEFAULT_MANUAL_TIER, "Eco", "Intermediaire", "Luxe", "Gold", "Silver", "Bronze"]


def after_migrate():
    _coerce_customer_tier_fields_to_links()
    _coerce_item_material_field_to_link()
    _coerce_customs_material_field_to_data()
    ensure_item_material_records()
    create_custom_fields(
        {
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
                    "fieldtype": "Data",
                    "insert_after": "custom_material",
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
                    "fieldname": "custom_orderlift_builder_section",
                    "label": "Orderlift Builder",
                    "fieldtype": "Section Break",
                    "insert_after": "currency",
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
                    "fieldname": "custom_last_builder_buy_rate",
                    "label": "Last Builder Buy Rate",
                    "fieldtype": "Currency",
                    "insert_after": "custom_target_margin_percent",
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
                    "fieldname": "source_scenario_rule",
                    "label": "Source Scenario Rule",
                    "fieldtype": "Data",
                    "insert_after": "source_margin_percent",
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
    frappe.clear_cache(doctype="Quotation")
    frappe.clear_cache(doctype="Quotation Item")
    frappe.clear_cache(doctype="Selling Settings")
    ensure_quotation_discount_snapshot_fields()
    ensure_default_pricing_tiers()
    ensure_pricing_workspace()


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
    for fieldname in ("tier", "manual_tier"):
        field = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": fieldname}, "name")
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


def _coerce_customs_material_field_to_data():
    field = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": "custom_customs_material"}, "name")
    if field:
        frappe.db.set_value(
            "Custom Field",
            field,
            {"fieldtype": "Data", "options": "", "label": "Douane Material"},
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
            "fieldtype": "Select",
            "options": "\n" + "\n".join(DEFAULT_PRICING_TIERS),
            "insert_after": "enable_dynamic_segmentation",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "read_only": 1,
            "hidden": 1,
        },
        {
            "fieldname": "manual_tier",
            "label": "Tier",
            "fieldtype": "Select",
            "options": "\n" + "\n".join(DEFAULT_PRICING_TIERS),
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
            "Quotation Item": [
                {
                    "fieldname": "source_gross_sell_rate",
                    "label": "Source Gross Sell Rate",
                    "fieldtype": "Currency",
                    "insert_after": "source_customs_basis",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_percent",
                    "label": "Source Discount Percent",
                    "fieldtype": "Percent",
                    "insert_after": "source_gross_sell_rate",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discount_amount",
                    "label": "Source Discount Amount",
                    "fieldtype": "Currency",
                    "insert_after": "source_discount_percent",
                    "read_only": 1,
                },
                {
                    "fieldname": "source_discounted_sell_rate",
                    "label": "Source Discounted Sell Rate",
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
                    "hidden": 1,
                    "print_hide": 1,
                },
            ]
        },
        update=True,
        ignore_validate=True,
    )


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
