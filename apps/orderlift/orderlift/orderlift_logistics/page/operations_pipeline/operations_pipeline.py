from __future__ import annotations

import frappe
from frappe.utils import cint, flt, getdate, today


TERMINAL_STATUSES = {
    "Cancelled",
    "Closed",
    "Completed",
    "Converted",
    "Delivered",
    "Fully Completed",
    "Lost",
    "Resolved",
    "Return Issued",
}

# ── Kanban columns ──────────────────────────────────────────────────────────

COLUMNS = [
    {"key": "new_triage", "label": "New / Triage", "order": 1},
    {"key": "in_progress", "label": "In Progress", "order": 2},
    {"key": "fulfilling", "label": "Fulfilling", "order": 3},
    {"key": "delivered", "label": "Delivered", "order": 4},
    {"key": "needs_attention", "label": "Needs Attention", "order": 5},
    {"key": "closed", "label": "Closed", "order": 6},
]


# ── Link Registry ───────────────────────────────────────────────────────────
# Each entry: (from_doctype, from_field, to_doctype, relation_type)
# relation_type: "fulfillment" (main spine), "sub-branch" (parallel flow), "related"
# from_field can be a child-table field via "child_table.fieldname" syntax.

LINK_REGISTRY = [
    # ── CRM → Selling ──────────────────────────────────────────────────
    ("Quotation", "party_name", "Lead", "upstream"),
    ("Quotation", "party_name", "Opportunity", "upstream"),
    ("Quotation", "opportunity", "Opportunity", "upstream"),
    ("Sales Order Item", "prevdoc_docname", "Quotation", "upstream"),
    ("Sales Order", "items.prevdoc_docname", "Quotation", "upstream"),

    # ── Customer (linked via customer_name on selling docs) ────────────
    ("Sales Order", "customer_name", "Customer", "downstream"),
    ("Quotation", "party_name", "Customer", "downstream"),
    ("Delivery Note", "customer_name", "Customer", "downstream"),
    ("Sales Invoice", "customer_name", "Customer", "downstream"),
    ("SAV Ticket", "customer", "Customer", "downstream"),
    ("Lead", "company_name", "Customer", "related"),
    ("Opportunity", "party_name", "Customer", "related"),
    ("Purchase Order", "supplier", "Supplier", "downstream"),
    ("Purchase Invoice", "supplier", "Supplier", "downstream"),
    ("Purchase Receipt", "supplier", "Supplier", "downstream"),

    # ── Fulfillment ────────────────────────────────────────────────────
    ("Delivery Note Item", "against_sales_order", "Sales Order", "upstream"),
    ("Delivery Note Item", "against_sales_invoice", "Sales Invoice", "upstream"),
    ("Delivery Stop", "delivery_note", "Delivery Note", "upstream"),

    # ── Project ────────────────────────────────────────────────────────
    ("Sales Order", "project", "Project", "downstream"),
    ("Sales Order", "custom_installation_project", "Project", "downstream"),

    # ── Accounting ─────────────────────────────────────────────────────
    ("Sales Invoice", "sales_order", "Sales Order", "upstream"),
    ("Sales Invoice", "delivery_note", "Delivery Note", "upstream"),
    ("Sales Invoice", "items.sales_order", "Sales Order", "upstream"),
    ("Sales Invoice", "items.delivery_note", "Delivery Note", "upstream"),
    ("Payment Entry", "references.reference_name", "Sales Invoice", "upstream"),
    ("Payment Entry", "references.reference_name", "Sales Order", "upstream"),
    ("Purchase Invoice", "purchase_order", "Purchase Order", "upstream"),
    ("Purchase Invoice", "purchase_receipt", "Purchase Receipt", "upstream"),

    # ── Buying ─────────────────────────────────────────────────────────
    ("Purchase Receipt", "items.purchase_order", "Purchase Order", "upstream"),
    ("Pick List", "locations.sales_order", "Sales Order", "upstream"),

    # ── After-sales ────────────────────────────────────────────────────
    ("SAV Ticket", "sales_order", "Sales Order", "upstream"),
    ("SAV Ticket", "delivery_note", "Delivery Note", "upstream"),
    ("SAV Ticket", "sales_invoice", "Sales Invoice", "upstream"),
    ("SAV Ticket", "installation_project", "Project", "upstream"),
    ("SAV Ticket", "serial_no", "Serial No", "upstream"),
    ("SAV Ticket", "quality_inspection", "Quality Inspection", "downstream"),

    # ── Quality (dynamic reference_type + reference_name pattern) ──────
    ("Quality Inspection", "DYN_REF", "Delivery Note", "upstream"),
    ("Quality Inspection", "DYN_REF", "Purchase Receipt", "upstream"),
    ("Quality Inspection", "DYN_REF", "Sales Invoice", "upstream"),

    # ── HR / Costing ───────────────────────────────────────────────────
    ("Timesheet", "project", "Project", "upstream"),
    ("Timesheet", "sales_invoice", "Sales Invoice", "upstream"),

    # ── Manufacturing ──────────────────────────────────────────────────
    ("Work Order", "sales_order", "Sales Order", "upstream"),
    ("Work Order", "project", "Project", "upstream"),
    ("Material Request", "items.sales_order", "Sales Order", "upstream"),
    ("Purchase Order", "items.sales_order", "Sales Order", "upstream"),
    ("Purchase Order", "items.material_request", "Material Request", "upstream"),

    # ── Native Support ─────────────────────────────────────────────────
    ("Issue", "sales_order", "Sales Order", "upstream"),
    ("Issue", "project", "Project", "upstream"),
    ("Issue", "serial_no", "Serial No", "upstream"),
    ("Maintenance Schedule", "sales_order", "Sales Order", "upstream"),
    ("Maintenance Visit", "sales_order", "Sales Order", "upstream"),
    ("Maintenance Visit", "purposes.delivery_note", "Delivery Note", "upstream"),

    # ── Communication (dynamic reference) ──────────────────────────────
    ("Communication", "DYN_REF_ANY", "_ANY", "related"),
]

