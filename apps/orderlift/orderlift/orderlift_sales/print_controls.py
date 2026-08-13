from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


SUBMITTED_PRINT_REQUIRED_DOCTYPES = frozenset(
    {
        "Quotation",
        "Sales Order",
        "Delivery Note",
        "Sales Invoice",
        "Payment Entry",
        "Material Request",
        "Request for Quotation",
        "Supplier Quotation",
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Stock Entry",
    }
)


def require_submitted_document_print(doc, method=None, print_settings=None) -> None:
    """Prevent draft/cancelled transactional documents from any print route."""
    if (
        doc.doctype not in SUBMITTED_PRINT_REQUIRED_DOCTYPES
        or cint(doc.docstatus) == 1
    ):
        return

    frappe.throw(
        _("This {0} must be submitted before it can be printed or exported as PDF.").format(
            _(doc.doctype)
        ),
        title=_("Submit Document Before Printing"),
        exc=frappe.ValidationError,
    )


def require_submitted_quotation_print(doc, method=None, print_settings=None) -> None:
    """Backward-compatible wrapper for older hook/cache references."""
    require_submitted_document_print(
        doc,
        method=method,
        print_settings=print_settings,
    )
