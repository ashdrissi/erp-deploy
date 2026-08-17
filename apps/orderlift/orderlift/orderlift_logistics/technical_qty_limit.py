from __future__ import annotations


LINEAGE_FIELD = "custom_technical_revision"
LINK_FIELD = "sales_order_item"
# Child doctypes whose rows ERPNext caps against Sales Order Item.stock_qty.
#
# Material Request declares that link in its status_updater. Purchase Order does NOT:
# its __init__ lists only the Material Request Item entry, and the Sales Order Item
# entry is *appended at runtime* by update_status_updater() (purchase_order.py) for
# drop-ship rows. Reading only __init__ is how this was first missed -- both are
# capped, and the error names the Sales Order Item in either case.
LINEAGE_ROW_DOCTYPES = frozenset({"Material Request Item", "Purchase Order Item"})


class OrderliftTechnicalQtyLimitMixin:
    """Exempt approved Technical List rows from the Sales-Order-qty overflow guard.

    ERPNext caps a Material Request or Purchase Order row at its linked
    ``Sales Order Item.stock_qty`` (``status_updater``, joining on ``sales_order_item``).
    Spec rule 16 makes the approved
    execution qty the cap for policy-covered Sales Orders, and rule 5 makes raising it an
    engineering decision that does not amend the Sales Order -- so without this exemption a
    revision that raises a quantity above the sold quantity cannot be procured at all.

    The exempt rows are not uncapped: ``validate_procurement_document`` holds them to the
    approved execution qty through the procurement pool before this ever runs. The cap moves
    to the correct document rather than disappearing.

    Implemented by hiding ``sales_order_item`` for the duration of the native check, because
    ``status_updater`` skips any row whose ``join_field`` is empty. Scoped deliberately:

    - only rows carrying a lineage stamp, so unstamped rows keep the native guard;
    - only around ``validate_qty``, never ``update_qty`` -- that one still needs the link so
      ``requested_qty`` on the Sales Order Item stays correct;
    - restored in ``finally``, so a throw inside the native check cannot leave the document
      with its Sales Order link missing.
    """

    def validate_qty(self):
        hidden = []
        for row in self.get_all_children():
            if getattr(row, "doctype", None) not in LINEAGE_ROW_DOCTYPES:
                continue
            if not (row.get(LINEAGE_FIELD) or "").strip():
                continue
            if not (row.get(LINK_FIELD) or "").strip():
                continue
            hidden.append((row, row.get(LINK_FIELD)))

        for row, _value in hidden:
            row.set(LINK_FIELD, None)
        try:
            super().validate_qty()
        finally:
            for row, value in hidden:
                row.set(LINK_FIELD, value)
