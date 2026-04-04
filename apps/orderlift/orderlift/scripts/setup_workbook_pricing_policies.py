from __future__ import annotations

from statistics import mean

import frappe
from frappe.utils import flt

from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import get_item_details_map, get_latest_item_prices
from orderlift.sales.utils.pricing_projection import apply_expenses


CUSTOMS_POLICY_NAME = "Workbook Morocco Customs 2026"
SOURCE_BUYING_PRICE_LIST = "Turkey Source Cost"
CONVERTED_BUYING_PRICE_LIST = "Turkey Source Cost MAD 2026"
USD_TO_MAD_RATE = 9.8
TRANSPORT_CONTAINER_TYPE = "40HC Konya-Tanger"
WORKBOOK_TRANSPORT_TOTAL = ((1500 * 9.8 + 3700 + 1000 + 1000 + 5000) * 1.15) + 2500
TRANSPORT_CONTAINER_PRICE = WORKBOOK_TRANSPORT_TOTAL / 2.0
TRANSPORT_TOTAL_MERCH_VALUE = 300000.0
MONTHLY_OVERHEAD_PERCENT = (54700.0 / TRANSPORT_TOTAL_MERCH_VALUE) * 100.0
HALF_OVERHEAD_PERCENT = MONTHLY_OVERHEAD_PERCENT / 2.0
IMPUTS_PERCENT = 7.0

SCENARIOS = [
    {
        "scenario_name": "Workbook Sans Stock Min 2026",
        "selling_price_list": "Morocco Min",
        "benchmark_policy": "Workbook Passive Benchmark Min 2026",
        "overhead_percent": HALF_OVERHEAD_PERCENT,
        "margin_percent": 7.5,
        "description": "Matches workbook formula M = base + customs + transport + 50% overhead + 7% impots + 30% of 25% margin.",
    },
    {
        "scenario_name": "Workbook Sans Stock Normal 2026",
        "selling_price_list": "Morocco Normal",
        "benchmark_policy": "Workbook Passive Benchmark Normal 2026",
        "overhead_percent": HALF_OVERHEAD_PERCENT,
        "margin_percent": 12.5,
        "description": "Matches workbook formula N = base + customs + transport + 50% overhead + 7% impots + 50% of 25% margin.",
    },
    {
        "scenario_name": "Workbook With Stock 2026",
        "selling_price_list": "Morocco With Stock",
        "benchmark_policy": "Workbook Passive Benchmark Stock 2026",
        "overhead_percent": MONTHLY_OVERHEAD_PERCENT,
        "margin_percent": 25.0,
        "description": "Matches workbook formula O = base + customs + transport + 100% overhead + 7% impots + 25% margin.",
    },
]

CUSTOMS_RULES = [
    {"material": "STEEL", "rate_per_kg": 13.0 * 0.2025, "rate_percent": 20.25, "sequence": 10, "priority": 10},
    {"material": "GALVA", "rate_per_kg": 24.0 * 0.2025, "rate_percent": 20.25, "sequence": 20, "priority": 10},
    {"material": "INOX", "rate_per_kg": 40.0 * 0.2025, "rate_percent": 20.25, "sequence": 30, "priority": 10},
    {"material": "COPPER", "rate_per_kg": 60.0 * 0.2025, "rate_percent": 20.25, "sequence": 40, "priority": 10},
    {"material": "ALUM", "rate_per_kg": 0.0, "rate_percent": 20.25, "sequence": 50, "priority": 20},
    {"material": "OTHER", "rate_per_kg": 0.0, "rate_percent": 20.25, "sequence": 60, "priority": 30},
]


def _get_or_create_by_title(doctype: str, title_field: str, title_value: str):
    name = frappe.db.get_value(doctype, {title_field: title_value}, "name")
    if name:
        return frappe.get_doc(doctype, name)
    doc = frappe.new_doc(doctype)
    setattr(doc, title_field, title_value)
    return doc


def _upsert_customs_policy() -> str:
    doc = _get_or_create_by_title("Pricing Customs Policy", "policy_name", CUSTOMS_POLICY_NAME)
    doc.company = doc.company or ""
    doc.is_active = 1
    doc.is_default = 1
    doc.notes = (
        "Derived from workbook customs column. Applies 20.25% with material-specific per-kg floors. "
        "ALUM/OTHER currently fall back to percent-only until business confirms a per-kg factor."
    )
    doc.set("customs_rules", [])
    for row in CUSTOMS_RULES:
        doc.append(
            "customs_rules",
            {
                **row,
                "is_active": 1,
                "notes": "Workbook material rule",
            },
        )
    doc.save(ignore_permissions=True)
    return doc.name


