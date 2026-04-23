app_name = "orderlift"
app_title = "Orderlift"
app_publisher = "Syntax Line"
app_description = "Custom ERP modules for Orderlift — multi-company elevator parts management"
app_email = "contact@syntaxline.dev"
app_license = "MIT"
app_version = "1.0.0"

# Boot — rename ERPNext → Orderlift in sidebar subtitle
extend_bootinfo = "orderlift.boot.extend_bootinfo"

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
]
app_include_js = [
    "/assets/orderlift/js/orderlift_bundle_20260422.js",
    "/assets/orderlift/js/sidebar_logo_fix_20260415b.js",
    "/assets/orderlift/js/refresh_stability_fix_20260415.js",
    "/assets/orderlift/js/desk_entry_redirect_20260422.js",
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
                    "Stock Manager",
                    "Sales Manager",
                    "Orderlift Commercial",
                    "Orderlift Technician",
                    "Orderlift Accountant",
                    "B2B Portal Client",
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
        # Update Sales Commission approval state from invoice payment status
        "on_submit": "orderlift.sales.utils.commission_calculator.sync_commissions_from_invoice",
        "on_update_after_submit": "orderlift.sales.utils.commission_calculator.sync_commissions_from_invoice",
        "on_cancel": "orderlift.sales.utils.commission_calculator.cancel_commissions",
    },
    "Sales Order": {
        # Notify stock manager when a sales order is confirmed
        # Also warn if linked installation project has a Blocked QC (SIG)
        "on_submit": [
            "orderlift.sales.utils.commission_calculator.create_sales_order_commissions",
            "orderlift.sales.utils.stock_notifier.notify_stock_manager",
            "orderlift.orderlift_sig.utils.project_status_guard.on_sales_order_submit",
        ],
        "on_cancel": "orderlift.sales.utils.commission_calculator.cancel_sales_order_commissions",
    },
    "Item": {
        # Archive cost price into Item Cost History on save when cost changes
        "before_save": "orderlift.sales.utils.cost_history.archive_cost_price",
        # Validate packaging profiles (single default, active fields, no duplicates)
        "validate": "orderlift.orderlift_logistics.utils.packaging_validation.validate_item_packaging_profiles",
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
    },
    "SAV Ticket": {
        # Notify assigned technician when ticket status changes to Assigned
        "on_update": "orderlift.orderlift_sav.doctype.sav_ticket.sav_ticket.on_status_change",
    },
    "Project": {
        # Recalculate QC status + enforce completion guard (SIG module)
        "before_save": [
            "orderlift.orderlift_sig.utils.project_qc.on_project_save",
            "orderlift.orderlift_sig.utils.project_status_guard.before_project_status_change",
        ],
    },
    "Delivery Trip": {
        # Block Delivery Trip creation for inbound or customer-managed scenarios
        "validate": "orderlift.logistics.utils.scenario_guard.validate_delivery_trip",
    },
}

doctype_js = {
    "Container Profile": "public/js/container_profile_form_20260411.js",
    "Delivery Note": "public/js/delivery_note_logistics.js",
    "Purchase Order": "public/js/purchase_order_pricing_alerts_20260417.js",
    "Purchase Receipt": "public/js/purchase_receipt_logistics.js",
    "Portal Customer Group Policy": "public/js/portal_customer_group_policy.js",
    "Portal Quote Request": "public/js/portal_quote_request.js",
    "Sales Order": "public/js/sales_order_logistics.js",
    # Loaded via doctype_js so setup/refresh fire before the form opens.
    # Use a versioned filename here instead of a query string because Frappe
    # loads doctype_js assets more reliably as plain paths.
    "Pricing Sheet": "public/js/pricing_sheet_form_20260501_110.js",
    "Pricing Benchmark Policy": "public/js/pricing_benchmark_policy_form.js",
    "Customer": "public/js/customer_tier_mode.js",
    "SAV Ticket": "public/js/sav_ticket_v3.js",
    # SIG module — Project form enhancements (QC Template, Geocoding)
    "Project": "public/js/project_sig.js",
    "QC Checklist Template": "orderlift_sig/doctype/qc_checklist_template/qc_checklist_template.js",
}

doctype_list_js = {
    "Portal Quote Request": "public/js/portal_quote_request_list.js",
}

extend_doctype_class = {
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
    ],
    "weekly": [
        # Flag slow-moving and overstock items for dashboard
        "orderlift.logistics.utils.stock_analyzer.flag_slow_moving_items",
        # Send weekly container load plan efficiency digest to dispatchers
        "orderlift.orderlift_logistics.utils.efficiency_digest.send_weekly_efficiency_digest",
    ],
}

after_migrate = [
    "orderlift.sales.utils.pricing_setup.after_migrate",
    "orderlift.sales.utils.commission_dashboard_setup.after_migrate",
    "orderlift.logistics.setup.after_migrate",
    "orderlift.orderlift_logistics.setup.after_migrate",
    "orderlift.orderlift_sig.setup.after_migrate",
    "orderlift.orderlift_sav.setup.after_migrate",
    "orderlift.scripts.setup_main_dashboard_sidebar.run",
]

on_login = [
    "orderlift.orderlift_client_portal.utils.website.sync_b2b_only_user_type_on_login",
    "orderlift.restricted_user_guard.redirect_on_login",
]

before_request = [
    "orderlift.dashboard_permissions.install_runtime_patches",
    "orderlift.restricted_user_guard.redirect_bare_desk_route",
    "orderlift.orderlift_client_portal.utils.website.redirect_b2b_only_users_from_desk",
    "orderlift.restricted_user_guard.guard_restricted_routes",
]

# ---------------------------------------------------------
# Permission guards — block system doctypes for restricted users
# ---------------------------------------------------------
has_permission = {
    "Module Def": "orderlift.restricted_user_guard.block_if_restricted",
    "DocType": "orderlift.restricted_user_guard.block_if_restricted",
    "Customize Form": "orderlift.restricted_user_guard.block_if_restricted",
    "System Settings": "orderlift.restricted_user_guard.block_if_restricted",
    "Server Script": "orderlift.restricted_user_guard.block_if_restricted",
    "Data Import": "orderlift.restricted_user_guard.block_if_restricted",
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
    "User Permission": "orderlift.restricted_user_guard.block_if_restricted",
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
