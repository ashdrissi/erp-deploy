from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from orderlift.menu_access import (
    get_all_companies,
    get_allowed_business_types,
    get_allowed_companies,
    get_user_default_company,
    get_menu_access_payload,
    save_menu_access_for_role as _save_menu_access_for_role,
    save_user_business_type_access as _save_user_business_type_access,
    save_user_company_access as _save_user_company_access,
    sync_menu_access_rules,
    user_can_access_all_business_types,
    user_can_access_all_companies,
)
from orderlift.menu_registry import BUSINESS_ROLES
from orderlift.company_access import ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES
from orderlift.role_capabilities import (
    ROLE_CAPABILITY_FIELD,
    capability_options,
    normalize_capabilities,
    serialize_capabilities,
)
from orderlift.orderlift_crm.company_business_type import get_company_business_type_names
from orderlift.warehouse_access import (
    get_selected_warehouses,
    get_visible_warehouses,
    save_user_warehouse_access as _save_user_warehouse_access,
)


SUPERADMIN_VISIBLE_ROLES = ["Administrator", "System Manager", "Developer"]
BUSINESS_ROLE_SET = set(BUSINESS_ROLES)


PERMISSION_FIELDS = (
    "select",
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "import",
    "export",
    "print",
    "email",
    "share",
)
HIDDEN_PERMISSION_FIELDS = ("if_owner",)
MANAGED_FORCED_OFF_PERMISSION_FIELDS = ("share",)
MANAGED_PERMISSION_DOCTYPE_SET = set(ORDERLIFT_MANAGED_SHARE_DISABLED_DOCTYPES)

ADMIN_ROLES = {"Administrator", "System Manager", "Developer"}
HIGH_ACCESS_ROLES = {"System Manager", "Administrator", "Developer", "Orderlift Admin"}
PROTECTED_DOCTYPES = {"User", "Role", "DocType", "Custom DocPerm", "DocPerm", "Page", "Report", "Workspace"}
BACKEND_FINANCE_PERMISSION_DOCTYPES = {"Account", "Cost Center", "Accounting Dimension", "Accounting Dimension Detail"}
LEGACY_ROLE_KEYWORDS = ("legacy", "old", "deprecated")
NON_BUSINESS_CUSTOM_ROLES = {"Employee Self Service"}
CRITICAL_USERS = {"Administrator"}
AUDIT_DOCTYPES = ["User", "Role", "Custom DocPerm", "Page", "Report", "User Permission", "Orderlift Menu Access Rule"]
MATRIX_DOCTYPE_LIMIT = 10000
ACCESS_CENTER_USER_PERMISSION_DOCTYPES = {"Company", "CRM Business Type", "Warehouse"}


MATRIX_DOCTYPE_GROUPS = (
    {
        "key": "access_admin",
        "label": "Access & Administration",
        "members": (
            "User", "Role", "Role Profile", "User Permission", "Custom DocPerm", "DocPerm", "Page", "Report",
            "Workspace", "Workflow", "Workflow State", "Assignment Rule", "Orderlift Menu Access Rule",
            "Module Def", "DocType", "Custom Field", "Property Setter", "Client Script", "Server Script",
        ),
        "prefixes": ("User", "Role", "Workflow", "DocPerm", "Page", "Report", "Workspace"),
    },
    {
        "key": "company_classification",
        "label": "Company & Classification",
        "members": (
            "Company", "CRM Business Type", "CRM Segment", "CRM Segment Assignment", "Partner Segment",
            "Territory", "Customer Group", "Sales Person", "Department", "Branch",
        ),
        "prefixes": ("Company", "CRM", "Partner Segment", "Territory", "Customer Group", "Sales Person"),
    },
    {
        "key": "crm_parties",
        "label": "CRM Parties",
        "members": ("Lead", "Prospect", "Customer", "Contact", "Address", "Communication", "ToDo", "Event", "Dynamic Link", "Sales Team"),
        "prefixes": ("Lead", "Prospect", "Customer", "Contact", "Address", "Communication", "ToDo", "Event"),
    },
    {"key": "opportunity", "label": "Opportunity", "members": ("Opportunity",), "prefixes": ("Opportunity", "Sales Stage")},
    {"key": "quotation", "label": "Quotation", "members": ("Quotation",), "prefixes": ("Quotation",)},
    {"key": "sales_order", "label": "Sales Order", "members": ("Sales Order", "Orderlift Order Status"), "prefixes": ("Sales Order", "Orderlift Order")},
    {
        "key": "sales_finance",
        "label": "Sales Invoicing & Payment",
        "members": ("Sales Invoice", "Payment Entry", "Payment Request", "Mode of Payment", "Payment Terms Template", "Payment Schedule"),
        "prefixes": ("Sales Invoice", "Payment Entry", "Payment", "Mode of Payment"),
    },
    {
        "key": "purchasing",
        "label": "Purchasing",
        "members": ("Supplier", "Material Request", "Request for Quotation", "Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice"),
        "prefixes": ("Supplier", "Material Request", "Request for Quotation", "Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice"),
    },
    {
        "key": "item_catalog",
        "label": "Item & Catalog",
        "members": ("Item", "Item Group", "Item Attribute", "Item Price", "Price List", "Product Bundle", "Item Alternative", "Item Manufacturer"),
        "prefixes": ("Item", "Price List", "Product Bundle", "Website Item"),
    },
    {
        "key": "stock_warehouse",
        "label": "Stock & Warehouse",
        "members": ("Warehouse", "Bin", "Stock Entry", "Stock Ledger Entry", "Stock Reconciliation", "Pick List", "Delivery Note", "Quality Inspection"),
        "prefixes": ("Warehouse", "Bin", "Stock", "Pick List", "Delivery Note", "Quality Inspection", "Serial No", "Batch"),
    },
    {
        "key": "logistics",
        "label": "Logistics",
        "members": ("Forecast Load Plan", "Logistics Pipeline Status", "Container Profile", "Shipment", "Delivery Trip", "Delivery Stop", "Vehicle", "Driver"),
        "prefixes": ("Forecast Load", "Logistics", "Container", "Shipment", "Delivery Trip", "Delivery Stop", "Vehicle", "Driver"),
    },
    {
        "key": "pricing_builder",
        "label": "Pricing Builder",
        "members": ("Pricing Sheet", "Pricing Scenario", "Pricing Benchmark Policy", "Pricing Customs Policy", "Pricing Tier", "Agent Pricing Rules", "Customer Segmentation Engine"),
        "prefixes": ("Pricing", "Agent Pricing", "Customer Segmentation"),
    },
    {
        "key": "projects_installation",
        "label": "Projects & Installation",
        "members": ("Project", "Task", "Timesheet", "Project Status", "Installation Stage", "Maintenance Schedule", "Maintenance Visit", "Contract"),
        "prefixes": ("Project", "Task", "Timesheet", "Installation", "Maintenance", "Contract"),
    },
    {"key": "sav_service", "label": "SAV & Service", "members": ("SAV Ticket", "Issue", "Warranty Claim"), "prefixes": ("SAV", "Issue", "Warranty")},
    {
        "key": "b2b_portal",
        "label": "B2B Portal",
        "members": ("Portal Customer Group Policy", "Portal Quote Request", "Web Form", "Website User"),
        "prefixes": ("Portal", "Web Form", "Website"),
    },
    {
        "key": "campaigns",
        "label": "Campaigns & Outreach",
        "members": ("Partner Campaign", "Partner Campaign Target", "Partner Campaign Status", "Campaign", "Email Campaign", "Email Template", "Newsletter"),
        "prefixes": ("Partner Campaign", "Campaign", "Email", "Newsletter"),
    },
    {
        "key": "hr_performance",
        "label": "HR & Performance",
        "members": ("Employee", "Salary Slip", "Payroll Entry", "Appraisal", "Appraisal Cycle", "Goal", "Performance Metric", "Performance Profile", "Performance Metric Snapshot", "Training Program", "Training Module", "Training Quiz"),
        "prefixes": ("Employee", "Salary", "Payroll", "Appraisal", "Goal", "Performance", "Training"),
    },
    {
        "key": "accounting_backend",
        "label": "Accounting Backend",
        "members": ("Account", "Cost Center", "Accounting Dimension", "Accounting Dimension Detail", "Journal Entry", "GL Entry", "Fiscal Year", "Finance Book"),
        "prefixes": ("Account", "Cost Center", "Accounting", "Journal Entry", "GL Entry", "Fiscal", "Finance Book"),
    },
)


