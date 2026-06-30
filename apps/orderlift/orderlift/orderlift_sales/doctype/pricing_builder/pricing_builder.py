import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime, nowdate

from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import (
    compute_margin_percent_for_basis,
    get_item_details_map,
    get_latest_item_prices,
)
from orderlift.orderlift_sales.utils.price_list_scope import apply_price_list_company, validate_price_list_scope
from orderlift.sales.utils.pricing_projection import apply_expenses
from orderlift.sales.utils.scenario_policy import resolve_scenario_rule


MAX_WARNING_LINES = 80
MAX_WARNING_LINE_LENGTH = 240
MAX_WARNING_TOTAL_LENGTH = 12000
BUILDER_ITEM_DOCTYPES = ("Pricing Builder Item", "Pricing Builder Manual Item")


class PricingBuilder(Document):
    def validate(self):
        self.default_qty = flt(self.default_qty or 1) or 1
        self.max_items = cint(self.max_items or 0)

    def calculate_items(self):
        rules = _normalize_rules(self.sourcing_rules or [])
        active_buying_lists = _ordered_buying_lists(rules)
        if not active_buying_lists:
            frappe.throw(_("Add at least one active sourcing rule with a Buying Price List."))
        existing_overrides = _existing_override_map(self.builder_items or [])
        selling_price_list_name = (self.selling_price_list_name or "").strip()
        existing_overrides = _merge_override_maps(
            _published_item_price_override_map(selling_price_list_name, self.name),
            existing_overrides,
        )
        manual_items = []

        qty = flt(self.default_qty or 1)
        if qty <= 0:
            qty = 1

        items, item_warnings = _load_builder_items(
            active_buying_lists,
            manual_items=manual_items,
            item_group=(getattr(self, "item_group", "") or "").strip(),
            max_items=cint(self.max_items or 0),
        )
        self.set("builder_items", [])

        if not items:
            self._apply_summary(_empty_summary())
            self.warnings_html = _warnings_html(item_warnings or [_("No items found for the selected buying price lists.")])
            return

        item_codes = [row.get("item") for row in items if row.get("item")]
        item_details = get_item_details_map(item_codes)
        item_meta = _get_builder_item_meta(item_codes)
        published_map = {}
        if selling_price_list_name and frappe.db.exists("Price List", selling_price_list_name):
            published_map = get_latest_item_prices(item_codes, selling_price_list_name, buying=False)

        sheet = frappe.new_doc("Pricing Sheet")
        sheet.customer = ""
        sheet.customer_type = ""
        sheet.tier = ""
        sheet.geography_territory = ""
        sheet.sales_person = ""

        scenario_docs = _get_scenario_docs(rules)
        scenario_caches = sheet._build_scenario_caches(scenario_docs, item_codes)
        customs_cache = {}
        benchmark_cache = {}
        benchmark_runtime_cache = {}
        warnings = list(item_warnings)
        result_rows = []

        for item_row in items:
            item_code = item_row.get("item")
            buying_list = item_row.get("buying_list") or ""
            matched_rule = _match_sourcing_rule(rules, buying_list)
            details = item_details.get(item_code) or {}
            meta = item_meta.get(item_code) or {}
            base_buy = flt(item_row.get("buy_price") or 0)
            status = "Ready"
            status_note = ""

            if not matched_rule:
                result_rows.append(_build_result_row(item_code, buying_list, meta.get("origin") or "", qty, base_buy, flt(published_map.get(item_code) or 0), "Missing Rule", _("No sourcing rule matched buying list {0}.").format(buying_list or "-"), item_group=details.get("item_group") or "", item_category=details.get("custom_item_category") or "", item_name=meta.get("item_name") or item_code, override_selling_price=_existing_override(existing_overrides, item_code, buying_list)))
                continue

            scenario_name = (matched_rule.get("pricing_scenario") or "").strip()
            if not scenario_name or scenario_name not in scenario_caches:
                result_rows.append(_build_result_row(item_code, buying_list, meta.get("origin") or "", qty, base_buy, flt(published_map.get(item_code) or 0), "Missing Rule", _("Select a valid Expenses Policy for buying list {0}.").format(buying_list or "-"), item_group=details.get("item_group") or "", item_category=details.get("custom_item_category") or "", item_name=meta.get("item_name") or item_code, override_selling_price=_existing_override(existing_overrides, item_code, buying_list)))
                continue

            row = frappe._dict(item=item_code, qty=qty, source_buying_price_list=buying_list, source_bundle="")
            cache = scenario_caches.get(scenario_name) or {}
            sheet._set_buy_price_for_row(row, cache.get("buying_price_list"), cache.get("buy_prices") or {}, {cache.get("buying_price_list"): cache.get("buy_prices") or {}}, force_refresh=True)

            base_buy = flt(row.buy_price or 0)
            if base_buy <= 0:
                result_rows.append(_build_result_row(item_code, buying_list, meta.get("origin") or "", qty, base_buy, flt(published_map.get(item_code) or 0), "Missing Buy Price", row.buy_price_message or _("No buying price found for {0}.").format(buying_list or "-"), item_group=details.get("item_group") or "", item_category=details.get("custom_item_category") or "", item_name=meta.get("item_name") or item_code, pricing_scenario=scenario_name, customs_policy=matched_rule.get("customs_policy") or "", benchmark_policy=matched_rule.get("benchmark_policy") or "", override_selling_price=_existing_override(existing_overrides, item_code, buying_list)))
                continue
            base_amount = base_buy * qty
            line_context = {
                "source_buying_price_list": buying_list,
                "sales_person": "",
                "geography_territory": "",
                "customer_type": "",
                "tier": "",
                "item": item_code,
                "source_bundle": "",
                "item_group": details.get("item_group") or "",
                "tariff_number": details.get("customs_tariff_number") or "",
                "material": details.get("custom_customs_material") or details.get("custom_material") or "",
            }

            row_customs_policy = _get_customs_policy_doc(matched_rule.get("customs_policy"), customs_cache)
            customs_calc = sheet._compute_customs_for_row(row, base_amount, item_details, row_customs_policy)
            transport_calc = sheet._compute_transport_for_row(row=row, qty=qty, base_amount=base_amount, item_details=item_details, transport_config=cache.get("transport_config") or {})
            effective_expenses = sheet._inject_transport_expense(cache.get("line_expenses") or [], transport_calc)
            storage_calc = sheet._compute_storage_for_row(row=row, qty=qty, item_details=item_details, storage_config=cache.get("storage_config") or {})
            effective_expenses = sheet._inject_storage_expense(effective_expenses, storage_calc)
            effective_expenses = sheet._strip_scenario_margin_expenses(effective_expenses)

            benchmark_policy_doc = _get_benchmark_policy_doc(matched_rule.get("benchmark_policy"), benchmark_cache)
            benchmark_result = None
            landed_cost = base_buy
            margin_basis = "Base Price"
            if benchmark_policy_doc:
                margin_basis = (getattr(benchmark_policy_doc, "margin_application_basis", "") or "Base Price").strip() or "Base Price"
                runtime = _get_benchmark_runtime_cache(benchmark_policy_doc, item_codes, benchmark_runtime_cache)
                landed_cost = sheet._compute_landed_cost(base_buy, qty, effective_expenses, customs_calc, transport_calc)
                benchmark_result = sheet._resolve_benchmark_for_row(row, landed_cost, benchmark_policy_doc, item_details, runtime.get("price_map") or {}, runtime.get("source_types") or {}, line_context)
                effective_expenses = sheet._inject_benchmark_margin_expense(
                    effective_expenses,
                    benchmark_result,
                    benchmark_policy_doc,
                    base_buy,
                    landed_cost,
                )

            pricing = apply_expenses(base_unit=base_buy, qty=qty, expenses=effective_expenses)
            component_summary = sheet._summarize_pricing_components(pricing.get("steps") or [], qty)
            projected_total = flt(pricing.get("projected_line") or 0) + flt(customs_calc.get("applied") or 0)
            projected_unit = projected_total / qty if qty else 0
            benchmark_reference = flt((benchmark_result or {}).get("benchmark_reference") or 0)
            published_price = flt(published_map.get(item_code) or 0)
            margin_amount = flt(component_summary.get("margin_unit") or 0)
            total_margin_amount = margin_amount
            final_margin_pct = compute_margin_percent_for_basis(
                margin_amount,
                margin_basis,
                base_buy,
                landed_cost,
            )
            total_margin_pct = compute_margin_percent_for_basis(
                total_margin_amount,
                margin_basis,
                base_buy,
                landed_cost,
            )
            cost_before_margin = (
                flt(base_buy)
                + flt(component_summary.get("policy_expense_unit") or 0)
                + (flt(customs_calc.get("applied") or 0) / qty if qty else 0)
            )
            override_selling_price = _existing_override(existing_overrides, item_code, buying_list)
            if flt(override_selling_price) > 0:
                final_margin_pct = _override_margin_percent(
                    override_selling_price,
                    margin_basis,
                    base_buy,
                    cost_before_margin,
                    final_margin_pct,
                )
                total_margin_pct = final_margin_pct
            discount_meta = extract_benchmark_discount_metadata(benchmark_result, benchmark_policy_doc)
            calculation_breakdown = _build_calculation_breakdown(
                qty=qty,
                base_buy=base_buy,
                buying_list=buying_list,
                pricing_scenario=scenario_name,
                customs_policy=matched_rule.get("customs_policy") or "",
                benchmark_policy=matched_rule.get("benchmark_policy") or "",
                pricing=pricing,
                customs_calc=customs_calc,
                benchmark_result=benchmark_result,
                benchmark_policy_doc=benchmark_policy_doc,
                discount_meta=discount_meta,
                margin_basis=margin_basis,
                landed_cost=landed_cost,
                component_summary=component_summary,
                projected_unit=projected_unit,
            )

            if base_buy <= 0:
                status = "Missing Buy Price"
                status_note = row.buy_price_message or _("No buying price found for {0}.").format(buying_list or "-")
            elif benchmark_policy_doc and benchmark_reference <= 0:
                status = "No Benchmark"
                status_note = "; ".join((benchmark_result or {}).get("warnings") or [])

            result_rows.append({
                "item": item_code,
                "item_name": meta.get("item_name") or item_code,
                "item_group": details.get("item_group") or "",
                "item_category": details.get("custom_item_category") or "",
                "material": details.get("custom_customs_material") or details.get("custom_material") or "",
                "customs_tariff_number": customs_calc.get("tariff_number") or details.get("customs_tariff_number") or "",
                "buying_list": buying_list,
                "origin": meta.get("origin") or "",
                "base_buy_price": base_buy,
                "expenses": flt(component_summary.get("policy_expense_unit") or 0),
                "customs_base_value": flt(customs_calc.get("base_value") or 0) / qty if qty else 0,
                "customs_value_per_kg": flt(customs_calc.get("value_per_kg") or 0),
                "customs_amount": flt(customs_calc.get("applied") or 0) / qty if qty else 0,
                "customs_weight_kg": (flt(customs_calc.get("weight_kg") or 0) / qty if qty else 0),
                "customs_line_weight_kg": flt(customs_calc.get("weight_kg") or 0),
                "customs_unit_weight_kg": flt(customs_calc.get("unit_weight_kg") or 0),
                "customs_package_weight_kg": flt(customs_calc.get("package_weight_kg") or 0),
                "packaging_units_per_package": flt(customs_calc.get("units_per_package") or 0),
                "packaging_package_count": flt(customs_calc.get("package_count") or 0),
                "packaging_profile_source": customs_calc.get("packaging_source") or "",
                "customs_basis": customs_calc.get("basis") or "",
                "customs_value_delta": flt(customs_calc.get("customs_value_delta") or 0) / qty if qty else 0,
                "customs_value_delta_tax_rate": flt(customs_calc.get("customs_value_delta_tax_rate") or 0),
                "customs_value_delta_tax_amount": flt(customs_calc.get("customs_value_delta_tax_amount") or 0) / qty if qty else 0,
                "margin_amount": margin_amount,
                "total_margin_amount": total_margin_amount,
                "avg_benchmark": benchmark_reference,
                "projected_price": projected_unit,
                "override_selling_price": override_selling_price,
                "final_margin_pct": final_margin_pct,
                "total_margin_pct": total_margin_pct,
                "target_margin_percent": discount_meta.get("target_margin_percent"),
                "margin_basis": margin_basis,
                "benchmark_is_fallback": discount_meta.get("benchmark_is_fallback"),
                "benchmark_rule_label": discount_meta.get("benchmark_rule_label"),
                "benchmark_rule_max_discount_percent": discount_meta.get("benchmark_rule_max_discount_percent"),
                "fallback_max_discount_percent": discount_meta.get("fallback_max_discount_percent"),
                "policy_max_discount_percent": discount_meta.get("policy_max_discount_percent"),
                "published_price": published_price,
                "status": status,
                "status_note": status_note,
                "pricing_scenario": scenario_name,
                "customs_policy": matched_rule.get("customs_policy") or "",
                "benchmark_policy": matched_rule.get("benchmark_policy") or "",
                "calculation_breakdown_json": frappe.as_json(calculation_breakdown),
                "selected": 0,
            })

            if customs_calc.get("warning"):
                warnings.append(_("{0}: {1}").format(item_code, customs_calc.get("warning")))
            for msg in (benchmark_result or {}).get("warnings") or []:
                warnings.append(_("{0}: {1}").format(item_code, msg))
            if transport_calc.get("warning"):
                warnings.append(_("{0}: {1}").format(item_code, transport_calc.get("warning")))
            if storage_calc.get("warning"):
                warnings.append(_("{0}: {1}").format(item_code, storage_calc.get("warning")))

        for row in result_rows:
            self.append("builder_items", row)

        summary = _build_summary(result_rows)
        self._apply_summary(summary)
        self.warnings_html = _warnings_html(_dedupe_warnings(warnings))

    def publish_prices(self, selected_only=False):
        price_list_name = _ensure_selling_price_list((self.selling_price_list_name or "").strip())
        stamp_price_list_from_builder(price_list_name, self)
        currency = frappe.db.get_value("Price List", price_list_name, "currency") or frappe.defaults.get_global_default("currency")
        created = 0
        updated = 0
        skipped = 0
        errors = []
        brand_map = _builder_source_brand_map(self.builder_items or [])

        for row in self.builder_items or []:
            if selected_only and not cint(row.selected):
                continue
            item_code = (row.item or "").strip()
            if not item_code:
                skipped += 1
                continue
            status = _effective_builder_status(row)
            if status in {"Missing Rule", "Missing Buy Price"}:
                skipped += 1
                continue
            final_price = flt(row.override_selling_price or 0) or flt(row.projected_price or 0)
            if final_price <= 0:
                skipped += 1
                continue
            try:
                existing_name = _get_latest_item_price_name(item_code, price_list_name)
                if existing_name:
                    doc = frappe.get_doc("Item Price", existing_name)
                    doc.price_list_rate = final_price
                    if hasattr(doc, "currency"):
                        doc.currency = currency
                    if hasattr(doc, "selling"):
                        doc.selling = 1
                    if hasattr(doc, "buying"):
                        doc.buying = 0
                    _set_builder_source_brand(doc, row, brand_map)
                    stamp_item_price_from_builder_row(doc, self.name, row)
                    _save_item_price_from_builder(doc)
                    updated += 1
                else:
                    doc = frappe.new_doc("Item Price")
                    doc.price_list = price_list_name
                    doc.item_code = item_code
                    doc.price_list_rate = final_price
                    if hasattr(doc, "currency"):
                        doc.currency = currency
                    if hasattr(doc, "selling"):
                        doc.selling = 1
                    if hasattr(doc, "buying"):
                        doc.buying = 0
                    if hasattr(doc, "uom"):
                        doc.uom = frappe.db.get_value("Item", item_code, "stock_uom")
                    if hasattr(doc, "valid_from"):
                        doc.valid_from = nowdate()
                    _set_builder_source_brand(doc, row, brand_map)
                    stamp_item_price_from_builder_row(doc, self.name, row)
                    _insert_item_price_from_builder(doc)
                    created += 1
                row.published_price = final_price
            except Exception:
                errors.append(_("{0}: publish failed").format(item_code))

        self.warnings_html = _warnings_html(errors)
        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors, "price_list": price_list_name}

    def _apply_summary(self, summary):
        self.total_items = cint(summary.get("item_count") or 0)
        self.ready_items = cint(summary.get("ready_count") or 0)
        self.changed_items = cint(summary.get("changed_count") or 0)
        self.new_items = cint(summary.get("new_count") or 0)
        self.missing_items = cint(summary.get("missing_count") or 0)


