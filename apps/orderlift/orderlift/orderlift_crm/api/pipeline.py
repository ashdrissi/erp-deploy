from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.orderlift_crm.status_config import UNASSIGNED_STATUS
from orderlift.orderlift_crm.status_workflow import list_editable_statuses, resolve_status_column


@frappe.whitelist()
def get_opportunity_pipeline_data(
    search: str | None = None,
    owner: str | None = None,
    source: str | None = None,
    company: str | None = None,
    business_type: str | None = None,
) -> dict:
    statuses = _filter_statuses_by_business_type(list_editable_statuses("Opportunity", include_inactive=False), business_type)
    cards = _opportunity_cards(
        search=search,
        owner=owner,
        source=source,
        company=company,
        business_type=business_type,
        statuses=statuses,
    )
    return {
        "columns": _build_columns(statuses, cards),
        "kpis": {
            "primary_label": _("Opportunities"),
            "primary_value": len(cards),
            "secondary_label": _("Pipeline Amount"),
            "secondary_value": f"{sum(flt(card.get('amount')) for card in cards):,.0f} DH",
            "tertiary_label": _("Quoted"),
            "tertiary_value": len([card for card in cards if any(doc.get("doctype") == "Quotation" for doc in card.get("docs", []))]),
            "quaternary_label": _("Stages"),
            "quaternary_value": len(statuses),
        },
        "filters": {
            "owners": sorted({card.get("owner") for card in cards if card.get("owner")}),
            "sources": sorted({card.get("source") for card in cards if card.get("source")}),
            "companies": sorted({card.get("company") for card in cards if card.get("company")}),
            "business_types": sorted({tag for card in cards for tag in [card.get("business_type")] if tag}),
        },
    }


@frappe.whitelist()
def update_opportunity_stage(opportunity: str, stage: str) -> dict:
    doc = frappe.get_doc("Opportunity", opportunity)
    _validate_status_for_document("Opportunity", stage, doc)
    previous = doc.sales_stage
    doc.sales_stage = stage
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_status_change("Opportunity", doc.name, previous, stage)
    statuses = list_editable_statuses("Opportunity", include_inactive=False)
    return _opportunity_card(doc.as_dict(), statuses)


@frappe.whitelist()
def get_project_pipeline_data(
    search: str | None = None,
    company: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    business_type: str | None = None,
    segment: str | None = None,
) -> dict:
    statuses = _filter_statuses_by_business_type(list_editable_statuses("Project", include_inactive=False), business_type or "Installation")
    cards = _project_cards(
        search=search,
        company=company,
        owner=owner,
        status=status,
        business_type=business_type,
        segment=segment,
        statuses=statuses,
    )
    completed_count = len([card for card in cards if card.get("stage") == "Completed"])
    return {
        "columns": _build_columns(statuses, cards),
        "kpis": {
            "primary_label": _("Projects"),
            "primary_value": len(cards),
            "secondary_label": _("Completed"),
            "secondary_value": completed_count,
            "tertiary_label": _("Blocked"),
            "tertiary_value": len([card for card in cards if card.get("stage") == "Blocked"]),
            "quaternary_label": _("Stages"),
            "quaternary_value": len(statuses),
        },
        "filters": {
            "companies": sorted({card.get("company") for card in cards if card.get("company")}),
            "owners": sorted({card.get("owner") for card in cards if card.get("owner")}),
            "statuses": [status["name"] for status in statuses],
            "business_types": sorted({card.get("business_type") for card in cards if card.get("business_type")}),
            "segments": sorted({card.get("crm_segment") for card in cards if card.get("crm_segment")}),
        },
    }


@frappe.whitelist()
def update_project_stage(project: str, stage: str) -> dict:
    doc = frappe.get_doc("Project", project)
    if not doc.meta.get_field("custom_project_status"):
        frappe.throw(_("Project is missing custom_project_status. Run migrate first."))
    _validate_status_for_document("Project", stage, doc)
    previous = doc.custom_project_status
    doc.custom_project_status = stage
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_status_change("Project", doc.name, previous, stage)
    statuses = list_editable_statuses("Project", include_inactive=False)
    return _project_card(doc.as_dict(), statuses)


