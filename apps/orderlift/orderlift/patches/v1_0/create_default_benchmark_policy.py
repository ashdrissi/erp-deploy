import frappe


def execute():
    """Create a default Pricing Benchmark Policy and backfill existing
    Pricing Margin Policies to Profile-Based mode (preserving old behaviour).
    """
    if not frappe.db.exists("DocType", "Pricing Benchmark Policy"):
        return

    # --- 1. Create default benchmark policy if none exists ---
    existing = frappe.db.get_value(
        "Pricing Benchmark Policy",
        {"is_default": 1, "is_active": 1},
        "name",
    )
    if not existing:
        policy = frappe.new_doc("Pricing Benchmark Policy")
        policy.policy_name = "Default Benchmark Policy"
        policy.is_active = 1
        policy.is_default = 1
        policy.method = "Median"
        policy.min_sources_required = 2
        policy.fallback_margin_percent = 10

        # Seed with Standard Selling as a sample source
        policy.append(
            "benchmark_sources",
            {
                "price_list": "Standard Selling",
                "label": "Standard Selling",
                "weight": 1,
                "is_active": 1,
            },
        )

        # Seed with three default ratio-band rules
        for ratio_min, ratio_max, margin in [
            (0, 0.6, 30),
            (0.6, 0.8, 18),
            (0.8, 0, 8),
        ]:
            policy.append(
                "benchmark_rules",
                {
                    "ratio_min": ratio_min,
                    "ratio_max": ratio_max,
                    "target_margin_percent": margin,
                    "priority": 10,
                    "sequence": 90,
                    "is_active": 1,
                },
            )

        policy.insert(ignore_permissions=True)

    # --- 2. Backfill existing margin policies to Profile-Based ---
    if frappe.db.exists("DocType", "Pricing Margin Policy"):
        policies = frappe.get_all(
            "Pricing Margin Policy",
            filters={"margin_mode": ["in", ["", None]]},
            pluck="name",
            limit_page_length=0,
        )
        for name in policies:
            frappe.db.set_value(
                "Pricing Margin Policy",
                name,
                "margin_mode",
                "Profile-Based",
            )
