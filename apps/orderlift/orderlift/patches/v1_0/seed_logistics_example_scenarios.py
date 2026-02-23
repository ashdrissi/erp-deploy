import frappe
from frappe.utils import add_days, nowdate


def execute():
    if not frappe.db.exists("DocType", "Container Profile"):
        return

    profiles = [
        {
            "container_name": "Camionnette 12m3",
            "container_code": "VAN-12M3",
            "container_type": "12m3 Van",
            "cost_rank": 10,
            "max_weight_kg": 1400,
            "max_volume_m3": 12,
            "is_active": 1,
            "notes": "Urban runs and urgent compact deliveries.",
        },
        {
            "container_name": "Container 20ft Standard",
            "container_code": "CTR-20STD",
            "container_type": "20ft",
            "cost_rank": 20,
            "max_weight_kg": 22000,
            "max_volume_m3": 33,
            "is_active": 1,
            "notes": "Default linehaul for balanced weight and volume.",
        },
        {
            "container_name": "Container 40ft Standard",
            "container_code": "CTR-40STD",
            "container_type": "40ft",
            "cost_rank": 30,
            "max_weight_kg": 26500,
            "max_volume_m3": 67,
            "is_active": 1,
            "notes": "Large-volume consolidation with mixed clients.",
        },
        {
            "container_name": "Heavy Motor Truck",
            "container_code": "TRK-HVY",
            "container_type": "Standard Truck",
            "cost_rank": 15,
            "max_weight_kg": 18000,
            "max_volume_m3": 24,
            "is_active": 1,
            "notes": "Optimized for dense elevator motors and machinery.",
        },
    ]

    for profile in profiles:
        if frappe.db.exists("Container Profile", {"container_code": profile["container_code"]}):
            continue

        doc = frappe.new_doc("Container Profile")
        doc.naming_series = "CP-.#####"
        doc.update(profile)
        doc.insert(ignore_permissions=True)

    _seed_load_plan_scenarios()


def _seed_load_plan_scenarios():
    if not frappe.db.exists("DocType", "Container Load Plan"):
        return

    company = _default_company()
    if not company:
        return

    scenarios = [
        {
            "container_label": "Scenario A - Dense Motors",
            "container_profile": _profile_by_code("TRK-HVY"),
            "destination_zone": "Casablanca Industrial",
            "departure_date": add_days(nowdate(), 1),
            "notes": "Weight-limited scenario with low volume usage.",
        },
        {
            "container_label": "Scenario B - Bulky Rails",
            "container_profile": _profile_by_code("CTR-40STD"),
            "destination_zone": "Rabat North",
            "departure_date": add_days(nowdate(), 2),
            "notes": "Volume-limited scenario with low payload pressure.",
        },
        {
            "container_label": "Scenario C - Balanced Groupage",
            "container_profile": _profile_by_code("CTR-20STD"),
            "destination_zone": "Marrakech South",
            "departure_date": add_days(nowdate(), 3),
            "notes": "Balanced multi-client groupage baseline.",
        },
    ]

    for scenario in scenarios:
        if not scenario.get("container_profile"):
            continue

        if frappe.db.exists(
            "Container Load Plan",
            {
                "container_label": scenario["container_label"],
                "company": company,
                "docstatus": 0,
            },
        ):
            continue

        doc = frappe.new_doc("Container Load Plan")
        doc.naming_series = "CLP-.#####"
        doc.company = company
        doc.status = "Planning"
        doc.analysis_status = "ok"
        doc.update(scenario)
        doc.insert(ignore_permissions=True)


def _profile_by_code(code):
    return frappe.db.get_value("Container Profile", {"container_code": code}, "name")


def _default_company():
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if company:
        return company

    companies = frappe.get_all("Company", pluck="name", limit_page_length=1)
    return companies[0] if companies else None
