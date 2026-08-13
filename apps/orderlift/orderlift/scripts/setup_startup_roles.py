from __future__ import annotations

import json

import frappe
from frappe.utils import cint

from orderlift.menu_access import sync_menu_access_rules
from orderlift.menu_registry import iter_menu_items, menu_item_by_key
from orderlift.startup_roles import (
    AGENT_PRICING_MANAGER_ROLE,
    CAMPAIGN_MANAGER_ROLE,
    CANONICAL_BUSINESS_ROLES,
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
    SAV_TECHNICIAN_ROLE,
    STARTUP_ROLES,
    STOCK_QUANTITY_VIEWER_ROLE,
)


READ_ONLY = {"read": 1, "report": 1, "print": 1, "email": 1}
SELECT_ONLY = {"select": 1}
READ_SELECT = {"read": 1, "select": 1}
READ_WRITE_CREATE = {"read": 1, "write": 1, "create": 1, "report": 1, "print": 1, "email": 1}
READ_WRITE = {"read": 1, "write": 1, "report": 1, "print": 1, "email": 1}
FILE_ACCESS = {"read": 1, "write": 1, "create": 1, "delete": 1}
TODO_ACCESS = {"select": 1, "read": 1, "write": 1, "create": 1, "delete": 1}
TAG_ACCESS = {"read": 1, "write": 1, "create": 1}
DIMENSIONING_FEATURE_ROLES = ("Orderlift Admin", "Pricing Configuration")
PRICING_SHEET_BUILDER_ROLES = ("Orderlift Admin", "Sales Manager", "Sales User")
DIMENSIONING_SET_BUILDER_ROLES = ("Orderlift Admin", "System Manager", "Pricing Configuration")
DIMENSIONING_SET_FULL_ACCESS_ROLES = ("Orderlift Admin", "Pricing Configuration")
TRANSACTION_USER = {
    "read": 1,
    "select": 1,
    "write": 1,
    "create": 1,
    "submit": 1,
    "report": 1,
    "export": 1,
    "print": 1,
    "email": 1,
}
TRANSACTION_DRAFT_USER = {
    **TRANSACTION_USER,
    "submit": 0,
}
TRANSACTION_MANAGER = {
    **TRANSACTION_USER,
    "delete": 1,
    "cancel": 1,
    "amend": 1,
}
SALES_ORDER_USER = {**TRANSACTION_USER, "cancel": 1, "amend": 1}
FULL_NON_DELETE = {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "import": 1, "print": 1, "email": 1}
MASTER_MANAGER = {**FULL_NON_DELETE, "select": 1, "delete": 1}
FULL_BUSINESS_ACCESS = {
    **MASTER_MANAGER,
    "submit": 1,
    "cancel": 1,
    "amend": 1,
}
DIMENSIONING_SET_ADMIN_PERMISSION = {
    **FULL_NON_DELETE,
    "select": 1,
    "delete": 1,
}
STOCK_OPERATIONAL = {
    "read": 1,
    "select": 1,
    "write": 1,
    "create": 1,
    "delete": 1,
    "submit": 1,
    "cancel": 1,
    "amend": 1,
    "report": 1,
    "export": 1,
    "print": 1,
    "email": 1,
}
STOCK_READ_ONLY = {"read": 1, "select": 1, "report": 1, "export": 1, "print": 1, "email": 1}
STOCK_SETTINGS_ACCESS = {"read": 1, "write": 1, "create": 1, "print": 1, "email": 1}
STOCK_ENTRY_TYPE_ACCESS = {"read": 1, "select": 1, "write": 1, "create": 1, "print": 1, "email": 1}
STOCK_SETTINGS_USER_PERMISSION_EXEMPT_FIELDS = (
    "item_group",
    "default_warehouse",
    "sample_retention_warehouse",
    "stock_uom",
    "role_allowed_to_over_deliver_receive",
    "role_allowed_to_create_edit_back_dated_transactions",
    "stock_auth_role",
)
ORDERLIFT_ADMIN_PROTECTED_DOCTYPES = {
    "Account",
    "Accounting Dimension",
    "Accounting Dimension Detail",
    "Assignment Rule",
    "Client Script",
    "Cost Center",
    "Custom DocPerm",
    "Custom Field",
    "Customize Form",
    "DocPerm",
    "DocType",
    "Error Log",
    "Module Def",
    "Page",
    "Property Setter",
    "Report",
    "Role",
    "Role Profile",
    "Server Script",
    "User",
    "User Permission",
    "Workflow",
    "Workflow State",
    "Workspace",
}
RETIRED_BUSINESS_DOCTYPES = {"Pricing Simulator Workbench", "Pricing Simulator Static Source"}

COMMERCIAL_AGENT_PERMISSIONS = {
    "Item": READ_ONLY,
    "Opportunity": READ_WRITE_CREATE,
    "Pricing Sheet": READ_WRITE_CREATE,
    "Quotation": TRANSACTION_USER,
    "Workflow State": READ_SELECT,
    "Price List": READ_SELECT,
    "Orderlift Other Charge": READ_SELECT,
    "Sales Commission": READ_ONLY,
    "Customer": READ_ONLY,
    "Prospect": READ_ONLY,
    "Lead": READ_ONLY,
}

