from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import frappe
from frappe import _
from frappe.utils import cint, flt

from orderlift.orderlift_logistics.utils.item_sequence import normalize_abbreviation
from orderlift.scripts import import_article_excel_catalog as catalog_import


DEFAULT_WORKBOOK = Path("/tmp/data base des articles avec les prix d'achats.xlsx")
DEFAULT_ORIGINAL_WORKBOOK = Path("/tmp/data base des articles.xlsx")
DEFAULT_SHEET = "Database"
CONFIRM_TOKEN = "APPLY_ARTICLE_BUYING_PRICE_SOURCE_OF_TRUTH"
SUPPLIER_PRICE_DENSITY_THRESHOLD_KG_PER_L = Decimal("0.355")

BUYING_PRICE_LISTS = {
    "MAD": {"name": "PRIX FOURNISSEUR MAD", "currency": "MAD", "company_source": "PRIX FOURNISSEUR MAD"},
    "USD_WEIGHT": {"name": "PRIX FOURNISSEUR USD Weight", "currency": "USD", "company_source": "PRIX FOURNISSEUR USD"},
    "USD_VOLUME": {"name": "PRIX FOURNISSEUR USD Volume", "currency": "USD", "company_source": "PRIX FOURNISSEUR USD"},
    "USD_VALUE": {"name": "PRIX FOURNISSEUR USD Value", "currency": "USD", "company_source": "PRIX FOURNISSEUR USD"},
    "TRY_WEIGHT": {"name": "PRIX FOURNISSEUR TRY Weight", "currency": "TRY", "company_source": "PRIX FOURNISSEUR TRY"},
    "TRY_VOLUME": {"name": "PRIX FOURNISSEUR TRY Volume", "currency": "TRY", "company_source": "PRIX FOURNISSEUR TRY"},
    "TRY_VALUE": {"name": "PRIX FOURNISSEUR TRY Value", "currency": "TRY", "company_source": "PRIX FOURNISSEUR TRY"},
}
SUPPLIER_BUYING_PRICE_LIST_KEYS = {
    "MAD": {"default": "MAD"},
    "USD": {"Weight": "USD_WEIGHT", "Volume": "USD_VOLUME", "Value": "USD_VALUE"},
    "TRY": {"Weight": "TRY_WEIGHT", "Volume": "TRY_VOLUME", "Value": "TRY_VALUE"},
}
LEGACY_BUYING_PRICE_LIST_NAMES = {"PRIX FOURNISSEUR USD", "PRIX FOURNISSEUR TRY"}
BUYING_PRICE_LIST_NAMES = {row["name"] for row in BUYING_PRICE_LISTS.values()} | LEGACY_BUYING_PRICE_LIST_NAMES
SOURCE_OF_TRUTH_BUYING_PRICE_LIST_NAMES = {row["name"] for row in BUYING_PRICE_LISTS.values()}
SELLING_PRICE_LISTS = {"PRIX CATALOGUE", "PRIX DE VENTE AU MAROC"}

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
SPEC_COLUMNS = ["SIZE", "TYPE", "FINITION", "CAPACITY", "VITESSE", "POWER", "AMPÉRAGE", "VOLTAGE"]
XML_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@frappe.whitelist()
def run(
    workbook_path: str | None = None,
    original_workbook_path: str | None = None,
    sheet_name: str = DEFAULT_SHEET,
    original_sheet_name: str | None = None,
    dry_run: int | str = 1,
    confirm: str | None = None,
    delete_selling_prices: int | str = 1,
    delete_stale_buying_prices: int | str = 1,
    delete_unlisted_buying_prices: int | str = 0,
    create_new_items: int | str = 1,
    delete_old_items: int | str = 1,
    update_images: int | str = 0,
    limit: int | str | None = None,
) -> dict:
    frappe.only_for("System Manager")
    """Update imported article buying prices from the refreshed workbook.

    This is intentionally separate from import_article_excel_catalog.run(), which creates items.
    Matching uses the original workbook to reconstruct generated item codes, then applies only
    exact row-identity matches from the new workbook.
    """

    dry_run = _truthy(dry_run)
    original_sheet_name = original_sheet_name or sheet_name
    delete_selling_prices = _truthy(delete_selling_prices)
    delete_stale_buying_prices = _truthy(delete_stale_buying_prices)
    delete_unlisted_buying_prices = _truthy(delete_unlisted_buying_prices)
    create_new_items = _truthy(create_new_items)
    delete_old_items = _truthy(delete_old_items)
    update_images = _truthy(update_images)
    limit = cint(limit or 0)

    if not dry_run and confirm != CONFIRM_TOKEN:
        frappe.throw(_("Pass confirm={0} to apply article buying price updates.").format(CONFIRM_TOKEN))

    workbook = Path(workbook_path or DEFAULT_WORKBOOK)
    original_workbook = Path(original_workbook_path or DEFAULT_ORIGINAL_WORKBOOK)
    if not workbook.exists():
        frappe.throw(_("Workbook not found: {0}").format(workbook))
    if not original_workbook.exists():
        frappe.throw(_("Original workbook not found: {0}").format(original_workbook))

    new_rows = _valid_item_rows(_read_xlsx_rows(workbook, sheet_name))
    original_rows = _valid_item_rows(_read_xlsx_rows(original_workbook, original_sheet_name))
    if limit:
        new_rows = new_rows[:limit]

    summary = _new_summary(
        workbook,
        original_workbook,
        sheet_name,
        original_sheet_name,
        dry_run,
        delete_selling_prices,
        delete_stale_buying_prices,
        delete_unlisted_buying_prices,
        create_new_items,
        delete_old_items,
        update_images,
        limit,
    )
    summary["new_rows"] = len(new_rows)
    summary["original_rows"] = len(original_rows)

    caches = _load_caches()
    item_caches = catalog_import._load_caches()
    virtual_sequences = catalog_import._load_virtual_sequences(item_caches)
    _ensure_buying_price_lists(summary, caches, dry_run=dry_run)
    if not dry_run:
        _ensure_item_price_brand_field()

    original_map = _build_original_item_map(original_rows, caches)
    matched_rows, unmatched_new = _match_new_rows(new_rows, original_map)
    source_matched_rows, unmatched_new = _match_unmatched_by_unique_source_code(unmatched_new, original_map)
    identity_matched_rows, unmatched_new = _match_unmatched_by_unique_row_identity(unmatched_new, original_map)
    loose_identity_matched_rows, unmatched_new = _match_unmatched_by_unique_loose_identity(unmatched_new, original_map)
    summary["matched_rows"] = len(matched_rows)
    summary["source_matched_changed_rows"] = len(source_matched_rows)
    summary["row_identity_matched_changed_source_rows"] = len(identity_matched_rows)
    summary["loose_identity_matched_changed_rows"] = len(loose_identity_matched_rows)
    summary["unmatched_new_rows"] = len(unmatched_new)
    summary["unmatched_original_rows"] = sum(len(rows) for rows in original_map.values())
    summary["unmatched_new_samples"] = _sample_rows(unmatched_new)
    summary["unmatched_original_samples"] = _sample_original_rows(original_map)

    imported_item_codes = [row["item_code"] for rows in original_map.values() for row in rows]
    imported_item_codes.extend(row["item_code"] for row, _new_row in matched_rows)
    imported_item_codes.extend(row["item_code"] for row, _new_row in source_matched_rows)
    imported_item_codes.extend(row["item_code"] for row, _new_row in identity_matched_rows)
    imported_item_codes.extend(row["item_code"] for row, _new_row in loose_identity_matched_rows)
    imported_item_codes = sorted(set(imported_item_codes))
    desired_buying_price_keys = set()

    for original, new_row in matched_rows:
        if _update_existing_item(
            original,
            new_row,
            summary,
            item_caches,
            dry_run=dry_run,
            create_missing=create_new_items,
            update_images=update_images,
        ):
            _process_matched_row(
                original,
                new_row,
                summary,
                caches,
                dry_run=dry_run,
                delete_stale_buying_prices=delete_stale_buying_prices,
                desired_buying_price_keys=desired_buying_price_keys,
                item_will_exist=True,
            )

    for original, new_row in source_matched_rows:
        summary["items_updated_from_source_code"] += 1
        if _update_existing_item(
            original,
            new_row,
            summary,
            item_caches,
            dry_run=dry_run,
            create_missing=create_new_items,
            update_images=update_images,
        ):
            _process_matched_row(
                original,
                new_row,
                summary,
                caches,
                dry_run=dry_run,
                delete_stale_buying_prices=delete_stale_buying_prices,
                desired_buying_price_keys=desired_buying_price_keys,
                item_will_exist=True,
            )

    for original, new_row in identity_matched_rows:
        summary["items_updated_from_row_identity"] += 1
        if _update_existing_item(
            original,
            new_row,
            summary,
            item_caches,
            dry_run=dry_run,
            create_missing=create_new_items,
            update_images=update_images,
        ):
            _process_matched_row(
                original,
                new_row,
                summary,
                caches,
                dry_run=dry_run,
                delete_stale_buying_prices=delete_stale_buying_prices,
                desired_buying_price_keys=desired_buying_price_keys,
                item_will_exist=True,
            )

    for original, new_row in loose_identity_matched_rows:
        summary["items_updated_from_loose_identity"] += 1
        if _update_existing_item(
            original,
            new_row,
            summary,
            item_caches,
            dry_run=dry_run,
            create_missing=create_new_items,
            update_images=update_images,
        ):
            _process_matched_row(
                original,
                new_row,
                summary,
                caches,
                dry_run=dry_run,
                delete_stale_buying_prices=delete_stale_buying_prices,
                desired_buying_price_keys=desired_buying_price_keys,
                item_will_exist=True,
            )

    if create_new_items:
        for row in unmatched_new:
            item_info = _find_existing_item_for_new_row(row, item_caches)
            if item_info:
                summary["existing_new_items_reused"] += 1
                item_will_exist = _update_existing_item(
                    item_info,
                    row,
                    summary,
                    item_caches,
                    dry_run=dry_run,
                    create_missing=False,
                    update_images=update_images,
                )
            else:
                item_info = _create_new_item(row, summary, item_caches, virtual_sequences, dry_run=dry_run)
                item_will_exist = bool(item_info)
            if item_info and item_will_exist:
                imported_item_codes.append(item_info["item_code"])
                _remove_original_item_code_from_map(original_map, item_info["item_code"])
                _process_matched_row(
                    item_info,
                    row,
                    summary,
                    caches,
                    dry_run=dry_run,
                    delete_stale_buying_prices=delete_stale_buying_prices,
                    desired_buying_price_keys=desired_buying_price_keys,
                    item_will_exist=True,
                )

    if delete_old_items:
        _delete_unmatched_original_items(original_map, summary, dry_run=dry_run)

    if delete_selling_prices:
        _delete_selling_prices(imported_item_codes, summary, dry_run=dry_run)
    if delete_unlisted_buying_prices:
        _delete_unlisted_buying_prices(desired_buying_price_keys, summary, dry_run=dry_run)

    _finalize_summary(summary)
    if not dry_run:
        frappe.db.commit()
    return summary


