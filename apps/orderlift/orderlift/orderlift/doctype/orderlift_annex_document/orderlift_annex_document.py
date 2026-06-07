from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from orderlift.document_templates import get_default_status, is_supported_template_target


class OrderliftAnnexDocument(Document):
    def validate(self):
        if not is_supported_template_target(self.reference_doctype):
            frappe.throw(_("Document templates are not enabled for {0}.").format(self.reference_doctype))
        if not frappe.db.exists(self.reference_doctype, self.reference_name):
            frappe.throw(_("{0} {1} was not found.").format(self.reference_doctype, self.reference_name))
        template = frappe.get_doc("Orderlift Document Template", self.template)
        self.template_name = template.template_name
        self.status = self.status or get_default_status(template)
        target_doctypes = {row.target_doctype for row in template.targets or []}
        if self.reference_doctype not in target_doctypes:
            frappe.throw(_("Template {0} is not enabled for {1}.").format(template.template_name, self.reference_doctype))