ITEM_CATALOG_READ_PERMISSIONS = {
    "Item": READ_ONLY,
    "Item Category": READ_ONLY,
    "Item Group": READ_ONLY,
    "Product Bundle": READ_ONLY,
}

COMMON_TRANSACTION_SUPPORT_PERMISSIONS = {
    "Address": READ_ONLY,
    "Company": SELECT_ONLY,
    "Communication": READ_ONLY,
    "Contact": READ_ONLY,
    "Currency": SELECT_ONLY,
    "Email Template": READ_ONLY,
    "Event": READ_WRITE_CREATE,
    "File": FILE_ACCESS,
    "Gender": READ_ONLY,
    "UOM": READ_ONLY,
    "Country": READ_ONLY,
    "Language": READ_ONLY,
    "Notification Log": READ_ONLY,
    "Payment Term": SELECT_ONLY,
    "Payment Terms Template": READ_ONLY,
    "Terms and Conditions": READ_ONLY,
    "Salutation": READ_ONLY,
    "Tag": TAG_ACCESS,
    "Tag Link": TAG_ACCESS,
    "ToDo": TODO_ACCESS,
    "Workflow State": READ_SELECT,
}

SALES_USER_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    **ITEM_CATALOG_READ_PERMISSIONS,
    "Price List": SELECT_ONLY,
    "Payment Terms Template": SELECT_ONLY,
    "Dimensioning Set": SELECT_ONLY,
    "CRM Business Type": SELECT_ONLY,
    "CRM Segment": SELECT_ONLY,
    "Installation Stage": SELECT_ONLY,
    "Partner Segment": SELECT_ONLY,
    "Pricing Tier": SELECT_ONLY,
    "Sales Stage": SELECT_ONLY,
    "Project Status": SELECT_ONLY,
    "Orderlift Order Status": SELECT_ONLY,
    "Lead": READ_WRITE_CREATE,
    "Prospect": READ_WRITE_CREATE,
    "Customer": READ_WRITE_CREATE,
    "Contact": READ_WRITE_CREATE,
    "Address": READ_WRITE_CREATE,
    "Communication": READ_WRITE_CREATE,
    "Appointment": READ_WRITE_CREATE,
    "Opportunity": READ_WRITE_CREATE,
    "Partner Campaign": READ_WRITE_CREATE,
    "Partner Campaign Target": READ_WRITE_CREATE,
    "Pricing Sheet": READ_WRITE_CREATE,
    "Quotation": TRANSACTION_USER,
    "Sales Order": SALES_ORDER_USER,
    "Project": READ_ONLY,
    "Contract": READ_ONLY,
    "Delivery Note": READ_ONLY,
    "Sales Invoice": READ_ONLY,
    "Sales Commission": READ_ONLY,
    "Portal Customer Group Policy": READ_ONLY,
    "Portal Quote Request": READ_ONLY,
    "Warehouse": READ_ONLY,
    "Sales Taxes and Charges Template": READ_ONLY,
    "Orderlift Other Charge": READ_SELECT,
}

SALES_MANAGER_PERMISSIONS = {
    **SALES_USER_PERMISSIONS,
    "Lead": MASTER_MANAGER,
    "Prospect": MASTER_MANAGER,
    "Customer": MASTER_MANAGER,
    "Contact": MASTER_MANAGER,
    "Address": MASTER_MANAGER,
    "Communication": MASTER_MANAGER,
    "Appointment": MASTER_MANAGER,
    "Opportunity": MASTER_MANAGER,
    "Partner Campaign": MASTER_MANAGER,
    "Partner Campaign Target": MASTER_MANAGER,
    "Pricing Sheet": MASTER_MANAGER,
    "Quotation": TRANSACTION_MANAGER,
    "Sales Order": TRANSACTION_MANAGER,
    "Sales Commission": READ_WRITE,
    "Stock Demand Plan": READ_ONLY,
}

PRICING_CONFIGURATION_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    "Item": READ_ONLY,
    "Price List": MASTER_MANAGER,
    "Item Price": MASTER_MANAGER,
    "Pricing Builder": MASTER_MANAGER,
    "Pricing Builder History": READ_ONLY,
    "Dimensioning Set": MASTER_MANAGER,
    "Pricing Scenario": MASTER_MANAGER,
    "Pricing Benchmark Policy": MASTER_MANAGER,
    "Pricing Customs Policy": MASTER_MANAGER,
    "Pricing Tier": MASTER_MANAGER,
    "Pricing Tier Modifier": MASTER_MANAGER,
    "Agent Pricing Rules": MASTER_MANAGER,
    "Buying Price Formula Rule": MASTER_MANAGER,
    "Orderlift Other Charge": MASTER_MANAGER,
    "Customer Segmentation Engine": MASTER_MANAGER,
    "Data Import": MASTER_MANAGER,
    "Data Import Log": READ_ONLY,
}

