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
        field_types = self._field_types()
        allowed_formula_names = set(field_types)
        allowed_formula_names.update(
            f"row_{cint(row.sequence or 0)}" for row in self.item_rules or [] if cint(row.sequence or 0)
        )
        for row in self.item_rules or []:
            if cint(row.is_active) != 1:
                continue
            if not row.item:
                frappe.throw(_("Row {0}: Item is required.").format(row.idx))
            try:
                if _uses_advanced_formula(row):
                    validate_formula(row.condition_formula or "", allowed_formula_names)
                    validate_formula(row.qty_formula or "", allowed_formula_names)
                    if not (row.qty_formula or "").strip():
                        validate_structured_quantity(row, field_types)
                else:
                    validate_structured_condition(row, field_types)
                    validate_structured_quantity(row, field_types)
            except ValueError as exc:
                frappe.throw(_("Row {0}: {1}").format(row.idx, str(exc)))

    def serialize_config(self):
        return {
            "name": self.name,
            "set_name": self.set_name or self.name,
            "description": self.description or "",
            "is_active": 1 if cint(self.is_active) else 0,
            "fields": self.serialize_questions(),
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
                    "articles": [],
                }
                by_group[group_key] = group
                groups.append(group)
            by_group[group_key]["articles"].append(
                {
                    "sequence": cint(row.sequence or 0),
                    "is_active": 1 if cint(row.is_active) else 0,
                    "rule_label": row.rule_label or row.item,
                    "item": row.item,
                    "display_group": row.display_group or "",
                    "condition_formula": row.condition_formula or "",
                    "qty_formula": row.qty_formula or "",
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
                        qty = flt(evaluate_structured_quantity(rule, values) or 0)
                else:
                    if not evaluate_structured_condition(rule, values, field_types):
                        qty = 0
                    else:
                        qty = flt(evaluate_structured_quantity(rule, values) or 0)
                if row_key:
                    formula_context[row_key] = qty
                if qty <= 0:
                    continue
            except Exception as exc:
                if row_key:
                    formula_context[row_key] = 0
                frappe.throw(_("Dimensioning rule {0}: {1}").format(rule.rule_label or rule.idx, str(exc)))

            preview.append(
                {
                    "rule_label": rule.rule_label or rule.item,
                    "item": rule.item,
                    "qty": qty,
                    "rule_group": rule.rule_group or "",
                    "display_group": (rule.display_group or self.set_name or self.name or "").strip(),
                    "show_in_detail": 1 if cint(rule.show_in_detail) else 0,
                }
            )
        self._add_item_preview_details(preview)
        return preview

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
                row.update({"item_name": "", "item_group": "", "stock_uom": "", "description": ""})
                continue
            row.update(
                {
                    "item_name": details.item_name or "",
                    "item_group": details.item_group or "",
                    "stock_uom": details.stock_uom or "",
                    "description": details.description or "",
                }
            )

    def _field_types(self):
        return {
            row.field_key: (row.field_type or "Data").strip().title()
            for row in (self.input_fields or [])
            if row.field_key
        }


@frappe.whitelist()
def get_dimensioning_set_payload(set_name):
    if not set_name:
        return {"set": None}
    doc = frappe.get_doc("Dimensioning Set", set_name)
    return {"set": doc.serialize_config()}


@frappe.whitelist()
def get_dimensioning_builder_payload(set_name=None):
    if not set_name:
        return {"set": None}
    doc = frappe.get_doc("Dimensioning Set", set_name)
    return {"set": doc.serialize_config()}


@frappe.whitelist()
def get_dimensioning_manager_data():
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
    doc.set("item_rules", [])

    for idx, field in enumerate(payload.get("fields") or payload.get("questions") or [], start=1):
        doc.append("input_fields", _question_row(field, idx))

    for group_idx, group in enumerate(_payload_rule_groups(payload), start=1):
        group_key = (group.get("rule_group") or f"GROUP-{group_idx:03d}").strip()
        for article_idx, article in enumerate(group.get("articles") or [], start=1):
            doc.append("item_rules", _article_rule_row(group, article, group_key, group_idx, article_idx))

    doc.save()
    return {"set": doc.serialize_config(), "name": doc.name}


@frappe.whitelist()
def delete_dimensioning_set(set_name=None):
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
        "rule_label": article.get("rule_label") or article.get("item") or f"Article {article_idx}",
        "item": article.get("item") or "",
        "quantity_mode": article.get("quantity_mode") or "fixed",
        "fixed_qty": flt(article.get("fixed_qty") or 1),
        "quantity_question_key": article.get("quantity_question_key") or "",
        "display_group": article.get("display_group") or "",
        "show_in_detail": 1 if cint(article.get("show_in_detail", 1)) else 0,
        "condition_formula": article.get("condition_formula") or group.get("condition_formula") or "",
        "qty_formula": article.get("qty_formula") or "",
    }


def _uses_advanced_formula(row):
    return bool((getattr(row, "condition_formula", None) or "").strip() or (getattr(row, "qty_formula", None) or "").strip())


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
    for group_idx, group in enumerate(_payload_rule_groups(payload), start=1):
        group_key = (group.get("rule_group") or f"GROUP-{group_idx:03d}").strip()
        for article_idx, article in enumerate(group.get("articles") or [], start=1):
            doc.append("item_rules", _article_rule_row(group, article, group_key, group_idx, article_idx))
    return doc


def _options_text(options):
    if isinstance(options, list):
        return "\n".join(str(option).strip() for option in options if str(option).strip())
    return options or ""
