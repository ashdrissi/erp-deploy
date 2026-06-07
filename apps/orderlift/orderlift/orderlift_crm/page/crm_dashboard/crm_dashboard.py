from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, now_datetime, nowdate

from orderlift.company_scope import company_field_for
from orderlift.menu_access import resolve_current_company, user_can_access_menu_key, user_can_access_page
from orderlift.orderlift_crm.company_business_type import get_company_business_type_names
from orderlift.orderlift_sales import reporting


def _first_existing(*doctypes):
    for doctype in doctypes:
        if frappe.db.exists("DocType", doctype):
            return doctype
    return None


LEAD_DOTYPE = _first_existing("CRM Lead", "Lead")
OPPORTUNITY_DOCTYPE = _first_existing("Opportunity")
CUSTOMER_DOCTYPE = _first_existing("Customer")
CONTACT_DOCTYPE = _first_existing("Contact")
SEGMENT_ENGINE_DOCTYPE = _first_existing("Customer Segmentation Engine")
NO_COMPANY_ACCESS_VALUE = "__orderlift_no_company_access__"
DASHBOARD_ADMIN_ROLES = {"Orderlift Admin", "Administrator", "System Manager", "Developer"}


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_docs": _get_recent_docs(),
        "alerts": _get_alerts(),
        "pipeline": _get_pipeline_breakdown(),
        "customer_mix": _get_customer_mix(),
        "opportunity_business_types": _get_opportunity_business_type_summary(),
        "opportunity_companies": _get_opportunity_company_summary(),
        "recent_communications": _get_recent_communications(),
        "upcoming_schedule": _get_upcoming_schedule(),
        "shortcuts": _get_shortcuts(),
    }


def _shortcut_definitions() -> list[dict]:
    return [
        {"icon": "plus", "label": _("New Lead"), "url": "/app/lead/new-lead-1", "variant": "primary", "doctype": "Lead", "ptype": "create", "menu_key": "crm.lead"},
        {"icon": "opportunity", "label": _("Opportunities"), "url": "/app/opportunity", "variant": "default", "doctype": "Opportunity", "menu_key": "crm.opportunity"},
        {"icon": "opportunity", "label": _("Prospects"), "url": "/app/prospect", "variant": "default", "doctype": "Prospect", "menu_key": "crm.prospect"},
        {"icon": "customer", "label": _("Customers"), "url": "/app/customer", "variant": "default", "doctype": "Customer", "menu_key": "crm.customer"},
        {"icon": "contact", "label": _("Contacts"), "url": "/app/contact", "variant": "default", "doctype": "Contact"},
        {"icon": "quote", "label": _("Quotations"), "url": "/app/quotation", "variant": "default", "doctype": "Quotation", "menu_key": "sales.quotation"},
        {"icon": "segment", "label": _("Segmentation"), "url": "/app/customer-segmentation-workspace", "variant": "default", "page": "customer-segmentation-workspace", "menu_key": "policies.customer_segmentation", "admin_only": True},
        {"icon": "communication", "label": _("Campaign Manager"), "url": "/app/campaign-manager", "variant": "default", "page": "campaign-manager", "menu_key": "crm.campaign_manager"},
        {"icon": "plus", "label": _("Campaign Builder"), "url": "/app/campaign-editor", "variant": "default", "page": "campaign-editor", "menu_key": "crm.campaign_builder"},
        {"icon": "calendar", "label": _("Opportunity Pipeline"), "url": "/app/opportunity-pipeline", "variant": "default", "page": "opportunity-pipeline", "menu_key": "crm.opportunity_pipeline"},
        {"icon": "calendar", "label": _("Project Pipeline"), "url": "/app/project-pipeline", "variant": "default", "page": "project-pipeline"},
        {"icon": "quote", "label": _("Sales Order Pipeline"), "url": "/app/sales-order-pipeline", "variant": "default", "page": "sales-order-pipeline"},
        {"icon": "segment", "label": _("Status Control"), "url": "/app/status-control", "variant": "default", "page": "status-control", "menu_key": "administration.status_control", "admin_only": True},
    ]


