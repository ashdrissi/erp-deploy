from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class TechnicalProcurementRoute(Document):
    def validate(self):
        ordered = sorted(self.steps or [], key=lambda row: (cint(row.sequence), cint(row.idx)))
        seen = set()
        for row in ordered:
            if cint(row.sequence) < 0:
                frappe.throw(_("Route step sequence cannot be negative."))
            if row.action in seen:
                frappe.throw(_("Action {0} appears more than once in this route.").format(row.action))
            if row.required_previous_action and row.required_previous_action not in seen:
                frappe.throw(
                    _("Required action {0} must appear before {1}.").format(
                        row.required_previous_action, row.action
                    )
                )
            seen.add(row.action)

        if cint(self.is_default) and cint(self.enabled):
            for row in frappe.get_all(
                self.doctype,
                filters={"enabled": 1, "is_default": 1, "name": ["!=", self.name or ""]},
                fields=["name", "company"],
                limit_page_length=0,
            ):
                if (row.get("company") or "") == (self.company or ""):
                    scope = self.company or _("global scope")
                    frappe.throw(_("Route {0} is already the default for {1}.").format(row.name, scope))
