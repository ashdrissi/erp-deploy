#!/usr/bin/env python3
"""Seed Orderlift demo data (idempotent).

This script is meant to run inside the ERPNext container.
It uses Frappe ORM to create a minimal multi-company structure, master data,
and pricing rules required for Orderlift V0 demos.

By default it only creates/updates records if missing.
If --reset=1 is provided, it will delete only records created by this script
using the "OL-DEMO" marker.
"""

from __future__ import annotations

import argparse
import os


MARKER = "OL-DEMO"


def _connect(site: str) -> None:
    import frappe

    # This stack runs gunicorn with working_dir=/home/frappe/frappe-bench/sites and SITES_PATH=.
    # Frappe resolves some site-relative paths (notably site log handlers) relative to CWD,
    # so we enforce the same CWD here.
    os.chdir("/home/frappe/frappe-bench/sites")

    frappe.init(site=site, sites_path=".", force=True)
    frappe.connect()


def _commit() -> None:
    import frappe

    frappe.db.commit()


def _get_or_create(doctype: str, filters: dict, values: dict):
    import frappe

    name = frappe.db.exists(doctype, filters)
    if name:
        doc = frappe.get_doc(doctype, name)
        changed = False
        for k, v in values.items():
            if doc.get(k) != v and v is not None:
                doc.set(k, v)
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
        return doc

    doc = frappe.get_doc({"doctype": doctype, **filters, **values})
    doc.insert(ignore_permissions=True)
    return doc


def _ensure_company(company_name: str, abbr: str, currency: str, parent_company: str | None, country: str):
    values = {
        "abbr": abbr,
        "default_currency": currency,
        "country": country,
        "is_group": 0,
        "parent_company": parent_company,
        "default_holiday_list": None,
        "domain": None,
        "website": None,
        "company_description": MARKER,
    }
    return _get_or_create(
        "Company",
        {"company_name": company_name},
        values,
    )


def _ensure_warehouse(company: str, warehouse_name: str, parent_warehouse: str | None, is_group: int):
    # ERPNext warehouse unique key is (warehouse_name, company)
    values = {
        "parent_warehouse": parent_warehouse,
        "is_group": is_group,
        "warehouse_type": None,
        "disabled": 0,
    }
    return _get_or_create(
        "Warehouse",
        {"warehouse_name": warehouse_name, "company": company},
        values,
    )


def _ensure_item_group(group_name: str, parent_item_group: str | None):
    values = {
        "parent_item_group": parent_item_group,
        "is_group": 0,
        "image": None,
    }
    return _get_or_create("Item Group", {"item_group_name": group_name}, values)


def _ensure_uom(uom: str):
    return _get_or_create("UOM", {"uom_name": uom}, {"enabled": 1})


def _ensure_item(
    item_code: str,
    item_name: str,
    item_group: str,
    stock_uom: str,
    weight_per_unit: float | None,
    weight_uom: str | None,
    valuation_rate: float | None,
    description: str | None,
):
    values = {
        "item_name": item_name,
        "item_group": item_group,
        "stock_uom": stock_uom,
        "is_stock_item": 1,
        "include_item_in_manufacturing": 0,
        "disabled": 0,
        "weight_per_unit": weight_per_unit,
        "weight_uom": weight_uom,
        "valuation_rate": valuation_rate,
        "standard_rate": valuation_rate,
        "description": description,
    }
    doc = _get_or_create("Item", {"item_code": item_code}, values)

    # Tag record so we can reset safely.
    if not doc.get("description") or MARKER not in doc.get("description"):
        doc.description = (doc.description or "") + f"\n[{MARKER}]"
        doc.save(ignore_permissions=True)

    return doc


def _ensure_customer_group(name: str):
    return _get_or_create("Customer Group", {"customer_group_name": name}, {"is_group": 0})


def _ensure_supplier_group(name: str):
    return _get_or_create("Supplier Group", {"supplier_group_name": name}, {"is_group": 0})


def _ensure_territory(name: str):
    return _get_or_create("Territory", {"territory_name": name}, {"is_group": 0})


def _ensure_price_list(name: str, currency: str, selling: int):
    values = {
        "currency": currency,
        "selling": selling,
        "buying": 0 if selling else 1,
        "enabled": 1,
    }
    return _get_or_create("Price List", {"price_list_name": name}, values)


def _ensure_customer(name: str, customer_group: str, territory: str, default_price_list: str):
    values = {
        "customer_name": name,
        "customer_group": customer_group,
        "territory": territory,
        "default_price_list": default_price_list,
        "customer_type": "Company",
        "disabled": 0,
    }
    doc = _get_or_create("Customer", {"customer_name": name}, values)
    if MARKER not in (doc.get("remarks") or ""):
        doc.remarks = ((doc.remarks or "") + f"\n[{MARKER}]").strip()
        doc.save(ignore_permissions=True)
    return doc


def _ensure_supplier(name: str, supplier_group: str, notes: str):
    values = {
        "supplier_name": name,
        "supplier_group": supplier_group,
        "supplier_type": "Company",
        "disabled": 0,
        "remarks": (notes + f"\n[{MARKER}]").strip(),
    }
    return _get_or_create("Supplier", {"supplier_name": name}, values)


def _ensure_pricing_rule_motor_discount(rule_name: str, discount_percentage: float, customer_group: str, item_group: str):
    values = {
        "apply_on": "Item Group",
        "item_group": item_group,
        "selling": 1,
        "buying": 0,
        "priority": 10,
        "disable": 0,
        "rate_or_discount": "Discount Percentage",
        "discount_percentage": discount_percentage,
        "title": rule_name,
        "description": f"[{MARKER}]",
    }
    doc = _get_or_create("Pricing Rule", {"title": rule_name}, values)

    # Ensure the customer group child table contains exactly one row.
    if not doc.get("customer_groups"):
        doc.append("customer_groups", {"customer_group": customer_group})
        doc.save(ignore_permissions=True)
    return doc


