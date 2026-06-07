from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt


OPPORTUNITY_CHECKS = [
    {
        "key": "has_quotation",
        "group": "Quotation",
        "label": "Has quotation",
        "description": "At least one saved Quotation is linked to the Opportunity.",
    },
    {
        "key": "has_submitted_quotation",
        "group": "Quotation",
        "label": "Has submitted quotation",
        "description": "At least one linked Quotation is submitted.",
    },
    {
        "key": "all_quotations_open",
        "group": "Quotation",
        "label": "All quotations are open",
        "description": "Every linked Quotation must have ERP status Open.",
    },
    {
        "key": "at_least_one_quotation_open",
        "group": "Quotation",
        "label": "At least one quotation is open",
        "description": "One or more linked Quotations must have ERP status Open.",
    },
    {
        "key": "no_quotation_cancelled",
        "group": "Quotation",
        "label": "No quotation is cancelled",
        "description": "None of the linked Quotations can be cancelled.",
    },
    {
        "key": "has_sales_order",
        "group": "Sales Order",
        "label": "Has sales order",
        "description": "At least one saved Sales Order is linked through a Quotation.",
    },
    {
        "key": "has_submitted_sales_order",
        "group": "Sales Order",
        "label": "Has submitted sales order",
        "description": "At least one linked Sales Order is submitted.",
    },
    {
        "key": "no_sales_order_cancelled",
        "group": "Sales Order",
        "label": "No sales order is cancelled",
        "description": "None of the linked Sales Orders can be cancelled.",
    },
    {
        "key": "has_project",
        "group": "Project",
        "label": "Has project",
        "description": "At least one Project is linked through a Sales Order.",
    },
    {
        "key": "no_project_cancelled",
        "group": "Project",
        "label": "No project is cancelled",
        "description": "None of the linked Projects can be cancelled.",
    },
]

OPPORTUNITY_CHECK_LABELS = {check["key"]: check["label"] for check in OPPORTUNITY_CHECKS}

PROJECT_CHECKS = [
    {
        "key": "has_linked_sales_order",
        "group": "Sales Order",
        "label": "Has linked sales order",
        "description": "At least one Sales Order is linked to the Project.",
    },
    {
        "key": "has_submitted_sales_order",
        "group": "Sales Order",
        "label": "Has submitted sales order",
        "description": "At least one submitted Sales Order is linked to the Project.",
    },
    {
        "key": "no_sales_order_cancelled",
        "group": "Sales Order",
        "label": "No sales order is cancelled",
        "description": "None of the Sales Orders linked to the Project are cancelled.",
    },
    {
        "key": "has_submitted_payment",
        "group": "Payment",
        "label": "Has submitted payment",
        "description": "A submitted Payment Entry is allocated to a linked Sales Order or Sales Invoice.",
    },
    {
        "key": "has_purchase_order",
        "group": "Purchase Order",
        "label": "Has purchase order",
        "description": "At least one Purchase Order is linked to the Project.",
    },
    {
        "key": "has_submitted_purchase_order",
        "group": "Purchase Order",
        "label": "Has submitted purchase order",
        "description": "At least one submitted Purchase Order is linked to the Project.",
    },
    {
        "key": "has_delivery_note",
        "group": "Delivery Note",
        "label": "Has delivery note",
        "description": "At least one Delivery Note is linked to the Project or its Sales Orders.",
    },
    {
        "key": "has_submitted_delivery_note",
        "group": "Delivery Note",
        "label": "Has submitted delivery note",
        "description": "At least one submitted Delivery Note is linked to the Project or its Sales Orders.",
    },
    {
        "key": "has_partial_delivery",
        "group": "Delivery Note",
        "label": "Has partial delivery",
        "description": "A linked Sales Order has delivery progress or a submitted Delivery Note exists.",
    },
    {
        "key": "all_sales_orders_delivered",
        "group": "Delivery Note",
        "label": "All sales orders are delivered",
        "description": "Every linked Sales Order is fully delivered.",
    },
    {
        "key": "has_sales_invoice",
        "group": "Sales Invoice",
        "label": "Has sales invoice",
        "description": "At least one Sales Invoice is linked to the Project or its Sales Orders.",
    },
    {
        "key": "has_submitted_sales_invoice",
        "group": "Sales Invoice",
        "label": "Has submitted sales invoice",
        "description": "At least one submitted Sales Invoice is linked to the Project or its Sales Orders.",
    },
    {
        "key": "all_sales_orders_billed",
        "group": "Sales Invoice",
        "label": "All sales orders are billed",
        "description": "Every linked Sales Order is fully billed.",
    },
    {
        "key": "has_expected_dates",
        "group": "Installation",
        "label": "Has scheduled dates",
        "description": "The Project has expected start and end dates for installation scheduling.",
    },
    {
        "key": "project_marked_completed",
        "group": "Installation",
        "label": "Project is marked completed",
        "description": "The Project is completed or its completion percentage is 100%.",
    },
]

