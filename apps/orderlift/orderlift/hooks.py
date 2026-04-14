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
    "/assets/orderlift/css/orderlift_logistics.css?v=20260410c",
    "/assets/orderlift/css/clp_dashboard_v4.css",
]
app_include_js = [
    "/assets/orderlift/js/orderlift_bundle.js",
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
    "Container Load Plan": {
        # Validate scenario consistency (flow_scope + source_type + shipping_responsibility)
        "validate": "orderlift.logistics.utils.scenario_guard.validate_container_load_plan",
    },
    "Delivery Trip": {
        # Block Delivery Trip creation for inbound or customer-managed scenarios
        "validate": "orderlift.logistics.utils.scenario_guard.validate_delivery_trip",
    },
}

doctype_js = {
    "Container Profile": "public/js/container_profile_form_20260411.js",
    "Container Load Plan": "public/js/clp_dashboard_v4.js",
    "Delivery Note": "public/js/delivery_note_logistics.js",
    "Purchase Receipt": "public/js/purchase_receipt_logistics.js",
    "Portal Customer Group Policy": "public/js/portal_customer_group_policy.js",
    "Portal Quote Request": "public/js/portal_quote_request.js",
    "Sales Order": "public/js/sales_order_logistics.js",
    # Loaded via doctype_js so setup/refresh fire before the form opens.
    # The file sets window["__orderlift_pricing_sheet_latest_loaded_v6"] = true
    # so the app_include_js global loader skips re-requiring it.
    "Pricing Sheet": "public/js/pricing_sheet_form_20260409_97.js",
    "Pricing Benchmark Policy": "public/js/pricing_benchmark_policy_form.js",
    "Customer": "public/js/customer_tier_mode.js",
    "SAV Ticket": "public/js/sav_ticket_v2.js",
    # SIG module — Project form enhancements (QC Template, Geocoding)
    "Project": "public/js/project_sig.js",
    "QC Checklist Template": "orderlift_sig/doctype/qc_checklist_template/qc_checklist_template.js",
}

doctype_list_js = {
    "Portal Quote Request": "public/js/portal_quote_request_list.js",
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
    "orderlift.scripts.setup_main_dashboard_sidebar.run",
]

on_login = [
    "orderlift.orderlift_client_portal.utils.website.sync_b2b_only_user_type_on_login",
]

before_request = [
    "orderlift.orderlift_client_portal.utils.website.redirect_b2b_only_users_from_desk",
]

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
#   Container Load Plan → CLP-.#####
#   Portal Order     → PO-B2B-.YYYY.-.#####
#   Sales Commission → COM-.YYYY.-.#####
