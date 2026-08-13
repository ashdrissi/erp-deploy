from __future__ import annotations

import json

import frappe
from frappe.utils import cint


TARGET_SETS = ("DSET-02731", "DSET-06189")

GROUP_TITLES = {
    "GROUP-1": "Standard equipment and cabin",
    "GROUP-2": "Gearbox traction components",
    "GROUP-5": "Automatic landing doors",
    "GROUP-6": "Door operator",
    "GROUP-7": "Electrical cables",
    "GROUP-8": "Landing controls",
    "GROUP-9": "Swing door operator",
    "GROUP-10": "Swing landing door components",
}

ARTICLE_LABELS = {
    "GROUP-5": "Selected automatic landing door",
    "GROUP-6": "Selected door operator",
    "GROUP-9": "Selected swing door operator",
    "GROUP-10": "Selected swing landing door",
}


def run(dry_run: int = 1) -> dict:
    dry_run = cint(dry_run)
    summary = {"dry_run": bool(dry_run), "sets": [], "updated_rows": 0}
    for set_name in TARGET_SETS:
        if not frappe.db.exists("Dimensioning Set", set_name):
            summary["sets"].append({"name": set_name, "status": "missing"})
            continue
        doc = frappe.get_doc("Dimensioning Set", set_name)
        changes = []
        for row in doc.item_rules or []:
            group = (row.rule_group or "").strip()
            row_changes = []
            title = GROUP_TITLES.get(group)
            if title and (row.rule_group_title or "").strip() != title:
                row.rule_group_title = title
                row_changes.append("rule_group_title")
            if group in ARTICLE_LABELS and (row.item_selection_mode or "fixed") == "filtered":
                label = _filtered_article_label(group, filters=_parse_filters(row.item_filters_json))
                if row.rule_label != label:
                    row.rule_label = label
                    row_changes.append("rule_label")
            filters = _parse_filters(row.item_filters_json)
            filters_changed = False
            if group in {"GROUP-5", "GROUP-10"} and (row.item_selection_mode or "fixed") == "filtered":
                filters_changed = _upsert_door_type_filter(filters) or filters_changed
            if group in {"GROUP-6", "GROUP-9"} and (row.item_selection_mode or "fixed") == "filtered":
                filters_changed = _replace_brand_filter(filters) or filters_changed
            if filters_changed:
                row.item_filters_json = json.dumps(filters, ensure_ascii=False, separators=(",", ":"))
                row_changes.append("item_filters_json")
            if row_changes:
                changes.append({"row": row.name, "group": group, "fields": row_changes})

        if set_name == "DSET-02731":
            values = frappe.parse_json(doc.preview_test_values_json or "{}") or {}
            if not values:
                values = {field.field_key: field.default_value for field in doc.input_fields or []}
            if str(values.get("g") or "").strip() == "0.9":
                values["g"] = "1.0"
                doc.preview_test_values_json = frappe.as_json(values)
                changes.append({"row": doc.name, "group": "preview", "fields": ["preview_test_values_json"]})

        if changes and not dry_run:
            doc.save(ignore_permissions=True)
        summary["sets"].append(
            {
                "name": set_name,
                "set_name": doc.set_name,
                "status": "would_update" if changes and dry_run else "updated" if changes else "unchanged",
                "changes": changes,
            }
        )
        summary["updated_rows"] += len(changes)
    if not dry_run:
        frappe.db.commit()
    return summary


def _parse_filters(raw) -> list[dict]:
    try:
        parsed = frappe.parse_json(raw or "[]") or []
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _upsert_door_type_filter(filters: list[dict]) -> bool:
    wanted = {
        "source": "specification",
        "field": "",
        "attribute": "Type",
        "operator": "contains",
        "value_source": "question",
        "value": "",
        "question_key": "s",
        "formula": "",
        "enabled": 1,
    }
    for index, current in enumerate(filters):
        if (current.get("source") or "") == "specification" and (current.get("attribute") or "").strip().lower() == "type":
            if current == wanted:
                return False
            filters[index] = wanted
            return True
    filters.append(wanted)
    return True


def _filtered_article_label(group: str, filters: list[dict]) -> str:
    if group == "GROUP-10" and any(
        "PORTE BUS" in str(row.get("value") or "").upper()
        for row in filters
    ):
        return "Selected folding bus door"
    return ARTICLE_LABELS[group]


def _replace_brand_filter(filters: list[dict]) -> bool:
    changed = False
    for current in filters:
        if (current.get("source") or "item_field") != "item_field" or (current.get("field") or "") != "brand":
            continue
        current.update(
            {
                "field": "item_name",
                "operator": "contains",
                "value_source": "question",
                "value": "",
                "question_key": "m_4",
                "formula": "",
                "enabled": 1,
            }
        )
        changed = True
    return changed
