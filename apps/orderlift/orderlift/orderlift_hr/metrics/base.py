"""Shared types and helpers for the performance metric registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import frappe


@dataclass
class MetricResult:
    value: float = 0.0
    unit: str = ""
    display: str | None = None
    status: str = "Computed"  # Computed | No Data | Error
    error: str | None = None
    details: dict = field(default_factory=dict)


MetricFn = Callable[[str, str, str, dict], MetricResult]


REGISTRY: dict[str, MetricFn] = {}


def register(code: str):
    """Decorator: register a metric function under its code."""

    def _wrap(fn: MetricFn) -> MetricFn:
        REGISTRY[code] = fn
        return fn

    return _wrap


def resolve_user(employee: str) -> str | None:
    if not employee:
        return None
    return frappe.db.get_value("Employee", employee, "user_id")


def resolve_sales_persons(employee: str) -> list[str]:
    if not employee:
        return []
    return frappe.get_all(
        "Sales Person",
        filters={"employee": employee},
        pluck="name",
    )


def normalise_score(
    value: float,
    target: float | None,
    direction: str = "Higher is better",
    curve: str = "Linear",
) -> float:
    """Map a raw metric value to a 0-100 score using direction + curve."""

    if target in (None, 0):
        return 100.0 if value else 0.0

    if curve == "Threshold (pass/fail)":
        if direction == "Higher is better":
            ok = value >= target
        else:
            ok = value <= target
        return 100.0 if ok else 0.0

    if direction == "Higher is better":
        ratio = (value or 0) / target
    else:
        ratio = target / value if value else 0.0

    score = max(0.0, min(1.0, ratio)) * 100.0

    if curve == "Stepped":
        return float(int(score / 25) * 25)

    return score


def format_display(value: float, unit: str) -> str:
    """Render a numeric value with its unit for table display."""
    if unit == "%":
        return f"{value:.1f}%"
    if unit in ("count", "", None):
        return f"{int(round(value))}"
    if unit in ("days", "hours", "min"):
        return f"{value:.1f} {unit}"
    if unit == "\u20ac":
        return f"\u20ac {value:,.0f}"
    return f"{value:.2f} {unit}".strip()


def hours_between(earlier, later) -> float:
    """Inclusive hours between two datetime/strings; 0.0 if missing."""
    if not earlier or not later:
        return 0.0
    earlier = frappe.utils.get_datetime(earlier)
    later = frappe.utils.get_datetime(later)
    delta = later - earlier
    return delta.total_seconds() / 3600.0
