from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import frappe
from frappe import _
from frappe.utils import cint, flt

from orderlift.orderlift_logistics.utils.item_sequence import get_next_item_code, normalize_abbreviation


DEFAULT_WORKBOOK = Path("/tmp/data base des articles.xlsx")
DEFAULT_SHEET = "Database"

PRICE_LISTS = {
    "catalogue": {"name": "PRIX CATALOGUE", "currency": "MAD", "selling": 1, "buying": 0},
    "vente_maroc": {"name": "PRIX DE VENTE AU MAROC", "currency": "MAD", "selling": 1, "buying": 0},
    "fournisseur_mad": {"name": "PRIX FOURNISSEUR MAD", "currency": "MAD", "selling": 0, "buying": 1},
    "fournisseur_usd": {"name": "PRIX FOURNISSEUR USD", "currency": "USD", "selling": 0, "buying": 1},
    "fournisseur_try": {"name": "PRIX FOURNISSEUR TRY", "currency": "TRY", "selling": 0, "buying": 1},
}

CATEGORY_ABBREVIATIONS = {
    "1. GROUPE DE TRACTION (MOTORISATION)": "GTR",
    "2. SUSPENSION ET COMPENSATION": "SUS",
    "3. STRUCTURE DE GUIDAGE (RAILS)": "RAIL",
    "4. CABINE ET ARCADES": "CAB",
    "5. PORTES ET ACCÈS": "POR",
    "6. ÉLECTRICITÉ ET ÉLECTRONIQUE (CONTRÔLE)": "ELEC",
    "7. SIGNALISATION ET INTERFACE": "SIG",
    "8. SÉCURITÉ": "SEC",
    "9. DIVERS": "DIV",
    "10. SET ASCENSEURS COMPLETS": "ASC",
}

SPEC_COLUMNS = {
    "SIZE": "Taille",
    "TYPE": "Type",
    "FINITION": "Finition",
    "CAPACITY": "Capacité",
    "VITESSE": "Vitesse",
    "POWER": "Puissance",
    "AMPÉRAGE": "Ampérage",
    "VOLTAGE": "Tension",
}

NUMERIC_SPEC_ATTRIBUTES = {
    "Tension": "V",
    "Ampérage": "A",
    "Puissance": "kW",
}

MATERIAL_ALIASES = {
    "ACIER": "STEEL",
    "ACIER EPOXY": "STEEL",
    "ALUMINIUM": "ALUM",
    "INOX": "INOX",
    "CUIVRE": "COPPER",
    "CUIVRE (CÂBLE)": "COPPER",
}

REQUIRED_HEADERS = {
    "ITEM CODE",
    "ITEM CATEGORY",
    "ITEM GROUP",
    "ITEM NAME",
    "DISCRIPTION",
    "MATERIAL",
    "BRAND",
    "DEFAULT SUPPLIER",
    "DEFAULT UNIT OF MEASURE",
    "PRIX CATALOGUE",
    "DEVIS PRIX FOURNISSEUR",
    "PRIX FOURNISSEUR",
    "PRIX DE VENTE AU MAROC",
    "POIDS",
    "VOLUME",
    "PACKAGING",
    "PACKAGING TYPE",
    'PACKAGING NUMBER OF "UNITÉ"',
    "POIDS/UNITÉ",
}

HEADER_ALIASES = {
    "ITEM NAME": ("ITEM NAME", "ITEM NAME FR"),
    "SECONDARY ITEM NAME": ("ITEM NAME EN", "SECONDARY ITEM NAME"),
    "DISCRIPTION": ("DISCRIPTION", "DESCRIPTION", "ITEM NAME EN"),
    "MATERIAL": ("MATERIAL", "MATERIAU"),
    "CUSTOMS MATERIAL": ("DOUANE MATERIAL",),
    "POIDS": ("POIDS", "POIDS PACKAGE (KG)"),
    "POIDS/UNITÉ": ("POIDS/UNITÉ",),
    "VOLUME": ("VOLUME", "VOLUME (L)"),
    "L": ("L", "LONG (CM)"),
    "L_2": ("L_2", "LARG (CM)"),
    "H": ("H", "H (CM)"),
    "IMAGE": ("IMAGE",),
    'PACKAGING NUMBER OF "UNITÉ"': ('PACKAGING NUMBER OF "UNITÉ"', 'PACKAGING NUMBER OF "UNITÉ"'),
}

