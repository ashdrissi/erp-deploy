import frappe
from frappe.utils import flt

from orderlift.orderlift_logistics.services.capacity_math import (
    candidate_pressure,
    compute_utilization,
    detect_limiting_factor,
    round3,
)


STATUS_OK = "ok"
STATUS_INCOMPLETE = "incomplete_data"
STATUS_NO_CONTAINER = "no_container_found"
STATUS_OVER_CAPACITY = "over_capacity"

def _get_item_metrics(item_code):
    values = frappe.db.get_value(
        "Item",
        item_code,
        [
            "custom_weight_kg",
            "custom_volume_m3",
            "custom_length_cm",
            "custom_width_cm",
            "custom_height_cm",
        ],
        as_dict=True,
    )
    if not values:
        return 0.0, 0.0

    unit_weight_kg = flt(values.custom_weight_kg)
    unit_volume_m3 = flt(values.custom_volume_m3)

    if unit_volume_m3 <= 0:
        length_cm = flt(values.custom_length_cm)
        width_cm = flt(values.custom_width_cm)
        height_cm = flt(values.custom_height_cm)
        if length_cm > 0 and width_cm > 0 and height_cm > 0:
            unit_volume_m3 = (length_cm * width_cm * height_cm) / 1000000

    return unit_weight_kg, unit_volume_m3


def compute_delivery_note_totals(delivery_note_name):
    doc = frappe.get_doc("Delivery Note", delivery_note_name)
    total_weight_kg = 0.0
    total_volume_m3 = 0.0
    items_summary = []
    missing_data_items = []

    for row in doc.items or []:
        qty = flt(row.qty)
        unit_weight_kg, unit_volume_m3 = _get_item_metrics(row.item_code)

        if unit_weight_kg <= 0 or unit_volume_m3 <= 0:
            missing_data_items.append(row.item_code)

        line_weight_kg = qty * unit_weight_kg
        line_volume_m3 = qty * unit_volume_m3

        total_weight_kg += line_weight_kg
        total_volume_m3 += line_volume_m3

        items_summary.append(
            {
                "item_code": row.item_code,
                "qty": qty,
                "unit_weight_kg": round3(unit_weight_kg),
                "unit_volume_m3": round3(unit_volume_m3),
                "line_weight_kg": round3(line_weight_kg),
                "line_volume_m3": round3(line_volume_m3),
            }
        )

    return {
        "delivery_note": doc.name,
        "customer": doc.customer,
        "destination_zone": (doc.get("custom_destination_zone") or "").strip(),
        "total_weight_kg": round3(total_weight_kg),
        "total_volume_m3": round3(total_volume_m3),
        "items": items_summary,
        "missing_data_items": sorted(set(missing_data_items)),
    }


def get_active_containers():
    return frappe.get_all(
        "Container Profile",
        filters={"is_active": 1},
        fields=["name", "container_name", "container_type", "max_weight_kg", "max_volume_m3", "cost_rank"],
        order_by="cost_rank asc, max_volume_m3 asc, max_weight_kg asc",
        limit_page_length=0,
    )


def recommend_container(total_weight_kg, total_volume_m3):
    for container in get_active_containers():
        if flt(total_weight_kg) <= flt(container.max_weight_kg) and flt(total_volume_m3) <= flt(container.max_volume_m3):
            utilization = compute_utilization(
                total_weight_kg,
                total_volume_m3,
                container.max_weight_kg,
                container.max_volume_m3,
            )
            return {
                "container": container,
                "weight_utilization_pct": utilization["weight_utilization_pct"],
                "volume_utilization_pct": utilization["volume_utilization_pct"],
                "limiting_factor": detect_limiting_factor(
                    utilization["weight_utilization_pct"], utilization["volume_utilization_pct"]
                ),
            }
    return None


