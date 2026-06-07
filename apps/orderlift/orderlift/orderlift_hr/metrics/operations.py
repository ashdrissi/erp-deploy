"""Operations-side metrics: installation QC and project ownership."""

from __future__ import annotations

import frappe

from orderlift.orderlift_hr.metrics.base import (
    MetricResult,
    hours_between,
    register,
    resolve_user,
)


def _date_filter(field: str, from_date: str, to_date: str):
    return {field: ["between", [from_date, to_date]]}


@register("ops.qc_items_verified")
def ops_qc_items_verified(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Installation QC Item",
        filters={
            "verified_by": user,
            "is_verified": 1,
            **_date_filter("verified_on", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")


@register("ops.qc_avg_verification_hours")
def ops_qc_avg_verification_hours(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="hours")
    rows = frappe.get_all(
        "Installation QC Item",
        filters={
            "verified_by": user,
            "is_verified": 1,
            **_date_filter("verified_on", from_date, to_date),
        },
        fields=["creation", "verified_on"],
        limit_page_length=0,
    )
    deltas = []
    for r in rows:
        h = hours_between(r.creation, r.verified_on)
        if h > 0:
            deltas.append(h)
    if not deltas:
        return MetricResult(value=0.0, unit="hours")
    return MetricResult(value=sum(deltas) / len(deltas), unit="hours")


@register("ops.projects_owned")
def ops_projects_owned(employee, from_date, to_date, params):
    user = resolve_user(employee)
    if not user:
        return MetricResult(status="No Data", unit="count")
    rows = frappe.get_all(
        "Project",
        filters={
            "owner": user,
            **_date_filter("creation", from_date, to_date),
        },
        fields=["name"],
        limit_page_length=0,
    )
    return MetricResult(value=float(len(rows)), unit="count")
