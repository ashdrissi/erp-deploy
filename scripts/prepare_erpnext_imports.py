from __future__ import annotations

import argparse
import csv
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile
import unicodedata


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

DEFAULT_XLSX = Path("/root/erp-deploy/docs/data/PRICING ORDER LIFT TURKEY - MOROCCO _v07.02.2026 (2).xlsx")
DEFAULT_XLSM = Path("/root/erp-deploy/docs/data/Pricing & Edition Devis_V01.2026 (3).xlsm")
DEFAULT_OUTPUT_DIR = Path("/root/erp-deploy/docs/data/generated")

GROUP_MAP = {
    "ARMOIRE": "Armoire",
    "AUTRES": "Autres",
    "BOUTONS": "Boutons",
    "CABINE & ARCADE": "Cabine & Arcade",
    "CABLES & ACCESSOIRES": "Cables & Accessoires",
    "CABLES ELECTRIQUES & ACCESSOIRES": "Cables Electriques & Accessoires",
    "GOSE": "Gose",
    "MOTEUR": "Moteur",
    "OPÉRATEUR": "Operateur",
    "PORTE": "Porte",
    "RAILS & ACCESSOIRES": "Rails & Accessoires",
}

PRICE_LISTS = [
    {
        "price_list": "Turkey Source Cost",
        "currency": "USD",
        "selling": "0",
        "buying": "1",
        "enabled": "1",
        "source_sheet": "Pricing Turkey",
        "source_column": "PRICE IN TURKEY (without kdv) + LOCAL TRANSP 'USD'",
    },
    {
        "price_list": "Morocco Min",
        "currency": "MAD",
        "selling": "1",
        "buying": "0",
        "enabled": "1",
        "source_sheet": "Pricing sheet clean",
        "source_column": "Prix a proposer ss stock (min)",
    },
    {
        "price_list": "Morocco Normal",
        "currency": "MAD",
        "selling": "1",
        "buying": "0",
        "enabled": "1",
        "source_sheet": "Pricing sheet clean",
        "source_column": "Prix a proposer (normal)",
    },
    {
        "price_list": "Morocco With Stock",
        "currency": "MAD",
        "selling": "1",
        "buying": "0",
        "enabled": "1",
        "source_sheet": "Pricing sheet clean",
        "source_column": "Prix a proposer avec stock",
    },
]

BRAND_PATTERNS = [
    ("ATERYA", ["ATERYA"]),
    ("AKIS", ["AKİŞ", "AKIS"]),
    ("DEAS", ["DEAS"]),
    ("FERMATOR", ["FERMATOR"]),
    ("MONARCH", ["MONARCH"]),
    ("EEM", [" EEM", "EEM ", "EEM+"] ),
    ("PRIMO", ["PRIMO"]),
    ("ADRIVE", ["ADRIVE"]),
    ("ARKEL", ["ARKEL"]),
    ("MUGEN", ["MUGEN"]),
    ("VOLPI", ["VOLPİ", "VOLPI"]),
    ("MONTANARI", ["MONTANARI"]),
]

SAFE_BUNDLES = [
    {
        "bundle_item_code": "IT.1",
        "description": "Workbook-explicit cabin set: cabin standard 1200/1100 + arcade/accessories gearbox.",
        "children": [
            {"item_code": "IT.1-5", "qty": "1"},
            {"item_code": "IT.1-11", "qty": "1"},
        ],
    },
    {
        "bundle_item_code": "IT.28",
        "description": "Workbook-explicit rail set composed of one guide rail 50 and one guide rail 70.",
        "children": [
            {"item_code": "IT.26", "qty": "1"},
            {"item_code": "IT.27", "qty": "1"},
        ],
    },
]

UOM_OVERRIDES = {
    "IT.33": "M",
    "IT.37": "Pc",
}

MATERIAL_MAP = {
    "STEEL": "STEEL",
    "INOX": "INOX",
    "GALVA": "GALVA",
    "COPPER": "COPPER",
    "ALUM": "ALUM",
    "ALUMINUM": "ALUM",
    "ALUMINIUM": "ALUM",
    "PVC": "OTHER",
    "CONCRETE": "OTHER",
    "OIL": "OTHER",
}


