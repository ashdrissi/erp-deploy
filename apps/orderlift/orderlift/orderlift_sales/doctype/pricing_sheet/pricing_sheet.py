import json
from functools import lru_cache
from time import perf_counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, now_datetime, nowdate, getdate, date_diff

from orderlift.warehouse_access import stock_warehouse_condition

from orderlift.sales.utils.customs_policy import compute_customs_amount, resolve_customs_rule
from orderlift.orderlift_logistics.utils.packaging_resolver import get_packaging_resolution
from orderlift.sales.utils.dimensioning import coerce_dimensioning_value
from orderlift.sales.utils.scenario_policy import resolve_scenario_rule
from orderlift.sales.utils.pricing_projection import (
    apply_discount_and_commission,
    apply_expenses,
    resolve_max_discount_cap,
)
from orderlift.sales.utils.benchmark_policy import (
    compute_margin_step,
    compute_policy_adjustment_step,
    resolve_benchmark_margin,
)
from orderlift.sales.utils.transport_allocation import compute_transport_allocation
from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
    DYNAMIC_MODE,
    STATIC_MODE,
    build_dynamic_context,
    build_static_context,
)
from orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine import (
    resolve_global_pricing_modifiers,
)
from orderlift.orderlift_sales.utils.tax_inclusive import (
    apply_quotation_sales_tax_template,
    company_default_sales_taxes_template,
    sales_tax_template_total_rate,
    sync_quotation_item_tax_inclusive_fields,
    sync_pricing_sheet_item_tax_inclusive_fields,
)
from orderlift.orderlift_sales.utils.price_list_scope import PRICE_LIST_TYPE_FIELD, can_override_quotation_pricing, get_price_list_type, validate_price_list_scope
from orderlift.startup_roles import QUOTATION_CAPABLE_COMMERCIAL_ROLES, RESTRICTED_COMMERCIAL_ROLES


MISSING_BUY_PRICE_MSG = "No buying price in {price_list}"
PRIVILEGED_PRICING_ROLES = {"Administrator", "Orderlift Admin", "Orderlift Business Admin", "Pricing Manager", "Sales Manager", "System Manager"}
RESTRICTED_AGENT_ROLES = RESTRICTED_COMMERCIAL_ROLES
NO_EXPENSES_SCENARIO = "__NO_EXPENSES_POLICY__"
SUPPORTED_PRICING_PARTY_TYPES = {"Customer", "Lead", "Prospect"}


