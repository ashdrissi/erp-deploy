import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from orderlift.sales.utils.dimensioning import validate_dimensioning_key, validate_formula


class DimensioningSet(Document):
    def validate(self):
        self._validate_fields()
        self._validate_rules()

    def _validate_fields(self):
        seen = set()
        for row in self.input_fields or []:
            if not row.label:
                frappe.throw(_("Row {0}: Field label is required.").format(row.idx))
            key = validate_dimensioning_key(row.field_key)
            row.field_key = key
            if key in seen:
                frappe.throw(_("Row {0}: Field key {1} is duplicated.").format(row.idx, key))
            seen.add(key)
            if (row.field_type or "").strip() == "Select" and not (row.options or "").strip():
                frappe.throw(_("Row {0}: Select fields require options.").format(row.idx))

    def _validate_rules(self):
        allowed_names = {row.field_key for row in (self.input_fields or []) if row.field_key}
        for row in self.item_rules or []:
            if cint(row.is_active) != 1:
                continue
            if not row.item:
                frappe.throw(_("Row {0}: Item is required.").format(row.idx))
            if not (row.qty_formula or "").strip():
                frappe.throw(_("Row {0}: Qty Formula is required.").format(row.idx))
            try:
                validate_formula(row.qty_formula, allowed_names)
                validate_formula(row.condition_formula, allowed_names)
            except ValueError as exc:
                frappe.throw(_("Row {0}: {1}").format(row.idx, str(exc)))
