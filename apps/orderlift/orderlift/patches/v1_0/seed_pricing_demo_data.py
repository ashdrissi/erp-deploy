import frappe
from frappe.utils import flt


def execute():
    """Seed demo data across all pricing engine doctypes.

    Populates: Benchmark Policy (with tier & zone modifiers),
    Customer Segmentation Engine, Agent Pricing Rules,
    and ensures customers have tiers and territories set.
    """

    _seed_benchmark_policy_modifiers()
    _seed_customer_segmentation_engine()
    _seed_agent_pricing_rules()
    _seed_customer_tiers()

    frappe.db.commit()


# ─────────────────────────────────────────────────────
# 1. Benchmark Policy — add Tier & Zone Modifiers
# ─────────────────────────────────────────────────────

def _seed_benchmark_policy_modifiers():
    if not frappe.db.exists("DocType", "Pricing Benchmark Policy"):
        return

    policy_name = frappe.db.get_value(
        "Pricing Benchmark Policy",
        {"is_default": 1, "is_active": 1},
        "name",
    )
    if not policy_name:
        return

    policy = frappe.get_doc("Pricing Benchmark Policy", policy_name)

    # Tier modifiers (if not already added)
    if not policy.get("tier_modifiers"):
        tier_data = [
            {"tier": "Gold",   "modifier_amount": 0,    "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Silver", "modifier_amount": -10,   "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Bronze", "modifier_amount": -15,   "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Eco",    "modifier_amount": -20,   "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Luxe",   "modifier_amount": 25,    "modifier_type": "Fixed", "is_active": 1},
        ]
        for t in tier_data:
            policy.append("tier_modifiers", t)

    # Zone modifiers
    if not policy.get("zone_modifiers"):
        # Get existing territories
        territories = frappe.get_all("Territory", pluck="name", limit_page_length=10)
        zone_data = []
        for i, terr in enumerate(territories[:5]):
            amounts = [50, 25, 0, -10, 15]
            zone_data.append({
                "territory": terr,
                "modifier_amount": amounts[i % len(amounts)],
                "modifier_type": "Fixed",
                "is_active": 1,
            })

        for z in zone_data:
            policy.append("zone_modifiers", z)

    policy.save(ignore_permissions=True)


# ─────────────────────────────────────────────────────
# 2. Customer Segmentation Engine
# ─────────────────────────────────────────────────────

def _seed_customer_segmentation_engine():
    if not frappe.db.exists("DocType", "Customer Segmentation Engine"):
        return

    if frappe.db.exists("Customer Segmentation Engine", {"engine_name": "Morocco B2B Tier Engine"}):
        return

    engine = frappe.new_doc("Customer Segmentation Engine")
    engine.engine_name = "Morocco B2B Tier Engine"
    engine.target_customer_type = ""
    engine.is_active = 1
    engine.description = "Auto-assigns Gold/Silver/Bronze/Eco tiers based on revenue and RFM scoring."

    rules = [
        {
            "designated_segment": "Gold",
            "variable_1": "Revenue (12 months)",
            "operator_1": "≥ (greater or equal)",
            "value_1": 2000000,
            "connector": "AND",
            "variable_2": "RFM Score",
            "operator_2": "≥ (greater or equal)",
            "value_2": 7,
            "priority": 10,
            "is_active": 1,
        },
        {
            "designated_segment": "Silver",
            "variable_1": "Revenue (12 months)",
            "operator_1": "≥ (greater or equal)",
            "value_1": 800000,
            "connector": "OR",
            "variable_2": "RFM Score",
            "operator_2": "≥ (greater or equal)",
            "value_2": 5,
            "priority": 20,
            "is_active": 1,
        },
        {
            "designated_segment": "Bronze",
            "variable_1": "Revenue (12 months)",
            "operator_1": "≥ (greater or equal)",
            "value_1": 200000,
            "connector": "OR",
            "variable_2": "Total Orders",
            "operator_2": "≥ (greater or equal)",
            "value_2": 5,
            "priority": 30,
            "is_active": 1,
        },
        {
            "designated_segment": "Eco",
            "is_default": 1,
            "priority": 99,
            "is_active": 1,
        },
    ]

    for rule in rules:
        engine.append("segmentation_rules", rule)

    engine.insert(ignore_permissions=True)


# ─────────────────────────────────────────────────────
# 3. Agent Pricing Rules
# ─────────────────────────────────────────────────────

def _seed_agent_pricing_rules():
    if not frappe.db.exists("DocType", "Agent Pricing Rules"):
        return

    sales_persons = frappe.get_all("Sales Person", pluck="name", limit_page_length=5)
    if not sales_persons:
        return

    for i, sp in enumerate(sales_persons):
        if frappe.db.exists("Agent Pricing Rules", {"sales_person": sp}):
            continue

        try:
            apr = frappe.new_doc("Agent Pricing Rules")
            apr.sales_person = sp

            if i % 2 == 0:
                # Dynamic mode
                apr.pricing_mode = "Dynamic Calculation Engine"
                apr.max_discount_percent = 15

                # Set default policies if they exist
                buying_list = frappe.db.get_value("Price List", {"buying": 1}, "name")
                if buying_list:
                    apr.default_buying_price_list = buying_list

                if frappe.db.exists("DocType", "Pricing Margin Rule"):
                    margin_policy = frappe.db.get_value("Pricing Margin Rule", {}, "name")
                    if margin_policy:
                        apr.default_margin_policy = margin_policy

                if frappe.db.exists("DocType", "Pricing Customs Policy"):
                    customs_policy = frappe.db.get_value("Pricing Customs Policy", {}, "name")
                    if customs_policy:
                        apr.default_customs_policy = customs_policy

                if frappe.db.exists("DocType", "Pricing Scenario"):
                    scenario = frappe.db.get_value("Pricing Scenario", {}, "name")
                    if scenario:
                        apr.default_expense_policy = scenario
            else:
                # Static mode
                apr.pricing_mode = "Pick from Published Selling Price List"
                apr.max_discount_percent = 10

                selling_lists = frappe.get_all(
                    "Price List", filters={"selling": 1}, pluck="name", limit_page_length=3
                )
                for seq, pl in enumerate(selling_lists):
                    apr.append("allocated_price_lists", {
                        "selling_price_list": pl,
                        "default_sequence": (seq + 1) * 10,
                        "is_active": 1,
                    })

            apr.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(f"Failed to seed Agent Pricing Rules for {sp}")
            frappe.clear_messages()


# ─────────────────────────────────────────────────────
# 4. Assign tiers to existing customers
# ─────────────────────────────────────────────────────

def _seed_customer_tiers():
    """Assign demo tiers to customers that don't have one yet."""
    if not frappe.db.has_column("Customer", "tier"):
        return

    customers_without_tier = frappe.get_all(
        "Customer",
        filters={"tier": ["in", ["", None]], "disabled": 0},
        pluck="name",
        limit_page_length=0,
    )

    tiers = ["Gold", "Silver", "Bronze", "Eco"]
    for i, cust in enumerate(customers_without_tier):
        tier = tiers[i % len(tiers)]
        frappe.db.set_value("Customer", cust, "tier", tier, update_modified=False)