def col_to_num(col: str) -> int:
    number = 0
    for char in col:
        if char.isalpha():
            number = number * 26 + ord(char.upper()) - 64
    return number


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").strip().lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_shared_strings(workbook: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    values = []
    for string_item in root.findall("main:si", NS):
        values.append("".join((node.text or "") for node in string_item.iterfind(".//main:t", NS)))
    return values


def parse_workbook_map(workbook: ZipFile) -> dict[str, str]:
    root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("pkgrel:Relationship", NS)}

    sheets = {}
    for sheet in root.find("main:sheets", NS):
        rel_id = sheet.attrib.get(f"{{{NS['rel']}}}id")
        sheets[sheet.attrib["name"]] = "xl/" + rel_map[rel_id].lstrip("/")
    return sheets


def get_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join((node.text or "") for node in cell.findall(".//main:t", NS))

    value = cell.find("main:v", NS)
    if value is None:
        return ""

    raw = value.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw

    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"

    return raw


def parse_sheet_rows(workbook_path: Path, sheet_name: str) -> list[tuple[int, list[str]]]:
    with ZipFile(workbook_path) as workbook:
        shared_strings = parse_shared_strings(workbook)
        sheet_path = parse_workbook_map(workbook)[sheet_name]
        root = ET.fromstring(workbook.read(sheet_path))

    rows = []
    sheet_data = root.find("main:sheetData", NS)
    if sheet_data is None:
        return rows

    for row in sheet_data.findall("main:row", NS):
        row_number = int(row.attrib.get("r", "0"))
        values_by_col = {}
        max_col = 0

        for cell in row.findall("main:c", NS):
            ref = cell.attrib.get("r", "")
            match = re.match(r"([A-Z]+)(\d+)", ref)
            if not match:
                continue
            col_number = col_to_num(match.group(1))
            max_col = max(max_col, col_number)
            values_by_col[col_number] = get_cell_value(cell, shared_strings)

        rows.append((row_number, [values_by_col.get(i, "") for i in range(1, max_col + 1)]))

    return rows


def normalize_ref(source_ref: str, description: str) -> tuple[str, str]:
    if source_ref == "IT.1-17" and description == "SET ARCADE TYPE L VVVF 2V":
        return "IT.1-17-ARCADE", "Duplicate source ref resolved from IT.1-17"
    if source_ref == "IT.1-18" and description == "SET ARCADE TYPE L GEARLESS":
        return "IT.1-18-ARCADE", "Duplicate source ref resolved from IT.1-18"
    return source_ref, ""


def clean_uom(source_ref: str, source_uom: str) -> tuple[str, str]:
    if source_ref in UOM_OVERRIDES:
        return UOM_OVERRIDES[source_ref], f"UOM overridden from {source_uom or 'blank'}"
    return source_uom, ""


def normalize_material(source_material: str) -> str:
    normalized = (source_material or "").strip().upper()
    if normalized == "":
        return ""
    if normalized in {"-", "N"}:
        return "OTHER"
    return MATERIAL_MAP.get(normalized, "OTHER")


def detect_brand(description: str) -> str:
    text = (description or "").upper()
    for brand_name, needles in BRAND_PATTERNS:
        for needle in needles:
            if needle in text:
                return brand_name
    return ""


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_item_groups() -> list[dict[str, str]]:
    rows = []
    for source_component, item_group_name in GROUP_MAP.items():
        rows.append(
            {
                "item_group": source_component.replace(" & ", "_").replace(" ", "_").replace("É", "E"),
                "item_group_name": item_group_name,
                "parent_item_group": "All Item Groups",
                "source_component": source_component,
                "review_note": "Confirm whether GOSE stays as its own family" if source_component == "GOSE" else "",
            }
        )
    return rows


def build_uoms() -> list[dict[str, str]]:
    return [
        {
            "uom": "Pc",
            "enabled": "1",
            "source_value": "Pc",
            "note": "Keep as source UOM unless business wants ERP standardization",
        },
        {"uom": "SET", "enabled": "1", "source_value": "SET", "note": ""},
        {"uom": "M", "enabled": "1", "source_value": "M", "note": "Represents linear meter"},
    ]


