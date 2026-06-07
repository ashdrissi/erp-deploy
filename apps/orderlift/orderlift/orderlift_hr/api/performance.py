"""Whitelisted endpoints driving the performance measurement layer."""

from __future__ import annotations

import json

import frappe
from frappe.utils import now_datetime

from orderlift.orderlift_hr.api.assignment import is_hr_admin
from orderlift.orderlift_hr.metrics import REGISTRY, MetricResult, normalise_score
from orderlift.orderlift_hr.metrics.base import format_display


def _ensure_admin():
    if not is_hr_admin():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)


def _parse_json(raw):
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _cycle_window(appraisal_cycle: str) -> tuple[str | None, str | None]:
    if not appraisal_cycle:
        return None, None
    row = frappe.db.get_value(
        "Appraisal Cycle",
        appraisal_cycle,
        ["start_date", "end_date"],
        as_dict=True,
    )
    if not row:
        return None, None
    return row.start_date, row.end_date


def _resolve_profile(profile: str | None, employee: str | None) -> dict | None:
    if profile:
        if not frappe.db.exists("Performance Profile", profile):
            return None
        return frappe.get_doc("Performance Profile", profile).as_dict()

    if not employee:
        return None

    emp = frappe.db.get_value(
        "Employee", employee, ["department", "designation"], as_dict=True
    )
    if not emp:
        return None

    candidates = frappe.get_all(
        "Performance Profile",
        filters={
            "is_active": 1,
            "auto_assign": 1,
        },
        fields=["name", "target_department", "target_designation"],
    )
    for cand in candidates:
        dept_ok = not cand.target_department or cand.target_department == emp.department
        desig_ok = not cand.target_designation or cand.target_designation == emp.designation
        if dept_ok and desig_ok:
            return frappe.get_doc("Performance Profile", cand.name).as_dict()
    return None


def _profile_metrics(profile_doc: dict) -> list[dict]:
    return [dict(row) for row in (profile_doc.get("metrics") or [])]


def _params_for_metric(metric_doc) -> dict:
    if not metric_doc:
        return {}
    raw_filters = None
    if metric_doc.get("filters_json"):
        raw_filters = metric_doc.get("filters_json")
    return {
        "source_doctype": metric_doc.get("source_doctype"),
        "aggregate": metric_doc.get("aggregate") or "count",
        "value_field": metric_doc.get("value_field"),
        "employee_link_field": metric_doc.get("employee_link_field") or "owner",
        "filters_json": raw_filters,
        "unit": metric_doc.get("unit"),
    }


def _run_metric(metric_doc, employee: str, from_date: str | None, to_date: str | None) -> MetricResult:
    code = metric_doc.get("metric_code") or metric_doc.get("name")
    source_type = metric_doc.get("source_type") or "Builtin"

    if source_type == "Manual":
        return MetricResult(status="No Data", unit=metric_doc.get("unit") or "")

    if source_type == "Doc Query":
        fn = REGISTRY.get("generic.doc_query")
        params = _params_for_metric(metric_doc)
        try:
            return fn(employee, from_date, to_date, params)
        except Exception as exc:
            frappe.log_error(frappe.get_traceback(), f"Metric compute failed: {code}")
            return MetricResult(status="Error", error=str(exc), unit=metric_doc.get("unit") or "")

    fn = REGISTRY.get(code)
    if not fn:
        return MetricResult(status="Error", error=f"No builtin for {code}", unit=metric_doc.get("unit") or "")

    try:
        return fn(employee, from_date, to_date, _params_for_metric(metric_doc))
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), f"Metric compute failed: {code}")
        return MetricResult(status="Error", error=str(exc), unit=metric_doc.get("unit") or "")


