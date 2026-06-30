import json

import frappe
from frappe.utils import cint, flt

from orderlift.warehouse_access import stock_warehouse_condition

from orderlift.orderlift_logistics.doctype.container_profile.container_profile import (
    DEFAULT_INTERNAL_DIMENSIONS_CM,
    derive_internal_dimensions_cm,
)
from orderlift.orderlift_logistics.services.load_planning import (
    _get_item_metrics,
    _get_packaging_metrics,
    _get_row_metrics,
)
from orderlift.orderlift_logistics.services.capacity_math import round3


# ---------------------------------------------------------------------------
# Flow scope → allowed source doctypes
# Inbound  = importing from suppliers  → Purchase Order only
# Domestic = local distribution        → Quotation, Sales Order, Delivery Note
# Outbound = export to customers       → Quotation, Sales Order, Delivery Note
# ---------------------------------------------------------------------------

FLOW_SCOPE_ALLOWED_DOCTYPES = {
    "Inbound": ["Purchase Order", "Material Request"],
    "Domestic": ["Opportunity", "Quotation", "Sales Order", "Delivery Note", "Material Request"],
    "Outbound": ["Opportunity", "Quotation", "Sales Order", "Delivery Note", "Material Request"],
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
    "Opportunity": {
        "abbr": "OPP",
        "party_field": "party_name",
        "party_type": "Customer",
        "party_link_field": "party_name",
        "date_field": "transaction_date",
        "items_table": "items",
        "extra_filters": {"status": ["not in", ["Closed", "Lost"]]},
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
    "Material Request": {
        "abbr": "MR",
        "party_field": "company",
        "party_type": "Company",
        "party_link_field": "company",
        "date_field": "transaction_date",
        "items_table": "items",
        "extra_filters": {"docstatus": ["!=", 2], "status": ["not in", ["Stopped", "Cancelled"]]},
    },
}


def _compute_doc_totals(doctype, doc_name, packaging_overrides=None):
    """Compute weight/volume totals and line items for any source doc."""
    doc = frappe.get_doc(doctype, doc_name)
    cfg = DOCTYPE_CONFIG.get(doctype, {})
    items_field = cfg.get("items_table", "items")

    packaging_overrides = packaging_overrides or {}
    total_weight = 0.0
    total_volume = 0.0
    line_items = []

    for row in getattr(doc, items_field, []) or []:
        qty = flt(row.qty)
        override_profile = packaging_overrides.get(row.name)
        metrics = _get_row_metrics(row, parent_doctype=doctype, packaging_profile=override_profile)
        packaging_source = metrics.get("packaging_source") or "item_fallback"
        if override_profile and packaging_source != "item_fallback":
            packaging_source = "planner_override"
        unit_w = flt(metrics["unit_weight_kg"])
        unit_v = flt(metrics["unit_volume_m3"])
        line_w = flt(metrics["line_weight_kg"])
        line_v = flt(metrics["line_volume_m3"])
        total_weight += line_w
        total_volume += line_v
        line_items.append({
            "item_code": row.item_code,
            "item_name": getattr(row, "item_name", row.item_code),
            "qty": qty,
            "source_row_name": row.name,
            "package_count": flt(metrics.get("package_count") or 0),
            "packaging_profile": metrics.get("resolved_profile_name") or "",
            "packaging_type": metrics.get("packaging_type") or "",
            "packaging_source": packaging_source,
            "resolved_uom": metrics.get("resolved_uom") or "",
            "unit_weight_kg": round3(unit_w),
            "unit_volume_m3": round3(unit_v),
            "length_cm": round3(metrics.get("length_cm")),
            "width_cm": round3(metrics.get("width_cm")),
            "height_cm": round3(metrics.get("height_cm")),
            "line_weight_kg": round3(line_w),
            "line_volume_m3": round3(line_v),
        })

    return {
        "total_weight_kg": round3(total_weight),
        "total_volume_m3": round3(total_volume),
        "item_count": len(line_items),
        "line_items": line_items,
    }


def _load_packaging_overrides(row):
    raw = getattr(row, "packaging_overrides_json", "") or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_packaging_layout(doc):
    raw = getattr(doc, "packaging_layout_json", "") or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _get_item_uom_data(item_code):
    """Get UOM and conversion data for an Item."""
    values = frappe.db.get_value(
        "Item", item_code,
        ["stock_uom", "purchase_uom", "min_order_qty"],
        as_dict=True,
    )
    if not values:
        return {"stock_uom": "Nos", "purchase_uom": "Nos", "min_order_qty": 0, "uom_conversion_factor": 1}

    stock_uom = values.stock_uom or "Nos"
    purchase_uom = values.purchase_uom or stock_uom

    # Get conversion factor: how many stock units per purchase unit
    uom_conversion_factor = 1.0
    if purchase_uom != stock_uom:
        conversion = frappe.db.get_value(
            "UOM Conversion Detail",
            {"parent": item_code, "uom": purchase_uom},
            "conversion_factor",
        )
        if conversion:
            uom_conversion_factor = flt(conversion)
        else:
            # Fallback: try to get from UOM table
            conversion = frappe.db.get_value(
                "UOM Conversion Detail",
                {"uom": purchase_uom},
                "conversion_factor",
            )
            if conversion:
                uom_conversion_factor = flt(conversion)

    return {
        "stock_uom": stock_uom,
        "purchase_uom": purchase_uom,
        "min_order_qty": flt(values.min_order_qty),
        "uom_conversion_factor": uom_conversion_factor,
    }


def _compute_single_item_metrics(item_code, qty):
    """Compute package-based weight/volume for a single item at a given qty."""
    metrics = _get_packaging_metrics(item_code=item_code, qty=qty)
    unit_w = flt(metrics.get("unit_weight_kg") or 0)
    unit_v = flt(metrics.get("unit_volume_m3") or 0)
    uom_data = _get_item_uom_data(item_code)
    return {
        "unit_weight_kg": round3(unit_w),
        "unit_volume_m3": round3(unit_v),
        "total_weight_kg": round3(metrics.get("line_weight_kg")),
        "total_volume_m3": round3(metrics.get("line_volume_m3")),
        "package_count": flt(metrics.get("package_count") or 0),
        "packaging_profile": metrics.get("resolved_profile_name") or "",
        "packaging_source": metrics.get("packaging_source") or "item_fallback",
        "packaging_type": metrics.get("packaging_type") or "",
        "resolved_uom": metrics.get("resolved_uom") or "",
        "length_cm": round3(metrics.get("length_cm")),
        "width_cm": round3(metrics.get("width_cm")),
        "height_cm": round3(metrics.get("height_cm")),
        **uom_data,
    }


def _infer_confidence(doctype, docstatus):
    """Map doctype + docstatus to a confidence level."""
    if doctype == "Quotation":
        return "inquiry"
    if docstatus == 1:
        return "committed"
    return "tentative"


def _container_dimensions_cm(profile):
    length = flt(getattr(profile, "length_cm", 0) or 0)
    width = flt(getattr(profile, "width_cm", 0) or 0)
    height = flt(getattr(profile, "height_cm", 0) or 0)
    if length > 0 and width > 0 and height > 0:
        return length, width, height

    defaults = DEFAULT_INTERNAL_DIMENSIONS_CM.get(getattr(profile, "container_type", "") or "")
    if defaults:
        return defaults

    derived = derive_internal_dimensions_cm(getattr(profile, "max_volume_m3", 0) or 0)
    if all(flt(value) > 0 for value in derived):
        return derived

    return length, width, height


def _has_column(doctype, fieldname):
    try:
        return frappe.db.has_column(doctype, fieldname)
    except Exception:
        return False


def _apply_company_filter(filters, doctype, company):
    company = (company or "").strip()
    if not company:
        return
    if _has_column(doctype, "company"):
        filters["company"] = company
    elif _has_column(doctype, "custom_company"):
        filters["custom_company"] = company


def _price_list_options(kind, company=None):
    from orderlift.orderlift_sales.utils.price_list_scope import get_item_price_access

    access = get_item_price_access(kind, company=company)
    if not access.get("permitted"):
        return []
    names = access.get("price_lists") or []
    if not names:
        return []
    return frappe.get_all(
        "Price List",
        filters={"name": ["in", names]},
        fields=["name", "currency"],
        order_by="name asc",
        limit_page_length=0,
    )


def _price_list_item_codes(price_list, kind, company=None):
    from orderlift.orderlift_sales.utils.price_list_scope import validate_price_list_scope

    price_list = validate_price_list_scope(price_list, kind=kind, required=False, company=company)
    if not price_list:
        return set()
    filters = {"price_list": price_list}
    if kind == "selling" and _has_column("Item Price", "selling"):
        filters["selling"] = 1
    if kind == "buying" and _has_column("Item Price", "buying"):
        filters["buying"] = 1
    return set(frappe.get_all("Item Price", filters=filters, pluck="item_code", limit_page_length=0) or [])


@frappe.whitelist()
def get_planner_price_lists(company=None):
    company = _active_planner_company(company)
    return {
        "selling": _price_list_options("selling", company=company),
        "buying": _price_list_options("buying", company=company),
    }


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
        _apply_company_filter(filters, dt, company)

        # Logistics custom fields (may not exist on Quotation)
        if flow_scope and _has_column(dt, "custom_flow_scope"):
            filters["custom_flow_scope"] = flow_scope
        if shipping_responsibility and _has_column(dt, "custom_shipping_responsibility"):
            filters["custom_shipping_responsibility"] = shipping_responsibility
        if destination_zone and _has_column(dt, "custom_destination_zone"):
            filters["custom_destination_zone"] = destination_zone

        fields = [
            "name",
            f"`{cfg['date_field']}` as doc_date",
            "docstatus",
        ]
        if _has_column(dt, "company"):
            fields.append("company")
        elif _has_column(dt, "custom_company"):
            fields.append("`custom_company` as company")
        # party field
        if _has_column(dt, cfg["party_field"]):
            fields.append(f"`{cfg['party_field']}` as party_name")
        if _has_column(dt, cfg["party_link_field"]):
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
    container_length_cm, container_width_cm, container_height_cm = _container_dimensions_cm(profile) if profile else (0, 0, 0)

    plan_items = []
    for row in doc.items or []:
        is_planned = row.is_planned or 0

        if is_planned:
            # Free/planning item — return single item metrics
            item_code = row.item_code or ""
            plan_items.append({
                "row_name": row.name,
                "id": f"PLAN-{row.name}",
                "source_doctype": "",
                "type": "PLAN",
                "party": row.party or "",
                "party_type": row.party_type or "",
                "confidence": row.confidence or "tentative",
                "docstatus_label": "",
                "volume": flt(row.total_volume_m3),
                "weight": flt(row.total_weight_kg),
                "item_count": 1,
                "date": str(row.date or ""),
                "selected": row.selected,
                "sequence": row.sequence,
                "is_planned": 1,
                "item_code": item_code,
                "item_name": row.item_name or item_code,
                "planned_qty": flt(row.planned_qty),
                "original_qty": flt(row.original_qty),
                "stock_uom": row.stock_uom or "",
                "purchase_uom": row.purchase_uom or "",
                "uom_conversion_factor": flt(row.uom_conversion_factor),
                "package_count": flt(getattr(row, "package_count", 0) or 0),
                "packaging_profile": getattr(row, "packaging_profile", "") or "",
                "packaging_source": getattr(row, "packaging_source", "") or "item_fallback",
                "length_cm": flt(getattr(row, "length_cm", 0) or 0),
                "width_cm": flt(getattr(row, "width_cm", 0) or 0),
                "height_cm": flt(getattr(row, "height_cm", 0) or 0),
                "line_items": [{
                    "item_code": item_code,
                    "item_name": row.item_name or item_code,
                    "qty": flt(row.planned_qty),
                    "package_count": flt(getattr(row, "package_count", 0) or 0),
                    "packaging_profile": getattr(row, "packaging_profile", "") or "",
                    "packaging_source": getattr(row, "packaging_source", "") or "item_fallback",
                    "resolved_uom": row.purchase_uom or row.stock_uom or "",
                    "unit_weight_kg": flt(row.unit_weight_kg),
                    "unit_volume_m3": flt(row.unit_volume_m3),
                    "length_cm": flt(getattr(row, "length_cm", 0) or 0),
                    "width_cm": flt(getattr(row, "width_cm", 0) or 0),
                    "height_cm": flt(getattr(row, "height_cm", 0) or 0),
                    "line_weight_kg": flt(row.total_weight_kg),
                    "line_volume_m3": flt(row.total_volume_m3),
                }],
            })
        else:
            # Sourced document — fetch line items from source doc
            overrides = _load_packaging_overrides(row)
            totals = _compute_doc_totals(row.source_doctype, row.source_name, packaging_overrides=overrides)
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
                "volume": flt(totals["total_volume_m3"]),
                "weight": flt(totals["total_weight_kg"]),
                "item_count": flt(totals["item_count"]),
                "date": str(row.date or ""),
                "selected": row.selected,
                "sequence": row.sequence,
                "is_planned": 0,
                "item_code": "",
                "item_name": "",
                "planned_qty": flt(row.planned_qty) or 1,
                "original_qty": flt(row.original_qty) or 1,
                "stock_uom": row.stock_uom or "",
                "purchase_uom": row.purchase_uom or "",
                "uom_conversion_factor": flt(row.uom_conversion_factor) or 1,
                "packaging_overrides_json": getattr(row, "packaging_overrides_json", "") or "",
                "line_items": totals["line_items"],
            })

    return {
        "name": doc.name,
        "plan_label": doc.plan_label,
        "company": doc.company,
        "container_profile": doc.container_profile,
        "route_origin": doc.route_origin or "",
        "route_destination": doc.route_destination or "",
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
        "notes": doc.notes,
        "items": plan_items,
        "packaging_layout": _load_packaging_layout(doc),
        "container": {
            "name": profile.name,
            "container_name": profile.container_name,
            "container_type": profile.container_type,
            "max_weight_kg": flt(profile.max_weight_kg),
            "max_volume_m3": flt(profile.max_volume_m3),
            "length_cm": container_length_cm,
            "width_cm": container_width_cm,
            "height_cm": container_height_cm,
        } if profile else None,
        "allowed_doctypes": allowed_doctypes_for_flow(doc.flow_scope),
        "capacity": get_capacity_status(plan_name),
    }


