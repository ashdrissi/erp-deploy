from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from orderlift.quotation_detail_templates import normalize_block_key, supported_block_types


class OrderliftQuotationDetailTemplate(Document):
    def validate(self):
        allowed_types = supported_block_types()
        seen_keys = set()
        for row in self.blocks or []:
            row.block_key = normalize_block_key(row.block_key or row.block_label or row.block_type)
            if row.block_key in seen_keys:
                frappe.throw(_("Block key {0} is duplicated.").format(row.block_key))
            seen_keys.add(row.block_key)
            if row.block_type not in allowed_types:
                frappe.throw(_("Unsupported quotation detail block type: {0}").format(row.block_type))
            row.display_order = cint(row.display_order) or row.idx
