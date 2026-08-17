from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from orderlift.menu_access import get_allowed_companies
from orderlift.role_capabilities import CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL, user_has_capability


PARTY_DOCTYPES = {"Lead", "Prospect", "Customer", "Supplier"}
PARTY_NAME_FIELDS = {
    "Customer": ("customer_name",),
    "Lead": ("company_name", "lead_name"),
    "Prospect": ("company_name",),
    "Supplier": ("supplier_name",),
}
PARTY_TAX_ID_FIELDS = {
    "Customer": "tax_id",
    "Lead": "custom_tax_id",
    "Prospect": "custom_tax_id",
    "Supplier": "tax_id",
}
DUPLICATE_PARTY_GROUPS = {
    "Customer": ("Customer", "Lead", "Prospect"),
    "Lead": ("Customer", "Lead", "Prospect"),
    "Prospect": ("Customer", "Lead", "Prospect"),
    "Supplier": ("Supplier",),
}
READ_PERMISSION_TYPES = {None, "read", "select", "report", "print", "email"}


def prepare_party(doc, method=None) -> None:
    if getattr(doc, "doctype", None) not in PARTY_DOCTYPES:
        return
    _validate_internal_companies(doc)
    _sync_primary_company(doc)
    _validate_unique_tax_id(doc)
    _validate_unique_party_name(doc)


def party_tax_id(doc) -> str:
    if not getattr(doc, "meta", None):
        return ""
    fieldname = PARTY_TAX_ID_FIELDS.get(getattr(doc, "doctype", None), "")
    if not fieldname:
        return ""
    if not doc.meta.get_field(fieldname):
        return ""
    return (doc.get(fieldname) or "").strip()


def party_has_company_access(party_type: str, party_name: str, company: str) -> bool:
    if party_type not in PARTY_DOCTYPES or not party_name or not company:
        return False
    internal_field = _internal_party_field(party_type)
    fields = ["custom_company", "represents_company"]
    if internal_field:
        fields.append(internal_field)
    values = frappe.db.get_value(party_type, party_name, fields, as_dict=True) or {}
    primary = values.get("custom_company") or ""
    represents_self = internal_field and values.get(internal_field) and values.get("represents_company") == company
    if primary == company and not represents_self:
        return True
    if not frappe.db.exists("DocType", "Party Internal Company Access"):
        return False
    return bool(
        frappe.db.exists(
            "Party Internal Company Access",
            {
                "parenttype": party_type,
                "parent": party_name,
                "parentfield": "custom_internal_company_access",
                "company": company,
            },
        )
    )


def add_party_company_access(
    party_type: str,
    party_name: str,
    company: str,
    *,
    approved_by: str | None = None,
) -> None:
    if party_type not in PARTY_DOCTYPES or not frappe.db.exists(party_type, party_name):
        frappe.throw(_("The selected party does not exist."))
    if not company or not frappe.db.exists("Company", company):
        frappe.throw(_("The selected internal company does not exist."))
    party = frappe.get_doc(party_type, party_name)
    if any((row.get("company") or "") == company for row in party.get("custom_internal_company_access") or []):
        return
    party.append(
        "custom_internal_company_access",
        {
            "company": company,
            "is_primary": 0,
            "approved_by": approved_by or frappe.session.user,
            "approved_on": now_datetime(),
        },
    )
    party.flags.ignore_orderlift_party_company_validation = True
    party.save(ignore_permissions=True)


@frappe.whitelist()
def get_party_workspace(party_type: str, party_name: str) -> dict:
    party = _get_permitted_party(party_type, party_name)
    return {
        "tax_id": party_tax_id(party),
        "addresses": _linked_addresses(party_type, party_name),
        "contacts": _linked_contacts(party_type, party_name),
        "deals": _linked_deals(party_type, party_name),
    }