def _upsert_benchmark_policy(policy_name: str, selling_price_list: str) -> str:
    doc = _get_or_create_by_title("Pricing Benchmark Policy", "policy_name", policy_name)
    doc.company = doc.company or ""
    doc.is_active = 1
    doc.is_default = 0
    doc.method = "Median"
    doc.min_sources_required = 1
    doc.fallback_margin_percent = 0
    doc.notes = (
        "Passive benchmark reference for workbook parity. Scenario expenses carry workbook margin; "
        "benchmark policy is set to 0% so it does not alter price output."
    )
    doc.set("benchmark_sources", [])
    doc.append(
        "benchmark_sources",
        {
            "price_list": selling_price_list,
            "label": selling_price_list,
            "source_kind": "Internal",
            "weight": 1,
            "is_active": 1,
        },
    )
    doc.set("benchmark_rules", [])
    doc.append(
        "benchmark_rules",
        {
            "ratio_min": 0,
            "ratio_max": 0,
            "target_margin_percent": 0,
            "priority": 10,
            "sequence": 10,
            "is_active": 1,
            "notes": "Workbook parity: margin handled in scenario expenses.",
        },
    )
    doc.set("tier_modifiers", [])
    doc.set("zone_modifiers", [])
    doc.save(ignore_permissions=True)
    return doc.name


def _upsert_scenario(defn: dict[str, str]) -> str:
    doc = _get_or_create_by_title("Pricing Scenario", "scenario_name", defn["scenario_name"])
    doc.description = defn["description"]
    doc.benchmark_price_list = ""
    doc.transport_is_active = 1
    doc.transport_container_type = TRANSPORT_CONTAINER_TYPE
    doc.transport_allocation_mode = "By Value"
    doc.transport_container_price = TRANSPORT_CONTAINER_PRICE
    doc.transport_total_merch_value = TRANSPORT_TOTAL_MERCH_VALUE
    doc.transport_total_weight_kg = 0
    doc.transport_total_volume_m3 = 0
    doc.set("expenses", [])
    doc.append(
        "expenses",
        {
            "sequence": 20,
            "label": "Charge equipe/bureau allocation",
            "type": "Percentage",
            "value": flt(defn["overhead_percent"]),
            "applies_to": "Base Price",
            "scope": "Per Unit",
            "is_active": 1,
            "notes": "Workbook linear share of monthly team/office charges. Nonlinear commission term is not represented.",
        },
    )
    doc.append(
        "expenses",
        {
            "sequence": 30,
            "label": "Impots workbook",
            "type": "Percentage",
            "value": IMPUTS_PERCENT,
            "applies_to": "Base Price",
            "scope": "Per Unit",
            "is_active": 1,
            "notes": "Workbook K column = 7% of base.",
        },
    )
    doc.append(
        "expenses",
        {
            "sequence": 90,
            "label": "Workbook margin",
            "type": "Percentage",
            "value": flt(defn["margin_percent"]),
            "applies_to": "Base Price",
            "scope": "Per Unit",
            "is_active": 1,
            "notes": "Workbook-derived margin component for this output mode.",
        },
    )
    doc.save(ignore_permissions=True)
    return doc.name


def _ensure_converted_buying_price_list() -> str:
    existing_name = frappe.db.exists("Price List", CONVERTED_BUYING_PRICE_LIST)
    if existing_name:
        doc = frappe.get_doc("Price List", existing_name)
    else:
        doc = frappe.new_doc("Price List")
        doc.price_list_name = CONVERTED_BUYING_PRICE_LIST

    doc.currency = "MAD"
    doc.buying = 1
    doc.selling = 0
    doc.enabled = 1
    doc.save(ignore_permissions=True)

    source_rows = frappe.get_all(
        "Item Price",
        filters={"price_list": SOURCE_BUYING_PRICE_LIST, "buying": 1},
        fields=["item_code", "price_list_rate", "uom"],
        limit_page_length=2000,
    )
    for row in source_rows:
        filters = {
            "item_code": row["item_code"],
            "price_list": CONVERTED_BUYING_PRICE_LIST,
            "uom": row.get("uom") or frappe.db.get_value("Item", row["item_code"], "stock_uom"),
        }
        rate = flt(row["price_list_rate"]) * USD_TO_MAD_RATE
        name = frappe.db.exists("Item Price", filters)
        if name:
            item_price = frappe.get_doc("Item Price", name)
            item_price.currency = "MAD"
            item_price.price_list_rate = rate
            item_price.buying = 1
            item_price.selling = 0
            item_price.save(ignore_permissions=True)
        else:
            frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": row["item_code"],
                    "price_list": CONVERTED_BUYING_PRICE_LIST,
                    "currency": "MAD",
                    "price_list_rate": rate,
                    "buying": 1,
                    "selling": 0,
                    "uom": filters["uom"],
                }
            ).insert(ignore_permissions=True)

    return doc.name