XML_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@frappe.whitelist()
def run(
    workbook_path: str | None = None,
    sheet_name: str = DEFAULT_SHEET,
    dry_run: int | str = 1,
    limit: int | str | None = None,
    start_row: int | str = 2,
    skip_zero_prices: int | str = 1,
    update_existing: int | str = 0,
    create_missing: int | str = 0,
):
    path = Path(workbook_path or DEFAULT_WORKBOOK)
    if not path.exists():
        frappe.throw(_("Workbook not found: {0}").format(path))

    dry_run = _truthy(dry_run)
    skip_zero_prices = _truthy(skip_zero_prices)
    update_existing = _truthy(update_existing)
    create_missing = _truthy(create_missing)
    limit = cint(limit or 0)
    start_row = cint(start_row or 2)

    rows = _read_xlsx_rows(path, sheet_name)
    selected_rows = [row for row in rows if row["excel_row"] >= start_row]
    if limit:
        selected_rows = selected_rows[:limit]

    summary = _new_summary(path, sheet_name, dry_run, limit, start_row, skip_zero_prices, update_existing, create_missing)
    _validate_headers(rows[0]["headers"] if rows else {}, summary)
    _analyze_source_codes(selected_rows, summary)

    caches = _load_caches()
    virtual_sequences = _load_virtual_sequences(caches)

    _ensure_price_lists(summary, caches, dry_run=dry_run)

    sequence_by_category = defaultdict(int)
    for row in selected_rows:
        _process_row(
            row,
            summary,
            caches,
            virtual_sequences,
            dry_run=dry_run,
            skip_zero_prices=skip_zero_prices,
            update_existing=update_existing,
            create_missing=create_missing,
            sequence_by_category=sequence_by_category,
        )

    _finalize_summary(summary)
    if not dry_run:
        _ensure_item_price_brand_field()
        frappe.db.commit()

    return summary


def _new_summary(path: Path, sheet_name: str, dry_run: bool, limit: int, start_row: int, skip_zero_prices: bool, update_existing: bool, create_missing: bool):
    return {
        "workbook_path": str(path),
        "sheet_name": sheet_name,
        "dry_run": dry_run,
        "limit": limit or None,
        "start_row": start_row,
        "skip_zero_prices": skip_zero_prices,
        "update_existing": update_existing,
        "create_missing": create_missing,
        "rows_read": 0,
        "rows_selected": 0,
        "items_created": 0,
        "items_updated": 0,
        "items_skipped": 0,
        "items_missing_for_update": [],
        "item_prices_created": 0,
        "item_prices_updated": 0,
        "item_prices_by_price_list": defaultdict(int),
        "packaging_profiles_created": 0,
        "spec_rows_created": 0,
        "new_price_lists": [],
        "new_brands": [],
        "new_suppliers": [],
        "new_uoms": [],
        "new_item_groups": [],
        "new_item_categories": [],
        "new_item_materials": [],
        "item_category_aliases": [],
        "new_spec_attributes": [],
        "new_customs_tariff_numbers": [],
        "skipped_prices": defaultdict(int),
        "duplicate_source_item_codes": [],
        "generated_item_code_samples": [],
        "warnings": [],
    }


