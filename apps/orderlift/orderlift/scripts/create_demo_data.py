"""Create demo data for testing logistics features."""
import frappe
from frappe.utils import today, add_days


def create_demo_data():
    """Create demo Container Profiles, Delivery Notes, and Load Plan."""
    print("\n✅ Creating Demo Data...")

    # Container Profiles
    containers = [
        {
            "container_name": "DEMO-20FT-STD",
            "container_type": "20ft",
            "max_weight_kg": 21000,
            "max_volume_m3": 33.0,
            "cost_per_kg": 0.05,
            "cost_per_m3": 3.0,
            "cost_rank": 1,
            "is_active": 1,
        },
        {
            "container_name": "DEMO-40FT-HC",
            "container_type": "40ft",
            "max_weight_kg": 28000,
            "max_volume_m3": 76.0,
            "cost_per_kg": 0.08,
            "cost_per_m3": 2.5,
            "cost_rank": 2,
            "is_active": 1,
        },
        {
            "container_name": "DEMO-TRUCK-10T",
            "container_type": "Standard Truck",
            "max_weight_kg": 10000,
            "max_volume_m3": 18.0,
            "cost_per_kg": 0.12,
            "cost_per_m3": 5.0,
            "cost_rank": 3,
            "is_active": 1,
        },
    ]

    print("\n=== Container Profiles ===")
    container_profile_ids = {}
    for c in containers:
        # Check if container already exists by name field
        existing = frappe.db.get_value("Container Profile", filters={"container_name": c["container_name"]})
        if not existing:
            doc = frappe.new_doc("Container Profile")
            doc.container_name = c["container_name"]
            doc.container_type = c["container_type"]
            doc.max_weight_kg = c["max_weight_kg"]
            doc.max_volume_m3 = c["max_volume_m3"]
            doc.cost_per_kg = c["cost_per_kg"]
            doc.cost_per_m3 = c["cost_per_m3"]
            doc.cost_rank = c["cost_rank"]
            doc.is_active = c["is_active"]
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            container_profile_ids[c['container_name']] = doc.name  # Store the auto-generated ID
            print(f"  ✓ {c['container_name']} (ID: {doc.name})")
        else:
            container_profile_ids[c['container_name']] = existing
            print(f"  ⊘ {c['container_name']} exists (ID: {existing})")

    # Delivery Notes
    print("\n=== Delivery Notes ===")
    dns_data = [
        {"customer": "Ash", "weight": 5000, "volume": 8.5, "zone": "Zone_North"},
        {"customer": "chaabi", "weight": 3500, "volume": 6.2, "zone": "Zone_North"},
        {"customer": "CUST-MAN-PART-ECO", "weight": 4200, "volume": 7.8, "zone": "Zone_South"},
        {"customer": "CUST-MAN-DISTR-BRONZE", "weight": 6500, "volume": 11.3, "zone": "Zone_South"},
        {"customer": "CUST-DYN-INST-BRONZE", "weight": 2800, "volume": 5.1, "zone": "Zone_East"},
    ]

    dn_names = []
    for idx, d in enumerate(dns_data):
        dn = frappe.new_doc("Delivery Note")
        dn.company = "Orderlift"
        dn.customer = d["customer"]
        dn.custom_destination_zone = d["zone"]
        item = dn.append("items", {})
        item.item_code = "IT.146"
        item.item_name = "LEAR POMPE"
        item.qty = 1
        item.rate = 1000
        item.amount = 1000
        item.custom_item_weight_kg = d["weight"]
        item.custom_item_volume_m3 = d["volume"]
        dn.insert(ignore_permissions=True)
        # Mark as pending (draft state) - Load Plan can still reference it
        dn_names.append(dn.name)
        print(f"  ✓ {dn.name} ({d['weight']}kg, {d['volume']}m³) - draft")

    # Container Load Plan
    print("\n=== Container Load Plan ===")
    clp = frappe.new_doc("Container Load Plan")
    clp.company = "Orderlift"
    clp.container_label = f"Demo Load Plan - {today()}"  # Add required label
    clp.container_profile = container_profile_ids.get("DEMO-20FT-STD")  # Use the actual container profile ID
    clp.destination_zone = "Zone_North"
    clp.departure_date = add_days(today(), 3)

    for i, dn_name in enumerate(dn_names[:3]):
        s = clp.append("shipments", {})
        s.delivery_note = dn_name
        s.sequence = (i + 1) * 10

    clp.insert(ignore_permissions=True)
    print(f"  ✓ {clp.name} with {len(dn_names[:3])} shipments")
    print(f"    - Container: DEMO-20FT-STD ({container_profile_ids.get('DEMO-20FT-STD')})")
    print(f"    - Zone: Zone_North")
    print(f"    - Departure: {add_days(today(), 3)}")

    frappe.db.commit()
    print("\n✅ Demo data created successfully!")
    print(f"\nTest URLs:")
    print(f"  http://erp.ecomepivot.com/app/container-profile")
    print(f"  http://erp.ecomepivot.com/app/delivery-note")
    print(f"  http://erp.ecomepivot.com/app/container-load-plan/{clp.name}")
    print(f"  http://erp.ecomepivot.com/app/logistics-hub-cockpit")
