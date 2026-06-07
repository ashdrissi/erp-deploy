"""Bridges between ERPNext Appraisal/Goal and Orderlift Performance Metrics.

Two doc_event hooks live here:

- `on_goal_validate(doc, method)` keeps `Goal.progress` in sync with the latest
  Performance Metric Snapshot whenever the goal participates in an appraisal
  cycle. Manual edits are honoured via a `_skip_snapshot_sync` flag.

- `on_appraisal_before_save(doc, method)` ensures the appraisal_kra child rows
  on an Appraisal mirror the weights configured on the matching Performance
  Profile. Existing rows are not overwritten if an admin already tuned them.
"""

from __future__ import annotations

import frappe


def _snapshot_for(employee: str, metric: str, appraisal_cycle: str):
    if not (employee and metric and appraisal_cycle):
        return None
    return frappe.db.get_value(
        "Performance Metric Snapshot",
        {"employee": employee, "metric": metric, "appraisal_cycle": appraisal_cycle},
        ["score_0_100", "value_display"],
        as_dict=True,
    )


def on_goal_validate(doc, method=None):
    if getattr(doc, "_skip_snapshot_sync", False):
        return

    cycle = getattr(doc, "appraisal_cycle", None)
    kra = getattr(doc, "kra", None)
    employee = getattr(doc, "employee", None)
    if not (cycle and kra and employee):
        return

    metric = frappe.db.get_value("Performance Metric", {"linked_kra": kra}, "name")
    if not metric:
        return

    snap = _snapshot_for(employee, metric, cycle)
    if not snap:
        return

    doc.progress = float(snap.score_0_100 or 0.0)


def _profile_for_employee(employee: str) -> str | None:
    emp = frappe.db.get_value(
        "Employee", employee, ["department", "designation"], as_dict=True
    )
    if not emp:
        return None
    candidates = frappe.get_all(
        "Performance Profile",
        filters={"is_active": 1, "auto_assign": 1},
        fields=["name", "target_department", "target_designation"],
    )
    for cand in candidates:
        dept_ok = not cand.target_department or cand.target_department == emp.department
        desig_ok = not cand.target_designation or cand.target_designation == emp.designation
        if dept_ok and desig_ok:
            return cand.name
    return None


def on_appraisal_before_save(doc, method=None):
    employee = getattr(doc, "employee", None)
    if not employee:
        return

    profile_name = _profile_for_employee(employee)
    if not profile_name:
        return

    profile = frappe.get_doc("Performance Profile", profile_name)
    if not profile.metrics:
        return

    metric_to_kra = {}
    for row in profile.metrics:
        kra = frappe.db.get_value("Performance Metric", row.metric, "linked_kra")
        if not kra:
            continue
        metric_to_kra[row.metric] = {"kra": kra, "weight": float(row.weight or 0.0)}

    if not metric_to_kra:
        return

    existing_by_kra = {
        getattr(row, "kra", None): row for row in (doc.appraisal_kra or [])
    }

    for info in metric_to_kra.values():
        if info["kra"] in existing_by_kra:
            continue
        doc.append(
            "appraisal_kra",
            {
                "kra": info["kra"],
                "per_weightage": info["weight"] * 100.0,
            },
        )
