from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt, now
from frappe.utils.print_format import download_pdf

from orderlift.client_portal.utils.access import (
    ensure_internal_reviewer,
    get_catalog_products_for_group,
    INTERNAL_REVIEW_ROLES,
    get_portal_user_context,
    resolve_portal_price,
)


@frappe.whitelist(allow_guest=False)
def get_bootstrap() -> dict:
    ctx = get_portal_user_context()
    visible_catalog = get_catalog(featured=0, limit=500)
    recent_requests = frappe.get_all(
        "Portal Quote Request",
        filters={"portal_user": ctx.user},
        fields=["name", "status", "currency", "total_amount", "modified"],
        order_by="modified desc",
        limit_page_length=5,
    )
    featured = get_catalog(featured=1, limit=6)
    if not featured:
        featured = visible_catalog[:6]
    quotations = get_my_quotations()[:3]
    return {
        "user": {
            "email": ctx.email,
            "customer": ctx.customer,
            "customer_name": ctx.customer_name,
            "customer_group": ctx.customer_group,
        },
        "policy": {
            "currency": (ctx.policy.currency if ctx.policy and hasattr(ctx.policy, "currency") else "") or "",
            "quote_request_allowed": int((ctx.policy.quote_request_allowed if ctx.policy else 0) or 0),
        },
        "featured_catalog": featured,
        "recent_requests": recent_requests,
        "recent_quotations": quotations,
        "metrics": {
            "visible_products": len(visible_catalog),
            "requests_total": frappe.db.count("Portal Quote Request", {"portal_user": ctx.user}),
            "quotations_total": len(get_my_quotations()),
            "featured_total": len([row for row in visible_catalog if int(row.get("featured") or 0) == 1]),
        },
    }


@frappe.whitelist(allow_guest=False)
def get_catalog(search: str = "", featured: int = 0, limit: int = 60) -> list[dict]:
    ctx = get_portal_user_context()
    rules = get_catalog_products_for_group(ctx.customer_group, featured_only=bool(int(featured or 0)))
    search_norm = (search or "").strip().lower()
    out = []

    for rule in rules:
        entry = _catalog_entry_from_rule(rule, ctx.policy.portal_price_list if ctx.policy else "")
        haystack = " ".join(filter(None, [entry.get("title"), entry.get("code"), entry.get("brand"), entry.get("item_group")])).lower()
        if search_norm and search_norm not in haystack:
            continue
        out.append(entry)
        if len(out) >= int(limit or 60):
            break
    return out


@frappe.whitelist(allow_guest=False)
def get_catalog_entry(kind: str, code: str) -> dict:
    ctx = get_portal_user_context()
    rules = get_catalog_products_for_group(ctx.customer_group)
    for rule in rules:
        entry = _catalog_entry_from_rule(rule, ctx.policy.portal_price_list if ctx.policy else "")
        if entry.get("kind") == kind and entry.get("code") == code:
            return entry
    frappe.throw(_("Catalog entry not available for your customer group."), frappe.PermissionError)


