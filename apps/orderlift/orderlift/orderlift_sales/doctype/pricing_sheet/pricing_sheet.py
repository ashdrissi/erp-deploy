import json
from time import perf_counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime, nowdate

from orderlift.sales.utils.customs_policy import compute_customs_amount, resolve_customs_rule
from orderlift.sales.utils.margin_policy import resolve_margin_rule
from orderlift.sales.utils.pricing_projection import apply_expenses


MISSING_BUY_PRICE_MSG = "No buying price in {price_list}"


class PricingSheet(Document):
    def before_save(self):
        self.recalculate()

    def recalculate(self):
        started = perf_counter()
        lines = self.lines or []
        self.projection_warnings = ""

        if not lines:
            self._reset_totals()
            self.applied_margin_policy = ""
            self.applied_margin_rule = ""
            self.applied_customs_policy = ""
            self.calculated_on = now_datetime()
            self.calculated_by = frappe.session.user
            self.calc_runtime_ms = (perf_counter() - started) * 1000
            return

        scenario_docs = self._collect_scenarios_or_throw(lines)
        self._sync_override_rows_for_scenarios(scenario_docs)

        margin_policy, margin_rule = self._resolve_margin_policy_and_rule()
        self.applied_margin_policy = margin_policy.name if margin_policy else ""
        self.applied_margin_rule = self._format_margin_rule(margin_rule) if margin_rule else ""
        customs_policy = self._resolve_customs_policy()
        self.applied_customs_policy = customs_policy.name if customs_policy else ""

        warnings = []
        if not margin_rule:
            warnings.append(
                _("No active margin rule matched customer type {0}, tier {1}.").format(
                    self.customer_type or "-",
                    self.tier or "-",
                )
            )
        if not customs_policy:
            warnings.append(_("No active customs policy found; customs costs default to zero."))
        item_codes = sorted({row.item for row in lines if row.item})
        item_details = get_item_details_map(item_codes)
        item_groups = {code: (item_details.get(code) or {}).get("item_group") for code in item_codes}

        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes, margin_rule=margin_rule)
        self._sync_line_override_rows_for_lines(lines, scenario_caches)

        total_base = 0.0
        total_expenses = 0.0
        total_final = 0.0
        line_snapshots = []

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            self._hydrate_line_from_item(row, item_groups)
            scenario_name, source = self._resolve_line_scenario(row)
            row.resolved_pricing_scenario = scenario_name
            row.scenario_source = source

            cache = scenario_caches.get(scenario_name)
            if not cache:
                frappe.throw(_("Unable to resolve pricing cache for scenario {0}").format(scenario_name))

            effective_line_expenses, has_line_override = self._apply_line_override_rows(
                row,
                scenario_name,
                cache["line_expenses"],
            )

            self._set_buy_price_from_map(row, cache["buying_price_list"], cache["buy_prices"])

            base_unit = flt(row.buy_price)
            base_amount = qty * base_unit
            row.base_amount = base_amount

            customs_calc = self._compute_customs_for_row(row, base_amount, item_details, customs_policy)
            if customs_calc.get("warning"):
                warnings.append(_("Row {0}: {1}").format(row.idx, customs_calc.get("warning")))

            pricing = apply_expenses(base_unit=base_unit, qty=qty, expenses=effective_line_expenses)
            line_snapshots.append(
                {
                    "row": row,
                    "scenario_name": scenario_name,
                    "qty": qty,
                    "base_unit": base_unit,
                    "base_amount": base_amount,
                    "pricing": pricing,
                    "sheet_fixed_total": cache["sheet_fixed_total"],
                    "benchmark_price_list": cache["benchmark_price_list"],
                    "benchmark_prices": cache["benchmark_prices"],
                    "has_line_override": has_line_override,
                    "customs_calc": customs_calc,
                }
            )
            total_base += base_amount

        scenario_allocation = {}
        for snap in line_snapshots:
            key = snap["scenario_name"]
            bucket = scenario_allocation.setdefault(
                key,
                {
                    "base": 0.0,
                    "qty": 0.0,
                    "sheet_fixed_total": flt(snap["sheet_fixed_total"]),
                },
            )
            bucket["base"] += flt(snap["base_amount"])
            bucket["qty"] += flt(snap["qty"])

        min_margin = flt(self.minimum_margin_percent)
        floor_violations = 0
        margin_violations = 0
        customs_total_applied = 0.0

        for snap in line_snapshots:
            row = snap["row"]
            qty = snap["qty"]
            base_unit = snap["base_unit"]
            base_amount = snap["base_amount"]
            pricing = snap["pricing"]
            customs_calc = snap.get("customs_calc") or {}
            sheet_fixed_total = snap["sheet_fixed_total"]
            scenario_name = snap["scenario_name"]
            alloc = scenario_allocation.get(scenario_name) or {
                "base": base_amount,
                "qty": qty,
                "sheet_fixed_total": sheet_fixed_total,
            }
            denom = flt(alloc["base"]) if flt(alloc["base"]) > 0 else flt(alloc["qty"])
            denom = denom or 1
            share_basis = base_amount if flt(alloc["base"]) > 0 else qty
            allocated_sheet = (share_basis / denom) * flt(alloc["sheet_fixed_total"])
            projected_total = flt(pricing["projected_line"]) + flt(allocated_sheet)
            projected_total += flt(customs_calc.get("applied") or 0)
            projected_unit = projected_total / qty if qty else 0
            expense_total = projected_total - base_amount

            steps = list(pricing["steps"])
            if allocated_sheet:
                steps.append(
                    {
                        "label": "Sheet Allocation",
                        "type": "Fixed",
                        "value": allocated_sheet,
                        "applies_to": "Running Total",
                        "scope": "Per Sheet",
                        "sequence": 9999,
                        "basis": projected_total,
                        "delta_unit": allocated_sheet / qty if qty else 0,
                        "delta_line": 0,
                        "delta_sheet": allocated_sheet,
                        "running_total": projected_unit,
                    }
                )

            self._append_customs_step(steps, qty, projected_unit, customs_calc)

            row.expense_total = expense_total
            row.projected_unit_price = projected_unit
            row.projected_total_price = projected_total
            row.pricing_breakdown_json = json.dumps(steps)
            row.breakdown_preview = self._build_breakdown_preview(steps)
            row.has_scenario_override = 1 if cache_has_override_steps(steps, source="sheet") else 0
            row.has_line_override = 1 if snap.get("has_line_override") or cache_has_override_steps(steps, source="line") else 0

            row.is_manual_override = 1 if flt(row.manual_sell_unit_price) > 0 else 0
            row.final_sell_unit_price = flt(row.manual_sell_unit_price) if row.is_manual_override else projected_unit
            row.final_sell_total = flt(row.final_sell_unit_price) * qty
            row.margin_pct = ((flt(row.final_sell_unit_price) - base_unit) / base_unit * 100) if base_unit > 0 else 0
            row.customs_material = customs_calc.get("material") or ""
            row.customs_weight_kg = flt(customs_calc.get("weight_kg") or 0)
            row.customs_rate_per_kg = flt(customs_calc.get("rate_per_kg") or 0)
            row.customs_rate_percent = flt(customs_calc.get("rate_percent") or 0)
            row.customs_by_kg = flt(customs_calc.get("by_kg") or 0)
            row.customs_by_percent = flt(customs_calc.get("by_percent") or 0)
            row.customs_applied = flt(customs_calc.get("applied") or 0)
            row.customs_basis = customs_calc.get("basis") or ""

            row.price_floor_violation = 1 if flt(row.final_sell_unit_price) < 0 else 0
            if row.price_floor_violation:
                floor_violations += 1
                warnings.append(_("Row {0}: final unit price is below zero.").format(row.idx))

            if min_margin and flt(row.margin_pct) < min_margin:
                margin_violations += 1
                warnings.append(
                    _("Row {0}: margin {1}% is below minimum {2}%.").format(
                        row.idx,
                        f"{flt(row.margin_pct):.2f}",
                        f"{min_margin:.2f}",
                    )
                )

            self._set_benchmark_status(
                row,
                snap["benchmark_price_list"],
                snap["benchmark_prices"],
                flt(row.final_sell_unit_price),
            )

            total_expenses += flt(row.expense_total)
            total_final += flt(row.final_sell_total)
            customs_total_applied += flt(row.customs_applied)

        self.total_buy = flt(total_base)
        self.total_expenses = flt(total_expenses)
        self.total_selling = flt(total_final)
        self.customs_total_applied = flt(customs_total_applied)
        self.projection_warnings = "\n".join(warnings[:25])
        self.calculated_on = now_datetime()
        self.calculated_by = frappe.session.user
        self.calc_runtime_ms = (perf_counter() - started) * 1000

        logger = frappe.logger("pricing")
        logger.info(
            "PricingSheet %s recalculated in %.2fms (lines=%s, floor_violations=%s, margin_violations=%s)",
            self.name or "NEW",
            flt(self.calc_runtime_ms),
            len(lines),
            floor_violations,
            margin_violations,
        )

        if cint(self.strict_margin_guard) and warnings:
            frappe.throw(_("Strict guard blocked save:\n{0}").format("\n".join(warnings[:10])))

    @frappe.whitelist()
    def load_scenario_overrides(self):
        lines = self.lines or []
        scenario_docs = self._collect_scenarios_or_throw(lines)
        self._sync_override_rows_for_scenarios(scenario_docs)
        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def load_line_overrides(self, line_name=None):
        lines = self.lines or []
        scenario_docs = self._collect_scenarios_or_throw(lines)
        self._sync_override_rows_for_scenarios(scenario_docs)
        _, margin_rule = self._resolve_margin_policy_and_rule()
        item_codes = sorted({row.item for row in lines if row.item})
        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes, margin_rule=margin_rule)
        self._sync_line_override_rows_for_lines(lines, scenario_caches, line_name=line_name)
        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def reset_scenario_overrides(self, scenario=None):
        if scenario:
            rows = [row for row in (self.scenario_overrides or []) if row.scenario == scenario]
        else:
            rows = list(self.scenario_overrides or [])

        for row in rows:
            row.override_value = flt(row.base_value)
            row.is_overridden = 0

        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def reset_line_overrides(self, line_name=None, expense_key=None):
        rows = list(self.line_overrides or [])
        for row in rows:
            if line_name and row.line_name != line_name:
                continue
            if expense_key and row.expense_key != expense_key:
                continue
            row.line_override_value = flt(row.sheet_override_value)
            row.is_overridden = 0

        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def prune_stale_scenario_overrides(self):
        kept = []
        for row in (self.scenario_overrides or []):
            if not row.expense_key:
                continue
            if cint(row.is_active) == 0 and (row.expense_label or "").startswith("[STALE]"):
                continue
            kept.append(row)

        self.set("scenario_overrides", [])
        for row in kept:
            self.append("scenario_overrides", row.as_dict())

        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def prune_stale_line_overrides(self):
        kept = []
        for row in (self.line_overrides or []):
            if not row.expense_key or not row.line_name:
                continue
            if cint(row.is_active) == 0 and (row.expense_label or "").startswith("[STALE]"):
                continue
            kept.append(row)

        self.set("line_overrides", [])
        for row in kept:
            self.append("line_overrides", row.as_dict())

        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def queue_recalculate(self):
        self.check_permission("write")
        job = frappe.enqueue(
            method="orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.recalculate_pricing_sheet_job",
            queue="short",
            timeout=600,
            pricing_sheet_name=self.name,
            user=frappe.session.user,
        )
        return {"job_id": getattr(job, "id", None)}

    @frappe.whitelist()
    def get_quotation_preview(self):
        lines = self.lines or []
        detailed_count = len([row for row in lines if cint(row.show_in_detail)])
        grouped_count = len(self._build_grouped_totals())
        return {
            "line_count": len(lines),
            "detailed_count": detailed_count,
            "grouped_count": grouped_count,
            "total_buy": flt(self.total_buy),
            "total_final": flt(self.total_selling),
            "customs_total": flt(self.customs_total_applied),
            "warnings": self.projection_warnings or "",
        }

    @frappe.whitelist()
    def refresh_buy_prices(self):
        lines = self.lines or []
        scenario_docs = self._collect_scenarios_or_throw(lines)
        _, margin_rule = self._resolve_margin_policy_and_rule()
        item_codes = sorted({row.item for row in lines if row.item})
        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes, margin_rule=margin_rule)

        for row in lines:
            scenario_name, source = self._resolve_line_scenario(row)
            row.resolved_pricing_scenario = scenario_name
            row.scenario_source = source
            cache = scenario_caches.get(scenario_name)
            if not cache:
                continue
            self._set_buy_price_from_map(row, cache["buying_price_list"], cache["buy_prices"], force_refresh=True)

        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def add_from_bundle(
        self,
        product_bundle=None,
        multiplier=1,
        replace_existing_lines=0,
        default_show_in_detail=1,
        default_display_group_source="Item Group",
        line_mode="Exploded",
        include_summary_in_detail=1,
        include_components_in_detail=1,
    ):
        self._get_default_scenario_or_throw()
        bundle_name = product_bundle or self.product_bundle
        if not bundle_name:
            frappe.throw(_("Please select a Product Bundle."))

        if cint(replace_existing_lines):
            self.set("lines", [])

        rows = self._get_template_rows(bundle_name)
        if not rows:
            frappe.throw(_("No template rows found in Product Bundle/BOM {0}.").format(bundle_name))

        qty_multiplier = flt(multiplier) or 1
        group_by_item_group = (default_display_group_source or "Item Group").strip() == "Item Group"
        show_detail = 1 if cint(default_show_in_detail) else 0
        mode = (line_mode or "Exploded").strip().title()
        if mode not in ("Exploded", "Bundle Single", "Both"):
            mode = "Exploded"
        summary_show_detail = 1 if cint(include_summary_in_detail) else 0
        component_show_detail = 1 if cint(include_components_in_detail) else 0

        item_codes = []
        for row in rows:
            code = row.get("item_code")
            if code:
                item_codes.append(str(code))
        item_codes.sort()
        item_groups = get_item_groups_map(item_codes)

        bundle_group_id = frappe.generate_hash(length=10)
        default_line_scenario = self._scenario_from_bundle_rule(bundle_name) or self.pricing_scenario

        if mode in ("Bundle Single", "Both"):
            bundle_item_code = self._get_bundle_parent_item(bundle_name)
            self.append(
                "lines",
                {
                    "item": bundle_item_code,
                    "qty": qty_multiplier,
                    "display_group": bundle_name,
                    "show_in_detail": summary_show_detail if mode == "Both" else show_detail,
                    "source_bundle": bundle_name,
                    "pricing_scenario": default_line_scenario,
                    "line_type": "Bundle Summary",
                    "bundle_group_id": bundle_group_id,
                },
            )

        if mode in ("Exploded", "Both"):
            for tpl in rows:
                item_code = tpl.get("item_code")
                if not item_code:
                    continue

                line_qty = flt(tpl.get("qty")) * qty_multiplier
                if line_qty <= 0:
                    continue

                display_group = bundle_name
                if group_by_item_group:
                    display_group = item_groups.get(item_code) or bundle_name

                self.append(
                    "lines",
                    {
                        "item": item_code,
                        "qty": line_qty,
                        "display_group": display_group,
                        "show_in_detail": component_show_detail if mode == "Both" else show_detail,
                        "source_bundle": bundle_name,
                        "pricing_scenario": default_line_scenario,
                        "line_type": "Bundle Component" if mode == "Both" else "Standard",
                        "bundle_group_id": bundle_group_id if mode == "Both" else "",
                    },
                )

        self.product_bundle = bundle_name
        self.refresh_buy_prices()
        return self.name

    def _collect_scenarios_or_throw(self, lines):
        scenario_names = set()
        default_scenario = (self.pricing_scenario or "").strip()
        if default_scenario:
            scenario_names.add(default_scenario)

        for row in lines:
            if row.pricing_scenario:
                scenario_names.add(row.pricing_scenario)

        for rule in (self.bundle_scenario_rules or []):
            if cint(rule.is_active) and rule.pricing_scenario:
                scenario_names.add(rule.pricing_scenario)

        if not scenario_names:
            frappe.throw(_("Please select at least one Pricing Scenario."))

        docs = {}
        missing = []
        for name in scenario_names:
            if not frappe.db.exists("Pricing Scenario", name):
                missing.append(name)
                continue
            docs[name] = frappe.get_doc("Pricing Scenario", name)

        if missing:
            frappe.throw(_("Missing Pricing Scenario(s): {0}").format(", ".join(sorted(missing))))

        return docs

    def _resolve_margin_policy_and_rule(self):
        policy_doc = None
        if self.margin_policy and frappe.db.exists("Pricing Margin Policy", self.margin_policy):
            policy_doc = frappe.get_doc("Pricing Margin Policy", self.margin_policy)
        else:
            default_name = frappe.db.get_value(
                "Pricing Margin Policy",
                {"is_default": 1, "is_active": 1},
                "name",
            )
            if default_name:
                policy_doc = frappe.get_doc("Pricing Margin Policy", default_name)
                self.margin_policy = default_name

        if not policy_doc:
            return None, None

        rule_dicts = [
            {
                "customer_type": row.customer_type,
                "tier": row.tier,
                "margin_percent": flt(row.margin_percent),
                "applies_to": row.applies_to,
                "sequence": cint(row.sequence),
                "priority": cint(row.priority),
                "is_active": cint(row.is_active),
                "idx": cint(row.idx),
            }
            for row in (policy_doc.margin_rules or [])
        ]
        rule = resolve_margin_rule(rule_dicts, customer_type=self.customer_type, tier=self.tier)
        return policy_doc, rule

    def _resolve_customs_policy(self):
        if not frappe.db.exists("DocType", "Pricing Customs Policy"):
            return None

        policy_doc = None
        if self.customs_policy and frappe.db.exists("Pricing Customs Policy", self.customs_policy):
            policy_doc = frappe.get_doc("Pricing Customs Policy", self.customs_policy)
        else:
            default_name = frappe.db.get_value(
                "Pricing Customs Policy",
                {"is_default": 1, "is_active": 1},
                "name",
            )
            if default_name:
                policy_doc = frappe.get_doc("Pricing Customs Policy", default_name)
                self.customs_policy = default_name

        if not policy_doc or cint(policy_doc.is_active) != 1:
            return None
        return policy_doc

    def _compute_customs_for_row(self, row, base_amount, item_details, customs_policy):
        details = item_details.get(row.item) or {}
        material = (details.get("custom_material") or "").strip().upper()
        unit_weight_kg = flt(details.get("custom_weight_kg"))
        qty = flt(row.qty)

        out = {
            "material": material,
            "weight_kg": unit_weight_kg,
            "rate_per_kg": 0.0,
            "rate_percent": 0.0,
            "by_kg": 0.0,
            "by_percent": 0.0,
            "applied": 0.0,
            "basis": "",
            "warning": "",
        }

        if not customs_policy:
            return out

        if not material:
            out["warning"] = _("item material is missing; customs set to 0")
            return out

        rule_dicts = [
            {
                "material": rule.material,
                "rate_per_kg": flt(rule.rate_per_kg),
                "rate_percent": flt(rule.rate_percent),
                "sequence": cint(rule.sequence),
                "priority": cint(rule.priority),
                "is_active": cint(rule.is_active),
                "idx": cint(rule.idx),
            }
            for rule in (customs_policy.customs_rules or [])
        ]
        rule = resolve_customs_rule(rule_dicts, material=material)
        if not rule:
            out["warning"] = _("no customs rule matched material {0}; customs set to 0").format(material)
            return out

        rate_per_kg = flt(rule.get("rate_per_kg"))
        rate_percent = flt(rule.get("rate_percent"))
        amounts = compute_customs_amount(
            base_amount=base_amount,
            qty=qty,
            unit_weight_kg=unit_weight_kg,
            rate_per_kg=rate_per_kg,
            rate_percent=rate_percent,
        )

        out.update(
            {
                "rate_per_kg": rate_per_kg,
                "rate_percent": rate_percent,
                "by_kg": flt(amounts.get("by_kg") or 0),
                "by_percent": flt(amounts.get("by_percent") or 0),
                "applied": flt(amounts.get("applied") or 0),
                "basis": amounts.get("basis") or "",
            }
        )
        return out

    def _append_customs_step(self, steps, qty, projected_unit, customs_calc):
        applied = flt((customs_calc or {}).get("applied") or 0)
        if applied <= 0:
            return

        steps.append(
            {
                "label": "Customs (MAX kg vs %)",
                "type": "Fixed",
                "value": applied,
                "applies_to": "Base Price",
                "scope": "Per Line",
                "sequence": 9998,
                "basis": 0,
                "delta_unit": applied / qty if qty else 0,
                "delta_line": applied,
                "delta_sheet": 0,
                "running_total": projected_unit,
                "customs_by_kg": flt(customs_calc.get("by_kg") or 0),
                "customs_by_percent": flt(customs_calc.get("by_percent") or 0),
                "customs_basis": customs_calc.get("basis") or "",
            }
        )

    def _inject_margin_expense(self, expenses, margin_rule):
        if not margin_rule:
            return expenses

        dynamic_margin = {
            "label": "Dynamic Margin",
            "type": "Percentage",
            "value": flt(margin_rule.get("margin_percent")),
            "applies_to": (margin_rule.get("applies_to") or "Running Total"),
            "scope": "Per Unit",
            "sequence": cint(margin_rule.get("sequence") or 90),
            "is_active": 1,
            "is_overridden": 0,
            "override_source": "margin_policy",
        }

        out = list(expenses or [])
        out.append(dynamic_margin)
        out = sorted(out, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx") or 0)))
        for exp in out:
            exp["expense_key"] = exp.get("expense_key") or make_expense_key(exp)
        return out

    def _format_margin_rule(self, rule):
        if not rule:
            return ""
        return _("{0}/{1}: {2}% on {3}").format(
            rule.get("customer_type") or "Any",
            rule.get("tier") or "Any",
            flt(rule.get("margin_percent")),
            rule.get("applies_to") or "Running Total",
        )

    def _build_scenario_caches(self, scenario_docs, item_codes, margin_rule=None):
        caches = {}
        for name, scenario in scenario_docs.items():
            buying_price_list = scenario.buying_price_list or "Buying"
            benchmark_price_list = scenario.benchmark_price_list or "Benchmark Selling"

            base_expenses = self._active_expenses(scenario)
            effective_expenses = self._apply_override_rows(name, base_expenses)
            effective_expenses = self._inject_margin_expense(effective_expenses, margin_rule)
            sheet_fixed_total = self._sheet_fixed_total(effective_expenses)
            line_expenses = [
                exp
                for exp in effective_expenses
                if not (
                    (exp.get("type") or "").title() == "Fixed"
                    and (exp.get("scope") or "").title() == "Per Sheet"
                )
            ]

            caches[name] = {
                "buying_price_list": buying_price_list,
                "benchmark_price_list": benchmark_price_list,
                "buy_prices": get_latest_item_prices(item_codes, buying_price_list, buying=True),
                "benchmark_prices": get_latest_item_prices(item_codes, benchmark_price_list, buying=False),
                "line_expenses": line_expenses,
                "sheet_fixed_total": sheet_fixed_total,
            }

        return caches

    def _sync_override_rows_for_scenarios(self, scenario_docs):
        existing = {}
        valid_keys = set()
        for row in (self.scenario_overrides or []):
            key = (row.scenario, row.expense_key)
            existing[key] = row

        for scenario_name, scenario in scenario_docs.items():
            for expense in self._active_expenses(scenario):
                expense_key = make_expense_key(expense)
                key = (scenario_name, expense_key)
                valid_keys.add(key)
                row = existing.get(key)

                if not row:
                    row = self.append(
                        "scenario_overrides",
                        {
                            "scenario": scenario_name,
                            "expense_key": expense_key,
                        },
                    )

                row.expense_label = expense.get("label")
                row.sequence = cint(expense.get("sequence"))
                row.type = expense.get("type")
                row.applies_to = expense.get("applies_to")
                row.scope = expense.get("scope")
                row.is_active = cint(expense.get("is_active"))
                row.base_value = flt(expense.get("value"))
                if row.override_value is None:
                    row.override_value = flt(row.base_value)
                row.is_overridden = 1 if flt(row.override_value) != flt(row.base_value) else 0

        for key, row in existing.items():
            if key in valid_keys:
                continue
            row.is_active = 0
            row.is_overridden = 0
            if row.expense_label and not row.expense_label.startswith("[STALE]"):
                row.expense_label = f"[STALE] {row.expense_label}"

    def _apply_override_rows(self, scenario_name, base_expenses):
        override_rows = {}
        for row in (self.scenario_overrides or []):
            if row.scenario != scenario_name:
                continue
            override_rows[row.expense_key] = row

        out = []
        for expense in base_expenses:
            key = make_expense_key(expense)
            row = override_rows.get(key)
            copied = dict(expense)
            copied["expense_key"] = key
            copied["override_source"] = None

            if row:
                copied["value"] = flt(row.override_value if row.override_value is not None else row.base_value)
                copied["is_overridden"] = 1 if flt(copied["value"]) != flt(row.base_value) else 0
                row.is_overridden = copied["is_overridden"]
                copied["override_source"] = "sheet" if copied["is_overridden"] else None
            else:
                copied["is_overridden"] = 0

            out.append(copied)

        return out

    def _sync_line_override_rows_for_lines(self, lines, scenario_caches, line_name=None):
        existing = {}
        valid_keys = set()
        for row in (self.line_overrides or []):
            key = (row.line_name, row.scenario, row.expense_key)
            existing[key] = row

        for line in lines:
            if line_name and line.name != line_name:
                continue
            if not line.item:
                continue

            scenario_name, _ = self._resolve_line_scenario(line)
            cache = scenario_caches.get(scenario_name)
            if not cache:
                continue

            for expense in cache.get("line_expenses") or []:
                expense_key = expense.get("expense_key") or make_expense_key(expense)
                key = (line.name, scenario_name, expense_key)
                valid_keys.add(key)
                row = existing.get(key)

                if not row:
                    row = self.append(
                        "line_overrides",
                        {
                            "line_name": line.name,
                            "line_idx": cint(line.idx),
                            "item": line.item,
                            "scenario": scenario_name,
                            "expense_key": expense_key,
                        },
                    )

                row.line_name = line.name
                row.line_idx = cint(line.idx)
                row.item = line.item
                row.scenario = scenario_name
                row.expense_key = expense_key
                row.expense_label = expense.get("label")
                row.sequence = cint(expense.get("sequence"))
                row.type = expense.get("type")
                row.applies_to = expense.get("applies_to")
                row.scope = expense.get("scope")
                row.is_active = 1
                row.base_value = flt(expense.get("base_value", expense.get("value")))
                row.sheet_override_value = flt(expense.get("value"))
                if row.line_override_value is None:
                    row.line_override_value = flt(row.sheet_override_value)
                row.is_overridden = 1 if flt(row.line_override_value) != flt(row.sheet_override_value) else 0

        for key, row in existing.items():
            if line_name and key[0] != line_name:
                continue
            if key in valid_keys:
                continue
            row.is_active = 0
            row.is_overridden = 0
            if row.expense_label and not row.expense_label.startswith("[STALE]"):
                row.expense_label = f"[STALE] {row.expense_label}"

    def _apply_line_override_rows(self, row, scenario_name, sheet_effective_expenses):
        if not row.name:
            return sheet_effective_expenses, False

        override_rows = {}
        for override in (self.line_overrides or []):
            if cint(override.is_active) != 1:
                continue
            if override.line_name != row.name or override.scenario != scenario_name:
                continue
            override_rows[override.expense_key] = override

        out = []
        has_line_override = False

        for expense in sheet_effective_expenses:
            copied = dict(expense)
            expense_key = copied.get("expense_key") or make_expense_key(copied)
            copied["expense_key"] = expense_key
            copied["base_value"] = flt(copied.get("base_value", copied.get("value")))

            override = override_rows.get(expense_key)
            if override and (copied.get("scope") or "").title() != "Per Sheet":
                copied["value"] = flt(
                    override.line_override_value
                    if override.line_override_value is not None
                    else override.sheet_override_value
                )
                is_line_overridden = 1 if flt(copied["value"]) != flt(override.sheet_override_value) else 0
                copied["is_overridden"] = 1 if is_line_overridden else copied.get("is_overridden", 0)
                copied["override_source"] = "line" if is_line_overridden else copied.get("override_source")
                override.is_overridden = is_line_overridden
                has_line_override = has_line_override or bool(is_line_overridden)
            elif override:
                override.line_override_value = flt(override.sheet_override_value)
                override.is_overridden = 0

            out.append(copied)

        return out, has_line_override

    def _resolve_line_scenario(self, row):
        if row.pricing_scenario:
            return row.pricing_scenario, "Line"

        if row.source_bundle:
            bundle_scenario = self._scenario_from_bundle_rule(row.source_bundle)
            if bundle_scenario:
                return bundle_scenario, "Bundle Rule"

        if self.pricing_scenario:
            return self.pricing_scenario, "Sheet Default"

        frappe.throw(_("Please set a default Pricing Scenario or line-level scenario."))

    def _scenario_from_bundle_rule(self, bundle_name):
        if not bundle_name:
            return None

        active_rules = [
            row
            for row in (self.bundle_scenario_rules or [])
            if cint(row.is_active) and row.bundle == bundle_name and row.pricing_scenario
        ]
        if not active_rules:
            return None

        active_rules = sorted(active_rules, key=lambda r: (cint(r.priority), cint(r.idx)))
        return active_rules[0].pricing_scenario

    def _active_expenses(self, scenario):
        as_dicts = [row.as_dict() for row in (scenario.expenses or []) if flt(row.is_active)]
        return sorted(as_dicts, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx"))))

    def _sheet_fixed_total(self, expenses):
        return sum(
            flt(row.get("value"))
            for row in expenses
            if (row.get("type") or "").title() == "Fixed" and (row.get("scope") or "").title() == "Per Sheet"
        )

    def _build_breakdown_preview(self, steps):
        if not steps:
            return _("No expenses")
        short = steps[:4]
        return " | ".join(
            f"{step.get('label')}: {flt(step.get('delta_unit') or 0) + flt(step.get('delta_line') or 0):.2f}"
            for step in short
        )

    def _get_template_rows(self, template_name):
        if frappe.db.exists("DocType", "Product Bundle") and frappe.db.exists("Product Bundle", template_name):
            bundle = frappe.get_doc("Product Bundle", template_name)
            return [{"item_code": row.item_code, "qty": flt(row.qty)} for row in (bundle.items or [])]

        if frappe.db.exists("DocType", "BOM") and frappe.db.exists("BOM", template_name):
            bom = frappe.get_doc("BOM", template_name)
            return [{"item_code": row.item_code, "qty": flt(row.qty)} for row in (bom.items or [])]

        return []

    def _get_default_scenario_or_throw(self):
        if not self.pricing_scenario:
            frappe.throw(_("Please select a Pricing Scenario."))
        return frappe.get_doc("Pricing Scenario", self.pricing_scenario)

    def _hydrate_line_from_item(self, row, item_groups):
        if not row.item:
            return
        if not row.display_group:
            row.display_group = item_groups.get(row.item) or "Ungrouped"

    def _set_buy_price_from_map(self, row, buying_price_list, buy_prices, force_refresh=False):
        if not row.item:
            return

        if not force_refresh and flt(row.buy_price) > 0:
            row.buy_price_missing = 0
            row.buy_price_message = ""
            return

        buy_price = buy_prices.get(row.item)
        if buy_price is None:
            row.buy_price_missing = 1
            row.buy_price_message = MISSING_BUY_PRICE_MSG.format(price_list=buying_price_list)
            if force_refresh and flt(row.buy_price) <= 0:
                row.buy_price = 0
            return

        row.buy_price = flt(buy_price)
        row.buy_price_missing = 0
        row.buy_price_message = ""

    def _set_benchmark_status(self, row, benchmark_list, benchmark_prices, computed_unit):
        benchmark_price = benchmark_prices.get(row.item)
        if benchmark_price is None or flt(benchmark_price) <= 0:
            row.benchmark_price = 0
            row.benchmark_delta_abs = 0
            row.benchmark_delta_pct = 0
            row.benchmark_status = "No Benchmark"
            row.benchmark_note = _("No benchmark price in {0}").format(benchmark_list)
            return

        row.benchmark_price = flt(benchmark_price)
        row.benchmark_delta_abs = flt(computed_unit) - flt(row.benchmark_price)
        row.benchmark_delta_pct = (row.benchmark_delta_abs / flt(row.benchmark_price)) * 100

        if flt(computed_unit) < flt(row.benchmark_price) * 0.8:
            row.benchmark_status = "Too Low"
            row.benchmark_note = _("Below benchmark")
        elif flt(computed_unit) > flt(row.benchmark_price) * 1.1:
            row.benchmark_status = "Too High"
            row.benchmark_note = _("Above benchmark")
        else:
            row.benchmark_status = "OK"
            row.benchmark_note = _("Within benchmark range")

    def _reset_totals(self):
        self.total_buy = 0
        self.total_expenses = 0
        self.total_selling = 0
        self.customs_total_applied = 0

    def _resolve_company_for_quotation(self):
        company = frappe.defaults.get_user_default("Company")
        if not company:
            company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            frappe.throw(
                _(
                    "Please set a default Company (User Defaults or Global Defaults) before generating a Quotation."
                )
            )
        return company

    @frappe.whitelist()
    def generate_quotation(self):
        self.check_permission("write")

        lines = self.lines or []
        if not self.customer:
            frappe.throw(_("Customer is required."))
        if not lines:
            frappe.throw(_("Please add at least one pricing line."))

        quotation = frappe.new_doc("Quotation")
        quotation.company = self._resolve_company_for_quotation()
        quotation.quotation_to = "Customer"
        quotation.party_name = self.customer
        if frappe.db.has_column("Quotation", "source_pricing_sheet"):
            quotation.source_pricing_sheet = self.name

        output_mode = (self.output_mode or "Avec details").strip().lower()
        if output_mode in ("sans details", "sans détails"):
            self._append_grouped_quotation_items(quotation)
        else:
            self._append_detailed_quotation_items(quotation)

        if not quotation.items:
            frappe.throw(_("No quotation items were generated from this Pricing Sheet."))

        quotation.insert()
        return quotation.name

    def _append_detailed_quotation_items(self, quotation):
        for row in self.lines or []:
            if not row.item:
                continue
            if not cint(row.show_in_detail):
                continue

            item_data = {
                "item_code": row.item,
                "qty": flt(row.qty),
                "rate": flt(row.final_sell_unit_price),
            }
            if frappe.db.has_column("Quotation Item", "source_pricing_sheet_line"):
                item_data["source_pricing_sheet_line"] = row.name
            if frappe.db.has_column("Quotation Item", "source_pricing_scenario"):
                item_data["source_pricing_scenario"] = row.resolved_pricing_scenario or row.pricing_scenario or self.pricing_scenario
            if frappe.db.has_column("Quotation Item", "source_pricing_override"):
                item_data["source_pricing_override"] = cint(
                    row.is_manual_override or row.has_scenario_override or row.has_line_override
                )
            if frappe.db.has_column("Quotation Item", "source_margin_policy"):
                item_data["source_margin_policy"] = self.margin_policy or ""
            if frappe.db.has_column("Quotation Item", "source_margin_percent"):
                item_data["source_margin_percent"] = flt(row.margin_pct)
            if frappe.db.has_column("Quotation Item", "source_customs_applied"):
                item_data["source_customs_applied"] = flt(row.customs_applied)
            if frappe.db.has_column("Quotation Item", "source_customs_basis"):
                item_data["source_customs_basis"] = row.customs_basis or ""

            quotation.append("items", item_data)

    def _append_grouped_quotation_items(self, quotation):
        config = self._get_group_line_config()
        group_item_code = config["item_code"]
        grouped = self._build_grouped_totals()

        for (group_name, scenario_name), group_total in grouped.items():
            item = {
                "item_code": group_item_code,
                "qty": 1,
                "rate": flt(group_total),
                "description": _("{0}: {1} [Scenario: {2}]").format(
                    config["description_prefix"], group_name, scenario_name or "-"
                ),
            }
            if frappe.db.has_column("Quotation Item", "source_pricing_scenario"):
                item["source_pricing_scenario"] = scenario_name
            quotation.append("items", item)

    def _build_grouped_totals(self):
        grouped = {}
        summary_bundle_ids = {
            row.bundle_group_id
            for row in (self.lines or [])
            if (row.line_type or "") == "Bundle Summary" and row.bundle_group_id
        }

        for row in self.lines or []:
            if flt(row.final_sell_total) == 0:
                continue
            if (row.line_type or "") == "Bundle Component" and row.bundle_group_id in summary_bundle_ids:
                continue

            fallback_group = row.display_group or "Ungrouped"
            scenario_name = row.resolved_pricing_scenario or row.pricing_scenario or self.pricing_scenario
            key = ((fallback_group or "Ungrouped").strip() or "Ungrouped", scenario_name)
            grouped[key] = grouped.get(key, 0.0) + flt(row.final_sell_total)

        return grouped

    def _get_group_line_config(self):
        settings_doctype = "Selling Settings"
        configured = None
        description_prefix = "Grouped from Pricing Sheet"

        if frappe.db.exists("DocType", settings_doctype):
            try:
                meta = frappe.get_meta(settings_doctype)
                if meta.has_field("custom_pricing_group_line_item"):
                    configured = frappe.db.get_single_value(settings_doctype, "custom_pricing_group_line_item")

                if meta.has_field("custom_pricing_group_desc_prefix"):
                    description_prefix = (
                        frappe.db.get_single_value(settings_doctype, "custom_pricing_group_desc_prefix")
                        or description_prefix
                    )
            except Exception:
                # Keep safe defaults if settings metadata is unavailable during bootstrap.
                pass

        item_code = configured or "GROUP_LINE"
        if not frappe.db.exists("Item", item_code):
            frappe.throw(
                _("Grouped quotation line item {0} is missing. Configure Selling Settings.").format(item_code)
            )
        return {
            "item_code": item_code,
            "description_prefix": description_prefix,
        }

    def _get_bundle_parent_item(self, bundle_name):
        if not frappe.db.exists("Product Bundle", bundle_name):
            frappe.throw(_("Product Bundle {0} not found.").format(bundle_name))

        if frappe.db.has_column("Product Bundle", "new_item_code"):
            item_code = frappe.db.get_value("Product Bundle", bundle_name, "new_item_code")
            if item_code:
                return item_code

        if frappe.db.has_column("Product Bundle", "item"):
            item_code = frappe.db.get_value("Product Bundle", bundle_name, "item")
            if item_code:
                return item_code

        settings_doctype = "Selling Settings"
        if frappe.db.exists("DocType", settings_doctype):
            try:
                meta = frappe.get_meta(settings_doctype)
                if meta.has_field("custom_pricing_group_line_item"):
                    fallback_item = frappe.db.get_single_value(settings_doctype, "custom_pricing_group_line_item")
                    if fallback_item:
                        return fallback_item
            except Exception:
                pass

        frappe.throw(
            _(
                "Product Bundle {0} has no parent item. Set Product Bundle parent item or configure Selling Settings fallback item."
            ).format(bundle_name)
        )


def make_expense_key(expense):
    return "|".join(
        [
            str(cint(expense.get("sequence"))),
            str((expense.get("label") or "").strip().lower()),
            str((expense.get("type") or "").strip().lower()),
            str((expense.get("applies_to") or "").strip().lower()),
            str((expense.get("scope") or "").strip().lower()),
        ]
    )


def cache_has_override_steps(steps, source=None):
    for step in steps or []:
        if not cint(step.get("is_overridden")):
            continue
        if source and (step.get("override_source") or "") != source:
            continue
        return True
    return False


def get_item_groups_map(item_codes):
    details = get_item_details_map(item_codes)
    return {name: (row or {}).get("item_group") for name, row in details.items()}


def get_item_details_map(item_codes):
    if not item_codes:
        return {}
    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_group", "custom_material", "custom_weight_kg"],
        limit_page_length=0,
    )
    return {
        row.name: {
            "item_group": row.item_group,
            "custom_material": row.custom_material,
            "custom_weight_kg": flt(row.custom_weight_kg),
        }
        for row in rows
    }


def get_latest_item_price(item_code, price_list, buying):
    return get_latest_item_prices([item_code], price_list, buying).get(item_code)


def get_latest_item_prices(item_codes, price_list, buying):
    if not item_codes or not price_list:
        return {}

    params = {
        "item_codes": tuple(item_codes),
        "price_list": price_list,
        "today": nowdate(),
        "buying": 1 if buying else 0,
    }

    conditions = [
        "ip.item_code in %(item_codes)s",
        "ip.price_list = %(price_list)s",
    ]

    has_enabled = frappe.db.has_column("Item Price", "enabled")
    has_buying = frappe.db.has_column("Item Price", "buying")
    has_valid_from = frappe.db.has_column("Item Price", "valid_from")
    has_valid_upto = frappe.db.has_column("Item Price", "valid_upto")

    if has_enabled:
        conditions.append("ip.enabled = 1")
    if has_buying:
        conditions.append("ip.buying = %(buying)s")
    if has_valid_from:
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if has_valid_upto:
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")

    order_by = "ip.item_code ASC, ip.modified DESC"
    if has_valid_from:
        order_by = "ip.item_code ASC, ip.valid_from DESC, ip.modified DESC"

    rows = frappe.db.sql(
        f"""
        SELECT ip.item_code, ip.price_list_rate
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        """,
        params,
        as_dict=True,
    )

    out = {}
    for row in rows:
        if row.item_code not in out:
            out[row.item_code] = flt(row.price_list_rate)
    return out


def recalculate_pricing_sheet_job(pricing_sheet_name, user=None):
    user_to_set = user or "Administrator"
    previous_user = frappe.session.user
    frappe.set_user(user_to_set)
    try:
        doc = frappe.get_doc("Pricing Sheet", pricing_sheet_name)
        doc.recalculate()
        doc.save(ignore_permissions=True)
    finally:
        frappe.set_user(previous_user)
    frappe.publish_realtime(
        "pricing_sheet_recalculated",
        {"pricing_sheet": pricing_sheet_name},
        user=user_to_set,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def stock_item_query(doctype, txt, searchfield, start, page_len, filters):
    txt_like = f"%{txt}%"
    return frappe.db.sql(
        """
        SELECT
            i.name,
            i.item_name,
            COALESCE(SUM(b.actual_qty), 0) AS stock_qty,
            i.stock_uom
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name
        WHERE i.disabled = 0
          AND i.is_stock_item = 1
          AND (i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s)
        GROUP BY i.name, i.item_name, i.stock_uom
        ORDER BY stock_qty DESC, i.name
        LIMIT %(start)s, %(page_len)s
        """,
        {"txt": txt_like, "start": start, "page_len": page_len},
    )


@frappe.whitelist()
def get_item_pricing_defaults(item_code, pricing_scenario=None):
    if not item_code:
        return {"buy_price": 0, "item_group": "Ungrouped"}

    buying_price_list = "Buying"
    if pricing_scenario and frappe.db.exists("Pricing Scenario", pricing_scenario):
        buying_price_list = (
            frappe.db.get_value("Pricing Scenario", pricing_scenario, "buying_price_list") or "Buying"
        )

    buy_price = get_latest_item_price(item_code, buying_price_list, buying=True)
    item_group = frappe.db.get_value("Item", item_code, "item_group") or "Ungrouped"
    return {
        "buy_price": flt(buy_price),
        "item_group": item_group,
    }
