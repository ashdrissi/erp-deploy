"""
SAV Ticket — Auto-fill helpers
-------------------------------
Cascade resolution: user enters one document, system fills the rest.
All functions are @frappe.whitelist() for client-side JS.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, today, getdate


@frappe.whitelist()
def resolve_from_serial_no(serial_no):
    """Given a Serial No, resolve the full chain."""
    if not serial_no:
        return {}

    serial = _get_readable_doc("Serial No", serial_no)

    result = {
        "item_concerned": serial.item_code,
        "batch": serial.batch_no,
        "warranty_expiry_date": serial.warranty_expiry_date,
        "serial_purchase_date": serial.purchase_date,
        "serial_status": serial.status,
    }

    # Delivery Note from serial
    if serial.delivery_document_type == "Delivery Note" and serial.delivery_document_no:
        dn = _get_optional_readable_doc("Delivery Note", serial.delivery_document_no)
        if dn:
            result["delivery_note"] = dn.name
            result["customer"] = dn.get("customer")
            result["source_delivery_date"] = dn.get("posting_date")
            result["installation_project"] = dn.get("project")

    # Sales Order from DN items
    if result.get("delivery_note"):
        so = frappe.db.sql("""
            SELECT DISTINCT soi.parent
            FROM `tabDelivery Note Item` dni
            JOIN `tabSales Order Item` soi ON dni.so_detail = soi.name
            WHERE dni.parent = %(dn)s
            LIMIT 1
        """, {"dn": result["delivery_note"]}, as_dict=True)
        so_name = _first_readable_link("Sales Order", [row.parent for row in so])
        if so_name:
            result["sales_order"] = so_name
            so_doc = _get_optional_readable_doc("Sales Order", so_name)
            if so_doc:
                if so_doc.get("project"):
                    result["installation_project"] = so_doc.get("project")
                if so_doc.get("customer"):
                    result["customer"] = so_doc.get("customer")

    # Sales Invoice from DN items
    if result.get("delivery_note"):
        invoice = frappe.db.sql("""
            SELECT DISTINCT sii.parent
            FROM `tabSales Invoice Item` sii
            JOIN `tabDelivery Note Item` dni ON sii.dn_detail = dni.name
            WHERE dni.parent = %(dn)s
            LIMIT 1
        """, {"dn": result["delivery_note"]}, as_dict=True)
        invoice_name = _first_readable_link("Sales Invoice", [row.parent for row in invoice])
        if invoice_name:
            result["sales_invoice"] = invoice_name

    # Fallback: invoice from SO
    if not result.get("sales_invoice") and result.get("sales_order"):
        invoice = frappe.db.sql("""
            SELECT DISTINCT sii.parent
            FROM `tabSales Invoice Item` sii
            JOIN `tabSales Order Item` soi ON sii.so_detail = soi.name
            WHERE soi.parent = %(so)s
            LIMIT 1
        """, {"so": result["sales_order"]}, as_dict=True)
        invoice_name = _first_readable_link("Sales Invoice", [row.parent for row in invoice])
        if invoice_name:
            result["sales_invoice"] = invoice_name

    # Warranty status
    result["warranty_status"] = _compute_warranty_status(
        serial.warranty_expiry_date, result.get("source_delivery_date")
    )

    # Days since delivery
    if result.get("source_delivery_date"):
        result["days_since_delivery"] = date_diff(today(), result["source_delivery_date"])

    # Customer tier
    if result.get("customer"):
        result["customer_tier"] = _get_customer_tier(result["customer"])

    # Site address
    result["site_address"] = _resolve_site_address(
        result.get("customer"), result.get("installation_project")
    )

    # Recurrence count
    result["recurrence_count"] = _count_recurrences(serial_no=serial_no)

    return result


@frappe.whitelist()
def resolve_from_sales_order(sales_order):
    """Given a Sales Order, resolve: Customer, Project, dates."""
    if not sales_order:
        return {}

    so = _get_readable_doc("Sales Order", sales_order)

    result = {
        "customer": so.get("customer"),
        "installation_project": so.get("project"),
        "source_delivery_date": so.get("delivery_date") or so.get("transaction_date"),
    }

    result["site_address"] = _resolve_site_address(so.get("customer"), so.get("project"))
    result["customer_tier"] = _get_customer_tier(so.get("customer"))

    if so.get("project"):
        result["recurrence_count"] = _count_recurrences(project=so.get("project"))
    elif so.get("customer"):
        result["recurrence_count"] = _count_recurrences(customer=so.get("customer"))

    # Linked Delivery Note
    dns = frappe.db.sql("""
        SELECT DISTINCT dni.parent
        FROM `tabDelivery Note Item` dni
        JOIN `tabSales Order Item` soi ON dni.so_detail = soi.name
        WHERE soi.parent = %(so)s
        LIMIT 1
    """, {"so": sales_order}, as_dict=True)
    dn_name = _first_readable_link("Delivery Note", [row.parent for row in dns])
    if dn_name:
        result["delivery_note"] = dn_name

    # Linked Sales Invoice
    invoices = frappe.db.sql("""
        SELECT DISTINCT sii.parent
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Order Item` soi ON sii.so_detail = soi.name
        WHERE soi.parent = %(so)s
        LIMIT 1
    """, {"so": sales_order}, as_dict=True)
    invoice_name = _first_readable_link("Sales Invoice", [row.parent for row in invoices])
    if invoice_name:
        result["sales_invoice"] = invoice_name

    if result.get("source_delivery_date"):
        result["days_since_delivery"] = date_diff(today(), result["source_delivery_date"])

    return result


@frappe.whitelist()
def resolve_from_delivery_note(delivery_note):
    """Given a Delivery Note, resolve: Customer, posting date, SO, project."""
    if not delivery_note:
        return {}

    dn = _get_readable_doc("Delivery Note", delivery_note)

    result = {
        "customer": dn.get("customer"),
        "source_delivery_date": dn.get("posting_date"),
        "installation_project": dn.get("project"),
    }

    result["site_address"] = _resolve_site_address(dn.get("customer"), dn.get("project"))
    result["customer_tier"] = _get_customer_tier(dn.get("customer"))

    # Linked SO
    so = frappe.db.sql("""
        SELECT DISTINCT soi.parent
        FROM `tabDelivery Note Item` dni
        JOIN `tabSales Order Item` soi ON dni.so_detail = soi.name
        WHERE dni.parent = %(dn)s
        LIMIT 1
    """, {"dn": delivery_note}, as_dict=True)
    so_name = _first_readable_link("Sales Order", [row.parent for row in so])
    if so_name:
        result["sales_order"] = so_name

    # Linked invoice
    invoice = frappe.db.sql("""
        SELECT DISTINCT sii.parent
        FROM `tabSales Invoice Item` sii
        JOIN `tabDelivery Note Item` dni ON sii.dn_detail = dni.name
        WHERE dni.parent = %(dn)s
        LIMIT 1
    """, {"dn": delivery_note}, as_dict=True)
    invoice_name = _first_readable_link("Sales Invoice", [row.parent for row in invoice])
    if invoice_name:
        result["sales_invoice"] = invoice_name

    if dn.get("project"):
        result["recurrence_count"] = _count_recurrences(project=dn.get("project"))
    elif dn.get("customer"):
        result["recurrence_count"] = _count_recurrences(customer=dn.get("customer"))
    else:
        result["recurrence_count"] = 0

    result["days_since_delivery"] = date_diff(today(), dn.get("posting_date"))

    return result


@frappe.whitelist()
def resolve_from_customer(customer):
    """Given a Customer, fill basic context."""
    if not customer:
        return {}

    cust = _get_optional_readable_doc("Customer", customer)
    if not cust:
        return {}

    result = {
        "customer_tier": _get_customer_tier(customer),
        "recurrence_count": _count_recurrences(customer=customer),
    }

    if cust.get("customer_primary_contact"):
        result["contact"] = cust.get("customer_primary_contact")

    if cust.get("primary_address"):
        result["site_address"] = cust.get("primary_address")

    return result


def _get_customer_tier(customer):
    """Get customer tier — safe: returns empty if field missing."""
    try:
        # Try known field names in order of likelihood
        for field in ("tier", "loyalty_program_tier", "custom_customer_tier"):
            val = frappe.db.get_value("Customer", customer, field)
            if val:
                return val
        return ""
    except Exception:
        return ""


def _compute_warranty_status(warranty_expiry_date, delivery_date):
    """Return human-readable warranty status."""
    if warranty_expiry_date:
        if getdate(warranty_expiry_date) >= getdate(today()):
            days_left = date_diff(warranty_expiry_date, today())
            return _("In warranty — {0} days remaining").format(days_left)
        else:
            days_expired = date_diff(today(), warranty_expiry_date)
            return _("Expired {0} days ago").format(days_expired)
    elif delivery_date:
        days = date_diff(today(), delivery_date)
        if days <= 365:
            return _("Possibly in warranty (delivered {0} days ago)").format(days)
        else:
            return _("Likely expired (delivered {0} days ago)").format(days)
    return ""


def _resolve_site_address(customer, project):
    """Get site address from project or customer."""
    if project and _can_read_doc("Project", project):
        addr = frappe.db.get_value("Project", project, "custom_site_address")
        if addr:
            return addr

    if customer and _can_read_doc("Customer", customer):
        addr = frappe.db.get_value("Customer", customer, "primary_address")
        if addr:
            return addr

        addr_row = frappe.db.sql("""
            SELECT a.address_line1, a.city, a.state, a.country
            FROM `tabDynamic Link` dl
            JOIN `tabAddress` a ON a.name = dl.parent
            WHERE dl.link_doctype = 'Customer' AND dl.link_name = %(c)s
            ORDER BY dl.idx ASC LIMIT 1
        """, {"c": customer}, as_dict=True)
        if addr_row:
            parts = [addr_row[0].address_line1, addr_row[0].city, addr_row[0].state, addr_row[0].country]
            return ", ".join(p for p in parts if p)

    return ""


def _count_recurrences(serial_no=None, item=None, project=None, customer=None):
    """Count open/in-progress SAV tickets for same entity."""
    filters = {"status": ["in", ["Open", "Assigned", "In Progress"]]}

    if serial_no:
        filters["serial_no"] = serial_no
    elif item:
        filters["item_concerned"] = item
    elif project:
        filters["installation_project"] = project
    elif customer:
        filters["customer"] = customer
    else:
        return 0

    return frappe.db.count("SAV Ticket", filters)


def _get_readable_doc(doctype, name):
    name = (name or "").strip()
    if not name:
        frappe.throw(_("{0} is required.").format(doctype))
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} not found.").format(doctype, name))
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    return doc


def _get_optional_readable_doc(doctype, name):
    if not (name or "").strip():
        return None
    try:
        return _get_readable_doc(doctype, name)
    except frappe.PermissionError:
        return None


def _can_read_doc(doctype, name):
    return _get_optional_readable_doc(doctype, name) is not None


def _first_readable_link(doctype, names):
    for name in names or []:
        if _can_read_doc(doctype, name):
            return name
    return ""