def _process_row(row, summary, caches, virtual_sequences, dry_run: bool, skip_zero_prices: bool, update_existing: bool = False, create_missing: bool = False, sequence_by_category=None):
    summary["rows_read"] += 1
    summary["rows_selected"] += 1

    item_name = _row_value(row, "ITEM NAME")
    erp_item_group = _clean(row.get("ITEM CATEGORY"))
    stock_uom = _clean(row.get("DEFAULT UNIT OF MEASURE"))
    category_article = _clean(row.get("ITEM GROUP"))

    if not item_name or not erp_item_group or not stock_uom or not category_article:
        summary["items_skipped"] += 1
        _warn(
            summary,
            row,
            "Missing required item data: ITEM NAME, ITEM GROUP, DEFAULT UNIT OF MEASURE, and ITEM CATEGORY are required.",
        )
        return

    item_group = _ensure_item_group(erp_item_group, summary, caches, dry_run=dry_run)
    category = _ensure_item_category(category_article, summary, caches, virtual_sequences, dry_run=dry_run)
    stock_uom = _ensure_uom(stock_uom, summary, caches, dry_run=dry_run)

    for attribute in SPEC_COLUMNS.values():
        _ensure_spec_attribute(attribute, summary, caches, dry_run=dry_run)

    if update_existing:
        sequence_by_category = sequence_by_category or defaultdict(int)
        sequence_by_category[category] += 1
        item_code = _format_item_code_for_category(category, sequence_by_category[category], caches)
    else:
        item_code = _next_item_code(category, caches, virtual_sequences, dry_run=dry_run)
    if len(summary["generated_item_code_samples"]) < 20:
        summary["generated_item_code_samples"].append(
            {"excel_row": row["excel_row"], "source_item_code": _clean(row.get("ITEM CODE")), "item_code": item_code}
        )

    item_doc = _build_item_doc(row, item_code, item_group, stock_uom, category, summary, caches, dry_run=dry_run)
    _append_specs(item_doc, row, summary)
    _append_packaging_profile(item_doc, row, stock_uom, summary)

    if update_existing and frappe.db.exists("Item", item_code):
        if not dry_run:
            existing_doc = frappe.get_doc("Item", item_code)
            _update_item_doc(existing_doc, item_doc)
            existing_doc.save(ignore_permissions=True)
        summary["items_updated"] += 1
    elif update_existing and not create_missing:
        summary["items_skipped"] += 1
        if len(summary["items_missing_for_update"]) < 100:
            summary["items_missing_for_update"].append(item_code)
        _warn(summary, row, f"Skipped update: generated item {item_code} does not exist.")
        return
    else:
        if not dry_run:
            item_doc.insert(ignore_permissions=True)
        summary["items_created"] += 1

    _create_item_prices(row, item_code, stock_uom, summary, caches, dry_run=dry_run, skip_zero_prices=skip_zero_prices, overwrite_existing=update_existing)


def _build_item_doc(row, item_code, item_group, stock_uom, category, summary, caches, dry_run: bool):
    unit_weight = _number(_row_value(row, "POIDS/UNITÉ"))
    values = {
        "doctype": "Item",
        "item_code": item_code,
        "item_name": _row_value(row, "ITEM NAME"),
        "custom_item_name_language": "fr",
        "custom_secondary_item_name": _row_value(row, "SECONDARY ITEM NAME"),
        "custom_secondary_item_name_language": "en" if _row_value(row, "SECONDARY ITEM NAME") else "",
        "description": _row_value(row, "DISCRIPTION"),
        "item_group": item_group,
        "stock_uom": stock_uom,
        "custom_item_category": category,
        "custom_material": _ensure_item_material(_row_value(row, "MATERIAL"), summary, caches, dry_run=dry_run),
        "custom_customs_material": _normalize_customs_material(_row_value(row, "CUSTOMS MATERIAL")),
        "custom_weight_kg": unit_weight,
        "custom_volume_m3": 0,
        "custom_length_cm": 0,
        "custom_width_cm": 0,
        "custom_height_cm": 0,
        "is_stock_item": 1,
        "is_purchase_item": 1,
        "is_sales_item": 1,
        "include_item_in_manufacturing": 0,
        "disabled": 0,
        "weight_per_unit": unit_weight,
        "weight_uom": "Kg" if unit_weight else "",
    }
    image_url = _normalize_image_url(_row_value(row, "IMAGE"))
    if image_url:
        values["image"] = image_url
    hs_code = _normalize_hs(row.get("HS CODE (10 DIGIT)"))
    if hs_code:
        values["customs_tariff_number"] = _ensure_customs_tariff_number(hs_code, summary, caches, dry_run=dry_run)

    return frappe.get_doc(values)


def _append_specs(item_doc, row, summary):
    for column, attribute in SPEC_COLUMNS.items():
        value = _clean(row.get(column))
        if not value or value == "-":
            continue
        item_doc.append("custom_specifications", {"specification_attribute": attribute, "value": value})
        summary["spec_rows_created"] += 1


def _append_packaging_profile(item_doc, row, stock_uom: str, summary):
    packaging = _clean(row.get("PACKAGING"))
    packaging_type = _clean(row.get("PACKAGING TYPE")) or packaging
    units_per_package = _number(_row_value(row, 'PACKAGING NUMBER OF "UNITÉ"'))
    weight_kg = _number(_row_value(row, "POIDS"))
    length_cm = _number(_row_value(row, "L"))
    width_cm = _number(_row_value(row, "L_2"))
    height_cm = _number(_row_value(row, "H"))
    volume_m3 = _volume_m3(row)

    if not packaging and not packaging_type and not units_per_package and not any([weight_kg, length_cm, width_cm, height_cm, volume_m3]):
        return

    item_doc.append(
        "custom_packaging_profiles",
        {
            "uom": stock_uom,
            "packaging_type": packaging_type,
            "units_per_package": units_per_package or 1,
            "weight_kg": weight_kg,
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "volume_m3": volume_m3,
            "is_default": 1,
            "is_active": 1,
            "notes": "Imported from data base des articles.xlsx" + (f"; Packaging: {packaging}" if packaging else ""),
        },
    )
    summary["packaging_profiles_created"] += 1