def _ensure_currency_exchange(from_currency: str, to_currency: str, exchange_rate: float):
    values = {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "exchange_rate": exchange_rate,
    }
    return _get_or_create("Currency Exchange", {"from_currency": from_currency, "to_currency": to_currency}, values)


def reset_demo(site: str) -> None:
    # Conservative reset: delete only records with our marker in key text fields.
    import frappe

    # Items
    for name in frappe.get_all("Item", filters={"description": ["like", f"%[{MARKER}]%"]}, pluck="name"):
        frappe.delete_doc("Item", name, ignore_permissions=True, force=True)

    # Customers
    for name in frappe.get_all("Customer", filters={"remarks": ["like", f"%[{MARKER}]%"]}, pluck="name"):
        frappe.delete_doc("Customer", name, ignore_permissions=True, force=True)

    # Suppliers
    for name in frappe.get_all("Supplier", filters={"remarks": ["like", f"%[{MARKER}]%"]}, pluck="name"):
        frappe.delete_doc("Supplier", name, ignore_permissions=True, force=True)

    # Pricing Rules
    for name in frappe.get_all("Pricing Rule", filters={"description": ["like", f"%[{MARKER}]%"]}, pluck="name"):
        frappe.delete_doc("Pricing Rule", name, ignore_permissions=True, force=True)

    _commit()


def seed(site: str) -> None:
    # Companies
    _ensure_company("Orderlift Group (Global)", "OLG", "USD", None, country="United States")
    _ensure_company("Orderlift Maroc", "OLM", "MAD", "Orderlift Group (Global)", country="Morocco")
    _ensure_company("Orderlift France", "OLF", "EUR", "Orderlift Group (Global)", country="France")

    # Warehouses (Morocco sample)
    root = _ensure_warehouse("Orderlift Maroc", "Orderlift Maroc", None, is_group=1).name
    _ensure_warehouse("Orderlift Maroc", "Entrepot Central (Real Stock)", root, is_group=0)
    _ensure_warehouse("Orderlift Maroc", "Stock Transit (Virtual)", root, is_group=0)
    _ensure_warehouse("Orderlift Maroc", "Stock Reserve (Virtual)", root, is_group=0)
    _ensure_warehouse("Orderlift Maroc", "Stock Retour (Quarantine)", root, is_group=0)

    # Item groups
    ig_root = _ensure_item_group("Orderlift Demo", None).name
    _ensure_item_group("Moteurs", ig_root)
    _ensure_item_group("Cabines", ig_root)
    _ensure_item_group("Cablage", ig_root)
    _ensure_item_group("Commandes", ig_root)

    # UOMs
    _ensure_uom("Unit")
    _ensure_uom("Meter")

    # Items (volume stored in description for now; create a custom field later if needed)
    _ensure_item(
        "MTR-5KW",
        "Moteur Traction 5kW",
        "Moteurs",
        "Unit",
        weight_per_unit=150.0,
        weight_uom="Kg",
        valuation_rate=450.00,
        description=f"Volume (m3): 0.8\nCost USD: 450.00\n[{MARKER}]",
    )
    _ensure_item(
        "CAB-LUX",
        "Cabine Ascenseur Luxe",
        "Cabines",
        "Unit",
        weight_per_unit=400.0,
        weight_uom="Kg",
        valuation_rate=1200.00,
        description=f"Volume (m3): 2.5\nCost USD: 1200.00\n[{MARKER}]",
    )
    _ensure_item(
        "PNL-STD",
        "Tableau Commande V2",
        "Commandes",
        "Unit",
        weight_per_unit=15.0,
        weight_uom="Kg",
        valuation_rate=150.00,
        description=f"Volume (m3): 0.1\nCost USD: 150.00\n[{MARKER}]",
    )
    _ensure_item(
        "CBL-STEEL",
        "Cable Acier 10mm",
        "Cablage",
        "Meter",
        weight_per_unit=0.5,
        weight_uom="Kg",
        valuation_rate=2.50,
        description=f"Volume (m3): 0.002\nCost USD: 2.50\n[{MARKER}]",
    )

    # Partners
    _ensure_customer_group("Installateur")
    _ensure_customer_group("Distributeur")
    _ensure_customer_group("Interne")

    _ensure_supplier_group("Verified")
    _ensure_territory("Morocco")
    _ensure_territory("Marrakech")
    _ensure_territory("Casablanca")

    _ensure_price_list("Standard Selling", "USD", selling=1)
    _ensure_price_list("Distributor A", "USD", selling=1)

    _ensure_customer("Ascenseurs du Sud", "Installateur", "Marrakech", "Standard Selling")
    _ensure_customer("Building Solutions SA", "Distributeur", "Casablanca", "Distributor A")

    _ensure_supplier("Global Motors Ltd", "Verified", "Lead time: 14 days")
    _ensure_supplier("SteelWorks Co", "Verified", "Lead time: 7 days")

    # Pricing rules
    _ensure_pricing_rule_motor_discount(
        "Distributeur - 15% discount on Moteurs",
        discount_percentage=15.0,
        customer_group="Distributeur",
        item_group="Moteurs",
    )

    # Currency exchange example
    _ensure_currency_exchange("USD", "MAD", exchange_rate=10.0)

    _commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--reset", default="0")
    args = parser.parse_args()

    site = args.site
    reset = args.reset in ("1", "true", "True", "yes", "YES")

    _connect(site)

    if reset:
        reset_demo(site)

    seed(site)


if __name__ == "__main__":
    main()
