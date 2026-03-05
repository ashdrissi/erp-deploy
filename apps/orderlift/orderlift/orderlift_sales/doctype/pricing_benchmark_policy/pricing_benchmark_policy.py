"""Pricing Benchmark Policy controller.

Manages benchmark sources (which price lists to compare against)
and ratio-band rules (cost/benchmark ratio -> margin %).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PricingBenchmarkPolicy(Document):
    def validate(self):
        self._validate_sources()
        self._validate_rules()

    def _validate_sources(self):
        active = 0
        seen = set()
        for row in self.benchmark_sources or []:
            row.price_list = (row.price_list or "").strip()
            if not row.price_list:
                frappe.throw(_("Row {0}: Price List is required.").format(row.idx))
            if row.price_list in seen:
                frappe.throw(_("Row {0}: duplicate price list {1}.").format(row.idx, row.price_list))
            seen.add(row.price_list)
            row.weight = flt(row.weight) or 1.0
            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active benchmark source is required."))

    def _validate_rules(self):
        active = 0
        for row in self.benchmark_rules or []:
            row.ratio_min = flt(row.ratio_min)
            row.ratio_max = flt(row.ratio_max)
            row.target_margin_percent = flt(row.target_margin_percent)
            row.priority = cint(row.priority or 10)
            row.sequence = cint(row.sequence or 90)

            if row.ratio_min < 0:
                frappe.throw(_("Row {0}: ratio_min cannot be negative.").format(row.idx))
            if row.ratio_max and row.ratio_max <= row.ratio_min:
                frappe.throw(_("Row {0}: ratio_max must be greater than ratio_min.").format(row.idx))
            if row.target_margin_percent < -100:
                frappe.throw(_("Row {0}: target margin cannot be below -100%.").format(row.idx))

            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active benchmark rule is required."))