def _upsert_snapshot(
    employee: str,
    metric_code: str,
    appraisal_cycle: str,
    from_date,
    to_date,
    result: MetricResult,
    target_value: float | None,
    score: float,
) -> str:
    existing = frappe.db.get_value(
        "Performance Metric Snapshot",
        {
            "employee": employee,
            "metric": metric_code,
            "appraisal_cycle": appraisal_cycle,
        },
        "name",
    )

    user_id = frappe.db.get_value("Employee", employee, "user_id")
    if user_id and not frappe.db.exists("User", user_id):
        user_id = None
    payload = {
        "employee": employee,
        "user": user_id,
        "metric": metric_code,
        "appraisal_cycle": appraisal_cycle,
        "from_date": from_date,
        "to_date": to_date,
        "value": float(result.value or 0.0),
        "value_display": result.display or format_display(result.value or 0.0, result.unit or ""),
        "target_value": float(target_value or 0.0),
        "score_0_100": float(score or 0.0),
        "last_computed_on": now_datetime(),
        "compute_status": result.status,
        "error_message": result.error or "",
    }

    if existing:
        doc = frappe.get_doc("Performance Metric Snapshot", existing)
        doc.update(payload)
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        return doc.name

    payload["doctype"] = "Performance Metric Snapshot"
    doc = frappe.get_doc(payload)
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def list_metrics():
    return frappe.get_all(
        "Performance Metric",
        filters={"is_active": 1},
        fields=[
            "name",
            "metric_code",
            "metric_name",
            "category",
            "unit",
            "direction",
            "default_target",
            "source_type",
            "score_curve",
            "linked_kra",
        ],
        order_by="category asc, metric_name asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def recompute_employee_snapshots(employee, appraisal_cycle, profile=None):
    if not employee or not appraisal_cycle:
        frappe.throw(frappe._("employee and appraisal_cycle are required"))

    if not is_hr_admin():
        own_employee = frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        )
        if own_employee != employee:
            frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    profile_doc = _resolve_profile(profile, employee)
    if not profile_doc:
        return {"status": "no_profile", "snapshots": []}

    from_date, to_date = _cycle_window(appraisal_cycle)
    rows = _profile_metrics(profile_doc)
    written = []
    for row in rows:
        metric_code = row.get("metric")
        if not metric_code:
            continue
        metric_doc = frappe.db.get_value(
            "Performance Metric",
            metric_code,
            [
                "metric_code",
                "source_type",
                "source_doctype",
                "aggregate",
                "value_field",
                "employee_link_field",
                "filters_json",
                "unit",
                "direction",
                "default_target",
                "score_curve",
            ],
            as_dict=True,
        )
        if not metric_doc or not metric_doc.get("metric_code"):
            continue

        result = _run_metric(metric_doc, employee, from_date, to_date)
        target = row.get("target_value") or metric_doc.get("default_target") or 0.0
        score = normalise_score(
            result.value or 0.0,
            target,
            direction=metric_doc.get("direction") or "Higher is better",
            curve=metric_doc.get("score_curve") or "Linear",
        )
        if result.status != "Computed":
            score = 0.0

        name = _upsert_snapshot(
            employee=employee,
            metric_code=metric_doc.get("metric_code"),
            appraisal_cycle=appraisal_cycle,
            from_date=from_date,
            to_date=to_date,
            result=result,
            target_value=target,
            score=score,
        )
        written.append({"snapshot": name, "metric": metric_doc.get("metric_code"), "score": score})

    return {"status": "ok", "profile": profile_doc.get("name"), "snapshots": written}


@frappe.whitelist()
def recompute_cycle(appraisal_cycle, profile=None):
    _ensure_admin()
    if not appraisal_cycle:
        frappe.throw(frappe._("appraisal_cycle is required"))

    appraisees = frappe.get_all(
        "Appraisee",
        filters={"parent": appraisal_cycle, "parenttype": "Appraisal Cycle"},
        fields=["employee"],
    )
    summary = []
    for app in appraisees:
        if not app.employee:
            continue
        result = recompute_employee_snapshots(app.employee, appraisal_cycle, profile)
        summary.append({"employee": app.employee, **result})
    return {"status": "ok", "count": len(summary), "items": summary}


