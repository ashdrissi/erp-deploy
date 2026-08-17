from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt


def validate_delivery_note_pick_list_reservation(doc, method=None) -> None:
    """Protect reserved stock while allowing direct delivery from the unreserved balance."""
    if not doc or cint(doc.get("is_return")):
        return

    pick_lists = {}
    direct_rows = defaultdict(list)
    problems = []
    for row in doc.get("items") or []:
        if not _requires_stock_reservation(row):
            continue

        item_label = _row_label(row)
        against_pick_list = (row.get("against_pick_list") or "").strip()
        pick_list_item = (row.get("pick_list_item") or "").strip()
        if not against_pick_list and not pick_list_item:
            warehouse = (row.get("warehouse") or "").strip()
            if not warehouse:
                problems.append(_("{0}: Warehouse is required for direct delivery.").format(item_label))
                continue
            if _active_row_reservation_qty(row, warehouse) > 0:
                problems.append(
                    _("{0}: this Sales Order row has reserved stock; create the Delivery Note from its Pick List.").format(
                        item_label
                    )
                )
                continue
            direct_rows[((row.get("item_code") or "").strip(), warehouse)].append(row)
            continue
        if not against_pick_list or not pick_list_item:
            problems.append(_("{0}: both Pick List and Pick List Item references are required.").format(item_label))
            continue
        # Spec rule 3: an engineering addition carries no Sales Order link, because
        # that link is what would pull it onto an invoice. A row stamped with a
        # technical revision is a deliberate addition, not a missing reference, so it
        # may reach delivery without one. Every other check on this route — both Pick
        # List references, a submitted Pick List, sufficient picked and reserved
        # quantity — still applies to it below.
        if not _carries_technical_lineage(row) and (
            not row.get("against_sales_order") or not row.get("so_detail")
        ):
            problems.append(_("{0}: Sales Order reference is required for reserved delivery.").format(item_label))
            continue

        pick_list = _get_pick_list(against_pick_list, pick_lists)
        if not pick_list:
            problems.append(_("{0}: Pick List {1} was not found.").format(item_label, against_pick_list))
            continue
        if cint(pick_list.docstatus) != 1:
            problems.append(_("{0}: Pick List {1} must be submitted.").format(item_label, pick_list.name))
            continue

        pick_row = next(
            (location for location in pick_list.get("locations") or [] if location.name == pick_list_item),
            None,
        )
        if not pick_row:
            problems.append(_("{0}: Pick List row {1} was not found.").format(item_label, pick_list_item))
            continue
        if flt(pick_row.get("picked_qty")) <= 0:
            problems.append(_("{0}: Pick List row must have a picked quantity.").format(item_label))
        if flt(pick_row.get("stock_reserved_qty")) <= 0:
            problems.append(_("{0}: reserve the submitted Pick List before submitting the Delivery Note.").format(item_label))
        delivery_stock_qty = _row_stock_qty(row)
        if delivery_stock_qty > flt(pick_row.get("picked_qty")):
            problems.append(_("{0}: Delivery quantity cannot exceed the picked quantity.").format(item_label))
        if delivery_stock_qty > flt(pick_row.get("stock_reserved_qty")):
            problems.append(_("{0}: Delivery quantity cannot exceed the reserved quantity.").format(item_label))

    for (item_code, warehouse), rows in direct_rows.items():
        requested_qty = sum(_row_stock_qty(row) for row in rows)
        available_qty = _available_unreserved_qty(item_code, warehouse)
        if requested_qty > available_qty + 0.000001:
            problems.append(
                _(
                    "{0} in {1}: direct delivery quantity {2} exceeds unreserved stock {3}. "
                    "Reduce the quantity or release another reservation."
                ).format(item_code, warehouse, requested_qty, available_qty)
            )
        for row in rows:
            problems.extend(_direct_serial_batch_problems(row, warehouse))

    if problems:
        frappe.throw("<br>".join(problems), title=_("Delivery Stock Validation"))


def _carries_technical_lineage(row) -> bool:
    return bool(str(row.get("custom_technical_revision") or "").strip())