def build_items() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    rows = []
    review_issues = []
    source_to_final_ref = {}
    seen_final_refs = set()
    turkey_material_map = {}

    for row_number, row in parse_sheet_rows(DEFAULT_XLSX, "Pricing Turkey"):
        if row_number <= 2:
            continue
        source_ref = (row[0] if len(row) > 0 else "").strip()
        if not source_ref.startswith("IT."):
            continue
        description = (row[1] if len(row) > 1 else "").strip()
        raw_material = (row[5] if len(row) > 5 else "").strip()
        turkey_material_map[f"{source_ref}::{description}"] = normalize_material(raw_material)

    for row_number, row in parse_sheet_rows(DEFAULT_XLSX, "Pricing sheet clean"):
        if row_number <= 10:
            continue

        source_ref = (row[0] if len(row) > 0 else "").strip()
        if not source_ref.startswith("IT."):
            continue

        description = (row[1] if len(row) > 1 else "").strip()
        component = (row[2] if len(row) > 2 else "").strip()
        source_uom = (row[3] if len(row) > 3 else "").strip()
        weight = (row[4] if len(row) > 4 else "").strip()
        material = turkey_material_map.get(f"{source_ref}::{description}", "")
        brand = detect_brand(description)

        item_code, ref_note = normalize_ref(source_ref, description)
        stock_uom, uom_note = clean_uom(source_ref, source_uom)

        notes = [note for note in (ref_note, uom_note) if note]
        if component == "GOSE":
            notes.append("Confirm GOSE item group naming")

        if item_code in seen_final_refs:
            raise ValueError(f"Final item code collision remains unresolved for {item_code}")

        seen_final_refs.add(item_code)
        source_to_final_ref[f"{source_ref}::{description}"] = item_code

        rows.append(
            {
                "item_code": item_code,
                "item_name": description,
                "description": description,
                "item_group": GROUP_MAP.get(component, component),
                "stock_uom": stock_uom,
                "brand": brand,
                "custom_material": material,
                "custom_weight_kg": weight,
                "custom_volume_m3": "0",
                "weight_per_unit": weight,
                "disabled": "0",
                "source_sheet": "Pricing sheet clean",
                "source_row": str(row_number),
                "source_ref": source_ref,
                "review_note": " | ".join(notes),
            }
        )

        if uom_note:
            review_issues.append(
                {
                    "ref": item_code,
                    "description": description,
                    "source_sheet": "Pricing sheet clean",
                    "issue": f"Source UOM `{source_uom}` overridden",
                    "recommended_action": stock_uom,
                }
            )

        if ref_note:
            review_issues.append(
                {
                    "ref": item_code,
                    "description": description,
                    "source_sheet": "Pricing sheet clean",
                    "issue": f"Source ref `{source_ref}` duplicated in workbook",
                    "recommended_action": "Use generated unique code",
                }
            )

            if component == "GOSE":
                review_issues.append(
                    {
                    "ref": item_code,
                    "description": description,
                    "source_sheet": "Pricing sheet clean",
                    "issue": "Component family `GOSE` needs category confirmation",
                    "recommended_action": "Keep as separate item group unless business says merge",
                    }
                )

        if not material:
            review_issues.append(
                {
                    "ref": item_code,
                    "description": description,
                    "source_sheet": "Pricing Turkey",
                    "issue": "Material is blank or unmapped in source workbook",
                    "recommended_action": "Review customs applicability for this item",
                }
            )

    return rows, review_issues, source_to_final_ref


def lookup_final_ref(source_ref: str, description: str, source_to_final_ref: dict[str, str]) -> str:
    return source_to_final_ref.get(f"{source_ref}::{description}", source_ref)


