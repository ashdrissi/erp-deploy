import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PricingSheet(Document):
    def before_save(self):
        self.recalculate()

    def recalculate(self):
        if not self.pricing_scenario:
            frappe.throw(_("Please select a Pricing Scenario."))

        scenario = frappe.get_doc("Pricing Scenario", self.pricing_scenario)
        items = self.items or []

        if not items:
            self._reset_totals()
            return

        container_shipping_cost = flt(scenario.container_shipping_cost)
        allocation_method = (scenario.transport_allocation_method or "").strip()

        overheads_percent = (
            flt(scenario.hr_percent)
            + flt(scenario.profit_taxes_percent)
            + flt(scenario.admin_percent)
            + flt(scenario.warranty_reserve_percent)
        )

        customs_by_material = {}
        for rule in scenario.customs_rules or []:
            if rule.material:
                customs_by_material[rule.material] = rule

        total_base_amount = 0.0
        total_weight = 0.0

        for row in items:
            qty = flt(row.qty)
            buy_price = flt(row.buy_price)
            kg_per_u = flt(row.kg_per_u)

            if qty < 0:
                frappe.throw(_("Row {0}: Qty cannot be negative.").format(row.idx))

            total_base_amount += qty * buy_price
            total_weight += qty * kg_per_u

        total_transport = 0.0
        total_customs = 0.0
        total_overheads = 0.0
        total_landed = 0.0
        total_selling = 0.0

        for row in items:
            qty = flt(row.qty)
            buy_price = flt(row.buy_price)
            kg_per_u = flt(row.kg_per_u)
            weight = qty * kg_per_u

            row.base_amount = qty * buy_price

            if allocation_method == "By Amount":
                if total_base_amount > 0:
                    row.transport_cost = (row.base_amount / total_base_amount) * container_shipping_cost
                else:
                    row.transport_cost = 0
            elif allocation_method == "By Weight":
                if total_weight > 0:
                    row.transport_cost = (weight / total_weight) * container_shipping_cost
                else:
                    row.transport_cost = 0
            else:
                row.transport_cost = 0

            rule = customs_by_material.get(row.material)
            if rule:
                kg_based = (
                    weight
                    * flt(rule.fixed_price_per_kg)
                    * (flt(rule.kg_rate_percent) / 100.0)
                )
                amount_based = row.base_amount * (flt(rule.amount_rate_percent) / 100.0)
                row.customs_cost = max(kg_based, amount_based)
            else:
                row.customs_cost = 0

            row.overheads_cost = row.base_amount * (overheads_percent / 100.0)
            row.landed_cost = (
                flt(row.base_amount)
                + flt(row.transport_cost)
                + flt(row.customs_cost)
                + flt(row.overheads_cost)
            )

            margin_percent = flt(row.margin_percent)
            if margin_percent <= 0:
                margin_percent = self._get_default_margin_percent(scenario)
                row.margin_percent = margin_percent

            if margin_percent >= 100:
                frappe.throw(
                    _("Row {0}: margin_percent must be lower than 100.").format(row.idx)
                )

            denominator = 1 - (margin_percent / 100.0)
            row.sell_total = row.landed_cost / denominator if denominator else 0
            row.sell_unit_price = (row.sell_total / qty) if qty > 0 else 0

            total_transport += flt(row.transport_cost)
            total_customs += flt(row.customs_cost)
            total_overheads += flt(row.overheads_cost)
            total_landed += flt(row.landed_cost)
            total_selling += flt(row.sell_total)

        self.total_base_amount = flt(total_base_amount)
        self.total_transport = flt(total_transport)
        self.total_customs = flt(total_customs)
        self.total_overheads = flt(total_overheads)
        self.total_landed_cost = flt(total_landed)
        self.total_selling_amount = flt(total_selling)

    def _get_default_margin_percent(self, scenario):
        customer_type = (self.customer_type or "").strip()
        tier = (self.tier or "").strip()

        if customer_type == "Distributor":
            return flt(scenario.distributor_margin_percent)
        if customer_type == "Installer":
            return flt(scenario.installer_margin_percent)
        if customer_type == "Final Client":
            if tier == "Luxe":
                return flt(scenario.luxe_margin_percent)
            return flt(scenario.eco_margin_percent)

        return 0.0

    def _reset_totals(self):
        self.total_base_amount = 0
        self.total_transport = 0
        self.total_customs = 0
        self.total_overheads = 0
        self.total_landed_cost = 0
        self.total_selling_amount = 0

    @frappe.whitelist()
    def generate_quotation(self):
        self.check_permission("read")

        if not self.customer:
            frappe.throw(_("Customer is required."))

        if not self.items:
            frappe.throw(_("Please add at least one item."))

        quotation = frappe.new_doc("Quotation")
        quotation.quotation_to = "Customer"
        quotation.party_name = self.customer

        for row in self.items:
            if not row.item_code:
                frappe.throw(_("Row {0}: item_code is required.").format(row.idx))

            qty = flt(row.qty)
            if qty <= 0:
                frappe.throw(_("Row {0}: qty must be greater than 0.").format(row.idx))

            quotation.append(
                "items",
                {
                    "item_code": row.item_code,
                    "qty": qty,
                    "rate": flt(row.sell_unit_price),
                },
            )

        quotation.insert()
        return quotation.name
