"""Training leaderboard scoring + ranking."""

from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import flt, now_datetime

from orderlift.orderlift_hr.api.assignment import (
    is_training_admin,
    resolve_assigned_programs,
)


WEIGHT_MODULE = 0.60
WEIGHT_QUIZ = 0.30
WEIGHT_RECENCY = 0.10


@frappe.whitelist()
def get_leaderboard(filters: dict | str | None = None) -> dict:
    """Return ranked employee rows.

    Admins get full columns + filters. Non-admins get a trimmed shape with their
    own row highlighted.
    """
    if isinstance(filters, str):
        import json as _json

        try:
            filters = _json.loads(filters or "{}")
        except _json.JSONDecodeError:
            filters = {}
    filters = filters or {}

    admin = is_training_admin()

    employees = _candidate_employees(filters if admin else {})
    rows = []
    for employee in employees:
        score_data = _compute_employee_score(employee.name)
        rows.append(
            {
                "employee": employee.name,
                "employee_name": employee.employee_name or employee.name,
                "department": employee.department,
                "designation": employee.designation,
                "total_score": round(score_data["total_score"], 1),
                "module_completion_pct": round(score_data["module_completion_pct"], 1),
                "quiz_average_pct": round(score_data["quiz_average_pct"], 1),
                "recent_activity_score": round(score_data["recent_activity_score"], 1),
                "modules_completed": score_data["modules_completed"],
                "modules_total": score_data["modules_total"],
                "last_activity": score_data["last_activity"],
            }
        )

    rows.sort(key=lambda r: (-r["total_score"], r["employee_name"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    own_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not admin:
        rows = [
            {
                "rank": row["rank"],
                "employee": row["employee"],
                "employee_name": row["employee_name"],
                "department": row["department"],
                "total_score": row["total_score"],
                "module_completion_pct": row["module_completion_pct"],
                "quiz_average_pct": row["quiz_average_pct"],
                "is_self": row["employee"] == own_employee,
            }
            for row in rows
        ]

    return {
        "viewer": {"is_admin": admin, "employee": own_employee},
        "rows": rows,
        "weights": {
            "module": WEIGHT_MODULE,
            "quiz": WEIGHT_QUIZ,
            "recency": WEIGHT_RECENCY,
        },
    }


@frappe.whitelist()
def recalculate_employee_score(employee: str) -> dict:
    """Admin-only: recompute score for one employee."""
    if not is_training_admin():
        frappe.throw(frappe._("Only admins may recalculate scores."), frappe.PermissionError)
    return _compute_employee_score(employee)


# -- Internals ----------------------------------------------------------------


def _candidate_employees(filters: dict) -> list:
    employee_filters = {"status": "Active"}
    if filters.get("department"):
        employee_filters["department"] = filters["department"]
    if filters.get("designation"):
        employee_filters["designation"] = filters["designation"]

    employees = frappe.get_all(
        "Employee",
        filters=employee_filters,
        fields=["name", "employee_name", "department", "designation"],
        limit_page_length=0,
    )

    if filters.get("program"):
        keep = []
        for employee in employees:
            if filters["program"] in resolve_assigned_programs(employee.name):
                keep.append(employee)
        employees = keep

    return employees


def _compute_employee_score(employee: str) -> dict:
    program_names = resolve_assigned_programs(employee)
    if program_names:
        modules = frappe.get_all(
            "Training Module",
            filters={
                "program": ["in", program_names],
                "is_active": 1,
                "is_required": 1,
            },
            fields=["name", "linked_quiz", "requires_quiz_pass"],
            limit_page_length=0,
        )
    else:
        modules = []

    module_names = [m.name for m in modules]

    progress_rows = frappe.get_all(
        "Employee Training Progress",
        filters={"employee": employee, "module": ["in", module_names]} if module_names else {"employee": employee, "module": ["in", ["__none__"]]},
        fields=["module", "studied", "last_activity"],
    )
    progress_by_module = {row.module: row for row in progress_rows}

    modules_completed = 0
    for module in modules:
        row = progress_by_module.get(module.name)
        if not row or not row.studied:
            continue
        if module.requires_quiz_pass and module.linked_quiz:
            if not frappe.db.exists(
                "Training Quiz Attempt",
                {"quiz": module.linked_quiz, "employee": employee, "passed": 1},
            ):
                continue
        modules_completed += 1

    modules_total = len(modules)
    module_completion_pct = (modules_completed / modules_total * 100.0) if modules_total else 0.0

    attempts = frappe.get_all(
        "Training Quiz Attempt",
        filters={"employee": employee, "completed_on": ["is", "set"]},
        fields=["quiz", "score_percentage", "completed_on"],
        order_by="completed_on desc",
    )
    latest_by_quiz: dict[str, float] = {}
    for row in attempts:
        latest_by_quiz.setdefault(row.quiz, flt(row.score_percentage))
    quiz_average_pct = (
        sum(latest_by_quiz.values()) / len(latest_by_quiz) if latest_by_quiz else 0.0
    )

    last_activity = frappe.db.sql(
        "select max(last_activity) from `tabEmployee Training Progress` where employee=%s",
        employee,
    )
    last_activity_dt = last_activity[0][0] if last_activity and last_activity[0] else None
    recent_activity_score = _recency_score(last_activity_dt)

    total = (
        WEIGHT_MODULE * module_completion_pct
        + WEIGHT_QUIZ * quiz_average_pct
        + WEIGHT_RECENCY * recent_activity_score
    )

    return {
        "total_score": total,
        "module_completion_pct": module_completion_pct,
        "quiz_average_pct": quiz_average_pct,
        "recent_activity_score": recent_activity_score,
        "modules_completed": modules_completed,
        "modules_total": modules_total,
        "last_activity": str(last_activity_dt) if last_activity_dt else None,
    }


def _recency_score(last_activity) -> float:
    if not last_activity:
        return 0.0
    delta = now_datetime() - frappe.utils.get_datetime(last_activity)
    days = delta.total_seconds() / 86400.0
    if days <= 7:
        return 100.0
    if days >= 30:
        return 0.0
    return 100.0 * (1.0 - (days - 7) / 23.0)
