from __future__ import annotations

import json

import frappe
from frappe.model.document import Document


class PerformanceMetric(Document):
    def validate(self):
        if self.source_type == "Doc Query":
            if not self.source_doctype:
                frappe.throw(frappe._("Doc Query metrics require a Source DocType."))
            if self.aggregate and self.aggregate != "count" and not self.value_field:
                frappe.throw(frappe._("Aggregate {0} requires a Value Field.").format(self.aggregate))
            if self.filters_json:
                try:
                    json.loads(self.filters_json)
                except json.JSONDecodeError as exc:
                    frappe.throw(frappe._("Filters JSON is not valid: {0}").format(exc))