class PricingSheet(Document):
    def before_validate(self):
        self._sync_party_fields()
        self._set_default_taxes_template()
        self._sanitize_line_policy_resolution_fields()

    def _set_default_taxes_template(self):
        if not self.meta.get_field("taxes_and_charges_template"):
            return
        if (getattr(self, "taxes_and_charges_template", "") or "").strip():
            return
        company = (getattr(self, "custom_company", "") or "").strip()
        template = company_default_sales_taxes_template(company) if company else ""
        if template:
            self.taxes_and_charges_template = template

    def _sync_party_fields(self):
        party_type = (getattr(self, "party_type", "") or "").strip()
        party_name = (getattr(self, "party_name", "") or "").strip()
        customer = (getattr(self, "customer", "") or "").strip()

        if not party_type:
            party_type = "Customer"
        if party_type not in SUPPORTED_PRICING_PARTY_TYPES:
            frappe.throw(_("Party Type must be Customer, Lead, or Prospect."))
        if not party_name and customer:
            party_type = "Customer"
            party_name = customer

        self.party_type = party_type
        self.party_name = party_name
        self.customer = party_name if party_type == "Customer" else ""

    def before_save(self):
        self._enforce_agent_pricing_inputs()
        self.recalculate()
        sync_pricing_sheet_item_tax_inclusive_fields(self)

    def _sanitize_line_policy_resolution_fields(self):
        for row in self.lines or []:
            if (getattr(row, "resolved_pricing_scenario", "") or "").strip() == NO_EXPENSES_SCENARIO:
                row.resolved_pricing_scenario = ""

            source = (getattr(row, "scenario_source", "") or "").strip()
            if source == "Simulator Fallback":
                row.scenario_source = "Draft Fallback"
            elif source == "Sheet Mapping":
                row.scenario_source = "Policy Rule"

    def recalculate(self):
        started = perf_counter()
        self._sync_customer_context()

        # ── Mode detection: delegate to static path when agent says so ──
        static_ctx = build_static_context(sales_person=self.sales_person)
        builder_mode = (getattr(self.flags, "pricing_builder_mode", "") or "").strip()
        if builder_mode == "Static":
            return self._recalculate_static(static_ctx, started)
        if builder_mode != "Dynamic" and static_ctx.get("pricing_mode") == STATIC_MODE:
            return self._recalculate_static(static_ctx, started)

        lines = self.lines or []
        self.projection_warnings = ""

        if not lines:
            self._reset_totals()
            self.applied_customs_policy = ""
            self.applied_benchmark_policy = ""
            self.calculated_on = now_datetime()
            self.calculated_by = frappe.session.user
            self.calc_runtime_ms = (perf_counter() - started) * 1000
            return

        item_codes = sorted({row.item for row in lines if row.item})
        self._validate_dynamic_line_items_in_allowed_buying_lists(item_codes)
        item_details = get_item_details_map(item_codes)
        item_groups = {code: (item_details.get(code) or {}).get("item_group") for code in item_codes}
        agent_discount_ctx = self._resolve_agent_discount_context()
        self._set_default_sales_person()
        self.allow_empty_expenses_policy = 1 if self._allow_policy_draft_mode() else 0
        self._apply_agent_dynamic_defaults()

        scenario_docs = self._collect_scenarios_or_throw(lines)

        customs_policy = self._resolve_customs_policy()
        self.applied_customs_policy = customs_policy.name if customs_policy else ""

        # Resolve pricing policy (formerly benchmark policy)
        benchmark_policy_doc = self._resolve_benchmark_policy()
        fallback_margin = flt(getattr(benchmark_policy_doc, "fallback_margin_percent", None) or 10) if benchmark_policy_doc else 10
        self.applied_benchmark_policy = benchmark_policy_doc.name if benchmark_policy_doc else ""

        customs_policy_cache = {customs_policy.name: customs_policy} if customs_policy else {}
        benchmark_policy_cache = {benchmark_policy_doc.name: benchmark_policy_doc} if benchmark_policy_doc else {}

        warnings = []
        draft_policy_mode = self._should_skip_policy_defaults()
        has_mapping_benchmark_policy = self._has_active_mapping_policy("benchmark_policy")
        has_mapping_customs_policy = self._has_active_mapping_policy("customs_policy")
        tier_warning = self._get_dynamic_tier_staleness_warning()
        if tier_warning:
            warnings.append(tier_warning)
        if not benchmark_policy_doc and not has_mapping_benchmark_policy and not draft_policy_mode:
            warnings.append(_("No active margin & benchmark policy found; dynamic margin is disabled."))
        if not customs_policy and not has_mapping_customs_policy and not draft_policy_mode:
            warnings.append(_("No active customs policy found; customs costs default to zero."))
        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes, benchmark_policy_doc=benchmark_policy_doc)

        total_base = 0.0
        total_expenses = 0.0
        total_final = 0.0
        line_snapshots = []
        used_draft_policy_fallback = False
        emitted_modifier_warnings = set()

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
            row.static_list_price = 0
            row.resolved_selling_price_list = ""
            line_context = self._build_rule_context(row=row, item_details=item_details)
            scenario_name, source, scenario_rule = self._resolve_line_scenario(
                row,
                line_context=line_context,
            )
            if scenario_name == NO_EXPENSES_SCENARIO:
                used_draft_policy_fallback = True
            row.resolved_pricing_scenario = "" if scenario_name == NO_EXPENSES_SCENARIO else scenario_name
            row.scenario_source = source
            row.resolved_scenario_rule = self._format_scenario_rule(scenario_rule)

            cache = scenario_caches.get(scenario_name)
            if not cache:
                frappe.throw(_("Unable to resolve pricing cache for scenario {0}").format(scenario_name))

            effective_line_expenses = list(cache["line_expenses"])
            has_line_override = False

            self._set_buy_price_for_row(
                row,
                cache["buying_price_list"],
                cache["buy_prices"],
                buy_price_cache_by_list,
                force_refresh=True,
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

            storage_calc = self._compute_storage_for_row(
                row=row,
                qty=qty,
                item_details=item_details,
                storage_config=cache.get("storage_config") or {},
            )
            if storage_calc.get("warning"):
                warnings.append(_("Row {0}: {1}").format(row.idx, storage_calc.get("warning")))

            effective_line_expenses = self._inject_storage_expense(effective_line_expenses, storage_calc)

            row_benchmark_policy = self._resolve_row_benchmark_policy(scenario_rule, benchmark_policy_doc, benchmark_policy_cache)
            effective_line_expenses = self._strip_scenario_margin_expenses(effective_line_expenses)

            # --- Benchmark-driven margin resolution ---
            benchmark_result = None
            landed_cost = base_unit
            margin_source = ""
            row_tier_mod, row_zone_mod, modifier_warning = self._resolve_segmentation_modifiers()
            if modifier_warning and modifier_warning not in emitted_modifier_warnings:
                warnings.append(modifier_warning)
                emitted_modifier_warnings.add(modifier_warning)

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
                        effective_line_expenses,
                        benchmark_result,
                        row_benchmark_policy,
                        base_unit,
                        landed_cost,
                    )
                    margin_source = "Fallback" if benchmark_result.get("is_fallback") else "Benchmark & Rule"
                    
                for w in (benchmark_result or {}).get("warnings") or []:
                    warnings.append(_("Row {0}: {1}").format(row.idx, w))
            else:
                if not draft_policy_mode:
                    warnings.append(_("Row {0}: no margin & benchmark policy found; margin is 0.").format(row.idx))

            # --- Inject dynamic modifiers (Tier & Zone) ---
            modifier_basis = (getattr(row_benchmark_policy, "margin_application_basis", "") or "Base Price").strip() or "Base Price"
            effective_line_expenses, row_tier_mod, row_zone_mod = self._inject_modifier_expenses(
                effective_line_expenses,
                row_tier_mod,
                row_zone_mod,
                modifier_basis=modifier_basis,
                base_unit=base_unit,
                loaded_cost=landed_cost if row_benchmark_policy else base_unit,
            )

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
                    "has_line_override": has_line_override,
                    "customs_calc": customs_calc,
                    "transport_calc": transport_calc,
                    "storage_calc": storage_calc,
                    "benchmark_result": benchmark_result,
                    "margin_source": margin_source,
                    "landed_cost": landed_cost,
                    "margin_application_basis": modifier_basis,
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

        floor_violations = 0
        customs_total_applied = 0.0

        for snap in line_snapshots:
            row = snap["row"]
            qty = snap["qty"]
            base_unit = snap["base_unit"]
            base_amount = snap["base_amount"]
            pricing = snap["pricing"]
            customs_calc = snap.get("customs_calc") or {}
            transport_calc = snap.get("transport_calc") or {}
            storage_calc = snap.get("storage_calc") or {}
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

            steps = list(pricing["steps"])
            component_summary = self._summarize_pricing_components(steps, qty, allocated_sheet)
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

            row.expense_unit_price = flt(component_summary.get("policy_expense_unit") or 0)
            row.expense_total = flt(component_summary.get("policy_expense_total") or 0)
            row.projected_unit_price = projected_unit
            row.projected_total_price = projected_total
            row.customs_unit_amount = flt(customs_calc.get("applied") or 0) / qty if qty else 0
            row.margin_unit_amount = flt(component_summary.get("margin_unit") or 0)
            row.margin_total_amount = flt(component_summary.get("margin_total") or 0)
            row.tier_modifier_amount = flt(component_summary.get("tier_unit") or 0)
            row.tier_modifier_total = flt(component_summary.get("tier_total") or 0)
            row.zone_modifier_amount = flt(component_summary.get("zone_unit") or 0)
            row.zone_modifier_total = flt(component_summary.get("zone_total") or 0)
            row.total_margin_unit_amount = flt(row.margin_unit_amount) + flt(row.tier_modifier_amount) + flt(row.zone_modifier_amount)
            row.total_margin_total_amount = flt(row.margin_total_amount) + flt(row.tier_modifier_total) + flt(row.zone_modifier_total)
            row.margin_basis = snap.get("margin_application_basis") or "Base Price"
            row.margin_pct = compute_margin_percent_for_basis(
                row.margin_unit_amount,
                row.margin_basis,
                base_unit,
                snap.get("landed_cost") or base_unit,
            )
            row.total_margin_pct = compute_margin_percent_for_basis(
                row.total_margin_unit_amount,
                row.margin_basis,
                base_unit,
                snap.get("landed_cost") or base_unit,
            )
            row.pricing_breakdown_json = json.dumps(steps)
            row.breakdown_preview = self._build_breakdown_preview(steps)
            row.has_scenario_override = 1 if cache_has_override_steps(steps, source="sheet") else 0
            row.has_line_override = 1 if snap.get("has_line_override") or cache_has_override_steps(steps, source="line") else 0
            br = snap.get("benchmark_result") or {}
            matched_br = br.get("matched_rule") or {}

            row.is_manual_override = 1 if flt(row.manual_sell_unit_price) > 0 else 0
            row.final_sell_unit_price = flt(row.manual_sell_unit_price) if row.is_manual_override else projected_unit
            if row.is_manual_override:
                manual_margin = flt(row.final_sell_unit_price) - base_unit - flt(row.expense_unit_price or 0) - flt(row.customs_unit_amount or 0)
                row.margin_unit_amount = manual_margin
                row.margin_total_amount = row.margin_unit_amount * qty
                row.total_margin_unit_amount = flt(row.margin_unit_amount) + flt(row.tier_modifier_amount) + flt(row.zone_modifier_amount)
                row.total_margin_total_amount = flt(row.margin_total_amount) + flt(row.tier_modifier_total) + flt(row.zone_modifier_total)
                row.margin_pct = compute_margin_percent_for_basis(
                    row.margin_unit_amount,
                    row.margin_basis,
                    base_unit,
                    snap.get("landed_cost") or base_unit,
                )
                row.total_margin_pct = compute_margin_percent_for_basis(
                    row.total_margin_unit_amount,
                    row.margin_basis,
                    base_unit,
                    snap.get("landed_cost") or base_unit,
                )
            row.final_sell_total = flt(row.final_sell_unit_price) * qty
            row.resolved_margin_rule = matched_br.get("label") if matched_br else (snap.get("benchmark_rule_label") or "")
            row.customs_material = customs_calc.get("material") or ""
            row.customs_tariff_number = customs_calc.get("tariff_number") or ""
            row.customs_weight_kg = flt(customs_calc.get("weight_kg") or 0)
            row.customs_value_per_kg = flt(customs_calc.get("value_per_kg") or 0)
            row.customs_base_value = flt(customs_calc.get("base_value") or 0)
            row.customs_total_percent = flt(customs_calc.get("total_percent") or 0)
            row.customs_rate_per_kg = flt(customs_calc.get("rate_per_kg") or 0)
            row.customs_rate_percent = flt(customs_calc.get("rate_percent") or 0)
            row.customs_by_kg = flt(customs_calc.get("by_kg") or 0)
            row.customs_by_percent = flt(customs_calc.get("by_percent") or 0)
            row.customs_applied = flt(customs_calc.get("applied") or 0)
            row.packaging_profile_source = customs_calc.get("packaging_source") or ""
            row.customs_basis = customs_calc.get("basis") or ""
            row.transport_allocation_mode = transport_calc.get("mode") or ""
            row.transport_container_type = transport_calc.get("container_type") or ""
            row.transport_basis_total = flt(transport_calc.get("denominator") or 0)
            row.transport_numerator = flt(transport_calc.get("numerator") or 0)
            row.transport_allocated = flt(transport_calc.get("applied") or 0)
            self._apply_line_discount_and_commission(
                row,
                qty=qty,
                benchmark_result=br,
                fallback_max_discount_percent=flt(getattr(row_benchmark_policy, "fallback_max_discount_percent", 0) or 0),
                agent_discount_ctx=agent_discount_ctx,
                steps=steps,
            )

            # Benchmark trace fields
            row.benchmark_reference = flt(br.get("benchmark_reference") or 0)
            row.benchmark_source_count = cint(br.get("source_count") or 0)
            row.benchmark_ratio = flt(br.get("ratio") or 0)
            row.benchmark_method = br.get("method") or ""
            row.resolved_benchmark_rule = self._format_benchmark_rule(matched_br) if matched_br else ""
            row.margin_source = snap.get("margin_source") or ""

            row.price_floor_violation = 1 if flt(row.final_sell_unit_price) < 0 else 0
            if row.price_floor_violation:
                floor_violations += 1
                warnings.append(_("Row {0}: final unit price is below zero.").format(row.idx))

            # Benchmark status: prefer new policy reference, fall back to old single-source
            br_active = br and flt(br.get("benchmark_reference") or 0) > 0
            if br_active:
                # Fix 1: use new multi-source benchmark_reference for status
                row.benchmark_price = flt(br["benchmark_reference"])  # Fix 4: sync fields
                self._set_benchmark_status_from_reference(
                    row, flt(br["benchmark_reference"]), flt(row.final_sell_unit_price),
                )
            else:
                self._set_benchmark_status_from_reference(row, 0, flt(row.final_sell_unit_price))

            total_expenses += flt(row.expense_total) + flt(row.customs_applied) + flt(row.margin_total_amount) + flt(row.tier_modifier_total) + flt(row.zone_modifier_total)
            total_final += flt(row.final_sell_total)
            customs_total_applied += flt(row.customs_applied)

        if used_draft_policy_fallback:
            warnings.append(
                _("Some lines do not have an active Policy Mapping yet. This Pricing Sheet is saved as a draft until you add a fallback mapping or line-level Expenses Policy.")
            )

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
            "PricingSheet %s recalculated in %.2fms (lines=%s, floor_violations=%s)",
            self.name or "NEW",
            flt(self.calc_runtime_ms),
            len(lines),
            floor_violations,
        )

    def _recalculate_static(self, static_ctx, started):
        """Price lines from the agent's selling price list instead of the dynamic engine."""
        lines = self.lines or []
        self.projection_warnings = ""
        warnings = []
        benchmark_policy_doc = self._resolve_static_benchmark_policy()
        tier_mod, zone_mod, modifier_warning = self._resolve_segmentation_modifiers()
        if modifier_warning:
            warnings.append(modifier_warning)
        modifier_basis = "Base Price"
        agent_discount_ctx = self._resolve_agent_discount_context()

        if not lines:
            self._reset_totals()
            self.applied_benchmark_policy = benchmark_policy_doc.name if benchmark_policy_doc else ""
            self.applied_customs_policy = ""
            self.resolved_mode = "Static"
            self.calculated_on = now_datetime()
            self.calculated_by = frappe.session.user
            self.calc_runtime_ms = (perf_counter() - started) * 1000
            return

        if self._is_restricted_agent_user():
            self._enforce_restricted_static_agent_context(static_ctx)

        price_lists = self._resolve_static_selling_price_lists(static_ctx)
        if not price_lists:
            frappe.throw(_("Select at least one Selling Price List before using static pricing."))
        self.selected_price_list = price_lists[0]

        # Bulk-fetch Item Prices in pricing currency plus builder metadata for discount caps.
        item_codes = list({row.item for row in lines if row.item})
        item_price_records, duplicate_warnings = get_latest_item_price_records_from_lists(
            item_codes,
            price_lists,
            buying=False,
            target_currency=get_pricing_currency(),
        )
        warnings.extend(duplicate_warnings)

        total_buy = 0.0
        total_expenses = 0.0
        total_final = 0.0
        missing = []

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            item_price_record = item_price_records.get(row.item) or {}
            list_price = item_price_record.get("price_list_rate")
            if list_price is None:
                missing.append(row.item or f"Row {row.idx}")
                list_price = 0.0

            row.static_list_price = list_price
            row.resolved_selling_price_list = item_price_record.get("price_list") or ""
            modifier_expenses, _tier_mod, _zone_mod = self._inject_modifier_expenses(
                [],
                tier_mod,
                zone_mod,
                modifier_basis=modifier_basis,
                base_unit=list_price,
                loaded_cost=list_price,
            )
            pricing = apply_expenses(base_unit=list_price, qty=qty, expenses=modifier_expenses)
            component_summary = self._summarize_pricing_components(pricing.get("steps") or [], qty)
            projected_unit = flt(pricing.get("projected_unit") or 0)
            projected_total = flt(pricing.get("projected_line") or 0)
            row.is_manual_override = 1 if flt(row.manual_sell_unit_price) > 0 else 0
            row.final_sell_unit_price = flt(row.manual_sell_unit_price) if row.is_manual_override else projected_unit
            row.final_sell_total = row.final_sell_unit_price * qty

            has_builder_stamp = bool((item_price_record.get("custom_pricing_builder") or "").strip())
            row.base_amount = 0.0
            row.target_margin_percent = flt(item_price_record.get("custom_target_margin_percent") or 0) if has_builder_stamp else 0.0
            row.builder_margin_percent = flt(item_price_record.get("custom_final_margin_percent") or 0) if has_builder_stamp else 0.0
            row.builder_price_overridden = 1 if has_builder_stamp and cint(item_price_record.get("custom_builder_price_overridden") or 0) else 0
            row.pricing_builder = (item_price_record.get("custom_pricing_builder") or "") if has_builder_stamp else ""
            row.builder_source_buying_price_list = (item_price_record.get("custom_source_buying_price_list") or "") if has_builder_stamp else ""
            row.margin_pct = flt(row.builder_margin_percent)
            row.buy_price = flt(item_price_record.get("custom_last_builder_buy_rate") or 0) if has_builder_stamp else 0
            row.expense_total = flt(item_price_record.get("custom_builder_expense_amount") or 0) * qty if has_builder_stamp else 0.0
            row.expense_unit_price = flt(item_price_record.get("custom_builder_expense_amount") or 0) if has_builder_stamp else 0.0
            row.projected_unit_price = projected_unit
            row.projected_total_price = projected_total
            row.customs_unit_amount = flt(item_price_record.get("custom_builder_customs_amount") or 0) if has_builder_stamp else 0.0
            row.customs_applied = row.customs_unit_amount * qty if has_builder_stamp else 0.0
            row.margin_basis = (item_price_record.get("custom_builder_margin_basis") or "").strip() or "Base Price" if has_builder_stamp else (getattr(row, "margin_basis", "") or "Base Price")
            if has_builder_stamp:
                pct = flt(row.builder_margin_percent)
                basis = row.margin_basis
                if basis == "Sale Price":
                    row.margin_unit_amount = flt(list_price) * pct / (100.0 - pct) if pct > 0 and pct < 100 else 0.0
                elif basis == "Loaded Cost":
                    landed = flt(row.buy_price) + flt(row.expense_unit_price) + flt(row.customs_unit_amount)
                    row.margin_unit_amount = landed * pct / 100.0 if landed > 0 else 0.0
                else:
                    row.margin_unit_amount = flt(list_price) * pct / 100.0
                row.margin_total_amount = row.margin_unit_amount * qty
            else:
                row.margin_unit_amount = 0.0
                row.margin_total_amount = 0.0
            row.tier_modifier_amount = flt(component_summary.get("tier_unit") or 0)
            row.tier_modifier_total = flt(component_summary.get("tier_total") or 0)
            row.zone_modifier_amount = flt(component_summary.get("zone_unit") or 0)
            row.zone_modifier_total = flt(component_summary.get("zone_total") or 0)
            total_margin_base_unit = list_price
            total_margin_landed_cost = list_price
            if has_builder_stamp and row.is_manual_override:
                landed_cost = flt(row.buy_price) + flt(row.expense_unit_price) + flt(row.customs_unit_amount)
                manual_margin = flt(row.final_sell_unit_price) - landed_cost
                row.margin_unit_amount = manual_margin
                row.margin_total_amount = row.margin_unit_amount * qty
                row.margin_pct = compute_margin_percent_for_basis(
                    row.margin_unit_amount,
                    row.margin_basis,
                    row.buy_price,
                    landed_cost,
                )
                row.builder_margin_percent = row.margin_pct
                total_margin_base_unit = row.buy_price
                total_margin_landed_cost = landed_cost
            row.total_margin_unit_amount = flt(row.margin_unit_amount) + flt(row.tier_modifier_amount) + flt(row.zone_modifier_amount)
            row.total_margin_total_amount = flt(row.margin_total_amount) + flt(row.tier_modifier_total) + flt(row.zone_modifier_total)
            row.total_margin_pct = compute_margin_percent_for_basis(
                row.total_margin_unit_amount,
                row.margin_basis,
                total_margin_base_unit,
                total_margin_landed_cost,
            )

            # Clear dynamic-only fields
            row.resolved_pricing_scenario = ""
            row.scenario_source = ""
            row.benchmark_reference = 0
            row.benchmark_ratio = 0
            row.benchmark_status = "No Benchmark"
            has_modifiers = flt(row.tier_modifier_total) or flt(row.zone_modifier_total)
            row.margin_source = "Builder Stamp" if has_builder_stamp else "Unstamped Static List"
            row.customs_material = ""
            row.customs_tariff_number = ""
            row.customs_weight_kg = 0
            row.customs_value_per_kg = 0
            row.customs_base_value = 0
            row.customs_total_percent = 0
            row.customs_rate_per_kg = 0
            row.customs_rate_percent = 0
            row.customs_by_kg = 0
            row.customs_by_percent = 0
            row.customs_basis = ""
            static_benchmark_result, static_fallback_max_discount = build_static_item_price_discount_context(
                item_price_record,
                benchmark_policy_doc,
            )
            self._apply_line_discount_and_commission(
                row,
                qty=qty,
                benchmark_result=static_benchmark_result,
                fallback_max_discount_percent=static_fallback_max_discount,
                agent_discount_ctx=agent_discount_ctx,
                steps=pricing.get("steps") or [],
            )
            row.pricing_breakdown_json = json.dumps(pricing.get("steps") or [])
            row.breakdown_preview = self._build_breakdown_preview(pricing.get("steps") or []) or f"List: {row.resolved_selling_price_list}"
            row.price_floor_violation = 0
            row.has_scenario_override = 0
            row.has_line_override = 0
            row.resolved_benchmark_rule = (item_price_record.get("custom_benchmark_rule_label") or "") if has_builder_stamp else ("Static List Modifiers" if has_modifiers else "")

            total_buy += flt(row.base_amount)
            total_expenses += flt(row.tier_modifier_total) + flt(row.zone_modifier_total)
            total_final += flt(row.final_sell_total)

        if missing:
            frappe.throw(_("{0} item(s) have no selling price in the selected lists ({1}): {2}").format(
                len(missing), ", ".join(price_lists), ", ".join(missing[:10])
            ))

        self.total_buy = flt(total_buy)
        self.total_expenses = flt(total_expenses)
        self.total_selling = flt(total_final)
        self.customs_total_applied = 0.0
        self.applied_benchmark_policy = benchmark_policy_doc.name if benchmark_policy_doc else ""
        self.applied_customs_policy = ""
        self.resolved_mode = "Static"
        self.projection_warnings = "\n".join(warnings)
        self.calculated_on = now_datetime()
        self.calculated_by = frappe.session.user
        self.calc_runtime_ms = (perf_counter() - started) * 1000

    @frappe.whitelist()
    def get_quotation_preview(self):
        lines = self.lines or []
        detailed_count = len([row for row in lines if cint(row.show_in_detail)])
        grouped_count = len(self._build_grouped_totals())
        total_tax = sum(flt(getattr(row, "custom_applied_taxes", 0) or 0) for row in lines)
        total_ttc = sum(
            flt(getattr(row, "custom_pt_ttc", 0) or 0)
            or flt(getattr(row, "discounted_sell_total", 0) or getattr(row, "final_sell_total", 0) or 0)
            for row in lines
        )
        return {
            "line_count": len(lines),
            "detailed_count": detailed_count,
            "grouped_count": grouped_count,
            "total_buy": flt(self.total_buy),
            "total_final": flt(self.total_selling),
            "total_tax": flt(total_tax),
            "total_ttc": flt(total_ttc),
            "customs_total": flt(self.customs_total_applied),
            "warnings": self.projection_warnings or "",
        }

    @frappe.whitelist()
    def refresh_buy_prices(self):
        if (getattr(self.flags, "pricing_builder_mode", "") or "").strip() == "Static":
            self.recalculate()
            self.save(ignore_permissions=True)
            return self.name

        lines = self.lines or []
        item_codes = sorted({row.item for row in lines if row.item})
        item_details = get_item_details_map(item_codes)
        scenario_docs = self._collect_scenarios_or_throw(lines)
        scenario_caches = self._build_scenario_caches(scenario_docs, item_codes)

        buy_price_cache_by_list = {
            cache.get("buying_price_list"): cache.get("buy_prices") or {}
            for cache in scenario_caches.values()
            if cache.get("buying_price_list")
        }

        for row in lines:
            context = self._build_rule_context(row=row, item_details=item_details)
            scenario_name, source, _scenario_rule = self._resolve_line_scenario(row, line_context=context)
            row.resolved_pricing_scenario = "" if scenario_name == NO_EXPENSES_SCENARIO else scenario_name
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
        bundle_name = product_bundle or getattr(self, "product_bundle", "")
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
        default_line_scenario = self.pricing_scenario

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

        if hasattr(self, "product_bundle"):
            self.product_bundle = bundle_name
        self.refresh_buy_prices()
        return self.name

    @frappe.whitelist()
    def get_dimensioning_config(self):
        if not self.dimensioning_set:
            return {"set": None, "values": {}}
        set_doc = self._get_dimensioning_set_doc(self.dimensioning_set)
        return {
            "set": self._serialize_dimensioning_set(set_doc),
            "values": self._get_dimensioning_values(),
        }

    @frappe.whitelist()
    def recalculate_preview(self):
        self.recalculate()
        return {
            "total_buy": flt(self.total_buy),
            "total_expenses": flt(self.total_expenses),
            "total_selling": flt(self.total_selling),
            "customs_total_applied": flt(self.customs_total_applied),
            "projection_warnings": self.projection_warnings or "",
            "resolved_mode": self.resolved_mode or "",
        }

    @frappe.whitelist()
    def add_dimensioning_items(self, input_values_json=None, replace_existing_generated=1):
        if not self.dimensioning_set:
            frappe.throw(_("Please select a Dimensioning Set."))

        set_doc = self._get_dimensioning_set_doc(self.dimensioning_set)
        values = self._coerce_dimensioning_inputs(
            set_doc,
            input_values_json=input_values_json,
        )
        generated_rows = self._generate_dimensioning_rows(set_doc, values)
        unresolved_rows = [row for row in generated_rows if not (row.get("item") or "").strip()]
        if unresolved_rows:
            messages = [row.get("resolution_warning") or row.get("rule_label") or _("Unresolved item") for row in unresolved_rows]
            frappe.throw(_("Resolve Dimensioning item filters before adding lines: {0}").format("; ".join(messages)))
        if not generated_rows:
            frappe.throw(_("No items were generated from the current dimensioning values."))

        self.dimensioning_inputs_json = json.dumps(values)

        if cint(replace_existing_generated):
            kept = [
                row for row in (self.lines or [])
                if (getattr(row, "dimensioning_set", "") or "") != set_doc.name
            ]
            self.set("lines", kept)

        for generated in generated_rows:
            self.append(
                "lines",
                {
                    "item": generated["item"],
                    "qty": generated["qty"],
                    "source_buying_price_list": self._resolve_source_buying_price_list(),
                    "display_group": generated["display_group"],
                    "show_in_detail": generated["show_in_detail"],
                    "dimensioning_set": set_doc.name,
                    "dimensioning_rule_label": generated["rule_label"],
                    "pricing_scenario": "",
                    "line_type": "Standard",
                },
            )

        self.refresh_buy_prices()
        return {
            "name": self.name,
            "added_count": len(generated_rows),
            "set_name": set_doc.name,
        }

    def _get_dimensioning_set_doc(self, set_name):
        if not frappe.db.exists("Dimensioning Set", set_name):
            frappe.throw(_("Dimensioning Set {0} does not exist.").format(set_name))
        doc = frappe.get_doc("Dimensioning Set", set_name)
        if cint(doc.is_active) != 1:
            frappe.throw(_("Dimensioning Set {0} is inactive.").format(set_name))
        return doc

    def _serialize_dimensioning_set(self, set_doc):
        return set_doc.serialize_config()

    def _get_dimensioning_values(self):
        raw = (self.dimensioning_inputs_json or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _coerce_dimensioning_inputs(self, set_doc, input_values_json=None):
        if input_values_json is None:
            raw_values = self._get_dimensioning_values()
        elif isinstance(input_values_json, str):
            raw_values = json.loads(input_values_json or "{}") if (input_values_json or "").strip() else {}
        else:
            raw_values = input_values_json or {}

        values = {}
        for field in self._safe_rows(set_doc.input_fields):
            key = field.field_key
            raw_value = raw_values.get(key, field.default_value)
            value = coerce_dimensioning_value(field.field_type, raw_value)
            if cint(field.is_required) and value in (None, "", False):
                frappe.throw(_("Dimensioning field {0} is required.").format(field.label or key))
            values[key] = value
        return values

    def _generate_dimensioning_rows(self, set_doc, values):
        return set_doc.preview_generated_items(values)

    def _safe_rows(self, rows):
        return rows or []

    def _allow_policy_draft_mode(self):
        return not self._is_restricted_agent_user()

    def _should_skip_policy_defaults(self):
        return self._allow_policy_draft_mode() and not self._get_active_policy_mappings()

    def _get_active_policy_mappings(self):
        return [row for row in (self.scenario_mappings or []) if cint(getattr(row, "is_active", 1))]

    def _get_fallback_policy_mapping(self):
        for row in self._get_active_policy_mappings():
            if not (getattr(row, "source_buying_price_list", "") or "").strip():
                return row
        return None

    def _has_active_mapping_policy(self, fieldname):
        for row in self._get_active_policy_mappings():
            if (getattr(row, fieldname, "") or "").strip():
                return True
        return False

    def _ensure_fallback_policy_mapping(self, pricing_scenario="", customs_policy="", benchmark_policy="", notes=""):
        pricing_scenario = (pricing_scenario or "").strip()
        if not pricing_scenario:
            return None

        customs_policy = (customs_policy or "").strip()
        benchmark_policy = (benchmark_policy or "").strip()
        fallback = self._get_fallback_policy_mapping()
        if fallback:
            if not fallback.pricing_scenario:
                fallback.pricing_scenario = pricing_scenario
            if customs_policy and not fallback.customs_policy:
                fallback.customs_policy = customs_policy
            if benchmark_policy and not fallback.benchmark_policy:
                fallback.benchmark_policy = benchmark_policy
            if not cint(getattr(fallback, "priority", 0)):
                fallback.priority = 10
            fallback.is_active = 1
            if notes and not fallback.notes:
                fallback.notes = notes
            return fallback

        row = self.append(
            "scenario_mappings",
            {
                "source_buying_price_list": "",
                "pricing_scenario": pricing_scenario,
                "customs_policy": customs_policy,
                "benchmark_policy": benchmark_policy,
                "priority": 10,
                "is_active": 1,
                "notes": notes,
            },
        )
        return row

    def _assert_mapping_value_allowed(self, value, allowed_values, message_template, row_label):
        value = (value or "").strip()
        if not value or not allowed_values:
            return
        if value in allowed_values:
            return
        frappe.throw(message_template.format(value, row_label, self.sales_person or "-"))

    def _assert_policy_rows_allowed(self, context):
        allowed_scenarios = context.get("allowed_pricing_scenarios") or []
        allowed_customs = context.get("allowed_customs_policies") or []
        allowed_benchmarks = context.get("allowed_benchmark_policies") or []

        for row in self._get_active_policy_mappings():
            row_label = _("mapping row {0}").format(row.idx)
            self._assert_mapping_value_allowed(
                row.pricing_scenario,
                allowed_scenarios,
                _("Expenses Policy {0} is not allowed for {1} (sales person {2})."),
                row_label,
            )
            self._assert_mapping_value_allowed(
                row.customs_policy,
                allowed_customs,
                _("Customs Policy {0} is not allowed for {1} (sales person {2})."),
                row_label,
            )
            self._assert_mapping_value_allowed(
                row.benchmark_policy,
                allowed_benchmarks,
                _("Margin & Benchmark Policy {0} is not allowed for {1} (sales person {2})."),
                row_label,
            )

    def _collect_scenarios_or_throw(self, lines):
        scenario_names = set()

        for row in lines:
            if row.pricing_scenario:
                scenario_names.add(row.pricing_scenario)

        for row in (self.scenario_mappings or []):
            if cint(row.is_active) and row.pricing_scenario:
                scenario_names.add(row.pricing_scenario)

        if not scenario_names and getattr(self, "allow_empty_expenses_policy", 0):
            return {
                NO_EXPENSES_SCENARIO: frappe._dict(
                    name=NO_EXPENSES_SCENARIO,
                    expenses=[],
                    transport_is_active=0,
                    transport_allocation_mode="",
                    transport_container_type="",
                    transport_container_price=0,
                    transport_total_kg=0,
                    transport_total_m3=0,
                    storage_is_active=0,
                    storage_cost_per_m3_per_month=0,
                    storage_duration_months=0,
                )
            }

        if not scenario_names:
            frappe.throw(_("Please configure at least one active Policy Mapping or line-level Expenses Policy."))

        docs = {}
        missing = []
        for name in scenario_names:
            if not frappe.db.exists("Pricing Scenario", name):
                missing.append(name)
                continue
            docs[name] = frappe.get_doc("Pricing Scenario", name)

        if missing:
            frappe.throw(_("Missing Expenses Policy record(s): {0}").format(", ".join(sorted(missing))))

        return docs

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
            "business_type": getattr(self, "crm_business_type", "") or "",
            "crm_business_type": getattr(self, "crm_business_type", "") or "",
            "crm_segment": getattr(self, "crm_segment", "") or "",
            "tier": self.tier,
            "item": item_code,
            "source_bundle": row.source_bundle,
            "item_group": item_meta.get("item_group"),
            "material": item_meta.get("custom_material"),
        }

    def _resolve_geography_context(self):
        geography_territory = (getattr(self, "geography_territory", "") or "").strip()
        if geography_territory:
            return {"geography_territory": geography_territory}

        customer = (getattr(self, "customer", "") or "").strip()
        territory = frappe.db.get_value("Customer", customer, "territory") if customer else None
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
        mapped_lists = sorted(
            {
                (getattr(row, "source_buying_price_list", "") or "").strip()
                for row in self._get_active_policy_mappings()
                if (getattr(row, "source_buying_price_list", "") or "").strip()
            }
        )
        if len(mapped_lists) == 1:
            return mapped_lists[0]

        context = build_dynamic_context(sales_person=self.sales_person)
        selected = context.get("selected") or {}
        buying_price_list = (selected.get("buying_price_list") or "").strip()
        if buying_price_list:
            return buying_price_list
        return ""

    def _resolve_static_selling_price_lists(self, static_ctx=None):
        selected = []
        seen = set()
        rows = sorted(
            [row for row in (getattr(self, "selected_selling_price_lists", None) or []) if cint(getattr(row, "is_active", 1))],
            key=lambda row: (cint(getattr(row, "sequence", 0) or 0), cint(getattr(row, "idx", 0) or 0)),
        )
        for row in rows:
            price_list = (getattr(row, "price_list", "") or "").strip()
            if price_list and price_list not in seen:
                selected.append(price_list)
                seen.add(price_list)

        legacy = (getattr(self, "selected_price_list", "") or "").strip()
        if legacy and legacy not in seen:
            selected.append(legacy)
            seen.add(legacy)

        if selected:
            return selected

        static_ctx = static_ctx if static_ctx is not None else build_static_context(sales_person=self.sales_person)
        for price_list in static_ctx.get("selling_price_lists") or []:
            price_list = (price_list or "").strip()
            if price_list and price_list not in seen:
                selected.append(price_list)
                seen.add(price_list)
        return selected

    def _resolve_dynamic_allowed_buying_price_lists(self):
        selected = []
        seen = set()
        for row in self._get_active_policy_mappings():
            price_list = (getattr(row, "source_buying_price_list", "") or "").strip()
            if price_list and price_list not in seen:
                selected.append(price_list)
                seen.add(price_list)
        if selected:
            return selected

        context = build_dynamic_context(sales_person=self.sales_person)
        for price_list in context.get("allowed_buying_price_lists") or []:
            price_list = (price_list or "").strip()
            if price_list and price_list not in seen:
                selected.append(price_list)
                seen.add(price_list)
        return selected

    def _validate_dynamic_line_items_in_allowed_buying_lists(self, item_codes):
        allowed_lists = self._resolve_dynamic_allowed_buying_price_lists()
        if not item_codes or not allowed_lists:
            return
        priced_items = get_item_codes_with_prices(item_codes, allowed_lists, buying=True)
        missing = [item_code for item_code in item_codes if item_code not in priced_items]
        if missing:
            frappe.throw(_("{0} item(s) have no buying price in the selected buying lists ({1}): {2}").format(
                len(missing), ", ".join(allowed_lists), ", ".join(missing[:10])
            ))

    def _is_restricted_agent_user(self):
        user = frappe.session.user
        if not user or user == "Administrator":
            return False

        roles = set(frappe.get_roles(user) or [])
        return bool(roles & RESTRICTED_AGENT_ROLES) and not (roles & PRIVILEGED_PRICING_ROLES)

    def _can_create_quotation_as_commercial_user(self):
        roles = set(frappe.get_roles(frappe.session.user) or [])
        return bool(roles & QUOTATION_CAPABLE_COMMERCIAL_ROLES)

    def _enforce_agent_pricing_inputs(self):
        if not self._is_restricted_agent_user():
            return

        self._set_default_sales_person()
        if not (self.sales_person or "").strip():
            frappe.throw(_("Link this user to a Sales Person before creating commercial pricing sheets."))

        static_ctx = build_static_context(sales_person=self.sales_person)
        self._enforce_restricted_static_agent_context(static_ctx)

        for row in self.lines or []:
            row.source_buying_price_list = ""
            row.pricing_scenario = ""

    def _enforce_restricted_static_agent_context(self, static_ctx=None):
        static_ctx = static_ctx if static_ctx is not None else build_static_context(sales_person=self.sales_person)
        pricing_mode = (static_ctx.get("pricing_mode") or "").strip()
        if not pricing_mode:
            frappe.throw(_("No Agent Pricing Rules found for selected sales person."))
        if pricing_mode != STATIC_MODE:
            frappe.throw(
                _("Commercial users must use Agent Pricing Rules in Published Selling Price List mode.")
            )

        lists = [price_list for price_list in (static_ctx.get("selling_price_lists") or []) if price_list]
        if not lists:
            frappe.throw(_("Add at least one active selling price list to this agent rule."))

        requested_price_list = (self.selected_price_list or "").strip()
        if requested_price_list and requested_price_list not in lists:
            frappe.throw(
                _("Selling Price List {0} is not allowed for sales person {1}.").format(
                    requested_price_list,
                    self.sales_person or "-",
                )
            )
        for price_list in self._resolve_static_selling_price_lists({"selling_price_lists": []}):
            if price_list not in lists:
                frappe.throw(
                    _("Selling Price List {0} is not allowed for sales person {1}.").format(
                        price_list,
                        self.sales_person or "-",
                    )
                )
        self.selected_price_list = requested_price_list or lists[0]
        return lists

    def _resolve_sheet_scenario_mapping(self, context):
        rules = [
            {
                "pricing_scenario": getattr(row, "pricing_scenario", ""),
                "source_buying_price_list": getattr(row, "source_buying_price_list", ""),
                "customs_policy": getattr(row, "customs_policy", ""),
                "benchmark_policy": getattr(row, "benchmark_policy", ""),
                "business_type": getattr(row, "business_type", ""),
                "crm_business_type": getattr(row, "business_type", ""),
                "crm_segment": getattr(row, "crm_segment", ""),
                "priority": cint(getattr(row, "priority", 10) or 10),
                "sequence": cint(getattr(row, "idx", 0) or 0),
                "is_active": cint(getattr(row, "is_active", 1)),
                "idx": cint(getattr(row, "idx", 0) or 0),
            }
            for row in (self.scenario_mappings or [])
        ]
        return resolve_scenario_rule(rules, context=context)

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
                benchmark_price_map[pl] = get_latest_item_prices(item_codes, pl, buying=None, target_currency=get_pricing_currency())

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
            if self._is_restricted_agent_user():
                self._enforce_restricted_static_agent_context(static_ctx)
                return
            if not self.selected_price_list:
                lists = static_ctx.get("selling_price_lists") or []
                if lists:
                    self.selected_price_list = lists[0]
            return

        if self._is_restricted_agent_user():
            self._enforce_restricted_static_agent_context(static_ctx)

        context = build_dynamic_context(sales_person=self.sales_person)
        if context.get("pricing_mode") != DYNAMIC_MODE:
            return

        selected = context.get("selected") or {}
        if self._is_restricted_agent_user():
            self._ensure_fallback_policy_mapping(
                pricing_scenario=selected.get("pricing_scenario"),
                customs_policy=selected.get("customs_policy"),
                benchmark_policy=selected.get("benchmark_policy"),
                notes=_("Agent fallback mapping"),
            )

        self._assert_policy_rows_allowed(context)

        allowed_scenarios = context.get("allowed_pricing_scenarios") or []
        if allowed_scenarios:
            for row in self.lines or []:
                row_scenario = (row.get("pricing_scenario") or "").strip()
                if row_scenario and row_scenario not in allowed_scenarios:
                    frappe.throw(
                        _("Line {0}: Expenses Policy {1} is not allowed for sales person {2}.").format(
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
        party_type = self._pricing_party_type()
        party_name = self._pricing_party_name()
        if not party_name:
            self.customer_type = ""
            self.tier = ""
            self.crm_business_type = ""
            self.crm_segment = ""
            return

        self.customer_type = ""
        self.tier = self._resolve_party_pricing_tier(party_type, party_name)
        if party_type == "Customer":
            crm_context = resolve_customer_crm_pricing_context(
                party_name,
                selected_business_type=getattr(self, "crm_business_type", "") or "",
                selected_segment=getattr(self, "crm_segment", "") or "",
            )
        else:
            crm_context = resolve_party_crm_pricing_context(
                party_type,
                party_name,
                selected_business_type=getattr(self, "crm_business_type", "") or "",
                selected_segment=getattr(self, "crm_segment", "") or "",
            )
        selected = crm_context.get("selected") or {}
        self.crm_business_type = selected.get("business_type") or ""
        self.crm_segment = selected.get("crm_segment") or ""

    def _pricing_party_type(self):
        party_type = (getattr(self, "party_type", "") or "").strip()
        if not party_type and (getattr(self, "customer", "") or "").strip():
            party_type = "Customer"
        return party_type or "Customer"

    def _pricing_party_name(self):
        return (getattr(self, "party_name", "") or getattr(self, "customer", "") or "").strip()

    def _resolve_party_pricing_tier(self, party_type, party_name):
        if party_type == "Customer":
            customer_fields = ["tier"]
            if frappe.db.has_column("Customer", "enable_dynamic_segmentation"):
                customer_fields.append("enable_dynamic_segmentation")
            customer_values = frappe.db.get_value("Customer", party_name, customer_fields, as_dict=True) or {}
            return self._resolve_customer_pricing_tier(customer_values, customer=party_name)

        fields = [field for field in ("manual_tier", "tier") if frappe.db.has_column(party_type, field)]
        if not fields:
            return ""
        values = frappe.db.get_value(party_type, party_name, fields, as_dict=True) or {}
        return (values.get("manual_tier") or values.get("tier") or "").strip()

    def _resolve_customer_pricing_tier(self, customer_values, customer=None):
        stored_tier = (customer_values.get("tier") or "").strip()
        if cint(customer_values.get("enable_dynamic_segmentation") or 0) != 1:
            return stored_tier

        from orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine import (
            calculate_customer_dynamic_tier,
        )

        result = calculate_customer_dynamic_tier(customer=customer or self.customer, apply=1) or {}
        return (result.get("tier") or stored_tier).strip()

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

        if self._should_skip_policy_defaults():
            return None

        policy_doc = None
        fallback_mapping = self._get_fallback_policy_mapping()
        mapping_policy = (getattr(fallback_mapping, "customs_policy", "") or "").strip() if fallback_mapping else ""
        if mapping_policy and frappe.db.exists("Pricing Customs Policy", mapping_policy):
            policy_doc = frappe.get_doc("Pricing Customs Policy", mapping_policy)
        elif self.customs_policy and frappe.db.exists("Pricing Customs Policy", self.customs_policy):
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
        tariff_number = (details.get("customs_tariff_number") or "").strip().upper()
        material = (details.get("custom_customs_material") or details.get("custom_material") or "").strip().upper()
        unit_weight_kg = flt(details.get("custom_weight_kg"))
        qty = flt(row.qty)
        packaging_profile = getattr(row, "custom_packaging_profile", None) or None

        resolution = get_packaging_resolution(
            item_code=row.item,
            packaging_profile=packaging_profile,
            qty=qty,
            uom=None,
        ) or {}

        resolved_weight_kg = flt(resolution.get("weight_kg") or 0)
        if resolved_weight_kg <= 0:
            resolved_weight_kg = unit_weight_kg
            resolution["resolved_source"] = "item_fallback"

        resolved_tariff = (resolution.get("customs_tariff_number") or "").strip().upper()
        if not resolved_tariff:
            resolved_tariff = tariff_number

        packaging_source = resolution.get("resolved_source", "item_fallback")
        package_count = resolution.get("package_count", qty)
        units_per_package = flt(resolution.get("units_per_package") or 1) or 1
        stock_qty = flt(resolution.get("stock_qty") or qty)
        unit_customs_weight_kg = resolved_weight_kg
        if packaging_source != "item_fallback" and units_per_package > 0:
            unit_customs_weight_kg = resolved_weight_kg / units_per_package

        out = {
            "tariff_number": resolved_tariff,
            "material": material,
            "weight_kg": 0.0,
            "unit_weight_kg": unit_customs_weight_kg,
            "package_weight_kg": resolved_weight_kg,
            "units_per_package": units_per_package,
            "stock_qty": stock_qty,
            "packaging_source": packaging_source,
            "package_count": package_count,
            "value_per_kg": 0.0,
            "base_value": 0.0,
            "total_percent": 0.0,
            "rate_per_kg": 0.0,
            "rate_percent": 0.0,
            "by_kg": 0.0,
            "by_percent": 0.0,
            "applied": 0.0,
            "basis": "",
            "mode": "",
            "warning": "",
        }

        if not customs_policy:
            return out

        if not resolved_tariff and not material:
            out["warning"] = _("item Customs Tariff Number is missing; customs set to 0")
            return out

        rule_dicts = [
            {
                "tariff_number": getattr(rule, "tariff_number", ""),
                "material": rule.material,
                "value_per_kg": flt(getattr(rule, "value_per_kg", 0) or 0),
                "rate_components": getattr(rule, "rate_components", "") or "",
                "rate_per_kg": 0,
                "rate_percent": flt(rule.rate_percent),
                "sequence": cint(rule.sequence),
                "priority": cint(rule.priority),
                "is_active": cint(rule.is_active),
                "idx": cint(rule.idx),
            }
            for rule in (customs_policy.customs_rules or [])
        ]
        rule = resolve_customs_rule(rule_dicts, tariff_number=resolved_tariff, material=material)
        if not rule:
            identifier = resolved_tariff or material or _("missing tariff")
            out["warning"] = _("no customs rule matched tariff/material {0}; customs set to 0").format(identifier)
            return out

        value_per_kg = flt(rule.get("value_per_kg") or 0)
        rate_components = rule.get("rate_components") or ""
        rate_per_kg = 0
        rate_percent = flt(rule.get("rate_percent"))
        total_weight_kg = stock_qty * unit_customs_weight_kg if packaging_source != "item_fallback" else qty * unit_customs_weight_kg
        out["weight_kg"] = total_weight_kg
        use_buying_amount_fallback = resolved_weight_kg <= 0 and flt(base_amount) > 0
        amounts = compute_customs_amount(
            base_amount=base_amount,
            qty=1,
            unit_weight_kg=total_weight_kg,
            rate_per_kg=rate_per_kg,
            rate_percent=rate_percent,
            value_per_kg=value_per_kg,
            rate_components=rate_components,
            base_amount_fallback=use_buying_amount_fallback,
        )

        out.update(
            {
                "mode": amounts.get("mode") or "",
                "value_per_kg": value_per_kg,
                "base_value": flt(amounts.get("base_value") or 0),
                "total_percent": flt(amounts.get("total_percent") or 0),
                "rate_per_kg": rate_per_kg,
                "rate_percent": flt(amounts.get("total_percent") or 0),
                "by_kg": flt(amounts.get("by_kg") or 0),
                "by_percent": flt(amounts.get("by_percent") or 0),
                "applied": flt(amounts.get("applied") or 0),
                "basis": amounts.get("basis") or "",
                "component_display": amounts.get("component_display") or "",
            }
        )
        self._apply_customs_value_delta_tax(out, base_amount, customs_policy)
        if use_buying_amount_fallback:
            out["warning"] = _("item Weight (kg) is missing; customs calculated from buying amount")
        elif resolved_weight_kg <= 0:
            out["warning"] = _("item Weight (kg) is missing; customs set to 0")
        return out

    def _apply_customs_value_delta_tax(self, customs_calc, base_amount, customs_policy):
        if not customs_policy or not cint(getattr(customs_policy, "enable_customs_value_delta_tax", 0) or 0):
            return
        customs_value = flt((customs_calc or {}).get("base_value") or 0)
        delta = customs_value - flt(base_amount or 0)
        if delta <= 0:
            customs_calc["customs_value_delta"] = 0.0
            customs_calc["customs_value_delta_tax_rate"] = 0.0
            customs_calc["customs_value_delta_tax_amount"] = 0.0
            customs_calc["customs_value_delta_tax_template"] = ""
            return

        template = (getattr(customs_policy, "customs_value_delta_tax_template", "") or "").strip()
        if not template:
            template = company_default_sales_taxes_template(self._resolve_modifier_company())
        rate = sales_tax_template_total_rate(template)
        amount = delta * rate / 100.0 if rate else 0.0
        customs_calc["customs_value_delta"] = flt(delta)
        customs_calc["customs_value_delta_tax_rate"] = flt(rate)
        customs_calc["customs_value_delta_tax_amount"] = flt(amount)
        customs_calc["customs_value_delta_tax_template"] = template
        customs_calc["applied"] = flt(customs_calc.get("applied") or 0) + flt(amount)

    def _append_customs_step(self, steps, qty, projected_unit, customs_calc):
        applied = flt((customs_calc or {}).get("applied") or 0)
        if applied <= 0:
            return

        delta_tax = flt((customs_calc or {}).get("customs_value_delta_tax_amount") or 0)
        base_customs = applied - delta_tax
        label = "Customs (Value/kg x weight x %)"

        steps.append(
            {
                "label": label,
                "type": "Fixed",
                "value": base_customs if delta_tax else applied,
                "applies_to": "Base Price",
                "scope": "Per Line",
                "sequence": 9998,
                "basis": 0,
                "delta_unit": 0,
                "delta_line": base_customs if delta_tax else applied,
                "delta_sheet": 0,
                "running_total": projected_unit,
                "customs_tariff_number": customs_calc.get("tariff_number") or "",
                "customs_base_value": flt(customs_calc.get("base_value") or 0),
                "customs_total_percent": flt(customs_calc.get("total_percent") or 0),
                "customs_by_kg": flt(customs_calc.get("by_kg") or 0),
                "customs_by_percent": flt(customs_calc.get("by_percent") or 0),
                "customs_basis": customs_calc.get("basis") or "",
                "customs_weight_kg": flt(customs_calc.get("weight_kg") or 0),
                "customs_unit_weight_kg": flt(customs_calc.get("unit_weight_kg") or 0),
                "customs_package_weight_kg": flt(customs_calc.get("package_weight_kg") or 0),
                "packaging_units_per_package": flt(customs_calc.get("units_per_package") or 0),
                "packaging_package_count": flt(customs_calc.get("package_count") or 0),
                "packaging_profile_source": customs_calc.get("packaging_source") or "",
            }
        )
        if delta_tax > 0:
            steps.append(
                {
                    "label": _("Customs Value Delta Tax"),
                    "type": "Fixed",
                    "value": delta_tax,
                    "applies_to": "Base Price",
                    "scope": "Per Line",
                    "sequence": 9999,
                    "basis": flt(customs_calc.get("customs_value_delta") or 0),
                    "delta_unit": 0,
                    "delta_line": delta_tax,
                    "delta_sheet": 0,
                    "running_total": projected_unit,
                    "customs_value_delta": flt(customs_calc.get("customs_value_delta") or 0),
                    "customs_value_delta_tax_rate": flt(customs_calc.get("customs_value_delta_tax_rate") or 0),
                    "customs_value_delta_tax_template": customs_calc.get("customs_value_delta_tax_template") or "",
                }
            )

    def _summarize_pricing_components(self, steps, qty, allocated_sheet=0.0):
        summary = {
            "policy_expense_unit": 0.0,
            "policy_expense_total": 0.0,
            "margin_unit": 0.0,
            "margin_total": 0.0,
            "tier_unit": 0.0,
            "tier_total": 0.0,
            "zone_unit": 0.0,
            "zone_total": 0.0,
        }

        for step in steps or []:
            source = (step.get("override_source") or "").strip()
            delta_unit = flt(step.get("delta_unit") or 0)
            delta_line = flt(step.get("delta_line") or 0)
            unit_amount = delta_unit + (delta_line / qty if qty else 0)
            total_amount = (delta_unit * qty) + delta_line

            if source == "pricing_policy":
                summary["margin_unit"] += unit_amount
                summary["margin_total"] += total_amount
            elif source == "tier_modifier":
                summary["tier_unit"] += unit_amount
                summary["tier_total"] += total_amount
            elif source == "zone_modifier":
                summary["zone_unit"] += unit_amount
                summary["zone_total"] += total_amount
            else:
                summary["policy_expense_unit"] += unit_amount
                summary["policy_expense_total"] += total_amount

        if allocated_sheet:
            summary["policy_expense_total"] += flt(allocated_sheet)
            summary["policy_expense_unit"] += flt(allocated_sheet) / qty if qty else 0

        return summary

    def _inject_margin_expense(self, expenses, margin_step):
        if not margin_step:
            return expenses

        out = list(expenses or [])
        out.append(margin_step)
        out = sorted(out, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx") or 0)))
        for exp in out:
            exp["expense_key"] = exp.get("expense_key") or make_expense_key(exp)
        return out

    def _resolve_segmentation_modifiers(self):
        """Resolve tier and zone modifiers from the Customer Segmentation Engine.

        Returns (tier_mod_dict, zone_mod_dict, warning) — each modifier is a
        dict with 'amount', 'type' ('Fixed'|'Percentage'), 'label', or None if
        no match.
        """
        company = self._resolve_modifier_company()
        if not company:
            return None, None, ""
        tier_mod, zone_mod, warning = resolve_global_pricing_modifiers(
            company=company,
            tier=(getattr(self, "tier", "") or "").strip(),
            business_type=(getattr(self, "crm_business_type", "") or "").strip(),
            crm_segment=(getattr(self, "crm_segment", "") or "").strip(),
            territory=self._resolve_modifier_territory(),
        )
        if not tier_mod:
            warning = warning or self._get_missing_segmentation_modifier_warning(company)
        return tier_mod, zone_mod, warning

    def _resolve_modifier_company(self):
        company = (getattr(self, "custom_company", "") or "").strip()
        if company:
            return company
        customer = (getattr(self, "customer", "") or "").strip()
        if customer and frappe.db.has_column("Customer", "custom_company"):
            return (frappe.db.get_value("Customer", customer, "custom_company") or "").strip()
        return ""

    def _resolve_modifier_territory(self):
        territory = (getattr(self, "geography_territory", "") or "").strip()
        if territory:
            return territory
        if not (getattr(self, "customer", "") or "").strip():
            return ""
        return (self._resolve_geography_context().get("geography_territory") or "").strip()

    def _get_missing_tier_modifier_warning(self, benchmark_policy_doc):
        if not self.customer or not benchmark_policy_doc:
            return ""
        if not frappe.db.has_column("Customer", "enable_dynamic_segmentation"):
            return ""

        is_dynamic = cint(
            frappe.db.get_value("Customer", self.customer, "enable_dynamic_segmentation") or 0
        )
        if is_dynamic != 1:
            return ""

        tier = (self.tier or "").strip()
        if not tier:
            return ""

        has_active_tier_modifiers = any(
            cint(row.get("is_active"))
            and any((row.get(fieldname) or "").strip() for fieldname in ("tier", "business_type", "crm_segment"))
            for row in (benchmark_policy_doc.get("tier_modifiers") or [])
        )
        if not has_active_tier_modifiers:
            return ""

        business_type = (getattr(self, "crm_business_type", "") or "").strip() or _("not set")
        crm_segment = (getattr(self, "crm_segment", "") or "").strip() or _("not set")
        return _(
            "Customer has Dynamic Segmentation enabled, but no active tier modifier matched Pricing Tier {0} in policy {1} for Business Type {2} / Segment {3}. Pricing continues without a tier modifier."
        ).format(tier, benchmark_policy_doc.name, business_type, crm_segment)

    def _get_missing_segmentation_modifier_warning(self, company):
        if not self.customer:
            return ""
        if not frappe.db.has_column("Customer", "enable_dynamic_segmentation"):
            return ""

        is_dynamic = cint(frappe.db.get_value("Customer", self.customer, "enable_dynamic_segmentation") or 0)
        if is_dynamic != 1:
            return ""

        tier = (self.tier or "").strip()
        if not tier:
            return ""

        engine_filters = {"is_active": 1}
        if frappe.db.has_column("Customer Segmentation Engine", "custom_company"):
            engine_filters["custom_company"] = company
        engine_name = frappe.db.get_value("Customer Segmentation Engine", engine_filters, "name")
        if not engine_name:
            return ""

        engine = frappe.get_doc("Customer Segmentation Engine", engine_name)
        has_active_tier_modifiers = any(
            cint(row.get("is_active"))
            and any((row.get(fieldname) or "").strip() for fieldname in ("tier", "business_type", "crm_segment"))
            for row in (engine.get("tier_modifiers") or [])
        )
        if not has_active_tier_modifiers:
            return ""

        business_type = (getattr(self, "crm_business_type", "") or "").strip() or _("not set")
        crm_segment = (getattr(self, "crm_segment", "") or "").strip() or _("not set")
        return _(
            "Customer has Dynamic Segmentation enabled, but no active global tier modifier matched Pricing Tier {0} in company {1} for Business Type {2} / Segment {3}. Pricing continues without a tier modifier."
        ).format(tier, company, business_type, crm_segment)

    def _inject_modifier_expenses(self, expenses, tier_mod, zone_mod, *, modifier_basis="Base Price", base_unit=0.0, loaded_cost=0.0):
        """Inject tier and zone modifiers as additional expenses.

        Returns (updated_expenses, tier_amount, zone_amount).
        """
        out = list(expenses or [])
        tier_amount = 0.0
        zone_amount = 0.0

        if tier_mod and flt(tier_mod["amount"]) != 0:
            tier_amount = flt(tier_mod["amount"])
            tier_expense = compute_policy_adjustment_step(
                label="Tier Modifier ({})".format(tier_mod["label"]),
                value=tier_amount,
                adjustment_type=tier_mod["type"] or "Fixed",
                adjustment_basis=modifier_basis,
                base_price=base_unit,
                loaded_cost=loaded_cost,
                sequence=95,
                override_source="tier_modifier",
            )
            out.append(tier_expense)

        if zone_mod and flt(zone_mod["amount"]) != 0:
            zone_amount = flt(zone_mod["amount"])
            zone_expense = compute_policy_adjustment_step(
                label="Zone Modifier ({})".format(zone_mod["label"]),
                value=zone_amount,
                adjustment_type=zone_mod["type"] or "Fixed",
                adjustment_basis=modifier_basis,
                base_price=base_unit,
                loaded_cost=loaded_cost,
                sequence=96,
                override_source="zone_modifier",
            )
            out.append(zone_expense)

        out = sorted(out, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx") or 0)))
        for exp in out:
            exp["expense_key"] = exp.get("expense_key") or make_expense_key(exp)

        return out, tier_amount, zone_amount

    # --- Benchmark-driven margin helpers ---

    def _resolve_benchmark_policy(self):
        """Fetch the Pricing Benchmark Policy linked to the sheet or fallback to default."""
        if self._should_skip_policy_defaults():
            return None

        fallback_mapping = self._get_fallback_policy_mapping()
        mapping_policy = (getattr(fallback_mapping, "benchmark_policy", "") or "").strip() if fallback_mapping else ""
        if mapping_policy and frappe.db.exists("Pricing Benchmark Policy", mapping_policy):
            return frappe.get_doc("Pricing Benchmark Policy", mapping_policy)
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

    def _resolve_static_benchmark_policy(self):
        """Static pricing can still use benchmark-policy tier/territory modifiers."""
        benchmark_policy = (getattr(self, "benchmark_policy", "") or "").strip()
        if benchmark_policy and frappe.db.exists("Pricing Benchmark Policy", benchmark_policy):
            return frappe.get_doc("Pricing Benchmark Policy", benchmark_policy)

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
                "max_discount_percent": flt(r.max_discount_percent),
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

    def _inject_benchmark_margin_expense(self, expenses, benchmark_result, benchmark_policy_doc, base_unit, landed_cost):
        """Inject margin expense from benchmark result."""
        if not benchmark_result:
            return expenses
        matched_rule = benchmark_result.get("matched_rule") or {}
        margin_step = compute_margin_step(
            flt(benchmark_result.get("target_margin_percent")),
            getattr(benchmark_policy_doc, "margin_application_basis", "Base Price"),
            base_price=base_unit,
            loaded_cost=landed_cost,
            sequence=cint(matched_rule.get("sequence") or 90),
            is_fallback=bool(benchmark_result.get("is_fallback")),
        )
        return self._inject_margin_expense(expenses, margin_step)

    def _format_benchmark_rule(self, rule):
        """Format a benchmark rule for display."""
        if not rule:
            return ""
        scope = rule.get("source_bundle") or rule.get("item_group") or rule.get("material") or "Any"
        return _("Ratio {0}-{1}: {2}% margin, {3}% max discount ({4})").format(
            f"{flt(rule.get('ratio_min')):.2f}",
            f"{flt(rule.get('ratio_max')):.2f}" if flt(rule.get("ratio_max")) > 0 else "∞",
            flt(rule.get("target_margin_percent")),
            flt(rule.get("max_discount_percent") or 0),
            scope,
        )

    def _resolve_agent_discount_context(self):
        sales_person = (self.sales_person or "").strip()
        if not sales_person:
            return {"max_discount_percent": 0.0, "commission_rate": 0.0}

        agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name")
        if not agent_name:
            return {"max_discount_percent": 0.0, "commission_rate": 0.0}

        values = frappe.db.get_value(
            "Agent Pricing Rules",
            agent_name,
            ["commission_rate"],
            as_dict=True,
        ) or {}
        return {
            "max_discount_percent": 0.0,
            "commission_rate": flt(values.get("commission_rate") or 0),
        }

    def _apply_line_discount_and_commission(self, row, qty, benchmark_result, fallback_max_discount_percent, agent_discount_ctx, steps):
        matched_rule = (benchmark_result or {}).get("matched_rule") or {}
        policy_max_discount = resolve_max_discount_cap(
            rule_max_discount_percent=flt(matched_rule.get("max_discount_percent") or 0),
            fallback_max_discount_percent=fallback_max_discount_percent,
            agent_max_discount_percent=flt(agent_discount_ctx.get("max_discount_percent") or 0),
            is_fallback=bool((benchmark_result or {}).get("is_fallback")),
        )
        can_override_pricing = can_override_quotation_pricing()
        validation_max_discount = 100.0 if can_override_pricing else policy_max_discount
        self._validate_manual_override_discount_floor(row, validation_max_discount)
        requested_discount = flt(row.discount_percent or 0)
        if requested_discount < 0:
            frappe.throw(_("Row {0}: Discount % cannot be negative.").format(row.idx))
        commission_rate = flt(agent_discount_ctx.get("commission_rate") or 0)
        reference_unit_price = flt(row.projected_unit_price or row.static_list_price or row.final_sell_unit_price)
        actual_unit_price = flt(row.final_sell_unit_price) * (1 - (requested_discount / 100.0))
        try:
            discount_result = apply_discount_and_commission(
                gross_unit_price=reference_unit_price,
                qty=qty,
                discount_percent=requested_discount,
                max_discount_percent=policy_max_discount,
                commission_rate=commission_rate,
                actual_unit_price=actual_unit_price,
                enforce_discount_cap=not can_override_pricing,
                discount_base_unit_price=flt(row.final_sell_unit_price),
            )
        except ValueError as exc:
            frappe.throw(_("Row {0}: {1}").format(row.idx, cstr(exc)))

        row.max_discount_percent_allowed = policy_max_discount
        row.discount_percent = flt(discount_result.get("discount_percent") or 0)
        row.discount_amount = flt(discount_result.get("discount_amount") or 0)
        row.discounted_sell_unit_price = flt(discount_result.get("discounted_unit_price") or 0)
        row.discounted_sell_total = flt(discount_result.get("discounted_total") or 0)
        row.commission_rate = flt(discount_result.get("commission_rate") or 0)
        row.commission_amount = flt(discount_result.get("commission_amount") or 0)

        if requested_discount > 0:
            steps.append(
                {
                    "label": "Agent Discount",
                    "type": "Percentage",
                    "value": requested_discount,
                    "applies_to": "Sell Price",
                    "scope": "Per Unit",
                    "sequence": 10010,
                    "delta_unit": -(flt(row.final_sell_unit_price) * (requested_discount / 100.0)),
                    "delta_line": 0,
                    "delta_sheet": 0,
                    "running_total": flt(discount_result.get("discounted_unit_price") or 0),
                }
            )
        if flt(discount_result.get("commission_amount") or 0) > 0:
            steps.append(
                {
                    "label": "Agent Commission",
                    "type": "Fixed",
                    "value": flt(discount_result.get("commission_amount") or 0),
                    "applies_to": "Discount",
                    "scope": "Per Line",
                    "sequence": 10020,
                    "delta_unit": 0,
                    "delta_line": 0,
                    "delta_sheet": 0,
                    "commission_rate": commission_rate,
                }
            )

    def _validate_manual_override_discount_floor(self, row, max_discount):
        if can_override_quotation_pricing():
            return
        manual_price = flt(row.manual_sell_unit_price or 0)
        if manual_price <= 0:
            return

        reference_price = flt(row.projected_unit_price or row.static_list_price or 0)
        if reference_price <= 0:
            return

        floor_price = reference_price * (1 - (flt(max_discount) / 100.0))
        if manual_price + 0.0001 >= floor_price:
            return

        frappe.throw(
            _(
                "Row {0}: Manual Unit Override {1} is below the minimum allowed {2} for Max Discount {3}%."
            ).format(row.idx, frappe.format_value(manual_price, {"fieldtype": "Currency"}), frappe.format_value(floor_price, {"fieldtype": "Currency"}), flt(max_discount)),
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

    def _inject_storage_expense(self, expenses, storage_calc):
        applied = flt((storage_calc or {}).get("applied") or 0)
        if applied <= 0:
            return list(expenses or [])

        out = list(expenses or [])
        out.append(
            {
                "label": "Storage Allocation",
                "type": "Fixed",
                "value": applied,
                "applies_to": "Base Price",
                "scope": "Per Line",
                "sequence": 16,
                "is_active": 1,
                "is_overridden": 0,
                "override_source": "storage_policy",
                "storage_volume_m3": flt(storage_calc.get("line_volume_m3") or 0),
                "storage_cost_per_m3_per_month": flt(storage_calc.get("cost_per_m3_per_month") or 0),
                "storage_duration_months": flt(storage_calc.get("duration_months") or 0),
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

    def _extract_storage_config(self, scenario):
        return {
            "is_active": cint(getattr(scenario, "storage_is_active", 0)),
            "cost_per_m3_per_month": flt(getattr(scenario, "storage_cost_per_m3_per_month", 0)),
            "duration_months": flt(getattr(scenario, "storage_duration_months", 0)),
        }

    def _compute_storage_for_row(self, row, qty, item_details, storage_config):
        details = item_details.get(row.item) or {}
        unit_volume_m3 = flt(details.get("custom_volume_m3"))
        line_volume_m3 = flt(qty) * unit_volume_m3
        rate = flt(storage_config.get("cost_per_m3_per_month") or 0)
        duration = flt(storage_config.get("duration_months") or 0)

        out = {
            "line_volume_m3": line_volume_m3,
            "unit_volume_m3": unit_volume_m3,
            "cost_per_m3_per_month": rate,
            "duration_months": duration,
            "applied": 0.0,
            "warning": "",
        }

        if cint(storage_config.get("is_active")) != 1:
            return out
        if rate <= 0 or duration <= 0:
            return out
        if line_volume_m3 <= 0:
            out["warning"] = _("storage volume is zero; storage cost set to 0")
            return out

        out["applied"] = rate * line_volume_m3 * duration
        return out

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

    def _build_scenario_caches(self, scenario_docs, item_codes, benchmark_policy_doc=None, target_currency=None):
        pricing_currency = (target_currency or "").strip() or get_pricing_currency()
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
                        item_codes, pl, buying=None, target_currency=pricing_currency
                    )

        caches = {}
        default_buying_price_list = self._resolve_source_buying_price_list()
        for name, scenario in scenario_docs.items():
            effective_expenses = self._active_expenses(scenario)
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
                "buying_price_list": default_buying_price_list,
                "buy_prices": get_latest_item_prices(item_codes, default_buying_price_list, buying=True, target_currency=pricing_currency)
                if default_buying_price_list
                else {},
                "benchmark_price_map": benchmark_price_map,
                "benchmark_source_types": benchmark_source_types,
                "line_expenses": line_expenses,
                "sheet_fixed_total": sheet_fixed_total,
                "transport_config": self._extract_transport_config(scenario),
                "storage_config": self._extract_storage_config(scenario),
            }

        if getattr(self, "allow_empty_expenses_policy", 0) and NO_EXPENSES_SCENARIO not in caches:
            caches[NO_EXPENSES_SCENARIO] = {
                "buying_price_list": default_buying_price_list,
                "buy_prices": get_latest_item_prices(item_codes, default_buying_price_list, buying=True, target_currency=pricing_currency)
                if default_buying_price_list
                else {},
                "benchmark_price_map": benchmark_price_map,
                "benchmark_source_types": benchmark_source_types,
                "line_expenses": [],
                "sheet_fixed_total": 0.0,
                "transport_config": self._extract_transport_config(
                    frappe._dict(
                        transport_is_active=0,
                        transport_container_type="",
                        transport_allocation_mode="",
                        transport_container_price=0,
                        transport_total_merch_value=0,
                        transport_total_weight_kg=0,
                        transport_total_volume_m3=0,
                    )
                ),
                "storage_config": self._extract_storage_config(
                    frappe._dict(
                        storage_is_active=0,
                        storage_cost_per_m3_per_month=0,
                        storage_duration_months=0,
                    )
                ),
            }

        return caches

    def _resolve_line_scenario(self, row, line_context=None):
        if row.pricing_scenario:
            return row.pricing_scenario, "Line", None

        mapping = self._resolve_sheet_scenario_mapping(line_context or self._build_rule_context(row))
        if mapping and mapping.get("pricing_scenario"):
            return mapping.get("pricing_scenario"), "Policy Rule", mapping

        if getattr(self, "allow_empty_expenses_policy", 0):
            return NO_EXPENSES_SCENARIO, "Draft Fallback", None

        frappe.throw(_("Please configure a Policy Mapping fallback row or set a line-level Expenses Policy."))
    def _active_expenses(self, scenario):
        as_dicts = [row.as_dict() for row in (scenario.expenses or []) if flt(row.is_active)]
        return sorted(as_dicts, key=lambda x: (cint(x.get("sequence")), cint(x.get("idx"))))

    def _strip_scenario_margin_expenses(self, expenses):
        filtered = []
        for expense in expenses or []:
            label = cstr(expense.get("label") or "").strip().lower()
            notes = cstr(expense.get("notes") or "").strip().lower()
            if "margin" in label or "margin" in notes:
                continue
            filtered.append(expense)
        return filtered

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
        fallback_mapping = self._get_fallback_policy_mapping()
        scenario_name = (getattr(fallback_mapping, "pricing_scenario", "") or "").strip() if fallback_mapping else ""
        if not scenario_name:
            scenario_name = (self.pricing_scenario or "").strip()
        if not scenario_name:
            frappe.throw(_("Please configure a fallback Policy Mapping row with an Expenses Policy."))
        return frappe.get_doc("Pricing Scenario", scenario_name)

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
            row.buy_price_message = (
                MISSING_BUY_PRICE_MSG.format(price_list=buying_price_list)
                if buying_price_list
                else _("Missing source buying price list for pricing calculation.")
            )
            if force_refresh and flt(row.buy_price) <= 0:
                row.buy_price = 0
            return

        row.buy_price = flt(buy_price)
        row.buy_price_missing = 0
        row.buy_price_message = ""

    def _set_buy_price_for_row(
        self,
        row,
        fallback_buying_price_list,
        fallback_buy_prices,
        buy_price_cache_by_list,
        force_refresh=False,
        target_currency=None,
    ):
        pricing_currency = (target_currency or "").strip() or get_pricing_currency()
        buying_price_list = (getattr(row, "source_buying_price_list", "") or "").strip() or fallback_buying_price_list
        row.source_buying_price_list = buying_price_list or ""
        buy_prices = fallback_buy_prices or {}

        if buying_price_list and buying_price_list != fallback_buying_price_list:
            cached_prices = buy_price_cache_by_list.get(buying_price_list)
            if cached_prices is None:
                cached_prices = get_latest_item_prices([row.item], buying_price_list, buying=True, target_currency=pricing_currency) if row.item else {}
                buy_price_cache_by_list[buying_price_list] = cached_prices
            elif row.item and row.item not in cached_prices:
                cached_prices.update(get_latest_item_prices([row.item], buying_price_list, buying=True, target_currency=pricing_currency))
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
        company = (getattr(self, "custom_company", "") or "").strip()
        if company:
            return company
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
    def get_linked_quotations(self):
        if not self.name or not frappe.db.has_column("Quotation", "source_pricing_sheet"):
            return []
        fields = ["name", "docstatus", "status", "transaction_date", "grand_total", "modified"]
        return frappe.get_all(
            "Quotation",
            filters={"source_pricing_sheet": self.name},
            fields=fields,
            order_by="modified desc",
            limit_page_length=0,
        )

    @frappe.whitelist()
    def generate_quotation(self, target_quotation=None):
        self.check_permission("write")
        if self._is_restricted_agent_user() and not self._can_create_quotation_as_commercial_user():
            frappe.throw(_("You need the Quotation Creator role to generate quotations."), frappe.PermissionError)

        # Reprice with the current selected lists before copying snapshot values into Quotation rows.
        self.recalculate()

        lines = self.lines or []
        party_type = self._pricing_party_type()
        party_name = self._pricing_party_name()
        if party_type not in SUPPORTED_PRICING_PARTY_TYPES or not party_name:
            frappe.throw(_("Customer, Lead, or Prospect is required."))
        if not frappe.db.exists(party_type, party_name):
            frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))
        if not lines:
            frappe.throw(_("Please add at least one pricing line."))

        target_quotation = (target_quotation or "").strip()
        quotation = self._get_target_quotation_for_update(target_quotation) if target_quotation else frappe.new_doc("Quotation")
        quotation.set("items", [])
        quotation.company = self._resolve_company_for_quotation()
        quotation.quotation_to = party_type
        quotation.party_name = party_name
        if quotation.meta.get_field("ignore_pricing_rule"):
            quotation.ignore_pricing_rule = 1
        if quotation.meta.get_field("custom_crm_business_type"):
            quotation.custom_crm_business_type = self.crm_business_type or ""
        if quotation.meta.get_field("custom_crm_segment"):
            quotation.custom_crm_segment = self.crm_segment or ""
        self._apply_quotation_price_list(quotation)
        if frappe.db.has_column("Quotation", "source_pricing_sheet"):
            quotation.source_pricing_sheet = self.name
        if quotation.meta.get_field("commission_sales_person"):
            quotation.commission_sales_person = self.sales_person or ""
        if (self.get("taxes_and_charges_template") or "").strip() and quotation.meta.get_field("taxes_and_charges"):
            quotation.taxes_and_charges = self.get("taxes_and_charges_template")
        if self.get("opportunity") and quotation.meta.get_field("opportunity"):
            quotation.opportunity = self.get("opportunity")
        if (self.get("geography_territory") or "").strip() and quotation.meta.get_field("territory"):
            quotation.territory = self.get("geography_territory")
        self._apply_quotation_selected_price_lists(quotation)

        output_mode = (self.output_mode or "Avec details").strip().lower()
        if output_mode in ("sans details", "sans détails"):
            self._append_grouped_quotation_items(quotation)
        else:
            self._append_detailed_quotation_items(quotation)

        if not quotation.items:
            frappe.throw(_("No quotation items were generated from this Pricing Sheet."))

        apply_quotation_sales_tax_template(quotation)
        sync_quotation_item_tax_inclusive_fields(quotation)

        if target_quotation:
            quotation.flags.allow_source_pricing_sheet_update = True
            quotation.save()
        else:
            quotation.insert()
        return quotation.name

    def _get_target_quotation_for_update(self, target_quotation):
        if not frappe.db.exists("Quotation", target_quotation):
            frappe.throw(_("Quotation {0} was not found.").format(target_quotation))
        quotation = frappe.get_doc("Quotation", target_quotation)
        quotation.check_permission("write")
        if cint(quotation.docstatus) != 0:
            frappe.throw(_("Only draft Quotations can be updated from a Pricing Sheet."))
        if not frappe.db.has_column("Quotation", "source_pricing_sheet"):
            frappe.throw(_("Quotation source Pricing Sheet field is not configured."))
        if (quotation.get("source_pricing_sheet") or "").strip() != self.name:
            frappe.throw(_("Quotation {0} is not linked to Pricing Sheet {1}.").format(target_quotation, self.name))
        return quotation

    def _apply_quotation_selected_price_lists(self, quotation):
        if not quotation.meta.get_field("selected_selling_price_lists"):
            return
        quotation.set("selected_selling_price_lists", [])
        seen = set()
        rows = sorted(
            [row for row in (getattr(self, "selected_selling_price_lists", None) or []) if (getattr(row, "price_list", "") or "").strip()],
            key=lambda row: (cint(getattr(row, "sequence", 0) or 0) or 999999, cint(getattr(row, "idx", 0) or 0)),
        )
        for row in rows:
            price_list = (getattr(row, "price_list", "") or "").strip()
            if not price_list or price_list in seen:
                continue
            seen.add(price_list)
            quotation.append(
                "selected_selling_price_lists",
                {
                    "price_list": price_list,
                    "sequence": cint(getattr(row, "sequence", 0) or 0) or len(seen) * 10,
                    "is_active": 1 if cint(getattr(row, "is_active", 1)) else 0,
                },
            )

    def _apply_quotation_price_list(self, quotation):
        price_list = self._resolve_quotation_selling_price_list()
        if not price_list:
            price_list = self._get_default_quotation_selling_price_list(quotation.company)
        if not frappe.db.exists("Price List", price_list):
            return

        company_currency = frappe.db.get_value("Company", quotation.company, "default_currency") or get_pricing_currency()
        price_list_currency = frappe.db.get_value("Price List", price_list, "currency") or company_currency
        quotation.selling_price_list = price_list
        quotation.price_list_currency = price_list_currency
        quotation.currency = price_list_currency
        quotation.conversion_rate = get_exchange_rate_for_pair(price_list_currency, company_currency)
        quotation.plc_conversion_rate = get_exchange_rate_for_pair(price_list_currency, company_currency)

    def _resolve_quotation_selling_price_list(self):
        if self._is_restricted_agent_user():
            static_ctx = build_static_context(sales_person=self.sales_person)
            self._enforce_restricted_static_agent_context(static_ctx)

        price_list = (self.selected_price_list or "").strip()
        if price_list:
            return price_list

        static_ctx = build_static_context(sales_person=self.sales_person)
        if static_ctx.get("pricing_mode") == STATIC_MODE:
            lists = static_ctx.get("selling_price_lists") or []
            return (lists[0] or "").strip() if lists else ""

        return ""

    def _get_default_quotation_selling_price_list(self, company=None):
        filters = {"selling": 1}
        if frappe.db.has_column("Price List", "enabled"):
            filters["enabled"] = 1
        if company and frappe.db.has_column("Price List", "custom_company"):
            filters["custom_company"] = company
        if frappe.db.has_column("Price List", PRICE_LIST_TYPE_FIELD):
            filters[PRICE_LIST_TYPE_FIELD] = "Selling"
        names = frappe.get_all(
            "Price List",
            filters=filters,
            fields=["name"],
            order_by="modified desc",
            limit_page_length=1,
        )
        return names[0].name if names else ""

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
            }
            item_data.update(self._quotation_item_price_values(flt(row.discounted_sell_unit_price or row.final_sell_unit_price), flt(row.qty), quotation))
            if frappe.db.has_column("Quotation Item", "source_pricing_sheet_line"):
                item_data["source_pricing_sheet_line"] = row.name
            if frappe.db.has_column("Quotation Item", "source_pricing_scenario"):
                item_data["source_pricing_scenario"] = row.resolved_pricing_scenario or row.pricing_scenario or ""
            if frappe.db.has_column("Quotation Item", "source_pricing_override"):
                item_data["source_pricing_override"] = cint(
                    row.is_manual_override or row.has_scenario_override or row.has_line_override
                )
            if frappe.db.has_column("Quotation Item", "source_pricing_policy"):
                item_data["source_pricing_policy"] = self.applied_benchmark_policy or self.benchmark_policy or ""
            if frappe.db.has_column("Quotation Item", "source_margin_percent") and (self.resolved_mode != "Static" or (getattr(row, "pricing_builder", "") or "").strip()):
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
            if frappe.db.has_column("Quotation Item", "source_gross_sell_rate"):
                item_data["source_gross_sell_rate"] = flt(row.final_sell_unit_price)
            if frappe.db.has_column("Quotation Item", "source_selling_price_list"):
                item_data["source_selling_price_list"] = (getattr(row, "resolved_selling_price_list", "") or "").strip()
            if frappe.db.has_column("Quotation Item", "source_price_list_sell_rate"):
                item_data["source_price_list_sell_rate"] = flt(
                    row.static_list_price or row.projected_unit_price or row.final_sell_unit_price
                )
            if frappe.db.has_column("Quotation Item", "source_discount_percent"):
                item_data["source_discount_percent"] = flt(row.discount_percent)
            if frappe.db.has_column("Quotation Item", "source_max_discount_percent"):
                item_data["source_max_discount_percent"] = flt(row.max_discount_percent_allowed)
            if frappe.db.has_column("Quotation Item", "source_discount_amount"):
                item_data["source_discount_amount"] = flt(row.discount_amount) / (flt(row.qty) or 1)
            if frappe.db.has_column("Quotation Item", "source_discounted_sell_rate"):
                item_data["source_discounted_sell_rate"] = flt(row.discounted_sell_unit_price or row.final_sell_unit_price)
            if frappe.db.has_column("Quotation Item", "source_commission_rate"):
                item_data["source_commission_rate"] = flt(row.commission_rate)
            if frappe.db.has_column("Quotation Item", "source_commission_amount"):
                item_data["source_commission_amount"] = flt(row.commission_amount)

            quotation.append("items", item_data)

    def _append_grouped_quotation_items(self, quotation):
        config = self._get_group_line_config()
        group_item_code = config["item_code"]
        grouped = self._build_grouped_totals()
        grouped_caps = self._build_grouped_max_discount_caps()

        for (group_name, scenario_name), group_total in grouped.items():
            item = {
                "item_code": group_item_code,
                "qty": 1,
                "description": _("{0}: {1} [Scenario: {2}]").format(
                    config["description_prefix"], group_name, scenario_name or "-"
                ),
            }
            item.update(self._quotation_item_price_values(flt(group_total), 1, quotation))
            if frappe.db.has_column("Quotation Item", "source_max_discount_percent"):
                item["source_max_discount_percent"] = flt(grouped_caps.get((group_name, scenario_name)) or 0)
            if frappe.db.has_column("Quotation Item", "source_gross_sell_rate"):
                item["source_gross_sell_rate"] = flt(group_total)
            if frappe.db.has_column("Quotation Item", "source_price_list_sell_rate"):
                item["source_price_list_sell_rate"] = flt(group_total)
            if frappe.db.has_column("Quotation Item", "source_discount_percent"):
                item["source_discount_percent"] = 0
            if frappe.db.has_column("Quotation Item", "source_discount_amount"):
                item["source_discount_amount"] = 0
            if frappe.db.has_column("Quotation Item", "source_discounted_sell_rate"):
                item["source_discounted_sell_rate"] = flt(group_total)
            if frappe.db.has_column("Quotation Item", "source_pricing_scenario"):
                item["source_pricing_scenario"] = scenario_name
            quotation.append("items", item)

    def _quotation_item_price_values(self, rate, qty, quotation):
        rate = flt(rate)
        qty = flt(qty) or 1
        conversion_rate = flt(getattr(quotation, "conversion_rate", 1) or 1)
        base_rate = rate * conversion_rate
        amount = rate * qty
        base_amount = base_rate * qty
        values = {
            "rate": rate,
            "price_list_rate": rate,
            "base_price_list_rate": base_rate,
            "base_rate": base_rate,
            "amount": amount,
            "base_amount": base_amount,
            "net_rate": rate,
            "net_amount": amount,
            "base_net_rate": base_rate,
            "base_net_amount": base_amount,
        }
        if frappe.db.has_column("Quotation Item", "ignore_pricing_rule"):
            values["ignore_pricing_rule"] = 1
        return values

    def _build_grouped_totals(self):
        grouped = {}
        summary_bundle_ids = {
            row.bundle_group_id
            for row in (self.lines or [])
            if (row.line_type or "") == "Bundle Summary" and row.bundle_group_id
        }

        for row in self.lines or []:
            effective_total = flt(row.discounted_sell_total or row.final_sell_total)
            if effective_total == 0:
                continue
            if (row.line_type or "") == "Bundle Component" and row.bundle_group_id in summary_bundle_ids:
                continue

            fallback_group = row.display_group or "Ungrouped"
            scenario_name = row.resolved_pricing_scenario or row.pricing_scenario or ""
            key = ((fallback_group or "Ungrouped").strip() or "Ungrouped", scenario_name)
            grouped[key] = grouped.get(key, 0.0) + effective_total

        return grouped

    def _build_grouped_max_discount_caps(self):
        grouped = {}
        summary_bundle_ids = {
            row.bundle_group_id
            for row in (self.lines or [])
            if (row.line_type or "") == "Bundle Summary" and row.bundle_group_id
        }

        for row in self.lines or []:
            effective_total = flt(row.discounted_sell_total or row.final_sell_total)
            if effective_total == 0:
                continue
            if (row.line_type or "") == "Bundle Component" and row.bundle_group_id in summary_bundle_ids:
                continue
            fallback_group = row.display_group or "Ungrouped"
            scenario_name = row.resolved_pricing_scenario or row.pricing_scenario or ""
            key = ((fallback_group or "Ungrouped").strip() or "Ungrouped", scenario_name)
            cap = flt(row.max_discount_percent_allowed)
            grouped[key] = cap if key not in grouped else min(grouped[key], cap)
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


def compute_margin_percent_for_basis(margin_unit_amount, margin_application_basis, base_unit, landed_cost):
    """Return the actual margin rate against the same basis used to calculate it."""
    amount = flt(margin_unit_amount)
    basis = (margin_application_basis or "Base Price").strip() or "Base Price"
    if basis == "Base Price":
        denominator = flt(base_unit)
    elif basis == "Sale Price":
        denominator = flt(landed_cost) + amount
    else:
        denominator = flt(landed_cost)

    if denominator <= 0:
        return 0.0
    return flt((amount / denominator) * 100)


def get_item_details_map(item_codes):
    if not item_codes:
        return {}
    fields = [
        "name",
        "item_group",
        "custom_material",
        "custom_customs_material",
        "custom_weight_kg",
        "custom_volume_m3",
        "customs_tariff_number",
    ]
    has_column = getattr(frappe.db, "has_column", lambda *args, **kwargs: True)
    if has_column("Item", "custom_item_category"):
        fields.append("custom_item_category")
    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=fields,
        limit_page_length=0,
    )
    return {
        row.name: {
            "item_group": row.item_group,
            "custom_material": row.custom_material,
            "custom_customs_material": getattr(row, "custom_customs_material", "") or "",
            "custom_weight_kg": flt(row.custom_weight_kg),
            "custom_volume_m3": flt(row.custom_volume_m3),
            "customs_tariff_number": row.customs_tariff_number,
            "custom_item_category": getattr(row, "custom_item_category", "") or "",
        }
        for row in rows
    }


def get_latest_item_price(item_code, price_list, buying, target_currency=None):
    return get_latest_item_prices([item_code], price_list, buying, target_currency=target_currency).get(item_code)


@lru_cache(maxsize=128)
def get_pricing_currency():
    return frappe.defaults.get_global_default("currency")


@lru_cache(maxsize=256)
def get_price_list_currency(price_list):
    if not price_list:
        return get_pricing_currency()
    return frappe.db.get_value("Price List", price_list, "currency") or get_pricing_currency()


@lru_cache(maxsize=256)
def get_exchange_rate_for_pair(from_currency, to_currency, rate_date=None):
    return flt(get_exchange_rate_info_for_pair(from_currency, to_currency, rate_date).get("exchange_rate") or 0)


@lru_cache(maxsize=256)
def get_exchange_rate_info_for_pair(from_currency, to_currency, rate_date=None):
    from_currency = (from_currency or "").strip().upper()
    to_currency = (to_currency or "").strip().upper()
    rate_date = rate_date or nowdate()

    if not from_currency or not to_currency or from_currency == to_currency:
        return {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "exchange_rate": 1.0,
            "rate_date": rate_date,
            "source": "Same Currency",
        }

    if frappe.db.exists("DocType", "Currency Exchange"):
        row = frappe.get_all(
            "Currency Exchange",
            filters={
                "from_currency": from_currency,
                "to_currency": to_currency,
                "date": ["<=", rate_date],
            },
            fields=["name", "date", "exchange_rate"],
            order_by="date desc, modified desc",
            limit_page_length=1,
        )
        if row and flt(row[0].exchange_rate) > 0:
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "exchange_rate": flt(row[0].exchange_rate),
                "rate_date": getattr(row[0], "date", rate_date) or rate_date,
                "source": "Currency Exchange",
                "source_name": getattr(row[0], "name", "") or "",
            }

        inverse = frappe.get_all(
            "Currency Exchange",
            filters={
                "from_currency": to_currency,
                "to_currency": from_currency,
                "date": ["<=", rate_date],
            },
            fields=["name", "date", "exchange_rate"],
            order_by="date desc, modified desc",
            limit_page_length=1,
        )
        if inverse and flt(inverse[0].exchange_rate) > 0:
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "exchange_rate": 1.0 / flt(inverse[0].exchange_rate),
                "rate_date": getattr(inverse[0], "date", rate_date) or rate_date,
                "source": "Currency Exchange (inverse)",
                "source_name": getattr(inverse[0], "name", "") or "",
            }

    try:
        from erpnext.setup.utils import get_exchange_rate  # type: ignore

        rate = flt(get_exchange_rate(from_currency, to_currency, rate_date) or 0)
        if rate > 0:
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "exchange_rate": rate,
                "rate_date": rate_date,
                "source": "ERPNext Exchange Rate",
            }
    except Exception:
        pass

    frappe.throw(_("Missing currency exchange rate from {0} to {1} for pricing.").format(from_currency, to_currency))


