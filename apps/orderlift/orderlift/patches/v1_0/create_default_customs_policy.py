import frappe


def execute():
    if not frappe.db.exists("DocType", "Pricing Customs Policy"):
        return

    existing_default = frappe.db.get_value(
        "Pricing Customs Policy",
        {"is_default": 1, "is_active": 1},
        "name",
    )
    if existing_default:
        _backfill_sheet_policy(existing_default)
        return

    policy = frappe.new_doc("Pricing Customs Policy")
    policy.policy_name = "Default Customs Policy"
    policy.is_active = 1
    policy.is_default = 1
    policy.append(
        "customs_rules",
        {
            "material": "",
            "rate_per_kg": 0,
            "rate_percent": 0,
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
        filters={"customs_policy": ["in", ["", None]]},
        pluck="name",
        limit_page_length=0,
    )
    for name in names:
        frappe.db.set_value("Pricing Sheet", name, "customs_policy", policy_name)
