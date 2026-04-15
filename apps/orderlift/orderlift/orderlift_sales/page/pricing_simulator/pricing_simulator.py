import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder import _load_builder_items, _normalize_rules
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
            "enabled_item_count": _count_enabled_items(),
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
            "buying_price_list": selected.get("buying_price_list") or "",
            "pricing_scenario": selected.get("pricing_scenario") or "",
            "customs_policy": selected.get("customs_policy") or "",
            "benchmark_policy": selected.get("benchmark_policy") or "",
            "allowed_scenarios": dynamic_context.get("allowed_pricing_scenarios") or [],
            "allowed_customs": dynamic_context.get("allowed_customs_policies") or [],
            "allowed_benchmarks": dynamic_context.get("allowed_benchmark_policies") or [],
        },
        "static": {"selling_price_lists": static_lists},
        "enabled_item_count": _count_enabled_items(),
        "warnings": [],
    }


@frappe.whitelist()
def run_pricing_simulation(payload=None):
    data = json.loads(payload) if isinstance(payload, str) else (payload or {})
    items, item_warnings = _resolve_items_for_simulation(data)
    if not items:
        frappe.throw(_("Add at least one item to simulate."))

    sales_person = (data.get("sales_person") or "").strip()
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name") if sales_person else None
    agent_doc = frappe.get_doc("Agent Pricing Rules", agent_name) if agent_name else None

    requested_mode = (data.get("mode") or "Auto").strip()
    resolved_mode = _resolve_mode(requested_mode, (agent_doc.pricing_mode if agent_doc else ""))

    if resolved_mode == "Static":
        out = _run_static_simulation(data, items, agent_doc, resolved_mode)
    else:
        out = _run_dynamic_simulation(data, items, agent_doc, resolved_mode)
    out["warnings"] = (item_warnings or []) + (out.get("warnings") or [])
    out["simulated_item_count"] = len(items)
    return out


