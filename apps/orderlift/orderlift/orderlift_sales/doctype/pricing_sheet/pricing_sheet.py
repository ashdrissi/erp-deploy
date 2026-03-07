import json
from time import perf_counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime, nowdate, getdate, date_diff

from orderlift.sales.utils.customs_policy import compute_customs_amount, resolve_customs_rule
from orderlift.sales.utils.scenario_policy import resolve_scenario_rule
from orderlift.sales.utils.pricing_projection import apply_expenses
from orderlift.sales.utils.benchmark_policy import resolve_benchmark_margin
from orderlift.sales.utils.transport_allocation import compute_transport_allocation
from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
    DYNAMIC_MODE,
    STATIC_MODE,
    build_dynamic_context,
    build_static_context,
)


MISSING_BUY_PRICE_MSG = "No buying price in {price_list}"


class PricingSheet(Document):
    def before_save(self):
        self.recalculate()

    def recalculate(self):
        started = perf_counter()
        self._sync_customer_context()

        # ── Mode detection: delegate to static path when agent says so ──
        static_ctx = build_static_context(sales_person=self.sales_person)
        if static_ctx.get("pricing_mode") == STATIC_MODE:
            return self._recalculate_static(static_ctx, started)

        lines = self.lines or []
        self.projection_warnings = ""

        if not lines:
            self._reset_totals()
            self.applied_scenario_policy = ""
            self.applied_customs_policy = ""
            self.applied_benchmark_policy = ""
            self.calculated_on = now_datetime()
            self.calculated_by = frappe.session.user
            self.calc_runtime_ms = (perf_counter() - started) * 1000
            return

        item_codes = sorted({row.item for row in lines if row.item})
        item_details = get_item_details_map(item_codes)
        item_groups = {code: (item_details.get(code) or {}).get("item_group") for code in item_codes}
        self._set_default_sales_person()
        self._apply_agent_dynamic_defaults()

        scenario_policy = self._resolve_scenario_policy()
        self.applied_scenario_policy = scenario_policy.name if scenario_policy else ""

        scenario_docs = self._collect_scenarios_or_throw(lines, item_details=item_details, scenario_policy=scenario_policy)
        self._sync_override_rows_for_scenarios(scenario_docs)

        customs_policy = self._resolve_customs_policy()
        self.applied_customs_policy = customs_policy.name if customs_policy else ""

        # Resolve pricing policy (formerly benchmark policy)
        benchmark_policy_doc = self._resolve_benchmark_policy()
        fallback_margin = flt(getattr(benchmark_policy_doc, "fallback_margin_percent", None) or 10) if benchmark_policy_doc else 10
        self.applied_benchmark_policy = benchmark_policy_doc.name if benchmark_policy_doc else ""

        customs_policy_cache = {customs_policy.name: customs_policy} if customs_policy else {}
        benchmark_policy_cache = {benchmark_policy_doc.name: benchmark_policy_doc} if benchmark_policy_doc else {}

        warnings = []
        tier_warning = self._get_dynamic_tier_staleness_warning()
        if tier_warning:
            warnings.append(tier_warning)
        if not benchmark_policy_doc:
            warnings.append(_("No active pricing policy found; dynamic margin is disabled."))
        if not customs_policy:
            warnings.append(_("No active customs policy found; customs costs default to zero."))
        if not scenario_policy:
            warnings.append(_("No active scenario policy found; scenario falls back to line/bundle/default selection."))

        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes, benchmark_policy_doc=benchmark_policy_doc)
        self._sync_line_override_rows_for_lines(
            lines,
            scenario_caches,
            item_details=item_details,
            scenario_policy=scenario_policy,
        )

        total_base = 0.0
        total_expenses = 0.0
        total_final = 0.0
        line_snapshots = []

        buy_price_cache_by_list = {
            cache.get("buying_price_list"): cache.get("buy_prices") or {}
            for cache in scenario_caches.values()
            if cache.get("buying_price_list")
        }

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            self._hydrate_line_from_item(row, item_groups)
            line_context = self._build_rule_context(row=row, item_details=item_details)
            scenario_name, source, scenario_rule = self._resolve_line_scenario(
                row,
                line_context=line_context,
                scenario_policy=scenario_policy,
            )
            row.resolved_pricing_scenario = scenario_name
            row.scenario_source = source
            row.resolved_scenario_rule = self._format_scenario_rule(scenario_rule)

            cache = scenario_caches.get(scenario_name)
            if not cache:
                frappe.throw(_("Unable to resolve pricing cache for scenario {0}").format(scenario_name))

            effective_line_expenses, has_line_override = self._apply_line_override_rows(
                row,
                scenario_name,
                cache["line_expenses"],
            )

            self._set_buy_price_for_row(
                row,
                cache["buying_price_list"],
                cache["buy_prices"],
                buy_price_cache_by_list,
            )

            base_unit = flt(row.buy_price)
            base_amount = qty * base_unit
            row.base_amount = base_amount

            row_customs_policy = self._resolve_row_customs_policy(scenario_rule, customs_policy, customs_policy_cache)
            customs_calc = self._compute_customs_for_row(row, base_amount, item_details, row_customs_policy)
            if customs_calc.get("warning"):
                warnings.append(_("Row {0}: {1}").format(row.idx, customs_calc.get("warning")))

            transport_calc = self._compute_transport_for_row(
                row=row,
                qty=qty,
                base_amount=base_amount,
                item_details=item_details,
                transport_config=cache.get("transport_config") or {},
            )
            if transport_calc.get("warning"):
                warnings.append(_("Row {0}: {1}").format(row.idx, transport_calc.get("warning")))

            effective_line_expenses = self._inject_transport_expense(effective_line_expenses, transport_calc)

            # --- Benchmark-driven margin resolution ---
            benchmark_result = None
            margin_source = ""

            row_benchmark_policy = self._resolve_row_benchmark_policy(scenario_rule, benchmark_policy_doc, benchmark_policy_cache)
            row_tier_mod, row_zone_mod = self._resolve_dynamic_modifiers(row_benchmark_policy)

            if row_benchmark_policy:
                landed_cost = self._compute_landed_cost(
                    base_unit, qty, effective_line_expenses, customs_calc, transport_calc
                )
                benchmark_runtime = self._get_benchmark_runtime_cache(
                    row_benchmark_policy,
                    benchmark_policy_cache,
                    item_codes,
                )
                benchmark_result = self._resolve_benchmark_for_row(
                    row, landed_cost, row_benchmark_policy, item_details,
                    benchmark_runtime.get("benchmark_price_map") or {},
                    benchmark_runtime.get("benchmark_source_types") or {},
                    line_context,
                )
                if benchmark_result:
                    effective_line_expenses = self._inject_benchmark_margin_expense(
                        effective_line_expenses, benchmark_result
                    )
                    margin_source = "Pricing Rule" if benchmark_result.get("is_fallback") else "Benchmark & Rule"
                    
                for w in (benchmark_result or {}).get("warnings") or []:
                    warnings.append(_("Row {0}: {1}").format(row.idx, w))
            else:
                warnings.append(_("Row {0}: no pricing policy found; margin is 0.").format(row.idx))

            # --- Inject dynamic modifiers (Tier & Zone) ---
            effective_line_expenses, row_tier_mod, row_zone_mod = self._inject_modifier_expenses(
                effective_line_expenses, row_tier_mod, row_zone_mod
            )
            row.tier_modifier_amount = row_tier_mod
            row.zone_modifier_amount = row_zone_mod

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
                    "transport_calc": transport_calc,
                    "benchmark_result": benchmark_result,
                    "margin_source": margin_source,
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
            transport_calc = snap.get("transport_calc") or {}
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
                        "applies_to": "Base Price",
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
            row.resolved_margin_rule = ""
            row.customs_material = customs_calc.get("material") or ""
            row.customs_weight_kg = flt(customs_calc.get("weight_kg") or 0)
            row.customs_rate_per_kg = flt(customs_calc.get("rate_per_kg") or 0)
            row.customs_rate_percent = flt(customs_calc.get("rate_percent") or 0)
            row.customs_by_kg = flt(customs_calc.get("by_kg") or 0)
            row.customs_by_percent = flt(customs_calc.get("by_percent") or 0)
            row.customs_applied = flt(customs_calc.get("applied") or 0)
            row.customs_basis = customs_calc.get("basis") or ""
            row.transport_allocation_mode = transport_calc.get("mode") or ""
            row.transport_container_type = transport_calc.get("container_type") or ""
            row.transport_basis_total = flt(transport_calc.get("denominator") or 0)
            row.transport_numerator = flt(transport_calc.get("numerator") or 0)
            row.transport_allocated = flt(transport_calc.get("applied") or 0)

            # Benchmark trace fields
            br = snap.get("benchmark_result") or {}
            row.benchmark_reference = flt(br.get("benchmark_reference") or 0)
            row.benchmark_source_count = cint(br.get("source_count") or 0)
            row.benchmark_ratio = flt(br.get("ratio") or 0)
            row.benchmark_method = br.get("method") or ""
            matched_br = br.get("matched_rule") or {}
            row.resolved_benchmark_rule = self._format_benchmark_rule(matched_br) if matched_br else ""
            row.margin_source = snap.get("margin_source") or ""

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

            # Benchmark status: prefer new policy reference, fall back to old single-source
            br_active = br and flt(br.get("benchmark_reference") or 0) > 0
            if br_active:
                # Fix 1: use new multi-source benchmark_reference for status
                row.benchmark_price = flt(br["benchmark_reference"])  # Fix 4: sync fields
                self._set_benchmark_status_from_reference(
                    row, flt(br["benchmark_reference"]), flt(row.final_sell_unit_price),
                )
            else:
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
        self.resolved_mode = "Dynamic"
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

    def _recalculate_static(self, static_ctx, started):
        """Price lines from the agent's selling price list instead of the dynamic engine."""
        lines = self.lines or []
        self.projection_warnings = ""
        warnings = []

        if not lines:
            self._reset_totals()
            self.resolved_mode = "Static"
            self.calculated_on = now_datetime()
            self.calculated_by = frappe.session.user
            self.calc_runtime_ms = (perf_counter() - started) * 1000
            return

        # Resolve price list: doc field → agent first list → throw
        price_list = (self.selected_price_list or "").strip()
        if not price_list:
            agent_lists = static_ctx.get("selling_price_lists") or []
            price_list = agent_lists[0] if agent_lists else ""
        if not price_list:
            frappe.throw(_("No Selling Price List configured. Add one to the Agent Pricing Rules allocated lists."))
        self.selected_price_list = price_list

        # Bulk-fetch Item Prices
        item_codes = list({row.item for row in lines if row.item})
        item_prices = {}
        if item_codes:
            raw = frappe.get_all(
                "Item Price",
                filters={"price_list": price_list, "item_code": ["in", item_codes], "selling": 1},
                fields=["item_code", "price_list_rate", "currency"],
                order_by="modified desc",
            )
            for rec in raw:
                if rec["item_code"] not in item_prices:
                    item_prices[rec["item_code"]] = flt(rec["price_list_rate"])

        total_buy = 0.0
        total_final = 0.0
        missing = []

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            list_price = item_prices.get(row.item)
            if list_price is None:
                missing.append(row.item or f"Row {row.idx}")
                list_price = 0.0

            row.static_list_price = list_price
            row.is_manual_override = 1 if flt(row.manual_sell_unit_price) > 0 else 0
            row.final_sell_unit_price = flt(row.manual_sell_unit_price) if row.is_manual_override else list_price
            row.final_sell_total = row.final_sell_unit_price * qty

            buy = flt(row.buy_price)
            row.base_amount = buy * qty
            row.margin_pct = ((row.final_sell_unit_price - buy) / buy * 100) if buy > 0 else 0.0
            row.expense_total = 0.0
            row.projected_unit_price = list_price
            row.projected_total_price = list_price * qty

            # Clear dynamic-only fields
            row.resolved_pricing_scenario = ""
            row.scenario_source = ""
            row.benchmark_reference = 0
            row.benchmark_ratio = 0
            row.benchmark_status = "No Benchmark"
            row.margin_source = "Price List"
            row.customs_applied = 0
            row.pricing_breakdown_json = "[]"
            row.breakdown_preview = f"List: {price_list}"
            row.price_floor_violation = 0

            total_buy += flt(row.base_amount)
            total_final += flt(row.final_sell_total)

        if missing:
            warnings.append(_("{0} item(s) have no price in '{1}': {2}").format(
                len(missing), price_list, ", ".join(missing[:10])
            ))

        self.total_buy = flt(total_buy)
        self.total_expenses = 0.0
        self.total_selling = flt(total_final)
        self.customs_total_applied = 0.0
        self.applied_benchmark_policy = ""
        self.applied_scenario_policy = ""
        self.applied_customs_policy = ""
        self.resolved_mode = "Static"
        self.projection_warnings = "\n".join(warnings)
        self.calculated_on = now_datetime()
        self.calculated_by = frappe.session.user
        self.calc_runtime_ms = (perf_counter() - started) * 1000

    @frappe.whitelist()
    def load_scenario_overrides(self):

        lines = self.lines or []
        item_codes = sorted({row.item for row in lines if row.item})
        item_details = get_item_details_map(item_codes)
        scenario_policy = self._resolve_scenario_policy()
        scenario_docs = self._collect_scenarios_or_throw(lines, item_details=item_details, scenario_policy=scenario_policy)
        self._sync_override_rows_for_scenarios(scenario_docs)
        self.recalculate()
        self.save(ignore_permissions=True)
        return self.name

    @frappe.whitelist()
    def load_line_overrides(self, line_name=None):
        lines = self.lines or []
        item_codes = sorted({row.item for row in lines if row.item})
        item_details = get_item_details_map(item_codes)
        scenario_policy = self._resolve_scenario_policy()
        scenario_docs = self._collect_scenarios_or_throw(lines, item_details=item_details, scenario_policy=scenario_policy)
        self._sync_override_rows_for_scenarios(scenario_docs)
        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes)
        self._sync_line_override_rows_for_lines(
            lines,
            scenario_caches,
            line_name=line_name,
            item_details=item_details,
            scenario_policy=scenario_policy,
        )
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
        item_codes = sorted({row.item for row in lines if row.item})
        item_details = get_item_details_map(item_codes)
        scenario_policy = self._resolve_scenario_policy()
        scenario_docs = self._collect_scenarios_or_throw(lines, item_details=item_details, scenario_policy=scenario_policy)
        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes)

        buy_price_cache_by_list = {
            cache.get("buying_price_list"): cache.get("buy_prices") or {}
            for cache in scenario_caches.values()
            if cache.get("buying_price_list")
        }

        for row in lines:
            context = self._build_rule_context(row=row, item_details=item_details)
            scenario_name, source, _ = self._resolve_line_scenario(row, line_context=context, scenario_policy=scenario_policy)
            row.resolved_pricing_scenario = scenario_name
            row.scenario_source = source
            cache = scenario_caches.get(scenario_name)
            if not cache:
                continue
            self._set_buy_price_for_row(
                row,
                cache["buying_price_list"],
                cache["buy_prices"],
                buy_price_cache_by_list,
                force_refresh=True,
            )

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

    def _collect_scenarios_or_throw(self, lines, item_details=None, scenario_policy=None):
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

        item_details = item_details or {}
        if scenario_policy:
            for row in lines:
                ctx = self._build_rule_context(row=row, item_details=item_details)
                matched = self._resolve_scenario_rule_for_row(ctx, scenario_policy)
                if matched and matched.get("pricing_scenario"):
                    scenario_names.add(matched.get("pricing_scenario"))

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

    def _resolve_scenario_policy(self):
        if not frappe.db.exists("DocType", "Pricing Scenario Policy"):
            return None

        policy_doc = None
        if self.scenario_policy and frappe.db.exists("Pricing Scenario Policy", self.scenario_policy):
            policy_doc = frappe.get_doc("Pricing Scenario Policy", self.scenario_policy)
        else:
            default_name = frappe.db.get_value(
                "Pricing Scenario Policy",
                {"is_default": 1, "is_active": 1},
                "name",
            )
            if default_name:
                policy_doc = frappe.get_doc("Pricing Scenario Policy", default_name)
                self.scenario_policy = default_name

        if not policy_doc or cint(policy_doc.is_active) != 1:
            return None
        return policy_doc

    def _resolve_scenario_rule_for_row(self, context, scenario_policy):
        if not scenario_policy:
            return None

        rules = [
            {
                "pricing_scenario": row.pricing_scenario,
                "source_buying_price_list": row.source_buying_price_list,
                "customs_policy": row.customs_policy,
                "benchmark_policy": row.benchmark_policy,
                "sales_person": row.sales_person,
                "geography_territory": row.geography_territory,
                "customer_type": row.customer_type,
                "tier": row.tier,
                "item": row.item,
                "source_bundle": row.source_bundle,
                "item_group": row.item_group,
                "material": row.material,
                "sequence": cint(row.sequence),
                "priority": cint(row.priority),
                "is_active": cint(row.is_active),
                "idx": cint(row.idx),
            }
            for row in (scenario_policy.scenario_rules or [])
        ]
        return resolve_scenario_rule(rules, context=context)

    def _build_rule_context(self, row=None, item_details=None):
        row = row or frappe._dict()
        item_details = item_details or {}
        item_code = row.item if row else None
        item_meta = item_details.get(item_code) or {}
        geo = self._resolve_geography_context()
        source_buying_price_list = (getattr(row, "source_buying_price_list", "") or "").strip()
        return {
            "source_buying_price_list": source_buying_price_list or self._resolve_source_buying_price_list(),
            "sales_person": self.sales_person,
            "geography_territory": geo.get("geography_territory"),
            "customer_type": self.customer_type,
            "tier": self.tier,
            "item": item_code,
            "source_bundle": row.source_bundle,
            "item_group": item_meta.get("item_group"),
            "material": item_meta.get("custom_material"),
        }

    def _resolve_geography_context(self):
        if self.geography_territory:
            return {"geography_territory": self.geography_territory}

        territory = frappe.db.get_value("Customer", self.customer, "territory") if self.customer else None
        if territory:
            return {"geography_territory": territory}

        return {"geography_territory": ""}

    def _set_default_sales_person(self):
        if self.sales_person:
            return
        if not frappe.db.exists("DocType", "Sales Person"):
            return
        if not frappe.db.has_column("Sales Person", "user"):
            return
        filters = {"user": frappe.session.user}
        if frappe.db.has_column("Sales Person", "enabled"):
            filters["enabled"] = 1
        sales_person = frappe.db.get_value("Sales Person", filters, "name")
        if sales_person:
            self.sales_person = sales_person

    def _resolve_source_buying_price_list(self):
        context = build_dynamic_context(sales_person=self.sales_person)
        selected = context.get("selected") or {}
        buying_price_list = (selected.get("buying_price_list") or "").strip()
        if buying_price_list:
            return buying_price_list

        if self.pricing_scenario:
            return (frappe.db.get_value("Pricing Scenario", self.pricing_scenario, "buying_price_list") or "").strip()
        return ""

    def _resolve_row_customs_policy(self, matched_rule, default_policy, policy_cache):
        if matched_rule and matched_rule.get("customs_policy"):
            return self._get_named_doc("Pricing Customs Policy", matched_rule.get("customs_policy"), policy_cache)
        return default_policy

    def _resolve_row_benchmark_policy(self, matched_rule, default_policy, policy_cache):
        if matched_rule and matched_rule.get("benchmark_policy"):
            return self._get_named_doc("Pricing Benchmark Policy", matched_rule.get("benchmark_policy"), policy_cache)
        return default_policy

    def _get_named_doc(self, doctype, name, cache):
        name = (name or "").strip()
        if not name:
            return None
        if name in cache:
            return cache[name]
        if not frappe.db.exists(doctype, name):
            return None
        doc = frappe.get_doc(doctype, name)
        if cint(getattr(doc, "is_active", 1)) != 1:
            return None
        cache[name] = doc
        return doc

    def _get_benchmark_runtime_cache(self, benchmark_policy_doc, runtime_cache, item_codes):
        if not benchmark_policy_doc:
            return {"benchmark_price_map": {}, "benchmark_source_types": {}}
        key = f"__runtime__::{benchmark_policy_doc.name}"
        cached = runtime_cache.get(key)
        if cached:
            return cached

        benchmark_price_map = {}
        benchmark_source_types = {}
        for src in benchmark_policy_doc.benchmark_sources or []:
            if not cint(src.is_active):
                continue
            pl = src.price_list
            if pl and pl not in benchmark_source_types:
                benchmark_source_types[pl] = get_price_list_type(pl)
            if pl and pl not in benchmark_price_map:
                benchmark_price_map[pl] = get_latest_item_prices(item_codes, pl, buying=None)

        cached = {
            "benchmark_price_map": benchmark_price_map,
            "benchmark_source_types": benchmark_source_types,
        }
        runtime_cache[key] = cached
        return cached

    def _apply_agent_dynamic_defaults(self):
        # --- Static mode: pre-fill selected_price_list ---
        static_ctx = build_static_context(sales_person=self.sales_person)
        if static_ctx.get("pricing_mode") == STATIC_MODE:
            if not self.selected_price_list:
                lists = static_ctx.get("selling_price_lists") or []
                if lists:
                    self.selected_price_list = lists[0]
            return

        context = build_dynamic_context(sales_person=self.sales_person)
        if context.get("pricing_mode") != DYNAMIC_MODE:
            return

        selected = context.get("selected") or {}
        if selected.get("pricing_scenario"):
            self.pricing_scenario = selected.get("pricing_scenario")
        if selected.get("customs_policy"):
            self.customs_policy = selected.get("customs_policy")
        if selected.get("benchmark_policy"):
            self.benchmark_policy = selected.get("benchmark_policy")

        self._assert_agent_dynamic_allowed(
            "pricing_scenario",
            context.get("allowed_pricing_scenarios") or [],
            _("Agent rule does not allow Pricing Scenario {0} for sales person {1}."),
        )
        self._assert_agent_dynamic_allowed(
            "customs_policy",
            context.get("allowed_customs_policies") or [],
            _("Agent rule does not allow Customs Policy {0} for sales person {1}."),
        )
        self._assert_agent_dynamic_allowed(
            "benchmark_policy",
            context.get("allowed_benchmark_policies") or [],
            _("Agent rule does not allow Pricing Policy {0} for sales person {1}."),
        )

        allowed_scenarios = context.get("allowed_pricing_scenarios") or []
        if allowed_scenarios:
            for row in self.lines or []:
                row_scenario = (row.get("pricing_scenario") or "").strip()
                if row_scenario and row_scenario not in allowed_scenarios:
                    frappe.throw(
                        _("Line {0}: Pricing Scenario {1} is not allowed for sales person {2}.").format(
                            row.idx,
                            row_scenario,
                            self.sales_person or "-",
                        )
                    )

    def _assert_agent_dynamic_allowed(self, fieldname, allowed_values, message_template):
        value = (getattr(self, fieldname, None) or "").strip()
        if not value:
            return
        if not allowed_values:
            return
        if value in allowed_values:
            return
        frappe.throw(message_template.format(value, self.sales_person or "-"))

    def _sync_customer_context(self):
        if not self.customer:
            self.customer_type = ""
            self.tier = ""
            return

        customer_values = frappe.db.get_value(
            "Customer",
            self.customer,
            ["customer_group", "tier"],
            as_dict=True,
        ) or {}

        self.customer_type = (customer_values.get("customer_group") or "").strip()
        self.tier = (customer_values.get("tier") or "").strip()

    def _get_dynamic_tier_staleness_warning(self):
        if not self.customer:
            return ""
        if not frappe.db.has_column("Customer", "enable_dynamic_segmentation"):
            return ""
        if not frappe.db.has_column("Customer", "tier_last_calculated_on"):
            return ""

        values = frappe.db.get_value(
            "Customer",
            self.customer,
            ["enable_dynamic_segmentation", "tier_last_calculated_on", "tier"],
            as_dict=True,
        ) or {}
        if cint(values.get("enable_dynamic_segmentation")) != 1:
            return ""
        if not values.get("tier"):
            return _("Customer has Dynamic Segmentation enabled but no tier is currently assigned.")

        calc_on = values.get("tier_last_calculated_on")
        if not calc_on:
            return _("Customer tier has no calculation timestamp; consider re-running segmentation.")

        stale_days = date_diff(nowdate(), getdate(calc_on))
        if stale_days > 7:
            return _("Customer tier is {0} days old; consider re-running segmentation.").format(stale_days)
        return ""

    def _format_scenario_rule(self, rule):
        if not rule:
            return ""
        parts = [rule.get("pricing_scenario") or ""]
        if rule.get("source_buying_price_list"):
            parts.append(_("Buying: {0}").format(rule.get("source_buying_price_list")))
        if rule.get("customs_policy"):
            parts.append(_("Customs: {0}").format(rule.get("customs_policy")))
        if rule.get("benchmark_policy"):
            parts.append(_("Benchmark: {0}").format(rule.get("benchmark_policy")))
        return " | ".join([p for p in parts if p])

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
                "delta_unit": 0,
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
            "applies_to": "Base Price",
            "scope": "Per Unit",
            "sequence": cint(margin_rule.get("sequence") or 90),
            "is_active": 1,
            "is_overridden": 0,
            "override_source": "pricing_policy",
        }

        out = list(expenses or [])
        out.append(dynamic_margin)
        out = sorted(out, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx") or 0)))
        for exp in out:
            exp["expense_key"] = exp.get("expense_key") or make_expense_key(exp)
        return out

    def _resolve_dynamic_modifiers(self, benchmark_policy_doc):
        """Resolve tier and zone modifiers from the benchmark policy.

        Returns (tier_mod_dict, zone_mod_dict) — each is a dict with
        'amount', 'type' ('Fixed'|'Percentage'), 'label', or None if
        no match.
        """
        tier_mod = None
        zone_mod = None
        if not benchmark_policy_doc:
            return tier_mod, zone_mod

        sheet_tier = (self.tier or "").strip()
        sheet_customer_group = (self.customer_type or "").strip()
        sheet_territory = (self.geography_territory or "").strip()

        # Match tier modifier
        if sheet_tier:
            tier_default_row = None
            for row in (benchmark_policy_doc.get("tier_modifiers") or []):
                if not row.get("is_active"):
                    continue
                if (row.get("tier") or "").strip() != sheet_tier:
                    continue

                row_customer_group = (row.get("customer_group") or "").strip()
                if row_customer_group:
                    if row_customer_group != sheet_customer_group:
                        continue
                    tier_mod = {
                        "amount": flt(row.get("modifier_amount")),
                        "type": row.get("modifier_type") or "Fixed",
                        "label": "Tier: {} / Group: {}".format(sheet_tier, row_customer_group),
                    }
                    break
                if tier_default_row is None:
                    tier_default_row = row

            if not tier_mod and tier_default_row:
                tier_mod = {
                    "amount": flt(tier_default_row.get("modifier_amount")),
                    "type": tier_default_row.get("modifier_type") or "Fixed",
                    "label": "Tier: {}".format(sheet_tier),
                }

        # Match zone modifier
        if sheet_territory:
            for row in (benchmark_policy_doc.get("zone_modifiers") or []):
                if not row.get("is_active"):
                    continue
                if (row.get("territory") or "").strip() == sheet_territory:
                    zone_mod = {
                        "amount": flt(row.get("modifier_amount")),
                        "type": row.get("modifier_type") or "Fixed",
                        "label": "Zone: {}".format(sheet_territory),
                    }
                    break

        return tier_mod, zone_mod

    def _inject_modifier_expenses(self, expenses, tier_mod, zone_mod):
        """Inject tier and zone modifiers as additional expenses.

        Returns (updated_expenses, tier_amount, zone_amount).
        """
        out = list(expenses or [])
        tier_amount = 0.0
        zone_amount = 0.0

        if tier_mod and flt(tier_mod["amount"]) != 0:
            tier_amount = flt(tier_mod["amount"])
            exp_type = "Percentage" if tier_mod["type"] == "Percentage" else "Fixed"
            tier_expense = {
                "label": "Tier Modifier ({})".format(tier_mod["label"]),
                "type": exp_type,
                "value": tier_amount,
                "applies_to": "Base Price",
                "scope": "Per Unit",
                "sequence": 95,
                "is_active": 1,
                "is_overridden": 0,
                "override_source": "tier_modifier",
            }
            out.append(tier_expense)

        if zone_mod and flt(zone_mod["amount"]) != 0:
            zone_amount = flt(zone_mod["amount"])
            exp_type = "Percentage" if zone_mod["type"] == "Percentage" else "Fixed"
            zone_expense = {
                "label": "Zone Modifier ({})".format(zone_mod["label"]),
                "type": exp_type,
                "value": zone_amount,
                "applies_to": "Base Price",
                "scope": "Per Unit",
                "sequence": 96,
                "is_active": 1,
                "is_overridden": 0,
                "override_source": "zone_modifier",
            }
            out.append(zone_expense)

        out = sorted(out, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx") or 0)))
        for exp in out:
            exp["expense_key"] = exp.get("expense_key") or make_expense_key(exp)

        return out, tier_amount, zone_amount

    # --- Benchmark-driven margin helpers ---

    def _resolve_benchmark_policy(self):
        """Fetch the Pricing Benchmark Policy linked to the sheet or fallback to default."""
        if self.benchmark_policy and frappe.db.exists("Pricing Benchmark Policy", self.benchmark_policy):
            return frappe.get_doc("Pricing Benchmark Policy", self.benchmark_policy)
        
        default_name = frappe.db.get_value(
            "Pricing Benchmark Policy",
            {"is_default": 1, "is_active": 1},
            "name",
        )
        if default_name:
            self.benchmark_policy = default_name
            return frappe.get_doc("Pricing Benchmark Policy", default_name)
            
        return None

    def _compute_landed_cost(self, base_unit, qty, expenses, customs_calc, transport_calc):
        """Compute landed cost = base + all expenses EXCEPT margin.

        This runs apply_expenses on the non-margin expenses to get the
        fully-loaded cost before any margin is applied.
        """
        # expenses list before margin injection already excludes margin
        pricing = apply_expenses(base_unit=base_unit, qty=qty, expenses=expenses)
        landed = flt(pricing["projected_unit"])
        # Add customs (per-unit equivalent)
        if customs_calc and flt(customs_calc.get("applied")):
            landed += flt(customs_calc["applied"]) / qty if qty else 0
        return landed

    def _resolve_benchmark_for_row(self, row, landed_cost, benchmark_policy_doc, item_details, price_map, source_types_map, line_context):
        """Resolve benchmark margin for a single pricing line."""
        sources = [
            {
                "price_list": src.price_list,
                "label": src.label or src.price_list,
                "source_kind": src.source_kind or "",
                "price_list_type": source_types_map.get(src.price_list, ""),
                "weight": flt(src.weight) or 1.0,
                "is_active": cint(src.is_active),
            }
            for src in benchmark_policy_doc.benchmark_sources or []
        ]
        rules = [
            {
                "ratio_min": flt(r.ratio_min),
                "ratio_max": flt(r.ratio_max),
                "target_margin_percent": flt(r.target_margin_percent),
                "item_group": r.item_group or "",
                "material": r.material or "",
                "source_bundle": r.source_bundle or "",
                "geography_territory": r.geography_territory or "",
                "priority": cint(r.priority or 10),
                "sequence": cint(r.sequence or 90),
                "is_active": cint(r.is_active),
                "idx": cint(r.idx or 0),
            }
            for r in benchmark_policy_doc.benchmark_rules or []
        ]

        return resolve_benchmark_margin(
            item_code=row.item,
            landed_cost=landed_cost,
            benchmark_sources=sources,
            benchmark_rules=rules,
            method=benchmark_policy_doc.method or "Median",
            benchmark_basis=benchmark_policy_doc.benchmark_basis or "Selling Market",
            min_sources=cint(benchmark_policy_doc.min_sources_required or 2),
            fallback_margin=flt(benchmark_policy_doc.fallback_margin_percent or 10),
            price_map=price_map,
            context=line_context,
        )

    def _inject_benchmark_margin_expense(self, expenses, benchmark_result):
        """Inject margin expense from benchmark result."""
        if not benchmark_result:
            return expenses
        margin_pct = flt(benchmark_result.get("target_margin_percent"))
        matched_rule = benchmark_result.get("matched_rule") or {}
        return self._inject_margin_expense(expenses, {
            "margin_percent": margin_pct,
            "sequence": cint(matched_rule.get("sequence") or 90),
        })

    def _inject_fallback_margin_expense(self, expenses, benchmark_result, fallback_margin):
        """Inject fallback margin when benchmark data insufficient."""
        margin_pct = flt(
            (benchmark_result or {}).get("target_margin_percent") or fallback_margin
        )
        return self._inject_margin_expense(expenses, {
            "margin_percent": margin_pct,
            "sequence": 90,
        })

    def _format_benchmark_rule(self, rule):
        """Format a benchmark rule for display."""
        if not rule:
            return ""
        scope = rule.get("source_bundle") or rule.get("item_group") or rule.get("material") or "Any"
        return _("Ratio {0}-{1}: {2}% ({3})").format(
            f"{flt(rule.get('ratio_min')):.2f}",
            f"{flt(rule.get('ratio_max')):.2f}" if flt(rule.get("ratio_max")) > 0 else "∞",
            flt(rule.get("target_margin_percent")),
            scope,
        )

    def _inject_transport_expense(self, expenses, transport_calc):
        applied = flt((transport_calc or {}).get("applied") or 0)
        if applied <= 0:
            return list(expenses or [])

        out = list(expenses or [])
        out.append(
            {
                "label": "Container Transport Allocation",
                "type": "Fixed",
                "value": applied,
                "applies_to": "Base Price",
                "scope": "Per Line",
                "sequence": 15,
                "is_active": 1,
                "is_overridden": 0,
                "override_source": "transport_policy",
            }
        )
        out = sorted(out, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx") or 0)))
        for exp in out:
            exp["expense_key"] = exp.get("expense_key") or make_expense_key(exp)
        return out

    def _extract_transport_config(self, scenario):
        return {
            "is_active": cint(getattr(scenario, "transport_is_active", 0)),
            "container_type": (getattr(scenario, "transport_container_type", "") or "").strip(),
            "allocation_mode": (getattr(scenario, "transport_allocation_mode", "By Value") or "By Value").strip().title(),
            "container_price": flt(getattr(scenario, "transport_container_price", 0)),
            "total_merch_value": flt(getattr(scenario, "transport_total_merch_value", 0)),
            "total_weight_kg": flt(getattr(scenario, "transport_total_weight_kg", 0)),
            "total_volume_m3": flt(getattr(scenario, "transport_total_volume_m3", 0)),
        }

    def _compute_transport_for_row(self, row, qty, base_amount, item_details, transport_config):
        details = item_details.get(row.item) or {}
        unit_weight_kg = flt(details.get("custom_weight_kg"))
        unit_volume_m3 = flt(details.get("custom_volume_m3"))
        line_weight_kg = flt(qty) * unit_weight_kg
        line_volume_m3 = flt(qty) * unit_volume_m3

        out = {
            "mode": (transport_config.get("allocation_mode") or "By Value").strip().title(),
            "container_type": transport_config.get("container_type") or "",
            "denominator": 0.0,
            "numerator": 0.0,
            "applied": 0.0,
            "warning": "",
        }

        if cint(transport_config.get("is_active")) != 1:
            return out

        calc = compute_transport_allocation(
            mode=transport_config.get("allocation_mode"),
            container_price=transport_config.get("container_price"),
            line_base_amount=base_amount,
            line_weight_kg=line_weight_kg,
            line_volume_m3=line_volume_m3,
            totals={
                "total_merch_value": transport_config.get("total_merch_value"),
                "total_weight_kg": transport_config.get("total_weight_kg"),
                "total_volume_m3": transport_config.get("total_volume_m3"),
            },
        )
        out.update(calc)
        return out

    def _format_margin_rule(self, rule):
        if not rule:
            return ""
        scope = rule.get("item") or rule.get("source_bundle") or rule.get("item_group") or rule.get("material") or "Any"
        sales_person = rule.get("sales_person") or "Any"
        return _("{0} / {1}: {2}% on {3}").format(
            sales_person,
            scope,
            flt(rule.get("margin_percent")),
            "Base Price",
        )

    def _build_scenario_caches(self, scenario_docs, item_codes, benchmark_policy_doc=None):
        # Pre-fetch benchmark prices from all sources in the benchmark policy
        benchmark_price_map = {}
        benchmark_source_types = {}
        if benchmark_policy_doc:
            for src in benchmark_policy_doc.benchmark_sources or []:
                if not cint(src.is_active):
                    continue
                pl = src.price_list
                if pl and pl not in benchmark_source_types:
                    benchmark_source_types[pl] = get_price_list_type(pl)
                if pl and pl not in benchmark_price_map:
                    benchmark_price_map[pl] = get_latest_item_prices(
                        item_codes, pl, buying=None
                    )

        caches = {}
        for name, scenario in scenario_docs.items():
            buying_price_list = scenario.buying_price_list or "Buying"
            benchmark_price_list = scenario.benchmark_price_list or "Benchmark Selling"

            base_expenses = self._active_expenses(scenario)
            effective_expenses = self._apply_override_rows(name, base_expenses)
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
                "benchmark_prices": get_latest_item_prices(item_codes, benchmark_price_list, buying=None),
                "benchmark_price_map": benchmark_price_map,
                "benchmark_source_types": benchmark_source_types,
                "line_expenses": line_expenses,
                "sheet_fixed_total": sheet_fixed_total,
                "transport_config": self._extract_transport_config(scenario),
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

    def _sync_line_override_rows_for_lines(self, lines, scenario_caches, line_name=None, item_details=None, scenario_policy=None):
        existing = {}
        valid_keys = set()
        item_details = item_details or {}
        for row in (self.line_overrides or []):
            key = (row.line_name, row.scenario, row.expense_key)
            existing[key] = row

        for line in lines:
            if line_name and line.name != line_name:
                continue
            if not line.item:
                continue

            line_context = self._build_rule_context(row=line, item_details=item_details)
            scenario_name, _, _ = self._resolve_line_scenario(
                line,
                line_context=line_context,
                scenario_policy=scenario_policy,
            )
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

    def _resolve_line_scenario(self, row, line_context=None, scenario_policy=None):
        if row.pricing_scenario:
            return row.pricing_scenario, "Line", None

        if row.source_bundle:
            bundle_scenario = self._scenario_from_bundle_rule(row.source_bundle)
            if bundle_scenario:
                return bundle_scenario, "Bundle Rule", None

        if scenario_policy:
            line_context = line_context or self._build_rule_context(row)
            matched = self._resolve_scenario_rule_for_row(line_context, scenario_policy)
            if matched and matched.get("pricing_scenario"):
                return matched.get("pricing_scenario"), "Policy Rule", matched

        if self.pricing_scenario:
            return self.pricing_scenario, "Sheet Default", None

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

    def _set_buy_price_for_row(
        self,
        row,
        scenario_buying_price_list,
        scenario_buy_prices,
        buy_price_cache_by_list,
        force_refresh=False,
    ):
        buying_price_list = (getattr(row, "source_buying_price_list", "") or "").strip() or scenario_buying_price_list
        buy_prices = scenario_buy_prices or {}

        if buying_price_list and buying_price_list != scenario_buying_price_list:
            cached_prices = buy_price_cache_by_list.get(buying_price_list)
            if cached_prices is None:
                cached_prices = get_latest_item_prices([row.item], buying_price_list, buying=True) if row.item else {}
                buy_price_cache_by_list[buying_price_list] = cached_prices
            buy_prices = cached_prices

        self._set_buy_price_from_map(row, buying_price_list, buy_prices, force_refresh=force_refresh)

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

    def _set_benchmark_status_from_reference(self, row, benchmark_ref, computed_unit):
        """Set benchmark status using the new multi-source benchmark_reference.

        Same logic as _set_benchmark_status but uses a pre-computed reference
        instead of looking up from a single price list.
        """
        if not benchmark_ref or flt(benchmark_ref) <= 0:
            row.benchmark_delta_abs = 0
            row.benchmark_delta_pct = 0
            row.benchmark_status = "No Benchmark"
            row.benchmark_note = _("Benchmark reference is zero")
            return

        row.benchmark_delta_abs = flt(computed_unit) - flt(benchmark_ref)
        row.benchmark_delta_pct = (row.benchmark_delta_abs / flt(benchmark_ref)) * 100

        if flt(computed_unit) < flt(benchmark_ref) * 0.8:
            row.benchmark_status = "Too Low"
            row.benchmark_note = _("Below benchmark (policy)")
        elif flt(computed_unit) > flt(benchmark_ref) * 1.1:
            row.benchmark_status = "Too High"
            row.benchmark_note = _("Above benchmark (policy)")
        else:
            row.benchmark_status = "OK"
            row.benchmark_note = _("Within benchmark range (policy)")

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
        geo = self._resolve_geography_context()
        geography_label = geo.get("geography_territory") or ""
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
            if frappe.db.has_column("Quotation Item", "source_pricing_policy"):
                item_data["source_pricing_policy"] = self.benchmark_policy or ""
            if frappe.db.has_column("Quotation Item", "source_margin_percent"):
                item_data["source_margin_percent"] = flt(row.margin_pct)
            if frappe.db.has_column("Quotation Item", "source_scenario_rule"):
                item_data["source_scenario_rule"] = row.resolved_scenario_rule or ""
            if frappe.db.has_column("Quotation Item", "source_margin_rule"):
                item_data["source_margin_rule"] = row.resolved_margin_rule or ""
            if frappe.db.has_column("Quotation Item", "source_sales_person"):
                item_data["source_sales_person"] = self.sales_person or ""
            if frappe.db.has_column("Quotation Item", "source_geography"):
                item_data["source_geography"] = geography_label
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
        fields=["name", "item_group", "custom_material", "custom_weight_kg", "custom_volume_m3"],
        limit_page_length=0,
    )
    return {
        row.name: {
            "item_group": row.item_group,
            "custom_material": row.custom_material,
            "custom_weight_kg": flt(row.custom_weight_kg),
            "custom_volume_m3": flt(row.custom_volume_m3),
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
    }
    if buying is not None:
        params["buying"] = 1 if buying else 0

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
    if has_buying and buying is not None:
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


def get_price_list_type(price_list_name):
    if not price_list_name:
        return "Unknown"
    values = frappe.db.get_value("Price List", price_list_name, ["buying", "selling"], as_dict=True) or {}
    is_buying = cint(values.get("buying")) == 1
    is_selling = cint(values.get("selling")) == 1
    if is_buying and is_selling:
        return "Mixed"
    if is_buying:
        return "Buying"
    if is_selling:
        return "Selling"
    return "Unknown"


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
def get_item_pricing_defaults(item_code, pricing_scenario=None, source_buying_price_list=None):
    if not item_code:
        return {"buy_price": 0, "item_group": "Ungrouped"}

    buying_price_list = (source_buying_price_list or "").strip() or "Buying"
    if not source_buying_price_list and pricing_scenario and frappe.db.exists("Pricing Scenario", pricing_scenario):
        buying_price_list = (
            frappe.db.get_value("Pricing Scenario", pricing_scenario, "buying_price_list") or "Buying"
        )

    buy_price = get_latest_item_price(item_code, buying_price_list, buying=True)
    item_group = frappe.db.get_value("Item", item_code, "item_group") or "Ungrouped"
    return {
        "buy_price": flt(buy_price),
        "item_group": item_group,
    }


@frappe.whitelist()
def get_agent_dynamic_defaults(sales_person=None):
    return build_dynamic_context(sales_person=sales_person)
