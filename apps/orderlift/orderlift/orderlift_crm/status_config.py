from __future__ import annotations

import json

import frappe

STATUS_COLOR_OPTIONS = ["Gray", "Blue", "Green", "Orange", "Red", "Purple"]
STATUS_COLOR_OPTIONS_TEXT = "\n".join(STATUS_COLOR_OPTIONS)
UNASSIGNED_STATUS = "__unassigned__"

PIPELINE_QUICK_ACTION_FIELDS = {
    "Opportunity": "custom_opportunity_pipeline_quick_actions",
    "Project": "custom_project_pipeline_quick_actions",
    "Sales Order": "custom_sales_order_pipeline_quick_actions",
    "Forecast Load Plan": "custom_forecast_load_plan_pipeline_quick_actions",
}

PIPELINE_QUICK_ACTIONS = {
    "Opportunity": [
        {
            "key": "pricing-sheet",
            "label": "Pricing Sheet",
            "description": "Create a Pricing Sheet with Opportunity context and items.",
        },
        {
            "key": "quotation",
            "label": "Quotation",
            "description": "Create a Quotation directly from the Opportunity context.",
        },
        {
            "key": "project",
            "label": "Project",
            "description": "Create a Project linked to this Opportunity.",
        },
        {
            "key": "sales-order",
            "label": "Sales Order",
            "description": "Create a Sales Order linked to this Opportunity.",
        },
    ],
    "Project": [
        {
            "key": "sales-order",
            "label": "Sales Order",
            "description": "Create a Sales Order linked to this Project.",
        },
        {
            "key": "purchase-order",
            "label": "Purchase Order",
            "description": "Create a Purchase Order linked to this Project.",
        },
    ],
    "Sales Order": [
        {
            "key": "delivery-note",
            "label": "Delivery Note",
            "description": "Create a Delivery Note from this Sales Order.",
        },
        {
            "key": "sales-invoice",
            "label": "Sales Invoice",
            "description": "Create a Sales Invoice from this Sales Order.",
        },
    ],
    "Forecast Load Plan": [],
}

DEFAULT_PIPELINE_QUICK_ACTIONS = {
    "Opportunity": ["pricing-sheet", "project"],
    "Project": ["sales-order", "purchase-order"],
    "Sales Order": ["delivery-note", "sales-invoice"],
    "Forecast Load Plan": [],
}

LOGISTICS_STATUS_SEEDS = [
    {"label": "Planning", "sequence": 10, "color": "Gray", "is_default": 1},
    {"label": "Ready", "sequence": 20, "color": "Blue", "is_default": 0},
    {"label": "Loading", "sequence": 30, "color": "Orange", "is_default": 0},
    {"label": "In Transit", "sequence": 40, "color": "Purple", "is_default": 0},
    {"label": "Delivered", "sequence": 50, "color": "Green", "is_default": 0},
    {"label": "Cancelled", "sequence": 60, "color": "Red", "is_default": 0},
]