def _run_dynamic_simulation(data, items, agent_doc, resolved_mode):
    doc = frappe.new_doc("Pricing Sheet")
    doc.allow_empty_expenses_policy = 1

    doc.customer = (data.get("customer") or "").strip()
    doc.sales_person = (data.get("sales_person") or "").strip()

    defaults = build_dynamic_context(agent_doc=agent_doc) if agent_doc else {}
    selected = defaults.get("selected") or {}

    sourcing_rules = _resolve_dynamic_sourcing_rules(data, selected)
    first_rule = sourcing_rules[0] if sourcing_rules else {}
    warnings = []

    if not ((data.get("pricing_scenario") or "").strip() or (first_rule.get("pricing_scenario") or "").strip() or (selected.get("pricing_scenario") or "").strip()):
        warnings.append(_("No Expenses Policy selected. Dynamic simulation continues with zero policy expenses."))
    elif any((rule.get("source_buying_price_list") or "").strip() and not (rule.get("pricing_scenario") or "").strip() for rule in sourcing_rules):
        warnings.append(_("Some dynamic source rows have no Expenses Policy. Matching items use zero policy expenses."))

    doc.pricing_scenario = (data.get("pricing_scenario") or first_rule.get("pricing_scenario") or selected.get("pricing_scenario") or "").strip()
    doc.customs_policy = (data.get("customs_policy") or first_rule.get("customs_policy") or selected.get("customs_policy") or "").strip()
    doc.benchmark_policy = (data.get("benchmark_policy") or first_rule.get("benchmark_policy") or selected.get("benchmark_policy") or "").strip()
    doc.geography_territory = (data.get("geography_territory") or "").strip()
    doc.minimum_margin_percent = flt(data.get("minimum_margin_percent") or 0)
    doc.set("scenario_mappings", [])
    for idx, rule in enumerate(sourcing_rules, start=1):
        doc.append(
            "scenario_mappings",
            {
                "source_buying_price_list": rule.get("source_buying_price_list") or "",
                "pricing_scenario": rule.get("pricing_scenario") or "",
                "customs_policy": rule.get("customs_policy") or "",
                "benchmark_policy": rule.get("benchmark_policy") or "",
                "priority": cint(rule.get("priority") or (idx * 10)),
                "is_active": 1 if cint(rule.get("is_active") or 0) else 0,
            },
        )

    doc.set("lines", [])
    for row in items:
        doc.append(
            "lines",
            {
                "item": row.get("item"),
                "qty": flt(row.get("qty") or 0),
                "source_bundle": row.get("source_bundle") or "",
                "source_buying_price_list": row.get("source_buying_price_list") or row.get("buying_list") or "",
            },
        )

    doc.recalculate()

    rows = []
    only_priced = cint(data.get("only_priced_items") or 0) == 1
    filtered_out = 0
    for line in doc.lines or []:
        row = {
            "item": line.item,
            "qty": flt(line.qty),
            "material": getattr(line, "customs_material", "") or "",
            "customs_tariff_number": getattr(line, "customs_tariff_number", "") or "",
            "source_buying_price_list": getattr(line, "source_buying_price_list", "") or "",
            "expenses_policy": line.resolved_pricing_scenario or doc.pricing_scenario or "",
            "customs_policy": doc.customs_policy or "",
            "benchmark_policy": doc.benchmark_policy or "",
            "buy_price": flt(line.buy_price),
            "expense_unit_price": flt(getattr(line, "expense_unit_price", 0)),
            "base_amount": flt(line.base_amount),
            "customs_base_value": flt(getattr(line, "customs_base_value", 0)),
            "customs_value_per_kg": flt(getattr(line, "customs_value_per_kg", 0)),
            "customs_total_percent": flt(getattr(line, "customs_total_percent", 0)),
            "final_sell_unit_price": flt(line.final_sell_unit_price),
            "final_sell_total": flt(line.final_sell_total),
            "margin_pct": flt(line.margin_pct),
            "resolved_pricing_scenario": line.resolved_pricing_scenario or "",
            "benchmark_reference": flt(line.benchmark_reference),
            "margin_unit_amount": flt(getattr(line, "margin_unit_amount", 0)),
            "benchmark_ratio": flt(line.benchmark_ratio),
            "benchmark_status": line.benchmark_status or "",
            "margin_source": line.margin_source or "",
            "tier_modifier_amount": flt(line.tier_modifier_amount),
            "zone_modifier_amount": flt(line.zone_modifier_amount),
            "customs_applied": flt(line.customs_applied),
            "transport_allocated": flt(line.transport_allocated),
            "applied_benchmark_policy": doc.benchmark_policy or "",
            "resolved_benchmark_rule": getattr(line, "resolved_benchmark_rule", "") or "",
        }
        if only_priced and flt(row.get("buy_price")) <= 0:
            filtered_out += 1
            continue
        rows.append(row)

    return {
        "mode": resolved_mode,
        "pricing_mode": "Dynamic",
        "rows": rows,
        "summary": {
            "item_count": len(rows),
            "policy_count": len([x for x in sourcing_rules if x.get("source_buying_price_list")]),
            "global_margin_pct": _compute_global_margin_pct(doc),
        },
        "resolved": {
            "pricing_scenario": doc.pricing_scenario or "",
            "customs_policy": doc.customs_policy or "",
            "benchmark_policy": doc.benchmark_policy or "",
        },
        "warnings": warnings + _split_warnings(doc.projection_warnings)
        + ([_("Filtered out {0} unpriced dynamic item(s)." ).format(filtered_out)] if filtered_out else []),
    }


