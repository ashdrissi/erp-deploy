from __future__ import annotations

import frappe


PARTY_DOCTYPES = {"Lead", "Prospect", "Customer"}


def resolve_party_context(
    party_type: str,
    party_name: str,
    *,
    source_doc=None,
    preferred_contact: str | None = None,
    preferred_billing_address: str | None = None,
    preferred_shipping_address: str | None = None,
) -> dict:
    party_type = (party_type or "").strip()
    party_name = (party_name or "").strip()
    if party_type not in PARTY_DOCTYPES or not party_name or not frappe.db.exists(party_type, party_name):
        return {}

    party = frappe.get_doc(party_type, party_name)
    classification = _primary_party_classification(party_type, party_name)
    contact_name = _resolve_contact_name(party, party_type, party_name, source_doc, preferred_contact)
    contact = _contact_details(contact_name)
    billing_address_name = _resolve_billing_address(
        party,
        party_type,
        party_name,
        source_doc,
        preferred_billing_address,
    )
    shipping_address_name = _resolve_shipping_address(
        party_type,
        party_name,
        source_doc,
        preferred_shipping_address,
    ) or billing_address_name
    site_address_name = _resolve_site_address(party_type, party_name, source_doc)
    general_email = party.get("custom_general_email") or party.get("email_id") or ""
    general_mobile = party.get("custom_general_mobile") or party.get("mobile_no") or ""
    general_phone = party.get("custom_general_phone") or party.get("phone") or ""
    general_whatsapp = party.get("custom_general_whatsapp") or party.get("whatsapp_no") or ""
    contact_email = contact.get("contact_email") or ""
    contact_mobile = contact.get("contact_mobile") or ""
    contact_phone = contact.get("contact_phone") or ""

    return {
        "party_type": party_type,
        "party_name": party_name,
        "display_name": _party_display_name(party, party_type),
        "company": party.get("custom_company") or party.get("company") or "",
        "territory": party.get("territory") or "",
        "city": party.get("city") or "",
        "industry": party.get("industry") or "",
        "website": party.get("website") or "",
        "language": party.get("language") or "",
        "customer_group": party.get("customer_group") or "",
        "tier": party.get("manual_tier") or party.get("tier") or "",
        "source": party.get("source") or party.get("utm_source") or "",
        "general_email": general_email,
        "general_mobile": general_mobile,
        "general_phone": general_phone,
        "general_whatsapp": general_whatsapp,
        "contact_email": contact_email,
        "contact_mobile": contact_mobile,
        "contact_phone": contact_phone,
        "email": contact_email or general_email,
        "mobile": contact_mobile or general_mobile or general_whatsapp,
        "phone": contact_phone or general_phone,
        "contact_name": contact_name or "",
        "contact_display": contact.get("contact_display") or "",
        "billing_address_name": billing_address_name or "",
        "billing_address_display": _address_display(billing_address_name),
        "shipping_address_name": shipping_address_name or "",
        "shipping_address_display": _address_display(shipping_address_name),
        "site_address_name": site_address_name or "",
        "site_address_display": _address_display(site_address_name),
        "tax_id": _party_tax_id(party),
        "business_type": classification.get("business_type") or "",
        "crm_segment": classification.get("crm_segment") or "",
        "segments": classification.get("segments") or [],
    }


def apply_party_context_to_opportunity(doc, context: dict, *, overwrite: bool = False) -> None:
    values = {
        "customer_name": context.get("display_name"),
        "company": context.get("company"),
        "industry": context.get("industry"),
        "territory": context.get("territory"),
        "city": context.get("city"),
        "website": context.get("website"),
        "language": context.get("language"),
        "phone": context.get("phone") or context.get("mobile"),
        "contact_person": context.get("contact_name"),
        "contact_display": context.get("contact_display"),
        "contact_email": context.get("email"),
        "contact_mobile": context.get("mobile") or context.get("phone"),
        "customer_address": context.get("billing_address_name"),
        "address_display": context.get("billing_address_display"),
        "custom_crm_business_type": context.get("business_type"),
        "custom_crm_segment": context.get("crm_segment"),
        "custom_tier": context.get("tier"),
        "custom_customer_tax_id": context.get("tax_id"),
        "custom_site_address_name": context.get("site_address_name"),
        "custom_site_address": context.get("site_address_display"),
    }
    _apply_values(doc, values, overwrite=overwrite)


