"""
Pricing Dashboard — server-side data provider.
Returns KPIs, recent sheets, and alert items for the dashboard page.
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_dashboard_data():
    """Aggregate all data needed by the Pricing Dashboard page."""
    return {
        "kpis": _get_kpis(),
        "recent_sheets": _get_recent_sheets(),
        "alerts": _get_alerts(),
    }


# ── KPIs ──────────────────────────────────────────────────────────────────────

def _get_kpis():
    kpis = {}

    # Total pricing sheets
    kpis["total_sheets"] = frappe.db.count("Pricing Sheet")

    # Sheets created this calendar month
    kpis["sheets_this_month"] = frappe.db.count(
        "Pricing Sheet",
        filters={"creation": [">=", frappe.utils.get_first_day(frappe.utils.nowdate())]},
    )

    # Average margin across sheets that have total_selling > 0
    avg = frappe.db.sql(
        """
        SELECT AVG(
            CASE
                WHEN total_selling > 0 AND total_buy > 0
                THEN ((total_selling - total_buy) / total_selling) * 100
                ELSE NULL
            END
        ) AS avg_margin
        FROM `tabPricing Sheet`
        WHERE total_selling > 0
        """,
        as_dict=True,
    )
    kpis["avg_margin_pct"] = round(float(avg[0].avg_margin or 0), 2) if avg else 0

    # Benchmark policies
    kpis["total_benchmark_policies"] = frappe.db.count("Pricing Benchmark Policy")
    kpis["benchmark_sources"] = frappe.db.count("Pricing Benchmark Source")

    # Customs policies and rules
    kpis["total_customs_policies"] = frappe.db.count("Pricing Customs Policy")
    kpis["customs_rules"] = frappe.db.count("Pricing Customs Rule")

    # Pricing scenarios and their expense entries
    kpis["total_scenarios"] = frappe.db.count("Pricing Scenario")
    kpis["total_scenario_expenses"] = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabPricing Scenario Expense`", as_list=True
    )[0][0]

    # Sheets with no benchmark policy and no customs policy (alert count)
    kpis["sheets_with_alerts"] = frappe.db.count(
        "Pricing Sheet",
        filters={"benchmark_policy": ["in", ["", None]]},
    )

    return kpis


# ── Recent sheets ───────────────────────────────────────────────────────────

def _get_recent_sheets():
    sheets = frappe.get_all(
        "Pricing Sheet",
        fields=["name", "sheet_name", "customer", "pricing_scenario", "total_selling", "modified", "modified_by"],
        order_by="modified desc",
        limit=12,
    )
    return sheets


# ── Alerts ──────────────────────────────────────────────────────────────────

def _get_alerts():
    alerts = []

    # Sheets missing benchmark policy
    missing_bench = frappe.db.count(
        "Pricing Sheet",
        filters={"benchmark_policy": ["in", ["", None]]},
    )
    if missing_bench:
        alerts.append({
            "level": "warn",
            "title": _("{0} sheet(s) have no Benchmark Policy").format(missing_bench),
            "message": _("Without a benchmark policy, margin guardrails won't be enforced."),
            "link": "/app/pricing-sheet?benchmark_policy=",
        })

    # Sheets missing customs policy
    missing_customs = frappe.db.count(
        "Pricing Sheet",
        filters={"customs_policy": ["in", ["", None]]},
    )
    if missing_customs:
        alerts.append({
            "level": "warn",
            "title": _("{0} sheet(s) have no Customs Policy").format(missing_customs),
            "message": _("Customs duties will not be applied to these pricing sheets."),
            "link": "/app/pricing-sheet?customs_policy=",
        })

    # Scenarios with no expenses
    empty_scenarios = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabPricing Scenario` ps
        WHERE NOT EXISTS (
            SELECT 1 FROM `tabPricing Scenario Expense` pse
            WHERE pse.parent = ps.name
        )
        """,
        as_list=True,
    )[0][0]
    if empty_scenarios:
        alerts.append({
            "level": "warn",
            "title": _("{0} scenario(s) have no expense entries").format(empty_scenarios),
            "message": _("Empty scenarios will produce zero-markup pricing."),
            "link": "/app/pricing-scenario",
        })

    # Benchmark policies with no sources
    empty_bench_policies = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabPricing Benchmark Policy` pbp
        WHERE NOT EXISTS (
            SELECT 1 FROM `tabPricing Benchmark Source` pbs
            WHERE pbs.parent = pbp.name
        )
        """,
        as_list=True,
    )[0][0]
    if empty_bench_policies:
        alerts.append({
            "level": "warn",
            "title": _("{0} benchmark policie(s) have no sources").format(empty_bench_policies),
            "message": _("Policies without sources won't produce benchmark comparisons."),
            "link": "/app/pricing-benchmark-policy",
        })

    return alerts
