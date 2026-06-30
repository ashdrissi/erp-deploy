from __future__ import annotations

import frappe

from orderlift.orderlift_sales.utils import price_list_import


PRICE_LIST_PAIRS = [
    ("PRIX FOURNISSEUR MAD", "PRIX FOURNISSEUR MAD - Installation"),
    ("PRIX FOURNISSEUR USD Weight", "PRIX FOURNISSEUR USD Weight - Installation"),
    ("PRIX FOURNISSEUR USD Volume", "PRIX FOURNISSEUR USD Volume - Installation"),
    ("PRIX FOURNISSEUR USD Value", "PRIX FOURNISSEUR USD Value - Installation"),
    ("PRIX FOURNISSEUR TRY Weight", "PRIX FOURNISSEUR TRY Weight - Installation"),
    ("PRIX FOURNISSEUR TRY Volume", "PRIX FOURNISSEUR TRY Volume - Installation"),
    ("PRIX FOURNISSEUR TRY Value", "PRIX FOURNISSEUR TRY Value - Installation"),
]


@frappe.whitelist()
def run(dry_run: int = 1, target_company: str = "Orderlift Maroc Installation") -> dict:
    frappe.only_for(["System Manager", "Orderlift Admin"])
    dry_run = int(dry_run or 0)
    summary = {"dry_run": dry_run, "pairs": []}
    for source, target in PRICE_LIST_PAIRS:
        detail = _sync_pair(source, target, target_company=target_company, dry_run=dry_run)
        summary["pairs"].append(detail)
    if not dry_run:
        frappe.db.commit()
    return summary


def _sync_pair(source: str, target: str, target_company: str, dry_run: int) -> dict:
    if not frappe.db.exists("Price List", source):
        frappe.throw("Source Price List {0} was not found.".format(source))
    target_exists = bool(frappe.db.exists("Price List", target))
    source_count = frappe.db.count("Item Price", {"price_list": source})
    target_count = frappe.db.count("Item Price", {"price_list": target}) if target_exists else 0
    detail = {
        "source": source,
        "target": target,
        "target_exists": target_exists,
        "source_item_prices": source_count,
        "target_item_prices_before": target_count,
        "target_item_prices_deleted": target_count,
        "target_item_prices_created": source_count,
    }
    if dry_run:
        return detail

    if not target_exists:
        source_doc = frappe.get_doc("Price List", source)
        target_doc = price_list_import._copy_price_list_doc(source_doc, target, target_company)
        target_doc.insert(ignore_permissions=True)
    else:
        source_doc = frappe.get_doc("Price List", source)
        target_doc = frappe.get_doc("Price List", target)
        price_list_import._copy_doc_fields(source_doc, target_doc, price_list_import.PRICE_LIST_COPY_EXCLUDED_FIELDS)
        target_doc.price_list_name = target
        if price_list_import._meta_has_field("Price List", "title"):
            target_doc.title = target
        company_field = price_list_import.company_field_for("Price List")
        if price_list_import._meta_has_field("Price List", company_field):
            target_doc.set(company_field, target_company)
        target_doc.save(ignore_permissions=True)

    for row in frappe.get_all("Item Price", filters={"price_list": target}, pluck="name", limit_page_length=0):
        frappe.delete_doc("Item Price", row, ignore_permissions=True)
    price_list_import._copy_item_prices(source, target)
    return detail
