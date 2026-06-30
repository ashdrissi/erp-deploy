from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import frappe
from frappe.utils import cint, flt

from orderlift.scripts.setup_dum_customs_policy import _read_rows


CUSTOMS_MATERIAL_VALUES = {
    "PLASTIQUE": 33,
    "CUIVRE": 60,
    "BETON": 5,
    "ACIER": 13,
    "COMPLET": 23,
    "ACIER (CARTE)": 50,
    "ACIER (GALET ET MOTEUR )": 25,
    "CAOUTCHOUC": 50,
}

DEFAULT_ARTICLE_SHEET = "Database"
DEFAULT_RATE_PERCENT = 20.25
DEFAULT_ITEM_MATERIAL_FIELD = "custom_customs_material"


@frappe.whitelist()
def run(
    policy_name: str | None = None,
    dry_run: int = 1,
    workbook_path: str | None = None,
    sheet_name: str = DEFAULT_ARTICLE_SHEET,
    replace_rules: int = 0,
    include_material_fallbacks: int = 1,
) -> dict:
    frappe.only_for(["System Manager", "Orderlift Admin"])
    dry_run = cint(dry_run)
    if workbook_path:
        return _run_article_workbook_sync(
            policy_name=policy_name,
            dry_run=dry_run,
            workbook_path=workbook_path,
            sheet_name=sheet_name,
            replace_rules=cint(replace_rules),
            include_material_fallbacks=cint(include_material_fallbacks),
        )

    policies = _target_policies(policy_name)
    summary = {
        "dry_run": dry_run,
        "policies": len(policies),
        "rules_updated": 0,
        "rules_created": 0,
        "warnings": [],
        "details": [],
    }
    for name in policies:
        policy = frappe.get_doc("Pricing Customs Policy", name)
        default_percent = _policy_default_percent(policy)
        existing = {_normalize_material(row.material): row for row in policy.customs_rules or [] if _normalize_material(row.material)}
        policy_detail = {"policy": name, "default_rate_percent": default_percent, "materials": []}
        for material, value_per_kg in CUSTOMS_MATERIAL_VALUES.items():
            key = _normalize_material(material)
            row = existing.get(key)
            if row:
                rate_percent = _effective_percent(row) or default_percent
                policy_detail["materials"].append(
                    {"material": material, "action": "update", "value_per_kg": value_per_kg, "rate_percent": rate_percent}
                )
                summary["rules_updated"] += 1
                if not dry_run:
                    row.material = material
                    row.value_per_kg = value_per_kg
                    row.rate_percent = rate_percent
                    row.rate_components = ""
                    row.rate_per_kg = 0
                    row.is_active = 1
                continue

            if not default_percent:
                summary["warnings"].append(
                    "Policy {0}: no existing Rate Percent found; created {1} with 0%.".format(name, material)
                )
            policy_detail["materials"].append(
                {"material": material, "action": "create", "value_per_kg": value_per_kg, "rate_percent": default_percent}
            )
            summary["rules_created"] += 1
            if not dry_run:
                policy.append(
                    "customs_rules",
                    {
                        "material": material,
                        "value_per_kg": value_per_kg,
                        "rate_percent": default_percent,
                        "rate_components": "",
                        "rate_per_kg": 0,
                        "sequence": 90,
                        "priority": 10,
                        "is_active": 1,
                        "notes": "Synced from db article 2- juin customs material table.",
                    },
                )
        summary["details"].append(policy_detail)
        if not dry_run:
            policy.save(ignore_permissions=True)
    if not dry_run:
        frappe.db.commit()
    return summary