@frappe.whitelist()
def get_access_command_center_data(
    search: str | None = None,
    selected_role: str | None = None,
    doctype_search: str | None = None,
    report_search: str | None = None,
) -> dict:
    _require_access_manager()
    users = _get_users(search)
    roles = _get_roles(search)
    selected_role = selected_role if selected_role and selected_role in _visible_role_names() and frappe.db.exists("Role", selected_role) else _default_role(roles)
    return {
        "summary": _get_summary(),
        "users": users,
        "roles": roles,
        "all_roles": _get_roles(),
        "role_profiles": _get_role_profiles(search),
        "companies": _get_companies(),
        "warehouses": _get_warehouses(),
        "business_types": _get_business_types(),
        "menu_access": _get_menu_access(),
        "permission_matrix": _get_permission_matrix(selected_role, doctype_search),
        "selected_role": selected_role,
        "page_access": _get_page_access(search),
        "report_access": _get_report_access(report_search or search),
        "user_permissions": _get_user_permissions(search),
        "audit_log": _get_audit_log(),
        "last_sync": str(now_datetime()),
        "permission_fields": list(PERMISSION_FIELDS),
        "role_capabilities": capability_options(),
    }


@frappe.whitelist()
def save_user_basic_info(payload: str | dict) -> dict:
    _require_access_manager()
    data = _loads(payload)
    user_name = (data.get("name") or "").strip()
    if not user_name or not frappe.db.exists("User", user_name):
        frappe.throw(_("User was not found."))
    _assert_user_scope(user_name)
    if user_name == frappe.session.user and not cint(data.get("enabled", 1)):
        frappe.throw(_("You cannot disable your own user account."))
    if _is_critical_user(user_name) and not cint(data.get("enabled", 1)):
        frappe.throw(_("The Administrator account cannot be disabled from Access Command Center."))

    user = frappe.get_doc("User", user_name)
    if not cint(data.get("enabled", 1)) and _has_role(user, "System Manager") and _enabled_system_manager_count() <= 1:
        frappe.throw(_("At least one enabled System Manager must remain available."))
    _set_if_field(user, "full_name", (data.get("full_name") or "").strip())
    _set_if_field(user, "enabled", cint(data.get("enabled", 1)))
    _set_if_field(user, "custom_owned_documents_only", cint(data.get("custom_owned_documents_only", 0)))
    _set_if_field(user, "user_type", data.get("user_type") or user.get("user_type"))
    _set_if_field(user, "default_workspace", (data.get("default_workspace") or "").strip())
    role_profile = (data.get("role_profile_name") or "").strip()
    if role_profile and not frappe.db.exists("Role Profile", role_profile):
        frappe.throw(_("Role Profile {0} was not found.").format(role_profile))
    _assert_role_profile_scope(role_profile)
    _set_if_field(user, "role_profile_name", role_profile)
    user.save(ignore_permissions=True)
    _add_audit_note("User", user.name, data.get("audit_note"), _("Updated user details."))
    frappe.db.commit()
    return get_user_detail(user.name)