def _get_plan_capacity(forecast):
    """Return the container's max volume and weight for a forecast plan."""
    if not forecast.container_profile:
        return 0.0, 0.0
    profile = frappe.get_cached_doc("Container Profile", forecast.container_profile)
    return flt(profile.max_volume_m3), flt(profile.max_weight_kg)


def _check_capacity(doc, new_vol=0, new_wt=0):
    """Check if adding items would exceed container capacity.
    Returns (can_add, current_vol, current_wt, max_vol, max_wt, over_vol, over_wt).
    """
    max_vol, max_wt = _get_plan_capacity(doc)
    max_vol = flt(max_vol)
    max_wt = flt(max_wt)
    if not max_vol and not max_wt:
        return True, 0, 0, 0, 0, 0, 0  # no limits set

    current_vol = sum(flt(row.total_volume_m3) for row in (doc.items or []) if row.selected)
    current_wt = sum(flt(row.total_weight_kg) for row in (doc.items or []) if row.selected)

    total_vol = current_vol + new_vol
    total_wt = current_wt + new_wt

    over_vol = max(0, total_vol - max_vol) if max_vol > 0 else 0
    over_wt = max(0, total_wt - max_wt) if max_wt > 0 else 0

    # Hard limit: can't exceed weight. Volume can exceed with warning.
    if max_wt > 0 and total_wt > max_wt:
        return False, current_vol, current_wt, max_vol, max_wt, over_vol, over_wt

    return True, current_vol, current_wt, max_vol, max_wt, over_vol, over_wt


