app_name = "orderlift"
app_title = "Orderlift"
app_publisher = "Syntax Line"
app_description = "Custom ERP modules for Orderlift — multi-company elevator parts management"
app_email = "contact@syntaxline.dev"
app_license = "MIT"
app_version = "1.0.0"

# Boot — rename ERPNext → Orderlift in sidebar subtitle and strip hidden navbar items.
extend_bootinfo = "orderlift.boot.extend_bootinfo"
boot_session = "orderlift.boot.extend_bootinfo"

# Required apps — orderlift depends on these being installed first
required_apps = ["frappe", "erpnext"]

# ---------------------------------------------------------
# Assets — included in Desk for all logged-in users
# ---------------------------------------------------------
app_include_css = [
    "/assets/orderlift/css/orderlift_bundle.css",
    "/assets/orderlift/css/orderlift_logistics_v2.css?v=20260415a",
    "/assets/orderlift/css/clp_dashboard_v4.css",
    "/assets/orderlift/css/pricing_sheet_20260414_82.css?v=20260501d",
    "/assets/orderlift/css/hr_shell.css?v=20260514c",
]
app_include_js = [
    "/assets/orderlift/js/orderlift_bundle_20260423e.js",
    "/assets/orderlift/js/orderlift_main_sidebar_lock_20260429b.js?v=20260429e",
    "/assets/orderlift/js/orderlift_change_company_label_20260519a.js?v=20260519a",
    "/assets/orderlift/js/orderlift_sidebar_tune_20260423e.js",
    "/assets/orderlift/js/orderlift_section_break_guard_20260423d.js",
    "/assets/orderlift/js/orderlift_main_dashboard_section_state_20260423g.js",
    "/assets/orderlift/js/crm_classification.js?v=20260601a",
    "/assets/orderlift/js/company_scope_form_20260601a.js?v=20260602a",
    "/assets/orderlift/js/company_scope_list_focus_20260601a.js?v=20260602a",
    "/assets/orderlift/js/sidebar_logo_fix_20260415b.js",
    "/assets/orderlift/js/refresh_stability_fix_20260415.js",
    "/assets/orderlift/js/desk_entry_redirect_20260427b.js",
    "/assets/orderlift/js/desk_dimensioning_route_redirect_20260428a.js",
    "/assets/orderlift/js/finance_account_guard_20260501a.js?v=20260501b",
    "/assets/orderlift/js/item_price_uom_default_20260506a.js?v=20260507a",
    "/assets/orderlift/js/document_annex_dialog_20260519a.js?v=20260519b",
    "/assets/orderlift/js/orderlift_home_page_scroll_fix_20260520b.js?v=20260520b",
]

# ---------------------------------------------------------
# Fixtures — exported configuration records loaded on
# bench migrate / bench --site <site> import-fixtures
# ---------------------------------------------------------
fixtures = [
    # Custom fields added to core ERPNext doctypes (Item, Customer, etc.)
    # All our custom fields use the "custom_" prefix per Frappe convention.
    # Filter by name prefix so only our fields are exported.
    {"dt": "Custom Field", "filters": [["name", "like", "%custom_%"]]},
    # Custom field JSON fixtures
    {"dt": "Custom Field", "filters": [["name", "=", "Sales Order-custom_forecast_plan"]]},
    {"dt": "Custom Field", "filters": [["name", "=", "Purchase Order-custom_forecast_plan"]]},
    {"dt": "Custom Field", "filters": [["name", "=", "Delivery Note-custom_forecast_plan"]]},
    # Property setters (field property overrides on existing doctypes)
    {"dt": "Property Setter", "filters": [["name", "like", "%-custom_%"]]},
    # Workflows on standard doctypes (Sales Order, Stock Entry, etc.)
    {"dt": "Workflow", "filters": [["name", "like", "Orderlift%"]]},
    {"dt": "Workflow State"},
    {"dt": "Workflow Action Master"},
    # Notification documents
    {"dt": "Notification", "filters": [["name", "like", "Orderlift%"]]},
    # Print formats (PDF templates)
    {"dt": "Print Format", "filters": [["name", "like", "Orderlift%"]]},
    # Role definitions
    {
        "dt": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "Orderlift Admin",
                    "Sales User",
                    "Pricing Manager",
                    "Logistics User",
                    "Finance User",
                    "Installation User",
                    "Service User",
                ],
            ]
        ],
    },
]