def _requires_stock_reservation(row) -> bool:
    item_code = (row.get("item_code") or "").strip()
    if not item_code:
        return False
    if row.get("delivered_by_supplier"):
        return False
    return cint(frappe.get_cached_value("Item", item_code, "is_stock_item")) == 1


def _get_pick_list(name: str, cache: dict):
    name = (name or "").strip()
    if not name:
        return None
    if name not in cache:
        cache[name] = frappe.get_doc("Pick List", name) if frappe.db.exists("Pick List", name) else None
    return cache[name]


def _active_row_reservation_qty(row, warehouse: str) -> float:
    sales_order = (row.get("against_sales_order") or "").strip()
    sales_order_item = (row.get("so_detail") or "").strip()
    if not sales_order or not sales_order_item:
        return 0.0
    from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
        get_sre_reserved_qty_for_voucher_detail_no,
    )

    return flt(
        get_sre_reserved_qty_for_voucher_detail_no(
            (row.get("item_code") or "").strip(),
            "Sales Order",
            sales_order,
            sales_order_item,
            warehouse=warehouse,
        )
    )


def _available_unreserved_qty(item_code: str, warehouse: str) -> float:
    from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
        get_available_qty_to_reserve,
    )

    return max(flt(get_available_qty_to_reserve(item_code, warehouse)), 0.0)


def _direct_serial_batch_problems(row, warehouse: str) -> list[str]:
    item_code = (row.get("item_code") or "").strip()
    item_details = frappe.get_cached_value(
        "Item", item_code, ["has_serial_no", "has_batch_no"], as_dict=True
    )
    if not item_details or not (cint(item_details.has_serial_no) or cint(item_details.has_batch_no)):
        return []

    serial_nos, batch_qty = _selected_serial_batch(row)
    problems = []
    if serial_nos:
        from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
            get_sre_reserved_serial_nos_details,
        )

        reserved_serials = set(get_sre_reserved_serial_nos_details(item_code, warehouse))
        conflicts = sorted(set(serial_nos).intersection(reserved_serials))
        if conflicts:
            problems.append(
                _("{0}: Serial Nos reserved for another delivery cannot be used: {1}.").format(
                    _row_label(row), ", ".join(conflicts[:10])
                )
            )

    if batch_qty:
        from erpnext.stock.doctype.batch.batch import get_batch_qty
        from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
            get_sre_reserved_batch_nos_details,
        )

        reserved_batches = get_sre_reserved_batch_nos_details(item_code, warehouse)
        for batch_no, requested_qty in batch_qty.items():
            actual_qty = flt(get_batch_qty(item_code=item_code, warehouse=warehouse, batch_no=batch_no))
            available_qty = max(actual_qty - flt(reserved_batches.get(batch_no)), 0.0)
            if requested_qty > available_qty + 0.000001:
                problems.append(
                    _("{0}: Batch {1} has only {2} unreserved quantity available.").format(
                        _row_label(row), batch_no, available_qty
                    )
                )
    return problems


def _selected_serial_batch(row) -> tuple[list[str], dict[str, float]]:
    serial_nos = [value.strip() for value in (row.get("serial_no") or "").splitlines() if value.strip()]
    batch_qty = defaultdict(float)
    if row.get("batch_no"):
        batch_qty[row.get("batch_no")] += _row_stock_qty(row)

    bundle = (row.get("serial_and_batch_bundle") or "").strip()
    if bundle:
        for entry in frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": bundle},
            fields=["serial_no", "batch_no", "qty"],
            limit_page_length=0,
        ):
            if entry.serial_no:
                serial_nos.append(entry.serial_no)
            if entry.batch_no:
                batch_qty[entry.batch_no] += abs(flt(entry.qty))
    return serial_nos, dict(batch_qty)


def _row_stock_qty(row) -> float:
    return flt(row.get("stock_qty")) or flt(row.get("qty")) * (flt(row.get("conversion_factor")) or 1)


def _row_label(row) -> str:
    return _("Row #{0} {1}").format(row.get("idx") or "-", row.get("item_code") or "")