def cleanup_pricing_builder_history(doc, method=None):
    builder_name = (doc.get("name") or "").strip()
    if not builder_name:
        return
    if frappe.db.exists("DocType", "Pricing Builder History"):
        frappe.db.delete("Pricing Builder History", {"pricing_builder": builder_name})
    if frappe.db.has_column("Item Price", "custom_pricing_builder"):
        frappe.db.sql(
            """
            UPDATE `tabItem Price`
            SET custom_pricing_builder = NULL
            WHERE custom_pricing_builder = %s
            """,
            (builder_name,),
        )
    if frappe.db.has_column("Pricing Sheet Item", "pricing_builder"):
        frappe.db.sql(
            """
            UPDATE `tabPricing Sheet Item`
            SET pricing_builder = NULL
            WHERE pricing_builder = %s
            """,
            (builder_name,),
        )
    if frappe.db.has_column("Price List", "custom_pricing_builder"):
        frappe.db.sql(
            """
            UPDATE `tabPrice List`
            SET custom_pricing_builder = NULL
            WHERE custom_pricing_builder = %s
            """,
            (builder_name,),
        )


def _save_item_price_from_builder(doc):
    previous_flag = getattr(frappe.flags, "orderlift_pricing_builder_publish", False)
    frappe.flags.orderlift_pricing_builder_publish = True
    try:
        doc.save(ignore_permissions=True)
    finally:
        frappe.flags.orderlift_pricing_builder_publish = previous_flag


