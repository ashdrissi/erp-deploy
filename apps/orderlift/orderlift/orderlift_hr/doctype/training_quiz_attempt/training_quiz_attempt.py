from __future__ import annotations

import frappe
from frappe.model.document import Document


class TrainingQuizAttempt(Document):
    def validate(self):
        if self.completed_on and not self.is_new():
            previous = self.get_doc_before_save()
            if previous and previous.completed_on:
                frozen_fields = (
                    "quiz",
                    "employee",
                    "user",
                    "started_on",
                    "completed_on",
                    "duration_seconds",
                    "score",
                    "max_score",
                    "score_percentage",
                    "passed",
                )
                for field in frozen_fields:
                    if self.get(field) != previous.get(field):
                        frappe.throw(
                            frappe._("Submitted quiz attempts cannot be modified.")
                        )
                if len(self.answers or []) != len(previous.answers or []):
                    frappe.throw(
                        frappe._("Submitted quiz attempts cannot be modified.")
                    )

        if self.max_score and self.max_score > 0:
            self.score_percentage = (float(self.score or 0) / float(self.max_score)) * 100.0
        else:
            self.score_percentage = 0.0

        if self.completed_on and self.started_on and not self.duration_seconds:
            delta = frappe.utils.get_datetime(self.completed_on) - frappe.utils.get_datetime(
                self.started_on
            )
            self.duration_seconds = int(delta.total_seconds())
