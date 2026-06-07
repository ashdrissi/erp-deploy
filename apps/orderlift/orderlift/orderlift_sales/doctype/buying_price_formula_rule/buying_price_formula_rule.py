from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class BuyingPriceFormulaRule(Document):
    def validate(self):
        self.rule_name = (self.rule_name or "").strip()
        self.source_item = (self.source_item or "").strip()
        if not self.rule_name:
            frappe.throw(_("Rule Name is required."))
        if not self.source_item:
            frappe.throw(_("Source Item is required."))

        seen = set()
        active_targets = 0
        for row in self.targets or []:
            row.target_item = (row.target_item or "").strip()
            row.adjustment_percent = flt(row.adjustment_percent or 0)
            row.is_active = 1 if cint(row.is_active if row.is_active is not None else 1) else 0
            if not row.target_item:
                frappe.throw(_("Target Item is required in row {0}.").format(row.idx))
            if row.target_item == self.source_item:
                frappe.throw(_("Target Item cannot be the same as Source Item in row {0}.").format(row.idx))
            if row.target_item in seen:
                frappe.throw(_("Target Item {0} is duplicated.").format(row.target_item))
            seen.add(row.target_item)
            if row.is_active:
                active_targets += 1

        if not active_targets:
            frappe.throw(_("Add at least one active formula target."))


def serialize_rule(doc):
    return {
        "name": doc.name,
        "rule_name": doc.rule_name,
        "source": doc.source_item,
        "checked": bool(cint(doc.is_active)),
        "targets": [
            {
                "code": row.target_item,
                "pct": flt(row.adjustment_percent or 0),
            }
            for row in doc.targets or []
            if cint(row.is_active)
        ],
        "notes": doc.notes or "",
    }
