"""Comprehensive demo data seeder for the entire Orderlift Pricing Engine.

Run via:  bench --site <site> execute orderlift.seed_all_demo.execute
"""
import frappe
from frappe.utils import flt, nowdate, add_days, random_string
import random


def execute():
    """Seed rich demo data across ALL pricing engine doctypes."""

    _seed_customers_and_tiers()
    _seed_pricing_scenarios()
    _seed_customs_policies()
    _seed_margin_policies()
    _seed_benchmark_policy()
    _seed_market_prices()
    _seed_scenario_policies()
    _seed_agent_pricing_rules()
    _seed_segmentation_engine()
    _seed_pricing_sheet()

    frappe.db.commit()
    print("\n✅  All demo data seeded successfully!")


# ─────────────────────────────────────────────────────
# 1. Customers & Tiers
# ─────────────────────────────────────────────────────

def _seed_customers_and_tiers():
    print("→ Seeding customers & tiers…")
    tiers = ["Gold", "Silver", "Bronze", "Eco"]
    types = ["Installateur", "Distributeur", "Promoteur", "Particulier"]
    segments = ["B2B", "B2B", "B2B", "B2C"]

    demo_customers = [
        {"name": "Atlas Distribution SARL", "tier": "Gold", "type": "Distributeur", "seg": "B2B"},
        {"name": "Maghreb Plomberie SA", "tier": "Silver", "type": "Installateur", "seg": "B2B"},
        {"name": "Casablanca Bâtiment", "tier": "Bronze", "type": "Promoteur", "seg": "B2B"},
        {"name": "Rabat Sanitaire", "tier": "Silver", "type": "Distributeur", "seg": "B2B"},
        {"name": "Marrakech Bricolage", "tier": "Eco", "type": "Particulier", "seg": "B2C"},
        {"name": "Tanger Construction Pro", "tier": "Gold", "type": "Promoteur", "seg": "B2B"},
        {"name": "Fès Matériaux", "tier": "Bronze", "type": "Installateur", "seg": "B2B"},
        {"name": "Agadir Steel Import", "tier": "Gold", "type": "Distributeur", "seg": "B2B"},
    ]

    territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"

    for c in demo_customers:
        if frappe.db.exists("Customer", {"customer_name": c["name"]}):
            # Update tier on existing
            cust_id = frappe.db.get_value("Customer", {"customer_name": c["name"]}, "name")
            frappe.db.set_value("Customer", cust_id, {
                "customer_group": frappe.db.get_value("Customer Group", {}, "name") or "All Customer Groups",
            })
            continue

        try:
            cust = frappe.new_doc("Customer")
            cust.customer_name = c["name"]
            cust.customer_type = "Company" if c["seg"] == "B2B" else "Individual"
            cust.customer_group = frappe.db.get_value("Customer Group", {}, "name") or "All Customer Groups"
            cust.territory = territory
            cust.insert(ignore_permissions=True)
            print(f"   Created customer: {c['name']}")
        except Exception:
            pass

    # Also assign tiers to ALL customers that don't have one
    all_custs = frappe.get_all("Customer", filters={"disabled": 0}, pluck="name")
    for i, cust_id in enumerate(all_custs):
        tier = tiers[i % len(tiers)]
        # Use custom field if it exists, otherwise skip
        if frappe.db.has_column("Customer", "tier"):
            frappe.db.set_value("Customer", cust_id, "tier", tier, update_modified=False)

    print(f"   Assigned tiers to {len(all_custs)} customers")


# ─────────────────────────────────────────────────────
# 2. Pricing Scenarios (with expenses)
# ─────────────────────────────────────────────────────

