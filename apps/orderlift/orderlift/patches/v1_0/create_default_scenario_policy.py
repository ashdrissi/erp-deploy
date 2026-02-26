import frappe


def execute():
    if not frappe.db.exists("DocType", "Pricing Scenario Policy"):
        return

    existing_default = frappe.db.get_value(
        "Pricing Scenario Policy",
        {"is_default": 1, "is_active": 1},
        "name",
    )
    if existing_default:
        _backfill_sheet_policy(existing_default)
        return

    default_scenario = frappe.db.get_value("Pricing Scenario", {}, "name")
    if not default_scenario:
        return

    policy = frappe.new_doc("Pricing Scenario Policy")
    policy.policy_name = "Default Scenario Policy"
    policy.is_active = 1
    policy.is_default = 1
    policy.append(
        "scenario_rules",
        {
            "pricing_scenario": default_scenario,
            "sequence": 90,
            "priority": 10,
            "is_active": 1,
            "notes": "Fallback rule",
        },
    )
    policy.insert(ignore_permissions=True)
    _backfill_sheet_policy(policy.name)


def _backfill_sheet_policy(policy_name):
    if not frappe.db.exists("DocType", "Pricing Sheet"):
        return

    names = frappe.get_all(
        "Pricing Sheet",
        filters={"scenario_policy": ["in", ["", None]]},
        pluck="name",
        limit_page_length=0,
    )
    for name in names:
        frappe.db.set_value("Pricing Sheet", name, "scenario_policy", policy_name)
