"""Sales-side metrics: orders, quotations, conversion, speed, commission."""

from __future__ import annotations

import statistics

import frappe

from orderlift.orderlift_hr.metrics.base import (
    MetricResult,
    hours_between,
    register,
    resolve_sales_persons,
    resolve_user,
)


def _date_filter(field: str, from_date: str, to_date: str):
    return {field: ["between", [from_date, to_date]]}


@register("sales.so_count")
def sales_so_count(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Sales Order",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("sales.so_total_amount")
def sales_so_total_amount(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="\u20ac")
    rows = frappe.get_all(
        "Sales Order",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["grand_total"],
        limit_page_length=0,
    )
    total = sum(float(r.grand_total or 0) for r in rows)
    return MetricResult(value=total, unit="\u20ac")


@register("sales.so_avg_value")
def sales_so_avg_value(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="\u20ac")
    rows = frappe.get_all(
        "Sales Order",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["grand_total"],
        limit_page_length=0,
    )
    if not rows:
        return MetricResult(value=0.0, unit="\u20ac")
    amounts = [float(r.grand_total or 0) for r in rows]
    return MetricResult(value=sum(amounts) / len(amounts), unit="\u20ac")


@register("sales.quotation_count")
def sales_quotation_count(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Quotation",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("sales.quotation_total_amount")
def sales_quotation_total_amount(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="\u20ac")
    rows = frappe.get_all(
        "Quotation",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["grand_total"],
        limit_page_length=0,
    )
    total = sum(float(r.grand_total or 0) for r in rows)
    return MetricResult(value=total, unit="\u20ac")


@register("sales.conversion_rate")
def sales_conversion_rate(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="%")

    quotations = frappe.get_all(
        "Quotation",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["name", "status"],
        limit_page_length=0,
    )
    total_q = len(quotations)
    if not total_q:
        return MetricResult(value=0.0, unit="%")
    ordered = sum(1 for q in quotations if q.status in ("Ordered", "Partially Ordered"))
    pct = (ordered / total_q) * 100.0
    return MetricResult(value=pct, unit="%", details={"ordered": ordered, "total": total_q})


def _quotation_speeds(user, from_date, to_date) -> list[float]:
    rows = frappe.get_all(
        "Quotation",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["creation", "modified"],
        limit_page_length=0,
    )
    speeds = []
    for r in rows:
        h = hours_between(r.creation, r.modified)
        if h > 0:
            speeds.append(h)
    return speeds


@register("sales.quotation_speed_avg")
def sales_quotation_speed_avg(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="hours")
    speeds = _quotation_speeds(user, from_date, to_date)
    if not speeds:
        return MetricResult(value=0.0, unit="hours")
    return MetricResult(value=sum(speeds) / len(speeds), unit="hours")


@register("sales.quotation_speed_median")
def sales_quotation_speed_median(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="hours")
    speeds = _quotation_speeds(user, from_date, to_date)
    if not speeds:
        return MetricResult(value=0.0, unit="hours")
    return MetricResult(value=statistics.median(speeds), unit="hours")


@register("sales.time_to_close_days")
def sales_time_to_close_days(employee, from_date, to_date, params):
    """Avg days from a user-owned Quotation submit to its Sales Order submit."""
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="days")
    so_rows = frappe.get_all(
        "Sales Order",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["name", "creation"],
        limit_page_length=0,
    )
    if not so_rows:
        return MetricResult(value=0.0, unit="days")
    deltas = []
    for so in so_rows:
        quote_rows = frappe.get_all(
            "Sales Order Item",
            filters={"parent": so.name, "prevdoc_docname": ["!=", ""]},
            fields=["prevdoc_docname"],
            limit_page_length=1,
        )
        if not quote_rows or not quote_rows[0].prevdoc_docname:
            continue
        q_creation = frappe.db.get_value("Quotation", quote_rows[0].prevdoc_docname, "creation")
        if not q_creation:
            continue
        delta_hours = hours_between(q_creation, so.creation)
        if delta_hours > 0:
            deltas.append(delta_hours / 24.0)
    if not deltas:
        return MetricResult(value=0.0, unit="days")
    return MetricResult(value=sum(deltas) / len(deltas), unit="days")


@register("sales.commission_total")
def sales_commission_total(employee, from_date, to_date, params):
    sales_persons = resolve_sales_persons(employee)
    if not sales_persons:
        return MetricResult(value=0.0, unit="\u20ac")
    rows = frappe.get_all(
        "Sales Commission",
        filters={
            "salesperson": ["in", sales_persons],
            "status": ["!=", "Cancelled"],
            **_date_filter("posting_date", from_date, to_date),
        },
        fields=["commission_amount"],
        limit_page_length=0,
    )
    total = sum(float(r.commission_amount or 0) for r in rows)
    return MetricResult(value=total, unit="\u20ac")


@register("sales.discount_compliance_pct")
def sales_discount_compliance_pct(employee, from_date, to_date, params):
    """Percent of user-owned Quotations where additional_discount_percentage <= max_allowed.

    params.max_allowed: float, default 10.0
    """
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="%")
    max_allowed = float((params or {}).get("max_allowed", 10.0))
    rows = frappe.get_all(
        "Quotation",
        filters={
            "owner": user,
            "docstatus": 1,
            **_date_filter("transaction_date", from_date, to_date),
        },
        fields=["additional_discount_percentage"],
        limit_page_length=0,
    )
    if not rows:
        return MetricResult(value=100.0, unit="%")
    compliant = sum(1 for r in rows if (r.additional_discount_percentage or 0) <= max_allowed)
    return MetricResult(value=(compliant / len(rows)) * 100.0, unit="%")