# ---------------------------------------------------------
# Document Events — server-side hooks on ERPNext doctypes
# ---------------------------------------------------------
doc_events = {
    "Sales Invoice": {
        "before_validate": "orderlift.orderlift_finance.account_governance.apply_document_account_defaults",
        "validate": "orderlift.orderlift_finance.account_governance.validate_finance_document",
        # Update Sales Commission approval state from invoice payment status
        "on_submit": "orderlift.sales.utils.commission_calculator.sync_commissions_from_invoice",
        "on_update_after_submit": "orderlift.sales.utils.commission_calculator.sync_commissions_from_invoice",
        "on_cancel": "orderlift.sales.utils.commission_calculator.cancel_commissions",
    },
    "Purchase Invoice": {
        "before_validate": "orderlift.orderlift_finance.account_governance.apply_document_account_defaults",
        "validate": "orderlift.orderlift_finance.account_governance.validate_finance_document",
    },
    "Payment Entry": {
        "before_validate": "orderlift.orderlift_finance.account_governance.apply_document_account_defaults",
        "validate": "orderlift.orderlift_finance.account_governance.validate_finance_document",
    },
    "Sales Order": {
        "before_validate": [
            "orderlift.sales.utils.sales_order_defaults.apply_company_defaults",
            "orderlift.orderlift_finance.account_governance.apply_document_account_defaults",
        ],
        "validate": [
            "orderlift.orderlift_crm.api.campaign.inherit_campaign_from_links",
            "orderlift.orderlift_crm.classification.sync_sales_order_crm_classification",
            "orderlift.orderlift_finance.account_governance.validate_finance_document",
            "orderlift.orderlift_crm.status_workflow.ensure_primary_status",
            "orderlift.company_scope.apply_company_scope",
        ],
        # Notify stock manager when a sales order is confirmed
        # Also warn if linked installation project has a Blocked QC (SIG)
        "on_submit": [
            "orderlift.orderlift_crm.api.campaign.sync_doc_campaign_rollup",
            "orderlift.sales.utils.commission_calculator.create_sales_order_commissions",
            "orderlift.sales.utils.stock_notifier.notify_stock_manager",
            "orderlift.orderlift_sig.utils.project_status_guard.on_sales_order_submit",
        ],
        "on_update": "orderlift.orderlift_crm.api.campaign.sync_doc_campaign_rollup",
        "on_cancel": "orderlift.sales.utils.commission_calculator.cancel_sales_order_commissions",
    },
    "Opportunity": {
        "before_insert": "orderlift.orderlift_crm.opportunity_hooks.assign_opportunity_name",
        "before_save": [
            "orderlift.orderlift_crm.opportunity_hooks.apply_opportunity_defaults",
            "orderlift.orderlift_crm.status_workflow.ensure_primary_status",
        ],
        "validate": "orderlift.company_scope.apply_company_scope",
        "on_trash": "orderlift.orderlift_crm.opportunity_hooks.unlink_prospect_opportunity_rows",
        "on_update": "orderlift.orderlift_crm.api.campaign.sync_doc_campaign_rollup",
    },
    "Quotation": {
        "validate": [
            "orderlift.orderlift_crm.api.campaign.inherit_campaign_from_links",
            "orderlift.orderlift_crm.classification.sync_quotation_crm_classification",
            "orderlift.company_scope.apply_company_scope",
        ],
        "on_update": "orderlift.orderlift_crm.api.campaign.sync_doc_campaign_rollup",
        "on_submit": "orderlift.orderlift_crm.api.campaign.sync_doc_campaign_rollup",
    },
    "Item": {
        "before_validate": "orderlift.orderlift_logistics.utils.item_sequence.apply_item_category_defaults",
        # Archive cost price into Item Cost History on save when cost changes
        "before_save": "orderlift.sales.utils.cost_history.archive_cost_price",
        "validate": [
            # Validate packaging profiles (single default, active fields, no duplicates)
            "orderlift.orderlift_logistics.utils.packaging_validation.validate_item_packaging_profiles",
            # Normalize dynamic French specification attributes and search text.
            "orderlift.orderlift_logistics.utils.item_specifications.validate_item_specifications",
        ],
    },
    "Item Price": {
        "after_insert": "orderlift.orderlift_sales.utils.price_list_auto_rebuild.on_item_price_change",
        "on_update": "orderlift.orderlift_sales.utils.price_list_auto_rebuild.on_item_price_change",
    },
    "Purchase Order": {
        # Resolve item packaging rows from selected/default packaging profiles.
        "validate": "orderlift.logistics.utils.purchase_order_packaging.validate_purchase_order_packaging",
    },
    "Purchase Receipt": {
        # Move stock to correct warehouse after quality inspection
        "on_submit": "orderlift.logistics.utils.stock_router.route_received_stock",
    },
    "Delivery Note": {
        # Inherit scenario classification from linked Sales Order
        "before_save": "orderlift.logistics.utils.flow_inherit.inherit_flow_from_sales_order",
        # Analyze physical shipment (weight/volume) on the real movement document
        "on_submit": "orderlift.logistics.utils.delivery_note_logistics.analyze_delivery_note",
        "on_cancel": "orderlift.logistics.utils.delivery_note_logistics.cancel_delivery_note_analysis",
    },
    "Customer": {
        "before_save": "orderlift.sales.utils.customer_tier.sync_customer_tier_mode",
        "validate": "orderlift.company_scope.apply_company_scope",
        "on_update": "orderlift.sales.utils.customer_tier.apply_dynamic_customer_tier",
    },
    "Prospect": {
        "before_save": "orderlift.sales.utils.customer_tier.sync_customer_tier_mode",
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Lead": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Supplier": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Price List": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Pricing Sheet": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Pricing Scenario": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Pricing Benchmark Policy": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Pricing Customs Policy": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Customer Segmentation Engine": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Partner Campaign": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Portal Customer Group Policy": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Portal Quote Request": {
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Company": {
        "after_insert": "orderlift.orderlift_finance.account_governance.ensure_company_finance_defaults",
        "on_update": "orderlift.orderlift_finance.account_governance.ensure_company_finance_defaults",
    },
    "SAV Ticket": {
        # Notify assigned technician when ticket status changes to Assigned
        "on_update": "orderlift.orderlift_sav.doctype.sav_ticket.sav_ticket.on_status_change",
    },
    "Project": {
        # Recalculate QC status + enforce completion guard (SIG module)
        "before_save": [
            "orderlift.orderlift_crm.classification.sync_project_crm_classification",
            "orderlift.orderlift_crm.status_workflow.ensure_primary_status",
            "orderlift.orderlift_sig.utils.project_qc.on_project_save",
            "orderlift.orderlift_sig.utils.project_status_guard.before_project_status_change",
        ],
        "validate": "orderlift.company_scope.apply_company_scope",
    },
    "Delivery Trip": {
        # Block Delivery Trip creation for inbound or customer-managed scenarios
        "validate": "orderlift.logistics.utils.scenario_guard.validate_delivery_trip",
    },
    "Goal": {
        "validate": "orderlift.orderlift_hr.api.appraisal_bridge.on_goal_validate",
    },
    "Appraisal": {
        "before_save": "orderlift.orderlift_hr.api.appraisal_bridge.on_appraisal_before_save",
    },
}

