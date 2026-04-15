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
        "defect_type_breakdown": _get_defect_type_breakdown(),
        "recurring_issues": _get_recurring_issues(),
        "warranty_exposure": _get_warranty_exposure(),
        "pending_stock_actions": _get_pending_stock_actions(),
        "top_problematic_items": _get_top_problematic_items(),
        "linked_executions": _get_linked_executions(),
        "mttr": _get_mttr(),
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

    # Warranty KPI — count open tickets where warranty_status contains "warranty" or "garantie"
    in_warranty = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Ticket`
        WHERE status NOT IN ('Closed')
        AND warranty_status LIKE '%warranty%'
    """)[0][0]

    # High severity open
    high_severity = frappe.db.count(
        "SAV Ticket",
        {"severity": ["in", ["High", "Critical"]], "status": ["not in", ["Closed", "Resolved"]]},
    )

    return {
        "total_tickets": int(total or 0),
        "open_tickets": int(open_count or 0),
        "assigned_tickets": int(assigned or 0),
        "in_progress_tickets": int(in_progress or 0),
        "resolved_tickets": int(resolved or 0),
        "closed_tickets": int(closed or 0),
        "sla_breach_tickets": int(sla_breach or 0),
        "critical_tickets": int(critical or 0),
        "in_warranty_open": int(in_warranty or 0),
        "high_severity_open": int(high_severity or 0),
    }


def _get_recent_tickets():
    return frappe.get_all(
        "SAV Ticket",
        fields=["name", "customer", "status", "priority", "assigned_technician",
                "defect_type", "serial_no", "severity", "sla_breach", "modified"],
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

    # High severity open tickets
    high_severity = frappe.db.count(
        "SAV Ticket",
        {"severity": "Critical", "status": ["not in", ["Closed", "Resolved"]]},
    )
    if high_severity:
        alerts.append(
            {
                "level": "error",
                "title": _("{0} ticket(s) with critical severity").format(high_severity),
                "message": _("These tickets have the highest severity level and need immediate attention."),
                "link": "/app/sav-ticket",
            }
        )

    # Pending stock actions
    pending_stock = frappe.db.sql("""
        SELECT COUNT(DISTINCT ssa.parent)
        FROM `tabSAV Stock Action` ssa
        JOIN `tabSAV Ticket` st ON st.name = ssa.parent
        WHERE ssa.status = 'Pending'
        AND st.status NOT IN ('Closed')
    """)[0][0]
    if pending_stock:
        alerts.append(
            {
                "level": "warn",
                "title": _("{0} pending stock action(s)").format(pending_stock),
                "message": _("Replacements, returns, or stock movements still need to be processed."),
                "link": "/app/sav-ticket",
            }
        )

    return alerts[:6]


def _get_status_breakdown():
    rows = frappe.get_all("SAV Ticket", fields=["status", "priority", "defect_type"], limit_page_length=500)
    return {
        "status": [{"label": label or _("Unspecified"), "value": value} for label, value in Counter((r.get("status") or "") for r in rows).most_common(6)],
        "priority": [{"label": label or _("Unspecified"), "value": value} for label, value in Counter((r.get("priority") or "") for r in rows).most_common(6)],
        "defect_type": [{"label": label or _("Unspecified"), "value": value} for label, value in Counter((r.get("defect_type") or "") for r in rows).most_common(4)],
    }


def _get_technician_load():
    rows = frappe.get_all(
        "SAV Ticket",
        fields=["assigned_technician", "status", "priority"],
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


def _get_defect_type_breakdown():
    """Breakdown of tickets by defect type: Installation, Product, Supplier."""
    rows = frappe.get_all(
        "SAV Ticket",
        fields=["defect_type", "status"],
        limit_page_length=500,
    )
    by_type = Counter(r.get("defect_type") or "" for r in rows)

    open_by_type = Counter(
        r.get("defect_type") or ""
        for r in rows
        if r.get("status") not in ("Closed", "Resolved")
    )

    result = []
    for dtype, total in by_type.most_common():
        label = dtype or _("Unspecified")
        result.append({
            "defect_type": label,
            "total": total,
            "open": open_by_type.get(dtype or "", 0),
        })
    return result


def _get_recurring_issues():
    """List of items/serials with multiple open tickets."""
    # Items appearing in multiple open tickets
    item_counts = frappe.db.sql("""
        SELECT item_concerned, COUNT(*) as cnt
        FROM `tabSAV Ticket`
        WHERE status IN ('Open', 'Assigned', 'In Progress')
        AND item_concerned IS NOT NULL AND item_concerned != ''
        GROUP BY item_concerned
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT 8
    """, as_dict=True)

    serial_counts = frappe.db.sql("""
        SELECT serial_no, COUNT(*) as cnt
        FROM `tabSAV Ticket`
        WHERE status IN ('Open', 'Assigned', 'In Progress')
        AND serial_no IS NOT NULL AND serial_no != ''
        GROUP BY serial_no
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT 8
    """, as_dict=True)

    return {
        "items": [{"label": r.item_concerned, "count": r.cnt} for r in item_counts],
        "serials": [{"label": r.serial_no, "count": r.cnt} for r in serial_counts],
        "total_recurring": frappe.db.count(
            "SAV Ticket",
            {"recurrence_count": [">", 0], "status": ["not in", ["Closed"]]},
        ),
    }


def _get_warranty_exposure():
    """Warranty-related metrics: in-warranty vs expired for open tickets."""
    in_warranty = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Ticket`
        WHERE status NOT IN ('Closed')
        AND warranty_status LIKE '%warranty%'
        AND warranty_status IS NOT NULL AND warranty_status != ''
    """)[0][0]

    expired = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Ticket`
        WHERE status NOT IN ('Closed')
        AND (warranty_status LIKE '%expired%' OR warranty_status LIKE '%expir%C3%A9e%')
    """)[0][0]

    no_warranty = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Ticket`
        WHERE status NOT IN ('Closed')
        AND (warranty_status IS NULL OR warranty_status = '')
    """)[0][0]

    return {
        "in_warranty": int(in_warranty or 0),
        "expired": int(expired or 0),
        "no_warranty_data": int(no_warranty or 0),
    }


def _get_pending_stock_actions():
    """Stock/replacement/return actions that need processing."""
    rows = frappe.db.sql("""
        SELECT ssa.action_type, ssa.reference_name, ssa.status,
               ssa.parent as ticket, st.customer, ssa.notes
        FROM `tabSAV Stock Action` ssa
        JOIN `tabSAV Ticket` st ON st.name = ssa.parent
        WHERE ssa.status = 'Pending'
        AND st.status NOT IN ('Closed')
        ORDER BY ssa.creation DESC
        LIMIT 10
    """, as_dict=True)

    return [
        {
            "action_type": r.action_type,
            "reference": r.reference_name,
            "ticket": r.ticket,
            "customer": r.customer,
            "notes": r.notes or "",
            "link": f"/app/sav-ticket/{r.ticket}",
        }
        for r in rows
    ]


def _get_top_problematic_items():
    """Items that generate the most SAV tickets overall."""
    rows = frappe.db.sql("""
        SELECT item_concerned, COUNT(*) as total,
               SUM(CASE WHEN status NOT IN ('Closed', 'Resolved') THEN 1 ELSE 0 END) as open_count,
               MAX(recurrence_count) as max_recurrence
        FROM `tabSAV Ticket`
        WHERE item_concerned IS NOT NULL AND item_concerned != ''
        GROUP BY item_concerned
        ORDER BY total DESC
        LIMIT 8
    """, as_dict=True)

    return [
        {
            "item": r.item_concerned,
            "total_tickets": r.total,
            "open_tickets": r.open_count,
            "max_recurrence": r.max_recurrence,
            "link": "/app/item/" + r.item_concerned if r.item_concerned else None,
        }
        for r in rows
    ]


def _get_linked_executions():
    """Count of linked Task, Timesheet, Event, Stock Entry from SAV child tables."""
    task_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Execution Link`
        WHERE reference_doctype = 'Task'
    """)[0][0]

    timesheet_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Execution Link`
        WHERE reference_doctype = 'Timesheet'
    """)[0][0]

    stock_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSAV Stock Action`
        WHERE reference_name IS NOT NULL AND reference_name != ''
    """)[0][0]

    return {
        "tasks": int(task_count or 0),
        "timesheets": int(timesheet_count or 0),
        "stock_entries": int(stock_count or 0),
    }


def _get_mttr():
    """Mean Time To Resolve — average days from creation to closure."""
    result = frappe.db.sql("""
        SELECT AVG(DATEDIFF(closure_date, creation)) as avg_days,
               MIN(DATEDIFF(closure_date, creation)) as min_days,
               MAX(DATEDIFF(closure_date, creation)) as max_days,
               COUNT(*) as count
        FROM `tabSAV Ticket`
        WHERE status = 'Closed'
        AND closure_date IS NOT NULL
    """, as_dict=True)

    if result and result[0].avg_days is not None:
        return {
            "avg_days": round(float(result[0].avg_days), 1),
            "min_days": int(result[0].min_days or 0),
            "max_days": int(result[0].max_days or 0),
            "sample_size": int(result[0].count or 0),
        }
    return {"avg_days": None, "min_days": None, "max_days": None, "sample_size": 0}
