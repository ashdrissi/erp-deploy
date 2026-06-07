from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from orderlift.menu_access import get_company_access_payload, user_can_access_company
from orderlift.orderlift_crm.company_business_type import get_single_company_business_type
from orderlift.orderlift_crm.status_config import UNASSIGNED_STATUS
from orderlift.orderlift_crm.status_checks import validate_status_checks
from orderlift.orderlift_crm.todo_priority import normalize_todo_priority
from orderlift.orderlift_crm.status_workflow import list_editable_statuses, resolve_status_column

PIPELINE_ASSIGNMENT_MARKER = "[Orderlift Pipeline]"
SUPPORTED_PIPELINE_DOCUMENT_TYPES = {"Opportunity", "Project", "Sales Order"}
DEFAULT_DRAFT_COMPANY = "Orderlift Maroc Installation"
DEFAULT_DRAFT_PROSPECT = "Draft Unassigned Prospect"
DEFAULT_INSTALLATION_BUSINESS_TYPE = "Installation"
DEFAULT_INSTALLATION_SEGMENT = "Individu"
DEFAULT_OPPORTUNITY_STAGE = "1. Demande Client"


@frappe.whitelist()
def get_opportunity_pipeline_data(
    search: str | None = None,
    owner: str | None = None,
    source: str | None = None,
    company: str | None = None,
    business_type: str | None = None,
    segment: str | None = None,
) -> dict:
    company = _resolve_pipeline_company(company)
    statuses = _filter_statuses_by_business_type(
        list_editable_statuses("Opportunity", include_inactive=False, company=company),
        business_type,
    )
    cards = _opportunity_cards(
        search=search,
        owner=owner,
        source=source,
        company=company,
        business_type=business_type,
        segment=segment,
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
            "companies": _allowed_pipeline_companies(),
            "business_types": sorted({tag for card in cards for tag in [card.get("business_type")] if tag}),
            "segments": sorted({card.get("crm_segment") for card in cards if card.get("crm_segment")}),
        },
        "selected_company": company,
    }


@frappe.whitelist()
def update_opportunity_stage(opportunity: str, stage: str) -> dict:
    doc = frappe.get_doc("Opportunity", opportunity)
    status_info = _validate_status_for_document("Opportunity", stage, doc)
    previous = doc.sales_stage
    doc.sales_stage = stage
    if status_info.get("auto_close_opportunity") and doc.meta.get_field("status"):
        doc.status = "Closed"
    doc.save(ignore_permissions=False)
    assignment = sync_pipeline_status_assignment("Opportunity", doc.name, status_info, stage)
    frappe.db.commit()
    _log_status_change("Opportunity", doc.name, previous, stage)
    statuses = list_editable_statuses("Opportunity", include_inactive=False, company=doc.get("company"))
    card = _opportunity_card(doc.as_dict(), statuses)
    card["assignment"] = assignment
    return card


@frappe.whitelist()
def get_project_pipeline_data(
    search: str | None = None,
    company: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    business_type: str | None = None,
    segment: str | None = None,
) -> dict:
    company = _resolve_pipeline_company(company)
    statuses = _filter_statuses_by_business_type(
        list_editable_statuses("Project", include_inactive=False, company=company),
        business_type or "Installation",
    )
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
            "companies": _allowed_pipeline_companies(),
            "owners": sorted({card.get("owner") for card in cards if card.get("owner")}),
            "statuses": [status["name"] for status in statuses],
            "business_types": sorted({card.get("business_type") for card in cards if card.get("business_type")}),
            "segments": sorted({card.get("crm_segment") for card in cards if card.get("crm_segment")}),
        },
        "selected_company": company,
    }


@frappe.whitelist()
def update_project_stage(project: str, stage: str) -> dict:
    doc = frappe.get_doc("Project", project)
    if not doc.meta.get_field("custom_project_status"):
        frappe.throw(_("Project is missing custom_project_status. Run migrate first."))
    status_info = _validate_status_for_document("Project", stage, doc)
    previous = doc.custom_project_status
    doc.custom_project_status = stage
    doc.save(ignore_permissions=False)
    assignment = sync_pipeline_status_assignment("Project", doc.name, status_info, stage)
    frappe.db.commit()
    _log_status_change("Project", doc.name, previous, stage)
    statuses = list_editable_statuses("Project", include_inactive=False, company=doc.get("company"))
    card = _project_card(doc.as_dict(), statuses)
    card["assignment"] = assignment
    return card


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
    company = _resolve_pipeline_company(company)
    statuses = list_editable_statuses("Sales Order", include_inactive=False, company=company)
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
            "companies": _allowed_pipeline_companies(),
            "owners": sorted({card.get("owner") for card in cards if card.get("owner")}),
            "statuses": [status["name"] for status in statuses],
            "business_types": sorted({card.get("business_type") for card in cards if card.get("business_type")}),
            "segments": sorted({card.get("crm_segment") for card in cards if card.get("crm_segment")}),
            "delivery_progress": ["Not delivered", "Partially delivered", "Delivered"],
            "billing_progress": ["Not billed", "Partially billed", "Billed"],
        },
        "selected_company": company,
    }


