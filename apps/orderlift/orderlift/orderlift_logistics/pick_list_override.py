from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


class OrderliftPickListMixin:
    def validate_sales_order(self):
        """Allow multiple partial Pick Lists while preventing over-picking."""
        if self.purpose != "Delivery":
            return
        current = defaultdict(float)
        for row in self.get("locations") or []:
            if row.sales_order_item:
                current[row.sales_order_item] += flt(row.stock_qty)
        if not current:
            return

        existing_rows = frappe.db.sql(
            """
            SELECT pli.sales_order_item, SUM(COALESCE(pli.stock_qty, 0)) AS stock_qty
            FROM `tabPick List Item` pli
            INNER JOIN `tabPick List` pl ON pl.name = pli.parent
            WHERE pli.sales_order_item IN %(items)s
              AND pl.docstatus < 2
              AND pl.name != %(current)s
            GROUP BY pli.sales_order_item
            """,
            {"items": tuple(current), "current": self.name or ""},
            as_dict=True,
        )
        existing = {row.sales_order_item: flt(row.stock_qty) for row in existing_rows}
        source_rows = frappe.get_all(
            "Sales Order Item",
            filters={"name": ["in", list(current)]},
            fields=["name", "parent", "qty", "delivered_qty", "conversion_factor"],
            limit_page_length=0,
        )
        source_by_name = {row.name: row for row in source_rows}
        for item_name, current_qty in current.items():
            source = source_by_name.get(item_name)
            if not source or frappe.db.get_value("Sales Order", source.parent, "docstatus") != 1:
                frappe.throw(_("Sales Order Item {0} must belong to a submitted Sales Order.").format(item_name))
            open_qty = max(
                (flt(source.qty) - flt(source.delivered_qty)) * (flt(source.conversion_factor) or 1),
                0,
            )
            planned = existing.get(item_name, 0) + current_qty
            if planned > open_qty + 1e-9:
                frappe.throw(
                    _("Pick Lists for Sales Order Item {0} exceed the remaining quantity {1}.").format(
                        item_name,
                        open_qty,
                    )
                )
