from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import frappe
from frappe import _
from frappe.utils import cint


DEFAULT_WORKBOOK = Path("/tmp/Resume_HS_Codes_DUM.xlsx")
DEFAULT_SHEET = "Résumé HS Codes"
DEFAULT_POLICY_NAME = "DUM Morocco Customs 2026"
DEFAULT_RATE_PERCENT = 20.25
DEFAULT_ARTICLE_SHEET = "Database"
MISSING_VALUE_ZERO_ACTIVE = "zero_active"
MISSING_VALUE_INACTIVE = "inactive"
MISSING_VALUE_SKIP = "skip"

XML_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@frappe.whitelist()
def run(
    workbook_path: str | None = None,
    sheet_name: str = DEFAULT_SHEET,
    policy_name: str = DEFAULT_POLICY_NAME,
    dry_run: int | str = 1,
    set_default: int | str = 1,
    missing_value_mode: str = MISSING_VALUE_ZERO_ACTIVE,
    article_workbook_path: str | None = None,
    article_sheet_name: str = DEFAULT_ARTICLE_SHEET,
    include_article_placeholders: int | str = 0,
):
    frappe.only_for(["System Manager", "Orderlift Admin"])
    path = Path(workbook_path or DEFAULT_WORKBOOK)
    if not path.exists():
        frappe.throw(_("Workbook not found: {0}").format(path))

    dry_run = _truthy(dry_run)
    set_default = _truthy(set_default)
    include_article_placeholders = _truthy(include_article_placeholders)
    rows = _read_rows(path, sheet_name, header_row=3)
    policy_rows, warnings = _build_policy_rows(rows, missing_value_mode=missing_value_mode)

    article_rows = []
    if include_article_placeholders:
        if not article_workbook_path:
            frappe.throw(_("Article workbook path is required when include_article_placeholders is enabled."))
        article_path = Path(article_workbook_path)
        if not article_path.exists():
            frappe.throw(_("Article workbook not found: {0}").format(article_path))
        article_rows = _read_rows(article_path, article_sheet_name, header_row=1)
        placeholders, placeholder_warnings = _build_article_placeholders(article_rows, policy_rows)
        policy_rows.extend(placeholders)
        warnings.extend(placeholder_warnings)
    active_rows = [row for row in policy_rows if row["is_active"]]

    summary = {
        "workbook_path": str(path),
        "sheet_name": sheet_name,
        "policy_name": policy_name,
        "dry_run": dry_run,
        "set_default": set_default,
        "rows_read": len(rows),
        "article_rows_read": len(article_rows),
        "rules_total": len(policy_rows),
        "rules_active": len(active_rows),
        "rules_inactive": len(policy_rows) - len(active_rows),
        "article_placeholders": sum(1 for row in policy_rows if row.get("is_article_placeholder")),
        "new_materials": [],
        "new_customs_tariff_numbers": [],
        "warnings": warnings,
        "samples": policy_rows[:20],
    }

    for row in policy_rows:
        _ensure_item_material(row["material"], summary, dry_run=dry_run)
        _ensure_customs_tariff_number(row["tariff_number"], summary, dry_run=dry_run)

    if not dry_run:
        _upsert_policy(policy_name, policy_rows, set_default=set_default)
        frappe.db.commit()

    summary["new_materials"] = sorted(set(summary["new_materials"]))
    summary["new_customs_tariff_numbers"] = sorted(set(summary["new_customs_tariff_numbers"]))
    return summary


