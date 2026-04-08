from __future__ import annotations

import frappe

from orderlift.client_portal.utils.access import INTERNAL_REVIEW_ROLES, PORTAL_ROLE, is_b2b_only_user


PORTAL_HOME = "b2b-portal"


def get_portal_home_page(user: str) -> str | None:
    return PORTAL_HOME if is_b2b_only_user(user) else None


def sync_b2b_only_user_type_on_login(login_manager=None) -> None:
    user = frappe.session.user
    if not user or user == "Guest":
        return

    roles = set(frappe.get_roles(user))
    if PORTAL_ROLE in roles and not roles.intersection(INTERNAL_REVIEW_ROLES):
        if frappe.db.get_value("User", user, "user_type") != "Website User":
            frappe.db.set_value("User", user, "user_type", "Website User", update_modified=False)


def redirect_b2b_only_users_from_desk() -> None:
    user = frappe.session.user
    if not is_b2b_only_user(user):
        return

    request = getattr(frappe.local, "request", None)
    path = getattr(request, "path", "") or ""
    if not path:
        return

    allowed_prefixes = (
        "/b2b-portal",
        "/login",
        "/logout",
        "/api/",
        "/assets/",
        "/files/",
    )
    if path.startswith(allowed_prefixes):
        return

    if path.startswith("/app") or path.startswith("/desk"):
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"/{PORTAL_HOME}"
        frappe.local.flags.redirect_location = f"/{PORTAL_HOME}"