def _get_shortcuts() -> list[dict]:
    return [
        {key: shortcut[key] for key in ["icon", "label", "url", "variant"]}
        for shortcut in _shortcut_definitions()
        if _shortcut_allowed(shortcut)
    ]


def _shortcut_allowed(shortcut: dict) -> bool:
    if shortcut.get("admin_only") and not _is_dashboard_admin_user():
        return False
    menu_key = shortcut.get("menu_key")
    if menu_key and not user_can_access_menu_key(menu_key):
        return False
    page = shortcut.get("page")
    if page and not user_can_access_page(page):
        return False
    doctype = shortcut.get("doctype")
    if doctype and frappe.db.exists("DocType", doctype):
        return frappe.has_permission(doctype, shortcut.get("ptype") or "read")
    return True


def _crm_reference_doctypes():
    doctypes = []
    for doctype in [LEAD_DOTYPE, OPPORTUNITY_DOCTYPE, "Prospect", CUSTOMER_DOCTYPE, CONTACT_DOCTYPE]:
        if doctype and frappe.db.exists("DocType", doctype):
            doctypes.append(doctype)
    return doctypes


def _get_kpis():
    first_day = get_first_day(nowdate())
    opportunity_rows = _opportunity_rows()
    gained_rows = [row for row in opportunity_rows if row.get("sales_stage") == "Won / Project"]
    active_rows = [row for row in opportunity_rows if row.get("sales_stage") not in {"Won / Project", "Lost"} and row.get("status") != "Lost"]
    leads_total = _scoped_count(LEAD_DOTYPE) if LEAD_DOTYPE else 0
    opportunities_total = _scoped_count(OPPORTUNITY_DOCTYPE) if OPPORTUNITY_DOCTYPE else 0
    prospects_total = _scoped_count("Prospect") if frappe.db.exists("DocType", "Prospect") else 0
    customers_total = _scoped_count(CUSTOMER_DOCTYPE, {"disabled": 0}) if CUSTOMER_DOCTYPE else 0
    contacts_total = len(_visible_contact_names()) if CONTACT_DOCTYPE else 0
    quotations_month = _scoped_count("Quotation", {"creation": [">=", first_day]}) if frappe.db.exists("DocType", "Quotation") else 0
    quotations_month_amounts = _document_amount_rows("Quotation", {"creation": [">=", first_day]})
    sales_orders_month = _scoped_count("Sales Order", {"creation": [">=", first_day]}) if frappe.db.exists("DocType", "Sales Order") else 0
    sales_orders_month_amounts = _document_amount_rows("Sales Order", {"creation": [">=", first_day]})
    segment_engines = _scoped_count(SEGMENT_ENGINE_DOCTYPE) if SEGMENT_ENGINE_DOCTYPE and _is_dashboard_admin_user() else 0

    return {
        "leads_total": int(leads_total or 0),
        "opportunities_total": int(opportunities_total or 0),
        "prospects_total": int(prospects_total or 0),
        "customers_total": int(customers_total or 0),
        "contacts_total": int(contacts_total or 0),
        "quotations_month": int(quotations_month or 0),
        "quotations_month_amounts": quotations_month_amounts,
        "sales_orders_month": int(sales_orders_month or 0),
        "sales_orders_month_amounts": sales_orders_month_amounts,
        "segment_engines": int(segment_engines or 0),
        "gained_opportunities": len(gained_rows),
        "active_opportunities": len(active_rows),
        "pipeline_amounts": _amount_rows(active_rows),
        "gained_amounts": _amount_rows(gained_rows),
    }


