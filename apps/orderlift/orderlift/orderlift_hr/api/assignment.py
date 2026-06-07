"""Resolves which Training Programs apply to which Employee."""

from __future__ import annotations

import frappe


def resolve_assigned_programs(employee: str) -> list[str]:
    """Return the list of active Training Program names that apply to the employee.

    Resolution: department match OR designation match OR manual override row.
    """
    if not employee or not frappe.db.exists("Employee", employee):
        return []

    department, designation = frappe.db.get_value(
        "Employee", employee, ["department", "designation"]
    ) or (None, None)

    matched: set[str] = set()

    or_filters = []
    if department:
        or_filters.append(["target_department", "=", department])
    if designation:
        or_filters.append(["target_designation", "=", designation])

    if or_filters:
        rows = frappe.get_list(
            "Training Program",
            filters=[["is_active", "=", 1]],
            or_filters=or_filters,
            fields=["name"],
            limit_page_length=0,
            ignore_permissions=True,
        )
        matched.update(r.name for r in rows)

    manual_rows = frappe.get_all(
        "Training Program Assignment",
        filters={"employee": employee, "parenttype": "Training Program"},
        fields=["parent"],
        limit_page_length=0,
    )
    for row in manual_rows:
        if frappe.db.get_value("Training Program", row.parent, "is_active"):
            matched.add(row.parent)

    return sorted(matched)


@frappe.whitelist()
def get_assigned_programs(employee: str | None = None) -> list[dict]:
    """Whitelisted helper returning program details for the current/given employee.

    Non-admins can only fetch their own.
    """
    target = _resolve_employee_or_self(employee)
    if not target:
        return []
    names = resolve_assigned_programs(target)
    if not names:
        return []
    return frappe.get_all(
        "Training Program",
        filters={"name": ["in", names]},
        fields=["name", "program_name", "description", "is_required"],
        order_by="program_name asc",
    )


def _resolve_employee_or_self(employee: str | None) -> str | None:
    """Returns the Employee to operate on. Admins may pass any; others get own."""
    if is_hr_admin():
        if employee:
            return employee
        return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    own = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if employee and employee != own:
        frappe.throw(frappe._("You can only view your own training data."), frappe.PermissionError)
    return own


def is_hr_admin(user: str | None = None) -> bool:
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return bool(roles & {"Orderlift Admin", "System Manager"})


def is_training_admin(user: str | None = None) -> bool:
    return is_hr_admin(user)
