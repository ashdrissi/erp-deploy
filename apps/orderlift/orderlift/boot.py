import frappe

from orderlift.restricted_user_guard import RESTRICTED_ROLE, BYPASS_ROLES


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
    "Data Import",
    "Notification Settings",
    "Scheduled Job Type",
    "Error Log",
    "Activity Log",
    "Access Log",
    "Route History",
    "Console Log",
    "Module Profile",
    "Role Profile",
    "User Permission",
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
    "Assignment Rule",
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
    """Replace 'ERPNext' app title with 'Orderlift' in the sidebar subtitle."""
    for app in bootinfo.get("app_data", []):
        if app.get("app_title") == "ERPNext":
            app["app_title"] = "Orderlift"

    # Role-based restriction check
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return

    roles = set(frappe.get_roles(user))
    if RESTRICTED_ROLE in roles and not roles.intersection(BYPASS_ROLES):
        bootinfo.is_restricted_shell_user = 1
        _strip_system_doctypes_from_boot(bootinfo)


def _strip_system_doctypes_from_boot(bootinfo):
    """Remove system doctypes from all boot permission lists so they
    never appear in search, navbar, or any client-side permission check."""
    user_info = bootinfo.get("user") or {}

    # Strip from all can_* permission lists
    for key in ("can_read", "can_write", "can_create", "can_delete",
                "can_cancel", "can_search", "can_get_report",
                "can_import", "can_export"):
        items = user_info.get(key)
        if isinstance(items, list):
            user_info[key] = [dt for dt in items if dt not in HIDDEN_DOCTYPES]

    # Strip from allowed_modules if present
    allowed = bootinfo.get("allowed_modules")
    if isinstance(allowed, list):
        bootinfo["allowed_modules"] = [
            m for m in allowed if m not in HIDDEN_DOCTYPES
        ]

    # Strip from module_app mapping
    module_app = bootinfo.get("module_app")
    if isinstance(module_app, dict):
        for dt in HIDDEN_DOCTYPES:
            module_app.pop(dt, None)