def _insert_item_price_from_builder(doc):
    previous_flag = getattr(frappe.flags, "orderlift_pricing_builder_publish", False)
    frappe.flags.orderlift_pricing_builder_publish = True
    try:
        doc.insert(ignore_permissions=True)
    finally:
        frappe.flags.orderlift_pricing_builder_publish = previous_flag


def cleanup_item_builder_rows(doc, method=None):
    item_code = (doc.get("name") or doc.get("item_code") or "").strip()
    if not item_code:
        return
    for doctype in BUILDER_ITEM_DOCTYPES:
        if frappe.db.exists("DocType", doctype):
            frappe.db.delete(doctype, {"item": item_code})


@frappe.whitelist()
def calculate_builder_doc(name):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.check_permission("write")
    doc.calculate_items()
    doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def publish_builder_doc(name, selected_only=0):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.check_permission("write")
    out = doc.publish_prices(selected_only=cint(selected_only) == 1)
    doc.save(ignore_permissions=True)
    return out


def _normalize_rules(rows):
    out = []
    for idx, row in enumerate(rows or [], start=1):
        get = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
        out.append({
            "source_buying_price_list": (get("buying_price_list", "") or get("source_buying_price_list", "") or "").strip(),
            "pricing_scenario": (get("pricing_scenario", "") or "").strip(),
            "customs_policy": (get("customs_policy", "") or "").strip(),
            "benchmark_policy": (get("benchmark_policy", "") or "").strip(),
            "priority": 10,
            "sequence": idx,
            "is_active": 1 if cint(get("is_active", 1)) else 0,
            "idx": idx,
        })
    return out


def _ordered_buying_lists(rules):
    out = []
    seen = set()
    for row in rules:
        if not cint(row.get("is_active") or 0):
            continue
        buying_list = (row.get("source_buying_price_list") or "").strip()
        if not buying_list or buying_list in seen:
            continue
        out.append(buying_list)
        seen.add(buying_list)
    return out