@frappe.whitelist()
def get_sales_order_pipeline_data(
    search: str | None = None,
    company: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    business_type: str | None = None,
    segment: str | None = None,
    delivery_progress: str | None = None,
    billing_progress: str | None = None,
) -> dict:
    statuses = list_editable_statuses("Sales Order", include_inactive=False)
    cards = _sales_order_cards(
        search=search,
        company=company,
        owner=owner,
        status=status,
        business_type=business_type,
        segment=segment,
        delivery_progress=delivery_progress,
        billing_progress=billing_progress,
        statuses=statuses,
    )
    return {
        "columns": _build_columns(statuses, cards),
        "kpis": {
            "primary_label": _("Sales Orders"),
            "primary_value": len(cards),
            "secondary_label": _("Order Amount"),
            "secondary_value": f"{sum(flt(card.get('amount')) for card in cards):,.0f} DH",
            "tertiary_label": _("Delivered"),
            "tertiary_value": len([card for card in cards if card.get("stage") in {"Delivered", "Completed"}]),
            "quaternary_label": _("Stages"),
            "quaternary_value": len(statuses),
        },
        "filters": {
            "companies": sorted({card.get("company") for card in cards if card.get("company")}),
            "owners": sorted({card.get("owner") for card in cards if card.get("owner")}),
            "statuses": [status["name"] for status in statuses],
            "business_types": sorted({card.get("business_type") for card in cards if card.get("business_type")}),
            "segments": sorted({card.get("crm_segment") for card in cards if card.get("crm_segment")}),
            "delivery_progress": ["Not delivered", "Partially delivered", "Delivered"],
            "billing_progress": ["Not billed", "Partially billed", "Billed"],
        },
    }


@frappe.whitelist()
def update_sales_order_stage(sales_order: str, stage: str) -> dict:
    doc = frappe.get_doc("Sales Order", sales_order)
    if not doc.meta.get_field("custom_orderlift_order_status"):
        frappe.throw(_("Sales Order is missing custom_orderlift_order_status. Run migrate first."))
    _validate_status_for_document("Sales Order", stage, doc)
    previous = doc.custom_orderlift_order_status
    doc.custom_orderlift_order_status = stage
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_status_change("Sales Order", doc.name, previous, stage)
    statuses = list_editable_statuses("Sales Order", include_inactive=False)
    return _sales_order_card(doc.as_dict(), statuses)


def _opportunity_cards(search=None, owner=None, source=None, company=None, business_type=None, statuses=None) -> list[dict]:
    filters = {"docstatus": ["<", 2]}
    if owner and owner != "All":
        filters["opportunity_owner"] = owner
    if company and company != "All":
        filters["company"] = company
    if source and source != "All" and _has_field("Opportunity", "custom_source_channel"):
        filters["custom_source_channel"] = source
    if business_type and business_type != "All" and _has_field("Opportunity", "custom_crm_business_type"):
        filters["custom_crm_business_type"] = business_type

    fields = [
        "name",
        "title",
        "party_name",
        "customer_name",
        "opportunity_amount",
        "opportunity_owner",
        "probability",
        "status",
        "sales_stage",
        "company",
        "opportunity_from",
    ]
    for custom_field in ["custom_next_action", "custom_source_channel", "custom_crm_business_type", "custom_crm_segment", "custom_partner_segment"]:
        if _has_field("Opportunity", custom_field):
            fields.append(custom_field)

    rows = frappe.get_all("Opportunity", filters=filters, fields=fields, order_by="modified desc", limit_page_length=200)
    cards = [_opportunity_card(row, statuses or []) for row in rows]
    if search:
        needle = search.strip().lower()
        cards = [
            card
            for card in cards
            if needle in f"{card.get('name')} {card.get('title')} {card.get('subtitle')} {card.get('company')} {card.get('source')}".lower()
        ]
    return cards


