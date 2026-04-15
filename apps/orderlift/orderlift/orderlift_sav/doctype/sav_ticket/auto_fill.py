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

    serial = frappe.db.get_value("Serial No", serial_no, [
        "item_code", "batch_no", "customer", "warranty_expiry_date",
        "purchase_date", "delivery_document_type", "delivery_document_no",
        "warehouse", "status", "description"
    ], as_dict=True)

    if not serial:
        frappe.throw(_("Serial No {0} not found.").format(serial_no))

    result = {
        "item_concerned": serial.item_code,
        "batch": serial.batch_no,
        "warranty_expiry_date": serial.warranty_expiry_date,
        "serial_purchase_date": serial.purchase_date,
        "serial_status": serial.status,
    }

    # Delivery Note from serial
    if serial.delivery_document_type == "Delivery Note" and serial.delivery_document_no:
        result["delivery_note"] = serial.delivery_document_no
        dn = frappe.db.get_value("Delivery Note", serial.delivery_document_no, [
            "customer", "posting_date", "project", "company"
        ], as_dict=True)
        if dn:
            result["customer"] = dn.customer
            result["source_delivery_date"] = dn.posting_date
            result["installation_project"] = dn.project

    # Sales Order from DN items
    if result.get("delivery_note"):
        so = frappe.db.sql("""
            SELECT DISTINCT soi.parent
            FROM `tabDelivery Note Item` dni
            JOIN `tabSales Order Item` soi ON dni.so_detail = soi.name
            WHERE dni.parent = %(dn)s
            LIMIT 1
        """, {"dn": result["delivery_note"]}, as_dict=True)
        if so:
            result["sales_order"] = so[0].parent
            so_doc = frappe.db.get_value("Sales Order", so[0].parent, [
                "project", "customer"
            ], as_dict=True)
            if so_doc:
                if so_doc.project:
                    result["installation_project"] = so_doc.project
                if so_doc.customer:
                    result["customer"] = so_doc.customer

    # Sales Invoice from DN items
    if result.get("delivery_note"):
        invoice = frappe.db.sql("""
            SELECT DISTINCT sii.parent
            FROM `tabSales Invoice Item` sii
            JOIN `tabDelivery Note Item` dni ON sii.dn_detail = dni.name
            WHERE dni.parent = %(dn)s
            LIMIT 1
        """, {"dn": result["delivery_note"]}, as_dict=True)
        if invoice:
            result["sales_invoice"] = invoice[0].parent

    # Fallback: invoice from SO
    if not result.get("sales_invoice") and result.get("sales_order"):
        invoice = frappe.db.sql("""
            SELECT DISTINCT sii.parent
            FROM `tabSales Invoice Item` sii
            JOIN `tabSales Order Item` soi ON sii.so_detail = soi.name
            WHERE soi.parent = %(so)s
            LIMIT 1
        """, {"so": result["sales_order"]}, as_dict=True)
        if invoice:
            result["sales_invoice"] = invoice[0].parent

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

    so = frappe.db.get_value("Sales Order", sales_order, [
        "customer", "project", "transaction_date", "delivery_date", "company"
    ], as_dict=True)

    if not so:
        frappe.throw(_("Sales Order {0} not found.").format(sales_order))

    result = {
        "customer": so.customer,
        "installation_project": so.project,
        "source_delivery_date": so.delivery_date or so.transaction_date,
    }

    result["site_address"] = _resolve_site_address(so.customer, so.project)
    result["customer_tier"] = _get_customer_tier(so.customer)

    if so.project:
        result["recurrence_count"] = _count_recurrences(project=so.project)
    elif so.customer:
        result["recurrence_count"] = _count_recurrences(customer=so.customer)

    # Linked Delivery Note
    dns = frappe.db.sql("""
        SELECT DISTINCT dni.parent
        FROM `tabDelivery Note Item` dni
        JOIN `tabSales Order Item` soi ON dni.so_detail = soi.name
        WHERE soi.parent = %(so)s
        LIMIT 1
    """, {"so": sales_order}, as_dict=True)
    if dns:
        result["delivery_note"] = dns[0].parent

    # Linked Sales Invoice
    invoices = frappe.db.sql("""
        SELECT DISTINCT sii.parent
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Order Item` soi ON sii.so_detail = soi.name
        WHERE soi.parent = %(so)s
        LIMIT 1
    """, {"so": sales_order}, as_dict=True)
    if invoices:
        result["sales_invoice"] = invoices[0].parent

    if result.get("source_delivery_date"):
        result["days_since_delivery"] = date_diff(today(), result["source_delivery_date"])

    return result


@frappe.whitelist()
def resolve_from_delivery_note(delivery_note):
    """Given a Delivery Note, resolve: Customer, posting date, SO, project."""
    if not delivery_note:
        return {}

    dn = frappe.db.get_value("Delivery Note", delivery_note, [
        "customer", "posting_date", "project", "company"
    ], as_dict=True)

    if not dn:
        frappe.throw(_("Delivery Note {0} not found.").format(delivery_note))

    result = {
        "customer": dn.customer,
        "source_delivery_date": dn.posting_date,
        "installation_project": dn.project,
    }

    result["site_address"] = _resolve_site_address(dn.customer, dn.project)
    result["customer_tier"] = _get_customer_tier(dn.customer)

    # Linked SO
    so = frappe.db.sql("""
        SELECT DISTINCT soi.parent
        FROM `tabDelivery Note Item` dni
        JOIN `tabSales Order Item` soi ON dni.so_detail = soi.name
        WHERE dni.parent = %(dn)s
        LIMIT 1
    """, {"dn": delivery_note}, as_dict=True)
    if so:
        result["sales_order"] = so[0].parent

    # Linked invoice
    invoice = frappe.db.sql("""
        SELECT DISTINCT sii.parent
        FROM `tabSales Invoice Item` sii
        JOIN `tabDelivery Note Item` dni ON sii.dn_detail = dni.name
        WHERE dni.parent = %(dn)s
        LIMIT 1
    """, {"dn": delivery_note}, as_dict=True)
    if invoice:
        result["sales_invoice"] = invoice[0].parent

    if dn.project:
        result["recurrence_count"] = _count_recurrences(project=dn.project)
    elif dn.customer:
        result["recurrence_count"] = _count_recurrences(customer=dn.customer)
    else:
        result["recurrence_count"] = 0

    result["days_since_delivery"] = date_diff(today(), dn.posting_date)

    return result


@frappe.whitelist()
def resolve_from_customer(customer):
    """Given a Customer, fill basic context."""
    if not customer:
        return {}

    cust = frappe.db.get_value("Customer", customer, [
        "customer_name", "customer_primary_contact", "primary_address"
    ], as_dict=True)
    if not cust:
        return {}

    result = {
        "customer_tier": _get_customer_tier(customer),
        "recurrence_count": _count_recurrences(customer=customer),
    }

    if cust.customer_primary_contact:
        result["contact"] = cust.customer_primary_contact

    if cust.primary_address:
        result["site_address"] = cust.primary_address

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
    if project:
        addr = frappe.db.get_value("Project", project, "custom_site_address")
        if addr:
            return addr

    if customer:
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
