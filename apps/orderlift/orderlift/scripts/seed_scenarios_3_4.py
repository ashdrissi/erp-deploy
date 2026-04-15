"""
Seed Scenarios 3 (Outbound) and 4 (Installation).
Run: bench --site erp.ecomepivot.com execute 'orderlift.scripts.seed_scenarios_3_4.run'
"""
import frappe
from frappe.utils import nowdate, add_days

TODAY = nowdate()
COMPANY = "Orderlift Maroc"
WAREHOUSE = "Entrepot Central (Real Stock) - OLM"

# Get container profile
CP = frappe.db.get_value("Container Profile", {"container_name": "40ft High Cube"})
if not CP:
    CP = frappe.db.get_value("Container Profile", {"container_name": "Container 40ft Standard"})

# Get 3 items
items = frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1}, limit=3)
ITEM_A = items[0].name if len(items) > 0 else None
ITEM_B = items[1].name if len(items) > 1 else None
ITEM_C = items[2].name if len(items) > 2 else None

print(f"Container Profile: {CP}")
print(f"Items: {ITEM_A}, {ITEM_B}, {ITEM_C}")

def ensure_customer(name, group="Commercial", territory="All Territories"):
    existing = frappe.db.exists("Customer", {"customer_name": name})
    if existing:
        print(f"  Customer exists: {existing}")
        return existing
    cust = frappe.new_doc("Customer")
    cust.customer_name = name
    cust.customer_group = group
    cust.territory = territory
    cust.customer_type = "Company"
    try:
        cust.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        print(f"  Customer created: {cust.name}")
        return cust.name
    except Exception as e:
        err = str(e)[:200]
        print(f"  Customer creation failed: {err}")
        # Try with minimal fields
        try:
            cust2 = frappe.new_doc("Customer")
            cust2.customer_name = name
            cust2.customer_group = "Individual"
            cust2.territory = "All Territories"
            cust2.insert(ignore_permissions=True, ignore_mandatory=True)
            frappe.db.commit()
            print(f"  Customer fallback created: {cust2.name}")
            return cust2.name
        except Exception as e2:
            print(f"  Fallback also failed: {str(e2)[:200]}")
            return None

def ensure_lead(name, company_name):
    existing = frappe.db.exists("Lead", {"lead_name": name})
    if existing:
        print(f"  Lead exists: {existing}")
        return existing
    lead = frappe.new_doc("Lead")
    lead.lead_name = name
    lead.company_name = company_name
    lead.source = "Existing Customer"
    lead.status = "Lead"
    try:
        lead.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        print(f"  Lead created: {lead.name}")
        return lead.name
    except Exception as e:
        print(f"  Lead failed: {str(e)[:100]}")
        return None

