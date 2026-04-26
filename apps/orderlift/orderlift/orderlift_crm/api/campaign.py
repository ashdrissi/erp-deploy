from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate, today

from orderlift.orderlift_crm.status_workflow import get_default_status_name
from orderlift.orderlift_crm.doctype.partner_campaign.partner_campaign import (
    get_default_target_status,
    resolve_party_snapshot,
    validate_target_status,
)


@frappe.whitelist()
def get_manager_data(campaign: str | None = None) -> dict:
    selected_campaign = campaign or _latest_campaign_name()
    return {
        "kpis": _global_campaign_kpis(),
        "campaigns": _campaign_rows(),
        "selected_campaign": selected_campaign,
        "targets": _campaign_targets(selected_campaign) if selected_campaign else [],
        "statuses": get_target_statuses(),
        "segments": get_partner_segments(),
    }


@frappe.whitelist()
def get_editor_data(campaign: str | None = None) -> dict:
    doc = _campaign_doc_dict(campaign) if campaign else _new_campaign_defaults()
    article_page = get_article_candidate_page(
        from_date=doc.get("sales_history_from_date"),
        to_date=doc.get("sales_history_to_date"),
        price_list=doc.get("price_list_filter"),
        item_group=doc.get("item_group_filter"),
        container=doc.get("container_filter"),
        supplier_payment_mode=doc.get("supplier_payment_mode_filter"),
        limit=80,
    )
    target_page = get_target_candidate_page(limit=80)
    return {
        "campaign": doc,
        "statuses": get_target_statuses(),
        "business_types": get_business_types(),
        "segments": get_partner_segments(),
        "filter_options": {
            "price_lists": _price_list_options(),
            "item_groups": _item_group_options(),
            "containers": _container_options(),
        },
        "articles": _merge_selected_items(article_page.get("rows") or [], doc.get("items") or []),
        "targets": _merge_selected_targets(target_page.get("rows") or [], doc.get("targets") or []),
        "article_paging": article_page,
        "target_paging": target_page,
    }


@frappe.whitelist()
def get_article_candidate_page(
    from_date: str | None = None,
    to_date: str | None = None,
    price_list: str | None = None,
    item_group: str | None = None,
    container: str | None = None,
    supplier_payment_mode: str | None = None,
    search: str | None = None,
    limit: int = 20,
    start: int = 0,
) -> dict:
    limit = min(max(cint(limit) or 20, 1), 200)
    start = max(cint(start), 0)
    rows = get_article_candidates(
        from_date=from_date,
        to_date=to_date,
        price_list=price_list,
        item_group=item_group,
        container=container,
        supplier_payment_mode=supplier_payment_mode,
        search=search,
        limit=limit + 1,
        start=start,
    )
    return {"rows": rows[:limit], "start": start, "limit": limit, "has_more": len(rows) > limit}


@frappe.whitelist()
def get_target_candidate_page(
    party_type: str | None = None,
    business_type: str | None = None,
    segment: str | None = None,
    search: str | None = None,
    limit: int = 20,
    start: int = 0,
) -> dict:
    limit = min(max(cint(limit) or 20, 1), 200)
    start = max(cint(start), 0)
    rows = get_target_candidates(
        party_type=party_type,
        business_type=business_type,
        segment=segment,
        search=search,
        limit=limit + 1,
        start=start,
    )
    return {"rows": rows[:limit], "start": start, "limit": limit, "has_more": len(rows) > limit}


@frappe.whitelist()
def save_campaign(payload: str | dict) -> dict:
    data = _loads(payload)
    name = data.get("name")
    doc = frappe.get_doc("Partner Campaign", name) if name else frappe.new_doc("Partner Campaign")

    for fieldname in [
        "campaign_name",
        "status",
        "campaign_owner",
        "default_channel",
        "campaign_date",
        "start_date",
        "end_date",
        "target_family",
        "business_type_filter",
        "crm_segment_filter",
        "partner_segment_filter",
        "description",
        "sales_history_from_date",
        "sales_history_to_date",
        "price_list_filter",
        "item_group_filter",
        "container_filter",
        "supplier_payment_mode_filter",
        "email_subject",
        "email_mode",
        "email_body",
        "whatsapp_text",
        "call_script",
    ]:
        if fieldname in data:
            setattr(doc, fieldname, data.get(fieldname))

    doc.set("items", [])
    for row in data.get("items") or []:
        if row.get("selected") is False:
            continue
        doc.append("items", _campaign_item_payload(row))

    doc.set("targets", [])
    for row in data.get("targets") or []:
        if row.get("selected") is False:
            continue
        doc.append("targets", _campaign_target_payload(row))

    _validate_campaign_ready_state(doc)
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return {"name": doc.name, "campaign": _campaign_doc_dict(doc.name)}


