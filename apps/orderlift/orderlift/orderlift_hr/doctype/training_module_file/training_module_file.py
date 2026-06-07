from __future__ import annotations

import frappe
from frappe.model.document import Document


class TrainingModuleFile(Document):
    def validate(self):
        ft = self.file_type
        if ft in ("PDF", "Excel", "Image") and not self.attachment:
            frappe.throw(frappe._("Attachment required for file type {0}.").format(ft))
        if ft in ("Video URL", "External Link") and not self.url:
            frappe.throw(frappe._("URL required for file type {0}.").format(ft))
        if ft == "Note" and not (self.note_body or "").strip():
            frappe.throw(frappe._("Note body required for Note file type."))
