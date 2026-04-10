"""
Domestic Dispatch
-----------------
Create Delivery Trip from domestic/outbound Container Load Plans or
standalone Delivery Notes.

Supports:
  - Domestic + Orderlift → Delivery Trip from CLP or DN
  - Outbound + Orderlift → Delivery Trip for local leg only

Blocked:
  - Inbound → no Delivery Trip (handled by scenario_guard.py)
  - Outbound + Customer → no Delivery Trip (customer manages shipping)
"""

import frappe


@frappe.whitelist()
def create_delivery_trip_from_load_plan(load_plan_name):
    """Create a Delivery Trip from a Domestic or Outbound/Orderlift CLP.

    Collects all Delivery Notes from the plan and creates one trip with
    multiple stops.

    Args:
        load_plan_name: Name of the Container Load Plan.

    Returns:
        dict with the new Delivery Trip name.
    """
    plan = frappe.get_doc("Container Load Plan", load_plan_name)

    # Validate scenario
    allowed = (
        plan.flow_scope == "Domestic"
        or (plan.flow_scope == "Outbound" and plan.shipping_responsibility == "Orderlift")
    )
    if not allowed:
        frappe.throw(
            "Delivery Trip can only be created for Domestic or Outbound/Orderlift plans.",
            title="Invalid Scenario",
        )

    if plan.source_type != "Delivery Note":
        frappe.throw(
            "Delivery Trip can only be created from plans with Delivery Note as source.",
            title="Invalid Source Type",
        )

    # Check for existing trip linked to this CLP
    existing = frappe.get_all(
        "Delivery Trip",
        filters={"custom_container_load_plan": plan.name, "docstatus": ["!=", 2]},
        limit=1,
    )
    if existing:
        frappe.throw(
            f"A Delivery Trip already exists for this plan: {existing[0].name}",
            title="Trip Already Exists",
        )

    trip = frappe.new_doc("Delivery Trip")
    trip.company = plan.company
    trip.custom_flow_scope = plan.flow_scope
    trip.custom_container_load_plan = plan.name

    stops_added = 0
    for row in plan.shipments or []:
        if not row.delivery_note:
            continue
        dn = frappe.get_doc("Delivery Note", row.delivery_note)
        trip.append("delivery_stops", {
            "delivery_note": row.delivery_note,
            "customer": row.customer or dn.customer,
            "address": dn.shipping_address_name or "",
            "customer_address": dn.shipping_address_name or "",
        })
        stops_added += 1

    if not stops_added:
        frappe.throw("No Delivery Notes found in this plan to create stops from.")

    trip.flags.ignore_permissions = True
    trip.insert()

    frappe.msgprint(
        f"Delivery Trip <b>{trip.name}</b> created with {stops_added} stop(s).",
        indicator="green",
        alert=True,
    )
    return {"delivery_trip": trip.name, "stops": stops_added}


@frappe.whitelist()
def create_delivery_trip_from_delivery_note(delivery_note_name):
    """Create a Delivery Trip directly from a single Delivery Note.

    For domestic DNs or outbound/orderlift DNs that need a local dispatch leg.

    Args:
        delivery_note_name: Name of the Delivery Note.

    Returns:
        dict with the new Delivery Trip name.
    """
    dn = frappe.get_doc("Delivery Note", delivery_note_name)
    flow = (dn.get("custom_flow_scope") or "").strip()
    responsibility = (dn.get("custom_shipping_responsibility") or "").strip()

    # Validate scenario
    allowed = (
        flow == "Domestic"
        or (flow == "Outbound" and responsibility == "Orderlift")
    )
    if not allowed:
        frappe.throw(
            "Delivery Trip can only be created for Domestic or Outbound/Orderlift Delivery Notes.",
            title="Invalid Scenario",
        )

    trip = frappe.new_doc("Delivery Trip")
    trip.company = dn.company
    trip.custom_flow_scope = flow
    trip.append("delivery_stops", {
        "delivery_note": dn.name,
        "customer": dn.customer,
        "address": dn.shipping_address_name or "",
        "customer_address": dn.shipping_address_name or "",
    })

    trip.flags.ignore_permissions = True
    trip.insert()

    frappe.msgprint(
        f"Delivery Trip <b>{trip.name}</b> created from {dn.name}.",
        indicator="green",
        alert=True,
    )
    return {"delivery_trip": trip.name}