def _opportunity_rows() -> list[dict]:
    if not OPPORTUNITY_DOCTYPE:
        return []
    fields = ["name", "status", "opportunity_amount"]
    for fieldname in ["sales_stage", "company", "currency", "custom_crm_business_type", "custom_crm_segment"]:
        if reporting.has_field(OPPORTUNITY_DOCTYPE, fieldname):
            fields.append(fieldname)
    rows = _scoped_get_all(OPPORTUNITY_DOCTYPE, fields=fields, limit_page_length=0)
    out = []
    for row in rows:
        company = row.get("company") or ""
        out.append(
            {
                "name": row.get("name"),
                "status": row.get("status") or "",
                "sales_stage": row.get("sales_stage") or row.get("status") or _("No Status"),
                "company": company,
                "currency": row.get("currency") or reporting.company_currency(company) or "",
                "amount": flt(row.get("opportunity_amount") or 0),
                "business_type": reporting.normalize_business_type(row.get("custom_crm_business_type")),
                "crm_segment": row.get("custom_crm_segment") or "",
            }
        )
    return out


def _amount_rows(rows: list[dict]) -> list[dict]:
    totals = reporting.empty_currency_totals()
    for row in rows:
        reporting.add_amount(totals, row.get("currency"), "revenue", row.get("amount"))
    return [
        {"currency": row["currency"], "amount": row["revenue"]}
        for row in reporting.currency_totals_to_rows(totals)
    ]


def _document_amount_rows(doctype: str, filters: dict) -> list[dict]:
    if not frappe.db.exists("DocType", doctype):
        return []
    fields = []
    for fieldname in ["grand_total", "currency"]:
        if reporting.has_field(doctype, fieldname):
            fields.append(fieldname)
    if "grand_total" not in fields:
        return []
    rows = _scoped_get_all(doctype, filters=filters, fields=fields, limit_page_length=0)
    totals = reporting.empty_currency_totals()
    for row in rows:
        reporting.add_amount(totals, row.get("currency"), "revenue", row.get("grand_total"))
    return [
        {"currency": row["currency"], "amount": row["revenue"]}
        for row in reporting.currency_totals_to_rows(totals)
    ]


def _get_opportunity_business_type_summary():
    visible_business_types = _visible_business_type_buckets()
    rows = {label: _opportunity_summary_row(label) for label in visible_business_types}
    for opportunity in _opportunity_rows():
        business_type = reporting.normalize_business_type(opportunity.get("business_type"))
        if business_type not in rows:
            continue
        row = rows[business_type]
        _add_opportunity_to_summary(row, opportunity)
    return [_serialize_opportunity_summary(row) for row in rows.values()]


def _get_opportunity_company_summary():
    companies = _visible_reporting_companies()
    rows = {company["name"]: _opportunity_summary_row(company["name"], company.get("currency")) for company in companies}
    if not rows:
        return []
    for opportunity in _opportunity_rows():
        if opportunity.get("company") not in rows:
            continue
        _add_opportunity_to_summary(rows[opportunity["company"]], opportunity)
    return [_serialize_opportunity_summary(row) for row in rows.values()]


def _opportunity_summary_row(label: str, currency: str | None = None) -> dict:
    return {
        "label": label,
        "currency": currency or "",
        "opportunities": 0,
        "gained": 0,
        "active": 0,
        "pipeline_amounts": reporting.empty_currency_totals(),
        "gained_amounts": reporting.empty_currency_totals(),
    }


def _add_opportunity_to_summary(row: dict, opportunity: dict) -> None:
    row["opportunities"] += 1
    if opportunity.get("sales_stage") == "Won / Project":
        row["gained"] += 1
        reporting.add_amount(row["gained_amounts"], opportunity.get("currency"), "revenue", opportunity.get("amount"))
    elif opportunity.get("sales_stage") != "Lost" and opportunity.get("status") != "Lost":
        row["active"] += 1
        reporting.add_amount(row["pipeline_amounts"], opportunity.get("currency"), "revenue", opportunity.get("amount"))