@frappe.whitelist()
def sync_item_customs_materials(
    workbook_path: str,
    sheet_name: str = DEFAULT_ARTICLE_SHEET,
    dry_run: int = 1,
    target_field: str = DEFAULT_ITEM_MATERIAL_FIELD,
) -> dict:
    frappe.only_for(["System Manager", "Orderlift Admin"])
    """Update Item customs material values from an article workbook.

    The material workbook has no Item Code, so matching is intentionally conservative:
    1. item_name + item_group + custom_item_category
    2. item_name + custom_item_category when unique
    3. item_name when unique
    Ambiguous rows are reported and skipped.
    """
    dry_run = cint(dry_run)
    target_field = (target_field or DEFAULT_ITEM_MATERIAL_FIELD).strip()
    if target_field not in {"custom_customs_material", "custom_material"}:
        frappe.throw("Unsupported target field: {0}".format(target_field))
    if not frappe.db.has_column("Item", target_field):
        frappe.throw("Item field {0} was not found.".format(target_field))

    path = Path(workbook_path)
    if not path.exists():
        frappe.throw("Workbook not found: {0}".format(path))

    rows = _read_rows(path, sheet_name, header_row=1)
    item_rows = _get_item_rows_for_material_sync(target_field)
    indexes = _build_item_match_indexes(item_rows)
    summary = {
        "dry_run": dry_run,
        "workbook_path": str(path),
        "sheet_name": sheet_name,
        "target_field": target_field,
        "rows_read": len(rows),
        "rows_with_material": 0,
        "matched_rows": 0,
        "updates": 0,
        "unchanged": 0,
        "unmatched": 0,
        "ambiguous": 0,
        "conflicts": 0,
        "match_methods": Counter(),
        "material_counts": Counter(),
        "samples": [],
        "unmatched_samples": [],
        "ambiguous_samples": [],
        "conflict_samples": [],
    }
    planned = {}

    for row in rows:
        source = _source_material_row(row)
        if not source["material"]:
            continue
        summary["rows_with_material"] += 1
        summary["material_counts"][source["material"]] += 1
        candidates, method = _match_item_material_row(source, indexes)
        if not candidates:
            summary["unmatched"] += 1
            _append_limited(summary["unmatched_samples"], source)
            continue
        if len(candidates) > 1:
            summary["ambiguous"] += 1
            _append_limited(
                summary["ambiguous_samples"],
                {**source, "candidates": [candidate["name"] for candidate in candidates[:8]]},
            )
            continue

        item = candidates[0]
        item_code = item["name"]
        existing_plan = planned.get(item_code)
        if existing_plan and existing_plan["material"] != source["material"]:
            summary["conflicts"] += 1
            _append_limited(
                summary["conflict_samples"],
                {"item": item_code, "existing": existing_plan, "incoming": source},
            )
            continue
        planned[item_code] = {"material": source["material"], "source": source, "item": item, "method": method}

    for item_code, plan in sorted(planned.items()):
        item = plan["item"]
        current = _clean(item.get(target_field))
        material = plan["material"]
        summary["matched_rows"] += 1
        summary["match_methods"][plan["method"]] += 1
        if _clean(current).upper() == material:
            summary["unchanged"] += 1
            continue
        summary["updates"] += 1
        _append_limited(
            summary["samples"],
            {
                "item": item_code,
                "item_name": item.get("item_name") or "",
                "item_group": item.get("item_group") or "",
                "item_category": item.get("custom_item_category") or "",
                "from": current,
                "to": material,
                "method": plan["method"],
                "excel_row": plan["source"].get("excel_row"),
            },
        )
        if not dry_run:
            frappe.db.set_value("Item", item_code, target_field, material)

    summary["match_methods"] = dict(summary["match_methods"])
    summary["material_counts"] = dict(sorted(summary["material_counts"].items()))
    if not dry_run:
        frappe.db.commit()
    return summary


def _source_material_row(row: dict) -> dict:
    return {
        "excel_row": row.get("excel_row"),
        "item_name": _row_value(row, "ITEM NAME FR", "ITEM NAME", "ITEM NAME EN"),
        "item_group": _row_value(row, "ITEM CATEGORY"),
        "item_category": _row_value(row, "ITEM GROUP"),
        "material": _normalize_workbook_material(_row_value(row, "DOUANE MATERIAL", "CUSTOMS MATERIAL", "MATERIAU")),
    }


