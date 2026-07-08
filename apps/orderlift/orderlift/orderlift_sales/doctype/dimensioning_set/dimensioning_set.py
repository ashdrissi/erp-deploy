import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from orderlift.sales.utils.dimensioning import (
    coerce_dimensioning_value,
    evaluate_formula,
    evaluate_structured_condition,
    evaluate_structured_quantity,
    validate_formula,
    validate_dimensioning_key,
    validate_structured_condition,
    validate_structured_quantity,
)


ITEM_FILTER_FIELDS = {
    "item": "name",
    "item_code": "name",
    "name": "name",
    "item_name": "item_name",
    "description": "description",
    "item_description": "description",
    "item_group": "item_group",
    "brand": "brand",
    "stock_uom": "stock_uom",
    "material": "custom_material",
    "custom_material": "custom_material",
    "customs_material": "custom_customs_material",
    "custom_customs_material": "custom_customs_material",
    "length_cm": "custom_length_cm",
    "custom_length_cm": "custom_length_cm",
    "width_cm": "custom_width_cm",
    "custom_width_cm": "custom_width_cm",
    "height_cm": "custom_height_cm",
    "custom_height_cm": "custom_height_cm",
    "item_category": "custom_item_category",
    "custom_item_category": "custom_item_category",
    "weight_per_unit": "weight_per_unit",
    "variant_of": "variant_of",
}
ITEM_FILTER_OPERATORS = {"==", "!=", "contains", ">", ">=", "<", "<="}


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
        for row in getattr(self, "derived_fields", None) or []:
            if not row.label:
                frappe.throw(_("Calculation row {0}: Label is required.").format(row.idx))
            key = validate_dimensioning_key(row.field_key)
            row.field_key = key
            if key in seen:
                frappe.throw(_("Calculation row {0}: Field key {1} is duplicated.").format(row.idx, key))
            try:
                validate_formula(row.formula or "", seen)
            except ValueError as exc:
                frappe.throw(_("Calculation row {0}: {1}").format(row.idx, str(exc)))
            seen.add(key)

    def _validate_rules(self):
        field_types = self._field_types()
        allowed_formula_names = set(field_types)
        allowed_formula_names.update(
            f"row_{cint(row.sequence or 0)}" for row in self.item_rules or [] if cint(row.sequence or 0)
        )
        for row in self.item_rules or []:
            if cint(row.is_active) != 1:
                continue
            selection_mode = _item_selection_mode(row)
            if selection_mode == "fixed" and not row.item:
                frappe.throw(_("Row {0}: Item is required.").format(row.idx))
            if selection_mode == "filtered":
                try:
                    _validate_item_filters(row, allowed_formula_names)
                except ValueError as exc:
                    frappe.throw(_("Row {0}: {1}").format(row.idx, str(exc)))
            try:
                if _uses_advanced_formula(row):
                    validate_formula(row.condition_formula or "", allowed_formula_names)
                    validate_formula(row.qty_formula or "", allowed_formula_names)
                    if not (row.qty_formula or "").strip():
                        validate_structured_quantity(row, field_types)
                else:
                    _validate_rule_condition(row, field_types, allowed_formula_names)
                    _validate_rule_quantity(row, field_types, allowed_formula_names)
            except ValueError as exc:
                frappe.throw(_("Row {0}: {1}").format(row.idx, str(exc)))

    def serialize_config(self):
        return {
            "name": self.name,
            "set_name": self.set_name or self.name,
            "description": self.description or "",
            "is_active": 1 if cint(self.is_active) else 0,
            "fields": self.serialize_questions(),
            "derived_fields": self.serialize_derived_fields(),
            "rule_groups": self.serialize_rule_groups(),
        }

    def serialize_questions(self):
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
                    "group": getattr(row, "group", None) or "",
                    "sequence": cint(row.sequence or 0),
                }
            )
        return fields

    def serialize_derived_fields(self):
        fields = []
        for row in sorted(getattr(self, "derived_fields", None) or [], key=lambda d: (cint(d.sequence or 0), cint(d.idx or 0))):
            fields.append(
                {
                    "field_key": row.field_key,
                    "label": row.label,
                    "field_type": row.field_type or "Float",
                    "formula": row.formula or "",
                    "help_text": row.help_text or "",
                    "group": getattr(row, "group", None) or "",
                    "sequence": cint(row.sequence or 0),
                }
            )
        return fields

    def serialize_rule_groups(self):
        groups = []
        by_group = {}
        for row in sorted(self.item_rules or [], key=lambda d: (cint(d.sequence or 0), cint(d.idx or 0))):
            group_key = (row.rule_group or "").strip() or f"GROUP-{len(groups) + 1:03d}"
            if group_key not in by_group:
                group = {
                    "rule_group": group_key,
                    "sequence": cint(row.sequence or 0),
                    "is_active": 1 if cint(row.is_active) else 0,
                    "condition_mode": row.condition_mode or "always",
                    "question_key": row.question_key or "",
                    "operator": row.operator or "==",
                    "compare_source": row.compare_source or "manual",
                    "manual_value": row.manual_value or "",
                    "compare_question_key": row.compare_question_key or "",
                    "condition_rules_json": row.condition_rules_json or "",
                    "articles": [],
                }
                by_group[group_key] = group
                groups.append(group)
            by_group[group_key]["articles"].append(
                {
                    "sequence": cint(row.sequence or 0),
                    "is_active": 1 if cint(row.is_active) else 0,
                    "rule_label": row.rule_label or row.item,
                    "item_selection_mode": _item_selection_mode(row),
                    "item": row.item,
                    "item_filters_json": _item_filters_json(row),
                    "display_group": row.display_group or "",
                    "condition_formula": row.condition_formula or "",
                    "condition_formula_builder_json": row.condition_formula_builder_json or "",
                    "qty_formula": row.qty_formula or "",
                    "qty_formula_builder_json": row.qty_formula_builder_json or "",
                    "quantity_mode": row.quantity_mode or "fixed",
                    "fixed_qty": flt(row.fixed_qty or 0),
                    "quantity_question_key": row.quantity_question_key or "",
                    "show_in_detail": 1 if cint(row.show_in_detail) else 0,
                }
            )
        return groups

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
        field_types = self._field_types()
        formula_context = dict(values or {})
        derived_values = self._evaluate_derived_fields(formula_context)
        formula_context.update(derived_values)
        for rule in sorted(self.item_rules or [], key=lambda d: (cint(d.sequence or 0), cint(d.idx or 0))):
            row_key = f"row_{cint(rule.sequence or 0)}" if cint(rule.sequence or 0) else ""
            if cint(rule.is_active) != 1:
                if row_key:
                    formula_context[row_key] = 0
                continue

            try:
                if _uses_advanced_formula(rule):
                    if (rule.condition_formula or "").strip() and not evaluate_formula(
                        rule.condition_formula,
                        formula_context,
                    ):
                        qty = 0
                    elif (rule.qty_formula or "").strip():
                        qty = flt(evaluate_formula(rule.qty_formula, formula_context) or 0)
                    else:
                        qty = flt(evaluate_structured_quantity(rule, formula_context) or 0)
                else:
                    if not _evaluate_rule_condition(rule, formula_context, field_types):
                        qty = 0
                    else:
                        qty = flt(_evaluate_rule_quantity(rule, formula_context) or 0)
                if row_key:
                    formula_context[row_key] = qty
                if qty <= 0:
                    continue
            except Exception as exc:
                if row_key:
                    formula_context[row_key] = 0
                frappe.throw(_("Dimensioning rule {0}: {1}").format(rule.rule_label or rule.idx, str(exc)))

            resolved_item, resolution_warning = self._resolve_rule_item(rule, formula_context)
            preview.append(
                {
                    "rule_label": rule.rule_label or resolved_item or rule.item,
                    "item": resolved_item,
                    "qty": qty,
                    "rule_group": rule.rule_group or "",
                    "display_group": (rule.display_group or self.set_name or self.name or "").strip(),
                    "show_in_detail": 1 if cint(rule.show_in_detail) else 0,
                    "item_selection_mode": _item_selection_mode(rule),
                    "resolution_warning": resolution_warning,
                    "missing_item": 1 if resolution_warning or not resolved_item else 0,
                }
            )
        self._add_item_preview_details(preview)
        return preview

    def _resolve_rule_item(self, rule, formula_context):
        if _item_selection_mode(rule) == "fixed":
            return (rule.item or "").strip(), ""
        return _resolve_filtered_item(rule, formula_context)

    def _add_item_preview_details(self, preview):
        item_codes = [row.get("item") for row in preview if row.get("item")]
        if not item_codes:
            return
        item_details = {
            row.name: row
            for row in frappe.get_all(
                "Item",
                filters={"name": ["in", item_codes]},
                fields=["name", "item_name", "item_group", "stock_uom", "description"],
                limit_page_length=0,
            )
        }
        for row in preview:
            details = item_details.get(row.get("item"))
            if not details:
                row.update({"item_name": "", "item_group": "", "stock_uom": "", "description": "", "missing_item": 1})
                if row.get("item") and not row.get("resolution_warning"):
                    row["resolution_warning"] = _("Item {0} was not found in the Items list.").format(row.get("item"))
                continue
            row.update(
                {
                    "item_name": details.item_name or "",
                    "item_group": details.item_group or "",
                    "stock_uom": details.stock_uom or "",
                    "description": details.description or "",
                }
            )

    def _evaluate_derived_fields(self, formula_context):
        values = {}
        for row in sorted(getattr(self, "derived_fields", None) or [], key=lambda d: (cint(d.sequence or 0), cint(d.idx or 0))):
            try:
                raw_value = evaluate_formula(row.formula or "0", formula_context)
                value = coerce_dimensioning_value(row.field_type, raw_value)
            except Exception as exc:
                frappe.throw(_("Dimensioning calculation {0}: {1}").format(row.label or row.field_key, str(exc)))
            values[row.field_key] = value
            formula_context[row.field_key] = value
        return values

    def _field_types(self):
        field_types = {
            row.field_key: (row.field_type or "Data").strip().title()
            for row in (self.input_fields or [])
            if row.field_key
        }
        field_types.update(
            {
                row.field_key: (row.field_type or "Data").strip().title()
                for row in (getattr(self, "derived_fields", None) or [])
                if row.field_key
            }
        )
        return field_types


