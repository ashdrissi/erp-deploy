from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from orderlift.document_templates import normalize_field_key


class OrderliftDocumentTemplate(Document):
    def validate(self):
        if not self.targets:
            frappe.throw(_("At least one target DocType is required."))

        seen_targets = set()
        for row in self.targets:
            if not frappe.db.exists("DocType", row.target_doctype):
                frappe.throw(_("Target DocType {0} was not found.").format(row.target_doctype))
            if row.target_doctype in seen_targets:
                frappe.throw(_("Target DocType {0} is duplicated.").format(row.target_doctype))
            seen_targets.add(row.target_doctype)
            row.display_order = row.display_order or row.idx

        seen_keys = set()
        for row in self.fields or []:
            row.field_key = normalize_field_key(row.field_key or row.field_label)
            if row.field_key in seen_keys:
                frappe.throw(_("Field key {0} is duplicated.").format(row.field_key))
            seen_keys.add(row.field_key)
            row.required_value_mode = "Checked" if row.fieldtype == "Check" and row.required_value_mode == "Checked" else "Present"

        if not self.statuses:
            frappe.throw(_("At least one status is required."))
        default_seen = False
        seen_statuses = set()
        for row in self.statuses:
            row.status_label = (row.status_label or "").strip()
            if not row.status_label:
                frappe.throw(_("Every status must have a label."))
            if row.status_label in seen_statuses:
                frappe.throw(_("Status {0} is duplicated.").format(row.status_label))
            seen_statuses.add(row.status_label)
            if cint(row.is_default) and not default_seen:
                default_seen = True
            elif cint(row.is_default):
                row.is_default = 0
        if self.statuses and not any(cint(row.is_default) for row in self.statuses):
            self.statuses[0].is_default = 1

    def on_trash(self):
        annex_count = frappe.db.count("Orderlift Annex Document", {"template": self.name})
        if annex_count:
            frappe.throw(
                _("This template is referenced by {0} annex document(s) and cannot be deleted.").format(annex_count)
            )
