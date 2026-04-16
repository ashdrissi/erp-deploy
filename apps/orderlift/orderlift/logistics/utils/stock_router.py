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

    if doc.get("custom_qc_routed"):
        return

    # Group items by QC status
    qc_passed = []
    qc_failed = []

    for item_row in doc.items or []:
        item_code = item_row.item_code
        qty = item_row.qty
        source_warehouse = _get_source_warehouse(doc, item_row)

        if not source_warehouse:
            frappe.log_error(
                f"Cannot route item {item_code} on Purchase Receipt {doc.name}: missing source warehouse",
                "Stock Router Error",
            )
            continue

        # Check quality inspection status
        # In ERPNext, quality_inspection is linked on item row
        # If inspection is linked and status is "Rejected", it's failed
        if item_row.quality_inspection:
            inspection = frappe.get_doc("Quality Inspection", item_row.quality_inspection)
            if inspection.status == "Rejected":
                qc_failed.append({
                    "item_code": item_code,
                    "qty": qty,
                    "warehouse": source_warehouse,
                    "inspection": item_row.quality_inspection,
                })
            else:
                qc_passed.append({
                    "item_code": item_code,
                    "qty": qty,
                    "warehouse": source_warehouse,
                    "inspection": item_row.quality_inspection,
                })
        else:
            # If no QC inspection linked, assume passed
            qc_passed.append({
                "item_code": item_code,
                "qty": qty,
                "warehouse": source_warehouse,
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


@frappe.whitelist()
def get_purchase_receipt_routing_summary(purchase_receipt_name: str) -> dict:
    """Return routing visibility data for the Purchase Receipt form."""
    pr = frappe.get_doc("Purchase Receipt", purchase_receipt_name)

    passed = []
    failed = []
    no_qi = []
    inspections = []

    for row in pr.items or []:
        inspection_name = row.quality_inspection
        if not inspection_name:
            no_qi.append({"item_code": row.item_code, "qty": row.qty})
            continue

        inspection = frappe.get_doc("Quality Inspection", inspection_name)
        inspections.append(
            {
                "name": inspection_name,
                "item_code": row.item_code,
                "status": inspection.status,
            }
        )
        target = failed if inspection.status == "Rejected" else passed
        target.append({"item_code": row.item_code, "qty": row.qty, "inspection": inspection_name})

    source_warehouses = _get_source_warehouses(pr)
    source_warehouse = source_warehouses[0] if len(source_warehouses) == 1 else ""
    real_warehouse = [_get_destination_warehouse(wh, "REAL") for wh in source_warehouses]
    return_warehouse = [_get_destination_warehouse(wh, "RETURN") for wh in source_warehouses]

    transfer_fields = ["name", "stock_entry_type", "posting_date", "docstatus", "to_warehouse"]
    if frappe.db.has_column("Stock Entry", "custom_source_pr"):
        transfers = frappe.get_all(
            "Stock Entry",
            filters={"custom_source_pr": purchase_receipt_name},
            fields=transfer_fields,
            order_by="posting_date desc, modified desc",
            limit_page_length=10,
        )
    else:
        transfers = []

    return {
        "purchase_receipt": pr.name,
        "warehouse": source_warehouse,
        "warehouses": source_warehouses,
        "qc_routed": bool(pr.get("custom_qc_routed")),
        "passed": passed,
        "failed": failed,
        "no_qi": no_qi,
        "inspections": inspections,
        "real_warehouse": real_warehouse[0] if len(real_warehouse) == 1 else real_warehouse,
        "return_warehouse": return_warehouse[0] if len(return_warehouse) == 1 else return_warehouse,
        "transfers": transfers,
    }


def _create_warehouse_transfer(pr_doc, items, destination_type):
    """Create Stock Entry to transfer items to destination warehouse."""
    if not items:
        return

    items_by_source = {}
    for item in items:
        items_by_source.setdefault(item["warehouse"], []).append(item)

    for source_warehouse, warehouse_items in items_by_source.items():
        dest_warehouse = _get_destination_warehouse(source_warehouse, destination_type)

        if not dest_warehouse:
            frappe.log_error(
                f"Cannot find {destination_type} warehouse for {source_warehouse}",
                "Stock Router Error",
            )
            continue

        if dest_warehouse == source_warehouse:
            continue

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.doctype = "Stock Entry"
        stock_entry.stock_entry_type = "Material Transfer"
        stock_entry.posting_date = nowdate()
        stock_entry.from_warehouse = source_warehouse
        stock_entry.to_warehouse = dest_warehouse
        if frappe.db.has_column("Stock Entry", "custom_source_pr"):
            stock_entry.custom_source_pr = pr_doc.name

        for item in warehouse_items:
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
            title="Stock Routed",
        )


def _get_source_warehouse(pr_doc, item_row):
    """Resolve the source warehouse for a Purchase Receipt item row."""
    return item_row.get("warehouse") or pr_doc.get("set_warehouse") or ""


def _get_source_warehouses(pr_doc):
    """Return the unique source warehouses present on a Purchase Receipt."""
    warehouses = []
    for row in pr_doc.items or []:
        warehouse = _get_source_warehouse(pr_doc, row)
        if warehouse and warehouse not in warehouses:
            warehouses.append(warehouse)
    return warehouses


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