def _update_item_doc(existing_doc, source_doc):
    for fieldname in [
        "item_name",
        "custom_item_name_language",
        "custom_secondary_item_name",
        "custom_secondary_item_name_language",
        "description",
        "item_group",
        "stock_uom",
        "custom_item_category",
        "custom_material",
        "custom_customs_material",
        "custom_weight_kg",
        "custom_volume_m3",
        "custom_length_cm",
        "custom_width_cm",
        "custom_height_cm",
        "is_stock_item",
        "is_purchase_item",
        "is_sales_item",
        "include_item_in_manufacturing",
        "disabled",
        "weight_per_unit",
        "weight_uom",
        "image",
        "customs_tariff_number",
    ]:
        if hasattr(existing_doc, fieldname) and hasattr(source_doc, fieldname):
            existing_doc.set(fieldname, source_doc.get(fieldname))
    if hasattr(existing_doc, "custom_specifications") and hasattr(source_doc, "custom_specifications"):
        existing_doc.set("custom_specifications", [])
        for row in source_doc.get("custom_specifications") or []:
            existing_doc.append("custom_specifications", row.as_dict())
    if hasattr(existing_doc, "custom_packaging_profiles") and hasattr(source_doc, "custom_packaging_profiles"):
        existing_doc.set("custom_packaging_profiles", [])
        for row in source_doc.get("custom_packaging_profiles") or []:
            existing_doc.append("custom_packaging_profiles", row.as_dict())


def _create_item_prices(row, item_code: str, stock_uom: str, summary, caches, dry_run: bool, skip_zero_prices: bool, overwrite_existing: bool = False):
    brand = _ensure_brand(_clean(row.get("BRAND")), summary, caches, dry_run=dry_run)
    supplier = _ensure_supplier(_clean(row.get("DEFAULT SUPPLIER")), summary, caches, dry_run=dry_run)
    prices = [
        ("PRIX CATALOGUE", "catalogue", None),
        ("PRIX DE VENTE AU MAROC", "vente_maroc", None),
    ]

    supplier_currency = _normalize_supplier_currency(_row_value(row, "DEVIS PRIX FOURNISSEUR"))
    if supplier_currency == "MAD":
        prices.append(("PRIX FOURNISSEUR", "fournisseur_mad", supplier))
    elif supplier_currency == "USD":
        prices.append(("PRIX FOURNISSEUR", "fournisseur_usd", supplier))
    elif supplier_currency == "TRY":
        prices.append(("PRIX FOURNISSEUR", "fournisseur_try", supplier))
    elif _row_value(row, "PRIX FOURNISSEUR"):
        summary["skipped_prices"]["unknown_supplier_currency"] += 1
        _warn(summary, row, f"Skipped supplier price: unsupported currency {_row_value(row, 'DEVIS PRIX FOURNISSEUR')!r}.")

    for source_column, price_key, price_supplier in prices:
        rate, reason = _parse_price(_row_value(row, source_column), skip_zero_prices=skip_zero_prices)
        if reason:
            summary["skipped_prices"][f"{source_column}: {reason}"] += 1
            continue

        price_list = PRICE_LISTS[price_key]["name"]
        values = {
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": price_list,
            "uom": stock_uom,
            "price_list_rate": float(rate),
            "brand": brand,
        }
        if price_supplier:
            values["supplier"] = price_supplier

        existing = _find_existing_item_price(item_code, price_list, price_supplier)

        if dry_run:
            if existing and overwrite_existing:
                summary["item_prices_updated"] += 1
            else:
                summary["item_prices_created"] += 1
            summary["item_prices_by_price_list"][price_list] += 1
            continue

        if existing:
            doc = frappe.get_doc("Item Price", existing)
            doc.update(values)
            doc.save(ignore_permissions=True)
            summary["item_prices_updated"] += 1
        else:
            doc = frappe.get_doc(values).insert(ignore_permissions=True)
            summary["item_prices_created"] += 1
        if brand:
            frappe.db.set_value("Item Price", doc.name, "brand", brand, update_modified=False)
        summary["item_prices_by_price_list"][price_list] += 1