OPPORTUNITY_STAGE_SEEDS = [
    {"label": "1. Demande Client", "sequence": 10, "color": "Blue", "is_default": 1, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "1'. Complément d'information", "sequence": 20, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "2. Prise de mesure en cours", "sequence": 25, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "2. Envoyé conception", "sequence": 30, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "3. Devis validé (interne)", "sequence": 40, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "1''.Visite réalisée", "sequence": 50, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "4. Devis Envoyé au client", "sequence": 60, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "5. Devis Envoyé", "sequence": 70, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "5. Suivi 1", "sequence": 80, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "5'. Suivi 2", "sequence": 90, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "6. Devis rejeté/annulé", "sequence": 100, "color": "Red", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "8. Avance 40% payée", "sequence": 110, "color": "Green", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "Distribution - 1. Demande Client", "display_label": "1. Demande Client", "sequence": 10, "color": "Blue", "is_default": 1, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 2. Prise de mesure en cours", "display_label": "2. Prise de mesure en cours", "sequence": 20, "color": "Purple", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 3. Envoyée conception", "display_label": "3. Envoyée conception", "sequence": 30, "color": "Purple", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 4. Devis validé", "display_label": "4. Devis validé", "sequence": 40, "color": "Blue", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 5. Devis Envoyé", "display_label": "5. Devis Envoyé", "sequence": 50, "color": "Blue", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 7. Devis en cours de révision/négotiation", "display_label": "7. Devis en cours de révision/négotiation", "sequence": 70, "color": "Orange", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 8. Devis approuvé par client", "display_label": "8. Devis approuvé par client", "sequence": 80, "color": "Green", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
    {"label": "Distribution - 9. Avance payée", "display_label": "9. Avance payée", "sequence": 90, "color": "Green", "is_default": 0, "distribution": 1, "installation": 0, "company": "Orderlift Maroc Distribution"},
]

PROJECT_STATUS_SEEDS = [
    {"label": "8. Avance 40% payée", "sequence": 10, "color": "Blue", "is_default": 1, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "9. prise de mesure en cours", "sequence": 20, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "10. Installateur affecté", "sequence": 30, "color": "Purple", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "11. Marchandise livréeau client", "sequence": 40, "color": "Orange", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "12. Paiement 2 réalisé", "sequence": 50, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "13. Installation complétée", "sequence": 60, "color": "Green", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "14. Paiement 3 réalisé", "sequence": 70, "color": "Blue", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "15. Mise en marche", "sequence": 80, "color": "Green", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
    {"label": "16. Paiement final fait", "sequence": 90, "color": "Green", "is_default": 0, "distribution": 0, "installation": 1, "company": "Orderlift Maroc Installation"},
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
        "display_label_field": "custom_display_label",
        "company_field": "custom_company",
        "sequence_field": "custom_sequence",
        "color_field": "custom_color",
        "active_field": "custom_is_active",
        "default_field": "custom_is_default",
        "distribution_field": "custom_applies_distribution",
        "installation_field": "custom_applies_installation",
        "assigned_user_field": "custom_assigned_user",
        "todo_priority_field": "custom_todo_priority",
        "auto_collapse_field": "custom_auto_collapse",
        "required_checks_field": "custom_required_checks",
        "confirmation_message_field": "custom_confirmation_message",
        "auto_close_opportunity_field": "custom_auto_close_opportunity",
        "target_doctype": "Opportunity",
        "target_field": "sales_stage",
        "legacy_label": "ERP Status",
        "legacy_field": "status",
        "seeds": OPPORTUNITY_STAGE_SEEDS,
        "show_flow_fields": False,
    },
    "Project": {
        "field_label": "Project Status",
        "page_title": "Project Status",
        "status_doctype": "Project Status",
        "label_field": "status_label",
        "display_label_field": "display_label",
        "company_field": "company",
        "sequence_field": "sequence",
        "color_field": "color",
        "active_field": "is_active",
        "default_field": "is_default",
        "distribution_field": "applies_distribution",
        "installation_field": "applies_installation",
        "assigned_user_field": "assigned_user",
        "todo_priority_field": "todo_priority",
        "auto_collapse_field": "custom_auto_collapse",
        "required_checks_field": "custom_required_checks",
        "confirmation_message_field": "custom_confirmation_message",
        "target_doctype": "Project",
        "target_field": "custom_project_status",
        "legacy_label": "ERP Project Status",
        "legacy_field": "status",
        "seeds": PROJECT_STATUS_SEEDS,
        "show_flow_fields": False,
    },
    "Sales Order": {
        "field_label": "Order Status",
        "page_title": "Sales Order Status",
        "status_doctype": "Orderlift Order Status",
        "label_field": "status_label",
        "display_label_field": "display_label",
        "company_field": "company",
        "sequence_field": "sequence",
        "color_field": "color",
        "active_field": "is_active",
        "default_field": "is_default",
        "distribution_field": "applies_distribution",
        "installation_field": "applies_installation",
        "assigned_user_field": "assigned_user",
        "todo_priority_field": "todo_priority",
        "auto_collapse_field": "custom_auto_collapse",
        "required_checks_field": "custom_required_checks",
        "confirmation_message_field": "custom_confirmation_message",
        "target_doctype": "Sales Order",
        "target_field": "custom_orderlift_order_status",
        "legacy_label": "ERP Sales Status",
        "legacy_field": "status",
        "seeds": SALES_ORDER_STATUS_SEEDS,
        "show_flow_fields": False,
    },
    "Forecast Load Plan": {
        "field_label": "Logistics Status",
        "page_title": "Shipment Plan Status",
        "status_doctype": "Logistics Pipeline Status",
        "label_field": "status_label",
        "display_label_field": "display_label",
        "company_field": "company",
        "fixed_status_values": True,
        "sequence_field": "sequence",
        "color_field": "color",
        "active_field": "is_active",
        "default_field": "is_default",
        "assigned_user_field": "assigned_user",
        "todo_priority_field": "todo_priority",
        "auto_collapse_field": "custom_auto_collapse",
        "required_checks_field": None,
        "confirmation_message_field": "confirmation_message",
        "target_doctype": "Forecast Load Plan",
        "target_field": "status",
        "legacy_label": "Fixed Lifecycle Status",
        "legacy_field": None,
        "seeds": LOGISTICS_STATUS_SEEDS,
        "show_flow_fields": False,
        "allow_create": False,
        "allow_delete": False,
        "allow_rename": False,
    },
}


def pipeline_quick_action_field(document_type: str) -> str:
    return PIPELINE_QUICK_ACTION_FIELDS.get(document_type, "")


def pipeline_quick_action_catalog(document_type: str) -> list[dict]:
    return [dict(action) for action in PIPELINE_QUICK_ACTIONS.get(document_type, [])]


def get_company_pipeline_quick_action_keys(document_type: str, company: str | None = None) -> list[str]:
    fieldname = pipeline_quick_action_field(document_type)
    catalog = pipeline_quick_action_catalog(document_type)
    allowed_keys = {action["key"] for action in catalog}
    default_keys = [key for key in DEFAULT_PIPELINE_QUICK_ACTIONS.get(document_type, []) if key in allowed_keys]
    company = (company or "").strip()
    if not fieldname or not company or not frappe.db.exists("Company", company):
        return default_keys
    if not getattr(frappe.db, "has_column", None) or not frappe.db.has_column("Company", fieldname):
        return default_keys

    raw = frappe.db.get_value("Company", company, fieldname)
    if not raw:
        return default_keys
    try:
        values = json.loads(raw)
    except Exception:
        return default_keys
    if not isinstance(values, list):
        return default_keys

    seen = set()
    out = []
    for value in values:
        key = str(value or "").strip()
        if not key or key in seen or key not in allowed_keys:
            continue
        seen.add(key)
        out.append(key)
    return out


def get_company_pipeline_quick_actions(document_type: str, company: str | None = None) -> list[dict]:
    selected = set(get_company_pipeline_quick_action_keys(document_type, company=company))
    return [action for action in pipeline_quick_action_catalog(document_type) if action["key"] in selected]


def save_company_pipeline_quick_action_keys(document_type: str, company: str, keys: list[str] | tuple[str, ...]) -> list[str]:
    company = (company or "").strip()
    if not company or not frappe.db.exists("Company", company):
        frappe.throw(frappe._("Company {0} was not found.").format(company or ""))
    fieldname = pipeline_quick_action_field(document_type)
    if not fieldname:
        return []
    if not getattr(frappe.db, "has_column", None) or not frappe.db.has_column("Company", fieldname):
        return []
    allowed_order = [action["key"] for action in pipeline_quick_action_catalog(document_type)]
    requested = {str(key or "").strip() for key in (keys or []) if str(key or "").strip()}
    clean = [key for key in allowed_order if key in requested]
    frappe.db.set_value("Company", company, fieldname, json.dumps(clean), update_modified=False)
    return clean