@frappe.whitelist()
def delete_user(user_name: str, audit_note: str | None = None) -> dict:
    _require_access_manager()
    user_name = (user_name or "").strip()
    if not user_name or not frappe.db.exists("User", user_name):
        frappe.throw(_("User {0} was not found.").format(user_name))
    if user_name == frappe.session.user:
        frappe.throw(_("You cannot delete your own user account."))
    _assert_user_scope(user_name)
    if _is_critical_user(user_name):
        frappe.throw(_("The Administrator account cannot be deleted from Access Command Center."))

    user = frappe.get_doc("User", user_name)
    if _has_role(user, "System Manager") and cint(user.get("enabled")) and _enabled_system_manager_count() <= 1:
        frappe.throw(_("At least one enabled System Manager must remain available."))

    _add_audit_note("User", user_name, audit_note, _("Deleted user from Access Command Center."))
    frappe.delete_doc("User", user_name, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": user_name}


@frappe.whitelist()
def create_user(payload: str | dict) -> dict:
    _require_access_manager()
    data = _loads(payload)
    email = (data.get("email") or "").strip()
    if not email:
        frappe.throw(_("Email is required."))
    if frappe.db.exists("User", email):
        frappe.throw(_("User {0} already exists.").format(email))

    roles = _clean_list(data.get("roles"))
    _assert_role_scope(roles)
    missing = [role for role in roles if not frappe.db.exists("Role", role)]
    if missing:
        frappe.throw(_("Unknown roles: {0}").format(", ".join(missing)))

    full_name = (data.get("full_name") or "").strip()
    user = frappe.new_doc("User")
    user.email = email
    user.first_name = full_name or email.split("@")[0]
    user.full_name = full_name or email
    user.enabled = cint(data.get("enabled", 1))
    user.user_type = data.get("user_type") or "System User"
    if user.meta.get_field("send_welcome_email"):
        user.send_welcome_email = cint(data.get("send_welcome_email", 0))
    role_profile = (data.get("role_profile_name") or "").strip()
    if role_profile:
        if not frappe.db.exists("Role Profile", role_profile):
            frappe.throw(_("Role Profile {0} was not found.").format(role_profile))
        _assert_role_profile_scope(role_profile)
        user.role_profile_name = role_profile
    for idx, role in enumerate(roles, start=1):
        user.append("roles", {"role": role, "idx": idx})
    user.insert(ignore_permissions=True)
    _add_audit_note("User", user.name, data.get("audit_note"), _("Created user from Access Command Center."))
    frappe.db.commit()
    return get_user_detail(user.name)


@frappe.whitelist()
def save_user_roles(user_name: str, roles: str | list, audit_note: str | None = None) -> dict:
    _require_access_manager()
    if not frappe.db.exists("User", user_name):
        frappe.throw(_("User {0} was not found.").format(user_name))
    _assert_user_scope(user_name)
    role_names = _clean_list(roles)
    _assert_role_scope(role_names)
    missing = [role for role in role_names if not frappe.db.exists("Role", role)]
    if missing:
        frappe.throw(_("Unknown roles: {0}").format(", ".join(missing)))

    user = frappe.get_doc("User", user_name)
    current_roles = [row.role for row in user.get("roles", []) if row.role]
    role_names = _merge_scoped_roles(current_roles, role_names)
    if user_name == frappe.session.user and "System Manager" in _session_roles() and "System Manager" not in role_names and frappe.session.user != "Administrator":
        frappe.throw(_("You cannot remove your own System Manager role from this page."))
    if _is_critical_user(user_name) and "System Manager" not in role_names:
        frappe.throw(_("Administrator must keep the System Manager role."))
    if "System Manager" in current_roles and "System Manager" not in role_names and cint(user.get("enabled")) and _enabled_system_manager_count() <= 1:
        frappe.throw(_("At least one enabled System Manager must remain available."))
    user.set("roles", [])
    for idx, role in enumerate(role_names, start=1):
        user.append("roles", {"role": role, "idx": idx})
    user.save(ignore_permissions=True)
    _add_audit_note("User", user.name, audit_note, _("Updated assigned roles."))
    frappe.db.commit()
    return get_user_detail(user.name)


@frappe.whitelist()
def save_user_companies(
    user_name: str,
    companies: str | list,
    default_company: str | None = None,
    audit_note: str | None = None,
) -> dict:
    _require_access_manager()
    _assert_user_scope(user_name)
    _assert_company_assignment_scope(_clean_list(companies), default_company)
    result = _save_user_company_access(user_name, companies, default_company=default_company)
    _cleanup_company_dependent_user_permissions(user_name)
    _add_audit_note("User", user_name, audit_note, _("Updated assigned companies."))
    frappe.db.commit()
    return {**result, "user_detail": get_user_detail(user_name)}


@frappe.whitelist()
def save_user_business_types(
    user_name: str,
    business_types: str | list,
    audit_note: str | None = None,
) -> dict:
    _require_access_manager()
    _assert_user_scope(user_name)
    _assert_business_type_assignment_scope(_clean_list(business_types))
    _assert_business_types_match_user_companies(user_name, _clean_list(business_types))
    result = _save_user_business_type_access(user_name, business_types)
    _add_audit_note("User", user_name, audit_note, _("Updated assigned business types."))
    frappe.db.commit()
    return {**result, "user_detail": get_user_detail(user_name)}


@frappe.whitelist()
def save_user_warehouses(
    user_name: str,
    warehouses: str | list,
    audit_note: str | None = None,
) -> dict:
    _require_access_manager()
    _assert_user_scope(user_name)
    _assert_warehouse_assignment_scope(_clean_list(warehouses))
    _assert_warehouses_match_user_companies(user_name, _clean_list(warehouses))
    result = _save_user_warehouse_access(user_name, warehouses)
    _add_audit_note("User", user_name, audit_note, _("Updated assigned warehouses."))
    frappe.db.commit()
    return {**result, "user_detail": get_user_detail(user_name)}


@frappe.whitelist()
def save_menu_access_for_role(role: str, menu_keys: str | list, audit_note: str | None = None) -> dict:
    _require_access_manager()
    _assert_role_scope([role])
    result = _save_menu_access_for_role(role, menu_keys)
    _add_audit_note("Role", role, audit_note, _("Updated menu access for role."))
    frappe.db.commit()
    return {**result, "menu_access": _get_menu_access()}


@frappe.whitelist()
def save_role(payload: str | dict) -> dict:
    _require_access_manager()
    data = _loads(payload)
    role_name = _validate_role_name(data.get("name") or data.get("role_name"))
    current_name = (data.get("current_name") or "").strip()
    _assert_role_scope([current_name or role_name, role_name])

    if current_name:
        if not frappe.db.exists("Role", current_name):
            frappe.throw(_("Role {0} was not found.").format(current_name))
        existing = frappe.get_doc("Role", current_name)
        if _is_protected_role_doc(existing):
            frappe.throw(_("Protected/system roles cannot be edited here. Use a custom role instead."))
        role = existing
        if role_name != current_name:
            frappe.throw(_("Renaming roles is not supported here. Create a new custom role instead."))
    else:
        if frappe.db.exists("Role", role_name):
            frappe.throw(_("Role {0} already exists.").format(role_name))
        role = frappe.new_doc("Role")
        role.role_name = role_name
        if role.meta.get_field("is_custom"):
            role.is_custom = 1

    if role.meta.get_field("desk_access"):
        role.desk_access = cint(data.get("desk_access", 1))
    if role.meta.get_field("disabled"):
        role.disabled = cint(data.get("disabled", 0))
    if role.meta.get_field("two_factor_auth"):
        role.two_factor_auth = cint(data.get("two_factor_auth", 0))
    if role.meta.get_field(ROLE_CAPABILITY_FIELD):
        role.set(ROLE_CAPABILITY_FIELD, serialize_capabilities(data.get("capabilities")))

    if role.is_new():
        role.insert(ignore_permissions=False)
    else:
        role.save(ignore_permissions=False)
    _add_audit_note("Role", role.name, data.get("audit_note"), _("Updated custom role from Access Command Center."))
    frappe.db.commit()
    return {"role": _role_payload(role.name)}


@frappe.whitelist()
def delete_role(role_name: str, audit_note: str | None = None) -> dict:
    _require_access_manager()
    role_name = (role_name or "").strip()
    _assert_role_scope([role_name])
    if not frappe.db.exists("Role", role_name):
        frappe.throw(_("Role {0} was not found.").format(role_name))
    role = frappe.get_doc("Role", role_name)
    if _is_protected_role_doc(role):
        frappe.throw(_("Protected/system roles cannot be deleted."))
    references = _role_dependency_summary(role_name)
    if references:
        frappe.throw(_("Role {0} is still referenced: {1}. Remove references before deleting.").format(role_name, ", ".join(references)))

    _add_audit_note("Role", role.name, audit_note, _("Deleted custom role from Access Command Center."))
    role.delete(ignore_permissions=False)
    frappe.db.commit()
    return {"deleted": role_name}


@frappe.whitelist()
def bulk_update_user_roles(user_names: str | list, role: str, action: str, audit_note: str | None = None) -> dict:
    _require_access_manager()
    users = _clean_list(user_names)
    role = (role or "").strip()
    action = (action or "add").strip().lower()
    if action not in {"add", "remove"}:
        frappe.throw(_("Bulk role action must be add or remove."))
    if not users:
        frappe.throw(_("Select at least one user."))
    _assert_role_scope([role])
    if not frappe.db.exists("Role", role):
        frappe.throw(_("Role {0} was not found.").format(role))

    updated = 0
    for user_name in users:
        if not frappe.db.exists("User", user_name):
            frappe.throw(_("User {0} was not found.").format(user_name))
        _assert_user_scope(user_name)
        user = frappe.get_doc("User", user_name)
        roles = [row.role for row in user.get("roles", []) if row.role]
        if action == "add":
            if role in roles:
                continue
            roles.append(role)
        else:
            if role not in roles:
                continue
            if user_name == frappe.session.user and role == "System Manager" and frappe.session.user != "Administrator":
                frappe.throw(_("You cannot remove your own System Manager role from this page."))
            if _is_critical_user(user_name) and role == "System Manager":
                frappe.throw(_("Administrator must keep the System Manager role."))
            if role == "System Manager" and cint(user.get("enabled")) and _enabled_system_manager_count() <= 1:
                frappe.throw(_("At least one enabled System Manager must remain available."))
            roles.remove(role)
        user.set("roles", [])
        for idx, role_name in enumerate(roles, start=1):
            user.append("roles", {"role": role_name, "idx": idx})
        user.save(ignore_permissions=True)
        _add_audit_note("User", user.name, audit_note, _("Bulk role assignment updated."))
        updated += 1
    frappe.db.commit()
    return {"updated": updated}


@frappe.whitelist()
def save_user_permission(payload: str | dict) -> dict:
    _require_access_manager()
    data = _loads(payload)
    permission_name = (data.get("name") or "").strip()
    user_name = (data.get("user") or "").strip()
    allow = (data.get("allow") or "").strip()
    for_value = (data.get("for_value") or "").strip()
    if not frappe.db.exists("User", user_name):
        frappe.throw(_("User {0} was not found.").format(user_name))
    _assert_user_scope(user_name)
    if not frappe.db.exists("DocType", allow):
        frappe.throw(_("Allowed DocType {0} was not found.").format(allow))
    if not for_value:
        frappe.throw(_("Allowed value is required."))
    _validate_user_permission_scope(allow, for_value)

    permission = frappe.get_doc("User Permission", permission_name) if permission_name else frappe.new_doc("User Permission")
    if permission_name:
        _validate_user_permission_scope(permission.allow, permission.for_value)
    permission.user = user_name
    permission.allow = allow
    permission.for_value = for_value
    permission.apply_to_all_doctypes = cint(data.get("apply_to_all_doctypes", 1))
    permission.applicable_for = (data.get("applicable_for") or "").strip()
    permission.is_default = cint(data.get("is_default", 0))
    if permission.is_new():
        permission.insert(ignore_permissions=True)
    else:
        permission.save(ignore_permissions=True)
    _add_audit_note("User Permission", permission.name, data.get("audit_note"), _("Updated user permission from Access Command Center."))
    frappe.db.commit()
    return {"user_permissions": _get_user_permissions(user_name)}


@frappe.whitelist()
def delete_user_permission(permission_name: str, audit_note: str | None = None) -> dict:
    _require_access_manager()
    permission_name = (permission_name or "").strip()
    if not frappe.db.exists("User Permission", permission_name):
        frappe.throw(_("User Permission {0} was not found.").format(permission_name))
    user_name, allow, for_value = frappe.db.get_value("User Permission", permission_name, ["user", "allow", "for_value"])
    _assert_user_scope(user_name)
    _validate_user_permission_scope(allow, for_value)
    _add_audit_note("User Permission", permission_name, audit_note, _("Deleted user permission from Access Command Center."))
    frappe.delete_doc("User Permission", permission_name, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": permission_name}


@frappe.whitelist()
def get_user_detail(user_name: str) -> dict:
    _require_access_manager()
    if not frappe.db.exists("User", user_name):
        frappe.throw(_("User {0} was not found.").format(user_name))
    _assert_user_scope(user_name)
    user = frappe.get_doc("User", user_name)
    roles = [row.role for row in user.get("roles", []) if row.role]
    visible_roles = _filter_roles_for_session(roles)
    user_permissions = frappe.get_all(
        "User Permission",
        filters={"user": user_name},
        fields=["name", "allow", "for_value", "apply_to_all_doctypes", "applicable_for", "is_default"],
        order_by="modified desc",
        limit_page_length=50,
    )
    return {
        "name": user.name,
        "email": user.get("email") or user.name,
        "full_name": user.get("full_name") or user.name,
        "enabled": cint(user.get("enabled")),
        "custom_owned_documents_only": cint(user.get("custom_owned_documents_only") or 0),
        "user_type": user.get("user_type") or "",
        "last_login": str(user.get("last_login") or ""),
        "role_profile_name": user.get("role_profile_name") or "",
        "default_workspace": user.get("default_workspace") or "",
        "roles": visible_roles,
        "role_count": len(visible_roles),
        "access_level": _access_level(visible_roles),
        "allowed_companies": get_allowed_companies(user.name),
        "default_company": get_user_default_company(user.name),
        "allowed_business_types": get_allowed_business_types(user.name),
        "allowed_warehouses": get_selected_warehouses(user.name),
        "user_permissions": user_permissions,
        "warnings": _user_warnings(user.name, roles),
    }


@frappe.whitelist()
def save_custom_docperm(role: str, doctype_name: str, values: str | dict, audit_note: str | None = None) -> dict:
    _require_access_manager()
    _assert_role_scope([role])
    if not frappe.db.exists("Role", role):
        frappe.throw(_("Role {0} was not found.").format(role))
    if not frappe.db.exists("DocType", doctype_name):
        frappe.throw(_("DocType {0} was not found.").format(doctype_name))

    data = _loads(values)
    flags = _coerce_permission_flags(data)
    permlevel = cint(data.get("permlevel", 0))
    docperm = _save_custom_docperm_record(role, doctype_name, flags, permlevel)
    _add_audit_note("Custom DocPerm", docperm.name, audit_note, _("Updated permission override."))
    frappe.clear_cache(doctype=doctype_name)
    frappe.db.commit()
    return _get_permission_matrix(role, data.get("doctype_search"))


@frappe.whitelist()
def save_custom_docperms(role: str, changes: str | list, audit_note: str | None = None) -> dict:
    _require_access_manager()
    _assert_role_scope([role])
    if not frappe.db.exists("Role", role):
        frappe.throw(_("Role {0} was not found.").format(role))

    rows = _loads(changes)
    if not isinstance(rows, list) or not rows:
        frappe.throw(_("Select at least one permission row to save."))

    prepared = []
    for row in rows:
        data = _loads(row)
        doctype_name = (data.get("doctype") or "").strip()
        if not frappe.db.exists("DocType", doctype_name):
            frappe.throw(_("DocType {0} was not found.").format(doctype_name))
        prepared.append((doctype_name, _coerce_permission_flags(data, doctype_name), cint(data.get("permlevel", 0))))

    saved = []
    for doctype_name, flags, permlevel in prepared:
        docperm = _save_custom_docperm_record(role, doctype_name, flags, permlevel)
        saved.append(docperm.name)
        _add_audit_note("Custom DocPerm", docperm.name, audit_note, _("Updated permission override."))
        frappe.clear_cache(doctype=doctype_name)
    frappe.db.commit()
    return {"saved": saved, "permission_matrix": _get_permission_matrix(role)}


def _save_custom_docperm_record(role: str, doctype_name: str, flags: dict, permlevel: int):
    flags = _force_disabled_permission_flags(doctype_name, flags)
    _validate_permission_edit(role, doctype_name, flags)

    filters = {"parent": doctype_name, "role": role, "permlevel": permlevel}
    doc_name = frappe.db.exists("Custom DocPerm", filters)
    docperm = frappe.get_doc("Custom DocPerm", doc_name) if doc_name else frappe.get_doc(
        {
            "doctype": "Custom DocPerm",
            "parent": doctype_name,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            "permlevel": permlevel,
        }
    )
    for fieldname in PERMISSION_FIELDS:
        setattr(docperm, fieldname, flags[fieldname])
    for fieldname in HIDDEN_PERMISSION_FIELDS:
        setattr(docperm, fieldname, 0)
    if doc_name:
        docperm.save(ignore_permissions=True)
    else:
        docperm.insert(ignore_permissions=True)
    return docperm


@frappe.whitelist()
def delete_custom_docperm(role: str, doctype_name: str, permlevel: int = 0, audit_note: str | None = None) -> dict:
    _require_access_manager()
    _assert_role_scope([role])
    _validate_permission_edit(role, doctype_name, {field: 1 for field in PERMISSION_FIELDS})
    doc_name = frappe.db.exists("Custom DocPerm", {"parent": doctype_name, "role": role, "permlevel": cint(permlevel)})
    if doc_name:
        frappe.delete_doc("Custom DocPerm", doc_name, ignore_permissions=True)
        _add_audit_note("DocType", doctype_name, audit_note, _("Reset custom permission override for role {0}.").format(role))
        frappe.clear_cache(doctype=doctype_name)
        frappe.db.commit()
    return _get_permission_matrix(role)


@frappe.whitelist()
def save_page_access(page_name: str, roles: str | list, audit_note: str | None = None) -> dict:
    _require_access_manager()
    if not frappe.db.exists("Page", page_name):
        frappe.throw(_("Page {0} was not found.").format(page_name))
    _save_child_roles("Page", page_name, roles)
    _add_audit_note("Page", page_name, audit_note, _("Updated page access roles."))
    frappe.db.commit()
    return {"page_access": _get_page_access(page_name)}


@frappe.whitelist()
def save_report_access(report_name: str, roles: str | list, audit_note: str | None = None) -> dict:
    _require_access_manager()
    if not frappe.db.exists("Report", report_name):
        frappe.throw(_("Report {0} was not found.").format(report_name))
    _save_child_roles("Report", report_name, roles)
    _add_audit_note("Report", report_name, audit_note, _("Updated report access roles."))
    frappe.db.commit()
    return {"report_access": _get_report_access(report_name)}


@frappe.whitelist()
def save_report_role_access(report_names: str | list, role: str, enabled: int = 1, audit_note: str | None = None) -> dict:
    _require_access_manager()
    report_names = _clean_list(report_names)
    role = (role or "").strip()
    _assert_role_scope([role])
    if not role or not frappe.db.exists("Role", role):
        frappe.throw(_("Role {0} was not found.").format(role))
    if not report_names:
        frappe.throw(_("Select at least one report."))

    missing = [name for name in report_names if not frappe.db.exists("Report", name)]
    if missing:
        frappe.throw(_("Unknown reports: {0}").format(", ".join(missing[:10])))

    updated = []
    for report_name in report_names:
        report = frappe.get_doc("Report", report_name)
        current_roles = [row.role for row in report.get("roles", []) if row.role]
        next_roles = list(current_roles)
        if cint(enabled):
            if role not in next_roles:
                next_roles.append(role)
        else:
            next_roles = [row_role for row_role in next_roles if row_role != role]
        if next_roles == current_roles:
            continue
        _save_child_roles("Report", report_name, next_roles)
        updated.append(report_name)
        _add_audit_note("Report", report_name, audit_note, _("Updated report access roles."))

    frappe.db.commit()
    return {"updated": updated, "report_access": _get_report_access()}


def _get_summary() -> dict:
    total_users = _count_visible_users()
    active_users = _count_visible_users({"enabled": 1})
    disabled_users = _count_visible_users({"enabled": 0})
    roles = _summary_roles()
    if _is_superadmin_session():
        system_roles = len([role for role in roles if not cint(role.get("is_custom"))])
        custom_roles = len([role for role in roles if cint(role.get("is_custom"))]) if _has_field("Role", "is_custom") else len(roles)
    else:
        system_roles = 0
        custom_roles = len(roles)
    admin_users = _count_visible_admin_users()
    recent_permission_changes = frappe.db.count(
        "Version",
        {"ref_doctype": ["in", AUDIT_DOCTYPES]},
    ) if frappe.db.exists("DocType", "Version") else 0
    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "system_roles": system_roles,
        "custom_roles": custom_roles,
        "admin_users": admin_users,
        "pending_reviews": 0,
        "recent_permission_changes": recent_permission_changes,
    }


def _visible_user_filters(extra: dict | None = None) -> list:
    filters = []
    hidden_users = _hidden_users_for_session()
    if hidden_users:
        filters.append(["User", "name", "not in", list(hidden_users)])
    for fieldname, value in (extra or {}).items():
        filters.append(["User", fieldname, "=", value])
    return filters


def _count_visible_users(extra: dict | None = None) -> int:
    return len(frappe.get_all("User", filters=_visible_user_filters(extra), pluck="name", limit_page_length=0))


def _summary_roles() -> list[dict]:
    filters = []
    visible_roles = _visible_role_names()
    if not _is_superadmin_session():
        filters.append(["Role", "name", "in", visible_roles])
    return frappe.get_all("Role", filters=filters, fields=["name", "is_custom"], limit_page_length=0)


def _count_visible_admin_users() -> int:
    admin_roles = HIGH_ACCESS_ROLES if _is_superadmin_session() else {"Orderlift Admin"}
    users = set(frappe.get_all(
        "Has Role",
        filters={"role": ["in", list(admin_roles)], "parenttype": "User"},
        pluck="parent",
        limit_page_length=0,
    ))
    users.difference_update(_hidden_users_for_session())
    return len(users)


def _get_users(search: str | None = None) -> list[dict]:
    filters = _visible_user_filters()
    clean_search = (search or "").strip()
    if clean_search:
        filters.append(["User", "name", "like", f"%{clean_search}%"])
    fields = _safe_fields("User", ["name", "email", "full_name", "enabled", "custom_owned_documents_only", "user_type", "last_login", "role_profile_name", "default_workspace"])
    rows = frappe.get_all("User", filters=filters, fields=fields, order_by="enabled desc, full_name asc, name asc", limit_page_length=80)
    role_counts = _user_role_counts([row.name for row in rows])
    user_roles = _user_roles([row.name for row in rows])
    result = []
    for row in rows:
        visible_roles = _filter_roles_for_session(user_roles.get(row.name, []))
        result.append({
            "name": row.name,
            "email": row.get("email") or row.name,
            "full_name": row.get("full_name") or row.name,
            "enabled": cint(row.get("enabled")),
            "custom_owned_documents_only": cint(row.get("custom_owned_documents_only") or 0),
            "user_type": row.get("user_type") or "",
            "last_login": str(row.get("last_login") or ""),
            "role_profile_name": row.get("role_profile_name") or "",
            "default_workspace": row.get("default_workspace") or "",
            "role_count": len(visible_roles),
            "main_role": _main_role(visible_roles),
            "access_level": _access_level(visible_roles),
        })
    return result


def _get_roles(search: str | None = None) -> list[dict]:
    visible_roles = _visible_role_names()
    filters = [["Role", "name", "in", visible_roles]]
    clean_search = (search or "").strip()
    if clean_search:
        filters.append(["Role", "name", "like", f"%{clean_search}%"])
    fields = _safe_fields("Role", ["name", "role_name", "desk_access", "disabled", "is_custom", ROLE_CAPABILITY_FIELD])
    rows = frappe.get_all("Role", filters=filters, fields=fields, order_by="disabled asc, is_custom asc, name asc", limit_page_length=150)
    assigned_counts = _role_user_counts([row.name for row in rows])
    return [_role_payload(row.name, row, assigned_counts) for row in rows]


def _get_role_profiles(search: str | None = None) -> list[dict]:
    return []


def _get_companies() -> list[dict]:
    return [{"name": name, "business_types": get_company_business_type_names(name)} for name in get_all_companies()]


def _get_warehouses() -> list[dict]:
    return get_visible_warehouses()


def _get_business_types() -> list[str]:
    if not frappe.db.exists("DocType", "CRM Business Type"):
        return []
    filters = {}
    if _has_field("CRM Business Type", "is_active"):
        filters["is_active"] = 1
    return frappe.get_all(
        "CRM Business Type",
        filters=filters,
        pluck="name",
        order_by="name asc",
        limit_page_length=0,
    )


def _get_menu_access() -> list[dict]:
    try:
        sync_menu_access_rules()
        payload = get_menu_access_payload()
        if _is_superadmin_session():
            return payload
        for row in payload:
            row["allowed_roles"] = _filter_roles_for_session(row.get("allowed_roles") or [])
            row["default_roles"] = _filter_roles_for_session(row.get("default_roles") or [])
        return payload
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Access Command Center menu access load failed")
        return []


def _get_permission_matrix(role: str | None, doctype_search: str | None = None) -> dict:
    if not role:
        return {"role": "", "rows": []}
    _assert_role_scope([role])
    filters = {"issingle": 0}
    clean_search = (doctype_search or "").strip()
    if clean_search:
        filters["name"] = ["like", f"%{clean_search}%"]
    doctypes = frappe.get_all(
        "DocType",
        filters=filters,
        fields=["name", "module", "custom", "istable"],
        order_by="module asc, name asc",
        limit_page_length=MATRIX_DOCTYPE_LIMIT,
    )
    missing_permission_doctypes = _missing_permission_doctype_names(
        doctypes,
        _permission_doctype_names_for_role(role, clean_search),
    )
    if missing_permission_doctypes:
        doctypes.extend(
            frappe.get_all(
                "DocType",
                filters={"issingle": 0, "name": ["in", missing_permission_doctypes]},
                fields=["name", "module", "custom", "istable"],
                order_by="module asc, name asc",
                limit_page_length=0,
            )
        )
    child_parent_map = _matrix_child_parent_map([doctype.name for doctype in doctypes])
    rows = []
    for doctype in doctypes:
        if not _permission_doctype_visible(doctype.name, role):
            continue
        group = _permission_matrix_group(doctype.name, doctype.get("module"), cint(doctype.get("istable")), child_parent_map)
        standard_rows = _perm_rows("DocPerm", doctype.name, role)
        custom_rows = _perm_rows("Custom DocPerm", doctype.name, role)
        for permlevel in _permission_levels_for_matrix(standard_rows, custom_rows):
            standard = standard_rows.get(permlevel, {})
            custom = custom_rows.get(permlevel, {})
            effective = custom or standard or {}
            rows.append(
                {
                    "row_key": f"{doctype.name}::{permlevel}",
                    "doctype": doctype.name,
                    "module": doctype.get("module") or _("Unassigned"),
                    "is_custom_doctype": cint(doctype.get("custom")),
                    "is_child_table": cint(doctype.get("istable")),
                    "is_protected": doctype.name in PROTECTED_DOCTYPES,
                    "permlevel": permlevel,
                    "source": "custom" if custom else ("standard" if standard else "none"),
                    "standard": _permission_flag_payload(doctype.name, standard) if standard else {},
                    "custom": _permission_flag_payload(doctype.name, custom) if custom else {},
                    "effective": _permission_flag_payload(doctype.name, effective),
                    "disabled_permission_fields": list(_disabled_permission_fields(doctype.name)),
                    "risk": _permission_risk(doctype.name, role, effective),
                    **group,
                }
            )
    rows.sort(key=_permission_matrix_sort_key)
    return {"role": role, "rows": rows}


def _matrix_child_parent_map(doctype_names: list[str]) -> dict[str, list[str]]:
    names = [name for name in doctype_names if name]
    if not names:
        return {}
    parent_map: dict[str, list[str]] = {}
    try:
        for row in frappe.get_all(
            "DocField",
            filters={"fieldtype": ["in", ["Table", "Table MultiSelect"]], "options": ["in", names]},
            fields=["parent", "options"],
            limit_page_length=0,
        ):
            if row.options and row.parent:
                parent_map.setdefault(row.options, []).append(row.parent)
    except Exception:
        pass
    try:
        for row in frappe.get_all(
            "Custom Field",
            filters={"fieldtype": ["in", ["Table", "Table MultiSelect"]], "options": ["in", names]},
            fields=["dt", "options"],
            limit_page_length=0,
        ):
            if row.options and row.dt:
                parent_map.setdefault(row.options, []).append(row.dt)
    except Exception:
        pass
    return {key: sorted(set(values)) for key, values in parent_map.items()}


def _permission_matrix_group(doctype: str, module: str | None, is_child_table: int, child_parent_map: dict[str, list[str]]) -> dict:
    group_index = {group["key"]: index for index, group in enumerate(MATRIX_DOCTYPE_GROUPS)}
    direct_group = _doctype_group_by_member(doctype)
    parent_doctype = ""
    relation = "primary"

    if is_child_table:
        parents = child_parent_map.get(doctype) or []
        parent_doctype = _preferred_matrix_parent(parents)
        parent_group = _doctype_group_by_member(parent_doctype) or _doctype_group_by_prefix(parent_doctype)
        if parent_group:
            direct_group = parent_group
            relation = "child"

    if not direct_group:
        direct_group = _doctype_group_by_prefix(doctype)
        relation = "related" if direct_group else relation

    if direct_group:
        return {
            "group_key": direct_group["key"],
            "group_label": direct_group["label"],
            "group_order": group_index.get(direct_group["key"], 999),
            "group_relation": relation,
            "group_parent_doctype": parent_doctype,
        }

    module_label = (module or "Unassigned").strip() or "Unassigned"
    return {
        "group_key": "module:" + module_label.lower().replace(" ", "_"),
        "group_label": f"{module_label} Module",
        "group_order": 1000,
        "group_relation": "child" if is_child_table else "module",
        "group_parent_doctype": parent_doctype,
    }


def _doctype_group_by_member(doctype: str | None) -> dict | None:
    if not doctype:
        return None
    for group in MATRIX_DOCTYPE_GROUPS:
        if doctype in group.get("members", ()):
            return group
    return None


def _doctype_group_by_prefix(doctype: str | None) -> dict | None:
    if not doctype:
        return None
    for group in MATRIX_DOCTYPE_GROUPS:
        for prefix in group.get("prefixes", ()):
            if doctype == prefix or doctype.startswith(prefix + " ") or doctype.startswith(prefix + "-"):
                return group
    return None


def _preferred_matrix_parent(parents: list[str]) -> str:
    if not parents:
        return ""
    for parent in parents:
        if _doctype_group_by_member(parent) or _doctype_group_by_prefix(parent):
            return parent
    return parents[0]


def _permission_doctype_names_for_role(role: str, doctype_search: str | None = None) -> set[str]:
    names = set()
    filters = {"role": role}
    clean_search = (doctype_search or "").strip()
    if clean_search:
        filters["parent"] = ["like", f"%{clean_search}%"]
    for perm_doctype in ("DocPerm", "Custom DocPerm"):
        for row in frappe.get_all(perm_doctype, filters=filters, fields=["parent"], limit_page_length=0):
            if row.get("parent"):
                names.add(row.parent)
    return names


def _missing_permission_doctype_names(doctypes: list[dict], permission_doctype_names: set[str]) -> list[str]:
    loaded = {row.get("name") for row in doctypes}
    return sorted(name for name in permission_doctype_names if name and name not in loaded)


def _permission_matrix_sort_key(row: dict) -> tuple:
    effective = row.get("effective") or {}
    has_permission = any(cint(effective.get(field)) for field in PERMISSION_FIELDS)
    source_order = {"custom": 0, "standard": 1, "none": 2}.get(row.get("source"), 3)
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(row.get("risk"), 4)
    return (
        0 if has_permission else 1,
        source_order,
        risk_order,
        (row.get("module") or "").lower(),
        (row.get("doctype") or "").lower(),
        cint(row.get("permlevel")),
    )


def _get_page_access(search: str | None = None) -> list[dict]:
    filters = []
    clean_search = (search or "").strip()
    if clean_search:
        filters.append(["Page", "name", "like", f"%{clean_search}%"])
    rows = frappe.get_all("Page", filters=filters, fields=["name", "title", "module", "system_page"], order_by="module asc, name asc", limit_page_length=80)
    role_map = _child_role_map("Page", [row.name for row in rows])
    return [
        {
            "name": row.name,
            "title": row.get("title") or row.name,
            "module": row.get("module") or "",
            "system_page": cint(row.get("system_page")),
            "roles": role_map.get(row.name, []),
        }
        for row in rows
    ]


def _get_report_access(search: str | None = None) -> list[dict]:
    filters = []
    or_filters = []
    clean_search = (search or "").strip()
    if clean_search:
        or_filters = [
            ["Report", "name", "like", f"%{clean_search}%"],
            ["Report", "ref_doctype", "like", f"%{clean_search}%"],
            ["Report", "report_type", "like", f"%{clean_search}%"],
        ]
    rows = frappe.get_all(
        "Report",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "ref_doctype", "report_type", "is_standard"],
        order_by="ref_doctype asc, name asc",
        limit_page_length=200,
    )
    role_map = _child_role_map("Report", [row.name for row in rows])
    return [
        {
            "name": row.name,
            "ref_doctype": row.get("ref_doctype") or "",
            "report_type": row.get("report_type") or "",
            "is_standard": cint(row.get("is_standard")),
            "roles": role_map.get(row.name, []),
        }
        for row in rows
    ]