@frappe.whitelist()
def get_dimensioning_set_payload(set_name):
    if not set_name:
        return {"set": None}
    frappe.has_permission("Dimensioning Set", "read", throw=True)
    doc = frappe.get_doc("Dimensioning Set", set_name)
    return {"set": doc.serialize_config()}


@frappe.whitelist()
def get_dimensioning_builder_payload(set_name=None):
    if not set_name:
        return {"set": None}
    frappe.has_permission("Dimensioning Set", "read", throw=True)
    doc = frappe.get_doc("Dimensioning Set", set_name)
    return {"set": doc.serialize_config()}


@frappe.whitelist()
def get_dimensioning_manager_data():
    frappe.has_permission("Dimensioning Set", "read", throw=True)
    rows = frappe.get_all(
        "Dimensioning Set",
        fields=["name", "set_name", "description", "is_active", "modified", "owner"],
        order_by="modified desc",
        limit_page_length=0,
    )
    sets = []
    for row in rows:
        doc = frappe.get_doc("Dimensioning Set", row.name)
        rule_groups = doc.serialize_rule_groups()
        sets.append(
            {
                "name": doc.name,
                "set_name": doc.set_name or doc.name,
                "description": doc.description or "",
                "is_active": 1 if cint(doc.is_active) else 0,
                "question_count": len(doc.input_fields or []),
                "rule_group_count": len(rule_groups),
                "article_count": len(doc.item_rules or []),
                "modified": row.modified,
                "owner": row.owner,
            }
        )
    return {"sets": sets}