FINANCE_USER_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    "Sales Invoice": TRANSACTION_USER,
    "Purchase Invoice": TRANSACTION_USER,
    "Payment Entry": TRANSACTION_USER,
    "Payment Request": READ_ONLY,
    "Payment Terms Template": READ_ONLY,
    "Payment Schedule": READ_ONLY,
    "Mode of Payment": READ_ONLY,
    "Bank Account": READ_ONLY,
    "Buying Settings": READ_ONLY,
    "Sales Order": READ_ONLY,
    "Purchase Order": READ_ONLY,
    "Purchase Receipt": READ_ONLY,
    "Customer": READ_ONLY,
    "Supplier": READ_ONLY,
    "Supplier Group": READ_ONLY,
}

FINANCE_ADMIN_PERMISSIONS = {
    **FINANCE_USER_PERMISSIONS,
    "Sales Invoice": TRANSACTION_MANAGER,
    "Purchase Invoice": TRANSACTION_MANAGER,
    "Payment Entry": TRANSACTION_MANAGER,
    "Sales Commission": READ_WRITE,
}

PURCHASE_USER_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    # ERPNext loads Company metadata after selection through frappe.client.get_value,
    # which requires read permission in addition to Link-field select permission.
    "Company": READ_ONLY,
    "Supplier": READ_ONLY,
    "Material Request": READ_ONLY,
    "Request for Quotation": TRANSACTION_USER,
    "Supplier Quotation": TRANSACTION_USER,
    "Purchase Order": TRANSACTION_DRAFT_USER,
    "Purchase Receipt": READ_ONLY,
    "Purchase Invoice": READ_ONLY,
    "Supplier Group": READ_ONLY,
    "Item": READ_ONLY,
    "Item Group": READ_ONLY,
    "Opportunity": SELECT_ONLY,
    "UOM": READ_ONLY,
    "Warehouse": READ_ONLY,
    "Price List": SELECT_ONLY,
    "Purchase Taxes and Charges Template": SELECT_ONLY,
    "Buying Price Change Log": READ_ONLY,
}

PURCHASE_MANAGER_PERMISSIONS = {
    **PURCHASE_USER_PERMISSIONS,
    "Supplier": READ_WRITE_CREATE,
    "Supplier Group": READ_WRITE_CREATE,
    "Material Request": TRANSACTION_MANAGER,
    "Request for Quotation": TRANSACTION_MANAGER,
    "Supplier Quotation": TRANSACTION_MANAGER,
    "Purchase Order": TRANSACTION_MANAGER,
    "Purchase Receipt": TRANSACTION_MANAGER,
    "Purchase Invoice": TRANSACTION_MANAGER,
    "Buying Price Change Log": READ_ONLY,
    "Stock Demand Plan": READ_ONLY,
    "Stock Planning Settings": READ_ONLY,
}

STOCK_USER_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    "Item": READ_ONLY,
    "Item Group": READ_ONLY,
    "Customer": READ_ONLY,
    "Supplier": READ_ONLY,
    "Warehouse": READ_ONLY,
    "Bin": READ_ONLY,
    "Stock Ledger Entry": READ_ONLY,
    "Purchase Order": READ_ONLY,
    "Material Request": TRANSACTION_USER,
    "Purchase Receipt": TRANSACTION_USER,
    "Stock Entry": TRANSACTION_USER,
    "Delivery Note": TRANSACTION_USER,
    "Pick List": TRANSACTION_USER,
    "Quality Inspection": TRANSACTION_USER,
    "Stock Demand Plan": READ_ONLY,
}

STOCK_MANAGER_PERMISSIONS = {
    **STOCK_USER_PERMISSIONS,
    "Warehouse": MASTER_MANAGER,
    "Material Request": TRANSACTION_MANAGER,
    "Purchase Receipt": TRANSACTION_MANAGER,
    "Stock Entry": TRANSACTION_MANAGER,
    "Delivery Note": TRANSACTION_MANAGER,
    "Pick List": TRANSACTION_MANAGER,
    "Quality Inspection": TRANSACTION_MANAGER,
    "Quality Inspection Template": MASTER_MANAGER,
    "Stock Settings": READ_WRITE,
    "Stock Planning Settings": READ_WRITE_CREATE,
    "Stock Entry Type": MASTER_MANAGER,
}

INSTALLATION_USER_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    "Project": READ_WRITE_CREATE,
    "Project Update": READ_WRITE_CREATE,
    "Contract": READ_WRITE_CREATE,
    "Task": READ_WRITE_CREATE,
    "Timesheet": READ_WRITE_CREATE,
    "Maintenance Schedule": READ_WRITE_CREATE,
    "QC Checklist Template": READ_WRITE_CREATE,
    "Sales Order": READ_ONLY,
    "Opportunity": READ_ONLY,
    "Project Status": SELECT_ONLY,
}

SERVICE_USER_PERMISSIONS = {
    **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
    "SAV Ticket": READ_WRITE_CREATE,
    "Issue": READ_ONLY,
    "Warranty Claim": READ_ONLY,
    "Customer": READ_ONLY,
    "Sales Order": READ_ONLY,
    "Delivery Note": READ_ONLY,
    "Sales Invoice": READ_ONLY,
}

