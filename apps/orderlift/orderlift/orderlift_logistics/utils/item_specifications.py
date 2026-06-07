from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def validate_item_specifications(item_doc, method=None):
    rows = item_doc.get("custom_specifications") or []
    seen = set()
    search_parts = []

    for row in rows:
        attribute_name = (
            getattr(row, "specification_attribute", "")
            or getattr(row, "attribute", "")
            or ""
        ).strip()
        if not attribute_name:
            continue

        key = attribute_name.lower()
        if key in seen:
            frappe.throw(_("Row {0}: duplicate specification attribute {1}.").format(row.idx, attribute_name))
        seen.add(key)

        attribute = frappe.get_cached_doc("Item Specification Attribute", attribute_name)
        if not flt(getattr(attribute, "is_active", 1)):
            frappe.throw(_("Row {0}: specification attribute {1} is inactive.").format(row.idx, attribute_name))

        value_type = (getattr(attribute, "value_type", "") or "Texte").strip()
        unit = (getattr(attribute, "unit", "") or "").strip()
        label = (getattr(attribute, "attribute_name", "") or attribute_name).strip()

        row.value_type = value_type
        row.unit = unit

        if value_type == "Nombre":
            raw_value = _spec_value(row)
            if raw_value == "":
                frappe.throw(_("Row {0}: value is required for specification {1}.").format(row.idx, label))

            value = _format_number(flt(raw_value))
            row.value = value
            row.number_value = flt(raw_value)
            row.display_value = _join_value_unit(value, unit)
            row.text_value = ""
        else:
            value = _spec_value(row)
            if not value:
                frappe.throw(_("Row {0}: value is required for specification {1}.").format(row.idx, label))
            row.value = value
            row.text_value = value
            row.display_value = _join_value_unit(value, unit)

        search_parts.append(f"{label}: {row.display_value}".lower())

    if item_doc.meta.get_field("custom_specification_search_text"):
        item_doc.custom_specification_search_text = " ".join(search_parts)


def _join_value_unit(value, unit):
    value = str(value or "").strip()
    unit = (unit or "").strip()
    return f"{value} {unit}".strip()


def _spec_value(row):
    value = getattr(row, "value", None)
    if value in (None, ""):
        value = getattr(row, "text_value", None)
    if value in (None, ""):
        value = getattr(row, "number_value", None)
    return str(value or "").strip()


def _format_number(value):
    number = flt(value)
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")
