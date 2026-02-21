import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate


MISSING_BUY_PRICE_MSG = "No buying price in {price_list}"


class PricingSheet(Document):
    def before_save(self):
        self.recalculate()

    def recalculate(self):
        scenario = self._get_scenario_or_throw()
        lines = self.lines or []

        if not lines:
            self._reset_totals()
            self.calculated_on = now_datetime()
            return

        expenses = self._active_expenses(scenario)

        total_base = 0.0
        total_expenses = 0.0
        total_final = 0.0

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            self._hydrate_line_from_item(row)
            self._set_buy_price_from_list(row, scenario, force_refresh=False)

            base_unit = flt(row.buy_price)
            row.base_amount = qty * base_unit

            pricing = self._apply_expenses(base_unit=base_unit, expenses=expenses)
            projected_unit = flt(pricing["projected_unit"])
            expense_unit = flt(pricing["expense_total_unit"])

            row.expense_total = expense_unit * qty
            row.projected_unit_price = projected_unit
            row.projected_total_price = projected_unit * qty
            row.pricing_breakdown_json = json.dumps(pricing["steps"])
            row.breakdown_preview = self._build_breakdown_preview(pricing["steps"])

            row.final_sell_unit_price = (
                flt(row.manual_sell_unit_price)
                if flt(row.manual_sell_unit_price) > 0
                else flt(row.projected_unit_price)
            )
            row.final_sell_total = flt(row.final_sell_unit_price) * qty

            self._set_benchmark_status(row, scenario, flt(row.final_sell_unit_price))

            total_base += flt(row.base_amount)
            total_expenses += flt(row.expense_total)
            total_final += flt(row.final_sell_total)

        self.total_buy = flt(total_base)
        self.total_expenses = flt(total_expenses)
        self.total_selling = flt(total_final)
        self.calculated_on = now_datetime()

    @frappe.whitelist()
    def refresh_buy_prices(self):
        scenario = self._get_scenario_or_throw()
        for row in self.lines or []:
            self._set_buy_price_from_list(row, scenario, force_refresh=True)
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

        if frappe.utils.cint(replace_existing_lines):
            self.set("lines", [])

        rows = self._get_template_rows(bundle_name)
        if not rows:
            frappe.throw(_("No template rows found in Product Bundle/BOM {0}.").format(bundle_name))

        qty_multiplier = flt(multiplier) or 1
        group_by_item_group = (default_display_group_source or "Item Group").strip() == "Item Group"
        show_detail = 1 if frappe.utils.cint(default_show_in_detail) else 0

        for tpl in rows:
            item_code = tpl.get("item_code")
            if not item_code:
                continue

            line_qty = flt(tpl.get("qty")) * qty_multiplier
            if line_qty <= 0:
                continue

            display_group = bundle_name
            if group_by_item_group:
                display_group = frappe.db.get_value("Item", item_code, "item_group") or bundle_name

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
        return [row for row in (scenario.expenses or []) if flt(row.is_active)]

    def _apply_expenses(self, base_unit, expenses):
        running_total = flt(base_unit)
        steps = []

        for exp in expenses:
            exp_type = (exp.type or "Percentage").strip().title()
            applies_to = (exp.applies_to or "Running Total").strip().title()
            value = flt(exp.value)

            basis = flt(base_unit) if applies_to == "Base Price" else flt(running_total)
            if exp_type == "Percentage":
                delta = basis * (value / 100.0)
            else:
                delta = value

            running_total += delta
            steps.append(
                {
                    "label": exp.label,
                    "type": exp_type,
                    "value": value,
                    "applies_to": applies_to,
                    "basis": basis,
                    "delta": delta,
                    "running_total": running_total,
                }
            )

        return {
            "projected_unit": running_total,
            "expense_total_unit": running_total - flt(base_unit),
            "steps": steps,
        }

    def _build_breakdown_preview(self, steps):
        if not steps:
            return "No expenses"
        return " | ".join(f"{s.get('label')}: {flt(s.get('delta')):.2f}" for s in steps)

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

    def _hydrate_line_from_item(self, row):
        if not row.item:
            return
        if not row.display_group:
            row.display_group = frappe.db.get_value("Item", row.item, "item_group") or "Ungrouped"

    def _set_buy_price_from_list(self, row, scenario, force_refresh=False):
        if not row.item:
            return

        if not force_refresh and flt(row.buy_price) > 0:
            row.buy_price_missing = 0
            row.buy_price_message = ""
            return

        buying_price_list = scenario.buying_price_list or "Buying"
        buy_price = get_latest_item_price(row.item, buying_price_list, buying=True)

        if buy_price is None:
            row.buy_price_missing = 1
            row.buy_price_message = MISSING_BUY_PRICE_MSG.format(price_list=buying_price_list)
            if force_refresh and flt(row.buy_price) <= 0:
                row.buy_price = 0
            return

        row.buy_price = flt(buy_price)
        row.buy_price_missing = 0
        row.buy_price_message = ""

    def _set_benchmark_status(self, row, scenario, computed_unit):
        benchmark_list = scenario.benchmark_price_list or "Benchmark Selling"
        benchmark_price = get_latest_item_price(row.item, benchmark_list, buying=False)
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
        self.check_permission("read")

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
        include_flagged = True
        for row in self.lines or []:
            if not row.item:
                continue
            if include_flagged and not row.show_in_detail:
                continue

            item_data = {
                "item_code": row.item,
                "qty": flt(row.qty),
                "rate": flt(row.final_sell_unit_price),
            }
            if frappe.db.has_column("Quotation Item", "source_pricing_sheet_line"):
                item_data["source_pricing_sheet_line"] = row.name

            quotation.append("items", item_data)

    def _append_grouped_quotation_items(self, quotation):
        group_item_code = self._ensure_group_line_item()
        grouped = {}

        for row in self.lines or []:
            fallback_group = frappe.db.get_value("Item", row.item, "item_group") if row.item else None
            key = (row.display_group or fallback_group or "Ungrouped").strip() or "Ungrouped"
            grouped[key] = grouped.get(key, 0.0) + flt(row.final_sell_total)

        for group_name, group_total in grouped.items():
            quotation.append(
                "items",
                {
                    "item_code": group_item_code,
                    "qty": 1,
                    "rate": flt(group_total),
                    "description": _("{0} (Grouped from Pricing Sheet)").format(group_name),
                },
            )

    def _ensure_group_line_item(self):
        item_code = "GROUP_LINE"
        if frappe.db.exists("Item", item_code):
            return item_code

        item = frappe.new_doc("Item")
        item.item_code = item_code
        item.item_name = "Quotation Group Line"
        item.item_group = "All Item Groups"
        item.stock_uom = "Nos"
        item.is_stock_item = 0
        item.insert(ignore_permissions=True)
        return item_code


def get_latest_item_price(item_code, price_list, buying):
    if not item_code or not price_list:
        return None

    params = {
        "item_code": item_code,
        "price_list": price_list,
        "today": nowdate(),
        "buying": 1 if buying else 0,
    }

    conditions = [
        "ip.item_code = %(item_code)s",
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

    order_by = "ip.modified DESC"
    if has_valid_from:
        order_by = "ip.valid_from DESC, ip.modified DESC"

    query = f"""
        SELECT ip.price_list_rate
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        LIMIT 1
    """

    rows = frappe.db.sql(query, params, as_list=True)
    return rows[0][0] if rows else None


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
