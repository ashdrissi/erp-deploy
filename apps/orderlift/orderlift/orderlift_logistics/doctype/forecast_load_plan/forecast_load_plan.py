import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ForecastLoadPlan(Document):
    def validate(self):
        self.recompute_totals()

    def recompute_totals(self):
        total_weight = 0.0
        total_volume = 0.0
        for row in self.items or []:
            if row.selected:
                total_weight += flt(row.total_weight_kg)
                total_volume += flt(row.total_volume_m3)

        self.total_weight_kg = flt(total_weight, 3)
        self.total_volume_m3 = flt(total_volume, 3)

        if self.container_profile:
            profile = frappe.get_cached_doc("Container Profile", self.container_profile)
            max_w = flt(profile.max_weight_kg)
            max_v = flt(profile.max_volume_m3)
            self.weight_utilization_pct = flt(total_weight / max_w * 100, 3) if max_w > 0 else 0
            self.volume_utilization_pct = flt(total_volume / max_v * 100, 3) if max_v > 0 else 0
        else:
            self.weight_utilization_pct = 0
            self.volume_utilization_pct = 0