def _get_user_permissions(search: str | None = None) -> list[dict]:
    filters = []
    clean_search = (search or "").strip()
    if clean_search:
        filters.append(["User Permission", "user", "like", f"%{clean_search}%"])
    rows = frappe.get_all(
        "User Permission",
        filters=filters,
        fields=["name", "user", "allow", "for_value", "apply_to_all_doctypes", "applicable_for", "is_default", "modified"],
        order_by="modified desc",
        limit_page_length=120,
    )
    if _is_superadmin_session():
        return rows
    hidden_users = _hidden_users_for_session()
    return [row for row in rows if row.get("user") not in hidden_users]


def _get_audit_log() -> list[dict]:
    events = []
    if frappe.db.exists("DocType", "Version"):
        rows = frappe.get_all(
            "Version",
            filters={"ref_doctype": ["in", AUDIT_DOCTYPES]},
            fields=["name", "owner", "ref_doctype", "docname", "modified", "data"],
            order_by="modified desc",
            limit_page_length=40,
        )
        events.extend([
        {
            "name": row.name,
            "actor": row.owner,
            "target_type": row.ref_doctype,
            "target": row.docname,
            "modified": str(row.modified or ""),
            "summary": _version_summary(row.get("data")),
            "risk": "high" if row.ref_doctype in {"Custom DocPerm", "User", "Role"} else "medium",
        }
        for row in rows
        ])
    if frappe.db.exists("DocType", "Comment"):
        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": ["in", AUDIT_DOCTYPES], "comment_type": "Info", "content": ["like", "%Access Command Center%"]},
            fields=["name", "owner", "reference_doctype", "reference_name", "modified", "content"],
            order_by="modified desc",
            limit_page_length=40,
        )
        events.extend([
            {
                "name": row.name,
                "actor": row.owner,
                "target_type": row.reference_doctype,
                "target": row.reference_name,
                "modified": str(row.modified or ""),
                "summary": row.content,
                "risk": "high" if row.reference_doctype in {"Custom DocPerm", "User", "Role"} else "medium",
            }
            for row in comments
        ])
    events = [event for event in events if _audit_event_visible(event)]
    return sorted(events, key=lambda row: row.get("modified") or "", reverse=True)[:50]