@frappe.whitelist()
def update_sales_order_stage(sales_order: str, stage: str) -> dict:
    doc = frappe.get_doc("Sales Order", sales_order)
    if not doc.meta.get_field("custom_orderlift_order_status"):
        frappe.throw(_("Sales Order is missing custom_orderlift_order_status. Run migrate first."))
    status_info = _validate_status_for_document("Sales Order", stage, doc)
    previous = doc.custom_orderlift_order_status
    doc.custom_orderlift_order_status = stage
    doc.save(ignore_permissions=False)
    assignment = sync_pipeline_status_assignment("Sales Order", doc.name, status_info, stage)
    frappe.db.commit()
    _log_status_change("Sales Order", doc.name, previous, stage)
    statuses = list_editable_statuses("Sales Order", include_inactive=False, company=doc.get("company"))
    card = _sales_order_card(doc.as_dict(), statuses)
    card["assignment"] = assignment
    return card


@frappe.whitelist()
def assign_pipeline_document(document_type: str, document_name: str, user: str | None = None) -> dict:
    document_type = (document_type or "").strip()
    document_name = (document_name or "").strip()
    if document_type not in SUPPORTED_PIPELINE_DOCUMENT_TYPES:
        frappe.throw(_("Unsupported pipeline document type: {0}").format(document_type))
    if not frappe.db.exists(document_type, document_name):
        frappe.throw(_("{0} {1} was not found.").format(document_type, document_name))

    user = (user or "").strip()
    if user:
        doc = frappe.get_doc(document_type, document_name)
        assignment = _assign_pipeline_document(document_type, document_name, user, _current_pipeline_stage(document_type, doc))
    else:
        _clear_pipeline_assignment_todos(document_type, document_name)
        assignment = _assignment_payload("")
    frappe.db.commit()
    card = _card_for_document(document_type, document_name)
    card["assignment"] = assignment
    return {"card": card, "assignment": assignment}


@frappe.whitelist()
def get_party_crm_classification(party_type: str, party_name: str) -> dict:
    party_type = (party_type or "").strip()
    party_name = (party_name or "").strip()
    if party_type not in {"Lead", "Prospect", "Customer"} or not party_name:
        return {"business_type": "", "crm_segment": "", "segments": []}
    if not frappe.db.exists(party_type, party_name):
        frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))

    segments = _party_crm_segments(party_type, party_name)
    primary = segments[0] if segments else {}
    return {
        "business_type": primary.get("business_type") or "",
        "crm_segment": primary.get("segment") or "",
        "segments": segments,
    }


@frappe.whitelist()
def get_party_defaults(party_type: str, party_name: str) -> dict:
    party_type = (party_type or "").strip()
    party_name = (party_name or "").strip()
    if party_type not in {"Lead", "Prospect", "Customer"} or not party_name:
        return {}
    if not frappe.db.exists(party_type, party_name):
        frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))

    doc = frappe.get_doc(party_type, party_name)
    classification = get_party_crm_classification(party_type, party_name)
    contact = _primary_contact_for_party(party_type, party_name)
    return {
        "party_type": party_type,
        "party_name": party_name,
        "display_name": _party_display_name(doc, party_type),
        "business_type": classification.get("business_type") or "",
        "crm_segment": classification.get("crm_segment") or "",
        "segments": classification.get("segments") or [],
        "tier": doc.get("manual_tier") or doc.get("tier") or "",
        "company": doc.get("company") or "",
        "industry": doc.get("industry") or "",
        "territory": doc.get("territory") or "",
        "city": doc.get("city") or "",
        "website": doc.get("website") or "",
        "customer_group": doc.get("customer_group") or "",
        "source": doc.get("source") or doc.get("utm_source") or "",
        "email": doc.get("email_id") or contact.get("email_id") or "",
        "mobile": doc.get("mobile_no") or doc.get("whatsapp_no") or contact.get("mobile_no") or "",
        "phone": doc.get("phone") or contact.get("phone") or contact.get("mobile_no") or "",
    }


@frappe.whitelist()
def create_draft_opportunity(company: str | None = None, business_type: str | None = None, segment: str | None = None) -> dict:
    company = _resolve_draft_company(company)
    business_type = (business_type or DEFAULT_INSTALLATION_BUSINESS_TYPE).strip()
    segment = (segment or DEFAULT_INSTALLATION_SEGMENT).strip()
    prospect = _ensure_draft_prospect(company=company, business_type=business_type, segment=segment)

    doc = frappe.new_doc("Opportunity")
    doc.naming_series = _default_naming_series("Opportunity") or "CRM-OPP-.YYYY.-"
    doc.opportunity_from = "Prospect"
    doc.party_name = prospect
    doc.customer_name = DEFAULT_DRAFT_PROSPECT
    doc.title = _("Draft Opportunity")
    doc.status = "Open"
    doc.sales_stage = DEFAULT_OPPORTUNITY_STAGE
    doc.opportunity_type = _default_opportunity_type()
    doc.company = company
    doc.transaction_date = nowdate()
    if doc.meta.get_field("custom_first_contact_date"):
        doc.custom_first_contact_date = nowdate()
    if doc.meta.get_field("custom_crm_business_type"):
        doc.custom_crm_business_type = business_type
    if doc.meta.get_field("custom_crm_segment"):
        doc.custom_crm_segment = segment
    desired_name = _assign_preform_opportunity_name(doc)
    doc.insert(ignore_permissions=False)
    _rename_preform_opportunity_if_needed(doc, desired_name)
    frappe.db.commit()
    return {"name": doc.name, "route": ["Form", "Opportunity", doc.name]}


