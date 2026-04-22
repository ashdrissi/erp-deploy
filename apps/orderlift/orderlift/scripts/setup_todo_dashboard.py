from __future__ import annotations

import json

import frappe
from frappe.utils import nowdate


MODULE = "Orderlift"


NUMBER_CARDS = [
    {
        "name": "Open ToDos",
        "label": "Open ToDos",
        "type": "Document Type",
        "document_type": "ToDo",
        "function": "Count",
        "filters_json": [["ToDo", "status", "=", "Open"]],
        "color": "#2563eb",
        "background_color": "#dbeafe",
    },
    {
        "name": "Closed ToDos",
        "label": "Closed ToDos",
        "type": "Document Type",
        "document_type": "ToDo",
        "function": "Count",
        "filters_json": [["ToDo", "status", "=", "Closed"]],
        "color": "#16a34a",
        "background_color": "#dcfce7",
    },
    {
        "name": "My Open ToDos",
        "label": "My Open ToDos",
        "type": "Custom",
        "document_type": "ToDo",
        "method": "orderlift.scripts.setup_todo_dashboard.get_my_open_todos",
        "color": "#7c3aed",
        "background_color": "#ede9fe",
    },
    {
        "name": "Overdue ToDos",
        "label": "Overdue ToDos",
        "type": "Custom",
        "document_type": "ToDo",
        "method": "orderlift.scripts.setup_todo_dashboard.get_overdue_todos",
        "color": "#dc2626",
        "background_color": "#fee2e2",
    },
]


DASHBOARD_CHARTS = [
    {
        "name": "ToDos by Status",
        "chart_type": "Group By",
        "type": "Donut",
        "document_type": "ToDo",
        "group_by_type": "Count",
        "group_by_based_on": "status",
        "number_of_groups": 0,
        "timeseries": 0,
        "filters_json": [],
    },
    {
        "name": "ToDos by Priority",
        "chart_type": "Group By",
        "type": "Bar",
        "document_type": "ToDo",
        "group_by_type": "Count",
        "group_by_based_on": "priority",
        "number_of_groups": 0,
        "timeseries": 0,
        "filters_json": [],
    },
    {
        "name": "ToDo Creation Trend",
        "chart_type": "Count",
        "type": "Line",
        "document_type": "ToDo",
        "based_on": "creation",
        "timeseries": 1,
        "timespan": "Last Month",
        "time_interval": "Weekly",
        "filters_json": [],
        "color": "#0f766e",
    },
]


def _upsert_number_card(config: dict[str, object]) -> str:
    doc = (
        frappe.get_doc("Number Card", config["name"])
        if frappe.db.exists("Number Card", config["name"])
        else frappe.new_doc("Number Card")
    )

    doc.label = config["label"]
    doc.type = config["type"]
    doc.document_type = config.get("document_type")
    doc.function = config.get("function") or "Count"
    doc.aggregate_function_based_on = config.get("aggregate_function_based_on") or ""
    doc.method = config.get("method") or ""
    doc.is_public = 1
    doc.is_standard = 0
    doc.module = None
    doc.filters_json = json.dumps(config.get("filters_json", []))
    doc.show_percentage_stats = 0
    doc.color = config.get("color")
    doc.background_color = config.get("background_color")

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return doc.name


def _upsert_dashboard_chart(config: dict[str, object]) -> str:
    doc = (
        frappe.get_doc("Dashboard Chart", config["name"])
        if frappe.db.exists("Dashboard Chart", config["name"])
        else frappe.new_doc("Dashboard Chart")
    )

    doc.chart_name = config["name"]
    doc.module = MODULE
    doc.chart_type = config["chart_type"]
    doc.document_type = config["document_type"]
    doc.type = config["type"]
    doc.is_public = 1
    doc.filters_json = json.dumps(config.get("filters_json", []))
    doc.timeseries = config.get("timeseries", 0)
    doc.timespan = config.get("timespan") or "Last Month"
    doc.time_interval = config.get("time_interval") or "Weekly"
    doc.based_on = config.get("based_on") or ""
    doc.group_by_type = config.get("group_by_type") or "Count"
    doc.group_by_based_on = config.get("group_by_based_on") or ""
    doc.aggregate_function_based_on = config.get("aggregate_function_based_on") or ""
    doc.number_of_groups = config.get("number_of_groups", 0)
    doc.color = config.get("color") or ""

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return doc.name


@frappe.whitelist()
def get_my_open_todos():
    if frappe.session.user == "Guest":
        return {"value": 0}

    count = frappe.db.count(
        "ToDo",
        {
            "status": "Open",
            "allocated_to": frappe.session.user,
        },
    )

    return {
        "value": count,
        "route": ["List", "ToDo", "List"],
        "route_options": {
            "status": [["=", "Open"]],
            "allocated_to": [["=", frappe.session.user]],
        },
    }


@frappe.whitelist()
def get_overdue_todos():
    count = frappe.db.count(
        "ToDo",
        {
            "status": "Open",
            "date": ["<", nowdate()],
        },
    )

    return {
        "value": count,
        "route": ["List", "ToDo", "List"],
        "route_options": {
            "status": [["=", "Open"]],
            "date": [["<", nowdate()]],
        },
    }


def run():
    cards = [_upsert_number_card(config) for config in NUMBER_CARDS]
    charts = [_upsert_dashboard_chart(config) for config in DASHBOARD_CHARTS]

    frappe.db.commit()
    return {"cards": cards, "charts": charts}
