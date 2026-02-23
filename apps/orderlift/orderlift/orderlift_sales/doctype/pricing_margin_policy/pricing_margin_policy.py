import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PricingMarginPolicy(Document):
    def validate(self):
        seen = set()
        active = 0

        for row in self.margin_rules or []:
            row.customer_type = (row.customer_type or "").strip()
            row.tier = (row.tier or "").strip()
            row.sequence = cint(row.sequence or 90)
            row.priority = cint(row.priority or 10)
            row.margin_percent = flt(row.margin_percent)
            row.applies_to = (row.applies_to or "Running Total").strip().title()

            if row.applies_to not in ("Base Price", "Running Total"):
                frappe.throw(_("Row {0}: Applies To must be Base Price or Running Total.").format(row.idx))

            if row.margin_percent < -100:
                frappe.throw(_("Row {0}: Margin percent cannot be below -100.").format(row.idx))

            key = (row.customer_type.lower(), row.tier.lower(), row.priority, cint(row.is_active))
            if key in seen:
                frappe.throw(
                    _("Duplicate margin rule for customer type {0}, tier {1}, priority {2}.").format(
                        row.customer_type or "Any",
                        row.tier or "Any",
                        row.priority,
                    )
                )
            seen.add(key)

            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active margin rule is required."))