def _serialize_opportunity_summary(row: dict) -> dict:
    return {
        "label": row["label"],
        "currency": row.get("currency") or "",
        "opportunities": row.get("opportunities") or 0,
        "gained": row.get("gained") or 0,
        "active": row.get("active") or 0,
        "pipeline_amounts": _amounts_from_totals(row.get("pipeline_amounts") or {}),
        "gained_amounts": _amounts_from_totals(row.get("gained_amounts") or {}),
    }


def _amounts_from_totals(totals: dict) -> list[dict]:
    return [
        {"currency": amount_row["currency"], "amount": amount_row["revenue"]}
        for amount_row in reporting.currency_totals_to_rows(totals)
    ]


def _get_recent_docs():
    rows = []

    def append_docs(doctype, fields, label_field, meta_label, route, limit=4):
        if not doctype:
            return
        for row in _scoped_get_all(
            doctype,
            fields=["name", *fields, "modified"],
            order_by="modified desc",
            limit_page_length=limit,
        ):
            rows.append(
                {
                    "label": row.get(label_field) or row.name,
                    "meta": _(meta_label),
                    "link": f"/app/{route}/{row.name}",
                    "modified": row.get("modified"),
                }
            )

    append_docs(LEAD_DOTYPE, ["lead_name", "company_name", "status"], "lead_name", "Lead", LEAD_DOTYPE.replace(" ", "-").lower())
    append_docs(OPPORTUNITY_DOCTYPE, ["party_name", "status"], "name", "Opportunity", "opportunity")
    append_docs(CUSTOMER_DOCTYPE, ["customer_name", "territory"], "customer_name", "Customer", "customer")

    rows.sort(key=lambda row: row.get("modified") or "", reverse=True)
    return rows[:10]


def _get_alerts():
    alerts = []

    if LEAD_DOTYPE:
        stale_leads = _scoped_count(LEAD_DOTYPE, {"modified": ["<", add_days(nowdate(), -14)]})
        if stale_leads:
            alerts.append(
                {
                    "level": "warn",
                    "title": _("{0} lead(s) have not been touched in 14+ days").format(stale_leads),
                    "message": _("Review stale pipeline entries and progress them or close them out."),
                    "link": f"/app/{LEAD_DOTYPE.replace(' ', '-').lower()}",
                }
            )

    if OPPORTUNITY_DOCTYPE:
        open_opportunities = _scoped_count(OPPORTUNITY_DOCTYPE, {"status": ["not in", ["Closed", "Lost"]]})
        if open_opportunities:
            alerts.append(
                {
                    "level": "info",
                    "title": _("{0} open opportunit(y/ies)").format(open_opportunities),
                    "message": _("Follow up on active deals and convert the qualified ones to quotations."),
                    "link": "/app/opportunity",
                }
            )

    if CUSTOMER_DOCTYPE and CONTACT_DOCTYPE:
        contacts_total = len(_visible_contact_names())
        customers_total = _scoped_count(CUSTOMER_DOCTYPE, {"disabled": 0})
        if customers_total > contacts_total:
            alerts.append(
                {
                    "level": "warn",
                    "title": _("Some customers may still be missing contacts"),
                    "message": _("Customer count is higher than contact count; review customer contact completeness."),
                    "link": "/app/customer",
                }
            )

    if SEGMENT_ENGINE_DOCTYPE and _is_dashboard_admin_user() and _scoped_count(SEGMENT_ENGINE_DOCTYPE) == 0:
        alerts.append(
            {
                "level": "info",
                "title": _("No customer segmentation engines configured"),
                "message": _("Dynamic customer tiering is available but not currently configured."),
                "link": "/app/customer-segmentation-workspace",
            }
        )

    return alerts[:6]