@frappe.whitelist()
def save_dimensioning_builder_payload(payload):
    frappe.has_permission("Dimensioning Set", "create", throw=True)
    payload = _parse_payload(payload)
    name = (payload.get("name") or "").strip()
    if name and frappe.db.exists("Dimensioning Set", name):
        doc = frappe.get_doc("Dimensioning Set", name)
    else:
        doc = frappe.new_doc("Dimensioning Set")

    doc.set_name = (payload.get("set_name") or payload.get("name") or _("New Dimensioning Set")).strip()
    doc.description = payload.get("description") or ""
    doc.is_active = 1 if cint(payload.get("is_active", 1)) else 0
    doc.set("input_fields", [])
    if hasattr(doc, "derived_fields"):
        doc.set("derived_fields", [])
    doc.set("item_rules", [])

    for idx, field in enumerate(payload.get("fields") or payload.get("questions") or [], start=1):
        doc.append("input_fields", _question_row(field, idx))
    if hasattr(doc, "derived_fields"):
        for idx, field in enumerate(payload.get("derived_fields") or [], start=1):
            doc.append("derived_fields", _derived_field_row(field, idx))

    for group_idx, group in enumerate(_payload_rule_groups(payload), start=1):
        group_key = (group.get("rule_group") or f"GROUP-{group_idx:03d}").strip()
        for article_idx, article in enumerate(group.get("articles") or [], start=1):
            doc.append("item_rules", _article_rule_row(group, article, group_key, group_idx, article_idx))

    doc.save()
    return {"set": doc.serialize_config(), "name": doc.name}


