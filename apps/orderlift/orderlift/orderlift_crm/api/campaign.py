from __future__ import annotations

import json
import html
import re
from typing import Any
from urllib.parse import quote, urlparse

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate, today

from orderlift.warehouse_access import stock_warehouse_condition

try:
    from frappe.utils import now
except ImportError:  # Unit tests use a small frappe.utils stub.
    now = nowdate

try:
    import requests
except ImportError:  # pragma: no cover - Frappe images include requests.
    requests = None

from orderlift.company_scope import company_field_for
from orderlift.menu_access import get_allowed_business_types, resolve_current_company, user_can_access_all_business_types
from orderlift.orderlift_crm.status_workflow import get_default_status_name
from orderlift.orderlift_crm.doctype.partner_campaign.partner_campaign import (
    clean_date_value,
    get_default_target_status,
    resolve_party_snapshot,
    validate_target_status,
)
from orderlift.orderlift_crm.todo_priority import DEFAULT_TODO_PRIORITY
from orderlift.startup_roles import STOCK_QUANTITY_VIEWER_ROLE


def _scope_company() -> str:
    """Active company to focus custom-page queries on (empty = no focus)."""
    try:
        return resolve_current_company() or ""
    except Exception:
        return ""


def _scope_currency() -> str:
    company = _scope_company()
    if company:
        try:
            return frappe.db.get_value("Company", company, "default_currency") or ""
        except Exception:
            pass
    defaults = getattr(frappe, "defaults", None)
    getter = getattr(defaults, "get_global_default", None)
    return getter("currency") if callable(getter) else ""


def _apply_company_filter(filters: dict, doctype: str) -> dict:
    """Focus a query on the active company when the doctype carries one."""
    company = _scope_company()
    if not company:
        return filters
    field = company_field_for(doctype)
    if _has_field(doctype, field):
        filters[field] = company
    return filters


def _apply_campaign_scope_filters(filters: dict) -> dict:
    _apply_company_filter(filters, "Partner Campaign")
    return filters


def _campaign_company_in_scope(campaign: str) -> bool:
    field = company_field_for("Partner Campaign")
    if not _has_field("Partner Campaign", field):
        return True
    company = _scope_company()
    if not company:
        return True
    campaign_company = frappe.db.get_value("Partner Campaign", campaign, field)
    return not campaign_company or campaign_company == company


def _campaign_business_type_in_scope(campaign: str) -> bool:
    allowed = _user_allowed_business_types()
    if allowed is None:
        return True
    field = "business_type_filter"
    if not _has_field("Partner Campaign", field):
        return True
    business_type = (frappe.db.get_value("Partner Campaign", campaign, field) or "").strip()
    return not business_type or business_type in allowed


def _get_campaign_doc(campaign: str, ptype: str = "read", include_archived: int | str = 0):
    if not campaign or not frappe.db.exists("Partner Campaign", campaign):
        frappe.throw(_("Campaign was not found."))
    if not _campaign_is_visible(campaign, include_archived=include_archived):
        frappe.throw(_("Campaign is outside your active company or business scope."))
    doc = frappe.get_doc("Partner Campaign", campaign)
    if not frappe.has_permission("Partner Campaign", ptype=ptype, doc=doc):
        frappe.throw(_("Not permitted to access campaign {0}.").format(campaign), frappe.PermissionError)
    return doc


def _selling_price_list_access() -> dict:
    from orderlift.orderlift_sales.utils.price_list_scope import get_item_price_access

    return get_item_price_access("selling", company=_scope_company() or None)


def _allowed_selling_price_lists() -> list[str]:
    access = _selling_price_list_access()
    if not access.get("permitted"):
        return []
    return list(access.get("price_lists") or [])


def _validate_campaign_price_list(price_list: str | None, required: bool = False) -> str:
    from orderlift.orderlift_sales.utils.price_list_scope import validate_price_list_scope

    resolved = validate_price_list_scope(
        price_list,
        kind="selling",
        required=required,
        company=_scope_company() or None,
    )
    if not resolved:
        return ""

    access = _selling_price_list_access()
    allowed = set(access.get("price_lists") or [])
    if not access.get("permitted") or resolved not in allowed:
        frappe.throw(_("Selling Price List {0} is not available for your campaign scope.").format(resolved))
    return resolved


def _can_view_stock_qty() -> bool:
    user = getattr(frappe.session, "user", "")
    if user == "Administrator":
        return True
    return STOCK_QUANTITY_VIEWER_ROLE in set(frappe.get_roles(user) or [])


def _user_allowed_business_types() -> set[str] | None:
    user = getattr(frappe.session, "user", None)
    if user_can_access_all_business_types(user):
        return None
    return set(get_allowed_business_types(user) or [])


def _validate_campaign_business_type(business_type: str | None) -> str:
    clean = (business_type or "").strip()
    allowed = _user_allowed_business_types()
    if clean and allowed is not None and clean not in allowed:
        frappe.throw(_("Business Type {0} is outside your campaign scope.").format(clean))
    return clean


def _validate_campaign_segment(segment: str | None) -> str:
    clean = (segment or "").strip()
    if not clean:
        return ""
    business_type = _segment_business_type(clean)
    if business_type:
        _validate_campaign_business_type(business_type)
    return clean


def _effective_business_type_filter(business_type: str | None):
    clean = _validate_campaign_business_type(business_type)
    if clean:
        return clean
    allowed = _user_allowed_business_types()
    if allowed is None:
        return None
    return sorted(allowed) or ["__none__"]


CAMPAIGN_ACTION_TYPES = {"Email", "WhatsApp", "Call", "Visit", "Other"}
WHATSAPP_MANUAL_MODE = "Manual Click-to-Chat"
WHATSAPP_TWILIO_MODE = "Twilio"
WHATSAPP_WEBHOOK_MODE = "Custom Webhook"
WHATSAPP_LEGACY_API_MODE = "Automated API"
WHATSAPP_AUTOMATED_MODES = {WHATSAPP_TWILIO_MODE, WHATSAPP_WEBHOOK_MODE, WHATSAPP_LEGACY_API_MODE}
VISIT_TODO_MARKER = "[Orderlift Campaign Visit]"
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_TEMPLATE_KEYS = {
    "first_name",
    "contact_name",
    "company",
    "party_name",
    "campaign_name",
    "campaign_code",
    "business_type",
    "crm_segment",
    "city",
    "visit_date",
    "selected_articles",
}


@frappe.whitelist()
def get_manager_data(campaign: str | None = None, include_archived: int | str = 0) -> dict:
    include_archived = cint(include_archived)
    selected_campaign = (
        campaign
        if campaign and _campaign_is_visible(campaign, include_archived=include_archived) and _campaign_has_permission(campaign)
        else _latest_campaign_name(include_archived=include_archived)
    )
    return {
        "kpis": _global_campaign_kpis(),
        "campaigns": _campaign_rows(include_archived=include_archived),
        "selected_campaign": selected_campaign,
        "selected_campaign_doc": _campaign_doc_dict(selected_campaign, include_archived=include_archived) if selected_campaign else {},
        "targets": _campaign_targets(selected_campaign, include_archived=include_archived) if selected_campaign else [],
        "statuses": get_target_statuses(),
        "segments": get_partner_segments(),
    }


@frappe.whitelist()
def archive_campaign(campaign: str) -> dict:
    doc = _get_campaign_doc(campaign, ptype="write")
    if not doc.meta.get_field("archived"):
        frappe.throw(_("Campaign archive field is not available. Run migration and try again."))
    doc.archived = 1
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return {"name": doc.name, "archived": 1}


