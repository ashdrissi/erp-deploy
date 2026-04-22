import frappe
from frappe import _
from frappe.utils import getdate


class ContractDateValidationMixin:
    def validate_dates(self):
        if self.start_date and self.end_date and getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(_("End Date cannot be before Start Date."))