def _merge_permission_maps(*permission_maps: dict) -> dict:
    merged = {}
    for permission_map in permission_maps:
        for doctype, flags in permission_map.items():
            merged.setdefault(doctype, {})
            for flag, value in flags.items():
                merged[doctype][flag] = max(cint(merged[doctype].get(flag)), cint(value))
    return merged


ORDERLIFT_ADMIN_PERMISSIONS = {
    **_merge_permission_maps(
        SALES_MANAGER_PERMISSIONS,
        PURCHASE_MANAGER_PERMISSIONS,
        STOCK_MANAGER_PERMISSIONS,
        FINANCE_ADMIN_PERMISSIONS,
        PRICING_CONFIGURATION_PERMISSIONS,
        INSTALLATION_USER_PERMISSIONS,
        SERVICE_USER_PERMISSIONS,
    ),
    "Item Category": MASTER_MANAGER,
    "Item Group": MASTER_MANAGER,
    "Product Bundle": MASTER_MANAGER,
    "Supplier": MASTER_MANAGER,
    "Supplier Group": MASTER_MANAGER,
    "Forecast Load Plan": MASTER_MANAGER,
    "Container Profile": MASTER_MANAGER,
    "CRM Business Type": MASTER_MANAGER,
    "CRM Segment": MASTER_MANAGER,
    "Partner Segment": MASTER_MANAGER,
    "Partner Campaign Status": MASTER_MANAGER,
    "Installation Stage": MASTER_MANAGER,
    "Sales Stage": MASTER_MANAGER,
    "Project Status": MASTER_MANAGER,
    "Orderlift Order Status": MASTER_MANAGER,
    "Logistics Pipeline Status": MASTER_MANAGER,
    "Stock Ledger Entry": FULL_BUSINESS_ACCESS,
    "Orderlift Menu Access Rule": MASTER_MANAGER,
    "Company": MASTER_MANAGER,
    "Currency": READ_ONLY,
    "Currency Exchange": MASTER_MANAGER,
    "Currency Exchange Settings": READ_WRITE,
    "Performance Metric": MASTER_MANAGER,
    "Performance Metric Snapshot": MASTER_MANAGER,
    "Performance Profile": MASTER_MANAGER,
    "Training Program": MASTER_MANAGER,
    "Training Level": MASTER_MANAGER,
    "Training Module": MASTER_MANAGER,
    "Training Quiz": MASTER_MANAGER,
    "Training Quiz Attempt": MASTER_MANAGER,
    "Training Quiz Question": MASTER_MANAGER,
    "QC Checklist Template": MASTER_MANAGER,
    "Email Template": MASTER_MANAGER,
    "Payment Term": MASTER_MANAGER,
    "Payment Terms Template": MASTER_MANAGER,
    "Terms and Conditions": MASTER_MANAGER,
    "File": MASTER_MANAGER,
    "Gender": MASTER_MANAGER,
    "Salutation": MASTER_MANAGER,
    "Tag": MASTER_MANAGER,
    "Tag Link": MASTER_MANAGER,
    "ToDo": MASTER_MANAGER,
    "Purchase Agent Rules": MASTER_MANAGER,
}

# Keep business-superuser access aligned with the visible matrix instead of a
# separate hidden permission list. System Manager gets the same business
# baseline without needing the Orderlift Admin role.
for _menu_item in iter_menu_items():
    if _menu_item.get("link_type") == "DocType" and _menu_item.get("link_to"):
        ORDERLIFT_ADMIN_PERMISSIONS[_menu_item["link_to"]] = FULL_BUSINESS_ACCESS

ORDERLIFT_ADMIN_PERMISSIONS["Stock Demand Plan"] = READ_ONLY

SYSTEM_MANAGER_BUSINESS_PERMISSIONS = {
    **ORDERLIFT_ADMIN_PERMISSIONS,
    "Data Import Log": MASTER_MANAGER,
    "Notification Log": MASTER_MANAGER,
    "Account": FULL_BUSINESS_ACCESS,
    "Accounting Dimension": FULL_BUSINESS_ACCESS,
    "Accounting Dimension Detail": FULL_BUSINESS_ACCESS,
    "Cost Center": FULL_BUSINESS_ACCESS,
}