def _get_item_rows_for_material_sync(target_field: str) -> list[dict]:
    fields = ["name", "item_name", "item_group", "custom_item_category", "custom_material", "custom_customs_material"]
    if frappe.db.has_column("Item", "custom_secondary_item_name"):
        fields.append("custom_secondary_item_name")
    if frappe.db.has_column("Item", "disabled"):
        fields.append("disabled")
    if target_field not in fields:
        fields.append(target_field)
    return frappe.get_all("Item", fields=fields, limit_page_length=0)


def _build_item_match_indexes(items: list[dict]) -> dict:
    indexes = {
        "strict": defaultdict(list),
        "category": defaultdict(list),
        "name": defaultdict(list),
    }
    for item in items:
        names = {_key(item.get("item_name"))}
        secondary = _key(item.get("custom_secondary_item_name"))
        if secondary:
            names.add(secondary)
        for name_key in names:
            if not name_key:
                continue
            group_key = _key(item.get("item_group"))
            category_key = _key(item.get("custom_item_category"))
            indexes["strict"][(name_key, group_key, category_key)].append(item)
            indexes["category"][(name_key, category_key)].append(item)
            indexes["name"][name_key].append(item)
    return indexes


def _match_item_material_row(source: dict, indexes: dict) -> tuple[list[dict], str]:
    name_key = _key(source.get("item_name"))
    group_key = _key(source.get("item_group"))
    category_key = _key(source.get("item_category"))
    if not name_key:
        return [], "missing_name"

    strict = indexes["strict"].get((name_key, group_key, category_key)) or []
    if len(strict) == 1:
        return strict, "name_group_category"
    if len(strict) > 1:
        return strict, "ambiguous_name_group_category"

    by_category = indexes["category"].get((name_key, category_key)) or []
    if len(by_category) == 1:
        return by_category, "name_category"
    if len(by_category) > 1:
        return by_category, "ambiguous_name_category"

    by_name = indexes["name"].get(name_key) or []
    if len(by_name) == 1:
        return by_name, "name_only"
    return by_name, "ambiguous_name_only" if by_name else "unmatched"


def _append_limited(target: list, value: dict, limit: int = 25) -> None:
    if len(target) < limit:
        target.append(value)


def _run_article_workbook_sync(
    policy_name: str | None,
    dry_run: int,
    workbook_path: str,
    sheet_name: str,
    replace_rules: int,
    include_material_fallbacks: int,
) -> dict:
    path = Path(workbook_path)
    if not path.exists():
        frappe.throw("Workbook not found: {0}".format(path))

    rows = _read_rows(path, sheet_name, header_row=1)
    policy_rows, warnings = _build_article_policy_rows(rows, include_material_fallbacks=include_material_fallbacks)
    policies = _target_policies(policy_name)
    summary = {
        "dry_run": dry_run,
        "workbook_path": str(path),
        "sheet_name": sheet_name,
        "rows_read": len(rows),
        "policies": len(policies),
        "rules_from_workbook": sum(1 for row in policy_rows if row.get("source") == "workbook"),
        "material_fallback_rules": sum(1 for row in policy_rows if row.get("source") == "material_fallback"),
        "rules_replaced": 0,
        "rules_updated": 0,
        "rules_created": 0,
        "unknown_materials": sorted({warning["material"] for warning in warnings if warning.get("type") == "unknown_material"}),
        "warnings": warnings,
        "samples": policy_rows[:20],
        "details": [],
    }

    for name in policies:
        policy = frappe.get_doc("Pricing Customs Policy", name)
        detail = {
            "policy": name,
            "existing_rules": len(policy.customs_rules or []),
            "replace_rules": replace_rules,
            "rules_total": len(policy_rows),
        }
        if replace_rules:
            summary["rules_replaced"] += len(policy.customs_rules or [])
            if not dry_run:
                policy.set("customs_rules", [])
                for row in policy_rows:
                    policy.append("customs_rules", _child_row(row))
        else:
            updated, created = _upsert_article_policy_rows(policy, policy_rows, dry_run=dry_run)
            summary["rules_updated"] += updated
            summary["rules_created"] += created
            detail.update({"rules_updated": updated, "rules_created": created})
        summary["details"].append(detail)
        if not dry_run:
            policy.save(ignore_permissions=True)
    if not dry_run:
        frappe.db.commit()
    return summary