def _new_summary(
    workbook: Path,
    original_workbook: Path,
    sheet_name: str,
    original_sheet_name: str,
    dry_run: bool,
    delete_selling_prices: bool,
    delete_stale_buying_prices: bool,
    delete_unlisted_buying_prices: bool,
    create_new_items: bool,
    delete_old_items: bool,
    update_images: bool,
    limit: int,
) -> dict:
    return {
        "workbook_path": str(workbook),
        "original_workbook_path": str(original_workbook),
        "sheet_name": sheet_name,
        "original_sheet_name": original_sheet_name,
        "dry_run": dry_run,
        "confirm_required_for_apply": CONFIRM_TOKEN,
        "delete_selling_prices": delete_selling_prices,
        "delete_stale_buying_prices": delete_stale_buying_prices,
        "delete_unlisted_buying_prices": delete_unlisted_buying_prices,
        "create_new_items": create_new_items,
        "delete_old_items": delete_old_items,
        "update_images": update_images,
        "limit": limit or None,
        "original_rows": 0,
        "new_rows": 0,
        "matched_rows": 0,
        "source_matched_changed_rows": 0,
        "row_identity_matched_changed_source_rows": 0,
        "unmatched_new_rows": 0,
        "unmatched_original_rows": 0,
        "items_missing": [],
        "items_updated": 0,
        "items_created": 0,
        "existing_new_items_reused": 0,
        "items_updated_from_source_code": 0,
        "items_updated_from_row_identity": 0,
        "items_updated_from_loose_identity": 0,
        "old_items_deleted": 0,
        "old_items_disabled": 0,
        "old_item_delete_failures": [],
        "old_item_disable_failures": [],
        "old_item_prices_deleted": 0,
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
        "spec_rows_created": 0,
        "packaging_profiles_created": 0,
        "generated_item_code_samples": [],
        "images_preserved": 0,
        "images_updated_from_source": 0,
        "buying_prices_created": 0,
        "buying_prices_updated": 0,
        "buying_prices_unchanged": 0,
        "buying_prices_deleted_stale": 0,
        "buying_prices_deleted_unlisted": 0,
        "selling_prices_deleted": 0,
        "blank_buying_prices": 0,
        "invalid_buying_prices": 0,
        "buying_prices_by_price_list": defaultdict(int),
        "supplier_price_routes": defaultdict(int),
        "supplier_price_value_route_samples": [],
        "unlisted_buying_price_delete_samples": [],
        "deleted_selling_by_price_list": defaultdict(int),
        "unmatched_new_samples": [],
        "unmatched_original_samples": [],
        "changes": [],
        "warnings": [],
    }