@frappe.whitelist()
def update_target_status(campaign: str, target_row: str, status: str) -> dict:
    doc = frappe.get_doc("Partner Campaign", campaign)
    status = validate_target_status(status)
    row = _find_target_row(doc, target_row)
    row.target_status = status
    row.last_contact_date = nowdate()
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Target Status Changed", f"{row.display_name or row.party_name}: {status}")
    return _target_row_dict(row)


@frappe.whitelist()
def create_prospect_from_target(campaign: str, target_row: str) -> dict:
    doc = frappe.get_doc("Partner Campaign", campaign)
    row = _find_target_row(doc, target_row)
    if row.prospect:
        return {"name": row.prospect}
    if row.party_type != "Lead":
        frappe.throw(_("Prospect can only be created directly from a Lead target."))

    lead = frappe.get_doc("Lead", row.party_name)
    prospect = frappe.new_doc("Prospect")
    prospect.company_name = lead.company_name or lead.lead_name or lead.name
    prospect.prospect_owner = lead.lead_owner or frappe.session.user
    prospect.company = lead.company
    prospect.territory = lead.territory
    _copy_party_segments(lead, prospect)
    _ensure_doc_segment(prospect, row.business_type, row.crm_segment)
    prospect.append(
        "leads",
        {
            "lead": lead.name,
            "lead_name": lead.lead_name,
            "email": lead.email_id,
            "mobile_no": lead.mobile_no,
            "lead_owner": lead.lead_owner,
            "status": lead.status,
        },
    )
    prospect.insert(ignore_permissions=False)

    doc, row = _reload_campaign_target(campaign, target_row)
    row.prospect = prospect.name
    row.target_status = _status_if_exists("Prospect Created") or row.target_status
    _set_last_campaign_on_party(row, doc.name)
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Prospect Created", f"{prospect.name} from {row.party_type} {row.party_name}")
    return {"name": prospect.name}


@frappe.whitelist()
def create_opportunity_from_target(campaign: str, target_row: str) -> dict:
    doc = frappe.get_doc("Partner Campaign", campaign)
    row = _find_target_row(doc, target_row)
    if row.opportunity:
        return {"name": row.opportunity}

    opportunity = frappe.new_doc("Opportunity")
    opportunity.opportunity_from = row.party_type
    opportunity.party_name = row.party_name
    opportunity.customer_name = row.display_name
    opportunity.opportunity_owner = row.assigned_to or doc.campaign_owner or frappe.session.user
    opportunity.transaction_date = today()
    opportunity.status = "Open"
    opportunity.opportunity_type = _default_opportunity_type()
    opportunity.opportunity_amount = _campaign_offer_amount(doc)
    opportunity.probability = 20
    opportunity.title = doc.campaign_name
    _set_if_field(opportunity, "custom_partner_campaign", doc.name)
    _set_if_field(opportunity, "custom_partner_campaign_target", row.name)
    _set_if_field(opportunity, "custom_crm_business_type", row.business_type)
    _set_if_field(opportunity, "custom_crm_segment", row.crm_segment)
    _set_if_field(opportunity, "custom_partner_segment", row.partner_segment)
    _set_if_field(opportunity, "sales_stage", get_default_status_name("Opportunity"))
    _set_if_field(opportunity, "custom_source_channel", doc.default_channel)
    _append_opportunity_items(opportunity, doc)
    opportunity.insert(ignore_permissions=False)

    doc, row = _reload_campaign_target(campaign, target_row)
    row.opportunity = opportunity.name
    row.target_status = _status_if_exists("Opportunity Created") or row.target_status
    _set_last_campaign_on_party(row, doc.name)
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Opportunity Created", f"{opportunity.name} from {row.party_type} {row.party_name}")
    return {"name": opportunity.name}


@frappe.whitelist()
def create_quotation_from_target(campaign: str, target_row: str) -> dict:
    doc = frappe.get_doc("Partner Campaign", campaign)
    row = _find_target_row(doc, target_row)
    if row.quotation:
        return {"name": row.quotation}

    quotation = frappe.new_doc("Quotation")
    quotation.company = _default_company()
    quotation.quotation_to = row.party_type
    quotation.party_name = row.party_name
    quotation.customer_name = row.display_name
    quotation.transaction_date = today()
    quotation.order_type = "Sales"
    if row.opportunity:
        quotation.opportunity = row.opportunity
    _set_if_field(quotation, "custom_partner_campaign", doc.name)
    _set_if_field(quotation, "custom_partner_campaign_target", row.name)
    _append_quotation_items(quotation, doc)
    quotation.insert(ignore_permissions=False)

    doc, row = _reload_campaign_target(campaign, target_row)
    row.quotation = quotation.name
    row.target_status = _status_if_exists("Quotation Created") or row.target_status
    _set_last_campaign_on_party(row, doc.name)
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Quotation Created", f"{quotation.name} from {row.party_type} {row.party_name}")
    return {"name": quotation.name}