def _get_pipeline_breakdown():
    sections = []

    if LEAD_DOTYPE:
        lead_rows = _scoped_get_all(LEAD_DOTYPE, fields=["status"], limit_page_length=500)
        lead_counts = Counter((row.get("status") or _("No Status")) for row in lead_rows)
        sections.append(
            {
                "label": _("Lead Pipeline"),
                "items": [
                    {"label": status, "value": count}
                    for status, count in lead_counts.most_common(6)
                ],
            }
        )

    if OPPORTUNITY_DOCTYPE:
        opportunity_rows = _scoped_get_all(OPPORTUNITY_DOCTYPE, fields=["status"], limit_page_length=500)
        opportunity_counts = Counter((row.get("status") or _("No Status")) for row in opportunity_rows)
        sections.append(
            {
                "label": _("Opportunity Pipeline"),
                "items": [
                    {"label": status, "value": count}
                    for status, count in opportunity_counts.most_common(6)
                ],
            }
        )

    if frappe.db.exists("DocType", "Prospect"):
        prospect_count = _scoped_count("Prospect")
        sections.append(
            {
                "label": _("Prospects"),
                "items": [{"label": _("Prospect Records"), "value": prospect_count}],
            }
        )

    return sections


def _get_customer_mix():
    if not _is_dashboard_admin_user():
        return {"hidden": True, "groups": [], "territories": []}
    if not CUSTOMER_DOCTYPE:
        return {"groups": [], "territories": []}

    customer_rows = _scoped_get_all(
        CUSTOMER_DOCTYPE,
        fields=[field for field in ["name", "territory"] if frappe.get_meta(CUSTOMER_DOCTYPE).get_field(field)],
        limit_page_length=1000,
    )
    segment_counts = Counter()
    customer_names = [row.get("name") for row in customer_rows if row.get("name")]
    if customer_names and frappe.db.exists("DocType", "CRM Segment Assignment"):
        rows = frappe.get_all(
            "CRM Segment Assignment",
            filters={"parenttype": CUSTOMER_DOCTYPE, "parent": ["in", customer_names]},
            fields=["business_type", "segment"],
            limit_page_length=0,
        )
        segment_counts = Counter(
            " / ".join([value for value in [row.get("business_type"), row.get("segment")] if value]) or _("Unassigned")
            for row in rows
        )
    territory_counts = Counter((row.get("territory") or _("Unassigned")) for row in customer_rows)

    return {
        "groups": [{"label": label, "value": value} for label, value in segment_counts.most_common(6)],
        "territories": [{"label": label, "value": value} for label, value in territory_counts.most_common(6)],
    }


