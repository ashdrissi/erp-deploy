from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import flt


DEFAULT_IMPORT_FILE = Path("/tmp/logistique_export.csv")

PACKAGING_TYPE_ALIASES = {
    "box": "Box",
    "palette": "Palette",
    "roleaux": "Rouleau",
    "rouleau": "Rouleau",
    "rouleux": "Rouleau",
    "unit": "Unit",
}


def run(import_file: str | None = None, dry_run: int | str = 1, update_item_hs: int | str = 1):
    import_path = Path(import_file or DEFAULT_IMPORT_FILE)
    if not import_path.exists():
        frappe.throw(_("Packaging import file not found: {0}").format(import_path))

    dry_run = _truthy(dry_run)
    update_item_hs = _truthy(update_item_hs)

    rows = _read_rows(import_path)
    uom_map = _get_uom_map()
    grouped_rows = _group_rows(rows)

    summary = {
        "import_file": str(import_path),
        "dry_run": dry_run,
        "update_item_hs": update_item_hs,
        "rows_read": len(rows),
        "items_seen": len(grouped_rows),
        "items_updated": 0,
        "items_missing": [],
        "new_uoms": [],
        "new_customs_tariff_numbers": [],
        "profiles_written": 0,
        "rows_deduped": 0,
        "warnings": [],
    }

    for item_code, item_rows in grouped_rows.items():
        if not frappe.db.exists("Item", item_code):
            summary["items_missing"].append(item_code)
            continue

        item_doc = frappe.get_doc("Item", item_code)
        desired_profiles, item_hs, item_stats = _build_profiles_for_item(item_rows, uom_map, summary, dry_run=dry_run)
        summary["rows_deduped"] += item_stats["rows_deduped"]

        if update_item_hs and item_hs:
            item_hs_link = _ensure_customs_tariff_number(item_hs, summary, dry_run=dry_run)
            if (item_doc.customs_tariff_number or "") != item_hs_link:
                item_doc.customs_tariff_number = item_hs_link

        item_doc.set("custom_packaging_profiles", [])
        for index, profile in enumerate(desired_profiles):
            item_doc.append(
                "custom_packaging_profiles",
                {
                    **profile,
                    "is_default": 1 if index == 0 else 0,
                    "is_active": 1,
                },
            )

        summary["profiles_written"] += len(desired_profiles)
        summary["items_updated"] += 1

        if not dry_run:
            item_doc.save(ignore_permissions=True)

    if not dry_run:
        frappe.db.commit()

    summary["items_missing"] = sorted(summary["items_missing"])
    summary["new_uoms"] = sorted(set(summary["new_uoms"]))
    summary["new_customs_tariff_numbers"] = sorted(set(summary["new_customs_tariff_numbers"]))
    return summary


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _get_uom_map() -> dict[str, str]:
    rows = frappe.get_all("UOM", fields=["name"], limit_page_length=0)
    return {(row.name or "").strip().lower(): row.name for row in rows}


def _group_rows(rows: list[dict[str, str]]) -> OrderedDict[str, list[dict[str, str]]]:
    grouped = OrderedDict()
    for row in rows:
        item_code = (row.get("Ref") or "").strip()
        if not item_code:
            continue
        grouped.setdefault(item_code, []).append(row)
    return grouped


def _build_profiles_for_item(item_rows, uom_map, summary, dry_run=False):
    profiles = []
    seen = set()
    row_stats = {"rows_deduped": 0}
    item_hs = ""

    for row in item_rows:
        item_hs = item_hs or _normalize_hs(row.get("Code SH"))
        profile = _build_profile(row, uom_map, summary, dry_run=dry_run)
        key = _profile_key(profile)
        if key in seen:
            row_stats["rows_deduped"] += 1
            continue
        seen.add(key)
        profiles.append(profile)

    return profiles, item_hs, row_stats


def _build_profile(row, uom_map, summary, dry_run=False):
    uom = _ensure_uom((row.get("Unité") or "").strip(), uom_map, summary, dry_run=dry_run)
    packaging_type = _normalize_packaging_type(row.get("Packaging Type"))
    units_per_package = flt(row.get("Nb Unités/Package") or 0) or 1.0
    weight_kg = flt(row.get("Poids") or 0)
    length_cm = flt(row.get("L") or 0)
    width_cm = flt(row.get("l") or 0)
    height_cm = flt(row.get("H") or 0)
    volume_m3 = 0.0
    if length_cm > 0 and width_cm > 0 and height_cm > 0:
        volume_m3 = (length_cm * width_cm * height_cm) / 1000000.0

    return {
        "uom": uom,
        "packaging_type": packaging_type,
        "units_per_package": units_per_package,
        "weight_kg": weight_kg,
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "volume_m3": volume_m3,
        "notes": "Imported from logistique_export.csv",
    }


def _normalize_packaging_type(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    normalized = " ".join(text.split())
    return PACKAGING_TYPE_ALIASES.get(normalized.lower(), normalized)


def _normalize_hs(value: str | None) -> str:
    return "".join(ch for ch in (value or "").strip() if ch.isalnum())


def _ensure_uom(raw_uom: str, uom_map: dict[str, str], summary: dict, dry_run: bool = False) -> str:
    if not raw_uom:
        frappe.throw(_("Packaging profile is missing UOM."))

    existing = uom_map.get(raw_uom.lower())
    if existing:
        return existing

    summary["new_uoms"].append(raw_uom)
    if dry_run:
        return raw_uom

    doc = frappe.get_doc({"doctype": "UOM", "uom_name": raw_uom, "enabled": 1})
    doc.insert(ignore_permissions=True)
    uom_map[raw_uom.lower()] = doc.name
    return doc.name


def _ensure_customs_tariff_number(code: str, summary: dict, dry_run: bool = False) -> str:
    if not code:
        return ""

    if frappe.db.exists("Customs Tariff Number", code):
        return code

    existing = frappe.db.get_value("Customs Tariff Number", {"tariff_number": code}, "name")
    if existing:
        return existing

    summary["new_customs_tariff_numbers"].append(code)
    if dry_run:
        return code

    doc = frappe.get_doc(
        {
            "doctype": "Customs Tariff Number",
            "name": code,
            "tariff_number": code,
            "description": code,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _profile_key(profile: dict) -> tuple:
    return (
        (profile.get("uom") or "").strip().upper(),
        (profile.get("packaging_type") or "").strip().upper(),
        flt(profile.get("units_per_package") or 0),
        flt(profile.get("weight_kg") or 0),
        flt(profile.get("length_cm") or 0),
        flt(profile.get("width_cm") or 0),
        flt(profile.get("height_cm") or 0),
    )


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no"}