def _opportunity_card(row, statuses: list[dict]) -> dict:
    docs = _opportunity_related_docs(row.get("name"))
    stage = _resolve_opportunity_stage(row, docs, statuses)
    return {
        "name": row.get("name"),
        "title": row.get("title") or row.get("name"),
        "subtitle": row.get("customer_name") or row.get("party_name") or "",
        "amount": row.get("opportunity_amount") or 0,
        "company": row.get("company") or "",
        "business_type": row.get("custom_crm_business_type") or "",
        "crm_segment": row.get("custom_crm_segment") or row.get("custom_partner_segment") or "",
        "owner": row.get("opportunity_owner") or "",
        "source": row.get("custom_source_channel") or "",
        "stage": stage,
        "legacy_status": row.get("status") or "",
        "tags": [
            row.get("opportunity_from"),
            row.get("custom_crm_business_type"),
            row.get("custom_crm_segment") or row.get("custom_partner_segment"),
            row.get("custom_source_channel"),
        ],
        "metrics": [
            {"label": _("ERP Status"), "value": row.get("status") or "-"},
            {"label": _("Probability"), "value": f"{flt(row.get('probability') or 0):.0f}%"},
            {"label": _("Owner"), "value": row.get("opportunity_owner") or "-"},
        ],
        "docs": docs,
    }


def _resolve_opportunity_stage(row, docs: list[dict], statuses: list[dict]) -> str:
    active_names = {status["name"] for status in statuses}
    stage = row.get("sales_stage")
    if stage in active_names:
        return stage
    labels = {doc.get("doctype") for doc in docs}
    if row.get("status") == "Lost" and "Lost" in active_names:
        return "Lost"
    if {"Sales Order", "Project"} & labels and "Won / Project" in active_names:
        return "Won / Project"
    if "Quotation" in labels and "Quotation Sent" in active_names:
        return "Quotation Sent"
    if statuses:
        default_stage = next((status["name"] for status in statuses if status.get("is_default")), statuses[0]["name"])
        return default_stage
    return UNASSIGNED_STATUS


def _opportunity_related_docs(opportunity: str) -> list[dict]:
    docs = []
    quotation = frappe.db.get_value(
        "Quotation",
        {"opportunity": opportunity, "docstatus": ["<", 2]},
        ["name", "status"],
        as_dict=True,
    )
    if not quotation:
        return docs
    docs.append(_doc_link("Quotation", quotation.name, _("Quotation"), quotation.status))

    sales_orders = frappe.db.sql(
        """
        SELECT DISTINCT so.name, so.status, COALESCE(so.custom_installation_project, so.project) AS project_name
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.prevdoc_docname = %s AND so.docstatus < 2
        ORDER BY so.modified DESC
        LIMIT 3
        """,
        (quotation.name,),
        as_dict=True,
    )
    for sales_order in sales_orders:
        docs.append(_doc_link("Sales Order", sales_order.name, _("Sales Order"), sales_order.status))
        if sales_order.project_name:
            project_status = frappe.db.get_value(
                "Project",
                sales_order.project_name,
                ["custom_project_status", "status"],
                as_dict=True,
            )
            if project_status:
                docs.append(
                    _doc_link(
                        "Project",
                        sales_order.project_name,
                        _("Project"),
                        project_status.get("custom_project_status") or project_status.get("status") or "-",
                    )
                )
    return docs


def _project_cards(search=None, company=None, owner=None, status=None, business_type=None, segment=None, statuses=None) -> list[dict]:
    filters = {}
    if company and company != "All":
        filters["company"] = company
    if owner and owner != "All" and _has_field("Project", "project_owner"):
        filters["project_owner"] = owner
    fields = ["name", "project_name", "customer", "company", "status"]
    for fieldname in ["project_owner", "custom_project_status", "custom_qc_status", "custom_crm_business_type", "custom_crm_segment", "custom_partner_segment"]:
        if _has_field("Project", fieldname):
            fields.append(fieldname)
    rows = frappe.get_all("Project", filters=filters, fields=fields, order_by="modified desc", limit_page_length=200)
    cards = [_project_card(row, statuses or []) for row in rows]
    cards = _filter_cards_by_common_criteria(cards, status=status, business_type=business_type, segment=segment)
    if search:
        needle = search.strip().lower()
        cards = [
            card
            for card in cards
            if needle in f"{card.get('name')} {card.get('title')} {card.get('subtitle')} {card.get('company')}".lower()
        ]
    return cards