def _audit_event_visible(event: dict) -> bool:
    if _is_superadmin_session():
        return True
    hidden_users = _hidden_users_for_session()
    actor = event.get("actor") or ""
    target = event.get("target") or ""
    target_type = event.get("target_type") or ""
    if actor in hidden_users:
        return False
    if target_type == "User":
        return target not in hidden_users
    if target_type == "Role":
        return target in _business_scope_role_set()
    if target_type == "Custom DocPerm":
        row = frappe.db.get_value("Custom DocPerm", target, ["role", "parent"], as_dict=True) if target else None
        role = row.role if row else ""
        parent = row.parent if row else ""
        if parent and not _permission_doctype_visible(parent, role):
            return False
        return not role or role in BUSINESS_ROLE_SET
    return True


def _save_child_roles(parenttype: str, parent: str, roles: str | list) -> None:
    role_names = _clean_list(roles)
    _assert_role_scope(role_names)
    missing = [role for role in role_names if not frappe.db.exists("Role", role)]
    if missing:
        frappe.throw(_("Unknown roles: {0}").format(", ".join(missing)))
    doc = frappe.get_doc(parenttype, parent)
    current_roles = [row.role for row in doc.get("roles", []) if row.role]
    role_names = _merge_scoped_roles(current_roles, role_names)
    doc.set("roles", [])
    for role in role_names:
        doc.append("roles", {"role": role})
    doc.save(ignore_permissions=False)


