import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
    DYNAMIC_MODE,
    build_dynamic_context,
)
from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import get_latest_item_prices


STATIC_MODE = "Pick from Published Selling Price List"


@frappe.whitelist()
def get_simulation_defaults(sales_person=None, mode="Auto"):
    mode = (mode or "Auto").strip()
    sales_person = (sales_person or "").strip()
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name") if sales_person else None

    if not agent_name:
        return {
            "sales_person": sales_person,
            "agent_rule": "",
            "resolved_mode": _resolve_mode(mode, None),
            "agent_mode": "",
            "dynamic": {},
            "static": {"selling_price_lists": []},
            "warnings": [_("No Agent Pricing Rules found for selected sales person.")] if sales_person else [],
        }

    agent_doc = frappe.get_doc("Agent Pricing Rules", agent_name)
    agent_mode = agent_doc.pricing_mode or ""
    resolved_mode = _resolve_mode(mode, agent_mode)

    dynamic_context = build_dynamic_context(agent_doc=agent_doc)
    selected = dynamic_context.get("selected") or {}
    static_lists = _get_static_lists(agent_doc)

    return {
        "sales_person": sales_person,
        "agent_rule": agent_name,
        "resolved_mode": resolved_mode,
        "agent_mode": agent_mode,
        "dynamic": {
            "pricing_scenario": selected.get("pricing_scenario") or "",
            "customs_policy": selected.get("customs_policy") or "",
            "benchmark_policy": selected.get("benchmark_policy") or "",
            "allowed_scenarios": dynamic_context.get("allowed_pricing_scenarios") or [],
            "allowed_customs": dynamic_context.get("allowed_customs_policies") or [],
            "allowed_benchmarks": dynamic_context.get("allowed_benchmark_policies") or [],
        },
        "static": {"selling_price_lists": static_lists},
        "warnings": [],
    }


@frappe.whitelist()
def run_pricing_simulation(payload=None):
    data = json.loads(payload) if isinstance(payload, str) else (payload or {})
    items = _normalize_items(data.get("items") or [])
    if not items:
        frappe.throw(_("Add at least one item to simulate."))

    sales_person = (data.get("sales_person") or "").strip()
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name") if sales_person else None
    agent_doc = frappe.get_doc("Agent Pricing Rules", agent_name) if agent_name else None

    requested_mode = (data.get("mode") or "Auto").strip()
    resolved_mode = _resolve_mode(requested_mode, (agent_doc.pricing_mode if agent_doc else ""))

    if resolved_mode == "Static":
        return _run_static_simulation(data, items, agent_doc, resolved_mode)
    return _run_dynamic_simulation(data, items, agent_doc, resolved_mode)


def _run_dynamic_simulation(data, items, agent_doc, resolved_mode):
    doc = frappe.new_doc("Pricing Sheet")

    doc.customer = (data.get("customer") or "").strip()
    doc.sales_person = (data.get("sales_person") or "").strip()

    defaults = build_dynamic_context(agent_doc=agent_doc) if agent_doc else {}
    selected = defaults.get("selected") or {}

    doc.pricing_scenario = (data.get("pricing_scenario") or selected.get("pricing_scenario") or "").strip()
    doc.customs_policy = (data.get("customs_policy") or selected.get("customs_policy") or "").strip()
    doc.benchmark_policy = (data.get("benchmark_policy") or selected.get("benchmark_policy") or "").strip()
    doc.scenario_policy = (data.get("scenario_policy") or "").strip()
    doc.geography_territory = (data.get("geography_territory") or "").strip()
    doc.minimum_margin_percent = flt(data.get("minimum_margin_percent") or 0)

    doc.set("lines", [])
    for row in items:
        doc.append(
            "lines",
            {
                "item": row.get("item"),
                "qty": flt(row.get("qty") or 0),
                "source_bundle": row.get("source_bundle") or "",
            },
        )

    doc.recalculate()

    rows = []
    for line in doc.lines or []:
        rows.append(
            {
                "item": line.item,
                "qty": flt(line.qty),
                "buy_price": flt(line.buy_price),
                "base_amount": flt(line.base_amount),
                "final_sell_unit_price": flt(line.final_sell_unit_price),
                "final_sell_total": flt(line.final_sell_total),
                "margin_pct": flt(line.margin_pct),
                "resolved_pricing_scenario": line.resolved_pricing_scenario or "",
                "benchmark_reference": flt(line.benchmark_reference),
                "benchmark_ratio": flt(line.benchmark_ratio),
                "benchmark_status": line.benchmark_status or "",
                "margin_source": line.margin_source or "",
                "tier_modifier_amount": flt(line.tier_modifier_amount),
                "zone_modifier_amount": flt(line.zone_modifier_amount),
                "customs_applied": flt(line.customs_applied),
                "transport_allocated": flt(line.transport_allocated),
            }
        )

    return {
        "mode": resolved_mode,
        "pricing_mode": "Dynamic",
        "rows": rows,
        "summary": {
            "total_buy": flt(doc.total_buy),
            "total_expenses": flt(doc.total_expenses),
            "total_selling": flt(doc.total_selling),
            "gross_margin": flt(doc.total_selling) - flt(doc.total_buy),
            "global_margin_pct": flt(doc.global_margin_pct),
        },
        "resolved": {
            "pricing_scenario": doc.pricing_scenario or "",
            "customs_policy": doc.customs_policy or "",
            "benchmark_policy": doc.benchmark_policy or "",
            "scenario_policy": doc.scenario_policy or "",
        },
        "warnings": _split_warnings(doc.projection_warnings),
    }