SAV_TECHNICIAN_PERMISSIONS = {
    "SAV Ticket": READ_WRITE_CREATE,
    "Customer": READ_ONLY,
    "Contact": READ_ONLY,
    "Address": READ_ONLY,
    "Sales Order": READ_ONLY,
    "Delivery Note": READ_ONLY,
    "Sales Invoice": READ_ONLY,
    "Project": READ_ONLY,
    "ToDo": READ_WRITE_CREATE,
    "Event": READ_WRITE_CREATE,
    "Communication": READ_WRITE_CREATE,
    "File": READ_WRITE_CREATE,
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
    # Report has customized permissions on configured sites. Keep the native
    # Desk User read path so individual Report.roles rows can authorize the
    # reports exposed by the menu without granting report administration.
    "Desk User": {"Report": READ_ONLY},
    "Orderlift Admin": ORDERLIFT_ADMIN_PERMISSIONS,
    "System Manager": SYSTEM_MANAGER_BUSINESS_PERMISSIONS,
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
        "Delivery Note": STOCK_OPERATIONAL,
        "Purchase Receipt": STOCK_OPERATIONAL,
        "Stock Entry": STOCK_OPERATIONAL,
        "Material Request": STOCK_OPERATIONAL,
        "Purchase Order": READ_ONLY,
        "Pick List": STOCK_OPERATIONAL,
        "Quality Inspection": STOCK_OPERATIONAL,
        "Warehouse": STOCK_READ_ONLY,
        "Bin": STOCK_READ_ONLY,
        "Stock Ledger Entry": STOCK_READ_ONLY,
        "Stock Settings": STOCK_SETTINGS_ACCESS,
        "Supplier": READ_ONLY,
        "Supplier Group": READ_ONLY,
        "Item": READ_ONLY,
        "Quality Inspection Template": READ_WRITE_CREATE,
        "Stock Entry Type": STOCK_ENTRY_TYPE_ACCESS,
        "Container Profile": READ_WRITE_CREATE,
        "Stock Demand Plan": READ_ONLY,
        "Stock Planning Settings": READ_ONLY,
    },
    "Logistics User": {
        **COMMON_TRANSACTION_SUPPORT_PERMISSIONS,
        **ITEM_CATALOG_READ_PERMISSIONS,
        "Forecast Load Plan": READ_WRITE_CREATE,
        "Delivery Note": TRANSACTION_USER,
        "Purchase Receipt": TRANSACTION_USER,
        "Stock Entry": TRANSACTION_USER,
        "Material Request": TRANSACTION_USER,
        "Purchase Order": READ_ONLY,
        "Pick List": TRANSACTION_USER,
        "Quality Inspection": TRANSACTION_USER,
        "Warehouse": STOCK_READ_ONLY,
        "Bin": STOCK_READ_ONLY,
        "Stock Ledger Entry": STOCK_READ_ONLY,
        "Stock Settings": STOCK_SETTINGS_ACCESS,
        "Supplier": READ_ONLY,
        "Supplier Group": READ_ONLY,
        "Quality Inspection Template": READ_WRITE_CREATE,
        "Stock Entry Type": STOCK_ENTRY_TYPE_ACCESS,
        "Container Profile": READ_WRITE_CREATE,
        "Logistics Pipeline Status": SELECT_ONLY,
        "Stock Demand Plan": READ_ONLY,
        "Stock Planning Settings": READ_ONLY,
    },
    "Stock User": STOCK_USER_PERMISSIONS,
    "Stock Manager": STOCK_MANAGER_PERMISSIONS,
    "BET Technical User": {
        "Item": READ_ONLY,
        "Opportunity": READ_ONLY,
        "Project": READ_ONLY,
        "Dimensioning Set": READ_WRITE_CREATE,
        "QC Checklist Template": READ_WRITE_CREATE,
    },
    "Finance Admin": FINANCE_ADMIN_PERMISSIONS,
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
    "Sales User": SALES_USER_PERMISSIONS,
    "Sales Manager": SALES_MANAGER_PERMISSIONS,
    "Purchase User": PURCHASE_USER_PERMISSIONS,
    "Purchase Manager": PURCHASE_MANAGER_PERMISSIONS,
    "Pricing Configuration": PRICING_CONFIGURATION_PERMISSIONS,
    "Finance User": FINANCE_USER_PERMISSIONS,
    "Installation User": INSTALLATION_USER_PERMISSIONS,
    "Service User": SERVICE_USER_PERMISSIONS,
    SAV_TECHNICIAN_ROLE: SAV_TECHNICIAN_PERMISSIONS,
    QUOTATION_CREATOR_ROLE: {
        "Quotation": TRANSACTION_USER,
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
        "Payment Entry": {**READ_WRITE, "submit": 1},
        "Sales Invoice": READ_ONLY,
    },
    STOCK_QUANTITY_VIEWER_ROLE: {
        "Item": READ_ONLY,
    },
}

STALE_DOCTYPE_PERMISSIONS = {
    "Sales Distribution Manager": ["Partner Campaign", "Partner Campaign Target"],
    "Sales Installation Manager": ["Partner Campaign", "Partner Campaign Target"],
    "Logistics Manager": ["Request for Quotation"],
    "Logistics User": ["Request for Quotation"],
}

STALE_MENU_ROLE_ASSIGNMENTS = {
    "Logistics Manager": [
        "purchasing.suppliers",
        "purchasing.material_request",
        "purchasing.rfq",
        "purchasing.purchase_order",
        "purchasing.purchase_receipt",
        "purchasing.delivery_note",
        "purchasing.pick_list",
    ],
    "Logistics User": [
        "purchasing.suppliers",
        "purchasing.material_request",
        "purchasing.rfq",
        "purchasing.purchase_order",
        "purchasing.purchase_receipt",
        "purchasing.delivery_note",
        "purchasing.pick_list",
    ],
}