def _process_matched_row(
    original: dict,
    row: dict,
    summary: dict,
    caches: dict,
    dry_run: bool,
    delete_stale_buying_prices: bool,
    desired_buying_price_keys: set | None = None,
    item_will_exist: bool = False,
) -> None:
    item_code = original["item_code"]
    if not item_will_exist and not frappe.db.exists("Item", item_code):
        _append_limited(summary["items_missing"], {"item_code": item_code, "source_item_code": _clean(row.get("ITEM CODE"))})
        return

    currency = _normalize_supplier_currency(_row_value(row, "DEVIS PRIX FOURNISSEUR"))
    rate, reason = _parse_price(_row_value(row, "PRIX FOURNISSEUR"))
    desired_price_list = ""

    if currency and currency not in SUPPLIER_BUYING_PRICE_LIST_KEYS:
        summary["invalid_buying_prices"] += 1
        _warn(summary, row, f"Unsupported supplier currency {currency!r}.")
        return

    if reason:
        summary["blank_buying_prices" if reason == "blank" else "invalid_buying_prices"] += 1
        if delete_stale_buying_prices:
            _delete_stale_buying_prices(item_code, desired_price_list, summary, dry_run=dry_run)
        return

    if not currency:
        summary["invalid_buying_prices"] += 1
        _warn(summary, row, "Supplier currency is required when supplier price is present.")
        return

    desired_price_list, route_info = _resolve_supplier_buying_price_list(currency, row)
    if desired_buying_price_keys is not None:
        desired_buying_price_keys.add((item_code, desired_price_list))
    _record_supplier_price_route(summary, currency, route_info)
    supplier = _ensure_supplier(_clean(row.get("DEFAULT SUPPLIER")), summary, caches, dry_run=dry_run)
    brand = _ensure_brand(_clean(row.get("BRAND")), summary, caches, dry_run=dry_run)
    stock_uom = original.get("stock_uom") or _clean(row.get("DEFAULT UNIT OF MEASURE"))

    existing_name = _find_existing_buying_price(item_code, desired_price_list, supplier)
    values = {
        "doctype": "Item Price",
        "item_code": item_code,
        "price_list": desired_price_list,
        "uom": stock_uom,
        "price_list_rate": float(rate),
        "supplier": supplier,
        "brand": brand,
    }

    if existing_name:
        doc = frappe.get_doc("Item Price", existing_name)
        changed = _item_price_changed(doc, values)
        if changed:
            summary["buying_prices_updated"] += 1
            _record_change(summary, "update", item_code, row, desired_price_list, doc, values, route_info=route_info)
            if not dry_run:
                doc.update(values)
                doc.save(ignore_permissions=True)
                if brand:
                    frappe.db.set_value("Item Price", doc.name, "brand", brand, update_modified=False)
        else:
            summary["buying_prices_unchanged"] += 1
    else:
        summary["buying_prices_created"] += 1
        _record_change(summary, "create", item_code, row, desired_price_list, None, values, route_info=route_info)
        if not dry_run:
            doc = frappe.get_doc(values).insert(ignore_permissions=True)
            if brand:
                frappe.db.set_value("Item Price", doc.name, "brand", brand, update_modified=False)

    summary["buying_prices_by_price_list"][desired_price_list] += 1
    if delete_stale_buying_prices:
        _delete_stale_buying_prices(item_code, desired_price_list, summary, dry_run=dry_run)


