"""
Stock Router
------------
After a Purchase Receipt is submitted, routes received items to the
correct warehouse based on quality inspection result:
  - QC passed  → Real Stock warehouse (-REAL)
  - QC failed  → Return warehouse (-RETURN) and notifies supplier

Called via hooks.py doc_events on Purchase Receipt (on_submit).
"""

import frappe
from frappe.utils import nowdate


def route_received_stock(doc, method=None):
    """Route received stock to REAL or RETURN warehouse after QC."""
    if not doc or doc.docstatus != 1:
        return

    # Group items by QC status
    qc_passed = []
    qc_failed = []

    for item_row in doc.items or []:
        item_code = item_row.item_code
        qty = item_row.qty

        # Check quality inspection status
        # In ERPNext, quality_inspection is linked on item row
        # If inspection is linked and status is "Rejected", it's failed
        if item_row.quality_inspection:
            inspection = frappe.get_doc("Quality Inspection", item_row.quality_inspection)
            if inspection.status == "Rejected":
                qc_failed.append({
                    "item_code": item_code,
                    "qty": qty,
                    "warehouse": doc.warehouse,
                    "inspection": item_row.quality_inspection,
                })
            else:
                qc_passed.append({
                    "item_code": item_code,
                    "qty": qty,
                    "warehouse": doc.warehouse,
                    "inspection": item_row.quality_inspection,
                })
        else:
            # If no QC inspection linked, assume passed
            qc_passed.append({
                "item_code": item_code,
                "qty": qty,
                "warehouse": doc.warehouse,
                "inspection": None,
            })

    # Route passed items to REAL warehouse
    if qc_passed:
        _create_warehouse_transfer(doc, qc_passed, "REAL")

    # Route failed items to RETURN warehouse
    if qc_failed:
        _create_warehouse_transfer(doc, qc_failed, "RETURN")
        _notify_suppliers_of_failures(doc, qc_failed)

    # Update PR status if all processed
    if qc_passed or qc_failed:
        frappe.db.set_value("Purchase Receipt", doc.name, "custom_qc_routed", 1)


def _create_warehouse_transfer(pr_doc, items, destination_type):
    """Create Stock Entry to transfer items to destination warehouse."""
    if not items:
        return

    # Determine destination warehouse
    source_warehouse = pr_doc.warehouse
    dest_warehouse = _get_destination_warehouse(source_warehouse, destination_type)

    if not dest_warehouse:
        frappe.log_error(
            f"Cannot find {destination_type} warehouse for {source_warehouse}",
            "Stock Router Error"
        )
        return

    # Create Stock Entry (Material Transfer)
    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.doctype = "Stock Entry"
    stock_entry.stock_entry_type = "Material Transfer"
    stock_entry.posting_date = nowdate()
    stock_entry.from_warehouse = source_warehouse
    stock_entry.to_warehouse = dest_warehouse
    stock_entry.custom_source_pr = pr_doc.name

    for item in items:
        stock_entry.append("items", {
            "item_code": item["item_code"],
            "qty": item["qty"],
            "s_warehouse": source_warehouse,
            "t_warehouse": dest_warehouse,
        })

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    frappe.msgprint(
        f"Stock Entry {stock_entry.name} created for {destination_type} routing",
        title="Stock Routed"
    )


def _get_destination_warehouse(source_warehouse, destination_type):
    """
    Get destination warehouse based on source and type.
    Convention: source_warehouse + "-REAL" or "-RETURN"
    Example: "Main Warehouse" → "Main Warehouse-REAL" or "Main Warehouse-RETURN"
    """
    dest_name = f"{source_warehouse}-{destination_type}"

    # Check if destination warehouse exists
    exists = frappe.db.exists("Warehouse", dest_name)
    if exists:
        return dest_name

    # If not, try with parent warehouse pattern
    # Example: "Main Warehouse-QC" → look for "Main Warehouse-REAL"
    base_warehouse = source_warehouse.replace("-QC", "").replace("-TEMP", "")
    dest_alt = f"{base_warehouse}-{destination_type}"

    exists = frappe.db.exists("Warehouse", dest_alt)
    if exists:
        return dest_alt

    return None


def _notify_suppliers_of_failures(pr_doc, failed_items):
    """Notify supplier when QC fails items."""
    supplier = pr_doc.supplier
    if not supplier:
        return

    supplier_doc = frappe.get_doc("Supplier", supplier)
    supplier_contact = supplier_doc.supplier_primary_contact
    supplier_email = None

    if supplier_contact:
        contact = frappe.get_doc("Contact", supplier_contact)
        supplier_email = contact.email_id or contact.email

    if not supplier_email:
        frappe.log_error(
            f"No email found for supplier {supplier}",
            "Stock Router Notification Error"
        )
        return

    # Create notification
    items_text = "\n".join([f"- {item['item_code']}: {item['qty']} units" for item in failed_items])

    frappe.sendmail(
        recipients=[supplier_email],
        subject=f"Quality Inspection Failed — Purchase Receipt {pr_doc.name}",
        message=f"""
Hello,

The following items in Purchase Receipt {pr_doc.name} have failed quality inspection:

{items_text}

Please contact us to arrange return/replacement.

Best regards,
{frappe.db.get_value('Company', pr_doc.company, 'company_name') or 'Orderlift'}
        """.strip(),
        reference_doctype="Purchase Receipt",
        reference_name=pr_doc.name,
    )
