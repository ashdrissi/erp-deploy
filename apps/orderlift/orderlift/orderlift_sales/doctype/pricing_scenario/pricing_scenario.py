import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PricingScenario(Document):
    def before_insert(self):
        if self.customs_rules:
            return

        for material, factor in {
            "STEEL": 13,
            "GALVA": 24,
            "INOX": 40,
            "COPPER": 60,
            "OTHER": 0,
        }.items():
            self.append(
                "customs_rules",
                {
                    "material": material,
                    "factor_per_kg": factor,
                },
            )

    def validate(self):
        self.buying_price_list = self.buying_price_list or "Buying"
        self.benchmark_price_list = self.benchmark_price_list or "Benchmark Selling"
        self._validate_customs_rules()
        self._compute_transport_total()
        self._compute_team_charge_total()

    def _validate_customs_rules(self):
        seen = set()
        for row in self.customs_rules or []:
            material = (row.material or "").strip().upper()
            if not material:
                frappe.throw(_("Row {0}: Material is required.").format(row.idx))
            if material in seen:
                frappe.throw(_("Duplicate customs rule for material {0}.").format(material))
            seen.add(material)

    def _compute_transport_total(self):
        usd_to_mad = flt(self.usd_to_mad_rate) or 1.0
        self.total_transport_cost = (
            flt(self.price_container_usd) * usd_to_mad
            + flt(self.price_truck_ttc)
            + flt(self.loading_cost)
            + flt(self.unloading_cost)
            + flt(self.transport_risk_alea)
        )

    def _compute_team_charge_total(self):
        self.total_team_office_charges = (
            flt(self.cars_amortization)
            + flt(self.hr_cost)
            + flt(self.rent_office_stock)
            + flt(self.accountant_other)
        )