# Doctypes we query for trace nodes
TRACE_DOCTYPES = [
    "Lead", "Opportunity", "Quotation", "Sales Order", "Purchase Order",
    "Delivery Note", "Delivery Trip", "Sales Invoice", "Purchase Invoice",
    "Purchase Receipt", "Payment Entry", "Project", "SAV Ticket",
    "Quality Inspection", "Timesheet", "Work Order", "Material Request",
    "Pick List", "Issue", "Maintenance Schedule", "Maintenance Visit",
    "Serial No", "Stock Entry", "Communication", "Customer", "Supplier",
]

# Map doctype → short code for UI
DOCTYPE_CODE = {
    "Lead": "LEAD",
    "Opportunity": "OPP",
    "Quotation": "QTN",
    "Sales Order": "SO",
    "Purchase Order": "PO",
    "Delivery Note": "DN",
    "Delivery Trip": "DT",
    "Sales Invoice": "SALES_INVOICE",
    "Purchase Invoice": "PURCHASE_INVOICE",
    "Purchase Receipt": "PR",
    "Payment Entry": "PAYMENT",
    "Project": "PRJ",
    "SAV Ticket": "SAV",
    "Quality Inspection": "QC",
    "Timesheet": "TIMESHEET",
    "Work Order": "WORK_ORDER",
    "Material Request": "MAT_REQ",
    "Pick List": "PICK_LIST",
    "Issue": "ISSUE",
    "Maintenance Schedule": "MAINT_SCHEDULE",
    "Maintenance Visit": "MAINT_VISIT",
    "Serial No": "SERIAL_NO",
    "Stock Entry": "STOCK_ENTRY",
    "Communication": "COMMUNICATION",
    "Supplier": "SUPPLIER",
}


# ── Public API ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_pipeline_data(
    company=None,
    flow_scope=None,
    shipping_responsibility=None,
    date_filter=None,
):
    """Return the 6-column Kanban pipeline with deal cards and health metadata."""
    cards = []
    cards.extend(_get_leads(company, date_filter))
    cards.extend(_get_opportunities(company, date_filter))
    cards.extend(_get_quotations(company, date_filter))
    cards.extend(_get_sales_orders(company, flow_scope, shipping_responsibility, date_filter))
    cards.extend(_get_material_requests(company, date_filter))
    cards.extend(_get_purchase_orders(company, flow_scope, date_filter))
    cards.extend(_get_pick_lists(company, date_filter))
    cards.extend(_get_delivery_notes(company, date_filter))
    cards.extend(_get_delivery_trips(company, date_filter))
    cards.extend(_get_sales_invoices(company, date_filter))
    cards.extend(_get_purchase_invoices(company, date_filter))
    cards.extend(_get_payment_entries(company, date_filter))
    cards.extend(_get_projects(company, date_filter))
    cards.extend(_get_sav_tickets(company, date_filter))
    cards.extend(_get_issues(company, date_filter))
    cards.extend(_get_maintenance_schedules(company, date_filter))
    cards.extend(_get_maintenance_visits(company, date_filter))

    # Compute column for each card
    for card in cards:
        card["column"] = _resolve_column(card)

    counts = {}
    for col in COLUMNS:
        counts[col["key"]] = sum(1 for c in cards if c["column"] == col["key"])

    return {
        "columns": COLUMNS,
        "cards": cards,
        "counts": counts,
        "totals": {
            "total_cards": len(cards),
            "total_value": sum(flt(c["value"]) for c in cards),
        },
    }


@frappe.whitelist()
def get_trace_data(entity_type, entity_name):
    """
    Walk the document graph from a starting node.
    Returns: { focused_node, nodes[], edges[], health_summary, communications[] }
    """
    visited = set()
    nodes = []
    edges = []
    queue = [(entity_type, entity_name, None)]  # (doctype, name, parent_info)

    while queue:
        doctype, name, parent = queue.pop(0)
        key = f"{doctype}::{name}"
        if key in visited or not doctype or not name:
            continue
        visited.add(key)

        # Fetch the document
        doc = _fetch_doc(doctype, name)
        if not doc:
            continue

        node = _build_node(doctype, doc)
        nodes.append(node)

        # Customer/Supplier are context leaves in the trace UI.
        if doctype in {"Customer", "Supplier"}:
            continue

        # Find upstream links (what points TO this doc)
        for link in LINK_REGISTRY:
            from_dt, from_field, to_dt, relation = link

            # DYN_REF_ANY: catch-all for Communications and similar
            if from_field == "DYN_REF_ANY":
                comms = frappe.get_all(
                    from_dt,
                    filters={"reference_doctype": doctype, "reference_name": name},
                    fields=["name"],
                    limit=10,
                )
                for c in comms:
                    comm_key = f"{from_dt}::{c.name}"
                    if comm_key not in visited:
                        edges.append({"from": name, "to": c.name, "relation": "related"})
                        queue.append((from_dt, c.name, key))
                continue

            if to_dt != doctype:
                continue

            refs = _find_upstream_refs(from_dt, from_field, name, target_doctype=doctype)
            source_dt = _get_upstream_source_doctype(from_dt, from_field)
            for ref_name in refs:
                if not _doc_exists(source_dt, ref_name):
                    continue
                ref_key = f"{source_dt}::{ref_name}"
                if ref_key not in visited:
                    edge_relation = "fulfillment" if relation == "upstream" else relation
                    # Fulfillment edges run earlier document -> later document.
                    if relation == "upstream":
                        edges.append({"from": name, "to": ref_name, "relation": edge_relation})
                    else:
                        edges.append({"from": name, "to": ref_name, "relation": edge_relation})
                    queue.append((source_dt, ref_name, key))

        # Find downstream links (what this doc points TO)
        for link in LINK_REGISTRY:
            from_dt, from_field, to_dt, relation = link
            if from_dt != doctype:
                continue
            if to_dt == "_ANY":
                # Dynamic reference — handled separately
                continue

            refs = _find_downstream_refs(doc, from_field, to_dt)
            for ref_name in refs:
                if not _doc_exists(to_dt, ref_name):
                    continue
                ref_key = f"{to_dt}::{ref_name}"
                if ref_key not in visited:
                    if relation == "upstream":
                        edge_relation = "fulfillment"
                        edges.append({"from": ref_name, "to": name, "relation": edge_relation})
                    else:
                        edge_relation = "sub-branch" if relation == "downstream" else relation
                        edges.append({"from": name, "to": ref_name, "relation": edge_relation})
                    queue.append((to_dt, ref_name, key))


    # Find the focused node
    focused = next((n for n in nodes if n["id"] == entity_name and n["doctype"] == entity_type), None)

    # Compute health summary
    health = _compute_health(nodes)

    deduped_edges = []
    seen_edges = set()
    for edge in edges:
        key = (edge.get("from"), edge.get("to"), edge.get("relation"))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        deduped_edges.append(edge)

    return {
        "focused": focused,
        "nodes": nodes,
        "edges": deduped_edges,
        "health": health,
        "root_node_id": entity_name,
    }