@frappe.whitelist()
def restore_campaign(campaign: str) -> dict:
    doc = _get_campaign_doc(campaign, ptype="write", include_archived=1)
    if not doc.meta.get_field("archived"):
        frappe.throw(_("Campaign archive field is not available. Run migration and try again."))
    doc.archived = 0
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return {"name": doc.name, "archived": 0}


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
    target_page = get_target_candidate_page(
        business_type=doc.get("business_type_filter"),
        segment=_campaign_crm_segment_filter(doc),
        limit=80,
    )
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
    _normalize_campaign_action_payload(data)
    name = data.get("name")
    doc = _get_campaign_doc(name, ptype="write") if name else frappe.new_doc("Partner Campaign")
    _ensure_campaign_action_field(doc, data.get("campaign_action_type"))

    for fieldname in [
        "campaign_name",
        "status",
        "campaign_action_type",
        "campaign_owner",
        "default_channel",
        "campaign_date",
        "start_date",
        "end_date",
        "target_family",
        "business_type_filter",
        "crm_segment_filter",
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
        "whatsapp_mode",
        "whatsapp_template",
        "whatsapp_template_language",
        "whatsapp_template_variables",
        "whatsapp_text",
        "call_script",
        "visit_subject",
        "visit_default_date",
        "visit_agenda",
        "other_subject",
        "other_notes",
        "visit_email_subject",
        "visit_email_mode",
        "visit_email_body",
        "visit_whatsapp_text",
        "visit_call_script",
    ]:
        if fieldname in data:
            setattr(doc, fieldname, data.get(fieldname))

    legacy_segment = (data.get("partner_segment_filter") or "").strip()
    if legacy_segment and not (doc.crm_segment_filter or "").strip():
        business_type, crm_segment = _resolve_legacy_segment(legacy_segment)
        doc.business_type_filter = doc.business_type_filter or business_type
        doc.crm_segment_filter = crm_segment
    if doc.meta.get_field("partner_segment_filter"):
        doc.partner_segment_filter = ""
    doc.price_list_filter = _validate_campaign_price_list(doc.price_list_filter, required=False)
    _validate_campaign_business_type(doc.business_type_filter)
    _validate_campaign_segment(doc.crm_segment_filter)

    doc.set("items", [])
    for row in data.get("items") or []:
        if row.get("selected") is False:
            continue
        doc.append(
            "items",
            _campaign_item_payload(
                row,
                price_list=doc.price_list_filter,
                supplier_payment_mode=doc.supplier_payment_mode_filter,
            ),
        )

    doc.set("targets", [])
    for row in data.get("targets") or []:
        if row.get("selected") is False:
            continue
        doc.append("targets", _campaign_target_payload(row))

    _sync_default_channel_from_action_type(doc)
    _validate_campaign_ready_state(doc)
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return {"name": doc.name, "campaign": _campaign_doc_dict(doc.name)}


@frappe.whitelist()
def render_campaign_content(campaign: str, target_row: str | None = None, action_type: str | None = None) -> dict:
    doc = _get_campaign_doc(campaign)
    row = _find_target_row(doc, target_row) if target_row else None
    return _render_campaign_content_for_doc(doc, row, action_type)


@frappe.whitelist()
def render_campaign_content_from_payload(payload: str | dict, target_row: str | None = None, action_type: str | None = None) -> dict:
    doc = _campaign_doc_from_payload(_loads(payload))
    row = _find_payload_target_row(doc, target_row) if target_row else _first_payload_target(doc)
    return _render_campaign_content_for_doc(doc, row, action_type)


@frappe.whitelist()
def get_campaign_send_preflight(
    campaign: str | None = None,
    payload: str | dict | None = None,
    target_rows: str | list | None = None,
    action_type: str | None = None,
) -> dict:
    if payload:
        doc = _campaign_doc_from_payload(_loads(payload))
    elif campaign:
        doc = _get_campaign_doc(campaign)
    else:
        frappe.throw(_("Campaign or payload is required."))
    return _campaign_send_preflight(doc, target_rows=target_rows, action_type=action_type)


def _render_campaign_content_for_doc(doc, row=None, action_type: str | None = None) -> dict:
    action_type = _normalize_action_type(action_type or _campaign_action_type(doc))
    context = _render_context(doc, row)

    if action_type == "Email":
        return {
            "action_type": action_type,
            "subject": _render_template(doc.email_subject or doc.campaign_name or doc.name, context),
            "body": _render_template(doc.email_body or "", context),
            "mode": doc.email_mode or "HTML",
        }
    if action_type == "WhatsApp":
        whatsapp_mode = _normalize_whatsapp_mode(doc.whatsapp_mode)
        return {
            "action_type": action_type,
            "mode": whatsapp_mode,
            "text": _render_template(doc.whatsapp_text or "", context),
            "template": _render_template(doc.whatsapp_template or "", context),
            "language": doc.whatsapp_template_language or "fr",
            "variables": _whatsapp_template_variables(doc, context),
        }
    if action_type == "Call":
        return {"action_type": action_type, "script": _render_template(doc.call_script or "", context)}
    if action_type == "Visit":
        return {
            "action_type": action_type,
            "subject": _render_template(doc.visit_subject or doc.campaign_name or doc.name, context),
            "agenda": _render_template(doc.visit_agenda or "", context),
            "visit_date": row.visit_date if row else doc.visit_default_date,
        }
    return {
        "action_type": "Other",
        "subject": _render_template(doc.other_subject or doc.campaign_name or doc.name, context),
        "notes": _render_template(doc.other_notes or "", context),
    }


@frappe.whitelist()
def get_email_preview(campaign: str, target_row: str) -> dict:
    return render_campaign_content(campaign, target_row, "Email")


@frappe.whitelist()
def send_campaign_email(campaign: str, target_row: str, scheduled_at: str | None = None) -> dict:
    doc, row = _get_campaign_and_target(campaign, target_row)
    _ensure_campaign_can_send(doc, [row.name], "Email", scheduled_at=scheduled_at)
    recipient = (row.email or "").strip()
    if not recipient:
        frappe.throw(_("Target {0} has no email address.").format(row.display_name or row.party_name))

    content = render_campaign_content(campaign, target_row, "Email")
    subject = content.get("subject") or doc.campaign_name or doc.name
    message = content.get("body") or ""
    kwargs = {
        "recipients": [recipient],
        "subject": subject,
        "message": message,
        "delayed": True,
        "reference_doctype": row.party_type,
        "reference_name": row.party_name,
    }
    if scheduled_at:
        kwargs["send_after"] = scheduled_at
    frappe.sendmail(**kwargs)

    doc, row = _reload_campaign_target(campaign, target_row)
    row.last_email_queue = _latest_email_queue(row.party_type, row.party_name, subject)
    _mark_row_outreach(row, "Email")
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Email Scheduled" if scheduled_at else "Email Queued", f"{recipient}: {subject}")
    return {"recipient": recipient, "subject": subject, "email_queue": row.last_email_queue or ""}


@frappe.whitelist()
def bulk_schedule_campaign_email(campaign: str, target_rows: str | list | None = None, scheduled_at: str | None = None) -> dict:
    rows = _loads(target_rows) if isinstance(target_rows, str) else target_rows
    doc = _get_campaign_doc(campaign)
    _ensure_campaign_can_send(doc, rows, "Email", scheduled_at=scheduled_at)
    target_names = set(rows or [row.name for row in doc.targets or []])
    return _bulk_target_action(doc, target_names, lambda row: send_campaign_email(campaign, row.name, scheduled_at))


@frappe.whitelist()
def get_whatsapp_click_to_chat(campaign: str, target_row: str) -> dict:
    doc, row = _get_campaign_and_target(campaign, target_row)
    _ensure_campaign_can_send(doc, [row.name], "WhatsApp")
    phone = normalize_whatsapp_phone(row.mobile_no)
    if not phone:
        frappe.throw(_("Target {0} has no valid WhatsApp phone number.").format(row.display_name or row.party_name))
    content = render_campaign_content(campaign, target_row, "WhatsApp")
    message = content.get("text") or ""
    return {"phone": phone, "message": message, "url": f"https://wa.me/{phone}?text={quote(message)}"}


