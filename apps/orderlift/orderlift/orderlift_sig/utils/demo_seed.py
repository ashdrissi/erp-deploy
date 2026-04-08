from __future__ import annotations

import frappe
from frappe.utils import add_days, now_datetime, today

from orderlift.orderlift_sig.utils.project_qc import _set_qc_status


TEMPLATE_NAME = "SIG Demo Template - Standard Lift Install"
ADMIN_USER = "Administrator"

TEMPLATE_ITEMS = [
    {
        "item_code": "Site Survey Complete",
        "description": "Site dimensions verified and access path confirmed.",
        "category": "Site Preparation",
        "is_mandatory": 1,
    },
    {
        "item_code": "Machine Room Cleared",
        "description": "Installation area cleared and ready for delivery.",
        "category": "Site Preparation",
        "is_mandatory": 1,
    },
    {
        "item_code": "Power Isolation Validated",
        "description": "Safety isolation and lockout process confirmed.",
        "category": "Safety",
        "is_mandatory": 1,
    },
    {
        "item_code": "Rails Aligned",
        "description": "Guide rails mounted and aligned to spec.",
        "category": "Mechanical",
        "is_mandatory": 0,
    },
    {
        "item_code": "Control Cabinet Wired",
        "description": "Control cabinet wiring completed and labeled.",
        "category": "Electrical",
        "is_mandatory": 0,
    },
    {
        "item_code": "As-Built Photos Uploaded",
        "description": "Final documentation and installation photos uploaded.",
        "category": "Documentation",
        "is_mandatory": 0,
    },
]

SCENARIOS = [
    {
        "project_name": "SIG DEMO - Casablanca New Installation",
        "project_type": "New Installation",
        "city": "Casablanca",
        "address": "Twin Center, Boulevard Zerktouni",
        "latitude": 33.5731,
        "longitude": -7.5898,
        "status": "Open",
        "verify_indexes": [],
        "remarks": {},
    },
    {
        "project_name": "SIG DEMO - Rabat Upgrade In Progress",
        "project_type": "Upgrade",
        "city": "Rabat",
        "address": "Avenue Mohammed V",
        "latitude": 34.0209,
        "longitude": -6.8416,
        "status": "Open",
        "verify_indexes": [0, 1, 2],
        "remarks": {3: "Rails pending final alignment after delivery window."},
    },
    {
        "project_name": "SIG DEMO - Marrakech Maintenance Blocked",
        "project_type": "Maintenance",
        "city": "Marrakech",
        "address": "Gueliz Service Corridor",
        "latitude": 31.6295,
        "longitude": -7.9811,
        "status": "Open",
        "verify_indexes": [0, 3],
        "remarks": {
            1: "Machine room still occupied by customer equipment.",
            2: "Safety isolation cannot be signed off yet.",
        },
    },
    {
        "project_name": "SIG DEMO - Tangier Inspection Complete",
        "project_type": "Inspection",
        "city": "Tangier",
        "address": "Tanger City Center",
        "latitude": 35.7595,
        "longitude": -5.8340,
        "status": "Completed",
        "verify_indexes": [0, 1, 2, 3, 4, 5],
        "remarks": {5: "Documentation uploaded and signed off by QA."},
    },
]


def seed_demo_data() -> dict:
    frappe.set_user(ADMIN_USER)

    company = frappe.defaults.get_global_default("company")
    if not company:
        companies = frappe.get_all("Company", pluck="name", limit=1)
        company = companies[0] if companies else None
    if not company:
        frappe.throw("No Company found. Create a Company before seeding SIG demo data.")

    sample_customer = None
    customers = frappe.get_all("Customer", pluck="name", limit=1)
    if customers:
        sample_customer = customers[0]

    template = _upsert_template()
    projects = [
        _upsert_project(index, scenario, sample_customer, company)
        for index, scenario in enumerate(SCENARIOS, start=1)
    ]

    frappe.db.commit()
    return {
        "template": template.name,
        "projects": projects,
    }


def _upsert_template():
    if frappe.db.exists("QC Checklist Template", TEMPLATE_NAME):
        template = frappe.get_doc("QC Checklist Template", TEMPLATE_NAME)
    else:
        template = frappe.new_doc("QC Checklist Template")
        template.template_name = TEMPLATE_NAME

    template.project_type = "New Installation"
    template.is_active = 1
    template.set("items", [])
    for item in TEMPLATE_ITEMS:
        template.append("items", item)

    if template.is_new():
        template.insert(ignore_permissions=True)
    else:
        template.save(ignore_permissions=True)

    return template


def _upsert_project(index: int, scenario: dict, sample_customer: str | None, company: str) -> dict:
    existing_name = frappe.db.exists("Project", {"project_name": scenario["project_name"]})
    if existing_name:
        project = frappe.get_doc("Project", existing_name)
    else:
        project = frappe.new_doc("Project")
        project.project_name = scenario["project_name"]

    project.status = "Open"
    project.company = company
    project.customer = sample_customer
    project.notes = f"SIG demo scenario seeded on {today()} to showcase Desk map, dashboard, and QC flows."
    project.expected_start_date = add_days(today(), index)
    project.expected_end_date = add_days(today(), index + 10)
    project.custom_project_type_ol = scenario["project_type"]
    project.custom_site_address = scenario["address"]
    project.custom_city = scenario["city"]
    project.custom_latitude = scenario["latitude"]
    project.custom_longitude = scenario["longitude"]
    project.custom_geocode_status = "Demo coordinates"
    project.custom_qc_template = TEMPLATE_NAME

    if project.is_new():
        project.insert(ignore_permissions=True)
    else:
        project.save(ignore_permissions=True)

    project = frappe.get_doc("Project", project.name)
    project.set("custom_qc_checklist", [])
    for item in TEMPLATE_ITEMS:
        project.append(
            "custom_qc_checklist",
            {
                "item_code": item["item_code"],
                "description": item["description"],
                "category": item["category"],
                "is_mandatory": item["is_mandatory"],
                "is_verified": 0,
                "remarks": "",
            },
        )

    for row_index, row in enumerate(project.custom_qc_checklist):
        if row_index in scenario["verify_indexes"]:
            row.is_verified = 1
            row.verified_by = ADMIN_USER
            row.verified_on = now_datetime()
        else:
            row.is_verified = 0
            row.verified_by = None
            row.verified_on = None
        row.remarks = scenario["remarks"].get(row_index, "")

    _set_qc_status(project)
    project.status = scenario["status"]
    project.save(ignore_permissions=True)

    return {
        "name": project.name,
        "project_name": project.project_name,
        "qc_status": project.custom_qc_status,
        "status": project.status,
    }