def _find_existing_item_price(item_code: str, price_list: str, supplier: str | None = None) -> str | None:
    rows = frappe.get_all(
        "Item Price",
        filters={"item_code": item_code, "price_list": price_list},
        fields=["name", "supplier"],
        order_by="modified desc",
        limit_page_length=0,
    )
    if not rows:
        return None

    supplier_key = _key(supplier)
    if supplier_key:
        for row in rows:
            if _key(row.get("supplier")) == supplier_key:
                return row.name

    for row in rows:
        if not _key(row.get("supplier")):
            return row.name
    return rows[0].name


@frappe.whitelist()
def repair_brand_and_sequences(workbook_path: str | None = None, sheet_name: str = DEFAULT_SHEET, dry_run: int | str = 1):
    path = Path(workbook_path or DEFAULT_WORKBOOK)
    if not path.exists():
        frappe.throw(_("Workbook not found: {0}").format(path))

    dry_run = _truthy(dry_run)
    rows = _read_xlsx_rows(path, sheet_name)
    caches = _load_caches()
    sequence_by_category = defaultdict(int)
    summary = {
        "workbook_path": str(path),
        "sheet_name": sheet_name,
        "dry_run": dry_run,
        "rows_read": len(rows),
        "items_seen": 0,
        "item_prices_brand_updated": 0,
        "missing_items": [],
        "category_sequences": {},
        "new_brands": [],
    }

    if not dry_run:
        _ensure_item_price_brand_field()

    for row in rows:
        if not _has_required_item_data(row):
            continue

        category = _resolve_item_category_for_mapping(_clean(row.get("ITEM GROUP")), caches)
        sequence_by_category[category] += 1
        item_code = _format_item_code_for_category(category, sequence_by_category[category], caches)
        summary["items_seen"] += 1

        if not frappe.db.exists("Item", item_code):
            if len(summary["missing_items"]) < 100:
                summary["missing_items"].append(item_code)
            continue

        brand = _ensure_brand(_clean(row.get("BRAND")), summary, caches, dry_run=dry_run)
        if not brand:
            continue

        price_names = frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name", limit_page_length=0)
        summary["item_prices_brand_updated"] += len(price_names)
        if not dry_run:
            for price_name in price_names:
                frappe.db.set_value("Item Price", price_name, "brand", brand, update_modified=False)

    for category, sequence in sequence_by_category.items():
        summary["category_sequences"][category] = sequence
        if not dry_run:
            frappe.db.set_value("Item Category", category, "current_sequence", sequence, update_modified=False)

    if not dry_run:
        frappe.db.commit()

    return summary


def _has_required_item_data(row):
    return bool(
        _row_value(row, "ITEM NAME")
        and _clean(row.get("ITEM GROUP"))
        and _clean(row.get("DEFAULT UNIT OF MEASURE"))
        and _clean(row.get("ITEM CATEGORY"))
    )


def _resolve_item_category_for_mapping(source_category: str, caches) -> str:
    if source_category in caches["item_categories"]:
        return source_category
    abbreviation = _category_abbreviation(source_category)
    return caches["item_category_by_abbreviation"].get(normalize_abbreviation(abbreviation), source_category)


def _format_item_code_for_category(category: str, sequence: int, caches) -> str:
    info = caches["item_categories"][category]
    abbreviation = normalize_abbreviation(info.get("abbreviation"))
    digits = cint(info.get("sequence_digits") or 5)
    return f"{abbreviation}-{sequence:0{digits}d}"


def _ensure_item_price_brand_field():
    _upsert_property_setter("Item Price", "brand", "fetch_from", "", "Data")
    _upsert_property_setter("Item Price", "brand", "read_only", "0", "Check")
    frappe.clear_cache(doctype="Item Price")


def _upsert_property_setter(doctype: str, fieldname: str, property_name: str, value, property_type: str):
    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "field_name": fieldname, "property": property_name},
        "name",
    )
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocField"
    setter.field_name = fieldname
    setter.property = property_name
    setter.property_type = property_type
    setter.value = value
    if existing:
        setter.save(ignore_permissions=True)
    else:
        setter.insert(ignore_permissions=True)