SALES_ORDER_CHECKS = [
    {
        "key": "sales_order_submitted",
        "group": "Sales Order",
        "label": "Sales order is submitted",
        "description": "The Sales Order document is submitted.",
    },
    {
        "key": "not_cancelled",
        "group": "Sales Order",
        "label": "Sales order is not cancelled",
        "description": "The Sales Order document is not cancelled.",
    },
    {
        "key": "has_customer",
        "group": "Sales Order",
        "label": "Has customer",
        "description": "The Sales Order is linked to a customer.",
    },
    {
        "key": "has_items",
        "group": "Sales Order",
        "label": "Has items",
        "description": "The Sales Order has at least one item row.",
    },
    {
        "key": "has_delivery_date",
        "group": "Sales Order",
        "label": "Has delivery date",
        "description": "The Sales Order has a delivery date.",
    },
    {
        "key": "has_project",
        "group": "Project",
        "label": "Has project",
        "description": "The Sales Order is linked to a Project or Installation Project.",
    },
    {
        "key": "has_submitted_delivery_note",
        "group": "Delivery Note",
        "label": "Has submitted delivery note",
        "description": "At least one submitted Delivery Note is linked to the Sales Order.",
    },
    {
        "key": "all_items_delivered",
        "group": "Delivery Note",
        "label": "All items are delivered",
        "description": "The Sales Order delivery percentage is complete.",
    },
    {
        "key": "has_submitted_sales_invoice",
        "group": "Sales Invoice",
        "label": "Has submitted sales invoice",
        "description": "At least one submitted Sales Invoice is linked to the Sales Order.",
    },
    {
        "key": "all_items_billed",
        "group": "Sales Invoice",
        "label": "All items are billed",
        "description": "The Sales Order billing percentage is complete.",
    },
]

CHECKS_BY_DOCUMENT_TYPE = {
    "Opportunity": OPPORTUNITY_CHECKS,
    "Project": PROJECT_CHECKS,
    "Sales Order": SALES_ORDER_CHECKS,
}

CHECK_LABELS_BY_DOCUMENT_TYPE = {
    document_type: {check["key"]: check["label"] for check in checks}
    for document_type, checks in CHECKS_BY_DOCUMENT_TYPE.items()
}


def get_predefined_status_checks(document_type: str) -> list[dict]:
    return CHECKS_BY_DOCUMENT_TYPE.get(document_type, [])


def validate_status_checks(document_type: str, doc, status_info: dict) -> None:
    checks = status_info.get("required_checks") or []
    if not checks:
        return

    context = _status_check_context(document_type, doc)
    failed = [check for check in checks if not _run_status_check(document_type, check, doc, context)]
    if not failed:
        return

    labels = [CHECK_LABELS_BY_DOCUMENT_TYPE.get(document_type, {}).get(check, check) for check in failed]
    frappe.throw(
        _("Cannot move {0} {1} to {2}. Missing required checks: {3}").format(
            document_type,
            doc.name,
            status_info.get("label") or status_info.get("name") or "status",
            ", ".join(labels),
        )
    )


