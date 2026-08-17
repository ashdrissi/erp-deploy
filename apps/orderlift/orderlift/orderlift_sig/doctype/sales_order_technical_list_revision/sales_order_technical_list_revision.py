from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from orderlift.orderlift_sig import technical_list


class SalesOrderTechnicalListRevision(Document):
    def after_insert(self):
        technical_list.initialize_revision_manifest(self)

    def before_validate(self):
        technical_list.prepare_revision_items(self)

    def validate(self):
        technical_list.validate_revision(self)

    def before_submit(self):
        technical_list.validate_revision(self, for_submit=True)
        self.reject_group_warehouses()
        from orderlift.annex_chain import on_technical_revision_submit

        on_technical_revision_submit(self)

    def reject_group_warehouses(self):
        """Refuse a group warehouse on any revision line.

        A group warehouse is a tree node, not a location: nothing can be stocked in it,
        so no line referencing one can ever be procured, picked or delivered. Worse, the
        document becomes unreadable to any user whose Warehouse user permissions cover
        only real warehouses -- and a group node cannot even be granted, because the
        Access Command Center offers only real warehouses.

        Caught at submit, so an approved revision is always executable. Engineering
        additions are the usual source: a sold line inherits its warehouse from the
        Sales Order row, an addition has no such source and can fall back to a parent.
        """
        rows_by_warehouse = {}
        for row in self.get("items") or []:
            warehouse = (row.get("warehouse") or "").strip()
            if not warehouse:
                continue
            if frappe.db.get_value("Warehouse", warehouse, "is_group"):
                rows_by_warehouse.setdefault(warehouse, []).append(str(row.idx))
        if not rows_by_warehouse:
            return
        detail = ", ".join(
            f"{warehouse} (row {', '.join(rows)})"
            for warehouse, rows in sorted(rows_by_warehouse.items())
        )
        frappe.throw(
            _(
                "Select the warehouse that holds the stock, not a group warehouse: {0}."
            ).format(detail)
        )

    def on_submit(self):
        technical_list.submit_revision(self)

    def before_cancel(self):
        technical_list.validate_revision_cancellation(self)

    def on_cancel(self):
        technical_list.cancel_revision(self)

    def after_delete(self):
        technical_list.cleanup_revision_pointers(self)
