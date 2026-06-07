from __future__ import annotations

import frappe
from frappe.model.document import Document


class PerformanceProfile(Document):
    def validate(self):
        seen: set[str] = set()
        for row in self.metrics or []:
            if row.metric in seen:
                frappe.throw(frappe._("Metric {0} listed twice in profile.").format(row.metric))
            seen.add(row.metric)
            if row.weight is None:
                row.weight = 0.0