def build_item_prices(source_to_final_ref: dict[str, str]) -> list[dict[str, str]]:
    rows = []

    for row_number, row in parse_sheet_rows(DEFAULT_XLSX, "Pricing sheet clean"):
        if row_number <= 10:
            continue
        source_ref = (row[0] if len(row) > 0 else "").strip()
        if not source_ref.startswith("IT."):
            continue

        description = (row[1] if len(row) > 1 else "").strip()
        final_ref = lookup_final_ref(source_ref, description, source_to_final_ref)
        uom, _ = clean_uom(source_ref, (row[3] if len(row) > 3 else "").strip())

        selling_prices = [
            ("Morocco Min", "MAD", row[5] if len(row) > 5 else "", "1", "0"),
            ("Morocco Normal", "MAD", row[6] if len(row) > 6 else "", "1", "0"),
            ("Morocco With Stock", "MAD", row[7] if len(row) > 7 else "", "1", "0"),
        ]
        for price_list, currency, rate, selling, buying in selling_prices:
            rate = (rate or "").strip()
            if not rate:
                continue
            rows.append(
                {
                    "item_code": final_ref,
                    "price_list": price_list,
                    "currency": currency,
                    "price_list_rate": rate,
                    "selling": selling,
                    "buying": buying,
                    "uom": uom,
                    "source_sheet": "Pricing sheet clean",
                    "source_row": str(row_number),
                    "source_ref": source_ref,
                }
            )

    for row_number, row in parse_sheet_rows(DEFAULT_XLSX, "Pricing Turkey"):
        if row_number <= 2:
            continue
        source_ref = (row[0] if len(row) > 0 else "").strip()
        if not source_ref.startswith("IT."):
            continue

        description = (row[1] if len(row) > 1 else "").strip()
        final_ref = lookup_final_ref(source_ref, description, source_to_final_ref)
        uom, _ = clean_uom(source_ref, (row[3] if len(row) > 3 else "").strip())
        rate = (row[6] if len(row) > 6 else "").strip()
        if not rate:
            continue

        rows.append(
            {
                "item_code": final_ref,
                "price_list": "Turkey Source Cost",
                "currency": "USD",
                "price_list_rate": rate,
                "selling": "0",
                "buying": "1",
                "uom": uom,
                "source_sheet": "Pricing Turkey",
                "source_row": str(row_number),
                "source_ref": source_ref,
            }
        )

    return rows


def classify_item_model(item: dict[str, str]) -> tuple[str, str]:
    description = item["item_name"].upper()
    item_group = item["item_group"]
    stock_uom = item["stock_uom"]

    if "+ CHASSIS" in description or description.startswith("CHASSIS MOTEUR"):
        return (
            "bom_review_candidate",
            "Motor/chassis combination may be better modeled later as an assembly or BOM-backed sellable item.",
        )

    if item_group in {"Cabine & Arcade", "Armoire", "Rails & Accessoires", "Autres"} and (
        stock_uom == "SET"
        or description.startswith("SET ")
        or " SET COMPLET" in description
        or " + " in description
        or " & " in description
        or " AVEC " in description
    ):
        return (
            "bundle_candidate",
            "Description/UOM suggests a commercial grouped offer that may later become a Product Bundle.",
        )

    return (
        "plain_item",
        "Keep as a normal Item for phase 1 import.",
    )


def _get_sheet_rows(workbook: ZipFile, sheet_name: str) -> tuple[str, dict[int, list[str]]]:
    workbook_map = parse_workbook_map(workbook)
    shared_strings = parse_shared_strings(workbook)
    sheet_path = workbook_map[sheet_name]
    root = ET.fromstring(workbook.read(sheet_path))
    rows = {}

    sheet_data = root.find("main:sheetData", NS)
    if sheet_data is None:
        return sheet_path, rows

    for row in sheet_data.findall("main:row", NS):
        row_number = int(row.attrib.get("r", "0"))
        values_by_col = {}
        max_col = 0
        for cell in row.findall("main:c", NS):
            ref = cell.attrib.get("r", "")
            match = re.match(r"([A-Z]+)(\d+)", ref)
            if not match:
                continue
            col_number = col_to_num(match.group(1))
            max_col = max(max_col, col_number)
            values_by_col[col_number] = get_cell_value(cell, shared_strings)
        rows[row_number] = [values_by_col.get(i, "") for i in range(1, max_col + 1)]

    return sheet_path, rows