@frappe.whitelist()
def send_campaign_whatsapp_template(campaign: str, target_row: str) -> dict:
    doc, row = _get_campaign_and_target(campaign, target_row)
    _ensure_campaign_can_send(doc, [row.name], "WhatsApp")
    whatsapp_mode = _normalize_whatsapp_mode(doc.whatsapp_mode)
    if whatsapp_mode == WHATSAPP_MANUAL_MODE:
        frappe.throw(_("Manual WhatsApp mode uses click-to-chat. Select Twilio or Custom Webhook for automated templates."))
    phone = normalize_whatsapp_phone(row.mobile_no)
    if not phone:
        frappe.throw(_("Target {0} has no valid WhatsApp phone number.").format(row.display_name or row.party_name))
    content = render_campaign_content(campaign, target_row, "WhatsApp")
    template = content.get("template") or doc.whatsapp_template
    message = content.get("text") or doc.whatsapp_text
    if whatsapp_mode == WHATSAPP_TWILIO_MODE and not template:
        frappe.throw(_("Select a Meta-approved WhatsApp template before automated sending."))
    if whatsapp_mode == WHATSAPP_WEBHOOK_MODE and not (template or message):
        frappe.throw(_("Add a webhook message or approved template before automated WhatsApp sending."))
    response = _send_whatsapp_api(phone, content, doc, row)

    doc, row = _reload_campaign_target(campaign, target_row)
    row.last_whatsapp_mode = whatsapp_mode
    _mark_row_outreach(row, "WhatsApp")
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "WhatsApp Template Sent", f"{row.display_name or row.party_name}: {template}")
    return response


@frappe.whitelist()
def mark_target_outreach(campaign: str, target_row: str, outreach_type: str, note: str | None = None, status: str | None = None) -> dict:
    doc, row = _get_campaign_and_target(campaign, target_row)
    outreach_type = _normalize_action_type(outreach_type)
    if outreach_type == "Email":
        frappe.throw(_("Use Send Email for email outreach so the Email Queue stays linked."))
    if note is not None:
        row.target_note = (note or "").strip()
    if status:
        row.target_status = validate_target_status(status)
    if outreach_type == "WhatsApp":
        row.last_whatsapp_mode = row.last_whatsapp_mode or _normalize_whatsapp_mode(doc.whatsapp_mode)
    _mark_row_outreach(row, outreach_type)
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, f"{outreach_type} Marked", row.display_name or row.party_name)
    return _target_row_dict(row)


@frappe.whitelist()
def update_target_visit(campaign: str, target_row: str, visit_date: str | None = None, visit_status: str | None = None) -> dict:
    doc, row = _get_campaign_and_target(campaign, target_row)
    row.visit_date = clean_date_value(visit_date)
    if visit_status is not None:
        row.visit_status = visit_status
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return _target_row_dict(row)


@frappe.whitelist()
def create_visit_todo(campaign: str, target_row: str) -> dict:
    doc, row = _get_campaign_and_target(campaign, target_row)
    if not row.visit_date:
        frappe.throw(_("Set a visit date for {0} before creating a ToDo.").format(row.display_name or row.party_name))
    content = render_campaign_content(campaign, target_row, "Visit")
    todo = _upsert_visit_todo(doc, row, content)
    row.visit_todo = todo.name
    row.visit_status = row.visit_status or "Planned"
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Visit ToDo Created", f"{row.display_name or row.party_name}: {todo.name}")
    return {"name": todo.name, "target": _target_row_dict(row)}


@frappe.whitelist()
def bulk_create_visit_todos(campaign: str, target_rows: str | list | None = None) -> dict:
    rows = _loads(target_rows) if isinstance(target_rows, str) else target_rows
    doc = _get_campaign_doc(campaign)
    target_names = set(rows or [row.name for row in doc.targets or [] if row.visit_date])
    return _bulk_target_action(doc, target_names, lambda row: create_visit_todo(campaign, row.name))


@frappe.whitelist()
def update_target_status(campaign: str, target_row: str, status: str) -> dict:
    doc = _get_campaign_doc(campaign, ptype="write")
    status = validate_target_status(status)
    row = _find_target_row(doc, target_row)
    row.target_status = status
    row.last_contact_date = nowdate()
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    _log_campaign_event(doc.name, "Target Status Changed", f"{row.display_name or row.party_name}: {status}")
    return _target_row_dict(row)


@frappe.whitelist()
def update_target_note(campaign: str, target_row: str, note: str | None = None) -> dict:
    doc = _get_campaign_doc(campaign, ptype="write")
    row = _find_target_row(doc, target_row)
    row.target_note = (note or "").strip()
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return _target_row_dict(row)


