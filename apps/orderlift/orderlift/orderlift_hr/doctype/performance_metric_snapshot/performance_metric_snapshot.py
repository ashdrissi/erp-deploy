from __future__ import annotations

import frappe
from frappe.model.document import Document


class PerformanceMetricSnapshot(Document):
    def validate(self):
        if not self.employee or not self.metric or not self.appraisal_cycle:
            return

        existing = frappe.db.get_value(
            "Performance Metric Snapshot",
            {
                "employee": self.employee,
                "metric": self.metric,
                "appraisal_cycle": self.appraisal_cycle,
                "name": ["!=", self.name or ""],
            },
            "name",
        )
        if existing:
            frappe.throw(
                frappe._(
                    "Snapshot for {0} / {1} / {2} already exists: {3}"
                ).format(self.employee, self.metric, self.appraisal_cycle, existing)
            )

        if self.employee and not self.user:
            self.user = frappe.db.get_value("Employee", self.employee, "user_id")