@frappe.whitelist()
def create_opportunity_from_preform(values: str | dict) -> dict:
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    company = _resolve_draft_company(values.get("company"))
    business_type = (values.get("business_type") or get_single_company_business_type(company) or "").strip()
    segment = (values.get("segment") or "").strip()
    party_type = (values.get("party_type") or "Prospect").strip()
    party_name = (values.get("party_name") or "").strip()
    client_name = (values.get("client_name") or values.get("title") or "").strip()
    phone = (values.get("phone") or "").strip()
    tier = (values.get("tier") or "").strip()
    territory = (values.get("territory") or "").strip()
    address = (values.get("address") or "").strip()

    if not client_name and not party_name:
        frappe.throw(_("Client or party is required."))
    if party_type not in {"Lead", "Prospect", "Customer"}:
        frappe.throw(_("Party Type must be Lead, Prospect, or Customer."))
    if party_name and not client_name:
        client_name = party_name
    if party_type in {"Prospect", "Customer"} and not frappe.db.exists(party_type, party_name):
        party_name = _create_preform_party(party_type, client_name, company, business_type, segment, phone, tier, territory)
    elif not party_name:
        party_type = "Prospect"
        party_name = _create_preform_party(party_type, client_name, company, business_type, segment, phone, tier, territory)
    elif not frappe.db.exists(party_type, party_name):
        frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))

    doc = frappe.new_doc("Opportunity")
    doc.naming_series = _default_naming_series("Opportunity") or "CRM-OPP-.YYYY.-"
    doc.opportunity_from = party_type
    doc.party_name = party_name
    doc.customer_name = client_name or _party_display_name(frappe.get_doc(party_type, party_name), party_type)
    doc.title = (values.get("title") or doc.customer_name or party_name).strip()
    doc.status = "Open"
    doc.sales_stage = DEFAULT_OPPORTUNITY_STAGE
    doc.opportunity_type = _default_opportunity_type()
    doc.company = company
    doc.transaction_date = nowdate()
    doc.opportunity_owner = frappe.session.user
    _set_if_field(doc, "custom_first_contact_date", nowdate())
    _set_if_field(doc, "custom_crm_business_type", business_type)
    _set_if_field(doc, "custom_crm_segment", segment)
    _set_if_field(doc, "custom_tier", tier or _tier_for_party(party_type, party_name))
    _set_if_field(doc, "custom_urgency", cint(values.get("urgency")))
    _set_if_field(doc, "custom_probability_level", values.get("probability_level") or "")
    _set_if_field(doc, "phone", phone)
    _set_if_field(doc, "contact_mobile", phone)
    _set_if_field(doc, "territory", territory)
    _set_if_field(doc, "address_display", address)
    _set_if_field(doc, "custom_site_address", address)
    desired_name = _assign_preform_opportunity_name(doc)
    doc.insert(ignore_permissions=False)
    _rename_preform_opportunity_if_needed(doc, desired_name)

    comment = (values.get("comment") or "").strip()
    if comment:
        _add_preform_comment(doc.name, comment)
    attachment = (values.get("attachment") or "").strip()
    if attachment:
        _attach_preform_file(doc.name, attachment)
    frappe.db.commit()
    return {"name": doc.name, "route": ["Form", "Opportunity", doc.name]}


@frappe.whitelist()
def prepare_quotation_from_opportunity(opportunity: str) -> dict:
    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        frappe.throw(_("Opportunity {0} was not found.").format(opportunity or ""))

    doc = frappe.get_doc("Opportunity", opportunity)
    customer = _customer_for_opportunity_party(doc)
    return {
        "route_options": {
            "quotation_to": "Customer",
            "party_name": customer.name,
            "customer_name": customer.customer_name,
            "opportunity": doc.name,
            "company": doc.get("company") or "",
            "custom_crm_business_type": doc.get("custom_crm_business_type") or "",
            "custom_crm_segment": doc.get("custom_crm_segment") or "",
        },
        "customer": customer.name,
        "customer_created": bool(getattr(customer, "_orderlift_created", False)),
    }