def _ensure_price_lists(summary, caches, dry_run: bool):
    for spec in PRICE_LISTS.values():
        name = spec["name"]
        if name in caches["price_lists"]:
            if not dry_run:
                doc = frappe.get_doc("Price List", name)
                doc.currency = spec["currency"]
                doc.selling = spec["selling"]
                doc.buying = spec["buying"]
                doc.enabled = 1
                doc.save(ignore_permissions=True)
            continue

        summary["new_price_lists"].append(name)
        caches["price_lists"].add(name)
        if not dry_run:
            frappe.get_doc(
                {
                    "doctype": "Price List",
                    "price_list_name": name,
                    "currency": spec["currency"],
                    "selling": spec["selling"],
                    "buying": spec["buying"],
                    "enabled": 1,
                }
            ).insert(ignore_permissions=True)


def _ensure_uom(name: str, summary, caches, dry_run: bool):
    existing = caches["uom_by_key"].get(_key(name))
    if existing:
        return existing
    if name in caches["uoms"]:
        return name
    summary["new_uoms"].append(name)
    caches["uoms"].add(name)
    caches["uom_by_key"][_key(name)] = name
    if not dry_run:
        frappe.get_doc({"doctype": "UOM", "uom_name": name, "enabled": 1}).insert(ignore_permissions=True)
    return name


def _ensure_brand(name: str, summary, caches, dry_run: bool):
    existing = caches["brand_by_key"].get(_key(name))
    if existing:
        return existing
    if not name or name in caches["brands"]:
        return name
    summary["new_brands"].append(name)
    caches["brands"].add(name)
    caches["brand_by_key"][_key(name)] = name
    if not dry_run:
        doc = frappe.new_doc("Brand")
        doc.brand = name
        doc.insert(ignore_permissions=True)
    return name


def _ensure_supplier(name: str, summary, caches, dry_run: bool):
    existing = caches["supplier_by_key"].get(_key(name))
    if existing:
        return existing
    if not name or name in caches["suppliers"]:
        return name
    summary["new_suppliers"].append(name)
    caches["suppliers"].add(name)
    caches["supplier_by_key"][_key(name)] = name
    if not dry_run:
        doc = frappe.new_doc("Supplier")
        doc.supplier_name = name
        doc.supplier_type = "Company"
        doc.supplier_group = caches["supplier_group"]
        doc.insert(ignore_permissions=True)
    return name


def _ensure_item_group(name: str, summary, caches, dry_run: bool):
    existing = caches["item_group_by_key"].get(_key(name))
    if existing:
        return existing
    if name in caches["item_groups"]:
        return name
    summary["new_item_groups"].append(name)
    caches["item_groups"].add(name)
    caches["item_group_by_key"][_key(name)] = name
    if not dry_run:
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return name


def _ensure_item_category(name: str, summary, caches, virtual_sequences, dry_run: bool):
    if name in caches["item_categories"]:
        return name
    abbreviation = _category_abbreviation(name)
    existing_by_abbreviation = caches["item_category_by_abbreviation"].get(normalize_abbreviation(abbreviation))
    if existing_by_abbreviation:
        if not any(row.get("source") == name for row in summary["item_category_aliases"]):
            summary["item_category_aliases"].append(
                {"source": name, "used_category": existing_by_abbreviation, "abbreviation": abbreviation}
            )
        return existing_by_abbreviation

    summary["new_item_categories"].append({"category": name, "abbreviation": abbreviation})
    caches["item_categories"][name] = {"abbreviation": abbreviation, "sequence_digits": 5, "current_sequence": 0}
    caches["item_category_by_abbreviation"][normalize_abbreviation(abbreviation)] = name
    virtual_sequences[name] = 0
    if not dry_run:
        doc = frappe.new_doc("Item Category")
        doc.category_name = name
        doc.abbreviation = abbreviation
        doc.sequence_digits = 5
        doc.current_sequence = 0
        doc.is_active = 1
        doc.insert(ignore_permissions=True)
    return name


def _ensure_item_material(name: str, summary, caches, dry_run: bool):
    material = _normalize_material_name(name)
    if not material:
        return ""
    existing = caches["item_material_by_key"].get(_key(material))
    if existing:
        return existing
    if material in caches["item_materials"]:
        return material
    summary["new_item_materials"].append(material)
    caches["item_materials"].add(material)
    caches["item_material_by_key"][_key(material)] = material
    if not dry_run:
        doc = frappe.new_doc("Item Material")
        doc.material_name = material
        doc.material_code = material
        doc.is_active = 1
        doc.insert(ignore_permissions=True)
    return material


