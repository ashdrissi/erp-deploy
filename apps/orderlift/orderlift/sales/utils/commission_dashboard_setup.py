from __future__ import annotations

import json

import frappe


def after_migrate():
    ensure_commission_dashboard_assets()
    ensure_commission_workspace()


def ensure_commission_dashboard_assets():
    cards = [
        {
            "name": "Pending Amount",
            "label": "Pending Amount",
            "function": "Sum",
            "aggregate_function_based_on": "commission_amount",
            "filters_json": json.dumps([["Sales Commission", "status", "=", "Pending"], ["Sales Commission", "docstatus", "=", 1]]),
        },
        {
            "name": "Approved Amount",
            "label": "Approved Amount",
            "function": "Sum",
            "aggregate_function_based_on": "commission_amount",
            "filters_json": json.dumps([["Sales Commission", "status", "=", "Approved"], ["Sales Commission", "docstatus", "=", 1]]),
        },
        {
            "name": "Paid Amount",
            "label": "Paid Amount",
            "function": "Sum",
            "aggregate_function_based_on": "commission_amount",
            "filters_json": json.dumps([["Sales Commission", "status", "=", "Paid"], ["Sales Commission", "docstatus", "=", 1]]),
        },
        {
            "name": "Commission Records",
            "label": "Commission Records",
            "function": "Count",
            "aggregate_function_based_on": "",
            "filters_json": json.dumps([["Sales Commission", "docstatus", "=", 1]]),
        },
    ]

    for card in cards:
        doc = frappe.get_doc("Number Card", card["name"]) if frappe.db.exists("Number Card", card["name"]) else frappe.new_doc("Number Card")
        doc.label = card["label"]
        doc.module = "Orderlift Sales"
        doc.type = "Document Type"
        doc.document_type = "Sales Commission"
        doc.function = card["function"]
        doc.aggregate_function_based_on = card["aggregate_function_based_on"]
        doc.is_public = 1
        doc.filters_json = card["filters_json"]
        doc.stats_time_interval = "Monthly"
        doc.show_percentage_stats = 1
        doc.save(ignore_permissions=True)

    charts = [
        {
            "name": "Commissions by Status",
            "chart_name": "Commissions by Status",
            "chart_type": "Group By",
            "document_type": "Sales Commission",
            "type": "Donut",
            "group_by_type": "Sum",
            "group_by_based_on": "status",
            "aggregate_function_based_on": "commission_amount",
            "number_of_groups": 0,
            "timeseries": 0,
            "timespan": "Last Year",
            "time_interval": "Monthly",
            "filters_json": json.dumps([["Sales Commission", "docstatus", "=", 1]]),
        },
        {
            "name": "Monthly Commission Amount",
            "chart_name": "Monthly Commission Amount",
            "chart_type": "Sum",
            "document_type": "Sales Commission",
            "type": "Bar",
            "based_on": "posting_date",
            "aggregate_function_based_on": "commission_amount",
            "timeseries": 1,
            "timespan": "Last Quarter",
            "time_interval": "Monthly",
            "filters_json": json.dumps([["Sales Commission", "docstatus", "=", 1]]),
        },
    ]

    for chart in charts:
        doc = frappe.get_doc("Dashboard Chart", chart["name"]) if frappe.db.exists("Dashboard Chart", chart["name"]) else frappe.new_doc("Dashboard Chart")
        doc.chart_name = chart["chart_name"]
        doc.module = "Orderlift Sales"
        doc.chart_type = chart["chart_type"]
        doc.document_type = chart["document_type"]
        doc.type = chart["type"]
        doc.is_public = 1
        doc.filters_json = chart["filters_json"]
        doc.timeseries = chart["timeseries"]
        doc.timespan = chart["timespan"]
        doc.time_interval = chart["time_interval"]
        doc.based_on = chart.get("based_on", "")
        doc.group_by_type = chart.get("group_by_type", "Count")
        doc.group_by_based_on = chart.get("group_by_based_on", "")
        doc.aggregate_function_based_on = chart.get("aggregate_function_based_on", "")
        doc.number_of_groups = chart.get("number_of_groups", 0)
        doc.save(ignore_permissions=True)


def ensure_commission_workspace():
    workspace_name = "Commissions"
    shortcuts = [
        {"label": "Sales Commission", "type": "DocType", "link_to": "Sales Commission"},
        {"label": "Sales Order", "type": "DocType", "link_to": "Sales Order"},
        {"label": "Sales Invoice", "type": "DocType", "link_to": "Sales Invoice"},
    ]

    content = [
        {
            "id": "commissions_header",
            "type": "header",
            "data": {"text": "<span class=\"h4\"><b>Commissions</b></span>", "col": 12},
        },
        {"id": "commissions_chart_status", "type": "chart", "data": {"chart_name": "Commissions by Status", "col": 6}},
        {"id": "commissions_chart_monthly", "type": "chart", "data": {"chart_name": "Monthly Commission Amount", "col": 6}},
        {"id": "commissions_card_pending", "type": "number_card", "data": {"number_card_name": "Pending Amount", "col": 3}},
        {"id": "commissions_card_approved", "type": "number_card", "data": {"number_card_name": "Approved Amount", "col": 3}},
        {"id": "commissions_card_paid", "type": "number_card", "data": {"number_card_name": "Paid Amount", "col": 3}},
        {"id": "commissions_card_count", "type": "number_card", "data": {"number_card_name": "Commission Records", "col": 3}},
        {"id": "commissions_spacer", "type": "spacer", "data": {"col": 12}},
        {
            "id": "commissions_shortcuts_header",
            "type": "header",
            "data": {"text": "<span class=\"h4\"><b>Workflow</b></span>", "col": 12},
        },
    ]

    for idx, shortcut in enumerate(shortcuts, start=1):
        content.append(
            {
                "id": f"commissions_shortcut_{idx}",
                "type": "shortcut",
                "data": {"shortcut_name": shortcut["label"], "col": 4},
            }
        )

    workspace = frappe.get_doc("Workspace", workspace_name) if frappe.db.exists("Workspace", workspace_name) else frappe.new_doc("Workspace")
    workspace.title = workspace_name
    workspace.label = workspace_name
    workspace.module = "Orderlift Sales"
    workspace.public = 1
    workspace.is_hidden = 0
    workspace.content = json.dumps(content)
    workspace.set("shortcuts", [])
    for shortcut in shortcuts:
        workspace.append("shortcuts", shortcut)
    workspace.save(ignore_permissions=True)