def _resolve_supplier_buying_price_list(currency: str, row: dict) -> tuple[str, dict]:
    currency = (currency or "").strip().upper()
    route_keys = SUPPLIER_BUYING_PRICE_LIST_KEYS.get(currency) or {}
    if "default" in route_keys:
        key = route_keys["default"]
        return BUYING_PRICE_LISTS[key]["name"], {"route": "Default", "density": None, "weight_kg": None, "volume_l": None}

    route, density, weight_kg, volume_l = _resolve_supplier_price_route(row)
    key = route_keys.get(route)
    if not key:
        frappe.throw(_("No buying price list configured for currency {0} route {1}.").format(currency, route))
    return BUYING_PRICE_LISTS[key]["name"], {
        "route": route,
        "density": density,
        "weight_kg": weight_kg,
        "volume_l": volume_l,
    }


def _resolve_supplier_price_route(row: dict) -> tuple[str, Decimal | None, Decimal | None, Decimal | None]:
    weight_kg = _packaging_weight_kg(row)
    volume_l = _packaging_volume_liters(row)
    if not weight_kg or not volume_l or weight_kg <= 0 or volume_l <= 0:
        return "Value", None, weight_kg, volume_l

    density = weight_kg / volume_l
    if density >= SUPPLIER_PRICE_DENSITY_THRESHOLD_KG_PER_L:
        return "Weight", density, weight_kg, volume_l
    return "Volume", density, weight_kg, volume_l


def _packaging_weight_kg(row: dict) -> Decimal | None:
    return _decimal(_row_value(row, "POIDS"))


def _packaging_volume_liters(row: dict) -> Decimal | None:
    volume_l = _decimal(row.get("VOLUME"))
    if volume_l:
        return volume_l
    volume_l = _decimal(row.get("VOLUME (L)"))
    return volume_l


def _record_supplier_price_route(summary: dict, currency: str, route_info: dict) -> None:
    route = (route_info or {}).get("route") or ""
    if not route or route == "Default":
        return
    key = f"{currency}_{route}"
    summary["supplier_price_routes"][key] += 1
    if route == "Value":
        _append_limited(
            summary["supplier_price_value_route_samples"],
            {
                "currency": currency,
                "weight_kg": _decimal_to_float((route_info or {}).get("weight_kg")),
                "volume_l": _decimal_to_float((route_info or {}).get("volume_l")),
            },
        )


def _find_existing_buying_price(item_code: str, price_list: str, supplier: str) -> str | None:
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
    for row in rows:
        if _key(row.get("supplier")) == supplier_key:
            return row.name
    return rows[0].name


def _item_price_changed(doc, values: dict) -> bool:
    current_rate = _decimal(doc.get("price_list_rate")) or Decimal("0")
    desired_rate = _decimal(values.get("price_list_rate")) or Decimal("0")
    return any(
        [
            abs(current_rate - desired_rate) > Decimal("0.000001"),
            _key(doc.get("uom")) != _key(values.get("uom")),
            _key(doc.get("supplier")) != _key(values.get("supplier")),
            _key(doc.get("brand")) != _key(values.get("brand")),
        ]
    )


def _delete_stale_buying_prices(item_code: str, desired_price_list: str, summary: dict, dry_run: bool) -> None:
    stale_names = frappe.get_all(
        "Item Price",
        filters={"item_code": item_code, "price_list": ["in", sorted(BUYING_PRICE_LIST_NAMES - {desired_price_list})]},
        pluck="name",
        limit_page_length=0,
    )
    summary["buying_prices_deleted_stale"] += len(stale_names)
    if not dry_run:
        for name in stale_names:
            frappe.delete_doc("Item Price", name, ignore_permissions=True)


def _delete_selling_prices(item_codes: list[str], summary: dict, dry_run: bool) -> None:
    if not item_codes:
        return
    for chunk in _chunks(item_codes, 400):
        rows = frappe.get_all(
            "Item Price",
            filters={"item_code": ["in", chunk], "price_list": ["in", sorted(SELLING_PRICE_LISTS)]},
            fields=["name", "price_list"],
            limit_page_length=0,
        )
        summary["selling_prices_deleted"] += len(rows)
        for row in rows:
            summary["deleted_selling_by_price_list"][row.price_list] += 1
        if not dry_run:
            for row in rows:
                frappe.delete_doc("Item Price", row.name, ignore_permissions=True)


def _delete_unlisted_buying_prices(desired_keys: set[tuple[str, str]], summary: dict, dry_run: bool) -> None:
    rows = frappe.get_all(
        "Item Price",
        filters={"price_list": ["in", sorted(SOURCE_OF_TRUTH_BUYING_PRICE_LIST_NAMES)]},
        fields=["name", "item_code", "price_list", "price_list_rate", "supplier"],
        limit_page_length=0,
    )
    for row in rows:
        if row.price_list not in SOURCE_OF_TRUTH_BUYING_PRICE_LIST_NAMES:
            continue
        if (row.item_code, row.price_list) in desired_keys:
            continue
        summary["buying_prices_deleted_unlisted"] += 1
        _append_limited(
            summary["unlisted_buying_price_delete_samples"],
            {
                "item_code": row.item_code,
                "price_list": row.price_list,
                "rate": flt(row.price_list_rate),
                "supplier": _clean(row.get("supplier")),
            },
            limit=200,
        )
        if not dry_run:
            frappe.delete_doc("Item Price", row.name, ignore_permissions=True)


