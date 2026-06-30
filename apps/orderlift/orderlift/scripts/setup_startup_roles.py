from __future__ import annotations

import json

import frappe
from frappe.utils import cint

from orderlift.menu_access import sync_menu_access_rules
from orderlift.menu_registry import menu_item_by_key
from orderlift.startup_roles import (
    AGENT_PRICING_MANAGER_ROLE,
    CAMPAIGN_MANAGER_ROLE,
    COMMERCIAL_AGENT_COORDINATOR_ROLE,
    COMMERCIAL_AGENT_PARTNER_ROLE,
    COMMERCIAL_AGENT_POINT_OF_SALE_ROLE,
    COMMERCIAL_AGENT_ROLE,
    COMMISSION_MANAGER_ROLE,
    DASHBOARD_MANAGER_ROLE,
    ITEM_MASTER_EDITOR_ROLE,
    OPPORTUNITY_ALL_ACCESS_ROLE,
    OPPORTUNITY_ASSIGNER_ROLE,
    PAYMENT_VALIDATOR_ROLE,
    QUOTATION_CREATOR_ROLE,
    STARTUP_ROLES,
    STOCK_QUANTITY_VIEWER_ROLE,
)


READ_ONLY = {"read": 1, "report": 1, "print": 1, "email": 1}
READ_SELECT = {"read": 1, "select": 1}
READ_WRITE_CREATE = {"read": 1, "write": 1, "create": 1, "report": 1, "print": 1, "email": 1}
READ_WRITE = {"read": 1, "write": 1, "report": 1, "print": 1, "email": 1}
FULL_NON_DELETE = {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "import": 1, "print": 1, "email": 1}

COMMERCIAL_AGENT_PERMISSIONS = {
    "Item": READ_ONLY,
    "Opportunity": READ_WRITE_CREATE,
    "Pricing Sheet": READ_WRITE_CREATE,
    "Quotation": READ_WRITE_CREATE,
    "Price List": READ_SELECT,
    "Sales Commission": READ_ONLY,
    "Customer": READ_ONLY,
    "Prospect": READ_ONLY,
    "Lead": READ_ONLY,
}

SALES_MANAGER_PERMISSIONS = {
    "Opportunity": READ_WRITE_CREATE,
    "Pricing Sheet": READ_WRITE_CREATE,
    "Quotation": READ_WRITE_CREATE,
    "Sales Order": READ_WRITE_CREATE,
    "Sales Commission": READ_WRITE,
    "Customer": READ_WRITE_CREATE,
    "Prospect": READ_WRITE_CREATE,
    "Lead": READ_WRITE_CREATE,
    "Agent Pricing Rules": READ_ONLY,
}

EXECUTIVE_READ_PERMISSIONS = {
    "Opportunity": READ_ONLY,
    "Pricing Sheet": READ_ONLY,
    "Quotation": READ_ONLY,
    "Sales Order": READ_ONLY,
    "Project": READ_ONLY,
    "Sales Commission": READ_ONLY,
    "Customer": READ_ONLY,
    "Supplier": READ_ONLY,
    "Item": READ_ONLY,
    "Item Price": READ_ONLY,
    "Price List": READ_ONLY,
    "Sales Invoice": READ_ONLY,
    "Purchase Invoice": READ_ONLY,
    "Payment Entry": READ_ONLY,
    "Forecast Load Plan": READ_ONLY,
    "SAV Ticket": READ_ONLY,
}

