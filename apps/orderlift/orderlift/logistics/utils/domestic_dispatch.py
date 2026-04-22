"""
Domestic Dispatch
-----------------
Create Delivery Trip from domestic/outbound Forecast Load Plans or
standalone Delivery Notes.

Supports:
  - Domestic + Orderlift → Delivery Trip from Forecast Load Plan or DN
  - Outbound + Orderlift → Delivery Trip for local leg only

Blocked:
  - Inbound → no Delivery Trip (handled by scenario_guard.py)
  - Outbound + Customer → no Delivery Trip (customer manages shipping)
"""

import frappe
from frappe.contacts.doctype.address.address import get_default_address
from frappe.utils import now_datetime


def _resolve_trip_vehicle(vehicle=None):
    vehicle = (vehicle or "").strip()
    if vehicle:
        return vehicle

    existing = frappe.get_all("Vehicle", pluck="name", limit=1)
    if existing:
        return existing[0]

    frappe.throw(
        "Vehicle is required to create Delivery Trip. Create a Vehicle first or pass one explicitly.",
        title="Missing Vehicle",
    )


def _resolve_departure_time(departure_time=None):
    return departure_time or now_datetime()


def _resolve_stop_address(customer=None, shipping_address_name=None):
    return shipping_address_name or (get_default_address("Customer", customer) if customer else None)


def _build_stop_payload(source_name, customer, shipping_address_name=None):
    address_name = _resolve_stop_address(customer=customer, shipping_address_name=shipping_address_name)
    payload = {
        "delivery_note": source_name,
        "customer": customer,
    }
    if address_name:
        payload["address"] = address_name
        payload["customer_address"] = address_name
    return payload


def _get_forecast_plan(plan_name):
    return frappe.get_doc("Forecast Load Plan", plan_name)


@frappe.whitelist()
def create_delivery_trip_from_forecast_plan(plan_name, vehicle=None, departure_time=None, driver=None):
    """Create a Delivery Trip from a Domestic or Outbound/Orderlift forecast plan.

    Collects all selected Delivery Notes from the plan and creates one trip
    with multiple stops.

    Args:
        plan_name: Name of the Forecast Load Plan.

    Returns:
        dict with the new Delivery Trip name.
    """
    plan = _get_forecast_plan(plan_name)

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

    if plan.status not in ("Ready", "Loading", "In Transit", "Delivered"):
        frappe.throw(
            "Delivery Trip can only be created after the forecast plan is confirmed.",
            title="Invalid Status",
        )

    # Check for existing trip linked to this forecast plan.
    existing = []
    if frappe.db.has_column("Delivery Trip", "custom_forecast_plan"):
        existing = frappe.get_all(
            "Delivery Trip",
            filters={"custom_forecast_plan": plan.name, "docstatus": ["!=", 2]},
            limit=1,
        )
    if existing:
        frappe.throw(
            f"A Delivery Trip already exists for this plan: {existing[0].name}",
            title="Trip Already Exists",
        )

    trip = frappe.new_doc("Delivery Trip")
    trip.company = plan.company
    trip.vehicle = _resolve_trip_vehicle(vehicle)
    trip.departure_time = _resolve_departure_time(departure_time)
    trip.custom_flow_scope = plan.flow_scope
    if frappe.db.has_column("Delivery Trip", "custom_forecast_plan"):
        trip.custom_forecast_plan = plan.name
    if driver and hasattr(trip, "driver"):
        trip.driver = driver

    stops_added = 0
    for row in plan.items or []:
        if not row.selected or row.source_doctype != "Delivery Note" or not row.source_name:
            continue
        dn = frappe.get_doc("Delivery Note", row.source_name)
        trip.append(
            "delivery_stops",
            _build_stop_payload(
                source_name=row.source_name,
                customer=row.party or dn.customer,
                shipping_address_name=dn.shipping_address_name,
            ),
        )
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
def create_delivery_trip_from_load_plan(load_plan_name, vehicle=None, departure_time=None, driver=None):
    """Backward-compatible wrapper for the legacy method name."""
    return create_delivery_trip_from_forecast_plan(
        plan_name=load_plan_name,
        vehicle=vehicle,
        departure_time=departure_time,
        driver=driver,
    )


@frappe.whitelist()
def create_delivery_trip_from_delivery_note(delivery_note_name, vehicle=None, departure_time=None, driver=None):
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
    trip.vehicle = _resolve_trip_vehicle(vehicle)
    trip.departure_time = _resolve_departure_time(departure_time)
    trip.custom_flow_scope = flow
    if driver and hasattr(trip, "driver"):
        trip.driver = driver
    trip.append(
        "delivery_stops",
        _build_stop_payload(
            source_name=dn.name,
            customer=dn.customer,
            shipping_address_name=dn.shipping_address_name,
        ),
    )

    trip.flags.ignore_permissions = True
    trip.insert()

    frappe.msgprint(
        f"Delivery Trip <b>{trip.name}</b> created from {dn.name}.",
        indicator="green",
        alert=True,
    )
    return {"delivery_trip": trip.name}