def _normalize_manual_items(rows, buying_lists):
    out = []
    seen = set()
    for row in rows or []:
        get = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
        if not cint(get("is_active", 1)):
            continue
        item_code = (get("item", "") or "").strip()
        if not item_code or item_code in seen:
            continue
        out.append({
            "item": item_code,
            "buying_list": (get("buying_price_list", "") or get("buying_list", "") or "").strip(),
        })
        seen.add(item_code)
    return out


def _load_builder_items(buying_lists, manual_items=None, item_group=None, max_items=0):
    manual_items = manual_items or []
    price_lists = list(buying_lists or [])
    for row in manual_items:
        buying_list = row.get("buying_list")
        if buying_list and buying_list not in price_lists:
            price_lists.append(buying_list)

    price_rows = _get_latest_buying_list_rows(price_lists)
    if not price_rows and not manual_items:
        return [], [_("No buying prices found in the selected buying price lists.")]
    item_priority = {name: idx for idx, name in enumerate(buying_lists)}
    grouped = {}
    price_by_key = {}
    for row in price_rows:
        item_code = row.get("item_code")
        if not item_code:
            continue
        price_by_key[(row.get("price_list"), item_code)] = flt(row.get("price_list_rate") or 0)
        if row.get("price_list") not in buying_lists:
            continue
        bucket = grouped.get(item_code)
        candidate = {"item": item_code, "buying_list": row.get("price_list") or "", "buy_price": flt(row.get("price_list_rate") or 0)}
        if not bucket or item_priority.get(candidate["buying_list"], 9999) < item_priority.get(bucket["buying_list"], 9999):
            grouped[item_code] = candidate
    warnings = []
    items = []
    if grouped:
        filters = {"name": ["in", list(grouped.keys())], "disabled": 0}
        if item_group and item_group != "All Item Groups":
            from orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator import _descendant_leaf_item_groups, _is_item_group_node
            if _is_item_group_node(item_group):
                descendants = _descendant_leaf_item_groups(item_group)
                if descendants:
                    filters["item_group"] = ["in", descendants]
                else:
                    warnings.append(_("Selected Item Group has no leaf item groups."))
            else:
                filters["item_group"] = item_group
        item_rows = frappe.get_all("Item", filters=filters, fields=["name"], order_by="name asc", limit_page_length=max_items if max_items > 0 else 0)
        items = [grouped.get(row.get("name")) for row in item_rows if grouped.get(row.get("name"))]
    elif not manual_items:
        warnings.append(_("No buying prices found in the selected buying price lists."))

    if manual_items:
        items = _merge_manual_items(items, manual_items, grouped, price_by_key, warnings)

    if not items:
        warnings.append(_("No items matched the selected buying lists and filters."))
    return items, warnings


def _merge_manual_items(items, manual_items, auto_grouped, price_by_key, warnings):
    item_codes = [row.get("item") for row in manual_items if row.get("item")]
    valid_items = set(frappe.get_all("Item", filters={"name": ["in", item_codes], "disabled": 0}, pluck="name", limit_page_length=0)) if item_codes else set()
    merged = list(items or [])
    index_by_item = {row.get("item"): idx for idx, row in enumerate(merged) if row and row.get("item")}
    for manual in manual_items:
        item_code = manual.get("item")
        if not item_code:
            continue
        if item_code not in valid_items:
            warnings.append(_("Manual item {0} was not found or is disabled.").format(item_code))
            continue
        buying_list = manual.get("buying_list") or ""
        candidate = {
            "item": item_code,
            "buying_list": buying_list,
            "buy_price": flt(price_by_key.get((buying_list, item_code)) or 0),
        }
        if item_code in index_by_item:
            merged[index_by_item[item_code]] = candidate
        else:
            index_by_item[item_code] = len(merged)
            merged.append(candidate)
    return merged


