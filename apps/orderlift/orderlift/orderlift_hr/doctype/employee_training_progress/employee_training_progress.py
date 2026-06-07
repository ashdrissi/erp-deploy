from __future__ import annotations

import frappe
from frappe.model.document import Document


class EmployeeTrainingProgress(Document):
    def validate(self):
        if not self.employee or not self.module:
            return

        existing = frappe.db.get_value(
            "Employee Training Progress",
            {"employee": self.employee, "module": self.module, "name": ["!=", self.name or ""]},
            "name",
        )
        if existing:
            frappe.throw(
                frappe._("Progress row for employee {0} and module {1} already exists: {2}").format(
                    self.employee, self.module, existing
                )
            )

        if self.module and (not self.program or not self.level):
            module = frappe.db.get_value(
                "Training Module", self.module, ["program", "level"], as_dict=True
            )
            if module:
                if not self.program:
                    self.program = module.program
                if not self.level:
                    self.level = module.level

        if self.studied and not self.studied_on:
            self.studied_on = frappe.utils.now_datetime()

        self.last_activity = frappe.utils.now_datetime()

        if self.employee and not self.user:
            self.user = frappe.db.get_value("Employee", self.employee, "user_id")