def convert_price_to_target_currency(amount, from_currency, target_currency):
    amount = flt(amount)
    if amount == 0:
        return 0.0
    rate = get_exchange_rate_for_pair(from_currency, target_currency, nowdate())
    return flt(amount * rate)


ITEM_PRICE_STATIC_STAMP_FIELDS = [
    "custom_pricing_builder",
    "custom_source_buying_price_list",
    "custom_benchmark_policy",
    "custom_benchmark_is_fallback",
    "custom_benchmark_rule_label",
    "custom_benchmark_rule_max_discount_percent",
    "custom_fallback_max_discount_percent",
    "custom_policy_max_discount_percent",
    "custom_target_margin_percent",
    "custom_final_margin_percent",
    "custom_builder_price_overridden",
    "custom_last_builder_buy_rate",
    "custom_builder_expense_amount",
    "custom_builder_customs_amount",
    "custom_builder_margin_basis",
]


def build_static_item_price_discount_context(item_price_record, benchmark_policy_doc=None):
    item_price_record = item_price_record or {}
    has_builder_stamp = any(
        (item_price_record.get(fieldname) not in (None, ""))
        for fieldname in (
            "custom_pricing_builder",
            "custom_source_buying_price_list",
            "custom_benchmark_policy",
            "custom_benchmark_rule_label",
        )
    )
    if has_builder_stamp:
        is_fallback = bool(cint(item_price_record.get("custom_benchmark_is_fallback") or 0))
        fallback_max_discount = flt(item_price_record.get("custom_fallback_max_discount_percent") or 0)
        if is_fallback:
            return {"is_fallback": True, "matched_rule": {}}, fallback_max_discount
        return {
            "is_fallback": False,
            "matched_rule": {
                "max_discount_percent": flt(item_price_record.get("custom_benchmark_rule_max_discount_percent") or 0),
            },
        }, fallback_max_discount

    fallback_max_discount = flt(_object_value(benchmark_policy_doc, "fallback_max_discount_percent") or 0)
    if fallback_max_discount > 0:
        return {"is_fallback": True, "matched_rule": {}}, fallback_max_discount
    return None, 0


