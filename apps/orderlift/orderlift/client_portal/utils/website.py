from __future__ import annotations

import frappe

from orderlift.client_portal.utils.access import is_b2b_only_user


PORTAL_HOME = "b2b-portal"
SYSTEM_USER_HOME = "main_dashboard_redirect"


def _is_system_user(user: str) -> bool:
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    return frappe.db.get_value("User", user, "user_type") == "System User"


def get_portal_home_page(user: str) -> str | None:
    # Portal-only users should land on the website portal even if their
    # user_type has not yet been normalized on this login.
    if is_b2b_only_user(user):
        return PORTAL_HOME

    # System users → redirect page (which redirects to /desk/home-page)
    if _is_system_user(user):
        return SYSTEM_USER_HOME

    # Guests / others → portal (which shows login or portal home)
    return PORTAL_HOME


def sync_b2b_only_user_type_on_login(login_manager=None) -> None:
    user = getattr(login_manager, "user", None) or frappe.session.user
    if not user or user == "Guest":
        return

    if is_b2b_only_user(user):
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