def build_item_images(items: list[dict[str, str]], output_dir: Path) -> tuple[list[dict[str, str]], Counter]:
    rows = []
    summary = Counter()
    item_name_map = {normalize_text(row["item_name"]): row["item_code"] for row in items}
    image_dir = output_dir / "item_images"
    if image_dir.exists():
        shutil.rmtree(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    def register_image(
        *,
        item_code: str,
        image_bytes: bytes,
        suffix: str,
        source_workbook: str,
        source_sheet: str,
        source_row: int,
        source_image: str,
        match_basis: str,
        seen: set[str],
    ) -> None:
        if item_code in seen:
            summary["duplicates_skipped"] += 1
            return
        seen.add(item_code)
        filename = f"{item_code}{suffix.lower()}"
        (image_dir / filename).write_bytes(image_bytes)
        rows.append(
            {
                "item_code": item_code,
                "image_filename": filename,
                "source_workbook": source_workbook,
                "source_sheet": source_sheet,
                "source_row": str(source_row),
                "source_image": source_image,
                "match_basis": match_basis,
            }
        )
        summary["mapped"] += 1

    seen_items: set[str] = set()
    pricing_workbook = DEFAULT_XLSX
    with ZipFile(pricing_workbook) as workbook:
        workbook_map = parse_workbook_map(workbook)
        shared_strings = parse_shared_strings(workbook)

        # Morocco Prices: match exact item names from the French column.
        morocco_sheet_path, morocco_rows = _get_sheet_rows(workbook, "Morocco Prices")
        morocco_sheet = ET.fromstring(workbook.read(morocco_sheet_path))
        morocco_rels = ET.fromstring(
            workbook.read(f"xl/worksheets/_rels/{Path(morocco_sheet_path).name}.rels")
        )
        morocco_rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"] for rel in morocco_rels.findall("pkgrel:Relationship", NS)
        }
        drawing = morocco_sheet.find("main:drawing", NS)
        if drawing is not None:
            drawing_target = morocco_rel_map[drawing.attrib[f"{{{NS['rel']}}}id"]]
            drawing_path = "xl/" + drawing_target.replace("../", "")
            drawing_root = ET.fromstring(workbook.read(drawing_path))
            drawing_rels = ET.fromstring(
                workbook.read(f"xl/drawings/_rels/{Path(drawing_path).name}.rels")
            )
            drawing_rel_map = {
                rel.attrib["Id"]: rel.attrib["Target"] for rel in drawing_rels.findall("pkgrel:Relationship", NS)
            }

            for anchor in list(drawing_root):
                frm = anchor.find("xdr:from", NS)
                pic = anchor.find("xdr:pic", NS)
                if frm is None or pic is None:
                    continue
                row_number = int(frm.find("xdr:row", NS).text) + 1
                values = morocco_rows.get(row_number, [])
                source_candidates = [values[2] if len(values) > 2 else "", values[1] if len(values) > 1 else ""]
                item_code = ""
                match_basis = ""
                for candidate in source_candidates:
                    key = normalize_text(candidate)
                    if key in item_name_map:
                        item_code = item_name_map[key]
                        match_basis = f"exact_name:{candidate}"
                        break
                if not item_code:
                    summary["unmatched"] += 1
                    continue

                blip = pic.find('.//a:blip', NS)
                if blip is None:
                    summary["unmatched"] += 1
                    continue
                target = drawing_rel_map[blip.attrib[f"{{{NS['rel']}}}embed"]]
                media_path = "xl/" + target.replace("../", "")
                suffix = Path(media_path).suffix or ".img"
                register_image(
                    item_code=item_code,
                    image_bytes=workbook.read(media_path),
                    suffix=suffix,
                    source_workbook=pricing_workbook.name,
                    source_sheet="Morocco Prices",
                    source_row=row_number,
                    source_image=Path(media_path).name,
                    match_basis=match_basis,
                    seen=seen_items,
                )

        # Pricing Turkey: direct ref-based image mapping when present.
        turkey_sheet_path, turkey_rows = _get_sheet_rows(workbook, "Pricing Turkey")
        turkey_sheet = ET.fromstring(workbook.read(turkey_sheet_path))
        turkey_rels_path = f"xl/worksheets/_rels/{Path(turkey_sheet_path).name}.rels"
        turkey_rels = ET.fromstring(workbook.read(turkey_rels_path))
        turkey_rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"] for rel in turkey_rels.findall("pkgrel:Relationship", NS)
        }
        turkey_drawing = turkey_sheet.find("main:drawing", NS)
        if turkey_drawing is not None:
            draw_target = turkey_rel_map[turkey_drawing.attrib[f"{{{NS['rel']}}}id"]]
            draw_path = "xl/" + draw_target.replace("../", "")
            draw_root = ET.fromstring(workbook.read(draw_path))
            draw_rels_path = f"xl/drawings/_rels/{Path(draw_path).name}.rels"
            if draw_rels_path in workbook.namelist():
                draw_rels = ET.fromstring(workbook.read(draw_rels_path))
                draw_rel_map = {
                    rel.attrib["Id"]: rel.attrib["Target"]
                    for rel in draw_rels.findall("pkgrel:Relationship", NS)
                }
                for anchor in list(draw_root):
                    frm = anchor.find("xdr:from", NS)
                    pic = anchor.find("xdr:pic", NS)
                    if frm is None or pic is None:
                        continue
                    row_number = int(frm.find("xdr:row", NS).text) + 1
                    values = turkey_rows.get(row_number, [])
                    source_ref = (values[0] if len(values) > 0 else "").strip()
                    description = (values[1] if len(values) > 1 else "").strip()
                    item_code = next(
                        (
                            row["item_code"]
                            for row in items
                            if row["source_ref"] == source_ref and row["item_name"] == description
                        ),
                        "",
                    )
                    if not item_code:
                        summary["unmatched"] += 1
                        continue

                    blip = pic.find('.//a:blip', NS)
                    if blip is None:
                        summary["unmatched"] += 1
                        continue
                    media_target = draw_rel_map[blip.attrib[f"{{{NS['rel']}}}embed"]]
                    media_path = "xl/" + media_target.replace("../", "")
                    register_image(
                        item_code=item_code,
                        image_bytes=workbook.read(media_path),
                        suffix=Path(media_path).suffix or ".img",
                        source_workbook=pricing_workbook.name,
                        source_sheet="Pricing Turkey",
                        source_row=row_number,
                        source_image=Path(media_path).name,
                        match_basis=f"direct_ref:{source_ref}",
                        seen=seen_items,
                    )

    return rows, summary


