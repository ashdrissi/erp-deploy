"""Attendance metrics built on ERPNext Attendance + Employee Checkin."""

from __future__ import annotations

import frappe

from orderlift.orderlift_hr.metrics.base import MetricResult, register


def _date_filter(field: str, from_date: str, to_date: str):
    return {field: ["between", [from_date, to_date]]}


def _attendance_rows(employee, from_date, to_date, fields):
    return frappe.get_all(
        "Attendance",
        filters={
            "employee": employee,
            "docstatus": 1,
            **_date_filter("attendance_date", from_date, to_date),
        },
        fields=fields,
        limit_page_length=0,
    )


@register("attendance.present_rate")
def attendance_present_rate(employee, from_date, to_date, params):
    if not employee:
        return MetricResult(status="No Data", unit="%")
    rows = _attendance_rows(employee, from_date, to_date, ["status"])
    if not rows:
        return MetricResult(value=0.0, unit="%")
    weight = 0.0
    for r in rows:
        if r.status == "Present":
            weight += 1.0
        elif r.status == "Half Day":
            weight += 0.5
        elif r.status == "Work From Home":
            weight += 1.0
    pct = (weight / len(rows)) * 100.0
    return MetricResult(value=pct, unit="%", details={"counted": weight, "total": len(rows)})


@register("attendance.absent_count")
def attendance_absent_count(employee, from_date, to_date, params):
    if not employee:
        return MetricResult(status="No Data", unit="count")
    rows = _attendance_rows(employee, from_date, to_date, ["status"])
    absent = sum(1 for r in rows if r.status == "Absent")
    return MetricResult(value=float(absent), unit="count")


@register("attendance.late_days_count")
def attendance_late_days_count(employee, from_date, to_date, params):
    """Count of attendance days where the employee was marked late.

    params.late_minutes_threshold: int (unused; we rely on Attendance.late_entry flag).
    """
    if not employee:
        return MetricResult(status="No Data", unit="count")
    rows = _attendance_rows(employee, from_date, to_date, ["late_entry"])
    late = sum(1 for r in rows if r.late_entry)
    return MetricResult(value=float(late), unit="count")


@register("attendance.avg_working_hours")
def attendance_avg_working_hours(employee, from_date, to_date, params):
    if not employee:
        return MetricResult(status="No Data", unit="hours")
    rows = _attendance_rows(employee, from_date, to_date, ["working_hours"])
    hours = [float(r.working_hours or 0) for r in rows if r.working_hours]
    if not hours:
        return MetricResult(value=0.0, unit="hours")
    return MetricResult(value=sum(hours) / len(hours), unit="hours")