WORKFLOW_PERMISSION_SCOPE = {
    "Desk User": {"Report"},
    "Logistics Manager": {
        "Purchase Order",
        "Supplier",
        "Supplier Group",
        "Request for Quotation",
    },
    "Logistics User": {
        "Delivery Note",
        "Purchase Receipt",
        "Stock Entry",
        "Material Request",
        "Purchase Order",
        "Pick List",
        "Quality Inspection",
        "Supplier",
        "Supplier Group",
        "Request for Quotation",
    },
    "Finance Admin": set(FINANCE_ADMIN_PERMISSIONS),
    "Finance User": set(FINANCE_USER_PERMISSIONS),
    PAYMENT_VALIDATOR_ROLE: {"Payment Entry", "Sales Invoice"},
    "Sales User": {"Quotation"},
    "Sales Manager": {"Quotation", "Sales Order", "Sales Commission"},
    "Sales Distribution Manager": {"Quotation", "Sales Order", "Sales Commission"},
    "Sales Installation Manager": {"Quotation", "Sales Order", "Sales Commission"},
    COMMERCIAL_AGENT_ROLE: {"Quotation"},
    COMMERCIAL_AGENT_PARTNER_ROLE: {"Quotation"},
    COMMERCIAL_AGENT_COORDINATOR_ROLE: {"Quotation"},
    COMMERCIAL_AGENT_POINT_OF_SALE_ROLE: {"Quotation"},
    QUOTATION_CREATOR_ROLE: {"Quotation"},
    "Purchase User": set(PURCHASE_USER_PERMISSIONS),
    "Purchase Manager": set(PURCHASE_MANAGER_PERMISSIONS),
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
        "finance.sales_payment_follow_up",
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
    SAV_TECHNICIAN_ROLE: ["sav.tickets", "training.center"],
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
        "stock.rate_review",
    ],
    "Purchase User": [
        "purchasing.suppliers",
        "purchasing.material_request",
        "purchasing.rfq",
        "purchasing.purchase_order",
        "purchasing.purchase_receipt",
        "items.item",
        "items.item_price",
        "stock.rate_review",
    ],
    "Stock Manager": [
        "stock.dashboard",
        "stock.balance",
        "stock.ledger",
        "items.item",
        "items.item_category",
        "items.item_group",
        "stock.delivery_note",
        "stock.purchase_receipt",
        "purchasing.delivery_note",
        "purchasing.pick_list",
        "stock.pick_list",
        "stock.stock_settings",
        "stock.rate_review",
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
        "stock.stock_entry",
        "stock.delivery_note",
        "stock.purchase_receipt",
        "stock.pick_list",
        "stock.stock_settings",
        "purchasing.delivery_note",
        "purchasing.purchase_receipt",
        "purchasing.material_request",
        "stock.dashboard",
    ],
    "Logistics User": [
        "logistics.pipeline",
        "logistics.container_planning",
        "logistics.container_profiles",
        "stock.dashboard",
        "stock.stock_entry",
        "stock.delivery_note",
        "stock.purchase_receipt",
        "stock.pick_list",
        "stock.stock_settings",
        "stock.balance",
        "stock.ledger",
        "stock.warehouse_tree",
        "stock.warehouse_report",
        "stock.quality_inspection",
        "stock.qi_templates",
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
        "finance.sales_payment_follow_up",
        "finance.sales_invoices",
        "finance.purchase_invoices",
        "finance.payments",
        "sales.commission_dashboard",
    ],
    "Finance User": [
        "finance.sale_financial_dashboard",
        "finance.sales_payment_follow_up",
        "finance.sales_invoices",
        "finance.purchase_invoices",
        "finance.payments",
    ],
    PAYMENT_VALIDATOR_ROLE: ["finance.payments"],
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
def run(
    dry_run: int = 0,
    exact_normalization: int = 0,
    seed_roles_only: int = 0,
) -> dict:
    frappe.only_for("System Manager")
    dry_run = cint(dry_run)
    exact_normalization = cint(exact_normalization)
    seed_roles_only = cint(seed_roles_only)
    if cint(dry_run):
        return {
            "dry_run": True,
            "exact_normalization": bool(exact_normalization),
            "seed_roles_only": bool(seed_roles_only),
            "permission_diff": [] if seed_roles_only else _permission_diff(exact_normalization=exact_normalization),
        }
    results = {
        "roles": [],
        "custom_docperms": [],
        "removed_custom_docperms": [],
        "removed_menu_roles": [],
        "menu_rules": [],
        "page_roles": [],
        "assigned_roles": [],
    }

    for role_name in CANONICAL_BUSINESS_ROLES:
        _ensure_role(role_name, results)

    if seed_roles_only:
        frappe.clear_cache()
        frappe.db.commit()
        return results

    managed_permission_roles = set(CANONICAL_BUSINESS_ROLES) | {"System Manager"}
    for role_name, doctype_permissions in DOCTYPE_PERMISSIONS.items():
        if role_name not in managed_permission_roles:
            continue
        if not frappe.db.exists("Role", role_name):
            continue
        for doctype, flags in doctype_permissions.items():
            if frappe.db.exists("DocType", doctype):
                _ensure_custom_docperm(
                    doctype,
                    role_name,
                    _with_default_flags(flags),
                    results,
                    overwrite_existing=exact_normalization,
                )

    if exact_normalization:
        _remove_unmapped_managed_custom_docperms(results)

    frappe.clear_cache()
    frappe.db.commit()
    return results