@frappe.whitelist()
def save_party_address(party_type: str, party_name: str, values: str | dict) -> dict:
    party = _get_permitted_party(party_type, party_name, ptype="write")
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    address_name = (values.get("name") or "").strip()
    address = frappe.get_doc("Address", address_name) if address_name else frappe.new_doc("Address")
    if address_name:
        address.check_permission("write")
    elif not frappe.has_permission("Address", "create"):
        frappe.throw(_("You do not have permission to create an Address."), frappe.PermissionError)

    for fieldname in ("address_title", "address_type", "address_line1", "address_line2", "city", "state", "country", "pincode", "phone", "email_id"):
        if address.meta.get_field(fieldname):
            address.set(fieldname, values.get(fieldname) or "")
    if address.meta.get_field("is_primary_address"):
        address.is_primary_address = int(bool(values.get("is_primary_address")))
    if address.meta.get_field("is_shipping_address"):
        address.is_shipping_address = int(bool(values.get("is_shipping_address")))
    if address.meta.get_field("custom_is_site_address"):
        address.custom_is_site_address = int(bool(values.get("custom_is_site_address")))
    if not any(
        row.get("link_doctype") == party_type and row.get("link_name") == party_name
        for row in address.get("links") or []
    ):
        address.append("links", {"link_doctype": party_type, "link_name": party_name})
    address.save(ignore_permissions=False) if address_name else address.insert(ignore_permissions=False)
    return {"name": address.name, "addresses": _linked_addresses(party.doctype, party.name)}


@frappe.whitelist()
def save_party_contact(party_type: str, party_name: str, values: str | dict) -> dict:
    party = _get_permitted_party(party_type, party_name, ptype="write")
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    contact_name = (values.get("name") or "").strip()
    contact = frappe.get_doc("Contact", contact_name) if contact_name else frappe.new_doc("Contact")
    if contact_name:
        contact.check_permission("write")
    elif not frappe.has_permission("Contact", "create"):
        frappe.throw(_("You do not have permission to create a Contact."), frappe.PermissionError)

    contact.first_name = (values.get("first_name") or "").strip()
    contact.last_name = (values.get("last_name") or "").strip()
    contact.designation = (values.get("designation") or "").strip()
    contact.is_primary_contact = int(bool(values.get("is_primary_contact")))
    contact.set("email_ids", [])
    if (values.get("email_id") or "").strip():
        contact.append("email_ids", {"email_id": values.get("email_id").strip(), "is_primary": 1})
    contact.set("phone_nos", [])
    if (values.get("mobile_no") or "").strip():
        contact.append("phone_nos", {"phone": values.get("mobile_no").strip(), "is_primary_mobile_no": 1})
    if (values.get("phone") or "").strip() and values.get("phone").strip() != (values.get("mobile_no") or "").strip():
        contact.append("phone_nos", {"phone": values.get("phone").strip(), "is_primary_phone": 1})
    if not any(
        row.get("link_doctype") == party_type and row.get("link_name") == party_name
        for row in contact.get("links") or []
    ):
        contact.append("links", {"link_doctype": party_type, "link_name": party_name})
    contact.save(ignore_permissions=False) if contact_name else contact.insert(ignore_permissions=False)
    return {"name": contact.name, "contacts": _linked_contacts(party.doctype, party.name)}


@frappe.whitelist()
def check_party_duplicates(party_type: str, values: str | dict, party_name: str | None = None) -> list[dict]:
    if party_type not in PARTY_DOCTYPES:
        frappe.throw(_("Party Type must be Lead, Prospect, Customer, or Supplier."))
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    matches = []
    target = _normalized_identity(values)
    if not any(target.values()):
        return []
    for candidate_type in _duplicate_party_types(party_type):
        for candidate in _candidate_parties(candidate_type):
            if candidate_type == party_type and candidate.name == party_name:
                continue
            score, reasons = _duplicate_score(target, _normalized_identity(candidate))
            if score < 70:
                continue
            visible = bool(frappe.has_permission(candidate_type, "read", doc=candidate.name))
            matches.append(
                {
                    "party_type": candidate_type if visible else "",
                    "party_name": candidate.name if visible else "",
                    "display_name": _party_display_name(candidate, candidate_type) if visible else _("Existing party in another internal company"),
                    "company": candidate.get("custom_company") if visible else "",
                    "score": score,
                    "reasons": reasons,
                    "requires_access_request": not visible,
                }
            )
    return sorted(matches, key=lambda row: (-row["score"], row["display_name"]))[:10]


