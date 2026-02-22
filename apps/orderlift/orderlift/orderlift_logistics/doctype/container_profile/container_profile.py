import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class ContainerProfile(Document):
    def validate(self):
        self.cost_rank = cint(self.cost_rank or 100)
        self.max_weight_kg = flt(self.max_weight_kg)
        self.max_volume_m3 = flt(self.max_volume_m3)

        if self.max_weight_kg <= 0:
            frappe.throw("Max Weight (kg) must be greater than zero.")
        if self.max_volume_m3 <= 0:
            frappe.throw("Max Volume (m3) must be greater than zero.")