def _get_latest_buying_list_rows(buying_lists):
    if not buying_lists:
        return []
    conditions = ["ip.price_list in %(price_lists)s"]
    params = {"price_lists": tuple(buying_lists), "today": nowdate()}
    if frappe.db.has_column("Item Price", "enabled"):
        conditions.append("ip.enabled = 1")
    if frappe.db.has_column("Item Price", "buying"):
        conditions.append("ip.buying = 1")
    if frappe.db.has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if frappe.db.has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")
    order_by = "ip.price_list ASC, ip.item_code ASC, ip.modified DESC"
    if frappe.db.has_column("Item Price", "valid_from"):
        order_by = "ip.price_list ASC, ip.item_code ASC, ip.valid_from DESC, ip.modified DESC"
    rows = frappe.db.sql(f"SELECT ip.price_list, ip.item_code, ip.price_list_rate FROM `tabItem Price` ip WHERE {' AND '.join(conditions)} ORDER BY {order_by}", params, as_dict=True)
    out = []
    seen = set()
    for row in rows:
        key = (row.get("price_list"), row.get("item_code"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _get_builder_item_meta(item_codes):
    if not item_codes:
        return {}
    fields = ["name", "item_name"]
    if frappe.db.has_column("Item", "country_of_origin"):
        fields.append("country_of_origin")
    rows = frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=fields, limit_page_length=0)
    out = {}
    for row in rows:
        out[row.name] = {"item_name": row.get("item_name") or row.name, "origin": row.get("country_of_origin") or ""}
    return out


def _get_scenario_docs(rules):
    names = sorted({row.get("pricing_scenario") for row in rules if row.get("pricing_scenario")})
    docs = {}
    for name in names:
        if frappe.db.exists("Pricing Scenario", name):
            docs[name] = frappe.get_doc("Pricing Scenario", name)
    return docs


def _match_sourcing_rule(rules, buying_list):
    return resolve_scenario_rule(rules, context={"source_buying_price_list": buying_list})


def _get_customs_policy_doc(name, cache):
    name = (name or "").strip()
    if not name:
        return None
    if name not in cache and frappe.db.exists("Pricing Customs Policy", name):
        cache[name] = frappe.get_doc("Pricing Customs Policy", name)
    return cache.get(name)


def _get_benchmark_policy_doc(name, cache):
    name = (name or "").strip()
    if not name:
        return None
    if name not in cache and frappe.db.exists("Pricing Benchmark Policy", name):
        cache[name] = frappe.get_doc("Pricing Benchmark Policy", name)
    return cache.get(name)


def _get_benchmark_runtime_cache(benchmark_policy_doc, item_codes, cache):
    key = benchmark_policy_doc.name
    if key in cache:
        return cache[key]
    price_map = {}
    source_types = {}
    for src in benchmark_policy_doc.benchmark_sources or []:
        if not cint(src.is_active):
            continue
        price_list = src.price_list
        if not price_list:
            continue
        if price_list not in source_types:
            source_types[price_list] = _price_list_type(price_list)
        if price_list not in price_map:
            price_map[price_list] = get_latest_item_prices(item_codes, price_list, buying=None)
    cache[key] = {"price_map": price_map, "source_types": source_types}
    return cache[key]


def _price_list_type(price_list_name):
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


def _get_latest_item_price_name(item_code, price_list):
    rows = frappe.get_all("Item Price", filters={"item_code": item_code, "price_list": price_list}, fields=["name"], order_by="modified desc", limit_page_length=1)
    return rows[0].name if rows else ""


def _effective_margin_pct(sell_price, cost_before_margin, fallback_percent=0.0):
    if flt(cost_before_margin) <= 0:
        return flt(fallback_percent)
    return flt(((flt(sell_price) - flt(cost_before_margin)) / flt(cost_before_margin)) * 100)


def _override_margin_percent(override_price, margin_basis, base_buy, cost_before_margin, fallback_percent=0.0):
    if flt(override_price) <= 0:
        return flt(fallback_percent)
    actual_margin = flt(override_price) - flt(cost_before_margin)
    return compute_margin_percent_for_basis(actual_margin, margin_basis, base_buy, cost_before_margin)


def _publish_state(projected_price, published_price):
    projected_price = flt(projected_price)
    published_price = flt(published_price)
    if published_price <= 0:
        return "New"
    if abs(projected_price - published_price) < 0.0001:
        return "Same"
    return "Changed"


def _empty_summary():
    return {"item_count": 0, "ready_count": 0, "changed_count": 0, "new_count": 0, "missing_count": 0}


def _build_summary(rows):
    summary = _empty_summary()
    summary["item_count"] = len(rows)
    for row in rows:
        status = _effective_builder_status(row)
        if status in {"Ready", "No Benchmark"}:
            summary["ready_count"] += 1
        if _publish_state(row.get("override_selling_price") or row.get("projected_price"), row.get("published_price")) == "Changed":
            summary["changed_count"] += 1
        if _publish_state(row.get("override_selling_price") or row.get("projected_price"), row.get("published_price")) == "New":
            summary["new_count"] += 1
        if status in {"Missing Rule", "Missing Buy Price"}:
            summary["missing_count"] += 1
    return summary


def _dedupe_warnings(messages):
    seen = set()
    out = []
    for msg in messages or []:
        value = (msg or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _existing_override_map(rows):
    exact = {}
    by_item = {}
    duplicate_items = set()
    for row in rows or []:
        value = flt(_row_value(row, "override_selling_price") or 0)
        if value <= 0:
            continue
        item_code = (_row_value(row, "item") or "").strip()
        buying_list = (_row_value(row, "buying_list") or "").strip()
        if not item_code:
            continue
        if buying_list:
            exact[(item_code, buying_list)] = value
        if item_code in by_item and by_item[item_code] != value:
            duplicate_items.add(item_code)
        else:
            by_item[item_code] = value
    for item_code in duplicate_items:
        by_item.pop(item_code, None)
    return {"exact": exact, "by_item": by_item}


def _merge_override_maps(base_overrides, preferred_overrides):
    merged = {"exact": {}, "by_item": {}}
    for source in (base_overrides or {}, preferred_overrides or {}):
        merged["exact"].update(source.get("exact") or {})
        merged["by_item"].update(source.get("by_item") or {})
    return merged


def _published_item_price_override_map(price_list_name, builder_name):
    price_list_name = (price_list_name or "").strip()
    builder_name = (builder_name or "").strip()
    required = (
        ("Item Price", "custom_pricing_builder"),
        ("Item Price", "custom_source_buying_price_list"),
        ("Item Price", "custom_builder_price_overridden"),
    )
    if not price_list_name or not builder_name or not all(_doctype_has_column(dt, field) for dt, field in required):
        return {"exact": {}, "by_item": {}}

    rows = frappe.get_all(
        "Item Price",
        filters={
            "price_list": price_list_name,
            "custom_pricing_builder": builder_name,
            "custom_builder_price_overridden": 1,
        },
        fields=["item_code", "custom_source_buying_price_list", "price_list_rate"],
        limit_page_length=0,
    )
    return _existing_override_map(
        [
            frappe._dict(
                item=row.item_code,
                buying_list=row.custom_source_buying_price_list,
                override_selling_price=row.price_list_rate,
            )
            for row in rows
        ]
    )


def _existing_override(overrides, item_code, buying_list):
    item_code = (item_code or "").strip()
    buying_list = (buying_list or "").strip()
    if not item_code:
        return 0
    exact = (overrides or {}).get("exact") or {}
    if buying_list and (item_code, buying_list) in exact:
        return flt(exact.get((item_code, buying_list)) or 0)
    return flt(((overrides or {}).get("by_item") or {}).get(item_code) or 0)


def _warnings_html(messages):
    items = [_truncate_warning_line(item) for item in _aggregate_warnings(messages)]
    if not items:
        return ""
    overflow = max(0, len(items) - MAX_WARNING_LINES)
    selected = items[:MAX_WARNING_LINES]
    if overflow:
        selected.append(_("{0} more warning(s) omitted. Review affected rows in the Builder table.").format(overflow))
    text = "\n".join(selected)
    while len(text) > MAX_WARNING_TOTAL_LENGTH and len(selected) > 1:
        selected.pop(-2 if overflow else -1)
        text = "\n".join(selected)
    if len(text) <= MAX_WARNING_TOTAL_LENGTH:
        return text
    return text[: MAX_WARNING_TOTAL_LENGTH - 80].rstrip() + "\n" + _("Additional warnings omitted to keep this record saveable.")


def _aggregate_warnings(messages):
    grouped = {}
    passthrough = []
    for msg in _dedupe_warnings(messages):
        item_code, detail = _split_item_warning(msg)
        if not item_code or not detail:
            passthrough.append(msg)
            continue
        grouped.setdefault(detail, [])
        if item_code not in grouped[detail]:
            grouped[detail].append(item_code)

    out = list(passthrough)
    for detail, item_codes in grouped.items():
        out.append(_format_grouped_warning(detail, item_codes))
    return out


def _split_item_warning(message):
    text = (message or "").strip()
    if ": " not in text:
        return "", text
    item_code, detail = text.split(": ", 1)
    item_code = item_code.strip()
    detail = detail.strip()
    if not item_code or " " in item_code or not detail:
        return "", text
    return item_code, detail


def _format_grouped_warning(detail, item_codes):
    visible = list(item_codes or [])[:12]
    suffix = ""
    hidden = max(0, len(item_codes or []) - len(visible))
    if hidden:
        suffix = _(" and {0} more").format(hidden)
    return _("{0}: affected articles {1}{2}").format(detail, ", ".join(visible), suffix)


def _truncate_warning_line(message):
    text = (message or "").strip()
    if len(text) <= MAX_WARNING_LINE_LENGTH:
        return text
    return text[: MAX_WARNING_LINE_LENGTH - 3].rstrip() + "..."


def _build_result_row(item_code, buying_list, origin, qty, base_buy, published_price, status, status_note, item_group="", item_category="", item_name="", pricing_scenario="", customs_policy="", benchmark_policy="", override_selling_price=0):
    return {
        "item": item_code,
        "item_name": item_name or item_code,
        "item_group": item_group,
        "item_category": item_category,
        "material": "",
        "customs_tariff_number": "",
        "buying_list": buying_list,
        "origin": origin,
        "base_buy_price": base_buy,
        "expenses": 0,
        "customs_base_value": 0,
        "customs_value_per_kg": 0,
        "customs_amount": 0,
        "customs_weight_kg": 0,
        "customs_line_weight_kg": 0,
        "customs_unit_weight_kg": 0,
        "customs_package_weight_kg": 0,
        "packaging_units_per_package": 0,
        "packaging_package_count": 0,
        "packaging_profile_source": "",
        "customs_basis": "",
        "margin_amount": 0,
        "total_margin_amount": 0,
        "avg_benchmark": 0,
        "projected_price": 0,
        "override_selling_price": flt(override_selling_price or 0),
        "final_margin_pct": 0,
        "total_margin_pct": 0,
        "target_margin_percent": 0,
        "margin_basis": "",
        "benchmark_is_fallback": 0,
        "benchmark_rule_label": "",
        "benchmark_rule_max_discount_percent": 0,
        "fallback_max_discount_percent": 0,
        "policy_max_discount_percent": 0,
        "published_price": published_price,
        "status": status,
        "status_note": status_note,
        "pricing_scenario": pricing_scenario,
        "customs_policy": customs_policy,
        "benchmark_policy": benchmark_policy,
        "calculation_breakdown_json": "",
        "selected": 0,
    }


def _build_calculation_breakdown(
    *,
    qty,
    base_buy,
    buying_list,
    pricing_scenario,
    customs_policy,
    benchmark_policy,
    pricing,
    customs_calc,
    benchmark_result,
    benchmark_policy_doc,
    discount_meta,
    margin_basis,
    landed_cost,
    component_summary,
    projected_unit,
):
    qty = flt(qty or 1) or 1
    customs_total = flt((customs_calc or {}).get("applied") or 0)
    customs_unit = customs_total / qty if qty else 0
    expenses_unit = flt(component_summary.get("policy_expense_unit") or 0)
    margin_unit = flt(component_summary.get("margin_unit") or 0)
    total_margin_unit = margin_unit + flt(component_summary.get("tier_unit") or 0) + flt(component_summary.get("zone_unit") or 0)
    cost_before_margin = flt(base_buy) + expenses_unit + customs_unit

    return {
        "summary": {
            "qty": qty,
            "base_unit": flt(base_buy),
            "expenses_unit": expenses_unit,
            "customs_unit": customs_unit,
            "cost_before_margin": cost_before_margin,
            "margin_unit": margin_unit,
            "total_margin_unit": total_margin_unit,
            "projected_unit": flt(projected_unit),
            "projected_total": flt(projected_unit) * qty,
            "buying_list": buying_list or "",
        },
        "expenses": {
            "policy": pricing_scenario or "",
            "unit": expenses_unit,
            "total": expenses_unit * qty,
            "steps": _build_expense_step_breakdown((pricing or {}).get("steps") or [], qty),
        },
        "customs": _build_customs_breakdown(customs_calc, qty, customs_policy),
        "margin": _build_margin_breakdown(
            benchmark_result=benchmark_result,
            benchmark_policy_doc=benchmark_policy_doc,
            discount_meta=discount_meta,
            benchmark_policy=benchmark_policy,
            margin_basis=margin_basis,
            base_buy=base_buy,
            landed_cost=landed_cost,
            margin_unit=margin_unit,
            total_margin_unit=total_margin_unit,
        ),
    }


def _build_expense_step_breakdown(steps, qty):
    out = []
    for step in steps or []:
        source = (step.get("override_source") or "").strip()
        if source in {"pricing_policy", "tier_modifier", "zone_modifier"}:
            continue
        delta_unit = flt(step.get("delta_unit") or 0)
        delta_line = flt(step.get("delta_line") or 0)
        delta_sheet = flt(step.get("delta_sheet") or 0)
        unit_amount = delta_unit + (delta_line / qty if qty else 0) + (delta_sheet / qty if qty else 0)
        out.append({
            "label": step.get("label") or _("Expense"),
            "type": step.get("type") or "",
            "value": flt(step.get("value") or 0),
            "applies_to": step.get("applies_to") or "",
            "scope": step.get("scope") or "",
            "basis": flt(step.get("basis") or 0),
            "unit_amount": unit_amount,
            "total_amount": unit_amount * qty,
            "delta_unit": delta_unit,
            "delta_line": delta_line,
            "delta_sheet": delta_sheet,
            "running_total": flt(step.get("running_total") or 0),
            "sequence": cint(step.get("sequence") or 0),
        })
    return out


def _build_customs_breakdown(customs_calc, qty, customs_policy):
    customs_calc = customs_calc or {}
    applied = flt(customs_calc.get("applied") or 0)
    delta_tax_amount = flt(customs_calc.get("customs_value_delta_tax_amount") or 0)
    base_customs_total = applied - delta_tax_amount
    return {
        "policy": customs_policy or "",
        "unit": applied / qty if qty else 0,
        "total": applied,
        "base_customs_total": base_customs_total,
        "base_customs_unit": base_customs_total / qty if qty else 0,
        "basis": customs_calc.get("basis") or "",
        "mode": customs_calc.get("mode") or "",
        "tariff_number": customs_calc.get("tariff_number") or "",
        "material": customs_calc.get("material") or "",
        "base_value": flt(customs_calc.get("base_value") or 0),
        "value_per_kg": flt(customs_calc.get("value_per_kg") or 0),
        "weight_kg": flt(customs_calc.get("weight_kg") or 0),
        "unit_weight_kg": flt(customs_calc.get("unit_weight_kg") or 0),
        "package_weight_kg": flt(customs_calc.get("package_weight_kg") or 0),
        "units_per_package": flt(customs_calc.get("units_per_package") or 0),
        "package_count": flt(customs_calc.get("package_count") or 0),
        "packaging_source": customs_calc.get("packaging_source") or "",
        "rate_percent": flt(customs_calc.get("total_percent") or 0),
        "component_display": customs_calc.get("component_display") or "",
        "warning": customs_calc.get("warning") or "",
        "customs_value_delta": flt(customs_calc.get("customs_value_delta") or 0),
        "customs_value_delta_tax_rate": flt(customs_calc.get("customs_value_delta_tax_rate") or 0),
        "customs_value_delta_tax_amount": delta_tax_amount,
        "customs_value_delta_tax_template": customs_calc.get("customs_value_delta_tax_template") or "",
    }


def _build_margin_breakdown(
    *,
    benchmark_result,
    benchmark_policy_doc,
    discount_meta,
    benchmark_policy,
    margin_basis,
    base_buy,
    landed_cost,
    margin_unit,
    total_margin_unit,
):
    benchmark_result = benchmark_result or {}
    matched_rule = benchmark_result.get("matched_rule") or {}
    target_margin = flt(discount_meta.get("target_margin_percent") or 0)
    basis = (margin_basis or "Base Price").strip() or "Base Price"
    if basis == "Base Price":
        basis_amount = flt(base_buy)
    else:
        basis_amount = flt(landed_cost)

    return {
        "policy": benchmark_policy or "",
        "policy_name": getattr(benchmark_policy_doc, "policy_name", "") or "",
        "basis": basis,
        "basis_amount": basis_amount,
        "landed_cost": flt(landed_cost),
        "target_margin_percent": target_margin,
        "unit": flt(margin_unit),
        "total_unit": flt(total_margin_unit),
        "is_fallback": 1 if benchmark_result.get("is_fallback") else 0,
        "benchmark_reference": flt(benchmark_result.get("benchmark_reference") or 0),
        "source_count": cint(benchmark_result.get("source_count") or 0),
        "min_sources_required": cint(benchmark_result.get("min_sources_required") or 0),
        "method": benchmark_result.get("method") or "",
        "ratio": flt(benchmark_result.get("ratio") or 0),
        "rule_label": discount_meta.get("benchmark_rule_label") or _format_benchmark_rule_label(matched_rule, benchmark_result.get("is_fallback")),
        "ratio_min": flt(matched_rule.get("ratio_min") or 0),
        "ratio_max": flt(matched_rule.get("ratio_max") or 0),
        "max_discount_percent": flt(discount_meta.get("policy_max_discount_percent") or 0),
        "warnings": benchmark_result.get("warnings") or [],
    }


def final_selling_price_for_builder_row(row):
    return flt(_row_value(row, "override_selling_price") or 0) or flt(_row_value(row, "projected_price") or 0)


def _effective_builder_status(row):
    status = (_row_value(row, "status") or "").strip()
    if status != "Missing Rule" and flt(_row_value(row, "base_buy_price") or 0) <= 0:
        return "Missing Buy Price"
    return status or "Ready"


def extract_benchmark_discount_metadata(benchmark_result, benchmark_policy_doc):
    fallback_max_discount = flt(_row_value(benchmark_policy_doc, "fallback_max_discount_percent", 0) or 0)
    target_margin = flt((benchmark_result or {}).get("target_margin_percent") or 0)
    is_fallback = 1 if (benchmark_result or {}).get("is_fallback") else 0
    matched_rule = (benchmark_result or {}).get("matched_rule") or {}
    rule_max_discount = 0 if is_fallback else flt(matched_rule.get("max_discount_percent") or 0)
    policy_max_discount = fallback_max_discount if is_fallback else rule_max_discount

    return {
        "target_margin_percent": target_margin,
        "benchmark_is_fallback": is_fallback,
        "benchmark_rule_label": _format_benchmark_rule_label(matched_rule, is_fallback),
        "benchmark_rule_max_discount_percent": rule_max_discount,
        "fallback_max_discount_percent": fallback_max_discount,
        "policy_max_discount_percent": policy_max_discount,
    }


def stamp_price_list_from_builder(price_list_name, builder_doc):
    if not price_list_name or not frappe.db.exists("Price List", price_list_name):
        return
    values = {}
    if _doctype_has_column("Price List", "custom_pricing_builder"):
        values["custom_pricing_builder"] = builder_doc.name
    if _doctype_has_column("Price List", "custom_source_buying_price_lists"):
        values["custom_source_buying_price_lists"] = "\n".join(_builder_source_buying_lists(builder_doc))
    if values:
        frappe.db.set_value("Price List", price_list_name, values, update_modified=False)


def stamp_item_price_from_builder_row(doc, builder_name, row, rebuild_time=None):
    override_price = flt(_row_value(row, "override_selling_price") or 0)
    final_margin_pct = flt(_row_value(row, "final_margin_pct") or 0)
    if override_price > 0:
        projected = flt(_row_value(row, "projected_price") or 0)
        margin_unit = flt(_row_value(row, "margin_amount") or 0)
        base_buy = flt(_row_value(row, "base_buy_price") or 0)
        margin_basis = (_row_value(row, "margin_basis") or "").strip() or "Base Price"
        cost_before_margin = max(projected - margin_unit, 0)
        final_margin_pct = _override_margin_percent(
            override_price,
            margin_basis,
            base_buy,
            cost_before_margin or base_buy,
            final_margin_pct,
        )
    values = {
        "custom_pricing_builder": builder_name,
        "custom_source_buying_price_list": _row_value(row, "buying_list"),
        "custom_pricing_scenario": _row_value(row, "pricing_scenario"),
        "custom_customs_policy": _row_value(row, "customs_policy"),
        "custom_benchmark_policy": _row_value(row, "benchmark_policy"),
        "custom_benchmark_is_fallback": 1 if cint(_row_value(row, "benchmark_is_fallback")) else 0,
        "custom_benchmark_rule_label": _row_value(row, "benchmark_rule_label"),
        "custom_benchmark_rule_max_discount_percent": flt(_row_value(row, "benchmark_rule_max_discount_percent") or 0),
        "custom_fallback_max_discount_percent": flt(_row_value(row, "fallback_max_discount_percent") or 0),
        "custom_policy_max_discount_percent": flt(_row_value(row, "policy_max_discount_percent") or 0),
        "custom_target_margin_percent": flt(_row_value(row, "target_margin_percent") or 0),
        "custom_final_margin_percent": flt(final_margin_pct),
        "custom_last_builder_buy_rate": flt(_row_value(row, "base_buy_price") or 0),
        "custom_builder_price_overridden": 1 if flt(_row_value(row, "override_selling_price") or 0) > 0 else 0,
        "custom_last_builder_rebuild_on": rebuild_time or now_datetime(),
        "custom_builder_expense_amount": flt(_row_value(row, "expenses") or 0),
        "custom_builder_customs_amount": flt(_row_value(row, "customs_amount") or 0),
        "custom_builder_margin_basis": (_row_value(row, "margin_basis") or "").strip() or "Base Price",
    }
    for fieldname, value in values.items():
        if _doc_has_field(doc, fieldname):
            setattr(doc, fieldname, value)


def backfill_selling_item_price_brands(price_list=None, dry_run=True, limit=0):
    if not frappe.db.has_column("Item Price", "brand") or not frappe.db.has_column("Item Price", "custom_source_buying_price_list"):
        return {"updated": 0, "candidates": 0, "dry_run": bool(cint(dry_run)), "sample": []}

    conditions = [
        "coalesce(sell_pl.selling, 0) = 1",
        "sell_ip.custom_source_buying_price_list IS NOT NULL",
        "sell_ip.custom_source_buying_price_list != %(blank)s",
        "(sell_ip.brand IS NULL OR sell_ip.brand = %(blank)s)",
        "buy_ip.brand IS NOT NULL",
        "buy_ip.brand != %(blank)s",
    ]
    params = {"blank": ""}
    if price_list:
        conditions.append("sell_ip.price_list = %(price_list)s")
        params["price_list"] = price_list
    limit_sql = ""
    if cint(limit) > 0:
        limit_sql = " LIMIT %(limit)s"
        params["limit"] = cint(limit)

    rows = frappe.db.sql(
        f"""
        SELECT sell_ip.name, sell_ip.item_code, sell_ip.price_list, sell_ip.custom_source_buying_price_list, buy_ip.brand
        FROM `tabItem Price` sell_ip
        INNER JOIN `tabPrice List` sell_pl ON sell_pl.name = sell_ip.price_list
        INNER JOIN `tabItem Price` buy_ip ON buy_ip.item_code = sell_ip.item_code
            AND buy_ip.price_list = sell_ip.custom_source_buying_price_list
        WHERE {' AND '.join(conditions)}
        ORDER BY sell_ip.price_list ASC, sell_ip.item_code ASC, buy_ip.modified DESC
        {limit_sql}
        """,
        params,
        as_dict=True,
    )

    seen = set()
    unique_rows = []
    for row in rows:
        if row.name in seen:
            continue
        seen.add(row.name)
        unique_rows.append(row)

    if not cint(dry_run):
        for row in unique_rows:
            frappe.db.set_value("Item Price", row.name, "brand", row.brand, update_modified=False)
        frappe.db.commit()

    return {
        "updated": 0 if cint(dry_run) else len(unique_rows),
        "candidates": len(unique_rows),
        "dry_run": bool(cint(dry_run)),
        "sample": [dict(row) for row in unique_rows[:10]],
    }


def _builder_source_brand_map(rows):
    pairs = sorted(
        {
            ((_row_value(row, "item") or "").strip(), (_row_value(row, "buying_list") or "").strip())
            for row in rows or []
            if (_row_value(row, "item") or "").strip() and (_row_value(row, "buying_list") or "").strip()
        }
    )
    if not pairs or not frappe.db.has_column("Item Price", "brand"):
        return {}

    item_codes = sorted({item_code for item_code, _buying_list in pairs})
    buying_lists = sorted({buying_list for _item_code, buying_list in pairs})
    conditions = [
        "ip.item_code IN %(item_codes)s",
        "ip.price_list IN %(buying_lists)s",
        "ifnull(ip.brand, '') != ''",
    ]
    params = {"item_codes": tuple(item_codes), "buying_lists": tuple(buying_lists), "today": nowdate()}
    if frappe.db.has_column("Item Price", "enabled"):
        conditions.append("ip.enabled = 1")
    if frappe.db.has_column("Item Price", "buying"):
        conditions.append("ip.buying = 1")
    if frappe.db.has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if frappe.db.has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")
    order_by = "ip.item_code ASC, ip.price_list ASC, ip.modified DESC"
    if frappe.db.has_column("Item Price", "valid_from"):
        order_by = "ip.item_code ASC, ip.price_list ASC, ip.valid_from DESC, ip.modified DESC"

    price_rows = frappe.db.sql(
        f"""
        SELECT ip.item_code, ip.price_list, ip.brand
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        """,
        params,
        as_dict=True,
    )
    out = {}
    allowed_pairs = set(pairs)
    for row in price_rows:
        key = (row.item_code, row.price_list)
        if key in allowed_pairs:
            out.setdefault(key, row.brand)
    return out


def _set_builder_source_brand(doc, row, brand_map):
    if not _doc_has_field(doc, "brand"):
        return
    item_code = (_row_value(row, "item") or "").strip()
    buying_list = (_row_value(row, "buying_list") or "").strip()
    doc.brand = brand_map.get((item_code, buying_list)) or getattr(doc, "brand", None) or ""


def _format_benchmark_rule_label(rule, is_fallback=0):
    if is_fallback:
        return "Fallback Margin"
    if not rule:
        return ""
    scope = rule.get("source_bundle") or rule.get("item_group") or rule.get("material") or rule.get("crm_segment") or rule.get("business_type") or "Any"
    ratio_min = flt(rule.get("ratio_min") or 0)
    ratio_max = flt(rule.get("ratio_max") or 0)
    ratio_text = f"{ratio_min:.2f}-{ratio_max:.2f}" if ratio_max > 0 else f"{ratio_min:.2f}-∞"
    return "Ratio {0}: {1}% margin, {2}% max discount ({3})".format(
        ratio_text,
        flt(rule.get("target_margin_percent") or 0),
        flt(rule.get("max_discount_percent") or 0),
        scope,
    )


def _builder_source_buying_lists(builder_doc):
    return _ordered_buying_lists(_normalize_rules(builder_doc.sourcing_rules or []))


def _row_value(row, fieldname, default=None):
    if isinstance(row, dict):
        return row.get(fieldname, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(row, fieldname, default)


def _doctype_has_column(doctype, fieldname):
    checker = getattr(frappe.db, "has_column", None)
    if not callable(checker):
        return True
    return checker(doctype, fieldname)


def _doc_has_field(doc, fieldname):
    meta = getattr(doc, "meta", None)
    has_field = getattr(meta, "has_field", None)
    if callable(has_field):
        return bool(has_field(fieldname))
    fields = getattr(meta, "fields", None) or []
    if fields:
        return any(getattr(field, "fieldname", "") == fieldname for field in fields)
    return hasattr(doc, fieldname)


def _ensure_selling_price_list(price_list_name):
    if frappe.db.exists("Price List", price_list_name):
        validate_price_list_scope(price_list_name, kind="selling", required=True)
        return price_list_name
    currency = frappe.defaults.get_global_default("currency")
    doc = frappe.new_doc("Price List")
    if hasattr(doc, "price_list_name"):
        doc.price_list_name = price_list_name
    if hasattr(doc, "title"):
        doc.title = price_list_name
    if hasattr(doc, "enabled"):
        doc.enabled = 1
    if hasattr(doc, "selling"):
        doc.selling = 1
    if hasattr(doc, "buying"):
        doc.buying = 0
    if hasattr(doc, "currency"):
        doc.currency = currency
    apply_price_list_company(doc)
    doc.insert(ignore_permissions=True)
    return doc.name