def _status_check_context(document_type: str, doc) -> dict:
    if document_type == "Opportunity":
        return _opportunity_check_context(doc)
    if document_type == "Project":
        return _project_check_context(doc)
    if document_type == "Sales Order":
        return _sales_order_check_context(doc)
    return {}


def _run_status_check(document_type: str, check: str, doc, context: dict) -> bool:
    if document_type == "Opportunity":
        return _run_opportunity_check(check, context)
    if document_type == "Project":
        return _run_project_check(check, doc, context)
    if document_type == "Sales Order":
        return _run_sales_order_check(check, doc, context)
    return False


def _opportunity_check_context(doc) -> dict:
    quotations = _linked_quotations(doc.name)
    sales_orders = _linked_sales_orders([quotation["name"] for quotation in quotations])
    projects = _linked_projects(sales_orders)
    return {
        "quotations": quotations,
        "sales_orders": sales_orders,
        "projects": projects,
    }


def _linked_quotations(opportunity: str) -> list[dict]:
    if not opportunity:
        return []
    return frappe.get_all(
        "Quotation",
        filters={"opportunity": opportunity, "docstatus": ["<", 2]},
        fields=["name", "status", "docstatus"],
        order_by="modified desc",
        limit_page_length=0,
    )


def _linked_sales_orders(quotation_names: list[str]) -> list[dict]:
    if not quotation_names:
        return []
    return frappe.db.sql(
        """
        SELECT DISTINCT so.name, so.status, so.docstatus, COALESCE(so.custom_installation_project, so.project) AS project_name
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.prevdoc_docname IN %(quotations)s AND so.docstatus < 2
        ORDER BY so.modified DESC
        """,
        {"quotations": tuple(quotation_names)},
        as_dict=True,
    )


def _linked_projects(sales_orders: list[dict]) -> list[dict]:
    project_names = sorted({row.get("project_name") for row in sales_orders if row.get("project_name")})
    if not project_names:
        return []
    return frappe.get_all(
        "Project",
        filters={"name": ["in", project_names]},
        fields=["name", "status"],
        limit_page_length=0,
    )


def _run_opportunity_check(check: str, context: dict) -> bool:
    quotations = context["quotations"]
    sales_orders = context["sales_orders"]
    projects = context["projects"]

    if check == "has_quotation":
        return bool(quotations)
    if check == "has_submitted_quotation":
        return any(cint(row.get("docstatus")) == 1 for row in quotations)
    if check == "all_quotations_open":
        return bool(quotations) and all(row.get("status") == "Open" for row in quotations)
    if check == "at_least_one_quotation_open":
        return any(row.get("status") == "Open" for row in quotations)
    if check == "no_quotation_cancelled":
        return bool(quotations) and all(cint(row.get("docstatus")) != 2 and row.get("status") != "Cancelled" for row in quotations)
    if check == "has_sales_order":
        return bool(sales_orders)
    if check == "has_submitted_sales_order":
        return any(cint(row.get("docstatus")) == 1 for row in sales_orders)
    if check == "no_sales_order_cancelled":
        return bool(sales_orders) and all(cint(row.get("docstatus")) != 2 and row.get("status") != "Cancelled" for row in sales_orders)
    if check == "has_project":
        return bool(projects)
    if check == "no_project_cancelled":
        return bool(projects) and all(row.get("status") != "Cancelled" for row in projects)
    return False


def _project_check_context(doc) -> dict:
    sales_orders = _project_sales_orders(doc.name)
    sales_order_names = [row.get("name") for row in sales_orders if row.get("name")]
    sales_invoices = _project_sales_invoices(doc.name, sales_order_names)
    return {
        "sales_orders": sales_orders,
        "purchase_orders": _project_purchase_orders(doc.name),
        "delivery_notes": _project_delivery_notes(doc.name, sales_order_names),
        "sales_invoices": sales_invoices,
        "payment_entries": _project_payment_entries(
            sales_order_names,
            [row.get("name") for row in sales_invoices if row.get("name")],
        ),
    }


