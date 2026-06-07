"""after_migrate hooks for the Orderlift HR module."""

from __future__ import annotations

import frappe


TRAINING_CENTER = "training-center"
TRAINING_LEADERBOARD = "training-leaderboard"
PERFORMANCE_LEADERBOARD = "performance-leaderboard"
PERFORMANCE_CYCLE_DASHBOARD = "performance-cycle-dashboard"

LEARNER_ROLES = (
    "Orderlift Admin",
    "System Manager",
    "Sales User",
    "Pricing Manager",
    "Logistics User",
    "Finance User",
    "Installation User",
    "Service User",
)

ADMIN_ROLES = ("Orderlift Admin", "System Manager")


# (metric_code, metric_name, category, unit, direction, default_target, description)
BUILTIN_METRICS: tuple[tuple[str, str, str, str, str, float, str], ...] = (
    (
        "sales.so_count",
        "Sales Orders Count",
        "Sales",
        "count",
        "Higher is better",
        0.0,
        "Number of submitted Sales Orders owned by the employee in the cycle period.",
    ),
    (
        "sales.so_total_amount",
        "Sales Orders Total",
        "Sales",
        "\u20ac",
        "Higher is better",
        0.0,
        "Sum of grand totals across all submitted Sales Orders owned by the employee.",
    ),
    (
        "sales.so_avg_value",
        "Sales Order Average Value",
        "Sales",
        "\u20ac",
        "Higher is better",
        0.0,
        "Average grand total per submitted Sales Order owned by the employee.",
    ),
    (
        "sales.quotation_count",
        "Quotations Submitted",
        "Quotations",
        "count",
        "Higher is better",
        0.0,
        "Number of submitted Quotations owned by the employee in the cycle period.",
    ),
    (
        "sales.quotation_total_amount",
        "Quotations Total Value",
        "Quotations",
        "\u20ac",
        "Higher is better",
        0.0,
        "Sum of grand totals across all submitted Quotations owned by the employee.",
    ),
    (
        "sales.conversion_rate",
        "Quote \u2192 Order Conversion",
        "Sales",
        "%",
        "Higher is better",
        50.0,
        "Percentage of submitted Quotations that became submitted Sales Orders for the same employee.",
    ),
    (
        "sales.quotation_speed_avg",
        "Quotation Speed (avg)",
        "Quotations",
        "hours",
        "Lower is better",
        24.0,
        "Average hours from Quotation creation to submission. Lower means faster turnaround.",
    ),
    (
        "sales.quotation_speed_median",
        "Quotation Speed (median)",
        "Quotations",
        "hours",
        "Lower is better",
        24.0,
        "Median hours from Quotation creation to submission. Less sensitive to outliers than the average.",
    ),
    (
        "sales.time_to_close_days",
        "Time to Close",
        "Sales",
        "days",
        "Lower is better",
        14.0,
        "Average days between submitting a Quotation and submitting the matching Sales Order. Measures sales-cycle speed.",
    ),
    (
        "sales.commission_total",
        "Commission Earned",
        "Sales",
        "\u20ac",
        "Higher is better",
        0.0,
        "Total commission amount earned by the salesperson on Sales Orders in the cycle period.",
    ),
    (
        "sales.discount_compliance_pct",
        "Discount Compliance",
        "Quality",
        "%",
        "Higher is better",
        95.0,
        "Percentage of submitted Quotations whose additional discount stays within the configured compliance band.",
    ),
    (
        "crm.opportunities_owned",
        "Opportunities Owned",
        "CRM",
        "count",
        "Higher is better",
        0.0,
        "Number of Opportunities where the employee is the opportunity owner during the cycle period.",
    ),
    (
        "crm.opportunities_won",
        "Opportunities Won",
        "CRM",
        "count",
        "Higher is better",
        0.0,
        "Number of owned Opportunities with status Converted or Closed in the cycle period.",
    ),
    (
        "crm.opportunity_win_rate",
        "Opportunity Win Rate",
        "CRM",
        "%",
        "Higher is better",
        30.0,
        "Percentage of owned Opportunities that were won (Converted or Closed) in the cycle period.",
    ),
    (
        "crm.pipeline_value",
        "Pipeline Value",
        "CRM",
        "\u20ac",
        "Higher is better",
        0.0,
        "Sum of opportunity_amount across all open Opportunities owned by the employee.",
    ),
    (
        "crm.campaign_targets_assigned",
        "Campaign Targets Assigned",
        "CRM",
        "count",
        "Higher is better",
        0.0,
        "Number of Partner Campaign Targets assigned to the employee during the cycle period.",
    ),
    (
        "crm.campaign_targets_contacted",
        "Campaign Targets Contacted",
        "CRM",
        "count",
        "Higher is better",
        0.0,
        "Number of assigned campaign targets that have a recorded last_contact_date within the cycle.",
    ),
    (
        "crm.campaign_targets_visited",
        "Campaign Targets Visited",
        "CRM",
        "count",
        "Higher is better",
        0.0,
        "Number of assigned campaign targets that have a recorded visit_date within the cycle.",
    ),
    (
        "crm.contact_rate",
        "Contact Rate",
        "CRM",
        "%",
        "Higher is better",
        60.0,
        "Percentage of assigned campaign targets that were actually contacted in the cycle.",
    ),
    (
        "ops.qc_items_verified",
        "QC Items Verified",
        "Operations",
        "count",
        "Higher is better",
        0.0,
        "Number of Installation QC Items the employee marked as verified during the cycle period.",
    ),
    (
        "ops.qc_avg_verification_hours",
        "QC Verification Speed",
        "Operations",
        "hours",
        "Lower is better",
        24.0,
        "Average hours between QC Item creation and verification. Lower is faster QC turnaround.",
    ),
    (
        "ops.projects_owned",
        "Projects Owned",
        "Operations",
        "count",
        "Higher is better",
        0.0,
        "Number of Projects where the employee is the project owner during the cycle period.",
    ),
    (
        "training.module_completion_pct",
        "Training Completion",
        "Training",
        "%",
        "Higher is better",
        80.0,
        "Percentage of assigned training modules the employee has completed across all programs.",
    ),
    (
        "training.quiz_average_pct",
        "Training Quiz Average",
        "Training",
        "%",
        "Higher is better",
        80.0,
        "Average quiz score (best attempt per quiz) across all completed training modules.",
    ),
    (
        "training.recency_score",
        "Training Recency",
        "Training",
        "%",
        "Higher is better",
        80.0,
        "Recency-weighted training engagement score. Decays over time so stale training counts less.",
    ),
    (
        "attendance.present_rate",
        "Attendance Rate",
        "Attendance",
        "%",
        "Higher is better",
        95.0,
        "Weighted attendance rate: Present counts as 1, Half Day as 0.5, divided by working days in the cycle.",
    ),
    (
        "attendance.absent_count",
        "Absences",
        "Attendance",
        "count",
        "Lower is better",
        2.0,
        "Number of Attendance records marked Absent during the cycle period.",
    ),
    (
        "attendance.late_days_count",
        "Late Days",
        "Attendance",
        "count",
        "Lower is better",
        3.0,
        "Number of Attendance records flagged with late_entry during the cycle period.",
    ),
    (
        "attendance.avg_working_hours",
        "Average Working Hours",
        "Attendance",
        "hours",
        "Higher is better",
        8.0,
        "Average working_hours per Attendance record across the cycle period.",
    ),
)


