from __future__ import annotations

import frappe
from frappe.model.document import Document


class TrainingModule(Document):
    def validate(self):
        if self.level:
            level_program = frappe.db.get_value("Training Level", self.level, "program")
            if level_program and level_program != self.program:
                frappe.throw(
                    frappe._("Level {0} belongs to program {1}, not {2}.").format(
                        self.level, level_program, self.program
                    )
                )
