import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PricingMarginPolicy(Document):
    def validate(self):
        seen = set()
        active = 0

        for row in self.margin_rules or []:
            row.sales_person = (row.sales_person or "").strip()
            row.geography_territory = (row.geography_territory or "").strip()
            row.geography_country = (row.geography_country or "").strip()
            row.geography_city = (row.geography_city or "").strip()
            row.geography_region = (row.geography_region or "").strip()
            row.customer_segment = (row.customer_segment or "").strip().upper()
            row.customer_type = (row.customer_type or "").strip()
            row.tier = (row.tier or "").strip()
            row.item = (row.item or "").strip()
            row.source_bundle = (row.source_bundle or "").strip()
            row.item_group = (row.item_group or "").strip()
            row.material = (row.material or "").strip().upper()
            row.sequence = cint(row.sequence or 90)
            row.priority = cint(row.priority or 10)
            row.margin_percent = flt(row.margin_percent)
            row.applies_to = (row.applies_to or "Running Total").strip().title()

            if row.item and row.item_group:
                frappe.throw(_("Row {0}: set Item or Item Group, not both.").format(row.idx))

            if row.applies_to not in ("Base Price", "Running Total"):
                frappe.throw(_("Row {0}: Applies To must be Base Price or Running Total.").format(row.idx))

            if row.margin_percent < -100:
                frappe.throw(_("Row {0}: Margin percent cannot be below -100.").format(row.idx))

            key = (
                row.sales_person.lower(),
                row.geography_territory.lower(),
                row.geography_country.lower(),
                row.geography_city.lower(),
                row.geography_region.lower(),
                row.customer_segment.lower(),
                row.customer_type.lower(),
                row.tier.lower(),
                row.item.lower(),
                row.source_bundle.lower(),
                row.item_group.lower(),
                row.material.lower(),
                row.priority,
                cint(row.is_active),
            )
            if key in seen:
                frappe.throw(_("Duplicate margin rule on row {0}.").format(row.idx))
            seen.add(key)

            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active margin rule is required."))