def _build_policy_rows(rows: list[dict], missing_value_mode: str = MISSING_VALUE_ZERO_ACTIVE) -> tuple[list[dict], list[dict]]:
    policy_rows = []
    warnings = []
    seen = Counter()
    missing_value_mode = (missing_value_mode or MISSING_VALUE_ZERO_ACTIVE).strip().lower()
    if missing_value_mode not in {MISSING_VALUE_ZERO_ACTIVE, MISSING_VALUE_INACTIVE, MISSING_VALUE_SKIP}:
        frappe.throw(_("Unsupported missing value mode: {0}").format(missing_value_mode))

    for row in rows:
        tariff_number = _normalize_tariff_number(row.get("CODE HS (10 DIG)"))
        material = _normalize_material_name(row.get("MATERIAU"))
        if not tariff_number or not material:
            continue

        value_per_kg = _decimal(row.get("VAL. DOUANE DH/KG (SOURCE DUM)"))
        value_source = "source_dum"
        if value_per_kg is None:
            value_per_kg = _decimal(row.get("VALEUR THORIQUE DH/KG"))
            value_source = "theoretical"

        is_active = value_per_kg is not None and value_per_kg > 0
        if value_per_kg is None or value_per_kg <= 0:
            if missing_value_mode == MISSING_VALUE_SKIP:
                warnings.append(
                    {
                        "excel_row": row.get("excel_row"),
                        "tariff_number": tariff_number,
                        "material": material,
                        "message": "Missing customs value; row skipped.",
                    }
                )
                continue
            is_active = missing_value_mode == MISSING_VALUE_ZERO_ACTIVE
            value_per_kg = Decimal("0")
            warnings.append(
                {
                    "excel_row": row.get("excel_row"),
                    "tariff_number": tariff_number,
                    "material": material,
                    "message": (
                        "Missing customs value; active zero-value rule will be created."
                        if is_active
                        else "Missing customs value; rule will be inactive."
                    ),
                }
            )

        key = (tariff_number, material)
        seen[key] += 1
        sequence = len(policy_rows) * 10 + 10
        note_parts = [
            "Source: Resume_HS_Codes_DUM.xlsx",
            f"Value source: {value_source}",
        ]
        if row.get("PRÉSENT DAN DUM"):
            note_parts.append(f"Present in DUM: {row.get('PRÉSENT DAN DUM')}")
        if row.get("REVISE"):
            note_parts.append(f"Revised: {row.get('REVISE')}")
        if seen[key] > 1:
            warnings.append(
                {
                    "excel_row": row.get("excel_row"),
                    "tariff_number": tariff_number,
                    "material": material,
                    "message": "Duplicate tariff/material in DUM workbook; later row kept as separate lower-priority rule.",
                }
            )

        policy_rows.append(
            {
                "tariff_number": tariff_number,
                "material": material,
                "value_per_kg": float(value_per_kg),
                "rate_components": "",
                "rate_per_kg": 0.0,
                "rate_percent": DEFAULT_RATE_PERCENT,
                "sequence": sequence,
                "priority": 10 + seen[key] - 1,
                "is_active": 1 if is_active else 0,
                "notes": "; ".join(note_parts),
            }
        )

    return policy_rows, warnings


def _build_article_placeholders(article_rows: list[dict], policy_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    policy_pairs = {(row["tariff_number"], row["material"]) for row in policy_rows if row.get("tariff_number") and row.get("material")}
    article_pairs = set()
    for row in article_rows:
        tariff_number = _normalize_tariff_number(_row_value(row, "HS CODE (10 DIGIT)", "HS CODE", "CODE HS (10 DIG)"))
        material = _normalize_material_name(_row_value(row, "DOUANE MATERIAL", "MATERIAU"))
        if tariff_number and material:
            article_pairs.add((tariff_number, material))

    placeholders = []
    warnings = []
    for tariff_number, material in sorted(article_pairs - policy_pairs):
        sequence = (len(policy_rows) + len(placeholders)) * 10 + 10
        placeholders.append(
            {
                "tariff_number": tariff_number,
                "material": material,
                "value_per_kg": 0.0,
                "rate_components": "",
                "rate_per_kg": 0.0,
                "rate_percent": DEFAULT_RATE_PERCENT,
                "sequence": sequence,
                "priority": 90,
                "is_active": 0,
                "notes": "Inactive placeholder: article workbook HS/material pair is missing from DUM summary.",
                "is_article_placeholder": 1,
            }
        )
        warnings.append(
            {
                "tariff_number": tariff_number,
                "material": material,
                "message": "Article HS/material pair missing from DUM summary; inactive placeholder created.",
            }
        )
    return placeholders, warnings


def _upsert_policy(policy_name: str, policy_rows: list[dict], set_default: bool):
    existing = frappe.db.get_value("Pricing Customs Policy", {"policy_name": policy_name}, "name")
    doc = frappe.get_doc("Pricing Customs Policy", existing) if existing else frappe.new_doc("Pricing Customs Policy")
    doc.policy_name = policy_name
    doc.company = doc.company or ""
    doc.is_active = 1
    doc.is_default = 1 if set_default else cint(doc.get("is_default") or 0)
    doc.notes = (
        "Seeded from Resume_HS_Codes_DUM.xlsx. Rules match by HS code and material; "
        "customs value is DUM value when present, otherwise theoretical value."
    )
    doc.set("customs_rules", [])
    for row in policy_rows:
        doc.append("customs_rules", {key: value for key, value in row.items() if key != "is_article_placeholder"})

    if set_default:
        for name in frappe.get_all(
            "Pricing Customs Policy",
            filters={"name": ["!=", existing or ""]},
            pluck="name",
            limit_page_length=0,
        ):
            frappe.db.set_value("Pricing Customs Policy", name, "is_default", 0, update_modified=False)

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item_material(material: str, summary: dict, dry_run: bool):
    material = _normalize_material_name(material)
    if not material:
        return ""
    if frappe.db.exists("Item Material", material):
        return material
    summary["new_materials"].append(material)
    if not dry_run:
        doc = frappe.new_doc("Item Material")
        doc.material_name = material
        doc.material_code = material
        doc.is_active = 1
        doc.insert(ignore_permissions=True)
    return material


def _ensure_customs_tariff_number(code: str, summary: dict, dry_run: bool):
    code = _normalize_tariff_number(code)
    if not code or frappe.db.exists("Customs Tariff Number", code):
        return code
    summary["new_customs_tariff_numbers"].append(code)
    if not dry_run:
        frappe.get_doc(
            {"doctype": "Customs Tariff Number", "name": code, "tariff_number": code, "description": code}
        ).insert(ignore_permissions=True)
    return code


def _read_rows(path: Path, sheet_name: str, header_row: int):
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_path = _resolve_sheet_path(archive, sheet_name)
        root = ET.fromstring(archive.read(sheet_path))

    raw_rows = []
    for row in root.findall(".//a:sheetData/a:row", XML_NS):
        raw_rows.append((cint(row.attrib.get("r")), _read_cells(row, shared_strings)))
    if len(raw_rows) < header_row:
        return []

    header_cells = next((cells for excel_row, cells in raw_rows if excel_row == header_row), raw_rows[header_row - 1][1])
    headers = _make_headers(header_cells)
    rows = []
    for excel_row, cells in raw_rows:
        if excel_row <= header_row:
            continue
        row = {"excel_row": excel_row}
        has_value = False
        for col, header in headers.items():
            value = _clean(cells.get(col))
            row[header] = value
            has_value = has_value or bool(value)
        if has_value:
            rows.append(row)
    return rows


def _read_shared_strings(archive: ZipFile):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in item.findall(".//a:t", XML_NS)) for item in root.findall("a:si", XML_NS)]