def _role_payload(role_name: str, row=None, assigned_counts: dict[str, int] | None = None) -> dict:
    assigned_counts = assigned_counts or {}
    if row is None:
        fields = _safe_fields("Role", ["name", "role_name", "desk_access", "disabled", "is_custom", ROLE_CAPABILITY_FIELD])
        row = frappe.get_all("Role", filters={"name": role_name}, fields=fields, limit_page_length=1)[0]
        assigned_counts = _role_user_counts([role_name])
    is_custom = cint(row.get("is_custom"))
    return {
        "name": row.name,
        "label": row.get("role_name") or row.name,
        "desk_access": cint(row.get("desk_access")),
        "disabled": cint(row.get("disabled")),
        "is_custom": is_custom,
        "is_system": not is_custom,
        "is_legacy": _is_legacy_role(row.name),
        "is_protected": row.name in HIGH_ACCESS_ROLES or not is_custom,
        "users": assigned_counts.get(row.name, 0),
        "access_level": _access_level([row.name]),
        "capabilities": normalize_capabilities(row.get(ROLE_CAPABILITY_FIELD)),
    }


def _first_perm(doctype: str, parent: str, role: str) -> dict:
    rows = frappe.get_all(
        doctype,
        filters={"parent": parent, "role": role},
        fields=["name", "permlevel", *PERMISSION_FIELDS],
        order_by="permlevel asc, modified desc",
        limit_page_length=1,
    )
    return rows[0] if rows else {}


def _perm_rows(doctype: str, parent: str, role: str) -> dict[int, dict]:
    rows = frappe.get_all(
        doctype,
        filters={"parent": parent, "role": role},
        fields=["name", "permlevel", *PERMISSION_FIELDS],
        order_by="permlevel asc, modified desc",
        limit_page_length=0,
    )
    result = {}
    for row in rows:
        permlevel = cint(row.get("permlevel", 0))
        if permlevel not in result:
            result[permlevel] = row
    return result


def _permission_levels_for_matrix(standard_rows: dict[int, dict], custom_rows: dict[int, dict]) -> list[int]:
    return sorted({0, *standard_rows.keys(), *custom_rows.keys()})


def _child_role_map(parenttype: str, parents: list[str]) -> dict[str, list[str]]:
    if not parents:
        return {}
    rows = frappe.get_all(
        "Has Role",
        filters={"parenttype": parenttype, "parent": ["in", parents]},
        fields=["parent", "role"],
        order_by="idx asc",
        limit_page_length=0,
    )
    result = {}
    for row in rows:
        if _is_superadmin_session() or row.role in BUSINESS_ROLE_SET:
            result.setdefault(row.parent, []).append(row.role)
    return result


