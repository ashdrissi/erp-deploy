from __future__ import annotations

from copy import deepcopy


ALL_USERS_ROLE = "All"

BUSINESS_ROLES = [
    "Orderlift Admin",
    "Sales User",
    "Pricing Manager",
    "Logistics User",
    "Finance User",
    "Installation User",
    "Service User",
]

ADMIN_ROLES = ["Orderlift Admin", "Administrator", "System Manager", "Developer"]
ACCESS_MANAGER_ROLES = ["Orderlift Admin", "System Manager"]
SALES_ROLES = ["Orderlift Admin", "Sales User", "Pricing Manager"]
PRICING_MANAGER_ROLES = ["Orderlift Admin", "Pricing Manager"]
FINANCE_ROLES = ["Orderlift Admin", "Finance User"]
LOGISTICS_ROLES = ["Orderlift Admin", "Logistics User"]
PROJECT_ROLES = ["Orderlift Admin", "Installation User", "Sales User"]
SAV_ROLES = ["Orderlift Admin", "Service User"]
SIG_ROLES = ["Orderlift Admin", "Installation User"]
HR_ROLES = ["Orderlift Admin"]
B2B_ROLES = ["Orderlift Admin", "Sales User", "Pricing Manager"]


HOME_LINK = {
    "key": "home.dashboard",
    "type": "Link",
    "label": "Dashboard",
    "link_type": "Page",
    "link_to": "home-page",
    "child": 0,
    "icon": "dashboard",
    "roles": [ALL_USERS_ROLE],
}


