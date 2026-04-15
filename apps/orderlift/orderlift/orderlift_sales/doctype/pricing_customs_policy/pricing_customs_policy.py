import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PricingCustomsPolicy(Document):
    def validate(self):
        seen = set()
        active = 0

        for row in self.customs_rules or []:
            row.tariff_number = (getattr(row, "tariff_number", "") or "").strip().upper()
            row.material = (row.material or "").strip().upper()
            row.value_per_kg = flt(getattr(row, "value_per_kg", 0) or 0)
            row.rate_components = (getattr(row, "rate_components", "") or "").strip()
            row.sequence = cint(row.sequence or 90)
            row.priority = cint(row.priority or 10)
            row.rate_per_kg = flt(row.rate_per_kg)
            row.rate_percent = flt(row.rate_percent)

            if row.value_per_kg < 0:
                frappe.throw(_("Row {0}: Value per kg cannot be negative.").format(row.idx))
            if row.rate_per_kg < 0:
                frappe.throw(_("Row {0}: Rate per kg cannot be negative.").format(row.idx))
            if row.rate_percent < 0:
                frappe.throw(_("Row {0}: Rate percent cannot be negative.").format(row.idx))

            key = ((row.tariff_number or row.material).lower(), row.priority, cint(row.is_active))
            if key in seen:
                frappe.throw(
                    _("Duplicate customs rule for tariff/material {0}, priority {1}.").format(
                        row.tariff_number or row.material or "Any",
                        row.priority,
                    )
                )
            seen.add(key)

            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active customs rule is required."))