def _get_recent_communications():
    if not frappe.db.exists("DocType", "Communication"):
        return []

    crm_doctypes = _crm_reference_doctypes()
    rows = frappe.get_all(
        "Communication",
        filters={"reference_doctype": ["in", crm_doctypes]} if crm_doctypes else None,
        fields=[
            "name",
            "subject",
            "reference_doctype",
            "reference_name",
            "communication_medium",
            "sent_or_received",
            "sender_full_name",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=30,
    )
    rows = [row for row in rows if _reference_allowed(row.get("reference_doctype"), row.get("reference_name"))][:6]
    return [
        {
            "subject": row.get("subject") or row.name,
            "meta": " · ".join(
                part for part in [row.get("communication_medium"), row.get("sent_or_received"), row.get("sender_full_name")] if part
            ),
            "link": f"/app/communication/{row.name}",
            "reference": " / ".join(part for part in [row.get("reference_doctype"), row.get("reference_name")] if part),
        }
        for row in rows
    ]


def _get_upcoming_schedule():
    if not frappe.db.exists("DocType", "Event"):
        return []

    crm_doctypes = _crm_reference_doctypes()
    filters = {"status": ["not in", ["Completed", "Closed", "Cancelled"]], "starts_on": [">=", now_datetime()]}
    if crm_doctypes:
        filters["reference_doctype"] = ["in", crm_doctypes]

    rows = frappe.get_all(
        "Event",
        filters=filters,
        fields=["name", "subject", "starts_on", "reference_doctype", "reference_docname", "event_type"],
        order_by="starts_on asc",
        limit_page_length=30,
    )
    rows = [row for row in rows if _reference_allowed(row.get("reference_doctype"), row.get("reference_docname"))][:6]
    return [
        {
            "subject": row.get("subject") or row.name,
            "starts_on": str(row.get("starts_on") or ""),
            "reference": " / ".join(part for part in [row.get("reference_doctype"), row.get("reference_docname")] if part),
            "meta": row.get("event_type") or "",
            "link": f"/app/event/{row.name}",
        }
        for row in rows
    ]


def _active_company_names() -> list[str]:
    company = resolve_current_company(user=frappe.session.user)
    return [company] if company else []


def _is_dashboard_admin_user() -> bool:
    return frappe.session.user == "Administrator" or bool(set(frappe.get_roles() or []).intersection(DASHBOARD_ADMIN_ROLES))


def _scoped_get_all(doctype: str, filters: dict | None = None, **kwargs):
    return frappe.get_all(doctype, filters=_scoped_filters(doctype, filters), **kwargs)


def _scoped_count(doctype: str, filters: dict | None = None) -> int:
    if not doctype or not frappe.db.exists("DocType", doctype):
        return 0
    return int(frappe.db.count(doctype, _scoped_filters(doctype, filters)) or 0)


def _scoped_filters(doctype: str, filters: dict | None = None) -> dict:
    filters = dict(filters or {})
    field = "name" if doctype == "Company" else company_field_for(doctype)
    if doctype != "Company" and not reporting.has_field(doctype, field):
        return filters
    companies = _active_company_names()
    filters[field] = ["in", companies] if companies else NO_COMPANY_ACCESS_VALUE
    return filters


def _visible_reporting_companies() -> list[dict]:
    active = set(_active_company_names())
    return [company for company in reporting.get_reporting_companies() if company.get("name") in active]


def _visible_business_type_buckets() -> list[str]:
    buckets = []
    for company in _active_company_names():
        for business_type in get_company_business_type_names(company):
            business_type = reporting.normalize_business_type(business_type)
            if business_type != "Unassigned" and business_type not in buckets:
                buckets.append(business_type)
    return buckets or list(reporting.BUSINESS_TYPE_BUCKETS)


def _visible_crm_names_by_doctype() -> dict[str, set[str]]:
    names_by_doctype = {}
    for doctype in _crm_reference_doctypes():
        if doctype == CONTACT_DOCTYPE:
            continue
        names_by_doctype[doctype] = {
            row.get("name") for row in _scoped_get_all(doctype, fields=["name"], limit_page_length=0) if row.get("name")
        }
    return names_by_doctype


def _visible_contact_names() -> set[str]:
    if not CONTACT_DOCTYPE or not frappe.db.exists("DocType", "Dynamic Link"):
        return set()
    names_by_doctype = _visible_crm_names_by_doctype()
    if not names_by_doctype:
        return set()
    rows = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": CONTACT_DOCTYPE, "link_doctype": ["in", list(names_by_doctype)]},
        fields=["parent", "link_doctype", "link_name"],
        limit_page_length=0,
    )
    return {
        row.get("parent")
        for row in rows
        if row.get("parent") and row.get("link_name") in names_by_doctype.get(row.get("link_doctype"), set())
    }


def _reference_allowed(reference_doctype: str | None, reference_name: str | None) -> bool:
    reference_doctype = (reference_doctype or "").strip()
    reference_name = (reference_name or "").strip()
    if not reference_doctype or not reference_name:
        return False
    if reference_doctype == CONTACT_DOCTYPE:
        return reference_name in _visible_contact_names()
    field = company_field_for(reference_doctype)
    if not reporting.has_field(reference_doctype, field):
        return False
    company = frappe.db.get_value(reference_doctype, reference_name, field)
    return company in set(_active_company_names())