@frappe.whitelist()
def request_duplicate_reuse(
    values: str | dict,
    requested_company: str,
    reason: str | None = None,
    party_type: str | None = None,
) -> dict:
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    matches = []
    target = _normalized_identity(values)
    candidate_types = _duplicate_party_types(party_type or "Customer")
    for candidate_type in candidate_types:
        for candidate in _candidate_parties(candidate_type):
            score, _reasons = _duplicate_score(target, _normalized_identity(candidate))
            if score >= 70:
                matches.append((score, candidate_type, candidate))
    if not matches:
        frappe.throw(_("No matching party was found."))
    _score, party_type, party = sorted(matches, key=lambda row: -row[0])[0]
    if party_has_company_access(party_type, party.name, requested_company):
        return {"status": "Already Available", "party_type": party_type, "party_name": party.name}
    existing = frappe.db.get_value(
        "Party Company Access Request",
        {
            "party_type": party_type,
            "party_name": party.name,
            "requested_company": requested_company,
            "status": "Pending",
        },
        "name",
    )
    if existing:
        return {"name": existing, "status": "Pending"}
    request = frappe.new_doc("Party Company Access Request")
    request.party_type = party_type
    request.party_name = party.name
    request.source_company = party.get("custom_company") or ""
    request.requested_company = requested_company
    request.request_reason = reason or ""
    request.insert(ignore_permissions=True)
    return {"name": request.name, "status": request.status}


@frappe.whitelist()
def convert_party_to_customer(party_type: str, party_name: str) -> dict:
    if party_type not in {"Lead", "Prospect"}:
        frappe.throw(_("Only a Lead or Prospect can be converted to Customer."))
    source = _get_permitted_party(party_type, party_name, ptype="write")
    if not frappe.has_permission("Customer", "create"):
        frappe.throw(_("You do not have permission to create a Customer."), frappe.PermissionError)
    from orderlift.orderlift_crm.party_propagation import ensure_customer_for_party

    customer = ensure_customer_for_party(party_type, party_name, source_doc=source)
    return {
        "name": customer.name,
        "route": ["Form", "Customer", customer.name],
        "converted_from_type": party_type,
        "converted_from_name": party_name,
    }


@frappe.whitelist()
def prepare_opportunity_from_party(source_name: str, party_type: str):
    party = _get_permitted_party(party_type, source_name)
    if party_type == "Lead":
        from erpnext.crm.doctype.lead.lead import make_opportunity
    elif party_type == "Prospect":
        from erpnext.crm.doctype.prospect.prospect import make_opportunity
    else:
        from erpnext.selling.doctype.customer.customer import make_opportunity
    target = make_opportunity(party.name)
    from orderlift.orderlift_crm.party_propagation import apply_party_context_to_opportunity, resolve_party_context

    target.company = party.get("custom_company") or target.get("company") or ""
    apply_party_context_to_opportunity(target, resolve_party_context(party_type, party.name), overwrite=True)
    return target


@frappe.whitelist()
def create_opportunity_from_party(party_type: str, party_name: str) -> dict:
    party = _get_permitted_party(party_type, party_name)
    if not frappe.has_permission("Opportunity", "create"):
        frappe.throw(_("You do not have permission to create an Opportunity."), frappe.PermissionError)

    from frappe.utils import nowdate

    from orderlift.orderlift_crm.party_propagation import apply_party_context_to_opportunity, resolve_party_context

    doc = frappe.new_doc("Opportunity")
    if doc.meta.get_field("naming_series"):
        doc.naming_series = frappe.get_meta("Opportunity").get_field("naming_series").default or "CRM-OPP-.YYYY.-"
    doc.opportunity_from = party_type
    doc.party_name = party.name
    doc.customer_name = _party_display_name(party, party_type)
    doc.title = doc.customer_name
    doc.status = "Open"
    if doc.meta.get_field("sales_stage"):
        doc.sales_stage = _default_sales_stage()
    if doc.meta.get_field("opportunity_type"):
        doc.opportunity_type = _default_opportunity_type()
    doc.company = party.get("custom_company") or party.get("company") or ""
    if doc.meta.get_field("transaction_date"):
        doc.transaction_date = nowdate()
    if doc.meta.get_field("opportunity_owner"):
        doc.opportunity_owner = frappe.session.user
    apply_party_context_to_opportunity(doc, resolve_party_context(party_type, party.name), overwrite=True)
    doc.insert(ignore_permissions=False)
    return {"name": doc.name, "route": ["Form", "Opportunity", doc.name]}


def party_access_request_query(user: str | None = None) -> str:
    user = user or frappe.session.user
    table = "`tabParty Company Access Request`"
    if user_has_capability(CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL, user=user):
        companies = get_allowed_companies(user)
        if not companies:
            return f"{table}.requested_by = {frappe.db.escape(user)}"
        escaped = ", ".join(frappe.db.escape(company) for company in companies)
        return f"({table}.requested_by = {frappe.db.escape(user)} or {table}.requested_company in ({escaped}))"
    return f"{table}.requested_by = {frappe.db.escape(user)}"


