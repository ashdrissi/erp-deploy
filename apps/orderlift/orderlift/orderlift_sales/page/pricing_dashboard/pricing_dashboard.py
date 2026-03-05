"""Pricing Dashboard server-side API.

Returns item-level pricing data across Pricing Sheets for the
master simulation dashboard.
"""

import frappe
from frappe import _
from frappe.utils import flt, cint


@frappe.whitelist()
def get_dashboard_data(filters=None):
    """Fetch aggregated pricing data for the dashboard.

    Returns:
        dict with keys: kpis, items, scenarios, sheets
    """
    import json
    filters = json.loads(filters) if isinstance(filters, str) else (filters or {})

    sheet_filters = {"docstatus": ["<", 2]}
    if filters.get("pricing_sheet"):
        sheet_filters["name"] = filters["pricing_sheet"]
    if filters.get("customer"):
        sheet_filters["customer"] = filters["customer"]
    if filters.get("pricing_scenario"):
        sheet_filters["pricing_scenario"] = filters["pricing_scenario"]

    sheets = frappe.get_all(
        "Pricing Sheet",
        filters=sheet_filters,
        fields=[
            "name", "sheet_name", "customer", "pricing_scenario",
            "benchmark_policy", "applied_benchmark_policy",
            "total_buy", "total_expenses", "total_selling",
            "calculated_on", "sales_person", "geography_territory",
        ],
        order_by="modified desc",
        limit_page_length=50,
    )

    if not sheets:
        return {"kpis": _empty_kpis(), "items": [], "scenarios": [], "sheets": []}

    sheet_names = [s.name for s in sheets]

    items = frappe.get_all(
        "Pricing Sheet Item",
        filters={"parent": ["in", sheet_names]},
        fields=[
            "parent", "item", "qty", "buy_price", "buy_price_missing",
            "base_amount", "expense_total", "projected_unit_price",
            "final_sell_unit_price", "final_sell_total", "margin_pct",
            "benchmark_price", "benchmark_delta_pct", "benchmark_status",
            "benchmark_reference", "benchmark_ratio", "benchmark_source_count",
            "benchmark_method", "margin_source",
            "resolved_pricing_scenario", "resolved_margin_rule",
            "resolved_benchmark_rule",
            "customs_applied", "transport_allocated",
        ],
        order_by="parent, idx",
        limit_page_length=0,
    )

    # Build KPIs
    total_items = len(items)
    total_buy = sum(flt(i.base_amount) for i in items)
    total_sell = sum(flt(i.final_sell_total) for i in items)
    avg_margin = (sum(flt(i.margin_pct) for i in items) / total_items) if total_items else 0

    benchmarked = [i for i in items if i.benchmark_reference and flt(i.benchmark_reference) > 0]
    benchmark_coverage = (len(benchmarked) / total_items * 100) if total_items else 0
    avg_ratio = (sum(flt(i.benchmark_ratio) for i in benchmarked) / len(benchmarked)) if benchmarked else 0

    margin_sources = {}
    for i in items:
        src = i.margin_source or "Unknown"
        margin_sources[src] = margin_sources.get(src, 0) + 1

    status_counts = {}
    for i in items:
        st = i.benchmark_status or "No Benchmark"
        status_counts[st] = status_counts.get(st, 0) + 1

    scenarios_set = set()
    for i in items:
        if i.resolved_pricing_scenario:
            scenarios_set.add(i.resolved_pricing_scenario)

    kpis = {
        "total_items": total_items,
        "total_sheets": len(sheets),
        "total_buy": total_buy,
        "total_sell": total_sell,
        "avg_margin": avg_margin,
        "benchmark_coverage": benchmark_coverage,
        "avg_ratio": avg_ratio,
        "margin_sources": margin_sources,
        "status_counts": status_counts,
        "scenarios_count": len(scenarios_set),
    }

    # Serialize child rows
    items_data = []
    sheet_map = {s.name: s for s in sheets}
    for i in items:
        sh = sheet_map.get(i.parent) or {}
        items_data.append({
            "sheet": i.parent,
            "sheet_name": getattr(sh, "sheet_name", ""),
            "customer": getattr(sh, "customer", ""),
            "item": i.item,
            "qty": flt(i.qty),
            "buy_price": flt(i.buy_price),
            "buy_missing": cint(i.buy_price_missing),
            "projected": flt(i.projected_unit_price),
            "final_price": flt(i.final_sell_unit_price),
            "margin_pct": flt(i.margin_pct),
            "benchmark_price": flt(i.benchmark_price),
            "benchmark_ref": flt(i.benchmark_reference),
            "benchmark_ratio": flt(i.benchmark_ratio),
            "benchmark_sources": cint(i.benchmark_source_count),
            "benchmark_status": i.benchmark_status or "",
            "benchmark_delta_pct": flt(i.benchmark_delta_pct),
            "margin_source": i.margin_source or "",
            "scenario": i.resolved_pricing_scenario or "",
            "margin_rule": i.resolved_margin_rule or "",
            "benchmark_rule": i.resolved_benchmark_rule or "",
            "customs": flt(i.customs_applied),
            "transport": flt(i.transport_allocated),
        })

    return {
        "kpis": kpis,
        "items": items_data,
        "scenarios": sorted(scenarios_set),
        "sheets": [
            {
                "name": s.name,
                "sheet_name": s.sheet_name,
                "customer": s.customer,
                "scenario": s.pricing_scenario,
                "total_buy": flt(s.total_buy),
                "total_sell": flt(s.total_selling),
                "benchmark_policy": s.applied_benchmark_policy or "",
                "calculated_on": str(s.calculated_on or ""),
            }
            for s in sheets
        ],
    }


def _empty_kpis():
    return {
        "total_items": 0,
        "total_sheets": 0,
        "total_buy": 0,
        "total_sell": 0,
        "avg_margin": 0,
        "benchmark_coverage": 0,
        "avg_ratio": 0,
        "margin_sources": {},
        "status_counts": {},
        "scenarios_count": 0,
    }
