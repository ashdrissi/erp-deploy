# Copyright (c) 2026, Orderlift and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


DYNAMIC_MODE = "Dynamic Calculation Engine"


class AgentPricingRules(Document):
    def validate(self):
        if self.pricing_mode != DYNAMIC_MODE:
            return

        self._normalize_dynamic_rows()
        rows = _active_dynamic_rows(self)
        if not rows:
            frappe.throw(_("Add at least one active Dynamic Configuration row for Dynamic mode."))

        self._validate_dynamic_rows(rows)

    def _normalize_dynamic_rows(self):
        for row in self.dynamic_pricing_configs or []:
            row.priority = cint(row.priority or 10)

    def _validate_dynamic_rows(self, rows):
        defaults = 0
        seen = set()

        for row in rows:
            defaults += cint(row.get("is_default"))

            key = (
                (row.get("buying_price_list") or "").strip().lower(),
                (row.get("pricing_scenario") or "").strip().lower(),
                (row.get("customs_policy") or "").strip().lower(),
                (row.get("benchmark_policy") or "").strip().lower(),
            )
            if key in seen:
                frappe.throw(_("Duplicate Dynamic Configuration rows are not allowed."))
            seen.add(key)

            pricing_scenario = row.get("pricing_scenario")
            buying_price_list = row.get("buying_price_list")
            if pricing_scenario and buying_price_list:
                scenario_buying = frappe.db.get_value("Pricing Scenario", pricing_scenario, "buying_price_list")
                if scenario_buying and scenario_buying != buying_price_list:
                    frappe.throw(
                        _("Dynamic config links scenario {0} to buying list {1}, but the scenario uses {2}.").format(
                            pricing_scenario,
                            buying_price_list,
                            scenario_buying,
                        )
                    )

        if defaults > 1:
            frappe.throw(_("Only one Dynamic Configuration row can be marked as Default."))


def build_dynamic_context(sales_person=None, agent_doc=None):
    if agent_doc is None:
        if not sales_person:
            return {"pricing_mode": "", "selected": {}, "rows": []}

        name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name")
        if not name:
            return {"pricing_mode": "", "selected": {}, "rows": []}

        agent_doc = frappe.get_doc("Agent Pricing Rules", name)

    rows = _active_dynamic_rows(agent_doc)
    rows = sorted(rows, key=_dynamic_sort_key)
    selected = rows[0] if rows else {}

    return {
        "pricing_mode": agent_doc.pricing_mode or "",
        "selected": selected,
        "rows": rows,
        "allowed_buying_price_lists": sorted({str(r.get("buying_price_list") or "") for r in rows if r.get("buying_price_list")}),
        "allowed_pricing_scenarios": sorted({str(r.get("pricing_scenario") or "") for r in rows if r.get("pricing_scenario")}),
        "allowed_customs_policies": sorted({str(r.get("customs_policy") or "") for r in rows if r.get("customs_policy")}),
        "allowed_benchmark_policies": sorted({str(r.get("benchmark_policy") or "") for r in rows if r.get("benchmark_policy")}),
    }


def _active_dynamic_rows(agent_doc):
    rows = []
    for row in agent_doc.get("dynamic_pricing_configs") or []:
        if not cint(row.get("is_active", 1)):
            continue
        rows.append(
            {
                "buying_price_list": row.get("buying_price_list") or "",
                "pricing_scenario": row.get("pricing_scenario") or "",
                "customs_policy": row.get("customs_policy") or "",
                "benchmark_policy": row.get("benchmark_policy") or "",
                "priority": cint(row.get("priority") or 10),
                "is_default": cint(row.get("is_default") or 0),
                "is_active": cint(row.get("is_active") or 1),
                "idx": cint(row.get("idx") or 0),
            }
        )

    if rows:
        return rows

    if agent_doc.pricing_mode == DYNAMIC_MODE and agent_doc.default_buying_price_list:
        benchmark_policy = agent_doc.get("default_benchmark_policy") or agent_doc.get("default_margin_policy") or ""
        return [
            {
                "buying_price_list": agent_doc.default_buying_price_list or "",
                "pricing_scenario": agent_doc.default_expense_policy or "",
                "customs_policy": agent_doc.default_customs_policy or "",
                "benchmark_policy": benchmark_policy,
                "priority": 10,
                "is_default": 1,
                "is_active": 1,
                "idx": 0,
            }
        ]

    return []


def _dynamic_sort_key(row):
    return (
        0 if cint(row.get("is_default")) else 1,
        cint(row.get("priority") or 10),
        cint(row.get("idx") or 0),
    )
