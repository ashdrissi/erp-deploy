import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import get_item_details_map, get_latest_item_prices
from orderlift.sales.utils.pricing_projection import apply_expenses
from orderlift.sales.utils.scenario_policy import resolve_scenario_rule


class PricingBuilder(Document):
    def validate(self):
        self.default_qty = flt(self.default_qty or 1) or 1
        self.max_items = cint(self.max_items or 0)

    def calculate_items(self):
        rules = _normalize_rules(self.sourcing_rules or [])
        active_buying_lists = _ordered_buying_lists(rules)
        if not active_buying_lists:
            frappe.throw(_("Add at least one active sourcing rule with a Buying Price List."))

        qty = flt(self.default_qty or 1)
        if qty <= 0:
            qty = 1

        items, item_warnings = _load_builder_items(
            active_buying_lists,
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
        selling_price_list_name = (self.selling_price_list_name or "").strip()
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
                result_rows.append(_build_result_row(item_code, buying_list, meta.get("origin") or "", qty, base_buy, flt(published_map.get(item_code) or 0), "Missing Rule", _("No sourcing rule matched buying list {0}.").format(buying_list or "-"), item_group=details.get("item_group") or "", item_name=meta.get("item_name") or item_code))
                continue

            scenario_name = (matched_rule.get("pricing_scenario") or "").strip()
            if not scenario_name or scenario_name not in scenario_caches:
                result_rows.append(_build_result_row(item_code, buying_list, meta.get("origin") or "", qty, base_buy, flt(published_map.get(item_code) or 0), "Missing Rule", _("Select a valid Expenses Policy for buying list {0}.").format(buying_list or "-"), item_group=details.get("item_group") or "", item_name=meta.get("item_name") or item_code))
                continue

            row = frappe._dict(item=item_code, qty=qty, source_buying_price_list=buying_list, source_bundle="")
            cache = scenario_caches.get(scenario_name) or {}
            sheet._set_buy_price_for_row(row, cache.get("buying_price_list"), cache.get("buy_prices") or {}, {cache.get("buying_price_list"): cache.get("buy_prices") or {}}, force_refresh=True)

            base_buy = flt(row.buy_price or 0)
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
                "material": details.get("custom_material") or "",
            }

            row_customs_policy = _get_customs_policy_doc(matched_rule.get("customs_policy"), customs_cache)
            customs_calc = sheet._compute_customs_for_row(row, base_amount, item_details, row_customs_policy)
            transport_calc = sheet._compute_transport_for_row(row=row, qty=qty, base_amount=base_amount, item_details=item_details, transport_config=cache.get("transport_config") or {})
            effective_expenses = sheet._inject_transport_expense(cache.get("line_expenses") or [], transport_calc)
            effective_expenses = sheet._strip_scenario_margin_expenses(effective_expenses)

            benchmark_policy_doc = _get_benchmark_policy_doc(matched_rule.get("benchmark_policy"), benchmark_cache)
            benchmark_result = None
            if benchmark_policy_doc:
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
            policy_margin_pct = flt((benchmark_result or {}).get("target_margin_percent") or 0)
            cost_before_margin = (
                flt(base_buy)
                + flt(component_summary.get("policy_expense_unit") or 0)
                + (flt(customs_calc.get("applied") or 0) / qty if qty else 0)
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
                "material": details.get("custom_material") or "",
                "buying_list": buying_list,
                "origin": meta.get("origin") or "",
                "base_buy_price": base_buy,
                "expenses": flt(component_summary.get("policy_expense_unit") or 0),
                "customs_amount": flt(customs_calc.get("applied") or 0) / qty if qty else 0,
                "margin_amount": flt(component_summary.get("margin_unit") or 0),
                "avg_benchmark": benchmark_reference,
                "projected_price": projected_unit,
                "override_selling_price": 0,
                "final_margin_pct": _effective_margin_pct(projected_unit, cost_before_margin, policy_margin_pct),
                "published_price": published_price,
                "status": status,
                "status_note": status_note,
                "pricing_scenario": scenario_name,
                "customs_policy": matched_rule.get("customs_policy") or "",
                "benchmark_policy": matched_rule.get("benchmark_policy") or "",
                "selected": 1 if status in {"Ready", "No Benchmark"} else 0,
            })

            if customs_calc.get("warning"):
                warnings.append(_("{0}: {1}").format(item_code, customs_calc.get("warning")))
            for msg in (benchmark_result or {}).get("warnings") or []:
                warnings.append(_("{0}: {1}").format(item_code, msg))
            if transport_calc.get("warning"):
                warnings.append(_("{0}: {1}").format(item_code, transport_calc.get("warning")))

        for row in result_rows:
            self.append("builder_items", row)

        summary = _build_summary(result_rows)
        self._apply_summary(summary)
        self.warnings_html = _warnings_html(_dedupe_warnings(warnings))

    def publish_prices(self, selected_only=False):
        price_list_name = _ensure_selling_price_list((self.selling_price_list_name or "").strip())
        currency = frappe.db.get_value("Price List", price_list_name, "currency") or frappe.defaults.get_global_default("currency")
        created = 0
        updated = 0
        skipped = 0
        errors = []

        for row in self.builder_items or []:
            if selected_only and not cint(row.selected):
                continue
            item_code = (row.item or "").strip()
            if not item_code:
                skipped += 1
                continue
            if (row.status or "").strip() in {"Missing Rule", "Missing Buy Price"}:
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
                    doc.save(ignore_permissions=True)
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
                    doc.insert(ignore_permissions=True)
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


