from __future__ import annotations

STATUS_COLOR_OPTIONS = ["Gray", "Blue", "Green", "Orange", "Red", "Purple"]
STATUS_COLOR_OPTIONS_TEXT = "\n".join(STATUS_COLOR_OPTIONS)
UNASSIGNED_STATUS = "__unassigned__"

OPPORTUNITY_STAGE_SEEDS = [
    {"label": "New", "sequence": 10, "color": "Blue", "is_default": 1, "distribution": 1, "installation": 1},
    {"label": "Qualified", "sequence": 20, "color": "Blue", "is_default": 0, "distribution": 1, "installation": 1},
    {"label": "Study Requested", "sequence": 30, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Study Done", "sequence": 40, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Site Visit", "sequence": 50, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Quotation Sent", "sequence": 60, "color": "Blue", "is_default": 0, "distribution": 1, "installation": 1},
    {"label": "Negotiation", "sequence": 70, "color": "Orange", "is_default": 0, "distribution": 1, "installation": 1},
    {"label": "Won / Project", "sequence": 80, "color": "Green", "is_default": 0, "distribution": 1, "installation": 1},
    {"label": "Lost", "sequence": 90, "color": "Red", "is_default": 0, "distribution": 1, "installation": 1},
]

PROJECT_STATUS_SEEDS = [
    {"label": "Advance Paid", "sequence": 10, "color": "Blue", "is_default": 1, "distribution": 0, "installation": 1},
    {"label": "Purchasing", "sequence": 20, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "First Delivery", "sequence": 30, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Final Payment", "sequence": 40, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Final Delivery", "sequence": 50, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Installation Scheduled", "sequence": 60, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Installation", "sequence": 70, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Installed", "sequence": 80, "color": "Green", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Completed", "sequence": 90, "color": "Green", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Blocked", "sequence": 100, "color": "Red", "is_default": 0, "distribution": 0, "installation": 1},
    {"label": "Cancelled", "sequence": 110, "color": "Gray", "is_default": 0, "distribution": 0, "installation": 1},
]

SALES_ORDER_STATUS_SEEDS = [
    {"label": "Confirmed", "sequence": 10, "color": "Blue", "is_default": 1, "distribution": 1, "installation": 0},
    {"label": "Advance Paid", "sequence": 20, "color": "Blue", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Purchasing", "sequence": 30, "color": "Purple", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Ready to Deliver", "sequence": 40, "color": "Orange", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Delivering", "sequence": 50, "color": "Orange", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Final Payment", "sequence": 60, "color": "Blue", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Delivered", "sequence": 70, "color": "Green", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Completed", "sequence": 80, "color": "Green", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Blocked", "sequence": 90, "color": "Red", "is_default": 0, "distribution": 1, "installation": 0},
    {"label": "Cancelled", "sequence": 100, "color": "Gray", "is_default": 0, "distribution": 1, "installation": 0},
]

STATUS_SOURCES = {
    "Opportunity": {
        "field_label": "Opportunity Status",
        "page_title": "Opportunity Status",
        "status_doctype": "Sales Stage",
        "label_field": "stage_name",
        "sequence_field": "custom_sequence",
        "color_field": "custom_color",
        "active_field": "custom_is_active",
        "default_field": "custom_is_default",
        "distribution_field": "custom_applies_distribution",
        "installation_field": "custom_applies_installation",
        "target_doctype": "Opportunity",
        "target_field": "sales_stage",
        "legacy_label": "ERP Status",
        "legacy_field": "status",
        "seeds": OPPORTUNITY_STAGE_SEEDS,
    },
    "Project": {
        "field_label": "Project Status",
        "page_title": "Project Status",
        "status_doctype": "Project Status",
        "label_field": "status_label",
        "sequence_field": "sequence",
        "color_field": "color",
        "active_field": "is_active",
        "default_field": "is_default",
        "distribution_field": "applies_distribution",
        "installation_field": "applies_installation",
        "target_doctype": "Project",
        "target_field": "custom_project_status",
        "legacy_label": "ERP Project Status",
        "legacy_field": "status",
        "seeds": PROJECT_STATUS_SEEDS,
    },
    "Sales Order": {
        "field_label": "Order Status",
        "page_title": "Sales Order Status",
        "status_doctype": "Orderlift Order Status",
        "label_field": "status_label",
        "sequence_field": "sequence",
        "color_field": "color",
        "active_field": "is_active",
        "default_field": "is_default",
        "distribution_field": "applies_distribution",
        "installation_field": "applies_installation",
        "target_doctype": "Sales Order",
        "target_field": "custom_orderlift_order_status",
        "legacy_label": "ERP Sales Status",
        "legacy_field": "status",
        "seeds": SALES_ORDER_STATUS_SEEDS,
    },
}