def build_item_modeling(items: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], Counter]:
    modeling_rows = []
    review_rows = []
    summary = Counter()

    for item in items:
        suggested_model, rationale = classify_item_model(item)
        summary[suggested_model] += 1

        row = {
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "stock_uom": item["stock_uom"],
            "suggested_model": suggested_model,
            "rationale": rationale,
            "source_ref": item["source_ref"],
            "source_row": item["source_row"],
        }
        modeling_rows.append(row)

        if suggested_model != "plain_item":
            review_rows.append(row)

    return modeling_rows, review_rows, summary


def write_outputs(output_dir: Path) -> dict[str, int]:
    item_groups = build_item_groups()
    uoms = build_uoms()
    items, review_issues, source_to_final_ref = build_items()
    item_prices = build_item_prices(source_to_final_ref)
    item_modeling, bundle_review, modeling_summary = build_item_modeling(items)
    item_images, image_summary = build_item_images(items, output_dir)
    safe_bundle_rows = []
    for bundle in SAFE_BUNDLES:
        for child in bundle["children"]:
            safe_bundle_rows.append(
                {
                    "bundle_item_code": bundle["bundle_item_code"],
                    "child_item_code": child["item_code"],
                    "qty": child["qty"],
                    "description": bundle["description"],
                }
            )

    write_csv(
        output_dir / "item_groups.csv",
        ["item_group", "item_group_name", "parent_item_group", "source_component", "review_note"],
        item_groups,
    )
    write_csv(output_dir / "uoms.csv", ["uom", "enabled", "source_value", "note"], uoms)
    write_csv(
        output_dir / "price_lists.csv",
        ["price_list", "currency", "selling", "buying", "enabled", "source_sheet", "source_column"],
        PRICE_LISTS,
    )
    write_csv(
        output_dir / "items.csv",
        [
            "item_code",
            "item_name",
            "description",
            "item_group",
            "stock_uom",
            "brand",
            "custom_material",
            "custom_weight_kg",
            "custom_volume_m3",
            "weight_per_unit",
            "disabled",
            "source_sheet",
            "source_row",
            "source_ref",
            "review_note",
        ],
        items,
    )
    write_csv(
        output_dir / "item_prices.csv",
        [
            "item_code",
            "price_list",
            "currency",
            "price_list_rate",
            "selling",
            "buying",
            "uom",
            "source_sheet",
            "source_row",
            "source_ref",
        ],
        item_prices,
    )
    write_csv(
        output_dir / "review_issues.csv",
        ["ref", "description", "source_sheet", "issue", "recommended_action"],
        review_issues,
    )
    write_csv(
        output_dir / "item_images.csv",
        [
            "item_code",
            "image_filename",
            "source_workbook",
            "source_sheet",
            "source_row",
            "source_image",
            "match_basis",
        ],
        item_images,
    )
    write_csv(
        output_dir / "product_bundles.csv",
        ["bundle_item_code", "child_item_code", "qty", "description"],
        safe_bundle_rows,
    )
    write_csv(
        output_dir / "item_modeling.csv",
        [
            "item_code",
            "item_name",
            "item_group",
            "stock_uom",
            "suggested_model",
            "rationale",
            "source_ref",
            "source_row",
        ],
        item_modeling,
    )
    write_csv(
        output_dir / "bundle_review_candidates.csv",
        [
            "item_code",
            "item_name",
            "item_group",
            "stock_uom",
            "suggested_model",
            "rationale",
            "source_ref",
            "source_row",
        ],
        bundle_review,
    )

    summary_path = output_dir / "bundle_modeling_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Item Modeling Summary",
                "",
                "Conservative phase-2 modeling guidance generated from the item catalog.",
                "",
                "## Counts",
                "",
                f"- plain_item: `{modeling_summary['plain_item']}`",
                f"- bundle_candidate: `{modeling_summary['bundle_candidate']}`",
                f"- bom_review_candidate: `{modeling_summary['bom_review_candidate']}`",
                "",
                "## Guidance",
                "",
                "- `plain_item`: import as a normal Item and use directly in pricing/transactions.",
                "- `bundle_candidate`: import as a normal Item first, then review as a possible ERPNext Product Bundle after child items are validated.",
                "- `bom_review_candidate`: import as a normal Item first, then review whether the business wants an assembly/BOM model instead of a simple bundle.",
                "",
                "## Important",
                "",
                "- These are conservative suggestions only; no bundle or BOM structures were auto-created from the spreadsheet because the files do not provide explicit child-item compositions.",
                "",
                "## Image Extraction",
                "",
                f"- mapped item images: `{image_summary['mapped']}`",
                f"- unmatched image anchors: `{image_summary['unmatched']}`",
                f"- duplicate image anchors skipped: `{image_summary['duplicates_skipped']}`",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "item_groups": len(item_groups),
        "uoms": len(uoms),
        "price_lists": len(PRICE_LISTS),
        "items": len(items),
        "item_prices": len(item_prices),
        "review_issues": len(review_issues),
        "bundle_review_candidates": len(bundle_review),
        "item_images": len(item_images),
        "product_bundle_rows": len(safe_bundle_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ERPNext import CSVs from the Orderlift pricing workbooks.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Only print the output counts without writing files")
    args = parser.parse_args()

    if not DEFAULT_XLSX.exists():
        raise FileNotFoundError(DEFAULT_XLSX)
    if not DEFAULT_XLSM.exists():
        raise FileNotFoundError(DEFAULT_XLSM)

    if args.dry_run:
        items, review_issues, source_to_final_ref = build_items()
        counts = {
            "item_groups": len(build_item_groups()),
            "uoms": len(build_uoms()),
            "price_lists": len(PRICE_LISTS),
            "items": len(items),
            "item_prices": len(build_item_prices(source_to_final_ref)),
            "review_issues": len(review_issues),
            "bundle_review_candidates": len(build_item_modeling(items)[1]),
            "item_images": len(build_item_images(items, args.output_dir)[0]),
            "product_bundle_rows": sum(len(bundle["children"]) for bundle in SAFE_BUNDLES),
        }
    else:
        counts = write_outputs(args.output_dir)

    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
