from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate() -> None:
    create_custom_fields(
        {
            "Purchase Invoice Item": [
                {
                    "fieldname": "custom_sales_order",
                    "label": "Sales Order",
                    "fieldtype": "Link",
                    "options": "Sales Order",
                    "insert_after": "project",
                    "description": "Standalone Sales Order receiving this direct charge. Use Project for project charges.",
                }
            ],
            "Project": [
                {
                    "fieldname": "custom_revenue_forecast_final",
                    "label": "Revenue Forecast Final",
                    "fieldtype": "Check",
                    "default": "0",
                    "read_only": 1,
                    "insert_after": "custom_project_status",
                    "description": "No additional uninvoiced revenue is expected for this Project.",
                },
                {
                    "fieldname": "custom_cost_forecast_final",
                    "label": "Cost Forecast Final",
                    "fieldtype": "Check",
                    "default": "0",
                    "read_only": 1,
                    "insert_after": "custom_revenue_forecast_final",
                    "description": "No additional uncovered cost is expected for this Project.",
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_revenue_forecast_final",
                    "label": "Revenue Forecast Final",
                    "fieldtype": "Check",
                    "default": "0",
                    "read_only": 1,
                    "allow_on_submit": 1,
                    "insert_after": "custom_orderlift_order_status",
                    "description": "No additional uninvoiced revenue is expected for this standalone Sales Order.",
                },
                {
                    "fieldname": "custom_cost_forecast_final",
                    "label": "Cost Forecast Final",
                    "fieldtype": "Check",
                    "default": "0",
                    "read_only": 1,
                    "allow_on_submit": 1,
                    "insert_after": "custom_revenue_forecast_final",
                    "description": "No additional uncovered cost is expected for this standalone Sales Order.",
                },
            ],
        },
        update=True,
    )


def validate_purchase_invoice_sales_order(doc, method=None) -> None:
    """Keep direct standalone-SO charges separate from project/PO lineage."""
    for item in doc.get("items") or []:
        sales_order = (item.get("custom_sales_order") or "").strip()
        if not sales_order:
            continue
        row_label = item.get("idx") or item.get("name") or "?"
        if doc.get("project") or item.get("project"):
            frappe.throw(
                _("Purchase Invoice row {0}: Sales Order cannot be combined with Project lineage.").format(
                    row_label
                )
            )
        if item.get("purchase_order") or item.get("po_detail"):
            frappe.throw(
                _("Purchase Invoice row {0}: direct Sales Order and Purchase Order lineage are mutually exclusive.").format(
                    row_label
                )
            )

        order = frappe.db.get_value(
            "Sales Order", sales_order, ["company", "docstatus", "project"], as_dict=True
        )
        if not order:
            frappe.throw(
                _("Purchase Invoice row {0}: Sales Order {1} does not exist.").format(
                    row_label, sales_order
                )
            )
        if order.get("company") != doc.get("company"):
            frappe.throw(
                _("Purchase Invoice row {0}: Sales Order {1} belongs to another company.").format(
                    row_label, sales_order
                )
            )
        if int(order.get("docstatus") or 0) != 1:
            frappe.throw(
                _("Purchase Invoice row {0}: Sales Order {1} must be submitted.").format(
                    row_label, sales_order
                )
            )
        if order.get("project"):
            frappe.throw(
                _("Purchase Invoice row {0}: Sales Order {1} is project-linked; use Project or Purchase Order lineage.").format(
                    row_label, sales_order
                )
            )


def protect_forecast_finality(doc, method=None) -> None:
    """Forecast closure is controlled only by the scoped finance API."""
    if not doc:
        return
    if getattr(doc, "is_new", lambda: False)():
        for fieldname in ("custom_revenue_forecast_final", "custom_cost_forecast_final"):
            if getattr(doc, "meta", None) and doc.meta.get_field(fieldname):
                doc.set(fieldname, 0)
        return
    for fieldname in ("custom_revenue_forecast_final", "custom_cost_forecast_final"):
        if not getattr(doc, "meta", None) or not doc.meta.get_field(fieldname):
            continue
        previous = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
        old_value = previous.get(fieldname) if previous else frappe.db.get_value(doc.doctype, doc.name, fieldname)
        if int(old_value or 0) != int(doc.get(fieldname) or 0):
            frappe.throw(_("Use Project & Order Finance to change Revenue or Cost Forecast Final."), frappe.PermissionError)