@frappe.whitelist()
def delete_dimensioning_set(set_name=None):
    frappe.has_permission("Dimensioning Set", "delete", throw=True)
    set_name = (set_name or "").strip()
    if not set_name:
        frappe.throw(_("Please select a Dimensioning Set to delete."))
    if not frappe.db.exists("Dimensioning Set", set_name):
        return {"deleted": 0, "name": set_name}

    linked_sheets = frappe.get_all(
        "Pricing Sheet",
        filters={"dimensioning_set": set_name},
        pluck="name",
        limit_page_length=5,
    )
    if linked_sheets:
        frappe.throw(
            _("Dimensioning Set {0} is used by Pricing Sheet(s): {1}. Remove those links before deleting.").format(
                set_name,
                ", ".join(linked_sheets),
            )
        )

    frappe.delete_doc("Dimensioning Set", set_name)
    frappe.db.commit()
    return {"deleted": 1, "name": set_name}


@frappe.whitelist()
def preview_dimensioning_builder_payload(set_name=None, payload=None, input_values_json=None):
    frappe.has_permission("Dimensioning Set", "read", throw=True)
    if payload:
        doc = _doc_from_payload(_parse_payload(payload))
    elif set_name:
        doc = frappe.get_doc("Dimensioning Set", set_name)
    else:
        return {"set": None, "values": {}, "items": []}
    values = doc.coerce_input_values(input_values_json=input_values_json)
    return {"set": doc.serialize_config(), "values": values, "items": doc.preview_generated_items(values)}


@frappe.whitelist()
def preview_dimensioning_set(set_name, input_values_json=None):
    frappe.has_permission("Dimensioning Set", "read", throw=True)
    if not set_name:
        return {"items": [], "values": {}}
    doc = frappe.get_doc("Dimensioning Set", set_name)
    values = doc.coerce_input_values(input_values_json=input_values_json)
    return {
        "set": doc.serialize_config(),
        "values": values,
        "items": doc.preview_generated_items(values),
    }


def _parse_payload(payload):
    if isinstance(payload, str):
        return frappe.parse_json(payload) or {}
    return payload or {}