doctype_js = {
    "Container Profile": "public/js/container_profile_form_20260411.js",
    "Delivery Note": "public/js/delivery_note_logistics.js",
    "Purchase Order": "public/js/purchase_order_pricing_alerts_20260417.js",
    "Purchase Receipt": "public/js/purchase_receipt_logistics.js",
    "Portal Customer Group Policy": "public/js/portal_customer_group_policy.js",
    "Portal Quote Request": "public/js/portal_quote_request.js",
    "Item Price": "public/js/item_price_uom_default_20260506a.js",
    "Sales Order": "public/js/sales_order_logistics_20260425d.js",
    # Loaded via doctype_js so setup/refresh fire before the form opens.
    # Keep a query version so Desk fetches the latest static asset after targeted edits.
    "Pricing Sheet": "public/js/pricing_sheet_form_20260501_110.js?v=20260601c",
    "Pricing Benchmark Policy": "public/js/pricing_benchmark_policy_form.js?v=20260601a",
    "Customer": "public/js/customer_tier_mode.js?v=20260601h",
    "Prospect": "public/js/customer_tier_mode.js?v=20260601h",
    "SAV Ticket": "public/js/sav_ticket_v3.js",
    # SIG module — Project form enhancements (QC Template, Geocoding)
    "Project": "public/js/project_sig_20260429c.js",
    "Sales Invoice": "public/js/finance_account_guard_20260501a.js?v=20260501b",
    "Purchase Invoice": "public/js/finance_account_guard_20260501a.js?v=20260501b",
    "Payment Entry": "public/js/finance_account_guard_20260501a.js?v=20260501b",
    "QC Checklist Template": "orderlift_sig/doctype/qc_checklist_template/qc_checklist_template.js",
}

