from frappe.model.document import Document
from frappe.utils import flt


class OrderliftOtherCharge(Document):
    def validate(self):
        if not (self.description or "").strip():
            self.description = self.charge_name
        self.default_rate = flt(self.default_rate)
