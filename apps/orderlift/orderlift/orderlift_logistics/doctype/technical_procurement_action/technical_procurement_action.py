from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


SAFE_ADAPTERS = {
    "revision_to_material_request": "Material Request",
    "revision_to_purchase_order": "Purchase Order",
    "revision_to_delivery_note": "Delivery Note",
    "revision_to_pick_list": "Pick List",
}


class TechnicalProcurementAction(Document):
    def validate(self):
        adapter_key = (self.adapter_key or "").strip()
        if adapter_key not in SAFE_ADAPTERS:
            frappe.throw(_("Select a supported technical procurement adapter."))
        if self.target_doctype != SAFE_ADAPTERS[adapter_key]:
            frappe.throw(
                _("Adapter {0} can only create {1}.").format(
                    adapter_key, SAFE_ADAPTERS[adapter_key]
                )
            )
        if cint(self.sequence) < 0:
            frappe.throw(_("Sequence cannot be negative."))
        if not self.is_new():
            existing = frappe.db.get_value(self.doctype, self.name, "adapter_key")
            if existing and existing != adapter_key:
                frappe.throw(_("Adapter Key cannot be changed after the action is created."))
