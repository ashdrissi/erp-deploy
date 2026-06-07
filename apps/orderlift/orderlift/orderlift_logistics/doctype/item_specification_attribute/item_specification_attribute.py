from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ItemSpecificationAttribute(Document):
    def validate(self):
        self.attribute_name = (self.attribute_name or "").strip()
        self.value_type = (self.value_type or "").strip()
        self.unit = (self.unit or "").strip()
        self.sequence = cint(self.sequence or 90)

        if self.value_type not in {"Texte", "Nombre"}:
            frappe.throw(_("Type de valeur invalide pour l'attribut de specification."))
