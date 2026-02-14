"""
Container Optimizer
-------------------
Calculates total shipment weight and volume from a list of items
and recommends the optimal transport type (van, truck, 20ft/40ft container).

Used by the Shipment Plan doctype.
"""

import frappe


# Transport thresholds — adjust with client after testing
THRESHOLDS = {
    "small_van":       {"max_weight_kg": 500,    "max_volume_m3": 2},
    "standard_truck":  {"max_weight_kg": 3_500,  "max_volume_m3": 20},
    "ftl_truck":       {"max_weight_kg": 22_000, "max_volume_m3": 90},
    "container_20ft":  {"max_weight_kg": 22_000, "max_volume_m3": 33},
    "container_40ft":  {"max_weight_kg": 26_500, "max_volume_m3": 67},
}


def calculate_shipment(items):
    """
    Calculate totals and recommend transport for a list of item lines.

    Args:
        items (list[dict]): Each dict has keys:
            item_code (str), qty (float),
            unit_weight_kg (float), unit_volume_m3 (float)

    Returns:
        dict: {total_weight_kg, total_volume_m3, recommendation}
    """
    total_weight = 0.0
    total_volume = 0.0

    for line in items:
        qty = float(line.get("qty", 0))
        total_weight += float(line.get("unit_weight_kg", 0)) * qty
        total_volume += float(line.get("unit_volume_m3", 0)) * qty

    recommendation = _recommend_transport(total_weight, total_volume)

    return {
        "total_weight_kg": round(total_weight, 3),
        "total_volume_m3": round(total_volume, 3),
        "recommendation": recommendation,
    }


def _recommend_transport(weight_kg, volume_m3):
    """Return transport type string based on weight and volume.

    Decision tree:
      1. Small Van: weight <= 500kg AND volume <= 2m3
      2. Standard Truck: weight <= 3,500kg AND volume <= 20m3
      3. Full Truck Load: weight <= 22,000kg AND volume <= 90m3
      4. 20ft Container: weight <= 22,000kg AND volume <= 33m3
      5. 40ft Container: weight <= 26,500kg AND volume <= 67m3
      6. Multiple containers for anything larger
    """
    t = THRESHOLDS

    if weight_kg <= t["small_van"]["max_weight_kg"] and \
       volume_m3 <= t["small_van"]["max_volume_m3"]:
        return "Small Van / Petit Camion"

    if weight_kg <= t["standard_truck"]["max_weight_kg"] and \
       volume_m3 <= t["standard_truck"]["max_volume_m3"]:
        return "Standard Truck / Camion Standard"

    if weight_kg <= t["container_20ft"]["max_weight_kg"] and \
       volume_m3 <= t["container_20ft"]["max_volume_m3"]:
        return "20ft Container / Conteneur 20 pieds"

    if weight_kg <= t["container_40ft"]["max_weight_kg"] and \
       volume_m3 <= t["container_40ft"]["max_volume_m3"]:
        return "40ft Container / Conteneur 40 pieds"

    if weight_kg <= t["ftl_truck"]["max_weight_kg"] and \
       volume_m3 <= t["ftl_truck"]["max_volume_m3"]:
        return "Full Truck Load / Camion Complet"

    return "Multiple Containers Required / Plusieurs Conteneurs Nécessaires"


@frappe.whitelist()
def calculate_from_shipment_plan(shipment_plan_name):
    """Whitelisted method: recalculate totals for a Shipment Plan doc."""
    doc = frappe.get_doc("Shipment Plan", shipment_plan_name)
    items = [
        {
            "item_code": row.item_code,
            "qty": row.qty,
            "unit_weight_kg": row.unit_weight_kg,
            "unit_volume_m3": row.unit_volume_m3,
        }
        for row in doc.items_summary
    ]
    result = calculate_shipment(items)
    frappe.db.set_value("Shipment Plan", shipment_plan_name, {
        "total_weight_kg": result["total_weight_kg"],
        "total_volume_m3": result["total_volume_m3"],
        "recommended_transport": result["recommendation"],
    })
    return result