@frappe.whitelist(allow_guest=False)
def submit_quote_request(payload: str) -> dict:
    ctx = get_portal_user_context()
    policy = ctx.policy
    if not policy or not policy.quote_request_allowed:
        frappe.throw(_("Quotation requests are not enabled for your customer group."), frappe.PermissionError)

    data = json.loads(payload or "{}") if isinstance(payload, str) else (payload or {})
    lines = data.get("items") or []
    if not lines:
        frappe.throw(_("Add at least one item before submitting your quotation request."))

    request = frappe.new_doc("Portal Quote Request")
    request.customer = ctx.customer
    request.customer_group = ctx.customer_group
    request.contact = ctx.contact
    request.portal_user = ctx.user
    request.currency = policy.currency or frappe.db.get_value("Price List", policy.portal_price_list, "currency") or "MAD"
    request.status = "Submitted"
    request.request_notes = (data.get("request_notes") or "").strip()
    request.submitted_on = now()

    allowed_rules = {row.name: row for row in get_catalog_products_for_group(ctx.customer_group)}
    total_qty = 0.0
    total_amount = 0.0

    for raw_line in lines:
        qty = flt(raw_line.get("qty") or 0)
        if qty <= 0:
            continue
        rule_name = raw_line.get("rule_name")
        rule = allowed_rules.get(rule_name)
        if not rule:
            frappe.throw(_("One of the requested products is not allowed for your customer group."), frappe.PermissionError)

        entry = _catalog_entry_from_rule(rule, policy.portal_price_list)
        rate = flt(entry.get("price_rate") or 0)
        if rate <= 0:
            frappe.throw(_("Item {0} has no valid portal price.").format(entry.get("title") or entry.get("code")))

        line_total = qty * rate
        request.append(
            "items",
            {
                "item_type": entry.get("kind", "item").title(),
                "item_code": entry.get("item_code"),
                "product_bundle": entry.get("product_bundle") or "",
                "item_name": entry.get("title") or entry.get("code"),
                "brand": entry.get("brand") or "",
                "uom": entry.get("uom") or "",
                "qty": qty,
                "unit_price": rate,
                "line_total": line_total,
                "source_price_list": policy.portal_price_list,
                "image": entry.get("image") or "",
            },
        )
        total_qty += qty
        total_amount += line_total

    if not request.items:
        frappe.throw(_("No valid request lines were submitted."))

    request.total_qty = total_qty
    request.total_amount = total_amount
    request.insert(ignore_permissions=True)
    _notify_internal_reviewers(request)
    _notify_request_submitted(request)
    return {"name": request.name, "status": request.status}


@frappe.whitelist(allow_guest=False)
def get_my_requests() -> list[dict]:
    ctx = get_portal_user_context()
    return frappe.get_all(
        "Portal Quote Request",
        filters={"portal_user": ctx.user},
        fields=["name", "status", "currency", "total_amount", "submitted_on", "linked_quotation", "modified"],
        order_by="modified desc",
        limit_page_length=100,
    )


@frappe.whitelist(allow_guest=False)
def get_request_detail(name: str) -> dict:
    ctx = get_portal_user_context()
    request = frappe.get_doc("Portal Quote Request", name)
    if request.portal_user != ctx.user and request.customer != ctx.customer:
        frappe.throw(_("You are not allowed to view this request."), frappe.PermissionError)
    return {
        "name": request.name,
        "customer": request.customer,
        "status": request.status,
        "currency": request.currency,
        "request_notes": request.request_notes,
        "review_comment": request.review_comment,
        "linked_quotation": request.linked_quotation,
        "quotation_pdf_url": f"/api/method/orderlift.orderlift_client_portal.api.download_request_quotation_pdf?name={request.name}" if request.linked_quotation else "",
        "submitted_on": request.submitted_on,
        "total_qty": request.total_qty,
        "total_amount": request.total_amount,
        "items": [
            {
                "item_type": row.item_type,
                "item_code": row.item_code,
                "product_bundle": row.product_bundle,
                "item_name": row.item_name,
                "brand": row.brand,
                "uom": row.uom,
                "qty": row.qty,
                "unit_price": row.unit_price,
                "line_total": row.line_total,
                "image": row.image,
            }
            for row in request.items
        ],
    }


@frappe.whitelist()
def get_review_queue() -> list[dict]:
    ensure_internal_reviewer()
    return frappe.get_all(
        "Portal Quote Request",
        filters={"status": ["in", ["Submitted", "Under Review", "Approved"]]},
        fields=["name", "customer", "customer_group", "portal_user", "status", "total_amount", "currency", "modified", "linked_quotation"],
        order_by="modified desc",
        limit_page_length=100,
    )


@frappe.whitelist()
def get_review_request_detail(name: str) -> dict:
    ensure_internal_reviewer()
    request = frappe.get_doc("Portal Quote Request", name)
    return {
        "name": request.name,
        "customer": request.customer,
        "customer_group": request.customer_group,
        "portal_user": request.portal_user,
        "status": request.status,
        "currency": request.currency,
        "request_notes": request.request_notes,
        "review_comment": request.review_comment,
        "linked_quotation": request.linked_quotation,
        "total_qty": request.total_qty,
        "total_amount": request.total_amount,
        "items": [
            {
                "item_name": row.item_name,
                "item_code": row.item_code,
                "product_bundle": row.product_bundle,
                "item_type": row.item_type,
                "brand": row.brand,
                "uom": row.uom,
                "qty": row.qty,
                "unit_price": row.unit_price,
                "line_total": row.line_total,
            }
            for row in request.items
        ],
    }


