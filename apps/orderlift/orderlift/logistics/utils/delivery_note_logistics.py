import frappe

from orderlift.orderlift_logistics.services.load_planning import (
    build_analysis,
    compute_delivery_note_totals,
    create_shipment_analysis,
    round3,
    recommend_container,
)


def _set_delivery_note_fields(delivery_note_name, totals, recommendation, status):
    updates = {}
    if frappe.db.has_column("Delivery Note", "custom_total_weight_kg"):
        updates["custom_total_weight_kg"] = totals["total_weight_kg"]
    if frappe.db.has_column("Delivery Note", "custom_total_volume_m3"):
        updates["custom_total_volume_m3"] = totals["total_volume_m3"]
    if frappe.db.has_column("Delivery Note", "custom_logistics_status"):
        updates["custom_logistics_status"] = status
    if frappe.db.has_column("Delivery Note", "custom_limiting_factor"):
        updates["custom_limiting_factor"] = recommendation["limiting_factor"] if recommendation else ""
    if frappe.db.has_column("Delivery Note", "custom_recommended_container"):
        updates["custom_recommended_container"] = recommendation["container"].name if recommendation else ""

    if updates:
        frappe.db.set_value("Delivery Note", delivery_note_name, updates)


def analyze_delivery_note(doc, method=None):
    totals = compute_delivery_note_totals(doc.name)
    recommendation = recommend_container(totals["total_weight_kg"], totals["total_volume_m3"])

    analysis_payload = build_analysis(
        source_type="Delivery Note",
        source_name=doc.name,
        customer=doc.customer,
        destination_zone=totals.get("destination_zone") or "",
        totals=totals,
        recommendation=recommendation,
    )
    analysis_payload["delivery_note"] = doc.name
    analysis_doc = create_shipment_analysis(analysis_payload)

    _set_delivery_note_fields(doc.name, totals, recommendation, analysis_doc.status)
    return analysis_doc.name


def cancel_delivery_note_analysis(doc, method=None):
    latest_analysis = frappe.get_value(
        "Shipment Analysis",
        {"source_type": "Delivery Note", "source_name": doc.name},
        "name",
        order_by="creation desc",
    )
    if latest_analysis:
        frappe.db.set_value("Shipment Analysis", latest_analysis, "status", "cancelled")


@frappe.whitelist()
def recompute_delivery_note_analysis(delivery_note_name):
    doc = frappe.get_doc("Delivery Note", delivery_note_name)
    analysis_name = analyze_delivery_note(doc)
    return {
        "analysis": analysis_name,
        "delivery_note": delivery_note_name,
    }


@frappe.whitelist()
def forecast_sales_order_container(sales_order_name):
    so = frappe.get_doc("Sales Order", sales_order_name)
    total_weight_kg = 0.0
    total_volume_m3 = 0.0
    missing_items = []

    for row in so.items or []:
        values = frappe.db.get_value(
            "Item",
            row.item_code,
            ["custom_weight_kg", "custom_volume_m3", "custom_length_cm", "custom_width_cm", "custom_height_cm"],
            as_dict=True,
        )
        values = values or {}
        unit_weight = float(values.get("custom_weight_kg") or 0)
        unit_volume = float(values.get("custom_volume_m3") or 0)

        if unit_volume <= 0:
            length = float(values.get("custom_length_cm") or 0)
            width = float(values.get("custom_width_cm") or 0)
            height = float(values.get("custom_height_cm") or 0)
            if length > 0 and width > 0 and height > 0:
                unit_volume = (length * width * height) / 1000000

        if unit_weight <= 0 or unit_volume <= 0:
            missing_items.append(row.item_code)

        qty = float(row.qty or 0)
        total_weight_kg += unit_weight * qty
        total_volume_m3 += unit_volume * qty

    recommendation = recommend_container(total_weight_kg, total_volume_m3)

    return {
        "sales_order": so.name,
        "total_weight_kg": round3(total_weight_kg),
        "total_volume_m3": round3(total_volume_m3),
        "status": "incomplete_data" if missing_items else ("ok" if recommendation else "no_container_found"),
        "missing_items": sorted(set(missing_items)),
        "recommended_container": recommendation["container"].name if recommendation else "",
        "weight_utilization_pct": recommendation["weight_utilization_pct"] if recommendation else 0,
        "volume_utilization_pct": recommendation["volume_utilization_pct"] if recommendation else 0,
        "limiting_factor": recommendation["limiting_factor"] if recommendation else "",
    }
