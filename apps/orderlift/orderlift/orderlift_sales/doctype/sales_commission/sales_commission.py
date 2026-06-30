"""Sales Commission controller.

Handles validation and status transitions for commission records.
Created automatically from submitted Sales Orders.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class SalesCommission(Document):
    def validate(self):
        self._normalize_legacy_status()
        self._validate_commission_rate()
        self._calculate_commission_amount()
        self._set_customer_from_sales_order()

    def before_submit(self):
        if not self.status or self.status == "Pending":
            self.status = "Approved"

    def on_cancel(self):
        self.status = "Cancelled"

    def _validate_commission_rate(self):
        if self.commission_rate and self.commission_rate < 0:
            frappe.throw(_("Commission rate cannot be negative"))
        if self.commission_rate and self.commission_rate > 100:
            frappe.throw(_("Commission rate cannot exceed 100%"))

    def _calculate_commission_amount(self):
        """Keep snapshot commission_amount authoritative for Sales Order-driven records."""
        if self.sales_order:
            return
        if self.base_amount and self.commission_rate and not self.commission_amount:
            self.commission_amount = self.base_amount * (self.commission_rate / 100)

    def _set_customer_from_sales_order(self):
        """Fetch customer from Sales Order if not already set."""
        if not self.customer and self.sales_order:
            self.customer = frappe.db.get_value(
                "Sales Order", self.sales_order, "customer"
            )

    def _normalize_legacy_status(self):
        if self.status == "Pending":
            self.status = "Approved"

    @frappe.whitelist()
    def mark_as_paid(self, payment_date=None, payment_reference=None):
        """Mark this commission as paid. Called from the form button."""
        if self.docstatus != 1:
            frappe.throw(_("Commission must be submitted before marking as paid"))
        if self.status == "Paid":
            frappe.throw(_("Commission is already marked as paid"))
        if self.status == "Cancelled":
            frappe.throw(_("Cannot pay a cancelled commission"))

        self.status = "Paid"
        self.payment_date = payment_date or frappe.utils.today()
        self.payment_reference = payment_reference or ""
        self.save(ignore_permissions=True)
        frappe.msgprint(
            _("Commission {0} marked as paid").format(self.name),
            indicator="green",
            alert=True,
        )