def _delete_unmatched_original_items(original_map: dict, summary: dict, dry_run: bool) -> None:
    for rows in original_map.values():
        for row in rows:
            item_code = row["item_code"]
            if not frappe.db.exists("Item", item_code):
                continue
            price_names = frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name", limit_page_length=0)
            summary["old_item_prices_deleted"] += len(price_names)
            if dry_run:
                summary["old_items_deleted"] += 1
                continue
            try:
                for price_name in price_names:
                    frappe.delete_doc("Item Price", price_name, ignore_permissions=True)
                frappe.delete_doc("Item", item_code, ignore_permissions=True)
                summary["old_items_deleted"] += 1
            except Exception as exc:
                disabled = _disable_old_item_after_delete_failure(item_code, summary)
                _append_limited(
                    summary["old_item_delete_failures"],
                    {
                        "item_code": item_code,
                        "source_item_code": row.get("source_item_code"),
                        "error": str(exc),
                        "disabled": disabled,
                    },
                    limit=300,
                )


def _disable_old_item_after_delete_failure(item_code: str, summary: dict) -> bool:
    try:
        frappe.db.set_value("Item", item_code, "disabled", 1)
        summary["old_items_disabled"] += 1
        return True
    except Exception as exc:
        _append_limited(summary["old_item_disable_failures"], {"item_code": item_code, "error": str(exc)}, limit=300)
        return False


def _update_existing_item(
    original: dict,
    row: dict,
    summary: dict,
    caches: dict,
    dry_run: bool,
    create_missing: bool = False,
    update_images: bool = False,
) -> bool:
    item_code = original["item_code"]
    item_exists = bool(frappe.db.exists("Item", item_code))
    category = catalog_import._ensure_item_category(
        _clean(row.get("ITEM GROUP")), summary, caches, defaultdict(int), dry_run=dry_run
    )
    item_group = catalog_import._ensure_item_group(_clean(row.get("ITEM CATEGORY")), summary, caches, dry_run=dry_run)
    stock_uom = catalog_import._ensure_uom(_clean(row.get("DEFAULT UNIT OF MEASURE")), summary, caches, dry_run=dry_run)
    original["stock_uom"] = stock_uom
    for attribute in catalog_import.SPEC_COLUMNS.values():
        catalog_import._ensure_spec_attribute(attribute, summary, caches, dry_run=dry_run)

    item_doc = catalog_import._build_item_doc(row, item_code, item_group, stock_uom, category, summary, caches, dry_run=dry_run)
    catalog_import._append_specs(item_doc, row, summary)
    catalog_import._append_packaging_profile(item_doc, row, stock_uom, summary)

    if not item_exists:
        if not create_missing:
            _append_limited(summary["items_missing"], {"item_code": item_code, "source_item_code": _clean(row.get("ITEM CODE"))})
            return False
        summary["items_created"] += 1
        if not dry_run:
            item_doc.insert(ignore_permissions=True)
        return True

    summary["items_updated"] += 1
    if dry_run:
        return True

    doc = frappe.get_doc("Item", item_code)
    _preserve_existing_local_image(doc, item_doc, summary, update_images=update_images)
    catalog_import._update_item_doc(doc, item_doc)
    doc.save(ignore_permissions=True)
    _set_source_image(item_code, item_doc, summary, update_images=update_images)
    return True


def _preserve_existing_local_image(existing_doc, source_doc, summary: dict, update_images: bool) -> None:
    if update_images:
        return
    current_image = existing_doc.get("image") or ""
    source_image = source_doc.get("image") or ""
    if current_image.startswith("/files/") and source_image.startswith("http"):
        source_doc.set("image", current_image)
        summary["images_preserved"] += 1


def _set_source_image(item_code: str, source_doc, summary: dict, update_images: bool) -> None:
    source_image = _clean(source_doc.get("image"))
    if not update_images or not source_image:
        return
    frappe.db.set_value("Item", item_code, "image", source_image, update_modified=False)
    summary["images_updated_from_source"] += 1


def _create_new_item(row: dict, summary: dict, caches: dict, virtual_sequences: dict, dry_run: bool) -> dict | None:
    item_name = _row_value(row, "ITEM NAME")
    erp_item_group = _clean(row.get("ITEM CATEGORY"))
    stock_uom = _clean(row.get("DEFAULT UNIT OF MEASURE"))
    category_article = _clean(row.get("ITEM GROUP"))
    if not item_name or not erp_item_group or not stock_uom or not category_article:
        return None

    item_group = catalog_import._ensure_item_group(erp_item_group, summary, caches, dry_run=dry_run)
    category = catalog_import._ensure_item_category(category_article, summary, caches, virtual_sequences, dry_run=dry_run)
    stock_uom = catalog_import._ensure_uom(stock_uom, summary, caches, dry_run=dry_run)
    for attribute in catalog_import.SPEC_COLUMNS.values():
        catalog_import._ensure_spec_attribute(attribute, summary, caches, dry_run=dry_run)
    item_code = catalog_import._next_item_code(category, caches, virtual_sequences, dry_run=dry_run)
    if len(summary["generated_item_code_samples"]) < 100:
        summary["generated_item_code_samples"].append(
            {"excel_row": row.get("excel_row"), "source_item_code": _clean(row.get("ITEM CODE")), "item_code": item_code}
        )
    item_doc = catalog_import._build_item_doc(row, item_code, item_group, stock_uom, category, summary, caches, dry_run=dry_run)
    catalog_import._append_specs(item_doc, row, summary)
    catalog_import._append_packaging_profile(item_doc, row, stock_uom, summary)
    summary["items_created"] += 1
    if not dry_run:
        item_doc.insert(ignore_permissions=True)
    return {"item_code": item_code, "source_item_code": _clean(row.get("ITEM CODE")), "stock_uom": stock_uom, "category": category}


