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

        total_base = 0.0
        total_weight = 0.0
        for row in lines:
            self._hydrate_line_from_item(row)
            self._set_buy_price_from_list(row, scenario, force_refresh=False)
            row.base_amount = flt(row.qty) * flt(row.buy_price)
            total_base += flt(row.base_amount)
            total_weight += flt(row.qty) * flt(row.weight_kg)

        scenario_container_value = flt(scenario.container_value_hypothesis) or total_base
        scenario_charges_value = flt(scenario.charges_pool_value_hypothesis) or total_base
        customs_rules = self._customs_rules_by_material(scenario)

        total_customs = 0.0
        total_transport = 0.0
        total_team = 0.0
        total_taxes = 0.0
        total_margin = 0.0
        total_selling = 0.0

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            base_amount = flt(row.base_amount)
            total_kg = qty * flt(row.weight_kg)

            if flt(scenario.is_local_buying):
                row.customs = 0
                row.transport_transitaire = 0
            else:
                row.customs = self._compute_customs(
                    base_amount=base_amount,
                    total_kg=total_kg,
                    material=(row.material or "").upper(),
                    scenario=scenario,
                    rules=customs_rules,
                )
                row.transport_transitaire = self._compute_transport(
                    row=row,
                    scenario=scenario,
                    total_weight=total_weight,
                    total_base=total_base,
                    scenario_container_value=scenario_container_value,
                )

            row.team_office_charge = self._compute_team_charge(
                row=row,
                scenario=scenario,
                total_base=total_base,
                scenario_charges_value=scenario_charges_value,
            )

            row.taxes_impots = base_amount * (flt(scenario.taxes_percent_of_buy) / 100.0)
            row.margin_amount = base_amount * (flt(scenario.margin_percent_of_buy) / 100.0)

            row.sell_sans_stock_min = (
                base_amount
                + flt(row.customs)
                + flt(row.transport_transitaire)
                + flt(row.team_office_charge) * flt(scenario.j_multiplier_sans_stock)
                + flt(row.taxes_impots)
                + flt(row.margin_amount) * flt(scenario.l_multiplier_min)
            )
            row.sell_sans_stock_max = (
                base_amount
                + flt(row.customs)
                + flt(row.transport_transitaire)
                + flt(row.team_office_charge) * flt(scenario.j_multiplier_sans_stock)
                + flt(row.taxes_impots)
                + flt(row.margin_amount) * flt(scenario.l_multiplier_max)
            )
            row.sell_stock = (
                base_amount
                + flt(row.customs)
                + flt(row.transport_transitaire)
                + flt(row.team_office_charge) * flt(scenario.j_multiplier_stock)
                + flt(row.taxes_impots)
                + flt(row.margin_amount) * flt(scenario.l_multiplier_stock)
            )

            selected_total = self._selected_total_for_mode(row)
            row.selected_sell_total = selected_total
            row.selected_sell_unit = selected_total / qty if qty else 0

            self._set_benchmark_status(row, scenario)

            row.final_sell_unit_price = (
                flt(row.manual_sell_unit_price)
                if flt(row.manual_sell_unit_price) > 0
                else flt(row.selected_sell_unit)
            )
            row.final_sell_total = flt(row.final_sell_unit_price) * qty

            total_customs += flt(row.customs)
            total_transport += flt(row.transport_transitaire)
            total_team += flt(row.team_office_charge)
            total_taxes += flt(row.taxes_impots)
            total_margin += flt(row.margin_amount)
            total_selling += flt(row.final_sell_total)

        self.total_buy = flt(total_base)
        self.total_customs = flt(total_customs)
        self.total_transport = flt(total_transport)
        self.total_team_charge = flt(total_team)
        self.total_taxes = flt(total_taxes)
        self.total_margin = flt(total_margin)
        self.total_selling = flt(total_selling)
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
        scenario = self._get_scenario_or_throw()
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

    def _get_template_rows(self, template_name):
        if frappe.db.exists("DocType", "Product Bundle") and frappe.db.exists("Product Bundle", template_name):
            bundle = frappe.get_doc("Product Bundle", template_name)
            return [
                {
                    "item_code": row.item_code,
                    "qty": flt(row.qty),
                }
                for row in (bundle.items or [])
            ]

        if frappe.db.exists("DocType", "BOM") and frappe.db.exists("BOM", template_name):
            bom = frappe.get_doc("BOM", template_name)
            return [
                {
                    "item_code": row.item_code,
                    "qty": flt(row.qty),
                }
                for row in (bom.items or [])
            ]

        return []

    def _get_scenario_or_throw(self):
        if not self.pricing_scenario:
            frappe.throw(_("Please select a Pricing Scenario."))
        return frappe.get_doc("Pricing Scenario", self.pricing_scenario)

    def _customs_rules_by_material(self, scenario):
        rules = {}
        for row in scenario.customs_rules or []:
            material = (row.material or "").strip().upper()
            if material:
                rules[material] = row
        return rules

    def _compute_customs(self, base_amount, total_kg, material, scenario, rules):
        fallback_percent = flt(scenario.customs_percent_default)
        rule = rules.get(material)
        if not rule:
            return base_amount * (fallback_percent / 100.0)

        percent = flt(rule.customs_percent) or fallback_percent
        factor = flt(rule.factor_per_kg)
        if material == "OTHER" or factor <= 0:
            return base_amount * (percent / 100.0)

        customs_base = max(base_amount, total_kg * factor)
        return customs_base * (percent / 100.0)

    def _compute_transport(self, row, scenario, total_weight, total_base, scenario_container_value):
        total_transport_cost = flt(scenario.total_transport_cost)
        if total_transport_cost <= 0:
            return 0.0

        method = (scenario.transport_allocation_method or "By Amount").strip()
        if method == "By Weight":
            row_weight = flt(row.qty) * flt(row.weight_kg)
            if total_weight <= 0:
                return 0.0
            return (row_weight / total_weight) * total_transport_cost

        denominator = scenario_container_value or total_base
        if denominator <= 0:
            return 0.0
        return (flt(row.base_amount) / denominator) * total_transport_cost

    def _compute_team_charge(self, row, scenario, total_base, scenario_charges_value):
        method = (scenario.team_charge_allocation_method or "By Amount").strip()
        if method == "Fixed % of buy price":
            return flt(row.base_amount) * (flt(scenario.team_charge_percent_of_buy) / 100.0)

        total_team = flt(scenario.total_team_office_charges)
        if total_team <= 0:
            return 0.0

        denominator = scenario_charges_value or total_base
        if denominator <= 0:
            return 0.0

        return (flt(row.base_amount) / denominator) * total_team

    def _selected_total_for_mode(self, row):
        mode = (self.price_mode or "max").strip().lower()
        if mode == "min":
            return flt(row.sell_sans_stock_min)
        if mode == "stock":
            return flt(row.sell_stock)
        return flt(row.sell_sans_stock_max)

    def _hydrate_line_from_item(self, row):
        if not row.item:
            return

        item_vals = frappe.db.get_value(
            "Item", row.item, ["custom_material", "custom_weight_kg", "item_group"], as_dict=True
        )
        if not item_vals:
            return

        row.material = (item_vals.custom_material or row.material or "OTHER").upper()
        row.weight_kg = flt(item_vals.custom_weight_kg)
        if not row.display_group:
            row.display_group = item_vals.item_group or "Ungrouped"

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

    def _set_benchmark_status(self, row, scenario):
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
        row.benchmark_delta_abs = flt(row.selected_sell_unit) - flt(row.benchmark_price)
        row.benchmark_delta_pct = (row.benchmark_delta_abs / flt(row.benchmark_price)) * 100

        if flt(row.selected_sell_unit) < flt(row.benchmark_price) * 0.8:
            row.benchmark_status = "Too Low"
            row.benchmark_note = _(
                "Computed {0} vs market {1} -> consider raising"
            ).format(flt(row.selected_sell_unit), flt(row.benchmark_price))
        elif flt(row.selected_sell_unit) > flt(row.benchmark_price) * 1.1:
            row.benchmark_status = "Too High"
            row.benchmark_note = _(
                "Computed {0} vs market {1} -> consider lowering"
            ).format(flt(row.selected_sell_unit), flt(row.benchmark_price))
        else:
            row.benchmark_status = "OK"
            row.benchmark_note = _("Within benchmark range")

    def _reset_totals(self):
        self.total_buy = 0
        self.total_customs = 0
        self.total_transport = 0
        self.total_team_charge = 0
        self.total_taxes = 0
        self.total_margin = 0
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

        if (self.output_mode or "Avec détails").strip() == "Sans détails":
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

    rows = frappe.db.sql(
        """
        SELECT ip.price_list_rate
        FROM `tabItem Price` ip
        WHERE ip.item_code = %(item_code)s
          AND ip.price_list = %(price_list)s
          AND ip.enabled = 1
          AND ip.buying = %(buying)s
          AND (ip.valid_from IS NULL OR ip.valid_from <= %(today)s)
          AND (ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)
        ORDER BY ip.valid_from DESC, ip.modified DESC
        LIMIT 1
        """,
        params,
        as_list=True,
    )
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
        return {"buy_price": 0, "material": "OTHER", "weight_kg": 0}

    item_vals = frappe.db.get_value(
        "Item", item_code, ["custom_material", "custom_weight_kg"], as_dict=True
    ) or {}

    buying_price_list = "Buying"
    if pricing_scenario and frappe.db.exists("Pricing Scenario", pricing_scenario):
        buying_price_list = (
            frappe.db.get_value("Pricing Scenario", pricing_scenario, "buying_price_list") or "Buying"
        )

    buy_price = get_latest_item_price(item_code, buying_price_list, buying=True)
    return {
        "buy_price": flt(buy_price),
        "material": (item_vals.get("custom_material") or "OTHER").upper(),
        "weight_kg": flt(item_vals.get("custom_weight_kg")),
    }