def _run_static_simulation(data, items, agent_doc, resolved_mode):
    requested_lists = data.get("selling_price_lists") or []
    requested_lists = [str(x).strip() for x in requested_lists if str(x).strip()]
    if not requested_lists and agent_doc:
        requested_lists = _get_static_lists(agent_doc)

    if not requested_lists:
        requested_lists = frappe.get_all(
            "Price List",
            filters={"enabled": 1, "selling": 1},
            pluck="name",
            limit_page_length=50,
        )

    if not requested_lists:
        frappe.throw(_("Static simulation requires at least one selling price list (from agent or manual override)."))

    item_codes = [x.get("item") for x in items]
    reference_buy_prices = {}
    buy_lists = [row.get("source_buying_price_list") for row in _normalize_rules(data.get("sourcing_rules") or []) if cint(row.get("is_active") or 0) and row.get("source_buying_price_list")]
    if buy_lists:
        first_buy = buy_lists[0]
        reference_buy_prices = get_latest_item_prices(item_codes, first_buy, buying=True) or {}
    price_maps = {
        pl: get_latest_item_prices(item_codes, pl, buying=False)
        for pl in requested_lists
    }

    rows = []
    missing = 0
    only_priced = cint(data.get("only_priced_items") or 0) == 1
    filtered_out = 0
    for row in items:
        code = row.get("item")
        qty = flt(row.get("qty") or 0)
        item_meta = frappe.db.get_value("Item", code, ["custom_material", "customs_tariff_number"], as_dict=1) or {}
        options = []
        for pl in requested_lists:
            rate = flt((price_maps.get(pl) or {}).get(code))
            if rate > 0:
                options.append({"price_list": pl, "rate": rate})

        selected = options[0] if options else {"price_list": "", "rate": 0}
        if not options:
            missing += 1

        out_row = {
            "item": code,
            "qty": qty,
            "material": item_meta.get("custom_material") or "",
            "customs_tariff_number": item_meta.get("customs_tariff_number") or "",
            "reference_buy_price": flt(reference_buy_prices.get(code) or 0),
            "selected_price_list": selected.get("price_list") or "",
            "selected_price": flt(selected.get("rate")),
            "line_total": flt(selected.get("rate")) * qty,
            "options": options,
            "option_count": len(options),
        }
        out_row["static_margin_pct"] = ((out_row["selected_price"] - out_row["reference_buy_price"]) / out_row["reference_buy_price"] * 100) if out_row["reference_buy_price"] > 0 else 0
        if only_priced and flt(out_row.get("selected_price")) <= 0:
            filtered_out += 1
            continue
        rows.append(out_row)

    warnings = []
    if missing:
        warnings.append(_("{0} item(s) have no static price in selected lists.").format(missing))
    if filtered_out:
        warnings.append(_("Filtered out {0} unpriced static item(s)." ).format(filtered_out))

    return {
        "mode": resolved_mode,
        "pricing_mode": "Static",
        "rows": rows,
        "summary": {
            "priced_items": len(rows) - missing,
            "missing_items": missing,
            "selling_lists_count": len(requested_lists),
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


def _resolve_items_for_simulation(data):
    use_all = cint(data.get("use_all_enabled_items") or 0) == 1
    qty_default = flt(data.get("default_qty") or 1)
    if qty_default <= 0:
        qty_default = 1

    if not use_all:
        return _normalize_items(data.get("items") or []), []

    mode = _resolve_mode((data.get("mode") or "Auto").strip(), "")
    item_group = (data.get("item_group") or "").strip()
    max_items = cint(data.get("max_items") or 0)
    item_search = (data.get("item_search") or "").strip()
    material = (data.get("material") or "").strip()

    if mode == "Dynamic":
        rules = _normalize_rules(data.get("sourcing_rules") or [])
        active_buying_lists = [row.get("source_buying_price_list") for row in rules if cint(row.get("is_active") or 0) and row.get("source_buying_price_list")]
        if active_buying_lists:
            items, warnings = _load_builder_items(active_buying_lists, item_group=item_group, max_items=max_items)
            return _apply_simulation_item_filters(items, qty_default, item_search=item_search, material=material), warnings

    if mode == "Static":
        selling_lists = [str(x).strip() for x in (data.get("selling_price_lists") or []) if str(x).strip()]
        if selling_lists:
            items, warnings = _load_static_items(selling_lists, item_group=item_group, max_items=max_items)
            return _apply_simulation_item_filters(items, qty_default, item_search=item_search, material=material), warnings

    if max_items < 0:
        max_items = 0

    filters: dict[str, Any] = {
        "disabled": 0,
    }
    if frappe.db.has_column("Item", "is_sales_item"):
        filters["is_sales_item"] = 1

    warnings = []
    if item_group and item_group != "All Item Groups":
        if _is_item_group_node(item_group):
            descendants = _descendant_leaf_item_groups(item_group)
            if descendants:
                filters["item_group"] = ["in", descendants]
            else:
                warnings.append(_("Selected Item Group has no leaf item groups."))
        else:
            filters["item_group"] = item_group

    rows = frappe.get_all(
        "Item",
        filters=filters,
        fields=["name"],
        order_by="name asc",
        limit_page_length=max_items if max_items > 0 else 0,
    )

    out = [
        {
            "item": row.get("name"),
            "qty": qty_default,
            "source_bundle": "",
        }
        for row in rows
        if row.get("name")
    ]

    if not out:
        warnings.append(_("No enabled items found for selected filters."))
    else:
        warnings.append(_("Auto-loaded {0} enabled item(s) for simulation.").format(len(out)))
    return out, warnings


def _apply_simulation_item_filters(items, qty_default, item_search="", material=""):
    out = []
    query = (item_search or "").strip().lower()
    material_filter = (material or "").strip().lower()
    if not items:
        return out

    item_codes = [row.get("item") for row in items if row.get("item")]
    details_map = {}
    if item_codes:
        details_map = {
            row.get("name"): row
            for row in frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=["name", "item_name", "item_group", "custom_material"], limit_page_length=0)
        }

    for row in items:
        code = row.get("item") or ""
        details = details_map.get(code) or {}
        haystack = " ".join([
            code,
            details.get("item_name") or "",
            details.get("item_group") or "",
            details.get("custom_material") or "",
        ]).lower()
        if query and query not in haystack:
            continue
        if material_filter and material_filter != (details.get("custom_material") or "").lower():
            continue
        out.append(
            {
                **row,
                "qty": flt(row.get("qty") or qty_default or 1) or 1,
                "source_buying_price_list": row.get("source_buying_price_list") or row.get("buying_list") or "",
            }
        )
    return out


def _load_static_items(selling_lists, item_group=None, max_items=0):
    if not selling_lists:
        return [], []
    rows = _get_latest_price_rows(selling_lists, buying=0)
    if not rows:
        return [], [_("No selling prices found in the selected selling price lists.")]

    grouped = {}
    priority = {name: idx for idx, name in enumerate(selling_lists)}
    for row in rows:
        item_code = row.get("item_code")
        if not item_code:
            continue
        candidate = {"item": item_code, "selected_price_list": row.get("price_list") or "", "selected_price": flt(row.get("price_list_rate") or 0)}
        bucket = grouped.get(item_code)
        if not bucket or priority.get(candidate["selected_price_list"], 9999) < priority.get(bucket["selected_price_list"], 9999):
            grouped[item_code] = candidate

    filters = {"name": ["in", list(grouped.keys())], "disabled": 0}
    warnings = []
    if item_group and item_group != "All Item Groups":
        if _is_item_group_node(item_group):
            descendants = _descendant_leaf_item_groups(item_group)
            if descendants:
                filters["item_group"] = ["in", descendants]
            else:
                warnings.append(_("Selected Item Group has no leaf item groups."))
        else:
            filters["item_group"] = item_group

    item_rows = frappe.get_all("Item", filters=filters, fields=["name"], order_by="name asc", limit_page_length=max_items if max_items > 0 else 0)
    items = [{"item": row.get("name"), "qty": 1, "source_bundle": ""} for row in item_rows if row.get("name")]
    if not items:
        warnings.append(_("No items matched the selected selling price lists and filters."))
    return items, warnings


def _get_latest_price_rows(price_lists, buying=0):
    conditions = ["ip.price_list in %(price_lists)s"]
    params = {"price_lists": tuple(price_lists), "today": frappe.utils.nowdate()}
    if frappe.db.has_column("Item Price", "enabled"):
        conditions.append("ip.enabled = 1")
    if frappe.db.has_column("Item Price", "buying"):
        conditions.append("ip.buying = %(buying)s")
        params["buying"] = cint(buying)
    if frappe.db.has_column("Item Price", "selling") and not buying:
        conditions.append("ip.selling = 1")
    if frappe.db.has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if frappe.db.has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")
    order_by = "ip.price_list ASC, ip.item_code ASC, ip.modified DESC"
    if frappe.db.has_column("Item Price", "valid_from"):
        order_by = "ip.price_list ASC, ip.item_code ASC, ip.valid_from DESC, ip.modified DESC"
    return frappe.db.sql(
        f"""
        select ip.item_code, ip.price_list, ip.price_list_rate
        from `tabItem Price` ip
        where {' and '.join(conditions)}
        order by {order_by}
        """,
        params,
        as_dict=True,
    )


def _resolve_dynamic_sourcing_rules(data, selected):
    rows = data.get("sourcing_rules") or []
    rules = _normalize_rules(rows)
    rules = [row for row in rules if cint(row.get("is_active") or 0) and row.get("source_buying_price_list")]
    if rules:
        return rules
    buying_list = (data.get("buying_price_list") or selected.get("buying_price_list") or "").strip()
    if not buying_list:
        return []
    return _normalize_rules(
        [{
            "buying_price_list": buying_list,
            "pricing_scenario": data.get("pricing_scenario") or selected.get("pricing_scenario") or "",
            "customs_policy": data.get("customs_policy") or selected.get("customs_policy") or "",
            "benchmark_policy": data.get("benchmark_policy") or selected.get("benchmark_policy") or "",
            "is_active": 1,
        }]
    )


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
    grouped = {}
    ordered = []
    for raw in (text or "").splitlines():
        value = raw.strip()
        if not value:
            continue
        normalized = value
        if normalized.lower().startswith("row ") and ":" in normalized:
            normalized = normalized.split(":", 1)[1].strip()
        if normalized not in grouped:
            grouped[normalized] = 0
            ordered.append(normalized)
        grouped[normalized] += 1

    out = []
    for msg in ordered:
        count = grouped.get(msg, 0)
        if count > 1:
            out.append(_("{0} rows: {1}").format(count, msg))
        else:
            out.append(msg)
    return out


def _count_enabled_items():
    filters = {"disabled": 0}
    if frappe.db.has_column("Item", "is_sales_item"):
        filters["is_sales_item"] = 1
    return cint(frappe.db.count("Item", filters=filters))


def _compute_global_margin_pct(doc):
    if hasattr(doc, "global_margin_pct"):
        return flt(getattr(doc, "global_margin_pct"))
    total_buy = flt(getattr(doc, "total_buy", 0))
    total_sell = flt(getattr(doc, "total_selling", 0))
    if total_sell <= 0:
        return 0.0
    return flt(((total_sell - total_buy) / total_sell) * 100)


def _is_item_group_node(item_group_name):
    return cint(frappe.db.get_value("Item Group", item_group_name, "is_group") or 0) == 1


def _descendant_leaf_item_groups(item_group_name):
    node = frappe.db.get_value("Item Group", item_group_name, ["lft", "rgt"], as_dict=True) or {}
    lft = cint(node.get("lft") or 0)
    rgt = cint(node.get("rgt") or 0)
    if not lft or not rgt:
        return []

    return frappe.get_all(
        "Item Group",
        filters={
            "lft": [">=", lft],
            "rgt": ["<=", rgt],
            "is_group": 0,
        },
        pluck="name",
        limit_page_length=0,
    )