def _find_existing_item_for_new_row(row: dict, caches: dict) -> dict | None:
    category = _resolve_item_category(_clean(row.get("ITEM GROUP")), caches)["name"]
    filters = {
        "item_name": _row_value(row, "ITEM NAME"),
        "item_group": _clean(row.get("ITEM CATEGORY")),
        "stock_uom": _clean(row.get("DEFAULT UNIT OF MEASURE")),
        "custom_item_category": category,
    }
    if not all(filters.values()):
        return None
    rows = frappe.get_all("Item", filters=filters, fields=["name", "stock_uom"], limit_page_length=2)
    if len(rows) != 1:
        return None
    return {
        "item_code": rows[0].name,
        "source_item_code": _clean(row.get("ITEM CODE")),
        "stock_uom": rows[0].stock_uom,
        "category": category,
    }


def _ensure_buying_price_lists(summary: dict, caches: dict, dry_run: bool) -> None:
    for spec in BUYING_PRICE_LISTS.values():
        name = spec["name"]
        company = _resolve_price_list_company(spec)
        if name in caches["price_lists"]:
            if not dry_run:
                doc = frappe.get_doc("Price List", name)
                doc.currency = spec["currency"]
                doc.buying = 1
                doc.selling = 0
                doc.enabled = 1
                _set_price_list_company(doc, company)
                doc.save(ignore_permissions=True)
            continue
        summary["new_price_lists"].append(name)
        caches["price_lists"].add(name)
        if not dry_run:
            doc = frappe.get_doc(
                {
                    "doctype": "Price List",
                    "price_list_name": name,
                    "currency": spec["currency"],
                    "buying": 1,
                    "selling": 0,
                    "enabled": 1,
                }
            )
            _set_price_list_company(doc, company)
            doc.insert(ignore_permissions=True)


def _resolve_price_list_company(spec: dict) -> str:
    if not _db_has_column("Price List", "custom_company"):
        return ""
    company = (spec.get("company") or "").strip()
    if company:
        return company
    source = (spec.get("company_source") or "").strip()
    if not source:
        return ""
    return (frappe.db.get_value("Price List", source, "custom_company") or "").strip()


def _set_price_list_company(doc, company: str) -> None:
    company = (company or "").strip()
    if not company or not _doc_has_field(doc, "custom_company"):
        return
    doc.set("custom_company", company)


def _ensure_brand(name: str, summary: dict, caches: dict, dry_run: bool) -> str:
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


def _ensure_supplier(name: str, summary: dict, caches: dict, dry_run: bool) -> str:
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


def _load_caches() -> dict:
    price_lists = set(frappe.get_all("Price List", pluck="name", limit_page_length=0))
    brands = set(frappe.get_all("Brand", pluck="name", limit_page_length=0))
    suppliers = set(frappe.get_all("Supplier", pluck="name", limit_page_length=0))
    item_categories = {
        row.name: row
        for row in frappe.get_all(
            "Item Category",
            fields=["name", "abbreviation", "sequence_digits", "current_sequence"],
            limit_page_length=0,
        )
    }
    return {
        "price_lists": price_lists,
        "brands": brands,
        "brand_by_key": {_key(name): name for name in brands},
        "suppliers": suppliers,
        "supplier_by_key": {_key(name): name for name in suppliers},
        "item_categories": item_categories,
        "item_category_by_abbreviation": {
            normalize_abbreviation(row.get("abbreviation")): name for name, row in item_categories.items()
        },
        "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
        or frappe.db.get_value("Supplier Group", {}, "name"),
    }


def _build_original_item_map(rows: list[dict], caches: dict) -> dict:
    sequence_by_category = defaultdict(int)
    mapped_rows = defaultdict(deque)
    for row in rows:
        category = _resolve_item_category(_clean(row.get("ITEM GROUP")), caches)
        sequence_by_category[category["name"]] += 1
        item_code = _format_item_code(category, sequence_by_category[category["name"]])
        mapped_rows[_row_signature(row)].append(
            {
                "item_code": item_code,
                "source_item_code": _clean(row.get("ITEM CODE")),
                "stock_uom": _clean(row.get("DEFAULT UNIT OF MEASURE")),
                "category": category["name"],
                "category_key": _source_category_key(row),
                "identity_signature": _row_identity_signature(row),
                "loose_identity_signature": _row_loose_identity_signature(row),
                "excel_row": row.get("excel_row"),
            }
        )
    return mapped_rows


def _match_new_rows(rows: list[dict], original_map: dict) -> tuple[list[tuple[dict, dict]], list[dict]]:
    matched = []
    unmatched = []
    for row in rows:
        signature = _row_signature(row)
        if original_map.get(signature):
            matched.append((original_map[signature].popleft(), row))
        else:
            unmatched.append(row)
    return matched, unmatched


def _match_unmatched_by_unique_source_code(rows: list[dict], original_map: dict) -> tuple[list[tuple[dict, dict]], list[dict]]:
    by_source = defaultdict(list)
    for original_rows in original_map.values():
        for original in original_rows:
            by_source[(_key(original.get("source_item_code")), original.get("category_key"))].append(original)

    matched = []
    unmatched = []
    for row in rows:
        source_key = (_key(row.get("ITEM CODE")), _source_category_key(row))
        candidates = by_source.get(source_key) or []
        if source_key[0] and len(candidates) == 1:
            original = candidates[0]
            _remove_original_from_map(original_map, original)
            by_source[source_key] = []
            matched.append((original, row))
        else:
            unmatched.append(row)
    return matched, unmatched