def has_party_access_request_permission(doc, ptype=None, user=None, permission_type=None):
    user = user or frappe.session.user
    permission_type = permission_type or ptype
    if user_has_capability(CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL, user=user):
        return True
    if permission_type == "create" and getattr(doc, "is_new", lambda: False)():
        return True
    return bool(doc.get("requested_by") == user and permission_type in READ_PERMISSION_TYPES)


def _sync_primary_company(doc) -> None:
    primary = (doc.get("custom_company") or "").strip()
    if not primary and doc.meta.get_field("company"):
        primary = (doc.get("company") or "").strip()
        if primary:
            doc.custom_company = primary
    if primary and doc.meta.get_field("company"):
        doc.company = primary


def _validate_unique_tax_id(doc) -> None:
    if getattr(doc.flags, "ignore_orderlift_party_duplicate_check", False):
        return
    tax_id = party_tax_id(doc)
    if not tax_id:
        return
    for party_type in _duplicate_party_types(doc.doctype):
        fieldname = PARTY_TAX_ID_FIELDS[party_type]
        if not frappe.get_meta(party_type).get_field(fieldname):
            continue
        duplicate = frappe.db.get_value(party_type, {fieldname: tax_id}, "name")
        if duplicate and not (party_type == doc.doctype and duplicate == doc.name) and not _same_party_lineage(doc, party_type, duplicate):
            frappe.throw(_("ICE / Tax ID {0} already belongs to {1} {2}.").format(tax_id, party_type, duplicate))


def _validate_unique_party_name(doc) -> None:
    if getattr(doc.flags, "ignore_orderlift_party_duplicate_check", False):
        return
    target_name = _normalized_identity(doc).get("name")
    if not target_name:
        return
    if not doc.is_new():
        previous = frappe.db.get_value(
            doc.doctype,
            doc.name,
            list(PARTY_NAME_FIELDS[doc.doctype]),
            as_dict=True,
        )
        if previous and _normalized_identity(previous).get("name") == target_name:
            return
    for party_type in _duplicate_party_types(doc.doctype):
        for candidate in _candidate_parties(party_type):
            if party_type == doc.doctype and candidate.name == doc.name:
                continue
            if _same_party_lineage(doc, party_type, candidate.name):
                continue
            if _normalized_identity(candidate).get("name") != target_name:
                continue
            if frappe.has_permission(party_type, "read", doc=candidate.name):
                frappe.throw(
                    _("A {0} named {1} already exists ({2}). Open and reuse it instead of creating a duplicate.").format(
                        party_type,
                        _party_display_name(candidate, party_type),
                        candidate.name,
                    )
                )
            frappe.throw(
                _("A party with this name already exists in another internal company. Request access instead of creating a duplicate.")
            )


def _duplicate_party_types(party_type: str) -> tuple[str, ...]:
    if party_type not in DUPLICATE_PARTY_GROUPS:
        frappe.throw(_("Party Type must be Lead, Prospect, Customer, or Supplier."))
    return DUPLICATE_PARTY_GROUPS[party_type]


def _same_party_lineage(doc, other_type: str, other_name: str) -> bool:
    if doc.doctype == "Lead" and other_type == "Customer":
        return (doc.get("customer") or "") == other_name
    if doc.doctype == "Customer" and other_type == "Lead":
        return (doc.get("lead_name") or "") == other_name
    if doc.doctype == "Customer" and other_type == "Prospect":
        return (doc.get("prospect_name") or "") == other_name
    if doc.doctype == "Prospect" and other_type == "Customer":
        return frappe.db.get_value("Customer", other_name, "prospect_name") == doc.name
    return False


