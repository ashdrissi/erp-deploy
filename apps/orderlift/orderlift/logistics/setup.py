import json

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
                    "fieldname": "custom_item_category",
                    "label": "Catégorie article",
                    "fieldtype": "Link",
                    "options": "Item Category",
                    "insert_after": "item_group",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "allow_in_quick_entry": 1,
                    "description": "Détermine l'abréviation utilisée pour la séquence du code article.",
                },
                {
                    "fieldname": "custom_category_abbreviation",
                    "label": "Abréviation catégorie",
                    "fieldtype": "Data",
                    "insert_after": "custom_item_category",
                    "fetch_from": "custom_item_category.abbreviation",
                    "read_only": 1,
                    "in_standard_filter": 1,
                    "allow_in_quick_entry": 1,
                },
                {
                    "fieldname": "custom_specifications_section",
                    "label": "Spécifications",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_category_abbreviation",
                    "collapsible": 1,
                    "collapsed": 1,
                },
                {
                    "fieldname": "custom_item_name_language",
                    "label": "Main Item Name Language",
                    "fieldtype": "Link",
                    "options": "Language",
                    "insert_after": "item_name",
                    "default": "fr",
                    "hidden": 1,
                    "description": "Hidden because the main Item Name is the default catalog language.",
                },
                {
                    "fieldname": "custom_secondary_item_name",
                    "label": "Second Language Name",
                    "fieldtype": "Data",
                    "insert_after": "custom_item_name_language",
                    "in_global_search": 1,
                    "search_index": 1,
                },
                {
                    "fieldname": "custom_secondary_item_name_language",
                    "label": "Second Name Language",
                    "fieldtype": "Link",
                    "options": "Language",
                    "insert_after": "custom_secondary_item_name",
                    "default": "en",
                },
                {
                    "fieldname": "custom_item_add_guide_section",
                    "label": "Guide ajout article",
                    "fieldtype": "Section Break",
                    "insert_after": "brand",
                    "collapsible": 1,
                    "collapsed": 1,
                },
                {
                    "fieldname": "custom_item_add_guide_html",
                    "label": "Guide ajout article",
                    "fieldtype": "HTML",
                    "insert_after": "custom_item_add_guide_section",
                    "options": "<div style=\"padding:8px 0 4px;line-height:1.55;\"><p><strong>Création d'article Orderlift.</strong></p><p><strong>Détails</strong>: choisir la Catégorie article. Si le code article est vide, le système génère un code avec l'abréviation de la catégorie, par exemple <code>ARM-00001</code>.</p><p><strong>Dimensions</strong>: renseigner poids, volume, longueur, largeur et hauteur dans la section Spécifications. Ces champs servent aux calculs logistiques, planning de chargement, transport et douane.</p><p><strong>Spécifications</strong>: utiliser le tableau Attribut/Valeur pour les données commerciales filtrables comme Taille, Capacité, Finition, Tension, Ampérage, Puissance et Type.</p><p><strong>UOM</strong>: l'unité principale reste le champ Default Unit of Measure. Les conversions restent dans la table UOMs.</p><p><strong>Packaging Profile</strong>: renseigner les formats réels d'achat/expédition dans Packaging Profiles. Ces profils alimentent les commandes d'achat et le planning logistique.</p><p><strong>HS code</strong>: renseigner Customs Tariff Number (HS code) pour appliquer la bonne politique douane dans les Pricing Sheets.</p></div>",
                },
                {
                    "fieldname": "custom_packaging_profiles",
                    "label": "Packaging Profiles",
                    "fieldtype": "Table",
                    "options": "Item Packaging Profile",
                    "insert_after": "uoms",
                },
                {
                    "fieldname": "custom_buying_item_prices_section",
                    "label": "Buying Prices",
                    "fieldtype": "Section Break",
                    "insert_after": "supplier_details",
                    "collapsible": 0,
                    "collapsed": 0,
                },
                {
                    "fieldname": "custom_buying_item_prices",
                    "label": "Buying Prices",
                    "fieldtype": "Table",
                    "options": "Orderlift Item Buying Price",
                    "insert_after": "custom_buying_item_prices_section",
                    "description": "Native Item price rows synced to Buying Item Price records on save.",
                },
                {
                    "fieldname": "custom_selling_item_prices_section",
                    "label": "Selling Prices",
                    "fieldtype": "Section Break",
                    "insert_after": "max_discount",
                    "collapsible": 0,
                    "collapsed": 0,
                },
                {
                    "fieldname": "custom_selling_item_prices",
                    "label": "Selling Prices",
                    "fieldtype": "Table",
                    "options": "Orderlift Item Selling Price",
                    "insert_after": "custom_selling_item_prices_section",
                    "description": "Native Item price rows synced to Selling Item Price records on save.",
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
                {
                    "fieldname": "custom_current_company_stock_qty",
                    "label": "Stock (Company Session)",
                    "fieldtype": "Float",
                    "insert_after": "custom_inventory_flag",
                    "read_only": 1,
                    "in_list_view": 1,
                    "description": "Read-only Item list value populated from stock in warehouses of the active company session.",
                },
                {
                    "fieldname": "custom_company_stock_section",
                    "label": "Stock par dépôt",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_current_company_stock_qty",
                    "collapsible": 1,
                    "collapsed": 0,
                    "description": "Lecture seule: stock par dépôt pour la société active.",
                },
                {
                    "fieldname": "custom_company_warehouse_stock",
                    "label": "Stock par dépôt",
                    "fieldtype": "Table",
                    "options": "Orderlift Item Warehouse Stock",
                    "insert_after": "custom_company_stock_section",
                    "read_only": 1,
                    "description": "Quantités disponibles dans les dépôts de la société active.",
                },
                {
                    "fieldname": "custom_company_stock_total",
                    "label": "Total Stock (Company Session)",
                    "fieldtype": "Float",
                    "insert_after": "custom_company_warehouse_stock",
                    "read_only": 1,
                    "description": "Somme des quantités du tableau Stock par dépôt pour la société active.",
                },
                {
                    "fieldname": "custom_specifications",
                    "label": "Spécifications",
                    "fieldtype": "Table",
                    "options": "Item Specification Value",
                    "insert_after": "custom_company_stock_total",
                    "description": "Attributs techniques dynamiques de l'article.",
                },
                {
                    "fieldname": "custom_specification_search_text",
                    "label": "Recherche spécifications",
                    "fieldtype": "Data",
                    "length": 500,
                    "insert_after": "custom_specifications",
                    "hidden": 1,
                    "read_only": 1,
                    "in_global_search": 1,
                    "in_standard_filter": 1,
                    "search_index": 1,
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
    seed_item_categories()
    backfill_item_category_item_groups()
    seed_item_specification_attributes()
    seed_douane_materials_from_items()
    enforce_item_price_child_table_fields()
    arrange_item_specification_fields()
    label_item_specifications_section()
    apply_item_field_order()

    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Buying Settings")
    frappe.clear_cache(doctype="Purchase Order")
    frappe.clear_cache(doctype="Sales Order")
    frappe.clear_cache(doctype="Delivery Note")
    frappe.clear_cache(doctype="Purchase Receipt")
    frappe.clear_cache(doctype="Stock Entry")
    frappe.clear_cache(doctype="Delivery Trip")
    retire_logistics_workspace()


def seed_item_specification_attributes():
    rows = [
        {"attribute_name": "Taille", "value_type": "Texte", "unit": "", "sequence": 10},
        {"attribute_name": "Capacité", "value_type": "Texte", "unit": "", "sequence": 20},
        {"attribute_name": "Finition", "value_type": "Texte", "unit": "", "sequence": 30},
        {"attribute_name": "Tension", "value_type": "Nombre", "unit": "V", "sequence": 40},
        {"attribute_name": "Ampérage", "value_type": "Nombre", "unit": "A", "sequence": 50},
        {"attribute_name": "Puissance", "value_type": "Nombre", "unit": "kW", "sequence": 60},
        {"attribute_name": "Type", "value_type": "Texte", "unit": "", "sequence": 70},
    ]

    for row in rows:
        existing = frappe.db.get_value("Item Specification Attribute", {"attribute_name": row["attribute_name"]}, "name")
        doc = frappe.get_doc("Item Specification Attribute", existing) if existing else frappe.new_doc("Item Specification Attribute")
        doc.update(
            {
                **row,
                "is_filterable": 1,
                "is_active": 1,
            }
        )
        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)


def seed_item_categories():
    rows = [
        {"category_name": "Armoire", "abbreviation": "ARM", "sequence_digits": 5},
        {"category_name": "Autres", "abbreviation": "AUT", "sequence_digits": 5},
        {"category_name": "Boutons", "abbreviation": "BTN", "sequence_digits": 5},
        {"category_name": "Cabine & Arcade", "abbreviation": "CAB", "sequence_digits": 5},
        {"category_name": "Cables & Accessoires", "abbreviation": "CABL", "sequence_digits": 5},
        {"category_name": "Cables Electriques & Accessoires", "abbreviation": "CELEC", "sequence_digits": 5},
        {"category_name": "Gose", "abbreviation": "GOSE", "sequence_digits": 5},
        {"category_name": "Moteur", "abbreviation": "MOT", "sequence_digits": 5},
        {"category_name": "Operateur", "abbreviation": "OPR", "sequence_digits": 5},
        {"category_name": "Porte", "abbreviation": "POR", "sequence_digits": 5},
        {"category_name": "Rails & Accessoires", "abbreviation": "RAIL", "sequence_digits": 5},
    ]

    for row in rows:
        existing = frappe.db.get_value("Item Category", {"category_name": row["category_name"]}, "name")
        doc = frappe.get_doc("Item Category", existing) if existing else frappe.new_doc("Item Category")
        current_sequence = doc.current_sequence if existing else 0
        doc.update({**row, "is_active": 1, "current_sequence": current_sequence or 0})
        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)