@frappe.whitelist()
def create_prospect_from_target(campaign: str, target_row: str) -> dict:
    doc = _get_campaign_doc(campaign, ptype="write")
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
    doc = _get_campaign_doc(campaign, ptype="write")
    row = _find_target_row(doc, target_row)
    if row.opportunity:
        return {"name": row.opportunity}

    opportunity = frappe.new_doc("Opportunity")
    opportunity.company = _campaign_company(doc) or _default_company()
    opportunity.opportunity_from = row.party_type
    opportunity.party_name = row.party_name
    opportunity.customer_name = row.display_name
    opportunity.opportunity_owner = row.assigned_to or doc.campaign_owner or frappe.session.user
    opportunity.transaction_date = today()
    opportunity.status = "Open"
    opportunity.opportunity_type = _default_opportunity_type()
    opportunity.opportunity_amount = _campaign_offer_amount(doc)
    opportunity.probability = 20
    opportunity.title = _opportunity_title_for_campaign_target(doc, row)
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
    doc = _get_campaign_doc(campaign, ptype="write")
    row = _find_target_row(doc, target_row)
    if row.quotation:
        return {"name": row.quotation}

    quotation = frappe.new_doc("Quotation")
    quotation.company = _campaign_company(doc) or _default_company()
    quotation.quotation_to = row.party_type
    quotation.party_name = row.party_name
    quotation.customer_name = row.display_name
    quotation.transaction_date = today()
    quotation.order_type = "Sales"
    if row.opportunity:
        quotation.opportunity = row.opportunity
    _set_if_field(quotation, "custom_partner_campaign", doc.name)
    _set_if_field(quotation, "custom_partner_campaign_target", row.name)
    _set_if_field(quotation, "custom_crm_business_type", row.business_type)
    _set_if_field(quotation, "custom_crm_segment", row.crm_segment)
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
    price_list = _validate_campaign_price_list(price_list, required=False)
    allowed_price_lists = _allowed_selling_price_lists()
    if not allowed_price_lists:
        return []
    item_codes = _container_item_codes(container)
    price_list_item_codes = _price_list_item_codes(
        price_list,
        supplier_payment_mode=supplier_payment_mode,
        allowed_price_lists=allowed_price_lists,
    )
    if not price_list_item_codes:
        return []
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
            allowed_price_lists=allowed_price_lists,
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
    business_type = _effective_business_type_filter(business_type)
    segment = _validate_campaign_segment(segment)
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
    filters = {"is_active": 1}
    allowed = _user_allowed_business_types()
    if allowed is not None:
        if not allowed:
            return []
        filters["business_type"] = ["in", sorted(allowed)]
    return frappe.get_all(
        "CRM Segment",
        filters=filters,
        fields=["name", "segment_name", "business_type", "sequence"],
        order_by="sequence asc, segment_name asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_business_types() -> list[dict]:
    if not frappe.db.exists("DocType", "CRM Business Type"):
        return []
    filters = {"is_active": 1}
    allowed = _user_allowed_business_types()
    if allowed is not None:
        if not allowed:
            return []
        filters["name"] = ["in", sorted(allowed)]
    return frappe.get_all(
        "CRM Business Type",
        filters=filters,
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
    scope_conditions = []
    company = _scope_company()
    company_field = company_field_for("Partner Campaign")
    if company and _has_field("Partner Campaign", company_field):
        scope_conditions.append(f"pc.`{company_field}` = %s")
        values.append(company)
    allowed_business_types = _user_allowed_business_types()
    if allowed_business_types is not None:
        if not allowed_business_types:
            return []
        scope_conditions.append("pct.business_type in %s")
        values.append(tuple(sorted(allowed_business_types)))
    scope_sql = ""
    if scope_conditions:
        scope_sql = " AND " + " AND ".join(scope_conditions)
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
        {scope_sql}
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
        quotation_names = _linked_quotation_names_from_sales_order(doc)
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


def _linked_quotation_names_from_sales_order(doc) -> list[str]:
    quotation_names = []
    for row in doc.get("items", []) or []:
        quotation = row.get("prevdoc_docname") if hasattr(row, "get") else getattr(row, "prevdoc_docname", None)
        if not quotation or quotation in quotation_names:
            continue
        if frappe.db.exists("Quotation", quotation):
            quotation_names.append(quotation)
    return quotation_names


def _campaign_rows(include_archived: int | str = 0) -> list[dict]:
    if not frappe.db.exists("DocType", "Partner Campaign"):
        return []
    include_archived = cint(include_archived)
    filters = {"archived": include_archived} if _campaign_archive_available() else {}
    _apply_campaign_scope_filters(filters)
    fields = [
        "name",
        "campaign_name",
        "campaign_action_type",
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
    ]
    if _campaign_archive_available():
        fields.append("archived")
    rows = frappe.get_list(
        "Partner Campaign",
        filters=filters,
        fields=fields,
        order_by="modified desc",
        limit_page_length=50,
    )
    rows = [row for row in rows if _campaign_business_type_in_scope(row.name)]
    target_counts = _campaign_target_counts([row.name for row in rows])
    for row in rows:
        row["target_count"] = target_counts.get(row.name, 0)
        row["campaign_action_type"] = _normalize_action_type(row.get("campaign_action_type") or row.get("default_channel"))
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


def _campaign_targets(campaign: str, include_archived: int | str = 0) -> list[dict]:
    doc = _get_campaign_doc(campaign, include_archived=include_archived)
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
        "email": getattr(row, "email", None) or "",
        "mobile_no": getattr(row, "mobile_no", None) or "",
        "target_status": row.target_status,
        "assigned_to": row.assigned_to,
        "target_note": getattr(row, "target_note", None) or "",
        "last_contact_date": row.last_contact_date,
        "last_outreach_type": getattr(row, "last_outreach_type", None) or "",
        "last_outreach_date": getattr(row, "last_outreach_date", None) or "",
        "last_email_queue": getattr(row, "last_email_queue", None) or "",
        "last_whatsapp_mode": getattr(row, "last_whatsapp_mode", None) or "",
        "visit_date": getattr(row, "visit_date", None) or "",
        "visit_status": getattr(row, "visit_status", None) or "",
        "visit_todo": getattr(row, "visit_todo", None) or "",
        "prospect": row.prospect,
        "opportunity": row.opportunity,
        "quotation": row.quotation,
        "sales_order": row.sales_order,
        "last_order_date": row.last_order_date,
    }


def _campaign_doc_dict(campaign: str, include_archived: int | str = 0) -> dict:
    doc = _get_campaign_doc(campaign, include_archived=include_archived)
    data = doc.as_dict()
    data["crm_segment_filter"] = _campaign_crm_segment_filter(data)
    data["partner_segment_filter"] = ""
    data["items"] = [_campaign_item_row_dict(row) for row in doc.items or []]
    data["targets"] = [_target_row_dict(row) for row in doc.targets or []]
    return data


def _campaign_item_row_dict(row) -> dict:
    data = row.as_dict() if hasattr(row, "as_dict") else dict(row)
    if not _can_view_stock_qty():
        data.pop("available_qty_snapshot", None)
        data["display_available_qty"] = 0
    return data


def _campaign_crm_segment_filter(campaign: dict) -> str | None:
    crm_segment = (campaign.get("crm_segment_filter") or "").strip()
    if crm_segment:
        return crm_segment
    _business_type, legacy_segment = _resolve_legacy_segment(campaign.get("partner_segment_filter"))
    return legacy_segment


def _new_campaign_defaults() -> dict:
    return {
        "campaign_name": "",
        "status": "Draft",
        "campaign_action_type": "WhatsApp",
        "campaign_owner": frappe.session.user,
        "default_channel": "WhatsApp",
        "campaign_date": today(),
        "sales_history_from_date": today(),
        "sales_history_to_date": today(),
        "email_mode": "HTML",
        "whatsapp_mode": WHATSAPP_MANUAL_MODE,
        "whatsapp_template_language": "fr",
        "visit_default_date": today(),
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


def _latest_campaign_name(include_archived: int | str = 0) -> str | None:
    if not frappe.db.exists("DocType", "Partner Campaign"):
        return None
    include_archived = cint(include_archived)
    filters = {"archived": include_archived} if _campaign_archive_available() else {}
    _apply_campaign_scope_filters(filters)
    rows = frappe.get_list(
        "Partner Campaign",
        filters=filters,
        fields=["name"],
        order_by="modified desc",
        limit_page_length=20,
    )
    for row in rows:
        if _campaign_business_type_in_scope(row.name) and _campaign_has_permission(row.name):
            return row.name
    return None


def _campaign_is_visible(campaign: str, include_archived: int | str = 0) -> bool:
    if not campaign or not frappe.db.exists("Partner Campaign", campaign):
        return False
    if not _campaign_company_in_scope(campaign):
        return False
    if not _campaign_business_type_in_scope(campaign):
        return False
    if not _campaign_archive_available():
        return True
    return cint(frappe.db.get_value("Partner Campaign", campaign, "archived")) == cint(include_archived)


def _campaign_has_permission(campaign: str, ptype: str = "read") -> bool:
    try:
        doc = frappe.get_doc("Partner Campaign", campaign)
        return bool(frappe.has_permission("Partner Campaign", ptype=ptype, doc=doc))
    except Exception:
        return False


def _campaign_archive_available() -> bool:
    return bool(frappe.get_meta("Partner Campaign").get_field("archived")) if frappe.db.exists("DocType", "Partner Campaign") else False


def _campaign_item_payload(
    row: dict,
    price_list: str | None = None,
    supplier_payment_mode: str | None = None,
) -> dict:
    item_code = row.get("item_code") or row.get("code") or row.get("name")
    supplier_payment_mode = row.get("supplier_payment_mode") or supplier_payment_mode
    price = _item_price(item_code, price_list=price_list, supplier_payment_mode=supplier_payment_mode) if item_code else {}
    show_stock_qty = _can_view_stock_qty()
    display_price = bool(row.get("display_price", row.get("withPrice", True)))
    if item_code and display_price and not price:
        frappe.throw(_("Item {0} has no allowed selling price for this campaign scope.").format(item_code))
    display_available_qty = bool(row.get("display_available_qty", row.get("withQty", True))) and show_stock_qty
    return {
        "item_code": item_code,
        "item_name": row.get("item_name"),
        "container": row.get("container"),
        "supplier_payment_mode": supplier_payment_mode,
        "sold_qty_period": flt(row.get("sold_qty_period") or row.get("sold")),
        "available_qty_snapshot": flt(row.get("available_qty_snapshot") or row.get("stock")) if show_stock_qty else 0,
        "price_snapshot": flt(price.get("price_list_rate") if price else 0),
        "currency": price.get("currency") if price else row.get("currency"),
        "display_price": 1 if display_price else 0,
        "display_available_qty": 1 if display_available_qty else 0,
        "source_item_price": price.get("name") if price else "",
    }


def _campaign_target_payload(row: dict) -> dict:
    party_type = row.get("party_type") or row.get("type")
    party_name = row.get("party_name") or row.get("name")
    snapshot = resolve_party_snapshot(party_type, party_name)
    raw_crm_segment = row.get("crm_segment") or snapshot.get("crm_segment")
    raw_legacy_segment = row.get("partner_segment") or row.get("className") or snapshot.get("partner_segment")
    business_type = row.get("business_type") or snapshot.get("business_type")
    crm_segment = raw_crm_segment
    if not crm_segment and raw_legacy_segment:
        resolved_business_type, resolved_crm_segment = _resolve_legacy_segment(raw_legacy_segment)
        business_type = business_type or resolved_business_type
        crm_segment = resolved_crm_segment
    business_type = business_type or _segment_business_type(crm_segment)
    payload = {
        "party_type": party_type,
        "party_name": party_name,
        "display_name": row.get("display_name") or snapshot.get("display_name"),
        "business_type": business_type,
        "crm_segment": crm_segment,
        "partner_segment": raw_legacy_segment,
        "city": row.get("city") or snapshot.get("city"),
        "contact": row.get("contact") or snapshot.get("contact"),
        "contact_person_name": row.get("contact_person_name") or row.get("contact_name") or snapshot.get("contact_person_name"),
        "email": row.get("email") or snapshot.get("email"),
        "mobile_no": row.get("mobile_no") or row.get("phone") or snapshot.get("mobile_no"),
        "target_status": row.get("target_status") or row.get("status") or get_default_target_status(),
        "assigned_to": row.get("assigned_to"),
        "target_note": row.get("target_note") or row.get("note") or "",
        "last_contact_date": clean_date_value(row.get("last_contact_date")),
        "last_outreach_type": row.get("last_outreach_type"),
        "last_outreach_date": clean_date_value(row.get("last_outreach_date")),
        "last_email_queue": row.get("last_email_queue"),
        "last_whatsapp_mode": row.get("last_whatsapp_mode"),
        "visit_date": clean_date_value(row.get("visit_date")),
        "visit_status": row.get("visit_status"),
        "visit_todo": row.get("visit_todo"),
        "last_order_date": clean_date_value(row.get("last_order_date")) or clean_date_value(snapshot.get("last_order_date")),
    }
    _validate_campaign_target_scope(payload)
    return payload


def _validate_campaign_target_scope(payload: dict) -> None:
    party_type = payload.get("party_type")
    party_name = payload.get("party_name")
    if party_type not in {"Lead", "Prospect", "Customer"} or not party_name:
        frappe.throw(_("Campaign target must be a Lead, Prospect, or Customer."))
    if not frappe.db.exists("DocType", party_type):
        return
    if not frappe.db.exists(party_type, party_name):
        frappe.throw(_("Campaign target {0} {1} was not found.").format(party_type, party_name))
    if not _party_company_in_scope(party_type, party_name):
        frappe.throw(_("Campaign target {0} is outside your active company.").format(party_name))

    allowed = _user_allowed_business_types()
    if allowed is None:
        return
    business_type = (payload.get("business_type") or "").strip()
    if not business_type:
        frappe.throw(_("Campaign target {0} has no allowed CRM Business Type.").format(party_name))
    if business_type not in allowed:
        frappe.throw(_("Campaign target {0} is outside your CRM Business Type scope.").format(party_name))


def _party_company_in_scope(party_type: str, party_name: str) -> bool:
    company = _scope_company()
    if not company:
        return True
    field = company_field_for(party_type)
    if not _has_field(party_type, field):
        return True
    party_company = frappe.db.get_value(party_type, party_name, field)
    return not party_company or party_company == company


def _campaign_doc_from_payload(data: dict):
    _normalize_campaign_action_payload(data)
    doc = frappe._dict(data)
    doc.name = doc.get("name") or "Draft Campaign"
    doc["items"] = [
        frappe._dict(
            _campaign_item_payload(
                row,
                price_list=data.get("price_list_filter"),
                supplier_payment_mode=data.get("supplier_payment_mode_filter"),
            )
        )
        for row in data.get("items") or []
    ]
    doc["targets"] = []
    for row in data.get("targets") or []:
        target = _campaign_target_payload(row)
        target["name"] = row.get("name") or row.get("id") or row.get("party_name")
        target["id"] = row.get("id") or target["name"]
        doc["targets"].append(frappe._dict(target))
    return doc


def _find_payload_target_row(doc, target_row: str | None):
    target_row = (target_row or "").strip()
    for row in doc.targets or []:
        identifiers = {
            (row.get("name") or "").strip(),
            (row.get("id") or "").strip(),
            (row.get("party_name") or "").strip(),
            f"{row.get('party_type') or ''}::{row.get('party_name') or ''}",
        }
        if target_row in identifiers:
            return row
    return _first_payload_target(doc)


def _first_payload_target(doc):
    rows = [row for row in doc.targets or [] if row.get("party_type") and row.get("party_name")]
    return rows[0] if rows else None


def _article_candidate(
    row,
    from_date=None,
    to_date=None,
    price_list=None,
    container=None,
    supplier_payment_mode=None,
    allowed_price_lists=None,
) -> dict:
    price = _item_price(
        row.name,
        price_list=price_list,
        supplier_payment_mode=supplier_payment_mode,
        allowed_price_lists=allowed_price_lists,
    )
    show_stock_qty = _can_view_stock_qty()
    payload = {
        "item_code": row.name,
        "item_name": row.item_name,
        "item_group": row.get("item_group"),
        "container": container,
        "supplier_payment_mode": price.get("supplier_payment_mode"),
        "sold_qty_period": _sold_qty(row.name, from_date, to_date),
        "price_snapshot": price.get("price_list_rate"),
        "currency": price.get("currency"),
        "source_item_price": price.get("name"),
        "display_price": 1,
        "display_available_qty": 1 if show_stock_qty else 0,
        "selected": False,
    }
    if show_stock_qty:
        payload["available_qty_snapshot"] = _available_qty(row.name)
    return payload


def _item_price(
    item_code: str,
    price_list: str | None = None,
    supplier_payment_mode: str | None = None,
    allowed_price_lists: list[str] | None = None,
) -> dict:
    price_list = _validate_campaign_price_list(price_list, required=False)
    allowed_price_lists = allowed_price_lists if allowed_price_lists is not None else _allowed_selling_price_lists()
    if not allowed_price_lists:
        return {}
    filters: dict[str, Any] = {"item_code": item_code, "selling": 1}
    if price_list:
        filters["price_list"] = price_list
    else:
        filters["price_list"] = ["in", allowed_price_lists]
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
    params = {"item_code": item_code}
    result = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabBin`
        WHERE item_code = %(item_code)s
        {stock_warehouse_condition("warehouse", params)}
        """,
        params,
    )
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
    rows = frappe.get_list(party_type, filters=filters, or_filters=or_filters, fields=fields, order_by="modified desc", limit_page_length=limit)
    return [_candidate_row(party_type, row) for row in rows]


def _party_filters(party_type: str, segment=None, business_type=None, search=None) -> dict:
    filters: dict[str, Any] = {}
    matching_parties = _parties_matching_crm_filter(party_type, business_type=business_type, segment=segment)
    if matching_parties is not None:
        filters["name"] = ["in", matching_parties or ["__none__"]]
    if party_type == "Customer":
        filters["disabled"] = 0
    _apply_company_filter(filters, party_type)
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
        fields += ["company_name", "territory", "prospect_owner"]
    else:
        fields += ["customer_name", "territory"]
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
    crm_info = _party_primary_crm_segment(party_type, row.name)
    crm_segments = _party_crm_segments(party_type, row.name)
    partner_segment = crm_info.get("crm_segment") or row.get("custom_partner_segment")
    snapshot = resolve_party_snapshot(party_type, row.name)
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
        "contact": snapshot.get("contact"),
        "contact_person_name": snapshot.get("contact_person_name"),
        "email": snapshot.get("email"),
        "mobile_no": snapshot.get("mobile_no"),
        "assigned_to": owner,
        "target_status": get_default_target_status(),
    }


def _find_target_row(doc, target_row: str):
    for row in doc.targets or []:
        if row.name == target_row:
            return row
    frappe.throw(_("Target row {0} was not found on campaign {1}.").format(target_row, doc.name))


def _reload_campaign_target(campaign: str, target_row: str):
    doc = _get_campaign_doc(campaign, ptype="write")
    return doc, _find_target_row(doc, target_row)


def _child_rows(doc, fieldname: str) -> list:
    if hasattr(doc, "get"):
        return doc.get(fieldname) or []
    return getattr(doc, fieldname, None) or []


def _append_opportunity_items(opportunity, campaign_doc):
    for item in _child_rows(campaign_doc, "items"):
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
    for item in _child_rows(campaign_doc, "items"):
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
    return flt(sum(flt(item.price_snapshot) for item in _child_rows(campaign_doc, "items") if item.display_price))


def _campaign_action_type(campaign_doc) -> str:
    get_value = campaign_doc.get if hasattr(campaign_doc, "get") else lambda fieldname: getattr(campaign_doc, fieldname, None)
    return _normalize_action_type(get_value("campaign_action_type") or get_value("default_channel"))


def _campaign_send_preflight(
    doc,
    target_rows: str | list | None = None,
    action_type: str | None = None,
) -> dict:
    action_type = _normalize_action_type(action_type or _campaign_action_type(doc))
    rows = _target_rows_for_preflight(doc, target_rows)
    campaign_blockers, campaign_warnings = _campaign_preflight_messages(doc, action_type)
    target_results = [_target_preflight(doc, row, action_type) for row in rows]
    blocker_count = len(campaign_blockers) + sum(len(row["blockers"]) for row in target_results)
    warning_count = len(campaign_warnings) + sum(len(row["warnings"]) for row in target_results)
    ready_count = sum(1 for row in target_results if row["ready"])
    return {
        "campaign": doc.get("name") or "",
        "action_type": action_type,
        "target_count": len(rows),
        "ready_count": ready_count,
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "campaign_blockers": campaign_blockers,
        "campaign_warnings": campaign_warnings,
        "targets": target_results,
        "ok": blocker_count == 0 and bool(rows),
    }


def _ensure_campaign_can_send(doc, target_rows: str | list | None, action_type: str, scheduled_at: str | None = None) -> dict:
    if scheduled_at and str(scheduled_at) <= str(now()):
        frappe.throw(_("Schedule time must be in the future."))
    preflight = _campaign_send_preflight(doc, target_rows=target_rows, action_type=action_type)
    if preflight["blocker_count"]:
        messages = list(preflight["campaign_blockers"])
        for row in preflight["targets"]:
            messages.extend([f"{row['label']}: {message}" for message in row["blockers"]])
        frappe.throw("<br>".join(messages[:12]))
    return preflight


def _target_rows_for_preflight(doc, target_rows: str | list | None) -> list:
    if isinstance(target_rows, str):
        target_rows = _loads(target_rows)
    names = {str(name) for name in target_rows or [] if name}
    rows = list(doc.get("targets") or [])
    if not names:
        return rows
    return [row for row in rows if str(row.get("name") or row.get("id") or row.get("party_name")) in names]


def _campaign_preflight_messages(doc, action_type: str) -> tuple[list[str], list[str]]:
    blockers = []
    warnings = []
    configured_action = _campaign_action_type(doc)
    if action_type != configured_action:
        blockers.append(_("Campaign type is {0}, not {1}.").format(configured_action, action_type))
    if cint(doc.get("archived")):
        blockers.append(_("Archived campaigns cannot send outreach."))
    status = (doc.get("status") or "Draft").strip()
    if status in {"Closed", "Paused"}:
        blockers.append(_("Campaign status is {0}.").format(status))
    elif status not in {"Ready", "Running"}:
        warnings.append(_("Campaign status is {0}. Set it to Ready or Running before operational sending.").format(status))
    if not _campaign_has_content(doc):
        blockers.append(_("Campaign is missing {0} content.").format(action_type))
    unknown = _unknown_placeholders_for_action(doc, action_type)
    if unknown:
        warnings.append(_("Unknown placeholders: {0}").format(", ".join(sorted(unknown))))
    if action_type == "WhatsApp":
        blockers.extend(_whatsapp_settings_blockers(doc))
    return blockers, warnings


def _target_preflight(doc, row, action_type: str) -> dict:
    blockers = []
    warnings = []
    label = row.get("display_name") or row.get("party_name") or row.get("name") or _("Target")
    if action_type == "Email":
        email_address = (row.get("email") or "").strip()
        if not email_address:
            blockers.append(_("Missing email address."))
        elif not EMAIL_RE.match(email_address):
            blockers.append(_("Invalid email address: {0}").format(email_address))
    if action_type == "WhatsApp":
        phone = normalize_whatsapp_phone(row.get("mobile_no"))
        if not phone:
            blockers.append(_("Missing valid WhatsApp phone number."))
    return {
        "id": row.get("name") or row.get("id") or row.get("party_name") or "",
        "label": label,
        "party_type": row.get("party_type") or "",
        "party_name": row.get("party_name") or "",
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def _unknown_placeholders_for_action(doc, action_type: str) -> set[str]:
    values = []
    if action_type == "Email":
        values.extend([doc.get("email_subject"), doc.get("email_body")])
    elif action_type == "WhatsApp":
        values.extend([doc.get("whatsapp_text"), doc.get("whatsapp_template"), doc.get("whatsapp_template_variables")])
    elif action_type == "Call":
        values.append(doc.get("call_script"))
    elif action_type == "Visit":
        values.extend([doc.get("visit_subject"), doc.get("visit_agenda")])
    elif action_type == "Other":
        values.extend([doc.get("other_subject"), doc.get("other_notes")])
    found = {match.group(1) for value in values for match in PLACEHOLDER_RE.finditer(value or "")}
    return found - ALLOWED_TEMPLATE_KEYS


def _whatsapp_settings_blockers(doc) -> list[str]:
    whatsapp_mode = _normalize_whatsapp_mode(doc.get("whatsapp_mode"))
    if whatsapp_mode == WHATSAPP_MANUAL_MODE:
        return []
    if not frappe.db.exists("DocType", "Orderlift WhatsApp Settings"):
        return [_('Orderlift WhatsApp Settings doctype is missing.')]
    settings = frappe.get_single("Orderlift WhatsApp Settings")
    blockers = []
    if not cint(settings.enabled):
        blockers.append(_("Orderlift WhatsApp Settings is disabled."))
    if whatsapp_mode == WHATSAPP_TWILIO_MODE:
        if not (settings.twilio_account_sid or "").strip():
            blockers.append(_("Twilio Account SID is missing."))
        if not _settings_password(settings, "twilio_auth_token"):
            blockers.append(_("Twilio Auth Token is missing."))
        if not normalize_whatsapp_phone(settings.twilio_from_number, ""):
            blockers.append(_("Twilio From Number is missing."))
        template = (doc.get("whatsapp_template") or "").strip()
        if template and not template.startswith("HX"):
            blockers.append(_("Twilio Content SID should start with HX."))
    if whatsapp_mode == WHATSAPP_WEBHOOK_MODE:
        webhook_url = (settings.custom_webhook_url or "").strip()
        if not webhook_url:
            blockers.append(_("Custom Webhook URL is missing."))
        elif not _webhook_url_is_allowed(webhook_url):
            blockers.append(_("Custom Webhook URL must be a public http(s) URL."))
    return blockers


def _webhook_url_is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    hostname = (parsed.hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return False
    return True


def _normalize_campaign_action_payload(data: dict) -> None:
    action_type = _normalize_action_type(data.get("campaign_action_type") or data.get("default_channel"))
    data["campaign_action_type"] = action_type
    data["default_channel"] = action_type if action_type in {"Email", "WhatsApp", "Call"} else ""


def _ensure_campaign_action_field(doc, action_type: str | None) -> None:
    if not action_type or action_type in {"Email", "WhatsApp", "Call"}:
        return
    if doc.meta.get_field("campaign_action_type"):
        return
    frappe.throw(_("Run bench migrate before saving {0} campaigns. The campaign_action_type field is missing.").format(action_type))


def _sync_default_channel_from_action_type(campaign_doc) -> None:
    action_type = _campaign_action_type(campaign_doc)
    campaign_doc.campaign_action_type = action_type
    campaign_doc.default_channel = action_type if action_type in {"Email", "WhatsApp", "Call"} else ""


def _opportunity_title_for_campaign_target(campaign_doc, target_row) -> str:
    target_name = (target_row.display_name or target_row.party_name or "").strip()
    if not target_name:
        target_name = campaign_doc.campaign_name or campaign_doc.name
    return f"{target_name} [{_campaign_short_code(campaign_doc.name)}]"


def _campaign_short_code(campaign: str | None) -> str:
    parts = [part for part in str(campaign or "").split("-") if part]
    if len(parts) >= 2 and parts[0] == "PC":
        return f"PC-{parts[-1]}"
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[-1]}"
    return str(campaign or "")


def _normalize_action_type(action_type: str | None) -> str:
    clean = (action_type or "").strip()
    return clean if clean in CAMPAIGN_ACTION_TYPES else "WhatsApp"


def _normalize_whatsapp_mode(mode: str | None) -> str:
    clean = (mode or "").strip()
    if clean in {WHATSAPP_MANUAL_MODE, WHATSAPP_TWILIO_MODE, WHATSAPP_WEBHOOK_MODE}:
        return clean
    if clean == WHATSAPP_LEGACY_API_MODE:
        return WHATSAPP_WEBHOOK_MODE
    return WHATSAPP_MANUAL_MODE


def _get_campaign_and_target(campaign: str, target_row: str):
    doc = _get_campaign_doc(campaign, ptype="write")
    return doc, _find_target_row(doc, target_row)


def _render_context(campaign_doc, target_row=None) -> dict:
    contact_name = (getattr(target_row, "contact_person_name", None) or "").strip() if target_row else ""
    company = (getattr(target_row, "display_name", None) or getattr(target_row, "party_name", None) or "").strip() if target_row else ""
    first_name = contact_name.split(" ", 1)[0] if contact_name else company.split(" ", 1)[0]
    return {
        "first_name": first_name,
        "contact_name": contact_name,
        "company": company,
        "party_name": getattr(target_row, "party_name", "") if target_row else "",
        "campaign_name": campaign_doc.campaign_name or campaign_doc.name,
        "campaign_code": _campaign_short_code(campaign_doc.name),
        "business_type": getattr(target_row, "business_type", "") if target_row else campaign_doc.business_type_filter,
        "crm_segment": getattr(target_row, "crm_segment", "") if target_row else campaign_doc.crm_segment_filter,
        "city": getattr(target_row, "city", "") if target_row else "",
        "visit_date": getattr(target_row, "visit_date", "") if target_row else campaign_doc.visit_default_date,
        "selected_articles": _selected_articles_text(campaign_doc),
    }


def _render_template(template: str | None, context: dict) -> str:
    def replace(match):
        key = match.group(1)
        value = context.get(key)
        return "" if value is None else str(value)

    return PLACEHOLDER_RE.sub(replace, template or "")


def _selected_articles_text(campaign_doc) -> str:
    lines = []
    show_stock_qty = _can_view_stock_qty()
    for item in _child_rows(campaign_doc, "items"):
        if not item.item_code:
            continue
        parts = [item.item_code]
        if item.item_name:
            parts.append(item.item_name)
        if item.display_available_qty and show_stock_qty:
            parts.append(_("Available: {0}").format(flt(item.available_qty_snapshot)))
        if item.display_price:
            parts.append(_("Price: {0} {1}").format(flt(item.price_snapshot), item.currency or _scope_currency()))
        lines.append(" - ".join(str(part) for part in parts if part is not None))
    return "\n".join(lines)


def _whatsapp_template_variables(campaign_doc, context: dict) -> dict:
    raw = (campaign_doc.whatsapp_template_variables or "").strip()
    if not raw:
        return {"1": context.get("contact_name") or context.get("company"), "2": context.get("campaign_name")}
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return {str(key): _render_template(str(value), context) for key, value in parsed.items()}
    if isinstance(parsed, list):
        return {str(index + 1): _render_template(str(value), context) for index, value in enumerate(parsed)}

    values = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = _render_template(value.strip(), context)
    return values or {"1": _render_template(raw, context)}


def normalize_whatsapp_phone(phone: str | None, default_country_code: str | None = None) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return ""
    default_country_code = re.sub(r"\D+", "", default_country_code or _default_country_code() or "212")
    if digits.startswith("0") and default_country_code:
        return default_country_code + digits.lstrip("0")
    if default_country_code and len(digits) <= 9 and not digits.startswith(default_country_code):
        return default_country_code + digits
    return digits


def _default_country_code() -> str:
    try:
        if frappe.db.exists("DocType", "Orderlift WhatsApp Settings"):
            return frappe.db.get_single_value("Orderlift WhatsApp Settings", "default_country_code") or "212"
    except Exception:
        pass
    return "212"


def _latest_email_queue(reference_doctype: str, reference_name: str, subject: str) -> str:
    try:
        if not frappe.db.exists("DocType", "Email Queue"):
            return ""
        filters = {}
        if _has_field("Email Queue", "reference_doctype"):
            filters["reference_doctype"] = reference_doctype
        if _has_field("Email Queue", "reference_name"):
            filters["reference_name"] = reference_name
        if _has_field("Email Queue", "subject") and subject:
            filters["subject"] = subject
        rows = frappe.get_all("Email Queue", filters=filters, fields=["name"], order_by="creation desc", limit_page_length=1)
        return rows[0].name if rows else ""
    except Exception:
        return ""


def _send_whatsapp_api(phone: str, content: dict, campaign_doc, target_row) -> dict:
    if requests is None:
        frappe.throw(_("Python requests is required for WhatsApp API sending."))
    if not frappe.db.exists("DocType", "Orderlift WhatsApp Settings"):
        frappe.throw(_("Create Orderlift WhatsApp Settings before automated WhatsApp sending."))
    settings = frappe.get_single("Orderlift WhatsApp Settings")
    if not cint(settings.enabled):
        frappe.throw(_("Enable Orderlift WhatsApp Settings before automated WhatsApp sending."))

    provider = _whatsapp_provider_for_campaign(campaign_doc, settings)
    if provider == "Twilio":
        return _send_twilio_whatsapp(phone, content, settings)
    return _send_custom_webhook_whatsapp(phone, content, campaign_doc, target_row, settings)


def _whatsapp_provider_for_campaign(campaign_doc, settings) -> str:
    whatsapp_mode = _normalize_whatsapp_mode(campaign_doc.whatsapp_mode)
    if whatsapp_mode in {WHATSAPP_TWILIO_MODE, WHATSAPP_WEBHOOK_MODE}:
        return whatsapp_mode
    provider = (settings.provider or WHATSAPP_WEBHOOK_MODE).strip()
    return WHATSAPP_TWILIO_MODE if provider == WHATSAPP_TWILIO_MODE else WHATSAPP_WEBHOOK_MODE


def _send_twilio_whatsapp(phone: str, content: dict, settings) -> dict:
    sid = (settings.twilio_account_sid or "").strip()
    token = _settings_password(settings, "twilio_auth_token")
    from_number = normalize_whatsapp_phone(settings.twilio_from_number, "")
    template = content.get("template")
    if not sid or not token or not from_number or not template:
        frappe.throw(_("Twilio WhatsApp requires Account SID, Auth Token, From Number, and Template."))
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    response = requests.post(
        url,
        data={
            "From": f"whatsapp:+{from_number}",
            "To": f"whatsapp:+{phone}",
            "ContentSid": template,
            "ContentVariables": json.dumps(content.get("variables") or {}),
        },
        auth=(sid, token),
        timeout=20,
    )
    if response.status_code >= 400:
        frappe.throw(_("Twilio WhatsApp send failed: {0}").format(response.text[:300]))
    data = response.json() if response.content else {}
    return {"provider": "Twilio", "message_id": data.get("sid") or "", "status": data.get("status") or "queued"}


def _send_custom_webhook_whatsapp(phone: str, content: dict, campaign_doc, target_row, settings) -> dict:
    webhook_url = (settings.custom_webhook_url or "").strip()
    if not webhook_url:
        frappe.throw(_("Custom webhook URL is required for WhatsApp automated sending."))
    secret = _settings_password(settings, "custom_webhook_secret")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    payload = {
        "phone": phone,
        "template": content.get("template"),
        "language": content.get("language"),
        "variables": content.get("variables") or {},
        "message": content.get("text") or "",
        "campaign": campaign_doc.name,
        "campaign_name": campaign_doc.campaign_name,
        "target_row": target_row.name,
        "party_type": target_row.party_type,
        "party_name": target_row.party_name,
    }
    response = requests.post(webhook_url, json=payload, headers=headers, timeout=20)
    if response.status_code >= 400:
        frappe.throw(_("WhatsApp webhook failed: {0}").format(response.text[:300]))
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    return {"provider": "Custom Webhook", "message_id": data.get("id") or data.get("message_id") or "", "status": data.get("status") or "sent"}


def _settings_password(settings, fieldname: str) -> str:
    try:
        return settings.get_password(fieldname) or ""
    except Exception:
        return settings.get(fieldname) or ""


def _mark_row_outreach(row, outreach_type: str) -> None:
    row.last_outreach_type = outreach_type
    row.last_outreach_date = nowdate()
    row.last_contact_date = nowdate()


def _upsert_visit_todo(campaign_doc, target_row, content: dict):
    allocated_to = target_row.assigned_to or campaign_doc.campaign_owner or frappe.session.user
    description = _visit_todo_description(campaign_doc, target_row, content)
    todo = None
    if target_row.visit_todo and frappe.db.exists("ToDo", target_row.visit_todo):
        existing = frappe.get_doc("ToDo", target_row.visit_todo)
        if existing.status == "Open":
            todo = existing
    if not todo:
        existing_name = _find_open_visit_todo(target_row.party_type, target_row.party_name, campaign_doc.name)
        todo = frappe.get_doc("ToDo", existing_name) if existing_name else None
    if todo:
        todo.allocated_to = allocated_to
        todo.date = target_row.visit_date
        todo.description = description
        todo.status = "Open"
        todo.save(ignore_permissions=True)
        return todo
    return frappe.get_doc(
        {
            "doctype": "ToDo",
            "allocated_to": allocated_to,
            "reference_type": target_row.party_type,
            "reference_name": target_row.party_name,
            "description": description,
            "status": "Open",
            "priority": DEFAULT_TODO_PRIORITY,
            "date": target_row.visit_date,
        }
    ).insert(ignore_permissions=True)


def _visit_todo_description(campaign_doc, target_row, content: dict) -> str:
    subject = content.get("subject") or campaign_doc.visit_subject or campaign_doc.campaign_name or campaign_doc.name
    agenda = content.get("agenda") or campaign_doc.visit_agenda or ""
    return "\n".join(
        part
        for part in [
            f"{VISIT_TODO_MARKER} {_campaign_short_code(campaign_doc.name)} - {subject}",
            target_row.display_name or target_row.party_name,
            agenda,
        ]
        if part
    )


def _find_open_visit_todo(reference_type: str, reference_name: str, campaign: str) -> str | None:
    rows = frappe.get_all(
        "ToDo",
        filters={"reference_type": reference_type, "reference_name": reference_name, "status": "Open"},
        fields=["name", "description"],
        limit_page_length=20,
    )
    for row in rows:
        description = row.get("description") or ""
        if VISIT_TODO_MARKER in description and _campaign_short_code(campaign) in description:
            return row.name
    return None


def _bulk_target_action(campaign_doc, target_names: set[str], action) -> dict:
    result = {"success": [], "warnings": [], "errors": []}
    for row in campaign_doc.targets or []:
        if row.name not in target_names:
            continue
        try:
            result["success"].append({"target": row.name, "result": action(row)})
        except Exception as exc:
            result["errors"].append({"target": row.name, "label": row.display_name or row.party_name, "error": str(exc)})
    return result


def _validate_campaign_ready_state(doc) -> None:
    if doc.status not in {"Ready", "Running"}:
        return

    missing = []
    if not (doc.campaign_name or "").strip():
        missing.append(_("campaign name"))
    if not [row for row in _child_rows(doc, "items") if row.item_code]:
        missing.append(_("at least one article"))
    if not [row for row in doc.targets or [] if row.party_type and row.party_name]:
        missing.append(_("at least one target"))
    if not _campaign_has_content(doc):
        missing.append(_("{0} content").format(_campaign_action_type(doc)))

    if missing:
        frappe.throw(_("Campaign cannot be {0} until it has {1}.").format(doc.status, ", ".join(missing)))


def _campaign_has_content(doc) -> bool:
    action_type = _campaign_action_type(doc)
    fields_by_action = {
        "Call": ["call_script"],
        "Visit": ["visit_subject", "visit_agenda"],
        "Other": ["other_subject", "other_notes"],
    }
    if action_type == "Email":
        return bool(_plain_content(doc.get("email_body")))
    if action_type == "WhatsApp":
        whatsapp_mode = _normalize_whatsapp_mode(doc.get("whatsapp_mode"))
        if whatsapp_mode == WHATSAPP_TWILIO_MODE:
            return bool((doc.get("whatsapp_template") or "").strip())
        if whatsapp_mode == WHATSAPP_WEBHOOK_MODE:
            return bool((doc.get("whatsapp_template") or "").strip() or (doc.get("whatsapp_text") or "").strip())
        return bool((doc.get("whatsapp_text") or "").strip())
    return any((doc.get(fieldname) or "").strip() for fieldname in fields_by_action.get(action_type, []))


def _plain_content(value: str | None) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return html.unescape(without_tags).strip()


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
        if isinstance(business_type, (list, tuple, set)):
            business_types = [bt for bt in business_type if bt]
            if not business_types:
                return []
            conditions.append("business_type in %s")
            values.append(tuple(business_types))
        else:
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
    return {"business_type": None, "crm_segment": None}


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


def _campaign_company(campaign_doc) -> str:
    field = company_field_for("Partner Campaign")
    if hasattr(campaign_doc, "get"):
        return campaign_doc.get(field) or _scope_company()
    return getattr(campaign_doc, field, None) or _scope_company()


def _loads(payload: str | dict) -> dict:
    if isinstance(payload, str):
        return json.loads(payload or "{}")
    return payload or {}


def _merge_selected_items(candidates: list[dict], selected_rows: list[dict]) -> list[dict]:
    candidate_map = {row.get("item_code"): {**row, "selected": False} for row in candidates}
    for row in selected_rows:
        row = _campaign_item_row_dict(row)
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
    allowed = _allowed_selling_price_lists()
    if not allowed:
        return []
    return frappe.get_list(
        "Price List",
        filters={"enabled": 1, "selling": 1, "name": ["in", allowed]},
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
    return frappe.get_list(
        "Forecast Load Plan",
        fields=["name", "plan_label", "status", "departure_date"],
        order_by="modified desc",
        limit_page_length=100,
    )


def _price_list_item_codes(
    price_list: str | None,
    supplier_payment_mode: str | None = None,
    allowed_price_lists: list[str] | None = None,
) -> list[str]:
    allowed_price_lists = allowed_price_lists if allowed_price_lists is not None else _allowed_selling_price_lists()
    if not allowed_price_lists:
        return []
    price_list = _validate_campaign_price_list(price_list, required=False)
    filters: dict[str, Any] = {"selling": 1}
    filters["price_list"] = price_list if price_list else ["in", allowed_price_lists]
    if supplier_payment_mode and _has_field("Item Price", "custom_supplier_payment_mode"):
        filters["custom_supplier_payment_mode"] = supplier_payment_mode
    return frappe.get_all("Item Price", filters=filters, pluck="item_code", limit_page_length=0)