def _run_static_simulation(data, items, agent_doc, resolved_mode):
    requested_lists = data.get("selling_price_lists") or []
    requested_lists = [str(x).strip() for x in requested_lists if str(x).strip()]
    if not requested_lists and agent_doc:
        requested_lists = _get_static_lists(agent_doc)

    if not requested_lists:
        frappe.throw(_("Static simulation requires at least one selling price list (from agent or manual override)."))

    item_codes = [x.get("item") for x in items]
    price_maps = {
        pl: get_latest_item_prices(item_codes, pl, buying=False)
        for pl in requested_lists
    }

    rows = []
    missing = 0
    for row in items:
        code = row.get("item")
        qty = flt(row.get("qty") or 0)
        options = []
        for pl in requested_lists:
            rate = flt((price_maps.get(pl) or {}).get(code))
            if rate > 0:
                options.append({"price_list": pl, "rate": rate})

        selected = options[0] if options else {"price_list": "", "rate": 0}
        if not options:
            missing += 1

        rows.append(
            {
                "item": code,
                "qty": qty,
                "selected_price_list": selected.get("price_list") or "",
                "selected_price": flt(selected.get("rate")),
                "line_total": flt(selected.get("rate")) * qty,
                "options": options,
                "option_count": len(options),
            }
        )

    total = sum(flt(x.get("line_total")) for x in rows)
    warnings = []
    if missing:
        warnings.append(_("{0} item(s) have no static price in selected lists.").format(missing))

    return {
        "mode": resolved_mode,
        "pricing_mode": "Static",
        "rows": rows,
        "summary": {
            "total_selling": total,
            "priced_items": len(rows) - missing,
            "missing_items": missing,
        },
        "resolved": {"selling_price_lists": requested_lists},
        "warnings": warnings,
    }


def _normalize_items(items):
    out = []
    for row in items:
        item = (row.get("item") or "").strip()
        qty = flt(row.get("qty") or 0)
        if not item:
            continue
        if qty <= 0:
            qty = 1
        out.append(
            {
                "item": item,
                "qty": qty,
                "source_bundle": (row.get("source_bundle") or "").strip(),
            }
        )
    return out


def _resolve_mode(requested_mode, agent_mode):
    requested_mode = (requested_mode or "Auto").strip()
    if requested_mode in {"Dynamic", "Static"}:
        return requested_mode
    if agent_mode == STATIC_MODE:
        return "Static"
    return "Dynamic"


def _get_static_lists(agent_doc):
    rows = []
    for row in agent_doc.get("allocated_price_lists") or []:
        if not cint(row.get("is_active", 1)):
            continue
        rows.append(
            {
                "price_list": (row.get("selling_price_list") or "").strip(),
                "sequence": cint(row.get("default_sequence") or 999),
                "idx": cint(row.get("idx") or 0),
            }
        )
    rows = [r for r in rows if r.get("price_list")]
    rows.sort(key=lambda x: (x.get("sequence"), x.get("idx")))
    return [r.get("price_list") for r in rows]


def _split_warnings(text):
    lines = []
    for raw in (text or "").splitlines():
        value = raw.strip()
        if value:
            lines.append(value)
    return lines