def _seed_pricing_scenarios():
    print("→ Seeding pricing scenarios…")

    buying_list = frappe.db.get_value("Price List", {"buying": 1}, "name")
    selling_list = frappe.db.get_value("Price List", {"selling": 1}, "name")

    scenarios = [
        {
            "scenario_name": "Morocco Import – Full Container",
            "description": "Full 40ft container import from China/Turkey — includes all standard expenses.",
            "transport_is_active": 1,
            "transport_container_type": "40ft HC",
            "transport_allocation_mode": "By Value",
            "transport_container_price": 28000,
            "transport_total_merch_value": 850000,
            "expenses": [
                {"sequence": 10, "label": "Freight Forwarding Fee", "type": "Fixed", "value": 3500, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 20, "label": "Port Handling", "type": "Fixed", "value": 1200, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 30, "label": "Insurance (0.35%)", "type": "Percentage", "value": 0.35, "scope": "Per Unit", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 40, "label": "Customs Clearance Fee", "type": "Fixed", "value": 2800, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 50, "label": "Inland Transport", "type": "Fixed", "value": 4500, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 60, "label": "Warehouse Handling", "type": "Percentage", "value": 1.5, "scope": "Per Unit", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 70, "label": "Quality Inspection", "type": "Fixed", "value": 800, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
            ],
        },
        {
            "scenario_name": "Morocco Import – Groupage (LCL)",
            "description": "Less-than-container-load groupage shipment — higher per-unit costs.",
            "transport_is_active": 1,
            "transport_container_type": "LCL Groupage",
            "transport_allocation_mode": "By Kg",
            "transport_container_price": 8500,
            "transport_total_weight_kg": 3200,
            "expenses": [
                {"sequence": 10, "label": "Freight (LCL surcharge)", "type": "Fixed", "value": 1800, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 20, "label": "Port Handling", "type": "Fixed", "value": 900, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 30, "label": "Insurance (0.5%)", "type": "Percentage", "value": 0.5, "scope": "Per Unit", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 40, "label": "Customs Clearance Fee", "type": "Fixed", "value": 2200, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 50, "label": "Inland Delivery", "type": "Fixed", "value": 2000, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
            ],
        },
        {
            "scenario_name": "Local Purchase – No Import",
            "description": "Direct purchase from local Moroccan suppliers — minimal expenses.",
            "transport_is_active": 0,
            "expenses": [
                {"sequence": 10, "label": "Local Transport", "type": "Fixed", "value": 500, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 20, "label": "Handling & Storage", "type": "Percentage", "value": 1.0, "scope": "Per Unit", "applies_to": "Base Price", "is_active": 1},
            ],
        },
        {
            "scenario_name": "European Import – Palletized",
            "description": "Import from EU (Spain, Italy, Germany) with palletized shipping.",
            "transport_is_active": 1,
            "transport_container_type": "Euro Pallet Truck",
            "transport_allocation_mode": "By Value",
            "transport_container_price": 12000,
            "transport_total_merch_value": 350000,
            "expenses": [
                {"sequence": 10, "label": "EU Freight (Road)", "type": "Fixed", "value": 6000, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 20, "label": "Ferry Crossing", "type": "Fixed", "value": 1500, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 30, "label": "Insurance (0.25%)", "type": "Percentage", "value": 0.25, "scope": "Per Unit", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 40, "label": "Customs Clearance", "type": "Fixed", "value": 2000, "scope": "Per Sheet", "applies_to": "Base Price", "is_active": 1},
                {"sequence": 50, "label": "Warehouse Receiving", "type": "Percentage", "value": 0.8, "scope": "Per Unit", "applies_to": "Base Price", "is_active": 1},
            ],
        },
    ]

    for s in scenarios:
        if frappe.db.exists("Pricing Scenario", {"scenario_name": s["scenario_name"]}):
            continue

        try:
            doc = frappe.new_doc("Pricing Scenario")
            doc.scenario_name = s["scenario_name"]
            doc.description = s.get("description", "")
            if buying_list:
                doc.buying_price_list = buying_list
            doc.transport_is_active = s.get("transport_is_active", 0)
            doc.transport_container_type = s.get("transport_container_type", "")
            doc.transport_allocation_mode = s.get("transport_allocation_mode", "By Value")
            doc.transport_container_price = s.get("transport_container_price", 0)
            doc.transport_total_merch_value = s.get("transport_total_merch_value", 0)
            doc.transport_total_weight_kg = s.get("transport_total_weight_kg", 0)
            doc.transport_total_volume_m3 = s.get("transport_total_volume_m3", 0)

            # Only set benchmark_price_list if a valid selling list exists
            if selling_list:
                doc.benchmark_price_list = selling_list

            for exp in s.get("expenses", []):
                doc.append("expenses", exp)

            doc.insert(ignore_permissions=True)
            print(f"   Created scenario: {s['scenario_name']} ({len(s.get('expenses',[]))} expenses)")
        except Exception as e:
            print(f"   ⚠ Failed to create scenario {s['scenario_name']}: {e}")


# ─────────────────────────────────────────────────────
# 3. Customs Policies (with rules)
# ─────────────────────────────────────────────────────

def _seed_customs_policies():
    print("→ Seeding customs policies…")

    policies = [
        {
            "policy_name": "Morocco Standard Import Duties",
            "company": None,
            "is_active": 1,
            "is_default": 1,
            "notes": "Standard Moroccan customs duties by material type. Updated for 2026 tariff schedule.",
            "rules": [
                {"material": "STEEL",  "rate_per_kg": 0.5,  "rate_percent": 2.5,  "sequence": 10, "priority": 10, "is_active": 1, "notes": "HS 7208-7229 — Hot/Cold rolled steel"},
                {"material": "GALVA",  "rate_per_kg": 0.5,  "rate_percent": 2.5,  "sequence": 20, "priority": 10, "is_active": 1, "notes": "HS 7210 — Galvanized steel products"},
                {"material": "INOX",   "rate_per_kg": 0.8,  "rate_percent": 2.5,  "sequence": 30, "priority": 10, "is_active": 1, "notes": "HS 7218-7223 — Stainless steel"},
                {"material": "ALUM",   "rate_per_kg": 1.2,  "rate_percent": 10.0, "sequence": 40, "priority": 10, "is_active": 1, "notes": "HS 7601-7616 — Aluminum & products"},
                {"material": "COPPER", "rate_per_kg": 2.0,  "rate_percent": 2.5,  "sequence": 50, "priority": 10, "is_active": 1, "notes": "HS 7401-7419 — Copper & products"},
                {"material": "OTHER",  "rate_per_kg": 0.3,  "rate_percent": 25.0, "sequence": 90, "priority": 10, "is_active": 1, "notes": "Default rate for unlisted materials"},
            ],
        },
        {
            "policy_name": "EU Free Trade Agreement Duties",
            "company": None,
            "is_active": 1,
            "is_default": 0,
            "notes": "Reduced duties under Morocco-EU Association Agreement (EUR.1 certificate required).",
            "rules": [
                {"material": "STEEL",  "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 10, "priority": 10, "is_active": 1, "notes": "Zero duty with EUR.1"},
                {"material": "GALVA",  "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 20, "priority": 10, "is_active": 1, "notes": "Zero duty with EUR.1"},
                {"material": "INOX",   "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 30, "priority": 10, "is_active": 1, "notes": "Zero duty with EUR.1"},
                {"material": "ALUM",   "rate_per_kg": 0.5, "rate_percent": 2.5,  "sequence": 40, "priority": 10, "is_active": 1, "notes": "Reduced rate with EUR.1"},
                {"material": "COPPER", "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 50, "priority": 10, "is_active": 1, "notes": "Zero duty with EUR.1"},
                {"material": "OTHER",  "rate_per_kg": 0, "rate_percent": 10.0, "sequence": 90, "priority": 10, "is_active": 1, "notes": "Reduced rate with EUR.1"},
            ],
        },
        {
            "policy_name": "Turkey FTA Duties",
            "company": None,
            "is_active": 1,
            "is_default": 0,
            "notes": "Morocco-Turkey Free Trade Agreement rates.",
            "rules": [
                {"material": "STEEL",  "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 10, "priority": 10, "is_active": 1, "notes": "Zero duty under FTA"},
                {"material": "GALVA",  "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 20, "priority": 10, "is_active": 1, "notes": "Zero duty under FTA"},
                {"material": "INOX",   "rate_per_kg": 0.4, "rate_percent": 1.25, "sequence": 30, "priority": 10, "is_active": 1, "notes": "Reduced rate under FTA"},
                {"material": "ALUM",   "rate_per_kg": 0.8, "rate_percent": 5.0,  "sequence": 40, "priority": 10, "is_active": 1, "notes": "Reduced rate under FTA"},
                {"material": "COPPER", "rate_per_kg": 0, "rate_percent": 0.0,  "sequence": 50, "priority": 10, "is_active": 1, "notes": "Zero duty under FTA"},
                {"material": "OTHER",  "rate_per_kg": 0, "rate_percent": 12.5, "sequence": 90, "priority": 10, "is_active": 1, "notes": "Reduced rate under FTA"},
            ],
        },
    ]

    for p in policies:
        if frappe.db.exists("Pricing Customs Policy", {"policy_name": p["policy_name"]}):
            continue

        try:
            doc = frappe.new_doc("Pricing Customs Policy")
            doc.policy_name = p["policy_name"]
            doc.is_active = p["is_active"]
            doc.is_default = p["is_default"]
            doc.notes = p.get("notes", "")
            if p.get("company"):
                doc.company = p["company"]

            for r in p.get("rules", []):
                doc.append("customs_rules", r)

            doc.insert(ignore_permissions=True)
            print(f"   Created customs policy: {p['policy_name']} ({len(p['rules'])} rules)")
        except Exception as e:
            print(f"   ⚠ Failed: {e}")


# ─────────────────────────────────────────────────────
# 4. Margin Policies (with rules)
# ─────────────────────────────────────────────────────

def _seed_margin_policies():
    print("→ Seeding margin policies…")

    policies = [
        {
            "policy_name": "Standard B2B Margin Schedule",
            "is_active": 1,
            "is_default": 1,
            "notes": "Default margin schedule for B2B customers. Rules are evaluated top-down by priority.",
            "rules": [
                {"margin_percent": 35, "tier": "Luxe", "customer_segment": "B2B", "priority": 10, "sequence": 10, "is_active": 1, "notes": "Premium Luxe clients get 35% margin"},
                {"margin_percent": 30, "tier": "Intermediaire", "customer_segment": "B2B", "priority": 20, "sequence": 20, "is_active": 1, "notes": "Intermediaire tier standard"},
                {"margin_percent": 25, "tier": "Eco", "customer_segment": "B2B", "priority": 30, "sequence": 30, "is_active": 1, "notes": "Eco — competitive pricing"},
                {"margin_percent": 22, "customer_segment": "B2B", "material": "STEEL", "priority": 50, "sequence": 50, "is_active": 1, "notes": "Steel fallback — lower margin due to competition"},
                {"margin_percent": 28, "customer_segment": "B2B", "material": "COPPER", "priority": 50, "sequence": 60, "is_active": 1, "notes": "Copper — higher margin opportunity"},
                {"margin_percent": 25, "priority": 99, "sequence": 99, "is_active": 1, "notes": "Default fallback 25%"},
            ],
        },
        {
            "policy_name": "B2C Retail Margin",
            "is_active": 1,
            "is_default": 0,
            "notes": "Higher margins for retail / individual customers.",
            "rules": [
                {"margin_percent": 45, "customer_segment": "B2C", "priority": 10, "sequence": 10, "is_active": 1, "notes": "Retail margin 45%"},
                {"margin_percent": 50, "customer_segment": "B2C", "material": "COPPER", "priority": 5, "sequence": 5, "is_active": 1, "notes": "Copper retail — premium 50%"},
                {"margin_percent": 40, "priority": 99, "sequence": 99, "is_active": 1, "notes": "Default retail fallback"},
            ],
        },
        {
            "policy_name": "Aggressive Competitor Match",
            "is_active": 1,
            "is_default": 0,
            "notes": "Low-margin policy for competitive situations. Use when matching competitor pricing.",
            "rules": [
                {"margin_percent": 12, "priority": 10, "sequence": 10, "is_active": 1, "notes": "Aggressive 12% margin across the board"},
                {"margin_percent": 8,  "material": "STEEL", "priority": 5, "sequence": 5, "is_active": 1, "notes": "Steel — ultra-competitive 8%"},
            ],
        },
    ]

    for p in policies:
        if frappe.db.exists("Pricing Margin Policy", {"policy_name": p["policy_name"]}):
            continue

        try:
            doc = frappe.new_doc("Pricing Margin Policy")
            doc.policy_name = p["policy_name"]
            doc.is_active = p["is_active"]
            doc.is_default = p["is_default"]
            doc.notes = p.get("notes", "")

            for r in p.get("rules", []):
                doc.append("margin_rules", r)

            doc.insert(ignore_permissions=True)
            print(f"   Created margin policy: {p['policy_name']} ({len(p['rules'])} rules)")
        except Exception as e:
            print(f"   ⚠ Failed: {e}")


# ─────────────────────────────────────────────────────
# 5. Benchmark Policy — sources & rules
# ─────────────────────────────────────────────────────

def _seed_benchmark_policy():
    print("→ Seeding benchmark policy data…")

    policy_name = frappe.db.get_value("Pricing Benchmark Policy", {"is_default": 1}, "name")
    if not policy_name:
        policy_name = frappe.db.get_value("Pricing Benchmark Policy", {}, "name")
    if not policy_name:
        print("   No Benchmark Policy found — skipping")
        return

    doc = frappe.get_doc("Pricing Benchmark Policy", policy_name)

    # Add benchmark sources if empty
    if not doc.get("benchmark_sources"):
        selling_lists = frappe.get_all("Price List", filters={"selling": 1}, pluck="name", limit=3)
        for i, pl in enumerate(selling_lists):
            doc.append("benchmark_sources", {
                "source_price_list": pl,
                "weight": round(1.0 / max(len(selling_lists), 1), 2),
                "is_active": 1,
            })

        # Also add market price as a source if the table supports it
        if selling_lists:
            print(f"   Added {len(selling_lists)} benchmark sources")

    # Make sure tier & zone modifiers are populated
    if not doc.get("tier_modifiers"):
        for t in [
            {"tier": "Gold",   "modifier_amount": 0,    "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Silver", "modifier_amount": -10,  "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Bronze", "modifier_amount": -15,  "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Eco",    "modifier_amount": -20,  "modifier_type": "Fixed", "is_active": 1},
            {"tier": "Luxe",   "modifier_amount": 25,   "modifier_type": "Fixed", "is_active": 1},
        ]:
            doc.append("tier_modifiers", t)
        print("   Added tier modifiers")

    if not doc.get("zone_modifiers"):
        territories = frappe.get_all("Territory", filters={"is_group": 0}, pluck="name", limit=5)
        amounts = [50, 25, 0, -10, 15]
        for i, terr in enumerate(territories[:5]):
            doc.append("zone_modifiers", {
                "territory": terr,
                "modifier_amount": amounts[i % len(amounts)],
                "modifier_type": "Fixed",
                "is_active": 1,
            })
        print(f"   Added {min(len(territories), 5)} zone modifiers")

    doc.save(ignore_permissions=True)
    print(f"   Benchmark policy {policy_name} updated")


# ─────────────────────────────────────────────────────
# 6. Market Price Entries
# ─────────────────────────────────────────────────────

def _seed_market_prices():
    print("→ Seeding market price entries…")

    items = frappe.get_all("Item", filters={"disabled": 0, "is_sales_item": 1}, pluck="name", limit=15)
    if not items:
        items = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=15)

    sources = ["Competitor A", "Competitor B", "Alibaba", "Made-in-China", "Market Survey", "TradeKey"]

    count = 0
    for item in items[:10]:
        for source in random.sample(sources, min(3, len(sources))):
            if frappe.db.exists("Market Price Entry", {"item": item, "source_name": source}):
                continue

            try:
                base = random.uniform(50, 5000)
                mp = frappe.new_doc("Market Price Entry")
                mp.item = item
                mp.source_name = source
                mp.price = round(base, 2)
                mp.currency = "MAD"
                mp.entry_date = add_days(nowdate(), -random.randint(1, 90))
                mp.notes = f"Collected from {source}"
                mp.insert(ignore_permissions=True)
                count += 1
            except Exception:
                pass

    print(f"   Created {count} market price entries")


# ─────────────────────────────────────────────────────
# 7. Scenario Policies (assignment rules)
# ─────────────────────────────────────────────────────

def _seed_scenario_policies():
    print("→ Seeding scenario policies…")

    if frappe.db.exists("Pricing Scenario Policy", {"policy_name": "Morocco Default Routing"}):
        return

    scenarios = frappe.get_all("Pricing Scenario", pluck="name", limit=4)
    if not scenarios:
        print("   No scenarios found — skipping")
        return

    try:
        doc = frappe.new_doc("Pricing Scenario Policy")
        doc.policy_name = "Morocco Default Routing"
        doc.is_active = 1
        doc.is_default = 1
        doc.notes = "Routes items to the correct pricing scenario based on material, territory, and customer segment."

        territories = frappe.get_all("Territory", filters={"is_group": 0}, pluck="name", limit=5)

        # Rule 1: Steel items → Full Container scenario
        if len(scenarios) >= 1:
            doc.append("scenario_rules", {
                "pricing_scenario": scenarios[0],
                "material": "STEEL",
                "priority": 10,
                "sequence": 10,
                "is_active": 1,
                "notes": "Steel imports via full container",
            })

        # Rule 2: Copper items → Groupage
        if len(scenarios) >= 2:
            doc.append("scenario_rules", {
                "pricing_scenario": scenarios[1],
                "material": "COPPER",
                "priority": 20,
                "sequence": 20,
                "is_active": 1,
                "notes": "Copper via groupage (smaller volumes)",
            })

        # Rule 3: Local territory → Local purchase
        if len(scenarios) >= 3 and territories:
            doc.append("scenario_rules", {
                "pricing_scenario": scenarios[2],
                "geography_territory": territories[0] if territories else None,
                "priority": 30,
                "sequence": 30,
                "is_active": 1,
                "notes": "Local territory → local purchase scenario",
            })

        # Rule 4: Default fallback
        if scenarios:
            doc.append("scenario_rules", {
                "pricing_scenario": scenarios[0],
                "priority": 99,
                "sequence": 99,
                "is_active": 1,
                "notes": "Default fallback scenario",
            })

        doc.insert(ignore_permissions=True)
        print(f"   Created scenario policy: Morocco Default Routing")
    except Exception as e:
        print(f"   ⚠ Failed: {e}")


# ─────────────────────────────────────────────────────
# 8. Agent Pricing Rules
# ─────────────────────────────────────────────────────

def _seed_agent_pricing_rules():
    print("→ Seeding agent pricing rules…")

    sales_persons = frappe.get_all("Sales Person", pluck="name", limit_page_length=5)
    if not sales_persons:
        print("   No sales persons found — skipping")
        return

    for i, sp in enumerate(sales_persons):
        if frappe.db.exists("Agent Pricing Rules", {"sales_person": sp}):
            continue

        try:
            apr = frappe.new_doc("Agent Pricing Rules")
            apr.sales_person = sp

            if i % 2 == 0:
                apr.pricing_mode = "Dynamic Calculation Engine"
                apr.max_discount_percent = 15

                buying_list = frappe.db.get_value("Price List", {"buying": 1}, "name")
                scenario = None
                if buying_list:
                    apr.default_buying_price_list = buying_list

                if frappe.db.exists("DocType", "Pricing Benchmark Policy"):
                    pricing_policy = frappe.db.get_value("Pricing Benchmark Policy", {}, "name")
                    if pricing_policy:
                        apr.default_benchmark_policy = pricing_policy

                if frappe.db.exists("DocType", "Pricing Customs Policy"):
                    customs = frappe.db.get_value("Pricing Customs Policy", {}, "name")
                    if customs:
                        apr.default_customs_policy = customs

                if frappe.db.exists("DocType", "Pricing Scenario"):
                    scenario = frappe.db.get_value("Pricing Scenario", {}, "name")
                    if scenario:
                        apr.default_expense_policy = scenario

                if buying_list and scenario:
                    apr.append("dynamic_pricing_configs", {
                        "buying_price_list": buying_list,
                        "pricing_scenario": scenario,
                        "customs_policy": apr.default_customs_policy,
                        "benchmark_policy": apr.default_benchmark_policy,
                        "priority": 10,
                        "is_default": 1,
                        "is_active": 1,
                    })
            else:
                apr.pricing_mode = "Pick from Published Selling Price List"
                apr.max_discount_percent = 10

                selling_lists = frappe.get_all("Price List", filters={"selling": 1}, pluck="name", limit=3)
                for seq, pl in enumerate(selling_lists):
                    apr.append("allocated_price_lists", {
                        "selling_price_list": pl,
                        "default_sequence": (seq + 1) * 10,
                        "is_active": 1,
                    })

            apr.insert(ignore_permissions=True)
            print(f"   Created agent rule: {sp} → {apr.pricing_mode}")
        except Exception as e:
            print(f"   ⚠ Failed for {sp}: {e}")
            frappe.clear_messages()


# ─────────────────────────────────────────────────────
# 9. Customer Segmentation Engine
# ─────────────────────────────────────────────────────

def _seed_segmentation_engine():
    print("→ Seeding segmentation engine…")

    if frappe.db.exists("Customer Segmentation Engine", {"engine_name": "Morocco B2B Tier Engine"}):
        print("   Already exists — skipping")
        return

    engine = frappe.new_doc("Customer Segmentation Engine")
    engine.engine_name = "Morocco B2B Tier Engine"
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
    print("   Created Morocco B2B Tier Engine")


# ─────────────────────────────────────────────────────
# 10. Pricing Sheet
# ─────────────────────────────────────────────────────

def _seed_pricing_sheet():
    print("→ Seeding demo pricing sheet…")

    if frappe.db.exists("Pricing Sheet", {"sheet_name": "Demo B2B Import Quotation"}):
        print("   Already exists — skipping")
        return

    items = frappe.get_all("Item", filters={"disabled": 0, "is_sales_item": 1}, pluck="name", limit=4)
    if not items:
        # Fallback to any items if no sales items exist
        items = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=4)
        
    if not items:
        print("   No items found — skipping")
        return

    customer = frappe.get_value("Customer", {"customer_name": "Atlas Distribution SARL"}, "name")
    if not customer:
        customer = frappe.get_all("Customer", pluck="name", limit=1)
        if customer:
            customer = customer[0]

    if not customer:
        print("   No customers found — skipping")
        return

    try:
        doc = frappe.new_doc("Pricing Sheet")
        doc.sheet_name = "Demo B2B Import Quotation"
        doc.customer = customer

        # Set policies explicitly to ensure rich data
        pricing_policy = frappe.db.get_value("Pricing Benchmark Policy", {"is_active": 1}, "name")
        customs_policy = frappe.db.get_value("Pricing Customs Policy", {"is_active": 1}, "name")
        scenario_policy = frappe.db.get_value("Pricing Scenario Policy", {"is_active": 1}, "name")
        
        if pricing_policy: doc.benchmark_policy = pricing_policy
        if customs_policy: doc.customs_policy = customs_policy
        if scenario_policy: doc.scenario_policy = scenario_policy
        
        scenario = frappe.db.get_value("Pricing Scenario", {}, "name")
        if scenario: doc.pricing_scenario = scenario

        for item in items:
            doc.append("lines", {
                "item": item,
                "qty": random.randint(10, 150)
            })

        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"   Created Pricing Sheet: {doc.name}")
    except Exception as e:
        print(f"   ⚠ Failed: {e}")
