from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ItemCategory(Document):
    def validate(self):
        self.item_group = (self.item_group or "").strip()
        self.category_name = (self.category_name or "").strip()
        self.abbreviation = _normalize_abbreviation(self.abbreviation)
        self.sequence_digits = cint(self.sequence_digits or 5)
        self.current_sequence = cint(self.current_sequence or 0)

        if not self.category_name:
            frappe.throw(_("Category name is required."))
        if not self.abbreviation:
            frappe.throw(_("Abbreviation is required for item sequencing."))
        if self.sequence_digits < 3:
            frappe.throw(_("Sequence digits must be at least 3."))
        if self.current_sequence < 0:
            frappe.throw(_("Current sequence cannot be negative."))
        if self.item_group and not frappe.db.exists("Item Group", self.item_group):
            frappe.throw(_("Item Group {0} does not exist.").format(self.item_group))


def _normalize_abbreviation(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").strip().upper())