def _validate_internal_companies(doc) -> None:
    rows = doc.get("custom_internal_company_access") or []
    if _is_internal_orderlift_party(doc):
        represented_company = (doc.get("represents_company") or "").strip()
        if represented_company:
            for row in list(rows):
                if (row.get("company") or "").strip() == represented_company:
                    doc.remove(row)
            rows = doc.get("custom_internal_company_access") or []
        for row in rows:
            row.is_primary = 0
        companies = [(row.get("company") or "").strip() for row in rows]
        if len(companies) != len(set(companies)):
            frappe.throw(_("Each internal company can appear only once."))
        _stamp_internal_company_access_approvals(doc, rows)
        return

    primary = (doc.get("custom_company") or "").strip()
    if primary and not any((row.get("company") or "").strip() == primary for row in rows):
        doc.append("custom_internal_company_access", {"company": primary, "is_primary": 1})
        rows = doc.get("custom_internal_company_access") or []
    companies = [(row.get("company") or "").strip() for row in rows]
    if len(companies) != len(set(companies)):
        frappe.throw(_("Each internal company can appear only once."))
    if not companies:
        return
    primary_rows = [row for row in rows if row.get("is_primary")]
    if not primary_rows:
        next((row for row in rows if row.get("company") == primary), rows[0]).is_primary = 1
    elif len(primary_rows) > 1:
        frappe.throw(_("Only one internal company can be primary."))
    selected_primary = next((row.get("company") for row in rows if row.get("is_primary")), "")
    if selected_primary:
        doc.custom_company = selected_primary
        if doc.meta.get_field("company"):
            doc.company = selected_primary
    _stamp_internal_company_access_approvals(doc, rows)


def _stamp_internal_company_access_approvals(doc, rows) -> None:
    if getattr(doc.flags, "ignore_orderlift_party_company_validation", False):
        return
    existing = set()
    if not doc.is_new():
        existing = set(
            frappe.get_all(
                "Party Internal Company Access",
                filters={"parenttype": doc.doctype, "parent": doc.name, "parentfield": "custom_internal_company_access"},
                pluck="company",
                limit_page_length=0,
            )
        )
    allowed = set(get_allowed_companies(frappe.session.user))
    can_approve = user_has_capability(CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL)
    for row in rows:
        company = (row.get("company") or "").strip()
        if company in existing:
            continue
        if company not in allowed and not can_approve:
            frappe.throw(_("Request approval before adding internal company {0}.").format(company))
        row.approved_by = row.get("approved_by") or frappe.session.user
        row.approved_on = row.get("approved_on") or now_datetime()


def _is_internal_orderlift_party(doc) -> bool:
    fieldname = _internal_party_field(getattr(doc, "doctype", ""))
    return bool(fieldname and doc.get(fieldname) and doc.get("represents_company"))


def _internal_party_field(doctype: str) -> str:
    return {
        "Customer": "is_internal_customer",
        "Supplier": "is_internal_supplier",
    }.get(doctype, "")


def _get_permitted_party(party_type: str, party_name: str, ptype: str = "read"):
    if party_type not in PARTY_DOCTYPES or not party_name or not frappe.db.exists(party_type, party_name):
        frappe.throw(_("The selected party does not exist."))
    party = frappe.get_doc(party_type, party_name)
    party.check_permission(ptype)
    return party


def _linked_addresses(party_type: str, party_name: str) -> list[dict]:
    names = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Address", "link_doctype": party_type, "link_name": party_name},
        pluck="parent",
        limit_page_length=0,
    )
    fields = ["name", "address_title", "address_type", "address_line1", "address_line2", "city", "state", "country", "pincode", "phone", "email_id", "is_primary_address", "is_shipping_address"]
    if frappe.get_meta("Address").get_field("custom_is_site_address"):
        fields.append("custom_is_site_address")
    return frappe.get_all("Address", filters={"name": ["in", list(dict.fromkeys(names))], "disabled": 0}, fields=fields, order_by="is_primary_address desc, is_shipping_address desc, modified desc", limit_page_length=0) if names else []


def _linked_contacts(party_type: str, party_name: str) -> list[dict]:
    names = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Contact", "link_doctype": party_type, "link_name": party_name},
        pluck="parent",
        limit_page_length=0,
    )
    if not names:
        return []
    filters = {"name": ["in", list(dict.fromkeys(names))]}
    fields = ["name", "first_name", "last_name", "designation", "email_id", "mobile_no", "phone", "is_primary_contact", "status"]
    if frappe.get_meta("Contact").get_field("disabled"):
        filters["disabled"] = 0
        fields.append("disabled")
    return frappe.get_all("Contact", filters=filters, fields=fields, order_by="is_primary_contact desc, modified desc", limit_page_length=0)