@frappe.whitelist()
def review_request_action(name: str, action: str, review_comment: str | None = None) -> dict:
    ensure_internal_reviewer()
    request = frappe.get_doc("Portal Quote Request", name)
    action = (action or "").strip().lower()
    if action == "approve":
        request.approve_request(review_comment)
        return {"name": request.name, "status": "Approved"}
    if action == "reject":
        request.reject_request(review_comment)
        return {"name": request.name, "status": "Rejected"}
    if action == "create_quotation":
        quotation = request.create_quotation()
        return {"name": request.name, "status": "Quotation Created", "linked_quotation": quotation}
    frappe.throw(_("Unsupported review action {0}").format(action))


@frappe.whitelist(allow_guest=False)
def get_my_quotations() -> list[dict]:
    ctx = get_portal_user_context()
    requests = frappe.get_all(
        "Portal Quote Request",
        filters={"customer": ctx.customer, "linked_quotation": ["is", "set"]},
        fields=["name", "linked_quotation", "modified"],
        order_by="modified desc",
        limit_page_length=100,
    )

    rows = []
    for request in requests:
        quotation_name = request.linked_quotation
        if not quotation_name:
            continue
        quotation = frappe.db.get_value(
            "Quotation",
            quotation_name,
            ["name", "status", "transaction_date", "valid_till", "grand_total", "currency"],
            as_dict=True,
        ) or {}
        if not quotation:
            continue
        rows.append(
            {
                "portal_request": request.name,
                "quotation": quotation.get("name"),
                "status": quotation.get("status") or "",
                "transaction_date": quotation.get("transaction_date"),
                "valid_till": quotation.get("valid_till"),
                "grand_total": quotation.get("grand_total") or 0,
                "currency": quotation.get("currency") or "MAD",
                "pdf_url": f"/api/method/orderlift.orderlift_client_portal.api.download_request_quotation_pdf?name={request.name}",
                "request_name": request.name,
            }
        )
    return rows


@frappe.whitelist(allow_guest=False)
def download_request_quotation_pdf(name: str):
    ctx = get_portal_user_context()
    request = frappe.get_doc("Portal Quote Request", name)
    if request.portal_user != ctx.user and request.customer != ctx.customer:
        frappe.throw(_("You are not allowed to download this quotation."), frappe.PermissionError)
    if not request.linked_quotation:
        frappe.throw(_("No quotation has been created for this request yet."))
    return download_pdf("Quotation", request.linked_quotation, None)


@frappe.whitelist()
def invite_portal_user(email: str, customer: str, first_name: str | None = None, last_name: str | None = None) -> dict:
    ensure_internal_reviewer()
    email = (email or "").strip().lower()
    customer = (customer or "").strip()
    if not email or not customer:
        frappe.throw(_("Email and customer are required to invite a portal user."))
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} does not exist.").format(customer))

    user_name = frappe.db.exists("User", email)
    if user_name:
        user = frappe.get_doc("User", user_name)
    else:
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = (first_name or email.split("@")[0]).strip() or email.split("@")[0]
        user.last_name = (last_name or "").strip()
        user.send_welcome_email = 1
        user.user_type = "Website User"
        user.enabled = 1
        user.append("roles", {"role": "B2B Portal Client"})
        user.insert(ignore_permissions=True)

    if not any((row.role or "") == "B2B Portal Client" for row in user.roles):
        user.append("roles", {"role": "B2B Portal Client"})

    current_roles = {(row.role or "") for row in user.roles}
    if not current_roles.intersection(INTERNAL_REVIEW_ROLES):
        user.user_type = "Website User"

    user.save(ignore_permissions=True)

    contact_name = frappe.db.get_value("Contact", {"email_id": email}, "name")
    if contact_name:
        contact = frappe.get_doc("Contact", contact_name)
    else:
        contact = frappe.new_doc("Contact")
        contact.first_name = user.first_name or email
        contact.last_name = user.last_name or ""
        contact.email_id = email
        contact.user = user.name
        contact.append("links", {"link_doctype": "Customer", "link_name": customer})
        contact.insert(ignore_permissions=True)

    if contact.user != user.name:
        contact.user = user.name
    if not any((row.link_doctype, row.link_name) == ("Customer", customer) for row in contact.links or []):
        contact.append("links", {"link_doctype": "Customer", "link_name": customer})
    contact.save(ignore_permissions=True)

    customer_doc = frappe.get_doc("Customer", customer)
    if not customer_doc.customer_primary_contact:
        customer_doc.customer_primary_contact = contact.name
    if not any((row.user or "") == user.name for row in customer_doc.portal_users or []):
        customer_doc.append("portal_users", {"user": user.name})
    customer_doc.save(ignore_permissions=True)

    return {"user": user.name, "contact": contact.name, "customer": customer}