@frappe.whitelist()
def get_document_preview(doctype, name):
    """Return generic preview data for a trace document popup."""
    doc = _fetch_doc(doctype, name)
    if not doc:
        frappe.throw(frappe._("{0} {1} not found").format(doctype, name))

    meta = frappe.get_meta(doctype)
    fields = []
    for fieldname in _get_preview_field_candidates(doctype):
        df = meta.get_field(fieldname)
        if not df:
            continue
        value = getattr(doc, fieldname, None)
        if value in (None, "", []):
            continue
        fields.append(
            {
                "fieldname": fieldname,
                "label": df.label or fieldname.replace("_", " ").title(),
                "value": _format_preview_value(value),
            }
        )

    return {
        "doctype": doctype,
        "name": name,
        "title": _get_doc_title(doctype, doc),
        "status": _get_doc_status_label(doctype, doc),
        "date": _get_doc_date(doctype, doc),
        "value": _get_doc_value(doctype, doc),
        "fields": fields,
    }


# ── Column resolution ──────────────────────────────────────────────────────

def _resolve_column(card):
    """Determine which Kanban column a card belongs to."""
    # Check "Needs Attention" first (cross-cutting alert)
    if _needs_attention(card):
        return "needs_attention"

    doctype = card.get("doctype", "")
    status = card.get("status", "")

    # Closed states
    if status in TERMINAL_STATUSES:
        if doctype == "SAV Ticket" and status in ("Closed", "Resolved"):
            return "closed"
        if doctype == "Delivery Trip" and status == "Completed":
            return "delivered"
        if doctype == "Project" and status == "Completed":
            return "closed"
        if doctype == "Delivery Note" and status in ("Completed", "Delivered", "Return Issued"):
            return "delivered"

        return "closed"

    # Delivered
    if doctype == "Delivery Note" and status in ("Submitted", "To Bill"):
        return "delivered"
    if doctype == "Delivery Trip" and status == "In Transit":
        return "fulfilling"

    # Fulfilling
    if doctype in ("Sales Order", "Purchase Order", "Delivery Note"):
        if status in ("To Deliver and Bill", "To Bill", "Submitted", "Overdue", "To Receive and Bill", "To Receive"):
            return "fulfilling"
    if doctype == "Project" and status in ("Open", "Running"):
        return "fulfilling"
    if doctype == "SAV Ticket" and status in ("Open", "Assigned", "In Progress", "Work In Progress", "On Hold"):
        return "fulfilling"

    # New / Triage
    if doctype == "Lead":
        return "new_triage"
    if doctype == "Opportunity" and status == "Open":
        return "new_triage"

    # In Progress
    if doctype in ("Quotation", "Opportunity"):
        return "in_progress"
    if doctype == "Sales Order" and status == "To Bill":
        return "in_progress"

    return "in_progress"


def _needs_attention(card):
    """Check if a card should be flagged in the Needs Attention column."""
    status = card.get("status", "")
    if status in TERMINAL_STATUSES:
        return False

    # Overdue date
    if card.get("overdue"):
        return True

    # Open SAV tickets linked
    if card.get("open_sav_count", 0) > 0:
        return True

    # Failed QC
    if card.get("qc_failed", False):
        return True

    # Blocked SAV
    if card.get("doctype") == "SAV Ticket" and status in ("On Hold", "Blocked"):
        return True

    return False


# ── Per-Doctype queries ────────────────────────────────────────────────────

def _get_leads(company, date_filter):
    filters = {"status": ["!=", "Converted"]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Lead", filters=filters,
        fields=_query_fields(
            "Lead",
            ["name", "company_name as customer", "status", "creation as doc_date", "annual_revenue as value"],
            ["company", "owner"],
        ),
        order_by="creation desc", limit_page_length=100,
    )
    return _cards(docs, "Lead", date_filter)


def _get_opportunities(company, date_filter):
    filters = {"status": ["!=", "Lost"]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Opportunity", filters=filters,
        fields=_query_fields(
            "Opportunity",
            [
                "name",
                "party_name as customer",
                "status",
                "transaction_date as doc_date",
                "opportunity_amount as value",
                "expected_closing as deadline",
            ],
            ["company", "owner"],
        ),
        order_by="transaction_date desc", limit_page_length=100,
    )
    return _cards(docs, "Opportunity", date_filter)


