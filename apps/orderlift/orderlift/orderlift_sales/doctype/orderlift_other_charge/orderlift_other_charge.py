import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OrderliftOtherCharge(Document):
    def validate(self):
        if not (self.description or "").strip():
            self.description = self.charge_name
        self.default_rate = flt(self.default_rate)
        self.default_expected_unit_cost = flt(self.default_expected_unit_cost)
        if self.default_expected_unit_cost < 0:
            frappe.throw(_("Default Expected Unit Cost HT cannot be negative."))