@frappe.whitelist()
def get_capacity_status(plan_name):
    """Return current capacity usage for a plan."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("read")

    max_vol, max_wt = _get_plan_capacity(doc)
    can_add, cur_vol, cur_wt, mx_vol, mx_wt, over_vol, over_wt = _check_capacity(doc)

    container_name = ""
    if doc.container_profile:
        cp = frappe.get_cached_doc("Container Profile", doc.container_profile)
        container_name = cp.container_name or cp.name

    return {
        "container_name": container_name,
        "max_volume_m3": max_vol or 0,
        "max_weight_kg": max_wt or 0,
        "used_volume_m3": round3(cur_vol),
        "used_weight_kg": round3(cur_wt),
        "volume_pct": round3((cur_vol / max_vol * 100) if max_vol > 0 else 0),
        "weight_pct": round3((cur_wt / max_wt * 100) if max_wt > 0 else 0),
        "remaining_volume_m3": round3(max(0, (max_vol or 0) - cur_vol)),
        "remaining_weight_kg": round3(max(0, (max_wt or 0) - cur_wt)),
        "over_volume": round3(over_vol),
        "over_weight": round3(over_wt),
        "at_weight_limit": over_wt > 0,
        "near_volume_limit": max_vol > 0 and cur_vol > 0 and (cur_vol / max_vol) > 0.9,
        "near_weight_limit": max_wt > 0 and cur_wt > 0 and (cur_wt / max_wt) > 0.9,
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

    # Check capacity before adding
    totals = _compute_doc_totals(source_doctype, source_name)
    can_add, cur_vol, cur_wt, max_vol, max_wt, over_vol, over_wt = _check_capacity(
        doc, totals["total_volume_m3"], totals["total_weight_kg"]
    )
    if not can_add:
        frappe.throw(
            f"Cannot add {source_name}: would exceed weight capacity. "
            f"Current: {round3(cur_wt)} / {round3(max_wt)} kg, "
            f"Would add {round3(totals['total_weight_kg'])} kg. "
            f"Remove items or choose a larger container."
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

    # Compute per-line-item metrics for the first item (aggregate row)
    # For sourced docs, planned_qty = original total item_count (documents, not units)
    # But for the line items we store individual metrics
    uom_data = _get_item_uom_data("Item")  # dummy — sourced items use aggregate totals

    doc.append("items", {
        "source_doctype": source_doctype,
        "source_name": source_name,
        "is_planned": 0,
        "party_type": party_type,
        "party": party,
        "confidence": confidence,
        "docstatus_label": "Submitted" if source_doc.docstatus == 1 else "Draft",
        "planned_qty": 1,  # 1 document row
        "original_qty": 1,
        "total_weight_kg": totals["total_weight_kg"],
        "total_volume_m3": totals["total_volume_m3"],
        "item_count": totals["item_count"],
        "packaging_overrides_json": "",
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


def _link_source_docs(forecast):
    """Write custom_forecast_plan link to all sourced submitted documents.
    Uses direct DB write to bypass submit validation.
    """
    field = "custom_forecast_plan"
    linked = []

    for row in forecast.items or []:
        if row.is_planned or not row.source_doctype or not row.source_name:
            continue
        if row.source_doctype not in ("Sales Order", "Purchase Order", "Delivery Note"):
            continue

        # Check docstatus via DB
        docstatus = frappe.db.get_value(row.source_doctype, row.source_name, "docstatus")
        if docstatus != 1:
            continue

        # Direct DB update to bypass submit validation
        current = frappe.db.get_value(row.source_doctype, row.source_name, field)
        if current != forecast.name:
            frappe.db.set_value(row.source_doctype, row.source_name, field, forecast.name)
            linked.append(f"{row.source_doctype} {row.source_name}")

    return linked


def _unlink_source_docs(forecast):
    """Clear custom_forecast_plan link from all sourced documents.
    Uses direct DB write to bypass submit validation.
    """
    field = "custom_forecast_plan"
    unlinked = []

    for row in forecast.items or []:
        if row.is_planned or not row.source_doctype or not row.source_name:
            continue
        if row.source_doctype not in ("Sales Order", "Purchase Order", "Delivery Note"):
            continue

        current = frappe.db.get_value(row.source_doctype, row.source_name, field)
        if current == forecast.name:
            frappe.db.set_value(row.source_doctype, row.source_name, field, None)
            unlinked.append(f"{row.source_doctype} {row.source_name}")

    return unlinked


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
def validate_plan_for_confirm(plan_name):
    """Check every plan item and return a list of issues blocking confirmation.

    Rules:
    - Quotation (any status) → must be converted to SO then DN
    - Sales Order (Draft) → must be submitted
    - Sales Order (Submitted) in Domestic/Outbound → create DN first
    - Purchase Order (Draft) → must be submitted
    - Purchase Order (Submitted) in Inbound → OK
    - Delivery Note (Submitted) → OK
    - Free items → flagged as needs procurement
    """
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("read")

    issues = []
    for row in (doc.items or []):
        if not row.selected:
            continue

        if row.is_planned:
            issues.append({
                "type": "free_item",
                "item_code": row.item_code or "",
                "item_name": row.item_name or "",
                "qty": flt(row.planned_qty),
                "message": f"Free planning item — needs procurement before loading",
            })
            continue

        sd = row.source_doctype or ""
        if sd == "Quotation":
            issues.append({
                "type": "needs_conversion",
                "doctype": sd,
                "docname": row.source_name,
                "party": row.party or "",
                "message": "Quotation is not a shipping document. Convert to Sales Order, then create Delivery Note.",
            })
        elif sd == "Sales Order":
            try:
                so = frappe.get_doc("Sales Order", row.source_name)
            except frappe.DoesNotExistError:
                issues.append({"type": "missing", "doctype": sd, "docname": row.source_name, "message": f"Sales Order {row.source_name} not found"})
                continue

            if so.docstatus == 0:
                issues.append({
                    "type": "draft",
                    "doctype": sd,
                    "docname": row.source_name,
                    "party": so.customer_name or "",
                    "message": "Draft Sales Order — must be submitted before shipping.",
                })
            else:
                issues.append({
                    "type": "needs_dn",
                    "doctype": sd,
                    "docname": row.source_name,
                    "party": so.customer_name or "",
                    "message": "Sales Order submitted but no Delivery Note. Create DN from this SO.",
                })
        elif sd == "Purchase Order":
            try:
                po = frappe.get_doc("Purchase Order", row.source_name)
            except frappe.DoesNotExistError:
                issues.append({"type": "missing", "doctype": sd, "docname": row.source_name, "message": f"Purchase Order {row.source_name} not found"})
                continue

            if po.docstatus == 0:
                issues.append({
                    "type": "draft",
                    "doctype": sd,
                    "docname": row.source_name,
                    "party": po.supplier_name or "",
                    "message": "Draft Purchase Order — must be submitted.",
                })
        # Delivery Note (Submitted) and other OK types → no issue

    return {
        "has_issues": len(issues) > 0,
        "issues": issues,
        "issue_count": len(issues),
        "draft_count": sum(1 for i in issues if i["type"] == "draft"),
        "conversion_count": sum(1 for i in issues if i["type"] in ("needs_conversion", "needs_dn")),
        "free_item_count": sum(1 for i in issues if i["type"] == "free_item"),
    }


@frappe.whitelist()
def advance_status(plan_name, new_status, bypass_validation=False):
    """Advance a Forecast Load Plan through its lifecycle.

    Status flow: Planning → Ready → Loading → In Transit → Delivered
    Also supports: any → Cancelled
    """
    valid_statuses = {"Planning", "Ready", "Loading", "In Transit", "Delivered", "Cancelled"}
    if new_status not in valid_statuses:
        frappe.throw(f"Invalid status: {new_status}. Must be one of {', '.join(valid_statuses)}")

    forecast = frappe.get_doc("Forecast Load Plan", plan_name)
    forecast.check_permission("write")

    # Block changes after Delivered
    if forecast.status == "Delivered":
        frappe.throw("This plan is already delivered and cannot be modified.")

    # Allow Cancel from any status
    if new_status == "Cancelled":
        _unlink_source_docs(forecast)
        forecast.status = "Cancelled"
        forecast.save(ignore_permissions=True)
        return get_plan_detail(plan_name)

    # Allow unconfirm: Ready → Planning (only before Loading)
    if new_status == "Planning" and forecast.status == "Ready":
        _unlink_source_docs(forecast)
        forecast.status = "Planning"
        forecast.save(ignore_permissions=True)
        return get_plan_detail(plan_name)

    # Prevent going backwards (except Cancel and Unconfirm)
    status_order = ["Planning", "Ready", "Loading", "In Transit", "Delivered"]
    current_idx = status_order.index(forecast.status) if forecast.status in status_order else 0
    new_idx = status_order.index(new_status) if new_status in status_order else 0
    if new_idx < current_idx:
        frappe.throw(f"Cannot move from {forecast.status} to {new_status}. Status can only move forward. Unconfirm is only available from Ready → Planning.")

    # On Planning → Ready: validate documents, link sources, and lock the plan.
    if new_status == "Ready":
        _ensure_ready_transition(forecast)
        if not bypass_validation:
            validation = validate_plan_for_confirm(plan_name)
            if validation["has_issues"]:
                return {"validation": validation}
        _link_source_docs(forecast)
 

    forecast.status = new_status
    forecast.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


def _ensure_ready_transition(forecast):
    """Validate the minimum requirements before locking a plan for execution."""
    if not forecast.container_profile:
        frappe.throw("Container Profile is required before confirming.")

    selected_rows = [row for row in (forecast.items or []) if row.selected]
    if not selected_rows:
        frappe.throw("No items selected for this container.")


@frappe.whitelist()
def get_container_profiles():
    """Return active container profiles for sidebar selection."""
    profiles = frappe.get_all(
        "Container Profile",
        filters={"is_active": 1},
        fields=[
            "name",
            "container_name",
            "container_type",
            "max_weight_kg",
            "max_volume_m3",
            "length_cm",
            "width_cm",
            "height_cm",
        ],
        order_by="cost_rank asc, max_volume_m3 asc",
        limit_page_length=0,
    )
    for profile in profiles:
        length, width, height = _container_dimensions_cm(profile)
        profile.length_cm = length
        profile.width_cm = width
        profile.height_cm = height
    return profiles


@frappe.whitelist()
def add_free_item(plan_name, item_code, planned_qty, party_type="", party=""):
    """Add a free/planning item to a Forecast Load Plan.

    Free items are not linked to source documents — they're pure planning entries.
    """
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    item = frappe.get_cached_doc("Item", item_code)
    metrics = _compute_single_item_metrics(item_code, flt(planned_qty))
    _assert_complete_packaging_metrics(item_code, metrics)

    # Check capacity
    can_add, cur_vol, cur_wt, max_vol, max_wt, over_vol, over_wt = _check_capacity(
        doc, metrics["total_volume_m3"], metrics["total_weight_kg"]
    )
    if not can_add:
        frappe.throw(
            f"Cannot add {item_code}: would exceed weight capacity. "
            f"Current: {round3(cur_wt)} / {round3(max_wt)} kg, "
            f"Would add {round3(metrics['total_weight_kg'])} kg."
        )

    row = doc.append("items", {
        "is_planned": 1,
        "item_code": item_code,
        "item_name": item.item_name or item_code,
        "source_doctype": "",
        "source_name": "",
        "party_type": party_type or "",
        "party": party or "",
        "confidence": "tentative",
        "planned_qty": flt(planned_qty),
        "original_qty": 0,
        "stock_uom": metrics["stock_uom"],
        "purchase_uom": metrics["purchase_uom"],
        "uom_conversion_factor": metrics["uom_conversion_factor"],
        "packaging_profile": metrics.get("packaging_profile") or "",
        "packaging_source": metrics.get("packaging_source") or "item_fallback",
        "package_count": metrics.get("package_count") or 0,
        "length_cm": metrics.get("length_cm") or 0,
        "width_cm": metrics.get("width_cm") or 0,
        "height_cm": metrics.get("height_cm") or 0,
        "total_weight_kg": metrics["total_weight_kg"],
        "total_volume_m3": metrics["total_volume_m3"],
        "unit_weight_kg": metrics["unit_weight_kg"],
        "unit_volume_m3": metrics["unit_volume_m3"],
        "selected": 1,
        "sequence": len(doc.items),
    })

    doc.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


def _assert_complete_packaging_metrics(item_code: str, metrics: dict) -> None:
    if metrics.get("packaging_source") == "item_fallback":
        frappe.throw(f"No active default packaging profile found for {item_code}.")
    if flt(metrics.get("unit_weight_kg") or 0) <= 0 or flt(metrics.get("unit_volume_m3") or 0) <= 0:
        frappe.throw(f"Packaging profile for {item_code} must have weight and volume.")
    if not (
        flt(metrics.get("length_cm") or 0) > 0
        and flt(metrics.get("width_cm") or 0) > 0
        and flt(metrics.get("height_cm") or 0) > 0
    ):
        frappe.throw(f"Packaging profile for {item_code} must have length, width, and height for 3D loading.")


@frappe.whitelist()
def update_item_line_qty(plan_name, row_name, planned_qty):
    """Update planned_qty for a plan item row.

    Recalculates weight/volume based on new qty.
    For free items: qty × unit metrics = totals.
    For sourced items: this adjusts the entire document's contribution.
    """
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    new_qty = flt(planned_qty)
    if new_qty <= 0:
        frappe.throw("Planned qty must be greater than 0.")

    for row in doc.items or []:
        if row.name == row_name:
            if row.is_planned:
                metrics = _compute_single_item_metrics(row.item_code, new_qty)
                _assert_complete_packaging_metrics(row.item_code, metrics)
                row.planned_qty = new_qty
                row.total_weight_kg = metrics["total_weight_kg"]
                row.total_volume_m3 = metrics["total_volume_m3"]
                row.unit_weight_kg = metrics["unit_weight_kg"]
                row.unit_volume_m3 = metrics["unit_volume_m3"]
                row.packaging_profile = metrics.get("packaging_profile") or ""
                row.packaging_source = metrics.get("packaging_source") or "item_fallback"
                row.package_count = metrics.get("package_count") or 0
                row.length_cm = metrics.get("length_cm") or 0
                row.width_cm = metrics.get("width_cm") or 0
                row.height_cm = metrics.get("height_cm") or 0
            else:
                # Sourced doc — scale the entire doc's contribution
                # Store the original totals, then scale by ratio
                original_qty = flt(row.original_qty) or 1
                scale = new_qty / original_qty if original_qty > 0 else 1
                # Recompute from source to get fresh line items
                overrides = _load_packaging_overrides(row)
                totals = _compute_doc_totals(row.source_doctype, row.source_name, packaging_overrides=overrides)
                row.planned_qty = new_qty
                row.total_weight_kg = round3(flt(totals["total_weight_kg"]) * scale)
                row.total_volume_m3 = round3(flt(totals["total_volume_m3"]) * scale)
            break
    else:
        frappe.throw(f"Row {row_name} not found in plan.")

    doc.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


@frappe.whitelist()
def update_source_line_packaging_override(plan_name, row_name, source_row_name, packaging_profile=None):
    """Set or clear a planner-only packaging override for one sourced line item."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    if not frappe.get_meta("Forecast Plan Item").get_field("packaging_overrides_json"):
        frappe.throw("Planner packaging overrides are not installed yet. Reload after migration.")

    for row in doc.items or []:
        if row.name != row_name:
            continue
        if row.is_planned:
            frappe.throw("Packaging override is only available for sourced document rows.")

        overrides = _load_packaging_overrides(row)
        profile_name = (packaging_profile or "").strip()
        if profile_name:
            overrides[source_row_name] = profile_name
        else:
            overrides.pop(source_row_name, None)

        row.packaging_overrides_json = json.dumps(overrides, separators=(",", ":")) if overrides else ""
        totals = _compute_doc_totals(row.source_doctype, row.source_name, packaging_overrides=overrides)
        row.total_weight_kg = flt(totals["total_weight_kg"])
        row.total_volume_m3 = flt(totals["total_volume_m3"])
        row.item_count = cint(totals["item_count"])
        break
    else:
        frappe.throw(f"Row {row_name} not found in plan.")

    doc.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


