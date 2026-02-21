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
app_include_css = ["/assets/orderlift/css/orderlift.css"]
app_include_js = ["/assets/orderlift/js/orderlift.js"]

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
        # Auto-create Sales Commission records on invoice submission
        "on_submit": "orderlift.sales.utils.commission_calculator.create_commissions",
        "on_cancel": "orderlift.sales.utils.commission_calculator.cancel_commissions",
    },
    "Sales Order": {
        # Notify stock manager when a sales order is confirmed
        "on_submit": "orderlift.sales.utils.stock_notifier.notify_stock_manager",
    },
    "Item": {
        # Archive cost price into Item Cost History on save when cost changes
        "before_save": "orderlift.sales.utils.cost_history.archive_cost_price",
    },
    "Purchase Receipt": {
        # Move stock to correct warehouse after quality inspection
        "on_submit": "orderlift.logistics.utils.stock_router.route_received_stock",
    },
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
    ],
}

after_migrate = [
    "orderlift.sales.utils.pricing_setup.after_migrate",
]

# ---------------------------------------------------------
# Portal (B2B web portal pages)
# ---------------------------------------------------------
website_route_rules = [
    {"from_route": "/b2b-portal", "to_route": "b2b-portal"},
    {"from_route": "/b2b-portal/<path:name>", "to_route": "b2b-portal"},
    {"from_route": "/project-map", "to_route": "project-map"},
]

# Roles allowed to access the web portal
website_context = {
    "favicon": "/assets/orderlift/images/favicon.ico",
    "splash_image": "/assets/orderlift/images/orderlift_logo.png",
}

# ---------------------------------------------------------
# Jinja2 custom filters/functions available in print formats
# and web templates
# ---------------------------------------------------------
jinja = {
    "methods": [
        "orderlift.utils.jinja_helpers.format_currency_fr",
        "orderlift.utils.jinja_helpers.get_company_address",
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
#   Shipment Plan    → SP-.YYYY.-.#####
#   Portal Order     → PO-B2B-.YYYY.-.#####
#   Sales Commission → COM-.YYYY.-.#####