MENU_SECTIONS = [
    {
        "key": "my_work",
        "label": "My Work",
        "icon": "user-round",
        "roles": [ALL_USERS_ROLE],
        "links": [
            {"key": "my_work.todo", "label": "ToDo", "link_type": "DocType", "link_to": "ToDo"},
            {"key": "my_work.calendar", "label": "Calendar", "link_type": "DocType", "link_to": "Event"},
        ],
    },
    {
        "key": "administration",
        "label": "Administration",
        "icon": "users",
        "roles": ADMIN_ROLES,
        "links": [
            {"key": "administration.status_control", "label": "Status Control", "link_type": "Page", "link_to": "status-control"},
            {"key": "administration.document_templates", "label": "Document Templates", "link_type": "Page", "link_to": "document-template-manager"},
            {"key": "administration.access_command_center", "label": "Access Command Center", "link_type": "Page", "link_to": "access-command-center", "roles": ACCESS_MANAGER_ROLES},
            {"key": "administration.menu_editor", "label": "Menu Editor", "link_type": "Page", "link_to": "menu-editor", "roles": ACCESS_MANAGER_ROLES},
            {"key": "administration.companies", "label": "Companies", "link_type": "DocType", "link_to": "Company"},
        ],
    },
    {
        "key": "crm_customers",
        "label": "CRM & Customers",
        "icon": "book-user",
        "roles": SALES_ROLES,
        "links": [
            {"key": "crm.crm_dashboard", "label": "CRM Dashboard", "link_type": "Page", "link_to": "crm-dashboard"},
            {"key": "crm.projects_list", "label": "Projects List", "link_type": "DocType", "link_to": "Project", "roles": SALES_ROLES + PROJECT_ROLES},
            {"key": "crm.campaign_manager", "label": "Campaign Manager", "link_type": "Page", "link_to": "campaign-manager"},
            {"key": "crm.campaign_builder", "label": "Campaign Builder", "link_type": "Page", "link_to": "campaign-editor"},
            {"key": "crm.opportunity_pipeline", "label": "Opportunity Pipeline", "link_type": "Page", "link_to": "opportunity-pipeline"},
            {"key": "crm.lead", "label": "Lead", "link_type": "DocType", "link_to": "Lead"},
            {"key": "crm.opportunity", "label": "Opportunity", "link_type": "DocType", "link_to": "Opportunity"},
            {"key": "crm.prospect", "label": "Prospect", "link_type": "DocType", "link_to": "Prospect"},
            {"key": "crm.customer", "label": "Customer", "link_type": "DocType", "link_to": "Customer"},
            {"key": "crm.communication", "label": "Communication", "link_type": "DocType", "link_to": "Communication"},
            {"key": "crm.appointment", "label": "Appointment", "link_type": "DocType", "link_to": "Appointment"},
        ],
    },
    {
        "key": "sales",
        "label": "Sales",
        "icon": "shopping-cart",
        "roles": SALES_ROLES,
        "links": [
            {"key": "sales.pricing_sheets", "label": "Pricing Sheets", "link_type": "Page", "link_to": "pricing-sheet-manager"},
            {"key": "sales.pricing_dashboard", "label": "Pricing Dashboard", "link_type": "Page", "link_to": "pricing-dashboard"},
            {"key": "sales.sales_order_pipeline", "label": "Sales Order Pipeline", "link_type": "Page", "link_to": "sales-order-pipeline"},
            {"key": "sales.project_pipeline", "label": "Project Pipeline", "link_type": "Page", "link_to": "project-pipeline", "roles": SALES_ROLES + PROJECT_ROLES},
            {"key": "sales.quotation", "label": "Quotation", "link_type": "DocType", "link_to": "Quotation"},
            {"key": "sales.sales_order", "label": "Sales Orders", "link_type": "DocType", "link_to": "Sales Order"},
            {"key": "sales.commission_dashboard", "label": "Commissions Dashboard", "link_type": "Page", "link_to": "commission-dashboard"},
            {"key": "sales.commissions", "label": "Commissions", "link_type": "DocType", "link_to": "Sales Commission"},
            {"key": "sales.pricing_simulator", "label": "Pricing Simulator", "link_type": "Page", "link_to": "pricing-simulator"},
        ],
    },
    {
        "key": "policies_configs",
        "label": "Policies & Configs",
        "icon": "shield",
        "roles": PRICING_MANAGER_ROLES,
        "links": [
            {"key": "policies.customs_policy", "label": "Customs Policy", "link_type": "DocType", "link_to": "Pricing Customs Policy"},
            {"key": "policies.expenses_policy", "label": "Expenses Policy", "link_type": "DocType", "link_to": "Pricing Scenario"},
            {"key": "policies.margin_benchmark", "label": "Margin & Benchmark Policy", "link_type": "DocType", "link_to": "Pricing Benchmark Policy"},
            {"key": "policies.customer_segmentation", "label": "Customer Segmentation Engine", "link_type": "Page", "link_to": "customer-segmentation-workspace"},
            {"key": "policies.pricing_tiers", "label": "Pricing Tiers", "link_type": "DocType", "link_to": "Pricing Tier"},
            {"key": "policies.agent_rules", "label": "Agent Rules", "link_type": "DocType", "link_to": "Agent Pricing Rules"},
        ],
    },
    {
        "key": "sav",
        "label": "SAV",
        "icon": "life-buoy",
        "roles": SAV_ROLES,
        "links": [
            {"key": "sav.dashboard", "label": "SAV Dashboard", "link_type": "Page", "link_to": "sav-dashboard"},
            {"key": "sav.tickets", "label": "SAV Tickets", "link_type": "DocType", "link_to": "SAV Ticket"},
        ],
    },
    {
        "key": "items_price_lists",
        "label": "Items & Price Lists",
        "icon": "box",
        "roles": SALES_ROLES + LOGISTICS_ROLES,
        "links": [
            {"key": "items.item", "label": "Item", "link_type": "DocType", "link_to": "Item"},
            {"key": "items.product_bundle", "label": "Product Bundle", "link_type": "DocType", "link_to": "Product Bundle"},
            {"key": "items.dimensioning_sets", "label": "Dimensioning Sets", "link_type": "Page", "link_to": "dimensioning-set-manager"},
            {"key": "items.item_price", "label": "Item Price", "link_type": "DocType", "link_to": "Item Price"},
            {"key": "items.price_list", "label": "Price List", "link_type": "DocType", "link_to": "Price List"},
            {"key": "items.catalogue_prix_articles", "label": "Catalogue Prix Articles", "link_type": "Page", "link_to": "catalogue-prix-articles", "roles": SALES_ROLES},
            {"key": "items.buying_price_builder", "label": "Buying Price Builder", "link_type": "Page", "link_to": "buying-price-builder", "roles": PRICING_MANAGER_ROLES + LOGISTICS_ROLES},
            {"key": "items.pricing_builder", "label": "Pricing Sheets", "link_type": "Page", "link_to": "pricing-sheet-manager", "roles": PRICING_MANAGER_ROLES},
            {"key": "items.static_pricing_builder", "label": "Selling Price List Builder", "link_type": "Page", "link_to": "pricing-builder-manager", "roles": PRICING_MANAGER_ROLES},
        ],
    },
    {
        "key": "finance",
        "label": "Finance",
        "icon": "chart-no-axes-combined",
        "roles": FINANCE_ROLES,
        "links": [
            {"key": "finance.sale_financial_dashboard", "label": "Sale Financial Dashboard", "link_type": "Page", "link_to": "sale-financial-dashboard"},
            {"key": "finance.sales_payment_summary", "label": "Sales Payment Summary", "link_type": "Report", "link_to": "Sales Payment Summary"},
            {"key": "finance.sales_invoices", "label": "Sales Invoices", "link_type": "DocType", "link_to": "Sales Invoice"},
            {"key": "finance.purchase_invoices", "label": "Purchase Invoices", "link_type": "DocType", "link_to": "Purchase Invoice"},
            {"key": "finance.payments", "label": "Payments", "link_type": "DocType", "link_to": "Payment Entry"},
        ],
    },
    {
        "key": "purchasing",
        "label": "Purchasing",
        "icon": "shopping-basket",
        "roles": LOGISTICS_ROLES,
        "links": [
            {"key": "purchasing.suppliers", "label": "Supplier List", "link_type": "DocType", "link_to": "Supplier"},
            {"key": "purchasing.material_request", "label": "Material Request", "link_type": "DocType", "link_to": "Material Request"},
            {"key": "purchasing.rfq", "label": "Request for Quotation", "link_type": "DocType", "link_to": "Request for Quotation"},
            {"key": "purchasing.purchase_order", "label": "Purchase Order", "link_type": "DocType", "link_to": "Purchase Order"},
            {"key": "purchasing.purchase_receipt", "label": "Purchase Receipt", "link_type": "DocType", "link_to": "Purchase Receipt"},
            {"key": "purchasing.delivery_note", "label": "Delivery Note", "link_type": "DocType", "link_to": "Delivery Note"},
            {"key": "purchasing.pick_list", "label": "Pick List", "link_type": "DocType", "link_to": "Pick List"},
        ],
    },
    {
        "key": "hr",
        "label": "HR & Performance",
        "icon": "file-user",
        "roles": HR_ROLES,
        "links": [
            {"key": "hr.dashboard", "label": "HR Dashboard", "link_type": "Page", "link_to": "hr-dashboard"},
            {"key": "hr.payroll_dashboard", "label": "Payroll Dashboard", "link_type": "Dashboard", "link_to": "Payroll"},
            {"key": "hr.employees", "label": "Employees", "link_type": "DocType", "link_to": "Employee"},
            {"key": "hr.salary_slip", "label": "Salary Slip", "link_type": "DocType", "link_to": "Salary Slip"},
            {"key": "hr.payrolls", "label": "Payrolls", "link_type": "DocType", "link_to": "Payroll Entry"},
            {"key": "training.performance_leaderboard", "label": "Performance Leaderboard", "link_type": "Page", "link_to": "performance-leaderboard", "roles": [ALL_USERS_ROLE]},
            {"key": "training.cycle_dashboard", "label": "Performance Cycle Dashboard", "link_type": "Page", "link_to": "performance-cycle-dashboard", "roles": HR_ROLES},
            {"key": "training.performance_metrics", "label": "Performance Metrics", "link_type": "DocType", "link_to": "Performance Metric", "roles": HR_ROLES},
            {"key": "training.performance_profiles", "label": "Performance Profiles", "link_type": "DocType", "link_to": "Performance Profile", "roles": HR_ROLES},
            {"key": "training.performance_snapshots", "label": "Performance Snapshots", "link_type": "DocType", "link_to": "Performance Metric Snapshot", "roles": HR_ROLES},
            {"key": "training.appraisals", "label": "Appraisals", "link_type": "DocType", "link_to": "Appraisal", "roles": HR_ROLES},
            {"key": "training.appraisal_cycles", "label": "Appraisal Cycles", "link_type": "DocType", "link_to": "Appraisal Cycle", "roles": HR_ROLES},
            {"key": "training.goals", "label": "Goals", "link_type": "DocType", "link_to": "Goal", "roles": HR_ROLES},
        ],
    },
    {
        "key": "training",
        "label": "Training",
        "icon": "graduation-cap",
        "roles": [ALL_USERS_ROLE],
        "links": [
            {"key": "training.center", "label": "Training Center", "link_type": "Page", "link_to": "training-center"},
            {"key": "training.leaderboard", "label": "Training Leaderboard", "link_type": "Page", "link_to": "training-leaderboard"},
            {"key": "training.programs", "label": "Training Programs", "link_type": "DocType", "link_to": "Training Program", "roles": HR_ROLES},
            {"key": "training.levels", "label": "Training Levels", "link_type": "DocType", "link_to": "Training Level", "roles": HR_ROLES},
            {"key": "training.modules", "label": "Training Modules", "link_type": "DocType", "link_to": "Training Module", "roles": HR_ROLES},
            {"key": "training.quizzes", "label": "Quizzes", "link_type": "DocType", "link_to": "Training Quiz", "roles": HR_ROLES},
            {"key": "training.quiz_questions", "label": "Quiz Questions", "link_type": "DocType", "link_to": "Training Quiz Question", "roles": HR_ROLES},
            {"key": "training.quiz_attempts", "label": "Quiz Attempts", "link_type": "DocType", "link_to": "Training Quiz Attempt", "roles": HR_ROLES},
        ],
    },
    {
        "key": "projects",
        "label": "Gestion de Projets",
        "icon": "briefcase-business",
        "roles": PROJECT_ROLES + SIG_ROLES,
        "links": [
            {"key": "projects.project_pipeline", "label": "Project Pipeline", "link_type": "Page", "link_to": "project-pipeline"},
            {"key": "projects.sales_order_pipeline", "label": "Sales Order Pipeline", "link_type": "Page", "link_to": "sales-order-pipeline", "roles": PROJECT_ROLES + SALES_ROLES},
            {"key": "projects.contract", "label": "Contract", "link_type": "DocType", "link_to": "Contract", "roles": PROJECT_ROLES + SALES_ROLES},
            {"key": "projects.tasks", "label": "Tasks", "link_type": "DocType", "link_to": "Task"},
            {"key": "projects.timesheet", "label": "Timesheet", "link_type": "DocType", "link_to": "Timesheet"},
            {"key": "projects.maintenance_schedule", "label": "Maintenance Schedule", "link_type": "DocType", "link_to": "Maintenance Schedule"},
        ],
    },
    {
        "key": "warehouse_stock",
        "label": "Warehouse & Stock",
        "icon": "package",
        "roles": LOGISTICS_ROLES,
        "links": [
            {"key": "stock.dashboard", "label": "Stock Dashboard", "link_type": "Page", "link_to": "stock-dashboard"},
            {"key": "stock.balance", "label": "Stock Balance", "link_type": "Report", "link_to": "Stock Balance"},
            {"key": "stock.ledger", "label": "Stock Ledger", "link_type": "Report", "link_to": "Stock Ledger"},
            {"key": "stock.quality_inspection", "label": "Quality Inspection", "link_type": "DocType", "link_to": "Quality Inspection"},
            {"key": "stock.qi_templates", "label": "QI Templates", "link_type": "DocType", "link_to": "Quality Inspection Template"},
        ],
    },
    {
        "key": "logistics",
        "label": "Logistics",
        "icon": "truck",
        "roles": LOGISTICS_ROLES,
        "links": [
            {"key": "logistics.pipeline", "label": "Logistics Pipeline", "link_type": "Page", "link_to": "logistics-pipeline"},
            {"key": "logistics.container_planning", "label": "Container Planning", "link_type": "Page", "link_to": "logistics-dashboard"},
            {"key": "logistics.container_profiles", "label": "Container Profiles", "link_type": "DocType", "link_to": "Container Profile"},
        ],
    },
    {
        "key": "b2b_portal",
        "label": "B2B Portal",
        "icon": "globe",
        "roles": B2B_ROLES,
        "links": [
            {"key": "b2b.dashboard", "label": "B2B Portal Dashboard", "link_type": "Page", "link_to": "b2b-portal-dashboard"},
            {"key": "b2b.portal_policies", "label": "Portal Policies", "link_type": "DocType", "link_to": "Portal Customer Group Policy"},
            {"key": "b2b.quote_requests", "label": "Portal Quote Requests", "link_type": "DocType", "link_to": "Portal Quote Request"},
            {"key": "b2b.review_board", "label": "Portal Review Board", "link_type": "Page", "link_to": "portal-review-board"},
        ],
    },
    {
        "key": "sig",
        "label": "SIG",
        "icon": "map",
        "roles": SIG_ROLES,
        "links": [
            {"key": "sig.dashboard", "label": "SIG Dashboard", "link_type": "Page", "link_to": "sig-dashboard"},
            {"key": "sig.project_map", "label": "Project Map", "link_type": "Page", "link_to": "project-map"},
            {"key": "sig.mobile_qc", "label": "Mobile QC", "link_type": "Page", "link_to": "sig-qc"},
            {"key": "sig.qc_templates", "label": "QC Templates", "link_type": "DocType", "link_to": "QC Checklist Template"},
            {"key": "sig.projects", "label": "Projects", "link_type": "DocType", "link_to": "Project"},
        ],
    },
]


