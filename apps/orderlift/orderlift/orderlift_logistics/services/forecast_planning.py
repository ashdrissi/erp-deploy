import frappe
from frappe.utils import flt, now_datetime, getdate

from orderlift.orderlift_logistics.services.load_planning import (
    _get_item_metrics,
)
from orderlift.orderlift_logistics.services.capacity_math import round3


# ---------------------------------------------------------------------------
# Flow scope → allowed source doctypes
# Inbound  = importing from suppliers  → Purchase Order only
# Domestic = local distribution        → Quotation, Sales Order, Delivery Note
# Outbound = export to customers       → Quotation, Sales Order, Delivery Note
# ---------------------------------------------------------------------------

FLOW_SCOPE_ALLOWED_DOCTYPES = {
    "Inbound": ["Purchase Order"],
    "Domestic": ["Quotation", "Sales Order", "Delivery Note"],
    "Outbound": ["Quotation", "Sales Order", "Delivery Note"],
}


def allowed_doctypes_for_flow(flow_scope):
    """Return list of allowed source doctypes for a flow scope, or all if unset."""
    if not flow_scope:
        return list(DOCTYPE_CONFIG.keys())
    return FLOW_SCOPE_ALLOWED_DOCTYPES.get(flow_scope, list(DOCTYPE_CONFIG.keys()))


# ---------------------------------------------------------------------------
# Source queue: normalise Quotation / Sales Order / Purchase Order / DN
# into a uniform shape for the planner UI
# ---------------------------------------------------------------------------

DOCTYPE_CONFIG = {
    "Quotation": {
        "abbr": "QT",
        "party_field": "party_name",
        "party_type": "Customer",
        "party_link_field": "party_name",
        "date_field": "transaction_date",
        "items_table": "items",
        "extra_filters": {},
    },
    "Sales Order": {
        "abbr": "SO",
        "party_field": "customer_name",
        "party_type": "Customer",
        "party_link_field": "customer",
        "date_field": "transaction_date",
        "items_table": "items",
        "extra_filters": {"status": ["not in", ["Closed", "Cancelled"]]},
    },
    "Purchase Order": {
        "abbr": "PO",
        "party_field": "supplier_name",
        "party_type": "Supplier",
        "party_link_field": "supplier",
        "date_field": "transaction_date",
        "items_table": "items",
        "extra_filters": {
            "status": ["not in", ["Closed", "Cancelled", "Completed"]],
            "per_received": ["<", 100],
        },
    },
    "Delivery Note": {
        "abbr": "DN",
        "party_field": "customer_name",
        "party_type": "Customer",
        "party_link_field": "customer",
        "date_field": "posting_date",
        "items_table": "items",
        "extra_filters": {"docstatus": 1},
    },
}


def _compute_doc_totals(doctype, doc_name):
    """Compute weight/volume totals and line items for any source doc."""
    doc = frappe.get_doc(doctype, doc_name)
    cfg = DOCTYPE_CONFIG.get(doctype, {})
    items_field = cfg.get("items_table", "items")

    total_weight = 0.0
    total_volume = 0.0
    line_items = []

    for row in getattr(doc, items_field, []) or []:
        qty = flt(row.qty)
        unit_w, unit_v = _get_item_metrics(row.item_code)
        line_w = qty * unit_w
        line_v = qty * unit_v
        total_weight += line_w
        total_volume += line_v
        line_items.append({
            "item_code": row.item_code,
            "item_name": getattr(row, "item_name", row.item_code),
            "qty": qty,
            "unit_weight_kg": round3(unit_w),
            "unit_volume_m3": round3(unit_v),
            "line_weight_kg": round3(line_w),
            "line_volume_m3": round3(line_v),
        })

    return {
        "total_weight_kg": round3(total_weight),
        "total_volume_m3": round3(total_volume),
        "item_count": len(line_items),
        "line_items": line_items,
    }


def _infer_confidence(doctype, docstatus):
    """Map doctype + docstatus to a confidence level."""
    if doctype == "Quotation":
        return "inquiry"
    if docstatus == 1:
        return "committed"
    return "tentative"


