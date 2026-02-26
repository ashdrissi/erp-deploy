import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class PricingScenarioPolicy(Document):
    def validate(self):
        seen = set()
        active = 0

        for row in self.scenario_rules or []:
            row.sales_person = (row.sales_person or "").strip()
            row.geography_type = (row.geography_type or "").strip().title()
            row.geography_value = (row.geography_value or "").strip()
            row.customer_segment = (row.customer_segment or "").strip().upper()
            row.customer_type = (row.customer_type or "").strip()
            row.tier = (row.tier or "").strip()
            row.item = (row.item or "").strip()
            row.item_group = (row.item_group or "").strip()
            row.material = (row.material or "").strip().upper()
            row.sequence = cint(row.sequence or 90)
            row.priority = cint(row.priority or 10)

            if row.geography_type and row.geography_type not in ("Territory", "Country", "Region"):
                frappe.throw(_("Row {0}: Geography Type must be Territory, Country, or Region.").format(row.idx))

            if row.item and row.item_group:
                frappe.throw(_("Row {0}: set Item or Item Group, not both.").format(row.idx))

            key = (
                row.pricing_scenario,
                row.sales_person.lower(),
                row.geography_type.lower(),
                row.geography_value.lower(),
                row.customer_segment.lower(),
                row.customer_type.lower(),
                row.tier.lower(),
                row.item.lower(),
                row.item_group.lower(),
                row.material.lower(),
                row.priority,
                cint(row.is_active),
            )
            if key in seen:
                frappe.throw(_("Duplicate scenario assignment rule on row {0}.").format(row.idx))
            seen.add(key)

            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active scenario assignment rule is required."))
