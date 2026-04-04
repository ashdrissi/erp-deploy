from __future__ import annotations

import csv
from pathlib import Path

import frappe
from frappe.utils import flt
from frappe.utils.file_manager import save_file


DEFAULT_IMPORT_DIR = Path("/tmp/orderlift-import")
WEIGHT_UOM = "Kg"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _ensure_uom(row: dict[str, str]) -> str:
    uom = row["uom"].strip()
    if frappe.db.exists("UOM", uom):
        return uom

    frappe.get_doc(
        {
            "doctype": "UOM",
            "uom_name": uom,
            "enabled": int(row.get("enabled") or 1),
        }
    ).insert(ignore_permissions=True)
    return uom


def _ensure_brand(brand_name: str) -> str:
    brand_name = (brand_name or "").strip()
    if not brand_name:
        return ""

    if frappe.db.exists("Brand", brand_name):
        return brand_name

    doc = frappe.new_doc("Brand")
    if hasattr(doc, "brand"):
        doc.brand = brand_name
    else:
        doc.name = brand_name
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item_group(row: dict[str, str]) -> str:
    name = row["item_group_name"].strip()
    if frappe.db.exists("Item Group", name):
        return name

    frappe.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": name,
            "parent_item_group": row.get("parent_item_group") or "All Item Groups",
            "is_group": 0,
        }
    ).insert(ignore_permissions=True)
    return name


def _ensure_price_list(row: dict[str, str]) -> str:
    name = row["price_list"].strip()
    if frappe.db.exists("Price List", name):
        doc = frappe.get_doc("Price List", name)
        doc.currency = row["currency"].strip()
        doc.selling = int(row["selling"] or 0)
        doc.buying = int(row["buying"] or 0)
        doc.enabled = int(row.get("enabled") or 1)
        doc.save(ignore_permissions=True)
        return name

    frappe.get_doc(
        {
            "doctype": "Price List",
            "price_list_name": name,
            "currency": row["currency"].strip(),
            "selling": int(row["selling"] or 0),
            "buying": int(row["buying"] or 0),
            "enabled": int(row.get("enabled") or 1),
        }
    ).insert(ignore_permissions=True)
    return name


def _ensure_item(row: dict[str, str]) -> str:
    item_code = row["item_code"].strip()
    values = {
        "item_code": item_code,
        "item_name": row["item_name"].strip(),
        "description": row.get("description", "").strip(),
        "item_group": row["item_group"].strip(),
        "stock_uom": row["stock_uom"].strip(),
        "brand": _ensure_brand(row.get("brand", "")),
        "custom_material": row.get("custom_material", "").strip(),
        "custom_weight_kg": flt(row.get("custom_weight_kg") or 0),
        "custom_volume_m3": flt(row.get("custom_volume_m3") or 0),
        "disabled": int(row.get("disabled") or 0),
        "is_stock_item": 1,
        "include_item_in_manufacturing": 0,
    }

    weight_per_unit = flt(row.get("weight_per_unit") or 0)
    if weight_per_unit:
        values["weight_per_unit"] = weight_per_unit
        values["weight_uom"] = WEIGHT_UOM

    if frappe.db.exists("Item", item_code):
        doc = frappe.get_doc("Item", item_code)
        doc.update(values)
        doc.save(ignore_permissions=True)
        return item_code

    frappe.get_doc({"doctype": "Item", **values}).insert(ignore_permissions=True)
    return item_code


def _ensure_item_price(row: dict[str, str]) -> str:
    filters = {
        "item_code": row["item_code"].strip(),
        "price_list": row["price_list"].strip(),
        "uom": row["uom"].strip(),
    }
    values = {
        "item_code": filters["item_code"],
        "price_list": filters["price_list"],
        "currency": row["currency"].strip(),
        "price_list_rate": flt(row["price_list_rate"]),
        "selling": int(row.get("selling") or 0),
        "buying": int(row.get("buying") or 0),
        "uom": filters["uom"],
    }

    name = frappe.db.exists("Item Price", filters)
    if name:
        doc = frappe.get_doc("Item Price", name)
        doc.update(values)
        doc.save(ignore_permissions=True)
        return name

    return frappe.get_doc({"doctype": "Item Price", **values}).insert(ignore_permissions=True).name