def _opportunity_cards(search=None, owner=None, source=None, company=None, business_type=None, segment=None, statuses=None) -> list[dict]:
    filters = {"docstatus": ["<", 2]}
    if owner and owner != "All":
        filters["opportunity_owner"] = owner
    if company and company != "All":
        filters["company"] = company
    if source and source != "All" and _has_field("Opportunity", "custom_source_channel"):
        filters["custom_source_channel"] = source
    if business_type and business_type != "All" and _has_field("Opportunity", "custom_crm_business_type"):
        filters["custom_crm_business_type"] = business_type
    if segment and segment != "All" and _has_field("Opportunity", "custom_crm_segment"):
        filters["custom_crm_segment"] = segment

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
    for custom_field in ["custom_source_channel", "custom_crm_business_type", "custom_crm_segment"]:
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
    assignment = _assignment_for_card("Opportunity", row.get("name"), stage, statuses)
    return {
        "name": row.get("name"),
        "title": row.get("title") or row.get("name"),
        "subtitle": row.get("customer_name") or row.get("party_name") or "",
        "amount": row.get("opportunity_amount") or 0,
        "company": row.get("company") or "",
        "business_type": row.get("custom_crm_business_type") or "",
        "crm_segment": row.get("custom_crm_segment") or "",
        "owner": row.get("opportunity_owner") or "",
        "assigned_user": assignment.get("user") or "",
        "assigned_user_label": assignment.get("label") or "",
        "assignment_source": assignment.get("source") or "",
        "source": row.get("custom_source_channel") or "",
        "stage": stage,
        "legacy_status": row.get("status") or "",
        "tags": [
            row.get("opportunity_from"),
            row.get("custom_crm_business_type"),
            row.get("custom_crm_segment"),
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
    for fieldname in ["project_owner", "custom_project_status", "custom_qc_status", "custom_crm_business_type", "custom_crm_segment", "custom_source_opportunity"]:
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
    crm_info = _project_crm_info(row)
    assignment = _assignment_for_card("Project", row.get("name"), stage, statuses)
    tags = []
    for tag in [crm_info.get("business_type") or "Installation", crm_info.get("crm_segment")]:
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
        "assigned_user": assignment.get("user") or "",
        "assigned_user_label": assignment.get("label") or "",
        "assignment_source": assignment.get("source") or "",
        "business_type": crm_info.get("business_type") or "Installation",
        "crm_segment": crm_info.get("crm_segment") or "",
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
    for fieldname in ["custom_orderlift_order_status", "custom_installation_project", "custom_crm_business_type", "custom_crm_segment", "custom_partner_campaign_target"]:
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
    crm_info = _sales_order_crm_info(row)
    business_type = crm_info.get("business_type") or _sales_order_business_type(row)
    crm_segment = crm_info.get("crm_segment") or ""
    assignment = _assignment_for_card("Sales Order", row.get("name"), stage, statuses)
    return {
        "name": row.get("name"),
        "title": _sales_order_title(row) or row.get("customer") or row.get("name"),
        "subtitle": row.get("company") or "",
        "amount": row.get("grand_total") or 0,
        "company": row.get("company") or "",
        "owner": row.get("owner") or "",
        "assigned_user": assignment.get("user") or "",
        "assigned_user_label": assignment.get("label") or "",
        "assignment_source": assignment.get("source") or "",
        "business_type": business_type,
        "crm_segment": crm_segment,
        "stage": stage,
        "delivered_pct": delivered_pct,
        "billed_pct": billed_pct,
        "legacy_status": row.get("status") or "",
        "tags": [tag for tag in [business_type, crm_segment] if tag],
        "metrics": [
            {"label": _("ERP Status"), "value": row.get("status") or "-"},
            {"label": _("Delivered"), "value": f"{delivered_pct:.0f}%"},
            {"label": _("Billed"), "value": f"{billed_pct:.0f}%"},
        ],
        "docs": docs,
    }


def _sales_order_title(row) -> str:
    project_name = row.get("custom_installation_project") or row.get("project")
    if not project_name:
        return ""
    return frappe.db.get_value("Project", project_name, "project_name") or ""


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


def _project_crm_info(row) -> dict:
    if row.get("custom_crm_business_type") or row.get("custom_crm_segment"):
        return {
            "business_type": row.get("custom_crm_business_type"),
            "crm_segment": row.get("custom_crm_segment"),
        }
    opportunity = row.get("custom_source_opportunity") or _project_source_opportunity(row.get("name"))
    if opportunity:
        return _opportunity_crm_info(opportunity)
    return {"business_type": "Installation", "crm_segment": None}


def _sales_order_crm_info(row) -> dict:
    if row.get("custom_crm_business_type") or row.get("custom_crm_segment"):
        return {
            "business_type": row.get("custom_crm_business_type"),
            "crm_segment": row.get("custom_crm_segment"),
        }
    target_row = row.get("custom_partner_campaign_target")
    if target_row and frappe.db.exists("DocType", "Partner Campaign Target"):
        campaign_info = frappe.db.get_value(
            "Partner Campaign Target",
            target_row,
            ["business_type", "crm_segment"],
            as_dict=True,
        )
        if campaign_info and (campaign_info.get("business_type") or campaign_info.get("crm_segment")):
            return {
                "business_type": campaign_info.get("business_type"),
                "crm_segment": campaign_info.get("crm_segment"),
            }
    opportunity = _sales_order_source_opportunity(row.get("name"))
    if opportunity:
        return _opportunity_crm_info(opportunity)
    project_name = row.get("custom_installation_project") or row.get("project")
    if project_name:
        project_opportunity = frappe.db.get_value("Project", project_name, "custom_source_opportunity") if _has_field("Project", "custom_source_opportunity") else None
        if project_opportunity:
            return _opportunity_crm_info(project_opportunity)
    return {"business_type": None, "crm_segment": None}


def _opportunity_crm_info(opportunity: str | None) -> dict:
    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        return {"business_type": None, "crm_segment": None}
    fields = []
    if _has_field("Opportunity", "custom_crm_business_type"):
        fields.append("custom_crm_business_type")
    if _has_field("Opportunity", "custom_crm_segment"):
        fields.append("custom_crm_segment")
    if not fields:
        return {"business_type": None, "crm_segment": None}
    values = frappe.db.get_value("Opportunity", opportunity, fields, as_dict=True) or {}
    return {
        "business_type": values.get("custom_crm_business_type"),
        "crm_segment": values.get("custom_crm_segment"),
    }


def _party_crm_segments(party_type: str, party_name: str) -> list[dict]:
    if party_type not in {"Lead", "Prospect", "Customer"} or not party_name:
        return []
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return []
    rows = frappe.get_all(
        "CRM Segment Assignment",
        filters={"parenttype": party_type, "parent": party_name},
        fields=["business_type", "segment", "is_primary"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )
    return [
        {
            "business_type": row.get("business_type") or "",
            "segment": row.get("segment") or "",
            "is_primary": cint(row.get("is_primary")),
        }
        for row in rows
        if row.get("business_type") or row.get("segment")
    ]


def _customer_for_opportunity_party(opportunity_doc):
    party_type = (opportunity_doc.get("opportunity_from") or "").strip()
    party_name = (opportunity_doc.get("party_name") or "").strip()
    if not party_type or not party_name:
        frappe.throw(_("Opportunity {0} does not have a party.").format(opportunity_doc.name))

    if party_type == "Customer":
        if not frappe.db.exists("Customer", party_name):
            frappe.throw(_("Customer {0} was not found.").format(party_name))
        customer = frappe.get_doc("Customer", party_name)
        _copy_party_segments_to_customer("Opportunity", opportunity_doc.name, customer)
        return customer

    if party_type not in {"Lead", "Prospect"}:
        frappe.throw(_("Quotation from Opportunity is supported for Lead, Prospect, or Customer parties."))
    if not frappe.db.exists(party_type, party_name):
        frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))

    source = frappe.get_doc(party_type, party_name)
    customer_name = _customer_name_for_party(source, party_type, opportunity_doc)
    customer = _existing_customer_for_party(source, party_type, customer_name)
    if customer:
        customer_doc = frappe.get_doc("Customer", customer)
        _copy_party_segments_to_customer(party_type, party_name, customer_doc)
        _copy_party_segments_to_customer("Opportunity", opportunity_doc.name, customer_doc)
        return customer_doc

    customer_doc = frappe.new_doc("Customer")
    customer_doc.customer_name = customer_name
    customer_doc.customer_type = "Company" if party_type == "Prospect" or source.get("company_name") else "Individual"
    customer_doc.customer_group = _default_customer_group()
    if source.get("territory"):
        customer_doc.territory = source.get("territory")
    if source.get("company") and customer_doc.meta.get_field("represents_company"):
        customer_doc.represents_company = source.get("company")
    if source.get("lead_owner") and customer_doc.meta.get_field("account_manager"):
        customer_doc.account_manager = source.get("lead_owner")
    if source.get("prospect_owner") and customer_doc.meta.get_field("account_manager"):
        customer_doc.account_manager = source.get("prospect_owner")

    _copy_party_segments_to_customer(party_type, party_name, customer_doc)
    _copy_party_segments_to_customer("Opportunity", opportunity_doc.name, customer_doc)
    customer_doc.insert(ignore_permissions=False)
    customer_doc._orderlift_created = True

    if party_type == "Lead" and source.meta.get_field("customer"):
        frappe.db.set_value("Lead", source.name, "customer", customer_doc.name, update_modified=False)
    frappe.db.commit()
    return customer_doc


def _customer_name_for_party(source_doc, party_type: str, opportunity_doc) -> str:
    if party_type == "Lead":
        return source_doc.get("company_name") or source_doc.get("lead_name") or opportunity_doc.get("customer_name") or source_doc.name
    return source_doc.get("company_name") or opportunity_doc.get("customer_name") or source_doc.name


def _party_display_name(doc, party_type: str) -> str:
    if party_type == "Customer":
        return doc.get("customer_name") or doc.name
    if party_type == "Lead":
        return doc.get("lead_name") or doc.get("company_name") or doc.name
    return doc.get("company_name") or doc.name


def _primary_contact_for_party(party_type: str, party_name: str) -> dict:
    if not frappe.db.exists("DocType", "Dynamic Link") or not frappe.db.exists("DocType", "Contact"):
        return {}
    link = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": party_type, "link_name": party_name, "parenttype": "Contact"},
        fields=["parent"],
        order_by="idx asc, modified desc",
        limit=1,
    )
    if not link:
        return {}
    fields = [field for field in ["email_id", "mobile_no", "phone"] if _has_field("Contact", field)]
    if not fields:
        return {}
    return frappe.db.get_value("Contact", link[0].parent, fields, as_dict=True) or {}