def _resolve_sheet_path(archive: ZipFile, sheet_name: str):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheet = workbook.find(f".//a:sheet[@name='{sheet_name}']", XML_NS)
    if sheet is None:
        frappe.throw(_("Sheet {0} not found in workbook.").format(sheet_name))
    relation_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
    return "xl/" + relmap[relation_id].lstrip("/")


def _read_cells(row, shared_strings):
    cells = {}
    for cell in row.findall("a:c", XML_NS):
        column = _cell_column(cell.attrib.get("r", ""))
        cells[column] = _cell_value(cell, shared_strings)
    return cells


def _cell_value(cell, shared_strings):
    if cell.attrib.get("t") == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//a:t", XML_NS))
    value = cell.find("a:v", XML_NS)
    if value is None:
        return ""
    text = value.text or ""
    if cell.attrib.get("t") == "s":
        return shared_strings[cint(text)]
    return text


def _make_headers(cells):
    headers = {}
    seen = Counter()
    for col in sorted(cells, key=_column_number):
        label = _clean_header(cells[col])
        if not label:
            continue
        seen[label] += 1
        headers[col] = label if seen[label] == 1 else f"{label}_{seen[label]}"
    return headers


def _row_value(row: dict, *headers: str):
    for header in headers:
        value = _clean(row.get(_clean_header(header)))
        if value:
            return value
    return ""


def _normalize_tariff_number(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _normalize_material_name(value):
    text = _clean(value).upper()
    if not text:
        return ""
    aliases = {
        "ACIER": "ACIER",
        "ACIER EPOXY": "ACIER",
        "ALUMINIUM": "ALUM",
        "BÉTON": "BETON",
        "CAOUTCHOUC": "CAOUTCHOUC",
        "CONCRETE": "BETON",
        "COPPER": "CUIVRE",
        "CUIVRE": "CUIVRE",
        "CUIVRE (CÂBLE)": "CUIVRE",
        "HUILE": "HUILE",
        "PLASTIQUE / PVC": "PLASTIQUE",
        "PVC": "PLASTIQUE",
        "STEEL": "ACIER",
    }
    if "GALVA" in text:
        return "GALVA"
    return aliases.get(text, text)


def _decimal(value):
    text = _clean(value).replace(" ", "").replace("\u00a0", "")
    if not text or text == "-" or text.startswith("#"):
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _format_percent(value):
    return str(int(value)) if float(value).is_integer() else str(value)


def _clean(value):
    if value is None:
        return ""
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    return "" if text == "-" else text


def _clean_header(value):
    return _clean(value).upper()


def _cell_column(cell_ref: str):
    return "".join(ch for ch in cell_ref if ch.isalpha())


def _column_number(column: str):
    value = 0
    for char in column:
        value = value * 26 + ord(char.upper()) - ord("A") + 1
    return value


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no"}
