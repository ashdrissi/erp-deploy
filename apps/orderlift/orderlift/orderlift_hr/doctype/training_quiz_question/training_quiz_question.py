from __future__ import annotations

import frappe
from frappe.model.document import Document


class TrainingQuizQuestion(Document):
    def validate(self):
        if not self.options:
            frappe.throw(frappe._("Question must have at least one option."))
        correct = [o for o in self.options if o.is_correct]
        if not correct:
            frappe.throw(frappe._("Question must mark at least one option as correct."))
        if self.question_type == "Single Choice" and len(correct) > 1:
            frappe.throw(frappe._("Single Choice questions must have exactly one correct option."))
        if self.question_type == "True/False" and len(self.options) != 2:
            frappe.throw(frappe._("True/False questions must have exactly two options."))
