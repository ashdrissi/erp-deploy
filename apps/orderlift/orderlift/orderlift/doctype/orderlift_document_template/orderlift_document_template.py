from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from orderlift.document_templates import is_supported_template_target, normalize_field_key


class OrderliftDocumentTemplate(Document):
    def validate(self):
        if not self.targets:
            frappe.throw(_("Add at least one target document."))
        for row in self.targets:
            if not is_supported_template_target(row.target_doctype):
                frappe.throw(_("Unsupported template target: {0}").format(row.target_doctype))

        seen_keys = set()
        for row in self.fields or []:
            row.field_key = normalize_field_key(row.field_key or row.field_label)
            if row.field_key in seen_keys:
                frappe.throw(_("Field key {0} is duplicated.").format(row.field_key))
            seen_keys.add(row.field_key)

        if not self.statuses:
            self.append("statuses", {"status_label": "Draft", "color": "Gray", "is_default": 1, "display_order": 1})
        default_seen = False
        for row in self.statuses:
            if cint(row.is_default) and not default_seen:
                default_seen = True
            elif cint(row.is_default):
                row.is_default = 0
        if self.statuses and not any(cint(row.is_default) for row in self.statuses):
            self.statuses[0].is_default = 1
