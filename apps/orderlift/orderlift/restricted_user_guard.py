"""
Server-side permission guard for restricted business users.

Blocks access to system/build doctypes for users with the "Orderlift Admin"
role who should only operate business documents (Sales Orders, Items,
Customers, etc.) but never touch schema, workspaces, modules, or settings.

Role-based: assign "Orderlift Admin" to any user to activate restrictions.
"""
from __future__ import annotations

import frappe
from werkzeug.wrappers import Response

from orderlift.menu_access import user_can_access_page
from orderlift.retired_pages import RETIRED_PAGE_NAMES, RETIRED_PAGE_REDIRECTS


# The role that triggers all restrictions
RESTRICTED_ROLE = "Orderlift Admin"
TARGET_URL = "/desk/home-page"
LEGACY_CRM_ROUTE_REDIRECTS = {
    "/desk/installation-pipeline": "/desk/opportunity-pipeline",
    "/app/installation-pipeline": "/desk/opportunity-pipeline",
}
RETIRED_PAGE_SLUGS = RETIRED_PAGE_NAMES

# Roles that bypass all restrictions (superadmins)
BYPASS_ROLES = frozenset(["System Manager", "Administrator"])
PERMISSION_CONTROLLED_SYSTEM_DOCTYPES = frozenset()
PERMISSION_CONTROLLED_SYSTEM_SLUGS = {}
PERMISSION_FIELDS = frozenset([
    "select", "read", "write", "create", "delete", "submit", "cancel", "amend",
    "report", "import", "export", "print", "email", "share",
])


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


