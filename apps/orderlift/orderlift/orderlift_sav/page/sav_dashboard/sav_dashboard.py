"""SAV Dashboard — premium landing page for after-sales tickets and interventions."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, nowdate


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_tickets": _get_recent_tickets(),
        "alerts": _get_alerts(),
        "status_breakdown": _get_status_breakdown(),
        "technician_load": _get_technician_load(),
        "upcoming_interventions": _get_upcoming_interventions(),
        "recent_communications": _get_recent_communications(),
    }


def _get_kpis():
    total = frappe.db.count("SAV Ticket")
    open_count = frappe.db.count("SAV Ticket", {"status": "Open"})
    assigned = frappe.db.count("SAV Ticket", {"status": "Assigned"})
    in_progress = frappe.db.count("SAV Ticket", {"status": "In Progress"})
    resolved = frappe.db.count("SAV Ticket", {"status": "Resolved"})
    closed = frappe.db.count("SAV Ticket", {"status": "Closed"})
    sla_breach = frappe.db.count("SAV Ticket", {"sla_breach": 1})
    critical = frappe.db.count("SAV Ticket", {"priority": "Critical"})

    return {
        "total_tickets": int(total or 0),
        "open_tickets": int(open_count or 0),
        "assigned_tickets": int(assigned or 0),
        "in_progress_tickets": int(in_progress or 0),
        "resolved_tickets": int(resolved or 0),
        "closed_tickets": int(closed or 0),
        "sla_breach_tickets": int(sla_breach or 0),
        "critical_tickets": int(critical or 0),
    }


def _get_recent_tickets():
    return frappe.get_all(
        "SAV Ticket",
        fields=["name", "customer", "status", "priority", "assigned_technician", "modified"],
        order_by="modified desc",
        limit_page_length=10,
    )


def _get_alerts():
    alerts = []

    critical_open = frappe.db.count(
        "SAV Ticket",
        {"priority": "Critical", "status": ["not in", ["Closed", "Resolved"]]},
    )
    if critical_open:
        alerts.append(
            {
                "level": "error",
                "title": _("{0} critical ticket(s) need action").format(critical_open),
                "message": _("Critical SAV tickets are still open or in progress."),
                "link": "/app/sav-ticket",
            }
        )

    overdue_assigned = frappe.db.count(
        "SAV Ticket",
        {
            "status": ["in", ["Assigned", "In Progress"]],
            "intervention_date": ["<", nowdate()],
        },
    )
    if overdue_assigned:
        alerts.append(
            {
                "level": "warn",
                "title": _("{0} intervention(s) are overdue").format(overdue_assigned),
                "message": _("Assigned or active interventions have dates in the past and need review."),
                "link": "/app/sav-ticket",
            }
        )

    unassigned = frappe.db.count("SAV Ticket", {"status": "Open", "assigned_technician": ["in", ["", None]]})
    if unassigned:
        alerts.append(
            {
                "level": "info",
                "title": _("{0} open ticket(s) still unassigned").format(unassigned),
                "message": _("Open incidents still need a technician assignment."),
                "link": "/app/sav-ticket",
            }
        )

    sla_breach = frappe.db.count("SAV Ticket", {"sla_breach": 1})
    if sla_breach:
        alerts.append(
            {
                "level": "error",
                "title": _("{0} ticket(s) marked as SLA breach").format(sla_breach),
                "message": _("Review the breached incidents and their escalation path."),
                "link": "/app/sav-ticket",
            }
        )

    return alerts[:6]


def _get_status_breakdown():
    rows = frappe.get_all("SAV Ticket", fields=["status", "priority"], limit_page_length=500)
    return {
        "status": [{"label": label or _("Unspecified"), "value": value} for label, value in Counter((r.get("status") or "") for r in rows).most_common(6)],
        "priority": [{"label": label or _("Unspecified"), "value": value} for label, value in Counter((r.get("priority") or "") for r in rows).most_common(6)],
    }


def _get_technician_load():
    rows = frappe.get_all(
        "SAV Ticket",
        fields=["assigned_technician", "status"],
        filters={"status": ["not in", ["Closed"]]},
        limit_page_length=500,
    )
    counts = Counter((row.get("assigned_technician") or _("Unassigned")) for row in rows)
    return [{"label": label, "value": value} for label, value in counts.most_common(8)]


def _get_upcoming_interventions():
    rows = frappe.get_all(
        "SAV Ticket",
        fields=["name", "customer", "assigned_technician", "intervention_date", "status", "priority"],
        filters={
            "status": ["in", ["Assigned", "In Progress", "Open"]],
            "intervention_date": [">=", nowdate()],
        },
        order_by="intervention_date asc",
        limit_page_length=6,
    )
    return [
        {
            "name": row.get("name"),
            "customer": row.get("customer") or "",
            "assigned_technician": row.get("assigned_technician") or _("Unassigned"),
            "intervention_date": str(row.get("intervention_date") or ""),
            "status": row.get("status") or "",
            "priority": row.get("priority") or "",
            "link": f"/app/sav-ticket/{row.get('name')}",
        }
        for row in rows
    ]


def _get_recent_communications():
    if not frappe.db.exists("DocType", "Communication"):
        return []

    rows = frappe.get_all(
        "Communication",
        filters={"reference_doctype": "SAV Ticket"},
        fields=["name", "subject", "reference_name", "communication_medium", "sent_or_received", "sender_full_name", "modified"],
        order_by="modified desc",
        limit_page_length=6,
    )
    return [
        {
            "subject": row.get("subject") or row.name,
            "ticket": row.get("reference_name") or "",
            "meta": " · ".join(
                part for part in [row.get("communication_medium"), row.get("sent_or_received"), row.get("sender_full_name")] if part
            ),
            "link": f"/app/communication/{row.name}",
        }
        for row in rows
    ]
