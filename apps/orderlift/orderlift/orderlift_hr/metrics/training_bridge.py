"""Thin wrappers that surface training-leaderboard signals as metrics."""

from __future__ import annotations

from orderlift.orderlift_hr.api.leaderboard import _compute_employee_score
from orderlift.orderlift_hr.metrics.base import MetricResult, register


@register("training.module_completion_pct")
def training_module_completion_pct(employee, from_date, to_date, params):
    if not employee:
        return MetricResult(status="No Data", unit="%")
    snap = _compute_employee_score(employee)
    return MetricResult(
        value=float(snap.get("module_completion_pct") or 0.0),
        unit="%",
        details={
            "modules_completed": snap.get("modules_completed"),
            "modules_total": snap.get("modules_total"),
        },
    )


@register("training.quiz_average_pct")
def training_quiz_average_pct(employee, from_date, to_date, params):
    if not employee:
        return MetricResult(status="No Data", unit="%")
    snap = _compute_employee_score(employee)
    return MetricResult(value=float(snap.get("quiz_average_pct") or 0.0), unit="%")


@register("training.recency_score")
def training_recency_score(employee, from_date, to_date, params):
    if not employee:
        return MetricResult(status="No Data", unit="%")
    snap = _compute_employee_score(employee)
    return MetricResult(
        value=float(snap.get("recent_activity_score") or 0.0),
        unit="%",
        details={"last_activity": snap.get("last_activity")},
    )