def seed_douane_materials_from_items():
    if not frappe.db.exists("DocType", "Douane Material"):
        return

    values = set(frappe.get_all(
        "Item",
        filters={"custom_customs_material": ["not in", ["", None]]},
        pluck="custom_customs_material",
        distinct=True,
        limit_page_length=0,
    ))
    if frappe.db.exists("DocType", "Pricing Customs Rule"):
        values.update(
            row.material
            for row in frappe.get_all("Pricing Customs Rule", fields=["material"], limit_page_length=0)
            if (row.material or "").strip()
        )
    for value in values:
        material_name = (value or "").strip().upper()
        if not material_name or frappe.db.exists("Douane Material", material_name):
            continue
        doc = frappe.new_doc("Douane Material")
        doc.material_name = material_name
        doc.material_code = material_name
        doc.is_active = 1
        doc.insert(ignore_permissions=True)


def enforce_item_price_child_table_fields():
    for doctype in ("Orderlift Item Buying Price", "Orderlift Item Selling Price"):
        if not frappe.db.exists("DocType", doctype):
            continue
        field_name = frappe.db.get_value("DocField", {"parent": doctype, "fieldname": "price_list_rate"}, "name")
        if field_name:
            frappe.db.set_value("DocField", field_name, "fieldtype", "Float", update_modified=False)
        _upsert_property_setter(doctype, "price_list_rate", "fieldtype", "Float", "Data")
        frappe.clear_cache(doctype=doctype)


