from __future__ import annotations

from frappe.utils import cint


def prepare_non_stock_sales_invoice_items(doc, method=None) -> None:
    """Avoid stock valuation validation noise for normal non-stock Sales Invoices."""
    if not doc or cint(doc.get("update_stock")):
        return
    for row in doc.get("items") or []:
        if hasattr(row, "meta") and row.meta.get_field("allow_zero_valuation_rate"):
            row.allow_zero_valuation_rate = 1
        elif isinstance(row, dict) and "allow_zero_valuation_rate" in row:
            row["allow_zero_valuation_rate"] = 1