@frappe.whitelist()
def get_article_candidates(
    from_date: str | None = None,
    to_date: str | None = None,
    price_list: str | None = None,
    item_group: str | None = None,
    container: str | None = None,
    supplier_payment_mode: str | None = None,
    search: str | None = None,
    limit: int = 80,
    start: int = 0,
) -> list[dict]:
    item_codes = _container_item_codes(container)
    price_list_item_codes = _price_list_item_codes(price_list, supplier_payment_mode=supplier_payment_mode)
    filters: dict[str, Any] = {"disabled": 0}
    if item_codes:
        filters["name"] = ["in", item_codes]
    if price_list_item_codes:
        existing = filters.get("name")
        if existing and isinstance(existing, list) and existing[0] == "in":
            filters["name"] = ["in", [code for code in existing[1] if code in set(price_list_item_codes)]]
        else:
            filters["name"] = ["in", price_list_item_codes]
    if item_group:
        filters["item_group"] = item_group
    or_filters = None
    if search:
        like = f"%{search}%"
        or_filters = [["Item", "name", "like", like], ["Item", "item_name", "like", like], ["Item", "item_group", "like", like]]

    items = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "item_name", "stock_uom", "item_group"],
        order_by="modified desc",
        limit_page_length=limit,
        limit_start=int(start or 0),
    )
    return [
        _article_candidate(
            row,
            from_date=from_date,
            to_date=to_date,
            price_list=price_list,
            container=container,
            supplier_payment_mode=supplier_payment_mode,
        )
        for row in items
    ]


@frappe.whitelist()
def get_target_candidates(
    party_type: str | None = None,
    business_type: str | None = None,
    segment: str | None = None,
    search: str | None = None,
    limit: int = 80,
    start: int = 0,
) -> list[dict]:
    parties = [party_type] if party_type in {"Lead", "Prospect", "Customer"} else ["Lead", "Prospect", "Customer"]
    rows = []
    for current_type in parties:
        rows.extend(
            _target_candidates_for_type(
                current_type,
                business_type=business_type,
                segment=segment,
                search=search,
                limit=limit,
            )
        )
    start = int(start or 0)
    limit = int(limit or 80)
    return rows[start : start + limit]