@frappe.whitelist()
def save_packaging_layout(plan_name, layout_json=None):
    """Persist manual package positions for the 3D planner view."""
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    if not frappe.get_meta("Forecast Load Plan").get_field("packaging_layout_json"):
        frappe.throw("Planner layout storage is not installed yet. Reload after migration.")

    try:
        layout = json.loads(layout_json or "{}")
    except Exception:
        frappe.throw("Invalid planner layout payload.")

    if not isinstance(layout, dict):
        frappe.throw("Invalid planner layout payload.")

    clean = {}
    for key, value in layout.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        clean[key[:180]] = {
            "x": round3(value.get("x")),
            "y": round3(value.get("y")),
            "z": round3(value.get("z")),
            "pl": round3(value.get("pl")),
            "pw": round3(value.get("pw")),
            "ph": round3(value.get("ph")),
        }

    doc.packaging_layout_json = json.dumps(clean, separators=(",", ":")) if clean else ""
    doc.save(ignore_permissions=True)
    return {"saved": True, "count": len(clean)}


@frappe.whitelist()
def remove_item_line(plan_name, row_name):
    """Remove a single item row from a Forecast Load Plan.

    Works for both sourced documents and free/planning items.
    """
    doc = frappe.get_doc("Forecast Load Plan", plan_name)
    doc.check_permission("write")

    doc.items = [row for row in (doc.items or []) if row.name != row_name]

    # Re-sequence
    for i, row in enumerate(doc.items or []):
        row.sequence = i

    doc.save(ignore_permissions=True)
    return get_plan_detail(plan_name)