def after_migrate() -> dict:
    return run(seed_roles_only=1)


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


def _ensure_custom_docperm(doctype: str, role: str, values: dict, results: dict, overwrite_existing: int = 0) -> None:
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    existing = frappe.db.exists("Custom DocPerm", filters)
    if existing:
        if overwrite_existing:
            frappe.db.set_value("Custom DocPerm", existing, values)
            action = "updated"
        else:
            action = "exists"
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


def _ensure_dimensioning_feature_access(results: dict) -> None:
    for role in DIMENSIONING_FEATURE_ROLES:
        if not frappe.db.exists("Role", role):
            continue
        _ensure_minimum_custom_docperm("Dimensioning Set", role, READ_ONLY, results)

    for role in DIMENSIONING_SET_FULL_ACCESS_ROLES:
        if not frappe.db.exists("Role", role):
            continue
        _ensure_minimum_custom_docperm(
            "Dimensioning Set", role, DIMENSIONING_SET_ADMIN_PERMISSION, results
        )

    if frappe.db.exists("Role", "BET Technical User"):
        _ensure_minimum_custom_docperm(
            "Dimensioning Set", "BET Technical User", READ_WRITE_CREATE, results
        )
        _ensure_minimum_custom_docperm("Item", "BET Technical User", READ_ONLY, results)

    for role in PRICING_SHEET_BUILDER_ROLES:
        _ensure_page_role("pricing-sheet-builder", role, results)
    for role in DIMENSIONING_SET_BUILDER_ROLES:
        _ensure_page_role("dimensioning-set-builder", role, results)


def _ensure_minimum_custom_docperm(doctype: str, role: str, values: dict, results: dict) -> None:
    if not frappe.db.exists("DocType", doctype):
        return
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    existing = frappe.db.exists("Custom DocPerm", filters)
    if not existing:
        _ensure_custom_docperm(doctype, role, _with_default_flags(values), results)
        return

    updates = {
        fieldname: 1
        for fieldname, value in values.items()
        if cint(value) and not cint(frappe.db.get_value("Custom DocPerm", existing, fieldname))
    }
    if updates:
        frappe.db.set_value("Custom DocPerm", existing, updates)
    results["custom_docperms"].append(
        {"doctype": doctype, "role": role, "action": "updated" if updates else "exists"}
    )


def _ensure_page_role(page: str, role: str, results: dict) -> None:
    if not frappe.db.exists("Page", page) or not frappe.db.exists("Role", role):
        return
    filters = {"parenttype": "Page", "parent": page, "role": role}
    if frappe.db.exists("Has Role", filters):
        action = "exists"
    else:
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parenttype": "Page",
                "parent": page,
                "parentfield": "roles",
                "role": role,
            }
        ).insert(ignore_permissions=True)
        action = "created"
    results["page_roles"].append({"parenttype": "Page", "parent": page, "role": role, "action": action})


def _remove_unmapped_managed_custom_docperms(results: dict) -> None:
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"role": ["in", CANONICAL_BUSINESS_ROLES]},
        fields=["name", "parent", "role", "permlevel"],
        limit_page_length=0,
    )
    for row in rows:
        desired_doctypes = DOCTYPE_PERMISSIONS.get(row.role, {})
        if row.parent in desired_doctypes:
            continue
        if not _should_remove_unmapped_permission(row.role, row.parent):
            continue
        frappe.delete_doc("Custom DocPerm", row.name, ignore_permissions=True)
        results["removed_custom_docperms"].append(
            {"doctype": row.parent, "role": row.role, "name": row.name}
        )


def _should_remove_unmapped_permission(role: str, doctype: str) -> bool:
    if doctype in RETIRED_BUSINESS_DOCTYPES:
        return True
    if role == "Orderlift Admin":
        return doctype in ORDERLIFT_ADMIN_PROTECTED_DOCTYPES
    exactly_managed_doctypes = {
        doctype_name
        for managed_role in CANONICAL_BUSINESS_ROLES
        for doctype_name in DOCTYPE_PERMISSIONS.get(managed_role, {})
    }
    return doctype in exactly_managed_doctypes


def _remove_stale_menu_role_assignments(results: dict) -> None:
    for role, menu_keys in STALE_MENU_ROLE_ASSIGNMENTS.items():
        for menu_key in menu_keys:
            name = frappe.db.exists("Orderlift Menu Access Rule", menu_key) or frappe.db.exists(
                "Orderlift Menu Access Rule",
                {"menu_key": menu_key},
            )
            if not name:
                continue
            current = frappe.db.get_value(
                "Orderlift Menu Access Rule",
                name,
                "allowed_roles_json",
            ) or "[]"
            roles = _clean_list(current)
            if role not in roles:
                continue
            roles = [item for item in roles if item != role]
            frappe.db.set_value(
                "Orderlift Menu Access Rule",
                name,
                "allowed_roles_json",
                json.dumps(roles),
            )
            results["removed_menu_roles"].append(
                {"menu_key": menu_key, "role": role}
            )


