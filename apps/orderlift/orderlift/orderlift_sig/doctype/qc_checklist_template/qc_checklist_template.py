from __future__ import annotations

import frappe
from frappe.model.document import Document


class QCChecklistTemplate(Document):
    def validate(self):
        if not self.items:
            frappe.throw(frappe._("A QC Checklist Template must have at least one item."))