def _question_row(field, idx):
    return {
        "sequence": cint(field.get("sequence") or idx * 10),
        "field_key": field.get("field_key") or f"question_{idx}",
        "label": field.get("label") or field.get("field_key") or f"Question {idx}",
        "field_type": field.get("field_type") or "Data",
        "options": _options_text(field.get("options")),
        "default_value": field.get("default_value") or "",
        "is_required": 1 if cint(field.get("is_required")) else 0,
        "group": field.get("group") or "",
        "help_text": field.get("help_text") or "",
    }


def _derived_field_row(field, idx):
    return {
        "sequence": cint(field.get("sequence") or idx * 10),
        "field_key": field.get("field_key") or f"calculation_{idx}",
        "label": field.get("label") or field.get("field_key") or f"Calculation {idx}",
        "field_type": field.get("field_type") or "Data",
        "formula": field.get("formula") or "",
        "group": field.get("group") or "",
        "help_text": field.get("help_text") or "",
    }


def _article_rule_row(group, article, group_key, group_idx, article_idx):
    sequence = cint(article.get("sequence") or group.get("sequence") or group_idx * 100 + article_idx)
    return {
        "sequence": sequence,
        "is_active": 1 if cint(article.get("is_active", group.get("is_active", 1))) else 0,
        "rule_group": group_key,
        "condition_mode": group.get("condition_mode") or "always",
        "question_key": group.get("question_key") or "",
        "operator": group.get("operator") or "==",
        "compare_source": group.get("compare_source") or "manual",
        "manual_value": group.get("manual_value") or "",
        "compare_question_key": group.get("compare_question_key") or "",
        "condition_rules_json": article.get("condition_rules_json") or group.get("condition_rules_json") or "",
        "rule_label": article.get("rule_label") or article.get("item") or f"Article {article_idx}",
        "item_selection_mode": article.get("item_selection_mode") or "fixed",
        "item": article.get("item") or "",
        "item_filters_json": _item_filters_json(article),
        "quantity_mode": article.get("quantity_mode") or "fixed",
        "fixed_qty": flt(article.get("fixed_qty") or 1),
        "quantity_question_key": article.get("quantity_question_key") or "",
        "display_group": article.get("display_group") or "",
        "show_in_detail": 1 if cint(article.get("show_in_detail", 1)) else 0,
        "condition_formula": article.get("condition_formula") or group.get("condition_formula") or "",
        "condition_formula_builder_json": article.get("condition_formula_builder_json") or group.get("condition_formula_builder_json") or "",
        "qty_formula": article.get("qty_formula") or "",
        "qty_formula_builder_json": article.get("qty_formula_builder_json") or "",
    }


def _uses_advanced_formula(row):
    return bool(
        ((getattr(row, "condition_formula", None) or "").strip() and _condition_mode(row) != "formula")
        or ((getattr(row, "qty_formula", None) or "").strip() and _quantity_mode(row) != "formula")
    )


def _condition_mode(row):
    mode = (getattr(row, "condition_mode", None) or "always").strip()
    return mode if mode in {"always", "based", "formula"} else "based"


def _quantity_mode(row):
    mode = (getattr(row, "quantity_mode", None) or "fixed").strip()
    return mode if mode in {"fixed", "question", "formula"} else "fixed"


def _validate_rule_condition(row, field_types, allowed_formula_names):
    if _condition_mode(row) == "formula":
        if not (getattr(row, "condition_formula", None) or "").strip():
            raise ValueError("Condition formula is required.")
        validate_formula(row.condition_formula or "", allowed_formula_names)
        return
    validate_structured_condition(row, field_types)


def _validate_rule_quantity(row, field_types, allowed_formula_names):
    if _quantity_mode(row) == "formula":
        if not (getattr(row, "qty_formula", None) or "").strip():
            raise ValueError("Quantity formula is required.")
        validate_formula(row.qty_formula or "", allowed_formula_names)
        return
    validate_structured_quantity(row, field_types)