@frappe.whitelist()
def sync_snapshots_to_goals(appraisal_cycle, profile=None):
    _ensure_admin()
    if not appraisal_cycle:
        frappe.throw(frappe._("appraisal_cycle is required"))

    snapshots = frappe.get_all(
        "Performance Metric Snapshot",
        filters={"appraisal_cycle": appraisal_cycle},
        fields=["name", "employee", "metric", "score_0_100", "target_value", "value_display"],
        limit_page_length=0,
    )
    written = 0
    skipped = 0
    for snap in snapshots:
        kra = frappe.db.get_value("Performance Metric", snap.metric, "linked_kra")
        if not kra:
            skipped += 1
            continue

        existing = frappe.db.get_value(
            "Goal",
            {
                "employee": snap.employee,
                "kra": kra,
                "appraisal_cycle": appraisal_cycle,
            },
            "name",
        )
        if existing:
            goal = frappe.get_doc("Goal", existing)
        else:
            goal = frappe.new_doc("Goal")
            goal.employee = snap.employee
            goal.kra = kra
            goal.appraisal_cycle = appraisal_cycle
            goal.goal_name = f"{snap.metric} ({appraisal_cycle})"

        goal.progress = float(snap.score_0_100 or 0.0)
        goal.status = "Completed" if (snap.score_0_100 or 0.0) >= 100 else "In Progress"
        goal.flags.ignore_permissions = True
        goal.save(ignore_permissions=True)
        written += 1

    return {"status": "ok", "written": written, "skipped": skipped}


@frappe.whitelist()
def get_employee_performance(employee, appraisal_cycle):
    if not employee or not appraisal_cycle:
        frappe.throw(frappe._("employee and appraisal_cycle are required"))

    if not is_hr_admin():
        own = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if own != employee:
            frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    snapshots = frappe.get_all(
        "Performance Metric Snapshot",
        filters={"employee": employee, "appraisal_cycle": appraisal_cycle},
        fields=[
            "metric",
            "value",
            "value_display",
            "target_value",
            "score_0_100",
            "compute_status",
            "last_computed_on",
        ],
        limit_page_length=0,
    )
    catalogue = {
        r.name: r
        for r in frappe.get_all(
            "Performance Metric",
            fields=["name", "metric_name", "category", "unit", "direction"],
            limit_page_length=0,
        )
    }
    rows = []
    for snap in snapshots:
        meta = catalogue.get(snap.metric) or {}
        rows.append(
            {
                "metric": snap.metric,
                "metric_name": meta.get("metric_name") or snap.metric,
                "category": meta.get("category") or "Other",
                "unit": meta.get("unit") or "",
                "value": snap.value,
                "value_display": snap.value_display,
                "target_value": snap.target_value,
                "score": snap.score_0_100,
                "status": snap.compute_status,
                "last_computed_on": str(snap.last_computed_on) if snap.last_computed_on else None,
            }
        )
    return {"employee": employee, "appraisal_cycle": appraisal_cycle, "rows": rows}