def run():
    print("\n" + "=" * 60)
    print("SEEDING SCENARIOS 3 & 4")
    print("=" * 60)

    # ============================
    # SCENARIO 3 - OUTBOUND
    # ============================
    print("\n-- SCENARIO 3: OUTBOUND (Export to France) --")
    cust3 = ensure_customer("Scenario 3 - Customer Paris", territory="France")
    if cust3:
        lead3 = ensure_lead("Scenario 3 - Lead Paris", "Scenario 3 - Customer Paris")
        # Quotation
        qt3_name = "Scenario 3 - Quotation"
        if not frappe.db.exists("Quotation", qt3_name):
            qt3 = frappe.new_doc("Quotation")
            qt3.quotation_to = "Customer"
            qt3.party_name = cust3
            qt3.company = COMPANY
            qt3.append("items", {"item_code": ITEM_A, "qty": 10})
            qt3.append("items", {"item_code": ITEM_C, "qty": 8})
            qt3.status = "Open"
            qt3.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  Quotation: {qt3.name}")
        else:
            print(f"  Quotation exists: {qt3_name}")

        # SO
        so3_name = "Scenario 3 - Sales Order"
        actual_so3 = None
        if not frappe.db.exists("Sales Order", so3_name):
            so3 = frappe.new_doc("Sales Order")
            so3.customer = cust3
            so3.company = COMPANY
            so3.transaction_date = TODAY
            so3.delivery_date = add_days(TODAY, 40)
            if ITEM_A:
                so3.append("items", {"item_code": ITEM_A, "qty": 10, "delivery_date": so3.delivery_date, "warehouse": WAREHOUSE})
            if ITEM_C:
                so3.append("items", {"item_code": ITEM_C, "qty": 8, "delivery_date": so3.delivery_date, "warehouse": WAREHOUSE})
            so3.insert(ignore_permissions=True)
            so3.submit()
            frappe.db.commit()
            actual_so3 = so3.name
            print(f"  SO: {actual_so3}")
        else:
            actual_so3 = frappe.db.get_value("Sales Order", so3_name, "name") or so3_name
            print(f"  SO exists: {actual_so3}")

        # Forecast Plan (Outbound)
        if not frappe.db.exists("Forecast Load Plan", {"plan_label": "Scenario 3 - Outbound to Paris"}):
            fp3 = frappe.new_doc("Forecast Load Plan")
            fp3.plan_label = "Scenario 3 - Outbound to Paris"
            fp3.company = COMPANY
            fp3.container_profile = CP
            fp3.route_origin = "Casablanca"
            fp3.route_destination = "Paris"
            fp3.flow_scope = "Outbound"
            fp3.shipping_responsibility = "Orderlift"
            fp3.departure_date = add_days(TODAY, 20)
            fp3.deadline = add_days(TODAY, 35)
            fp3.status = "Ready"
            fp3.append("items", {
                "source_doctype": "Sales Order",
                "source_name": actual_so3,
                "party_type": "Customer",
                "party": cust3,
                "confidence": "committed",
                "planned_qty": 1,
                "original_qty": 1,
                "total_weight_kg": 650,
                "total_volume_m3": 18,
                "selected": 1,
                "sequence": 0,
            })
            fp3.append("items", {
                "is_planned": 1,
                "item_code": ITEM_B,
                "item_name": frappe.db.get_value("Item", ITEM_B, "item_name"),
                "confidence": "tentative",
                "planned_qty": 20,
                "original_qty": 0,
                "total_weight_kg": 100,
                "total_volume_m3": 2,
                "selected": 1,
                "sequence": 1,
            })
            fp3.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  Forecast Plan: {fp3.name} (Ready)")
            # Link source docs
            try:
                from orderlift.orderlift_logistics.services.forecast_planning import _link_source_docs
                _link_source_docs(fp3)
                frappe.db.commit()
            except Exception as e:
                print(f"  Link warning: {e}")
        else:
            fp3_name = frappe.db.get_value("Forecast Load Plan", {"plan_label": "Scenario 3 - Outbound to Paris"})
            print(f"  Forecast Plan exists: {fp3_name}")
    else:
        print("  SKIPPED - customer creation failed")

    # ============================
    # SCENARIO 4 - INSTALLATION
    # ============================
    print("\n-- SCENARIO 4: INSTALLATION (Full Project Flow) --")
    cust4 = ensure_customer("Scenario 4 - Customer Lyon", territory="France")
    if cust4:
        lead4 = ensure_lead("Scenario 4 - Lead Lyon", "Scenario 4 - Customer Lyon")

        # Quotation
        qt4_name = "Scenario 4 - Quotation"
        if not frappe.db.exists("Quotation", qt4_name):
            qt4 = frappe.new_doc("Quotation")
            qt4.quotation_to = "Customer"
            qt4.party_name = cust4
            qt4.company = COMPANY
            qt4.append("items", {"item_code": ITEM_A, "qty": 3})
            qt4.append("items", {"item_code": ITEM_B, "qty": 4})
            qt4.append("items", {"item_code": ITEM_C, "qty": 5})
            qt4.status = "Open"
            qt4.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  Quotation: {qt4.name}")
        else:
            print(f"  Quotation exists: {qt4_name}")

        # SO
        so4_label = "Scenario 4 - Sales Order"
        actual_so4 = None
        if not frappe.db.exists("Sales Order", so4_label):
            so4 = frappe.new_doc("Sales Order")
            so4.customer = cust4
            so4.company = COMPANY
            so4.transaction_date = TODAY
            so4.delivery_date = add_days(TODAY, 25)
            if ITEM_A:
                so4.append("items", {"item_code": ITEM_A, "qty": 3, "delivery_date": so4.delivery_date, "warehouse": WAREHOUSE})
            if ITEM_B:
                so4.append("items", {"item_code": ITEM_B, "qty": 4, "delivery_date": so4.delivery_date, "warehouse": WAREHOUSE})
            if ITEM_C:
                so4.append("items", {"item_code": ITEM_C, "qty": 5, "delivery_date": so4.delivery_date, "warehouse": WAREHOUSE})
            so4.insert(ignore_permissions=True)
            so4.submit()
            frappe.db.commit()
            actual_so4 = so4.name
            print(f"  SO: {actual_so4}")
        else:
            actual_so4 = frappe.db.get_value("Sales Order", so4_label, "name") or so4_label
            print(f"  SO exists: {actual_so4}")

        # Project
        proj4_name = frappe.db.exists("Project", {"project_name": "Scenario 4 - Lyon Installation"})
        if not proj4_name:
            proj4 = frappe.new_doc("Project")
            proj4.project_name = "Scenario 4 - Lyon Installation"
            proj4.customer = cust4
            proj4.status = "Open"
            proj4.company = COMPANY
            proj4.expected_start_date = TODAY
            proj4.expected_end_date = add_days(TODAY, 60)
            proj4.insert(ignore_permissions=True)
            frappe.db.commit()
            proj4_name = proj4.name
            print(f"  Project: {proj4_name}")
        frappe.db.set_value("Sales Order", actual_so4, "project", proj4_name)
        frappe.db.commit()
        print(f"  Project linked: {proj4_name}")

        # QC Template
        qc_name = "Scenario 4 - QC Template"
        if not frappe.db.exists("QC Checklist Template", qc_name):
            qc = frappe.new_doc("QC Checklist Template")
            qc.template_name = qc_name
            qc.append("items", {"item_code": "Check Power Supply", "description": "Verify electrical connections"})
            qc.append("items", {"item_code": "Check Safety Systems", "description": "Test emergency stop"})
            qc.append("items", {"item_code": "Check Door Operation", "description": "Verify door cycles"})
            qc.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  QC Template: {qc.name}")
        else:
            print(f"  QC Template exists: {qc_name}")

        # Delivery Trip (skipped - too many mandatory links)
        print("  Delivery Trip: skipped (needs Address/Vehicle)")

        # Forecast Plan (In Transit)
        if not frappe.db.exists("Forecast Load Plan", {"plan_label": "Scenario 4 - Installation to Lyon"}):
            fp4 = frappe.new_doc("Forecast Load Plan")
            fp4.plan_label = "Scenario 4 - Installation to Lyon"
            fp4.company = COMPANY
            fp4.container_profile = CP
            fp4.route_origin = "Casablanca"
            fp4.route_destination = "Lyon"
            fp4.flow_scope = "Outbound"
            fp4.shipping_responsibility = "Orderlift"
            fp4.departure_date = add_days(TODAY, -10)
            fp4.deadline = add_days(TODAY, 5)
            fp4.status = "In Transit"
            fp4.append("items", {
                "source_doctype": "Sales Order",
                "source_name": actual_so4,
                "party_type": "Customer",
                "party": cust4,
                "confidence": "committed",
                "planned_qty": 1,
                "original_qty": 1,
                "total_weight_kg": 400,
                "total_volume_m3": 12,
                "selected": 1,
                "sequence": 0,
            })
            fp4.append("items", {
                "is_planned": 1,
                "item_code": ITEM_B,
                "item_name": frappe.db.get_value("Item", ITEM_B, "item_name"),
                "confidence": "committed",
                "planned_qty": 15,
                "original_qty": 0,
                "total_weight_kg": 75,
                "total_volume_m3": 1.5,
                "selected": 1,
                "sequence": 1,
            })
            fp4.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  Forecast Plan: {fp4.name} (In Transit)")
            try:
                from orderlift.orderlift_logistics.services.forecast_planning import _link_source_docs
                _link_source_docs(fp4)
                frappe.db.commit()
            except Exception as e:
                print(f"  Link warning: {e}")
        else:
            fp4_name = frappe.db.get_value("Forecast Load Plan", {"plan_label": "Scenario 4 - Installation to Lyon"})
            print(f"  Forecast Plan exists: {fp4_name}")
    else:
        print("  SKIPPED - customer creation failed")

    # Summary
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    for dt in ["Lead", "Customer", "Quotation", "Sales Order", "Forecast Load Plan", "Project", "Delivery Trip"]:
        count = frappe.db.count(dt, {"name": ["like", "Scenario%"]})
        if count:
            print(f"  {dt}: {count}")

    fps = frappe.get_all("Forecast Load Plan", filters={"plan_label": ["like", "Scenario%"]}, fields=["name", "plan_label", "status", "flow_scope"])
    print(f"\n  Forecast Plans:")
    for fp in fps:
        print(f"    {fp.name}: {fp.plan_label} [{fp.status}] -- {fp.flow_scope}")