def _role_profile_role_counts(profile_names: list[str]) -> dict[str, int]:
    if not profile_names:
        return {}
    child_doctype = _child_table_doctype("Role Profile", "roles")
    if child_doctype:
        try:
            rows = frappe.get_all(
                child_doctype,
                filters={"parent": ["in", profile_names]},
                fields=["parent", "role"],
                limit_page_length=0,
            )
            counts = {}
            for row in rows:
                counts[row.parent] = counts.get(row.parent, 0) + 1
            return counts
        except Exception:
            pass
    counts = {}
    for profile_name in profile_names:
        try:
            counts[profile_name] = len(frappe.get_doc("Role Profile", profile_name).get("roles") or [])
        except Exception:
            counts[profile_name] = 0
    return counts


def _role_dependency_summary(role_name: str) -> list[str]:
    dependencies = []
    checks = [
        ("assigned users", lambda: frappe.db.count("Has Role", {"parenttype": "User", "role": role_name})),
        ("page access rows", lambda: frappe.db.count("Has Role", {"parenttype": "Page", "role": role_name})),
        ("report access rows", lambda: frappe.db.count("Has Role", {"parenttype": "Report", "role": role_name})),
        ("standard permissions", lambda: frappe.db.count("DocPerm", {"role": role_name})),
        ("custom permission overrides", lambda: frappe.db.count("Custom DocPerm", {"role": role_name})),
    ]
    child_doctype = _child_table_doctype("Role Profile", "roles")
    if child_doctype:
        checks.append(("role profiles", lambda: frappe.db.count(child_doctype, {"role": role_name})))
    for label, count_fn in checks:
        try:
            count = count_fn()
        except Exception:
            count = 0
        if count:
            dependencies.append(_("{0} {1}").format(count, label))
    return dependencies


def _session_roles() -> set[str]:
    return set(frappe.get_roles(frappe.session.user))


def _is_superadmin_session() -> bool:
    if frappe.session.user == "Administrator":
        return True
    return bool(ADMIN_ROLES.intersection(_session_roles()))


def _visible_role_names() -> list[str]:
    custom_business_roles = _custom_business_role_names()
    if _is_superadmin_session():
        return _dedupe([*BUSINESS_ROLES, *custom_business_roles, *SUPERADMIN_VISIBLE_ROLES])
    return _dedupe([*BUSINESS_ROLES, *custom_business_roles])


def _custom_business_role_names() -> list[str]:
    if not hasattr(frappe, "get_all"):
        return []

    filters = {}
    try:
        if _has_field("Role", "is_custom"):
            filters["is_custom"] = 1
    except Exception:
        return []

    try:
        rows = frappe.get_all("Role", filters=filters, fields=["name"], order_by="name asc", limit_page_length=0)
    except Exception:
        return []

    protected_roles = set(ADMIN_ROLES) | set(SUPERADMIN_VISIBLE_ROLES) | BUSINESS_ROLE_SET | NON_BUSINESS_CUSTOM_ROLES
    return [
        row.name
        for row in rows
        if row.name and row.name not in protected_roles and not _is_legacy_role(row.name)
    ]


def _business_scope_role_set() -> set[str]:
    return BUSINESS_ROLE_SET | set(_custom_business_role_names())


def _filter_roles_for_session(roles: list[str]) -> list[str]:
    if _is_superadmin_session():
        return roles
    business_scope_roles = _business_scope_role_set()
    return [role for role in roles if role in business_scope_roles]


def _assert_role_scope(roles: list[str]) -> None:
    if _is_superadmin_session():
        return
    business_scope_roles = _business_scope_role_set()
    restricted = [
        role
        for role in roles
        if role not in business_scope_roles and (role in ADMIN_ROLES or role in SUPERADMIN_VISIBLE_ROLES or _role_exists(role))
    ]
    if restricted:
        frappe.throw(_("Orderlift Admins can manage business roles only: {0}").format(", ".join(restricted)))


def _merge_scoped_roles(current_roles: list[str], requested_roles: list[str]) -> list[str]:
    if _is_superadmin_session():
        return requested_roles
    business_scope_roles = _business_scope_role_set()
    merged = [role for role in current_roles if role not in business_scope_roles]
    for role in requested_roles:
        if role not in merged:
            merged.append(role)
    return merged


def _superadmin_users() -> set[str]:
    users = {"Administrator"}
    if not frappe.db.exists("DocType", "Has Role"):
        return users
    rows = frappe.get_all(
        "Has Role",
        filters={"parenttype": "User", "role": ["in", list(ADMIN_ROLES)]},
        pluck="parent",
        limit_page_length=0,
    )
    users.update(rows)
    return users


def _hidden_users_for_session() -> set[str]:
    if _is_superadmin_session():
        return set()
    return _superadmin_users().union({"Guest"})


def _assert_user_scope(user_name: str | None) -> None:
    if _is_superadmin_session():
        return
    if not user_name:
        frappe.throw(_("User is required."))
    if user_name in _hidden_users_for_session():
        frappe.throw(_("Only superadmins can manage system or superadmin users."))


def _child_table_doctype(parent_doctype: str, fieldname: str) -> str:
    try:
        field = frappe.get_meta(parent_doctype).get_field(fieldname)
    except Exception:
        return ""
    return field.options if field else ""


def _is_critical_user(user_name: str) -> bool:
    return user_name in CRITICAL_USERS


def _has_role(user, role_name: str) -> bool:
    return any(row.role == role_name for row in user.get("roles", []) if row.role)


def _enabled_system_manager_count() -> int:
    users = frappe.get_all(
        "Has Role",
        filters={"parenttype": "User", "role": "System Manager"},
        pluck="parent",
        limit_page_length=0,
    )
    if not users:
        return 0
    unique_users = list(dict.fromkeys(users))
    return frappe.db.count("User", {"name": ["in", unique_users], "enabled": 1})


def _coerce_permission_flags(values: dict, doctype_name: str | None = None) -> dict:
    return _force_disabled_permission_flags(
        doctype_name,
        {field: 1 if cint(values.get(field)) else 0 for field in PERMISSION_FIELDS},
    )


def _permission_flag_payload(doctype_name: str, values: dict) -> dict:
    return _force_disabled_permission_flags(
        doctype_name,
        {field: cint(values.get(field)) for field in PERMISSION_FIELDS},
    )


def _force_disabled_permission_flags(doctype_name: str | None, flags: dict) -> dict:
    flags = dict(flags or {})
    for fieldname in _disabled_permission_fields(doctype_name):
        flags[fieldname] = 0
    return flags


def _disabled_permission_fields(doctype_name: str | None) -> tuple[str, ...]:
    if doctype_name in MANAGED_PERMISSION_DOCTYPE_SET:
        return MANAGED_FORCED_OFF_PERMISSION_FIELDS
    return ()


def _validate_permission_edit(role: str, doctype_name: str, flags: dict) -> None:
    if not _permission_doctype_visible(doctype_name, role):
        frappe.throw(_("Protected system, accounting, and Cost Center permissions are superadmin-only."))
    if frappe.session.user == "Administrator":
        return
    if role == "System Manager" and doctype_name in PROTECTED_DOCTYPES and not flags.get("read"):
        frappe.throw(_("System Manager must keep read access on protected system doctypes."))
    if role == "System Manager" and doctype_name in {"User", "Role", "Custom DocPerm"} and not flags.get("write"):
        frappe.throw(_("System Manager write access on critical access doctypes cannot be removed here."))


def _validate_role_name(role_name: str | None) -> str:
    role_name = (role_name or "").strip()
    if not role_name:
        frappe.throw(_("Role name is required."))
    if len(role_name) > 140:
        frappe.throw(_("Role name is too long."))
    return role_name


def _is_protected_role_doc(role) -> bool:
    return role.name in HIGH_ACCESS_ROLES or not cint(role.get("is_custom"))


def _require_access_manager() -> None:
    if _is_superadmin_session():
        return
    if "Orderlift Admin" not in _session_roles():
        frappe.throw(_("Only Orderlift Admins and superadmins can use Access Command Center."), frappe.PermissionError)


def _permission_doctype_visible(doctype_name: str, role: str | None = None) -> bool:
    if doctype_name in PROTECTED_DOCTYPES:
        return _is_superadmin_session() and role in ADMIN_ROLES
    if doctype_name not in BACKEND_FINANCE_PERMISSION_DOCTYPES:
        return True
    return _is_superadmin_session() and role in ADMIN_ROLES


def _assert_role_profile_scope(role_profile: str | None) -> None:
    role_profile = (role_profile or "").strip()
    if not role_profile:
        return
    _assert_role_scope(_role_profile_roles(role_profile))


def _role_profile_roles(role_profile: str) -> list[str]:
    if not frappe.db.exists("Role Profile", role_profile):
        return []
    try:
        doc = frappe.get_doc("Role Profile", role_profile)
        return [row.role for row in doc.get("roles", []) if row.role]
    except Exception:
        child_doctype = _child_table_doctype("Role Profile", "roles")
        if not child_doctype:
            return []
        return frappe.get_all(
            child_doctype,
            filters={"parenttype": "Role Profile", "parent": role_profile},
            pluck="role",
            limit_page_length=0,
        )