def get_menu_sections() -> list[dict]:
    return deepcopy(MENU_SECTIONS)


def iter_menu_items(include_home: bool = True):
    if include_home:
        yield _normalize_item(HOME_LINK, section=None, section_key=None, section_roles=HOME_LINK.get("roles") or [])

    for section in MENU_SECTIONS:
        section_roles = section.get("roles") or []
        for link in section.get("links", []):
            yield _normalize_item(
                link,
                section=section["label"],
                section_key=section["key"],
                section_roles=section_roles,
            )


def build_sidebar_rows() -> list[dict]:
    rows = [_sidebar_link_row(HOME_LINK)]
    for section in MENU_SECTIONS:
        rows.append(
            {
                "type": "Section Break",
                "label": section["label"],
                "child": 0,
                "icon": section.get("icon") or "folder",
                "indent": 1,
                "collapsible": 1,
                "keep_closed": 1,
            }
        )
        for link in section.get("links", []):
            rows.append(_sidebar_link_row(link))
    return rows


def menu_item_by_key(menu_key: str) -> dict | None:
    for item in iter_menu_items():
        if item["key"] == menu_key:
            return item
    return None


def menu_item_for_row(row: dict) -> dict | None:
    menu_key = row.get("_menu_key") or row.get("menu_key")
    if menu_key:
        item = menu_item_by_key(menu_key)
        if item:
            return item

    row_label = row.get("label")
    row_link_type = row.get("link_type")
    row_link_to = row.get("link_to")
    row_url = row.get("url")

    for item in iter_menu_items():
        if row_link_type and row_link_to and item.get("link_type") == row_link_type and item.get("link_to") == row_link_to:
            return item
        if row_url and item.get("url") == row_url:
            return item
        if row_label == item.get("label") and row_link_type == item.get("link_type") and row_link_to == item.get("link_to"):
            return item
    return None


