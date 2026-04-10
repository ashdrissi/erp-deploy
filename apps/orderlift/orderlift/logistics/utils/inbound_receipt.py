"""
Inbound Receipt
---------------
Manual draft Purchase Receipt creation from an inbound Container Load Plan.

Triggered via a button on the CLP form. Creates one draft PR per PO
in the plan. Does NOT auto-submit — user must review and submit each PR.

Called via whitelisted method:
  orderlift.logistics.utils.inbound_receipt.create_draft_purchase_receipts
"""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def create_draft_purchase_receipts(load_plan_name):
    """Create draft Purchase Receipts from an inbound CLP.

    One PR per unique Purchase Order in the plan. Skips POs that already
    have a non-cancelled PR. Does NOT auto-submit.

    Args:
        load_plan_name: Name of the Container Load Plan.

    Returns:
        dict with 'created' list of PR names and 'skipped' count.
    """
    plan = frappe.get_doc("Container Load Plan", load_plan_name)

    # Safety checks
    if plan.flow_scope != "Inbound":
        frappe.throw("Purchase Receipt creation is only for inbound plans.")
    if plan.source_type != "Purchase Order":
        frappe.throw("This plan does not use Purchase Orders as source.")
    if plan.status not in ("Loading", "Delivered", "In Transit"):
        frappe.throw(
            f"Container must be Loading, In Transit, or Delivered to create receipts. "
            f"Current status: {plan.status}"
        )

    created = []
    skipped = 0

    # Collect unique POs from the plan
    processed_pos = set()
    for row in plan.shipments or []:
        po_name = row.get("purchase_order")
        if not po_name or po_name in processed_pos:
            continue
        processed_pos.add(po_name)

        # Check if a non-cancelled PR already exists for this PO
        existing = frappe.get_all(
            "Purchase Receipt",
            filters={
                "docstatus": ["!=", 2],
            },
            or_filters={
                "purchase_order": po_name,
            },
            limit=1,
        )

        # Also check via PR items for POs mapped through the standard flow
        if not existing:
            existing = frappe.get_all(
                "Purchase Receipt Item",
                filters={"purchase_order": po_name, "docstatus": ["!=", 2]},
                fields=["parent"],
                limit=1,
            )

        if existing:
            skipped += 1
            continue

        # Create draft PR from PO
        pr = _create_pr_from_po(po_name, plan.company)
        if pr:
            created.append(pr.name)

    frappe.db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "message": f"Created {len(created)} draft Purchase Receipt(s). {skipped} skipped (already exist).",
    }


def _create_pr_from_po(po_name, company):
    """Create a single draft Purchase Receipt from a Purchase Order."""
    po = frappe.get_doc("Purchase Order", po_name)

    pr = frappe.new_doc("Purchase Receipt")
    pr.supplier = po.supplier
    pr.company = company or po.company
    pr.buying_price_list = po.buying_price_list
    pr.currency = po.currency
    pr.conversion_rate = po.conversion_rate

    for po_item in po.items or []:
        # Only include items that haven't been fully received
        pending_qty = flt(po_item.qty) - flt(po_item.received_qty)
        if pending_qty <= 0:
            continue

        pr.append("items", {
            "item_code": po_item.item_code,
            "item_name": po_item.item_name,
            "description": po_item.description,
            "qty": pending_qty,
            "uom": po_item.uom,
            "stock_uom": po_item.stock_uom,
            "conversion_factor": po_item.conversion_factor,
            "rate": po_item.rate,
            "amount": pending_qty * flt(po_item.rate),
            "warehouse": po_item.warehouse,
            "purchase_order": po_name,
            "purchase_order_item": po_item.name,
        })

    if not pr.items:
        return None  # All items already received

    pr.flags.ignore_permissions = True
    pr.insert()

    frappe.msgprint(
        f"Draft Purchase Receipt <b>{pr.name}</b> created from {po_name}.",
        indicator="green",
        alert=True,
    )
    return pr
