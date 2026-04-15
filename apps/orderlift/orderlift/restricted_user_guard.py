"""
Server-side permission guard for restricted business users.

Blocks access to system/build doctypes for users with the "Orderlift Admin"
role who should only operate business documents (Sales Orders, Items,
Customers, etc.) but never touch schema, workspaces, modules, or settings.

Role-based: assign "Orderlift Admin" to any user to activate restrictions.
"""
from __future__ import annotations

import frappe

# The role that triggers all restrictions
RESTRICTED_ROLE = "Orderlift Admin"

# Roles that bypass all restrictions (superadmins)
BYPASS_ROLES = frozenset(["System Manager", "Administrator", "Developer"])


def _is_restricted(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return False
    roles = set(frappe.get_roles(user))
    if RESTRICTED_ROLE not in roles:
        return False
    if roles.intersection(BYPASS_ROLES):
        return False
    return True


def block_if_restricted(user: str | None = None) -> bool:
    """has_permission handler — return False to deny, True to allow."""
    if _is_restricted(user):
        return False
    return True


def redirect_bare_desk_route() -> None:
    """Always send bare /desk to Main Dashboard shell."""
    request = getattr(frappe.local, "request", None)
    path = (getattr(request, "path", "") or "").rstrip("/")
    if path == "/desk":
        _redirect_home()


def redirect_on_login(login_manager):
    """on_login hook — redirect restricted users to /desk/home-page."""
    user = getattr(login_manager, "user", None)
    if user and _is_restricted(user):
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/desk/home-page?sidebar=Main+Dashboard"


def guard_restricted_routes() -> None:
    """before_request hook — redirect restricted users away from system pages."""
    user = frappe.session.user
    if not _is_restricted(user):
        return

    request = getattr(frappe.local, "request", None)
    path = (getattr(request, "path", "") or "").rstrip("/")
    if not path:
        return

    # Always allow these
    allowed_prefixes = (
        "/api/",
        "/assets/",
        "/files/",
        "/login",
        "/logout",
        "/app/home-page",
        "/desk/home-page",
    )
    if path.startswith(allowed_prefixes):
        return

    # Block bare /desk and /app (shows module cards / default landing)
    if path in ("/desk", "/app"):
        _redirect_home()
        return

    # Block these exact paths or prefixes (both /app and /desk variants)
    blocked_slugs = (
        "workspace",
        "workspaces",
        "module-def",
        "doctype",
        "customize-form",
        "system-settings",
        "server-script",
        "data-import",
        "custom-field",
        "custom-docperm",
        "property-setter",
        "client-script",
        "scheduled-job-type",
        "error-log",
        "activity-log",
        "access-log",
        "route-history",
        "console-log",
        "module-profile",
        "role",
        "role-profile",
        "user-permission",
        "email-account",
        "email-domain",
        "website-settings",
        "web-form",
        "print-format",
        "auto-repeat",
        "prepared-report",
        "installed-applications",
        "installed-app",
        "package",
        "build",
        "notification-settings",
        "rq-worker",
        "rq-job",
        "scheduled-job-log",
        "recorder",
        "api-request-log",
        "view-log",
        "patch-log",
        "log-settings",
        "system-console",
        "system-health-report",
        "sms-log",
        "sms-settings",
        "assignment-rule",
        "auto-email-report",
        "email-queue",
        "email-group",
        "email-rule",
        "email-flag-queue",
        "oauth-client",
        "oauth-settings",
        "oauth-provider-settings",
        "ldap-settings",
        "social-login-key",
        "integration-request",
        "webhook-request-log",
        "push-notification-settings",
        "about-us-settings",
        "contact-us-settings",
        "portal-settings",
        "website-script",
        "website-theme",
        "website-settings",
        "print-settings",
        "navbar-settings",
        "domain-settings",
        "session-default-settings",
        "bulk-update",
        "permission-inspector",
        "role-permission-for-page-and-report",
        "data-export",
        "data-import-log",
        "document-naming-rule",
        "deleted-document",
        "submission-queue",
        "global-search-settings",
        "geolocation-settings",
        "google-settings",
        "desktop-settings",
        "user-type",
        "user-group",
    )

    # Extract first slug after /app/ or /desk/
    slug = ""
    if path.startswith("/app/"):
        slug = path[5:].split("/")[0].lower()
    elif path.startswith("/desk/"):
        slug = path[6:].split("/")[0].lower()

    if slug in blocked_slugs:
        _redirect_home()
        return


def _redirect_home() -> None:
    from werkzeug.wrappers import Response

    target = "/desk/home-page?sidebar=Main+Dashboard"
    frappe.local.response = Response(
        status=302,
        headers={"Location": target, "Cache-Control": "no-store"},
    )
