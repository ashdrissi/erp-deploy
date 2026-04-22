from __future__ import annotations

import frappe
from frappe import _


PORTAL_ROLE = "B2B Portal Client"
INTERNAL_REVIEW_ROLES = {"Orderlift Admin", "System Manager", "Sales Manager", "Orderlift Commercial"}
DEFAULT_CUSTOMER_GROUP = "All Customer Groups"


def _has_b2b_only_roles(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False

    roles = set(frappe.get_roles(user))
    return PORTAL_ROLE in roles and not roles.intersection(INTERNAL_REVIEW_ROLES)


def get_portal_user_context(require_policy: bool = True) -> frappe._dict:
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login is required to access the B2B portal."), frappe.PermissionError)

    roles = set(frappe.get_roles(user))
    if PORTAL_ROLE not in roles and not roles.intersection(INTERNAL_REVIEW_ROLES):
        frappe.throw(_("You are not allowed to access the B2B portal."), frappe.PermissionError)

    contact = _resolve_contact(user)
    if not contact:
        frappe.throw(_("No Contact is linked to this portal user."), frappe.PermissionError)

    customer = _resolve_customer(contact)
    if not customer:
        frappe.throw(_("No Customer is linked to this portal user."), frappe.PermissionError)

    customer_doc = frappe.get_doc("Customer", customer)
    customer_group = (customer_doc.customer_group or "").strip()
    if not customer_group:
        frappe.throw(_("The linked customer has no Customer Group."), frappe.PermissionError)

    policy_name = _get_policy_name(customer_group)
    if require_policy and not policy_name:
        frappe.throw(_("No active portal policy exists for customer group {0}." ).format(customer_group), frappe.PermissionError)

    policy = frappe.get_doc("Portal Customer Group Policy", policy_name) if policy_name else None

    return frappe._dict(
        user=user,
        roles=list(roles),
        contact=contact,
        customer=customer,
        customer_name=customer_doc.customer_name,
        customer_group=customer_group,
        policy=policy,
        email=frappe.db.get_value("Contact", contact, "email_id") or frappe.db.get_value("User", user, "email") or user,
    )


def ensure_internal_reviewer() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(INTERNAL_REVIEW_ROLES):
        frappe.throw(_("Only internal sales reviewers can perform this action."), frappe.PermissionError)


def is_b2b_only_user(user: str | None = None) -> bool:
    return _has_b2b_only_roles(user)


def get_catalog_products_for_group(customer_group: str, featured_only: bool = False) -> list[frappe._dict]:
    policy_name = _get_policy_name(customer_group)
    if not policy_name:
        return []

    policy = frappe.get_doc("Portal Customer Group Policy", policy_name)
    rows = []
    for row in policy.catalog_items or []:
        if not row.enabled:
            continue
        if featured_only and not row.featured:
            continue
        rows.append(
            frappe._dict(
                name=row.name,
                customer_group=customer_group,
                item_code=row.item_code,
                product_bundle=row.product_bundle,
                portal_title=row.portal_title,
                short_description=row.short_description,
                featured=row.featured,
                sort_order=row.sort_order,
                allow_quote=row.allow_quote,
            )
        )
    rows.sort(key=lambda r: (int(r.sort_order or 0), (r.portal_title or r.item_code or r.product_bundle or "")))
    return rows


def _get_policy_name(customer_group: str) -> str | None:
    if customer_group:
        exact = frappe.db.get_value(
            "Portal Customer Group Policy",
            {"customer_group": customer_group, "enabled": 1},
            "name",
        )
        if exact:
            return exact

    return frappe.db.get_value(
        "Portal Customer Group Policy",
        {"customer_group": DEFAULT_CUSTOMER_GROUP, "enabled": 1},
        "name",
    )


def resolve_portal_price(item_code: str, price_list: str) -> frappe._dict:
    if not item_code or not price_list:
        return frappe._dict(price_list=price_list, currency="", rate=0)

    row = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list},
        ["currency", "price_list_rate"],
        as_dict=True,
    ) or {}
    return frappe._dict(
        price_list=price_list,
        currency=row.get("currency") or frappe.db.get_value("Price List", price_list, "currency") or "",
        rate=row.get("price_list_rate") or 0,
    )


def _resolve_contact(user: str) -> str | None:
    contact = frappe.db.get_value("Contact", {"user": user}, "name")
    if contact:
        return contact
    email = frappe.db.get_value("User", user, "email") or user
    return frappe.db.get_value("Contact", {"email_id": email}, "name")


def _resolve_customer(contact: str) -> str | None:
    rows = frappe.db.sql(
        """
        SELECT link_name
        FROM `tabDynamic Link`
        WHERE parenttype = 'Contact' AND parent = %s AND link_doctype = 'Customer'
        ORDER BY idx ASC
        LIMIT 1
        """,
        (contact,),
        as_list=True,
    )
    if rows:
        return rows[0][0]

    customer = frappe.db.get_value("Customer", {"customer_primary_contact": contact}, "name")
    if customer:
        return customer

    portal_rows = frappe.get_all(
        "Customer",
        filters={"portal_users.user": frappe.session.user},
        fields=["name"],
        limit_page_length=1,
    )
    return portal_rows[0]["name"] if portal_rows else None