def _match_unmatched_by_unique_row_identity(rows: list[dict], original_map: dict) -> tuple[list[tuple[dict, dict]], list[dict]]:
    by_identity = defaultdict(list)
    for original_rows in original_map.values():
        for original in original_rows:
            by_identity[original["identity_signature"]].append(original)

    matched = []
    unmatched = []
    for row in rows:
        candidates = by_identity.get(_row_identity_signature(row)) or []
        if len(candidates) == 1:
            original = candidates[0]
            _remove_original_from_map(original_map, original)
            by_identity[original["identity_signature"]] = []
            matched.append((original, row))
        else:
            unmatched.append(row)
    return matched, unmatched


def _match_unmatched_by_unique_loose_identity(rows: list[dict], original_map: dict) -> tuple[list[tuple[dict, dict]], list[dict]]:
    by_identity = defaultdict(list)
    for original_rows in original_map.values():
        for original in original_rows:
            by_identity[original["loose_identity_signature"]].append(original)

    new_counts = Counter(_row_loose_identity_signature(row) for row in rows)
    matched = []
    unmatched = []
    for row in rows:
        signature = _row_loose_identity_signature(row)
        candidates = by_identity.get(signature) or []
        if new_counts[signature] == 1 and len(candidates) == 1:
            original = candidates[0]
            _remove_original_from_map(original_map, original)
            by_identity[signature] = []
            matched.append((original, row))
        else:
            unmatched.append(row)
    return matched, unmatched


def _remove_original_from_map(original_map: dict, original: dict) -> None:
    for rows in original_map.values():
        for existing in list(rows):
            if existing is original:
                rows.remove(existing)
                return


def _remove_original_item_code_from_map(original_map: dict, item_code: str) -> None:
    if not item_code:
        return
    for rows in original_map.values():
        for existing in list(rows):
            if existing.get("item_code") == item_code:
                rows.remove(existing)


def _row_signature(row: dict) -> tuple:
    return tuple(
        [
            _key(row.get("ITEM CODE")),
            _source_category_key(row),
            _key(_row_value(row, "ITEM NAME")),
            _key(row.get("ITEM GROUP")),
            _key(row.get("DEFAULT UNIT OF MEASURE")),
        ]
        + [_key(row.get(column)) for column in SPEC_COLUMNS]
    )


def _row_identity_signature(row: dict) -> tuple:
    return tuple(
        [
            _source_category_key(row),
            _key(_row_value(row, "ITEM NAME")),
            _key(row.get("ITEM GROUP")),
            _key(row.get("DEFAULT UNIT OF MEASURE")),
        ]
        + [_key(row.get(column)) for column in SPEC_COLUMNS]
    )


def _row_loose_identity_signature(row: dict) -> tuple:
    return tuple(
        [
            _source_category_key(row),
            _key(_row_value(row, "ITEM NAME")),
            _key(row.get("ITEM GROUP")),
        ]
        + [_key(row.get(column)) for column in SPEC_COLUMNS]
    )


def _source_category_key(row: dict) -> str:
    return _key(row.get("ITEM GROUP"))


def _resolve_item_category(source_category: str, caches: dict) -> dict:
    if source_category in caches["item_categories"]:
        category = caches["item_categories"][source_category]
        return {"name": source_category, "abbreviation": category.get("abbreviation"), "sequence_digits": category.get("sequence_digits")}

    abbreviation = normalize_abbreviation(_category_abbreviation(source_category))
    existing_name = caches["item_category_by_abbreviation"].get(abbreviation)
    if existing_name:
        category = caches["item_categories"][existing_name]
        return {"name": existing_name, "abbreviation": category.get("abbreviation"), "sequence_digits": category.get("sequence_digits")}

    return {"name": source_category, "abbreviation": abbreviation, "sequence_digits": 5}


def _format_item_code(category: dict, sequence: int) -> str:
    abbreviation = normalize_abbreviation(category.get("abbreviation"))
    digits = cint(category.get("sequence_digits") or 5)
    return f"{abbreviation}-{sequence:0{digits}d}"


def _category_abbreviation(category: str) -> str:
    if category in CATEGORY_ABBREVIATIONS:
        return CATEGORY_ABBREVIATIONS[category]
    words = re.findall(r"[A-Z0-9À-Ý]+", category.upper())
    abbreviation = "".join(word[:1] for word in words[:4]) or "CAT"
    return normalize_abbreviation(abbreviation)[:8] or "CAT"


def _valid_item_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if _row_value(row, "ITEM NAME")
        and _clean(row.get("ITEM GROUP"))
        and _clean(row.get("DEFAULT UNIT OF MEASURE"))
        and _clean(row.get("ITEM CATEGORY"))
    ]


def _read_xlsx_rows(path: Path, sheet_name: str) -> list[dict]:
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
        row = {"excel_row": excel_row}
        has_value = False
        for column, header in headers.items():
            value = _clean(cells.get(column))
            row[header] = value
            has_value = has_value or bool(value)
        if has_value:
            rows.append(row)
    return rows


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in item.findall(".//a:t", XML_NS)) for item in root.findall("a:si", XML_NS)]


