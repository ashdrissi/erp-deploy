import frappe
from frappe.model.document import Document


class ShipmentAnalysis(Document):
    def validate(self):
        self.status = (self.status or "ok").strip().lower()
        if self.status not in {
            "ok",
            "incomplete_data",
            "no_container_found",
            "over_capacity",
            "cancelled",
        }:
            frappe.throw("Invalid shipment analysis status.")
