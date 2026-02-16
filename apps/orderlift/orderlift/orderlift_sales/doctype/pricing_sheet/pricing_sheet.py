import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class PricingSheet(Document):
    def before_save(self):
        self.recalculate()

    def recalculate(self):
        if not self.pricing_scenario:
            frappe.throw(_("Please select a Pricing Scenario."))

        scenario = frappe.get_doc("Pricing Scenario", self.pricing_scenario)
        lines = self.lines or []

        if not lines:
            self._reset_totals()
            self.calculated_on = now_datetime()
            return

        total_weight = sum(flt(row.qty) * flt(row.weight_kg) for row in lines)
        total_base = 0.0

        for row in lines:
            self._hydrate_line_from_item(row)
            if flt(row.buy_price) <= 0 and row.item:
                row.buy_price = self._get_default_buy_price(row.item)
            row.base_amount = flt(row.qty) * flt(row.buy_price)
            total_base += flt(row.base_amount)

        scenario_container_value = flt(scenario.container_value_hypothesis) or total_base
        scenario_charges_value = flt(scenario.charges_pool_value_hypothesis) or total_base

        total_customs = 0.0
        total_transport = 0.0
        total_team = 0.0
        total_taxes = 0.0
        total_margin = 0.0
        total_selling = 0.0

        customs_rules = self._customs_rules_by_material(scenario)

        for row in lines:
            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx))

            base_amount = flt(row.base_amount)
            total_kg = qty * flt(row.weight_kg)

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

            total_customs += flt(row.customs)
            total_transport += flt(row.transport_transitaire)
            total_team += flt(row.team_office_charge)
            total_taxes += flt(row.taxes_impots)
            total_margin += flt(row.margin_amount)
            total_selling += flt(selected_total)

        self.total_buy = flt(total_base)
        self.total_customs = flt(total_customs)
        self.total_transport = flt(total_transport)
        self.total_team_charge = flt(total_team)
        self.total_taxes = flt(total_taxes)
        self.total_margin = flt(total_margin)
        self.total_selling = flt(total_selling)
        self.calculated_on = now_datetime()

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
        method = (scenario.transport_allocation_method or "By Amount").strip()

        if total_transport_cost <= 0:
            return 0.0

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
            "Item", row.item, ["custom_material", "custom_weight_kg"], as_dict=True
        )
        if not item_vals:
            return

        row.material = (item_vals.custom_material or row.material or "OTHER").upper()
        row.weight_kg = flt(item_vals.custom_weight_kg)

    def _get_default_buy_price(self, item_code):
        price = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "buying": 1,
                "enabled": 1,
            },
            "price_list_rate",
            order_by="modified desc",
        )
        return flt(price)

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

        if not self.customer:
            frappe.throw(_("Customer is required."))

        lines = self.lines or []
        if not lines:
            frappe.throw(_("Please add at least one pricing line."))

        quotation = frappe.new_doc("Quotation")
        quotation.company = self._resolve_company_for_quotation()
        quotation.quotation_to = "Customer"
        quotation.party_name = self.customer

        if frappe.db.has_column("Quotation", "source_pricing_sheet"):
            quotation.source_pricing_sheet = self.name

        output_mode = (self.output_mode or "Avec détails").strip()
        if output_mode == "Sans détails":
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
            if not row.show_in_detail:
                continue

            quotation.append(
                "items",
                {
                    "item_code": row.item,
                    "qty": flt(row.qty),
                    "rate": flt(row.selected_sell_unit),
                },
            )

    def _append_grouped_quotation_items(self, quotation):
        grouped = {}
        for row in self.lines or []:
            key = (row.display_group or "Ungrouped").strip() or "Ungrouped"
            grouped.setdefault(key, {"total": 0.0, "item_code": row.item})
            grouped[key]["total"] += flt(row.selected_sell_total)
            if not grouped[key]["item_code"] and row.item:
                grouped[key]["item_code"] = row.item

        for group_name, group_data in grouped.items():
            item_code = group_data["item_code"]
            if not item_code:
                continue

            quotation.append(
                "items",
                {
                    "item_code": item_code,
                    "qty": 1,
                    "rate": flt(group_data["total"]),
                    "description": _("{0} (Grouped from Pricing Sheet)").format(group_name),
                },
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
def get_item_pricing_defaults(item_code):
    if not item_code:
        return {"buy_price": 0, "material": "OTHER", "weight_kg": 0}

    item_vals = frappe.db.get_value(
        "Item", item_code, ["custom_material", "custom_weight_kg"], as_dict=True
    ) or {}

    buy_price = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "buying": 1,
            "enabled": 1,
        },
        "price_list_rate",
        order_by="modified desc",
    )

    return {
        "buy_price": flt(buy_price),
        "material": (item_vals.get("custom_material") or "OTHER").upper(),
        "weight_kg": flt(item_vals.get("custom_weight_kg")),
    }