def _object_value(obj, fieldname, default=None):
    if isinstance(obj, dict):
        return obj.get(fieldname, default)
    getter = getattr(obj, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(obj, fieldname, default)


def get_latest_item_price_records(item_codes, price_list, buying, target_currency=None):
    if not item_codes or not price_list:
        return {}

    # Unit tests monkeypatch get_latest_item_prices and use a minimal DB stub without SQL.
    if not hasattr(frappe.db, "sql"):
        return {
            item_code: {"item_code": item_code, "price_list_rate": rate}
            for item_code, rate in get_latest_item_prices(item_codes, price_list, buying, target_currency=target_currency).items()
        }

    price_list_currency = get_price_list_currency(price_list)
    target_currency = (target_currency or "").strip() or price_list_currency

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

    extra_fields = [fieldname for fieldname in ITEM_PRICE_STATIC_STAMP_FIELDS if frappe.db.has_column("Item Price", fieldname)]
    extra_select = "" if not extra_fields else ", " + ", ".join(f"ip.`{fieldname}`" for fieldname in extra_fields)
    rows = frappe.db.sql(
        f"""
        SELECT ip.name, ip.item_code, ip.price_list_rate, ip.modified{extra_select}
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        """,
        params,
        as_dict=True,
    )

    out = {}
    for row in rows:
        if row.item_code in out:
            continue
        record = dict(row)
        record["price_list_rate"] = convert_price_to_target_currency(
            row.price_list_rate,
            price_list_currency,
            target_currency,
        )
        out[row.item_code] = record
    return out


def get_latest_item_price_records_from_lists(item_codes, price_lists, buying, target_currency=None):
    out = {}
    duplicate_map = {}
    for price_list in price_lists or []:
        price_list = (price_list or "").strip()
        if not price_list:
            continue
        records = get_latest_item_price_records(item_codes, price_list, buying, target_currency=target_currency)
        for item_code, record in records.items():
            copied = dict(record)
            copied["price_list"] = price_list
            if item_code in out:
                duplicate_map.setdefault(item_code, []).append(dict(copied))
                duplicate_map[item_code].append(dict(out[item_code]))
                continue
            out[item_code] = copied

    warnings = []
    seen = set()
    for item_code, records in duplicate_map.items():
        unique_lists = []
        for record in records:
            price_list = (record.get("price_list") or "").strip()
            if price_list and price_list not in unique_lists:
                unique_lists.append(price_list)
        if len(unique_lists) < 2:
            continue
        key = (item_code, tuple(unique_lists))
        if key in seen:
            continue
        seen.add(key)
        winning_list = (out.get(item_code) or {}).get("price_list") or ""
        warnings.append(
            _("Static duplicate Item Price for {0} found in lists {1}; configured list {2} was used.").format(
                item_code,
                ", ".join(unique_lists),
                winning_list or "-",
            )
        )
    return out, warnings


def get_latest_item_prices(item_codes, price_list, buying, target_currency=None):
    if not item_codes or not price_list:
        return {}

    price_list_currency = get_price_list_currency(price_list)
    target_currency = (target_currency or "").strip() or price_list_currency

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
            out[row.item_code] = convert_price_to_target_currency(
                row.price_list_rate,
                price_list_currency,
                target_currency,
            )
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
    params = {"txt": txt_like, "start": start, "page_len": page_len}
    return frappe.db.sql(
        f"""
        SELECT
            i.name,
            i.item_name,
            COALESCE(SUM(b.actual_qty), 0) AS stock_qty,
            i.stock_uom
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name
        WHERE i.disabled = 0
          AND i.is_stock_item = 1
          AND (i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s OR i.description LIKE %(txt)s)
          {stock_warehouse_condition("b.warehouse", params)}
        GROUP BY i.name, i.item_name, i.stock_uom
        ORDER BY stock_qty DESC, i.name
        LIMIT %(start)s, %(page_len)s
        """,
        params,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def priced_item_query(doctype, txt, searchfield, start, page_len, filters):
    filters = filters or {}
    price_lists = _clean_filter_list(filters.get("price_lists") if hasattr(filters, "get") else None)
    buying = cint(filters.get("buying") if hasattr(filters, "get") else 0)
    item_group = (filters.get("item_group") if hasattr(filters, "get") else "") or ""
    price_lists = _scoped_query_price_lists(price_lists, buying=buying)
    if not price_lists:
        return []

    txt_like = f"%{txt}%"
    conditions = [
        "i.disabled = 0",
        "ip.price_list in %(price_lists)s",
        "(i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s)",
    ]
    if item_group:
        conditions.append("i.item_group = %(item_group)s")
    if frappe.db.has_column("Item Price", "enabled"):
        conditions.append("ip.enabled = 1")
    if frappe.db.has_column("Item Price", "buying"):
        conditions.append("ip.buying = %(buying)s")
    if frappe.db.has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if frappe.db.has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")

    return frappe.db.sql(
        f"""
        SELECT DISTINCT
            i.name,
            i.item_name,
            i.stock_uom
        FROM `tabItem` i
        INNER JOIN `tabItem Price` ip ON ip.item_code = i.name
        WHERE {' AND '.join(conditions)}
        ORDER BY i.name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "price_lists": tuple(price_lists),
            "buying": 1 if buying else 0,
            "item_group": item_group,
            "txt": txt_like,
            "today": nowdate(),
            "start": start,
            "page_len": page_len,
        },
    )


def _scoped_query_price_lists(price_lists, buying):
    kind = "buying" if cint(buying) else "selling"
    scoped = []
    for price_list in price_lists or []:
        try:
            scoped.append(validate_price_list_scope(price_list, kind=kind, required=True))
        except Exception:
            continue
    return scoped


def get_item_codes_with_prices(item_codes, price_lists, buying):
    item_codes = _clean_filter_list(item_codes)
    price_lists = _clean_filter_list(price_lists)
    if not item_codes or not price_lists or not hasattr(frappe.db, "sql"):
        return set()

    conditions = [
        "ip.item_code in %(item_codes)s",
        "ip.price_list in %(price_lists)s",
    ]
    if frappe.db.has_column("Item Price", "enabled"):
        conditions.append("ip.enabled = 1")
    if frappe.db.has_column("Item Price", "buying"):
        conditions.append("ip.buying = %(buying)s")
    if frappe.db.has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if frappe.db.has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")

    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT ip.item_code
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        """,
        {
            "item_codes": tuple(item_codes),
            "price_lists": tuple(price_lists),
            "buying": 1 if buying else 0,
            "today": nowdate(),
        },
        pluck=True,
    )
    return set(rows or [])


def _clean_filter_list(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            value = parsed
        except Exception:
            value = [value]
    out = []
    seen = set()
    for item in value or []:
        item = (str(item) if item is not None else "").strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


@frappe.whitelist()
def get_item_pricing_defaults(item_code, pricing_scenario=None, source_buying_price_list=None):
    if not item_code:
        return {"buy_price": 0, "item_group": "Ungrouped"}

    buying_price_list = (source_buying_price_list or "").strip() or "Buying"

    buy_price = get_latest_item_price(item_code, buying_price_list, buying=True, target_currency=get_pricing_currency())
    item_group = frappe.db.get_value("Item", item_code, "item_group") or "Ungrouped"
    return {
        "buy_price": flt(buy_price),
        "currency": get_pricing_currency(),
        "item_group": item_group,
    }


@frappe.whitelist()
def get_customer_pricing_context(customer=None, business_type=None, crm_segment=None):
    return get_party_pricing_context(
        party_type="Customer",
        party_name=customer,
        business_type=business_type,
        crm_segment=crm_segment,
    )


@frappe.whitelist()
def get_party_pricing_context(party_type="Customer", party_name=None, business_type=None, crm_segment=None):
    party_type = (party_type or "Customer").strip()
    party_name = (party_name or "").strip()
    if party_type not in SUPPORTED_PRICING_PARTY_TYPES:
        frappe.throw(_("Party Type must be Customer, Lead, or Prospect."))
    if party_type == "Customer":
        return _customer_pricing_context(party_name, business_type=business_type, crm_segment=crm_segment)

    return _lead_or_prospect_pricing_context(
        party_type,
        party_name,
        business_type=business_type,
        crm_segment=crm_segment,
    )


def _empty_party_pricing_context():
    return {
        "customer_type": "",
        "tier": "",
        "tier_mode": "",
        "tier_source": "",
        "tier_status": "",
        "tier_message": "",
        "enable_dynamic_segmentation": 0,
        "segments": [],
        "selected": {"business_type": "", "crm_segment": ""},
    }


def _customer_pricing_context(customer=None, business_type=None, crm_segment=None):
    if not customer:
        return _empty_party_pricing_context()

    fields = ["tier"]
    for fieldname in ("manual_tier", "enable_dynamic_segmentation", "tier_source", "tier_last_calculated_on"):
        if frappe.db.has_column("Customer", fieldname):
            fields.append(fieldname)
    values = frappe.db.get_value("Customer", customer, fields, as_dict=True) or {}
    is_dynamic = cint(values.get("enable_dynamic_segmentation") or 0) == 1
    tier = (values.get("tier") or "").strip()
    tier_source = (values.get("tier_source") or "").strip()
    tier_status = "manual"
    tier_message = _("Manual Pricing Tier selected on the Customer.")

    if is_dynamic:
        from orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine import (
            calculate_customer_dynamic_tier,
        )

        result = calculate_customer_dynamic_tier(customer=customer, apply=1) or {}
        tier = (result.get("tier") or "").strip()
        tier_source = (result.get("engine_name") or tier_source or _("Dynamic Segmentation")).strip()
        tier_status = result.get("status") or "missing_rule"
        tier_message = result.get("message") or _("Dynamic segmentation did not return a Pricing Tier.")
    else:
        tier = tier or (values.get("manual_tier") or "").strip()

    crm_context = resolve_party_crm_pricing_context(
        "Customer",
        customer,
        selected_business_type=business_type,
        selected_segment=crm_segment,
    )
    return {
        "customer_type": "",
        "tier": tier,
        "tier_mode": _("Dynamic Segmentation") if is_dynamic else _("Manual"),
        "tier_source": tier_source or (_("Dynamic Segmentation") if is_dynamic else _("Manual")),
        "tier_status": tier_status,
        "tier_message": tier_message,
        "tier_last_calculated_on": values.get("tier_last_calculated_on"),
        "enable_dynamic_segmentation": 1 if is_dynamic else 0,
        **crm_context,
    }


def _lead_or_prospect_pricing_context(party_type, party_name=None, business_type=None, crm_segment=None):
    if not party_name:
        return _empty_party_pricing_context()
    if not frappe.db.exists(party_type, party_name):
        frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))

    fields = [field for field in ("manual_tier", "tier") if frappe.db.has_column(party_type, field)]
    values = frappe.db.get_value(party_type, party_name, fields, as_dict=True) if fields else {}
    tier = (values or {}).get("manual_tier") or (values or {}).get("tier") or ""
    crm_context = resolve_party_crm_pricing_context(
        party_type,
        party_name,
        selected_business_type=business_type,
        selected_segment=crm_segment,
    )
    return {
        "customer_type": "",
        "tier": tier,
        "tier_mode": _("Manual") if tier else "",
        "tier_source": _("Manual") if tier else "",
        "tier_status": "manual" if tier else "",
        "tier_message": _("Manual Pricing Tier selected on the party.") if tier else "",
        "tier_last_calculated_on": None,
        "enable_dynamic_segmentation": 0,
        **crm_context,
    }


def resolve_customer_crm_pricing_context(customer, selected_business_type=None, selected_segment=None):
    return resolve_party_crm_pricing_context(
        "Customer",
        customer,
        selected_business_type=selected_business_type,
        selected_segment=selected_segment,
    )


def resolve_party_crm_pricing_context(party_type, party_name, selected_business_type=None, selected_segment=None):
    selected_business_type = (selected_business_type or "").strip()
    selected_segment = (selected_segment or "").strip()
    segments = _party_crm_segments(party_type, party_name)
    selected = None

    if selected_business_type or selected_segment:
        for row in segments:
            if selected_business_type and row.get("business_type") != selected_business_type:
                continue
            if selected_segment and row.get("crm_segment") != selected_segment:
                continue
            selected = row
            break

    if not selected:
        selected = next((row for row in segments if cint(row.get("is_primary"))), None)
    if not selected and segments:
        selected = segments[0]

    return {
        "segments": segments,
        "selected": selected or {"business_type": "", "crm_segment": "", "is_primary": 0},
        "has_multiple": len(segments) > 1,
    }


def _customer_crm_segments(customer):
    return _party_crm_segments("Customer", customer)


def _party_crm_segments(party_type, party_name):
    if party_type not in SUPPORTED_PRICING_PARTY_TYPES:
        return []
    if not party_name or not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return []
    rows = frappe.get_all(
        "CRM Segment Assignment",
        filters={"parenttype": party_type, "parent": party_name},
        fields=["business_type", "segment", "is_primary", "idx"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )
    return [
        {
            "business_type": row.business_type or "",
            "crm_segment": row.segment or "",
            "is_primary": 1 if cint(row.is_primary) else 0,
        }
        for row in rows
        if row.business_type or row.segment
    ]


@frappe.whitelist()
def get_agent_dynamic_defaults(sales_person=None):
    return build_dynamic_context(sales_person=sales_person)


@frappe.whitelist()
def get_dimensioning_set_payload(set_name):
    if not set_name:
        return {"set": None}
    sheet = frappe.new_doc("Pricing Sheet")
    set_doc = sheet._get_dimensioning_set_doc(set_name)
    return {"set": sheet._serialize_dimensioning_set(set_doc)}