def apply_party_context_to_customer(doc, context: dict, *, overwrite: bool = False) -> None:
    values = {
        "customer_name": context.get("display_name"),
        "industry": context.get("industry"),
        "territory": context.get("territory"),
        "website": context.get("website"),
        "language": context.get("language"),
        "custom_general_email": context.get("general_email"),
        "custom_general_mobile": context.get("general_mobile"),
        "custom_general_phone": context.get("general_phone"),
        "custom_general_whatsapp": context.get("general_whatsapp"),
        "mobile_no": context.get("mobile") or context.get("phone"),
        "email_id": context.get("email"),
        "customer_primary_contact": context.get("contact_name"),
        "customer_primary_address": context.get("billing_address_name"),
        "tax_id": context.get("tax_id"),
    }
    _apply_values(doc, values, overwrite=overwrite)


def apply_party_context_to_quotation(doc, context: dict, *, overwrite: bool = False) -> None:
    values = {
        "customer_name": context.get("display_name"),
        "territory": context.get("territory"),
        "language": context.get("language"),
        "contact_person": context.get("contact_name"),
        "contact_display": context.get("contact_display"),
        "contact_email": context.get("email"),
        "contact_mobile": context.get("mobile") or context.get("phone"),
        "customer_address": context.get("billing_address_name"),
        "address_display": context.get("billing_address_display"),
        "shipping_address_name": context.get("shipping_address_name"),
        "shipping_address": context.get("shipping_address_display"),
        "custom_customer_tax_id": context.get("tax_id"),
        "tax_id": context.get("tax_id"),
        "custom_site_address_name": context.get("site_address_name"),
    }
    _apply_values(doc, values, overwrite=overwrite)


def link_party_contacts_and_addresses(
    source_type: str,
    source_name: str,
    target_type: str,
    target_name: str,
) -> None:
    if not source_type or not source_name or not target_type or not target_name:
        return
    for parenttype in ("Contact", "Address"):
        rows = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": source_type,
                "link_name": source_name,
                "parenttype": parenttype,
            },
            pluck="parent",
            limit_page_length=0,
        )
        for name in dict.fromkeys(rows):
            if not frappe.db.exists(parenttype, name):
                continue
            linked_doc = frappe.get_doc(parenttype, name)
            if any(
                row.get("link_doctype") == target_type and row.get("link_name") == target_name
                for row in linked_doc.get("links") or []
            ):
                continue
            linked_doc.append("links", {"link_doctype": target_type, "link_name": target_name})
            linked_doc.save(ignore_permissions=True)


def apply_customer_ownership(customer, user: str | None) -> None:
    user = (user or "").strip()
    if not user or not frappe.db.exists("User", user):
        return
    if customer.meta.get_field("account_manager") and not customer.get("account_manager"):
        customer.account_manager = user
    if not customer.meta.get_field("sales_team") or customer.get("sales_team"):
        return
    sales_person = sales_person_for_user(user)
    if sales_person:
        customer.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})


def sales_person_for_user(user: str | None) -> str:
    user = (user or "").strip()
    if not user or not frappe.db.exists("DocType", "Sales Person"):
        return ""
    if not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def set_first_customer_address(doc, method=None) -> None:
    if not doc or not getattr(doc, "name", None) or _to_int(doc.get("disabled")):
        return
    customers = [
        row.get("link_name")
        for row in doc.get("links") or []
        if row.get("link_doctype") == "Customer" and row.get("link_name")
    ]
    for customer_name in dict.fromkeys(customers):
        if not frappe.db.exists("Customer", customer_name):
            continue
        customer = frappe.get_doc("Customer", customer_name)
        if customer.get("customer_primary_address"):
            continue
        customer.customer_primary_address = doc.name
        customer.save(ignore_permissions=True)