doctype_list_js = {
    "Portal Quote Request": "public/js/portal_quote_request_list.js",
}

extend_doctype_class = {
    "Customer": "orderlift.sales.utils.customer_tier.CustomerGroupFallbackMixin",
    "Contract": "orderlift.crm.extensions.contract.ContractDateValidationMixin",
}

# ---------------------------------------------------------
# Scheduled Tasks
# ---------------------------------------------------------
scheduler_events = {
    "daily": [
        # Check contact schedules and create overdue Tasks
        "orderlift.crm.utils.notification_scheduler.run_daily",
        # Check reorder levels and draft Purchase Orders
        "orderlift.logistics.utils.reorder_manager.check_reorder_levels",
        # Recompute every open Appraisal Cycle's performance snapshots
        "orderlift.orderlift_hr.api.performance.recompute_open_cycles",
    ],
    "weekly": [
        # Flag slow-moving and overstock items for dashboard
        "orderlift.logistics.utils.stock_analyzer.flag_slow_moving_items",
        # Send weekly container load plan efficiency digest to dispatchers
        "orderlift.orderlift_logistics.utils.efficiency_digest.send_weekly_efficiency_digest",
    ],
}

after_migrate = [
    "orderlift.scripts.setup_master_data.after_migrate",
    "orderlift.sales.utils.pricing_setup.after_migrate",
    "orderlift.sales.utils.commission_dashboard_setup.after_migrate",
    "orderlift.logistics.setup.after_migrate",
    "orderlift.orderlift_logistics.setup.after_migrate",
    "orderlift.orderlift_sig.setup.after_migrate",
    "orderlift.orderlift_crm.setup.after_migrate",
    "orderlift.company_scope.after_migrate",
    "orderlift.orderlift_finance.account_governance.after_migrate",
    "orderlift.orderlift_sales.page.sale_financial_dashboard.sale_financial_dashboard.sync_page_roles",
    "orderlift.orderlift_sav.setup.after_migrate",
    "orderlift.orderlift_hr.setup.after_migrate",
    "orderlift.scripts.setup_french_translations.after_migrate",
    "orderlift.scripts.setup_main_dashboard_sidebar.run",
    "orderlift.scripts.ensure_orderlift_admin_permissions.run",
]

on_login = [
    "orderlift.orderlift_client_portal.utils.website.sync_b2b_only_user_type_on_login",
    "orderlift.restricted_user_guard.redirect_on_login",
]

before_request = [
    "orderlift.dashboard_permissions.install_runtime_patches",
    "orderlift.restricted_user_guard.redirect_legacy_crm_page_routes",
    "orderlift.restricted_user_guard.redirect_bare_desk_route",
    "orderlift.orderlift_client_portal.utils.website.redirect_b2b_only_users_from_desk",
    "orderlift.restricted_user_guard.guard_orderlift_menu_routes",
    "orderlift.restricted_user_guard.guard_restricted_routes",
]