def _active_planner_company(company=None):
    clean = (company or "").strip()
    if clean:
        return clean
    try:
        from orderlift.menu_access import resolve_current_company

        return (resolve_current_company(user=frappe.session.user) or "").strip()
    except Exception:
        return ""


def _company_item_codes(company: str) -> set[str]:
    company = (company or "").strip()
    if not company:
        return set()
    disabled_condition = _warehouse_disabled_condition("w")
    params = {"company": company}
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT b.item_code
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE w.company = %(company)s
          {disabled_condition}
          AND b.item_code IS NOT NULL
          {stock_warehouse_condition("b.warehouse", params)}
        """,
        params,
        as_dict=True,
    )
    return {row.item_code for row in rows if row.item_code}


def _warehouse_disabled_condition(alias="w"):
    try:
        if not frappe.db.has_column("Warehouse", "disabled"):
            return ""
    except Exception:
        return ""
    return f"AND ifnull({alias}.disabled, 0) = 0"


@frappe.whitelist()
def get_item_search(search_term, item_group=None, limit=50, company=None, selling_price_list=None, buying_price_list=None):
    """Search Item Master for the item picker.

    Returns items matching search_term (code or name) with weight/volume/UOM data.
    """
    import json
    if isinstance(search_term, str):
        search_term = json.loads(search_term) if search_term.startswith('"') else search_term

    company = _active_planner_company(company)
    item_codes = _company_item_codes(company)
    selling_codes = _price_list_item_codes(selling_price_list, "selling", company=company) if selling_price_list else set()
    buying_codes = _price_list_item_codes(buying_price_list, "buying", company=company) if buying_price_list else set()
    if selling_codes:
        item_codes &= selling_codes
    if buying_codes:
        item_codes &= buying_codes
    if not company or not item_codes:
        return []

    filters = {"disabled": 0, "name": ["in", sorted(item_codes)]}
    if item_group and item_group != "All":
        filters["item_group"] = item_group

    # Search by code or name
    or_filters = [
        ["name", "like", f"%{search_term}%"],
        ["item_name", "like", f"%{search_term}%"],
    ]

    items = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name", "item_name", "item_group", "stock_uom", "purchase_uom",
            "min_order_qty", "custom_weight_kg", "custom_volume_m3",
            "custom_length_cm", "custom_width_cm", "custom_height_cm",
        ],
        order_by="name asc",
        limit_page_length=limit,
    )

    results = []
    for item in items:
        unit_w, unit_v = _get_item_metrics(item.name)
        metrics = _get_packaging_metrics(item_code=item.name, qty=1)
        uom_data = _get_item_uom_data(item.name)
        results.append({
            "item_code": item.name,
            "item_name": item.item_name or item.name,
            "item_group": item.item_group,
            "stock_uom": uom_data["stock_uom"],
            "purchase_uom": uom_data["purchase_uom"],
            "min_order_qty": uom_data["min_order_qty"],
            "uom_conversion_factor": uom_data["uom_conversion_factor"],
            "unit_weight_kg": round3(unit_w),
            "unit_volume_m3": round3(unit_v),
            "package_count": flt(metrics.get("package_count") or 0),
            "packaging_profile": metrics.get("resolved_profile_name") or "",
            "packaging_source": metrics.get("packaging_source") or "item_fallback",
            "packaging_type": metrics.get("packaging_type") or "",
            "length_cm": round3(metrics.get("length_cm")),
            "width_cm": round3(metrics.get("width_cm")),
            "height_cm": round3(metrics.get("height_cm")),
            "has_weight": unit_w > 0,
            "has_volume": unit_v > 0,
            "has_dimensions": flt(metrics.get("length_cm") or 0) > 0 and flt(metrics.get("width_cm") or 0) > 0 and flt(metrics.get("height_cm") or 0) > 0,
        })

    return results


@frappe.whitelist()
def get_reorder_suggestions(company=None, limit=20):
    """Return company items below safety stock/reorder level — candidates for adding to a plan."""
    company = _active_planner_company(company)
    if not company:
        return []
    disabled_condition = _warehouse_disabled_condition("w")
    if _has_column("Item", "safety_stock"):
        params = {"company": company, "limit": limit}
        items = frappe.db.sql(f"""
            SELECT
                b.item_code,
                i.item_name,
                i.item_group,
                i.stock_uom,
                i.purchase_uom,
                i.min_order_qty,
                sum(b.actual_qty) as actual_qty,
                max(i.safety_stock) as reorder_level,
                max(ifnull(ir.warehouse_reorder_qty, 0)) as reorder_qty,
                i.custom_weight_kg,
                i.custom_volume_m3,
                'Safety Stock' as threshold_type
            FROM `tabBin` b
            JOIN `tabWarehouse` w ON w.name = b.warehouse
            JOIN `tabItem` i ON i.name = b.item_code
            LEFT JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
            WHERE w.company = %(company)s
                {disabled_condition}
                AND i.disabled = 0
                {stock_warehouse_condition("b.warehouse", params)}
            GROUP BY b.item_code, i.item_name, i.item_group, i.stock_uom, i.purchase_uom, i.min_order_qty,
                i.custom_weight_kg, i.custom_volume_m3
            HAVING reorder_level > 0 AND actual_qty <= reorder_level
            ORDER BY (reorder_level - actual_qty) DESC
            LIMIT %(limit)s
        """, params, as_dict=True)
    else:
        params = {"company": company, "limit": limit}
        items = frappe.db.sql(f"""
            SELECT
                b.item_code,
                i.item_name,
                i.item_group,
                i.stock_uom,
                i.purchase_uom,
                i.min_order_qty,
                b.actual_qty,
                ir.warehouse_reorder_level as reorder_level,
                ir.warehouse_reorder_qty as reorder_qty,
                i.custom_weight_kg,
                i.custom_volume_m3,
                'Warehouse Reorder' as threshold_type
            FROM `tabBin` b
            JOIN `tabWarehouse` w ON w.name = b.warehouse
            JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
            JOIN `tabItem` i ON i.name = b.item_code
            WHERE b.actual_qty <= ir.warehouse_reorder_level
                AND w.company = %(company)s
                {disabled_condition}
                AND i.disabled = 0
                {stock_warehouse_condition("b.warehouse", params)}
            ORDER BY (ir.warehouse_reorder_level - b.actual_qty) DESC
            LIMIT %(limit)s
        """, params, as_dict=True)

    results = []
    for item in items:
        unit_w, unit_v = _get_item_metrics(item.item_code)
        metrics = _get_packaging_metrics(item_code=item.item_code, qty=flt(item.reorder_qty) or 1)
        uom_data = _get_item_uom_data(item.item_code)
        results.append({
            "item_code": item.item_code,
            "item_name": item.item_name or item.item_code,
            "item_group": item.item_group,
            "stock_uom": uom_data["stock_uom"],
            "purchase_uom": uom_data["purchase_uom"],
            "min_order_qty": uom_data["min_order_qty"],
            "uom_conversion_factor": uom_data["uom_conversion_factor"],
            "unit_weight_kg": round3(unit_w),
            "unit_volume_m3": round3(unit_v),
            "package_count": flt(metrics.get("package_count") or 0),
            "packaging_profile": metrics.get("resolved_profile_name") or "",
            "packaging_source": metrics.get("packaging_source") or "item_fallback",
            "packaging_type": metrics.get("packaging_type") or "",
            "length_cm": round3(metrics.get("length_cm")),
            "width_cm": round3(metrics.get("width_cm")),
            "height_cm": round3(metrics.get("height_cm")),
            "actual_qty": flt(item.actual_qty),
            "reorder_level": flt(item.reorder_level),
            "reorder_qty": flt(item.reorder_qty),
            "threshold_type": item.get("threshold_type") or "Safety Stock",
            "suggested_qty": flt(item.reorder_qty) or (flt(item.reorder_level) - flt(item.actual_qty)),
        })

    return results