def _ensure_spec_attribute(name: str, summary, caches, dry_run: bool):
    if name in caches["spec_attributes"]:
        return name
    summary["new_spec_attributes"].append(name)
    caches["spec_attributes"].add(name)
    if not dry_run:
        doc = frappe.new_doc("Item Specification Attribute")
        doc.attribute_name = name
        doc.value_type = "Nombre" if name in NUMERIC_SPEC_ATTRIBUTES else "Texte"
        doc.unit = NUMERIC_SPEC_ATTRIBUTES.get(name, "")
        doc.sequence = 90
        doc.is_filterable = 1
        doc.is_active = 1
        doc.insert(ignore_permissions=True)
    return name


def _ensure_customs_tariff_number(code: str, summary, caches, dry_run: bool):
    if code in caches["customs_tariff_numbers"]:
        return code
    summary["new_customs_tariff_numbers"].append(code)
    caches["customs_tariff_numbers"].add(code)
    if not dry_run:
        frappe.get_doc(
            {"doctype": "Customs Tariff Number", "name": code, "tariff_number": code, "description": code}
        ).insert(ignore_permissions=True)
    return code


def _next_item_code(category: str, caches, virtual_sequences, dry_run: bool):
    if not dry_run:
        return get_next_item_code(category)

    info = caches["item_categories"][category]
    abbreviation = normalize_abbreviation(info["abbreviation"])
    digits = cint(info.get("sequence_digits") or 5)
    virtual_sequences[category] = cint(virtual_sequences.get(category) or 0) + 1
    return f"{abbreviation}-{virtual_sequences[category]:0{digits}d}"


def _load_caches():
    price_lists = set(frappe.get_all("Price List", pluck="name", limit_page_length=0))
    uoms = set(frappe.get_all("UOM", pluck="name", limit_page_length=0))
    brands = set(frappe.get_all("Brand", pluck="name", limit_page_length=0))
    suppliers = set(frappe.get_all("Supplier", pluck="name", limit_page_length=0))
    item_groups = set(frappe.get_all("Item Group", pluck="name", limit_page_length=0))
    item_categories = {
        row.name: row
        for row in frappe.get_all(
            "Item Category",
            fields=["name", "abbreviation", "sequence_digits", "current_sequence"],
            limit_page_length=0,
        )
    }
    item_materials = (
        set(frappe.get_all("Item Material", pluck="name", limit_page_length=0))
        if frappe.db.exists("DocType", "Item Material")
        else set()
    )
    return {
        "price_lists": price_lists,
        "uoms": uoms,
        "uom_by_key": {_key(name): name for name in uoms},
        "brands": brands,
        "brand_by_key": {_key(name): name for name in brands},
        "suppliers": suppliers,
        "supplier_by_key": {_key(name): name for name in suppliers},
        "item_groups": item_groups,
        "item_group_by_key": {_key(name): name for name in item_groups},
        "spec_attributes": set(frappe.get_all("Item Specification Attribute", pluck="name", limit_page_length=0)),
        "customs_tariff_numbers": set(frappe.get_all("Customs Tariff Number", pluck="name", limit_page_length=0)),
        "item_categories": item_categories,
        "item_materials": item_materials,
        "item_material_by_key": {_key(name): name for name in item_materials},
        "item_category_by_abbreviation": {
            normalize_abbreviation(row.get("abbreviation")): name for name, row in item_categories.items()
        },
        "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
        or frappe.db.get_value("Supplier Group", {}, "name"),
    }


def _load_virtual_sequences(caches):
    return {name: cint(row.get("current_sequence") or 0) for name, row in caches["item_categories"].items()}


def _read_xlsx_rows(path: Path, sheet_name: str):
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_path = _resolve_sheet_path(archive, sheet_name)
        root = ET.fromstring(archive.read(sheet_path))

    raw_rows = []
    for row in root.findall(".//a:sheetData/a:row", XML_NS):
        raw_rows.append((cint(row.attrib.get("r")), _read_cells(row, shared_strings)))
    if not raw_rows:
        return []

    headers = _make_headers(raw_rows[0][1])
    rows = []
    for excel_row, cells in raw_rows[1:]:
        row = {"excel_row": excel_row, "headers": headers}
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
    target = relmap[relation_id]
    return "xl/" + target.lstrip("/")


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