@frappe.whitelist()
def get_forecast_source_queue(company=None, flow_scope=None, shipping_responsibility=None,
                               destination_zone=None, source_types=None):
    """Return normalised source documents for the planner queue.

    Args:
        company: filter by company
        flow_scope: Inbound/Domestic/Outbound
        shipping_responsibility: Orderlift/Customer
        destination_zone: zone string
        source_types: JSON list like ["Sales Order","Purchase Order"] or None for all

    Returns:
        list of queue-item dicts
    """
    import json
    if source_types and isinstance(source_types, str):
        source_types = json.loads(source_types)
    if not source_types:
        source_types = list(DOCTYPE_CONFIG.keys())

    # Enforce flow scope compatibility
    allowed = allowed_doctypes_for_flow(flow_scope)
    source_types = [dt for dt in source_types if dt in allowed]

    results = []
    for dt in source_types:
        cfg = DOCTYPE_CONFIG.get(dt)
        if not cfg:
            continue

        filters = dict(cfg.get("extra_filters") or {})
        if company:
            filters["company"] = company

        # Logistics custom fields (may not exist on Quotation)
        if flow_scope and frappe.db.has_column(dt, "custom_flow_scope"):
            filters["custom_flow_scope"] = flow_scope
        if shipping_responsibility and frappe.db.has_column(dt, "custom_shipping_responsibility"):
            filters["custom_shipping_responsibility"] = shipping_responsibility
        if destination_zone and frappe.db.has_column(dt, "custom_destination_zone"):
            filters["custom_destination_zone"] = destination_zone

        fields = [
            "name",
            f"`{cfg['date_field']}` as doc_date",
            "docstatus",
            "company",
        ]
        # party field
        if frappe.db.has_column(dt, cfg["party_field"]):
            fields.append(f"`{cfg['party_field']}` as party_name")
        if frappe.db.has_column(dt, cfg["party_link_field"]):
            fields.append(f"`{cfg['party_link_field']}` as party_link")

        docs = frappe.get_all(
            dt,
            filters=filters,
            fields=fields,
            order_by=f"{cfg['date_field']} asc, creation asc",
            limit_page_length=200,
        )

        for doc in docs:
            totals = _compute_doc_totals(dt, doc.name)
            results.append({
                "id": doc.name,
                "source_doctype": dt,
                "type": cfg["abbr"],
                "party": doc.get("party_name") or doc.get("party_link") or "",
                "party_type": cfg["party_type"],
                "party_link": doc.get("party_link") or "",
                "date": str(doc.get("doc_date") or ""),
                "docstatus": doc.docstatus,
                "docstatus_label": "Submitted" if doc.docstatus == 1 else "Draft",
                "confidence": _infer_confidence(dt, doc.docstatus),
                "volume": totals["total_volume_m3"],
                "weight": totals["total_weight_kg"],
                "item_count": totals["item_count"],
                "line_items": totals["line_items"],
            })

    return results


@frappe.whitelist()
def get_plan_detail(plan_name):
    """Load a Forecast Load Plan with its items + container profile capacity."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("read")

    profile = None
    if doc.container_profile:
        profile = frappe.get_cached_doc("Container Profile", doc.container_profile)

    plan_items = []
    for row in doc.items or []:
        # Fetch line items from source doc
        totals = _compute_doc_totals(row.source_doctype, row.source_name)
        cfg = DOCTYPE_CONFIG.get(row.source_doctype, {})
        plan_items.append({
            "row_name": row.name,
            "id": row.source_name,
            "source_doctype": row.source_doctype,
            "type": cfg.get("abbr", row.source_doctype[:2].upper()),
            "party": row.party or "",
            "party_type": row.party_type or "",
            "confidence": row.confidence or "tentative",
            "docstatus_label": row.docstatus_label or "",
            "volume": flt(row.total_volume_m3),
            "weight": flt(row.total_weight_kg),
            "item_count": flt(row.item_count),
            "date": str(row.date or ""),
            "selected": row.selected,
            "sequence": row.sequence,
            "line_items": totals["line_items"],
        })

    return {
        "name": doc.name,
        "plan_label": doc.plan_label,
        "company": doc.company,
        "container_profile": doc.container_profile,
        "flow_scope": doc.flow_scope,
        "shipping_responsibility": doc.shipping_responsibility,
        "destination_zone": doc.destination_zone,
        "departure_date": str(doc.departure_date or ""),
        "deadline": str(doc.deadline or ""),
        "status": doc.status,
        "total_weight_kg": flt(doc.total_weight_kg),
        "total_volume_m3": flt(doc.total_volume_m3),
        "weight_utilization_pct": flt(doc.weight_utilization_pct),
        "volume_utilization_pct": flt(doc.volume_utilization_pct),
        "container_load_plan": doc.container_load_plan,
        "notes": doc.notes,
        "items": plan_items,
        "container": {
            "name": profile.name,
            "container_name": profile.container_name,
            "container_type": profile.container_type,
            "max_weight_kg": flt(profile.max_weight_kg),
            "max_volume_m3": flt(profile.max_volume_m3),
        } if profile else None,
        "allowed_doctypes": allowed_doctypes_for_flow(doc.flow_scope),
    }


@frappe.whitelist()
def add_item_to_plan(plan_name, source_doctype, source_name):
    """Add a source document to a Forecast Load Plan."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    # Enforce flow scope compatibility
    allowed = allowed_doctypes_for_flow(doc.flow_scope)
    if source_doctype not in allowed:
        frappe.throw(
            f"{source_doctype} is not compatible with {doc.flow_scope or 'unset'} flow scope. "
            f"Allowed: {', '.join(allowed)}"
        )

    # Prevent duplicates
    for row in doc.items or []:
        if row.source_doctype == source_doctype and row.source_name == source_name:
            frappe.throw(f"{source_name} is already in this plan.")

    cfg = DOCTYPE_CONFIG.get(source_doctype, {})
    totals = _compute_doc_totals(source_doctype, source_name)
    source_doc = frappe.get_doc(source_doctype, source_name)

    party_type = cfg.get("party_type", "Customer")
    party = ""
    if cfg.get("party_link_field"):
        party = getattr(source_doc, cfg["party_link_field"], "")

    confidence = _infer_confidence(source_doctype, source_doc.docstatus)

    doc.append("items", {
        "source_doctype": source_doctype,
        "source_name": source_name,
        "party_type": party_type,
        "party": party,
        "confidence": confidence,
        "docstatus_label": "Submitted" if source_doc.docstatus == 1 else "Draft",
        "total_weight_kg": totals["total_weight_kg"],
        "total_volume_m3": totals["total_volume_m3"],
        "item_count": totals["item_count"],
        "date": getattr(source_doc, cfg.get("date_field", "creation"), None),
        "selected": 1,
        "sequence": len(doc.items),
    })

    doc.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