def _project_card(row, statuses: list[dict]) -> dict:
    docs = _project_related_docs(row.get("name"))
    stage = resolve_status_column("Project", row.get("custom_project_status"), row.get("status"), statuses)
    tags = []
    for tag in [row.get("custom_crm_business_type") or "Installation", row.get("custom_crm_segment") or row.get("custom_partner_segment")]:
        if tag:
            tags.append(tag)
    if row.get("custom_qc_status"):
        tags.append(f"QC {row.get('custom_qc_status')}")
    return {
        "name": row.get("name"),
        "title": row.get("project_name") or row.get("name"),
        "subtitle": row.get("customer") or "",
        "amount": 0,
        "company": row.get("company") or "",
        "owner": row.get("project_owner") or "",
        "business_type": row.get("custom_crm_business_type") or "Installation",
        "crm_segment": row.get("custom_crm_segment") or row.get("custom_partner_segment") or "",
        "stage": stage,
        "legacy_status": row.get("status") or "",
        "tags": tags,
        "metrics": [
            {"label": _("ERP Status"), "value": row.get("status") or "-"},
            {"label": _("Customer"), "value": row.get("customer") or "-"},
            {"label": _("QC"), "value": row.get("custom_qc_status") or "-"},
        ],
        "docs": docs,
    }


def _project_related_docs(project: str) -> list[dict]:
    docs = []
    for row in frappe.db.sql(
        """
        SELECT name, status
        FROM `tabSales Order`
        WHERE docstatus < 2 AND (project = %s OR custom_installation_project = %s)
        ORDER BY modified DESC
        LIMIT 3
        """,
        (project, project),
        as_dict=True,
    ):
        docs.append(_doc_link("Sales Order", row.name, _("Sales Order"), row.status))
    for row in _linked_status_rows(
        "Purchase Order",
        """
        SELECT DISTINCT po.name, po.status
        FROM `tabPurchase Order` po
        LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        WHERE po.docstatus < 2 AND (po.project = %s OR poi.project = %s)
        ORDER BY po.modified DESC
        LIMIT 3
        """,
        (project, project),
    ):
        docs.append(_doc_link("Purchase Order", row["name"], _("Purchase Order"), row["status"]))
    for row in _linked_status_rows(
        "Delivery Note",
        """
        SELECT DISTINCT dn.name, dn.status
        FROM `tabDelivery Note` dn
        LEFT JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
        WHERE dn.docstatus < 2 AND (dn.project = %s OR dni.project = %s)
        ORDER BY dn.modified DESC
        LIMIT 3
        """,
        (project, project),
    ):
        docs.append(_doc_link("Delivery Note", row["name"], _("Delivery Note"), row["status"]))
    for row in _linked_status_rows(
        "Sales Invoice",
        """
        SELECT DISTINCT si.name, si.status
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus < 2 AND (si.project = %s OR sii.project = %s)
        ORDER BY si.modified DESC
        LIMIT 3
        """,
        (project, project),
    ):
        docs.append(_doc_link("Sales Invoice", row["name"], _("Sales Invoice"), row["status"]))
    return docs