# ---------------------------------------------------------
# Permission guards — block system doctypes for restricted users
# ---------------------------------------------------------
has_permission = {
    "Company": "orderlift.company_access.has_company_permission",
    "Account": "orderlift.orderlift_finance.account_governance.has_account_permission",
    "Cost Center": "orderlift.orderlift_finance.account_governance.has_cost_center_permission",
    "Opportunity": "orderlift.company_access.has_company_permission",
    "Quotation": "orderlift.company_access.has_company_permission",
    "Sales Order": "orderlift.company_access.has_company_permission",
    "Sales Invoice": "orderlift.company_access.has_company_permission",
    "Purchase Order": "orderlift.company_access.has_company_permission",
    "Purchase Receipt": "orderlift.company_access.has_company_permission",
    "Purchase Invoice": "orderlift.company_access.has_company_permission",
    "Delivery Note": "orderlift.company_access.has_company_permission",
    "Payment Entry": "orderlift.company_access.has_company_permission",
    "Stock Entry": "orderlift.company_access.has_company_permission",
    "Material Request": "orderlift.company_access.has_company_permission",
    "Request for Quotation": "orderlift.company_access.has_company_permission",
    "Project": "orderlift.company_access.has_company_permission",
    "Sales Commission": "orderlift.company_access.has_company_permission",
    "SAV Ticket": "orderlift.company_access.has_company_permission",
    "Forecast Load Plan": "orderlift.company_access.has_company_permission",
    "Customer": "orderlift.company_access.has_company_permission",
    "Supplier": "orderlift.company_access.has_company_permission",
    "Price List": "orderlift.company_access.has_company_permission",
    "Prospect": "orderlift.company_access.has_company_permission",
    "Lead": "orderlift.company_access.has_company_permission",
    "Pricing Sheet": "orderlift.company_access.has_company_permission",
    "Pricing Scenario": "orderlift.company_access.has_company_permission",
    "Pricing Benchmark Policy": "orderlift.company_access.has_company_permission",
    "Pricing Customs Policy": "orderlift.company_access.has_company_permission",
    "Customer Segmentation Engine": "orderlift.company_access.has_company_permission",
    "Partner Campaign": "orderlift.company_access.has_company_permission",
    "Portal Customer Group Policy": "orderlift.company_access.has_company_permission",
    "Portal Quote Request": "orderlift.company_access.has_company_permission",
    "Training Quiz Attempt": "orderlift.orderlift_hr.api.training.has_permission",
    "Employee Training Progress": "orderlift.orderlift_hr.api.training.has_permission",
    "Performance Metric Snapshot": "orderlift.orderlift_hr.api.performance_permissions.has_permission",
    "Module Def": "orderlift.restricted_user_guard.block_if_restricted",
    "DocType": "orderlift.restricted_user_guard.block_if_restricted",
    "Customize Form": "orderlift.restricted_user_guard.block_if_restricted",
    "System Settings": "orderlift.restricted_user_guard.block_if_restricted",
    "Server Script": "orderlift.restricted_user_guard.block_if_restricted",
    "Custom Field": "orderlift.restricted_user_guard.block_if_restricted",
    "Custom DocPerm": "orderlift.restricted_user_guard.block_if_restricted",
    "Property Setter": "orderlift.restricted_user_guard.block_if_restricted",
    "Client Script": "orderlift.restricted_user_guard.block_if_restricted",
    "Scheduled Job Type": "orderlift.restricted_user_guard.block_if_restricted",
    "Error Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Activity Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Access Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Route History": "orderlift.restricted_user_guard.block_if_restricted",
    "Console Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Module Profile": "orderlift.restricted_user_guard.block_if_restricted",
    "Role Profile": "orderlift.restricted_user_guard.block_if_restricted",
    "Email Account": "orderlift.restricted_user_guard.block_if_restricted",
    "Email Domain": "orderlift.restricted_user_guard.block_if_restricted",
    "Website Settings": "orderlift.restricted_user_guard.block_if_restricted",
    "Web Form": "orderlift.restricted_user_guard.block_if_restricted",
    "Print Format": "orderlift.restricted_user_guard.block_if_restricted",
    "Auto Repeat": "orderlift.restricted_user_guard.block_if_restricted",
    "Prepared Report": "orderlift.restricted_user_guard.block_if_restricted",
    "Installed Application": "orderlift.restricted_user_guard.block_if_restricted",
    "Installed Applications": "orderlift.restricted_user_guard.block_if_restricted",
    "Package": "orderlift.restricted_user_guard.block_if_restricted",
    "Notification Settings": "orderlift.restricted_user_guard.block_if_restricted",
    "RQ Worker": "orderlift.restricted_user_guard.block_if_restricted",
    "RQ Job": "orderlift.restricted_user_guard.block_if_restricted",
    "Scheduled Job Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Recorder": "orderlift.restricted_user_guard.block_if_restricted",
    "API Request Log": "orderlift.restricted_user_guard.block_if_restricted",
    "View Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Patch Log": "orderlift.restricted_user_guard.block_if_restricted",
    "Log Settings": "orderlift.restricted_user_guard.block_if_restricted",
}

