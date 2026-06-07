from __future__ import annotations

import frappe
from frappe.model.document import Document


class TrainingQuiz(Document):
    def validate(self):
        if not self.linked_module and not self.linked_level:
            frappe.throw(frappe._("A quiz must be linked to either a Module or a Level."))
        if self.linked_module and self.linked_level:
            frappe.throw(frappe._("A quiz can be linked to a Module or a Level, not both."))
        if self.unlimited_attempts:
            self.max_attempts = 0