def _sales_order_cards(
    search=None,
    company=None,
    owner=None,
    status=None,
    business_type=None,
    segment=None,
    delivery_progress=None,
    billing_progress=None,
    statuses=None,
) -> list[dict]:
    filters = {"docstatus": ["<", 2]}
    if company and company != "All":
        filters["company"] = company
    if owner and owner != "All":
        filters["owner"] = owner
    fields = ["name", "customer", "company", "owner", "status", "grand_total", "per_delivered", "per_billed", "project"]
    for fieldname in ["custom_orderlift_order_status", "custom_installation_project", "custom_crm_business_type", "custom_crm_segment", "custom_partner_segment"]:
        if _has_field("Sales Order", fieldname):
            fields.append(fieldname)
    rows = frappe.get_all("Sales Order", filters=filters, fields=fields, order_by="modified desc", limit_page_length=200)
    cards = [_sales_order_card(row, statuses or []) for row in rows]
    cards = _filter_cards_by_common_criteria(cards, status=status, business_type=business_type, segment=segment)
    cards = [
        card
        for card in cards
        if _progress_bucket(card.get("delivered_pct"), "delivered") == delivery_progress or not delivery_progress or delivery_progress == "All"
    ]
    cards = [
        card
        for card in cards
        if _progress_bucket(card.get("billed_pct"), "billed") == billing_progress or not billing_progress or billing_progress == "All"
    ]
    if search:
        needle = search.strip().lower()
        cards = [
            card
            for card in cards
            if needle in f"{card.get('name')} {card.get('title')} {card.get('subtitle')} {card.get('company')}".lower()
        ]
    return cards


def _sales_order_card(row, statuses: list[dict]) -> dict:
    docs = _sales_order_related_docs(row.get("name"), row.get("project") or row.get("custom_installation_project"))
    stage = resolve_status_column("Sales Order", row.get("custom_orderlift_order_status"), row.get("status"), statuses)
    delivered_pct = flt(row.get("per_delivered") or 0)
    billed_pct = flt(row.get("per_billed") or 0)
    business_type = _sales_order_business_type(row)
    return {
        "name": row.get("name"),
        "title": row.get("customer") or row.get("name"),
        "subtitle": row.get("company") or "",
        "amount": row.get("grand_total") or 0,
        "company": row.get("company") or "",
        "owner": row.get("owner") or "",
        "business_type": business_type,
        "crm_segment": row.get("custom_crm_segment") or row.get("custom_partner_segment") or "",
        "stage": stage,
        "delivered_pct": delivered_pct,
        "billed_pct": billed_pct,
        "legacy_status": row.get("status") or "",
        "tags": [tag for tag in [business_type, row.get("custom_crm_segment") or row.get("custom_partner_segment")] if tag],
        "metrics": [
            {"label": _("ERP Status"), "value": row.get("status") or "-"},
            {"label": _("Delivered"), "value": f"{delivered_pct:.0f}%"},
            {"label": _("Billed"), "value": f"{billed_pct:.0f}%"},
        ],
        "docs": docs,
    }


def _sales_order_related_docs(sales_order: str, project_name: str | None) -> list[dict]:
    docs = []
    if project_name:
        project_status = frappe.db.get_value(
            "Project",
            project_name,
            ["custom_project_status", "status"],
            as_dict=True,
        )
        if project_status:
            docs.append(
                _doc_link(
                    "Project",
                    project_name,
                    _("Project"),
                    project_status.get("custom_project_status") or project_status.get("status") or "-",
                )
            )
    for row in _linked_status_rows(
        "Material Request",
        """
        SELECT DISTINCT mr.name, mr.status
        FROM `tabMaterial Request` mr
        INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
        WHERE mr.docstatus < 2 AND mri.sales_order = %s
        ORDER BY mr.modified DESC
        LIMIT 3
        """,
        (sales_order,),
    ):
        docs.append(_doc_link("Material Request", row["name"], _("Material Request"), row["status"]))
    for row in _linked_status_rows(
        "Purchase Order",
        """
        SELECT DISTINCT po.name, po.status
        FROM `tabPurchase Order` po
        INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        WHERE po.docstatus < 2 AND poi.sales_order = %s
        ORDER BY po.modified DESC
        LIMIT 3
        """,
        (sales_order,),
    ):
        docs.append(_doc_link("Purchase Order", row["name"], _("Purchase Order"), row["status"]))
    for row in _linked_status_rows(
        "Delivery Note",
        """
        SELECT DISTINCT dn.name, dn.status
        FROM `tabDelivery Note` dn
        INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
        WHERE dn.docstatus < 2 AND dni.against_sales_order = %s
        ORDER BY dn.modified DESC
        LIMIT 3
        """,
        (sales_order,),
    ):
        docs.append(_doc_link("Delivery Note", row["name"], _("Delivery Note"), row["status"]))
    for row in _linked_status_rows(
        "Sales Invoice",
        """
        SELECT DISTINCT si.name, si.status
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus < 2 AND sii.sales_order = %s
        ORDER BY si.modified DESC
        LIMIT 3
        """,
        (sales_order,),
    ):
        docs.append(_doc_link("Sales Invoice", row["name"], _("Sales Invoice"), row["status"]))
    return docs