def set_first_customer_contact(doc, method=None) -> None:
    if not doc or not getattr(doc, "name", None):
        return
    customers = [
        row.get("link_name")
        for row in doc.get("links") or []
        if row.get("link_doctype") == "Customer" and row.get("link_name")
    ]
    for customer_name in dict.fromkeys(customers):
        if not frappe.db.exists("Customer", customer_name):
            continue
        customer = frappe.get_doc("Customer", customer_name)
        if customer.get("customer_primary_contact"):
            continue
        customer.customer_primary_contact = doc.name
        customer.save(ignore_permissions=True)


def ensure_customer_for_party(party_type: str, party_name: str, *, source_doc=None):
    party_type = (party_type or "").strip()
    party_name = (party_name or "").strip()
    if party_type == "Customer":
        if not frappe.db.exists("Customer", party_name):
            frappe.throw("Customer {0} was not found.".format(party_name))
        return frappe.get_doc("Customer", party_name)
    if party_type not in {"Lead", "Prospect"} or not frappe.db.exists(party_type, party_name):
        frappe.throw("Lead or Prospect party was not found.")

    source = frappe.get_doc(party_type, party_name)
    context = resolve_party_context(party_type, party_name, source_doc=source_doc)
    display_name = _party_display_name(source, party_type)
    customer_name = _find_existing_customer(source, party_type, context.get("tax_id"), display_name)
    customer = frappe.get_doc("Customer", customer_name) if customer_name else frappe.new_doc("Customer")
    if customer.is_new():
        customer.customer_name = display_name
        customer.customer_type = "Company" if source.get("company_name") else "Individual"
        customer.customer_group = _default_customer_group()
        customer.custom_company = source.get("custom_company") or source.get("company") or ""
        if source.get("territory"):
            customer.territory = source.get("territory")
    _set_customer_lineage(customer, party_type, party_name, _source_opportunity_name(source_doc))
    apply_party_context_to_customer(customer, context)
    _copy_party_rows(source, customer, "custom_crm_segments", ("business_type", "segment"))
    _copy_party_rows(source, customer, "custom_internal_company_access", ("company",))
    customer.flags.ignore_orderlift_party_duplicate_check = True
    customer.insert(ignore_permissions=False) if customer.is_new() else customer.save(ignore_permissions=False)
    link_party_contacts_and_addresses(party_type, party_name, "Customer", customer.name)
    if source_doc and getattr(source_doc, "doctype", None) == "Opportunity":
        link_party_contacts_and_addresses("Opportunity", source_doc.name, "Customer", customer.name)
    customer.reload()
    _apply_linked_customer_defaults(customer)
    if party_type == "Lead" and source.meta.get_field("customer"):
        frappe.db.set_value("Lead", source.name, "customer", customer.name, update_modified=False)
    return customer