@frappe.whitelist()
def calculate_builder_doc(name):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.calculate_items()
    doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def publish_builder_doc(name, selected_only=0):
    doc = frappe.get_doc("Pricing Builder", name)
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


def _load_builder_items(buying_lists, item_group=None, max_items=0):
    price_rows = _get_latest_buying_list_rows(buying_lists)
    if not price_rows:
        return [], [_("No buying prices found in the selected buying price lists.")]
    item_priority = {name: idx for idx, name in enumerate(buying_lists)}
    grouped = {}
    for row in price_rows:
        item_code = row.get("item_code")
        if not item_code:
            continue
        bucket = grouped.get(item_code)
        candidate = {"item": item_code, "buying_list": row.get("price_list") or "", "buy_price": flt(row.get("price_list_rate") or 0)}
        if not bucket or item_priority.get(candidate["buying_list"], 9999) < item_priority.get(bucket["buying_list"], 9999):
            grouped[item_code] = candidate
    filters = {"name": ["in", list(grouped.keys())], "disabled": 0}
    warnings = []
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
    if not items:
        warnings.append(_("No items matched the selected buying lists and filters."))
    return items, warnings


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
        if row.get("status") in {"Ready", "No Benchmark"}:
            summary["ready_count"] += 1
        if _publish_state(row.get("override_selling_price") or row.get("projected_price"), row.get("published_price")) == "Changed":
            summary["changed_count"] += 1
        if _publish_state(row.get("override_selling_price") or row.get("projected_price"), row.get("published_price")) == "New":
            summary["new_count"] += 1
        if row.get("status") in {"Missing Rule", "Missing Buy Price"}:
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


def _warnings_html(messages):
    items = _dedupe_warnings(messages)
    if not items:
        return ""
    return "\n".join(items)


def _build_result_row(item_code, buying_list, origin, qty, base_buy, published_price, status, status_note, item_group="", item_name=""):
    return {
        "item": item_code,
        "item_name": item_name or item_code,
        "item_group": item_group,
        "material": "",
        "buying_list": buying_list,
        "origin": origin,
        "base_buy_price": base_buy,
        "expenses": 0,
        "customs_amount": 0,
        "margin_amount": 0,
        "avg_benchmark": 0,
        "projected_price": 0,
        "override_selling_price": 0,
        "final_margin_pct": 0,
        "published_price": published_price,
        "status": status,
        "status_note": status_note,
        "pricing_scenario": "",
        "customs_policy": "",
        "benchmark_policy": "",
        "selected": 0,
    }


def _ensure_selling_price_list(price_list_name):
    if frappe.db.exists("Price List", price_list_name):
        return price_list_name
    currency = frappe.defaults.get_global_default("currency") or "MAD"
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
    doc.insert(ignore_permissions=True)
    return doc.name