def _resolve_sheet_path(archive: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheet = workbook.find(f".//a:sheet[@name='{sheet_name}']", XML_NS)
    if sheet is None:
        frappe.throw(_("Sheet {0} not found in workbook.").format(sheet_name))
    relation_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
    return "xl/" + relmap[relation_id].lstrip("/")


def _read_cells(row, shared_strings: list[str]) -> dict:
    cells = {}
    for cell in row.findall("a:c", XML_NS):
        column = _cell_column(cell.attrib.get("r", ""))
        cells[column] = _cell_value(cell, shared_strings)
    return cells


def _cell_value(cell, shared_strings: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//a:t", XML_NS))
    value = cell.find("a:v", XML_NS)
    if value is None:
        return ""
    text = value.text or ""
    if cell.attrib.get("t") == "s":
        return shared_strings[cint(text)]
    return text


def _make_headers(cells: dict) -> dict:
    headers = {}
    seen = Counter()
    for column in sorted(cells, key=_column_number):
        label = _clean(cells[column]).upper()
        if not label:
            continue
        seen[label] += 1
        headers[column] = label if seen[label] == 1 else f"{label}_{seen[label]}"
    return headers


def _parse_price(value) -> tuple[Decimal | None, str]:
    text = _clean(value)
    if not text:
        return None, "blank"
    if text.startswith("#"):
        return None, "invalid"
    number = _decimal(text)
    if number is None:
        return None, "invalid"
    if number == 0:
        return None, "zero"
    return number, ""


def _normalize_supplier_currency(value) -> str:
    text = _clean(value).upper()
    if text in {"USD", "DOLLAR", "DOLLARS", "$", "US DOLLAR", "US DOLLARS"}:
        return "USD"
    if text in {"MAD", "DH", "DHS", "MAD/DH"}:
        return "MAD"
    if text in {"TRY", "TL", "TURKISH LIRA", "LIRA"}:
        return "TRY"
    return text


def _decimal(value) -> Decimal | None:
    text = _clean(value)
    if not text or text == "-" or text.startswith("#"):
        return None
    text = text.replace(" ", "").replace("\u00a0", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return Decimal(str(text))
    except InvalidOperation:
        return None


def _ensure_item_price_brand_field() -> None:
    _upsert_property_setter("Item Price", "brand", "fetch_from", "", "Data")
    _upsert_property_setter("Item Price", "brand", "read_only", "0", "Check")
    frappe.clear_cache(doctype="Item Price")


def _upsert_property_setter(doctype: str, fieldname: str, property_name: str, value, property_type: str) -> None:
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


def _record_change(summary: dict, action: str, item_code: str, row: dict, price_list: str, existing, values: dict, route_info: dict | None = None) -> None:
    if len(summary["changes"]) >= 200:
        return
    change = {
        "action": action,
        "item_code": item_code,
        "source_item_code": _clean(row.get("ITEM CODE")),
        "price_list": price_list,
        "old_rate": flt(existing.get("price_list_rate")) if existing else None,
        "new_rate": values.get("price_list_rate"),
        "old_supplier": _clean(existing.get("supplier")) if existing else "",
        "new_supplier": values.get("supplier") or "",
        "old_brand": _clean(existing.get("brand")) if existing else "",
        "new_brand": values.get("brand") or "",
    }
    if route_info and route_info.get("route") != "Default":
        change.update(
            {
                "supplier_price_route": route_info.get("route") or "",
                "packaging_density_kg_per_l": _decimal_to_float(route_info.get("density")),
                "packaging_weight_kg": _decimal_to_float(route_info.get("weight_kg")),
                "packaging_volume_l": _decimal_to_float(route_info.get("volume_l")),
            }
        )
    summary["changes"].append(change)


def _decimal_to_float(value):
    return float(value) if value is not None else None


def _sample_rows(rows: list[dict], limit: int = 100) -> list[dict]:
    return [
        {
            "excel_row": row.get("excel_row"),
            "source_item_code": _clean(row.get("ITEM CODE")),
            "item_name": _row_value(row, "ITEM NAME"),
            "item_category": _clean(row.get("ITEM CATEGORY")),
        }
        for row in rows[:limit]
    ]


def _sample_original_rows(original_map: dict, limit: int = 100) -> list[dict]:
    samples = []
    for rows in original_map.values():
        for row in rows:
            samples.append(row)
            if len(samples) >= limit:
                return samples
    return samples


def _warn(summary: dict, row: dict, message: str) -> None:
    _append_limited(
        summary["warnings"],
        {"excel_row": row.get("excel_row"), "source_item_code": _clean(row.get("ITEM CODE")), "message": message},
        limit=300,
    )


def _append_limited(rows: list, value: dict, limit: int = 100) -> None:
    if len(rows) < limit:
        rows.append(value)


def _finalize_summary(summary: dict) -> None:
    for key in [
        "new_price_lists",
        "new_brands",
        "new_suppliers",
        "items_missing",
        "old_item_delete_failures",
        "old_item_disable_failures",
        "warnings",
        "changes",
        "unmatched_new_samples",
        "unmatched_original_samples",
        "generated_item_code_samples",
        "supplier_price_value_route_samples",
        "unlisted_buying_price_delete_samples",
        "new_uoms",
        "new_item_groups",
        "new_item_categories",
        "new_item_materials",
        "item_category_aliases",
        "new_spec_attributes",
        "new_customs_tariff_numbers",
    ]:
        summary[key] = list(summary[key])
    for key in ["buying_prices_by_price_list", "supplier_price_routes", "deleted_selling_by_price_list"]:
        summary[key] = dict(summary[key])


def _db_has_column(doctype: str, fieldname: str) -> bool:
    checker = getattr(getattr(frappe, "db", None), "has_column", None)
    return bool(checker(doctype, fieldname)) if callable(checker) else False


def _doc_has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    has_field = getattr(meta, "has_field", None)
    if callable(has_field):
        return bool(has_field(fieldname))
    return hasattr(doc, fieldname) or hasattr(doc, "set")


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", ""}
    return bool(cint(value))


def _clean(value) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    return "" if text == "-" else text


def _row_value(row: dict, canonical_header: str) -> str:
    return catalog_import._row_value(row, canonical_header)


def _key(value) -> str:
    return _clean(value).casefold()


def _cell_column(cell_ref: str) -> str:
    return "".join(ch for ch in cell_ref if ch.isalpha())


def _column_number(column: str) -> int:
    result = 0
    for char in column:
        result = result * 26 + ord(char.upper()) - 64
    return result


def _chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]