def apply_sales_order_party_context(doc, method=None) -> None:
    quotations = _source_quotations(doc)
    if not quotations:
        _apply_customer_tax_id(doc)
        return
    parties = {(row.get("quotation_to") or "", row.get("party_name") or "") for row in quotations}
    if len(parties) != 1:
        frappe.throw("All source Quotations in one Sales Order must use the same party.")
    party_type, party_name = next(iter(parties))
    customer = ensure_customer_for_party(party_type, party_name, source_doc=quotations[0])
    if doc.get("customer") and doc.get("customer") != customer.name:
        frappe.throw("Sales Order Customer must match its source Quotation party.")
    doc.customer = customer.name
    context = resolve_party_context("Customer", customer.name, source_doc=quotations[0])
    tax_id = context.get("tax_id") or _customer_tax_id(customer.name)
    values = {
        "customer_name": context.get("display_name"),
        "contact_person": context.get("contact_name"),
        "contact_display": context.get("contact_display"),
        "contact_mobile": context.get("mobile") or context.get("phone"),
        "contact_email": context.get("email"),
        "customer_address": context.get("billing_address_name"),
        "address_display": context.get("billing_address_display"),
        "shipping_address_name": context.get("shipping_address_name"),
        "shipping_address": context.get("shipping_address_display"),
        "tax_id": tax_id,
        "custom_customer_tax_id": tax_id,
        "custom_site_address_name": quotations[0].get("custom_site_address_name") or context.get("site_address_name"),
    }
    _apply_values(doc, values, overwrite=False)


def sync_downstream_sales_party_context(doc, method=None) -> None:
    sales_orders = _source_sales_orders(doc)
    if not sales_orders:
        _apply_customer_tax_id(doc)
        return
    customers = {(row.get("customer") or "").strip() for row in sales_orders if row.get("customer")}
    projects = {
        (row.get("custom_installation_project") or row.get("project") or "").strip()
        for row in sales_orders
        if row.get("custom_installation_project") or row.get("project")
    }
    if len(customers) > 1 or len(projects) > 1:
        frappe.throw("Source Sales Orders must use the same Customer and Project.")
    source = sales_orders[0]
    tax_id = source.get("tax_id") or source.get("custom_customer_tax_id") or _customer_tax_id(source.get("customer"))
    values = {
        "customer": source.get("customer"),
        "customer_name": source.get("customer_name"),
        "contact_person": source.get("contact_person"),
        "contact_display": source.get("contact_display"),
        "contact_mobile": source.get("contact_mobile"),
        "contact_email": source.get("contact_email"),
        "customer_address": source.get("customer_address"),
        "address_display": source.get("address_display"),
        "shipping_address_name": source.get("shipping_address_name"),
        "shipping_address": source.get("shipping_address"),
        "tax_id": tax_id,
        "custom_customer_tax_id": tax_id,
        "project": source.get("custom_installation_project") or source.get("project"),
        "custom_site_address_name": source.get("custom_site_address_name"),
    }
    _apply_values(doc, values, overwrite=False)


def _apply_customer_tax_id(doc) -> None:
    customer = (doc.get("customer") or "").strip()
    tax_id = _customer_tax_id(customer)
    if not tax_id:
        return
    _apply_values(doc, {"tax_id": tax_id, "custom_customer_tax_id": tax_id}, overwrite=False)


def _customer_tax_id(customer: str | None) -> str:
    customer = (customer or "").strip()
    if not customer:
        return ""
    return (frappe.db.get_value("Customer", customer, "tax_id") or "").strip()


def _apply_values(doc, values: dict, *, overwrite: bool) -> None:
    for fieldname, value in values.items():
        if value in (None, "") or not doc.meta.get_field(fieldname):
            continue
        if not overwrite and doc.get(fieldname) not in (None, ""):
            continue
        doc.set(fieldname, value)


def _source_quotations(doc) -> list:
    names = list(dict.fromkeys(
        (row.get("prevdoc_docname") or "").strip()
        for row in doc.get("items") or []
        if (row.get("prevdoc_docname") or "").strip()
    ))
    return [frappe.get_doc("Quotation", name) for name in names if frappe.db.exists("Quotation", name)]


def _source_sales_orders(doc) -> list:
    fieldname = "against_sales_order" if getattr(doc, "doctype", None) == "Delivery Note" else "sales_order"
    names = list(dict.fromkeys(
        (row.get(fieldname) or "").strip()
        for row in doc.get("items") or []
        if (row.get(fieldname) or "").strip()
    ))
    return [frappe.get_doc("Sales Order", name) for name in names if frappe.db.exists("Sales Order", name)]