def page_menu_map() -> dict[str, list[str]]:
    pages: dict[str, list[str]] = {}
    for item in iter_menu_items():
        if item.get("link_type") != "Page" or not item.get("link_to"):
            continue
        pages.setdefault(item["link_to"], []).append(item["key"])
    return pages


def default_roles_for_key(menu_key: str) -> list[str]:
    item = menu_item_by_key(menu_key)
    return list(item.get("roles") or []) if item else []


def _normalize_item(link: dict, *, section: str | None, section_key: str | None, section_roles: list[str]) -> dict:
    roles = list(dict.fromkeys(link.get("roles") or section_roles or [ALL_USERS_ROLE]))
    return {
        "key": link["key"],
        "section": section or "Home",
        "section_key": section_key or "home",
        "label": link["label"],
        "type": link.get("type") or "Link",
        "link_type": link.get("link_type") or "DocType",
        "link_to": link.get("link_to") or "",
        "url": link.get("url") or "",
        "icon": link.get("icon") or "dot",
        "roles": roles,
        "company_scoped": bool(link.get("company_scoped", True)),
    }


def _sidebar_link_row(link: dict) -> dict:
    row = {
        "_menu_key": link.get("key"),
        "type": link.get("type") or "Link",
        "label": link["label"],
        "link_type": link.get("link_type") or "DocType",
        "link_to": link.get("link_to"),
        "url": link.get("url"),
        "child": link.get("child", 1),
        "icon": link.get("icon") or "dot",
    }
    return {key: value for key, value in row.items() if value is not None}