def arrange_item_specification_fields():
    for fieldname in ["Item-custom_import_key", "Item-custom_legacy_item_code", "Item-custom_item_settings_section"]:
        if frappe.db.exists("Custom Field", fieldname):
            frappe.delete_doc("Custom Field", fieldname, ignore_permissions=True, force=True)

    ordering = [
        ("Item-custom_item_category", "item_group", 6),
        ("Item-custom_category_abbreviation", "custom_item_category", 7),
        ("Item-custom_item_name_language", "item_name", 8),
        ("Item-custom_secondary_item_name", "custom_item_name_language", 9),
        ("Item-custom_secondary_item_name_language", "custom_secondary_item_name", 10),
        ("Item-custom_specifications_section", "asset_naming_series", 17),
        ("Item-custom_material", "custom_specifications_section", 18),
        ("Item-custom_customs_material", "customs_tariff_number", 19),
        ("Item-custom_weight_kg", "custom_customs_material", 20),
        ("Item-custom_volume_m3", "custom_weight_kg", 21),
        ("Item-custom_length_cm", "custom_volume_m3", 22),
        ("Item-custom_width_cm", "custom_length_cm", 23),
        ("Item-custom_height_cm", "custom_width_cm", 24),
        ("Item-custom_inventory_flag", "custom_height_cm", 25),
        ("Item-custom_specifications", "custom_inventory_flag", 26),
        ("Item-custom_specification_search_text", "custom_specifications", 27),
        ("Item-custom_packaging_profiles", "uoms", 30),
        ("Item-custom_buying_item_prices_section", "supplier_details", 31),
        ("Item-custom_buying_item_prices", "custom_buying_item_prices_section", 32),
        ("Item-custom_selling_item_prices_section", "max_discount", 33),
        ("Item-custom_selling_item_prices", "custom_selling_item_prices_section", 34),
        ("Item-custom_item_add_guide_section", "brand", 35),
        ("Item-custom_item_add_guide_html", "custom_item_add_guide_section", 36),
    ]

    for name, insert_after, idx in ordering:
        if frappe.db.exists("Custom Field", name):
            frappe.db.set_value(
                "Custom Field",
                name,
                {"insert_after": insert_after, "idx": idx},
                update_modified=False,
            )