def _resolve_contact_name(party, party_type, party_name, source_doc, preferred_contact) -> str:
    candidates = [
        preferred_contact,
        source_doc.get("contact_person") if source_doc else None,
        party.get("customer_primary_contact") if party_type == "Customer" else None,
    ]
    for contact_name in candidates:
        if contact_name and frappe.db.exists("Contact", contact_name):
            return contact_name
    try:
        from frappe.contacts.doctype.contact.contact import get_default_contact

        default_contact = get_default_contact(party_type, party_name) or ""
        if default_contact:
            return default_contact
    except (ImportError, TypeError):
        pass
    names = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Contact", "link_doctype": party_type, "link_name": party_name},
        pluck="parent",
        limit_page_length=0,
    )
    if not names:
        return ""
    return frappe.db.get_value(
        "Contact",
        {"name": ["in", list(dict.fromkeys(names))]},
        "name",
        order_by="is_primary_contact desc, modified desc",
    ) or ""


def _resolve_billing_address(party, party_type, party_name, source_doc, preferred_address) -> str:
    candidates = [
        preferred_address,
        source_doc.get("customer_address") if source_doc else None,
        party.get("customer_primary_address") if party_type == "Customer" else None,
    ]
    for address_name in candidates:
        if _valid_address(address_name):
            return address_name
    try:
        from frappe.contacts.doctype.address.address import get_default_address

        default_address = get_default_address(party_type, party_name) or ""
        if default_address:
            return default_address
    except (ImportError, TypeError):
        pass
    return _linked_address_name(party_type, party_name, {"is_primary_address": 1}) or _linked_address_name(party_type, party_name)


def _resolve_shipping_address(party_type, party_name, source_doc, preferred_address) -> str:
    candidates = [
        preferred_address,
        source_doc.get("shipping_address_name") if source_doc else None,
    ]
    for address_name in candidates:
        if _valid_address(address_name):
            return address_name
    try:
        from erpnext.accounts.party import get_party_shipping_address

        shipping_address = get_party_shipping_address(party_type, party_name) or ""
        if shipping_address:
            return shipping_address
    except (ImportError, TypeError):
        pass
    return _linked_address_name(party_type, party_name, {"is_shipping_address": 1})


def _resolve_site_address(party_type, party_name, source_doc) -> str:
    candidate = source_doc.get("custom_site_address_name") if source_doc else None
    if _valid_address(candidate):
        return candidate
    if not frappe.db.has_column("Address", "custom_is_site_address"):
        return ""
    names = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Address", "link_doctype": party_type, "link_name": party_name},
        pluck="parent",
        limit_page_length=0,
    )
    if not names:
        return ""
    return frappe.db.get_value(
        "Address",
        {"name": ["in", names], "disabled": 0, "custom_is_site_address": 1},
        "name",
        order_by="modified desc",
    ) or ""


def _contact_details(contact_name: str | None) -> dict:
    if not contact_name:
        return {}
    try:
        from frappe.contacts.doctype.contact.contact import get_contact_details

        return get_contact_details(contact_name) or {}
    except (ImportError, TypeError):
        return {}


def _address_display(address_name: str | None) -> str:
    if not _valid_address(address_name):
        return ""
    try:
        from frappe.contacts.doctype.address.address import get_address_display

        return get_address_display(frappe.get_doc("Address", address_name).as_dict()) or ""
    except (ImportError, TypeError):
        return ""


def _valid_address(address_name: str | None) -> bool:
    return bool(
        address_name
        and frappe.db.exists("Address", address_name)
        and not _to_int(frappe.db.get_value("Address", address_name, "disabled") or 0)
    )