def _resolve_draft_company(company: str | None = None) -> str:
    requested = (company or "").strip() or DEFAULT_DRAFT_COMPANY
    if requested and frappe.db.exists("Company", requested) and user_can_access_company(requested):
        return requested
    return _resolve_pipeline_company(None)


def _ensure_draft_prospect(company: str, business_type: str, segment: str) -> str:
    existing = frappe.db.exists("Prospect", DEFAULT_DRAFT_PROSPECT) or frappe.db.get_value(
        "Prospect",
        {"company_name": DEFAULT_DRAFT_PROSPECT},
        "name",
    )
    if existing:
        _ensure_party_segment("Prospect", existing, business_type, segment)
        return existing

    prospect = frappe.new_doc("Prospect")
    prospect.company_name = DEFAULT_DRAFT_PROSPECT
    if prospect.meta.get_field("company"):
        prospect.company = company
    if prospect.meta.get_field("customer_group"):
        prospect.customer_group = _default_customer_group()
    if prospect.meta.get_field("territory") and frappe.db.exists("Territory", "Morocco"):
        prospect.territory = "Morocco"
    if prospect.meta.get_field("enable_dynamic_segmentation"):
        prospect.enable_dynamic_segmentation = 0
    _append_party_segment(prospect, business_type, segment)
    prospect.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    return prospect.name