def _is_system_user(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    return frappe.db.get_value("User", user, "user_type") == "System User"


def _set_redirect(location: str) -> None:
    """Set a safe 307 redirect that works in all before_request contexts."""
    frappe.flags.redirect_location = location
    frappe.local.flags.redirect_location = location

    # If frappe.local.response is already a Response, swap it out.
    if isinstance(frappe.local.response, Response):
        frappe.local.response = Response(
            status=307,
            headers={"Location": location, "Cache-Control": "no-store"},
        )
    else:
        # dict-style response — set redirect fields.
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = location


def _do_redirect() -> None:
    _set_redirect(TARGET_URL)


def redirect_legacy_crm_page_routes() -> None:
    """Normalize removed CRM page URLs to the active Desk routes."""
    request = getattr(frappe.local, "request", None)
    if not request:
        return

    path = (getattr(request, "path", "") or "").rstrip("/")
    location = LEGACY_CRM_ROUTE_REDIRECTS.get(path)
    if not location:
        return

    query = getattr(request, "query_string", b"") or b""
    if query:
        location = f"{location}?{query.decode('utf-8', errors='ignore')}"
    _set_redirect(location)


def block_if_restricted(doc=None, ptype: str | None = None, user: str | None = None, permission_type: str | None = None) -> bool:
    """has_permission handler — return False to deny, True to allow."""
    if isinstance(doc, str) and not user and not ptype and not permission_type:
        user = doc
        doc = None
    user = user or frappe.session.user
    doctype = getattr(doc, "doctype", None)
    if _is_restricted(user):
        return False
    return True


def _system_doctype_explicitly_allowed(doctype: str | None, user: str | None = None, ptype: str | None = None) -> bool:
    if doctype not in PERMISSION_CONTROLLED_SYSTEM_DOCTYPES:
        return False
    return _role_has_docperm(doctype, user or frappe.session.user, ptype or "read")


def _role_has_docperm(doctype: str, user: str, ptype: str) -> bool:
    fieldname = (ptype or "read").lower()
    if fieldname not in PERMISSION_FIELDS:
        fieldname = "read"
    roles = set(frappe.get_roles(user))
    if not roles:
        return False
    filters = {"parent": doctype, "role": ["in", list(roles)], fieldname: 1}
    for perm_doctype in ("Custom DocPerm", "DocPerm"):
        if frappe.db.exists(perm_doctype, filters):
            return True
    return False


def redirect_on_login(login_manager):
    """on_login hook — redirect system users to Main Dashboard."""
    user = getattr(login_manager, "user", None)
    request = getattr(frappe.local, "request", None)
    path = (getattr(request, "path", "") or "").rstrip("/")

    # The themed login page posts via AJAX and expects JSON.
    if path in ("/login", "/api/method/login"):
        return

    if user and _is_system_user(user):
        _do_redirect()


def redirect_bare_desk_route() -> None:
    """Redirect logged-in system users from bare desk entry routes."""
    if not _is_system_user():
        return

    request = getattr(frappe.local, "request", None)
    if not request:
        return
    path = (getattr(request, "path", "") or "").rstrip("/")

    # Website root is handled by get_website_user_home_page.
    if path in ("/desk", "/app"):
        _do_redirect()


def guard_restricted_routes() -> None:
    """before_request hook — redirect restricted users away from system pages."""
    user = frappe.session.user
    if user in ("Administrator", "Guest") or not _is_restricted(user):
        return

    request = getattr(frappe.local, "request", None)
    if not request:
        return
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

    # Extract first slug after /app/ or /desk/
    slug = ""
    if path.startswith("/app/"):
        slug = path[5:].split("/")[0].lower()
    elif path.startswith("/desk/"):
        slug = path[6:].split("/")[0].lower()

    blocked_slugs = (
        "workspace", "workspaces", "module-def", "doctype", "customize-form",
        "account", "cost-center", "chart-of-accounts", "accounting-dimension", "accounting-dimension-detail",
        "system-settings", "server-script", "custom-field",
        "custom-docperm", "property-setter", "client-script", "scheduled-job-type",
        "error-log", "activity-log", "access-log", "route-history", "console-log",
        "module-profile", "role-profile", "email-account",
        "email-domain", "website-settings", "web-form", "print-format", "auto-repeat",
        "prepared-report", "installed-applications", "installed-app", "package",
        "build", "notification-settings", "rq-worker", "rq-job", "scheduled-job-log",
        "recorder", "api-request-log", "view-log", "patch-log", "log-settings",
        "system-console", "system-health-report", "sms-log", "sms-settings",
        "auto-email-report", "email-queue", "email-group",
        "email-rule", "email-flag-queue", "oauth-client", "oauth-settings",
        "oauth-provider-settings", "ldap-settings", "social-login-key",
        "integration-request", "webhook-request-log", "push-notification-settings",
        "about-us-settings", "contact-us-settings", "portal-settings", "website-script",
        "website-theme", "print-settings", "navbar-settings", "domain-settings",
        "session-default-settings", "bulk-update", "permission-inspector",
        "role-permission-for-page-and-report", "data-export", "data-import-log",
        "document-naming-rule", "deleted-document", "submission-queue",
        "global-search-settings", "geolocation-settings", "google-settings",
        "desktop-settings", "user-type", "user-group",
    )

    if slug in blocked_slugs:
        allowed_doctype = PERMISSION_CONTROLLED_SYSTEM_SLUGS.get(slug)
        if allowed_doctype and _system_doctype_explicitly_allowed(allowed_doctype, user, "read"):
            return
        _do_redirect()


def guard_orderlift_menu_routes() -> None:
    """Block direct access to custom Desk pages hidden by menu access rules."""
    user = frappe.session.user
    request = getattr(frappe.local, "request", None)
    if not request:
        return
    path = (getattr(request, "path", "") or "").rstrip("/")
    if not path.startswith(("/app/", "/desk/")):
        return

    slug = ""
    if path.startswith("/app/"):
        slug = path[5:].split("/")[0].lower()
    elif path.startswith("/desk/"):
        slug = path[6:].split("/")[0].lower()
    if slug in RETIRED_PAGE_SLUGS:
        _set_redirect(RETIRED_PAGE_REDIRECTS.get(slug, TARGET_URL))
        return
    if user in ("Administrator", "Guest"):
        return
    if not slug or slug == "home-page":
        return

    try:
        allowed = user_can_access_page(slug, user=user)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Orderlift menu route guard failed")
        if frappe.db.exists("Page", slug):
            module = frappe.db.get_value("Page", slug, "module") or ""
            if module.startswith("Orderlift"):
                _do_redirect()
        return
    if not allowed:
        _do_redirect()
