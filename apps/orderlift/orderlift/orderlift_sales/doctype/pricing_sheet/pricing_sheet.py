import json
from time import perf_counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime, nowdate

from orderlift.sales.utils.pricing_projection import apply_expenses


MISSING_BUY_PRICE_MSG = "No buying price in {price_list}"


class PricingSheet(Document):
    def before_save(self):
        self.recalculate()

    def recalculate(self):
        started = perf_counter()
        scenario = self._get_scenario_or_throw()
        lines = self.lines or []
        self.projection_warnings = ""

        if not lines:
            self._reset_totals()
            self.calculated_on = now_datetime()
            self.calculated_by = frappe.session.user
            self.calc_runtime_ms = (perf_counter() - started) * 1000
            return

        warnings = []
        item_codes = sorted({row.item for row in lines if row.item})
        item_groups = get_item_groups_map(item_codes)

        buying_price_list = scenario.buying_price_list or "Buying"
        benchmark_price_list = scenario.benchmark_price_list or "Benchmark Selling"
        buy_prices = get_latest_item_prices(item_codes, buying_price_list, buying=True)
        benchmark_prices = get_latest_item_prices(item_codes, benchmark_price_list, buying=False)

        expenses = self._active_expenses(scenario)
        sheet_fixed_total = self._sheet_fixed_total(expenses)
        line_expenses = [
            exp
            for exp in expenses
            if not ((exp.get("type") or "").title() == "Fixed" and (exp.get("scope") or "").title() == "Per Sheet")
        ]

        total_base = 0.0
        total_expenses = 0.0
        total_final = 0.0
        line_snapshots = []

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            self._hydrate_line_from_item(row, item_groups)
            self._set_buy_price_from_map(row, buying_price_list, buy_prices)

            base_unit = flt(row.buy_price)
            base_amount = qty * base_unit
            row.base_amount = base_amount

            pricing = apply_expenses(base_unit=base_unit, qty=qty, expenses=line_expenses)
            line_snapshots.append(
                {
                    "row": row,
                    "qty": qty,
                    "base_unit": base_unit,
                    "base_amount": base_amount,
                    "pricing": pricing,
                }
            )
            total_base += base_amount

        allocation_denom = total_base if total_base > 0 else sum(s["qty"] for s in line_snapshots)
        allocation_denom = allocation_denom or 1

        min_margin = flt(self.minimum_margin_percent)
        floor_violations = 0
        margin_violations = 0

        for snap in line_snapshots:
            row = snap["row"]
            qty = snap["qty"]
            base_unit = snap["base_unit"]
            base_amount = snap["base_amount"]
            pricing = snap["pricing"]

            share_basis = base_amount if total_base > 0 else qty
            allocated_sheet = (share_basis / allocation_denom) * sheet_fixed_total
            projected_total = flt(pricing["projected_line"]) + flt(allocated_sheet)
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

            row.expense_total = expense_total
            row.projected_unit_price = projected_unit
            row.projected_total_price = projected_total
            row.pricing_breakdown_json = json.dumps(steps)
            row.breakdown_preview = self._build_breakdown_preview(steps)

            row.is_manual_override = 1 if flt(row.manual_sell_unit_price) > 0 else 0
            row.final_sell_unit_price = flt(row.manual_sell_unit_price) if row.is_manual_override else projected_unit
            row.final_sell_total = flt(row.final_sell_unit_price) * qty
            row.margin_pct = ((flt(row.final_sell_unit_price) - base_unit) / base_unit * 100) if base_unit > 0 else 0

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

            self._set_benchmark_status(row, benchmark_price_list, benchmark_prices, flt(row.final_sell_unit_price))

            total_expenses += flt(row.expense_total)
            total_final += flt(row.final_sell_total)

        self.total_buy = flt(total_base)
        self.total_expenses = flt(total_expenses)
        self.total_selling = flt(total_final)
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
        grouped_count = len(
            {
                ((row.display_group or "").strip() or "Ungrouped")
                for row in lines
                if flt(row.final_sell_total) != 0
            }
        )
        return {
            "line_count": len(lines),
            "detailed_count": detailed_count,
            "grouped_count": grouped_count,
            "total_buy": flt(self.total_buy),
            "total_final": flt(self.total_selling),
            "warnings": self.projection_warnings or "",
        }

    @frappe.whitelist()
    def refresh_buy_prices(self):
        scenario = self._get_scenario_or_throw()
        lines = self.lines or []
        item_codes = sorted({row.item for row in lines if row.item})
        buy_prices = get_latest_item_prices(item_codes, scenario.buying_price_list or "Buying", buying=True)
        for row in lines:
            self._set_buy_price_from_map(row, scenario.buying_price_list or "Buying", buy_prices, force_refresh=True)
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
    ):
        self._get_scenario_or_throw()
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

        item_codes = []
        for row in rows:
            code = row.get("item_code")
            if code:
                item_codes.append(str(code))
        item_codes.sort()
        item_groups = get_item_groups_map(item_codes)

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
                    "show_in_detail": show_detail,
                },
            )

        self.product_bundle = bundle_name
        self.refresh_buy_prices()
        return self.name

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

    def _get_scenario_or_throw(self):
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
                item_data["source_pricing_scenario"] = self.pricing_scenario
            if frappe.db.has_column("Quotation Item", "source_pricing_override"):
                item_data["source_pricing_override"] = cint(row.is_manual_override)

            quotation.append("items", item_data)

    def _append_grouped_quotation_items(self, quotation):
        config = self._get_group_line_config()
        group_item_code = config["item_code"]
        grouped = {}

        for row in self.lines or []:
            fallback_group = row.display_group or "Ungrouped"
            key = (fallback_group or "Ungrouped").strip() or "Ungrouped"
            grouped[key] = grouped.get(key, 0.0) + flt(row.final_sell_total)

        for group_name, group_total in grouped.items():
            item = {
                "item_code": group_item_code,
                "qty": 1,
                "rate": flt(group_total),
                "description": _("{0}: {1}").format(config["description_prefix"], group_name),
            }
            if frappe.db.has_column("Quotation Item", "source_pricing_scenario"):
                item["source_pricing_scenario"] = self.pricing_scenario
            quotation.append("items", item)

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


def get_item_groups_map(item_codes):
    if not item_codes:
        return {}
    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_group"],
        limit_page_length=0,
    )
    return {row.name: row.item_group for row in rows}


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
