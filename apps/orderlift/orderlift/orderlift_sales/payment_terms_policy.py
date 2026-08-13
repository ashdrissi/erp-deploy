from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.reference_access import require_reference_use
from orderlift.role_capabilities import CAPABILITY_QUOTATION_OVERRIDE, user_has_capability


def can_override_payment_terms(user: str | None = None) -> bool:
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user) or [])
    if user == "Administrator" or "Orderlift Admin" in roles:
        return True
    return user_has_capability(CAPABILITY_QUOTATION_OVERRIDE, user=user, roles=roles)


def get_allowed_payment_terms_templates(user: str | None = None) -> list[str]:
    user = user or frappe.session.user
    if can_override_payment_terms(user):
        return frappe.get_all("Payment Terms Template", pluck="name", order_by="name asc", limit_page_length=0)

    sales_person = _sales_person_for_user(user)
    if not sales_person:
        return []
    rules_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name")
    if not rules_name or not frappe.get_meta("Agent Pricing Rules").get_field("allowed_payment_terms"):
        return []
    return frappe.get_all(
        "Agent Allowed Payment Terms",
        filters={
            "parent": rules_name,
            "parenttype": "Agent Pricing Rules",
            "parentfield": "allowed_payment_terms",
            "is_active": 1,
        },
        pluck="payment_terms_template",
        order_by="is_default desc, idx asc",
        limit_page_length=0,
    )


def get_default_payment_terms_template(user: str | None = None) -> str:
    templates = get_allowed_payment_terms_templates(user)
    return templates[0] if templates else ""


@frappe.whitelist()
def get_sales_order_payment_terms_policy(sales_order: str | None = None) -> dict:
    if sales_order and frappe.db.exists("Sales Order", sales_order):
        frappe.get_doc("Sales Order", sales_order).check_permission("read")
    can_override = can_override_payment_terms()
    templates = get_allowed_payment_terms_templates()
    return {
        "can_override": can_override,
        "allowed_templates": templates,
        "default_template": "" if can_override else (templates[0] if templates else ""),
    }


def apply_sales_order_payment_terms_policy(doc, method=None) -> None:
    if not doc or can_override_payment_terms():
        return

    allowed = set(get_allowed_payment_terms_templates())
    template = (doc.get("payment_terms_template") or "").strip()
    if not template:
        template = get_default_payment_terms_template()
        if template:
            doc.payment_terms_template = template
    if template and template not in allowed:
        frappe.throw(
            _("Payment Terms Template {0} is not allocated to your Agent Pricing Rules.").format(template),
            frappe.PermissionError,
        )

    if not template:
        doc.set("payment_schedule", [])
        return

    require_reference_use("Payment Terms Template", template, label="Payment Terms Template")
    from erpnext.controllers.accounts_controller import get_payment_terms

    schedule = get_payment_terms(
        template,
        posting_date=doc.get("transaction_date"),
        grand_total=doc.get("grand_total"),
        base_grand_total=doc.get("base_grand_total"),
    ) or []
    doc.set("payment_schedule", [])
    for row in schedule:
        doc.append("payment_schedule", row)


def _sales_person_for_user(user: str) -> str:
    if not user or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""