def build_analysis(source_type, source_name, customer, destination_zone, totals, recommendation):
    missing_data_items = totals.get("missing_data_items") or []
    if missing_data_items:
        status = STATUS_INCOMPLETE
    elif not recommendation:
        status = STATUS_NO_CONTAINER
    else:
        status = STATUS_OK

    analysis = {
        "doctype": "Shipment Analysis",
        "source_type": source_type,
        "source_name": source_name,
        "customer": customer,
        "destination_zone": destination_zone,
        "total_weight_kg": round3(totals.get("total_weight_kg")),
        "total_volume_m3": round3(totals.get("total_volume_m3")),
        "status": status,
        "missing_data_json": frappe.as_json(missing_data_items),
        "missing_data_count": len(missing_data_items),
        "engine_version": "container-v1",
    }

    if recommendation and status == STATUS_OK:
        container = recommendation["container"]
        analysis.update(
            {
                "recommended_container": container.name,
                "weight_utilization_pct": recommendation["weight_utilization_pct"],
                "volume_utilization_pct": recommendation["volume_utilization_pct"],
                "limiting_factor": recommendation["limiting_factor"],
            }
        )

    return analysis


def create_shipment_analysis(analysis_payload):
    return frappe.get_doc(analysis_payload).insert(ignore_permissions=True)


def _delivery_note_assigned_elsewhere(load_plan_name, delivery_note):
    rows = frappe.get_all(
        "Load Plan Shipment",
        filters={"delivery_note": delivery_note, "parent": ["!=", load_plan_name]},
        fields=["parent"],
        limit_page_length=1,
    )
    if not rows:
        return False

    parent = frappe.get_value("Container Load Plan", rows[0].parent, ["docstatus", "status"], as_dict=True)
    if not parent:
        return False
    if parent.docstatus == 2:
        return False
    if (parent.status or "").strip().lower() == "cancelled":
        return False
    return True


def pending_delivery_notes(destination_zone=None, company=None):
    filters = {"docstatus": 1}
    if destination_zone:
        filters["custom_destination_zone"] = destination_zone
    if company:
        filters["company"] = company

    return frappe.get_all(
        "Delivery Note",
        filters=filters,
        fields=["name", "customer", "company", "posting_date", "custom_destination_zone"],
        order_by="posting_date asc, creation asc",
        limit_page_length=0,
    )


def _score_candidate(candidate, remaining_weight, remaining_volume):
    return candidate_pressure(
        candidate["total_weight_kg"],
        candidate["total_volume_m3"],
        remaining_weight,
        remaining_volume,
    )


def suggest_shipments_for_load_plan(load_plan):
    if not load_plan.container_profile:
        frappe.throw("Container Profile is required before suggesting shipments.")

    profile = frappe.get_doc("Container Profile", load_plan.container_profile)

    already_added = {row.delivery_note for row in (load_plan.shipments or []) if row.delivery_note}

    used_weight = flt(load_plan.total_weight_kg)
    used_volume = flt(load_plan.total_volume_m3)
    remaining_weight = max(0, flt(profile.max_weight_kg) - used_weight)
    remaining_volume = max(0, flt(profile.max_volume_m3) - used_volume)

    candidates = []
    rejected = []
    for dn in pending_delivery_notes(destination_zone=load_plan.destination_zone, company=load_plan.company):
        if dn.name in already_added:
            continue
        if _delivery_note_assigned_elsewhere(load_plan.name, dn.name):
            continue

        totals = compute_delivery_note_totals(dn.name)
        if totals["missing_data_items"]:
            rejected.append({"delivery_note": dn.name, "reason": "incomplete_data"})
            continue

        candidates.append(
            {
                "delivery_note": dn.name,
                "customer": dn.customer,
                "total_weight_kg": totals["total_weight_kg"],
                "total_volume_m3": totals["total_volume_m3"],
                "score": _score_candidate(totals, remaining_weight, remaining_volume),
            }
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)

    selected = []
    for candidate in candidates:
        fits_weight = flt(candidate["total_weight_kg"]) <= flt(remaining_weight)
        fits_volume = flt(candidate["total_volume_m3"]) <= flt(remaining_volume)
        if fits_weight and fits_volume:
            selected.append(candidate)
            remaining_weight -= flt(candidate["total_weight_kg"])
            remaining_volume -= flt(candidate["total_volume_m3"])
        else:
            if not fits_weight and not fits_volume:
                reason = "both"
            elif not fits_weight:
                reason = "weight"
            else:
                reason = "volume"
            rejected.append({"delivery_note": candidate["delivery_note"], "reason": reason})

    return {
        "selected": selected,
        "rejected": rejected,
        "remaining_weight_kg": round3(remaining_weight),
        "remaining_volume_m3": round3(remaining_volume),
    }