def _catalog_entry_from_rule(rule: frappe._dict, price_list: str) -> dict:
    if rule.product_bundle:
        bundle = frappe.get_doc("Product Bundle", rule.product_bundle)
        item = frappe.get_doc("Item", bundle.new_item_code)
        price = resolve_portal_price(item.name, price_list)
        return {
            "rule_name": rule.name,
            "kind": "bundle",
            "code": bundle.name,
            "item_code": item.name,
            "product_bundle": bundle.name,
            "title": rule.portal_title or item.item_name or item.name,
            "description": rule.short_description or bundle.description or item.description or "",
            "brand": item.brand or "",
            "item_group": item.item_group or "",
            "image": item.image or "",
            "uom": item.stock_uom or "",
            "material": getattr(item, "custom_material", "") or "",
            "weight_kg": flt(getattr(item, "custom_weight_kg", 0) or getattr(item, "weight_per_unit", 0)),
            "price_label": _("Quoted price"),
            "currency": price.currency,
            "price_rate": flt(price.rate),
            "featured": int(rule.featured or 0),
            "allow_quote": int(rule.allow_quote or 0),
            "children": [
                {
                    "item_code": row.item_code,
                    "qty": row.qty,
                    "uom": row.uom,
                    "description": row.description,
                    "brand": frappe.db.get_value("Item", row.item_code, "brand") or "",
                }
                for row in bundle.items
            ],
        }

    item = frappe.get_doc("Item", rule.item_code)
    price = resolve_portal_price(item.name, price_list)
    return {
        "rule_name": rule.name,
        "kind": "item",
        "code": item.name,
        "item_code": item.name,
        "product_bundle": "",
        "title": rule.portal_title or item.item_name or item.name,
        "description": rule.short_description or item.description or "",
        "brand": item.brand or "",
        "item_group": item.item_group or "",
        "image": item.image or "",
        "uom": item.stock_uom or "",
        "material": getattr(item, "custom_material", "") or "",
        "weight_kg": flt(getattr(item, "custom_weight_kg", 0) or getattr(item, "weight_per_unit", 0)),
        "price_label": _("Quoted price"),
        "currency": price.currency,
        "price_rate": flt(price.rate),
        "featured": int(rule.featured or 0),
        "allow_quote": int(rule.allow_quote or 0),
        "children": [],
    }


def _notify_internal_reviewers(request):
    recipients = []
    for role in ["Sales Manager", "Orderlift Commercial", "Orderlift Admin"]:
        recipients.extend(frappe.get_all("Has Role", filters={"role": role}, pluck="parent", limit_page_length=100))
    recipients = sorted({user for user in recipients if user and user != "Administrator"})
    emails = [frappe.db.get_value("User", user, "email") for user in recipients]
    emails = [email for email in emails if email]
    if not emails:
        return
    frappe.sendmail(
        recipients=emails,
        subject=_("New Portal Quote Request {0}").format(request.name),
        message=_("A new B2B portal quote request was submitted by {0} for customer {1}.").format(request.portal_user, request.customer),
        delayed=False,
    )


def _notify_request_submitted(request):
    email = frappe.db.get_value("Contact", request.contact, "email_id") or frappe.db.get_value("User", request.portal_user, "email")
    if not email:
        return
    frappe.sendmail(
        recipients=[email],
        subject=_("Quotation Request Received: {0}").format(request.name),
        message=_("Your quotation request has been submitted and is now under review."),
        delayed=False,
    )
