"""CRM-side metrics: opportunities and partner campaign outreach."""

from __future__ import annotations

import frappe

from orderlift.orderlift_hr.metrics.base import (
    MetricResult,
    register,
    resolve_user,
)


def _date_filter(field: str, from_date: str, to_date: str):
    return {field: ["between", [from_date, to_date]]}


WON_STATUSES = ("Converted", "Closed")


@register("crm.opportunities_owned")
def crm_opportunities_owned(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Opportunity",
        filters={
            "opportunity_owner": user,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("crm.opportunities_won")
def crm_opportunities_won(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Opportunity",
        filters={
            "opportunity_owner": user,
            "status": ["in", WON_STATUSES],
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("crm.opportunity_win_rate")
def crm_opportunity_win_rate(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="%")
    rows = frappe.get_all(
        "Opportunity",
        filters={
            "opportunity_owner": user,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["status"],
        limit_page_length=0,
    )
    if not rows:
        return MetricResult(value=0.0, unit="%")
    won = sum(1 for r in rows if r.status in WON_STATUSES)
    return MetricResult(
        value=(won / len(rows)) * 100.0,
        unit="%",
        details={"won": won, "total": len(rows)},
    )


@register("crm.pipeline_value")
def crm_pipeline_value(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="\u20ac")
    rows = frappe.get_all(
        "Opportunity",
        filters={
            "opportunity_owner": user,
            "status": ["not in", ("Lost", "Closed", "Converted")],
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["opportunity_amount"],
        limit_page_length=0,
    )
    total = sum(float(r.opportunity_amount or 0) for r in rows)
    return MetricResult(value=total, unit="\u20ac")


@register("crm.campaign_targets_assigned")
def crm_campaign_targets_assigned(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Partner Campaign Target",
        filters={
            "assigned_to": user,
            **_date_filter("creation", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("crm.campaign_targets_contacted")
def crm_campaign_targets_contacted(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Partner Campaign Target",
        filters={
            "assigned_to": user,
            "last_contact_date": ["between", [from_date, to_date]],
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("crm.campaign_targets_visited")
def crm_campaign_targets_visited(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Partner Campaign Target",
        filters={
            "assigned_to": user,
            "visit_date": ["between", [from_date, to_date]],
            "visit_status": "Done",
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("crm.contact_rate")
def crm_contact_rate(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="%")
    assigned = frappe.get_all(
        "Partner Campaign Target",
        filters={
            "assigned_to": user,
            **_date_filter("creation", from_date, to_date),
        },
        fields=["last_contact_date"],
        limit_page_length=0,
    )
    if not assigned:
        return MetricResult(value=0.0, unit="%")
    contacted = sum(1 for r in assigned if r.last_contact_date)
    return MetricResult(
        value=(contacted / len(assigned)) * 100.0,
        unit="%",
        details={"contacted": contacted, "assigned": len(assigned)},
    )