def _create_preform_prospect(
    client_name: str,
    company: str,
    business_type: str,
    segment: str,
    phone: str,
    tier: str,
    territory: str,
) -> str:
    existing = frappe.db.get_value("Prospect", {"company_name": client_name}, "name") if client_name else None
    if existing:
        _ensure_party_segment("Prospect", existing, business_type, segment)
        return existing
    prospect = frappe.new_doc("Prospect")
    prospect.company_name = client_name
    _set_if_field(prospect, "company", company)
    _set_if_field(prospect, "phone", phone)
    _set_if_field(prospect, "mobile_no", phone)
    _set_if_field(prospect, "territory", territory)
    if prospect.meta.get_field("customer_group"):
        prospect.customer_group = _default_customer_group()
    if prospect.meta.get_field("enable_dynamic_segmentation"):
        prospect.enable_dynamic_segmentation = 0
    if tier and prospect.meta.get_field("manual_tier"):
        prospect.manual_tier = tier
    _append_party_segment(prospect, business_type, segment)
    prospect.insert(ignore_permissions=True, ignore_mandatory=True)
    return prospect.name


def _create_preform_party(
    party_type: str,
    client_name: str,
    company: str,
    business_type: str,
    segment: str,
    phone: str,
    tier: str,
    territory: str,
) -> str:
    if party_type == "Customer":
        return _create_preform_customer(client_name, company, business_type, segment, phone, tier, territory)
    return _create_preform_prospect(client_name, company, business_type, segment, phone, tier, territory)


def _create_preform_customer(
    client_name: str,
    company: str,
    business_type: str,
    segment: str,
    phone: str,
    tier: str,
    territory: str,
) -> str:
    existing = frappe.db.get_value("Customer", {"customer_name": client_name}, "name") if client_name else None
    if existing:
        _ensure_party_segment("Customer", existing, business_type, segment)
        return existing
    customer = frappe.new_doc("Customer")
    customer.customer_name = client_name
    customer.customer_type = "Individual"
    customer.customer_group = _default_customer_group()
    _set_if_field(customer, "company", company)
    _set_if_field(customer, "mobile_no", phone)
    _set_if_field(customer, "phone", phone)
    _set_if_field(customer, "territory", territory or _default_territory())
    if customer.meta.get_field("enable_dynamic_segmentation"):
        customer.enable_dynamic_segmentation = 0
    if tier and customer.meta.get_field("manual_tier"):
        customer.manual_tier = tier
    _append_party_segment(customer, business_type, segment)
    customer.insert(ignore_permissions=True, ignore_mandatory=True)
    return customer.name


def _assign_preform_opportunity_name(doc) -> str:
    from orderlift.orderlift_crm.opportunity_hooks import assign_opportunity_name

    assign_opportunity_name(doc)
    return doc.name or ""


def _rename_preform_opportunity_if_needed(doc, desired_name: str) -> None:
    desired_name = (desired_name or "").strip()
    if not desired_name or doc.name == desired_name:
        return
    frappe.rename_doc("Opportunity", doc.name, desired_name, force=True, merge=False)
    doc.name = desired_name


def _default_territory() -> str:
    if frappe.db.exists("Territory", "Morocco"):
        return "Morocco"
    return frappe.db.get_value("Territory", {}, "name") or ""


def _tier_for_party(party_type: str, party_name: str) -> str:
    if party_type not in {"Customer", "Prospect"} or not party_name or not frappe.db.exists(party_type, party_name):
        return ""
    fields = [field for field in ["manual_tier", "tier"] if _has_field(party_type, field)]
    if not fields:
        return ""
    values = frappe.db.get_value(party_type, party_name, fields, as_dict=True) or {}
    return values.get("manual_tier") or values.get("tier") or ""


def _set_if_field(doc, fieldname: str, value) -> None:
    if doc.meta.get_field(fieldname) and value not in (None, ""):
        doc.set(fieldname, value)


def _add_preform_comment(opportunity: str, comment: str) -> None:
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": "Opportunity",
            "reference_name": opportunity,
            "content": frappe.utils.escape_html(comment),
        }
    ).insert(ignore_permissions=True)


def _attach_preform_file(opportunity: str, file_url: str) -> None:
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_name:
        return
    file_doc = frappe.get_doc("File", file_name)
    file_doc.attached_to_doctype = "Opportunity"
    file_doc.attached_to_name = opportunity
    file_doc.save(ignore_permissions=True)


def _ensure_party_segment(party_type: str, party_name: str, business_type: str, segment: str) -> None:
    if not (business_type and segment):
        return
    if not frappe.db.exists(party_type, party_name):
        return
    doc = frappe.get_doc(party_type, party_name)
    before = len(doc.get("custom_crm_segments") or [])
    _append_party_segment(doc, business_type, segment)
    if len(doc.get("custom_crm_segments") or []) != before:
        doc.save(ignore_permissions=True)
        frappe.db.commit()


def _append_party_segment(doc, business_type: str, segment: str) -> None:
    if not doc.meta.get_field("custom_crm_segments") or not (business_type and segment):
        return
    existing = {(row.get("business_type"), row.get("segment")) for row in doc.get("custom_crm_segments") or []}
    key = (business_type, segment)
    if key in existing:
        return
    doc.append(
        "custom_crm_segments",
        {
            "business_type": business_type,
            "segment": segment,
            "is_primary": 0 if existing else 1,
        },
    )