def backfill_item_category_item_groups():
    if not frappe.db.exists("DocType", "Item Category"):
        return
    if not frappe.db.has_column("Item Category", "item_group"):
        return
    if not frappe.db.has_column("Item", "custom_item_category"):
        return

    rows = frappe.db.sql(
        """
        SELECT custom_item_category AS category, item_group, COUNT(*) AS item_count
        FROM `tabItem`
        WHERE COALESCE(custom_item_category, '') != ''
          AND COALESCE(item_group, '') != ''
        GROUP BY custom_item_category, item_group
        ORDER BY custom_item_category, item_count DESC
        """,
        as_dict=True,
    )
    grouped = {}
    for row in rows:
        grouped.setdefault(row.category, []).append(row)

    ambiguous = []
    for category, category_rows in grouped.items():
        if not frappe.db.exists("Item Category", category):
            continue
        current_group = (frappe.db.get_value("Item Category", category, "item_group") or "").strip()
        if current_group:
            continue
        groups = [row.item_group for row in category_rows if row.item_group]
        if len(set(groups)) == 1:
            frappe.db.set_value("Item Category", category, "item_group", groups[0], update_modified=False)
        else:
            ambiguous.append(f"{category}: {', '.join(groups[:5])}")

    if ambiguous:
        frappe.logger("orderlift").warning(
            "Ambiguous Item Category item_group backfill skipped for %s categor(ies): %s",
            len(ambiguous),
            "; ".join(ambiguous[:20]),
        )