def _project_sales_orders(project: str) -> list[dict]:
    if not project or not frappe.db.exists("DocType", "Sales Order"):
        return []
    if _db_has_column("Sales Order", "custom_installation_project"):
        return frappe.db.sql(
            """
            SELECT name, status, docstatus, per_delivered, per_billed
            FROM `tabSales Order`
            WHERE project = %(project)s OR custom_installation_project = %(project)s
            ORDER BY modified DESC
            """,
            {"project": project},
            as_dict=True,
        )
    return frappe.get_all(
        "Sales Order",
        filters={"project": project},
        fields=["name", "status", "docstatus", "per_delivered", "per_billed"],
        order_by="modified desc",
        limit_page_length=0,
    )


def _project_purchase_orders(project: str) -> list[dict]:
    if not project or not frappe.db.exists("DocType", "Purchase Order"):
        return []
    return frappe.db.sql(
        """
        SELECT DISTINCT po.name, po.status, po.docstatus
        FROM `tabPurchase Order` po
        LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        WHERE po.project = %(project)s OR poi.project = %(project)s
        ORDER BY po.modified DESC
        """,
        {"project": project},
        as_dict=True,
    )


def _project_delivery_notes(project: str, sales_order_names: list[str]) -> list[dict]:
    if not project or not frappe.db.exists("DocType", "Delivery Note"):
        return []
    params = {"project": project}
    sales_order_filter = ""
    if sales_order_names:
        params["sales_orders"] = tuple(sales_order_names)
        sales_order_filter = "OR dni.against_sales_order IN %(sales_orders)s"
    return frappe.db.sql(
        f"""
        SELECT DISTINCT dn.name, dn.status, dn.docstatus
        FROM `tabDelivery Note` dn
        LEFT JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
        WHERE dn.project = %(project)s OR dni.project = %(project)s {sales_order_filter}
        ORDER BY dn.modified DESC
        """,
        params,
        as_dict=True,
    )


def _project_sales_invoices(project: str, sales_order_names: list[str]) -> list[dict]:
    if not project or not frappe.db.exists("DocType", "Sales Invoice"):
        return []
    params = {"project": project}
    sales_order_filter = ""
    if sales_order_names:
        params["sales_orders"] = tuple(sales_order_names)
        sales_order_filter = "OR sii.sales_order IN %(sales_orders)s"
    return frappe.db.sql(
        f"""
        SELECT DISTINCT si.name, si.status, si.docstatus
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.project = %(project)s OR sii.project = %(project)s {sales_order_filter}
        ORDER BY si.modified DESC
        """,
        params,
        as_dict=True,
    )


def _project_payment_entries(sales_order_names: list[str], sales_invoice_names: list[str]) -> list[dict]:
    references = []
    params = {}
    if sales_order_names:
        params["sales_orders"] = tuple(sales_order_names)
        references.append("(per.reference_doctype = 'Sales Order' AND per.reference_name IN %(sales_orders)s)")
    if sales_invoice_names:
        params["sales_invoices"] = tuple(sales_invoice_names)
        references.append("(per.reference_doctype = 'Sales Invoice' AND per.reference_name IN %(sales_invoices)s)")
    if not references or not frappe.db.exists("DocType", "Payment Entry"):
        return []
    return frappe.db.sql(
        f"""
        SELECT DISTINCT pe.name, pe.docstatus, per.reference_doctype, per.reference_name, per.allocated_amount
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.docstatus = 1 AND per.allocated_amount > 0 AND ({' OR '.join(references)})
        ORDER BY pe.modified DESC
        """,
        params,
        as_dict=True,
    )