def _build_article_policy_rows(rows: list[dict], include_material_fallbacks: int = 1) -> tuple[list[dict], list[dict]]:
    material_values = {_normalize_material(material): value for material, value in CUSTOMS_MATERIAL_VALUES.items()}
    fallback_materials = {_normalize_material(material): material for material in CUSTOMS_MATERIAL_VALUES}
    pair_counts = Counter()
    missing_counts = Counter()
    skipped_unknown = Counter()
    examples = {}
    known_materials = {}
    warnings = []

    for row in rows:
        tariff_number = _normalize_tariff_number(_row_value(row, "HS CODE (10 DIGIT)", "HS CODE", "CODE HS (10 DIG)"))
        material = _normalize_workbook_material(_row_value(row, "DOUANE MATERIAL", "MATERIAU"))
        if not tariff_number or not material:
            missing_counts[(bool(tariff_number), bool(material))] += 1
            continue

        material_key = _normalize_material(material)
        value_per_kg = material_values.get(material_key)
        if value_per_kg is None:
            skipped_unknown[(material, tariff_number)] += 1
            continue

        key = (tariff_number, material)
        pair_counts[key] += 1
        examples.setdefault(key, row.get("excel_row"))
        known_materials.setdefault(material_key, set()).add(material)

    for (has_tariff, has_material), count in sorted(missing_counts.items()):
        warnings.append(
            {
                "type": "missing_required_value",
                "has_tariff_number": has_tariff,
                "has_material": has_material,
                "rows": count,
                "message": "Article rows skipped because HS code or Douane material is blank.",
            }
        )
    for (material, tariff_number), count in sorted(skipped_unknown.items()):
        warnings.append(
            {
                "type": "unknown_material",
                "material": material,
                "tariff_number": tariff_number,
                "rows": count,
                "message": "Article HS/material pair skipped because no customs value was provided for the material.",
            }
        )

    policy_rows = []
    for index, ((tariff_number, material), count) in enumerate(sorted(pair_counts.items()), start=1):
        value_per_kg = material_values[_normalize_material(material)]
        policy_rows.append(
            {
                "tariff_number": tariff_number,
                "material": material,
                "value_per_kg": value_per_kg,
                "rate_percent": DEFAULT_RATE_PERCENT,
                "rate_components": "",
                "rate_per_kg": 0,
                "sequence": index * 10,
                "priority": 10,
                "is_active": 1,
                "notes": "Synced from db article 2- juin article workbook. Rows matched: {0}. First row: {1}.".format(
                    count, examples.get((tariff_number, material)) or ""
                ),
                "source": "workbook",
            }
        )

    if include_material_fallbacks:
        base_sequence = len(policy_rows) * 10
        fallback_rows = []
        for material_key in sorted(fallback_materials):
            materials = set(known_materials.get(material_key) or [])
            materials.add(fallback_materials[material_key])
            for material in sorted(materials):
                fallback_rows.append((material_key, material))
        for index, (material_key, material) in enumerate(fallback_rows, start=1):
            policy_rows.append(
                {
                    "tariff_number": "",
                    "material": material,
                    "value_per_kg": material_values[material_key],
                    "rate_percent": DEFAULT_RATE_PERCENT,
                    "rate_components": "",
                    "rate_per_kg": 0,
                    "sequence": base_sequence + index * 10,
                    "priority": 90,
                    "is_active": 1,
                    "notes": "Material fallback synced from provided customs material value table.",
                    "source": "material_fallback",
                }
            )

    return policy_rows, warnings