def _linked_address_name(party_type: str, party_name: str, extra_filters: dict | None = None) -> str:
    names = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Address", "link_doctype": party_type, "link_name": party_name},
        pluck="parent",
        limit_page_length=0,
    )
    if not names:
        return ""
    filters = {"name": ["in", list(dict.fromkeys(names))], "disabled": 0}
    if extra_filters:
        filters.update(extra_filters)
    return frappe.db.get_value("Address", filters, "name", order_by="modified desc") or ""


def _party_display_name(doc, party_type: str) -> str:
    if party_type == "Customer":
        return doc.get("customer_name") or doc.name
    if party_type == "Lead":
        return doc.get("company_name") or doc.get("lead_name") or doc.name
    return doc.get("company_name") or doc.name


def _party_tax_id(doc) -> str:
    fieldname = "tax_id" if getattr(doc, "doctype", None) == "Customer" else "custom_tax_id"
    return (doc.get(fieldname) or "").strip()


def _find_existing_customer(source, party_type: str, tax_id: str, display_name: str) -> str:
    if party_type == "Lead" and source.meta.get_field("customer") and source.get("customer"):
        if frappe.db.exists("Customer", source.get("customer")):
            return source.get("customer")
    if tax_id:
        customer = frappe.db.get_value("Customer", {"tax_id": tax_id}, "name")
        if customer:
            return customer
    return frappe.db.get_value("Customer", {"customer_name": display_name}, "name") or ""


def _default_customer_group() -> str:
    return frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"


def _set_customer_lineage(customer, party_type: str, party_name: str, opportunity_name: str | None) -> None:
    source_field = {"Lead": "lead_name", "Prospect": "prospect_name"}.get(party_type)
    if source_field and customer.meta.get_field(source_field) and not customer.get(source_field):
        customer.set(source_field, party_name)
    if opportunity_name and customer.meta.get_field("opportunity_name") and not customer.get("opportunity_name"):
        customer.opportunity_name = opportunity_name


def _source_opportunity_name(source_doc) -> str:
    if not source_doc:
        return ""
    if getattr(source_doc, "doctype", None) == "Opportunity":
        return getattr(source_doc, "name", "") or ""
    if getattr(source_doc, "doctype", None) in {"Quotation", "Pricing Sheet"}:
        return source_doc.get("opportunity") or ""
    return ""


def _copy_party_rows(source, target, fieldname: str, key_fields: tuple[str, ...]) -> None:
    if not target.meta.get_field(fieldname):
        return
    existing = {tuple(row.get(field) or "" for field in key_fields) for row in target.get(fieldname) or []}
    for row in source.get(fieldname) or []:
        key = tuple(row.get(field) or "" for field in key_fields)
        if not all(key) or key in existing:
            continue
        target.append(fieldname, {field: row.get(field) for field in row.as_dict() if field not in {"name", "parent", "parenttype", "parentfield", "doctype", "idx"}})
        existing.add(key)


def _apply_linked_customer_defaults(customer) -> None:
    context = resolve_party_context("Customer", customer.name)
    before = (customer.get("customer_primary_contact") or "", customer.get("customer_primary_address") or "")
    apply_party_context_to_customer(customer, context)
    after = (customer.get("customer_primary_contact") or "", customer.get("customer_primary_address") or "")
    if after != before:
        customer.save(ignore_permissions=False)


def _primary_party_classification(party_type: str, party_name: str) -> dict:
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return {"business_type": "", "crm_segment": "", "segments": []}
    rows = frappe.get_all(
        "CRM Segment Assignment",
        filters={"parenttype": party_type, "parent": party_name},
        fields=["business_type", "segment", "is_primary"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )
    segments = [
        {
            "business_type": row.get("business_type") or "",
            "crm_segment": row.get("segment") or "",
            "is_primary": _to_int(row.get("is_primary")),
        }
        for row in rows
        if row.get("business_type") or row.get("segment")
    ]
    primary = segments[0] if segments else {}
    return {
        "business_type": primary.get("business_type") or "",
        "crm_segment": primary.get("crm_segment") or "",
        "segments": segments,
    }


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