def _get_quotations(company, date_filter):
    filters = {"status": ["not in", ["Lost", "Cancelled"]]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Quotation", filters=filters,
        fields=_query_fields(
            "Quotation",
            [
                "name",
                "party_name as customer",
                "status",
                "transaction_date as doc_date",
                "grand_total as value",
                "valid_till as deadline",
            ],
            ["company", "owner"],
        ),
        order_by="transaction_date desc", limit_page_length=100,
    )
    return _cards(docs, "Quotation", date_filter)


def _get_sales_orders(company, flow_scope, shipping_resp, date_filter):
    from orderlift.orderlift_logistics.services.forecast_planning import DOCTYPE_CONFIG

    filters = dict(DOCTYPE_CONFIG["Sales Order"]["extra_filters"])
    if company:
        filters["company"] = company
    if flow_scope:
        filters["custom_flow_scope"] = flow_scope
    if shipping_resp:
        filters["custom_shipping_responsibility"] = shipping_resp

    docs = frappe.get_all(
        "Sales Order", filters=filters,
        fields=_query_fields(
            "Sales Order",
            [
                "name", "customer_name as customer", "status",
                "transaction_date as doc_date", "grand_total as value",
                "delivery_date as deadline",
                "custom_flow_scope as flow_scope",
                "custom_shipping_responsibility as shipping_resp",
                "project",
            ],
            ["company", "owner"],
        ),
        order_by="transaction_date desc", limit_page_length=200,
    )

    docs = [so for so in docs if not _skip_date_filter(so.get("doc_date"), date_filter)]
    if not docs:
        return []

    sales_order_names = [so.name for so in docs]
    items_count_map = _get_grouped_counts("Sales Order Item", "parent", {"parent": ["in", sales_order_names]})
    open_sav_map = _get_grouped_counts(
        "SAV Ticket",
        "sales_order",
        {"sales_order": ["in", sales_order_names], "status": ["!=", "Closed"]},
    )
    delivery_notes_by_sales_order = _get_delivery_notes_by_sales_orders(sales_order_names)
    rejected_delivery_notes = _get_rejected_delivery_notes(delivery_notes_by_sales_order)

    cards = []
    for so in docs:
        delivery_notes = delivery_notes_by_sales_order.get(so.name, set())
        cards.append(
            _make_card(
                so,
                "Sales Order",
                items_count=items_count_map.get(so.name, 0),
                open_sav=open_sav_map.get(so.name, 0),
                qc_failed=any(delivery_note in rejected_delivery_notes for delivery_note in delivery_notes),
            )
        )
    return cards


def _get_purchase_orders(company, flow_scope, date_filter):
    filters = {"status": ["not in", ["Completed", "Cancelled", "Closed"]]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Purchase Order", filters=filters,
        fields=_query_fields(
            "Purchase Order",
            [
                "name",
                "supplier_name as customer",
                "status",
                "transaction_date as doc_date",
                "grand_total as value",
                "schedule_date as deadline",
            ],
            ["company", "owner", "project"],
        ),
        order_by="transaction_date desc", limit_page_length=100,
    )
    return _cards(docs, "Purchase Order", date_filter)