def _permission_diff(*, exact_normalization: int = 0) -> list[dict]:
    permission_fields = tuple(_with_default_flags({}))
    diff = []
    managed_permission_roles = set(CANONICAL_BUSINESS_ROLES) | {"System Manager"}
    for role, doctype_permissions in DOCTYPE_PERMISSIONS.items():
        if role not in managed_permission_roles:
            continue
        for doctype, flags in doctype_permissions.items():
            if not frappe.db.exists("DocType", doctype):
                continue
            filters = {"parent": doctype, "role": role, "permlevel": 0}
            existing = frappe.db.exists("Custom DocPerm", filters)
            desired = _with_default_flags(flags)
            if not existing:
                diff.append(
                    {
                        "action": "create",
                        "doctype": doctype,
                        "role": role,
                        "desired": desired,
                    }
                )
                continue
            current = frappe.db.get_value(
                "Custom DocPerm",
                existing,
                list(permission_fields),
                as_dict=True,
            ) or {}
            changed = {
                fieldname: {
                    "from": cint(current.get(fieldname)),
                    "to": cint(desired.get(fieldname)),
                }
                for fieldname in permission_fields
                if cint(current.get(fieldname)) != cint(desired.get(fieldname))
            }
            if changed and exact_normalization:
                diff.append(
                    {
                        "action": "update",
                        "doctype": doctype,
                        "role": role,
                        "name": existing,
                        "changes": changed,
                    }
                )
    if exact_normalization:
        rows = frappe.get_all(
            "Custom DocPerm",
            filters={"role": ["in", CANONICAL_BUSINESS_ROLES]},
            fields=["name", "parent", "role", "permlevel"],
            limit_page_length=0,
        )
        for row in rows:
            if row.parent in DOCTYPE_PERMISSIONS.get(row.role, {}):
                continue
            if not _should_remove_unmapped_permission(row.role, row.parent):
                continue
            diff.append(
                {
                    "action": "remove",
                    "doctype": row.parent,
                    "role": row.role,
                    "name": row.name,
                }
            )
    return diff


def _pair_is_in_workflow_scope(role: str, doctype: str) -> bool:
    return doctype in WORKFLOW_PERMISSION_SCOPE.get(role, set())


def _ensure_menu_roles(results: dict, roles: set[str] | None = None) -> None:
    sync_menu_access_rules()
    for role, menu_keys in MENU_ROLE_MAP.items():
        if roles is not None and role not in roles:
            continue
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
    _ensure_allowed_menu_link_roles(results, roles=roles)


def _ensure_link_role(menu_key: str, role: str, results: dict) -> None:
    item = menu_item_by_key(menu_key)
    if not item or item.get("link_type") not in {"Page", "Report"} or not item.get("link_to"):
        return
    parenttype = item["link_type"]
    parent = item["link_to"]
    if not frappe.db.exists(parenttype, parent) or not frappe.db.exists("Role", role):
        return
    if parenttype == "Page":
        _ensure_page_role(parent, role, results)
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


def _ensure_allowed_menu_link_roles(results: dict, roles: set[str] | None = None) -> None:
    rows = frappe.get_all(
        "Orderlift Menu Access Rule",
        filters={"enabled": 1, "link_type": ["in", ["Page", "Report"]]},
        fields=["menu_key", "allowed_roles_json"],
        limit_page_length=0,
    )
    for row in rows:
        for role in _clean_list(row.get("allowed_roles_json")):
            if roles is not None and role not in roles:
                continue
            _ensure_link_role(row.menu_key, role, results)


def _ensure_stock_settings_user_permission_exempt_fields(results: dict) -> None:
    if not frappe.db.exists("DocType", "Stock Settings"):
        return
    for fieldname in STOCK_SETTINGS_USER_PERMISSION_EXEMPT_FIELDS:
        if not frappe.get_meta("Stock Settings").get_field(fieldname):
            continue
        _ensure_field_property_setter(
            "Stock Settings",
            fieldname,
            "ignore_user_permissions",
            "Check",
            1,
            results,
        )


def _ensure_field_property_setter(
    doctype: str,
    fieldname: str,
    property_name: str,
    property_type: str,
    value,
    results: dict,
) -> None:
    filters = {"doc_type": doctype, "field_name": fieldname, "property": property_name}
    existing = frappe.db.get_value("Property Setter", filters, "name")
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocField"
    setter.field_name = fieldname
    setter.property = property_name
    setter.property_type = property_type
    setter.value = str(value)
    if existing:
        setter.save(ignore_permissions=True)
        action = "updated"
    else:
        setter.insert(ignore_permissions=True)
        action = "created"
    results.setdefault("property_setters", []).append(
        {"doctype": doctype, "fieldname": fieldname, "property": property_name, "action": action}
    )


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