permission_query_conditions = {
    "Company": "orderlift.company_access.company_query",
    "Opportunity": "orderlift.company_access.opportunity_query",
    "Quotation": "orderlift.company_access.quotation_query",
    "Sales Order": "orderlift.company_access.sales_order_query",
    "Sales Invoice": "orderlift.company_access.sales_invoice_query",
    "Purchase Order": "orderlift.company_access.purchase_order_query",
    "Purchase Receipt": "orderlift.company_access.purchase_receipt_query",
    "Purchase Invoice": "orderlift.company_access.purchase_invoice_query",
    "Delivery Note": "orderlift.company_access.delivery_note_query",
    "Payment Entry": "orderlift.company_access.payment_entry_query",
    "Stock Entry": "orderlift.company_access.stock_entry_query",
    "Material Request": "orderlift.company_access.material_request_query",
    "Request for Quotation": "orderlift.company_access.request_for_quotation_query",
    "Project": "orderlift.company_access.project_query",
    "Sales Commission": "orderlift.company_access.sales_commission_query",
    "SAV Ticket": "orderlift.company_access.sav_ticket_query",
    "Forecast Load Plan": "orderlift.company_access.forecast_load_plan_query",
    "Customer": "orderlift.company_access.customer_query",
    "Supplier": "orderlift.company_access.supplier_query",
    "Price List": "orderlift.company_access.price_list_query",
    "Prospect": "orderlift.company_access.prospect_query",
    "Lead": "orderlift.company_access.lead_query",
    "Pricing Sheet": "orderlift.company_access.pricing_sheet_query",
    "Pricing Scenario": "orderlift.company_access.pricing_scenario_query",
    "Pricing Benchmark Policy": "orderlift.company_access.pricing_benchmark_policy_query",
    "Pricing Customs Policy": "orderlift.company_access.pricing_customs_policy_query",
    "Customer Segmentation Engine": "orderlift.company_access.customer_segmentation_engine_query",
    "Partner Campaign": "orderlift.company_access.partner_campaign_query",
    "Portal Customer Group Policy": "orderlift.company_access.portal_customer_group_policy_query",
    "Portal Quote Request": "orderlift.company_access.portal_quote_request_query",
    "Training Quiz Attempt": "orderlift.orderlift_hr.api.training.quiz_attempt_query",
    "Employee Training Progress": "orderlift.orderlift_hr.api.training.progress_query",
    "Performance Metric Snapshot": "orderlift.orderlift_hr.api.performance_permissions.snapshot_query",
}

# ---------------------------------------------------------
# Portal (B2B web portal pages)
# ---------------------------------------------------------
website_route_rules = [
    {"from_route": "/b2b-portal", "to_route": "b2b_portal"},
    {"from_route": "/b2b-portal/<path:name>", "to_route": "b2b_portal"},
]

# Roles allowed to access the web portal
website_context = {
    "favicon": "/assets/frappe/images/frappe-favicon.svg",
    "splash_image": "/assets/frappe/images/frappe-framework-logo.svg",
}

get_website_user_home_page = "orderlift.orderlift_client_portal.utils.website.get_portal_home_page"

# ---------------------------------------------------------
# Jinja2 custom filters/functions available in print formats
# and web templates
# ---------------------------------------------------------
jinja = {
    "methods": [
        "orderlift.utils.jinja_helpers.format_currency_fr",
        "orderlift.utils.jinja_helpers.get_company_address",
        "orderlift.utils.jinja_helpers.get_company_info",
    ]
}

# ---------------------------------------------------------
# Override standard Frappe/ERPNext whitelisted methods
# (only if absolutely necessary — prefer doc_events instead)
# ---------------------------------------------------------
# override_whitelisted_methods = {}

# ---------------------------------------------------------
# Naming series defaults (applied via fixtures or migration)
# ---------------------------------------------------------
# These are set on the relevant Doctype records, listed here
# for documentation:
#
#   SAV Ticket       → SAV-.YYYY.-.#####
#   Portal Order     → PO-B2B-.YYYY.-.#####
#   Sales Commission → COM-.YYYY.-.#####