def _default_naming_series(doctype: str) -> str:
    meta = frappe.get_meta(doctype)
    field = meta.get_field("naming_series")
    options = [row.strip() for row in (field.options or "").split("\n") if row.strip()] if field else []
    return options[0] if options else ""


def _default_opportunity_type() -> str:
    if frappe.db.exists("Opportunity Type", "Sales"):
        return "Sales"
    return frappe.db.get_value("Opportunity Type", {}, "name") or "Sales"


def _existing_customer_for_party(source_doc, party_type: str, customer_name: str) -> str | None:
    if party_type == "Lead" and source_doc.meta.get_field("customer") and source_doc.get("customer"):
        if frappe.db.exists("Customer", source_doc.get("customer")):
            return source_doc.get("customer")
    if frappe.db.exists("Customer", customer_name):
        return customer_name
    return frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")


def _copy_party_segments_to_customer(source_type: str, source_name: str, customer_doc) -> None:
    if not customer_doc.meta.get_field("custom_crm_segments"):
        return
    rows = []
    if source_type in {"Lead", "Prospect", "Customer"}:
        rows = _party_crm_segments(source_type, source_name)
    elif source_type == "Opportunity":
        info = _opportunity_crm_info(source_name)
        if info.get("business_type") or info.get("crm_segment"):
            rows = [{"business_type": info.get("business_type") or "", "segment": info.get("crm_segment") or "", "is_primary": 1}]
    if not rows:
        return

    existing = {(row.get("business_type"), row.get("segment")) for row in customer_doc.get("custom_crm_segments") or []}
    changed = False
    for row in rows:
        key = (row.get("business_type") or "", row.get("segment") or "")
        if not all(key) or key in existing:
            continue
        customer_doc.append(
            "custom_crm_segments",
            {
                "business_type": key[0],
                "segment": key[1],
                "is_primary": 0 if existing else cint(row.get("is_primary")) or 1,
            },
        )
        existing.add(key)
        changed = True
    if changed and not customer_doc.is_new():
        customer_doc.save(ignore_permissions=False)


def _default_customer_group() -> str:
    if frappe.db.exists("Customer Group", "All Customer Groups") and not cint(
        frappe.db.get_value("Customer Group", "All Customer Groups", "is_group")
    ):
        return "All Customer Groups"
    leaf_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    if leaf_group:
        return leaf_group
    return frappe.db.get_value("Customer Group", {}, "name") or "All Customer Groups"


def _project_source_opportunity(project: str | None) -> str | None:
    if not project or not frappe.db.exists("DocType", "Sales Order"):
        return None
    rows = frappe.db.sql(
        """
        SELECT q.opportunity
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        INNER JOIN `tabQuotation` q ON q.name = soi.prevdoc_docname
        WHERE so.docstatus < 2
          AND (so.project = %s OR so.custom_installation_project = %s)
          AND COALESCE(q.opportunity, '') != ''
        ORDER BY so.modified DESC
        LIMIT 1
        """,
        (project, project),
        as_dict=True,
    )
    return rows[0].opportunity if rows else None


def _sales_order_source_opportunity(sales_order: str | None) -> str | None:
    if not sales_order or not frappe.db.exists("DocType", "Quotation"):
        return None
    rows = frappe.db.sql(
        """
        SELECT q.opportunity
        FROM `tabSales Order Item` soi
        INNER JOIN `tabQuotation` q ON q.name = soi.prevdoc_docname
        WHERE soi.parent = %s
          AND COALESCE(q.opportunity, '') != ''
        ORDER BY soi.idx ASC
        LIMIT 1
        """,
        (sales_order,),
        as_dict=True,
    )
    return rows[0].opportunity if rows else None


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
                "assigned_user": status.get("assigned_user") or "",
                "auto_collapse": cint(status.get("auto_collapse")),
                "confirmation_message": status.get("confirmation_message") or "",
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
    statuses = {
        status["name"]: status
        for status in list_editable_statuses(document_type, include_inactive=False, company=doc.get("company"))
    }
    status = statuses.get(stage)
    if not status:
        frappe.throw(_("Status {0} is not active for {1}.").format(stage, document_type))
    business_type = _document_business_type(document_type, doc)
    if business_type == "Distribution" and not status.get("applies_distribution"):
        frappe.throw(_("Status {0} does not apply to Distribution {1} records.").format(stage, document_type))
    if business_type == "Installation" and not status.get("applies_installation"):
        frappe.throw(_("Status {0} does not apply to Installation {1} records.").format(stage, document_type))
    validate_status_checks(document_type, doc, status)
    return status


def sync_pipeline_status_assignment(document_type: str, document_name: str, status_info: dict | None, stage: str | None = None) -> dict:
    _clear_pipeline_assignment_todos(document_type, document_name)
    status_info = status_info or {}
    return _assign_pipeline_document(
        document_type,
        document_name,
        status_info.get("assigned_user"),
        stage,
        priority=status_info.get("todo_priority"),
    )