DOCTYPE_PERMISSIONS = {
    "Orderlift Executive": EXECUTIVE_READ_PERMISSIONS,
    "Sales Distribution Manager": SALES_MANAGER_PERMISSIONS,
    "Sales Installation Manager": {**SALES_MANAGER_PERMISSIONS, "Project": READ_WRITE_CREATE, "Contract": READ_WRITE_CREATE},
    COMMERCIAL_AGENT_ROLE: COMMERCIAL_AGENT_PERMISSIONS,
    COMMERCIAL_AGENT_PARTNER_ROLE: COMMERCIAL_AGENT_PERMISSIONS,
    COMMERCIAL_AGENT_COORDINATOR_ROLE: COMMERCIAL_AGENT_PERMISSIONS,
    COMMERCIAL_AGENT_POINT_OF_SALE_ROLE: COMMERCIAL_AGENT_PERMISSIONS,
    "Project Manager": {
        "Project": READ_WRITE_CREATE,
        "Task": READ_WRITE_CREATE,
        "Timesheet": READ_WRITE_CREATE,
        "Contract": READ_WRITE_CREATE,
        "SAV Ticket": READ_WRITE_CREATE,
        "Sales Order": READ_ONLY,
        "Opportunity": READ_ONLY,
        "Forecast Load Plan": READ_ONLY,
    },
    "Pricing Import Manager": {
        "Item": READ_ONLY,
        "Item Price": FULL_NON_DELETE,
        "Price List": READ_WRITE_CREATE,
        "Pricing Sheet": READ_WRITE_CREATE,
        "Pricing Builder": READ_WRITE_CREATE,
        "Pricing Scenario": READ_WRITE_CREATE,
        "Pricing Benchmark Policy": READ_WRITE_CREATE,
        "Pricing Customs Policy": READ_WRITE_CREATE,
        "Agent Pricing Rules": READ_WRITE_CREATE,
        "Data Import": READ_WRITE_CREATE,
    },
    "Logistics Manager": {
        "Forecast Load Plan": READ_WRITE_CREATE,
        "Delivery Note": READ_WRITE_CREATE,
        "Purchase Receipt": READ_WRITE_CREATE,
        "Stock Entry": READ_WRITE_CREATE,
        "Material Request": READ_WRITE_CREATE,
        "Request for Quotation": READ_WRITE_CREATE,
        "Purchase Order": READ_ONLY,
        "Item": READ_ONLY,
        "Container Profile": READ_WRITE_CREATE,
    },
    "BET Technical User": {
        "Item": READ_ONLY,
        "Opportunity": READ_ONLY,
        "Project": READ_ONLY,
        "Dimensioning Set": READ_WRITE_CREATE,
        "QC Checklist Template": READ_WRITE_CREATE,
    },
    "Finance Admin": {
        "Payment Entry": READ_WRITE_CREATE,
        "Sales Invoice": READ_WRITE_CREATE,
        "Purchase Invoice": READ_WRITE_CREATE,
        "Sales Order": READ_ONLY,
        "Purchase Order": READ_ONLY,
        "Sales Commission": READ_WRITE,
        "Customer": READ_ONLY,
        "Supplier": READ_ONLY,
    },
    "HR Training Manager": {
        "Training Program": READ_WRITE_CREATE,
        "Training Level": READ_WRITE_CREATE,
        "Training Module": READ_WRITE_CREATE,
        "Training Quiz": READ_WRITE_CREATE,
        "Training Quiz Question": READ_WRITE_CREATE,
        "Training Quiz Attempt": READ_ONLY,
        "Performance Metric": READ_WRITE_CREATE,
        "Performance Profile": READ_WRITE_CREATE,
        "Performance Metric Snapshot": READ_ONLY,
        "Appraisal": READ_WRITE_CREATE,
        "Appraisal Cycle": READ_WRITE_CREATE,
        "Goal": READ_WRITE_CREATE,
        "Employee": READ_ONLY,
    },
    "Sales User": {
        "Quotation": READ_ONLY,
        "Opportunity": READ_WRITE_CREATE,
    },
    QUOTATION_CREATOR_ROLE: {
        "Quotation": READ_WRITE_CREATE,
        "Price List": READ_SELECT,
    },
    OPPORTUNITY_ALL_ACCESS_ROLE: {
        "Opportunity": READ_ONLY,
    },
    COMMISSION_MANAGER_ROLE: {
        "Sales Commission": READ_WRITE,
    },
    ITEM_MASTER_EDITOR_ROLE: {
        "Item": {**READ_WRITE_CREATE, "import": 1, "export": 1},
        "Item Price": {**READ_WRITE_CREATE, "import": 1, "export": 1},
        "Price List": READ_WRITE_CREATE,
    },
    AGENT_PRICING_MANAGER_ROLE: {
        "Agent Pricing Rules": READ_WRITE_CREATE,
    },
    CAMPAIGN_MANAGER_ROLE: {
        "Partner Campaign": READ_WRITE_CREATE,
        "Partner Campaign Target": READ_WRITE_CREATE,
    },
    PAYMENT_VALIDATOR_ROLE: {
        "Payment Entry": READ_WRITE,
        "Sales Invoice": READ_ONLY,
    },
    STOCK_QUANTITY_VIEWER_ROLE: {
        "Item": READ_ONLY,
    },
}

STALE_DOCTYPE_PERMISSIONS = {
    "Sales Distribution Manager": ["Partner Campaign", "Partner Campaign Target"],
    "Sales Installation Manager": ["Partner Campaign", "Partner Campaign Target"],
}