def _evaluate_rule_condition(row, formula_context, field_types):
    if _condition_mode(row) == "formula":
        return bool(evaluate_formula(row.condition_formula or "0", formula_context))
    return evaluate_structured_condition(row, formula_context, field_types)


def _evaluate_rule_quantity(row, formula_context):
    if _quantity_mode(row) == "formula":
        return flt(evaluate_formula(row.qty_formula or "0", formula_context) or 0)
    return evaluate_structured_quantity(row, formula_context)


def _payload_rule_groups(payload):
    groups = payload.get("rule_groups") or []
    if groups:
        return groups

    by_group = {}
    ordered = []
    for idx, rule in enumerate(payload.get("item_rules") or [], start=1):
        group_key = (rule.get("rule_group") or _condition_group_key(rule) or f"GROUP-{idx:03d}").strip()
        if group_key not in by_group:
            group = {
                "rule_group": group_key,
                "sequence": rule.get("sequence") or idx * 10,
                "is_active": rule.get("is_active", 1),
                "condition_mode": rule.get("condition_mode") or "always",
                "question_key": rule.get("question_key") or "",
                "operator": rule.get("operator") or "==",
                "compare_source": rule.get("compare_source") or "manual",
                "manual_value": rule.get("manual_value") or "",
                "compare_question_key": rule.get("compare_question_key") or "",
                "condition_rules_json": rule.get("condition_rules_json") or "",
                "articles": [],
            }
            by_group[group_key] = group
            ordered.append(group)
        by_group[group_key]["articles"].append(rule)
    return ordered


def _condition_group_key(rule):
    mode = rule.get("condition_mode") or "always"
    if mode == "always":
        return "always"
    return "|".join(
        [
            mode,
            rule.get("question_key") or "",
            rule.get("operator") or "==",
            rule.get("compare_source") or "manual",
            rule.get("manual_value") or "",
            rule.get("compare_question_key") or "",
        ]
    )


def _doc_from_payload(payload):
    doc = frappe.new_doc("Dimensioning Set")
    doc.set_name = payload.get("set_name") or payload.get("name") or "Preview"
    doc.description = payload.get("description") or ""
    doc.is_active = 1
    for idx, field in enumerate(payload.get("fields") or payload.get("questions") or [], start=1):
        doc.append("input_fields", _question_row(field, idx))
    if hasattr(doc, "derived_fields"):
        for idx, field in enumerate(payload.get("derived_fields") or [], start=1):
            doc.append("derived_fields", _derived_field_row(field, idx))
    for group_idx, group in enumerate(_payload_rule_groups(payload), start=1):
        group_key = (group.get("rule_group") or f"GROUP-{group_idx:03d}").strip()
        for article_idx, article in enumerate(group.get("articles") or [], start=1):
            doc.append("item_rules", _article_rule_row(group, article, group_key, group_idx, article_idx))
    return doc


def _options_text(options):
    if isinstance(options, list):
        return "\n".join(str(option).strip() for option in options if str(option).strip())
    return options or ""


def _item_selection_mode(row):
    mode = (getattr(row, "item_selection_mode", None) if not isinstance(row, dict) else row.get("item_selection_mode"))
    return mode if mode in {"fixed", "filtered"} else "fixed"


def _item_filters_json(row):
    if isinstance(row, dict):
        raw = row.get("item_filters_json")
        if raw:
            return raw if isinstance(raw, str) else frappe.as_json(raw)
        filters = row.get("item_filters") or row.get("filters") or []
        return frappe.as_json(filters) if filters else ""
    return getattr(row, "item_filters_json", None) or ""


def _parse_item_filters(row):
    raw = _item_filters_json(row)
    if not raw:
        return []
    parsed = frappe.parse_json(raw) if isinstance(raw, str) else raw
    if isinstance(parsed, dict):
        parsed = parsed.get("filters") or []
    if not isinstance(parsed, list):
        raise ValueError("Item filters must be a JSON list.")
    return [filter_row for filter_row in parsed if isinstance(filter_row, dict) and cint(filter_row.get("enabled", 1))]