def _assign_pipeline_document(
    document_type: str,
    document_name: str,
    user: str | None,
    stage: str | None = None,
    priority: str | None = None,
) -> dict:
    user = (user or "").strip()
    if not user:
        return {}
    _validate_enabled_user(user)
    company = frappe.db.get_value(document_type, document_name, "company") if _has_field(document_type, "company") else ""
    if company and not user_can_access_company(company, user=user):
        frappe.throw(_("User {0} cannot access company {1}.").format(user, company))

    description = _assignment_description(document_type, document_name, stage)
    todo_priority = normalize_todo_priority(priority)
    existing = _find_open_pipeline_todo(document_type, document_name, user)
    if existing:
        todo = frappe.get_doc("ToDo", existing.name)
        todo.description = description
        todo.status = "Open"
        todo.priority = todo_priority
        todo.date = nowdate()
        todo.save(ignore_permissions=True)
        todo_name = todo.name
    else:
        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "reference_type": document_type,
                "reference_name": document_name,
                "description": description,
                "status": "Open",
                "priority": todo_priority,
                "date": nowdate(),
            }
        ).insert(ignore_permissions=True)
        todo_name = todo.name

    _close_other_pipeline_assignment_todos(document_type, document_name, user)
    return _assignment_payload(user, source="todo", todo_name=todo_name)


def _assignment_for_card(document_type: str, document_name: str | None, stage: str | None, statuses: list[dict]) -> dict:
    if not document_name:
        return _assignment_payload("")
    todo = _find_open_pipeline_todo(document_type, document_name)
    if todo and todo.get("allocated_to"):
        return _assignment_payload(todo.get("allocated_to"), source="todo", todo_name=todo.get("name"))
    return _assignment_payload("")


def _find_open_pipeline_todo(document_type: str, document_name: str, user: str | None = None):
    filters = {
        "reference_type": document_type,
        "reference_name": document_name,
        "status": "Open",
    }
    if user:
        filters["allocated_to"] = user
    rows = frappe.get_all(
        "ToDo",
        filters=filters,
        fields=["name", "allocated_to", "description"],
        order_by="modified desc",
        limit_page_length=10,
    )
    for row in rows:
        if PIPELINE_ASSIGNMENT_MARKER in (row.get("description") or ""):
            return row
    return None


def _close_other_pipeline_assignment_todos(document_type: str, document_name: str, keep_user: str) -> None:
    rows = frappe.get_all(
        "ToDo",
        filters={"reference_type": document_type, "reference_name": document_name, "status": "Open"},
        fields=["name", "allocated_to", "description"],
        limit_page_length=0,
    )
    for row in rows:
        if row.get("allocated_to") == keep_user:
            continue
        if PIPELINE_ASSIGNMENT_MARKER not in (row.get("description") or ""):
            continue
        frappe.db.set_value("ToDo", row.name, "status", "Closed", update_modified=True)


def _clear_pipeline_assignment_todos(document_type: str, document_name: str) -> None:
    rows = frappe.get_all(
        "ToDo",
        filters={"reference_type": document_type, "reference_name": document_name, "status": "Open"},
        fields=["name", "description"],
        limit_page_length=0,
    )
    for row in rows:
        if PIPELINE_ASSIGNMENT_MARKER not in (row.get("description") or ""):
            continue
        frappe.db.set_value("ToDo", row.name, "status", "Closed", update_modified=True)


def _assignment_description(document_type: str, document_name: str, stage: str | None = None) -> str:
    if stage:
        return f"{PIPELINE_ASSIGNMENT_MARKER} {document_type} {document_name} moved to {stage}."
    return f"{PIPELINE_ASSIGNMENT_MARKER} Follow up {document_type} {document_name}."


def _assignment_payload(user: str | None, source: str = "", todo_name: str | None = None) -> dict:
    user = (user or "").strip()
    if not user:
        return {"user": "", "label": "", "source": "", "todo": ""}
    return {
        "user": user,
        "label": _user_label(user),
        "source": source,
        "todo": todo_name or "",
    }


def _validate_enabled_user(user: str) -> None:
    if not frappe.db.exists("User", user):
        frappe.throw(_("User {0} was not found.").format(user))
    if not cint(frappe.db.get_value("User", user, "enabled")):
        frappe.throw(_("User {0} is disabled.").format(user))


def _user_label(user: str) -> str:
    return frappe.db.get_value("User", user, "full_name") or user


def _current_pipeline_stage(document_type: str, doc) -> str | None:
    if document_type == "Opportunity":
        return doc.get("sales_stage")
    if document_type == "Project":
        return doc.get("custom_project_status")
    if document_type == "Sales Order":
        return doc.get("custom_orderlift_order_status")
    return None


def _card_for_document(document_type: str, document_name: str) -> dict:
    doc = frappe.get_doc(document_type, document_name)
    statuses = list_editable_statuses(document_type, include_inactive=False, company=doc.get("company"))
    if document_type == "Opportunity":
        return _opportunity_card(doc.as_dict(), statuses)
    if document_type == "Project":
        return _project_card(doc.as_dict(), statuses)
    if document_type == "Sales Order":
        return _sales_order_card(doc.as_dict(), statuses)
    frappe.throw(_("Unsupported pipeline document type: {0}").format(document_type))


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


def _resolve_pipeline_company(company: str | None = None) -> str:
    company = (company or "").strip()
    payload = get_company_access_payload(requested_company=company if company != "All" else None)
    allowed = payload.get("companies") or []
    if company and company != "All":
        return company
    current_company = payload.get("current_company") or ""
    if current_company:
        return current_company
    frappe.throw(_("No company is available for your user."))


def _allowed_pipeline_companies() -> list[str]:
    return get_company_access_payload().get("companies") or []


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