MENU_ROLE_MAP = {
    "Orderlift Executive": [
        "home.dashboard",
        "crm.crm_dashboard",
        "crm.opportunity_pipeline",
        "sales.pricing_dashboard",
        "sales.sales_order_pipeline",
        "sales.project_pipeline",
        "finance.sale_financial_dashboard",
        "finance.sales_payment_summary",
        "items.catalogue_prix_articles",
    ],
    "Sales Distribution Manager": [
        "crm.crm_dashboard",
        "crm.opportunity_pipeline",
        "crm.opportunity",
        "crm.customer",
        "sales.pricing_sheets",
        "sales.quotation",
        "sales.sales_order",
        "sales.commission_dashboard",
        "items.catalogue_prix_articles",
    ],
    "Sales Installation Manager": [
        "crm.crm_dashboard",
        "crm.opportunity_pipeline",
        "crm.opportunity",
        "crm.customer",
        "sales.pricing_sheets",
        "sales.quotation",
        "sales.project_pipeline",
        "projects.project_pipeline",
        "projects.contract",
        "sales.commission_dashboard",
        "items.catalogue_prix_articles",
    ],
    COMMERCIAL_AGENT_ROLE: [
        "crm.opportunity_pipeline",
        "crm.opportunity",
        "sales.pricing_sheets",
        "sales.commission_dashboard",
        "sales.commissions",
        "items.catalogue_prix_articles",
    ],
    COMMERCIAL_AGENT_PARTNER_ROLE: [
        "crm.opportunity_pipeline",
        "sales.pricing_sheets",
        "sales.commission_dashboard",
        "items.catalogue_prix_articles",
    ],
    COMMERCIAL_AGENT_COORDINATOR_ROLE: [
        "crm.opportunity_pipeline",
        "crm.opportunity",
        "sales.pricing_sheets",
        "sales.commission_dashboard",
        "items.catalogue_prix_articles",
    ],
    COMMERCIAL_AGENT_POINT_OF_SALE_ROLE: [
        "crm.opportunity_pipeline",
        "crm.opportunity",
        "sales.pricing_sheets",
        "sales.quotation",
        "sales.commission_dashboard",
        "items.catalogue_prix_articles",
    ],
    QUOTATION_CREATOR_ROLE: ["sales.quotation"],
    ITEM_MASTER_EDITOR_ROLE: ["items.item", "items.item_price", "items.price_list"],
    AGENT_PRICING_MANAGER_ROLE: ["policies.agent_rules"],
    CAMPAIGN_MANAGER_ROLE: ["crm.campaign_manager", "crm.campaign_builder"],
    DASHBOARD_MANAGER_ROLE: ["home.dashboard", "crm.crm_dashboard", "sales.pricing_dashboard"],
    COMMISSION_MANAGER_ROLE: ["sales.commission_dashboard", "sales.commissions"],
    "Purchase Manager": [
        "purchasing.suppliers",
        "purchasing.material_request",
        "purchasing.rfq",
        "purchasing.purchase_order",
        "purchasing.purchase_receipt",
        "items.item",
        "items.item_price",
    ],
    "Stock Manager": [
        "stock.dashboard",
        "stock.balance",
        "stock.ledger",
        "items.item",
        "items.item_category",
        "items.item_group",
        "purchasing.delivery_note",
        "purchasing.pick_list",
    ],
    "Project Manager": [
        "projects.project_pipeline",
        "projects.sales_order_pipeline",
        "projects.contract",
        "projects.tasks",
        "projects.timesheet",
        "sav.tickets",
    ],
    "Pricing Import Manager": [
        "items.item_price",
        "items.price_list",
        "items.buying_price_builder",
        "items.static_pricing_builder",
        "sales.pricing_sheets",
        "policies.customs_policy",
        "policies.expenses_policy",
        "policies.margin_benchmark",
        "policies.agent_rules",
    ],
    "Logistics Manager": [
        "logistics.pipeline",
        "logistics.container_planning",
        "logistics.container_profiles",
        "purchasing.delivery_note",
        "purchasing.purchase_receipt",
        "purchasing.material_request",
        "stock.dashboard",
    ],
    "BET Technical User": [
        "items.item",
        "items.dimensioning_sets",
        "crm.opportunity_pipeline",
        "projects.project_pipeline",
        "sig.qc_templates",
    ],
    "Finance Admin": [
        "finance.sale_financial_dashboard",
        "finance.sales_payment_summary",
        "finance.sales_invoices",
        "finance.purchase_invoices",
        "finance.payments",
        "sales.commission_dashboard",
    ],
    "HR Training Manager": [
        "hr.dashboard",
        "training.cycle_dashboard",
        "training.performance_metrics",
        "training.performance_profiles",
        "training.performance_snapshots",
        "training.appraisals",
        "training.appraisal_cycles",
        "training.goals",
        "training.programs",
        "training.levels",
        "training.modules",
        "training.quizzes",
        "training.quiz_questions",
        "training.quiz_attempts",
    ],
}