def _get_material_requests(company, date_filter):
    if not _doctype_exists("Material Request"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company and _doctype_has_field("Material Request", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "Material Request", filters=filters,
        fields=_query_fields(
            "Material Request",
            ["name", "status", "transaction_date as doc_date"],
            ["company", "owner", "project"],
        ),
        order_by="transaction_date desc", limit_page_length=100,
    )
    return _cards(docs, "Material Request", date_filter)


def _get_pick_lists(company, date_filter):
    if not _doctype_exists("Pick List"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company and _doctype_has_field("Pick List", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "Pick List", filters=filters,
        fields=_query_fields(
            "Pick List",
            ["name", "status", "creation as doc_date"],
            ["company", "owner", "project"],
        ),
        order_by="creation desc", limit_page_length=100,
    )
    return _cards(docs, "Pick List", date_filter)


def _get_delivery_notes(company, date_filter):
    filters = {"status": ["not in", ["Cancelled", "Return Issued"]]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Delivery Note", filters=filters,
        fields=_query_fields(
            "Delivery Note",
            ["name", "customer_name as customer", "status", "posting_date as doc_date", "grand_total as value"],
            ["company", "owner", "project"],
        ),
        order_by="posting_date desc", limit_page_length=100,
    )
    return _cards(docs, "Delivery Note", date_filter)


def _get_delivery_trips(company, date_filter):
    filters = {"docstatus": 1}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Delivery Trip", filters=filters,
        fields=_query_fields(
            "Delivery Trip",
            ["name", "status", "departure_time as doc_date", "departure_time as deadline"],
            ["company", "owner"],
        ),
        order_by="departure_time desc", limit_page_length=100,
    )

    docs = [dt for dt in docs if not _skip_date_filter(dt.get("doc_date"), date_filter)]
    if not docs:
        return []

    trip_customers = _get_delivery_trip_customers([dt.name for dt in docs])

    cards = []
    for dt in docs:
        customer = trip_customers.get(dt.name, "")
        cards.append({
            "name": dt.name,
            "doctype": "Delivery Trip",
            "customer": customer,
            "value": 0,
            "date": str(dt.get("doc_date") or ""),
            "deadline": dt.get("deadline"),
            "flow_scope": "",
            "shipping_resp": "",
            "company": dt.get("company") or "",
            "project": dt.get("project") or "",
            "owner": dt.get("owner") or "",
            "status": dt.status,
            "items_count": 0,
            "overdue": _is_overdue(dt.get("deadline")),
            "open_sav_count": 0,
            "qc_failed": False,
            "column": None,
        })
    return cards


def _get_sales_invoices(company, date_filter):
    if not _doctype_exists("Sales Invoice"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Sales Invoice", filters=filters,
        fields=_query_fields(
            "Sales Invoice",
            [
                "name", "customer_name as customer", "status",
                "posting_date as doc_date", "grand_total as value", "due_date as deadline",
            ],
            ["company", "owner", "project"],
        ),
        order_by="posting_date desc", limit_page_length=100,
    )
    return _cards(docs, "Sales Invoice", date_filter)


def _get_purchase_invoices(company, date_filter):
    if not _doctype_exists("Purchase Invoice"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Purchase Invoice", filters=filters,
        fields=_query_fields(
            "Purchase Invoice",
            [
                "name", "supplier_name as customer", "status",
                "posting_date as doc_date", "grand_total as value", "due_date as deadline",
            ],
            ["company", "owner", "project"],
        ),
        order_by="posting_date desc", limit_page_length=100,
    )
    return _cards(docs, "Purchase Invoice", date_filter)


def _get_payment_entries(company, date_filter):
    if not _doctype_exists("Payment Entry"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company and _doctype_has_field("Payment Entry", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "Payment Entry", filters=filters,
        fields=_query_fields(
            "Payment Entry",
            [
                "name", "party as customer", "payment_type", "docstatus",
                "posting_date as doc_date", "paid_amount as value",
            ],
            ["company", "owner", "project"],
        ),
        order_by="posting_date desc", limit_page_length=100,
    )

    cards = []
    for doc in docs:
        status = "Completed" if int(doc.get("docstatus") or 0) == 1 else "Draft"
        if _skip_date_filter(doc.get("doc_date"), date_filter):
            continue
        cards.append({
            "name": doc.name,
            "doctype": "Payment Entry",
            "customer": doc.get("customer") or "",
            "value": flt(doc.get("value")),
            "date": str(doc.get("doc_date") or ""),
            "deadline": doc.get("deadline"),
            "flow_scope": "",
            "shipping_resp": "",
            "company": doc.get("company") or "",
            "project": doc.get("project") or "",
            "owner": doc.get("owner") or "",
            "status": status,
            "items_count": 0,
            "overdue": False,
            "open_sav_count": 0,
            "qc_failed": False,
            "column": None,
        })
    return [card for card in cards if card]


def _get_projects(company, date_filter):
    filters = {"status": ["not in", ["Completed", "Cancelled"]]}
    if company:
        filters["company"] = company

    docs = frappe.get_all(
        "Project", filters=filters,
        fields=_query_fields(
            "Project",
            [
                "name",
                "customer",
                "status",
                "expected_start_date as doc_date",
                "expected_end_date as deadline",
                "gross_margin as value",
            ],
            ["company", "owner"],
        ),
        order_by="expected_start_date desc", limit_page_length=100,
    )
    return _cards(docs, "Project", date_filter)


def _get_sav_tickets(company, date_filter):
    filters = {"status": ["!=", "Closed"]}
    if company and _doctype_has_field("SAV Ticket", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "SAV Ticket", filters=filters,
        fields=_query_fields(
            "SAV Ticket",
            [
                "name", "customer", "status", "creation as doc_date",
                "defect_type", "serial_no", "sales_order", "delivery_note", "sla_breach",
            ],
            ["company", "owner", ("installation_project", "project")],
        ),
        order_by="creation desc", limit_page_length=100,
    )
    cards = []
    for s in docs:
        if _skip_date_filter(s.get("doc_date"), date_filter):
            continue
        cards.append({
            "name": s.name,
            "doctype": "SAV Ticket",
            "customer": s.customer or "",
            "value": 0,
            "date": str(s.get("doc_date") or ""),
            "flow_scope": "",
            "shipping_resp": "",
            "company": s.get("company") or "",
            "project": s.get("project") or "",
            "owner": s.get("owner") or "",
            "status": s.status,
            "items_count": 0,
            "overdue": bool(s.get("sla_breach")),
            "open_sav_count": 0,
            "qc_failed": False,
            "column": None,
        })
    return cards


def _get_issues(company, date_filter):
    if not _doctype_exists("Issue"):
        return []

    filters = {"status": ["!=" , "Closed"]}
    if company and _doctype_has_field("Issue", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "Issue", filters=filters,
        fields=_query_fields(
            "Issue",
            ["name", "subject as customer", "status", "creation as doc_date"],
            ["company", "owner", "project"],
        ),
        order_by="creation desc", limit_page_length=100,
    )
    return _cards(docs, "Issue", date_filter)


def _get_maintenance_schedules(company, date_filter):
    if not _doctype_exists("Maintenance Schedule"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company and _doctype_has_field("Maintenance Schedule", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "Maintenance Schedule", filters=filters,
        fields=_query_fields(
            "Maintenance Schedule",
            ["name", "status", "transaction_date as doc_date"],
            ["company", "owner", "project"],
        ),
        order_by="transaction_date desc", limit_page_length=100,
    )
    return _cards(docs, "Maintenance Schedule", date_filter)


def _get_maintenance_visits(company, date_filter):
    if not _doctype_exists("Maintenance Visit"):
        return []

    filters = {"docstatus": ["<", 2]}
    if company and _doctype_has_field("Maintenance Visit", "company"):
        filters["company"] = company

    docs = frappe.get_all(
        "Maintenance Visit", filters=filters,
        fields=_query_fields(
            "Maintenance Visit",
            ["name", "status", "mntc_date as doc_date"],
            ["company", "owner", "project"],
        ),
        order_by="mntc_date desc", limit_page_length=100,
    )
    return _cards(docs, "Maintenance Visit", date_filter)


# ── Card builders ──────────────────────────────────────────────────────────

def _card(doc, doctype, date_filter, value=None):
    """Build a card from a doc dict with generic field names."""
    if _skip_date_filter(doc.get("doc_date"), date_filter):
        return None
    val = value if value is not None else flt(doc.get("value"))
    return {
        "name": doc.name,
        "doctype": doctype,
        "customer": doc.get("customer") or "",
        "value": val,
        "date": str(doc.get("doc_date") or ""),
        "deadline": doc.get("deadline"),
        "flow_scope": doc.get("flow_scope") or "",
        "shipping_resp": doc.get("shipping_resp") or "",
        "company": doc.get("company") or "",
        "project": doc.get("project") or (doc.name if doctype == "Project" else ""),
        "owner": doc.get("owner") or "",
        "status": doc.get("status") or "",
        "items_count": 0,
        "overdue": bool(doc.get("overdue")) or _is_overdue(doc.get("deadline")),
        "open_sav_count": 0,
        "qc_failed": False,
        "column": None,  # resolved later
    }


def _make_card(doc, doctype, items_count=0, open_sav=0, qc_failed=False):
    return {
        "name": doc.name,
        "doctype": doctype,
        "customer": doc.get("customer") or "",
        "value": flt(doc.get("value")),
        "date": str(doc.get("doc_date") or ""),
        "deadline": doc.get("deadline"),
        "flow_scope": doc.get("flow_scope") or "",
        "shipping_resp": doc.get("shipping_resp") or "",
        "company": doc.get("company") or "",
        "project": doc.get("project") or (doc.name if doctype == "Project" else ""),
        "owner": doc.get("owner") or "",
        "status": doc.get("status") or "",
        "items_count": items_count,
        "overdue": _is_overdue(doc.get("deadline")),
        "open_sav_count": open_sav,
        "qc_failed": qc_failed,
        "column": None,
    }


# ── Trace engine ───────────────────────────────────────────────────────────

def _fetch_doc(doctype, name):
    """Fetch a document with its key fields."""
    try:
        return frappe.get_doc(doctype, name)
    except Exception:
        return None


def _build_node(doctype, doc):
    """Convert a Frappe doc to a trace node."""
    code = DOCTYPE_CODE.get(doctype, doctype)
    title = _get_doc_title(doctype, doc)
    status = _get_doc_status(doctype, doc)
    status_label = _get_doc_status_label(doctype, doc)
    date = _get_doc_date(doctype, doc)
    value = _get_doc_value(doctype, doc)

    return {
        "id": doc.name,
        "type": code,
        "doctype": doctype,
        "title": title,
        "status": status,
        "status_label": status_label,
        "date": date,
        "value": value,
    }


def _get_doc_title(doctype, doc):
    """Human-readable title for a document."""
    titles = {
        "Lead": getattr(doc, "company_name", "") or doc.name,
        "Opportunity": getattr(doc, "party_name", "") or doc.name,
        "Quotation": getattr(doc, "customer_name", "") or getattr(doc, "party_name", "") or doc.name,
        "Sales Order": getattr(doc, "customer_name", "") or doc.name,
        "Purchase Order": getattr(doc, "supplier_name", "") or doc.name,
        "Purchase Receipt": getattr(doc, "supplier_name", "") or doc.name,
        "Purchase Invoice": getattr(doc, "supplier_name", "") or doc.name,
        "Supplier": getattr(doc, "supplier_name", "") or doc.name,
        "Delivery Note": getattr(doc, "customer_name", "") or doc.name,
        "Delivery Trip": getattr(doc, "name", "") or doc.name,
        "Sales Invoice": getattr(doc, "customer_name", "") or doc.name,
        "Project": getattr(doc, "project_name", "") or doc.name,
        "SAV Ticket": getattr(doc, "subject", "") or doc.name,
        "Quality Inspection": getattr(doc, "report_no", "") or doc.name,
        "Communication": getattr(doc, "subject", "") or doc.name,
    }
    return titles.get(doctype, doc.name)


def _get_doc_status(doctype, doc):
    """Map document status to trace status codes."""
    raw = getattr(doc, "status", "")
    if doctype == "Communication":
        return "completed"

    status_map = {
        "completed": ["Completed", "Delivered", "Converted", "Return Issued", "Resolved", "Closed"],
        "active": ["Submitted", "Open", "To Deliver and Bill", "To Bill", "Overdue",
                    "To Receive and Bill", "To Receive", "Running", "Work In Progress",
                    "In Transit", "Planning", "Ready", "Loading"],
        "blocked": ["On Hold", "Blocked", "Rejected"],
        "warning": ["Overdue"],
    }

    for status, values in status_map.items():
        if raw in values:
            return status

    if raw in ("Cancelled", "Lost"):
        return "completed"

    return "pending"


def _get_doc_status_label(doctype, doc):
    """Return the document's real business status label for UI display."""
    raw = getattr(doc, "status", None)
    if raw:
        return str(raw)

    docstatus = cint(getattr(doc, "docstatus", 0) or 0)
    if docstatus == 1:
        return "Submitted"
    if docstatus == 2:
        return "Cancelled"
    return "Draft"


def _get_doc_date(doctype, doc):
    """Get the primary date from a document."""
    date_fields = {
        "Lead": "creation",
        "Opportunity": "transaction_date",
        "Quotation": "transaction_date",
        "Sales Order": "transaction_date",
        "Purchase Order": "transaction_date",
        "Delivery Note": "posting_date",
        "Delivery Trip": "departure_time",
        "Sales Invoice": "posting_date",
        "Purchase Invoice": "posting_date",
        "Purchase Receipt": "posting_date",
        "Payment Entry": "posting_date",
        "Project": "expected_start_date",
        "SAV Ticket": "creation",
        "Quality Inspection": "report_date",
        "Timesheet": "start_date",
        "Work Order": "creation",
        "Material Request": "transaction_date",
        "Pick List": "creation",
        "Issue": "creation",
        "Maintenance Schedule": "transaction_date",
        "Maintenance Visit": "mntc_date",
        "Communication": "creation",
        "Supplier": "creation",
    }
    field = date_fields.get(doctype, "creation")
    val = getattr(doc, field, None) or getattr(doc, "creation", None)
    return str(val)[:10] if val else ""


def _get_doc_value(doctype, doc):
    """Get monetary value from a document."""
    value_fields = {
        "Lead": "annual_revenue",
        "Opportunity": "opportunity_amount",
        "Quotation": "grand_total",
        "Sales Order": "grand_total",
        "Purchase Order": "grand_total",
        "Delivery Note": "grand_total",
        "Sales Invoice": "grand_total",
        "Purchase Invoice": "grand_total",
        "Payment Entry": "paid_amount",
        "SAV Ticket": "claim_amount",
        "Project": "gross_margin",
    }
    field = value_fields.get(doctype)
    if field:
        return flt(getattr(doc, field, 0))
    return 0


def _get_preview_field_candidates(doctype):
    candidates = {
        "Lead": ["status", "company_name", "email_id", "mobile_no", "territory"],
        "Opportunity": ["status", "party_name", "opportunity_type", "opportunity_from", "sales_stage", "opportunity_amount"],
        "Quotation": ["status", "party_name", "customer_name", "transaction_date", "valid_till", "grand_total"],
        "Sales Order": ["status", "customer_name", "transaction_date", "delivery_date", "custom_installation_project", "grand_total"],
        "Delivery Note": ["status", "customer_name", "posting_date", "project", "grand_total"],
        "Sales Invoice": ["status", "customer_name", "posting_date", "due_date", "grand_total", "outstanding_amount"],
        "Payment Entry": ["payment_type", "party", "posting_date", "paid_amount", "received_amount", "reference_no"],
        "Project": ["status", "project_name", "customer", "company", "expected_start_date", "expected_end_date", "custom_qc_status"],
        "Material Request": ["status", "transaction_date", "material_request_type", "company"],
        "Purchase Order": ["status", "supplier_name", "transaction_date", "schedule_date", "advance_payment_status", "grand_total"],
        "Purchase Receipt": ["status", "supplier_name", "posting_date", "project", "grand_total"],
        "Purchase Invoice": ["status", "supplier_name", "posting_date", "due_date", "grand_total", "outstanding_amount"],
        "Pick List": ["status", "purpose", "company"],
        "SAV Ticket": ["status", "customer", "defect_type", "priority", "severity", "assigned_technician"],
        "Issue": ["status", "subject", "raised_by", "customer", "priority"],
        "Maintenance Schedule": ["status", "transaction_date", "customer", "sales_order"],
        "Maintenance Visit": ["status", "mntc_date", "customer", "sales_order"],
        "Communication": ["communication_type", "communication_medium", "sender_full_name", "reference_doctype", "reference_name", "subject"],
    }
    return candidates.get(
        doctype,
        ["status", "company", "customer", "supplier", "posting_date", "transaction_date", "grand_total", "outstanding_amount"],
    )


def _format_preview_value(value):
    if hasattr(value, "isoformat"):
        return str(value)[:19]
    if isinstance(value, float):
        return str(round(value, 2))
    return str(value)


def _find_upstream_refs(from_dt, from_field, target_name, target_doctype=None):
    """Find documents that reference target_name via from_field.

    If from_dt is a child table (e.g. 'Sales Order Item'), queries it directly
    and returns the parent document names.
    If from_dt is a parent doctype with a child table field (e.g. 'Delivery Note', 'items.against_sales_order'),
    queries the child table and returns parent document names.
    Otherwise queries from_dt directly.
    """
    if from_field == "DYN_REF":
        refs = frappe.get_all(
            from_dt,
            filters={"reference_type": target_doctype, "reference_name": target_name},
            fields=["name"],
        )
        return [r.name for r in refs]

    if "." in from_field:
        table_field, child_field = from_field.split(".", 1)
        child_dt = _get_child_table_doctype(from_dt, table_field)
        if not child_dt:
            return []
        if not _doctype_has_field(child_dt, child_field):
            return []

        refs = frappe.get_all(
            child_dt,
            filters={"parenttype": from_dt, child_field: target_name},
            fields=["parent"],
            limit_page_length=0,
        )
        return list({r.parent for r in refs if getattr(r, "parent", None)})

    if _is_child_table(from_dt):
        refs = frappe.get_all(
            from_dt,
            filters={from_field: target_name},
            fields=["parent"],
            limit_page_length=0,
        )
        return list({r.parent for r in refs if getattr(r, "parent", None)})

    try:
        refs = frappe.get_all(
            from_dt,
            filters={from_field: target_name},
            fields=["name"],
            limit_page_length=0,
        )
    except Exception:
        return []

    return [r.name for r in refs]


def _find_downstream_refs(doc, from_field, to_dt):
    """Find documents that this doc references via from_field."""
    if "." in from_field:
        child_table, fieldname = from_field.split(".", 1)
        children = getattr(doc, child_table, [])
        refs = []
        for child in children:
            ref_name = getattr(child, fieldname, "")
            if not ref_name:
                continue
            reference_doctype = getattr(child, "reference_doctype", None)
            if reference_doctype and reference_doctype != to_dt:
                continue
            refs.append(ref_name)
        return refs
    else:
        val = getattr(doc, from_field, "")
        return [val] if val else []


def _add_communications(doc_name, doc_type, edges, queue, visited):
    """Add Communication nodes linked to this document."""
    comms = frappe.get_all(
        "Communication",
        filters={"reference_doctype": doc_type, "reference_name": doc_name},
        fields=["name", "subject", "communication_date as doc_date", "sender"],
        order_by="communication_date desc",
        limit=10,
    )
    for comm in comms:
        key = f"Communication::{comm.name}"
        if key in visited:
            continue
        visited.add(key)
        edges.append({"from": doc_name, "to": comm.name, "relation": "related"})
        queue.append(("Communication", comm.name, None))


def _compute_health(nodes):
    """Compute health summary from trace nodes."""
    payments = [n for n in nodes if n["type"] == "PAYMENT"]
    qcs = [n for n in nodes if n["type"] == "QC"]
    savs = [n for n in nodes if n["type"] == "SAV"]

    return {
        "payment_status": "Settled" if any(p["status"] == "completed" for p in payments) else "Pending",
        "payment_count": len(payments),
        "qc_passed": sum(1 for q in qcs if q["status"] == "completed"),
        "qc_total": len(qcs),
        "qc_status": "Warning" if any(q["status"] in ("blocked", "warning") for q in qcs) else ("Passed" if qcs else "Pending"),
        "open_sav": sum(1 for s in savs if s["status"] != "completed"),
        "total_sav": len(savs),
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _cards(docs, doctype, date_filter):
    return [card for doc in docs if (card := _card(doc, doctype, date_filter))]


def _get_grouped_counts(doctype, group_field, filters):
    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=[f"{group_field} as group_key", {"COUNT": "name", "as": "count"}],
        group_by=group_field,
        limit_page_length=0,
    )
    return {row.group_key: int(row.count or 0) for row in rows if row.group_key}


def _get_delivery_notes_by_sales_orders(sales_order_names):
    if not sales_order_names:
        return {}

    rows = frappe.get_all(
        "Delivery Note Item",
        filters={"against_sales_order": ["in", sales_order_names], "parenttype": "Delivery Note"},
        fields=["against_sales_order", "parent"],
        order_by="parent asc",
        limit_page_length=0,
    )

    delivery_notes_by_sales_order = {}
    for row in rows:
        if not row.against_sales_order or not row.parent:
            continue
        delivery_notes_by_sales_order.setdefault(row.against_sales_order, set()).add(row.parent)

    return delivery_notes_by_sales_order


def _get_rejected_delivery_notes(delivery_notes_by_sales_order):
    delivery_note_names = sorted(
        {
            delivery_note
            for delivery_notes in delivery_notes_by_sales_order.values()
            for delivery_note in delivery_notes
        }
    )
    if not delivery_note_names:
        return set()

    return set(
        frappe.get_all(
            "Quality Inspection",
            filters={
                "reference_type": "Delivery Note",
                "reference_name": ["in", delivery_note_names],
                "status": "Rejected",
            },
            pluck="reference_name",
            limit_page_length=0,
        )
    )


def _get_delivery_trip_customers(delivery_trip_names):
    if not delivery_trip_names:
        return {}

    rows = frappe.get_all(
        "Delivery Stop",
        filters={"parent": ["in", delivery_trip_names]},
        fields=["parent", "customer", "idx"],
        order_by="parent asc, idx asc",
        limit_page_length=0,
    )

    customers = {}
    for row in rows:
        if row.parent not in customers:
            customers[row.parent] = row.customer or ""

    return customers


def _get_child_table_doctype(parent_doctype, table_fieldname):
    try:
        field = frappe.get_meta(parent_doctype).get_field(table_fieldname)
    except Exception:
        return None

    return getattr(field, "options", None)


_CHILD_TABLE_CACHE = {}


def _is_child_table(doctype):
    """Check if a doctype is a child table (istable=1)."""
    if doctype in _CHILD_TABLE_CACHE:
        return _CHILD_TABLE_CACHE[doctype]
    try:
        meta = frappe.get_meta(doctype)
        result = getattr(meta, "istable", False)
        _CHILD_TABLE_CACHE[doctype] = result
        return result
    except Exception:
        return False


def _get_child_table_parent_field(child_table):
    """Get the parent reference field name on a child table (usually 'parent')."""
    return "parent"


_CHILD_PARENT_DOCTYPE_CACHE = {}


def _get_child_table_parent_doctype(child_table):
    """Resolve the parent doctype for a child table from DocField table definitions."""
    if child_table in _CHILD_PARENT_DOCTYPE_CACHE:
        return _CHILD_PARENT_DOCTYPE_CACHE[child_table]

    try:
        rows = frappe.get_all(
            "DocField",
            filters={"fieldtype": "Table", "options": child_table},
            fields=["parent"],
            limit_page_length=0,
        )
    except Exception:
        rows = []

    parent_doctype = rows[0].parent if rows else None
    _CHILD_PARENT_DOCTYPE_CACHE[child_table] = parent_doctype
    return parent_doctype


def _get_upstream_source_doctype(from_dt, from_field):
    """Determine the actual doctype returned by _find_upstream_refs."""
    if "." in from_field:
        return from_dt
    if _is_child_table(from_dt):
        return _get_child_table_parent_doctype(from_dt) or from_dt
    return from_dt


def _doctype_has_field(doctype, fieldname):
    try:
        meta = frappe.get_meta(doctype)
        has_field = getattr(meta, "has_field", None)
        if callable(has_field) and has_field(fieldname):
            return True
        return bool(meta.get_field(fieldname))
    except Exception:
        return False


def _query_fields(doctype, fields, optional_fields=None):
    query_fields = list(fields)
    for field in optional_fields or []:
        alias = None
        fieldname = field
        if isinstance(field, tuple):
            fieldname, alias = field
        if not _doctype_has_field(doctype, fieldname):
            continue
        query_fields.append(f"{fieldname} as {alias}" if alias else fieldname)
    return query_fields


def _doctype_exists(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _doc_exists(doctype, name):
    try:
        return bool(doctype and name and frappe.db.exists(doctype, name))
    except Exception:
        return False

def _is_overdue(date_str):
    if not date_str:
        return False
    try:
        return getdate(date_str) < getdate(today())
    except Exception:
        return False


def _skip_date_filter(date_str, filter_val):
    if not filter_val or filter_val == "all":
        return False
    if not date_str:
        return True

    try:
        d = getdate(date_str)
        t = getdate(today())
    except Exception:
        return True

    if filter_val == "today":
        return d != t
    elif filter_val == "this_week":
        return d.isocalendar()[1] != t.isocalendar()[1] or d.year != t.year
    elif filter_val == "this_month":
        return d.month != t.month or d.year != t.year

    return False
