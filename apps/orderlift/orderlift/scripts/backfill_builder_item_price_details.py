"""Backfill builder-stamped Item Price records with expense, customs, and
margin-basis data from their source Pricing Builder items.

Run from bench:
    bench --site <site> execute orderlift.scripts.backfill_builder_item_price_details.run \
        --kwargs '{"dry_run":1}'
    bench --site <site> execute orderlift.scripts.backfill_builder_item_price_details.run \
        --kwargs '{"dry_run":0}'
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt


STAMP_FIELDS = [
    "custom_builder_expense_amount",
    "custom_builder_customs_amount",
    "custom_builder_margin_basis",
    "custom_final_margin_percent",
    "custom_target_margin_percent",
]


@frappe.whitelist()
def run(
    dry_run: int | str = 1,
    limit: int | str | None = None,
    price_list: str | None = None,
):
    frappe.only_for("System Manager")
    dry_run = cint(dry_run)
    limit = cint(limit or 0)

    _verify_fields()

    conditions = ["ip.custom_pricing_builder IS NOT NULL", "ip.custom_pricing_builder != ''"]
    params = {}
    if price_list:
        conditions.append("ip.price_list = %(price_list)s")
        params["price_list"] = price_list

    limit_clause = " LIMIT %(limit)s" if limit else ""
    if limit:
        params["limit"] = limit

    rows = frappe.db.sql(
        f"""
        SELECT ip.name, ip.item_code, ip.price_list, ip.custom_pricing_builder,
               ip.custom_source_buying_price_list, ip.custom_builder_expense_amount,
               ip.custom_builder_customs_amount, ip.custom_builder_margin_basis,
               ip.custom_final_margin_percent, ip.custom_target_margin_percent
        FROM `tabItem Price` ip
        WHERE {' AND '.join(conditions)}
        ORDER BY ip.modified DESC
        {limit_clause}
        """,
        params,
        as_dict=True,
    )

    total = len(rows)
    updated = 0
    already_ok = 0
    not_found = 0
    errors = []
    max_errors = 30

    for ip_row in rows:
        buying_list = (ip_row.get("custom_source_buying_price_list") or "").strip()
        item_code = (ip_row.get("item_code") or "").strip()
        builder_name = (ip_row.get("custom_pricing_builder") or "").strip()

        if not frappe.db.exists("Pricing Builder", builder_name):
            not_found += 1
            if len(errors) < max_errors:
                errors.append(_("Builder {0} not found for {1}").format(builder_name, ip_row.name))
            continue

        try:
            doc = frappe.get_doc("Pricing Builder", builder_name)
        except Exception:
            not_found += 1
            if len(errors) < max_errors:
                errors.append(_("Failed to load builder {0}").format(builder_name))
            continue

        # Find matching builder item row
        matched = None
        for row in doc.builder_items or []:
            row_item = (row.item or "").strip()
            row_buying = (row.buying_list or "").strip()
            if row_item == item_code and (not buying_list or row_buying == buying_list):
                matched = row
                break
        if matched is None:
            for row in doc.builder_items or []:
                row_item = (row.item or "").strip()
                if row_item == item_code:
                    matched = row
                    break

        if matched is None:
            not_found += 1
            if len(errors) < max_errors:
                errors.append(
                    _("Item {0} not found in builder {1}").format(item_code, builder_name)
                )
            continue

        expense = flt(getattr(matched, "expenses", 0) or 0)
        customs = flt(getattr(matched, "customs_amount", 0) or 0)
        margin_basis = (getattr(matched, "margin_basis", "") or "").strip() or "Base Price"
        final_margin = flt(getattr(matched, "final_margin_pct", 0) or 0)
        target_margin = flt(getattr(matched, "target_margin_percent", 0) or 0)

        current_expense = flt(ip_row.get("custom_builder_expense_amount") or 0)
        current_customs = flt(ip_row.get("custom_builder_customs_amount") or 0)
        current_basis = (ip_row.get("custom_builder_margin_basis") or "").strip()
        current_final = flt(ip_row.get("custom_final_margin_percent") or 0)
        current_target = flt(ip_row.get("custom_target_margin_percent") or 0)

        if (
            abs(current_expense - expense) < 0.001
            and abs(current_customs - customs) < 0.001
            and current_basis == margin_basis
            and abs(current_final - final_margin) < 0.001
            and abs(current_target - target_margin) < 0.001
        ):
            already_ok += 1
            continue

        if not dry_run:
            frappe.db.set_value(
                "Item Price",
                ip_row.name,
                {
                    "custom_builder_expense_amount": expense,
                    "custom_builder_customs_amount": customs,
                    "custom_builder_margin_basis": margin_basis,
                    "custom_final_margin_percent": final_margin,
                    "custom_target_margin_percent": target_margin,
                },
                update_modified=False,
            )
        updated += 1

    if not dry_run and updated:
        frappe.db.commit()

    return {
        "dry_run": bool(dry_run),
        "total": total,
        "updated": updated,
        "already_ok": already_ok,
        "not_found": not_found,
        "errors": errors,
    }


def _verify_fields():
    missing = []
    for field in STAMP_FIELDS:
        if not frappe.db.has_column("Item Price", field):
            missing.append(field)
    if missing:
        frappe.throw(
            _("Missing Item Price columns: {0}. Run bench migrate first.").format(
                ", ".join(missing)
            )
        )