@frappe.whitelist()
def get_performance_leaderboard(appraisal_cycle, profile=None, filters=None):
    if not appraisal_cycle:
        frappe.throw(frappe._("appraisal_cycle is required"))

    admin = is_hr_admin()
    filters_obj = _parse_json(filters) or {}

    appraisees = frappe.get_all(
        "Appraisee",
        filters={"parent": appraisal_cycle, "parenttype": "Appraisal Cycle"},
        fields=["employee"],
    )
    employee_names = [a.employee for a in appraisees if a.employee]
    if not employee_names:
        return {"admin": admin, "rows": [], "categories": []}

    employee_filters = {"name": ["in", employee_names]}
    if filters_obj.get("department"):
        employee_filters["department"] = filters_obj["department"]
    if filters_obj.get("designation"):
        employee_filters["designation"] = filters_obj["designation"]

    employees = frappe.get_all(
        "Employee",
        filters=employee_filters,
        fields=["name", "employee_name", "department", "designation", "user_id", "image"],
        limit_page_length=0,
    )

    snapshots = frappe.get_all(
        "Performance Metric Snapshot",
        filters={"appraisal_cycle": appraisal_cycle, "employee": ["in", [e.name for e in employees]]},
        fields=[
            "employee",
            "metric",
            "score_0_100",
            "value",
            "value_display",
            "target_value",
            "last_computed_on",
        ],
        limit_page_length=0,
    )

    metric_meta = {
        r.name: r
        for r in frappe.get_all(
            "Performance Metric",
            fields=["name", "category", "metric_name", "unit", "direction"],
            limit_page_length=0,
        )
    }

    by_employee: dict[str, dict] = {}
    categories: set[str] = set()
    metric_catalogue: dict[str, dict] = {}
    for snap in snapshots:
        meta = metric_meta.get(snap.metric)
        category = (meta and meta.category) or "Other"
        categories.add(category)
        if snap.metric not in metric_catalogue:
            metric_catalogue[snap.metric] = {
                "metric": snap.metric,
                "metric_name": (meta and meta.metric_name) or snap.metric,
                "category": category,
                "unit": (meta and meta.unit) or "",
                "direction": (meta and meta.direction) or "Higher is better",
            }
        bucket = by_employee.setdefault(
            snap.employee,
            {"total": 0.0, "count": 0, "categories": {}, "metrics": {}, "last_activity": None},
        )
        cat = bucket["categories"].setdefault(category, {"total": 0.0, "count": 0})
        cat["total"] += float(snap.score_0_100 or 0.0)
        cat["count"] += 1
        bucket["total"] += float(snap.score_0_100 or 0.0)
        bucket["count"] += 1
        bucket["metrics"][snap.metric] = {
            "score": float(snap.score_0_100 or 0.0),
            "value": snap.value,
            "value_display": snap.value_display,
            "target_value": snap.target_value,
        }
        if snap.last_computed_on and (
            bucket["last_activity"] is None or snap.last_computed_on > bucket["last_activity"]
        ):
            bucket["last_activity"] = snap.last_computed_on

    rows = []
    own_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    for emp in employees:
        bucket = by_employee.get(emp.name) or {
            "total": 0.0,
            "count": 0,
            "categories": {},
            "metrics": {},
            "last_activity": None,
        }
        avg = (bucket["total"] / bucket["count"]) if bucket["count"] else 0.0
        cats = {
            cat: round((v["total"] / v["count"]) if v["count"] else 0.0, 1)
            for cat, v in bucket["categories"].items()
        }
        row = {
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "department": emp.department,
            "designation": emp.designation,
            "image": emp.image,
            "score": round(avg, 1),
            "categories": cats,
            "metric_count": bucket["count"],
            "last_activity": str(bucket["last_activity"]) if bucket["last_activity"] else None,
            "is_self": emp.name == own_employee,
        }
        if admin:
            row["metric_scores"] = {
                k: {
                    "score": round(v["score"], 1),
                    "value_display": v["value_display"],
                    "target_value": v["target_value"],
                }
                for k, v in bucket["metrics"].items()
            }
        if not admin:
            row.pop("designation", None)
            row.pop("last_activity", None)
        rows.append(row)

    rows.sort(key=lambda r: r["score"], reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx

    return {
        "admin": admin,
        "rows": rows,
        "categories": sorted(categories),
        "metrics": sorted(metric_catalogue.values(), key=lambda m: (m["category"], m["metric_name"])) if admin else [],
        "appraisal_cycle": appraisal_cycle,
    }


def recompute_open_cycles():
    """Daily scheduler entry: recompute every In Progress Appraisal Cycle."""
    cycles = frappe.get_all(
        "Appraisal Cycle",
        filters={"status": "In Progress"},
        fields=["name"],
        limit_page_length=0,
    )
    for cycle in cycles:
        try:
            recompute_cycle(cycle.name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"recompute_open_cycles failed for {cycle.name}",
            )