def _scenario_doc(name: str):
    names = frappe.get_all("Pricing Scenario", filters={"scenario_name": name}, pluck="name", limit_page_length=1)
    if not names:
        frappe.throw(f"Pricing Scenario not found for scenario_name={name}")
    return frappe.get_doc("Pricing Scenario", names[0])


def _customs_doc(name: str):
    names = frappe.get_all("Pricing Customs Policy", filters={"policy_name": name}, pluck="name", limit_page_length=1)
    if not names:
        frappe.throw(f"Pricing Customs Policy not found for policy_name={name}")
    return frappe.get_doc("Pricing Customs Policy", names[0])


def _benchmark_doc(name: str):
    names = frappe.get_all("Pricing Benchmark Policy", filters={"policy_name": name}, pluck="name", limit_page_length=1)
    if not names:
        frappe.throw(f"Pricing Benchmark Policy not found for policy_name={name}")
    return frappe.get_doc("Pricing Benchmark Policy", names[0])


def _compute_projected_unit(item_code: str, scenario_doc, customs_doc) -> float:
    from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import PricingSheet

    sheet = frappe.new_doc("Pricing Sheet")
    row = frappe._dict(item=item_code, qty=1)
    item_details = get_item_details_map([item_code])
    buy_price = flt(get_latest_item_prices([item_code], CONVERTED_BUYING_PRICE_LIST, buying=True).get(item_code) or 0)
    base_amount = buy_price
    customs_calc = sheet._compute_customs_for_row(row, base_amount, item_details, customs_doc)
    expenses = sheet._active_expenses(scenario_doc)
    transport_calc = sheet._compute_transport_for_row(
        row=row,
        qty=1,
        base_amount=base_amount,
        item_details=item_details,
        transport_config=sheet._extract_transport_config(scenario_doc),
    )
    expenses = sheet._inject_transport_expense(expenses, transport_calc)
    pricing = apply_expenses(base_unit=buy_price, qty=1, expenses=expenses)
    return flt(pricing.get("projected_line") or 0) + flt(customs_calc.get("applied") or 0)


@frappe.whitelist()
def run() -> dict:
    customs_name = _upsert_customs_policy()
    converted_buying_list = _ensure_converted_buying_price_list()
    scenario_names = []
    benchmark_names = []
    for definition in SCENARIOS:
        benchmark_names.append(_upsert_benchmark_policy(definition["benchmark_policy"], definition["selling_price_list"]))
        scenario_names.append(_upsert_scenario(definition))
    frappe.db.commit()
    return {
        "customs_policy": customs_name,
        "converted_buying_price_list": converted_buying_list,
        "scenarios": scenario_names,
        "benchmark_policies": benchmark_names,
    }


@frappe.whitelist()
def verify() -> dict:
    customs_doc = _customs_doc(CUSTOMS_POLICY_NAME)
    sample_items = ["IT.1", "IT.1-11", "IT.33", "IT.47", "IT.64"]
    out = []

    for definition in SCENARIOS:
        scenario_doc = _scenario_doc(definition["scenario_name"])
        target_prices = get_latest_item_prices(sample_items, definition["selling_price_list"], buying=False)
        comparisons = []
        deltas = []
        for item_code in sample_items:
            projected = _compute_projected_unit(item_code, scenario_doc, customs_doc)
            target = flt(target_prices.get(item_code) or 0)
            delta = projected - target
            deltas.append(abs(delta))
            comparisons.append(
                {
                    "item_code": item_code,
                    "projected": round(projected, 6),
                    "target_price_list": definition["selling_price_list"],
                    "target": round(target, 6),
                    "delta": round(delta, 6),
                }
            )
        out.append(
            {
                "scenario": definition["scenario_name"],
                "selling_price_list": definition["selling_price_list"],
                "avg_abs_delta": round(mean(deltas), 6) if deltas else 0,
                "max_abs_delta": round(max(deltas), 6) if deltas else 0,
                "comparisons": comparisons,
            }
        )

    return {
        "customs_policy": CUSTOMS_POLICY_NAME,
        "converted_buying_price_list": CONVERTED_BUYING_PRICE_LIST,
        "usd_to_mad_rate": USD_TO_MAD_RATE,
        "transport_container_price": round(TRANSPORT_CONTAINER_PRICE, 6),
        "workbook_transport_total": round(WORKBOOK_TRANSPORT_TOTAL, 6),
        "monthly_overhead_percent": round(MONTHLY_OVERHEAD_PERCENT, 6),
        "scenarios": out,
        "note": "Data-only parity. Remaining deltas come mainly from the workbook's nonlinear charge-equipe commission term and from items whose source material is blank/ambiguous.",
    }