def after_migrate() -> None:
    """Keep page roles + metric catalogue in sync after each migration."""
    sync_page_roles(TRAINING_CENTER, LEARNER_ROLES)
    sync_page_roles(TRAINING_LEADERBOARD, LEARNER_ROLES)
    sync_page_roles(PERFORMANCE_LEADERBOARD, LEARNER_ROLES)
    sync_page_roles(PERFORMANCE_CYCLE_DASHBOARD, ADMIN_ROLES)
    seed_performance_metrics()
    frappe.db.commit()


def sync_page_roles(page_name: str, roles: tuple[str, ...]) -> dict:
    if not frappe.db.exists("Page", page_name):
        return {"skipped": True, "reason": "missing page", "page": page_name}
    page = frappe.get_doc("Page", page_name)
    page.set("roles", [])
    for role in roles:
        if frappe.db.exists("Role", role):
            page.append("roles", {"role": role})
    page.save(ignore_permissions=True)
    return {"page": page_name, "roles": list(roles)}


def seed_performance_metrics() -> dict:
    if not frappe.db.exists("DocType", "Performance Metric"):
        return {"skipped": True, "reason": "doctype missing"}
    written = 0
    updated = 0
    for code, name, category, unit, direction, target, description in BUILTIN_METRICS:
        if frappe.db.exists("Performance Metric", code):
            current = frappe.db.get_value(
                "Performance Metric", code, "description"
            )
            if not current and description:
                frappe.db.set_value(
                    "Performance Metric", code, "description", description
                )
                updated += 1
            continue
        doc = frappe.get_doc(
            {
                "doctype": "Performance Metric",
                "metric_code": code,
                "metric_name": name,
                "category": category,
                "unit": unit,
                "direction": direction,
                "default_target": target,
                "description": description,
                "source_type": "Builtin",
                "score_curve": "Linear",
                "is_active": 1,
            }
        )
        doc.insert(ignore_permissions=True)
        written += 1
    return {"seeded": written, "updated": updated, "total": len(BUILTIN_METRICS)}