def _linked_deals(party_type: str, party_name: str) -> dict:
    opportunities = frappe.get_all(
        "Opportunity",
        filters={"opportunity_from": party_type, "party_name": party_name},
        fields=["name", "title", "customer_name", "sales_stage", "status", "opportunity_amount", "modified"],
        order_by="modified desc",
        limit_page_length=20,
    )
    opportunity_names = [row.name for row in opportunities]
    quotations = []
    sales_orders = []
    projects = []
    if opportunity_names:
        quotations = frappe.get_all(
            "Quotation",
            filters={"opportunity": ["in", opportunity_names], "docstatus": ["<", 2]},
            fields=["name", "status", "grand_total", "transaction_date", "opportunity", "modified"],
            order_by="modified desc",
            limit_page_length=20,
        )
        quote_names = [row.name for row in quotations]
        if quote_names:
            sales_orders = frappe.db.sql(
                """
                SELECT DISTINCT so.name, so.status, so.grand_total, so.transaction_date, soi.prevdoc_docname, so.modified
                FROM `tabSales Order` so
                INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
                WHERE so.docstatus < 2 AND soi.prevdoc_docname IN %(quotations)s
                ORDER BY so.modified DESC
                LIMIT 20
                """,
                {"quotations": quote_names},
                as_dict=True,
            )
        if frappe.get_meta("Project").get_field("custom_source_opportunity"):
            projects = frappe.get_all(
                "Project",
                filters={"custom_source_opportunity": ["in", opportunity_names]},
                fields=["name", "project_name", "status", "custom_project_status", "custom_source_opportunity", "modified"],
                order_by="modified desc",
                limit_page_length=20,
            )
    return {
        "opportunities": opportunities,
        "quotations": quotations,
        "sales_orders": sales_orders,
        "projects": projects,
    }


def _candidate_parties(party_type: str):
    meta = frappe.get_meta(party_type)
    fields = ["name", "custom_company"]
    for fieldname in ("customer_name", "supplier_name", "company_name", "lead_name", "first_name", "last_name", "tax_id", "custom_tax_id", "custom_general_email", "custom_general_mobile", "custom_general_phone", "custom_general_whatsapp", "email_id", "mobile_no", "phone", "whatsapp_no"):
        if meta.get_field(fieldname):
            fields.append(fieldname)
    return frappe.get_all(party_type, fields=list(dict.fromkeys(fields)), limit_page_length=0, order_by="modified desc")


def _normalized_identity(values) -> dict:
    getter = values.get
    name = getter("customer_name") or getter("supplier_name") or getter("company_name") or getter("party_name") or getter("lead_name") or ""
    contact = getter("contact_name") or " ".join(filter(None, [getter("first_name"), getter("last_name")]))
    return {
        "name": _normalize_text(name),
        "contact": _normalize_text(contact),
        "tax_id": _normalize_code(getter("tax_id") or getter("custom_tax_id") or ""),
        "email": (getter("custom_general_email") or getter("email_id") or getter("email") or "").strip().lower(),
        "phone": _normalize_code(getter("custom_general_mobile") or getter("custom_general_phone") or getter("custom_general_whatsapp") or getter("mobile_no") or getter("phone") or getter("whatsapp_no") or ""),
    }


def _duplicate_score(left: dict, right: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    for fieldname, weight, label in (("tax_id", 100, "ICE / Tax ID"), ("email", 85, "Email"), ("phone", 75, "Phone"), ("name", 70, "Party name"), ("contact", 20, "Contact name")):
        if left.get(fieldname) and left[fieldname] == right.get(fieldname):
            score = max(score, weight)
            reasons.append(label)
    if left.get("name") and left["name"] == right.get("name") and left.get("contact") and left["contact"] == right.get("contact"):
        score = max(score, 90)
    return score, reasons


def _normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).split())


def _normalize_code(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", value or "").upper()


def _party_display_name(doc, party_type: str) -> str:
    if party_type == "Customer":
        return doc.get("customer_name") or doc.name
    if party_type == "Lead":
        return doc.get("company_name") or doc.get("lead_name") or doc.name
    if party_type == "Supplier":
        return doc.get("supplier_name") or doc.name
    return doc.get("company_name") or doc.name


def _default_sales_stage() -> str:
    filters = {"enabled": 1} if frappe.get_meta("Sales Stage").get_field("enabled") else {}
    stage = frappe.db.get_value("Sales Stage", filters, "name")
    return stage or frappe.db.get_value("Sales Stage", {}, "name") or ""


def _default_opportunity_type() -> str:
    return frappe.db.get_value("Opportunity Type", {}, "name") or "Sales"