@frappe.whitelist()
def run(assign_existing_sales_users: int = 0) -> dict:
    frappe.only_for("System Manager")
    results = {
        "roles": [],
        "custom_docperms": [],
        "removed_custom_docperms": [],
        "menu_rules": [],
        "page_roles": [],
        "assigned_roles": [],
    }

    for role_name in STARTUP_ROLES:
        _ensure_role(role_name, results)

    for role_name, doctype_permissions in DOCTYPE_PERMISSIONS.items():
        if not frappe.db.exists("Role", role_name):
            continue
        for doctype, flags in doctype_permissions.items():
            if frappe.db.exists("DocType", doctype):
                _ensure_custom_docperm(doctype, role_name, _with_default_flags(flags), results)

    _remove_stale_custom_docperms(results)

    _ensure_menu_roles(results)

    if cint(assign_existing_sales_users):
        _assign_role_to_sales_users(QUOTATION_CREATOR_ROLE, results)

    frappe.clear_cache()
    frappe.db.commit()
    return results


def _ensure_role(role_name: str, results: dict) -> None:
    if frappe.db.exists("Role", role_name):
        action = "exists"
    else:
        role = frappe.new_doc("Role")
        role.role_name = role_name
        if role.meta.get_field("desk_access"):
            role.desk_access = 1
        if role.meta.get_field("is_custom"):
            role.is_custom = 1
        role.insert(ignore_permissions=True)
        action = "created"
    results["roles"].append({"role": role_name, "action": action})


def _ensure_custom_docperm(doctype: str, role: str, values: dict, results: dict) -> None:
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    existing = frappe.db.exists("Custom DocPerm", filters)
    if existing:
        frappe.db.set_value("Custom DocPerm", existing, values)
        action = "updated"
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 0,
                **values,
            }
        )
        doc.insert(ignore_permissions=True)
        action = "created"
    results["custom_docperms"].append({"doctype": doctype, "role": role, "action": action})


def _remove_stale_custom_docperms(results: dict) -> None:
    for role, doctypes in STALE_DOCTYPE_PERMISSIONS.items():
        for doctype in doctypes:
            filters = {"parent": doctype, "role": role, "permlevel": 0}
            doc_name = frappe.db.exists("Custom DocPerm", filters)
            if not doc_name:
                continue
            frappe.delete_doc("Custom DocPerm", doc_name, ignore_permissions=True)
            results["removed_custom_docperms"].append({"doctype": doctype, "role": role, "name": doc_name})


def _ensure_menu_roles(results: dict) -> None:
    sync_menu_access_rules()
    for role, menu_keys in MENU_ROLE_MAP.items():
        for menu_key in menu_keys:
            name = frappe.db.exists("Orderlift Menu Access Rule", menu_key) or frappe.db.exists(
                "Orderlift Menu Access Rule",
                {"menu_key": menu_key},
            )
            if not name:
                continue
            current = frappe.db.get_value("Orderlift Menu Access Rule", name, "allowed_roles_json") or "[]"
            roles = _clean_list(current)
            if role not in roles:
                roles.append(role)
                frappe.db.set_value("Orderlift Menu Access Rule", name, "allowed_roles_json", json.dumps(roles))
                action = "updated"
            else:
                action = "exists"
            results["menu_rules"].append({"menu_key": menu_key, "role": role, "action": action})
            _ensure_link_role(menu_key, role, results)


def _ensure_link_role(menu_key: str, role: str, results: dict) -> None:
    item = menu_item_by_key(menu_key)
    if not item or item.get("link_type") not in {"Page", "Report"} or not item.get("link_to"):
        return
    parenttype = item["link_type"]
    parent = item["link_to"]
    if not frappe.db.exists(parenttype, parent):
        return
    filters = {"parenttype": parenttype, "parent": parent, "role": role}
    if frappe.db.exists("Has Role", filters):
        action = "exists"
    else:
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parenttype": parenttype,
                "parent": parent,
                "parentfield": "roles",
                "role": role,
            }
        ).insert(ignore_permissions=True)
        action = "created"
    results["page_roles"].append({"parenttype": parenttype, "parent": parent, "role": role, "action": action})


def _assign_role_to_sales_users(role: str, results: dict) -> None:
    for row in frappe.get_all("Has Role", filters={"role": "Sales User", "parenttype": "User"}, fields=["parent"]):
        user = row.parent
        if not user or user in {"Administrator", "Guest"} or not frappe.db.exists("User", user):
            continue
        if frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": role}):
            action = "exists"
        else:
            frappe.get_doc(
                {
                    "doctype": "Has Role",
                    "parenttype": "User",
                    "parent": user,
                    "parentfield": "roles",
                    "role": role,
                }
            ).insert(ignore_permissions=True)
            action = "created"
        results["assigned_roles"].append({"user": user, "role": role, "action": action})


def _with_default_flags(values: dict) -> dict:
    defaults = {
        "read": 0,
        "select": 0,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "if_owner": 0,
        "print": 0,
        "email": 0,
    }
    return {**defaults, **values}


def _clean_list(value) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value or "[]")
        except Exception:
            value = [value]
    out = []
    seen = set()
    for item in value or []:
        item = (str(item or "")).strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out