@frappe.whitelist()
def remove_item_from_plan(plan_name, source_name):
    """Remove a source document from a Forecast Load Plan."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    doc.items = [row for row in (doc.items or [])
                 if row.source_name != source_name]

    doc.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


@frappe.whitelist()
def update_item_confidence(plan_name, source_name, confidence):
    """Update confidence level for a plan item."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    for row in doc.items or []:
        if row.source_name == source_name:
            row.confidence = confidence
            break

    doc.save(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist()
def convert_to_clp(plan_name):
    """Convert a Forecast Load Plan into a Container Load Plan.

    Only committed/ready items with compatible source types (DN/PO) are pushed.
    Updates forecast status to Converted and links the CLP.
    """
    forecast = frappe.get_doc("Forecast Load Plan", plan_name)
    forecast.check_permission("write")

    if forecast.status == "Converted":
        frappe.throw("This forecast plan has already been converted.")

    if not forecast.container_profile:
        frappe.throw("Container Profile is required before converting.")

    # Determine source_type for CLP
    convertible_types = {"Delivery Note", "Purchase Order"}
    eligible_rows = [
        row for row in (forecast.items or [])
        if row.selected
        and row.confidence in ("committed", "ready")
        and row.source_doctype in convertible_types
    ]

    if not eligible_rows:
        frappe.throw("No committed/ready Delivery Notes or Purchase Orders to convert.")

    # Determine CLP source_type from majority
    dn_count = sum(1 for r in eligible_rows if r.source_doctype == "Delivery Note")
    po_count = sum(1 for r in eligible_rows if r.source_doctype == "Purchase Order")
    source_type = "Delivery Note" if dn_count >= po_count else "Purchase Order"

    clp = frappe.new_doc("Container Load Plan")
    clp.container_label = forecast.plan_label
    clp.container_profile = forecast.container_profile
    clp.company = forecast.company
    clp.flow_scope = forecast.flow_scope or "Domestic"
    clp.shipping_responsibility = forecast.shipping_responsibility or "Orderlift"
    clp.source_type = source_type
    clp.destination_zone = forecast.destination_zone or ""
    clp.departure_date = forecast.departure_date or getdate()
    clp.status = "Planning"

    seq = 0
    for row in eligible_rows:
        shipment = {
            "shipment_weight_kg": flt(row.total_weight_kg),
            "shipment_volume_m3": flt(row.total_volume_m3),
            "selected": 1,
            "sequence": seq,
        }
        if row.source_doctype == "Delivery Note":
            shipment["delivery_note"] = row.source_name
            shipment["customer"] = row.party if row.party_type == "Customer" else ""
        elif row.source_doctype == "Purchase Order":
            shipment["purchase_order"] = row.source_name
            shipment["supplier"] = row.party if row.party_type == "Supplier" else ""

        clp.append("shipments", shipment)
        seq += 1

    clp.insert(ignore_permissions=True)

    # Update forecast
    forecast.status = "Converted"
    forecast.container_load_plan = clp.name
    forecast.converted_on = now_datetime()
    forecast.save(ignore_permissions=True)

    return {
        "clp_name": clp.name,
        "clp_label": clp.container_label,
        "forecast_status": "Converted",
    }


@frappe.whitelist()
def get_container_profiles():
    """Return active container profiles for sidebar selection."""
    return frappe.get_all(
        "Container Profile",
        filters={"is_active": 1},
        fields=["name", "container_name", "container_type", "max_weight_kg", "max_volume_m3"],
        order_by="cost_rank asc, max_volume_m3 asc",
        limit_page_length=0,
    )
