from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ItemMaterial(Document):
    def validate(self):
        self.material_name = (self.material_name or "").strip().upper()
        self.material_code = (self.material_code or self.material_name or "").strip().upper()
        self.aliases = (self.aliases or "").strip()

        if not self.material_name:
            frappe.throw(_("Material name is required."))
        if not self.material_code:
            frappe.throw(_("Material code is required."))
