from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, now_datetime, nowdate


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


@frappe.whitelist()
def get_dashboard_data():
    return {
        "kpis": _get_kpis(),
        "recent_docs": _get_recent_docs(),
        "alerts": _get_alerts(),
        "pipeline": _get_pipeline_breakdown(),
        "customer_mix": _get_customer_mix(),
        "recent_communications": _get_recent_communications(),
        "upcoming_schedule": _get_upcoming_schedule(),
    }


def _crm_reference_doctypes():
    doctypes = []
    for doctype in [LEAD_DOTYPE, OPPORTUNITY_DOCTYPE, "Prospect", CUSTOMER_DOCTYPE, CONTACT_DOCTYPE]:
        if doctype and frappe.db.exists("DocType", doctype):
            doctypes.append(doctype)
    return doctypes


def _get_kpis():
    first_day = get_first_day(nowdate())
    leads_total = frappe.db.count(LEAD_DOTYPE) if LEAD_DOTYPE else 0
    opportunities_total = frappe.db.count(OPPORTUNITY_DOCTYPE) if OPPORTUNITY_DOCTYPE else 0
    prospects_total = frappe.db.count("Prospect") if frappe.db.exists("DocType", "Prospect") else 0
    customers_total = frappe.db.count(CUSTOMER_DOCTYPE, {"disabled": 0}) if CUSTOMER_DOCTYPE else 0
    contacts_total = frappe.db.count(CONTACT_DOCTYPE) if CONTACT_DOCTYPE else 0
    quotations_month = frappe.db.count("Quotation", {"creation": [">=", first_day]}) if frappe.db.exists("DocType", "Quotation") else 0
    segment_engines = frappe.db.count(SEGMENT_ENGINE_DOCTYPE) if SEGMENT_ENGINE_DOCTYPE else 0

    return {
        "leads_total": int(leads_total or 0),
        "opportunities_total": int(opportunities_total or 0),
        "prospects_total": int(prospects_total or 0),
        "customers_total": int(customers_total or 0),
        "contacts_total": int(contacts_total or 0),
        "quotations_month": int(quotations_month or 0),
        "segment_engines": int(segment_engines or 0),
    }


def _get_recent_docs():
    rows = []

    def append_docs(doctype, fields, label_field, meta_label, route, limit=4):
        if not doctype:
            return
        for row in frappe.get_all(
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
        stale_leads = frappe.db.count(LEAD_DOTYPE, {"modified": ["<", add_days(nowdate(), -14)]})
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
        open_opportunities = frappe.db.count(OPPORTUNITY_DOCTYPE, {"status": ["not in", ["Closed", "Lost"]]})
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
        contacts_total = frappe.db.count(CONTACT_DOCTYPE)
        customers_total = frappe.db.count(CUSTOMER_DOCTYPE, {"disabled": 0})
        if customers_total > contacts_total:
            alerts.append(
                {
                    "level": "warn",
                    "title": _("Some customers may still be missing contacts"),
                    "message": _("Customer count is higher than contact count; review customer contact completeness."),
                    "link": "/app/customer",
                }
            )

    if SEGMENT_ENGINE_DOCTYPE and frappe.db.count(SEGMENT_ENGINE_DOCTYPE) == 0:
        alerts.append(
            {
                "level": "info",
                "title": _("No customer segmentation engines configured"),
                "message": _("Dynamic customer tiering is available but not currently configured."),
                "link": "/app/customer-segmentation-engine",
            }
        )

    return alerts[:6]


def _get_pipeline_breakdown():
    sections = []

    if LEAD_DOTYPE:
        lead_rows = frappe.get_all(LEAD_DOTYPE, fields=["status"], limit_page_length=500)
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
        opportunity_rows = frappe.get_all(OPPORTUNITY_DOCTYPE, fields=["status"], limit_page_length=500)
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
        prospect_count = frappe.db.count("Prospect")
        sections.append(
            {
                "label": _("Prospects"),
                "items": [{"label": _("Prospect Records"), "value": prospect_count}],
            }
        )

    return sections


def _get_customer_mix():
    if not CUSTOMER_DOCTYPE:
        return {"groups": [], "territories": []}

    customer_rows = frappe.get_all(
        CUSTOMER_DOCTYPE,
        fields=[field for field in ["customer_group", "territory"] if frappe.get_meta(CUSTOMER_DOCTYPE).get_field(field)],
        limit_page_length=1000,
    )
    group_counts = Counter((row.get("customer_group") or _("Unassigned")) for row in customer_rows)
    territory_counts = Counter((row.get("territory") or _("Unassigned")) for row in customer_rows)

    return {
        "groups": [{"label": label, "value": value} for label, value in group_counts.most_common(6)],
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
        limit_page_length=6,
    )
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
        limit_page_length=6,
    )
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
