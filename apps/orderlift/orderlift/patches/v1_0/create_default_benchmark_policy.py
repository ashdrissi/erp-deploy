import frappe


def execute():
    if not frappe.db.exists("DocType", "Pricing Benchmark Policy"):
        return

    existing_default = frappe.db.get_value(
        "Pricing Benchmark Policy",
        {"is_default": 1, "is_active": 1},
        "name",
    )
    if existing_default:
        _backfill_sheet_policy(existing_default)
        return

    policy = frappe.new_doc("Pricing Benchmark Policy")
    policy.policy_name = "Default Pricing Policy"
    policy.is_active = 1
    policy.is_default = 1
    policy.append(
        "benchmark_rules",
        {
            "customer_type": "",
            "target_margin_percent": 15,
            "min_sources_required": 1,
            "fallback_margin": 15,
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

    names = frappe.get_all("Pricing Sheet", filters={"benchmark_policy": ["in", ["", None]]}, pluck="name", limit_page_length=0)
    for name in names:
        frappe.db.set_value("Pricing Sheet", name, "benchmark_policy", policy_name)