def _validate_item_filters(row, allowed_formula_names):
    filters = _parse_item_filters(row)
    if not filters:
        raise ValueError("Filtered item selection requires at least one filter.")
    for idx, filter_row in enumerate(filters, start=1):
        source = (filter_row.get("source") or "item_field").strip()
        operator = (filter_row.get("operator") or "==").strip()
        if operator not in ITEM_FILTER_OPERATORS:
            raise ValueError(f"Item filter {idx}: unsupported operator '{operator}'.")
        if source == "item_field":
            field = _normalize_item_filter_field(filter_row.get("field"))
            if not field:
                raise ValueError(f"Item filter {idx}: unsupported Item field '{filter_row.get('field')}'.")
        elif source == "specification":
            if not (filter_row.get("attribute") or filter_row.get("field") or "").strip():
                raise ValueError(f"Item filter {idx}: specification attribute is required.")
        else:
            raise ValueError(f"Item filter {idx}: unsupported source '{source}'.")
        if (filter_row.get("value_source") or "manual") == "formula":
            validate_formula(filter_row.get("formula") or "", allowed_formula_names)


def _resolve_filtered_item(rule, formula_context):
    try:
        resolved_filters = _resolved_item_filters(rule, formula_context)
    except ValueError as exc:
        return "", str(exc)
    if not resolved_filters:
        return "", _("No item filters are configured.")

    item_filters = {"disabled": 0}
    post_filters = []
    spec_filters = []
    for filter_row in resolved_filters:
        source = filter_row["source"]
        if source == "item_field" and _can_filter_in_db(filter_row):
            item_filters[filter_row["field"]] = _db_filter_value(filter_row)
        elif source == "item_field":
            post_filters.append(filter_row)
        else:
            spec_filters.append(filter_row)

    candidates = frappe.get_all(
        "Item",
        filters=item_filters,
            fields=_item_candidate_fields(),
        order_by="name asc",
        limit_page_length=200,
    )
    if post_filters:
        candidates = [row for row in candidates if all(_matches_filter(row.get(f["field"]), f) for f in post_filters)]
    if spec_filters and candidates:
        candidates = _filter_items_by_specifications(candidates, spec_filters)

    if len(candidates) == 1:
        return candidates[0].name, ""
    label = getattr(rule, "rule_label", None) or getattr(rule, "item", None) or _("Filtered item")
    if not candidates:
        return "", _("No Item matched filters for {0}.").format(label)
    sample = ", ".join(row.name for row in candidates[:5])
    return "", _("Filters for {0} matched multiple Items: {1}.").format(label, sample)


def _resolved_item_filters(rule, formula_context):
    resolved = []
    for idx, filter_row in enumerate(_parse_item_filters(rule), start=1):
        source = (filter_row.get("source") or "item_field").strip()
        operator = (filter_row.get("operator") or "==").strip()
        if source not in {"item_field", "specification"}:
            raise ValueError(f"Item filter {idx}: unsupported source '{source}'.")
        if operator not in ITEM_FILTER_OPERATORS:
            raise ValueError(f"Item filter {idx}: unsupported operator '{operator}'.")
        value = _resolve_item_filter_value(filter_row, formula_context, idx)
        if value in (None, ""):
            continue
        field = _normalize_item_filter_field(filter_row.get("field"))
        if source == "item_field" and not field:
            raise ValueError(f"Item filter {idx}: unsupported Item field '{filter_row.get('field')}'.")
        attribute = (filter_row.get("attribute") or filter_row.get("field") or "").strip()
        if source == "specification" and not attribute:
            raise ValueError(f"Item filter {idx}: specification attribute is required.")
        resolved.append(
            {
                "source": source,
                "field": field,
                "attribute": attribute,
                "operator": operator,
                "value": value,
            }
        )
    return resolved


