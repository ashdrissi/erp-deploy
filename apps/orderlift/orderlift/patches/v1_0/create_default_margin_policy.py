import frappe


def execute():
    if not frappe.db.exists("DocType", "Pricing Margin Policy"):
        return

    existing_default = frappe.db.get_value(
        "Pricing Margin Policy",
        {"is_default": 1, "is_active": 1},
        "name",
    )
    if existing_default:
        _backfill_sheet_policy(existing_default)
        return

    policy = frappe.new_doc("Pricing Margin Policy")
    policy.policy_name = "Default Margin Policy"
    policy.is_active = 1
    policy.is_default = 1
    policy.append(
        "margin_rules",
        {
            "customer_type": "",
            "tier": "",
            "margin_percent": 15,
            "applies_to": "Running Total",
            "sequence": 90,
            "priority": 10,
            "is_active": 1,
        },
    )
    policy.insert(ignore_permissions=True)
    _backfill_sheet_policy(policy.name)


def _backfill_sheet_policy(policy_name):
    if not frappe.db.exists("DocType", "Pricing Sheet"):
        return

    names = frappe.get_all("Pricing Sheet", filters={"margin_policy": ["in", ["", None]]}, pluck="name", limit_page_length=0)
    for name in names:
        frappe.db.set_value("Pricing Sheet", name, "margin_policy", policy_name)