def label_item_specifications_section():
    for property_name in ["label", "collapsible", "collapsed", "insert_after"]:
        _delete_property_setter("Item", "section_break_gjns", property_name)

    _upsert_property_setter("Item", "unit_of_measure_conversion", "label", "UOM", "Data")
    _upsert_property_setter(
        "Item", "unit_of_measure_conversion", "insert_after", "custom_specification_search_text", "Data"
    )
    _upsert_property_setter("Item", "stock_uom", "insert_after", "unit_of_measure_conversion", "Data")
    _upsert_property_setter("Item", "uoms", "insert_after", "stock_uom", "Data")
    _upsert_property_setter("Item", "section_break_11", "insert_after", "custom_packaging_profiles", "Data")
    _upsert_property_setter("Item", "description", "insert_after", "section_break_11", "Data")
    _upsert_property_setter("Item", "brand", "insert_after", "description", "Data")

    standard_ordering = [
        ("disabled", 8),
        ("allow_alternative_item", 9),
        ("is_stock_item", 10),
        ("has_variants", 11),
        ("is_fixed_asset", 12),
        ("auto_create_assets", 13),
        ("is_grouped_asset", 14),
        ("asset_category", 15),
        ("asset_naming_series", 16),
        ("unit_of_measure_conversion", 27),
        ("stock_uom", 28),
        ("uoms", 29),
        ("section_break_11", 31),
        ("description", 32),
        ("brand", 33),
        ("section_break_gjns", 36),
        ("opening_stock", 37),
        ("standard_rate", 38),
        ("section_break_znra", 39),
    ]
    for fieldname, idx in standard_ordering:
        _upsert_property_setter("Item", fieldname, "idx", idx, "Int")

    _upsert_property_setter("Item", "section_break_gjns", "hidden", "1", "Check")
    _upsert_property_setter("Item", "section_break_znra", "hidden", "1", "Check")
    _upsert_property_setter("Item", "country_of_origin", "hidden", "1", "Check")
    _upsert_property_setter("Item", "supplier_details", "collapsed", "0", "Check")
    _upsert_property_setter("Item", "supplier_items", "hidden", "1", "Check")
    _upsert_property_setter("Item", "item_code", "read_only", "1", "Check")
    _upsert_property_setter("Item", "item_code", "default", "AUTO", "Data")
    _upsert_property_setter(
        "Item",
        "item_code",
        "description",
        "Generated from Catégorie article sequence when the Item is saved.",
        "Text",
    )
    _upsert_property_setter("Item", "custom_specifications_section", "collapsible", "1", "Check")
    _upsert_property_setter("Item", "custom_specifications_section", "collapsed", "1", "Check")
    _upsert_property_setter("Item", "custom_item_add_guide_section", "collapsed", "1", "Check")
    for fieldname in ["allow_alternative_item", "is_stock_item", "has_variants", "is_fixed_asset"]:
        _upsert_property_setter("Item", fieldname, "hidden", "1", "Check")
    _upsert_property_setter("Item", "opening_stock", "hidden", "1", "Check")
    _upsert_property_setter("Item", "standard_rate", "hidden", "1", "Check")


def apply_item_field_order():
    meta = frappe.get_meta("Item")
    existing = [df.fieldname for df in meta.fields]
    desired_start = [
        "details",
        "naming_series",
        "item_code",
        "item_name",
        "custom_item_name_language",
        "custom_secondary_item_name",
        "custom_secondary_item_name_language",
        "item_group",
        "custom_item_category",
        "custom_category_abbreviation",
        "disabled",
        "allow_alternative_item",
        "is_stock_item",
        "has_variants",
        "is_fixed_asset",
        "auto_create_assets",
        "is_grouped_asset",
        "asset_category",
        "asset_naming_series",
        "custom_specifications_section",
        "custom_material",
        "custom_weight_kg",
        "custom_volume_m3",
        "custom_length_cm",
        "custom_width_cm",
        "custom_height_cm",
        "custom_inventory_flag",
        "custom_specifications",
        "custom_specification_search_text",
        "unit_of_measure_conversion",
        "stock_uom",
        "uoms",
        "custom_packaging_profiles",
        "foreign_trade_details",
        "customs_tariff_number",
        "custom_customs_material",
        "country_of_origin",
        "section_break_11",
        "description",
        "brand",
        "supplier_details",
        "custom_buying_item_prices_section",
        "custom_buying_item_prices",
        "supplier_items",
        "sales_details",
        "is_sales_item",
        "max_discount",
        "custom_selling_item_prices_section",
        "custom_selling_item_prices",
        "custom_item_add_guide_section",
        "custom_item_add_guide_html",
    ]

    ordered = [fieldname for fieldname in desired_start if fieldname in existing]
    ordered_set = set(ordered)
    ordered.extend(fieldname for fieldname in existing if fieldname not in ordered_set)
    _upsert_doctype_property_setter("Item", "field_order", json.dumps(ordered), "Text")


def _delete_property_setter(doctype: str, fieldname: str, property_name: str):
    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "field_name": fieldname, "property": property_name},
        "name",
    )
    if existing:
        frappe.delete_doc("Property Setter", existing, ignore_permissions=True, force=True)


def _upsert_doctype_property_setter(doctype: str, property_name: str, value, property_type: str):
    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "doctype_or_field": "DocType", "property": property_name},
        "name",
    )
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocType"
    setter.field_name = None
    setter.property = property_name
    setter.property_type = property_type
    setter.value = str(value)
    if existing:
        setter.save(ignore_permissions=True)
    else:
        setter.insert(ignore_permissions=True)


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
    setter.value = str(value)
    if existing:
        setter.save(ignore_permissions=True)
    else:
        setter.insert(ignore_permissions=True)


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