@frappe.whitelist()
def get_target_statuses() -> list[dict]:
    if not frappe.db.exists("DocType", "Partner Campaign Status"):
        return []
    return frappe.get_all(
        "Partner Campaign Status",
        filters={"is_active": 1},
        fields=["name", "status_label", "sequence", "color", "is_default"],
        order_by="sequence asc, status_label asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_partner_segments() -> list[dict]:
    if not frappe.db.exists("DocType", "CRM Segment"):
        return []
    return frappe.get_all(
        "CRM Segment",
        filters={"is_active": 1},
        fields=["name", "segment_name", "business_type", "sequence"],
        order_by="sequence asc, segment_name asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_business_types() -> list[dict]:
    if not frappe.db.exists("DocType", "CRM Business Type"):
        return []
    return frappe.get_all(
        "CRM Business Type",
        filters={"is_active": 1},
        fields=["name", "type_name", "sequence"],
        order_by="sequence asc, type_name asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_party_campaign_history(party_type: str, party_name: str) -> list[dict]:
    if party_type not in {"Lead", "Prospect", "Customer"} or not party_name:
        return []
    if not frappe.db.exists("DocType", "Partner Campaign Target"):
        return []

    extra_condition = ""
    values: list[Any] = [party_type, party_name]
    if party_type == "Prospect":
        extra_condition = " OR pct.prospect = %s"
        values.append(party_name)
    rows = frappe.db.sql(
        f"""
        SELECT
            pct.name,
            pct.parent AS campaign,
            pc.campaign_name,
            pc.status AS campaign_status,
            pc.campaign_date,
            pct.business_type,
            pct.crm_segment,
            pct.target_status,
            pct.assigned_to,
            pct.last_contact_date,
            pct.opportunity,
            pct.quotation,
            pct.sales_order
        FROM `tabPartner Campaign Target` pct
        INNER JOIN `tabPartner Campaign` pc ON pc.name = pct.parent
        WHERE (pct.party_type = %s AND pct.party_name = %s){extra_condition}
        ORDER BY COALESCE(pc.campaign_date, pc.modified) DESC, pct.idx ASC
        LIMIT 50
        """,
        values,
        as_dict=True,
    )
    return [_history_row(row) for row in rows]


@frappe.whitelist()
def get_article_filter_options() -> dict:
    return {
        "price_lists": _price_list_options(),
        "item_groups": _item_group_options(),
        "containers": _container_options(),
    }


def sync_doc_campaign_rollup(doc, method=None):
    campaign = doc.get("custom_partner_campaign")
    if not campaign or not frappe.db.exists("Partner Campaign", campaign):
        return
    campaign_doc = frappe.get_doc("Partner Campaign", campaign)
    _link_doc_to_campaign_target(campaign_doc, doc)
    campaign_doc.save(ignore_permissions=True)


def inherit_campaign_from_links(doc, method=None):
    """Copy campaign context from upstream Opportunity/Quotation when ERPNext creates downstream docs."""
    if doc.get("custom_partner_campaign"):
        return

    context = {}
    if doc.doctype == "Quotation" and doc.get("opportunity"):
        context = frappe.db.get_value(
            "Opportunity",
            doc.opportunity,
            ["custom_partner_campaign", "custom_partner_campaign_target"],
            as_dict=True,
        ) or {}
    elif doc.doctype == "Sales Order":
        quotation_names = [row.prevdoc_docname for row in doc.get("items", []) if row.prevdoc_doctype == "Quotation" and row.prevdoc_docname]
        if quotation_names:
            context = frappe.db.get_value(
                "Quotation",
                quotation_names[0],
                ["custom_partner_campaign", "custom_partner_campaign_target"],
                as_dict=True,
            ) or {}

    if context.get("custom_partner_campaign") and doc.meta.get_field("custom_partner_campaign"):
        doc.custom_partner_campaign = context.get("custom_partner_campaign")
    if context.get("custom_partner_campaign_target") and doc.meta.get_field("custom_partner_campaign_target"):
        doc.custom_partner_campaign_target = context.get("custom_partner_campaign_target")


def _campaign_rows() -> list[dict]:
    if not frappe.db.exists("DocType", "Partner Campaign"):
        return []
    rows = frappe.get_all(
        "Partner Campaign",
        fields=[
            "name",
            "campaign_name",
            "status",
            "campaign_owner",
            "default_channel",
            "start_date",
            "end_date",
            "opportunity_count",
            "quotation_count",
            "quotation_amount",
            "sales_order_count",
            "sales_order_amount",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=50,
    )
    target_counts = _campaign_target_counts([row.name for row in rows])
    for row in rows:
        row["target_count"] = target_counts.get(row.name, 0)
    return rows


def _campaign_target_counts(campaigns: list[str]) -> dict[str, int]:
    if not campaigns:
        return {}
    rows = frappe.get_all(
        "Partner Campaign Target",
        filters={"parent": ["in", campaigns]},
        fields=["parent"],
        limit_page_length=0,
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.parent] = counts.get(row.parent, 0) + 1
    return counts


def _campaign_targets(campaign: str) -> list[dict]:
    doc = frappe.get_doc("Partner Campaign", campaign)
    return [_target_row_dict(row) for row in doc.targets or []]


def _target_row_dict(row) -> dict:
    return {
        "name": row.name,
        "party_type": row.party_type,
        "party_name": row.party_name,
        "display_name": row.display_name or row.party_name,
        "business_type": row.business_type,
        "crm_segment": row.crm_segment,
        "partner_segment": row.crm_segment or row.partner_segment,
        "city": row.city,
        "contact": row.contact,
        "contact_person_name": row.contact_person_name,
        "target_status": row.target_status,
        "assigned_to": row.assigned_to,
        "last_contact_date": row.last_contact_date,
        "prospect": row.prospect,
        "opportunity": row.opportunity,
        "quotation": row.quotation,
        "sales_order": row.sales_order,
        "last_order_date": row.last_order_date,
    }


def _campaign_doc_dict(campaign: str) -> dict:
    doc = frappe.get_doc("Partner Campaign", campaign)
    data = doc.as_dict()
    data["items"] = [row.as_dict() for row in doc.items or []]
    data["targets"] = [_target_row_dict(row) for row in doc.targets or []]
    return data


def _new_campaign_defaults() -> dict:
    return {
        "campaign_name": "",
        "status": "Draft",
        "campaign_owner": frappe.session.user,
        "default_channel": "WhatsApp",
        "campaign_date": today(),
        "sales_history_from_date": today(),
        "sales_history_to_date": today(),
        "email_mode": "HTML",
        "items": [],
        "targets": [],
    }


def _global_campaign_kpis() -> dict:
    campaigns = _campaign_rows()
    return {
        "campaign_count": len(campaigns),
        "opportunity_count": sum(row.get("opportunity_count") or 0 for row in campaigns),
        "quotation_count": sum(row.get("quotation_count") or 0 for row in campaigns),
        "quotation_amount": sum(flt(row.get("quotation_amount")) for row in campaigns),
        "sales_order_count": sum(row.get("sales_order_count") or 0 for row in campaigns),
        "sales_order_amount": sum(flt(row.get("sales_order_amount")) for row in campaigns),
    }


def _latest_campaign_name() -> str | None:
    return frappe.db.get_value("Partner Campaign", {}, "name", order_by="modified desc") if frappe.db.exists("DocType", "Partner Campaign") else None


def _campaign_item_payload(row: dict) -> dict:
    return {
        "item_code": row.get("item_code") or row.get("code") or row.get("name"),
        "item_name": row.get("item_name"),
        "container": row.get("container"),
        "supplier_payment_mode": row.get("supplier_payment_mode"),
        "sold_qty_period": flt(row.get("sold_qty_period") or row.get("sold")),
        "available_qty_snapshot": flt(row.get("available_qty_snapshot") or row.get("stock")),
        "price_snapshot": flt(row.get("price_snapshot") or row.get("price")),
        "currency": row.get("currency"),
        "display_price": 1 if row.get("display_price", row.get("withPrice", True)) else 0,
        "display_available_qty": 1 if row.get("display_available_qty", row.get("withQty", True)) else 0,
        "source_item_price": row.get("source_item_price"),
    }


def _campaign_target_payload(row: dict) -> dict:
    party_type = row.get("party_type") or row.get("type")
    party_name = row.get("party_name") or row.get("name")
    snapshot = resolve_party_snapshot(party_type, party_name)
    crm_segment = row.get("crm_segment") or row.get("partner_segment") or row.get("className") or snapshot.get("crm_segment")
    business_type = row.get("business_type") or snapshot.get("business_type") or _segment_business_type(crm_segment)
    return {
        "party_type": party_type,
        "party_name": party_name,
        "display_name": row.get("display_name") or snapshot.get("display_name"),
        "business_type": business_type,
        "crm_segment": crm_segment,
        "partner_segment": snapshot.get("partner_segment") or row.get("partner_segment") or row.get("className"),
        "city": row.get("city") or snapshot.get("city"),
        "contact": row.get("contact"),
        "contact_person_name": row.get("contact_person_name") or row.get("contact_name"),
        "target_status": row.get("target_status") or row.get("status") or get_default_target_status(),
        "assigned_to": row.get("assigned_to"),
        "last_contact_date": row.get("last_contact_date"),
        "last_order_date": row.get("last_order_date") or snapshot.get("last_order_date"),
    }


def _article_candidate(row, from_date=None, to_date=None, price_list=None, container=None, supplier_payment_mode=None) -> dict:
    price = _item_price(row.name, price_list=price_list, supplier_payment_mode=supplier_payment_mode)
    return {
        "item_code": row.name,
        "item_name": row.item_name,
        "item_group": row.get("item_group"),
        "container": container,
        "supplier_payment_mode": price.get("supplier_payment_mode"),
        "sold_qty_period": _sold_qty(row.name, from_date, to_date),
        "available_qty_snapshot": _available_qty(row.name),
        "price_snapshot": price.get("price_list_rate"),
        "currency": price.get("currency"),
        "source_item_price": price.get("name"),
        "display_price": 1,
        "display_available_qty": 1,
        "selected": False,
    }


def _item_price(item_code: str, price_list: str | None = None, supplier_payment_mode: str | None = None) -> dict:
    filters: dict[str, Any] = {"item_code": item_code, "selling": 1}
    if price_list:
        filters["price_list"] = price_list
    if supplier_payment_mode and _has_field("Item Price", "custom_supplier_payment_mode"):
        filters["custom_supplier_payment_mode"] = supplier_payment_mode
    fields = ["name", "price_list", "price_list_rate", "currency"]
    if _has_field("Item Price", "custom_supplier_payment_mode"):
        fields.append("custom_supplier_payment_mode")
    row = frappe.get_all("Item Price", filters=filters, fields=fields, order_by="valid_from desc, modified desc", limit=1)
    if not row:
        return {}
    result = dict(row[0])
    result["supplier_payment_mode"] = result.get("custom_supplier_payment_mode")
    return result


def _sold_qty(item_code: str, from_date: str | None, to_date: str | None) -> float:
    conditions = ["soi.item_code = %s", "so.docstatus = 1"]
    values: list[Any] = [item_code]
    if from_date:
        conditions.append("so.transaction_date >= %s")
        values.append(from_date)
    if to_date:
        conditions.append("so.transaction_date <= %s")
        values.append(to_date)
    result = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(soi.qty), 0)
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE {' AND '.join(conditions)}
        """,
        values,
    )
    return flt(result[0][0]) if result else 0.0


def _available_qty(item_code: str) -> float:
    result = frappe.db.sql("SELECT COALESCE(SUM(actual_qty), 0) FROM `tabBin` WHERE item_code = %s", item_code)
    return flt(result[0][0]) if result else 0.0


def _container_item_codes(container: str | None) -> list[str]:
    if not container or not frappe.db.exists("Forecast Load Plan", container):
        return []
    return frappe.get_all(
        "Forecast Plan Item",
        filters={"parent": container},
        pluck="item_code",
        limit_page_length=0,
    )


def _target_candidates_for_type(party_type: str, segment=None, business_type=None, search=None, limit=80) -> list[dict]:
    if not frappe.db.exists("DocType", party_type):
        return []
    filters = _party_filters(party_type, segment=segment, business_type=business_type, search=search)
    or_filters = _party_search_or_filters(party_type, search=search)
    fields = _party_fields(party_type)
    rows = frappe.get_all(party_type, filters=filters, or_filters=or_filters, fields=fields, order_by="modified desc", limit_page_length=limit)
    return [_candidate_row(party_type, row) for row in rows]


def _party_filters(party_type: str, segment=None, business_type=None, search=None) -> dict:
    filters: dict[str, Any] = {}
    matching_parties = _parties_matching_crm_filter(party_type, business_type=business_type, segment=segment)
    if matching_parties is not None:
        filters["name"] = ["in", matching_parties or ["__none__"]]
    if party_type == "Customer":
        filters["disabled"] = 0
    return filters


def _party_search_or_filters(party_type: str, search=None) -> list[list[str]] | None:
    if not search:
        return None
    like = f"%{search}%"
    if party_type == "Lead":
        return [["Lead", "name", "like", like], ["Lead", "company_name", "like", like], ["Lead", "lead_name", "like", like], ["Lead", "city", "like", like]]
    if party_type == "Prospect":
        return [["Prospect", "name", "like", like], ["Prospect", "company_name", "like", like], ["Prospect", "territory", "like", like]]
    return [["Customer", "name", "like", like], ["Customer", "customer_name", "like", like], ["Customer", "territory", "like", like]]


def _party_fields(party_type: str) -> list[str]:
    fields = ["name", "modified"]
    if party_type == "Lead":
        fields += ["lead_name", "company_name", "city", "lead_owner"]
    elif party_type == "Prospect":
        fields += ["company_name", "territory", "prospect_owner", "customer_group"]
    else:
        fields += ["customer_name", "territory", "customer_group"]
    if _has_field(party_type, "custom_partner_segment"):
        fields.append("custom_partner_segment")
    return fields


def _candidate_row(party_type: str, row: dict) -> dict:
    if party_type == "Lead":
        display_name = row.get("company_name") or row.get("lead_name") or row.name
        city = row.get("city")
        owner = row.get("lead_owner")
    elif party_type == "Prospect":
        display_name = row.get("company_name") or row.name
        city = row.get("territory")
        owner = row.get("prospect_owner")
    else:
        display_name = row.get("customer_name") or row.name
        city = row.get("territory")
        owner = None
    crm_info = _party_primary_crm_segment(party_type, row.name, row.get("custom_partner_segment") or row.get("customer_group"))
    crm_segments = _party_crm_segments(party_type, row.name)
    partner_segment = crm_info.get("crm_segment") or row.get("custom_partner_segment") or row.get("customer_group")
    return {
        "selected": False,
        "party_type": party_type,
        "party_name": row.name,
        "display_name": display_name,
        "business_type": crm_info.get("business_type"),
        "crm_segment": crm_info.get("crm_segment"),
        "crm_segments": crm_segments,
        "partner_segment": partner_segment,
        "city": city,
        "assigned_to": owner,
        "target_status": get_default_target_status(),
    }


def _find_target_row(doc, target_row: str):
    for row in doc.targets or []:
        if row.name == target_row:
            return row
    frappe.throw(_("Target row {0} was not found on campaign {1}.").format(target_row, doc.name))


def _reload_campaign_target(campaign: str, target_row: str):
    doc = frappe.get_doc("Partner Campaign", campaign)
    return doc, _find_target_row(doc, target_row)


def _append_opportunity_items(opportunity, campaign_doc):
    for item in campaign_doc.items or []:
        if not item.item_code:
            continue
        opportunity.append(
            "items",
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": frappe.db.get_value("Item", item.item_code, "stock_uom"),
                "qty": 1,
                "rate": item.price_snapshot if item.display_price else 0,
                "amount": item.price_snapshot if item.display_price else 0,
            },
        )


def _append_quotation_items(quotation, campaign_doc):
    for item in campaign_doc.items or []:
        if not item.item_code:
            continue
        quotation.append(
            "items",
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.item_name or item.item_code,
                "qty": 1,
                "uom": frappe.db.get_value("Item", item.item_code, "stock_uom"),
                "rate": item.price_snapshot if item.display_price else 0,
            },
        )
    if not quotation.items:
        frappe.throw(_("Campaign has no selected articles to quote."))


def _campaign_offer_amount(campaign_doc) -> float:
    return flt(sum(flt(item.price_snapshot) for item in campaign_doc.items or [] if item.display_price))


def _validate_campaign_ready_state(doc) -> None:
    if doc.status not in {"Ready", "Running"}:
        return

    missing = []
    if not (doc.campaign_name or "").strip():
        missing.append(_("campaign name"))
    if not [row for row in doc.items or [] if row.item_code]:
        missing.append(_("at least one article"))
    if not [row for row in doc.targets or [] if row.party_type and row.party_name]:
        missing.append(_("at least one target"))
    if not _campaign_has_content(doc):
        missing.append(_("email, WhatsApp, or call content"))

    if missing:
        frappe.throw(_("Campaign cannot be {0} until it has {1}.").format(doc.status, ", ".join(missing)))


def _campaign_has_content(doc) -> bool:
    return any(
        (doc.get(fieldname) or "").strip()
        for fieldname in ["email_subject", "email_body", "whatsapp_text", "call_script"]
    )


def _log_campaign_event(campaign: str, event: str, detail: str) -> None:
    try:
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Partner Campaign",
                "reference_name": campaign,
                "content": f"{event}: {detail}",
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Orderlift campaign audit log failed")


def _link_doc_to_campaign_target(campaign_doc, doc):
    target_row = doc.get("custom_partner_campaign_target")
    if not target_row:
        return
    for row in campaign_doc.targets or []:
        if row.name != target_row:
            continue
        if doc.doctype == "Opportunity":
            row.opportunity = doc.name
            row.target_status = _status_if_exists("Opportunity Created") or row.target_status
        elif doc.doctype == "Quotation":
            row.quotation = doc.name
            row.target_status = _status_if_exists("Quotation Created") or row.target_status
        elif doc.doctype == "Sales Order":
            row.sales_order = doc.name
            row.target_status = _status_if_exists("Converted") or row.target_status
        break


def _set_last_campaign_on_party(row, campaign: str):
    return


def _history_row(row) -> dict:
    docs = []
    for doctype, fieldname in [("Opportunity", "opportunity"), ("Quotation", "quotation"), ("Sales Order", "sales_order")]:
        name = row.get(fieldname)
        if not name:
            continue
        status = frappe.db.get_value(doctype, name, "status") if frappe.db.exists(doctype, name) else "-"
        docs.append({"doctype": doctype, "name": name, "status": status or "-"})
    return {
        "campaign": row.campaign,
        "campaign_name": row.campaign_name or row.campaign,
        "campaign_status": row.campaign_status,
        "campaign_date": row.campaign_date,
        "business_type": row.business_type,
        "crm_segment": row.crm_segment,
        "target_status": row.target_status,
        "assigned_to": row.assigned_to,
        "last_contact_date": row.last_contact_date,
        "docs": docs,
    }


def _parties_matching_crm_filter(party_type: str, business_type=None, segment=None) -> list[str] | None:
    if not business_type and not segment:
        return None
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return []
    conditions = ["parenttype = %s"]
    values: list[Any] = [party_type]
    if business_type:
        conditions.append("business_type = %s")
        values.append(business_type)
    if segment:
        conditions.append("segment = %s")
        values.append(segment)
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT parent
        FROM `tabCRM Segment Assignment`
        WHERE {' AND '.join(conditions)}
        """,
        values,
        as_dict=True,
    )
    return [row.parent for row in rows]


def _party_crm_segments(party_type: str, party_name: str) -> list[dict]:
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return []
    return frappe.get_all(
        "CRM Segment Assignment",
        filters={"parenttype": party_type, "parent": party_name},
        fields=["business_type", "segment", "is_primary"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )


def _party_primary_crm_segment(party_type: str, party_name: str, fallback_segment: str | None = None) -> dict:
    rows = _party_crm_segments(party_type, party_name)
    if rows:
        return {"business_type": rows[0].business_type, "crm_segment": rows[0].segment}
    business_type, crm_segment = _resolve_legacy_segment(fallback_segment)
    return {"business_type": business_type, "crm_segment": crm_segment}


def _copy_party_segments(source_doc, target_doc):
    if not target_doc.meta.get_field("custom_crm_segments"):
        return
    rows = source_doc.get("custom_crm_segments") or []
    for row in rows:
        target_doc.append(
            "custom_crm_segments",
            {
                "business_type": row.business_type,
                "segment": row.segment,
                "is_primary": row.is_primary,
            },
        )


def _ensure_doc_segment(doc, business_type: str | None, segment: str | None):
    if not business_type or not segment or not doc.meta.get_field("custom_crm_segments"):
        return
    existing = {row.segment for row in doc.get("custom_crm_segments") or []}
    if segment in existing:
        return
    doc.append("custom_crm_segments", {"business_type": business_type, "segment": segment, "is_primary": 0 if existing else 1})


def _segment_business_type(segment: str | None) -> str | None:
    if not segment:
        return None
    if frappe.db.exists("CRM Segment", segment):
        return frappe.db.get_value("CRM Segment", segment, "business_type")
    business_type, _crm_segment = _resolve_legacy_segment(segment)
    return business_type


def _resolve_legacy_segment(segment: str | None) -> tuple[str | None, str | None]:
    if not segment:
        return None, None
    legacy_map = {
        "Grossiste": ("Distribution", "Grossiste"),
        "Distributeur": ("Distribution", "Grossiste"),
        "Revendeur": ("Distribution", "Revendeur"),
        "Installateur": ("Distribution", "Installateur"),
        "Promoteur": ("Installation", "Promoteur"),
        "Particulier": ("Installation", "Individu"),
        "Individu": ("Installation", "Individu"),
    }
    if segment in legacy_map:
        return legacy_map[segment]
    if frappe.db.exists("CRM Segment", segment):
        return frappe.db.get_value("CRM Segment", segment, "business_type"), segment
    return None, None


def _set_if_field(doc, fieldname: str, value):
    if value is not None and doc.meta.get_field(fieldname):
        doc.set(fieldname, value)


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _status_if_exists(status: str) -> str | None:
    return status if frappe.db.exists("Partner Campaign Status", status) else None


def _default_opportunity_type() -> str | None:
    return frappe.db.get_value("Opportunity Type", "Sales") or frappe.db.get_value("Opportunity Type", {}, "name")


def _default_company() -> str:
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    if company:
        return company
    return frappe.get_all("Company", pluck="name", limit_page_length=1)[0]


def _loads(payload: str | dict) -> dict:
    if isinstance(payload, str):
        return json.loads(payload or "{}")
    return payload or {}


def _merge_selected_items(candidates: list[dict], selected_rows: list[dict]) -> list[dict]:
    candidate_map = {row.get("item_code"): {**row, "selected": False} for row in candidates}
    for row in selected_rows:
        item_code = row.get("item_code")
        selected = {
            **row,
            "selected": True,
            "display_price": bool(row.get("display_price")),
            "display_available_qty": bool(row.get("display_available_qty")),
        }
        if item_code in candidate_map:
            candidate_map[item_code].update(selected)
        elif item_code:
            candidate_map[item_code] = selected
    return list(candidate_map.values())


def _merge_selected_targets(candidates: list[dict], selected_rows: list[dict]) -> list[dict]:
    candidate_map = {
        (row.get("party_type"), row.get("party_name")): {**row, "selected": False}
        for row in candidates
    }
    for row in selected_rows:
        key = (row.get("party_type"), row.get("party_name"))
        selected = {**row, "selected": True}
        if key in candidate_map:
            candidate_map[key].update(selected)
        elif all(key):
            candidate_map[key] = selected
    return list(candidate_map.values())


def _price_list_options() -> list[dict]:
    return frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        fields=["name", "currency"],
        order_by="name asc",
        limit_page_length=0,
    )


def _item_group_options() -> list[dict]:
    return frappe.get_all(
        "Item Group",
        filters={"is_group": 0},
        fields=["name", "parent_item_group"],
        order_by="name asc",
        limit_page_length=0,
    )


def _container_options() -> list[dict]:
    if not frappe.db.exists("DocType", "Forecast Load Plan"):
        return []
    return frappe.get_all(
        "Forecast Load Plan",
        fields=["name", "plan_label", "status", "departure_date"],
        order_by="modified desc",
        limit_page_length=100,
    )


def _price_list_item_codes(price_list: str | None, supplier_payment_mode: str | None = None) -> list[str]:
    if not price_list:
        return []
    filters: dict[str, Any] = {"price_list": price_list, "selling": 1}
    if supplier_payment_mode and _has_field("Item Price", "custom_supplier_payment_mode"):
        filters["custom_supplier_payment_mode"] = supplier_payment_mode
    return frappe.get_all("Item Price", filters=filters, pluck="item_code", limit_page_length=0)