def _run_project_check(check: str, doc, context: dict) -> bool:
    sales_orders = context["sales_orders"]
    purchase_orders = context["purchase_orders"]
    delivery_notes = context["delivery_notes"]
    sales_invoices = context["sales_invoices"]
    payment_entries = context["payment_entries"]

    if check == "has_linked_sales_order":
        return bool(sales_orders)
    if check == "has_expected_dates":
        return bool(doc.get("expected_start_date") and doc.get("expected_end_date"))
    if check == "has_submitted_sales_order":
        return any(cint(row.get("docstatus")) == 1 for row in sales_orders)
    if check == "no_sales_order_cancelled":
        return bool(sales_orders) and all(
            cint(row.get("docstatus")) != 2 and row.get("status") != "Cancelled" for row in sales_orders
        )
    if check == "has_submitted_payment":
        return bool(payment_entries)
    if check == "has_purchase_order":
        return bool(purchase_orders)
    if check == "has_submitted_purchase_order":
        return any(cint(row.get("docstatus")) == 1 for row in purchase_orders)
    if check == "has_delivery_note":
        return bool(delivery_notes)
    if check == "has_submitted_delivery_note":
        return any(cint(row.get("docstatus")) == 1 for row in delivery_notes)
    if check == "has_partial_delivery":
        return any(cint(row.get("docstatus")) == 1 for row in delivery_notes) or any(
            flt(row.get("per_delivered")) > 0 for row in sales_orders
        )
    if check == "all_sales_orders_delivered":
        return bool(sales_orders) and all(flt(row.get("per_delivered")) >= 99.99 for row in sales_orders)
    if check == "has_sales_invoice":
        return bool(sales_invoices)
    if check == "has_submitted_sales_invoice":
        return any(cint(row.get("docstatus")) == 1 for row in sales_invoices)
    if check == "all_sales_orders_billed":
        return bool(sales_orders) and all(flt(row.get("per_billed")) >= 99.99 for row in sales_orders)
    if check == "project_marked_completed":
        return doc.get("status") == "Completed" or flt(doc.get("percent_complete")) >= 99.99
    return False


def _sales_order_check_context(doc) -> dict:
    return {
        "has_submitted_delivery_note": _has_submitted_delivery_note(doc.name),
        "has_submitted_sales_invoice": _has_submitted_sales_invoice(doc.name),
    }


def _has_submitted_delivery_note(sales_order: str) -> bool:
    if not sales_order or not frappe.db.exists("DocType", "Delivery Note"):
        return False
    return bool(
        frappe.db.sql(
            """
            SELECT dn.name
            FROM `tabDelivery Note` dn
            INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
            WHERE dn.docstatus = 1 AND dni.against_sales_order = %s
            LIMIT 1
            """,
            (sales_order,),
        )
    )


def _has_submitted_sales_invoice(sales_order: str) -> bool:
    if not sales_order or not frappe.db.exists("DocType", "Sales Invoice"):
        return False
    return bool(
        frappe.db.sql(
            """
            SELECT si.name
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
            WHERE si.docstatus = 1 AND sii.sales_order = %s
            LIMIT 1
            """,
            (sales_order,),
        )
    )


def _run_sales_order_check(check: str, doc, context: dict) -> bool:
    if check == "sales_order_submitted":
        return cint(doc.get("docstatus")) == 1
    if check == "not_cancelled":
        return cint(doc.get("docstatus")) != 2 and doc.get("status") != "Cancelled"
    if check == "has_customer":
        return bool(doc.get("customer"))
    if check == "has_items":
        return bool(doc.get("items")) or bool(
            frappe.db.exists("Sales Order Item", {"parent": doc.name})
        )
    if check == "has_delivery_date":
        return bool(doc.get("delivery_date"))
    if check == "has_project":
        return bool(doc.get("project") or doc.get("custom_installation_project"))
    if check == "has_submitted_delivery_note":
        return bool(context["has_submitted_delivery_note"])
    if check == "all_items_delivered":
        return flt(doc.get("per_delivered")) >= 99.99
    if check == "has_submitted_sales_invoice":
        return bool(context["has_submitted_sales_invoice"])
    if check == "all_items_billed":
        return flt(doc.get("per_billed")) >= 99.99
    return False


def _db_has_column(doctype: str, fieldname: str) -> bool:
    has_column = getattr(frappe.db, "has_column", None)
    return bool(has_column and has_column(doctype, fieldname))