def _validate_headers(headers, summary):
    labels = set(headers.values())
    optional = {"PRIX CATALOGUE", "PRIX DE VENTE AU MAROC"}
    missing = []
    for header in sorted(REQUIRED_HEADERS - optional):
        aliases = HEADER_ALIASES.get(header, (header,))
        if not any(alias in labels for alias in aliases):
            missing.append(header)
    if missing:
        summary["warnings"].append({"type": "missing_headers", "headers": missing})


def _analyze_source_codes(rows, summary):
    counts = Counter(_clean(row.get("ITEM CODE")) for row in rows if _clean(row.get("ITEM CODE")))
    summary["duplicate_source_item_codes"] = sorted([code for code, count in counts.items() if count > 1])[:100]


def _category_abbreviation(category: str):
    if category in CATEGORY_ABBREVIATIONS:
        return CATEGORY_ABBREVIATIONS[category]
    words = re.findall(r"[A-Z0-9À-Ý]+", category.upper())
    abbreviation = "".join(word[:1] for word in words[:4]) or "CAT"
    return normalize_abbreviation(abbreviation)[:8] or "CAT"


def _normalize_supplier_currency(value):
    text = _clean(value).upper()
    if text in {"USD", "DOLLAR", "DOLLARS", "$", "US DOLLAR", "US DOLLARS"}:
        return "USD"
    if text in {"MAD", "DH", "DHS", "MAD/DH"}:
        return "MAD"
    if text in {"TRY", "TL", "TURKISH LIRA", "LIRA"}:
        return "TRY"
    return ""


def _parse_price(value, skip_zero_prices: bool):
    text = _clean(value)
    if not text:
        return None, "blank"
    if text.startswith("#"):
        return None, "invalid"
    number = _decimal(text)
    if number is None:
        return None, "invalid"
    if number == 0 and skip_zero_prices:
        return None, "zero"
    return number, ""


def _row_value(row, canonical_header: str):
    for header in HEADER_ALIASES.get(canonical_header, (canonical_header,)):
        value = _clean(row.get(header))
        if value:
            return value
    return ""


def _volume_m3(row):
    volume_m3 = _number(row.get("VOLUME"))
    if volume_m3:
        return volume_m3
    volume_l = _number(row.get("VOLUME (L)"))
    return volume_l / 1000 if volume_l else 0


def _number(value):
    number = _decimal(value)
    return flt(number) if number is not None else 0


def _decimal(value):
    text = _clean(value)
    if not text or text == "-" or text.startswith("#"):
        return None
    text = text.replace(" ", "").replace("\u00a0", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _normalize_hs(value):
    text = _clean(value)
    if not text or text == "-":
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_image_url(value):
    text = _clean(value)
    if not text:
        return ""
    file_id = _google_drive_file_id(text)
    if file_id:
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
    return text


def _google_drive_file_id(value: str) -> str:
    parsed = urlparse(value)
    if "drive.google.com" not in parsed.netloc:
        return ""
    match = re.search(r"/file/d/([^/]+)", parsed.path)
    if match:
        return match.group(1)
    params = parse_qs(parsed.query)
    return (params.get("id") or [""])[0]


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


def _normalize_customs_material(value):
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


def _normalize_material(value):
    return _normalize_material_name(value)


def _clean(value):
    if value is None:
        return ""
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    return "" if text == "-" else text


def _clean_header(value):
    return _clean(value).upper()


def _key(value):
    return _clean(value).casefold()


def _cell_column(cell_ref: str):
    return "".join(ch for ch in cell_ref if ch.isalpha())


def _column_number(column: str):
    result = 0
    for char in column:
        result = result * 26 + ord(char.upper()) - 64
    return result


def _warn(summary, row, message: str):
    if len(summary["warnings"]) < 300:
        summary["warnings"].append(
            {"excel_row": row.get("excel_row"), "source_item_code": _clean(row.get("ITEM CODE")), "message": message}
        )


def _finalize_summary(summary):
    for key in [
        "new_price_lists",
        "new_brands",
        "new_suppliers",
        "new_uoms",
        "new_item_groups",
        "new_item_materials",
        "new_spec_attributes",
        "new_customs_tariff_numbers",
    ]:
        summary[key] = sorted(set(summary[key]))
    summary["item_prices_by_price_list"] = dict(sorted(summary["item_prices_by_price_list"].items()))
    summary["skipped_prices"] = dict(sorted(summary["skipped_prices"].items()))


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no"}
