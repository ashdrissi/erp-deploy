import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from orderlift.sales.utils.dimensioning import (
    coerce_dimensioning_value,
    evaluate_formula,
    validate_dimensioning_key,
    validate_formula,
)


class DimensioningSet(Document):
    def validate(self):
        self._validate_fields()
        self._validate_rules()

    def _validate_fields(self):
        seen = set()
        for row in self.input_fields or []:
            if not row.label:
                frappe.throw(_("Row {0}: Caracteristique is required.").format(row.idx))
            key = validate_dimensioning_key(row.field_key)
            row.field_key = key
            if key in seen:
                frappe.throw(_("Row {0}: Field key {1} is duplicated.").format(row.idx, key))
            seen.add(key)
            if (row.field_type or "").strip() == "Select" and not (row.options or "").strip():
                frappe.throw(_("Row {0}: Select caracteristiques require options.").format(row.idx))

    def _validate_rules(self):
        allowed_names = {row.field_key for row in (self.input_fields or []) if row.field_key}
        for row in self.item_rules or []:
            if cint(row.is_active) != 1:
                continue
            if not row.item:
                frappe.throw(_("Row {0}: Item is required.").format(row.idx))
            if not (row.qty_formula or "").strip():
                frappe.throw(_("Row {0}: Quantity formula is required.").format(row.idx))
            try:
                validate_formula(row.qty_formula, allowed_names)
                validate_formula(row.condition_formula, allowed_names)
            except ValueError as exc:
                frappe.throw(_("Row {0}: {1}").format(row.idx, str(exc)))

    def serialize_config(self):
        fields = []
        for row in sorted(self.input_fields or [], key=lambda d: (cint(d.sequence or 0), cint(d.idx or 0))):
            fields.append(
                {
                    "field_key": row.field_key,
                    "label": row.label,
                    "field_type": row.field_type or "Float",
                    "options": [opt.strip() for opt in (row.options or "").splitlines() if opt.strip()],
                    "default_value": row.default_value or "",
                    "is_required": 1 if cint(row.is_required) else 0,
                    "help_text": row.help_text or "",
                    "sequence": cint(row.sequence or 0),
                }
            )
        return {
            "name": self.name,
            "set_name": self.set_name or self.name,
            "description": self.description or "",
            "fields": fields,
        }

    def coerce_input_values(self, input_values_json=None):
        if input_values_json is None:
            raw_values = {}
        elif isinstance(input_values_json, str):
            raw_values = frappe.parse_json(input_values_json) or {}
        else:
            raw_values = input_values_json or {}

        values = {}
        for field in self.input_fields or []:
            key = field.field_key
            raw_value = raw_values.get(key, field.default_value)
            value = coerce_dimensioning_value(field.field_type, raw_value)
            if cint(field.is_required) and value in (None, "", False):
                frappe.throw(_("Caracteristique {0} is required.").format(field.label or key))
            values[key] = value
        return values

    def preview_generated_items(self, values):
        preview = []
        for rule in sorted(self.item_rules or [], key=lambda d: (cint(d.sequence or 0), cint(d.idx or 0))):
            if cint(rule.is_active) != 1:
                continue

            condition_ok = True
            if (rule.condition_formula or "").strip():
                condition_ok = bool(evaluate_formula(rule.condition_formula, values))
            if not condition_ok:
                continue

            qty = flt(evaluate_formula(rule.qty_formula, values) or 0)
            if qty <= 0:
                continue

            preview.append(
                {
                    "rule_label": rule.rule_label or rule.item,
                    "item": rule.item,
                    "qty": qty,
                    "qty_formula": rule.qty_formula or "",
                    "condition_formula": rule.condition_formula or "",
                    "display_group": (rule.display_group or self.set_name or self.name or "").strip(),
                    "show_in_detail": 1 if cint(rule.show_in_detail) else 0,
                }
            )
        return preview


@frappe.whitelist()
def get_dimensioning_set_payload(set_name):
    if not set_name:
        return {"set": None}
    doc = frappe.get_doc("Dimensioning Set", set_name)
    return {"set": doc.serialize_config()}


@frappe.whitelist()
def preview_dimensioning_set(set_name, input_values_json=None):
    if not set_name:
        return {"items": [], "values": {}}
    doc = frappe.get_doc("Dimensioning Set", set_name)
    values = doc.coerce_input_values(input_values_json=input_values_json)
    return {
        "set": doc.serialize_config(),
        "values": values,
        "items": doc.preview_generated_items(values),
    }
