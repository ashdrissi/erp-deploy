import frappe
from frappe import _
from frappe.model.document import Document


class BuyingPriceChangeLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(_("Buying Price Change Log records are immutable."))
