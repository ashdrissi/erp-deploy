"""HR Dashboard — workforce, leave, attendance, payroll, and employee activity."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, nowdate


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_docs": _get_recent_docs(),
        "alerts": _get_alerts(),
        "workforce_mix": _get_workforce_mix(),
        "upcoming_milestones": _get_upcoming_milestones(),
        "leave_pipeline": _get_leave_pipeline(),
    }


def _get_kpis():
    first_day = get_first_day(nowdate())
    active_employees = frappe.db.count("Employee", {"status": "Active"}) if frappe.db.exists("DocType", "Employee") else 0
    departments = 0
    if frappe.db.exists("DocType", "Employee"):
        departments = len({row.department for row in frappe.get_all("Employee", fields=["department"], filters={"status": "Active"}, limit_page_length=500) if row.department})
    leave_open = frappe.db.count("Leave Application", {"status": ["not in", ["Rejected", "Cancelled"]]}) if frappe.db.exists("DocType", "Leave Application") else 0
    attendance_today = frappe.db.count("Attendance", {"attendance_date": nowdate()}) if frappe.db.exists("DocType", "Attendance") else 0
    salary_slips_month = frappe.db.count("Salary Slip", {"start_date": [">=", first_day]}) if frappe.db.exists("DocType", "Salary Slip") else 0
    expense_claims_open = frappe.db.count("Expense Claim", {"status": ["not in", ["Paid", "Rejected"]]}) if frappe.db.exists("DocType", "Expense Claim") else 0
    payroll_entries_month = frappe.db.count("Payroll Entry", {"start_date": [">=", first_day]}) if frappe.db.exists("DocType", "Payroll Entry") else 0

    return {
        "active_employees": int(active_employees or 0),
        "departments": int(departments or 0),
        "leave_open": int(leave_open or 0),
        "attendance_today": int(attendance_today or 0),
        "salary_slips_month": int(salary_slips_month or 0),
        "expense_claims_open": int(expense_claims_open or 0),
        "payroll_entries_month": int(payroll_entries_month or 0),
    }


def _get_recent_docs():
    rows = []

    def append_docs(doctype, fields, label_field, meta_label, route, limit=4):
        if not frappe.db.exists("DocType", doctype):
            return
        for row in frappe.get_all(
            doctype,
            fields=["name", *fields, "modified"],
            order_by="modified desc",
            limit_page_length=limit,
        ):
            rows.append(
                {
                    "label": row.get(label_field) or row.name,
                    "meta": _(meta_label),
                    "link": f"/app/{route}/{row.name}",
                    "modified": row.get("modified"),
                }
            )

    append_docs("Employee", ["employee_name", "department", "designation"], "employee_name", "Employee", "employee")
    append_docs("Leave Application", ["employee_name", "status"], "name", "Leave Application", "leave-application", limit=3)
    append_docs("Expense Claim", ["employee", "status"], "name", "Expense Claim", "expense-claim", limit=3)
    rows.sort(key=lambda row: row.get("modified") or "", reverse=True)
    return rows[:10]


def _get_alerts():
    alerts = []
    if frappe.db.exists("DocType", "Attendance") and frappe.db.count("Employee", {"status": "Active"}) > 0:
        attendance_today = frappe.db.count("Attendance", {"attendance_date": nowdate()})
        if attendance_today == 0:
            alerts.append({
                "level": "warn",
                "title": _("No attendance captured today"),
                "message": _("Attendance has not been recorded for the current date yet."),
                "link": "/app/attendance",
            })

    if frappe.db.exists("DocType", "Leave Application"):
        pending_leave = frappe.db.count("Leave Application", {"status": ["in", ["Open", "Approved"]]})
        if pending_leave:
            alerts.append({
                "level": "info",
                "title": _("{0} leave request(s) active").format(pending_leave),
                "message": _("Review approved and open leave applications to avoid coverage gaps."),
                "link": "/app/leave-application",
            })

    if frappe.db.exists("DocType", "Expense Claim"):
        open_claims = frappe.db.count("Expense Claim", {"status": ["not in", ["Paid", "Rejected"]]})
        if open_claims:
            alerts.append({
                "level": "warn",
                "title": _("{0} expense claim(s) still open").format(open_claims),
                "message": _("Finance and HR should clear pending employee reimbursements."),
                "link": "/app/expense-claim",
            })

    return alerts[:6]


def _get_workforce_mix():
    if not frappe.db.exists("DocType", "Employee"):
        return {"departments": [], "designations": [], "status": []}
    rows = frappe.get_all("Employee", fields=["department", "designation", "status"], limit_page_length=500)
    return {
        "departments": [{"label": label, "value": value} for label, value in Counter((r.get("department") or _("Unassigned")) for r in rows).most_common(6)],
        "designations": [{"label": label, "value": value} for label, value in Counter((r.get("designation") or _("Unassigned")) for r in rows).most_common(6)],
        "status": [{"label": label, "value": value} for label, value in Counter((r.get("status") or _("Unassigned")) for r in rows).most_common(6)],
    }


def _get_upcoming_milestones():
    if not frappe.db.exists("DocType", "Employee"):
        return []
    rows = frappe.get_all(
        "Employee",
        fields=["name", "employee_name", "date_of_joining", "department", "designation"],
        filters={"status": "Active", "date_of_joining": [">=", add_days(nowdate(), -30)]},
        order_by="date_of_joining desc",
        limit_page_length=6,
    )
    return [
        {
            "name": row.name,
            "employee_name": row.employee_name or row.name,
            "date": str(row.date_of_joining or ""),
            "meta": " · ".join(part for part in [row.department, row.designation] if part),
            "link": f"/app/employee/{row.name}",
        }
        for row in rows
    ]


def _get_leave_pipeline():
    if not frappe.db.exists("DocType", "Leave Application"):
        return []
    rows = frappe.get_all("Leave Application", fields=["status"], limit_page_length=500)
    counts = Counter((row.get("status") or _("Unassigned")) for row in rows)
    return [{"label": label, "value": value} for label, value in counts.most_common(6)]