def _sales_order_business_type(row) -> str:
    if row.get("custom_crm_business_type"):
        return row.get("custom_crm_business_type")
    if row.get("custom_installation_project") or row.get("project"):
        return "Installation"
    return "Distribution"


def _linked_status_rows(doctype: str, query: str, params: tuple) -> list[dict]:
    return frappe.db.sql(query, params, as_dict=True)


def _build_columns(statuses: list[dict], cards: list[dict]) -> list[dict]:
    columns = []
    unassigned_cards = [card for card in cards if card.get("stage") == UNASSIGNED_STATUS]
    if unassigned_cards:
        columns.append(
            {
                "name": UNASSIGNED_STATUS,
                "label": _("Unassigned"),
                "color": "Gray",
                "cards": unassigned_cards,
            }
        )
    for status in statuses:
        columns.append(
            {
                "name": status["name"],
                "label": status["label"],
                "color": status["color"],
                "cards": [card for card in cards if card.get("stage") == status["name"]],
            }
        )
    return columns


def _filter_statuses_by_business_type(statuses: list[dict], business_type: str | None) -> list[dict]:
    if not business_type or business_type == "All":
        return statuses
    key = "applies_distribution" if business_type == "Distribution" else "applies_installation"
    return [status for status in statuses if status.get(key)]


def _filter_cards_by_common_criteria(cards: list[dict], status=None, business_type=None, segment=None) -> list[dict]:
    if status and status != "All":
        cards = [card for card in cards if card.get("stage") == status]
    if business_type and business_type != "All":
        cards = [card for card in cards if card.get("business_type") == business_type]
    if segment and segment != "All":
        cards = [card for card in cards if card.get("crm_segment") == segment]
    return cards


def _progress_bucket(value, kind: str) -> str:
    percentage = flt(value or 0)
    if percentage >= 100:
        return "Delivered" if kind == "delivered" else "Billed"
    if percentage > 0:
        return "Partially delivered" if kind == "delivered" else "Partially billed"
    return "Not delivered" if kind == "delivered" else "Not billed"


def _doc_link(doctype: str, name: str, label: str, status: str | None) -> dict:
    return {"doctype": doctype, "name": name, "label": label, "status": status or "-"}


def _validate_status_for_document(document_type: str, stage: str, doc) -> dict:
    statuses = {status["name"]: status for status in list_editable_statuses(document_type, include_inactive=False)}
    status = statuses.get(stage)
    if not status:
        frappe.throw(_("Status {0} is not active for {1}.").format(stage, document_type))
    business_type = _document_business_type(document_type, doc)
    if business_type == "Distribution" and not status.get("applies_distribution"):
        frappe.throw(_("Status {0} does not apply to Distribution {1} records.").format(stage, document_type))
    if business_type == "Installation" and not status.get("applies_installation"):
        frappe.throw(_("Status {0} does not apply to Installation {1} records.").format(stage, document_type))
    return status


def _document_business_type(document_type: str, doc) -> str | None:
    if document_type == "Project":
        return "Installation"
    if document_type == "Sales Order":
        if doc.meta.get_field("custom_crm_business_type") and doc.get("custom_crm_business_type"):
            return doc.get("custom_crm_business_type")
        if doc.get("custom_installation_project") or doc.get("project"):
            return "Installation"
        return "Distribution"
    if document_type == "Opportunity" and doc.meta.get_field("custom_crm_business_type"):
        return doc.get("custom_crm_business_type")
    return None


def _log_status_change(document_type: str, name: str, previous: str | None, current: str) -> None:
    try:
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": document_type,
                "reference_name": name,
                "content": _("Pipeline status changed from {0} to {1}").format(previous or "-", current),
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Orderlift pipeline status audit log failed")


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))