def _assert_company_assignment_scope(companies: list[str], default_company: str | None = None) -> None:
    if _is_superadmin_session() or user_can_access_all_companies(frappe.session.user):
        return
    allowed = set(get_allowed_companies(frappe.session.user))
    requested = set(companies or [])
    if default_company:
        requested.add(default_company)
    blocked = sorted(requested - allowed)
    if blocked:
        frappe.throw(_("You can assign only companies you can access: {0}").format(", ".join(blocked)))


def _assert_business_type_assignment_scope(business_types: list[str]) -> None:
    if _is_superadmin_session() or user_can_access_all_business_types(frappe.session.user):
        return
    allowed = set(get_allowed_business_types(frappe.session.user))
    blocked = sorted(set(business_types or []) - allowed)
    if blocked:
        frappe.throw(_("You can assign only business types you can access: {0}").format(", ".join(blocked)))


def _assert_warehouse_assignment_scope(warehouses: list[str]) -> None:
    if _is_superadmin_session():
        return
    allowed = {row.name for row in get_visible_warehouses()}
    blocked = sorted(set(warehouses or []) - allowed)
    if blocked:
        frappe.throw(_("You can assign only warehouses you can access: {0}").format(", ".join(blocked)))


def _assert_business_types_match_user_companies(user_name: str, business_types: list[str]) -> None:
    business_types = _clean_list(business_types)
    if not business_types:
        return
    allowed = _business_types_for_user_companies(user_name)
    blocked = sorted(set(business_types) - allowed)
    if blocked:
        frappe.throw(_("Business types not available for this user's selected companies: {0}").format(", ".join(blocked)))


def _assert_warehouses_match_user_companies(user_name: str, warehouses: list[str]) -> None:
    warehouses = _clean_list(warehouses)
    if not warehouses:
        return
    companies = set(get_allowed_companies(user_name))
    blocked = []
    for warehouse in warehouses:
        company = frappe.db.get_value("Warehouse", warehouse, "company") or ""
        if company not in companies:
            blocked.append(warehouse)
    if blocked:
        frappe.throw(_("Warehouses not available for this user's selected companies: {0}").format(", ".join(sorted(blocked))))


def _cleanup_company_dependent_user_permissions(user_name: str) -> None:
    companies = set(get_allowed_companies(user_name))
    allowed_business_types = _business_types_for_user_companies(user_name)
    rows = frappe.get_all(
        "User Permission",
        filters={"user": user_name, "allow": ["in", ["CRM Business Type", "Warehouse"]]},
        fields=["name", "allow", "for_value", "apply_to_all_doctypes", "applicable_for"],
        limit_page_length=0,
    )
    for row in rows:
        if not cint(row.get("apply_to_all_doctypes")) or (row.get("applicable_for") or "").strip():
            continue
        if row.allow == "CRM Business Type" and row.for_value not in allowed_business_types:
            frappe.delete_doc("User Permission", row.name, ignore_permissions=True)
        elif row.allow == "Warehouse":
            company = frappe.db.get_value("Warehouse", row.for_value, "company") or ""
            if company not in companies:
                frappe.delete_doc("User Permission", row.name, ignore_permissions=True)


def _business_types_for_user_companies(user_name: str) -> set[str]:
    business_types = set()
    for company in get_allowed_companies(user_name):
        business_types.update(get_company_business_type_names(company))
    return business_types


def _validate_user_permission_scope(allow: str, for_value: str | None = None) -> None:
    allow = (allow or "").strip()
    for_value = (for_value or "").strip()
    if allow not in ACCESS_CENTER_USER_PERMISSION_DOCTYPES:
        frappe.throw(_("Access Command Center can manage Company, CRM Business Type, and Warehouse user permissions only."))
    if for_value and not frappe.db.exists(allow, for_value):
        frappe.throw(_("Allowed value {0} was not found for {1}.").format(for_value, allow))
    if allow == "Company":
        _assert_company_assignment_scope([for_value] if for_value else [])
    elif allow == "CRM Business Type":
        _assert_business_type_assignment_scope([for_value] if for_value else [])
    elif allow == "Warehouse":
        _assert_warehouse_assignment_scope([for_value] if for_value else [])


def _user_role_counts(users: list[str]) -> dict[str, int]:
    if not users:
        return {}
    rows = frappe.get_all("Has Role", filters={"parenttype": "User", "parent": ["in", users]}, fields=["parent", "role"], limit_page_length=0)
    counts = {}
    for row in rows:
        counts[row.parent] = counts.get(row.parent, 0) + 1
    return counts


def _user_roles(users: list[str]) -> dict[str, list[str]]:
    if not users:
        return {}
    rows = frappe.get_all("Has Role", filters={"parenttype": "User", "parent": ["in", users]}, fields=["parent", "role"], limit_page_length=0)
    result = {}
    for row in rows:
        result.setdefault(row.parent, []).append(row.role)
    return result


def _role_user_counts(roles: list[str]) -> dict[str, int]:
    if not roles:
        return {}
    rows = frappe.get_all("Has Role", filters={"parenttype": "User", "role": ["in", roles]}, fields=["role", "parent"], limit_page_length=0)
    counts = {}
    seen = set()
    for row in rows:
        key = (row.role, row.parent)
        if key in seen:
            continue
        seen.add(key)
        counts[row.role] = counts.get(row.role, 0) + 1
    return counts


def _main_role(roles: list[str]) -> str:
    for role in (
        "System Manager",
        "Orderlift Admin",
        "Pricing Manager",
        "Sales User",
        "Logistics User",
        "Finance User",
        "Installation User",
        "Service User",
    ):
        if role in roles:
            return role
    return roles[0] if roles else "No Role"


def _access_level(roles: list[str]) -> str:
    if any(role in ADMIN_ROLES for role in roles):
        return "Admin Level"
    if any(role in HIGH_ACCESS_ROLES for role in roles):
        return "High Access"
    if roles:
        return "Managed Access"
    return "No Access"


def _permission_risk(doctype_name: str, role: str, values: dict) -> str:
    if doctype_name in PROTECTED_DOCTYPES and (cint(values.get("write")) or cint(values.get("delete"))):
        return "critical"
    if role in HIGH_ACCESS_ROLES or cint(values.get("delete")) or cint(values.get("submit")) or cint(values.get("cancel")):
        return "high"
    if cint(values.get("write")) or cint(values.get("create")):
        return "medium"
    return "low"


def _user_warnings(user_name: str, roles: list[str]) -> list[str]:
    warnings = []
    if any(role in ADMIN_ROLES for role in roles):
        warnings.append(_("This user has administrator-level access."))
    if user_name == frappe.session.user:
        warnings.append(_("You are editing your own account. Self-lockout protections are active."))
    return warnings


def _is_legacy_role(role_name: str) -> bool:
    lowered = role_name.lower()
    return any(keyword in lowered for keyword in LEGACY_ROLE_KEYWORDS)


def _default_role(roles: list[dict]) -> str:
    for role in roles:
        if role.get("name") == "System Manager":
            return role["name"]
    return roles[0]["name"] if roles else ""


def _clean_list(value: str | list | tuple | None) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value or "[]")
        except ValueError:
            value = [value]
    clean = []
    for item in value or []:
        item = (item or "").strip()
        if item and item not in clean:
            clean.append(item)
    return clean


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _role_exists(role: str) -> bool:
    try:
        return bool(frappe.db.exists("Role", role))
    except Exception:
        return False


def _set_if_field(doc, fieldname: str, value) -> None:
    if doc.meta.get_field(fieldname):
        doc.set(fieldname, value)


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _safe_fields(doctype: str, fields: list[str]) -> list[str]:
    meta = frappe.get_meta(doctype)
    return [field for field in fields if field == "name" or meta.get_field(field)]


def _add_audit_note(reference_doctype: str, reference_name: str, audit_note: str | None, fallback: str) -> None:
    content = (audit_note or fallback or "").strip()
    if not content:
        return
    try:
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "content": content,
            }
        ).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Access Command Center audit note failed")


def _version_summary(data: str | None) -> str:
    if not data:
        return _("Access record changed")
    try:
        parsed = json.loads(data)
    except ValueError:
        return _("Access record changed")
    changed = parsed.get("changed") or []
    if changed:
        fields = [row[0] for row in changed if row]
        return _("Changed {0}").format(", ".join(fields[:4]))
    added = parsed.get("added") or []
    removed = parsed.get("removed") or []
    if added or removed:
        return _("Updated child access rows")
    return _("Access record changed")


def _loads(payload: str | dict | None) -> dict:
    if isinstance(payload, str):
        return json.loads(payload or "{}")
    return payload or {}
