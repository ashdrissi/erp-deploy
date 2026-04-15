import frappe


@frappe.whitelist()
def get_dashboard_data():
    """Return container planning data for the dashboard."""
    kpis = {
        "planning_count": frappe.db.count("Forecast Load Plan", {"status": "Planning"}),
        "ready_count": frappe.db.count("Forecast Load Plan", {"status": "Ready"}),
        "loading_count": frappe.db.count("Forecast Load Plan", {"status": "Loading"}),
        "in_transit_count": frappe.db.count("Forecast Load Plan", {"status": "In Transit"}),
        "delivered_count": frappe.db.count("Forecast Load Plan", {"status": "Delivered"}),
        "profiles_count": frappe.db.count("Container Profile", {"is_active": 1}),
    }

    # Recent containers ordered by departure date
    containers = frappe.get_all(
        "Forecast Load Plan",
        filters={"status": ["not in", ["Cancelled"]]},
        fields=[
            "name", "plan_label", "status",
            "route_origin", "route_destination",
            "departure_date", "deadline",
            "total_volume_m3", "total_weight_kg",
            "container_profile",
        ],
        order_by="departure_date desc",
        limit_page_length=20,
    )

    # Build alerts
    alerts = []
    # Containers approaching departure without being confirmed
    upcoming = frappe.db.sql("""
        SELECT name, plan_label, departure_date
        FROM `tabForecast Load Plan`
        WHERE status = 'Planning'
            AND departure_date IS NOT NULL
            AND departure_date <= CURDATE() + INTERVAL 3 DAY
        ORDER BY departure_date ASC
        LIMIT 5
    """, as_dict=True)
    for c in upcoming:
        alerts.append({
            "title": f"Container {c.plan_label or c.name} departs soon",
            "message": f"Departure date: {c.departure_date}. Review and confirm before departure.",
            "link": f"/app/forecast-plans/{c.name}",
            "level": "warn",
        })

    # Containers in transit
    in_transit = frappe.db.sql("""
        SELECT name, plan_label, departure_date, deadline
        FROM `tabForecast Load Plan`
        WHERE status = 'In Transit'
            AND deadline IS NOT NULL
        ORDER BY deadline ASC
        LIMIT 3
    """, as_dict=True)
    for c in in_transit:
        alerts.append({
            "title": f"Container {c.plan_label or c.name} in transit",
            "message": f"Departed: {c.departure_date}. Deadline: {c.deadline}.",
            "link": f"/app/forecast-plans/{c.name}",
            "level": "info",
        })

    return {
        "kpis": kpis,
        "containers": containers,
        "alerts": alerts,
    }