def _upsert_article_policy_rows(policy, policy_rows: list[dict], dry_run: int) -> tuple[int, int]:
    existing = {
        (_normalize_tariff_number(row.tariff_number), _normalize_workbook_material(row.material)): row
        for row in policy.customs_rules or []
    }
    updated = 0
    created = 0
    for row in policy_rows:
        key = (_normalize_tariff_number(row.get("tariff_number")), _normalize_workbook_material(row.get("material")))
        child = existing.get(key)
        if child:
            updated += 1
            if not dry_run:
                _apply_child_row(child, row)
            continue
        created += 1
        if not dry_run:
            policy.append("customs_rules", _child_row(row))
    return updated, created


def _target_policies(policy_name: str | None) -> list[str]:
    policy_name = (policy_name or "").strip()
    if policy_name:
        if not frappe.db.exists("Pricing Customs Policy", policy_name):
            frappe.throw("Pricing Customs Policy {0} was not found.".format(policy_name))
        return [policy_name]
    return frappe.get_all("Pricing Customs Policy", filters={"is_active": 1}, pluck="name", limit_page_length=0)


def _child_row(row: dict) -> dict:
    return {
        "tariff_number": row.get("tariff_number") or "",
        "material": row.get("material") or "",
        "value_per_kg": row.get("value_per_kg") or 0,
        "rate_percent": row.get("rate_percent") or 0,
        "rate_components": row.get("rate_components") or "",
        "rate_per_kg": row.get("rate_per_kg") or 0,
        "sequence": row.get("sequence") or 90,
        "priority": row.get("priority") or 10,
        "is_active": row.get("is_active", 1),
        "notes": row.get("notes") or "",
    }


def _apply_child_row(child, row: dict) -> None:
    for field, value in _child_row(row).items():
        setattr(child, field, value)


def _row_value(row: dict, *headers: str) -> str:
    for header in headers:
        value = _clean(row.get(_clean_header(header)))
        if value:
            return value
    return ""


def _normalize_tariff_number(value: str | None) -> str:
    text = _clean(value)
    if not text or text == "-":
        return ""
    return "".join(ch for ch in text.upper() if ch.isalnum())


def _normalize_workbook_material(value: str | None) -> str:
    text = _clean(value).upper()
    if not text:
        return ""
    aliases = {
        "BÉTON": "BETON",
        "CONCRETE": "BETON",
        "COPPER": "CUIVRE",
        "PLASTIC": "PLASTIQUE",
        "PLASTIQUE / PVC": "PLASTIQUE",
        "PVC": "PLASTIQUE",
        "STEEL": "ACIER",
    }
    return aliases.get(text, text)


def _policy_default_percent(policy) -> float:
    values = [_effective_percent(row) for row in (policy.customs_rules or []) if cint(row.is_active)]
    values = [flt(value) for value in values if flt(value)]
    if not values:
        return 0.0
    counts = Counter(values)
    return counts.most_common(1)[0][0]


def _effective_percent(row) -> float:
    if flt(getattr(row, "rate_percent", 0) or 0):
        return flt(row.rate_percent)
    return sum(_parse_percent_components(getattr(row, "rate_components", "") or ""))


def _parse_percent_components(value: str) -> list[float]:
    return [flt(match) for match in re.findall(r"\d+(?:\.\d+)?", str(value or ""))]


def _normalize_material(value: str | None) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip().upper())
    text = re.sub(r"\s+\)", ")", text)
    aliases = {
        "BÉTON": "BETON",
        "CONCRETE": "BETON",
        "COPPER": "CUIVRE",
        "PLASTIC": "PLASTIQUE",
        "PLASTIQUE / PVC": "PLASTIQUE",
        "PVC": "PLASTIQUE",
        "STEEL": "ACIER",
    }
    return aliases.get(text, text)


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    return "" if text == "-" else text


def _key(value: str | None) -> str:
    return _clean(value).casefold()


def _clean_header(value: str | None) -> str:
    return _clean(value).upper()