def _ensure_item_image(row: dict[str, str], image_dir: Path) -> str:
    item_code = row["item_code"].strip()
    filename = row["image_filename"].strip()
    file_path = image_dir / filename
    if not file_path.exists():
        frappe.throw(f"Missing image file for {item_code}: {file_path}")

    existing = frappe.db.exists(
        "File",
        {
            "attached_to_doctype": "Item",
            "attached_to_name": item_code,
            "file_name": filename,
            "is_private": 0,
        },
    )

    if existing:
        file_doc = frappe.get_doc("File", existing)
    else:
        file_doc = save_file(
            filename,
            file_path.read_bytes(),
            "Item",
            item_code,
            is_private=0,
        )

    item = frappe.get_doc("Item", item_code)
    if item.image != file_doc.file_url:
        item.db_set("image", file_doc.file_url, update_modified=False)

    return file_doc.name


def _ensure_product_bundles(rows: list[dict[str, str]]) -> int:
    grouped = {}
    for row in rows:
        grouped.setdefault(row["bundle_item_code"].strip(), []).append(row)

    count = 0
    for bundle_item_code, children in grouped.items():
        item = frappe.get_doc("Item", bundle_item_code)
        if item.is_stock_item:
            item.db_set("is_stock_item", 0, update_modified=False)

        existing_name = frappe.db.exists("Product Bundle", {"new_item_code": bundle_item_code})
        if existing_name:
            bundle = frappe.get_doc("Product Bundle", existing_name)
        else:
            bundle = frappe.new_doc("Product Bundle")
            bundle.new_item_code = bundle_item_code

        bundle.description = children[0].get("description", "")
        bundle.disabled = 0
        bundle.set("items", [])
        for child in children:
            child_item = frappe.get_doc("Item", child["child_item_code"].strip())
            bundle.append(
                "items",
                {
                    "item_code": child_item.name,
                    "qty": flt(child.get("qty") or 1),
                    "description": child_item.description or child_item.item_name,
                    "uom": child_item.stock_uom,
                    "rate": 0,
                },
            )

        if bundle.is_new():
            bundle.insert(ignore_permissions=True)
        else:
            bundle.save(ignore_permissions=True)
        count += 1

    return count


@frappe.whitelist()
def run(import_dir: str = str(DEFAULT_IMPORT_DIR)) -> dict[str, int]:
    base = Path(import_dir)
    required_files = [
        "uoms.csv",
        "item_groups.csv",
        "price_lists.csv",
        "items.csv",
        "item_prices.csv",
    ]
    missing = [name for name in required_files if not (base / name).exists()]
    if missing:
        frappe.throw(f"Missing import files in {base}: {', '.join(missing)}")

    counts = {
        "uoms": 0,
        "item_groups": 0,
        "price_lists": 0,
        "items": 0,
        "item_prices": 0,
        "item_images": 0,
        "product_bundles": 0,
    }

    for row in _read_csv(base / "uoms.csv"):
        _ensure_uom(row)
        counts["uoms"] += 1

    for row in _read_csv(base / "item_groups.csv"):
        _ensure_item_group(row)
        counts["item_groups"] += 1

    for row in _read_csv(base / "price_lists.csv"):
        _ensure_price_list(row)
        counts["price_lists"] += 1

    for row in _read_csv(base / "items.csv"):
        _ensure_item(row)
        counts["items"] += 1

    for row in _read_csv(base / "item_prices.csv"):
        _ensure_item_price(row)
        counts["item_prices"] += 1

    image_csv = base / "item_images.csv"
    image_dir = base / "item_images"
    if image_csv.exists():
        for row in _read_csv(image_csv):
            _ensure_item_image(row, image_dir)
            counts["item_images"] += 1

    bundle_csv = base / "product_bundles.csv"
    if bundle_csv.exists() and frappe.db.exists("DocType", "Product Bundle"):
        counts["product_bundles"] = _ensure_product_bundles(_read_csv(bundle_csv))

    frappe.db.commit()
    return counts