def _resolve_item_filter_value(filter_row, formula_context, idx):
    source = (filter_row.get("value_source") or "manual").strip()
    if source == "question":
        key = (filter_row.get("question_key") or filter_row.get("value") or "").strip()
        if key not in formula_context:
            raise ValueError(f"Item filter {idx}: unknown question '{key}'.")
        return formula_context.get(key)
    if source == "formula":
        formula = filter_row.get("formula") or ""
        return evaluate_formula(formula, formula_context)
    if source != "manual":
        raise ValueError(f"Item filter {idx}: unsupported value source '{source}'.")
    return filter_row.get("value")


def _normalize_item_filter_field(field):
    normalized = ITEM_FILTER_FIELDS.get((field or "").strip())
    if not normalized:
        return ""
    if normalized == "name":
        return normalized
    try:
        return normalized if frappe.get_meta("Item").has_field(normalized) else ""
    except Exception:
        return ""


def _item_candidate_fields():
    fields = ["name", "item_name", "description", "item_group", "brand", "stock_uom"]
    optional_fields = [
        "custom_material",
        "custom_customs_material",
        "custom_item_category",
        "custom_length_cm",
        "custom_width_cm",
        "custom_height_cm",
        "weight_per_unit",
        "variant_of",
    ]
    try:
        meta = frappe.get_meta("Item")
        fields.extend(field for field in optional_fields if meta.has_field(field))
    except Exception:
        pass
    return fields


def _can_filter_in_db(filter_row):
    return filter_row["operator"] in {"==", "!=", "contains", ">", ">=", "<", "<="}


def _db_filter_value(filter_row):
    operator = filter_row["operator"]
    value = filter_row["value"]
    if operator == "==":
        return value
    if operator == "contains":
        return ["like", f"%{value}%"]
    return [operator, value]


def _filter_items_by_specifications(candidates, spec_filters):
    names = [row.name for row in candidates]
    for filter_row in spec_filters:
        rows = frappe.get_all(
            "Item Specification Value",
            filters={
                "parenttype": "Item",
                "parentfield": "custom_specifications",
                "parent": ["in", names],
                "specification_attribute": filter_row["attribute"],
            },
            fields=["parent", "value", "text_value", "number_value", "display_value"],
            limit_page_length=0,
        )
        matched = {
            row.parent
            for row in rows
            if _matches_filter(_spec_filter_actual_value(row), filter_row)
        }
        candidates = [row for row in candidates if row.name in matched]
        names = [row.name for row in candidates]
        if not candidates:
            break
    return candidates


def _spec_filter_actual_value(row):
    return row.value or row.text_value or row.display_value or row.number_value or ""


def _matches_filter(actual, filter_row):
    operator = filter_row["operator"]
    expected = filter_row["value"]
    actual_number = _as_number(actual)
    expected_number = _as_number(expected)
    if actual_number is not None and expected_number is not None:
        left = actual_number
        right = expected_number
    else:
        left = str(actual or "").strip().lower()
        right = str(expected or "").strip().lower()
    if operator == "contains":
        return str(right) in str(left)
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    return False


def _as_number(value):
    try:
        if value in (None, ""):
            return None
        if not str(value).strip().replace(".", "", 1).replace("-", "", 1).isdigit():
            return None
        return flt(value)
    except Exception:
        return None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def dimensioning_item_query(doctype, txt, searchfield, start, page_len, filters):
    txt_like = f"%{txt}%"
    return frappe.db.sql(
        """
        SELECT
            i.name,
            i.item_name,
            i.item_group,
            i.stock_uom
        FROM `tabItem` i
        WHERE ifnull(i.disabled, 0) = 0
          AND ifnull(i.is_stock_item, 0) = 1
          AND (i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s OR i.description LIKE %(txt)s)
        ORDER BY
            CASE WHEN i.name LIKE %(starts_with)s THEN 0 ELSE 1 END,
            i.name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": txt_like,
            "starts_with": f"{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )
