import frappe

from orderlift.menu_access import apply_menu_access_to_bootinfo, get_company_access_payload
from orderlift.restricted_user_guard import (
    BYPASS_ROLES,
    PERMISSION_CONTROLLED_SYSTEM_DOCTYPES,
    RESTRICTED_ROLE,
    _system_doctype_explicitly_allowed,
)


# Doctypes that restricted users must never see in search or access
HIDDEN_DOCTYPES = frozenset([
    "Module Def",
    "Workspace",
    "Workspace Sidebar",
    "DocType",
    "DocType Layout",
    "Customize Form",
    "Custom Field",
    "Custom DocPerm",
    "Property Setter",
    "Client Script",
    "Server Script",
    "System Settings",
    "Notification Settings",
    "Scheduled Job Type",
    "Error Log",
    "Activity Log",
    "Access Log",
    "Route History",
    "Console Log",
    "Module Profile",
    "Role Profile",
    "Email Account",
    "Email Domain",
    "Website Settings",
    "Web Form",
    "Print Format",
    "Auto Repeat",
    "Prepared Report",
    "Installed Application",
    "Installed Applications",
    "Package",
    "System Health Report",
    "System Console",
    "RQ Job",
    "RQ Worker",
    "Role Replication",
    "Document Naming Settings",
    "Scheduled Job Log",
    "Recorder",
    "API Request Log",
    "View Log",
    "Patch Log",
    "Log Settings",
    "SMS Log",
    "SMS Settings",
    "Auto Email Report",
    "Email Queue",
    "Email Group",
    "Email Rule",
    "Email Flag Queue",
    "OAuth Client",
    "OAuth Settings",
    "OAuth Provider Settings",
    "LDAP Settings",
    "Social Login Key",
    "Integration Request",
    "Webhook Request Log",
    "Push Notification Settings",
    "About Us Settings",
    "Contact Us Settings",
    "Portal Settings",
    "Website Script",
    "Website Theme",
    "Print Settings",
    "Navbar Settings",
    "Domain Settings",
    "Session Default Settings",
    "Bulk Update",
    "Permission Inspector",
    "Permission Log",
    "Role Permission for Page and Report",
    "Data Export",
    "Data Import Log",
    "Document Naming Rule",
    "Deleted Document",
    "Submission Queue",
    "Global Search Settings",
    "Geolocation Settings",
    "Google Settings",
    "Desktop Settings",
    "User Type",
    "User Group",
    "Custom Role",
    "Audit Trail",
    "Version",
    "DocShare",
    "Document Share Key",
    "Package Import",
    "Package Release",
    "Milestone",
    "Milestone Tracker",
    "Reminder",
    "Success Action",
])


def extend_bootinfo(bootinfo):
    """Replace ERPNext sidebar subtitle with the user's current company."""
    user = frappe.session.user
    desk_settings = bootinfo.get("desk_settings") or {}
    desk_settings["view_switcher"] = 1
    bootinfo["desk_settings"] = desk_settings
    _apply_orderlift_capabilities_to_bootinfo(bootinfo)
    sidebar_title = _sidebar_company_title(user)
    for app in bootinfo.get("app_data", []):
        if app.get("app_title") in {"ERPNext", "Orderlift"}:
            app["app_title"] = sidebar_title

    _strip_demo_navbar_items(bootinfo)

    # Role-based restriction check
    if user not in ("Guest", None):
        try:
            apply_menu_access_to_bootinfo(bootinfo, user=user)
            _apply_active_company_defaults(bootinfo)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Orderlift boot menu access failed")

    if user in ("Administrator", "Guest"):
        return

    roles = set(frappe.get_roles(user))
    if RESTRICTED_ROLE in roles and not roles.intersection(BYPASS_ROLES):
        bootinfo.is_restricted_shell_user = 1
        _strip_system_doctypes_from_boot(bootinfo)


def _apply_orderlift_capabilities_to_bootinfo(bootinfo) -> None:
    """Expose server-authoritative capability decisions to Desk scripts."""
    can_override = False
    can_manage_stock_rates = False
    privileged_pricing = False
    commission_assignment = False
    commission_payout = False
    opportunity_pipeline_assignment = False
    project_pipeline_assignment = False
    sales_order_pipeline_assignment = False
    if frappe.session.user not in ("Guest", None):
        try:
            can_override = bool(_can_override_quotation_pricing())
            can_manage_stock_rates = bool(_can_manage_stock_rates())
            privileged_pricing = _user_has_capability("privileged_pricing")
            commission_assignment = _user_has_capability("commission_assignment_management")
            commission_payout = _user_has_capability("commission_payout_management")
            opportunity_pipeline_assignment = _user_has_capability("opportunity_pipeline_assignment")
            project_pipeline_assignment = _user_has_capability("project_pipeline_assignment")
            sales_order_pipeline_assignment = _user_has_capability("sales_order_pipeline_assignment")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Orderlift boot capability resolution failed")
    bootinfo["orderlift_capabilities"] = {
        "quotation_override": can_override,
        "stock_rate_access": can_manage_stock_rates,
        "stock_rate_review": can_manage_stock_rates,
        "privileged_pricing": privileged_pricing,
        "commission_assignment_management": commission_assignment,
        "commission_payout_management": commission_payout,
        "pipeline_assignment_management": any(
            (
                opportunity_pipeline_assignment,
                project_pipeline_assignment,
                sales_order_pipeline_assignment,
            )
        ),
        "opportunity_pipeline_assignment": opportunity_pipeline_assignment,
        "project_pipeline_assignment": project_pipeline_assignment,
        "sales_order_pipeline_assignment": sales_order_pipeline_assignment,
    }


def _apply_active_company_defaults(bootinfo) -> None:
    """Expose the browser-session company through Frappe's native client defaults."""
    access = bootinfo.get("orderlift_company_access") or {}
    company = (access.get("current_company") or "").strip()
    if not company:
        return

    sysdefaults = bootinfo.get("sysdefaults") or {}
    sysdefaults["company"] = company
    sysdefaults["Company"] = company
    bootinfo["sysdefaults"] = sysdefaults

    user = bootinfo.get("user") or {}
    defaults = user.get("defaults") or {}
    defaults["company"] = company
    defaults["Company"] = company
    user["defaults"] = defaults
    bootinfo["user"] = user


def _can_override_quotation_pricing() -> bool:
    from orderlift.orderlift_sales.utils.price_list_scope import can_override_quotation_pricing

    return bool(can_override_quotation_pricing())


def _can_manage_stock_rates() -> bool:
    from orderlift.orderlift_logistics.utils.stock_rate_review import can_manage_stock_rates

    return bool(can_manage_stock_rates())


def _user_has_capability(capability: str) -> bool:
    from orderlift.role_capabilities import user_has_capability

    return bool(user_has_capability(capability))


def _sidebar_company_title(user: str | None) -> str:
    return "Orderlift"


def _strip_demo_navbar_items(bootinfo):
    navbar_settings = bootinfo.get("navbar_settings") or {}
    settings_dropdown = (
        navbar_settings.get("settings_dropdown")
        if isinstance(navbar_settings, dict)
        else getattr(navbar_settings, "settings_dropdown", None)
    )
    if not isinstance(settings_dropdown, list):
        return

    filtered = [
        item
        for item in settings_dropdown
        if (item.get("item_label") or item.get("label")) != "Delete Demo Data"
    ]
    if isinstance(navbar_settings, dict):
        navbar_settings["settings_dropdown"] = filtered
    else:
        navbar_settings.settings_dropdown = filtered


def _strip_system_doctypes_from_boot(bootinfo):
    """Remove system doctypes from all boot permission lists so they
    never appear in search, navbar, or any client-side permission check."""
    user_info = bootinfo.get("user") or {}
    hidden_doctypes = _hidden_doctypes_for_boot()

    # Strip from all can_* permission lists
    for key in ("can_read", "can_write", "can_create", "can_delete",
                "can_cancel", "can_search", "can_get_report",
                "can_import", "can_export"):
        items = user_info.get(key)
        if isinstance(items, list):
            user_info[key] = [dt for dt in items if dt not in hidden_doctypes]

    # Strip from allowed_modules if present
    allowed = bootinfo.get("allowed_modules")
    if isinstance(allowed, list):
        bootinfo["allowed_modules"] = [
            m for m in allowed if m not in hidden_doctypes
        ]

    # Strip from module_app mapping
    module_app = bootinfo.get("module_app")
    if isinstance(module_app, dict):
        for dt in hidden_doctypes:
            module_app.pop(dt, None)


def _hidden_doctypes_for_boot() -> set[str]:
    hidden_doctypes = set(HIDDEN_DOCTYPES)
    for doctype in PERMISSION_CONTROLLED_SYSTEM_DOCTYPES:
        try:
            if _system_doctype_explicitly_allowed(doctype, frappe.session.user, "read"):
                hidden_doctypes.discard(doctype)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Orderlift boot system doctype permission check failed")
    return hidden_doctypes
