from __future__ import annotations

import json
from contextlib import suppress

import frappe
from frappe.utils import cint

from orderlift.menu_registry import (
    ALL_USERS_ROLE,
    ADMIN_ROLES,
    BUSINESS_ROLES,
    build_sidebar_rows,
    default_roles_for_key,
    get_menu_sections,
    iter_menu_items,
    menu_item_by_key,
    menu_item_for_row,
    page_menu_map,
)


MENU_ACCESS_DOCTYPE = "Orderlift Menu Access Rule"
COMPANY_DOCTYPE = "Company"
BUSINESS_TYPE_DOCTYPE = "CRM Business Type"
ADMIN_BYPASS_ROLES = {"System Manager", "Administrator", "Developer"}
LEGACY_DEFAULT_MENU_ROLES = {
    "Accounts Manager",
    "Accounts User",
    "B2B Portal Manager",
    "Finance User",  # kept through BUSINESS_ROLES below
    "HR Manager",
    "HR User",
    "Logistics Manager",
    "Manufacturing Manager",
    "Manufacturing User",
    "Orderlift Accountant",
    "Orderlift Business Admin",
    "Orderlift Commercial",
    "Orderlift Technician",
    "Projects Manager",
    "Projects User",
    "Purchase Manager",
    "Purchase User",
    "Purchasing User",
    "SAV Manager",
    "SAV User",
    "SIG Manager",
    "SIG Technician",
    "Sales Manager",
    "Stock Manager",
    "Stock User",
    "Warehouse User",
}


def sync_menu_access_rules() -> dict:
    """Upsert menu access rules from the central registry.

    Existing allowed role choices are preserved so admins can safely manage access
    from Access Command Center after the initial seed.
    """
    if not _doctype_available(MENU_ACCESS_DOCTYPE):
        return {"skipped": True, "reason": "missing doctype"}

    ensure_business_roles()

    active_keys = set()
    created = 0
    updated = 0
    for idx, item in enumerate(iter_menu_items(), start=1):
        menu_key = item["key"]
        active_keys.add(menu_key)
        doc_name = frappe.db.exists(MENU_ACCESS_DOCTYPE, menu_key) or frappe.db.exists(
            MENU_ACCESS_DOCTYPE,
            {"menu_key": menu_key},
        )
        if doc_name:
            existing = frappe.db.get_value(
                MENU_ACCESS_DOCTYPE,
                doc_name,
                ["allowed_roles_json", "enabled", "label", "menu_order"],
                as_dict=True,
            ) or {}
            roles = _sanitize_allowed_roles_for_item(
                item,
                _clean_list(existing.get("allowed_roles_json")),
            )
            custom_label = (existing.get("label") or "").strip() or item.get("label") or ""
            custom_order = cint(existing.get("menu_order")) or idx
            values = {
                "menu_key": menu_key,
                "section": item.get("section") or "",
                "label": custom_label,
                "link_type": item.get("link_type") or "",
                "link_to": item.get("link_to") or "",
                "url": item.get("url") or "",
                "icon": item.get("icon") or "",
                "default_roles_json": json.dumps(item.get("roles") or []),
                "company_scoped": 1 if item.get("company_scoped") else 0,
                "menu_order": custom_order,
                "allowed_roles_json": json.dumps(roles),
            }
            if existing.get("enabled") is None:
                values["enabled"] = 1
            frappe.db.set_value(MENU_ACCESS_DOCTYPE, doc_name, values)
            updated += 1
            continue
        else:
            doc = frappe.new_doc(MENU_ACCESS_DOCTYPE)
            doc.name = menu_key
            doc.menu_key = menu_key
            doc.allowed_roles_json = json.dumps(_sanitize_allowed_roles_for_item(item, item.get("roles") or []))
            doc.enabled = 1
            created += 1

        doc.menu_key = menu_key
        doc.section = item.get("section") or ""
        doc.label = item.get("label") or ""
        doc.link_type = item.get("link_type") or ""
        doc.link_to = item.get("link_to") or ""
        doc.url = item.get("url") or ""
        doc.icon = item.get("icon") or ""
        doc.default_roles_json = json.dumps(item.get("roles") or [])
        doc.company_scoped = 1 if item.get("company_scoped") else 0
        doc.menu_order = idx
        if doc.get("enabled") is None:
            doc.enabled = 1
        doc.save(ignore_permissions=True)

    stale_names = frappe.get_all(
        MENU_ACCESS_DOCTYPE,
        filters={"menu_key": ["not in", list(active_keys)]},
        pluck="name",
        limit_page_length=0,
    )
    for name in stale_names:
        frappe.db.set_value(MENU_ACCESS_DOCTYPE, name, "enabled", 0, update_modified=False)

    return {"created": created, "updated": updated, "disabled_stale": len(stale_names)}


def ensure_business_roles() -> dict:
    if not _doctype_available("Role"):
        return {"skipped": True, "reason": "missing Role doctype"}

    created = []
    platform_roles = [role for role in ADMIN_ROLES if role != "Administrator"]
    for role_name in list(BUSINESS_ROLES) + platform_roles:
        if frappe.db.exists("Role", role_name):
            continue
        role = frappe.new_doc("Role")
        role.role_name = role_name
        if role.meta.get_field("desk_access"):
            role.desk_access = 1
        if role.meta.get_field("is_custom"):
            role.is_custom = 1
        role.insert(ignore_permissions=True)
        created.append(role_name)
    return {"created": created}


def get_menu_access_payload() -> list[dict]:
    rules = _menu_rule_map()
    payload = []
    for item in iter_menu_items():
        rule = rules.get(item["key"])
        enabled = _rule_enabled(rule)
        payload.append(
            {
                **item,
                "enabled": enabled,
                "allowed_roles": _rule_roles(rule, item["key"]) if enabled else [],
                "denied_roles": _rule_denied_roles(rule) if enabled else [],
                "default_roles": item.get("roles") or [],
            }
        )
    return payload


def save_menu_access_for_role(role: str, menu_keys: list[str] | str) -> dict:
    role = (role or "").strip()
    if not role or not frappe.db.exists("Role", role):
        frappe.throw(f"Role {role} was not found.")

    selected_keys = set(_clean_list(menu_keys))
    sync_menu_access_rules()
    rules = _menu_rule_map()

    changed = 0
    for item in iter_menu_items():
        menu_key = item["key"]
        doc = rules.get(menu_key)
        if not doc:
            continue
        roles = _rule_roles(doc, menu_key)
        denied_roles = _rule_denied_roles(doc)
        next_roles = list(roles)
        next_denied_roles = list(denied_roles)
        values = {}
        selected = menu_key in selected_keys
        if selected:
            if role in next_denied_roles:
                next_denied_roles.remove(role)
            if ALL_USERS_ROLE not in next_roles and role not in next_roles:
                next_roles.append(role)
        else:
            if ALL_USERS_ROLE in next_roles and role not in next_denied_roles:
                next_denied_roles.append(role)
            elif role in next_roles:
                next_roles.remove(role)
            elif role in next_denied_roles and ALL_USERS_ROLE not in next_roles:
                next_denied_roles.remove(role)
        if selected and not _rule_enabled(doc):
            values["enabled"] = 1
        next_roles = _sanitize_allowed_roles_for_item(item, next_roles)
        if next_roles != roles:
            values["allowed_roles_json"] = json.dumps(next_roles)
        if next_denied_roles != denied_roles:
            values["denied_roles_json"] = json.dumps(next_denied_roles)
        if values:
            frappe.db.set_value(MENU_ACCESS_DOCTYPE, doc.name, values)
            changed += 1

    frappe.clear_cache()
    return {"role": role, "changed": changed, "selected": len(selected_keys)}


def user_can_access_menu_key(
    menu_key: str,
    user: str | None = None,
    roles: set[str] | None = None,
    rules: dict[str, object] | None = None,
) -> bool:
    if not menu_key:
        return False
    user = user or frappe.session.user
    roles = roles if roles is not None else _get_roles(user)
    if _is_admin_user(user, roles):
        return True

    rule = (rules if rules is not None else _menu_rule_map()).get(menu_key)
    if not _rule_enabled(rule):
        return False
    allowed_roles = _rule_roles(rule, menu_key)
    if roles.intersection(_rule_denied_roles(rule)):
        return False
    return _roles_allow(allowed_roles, roles)


def user_can_access_page(page_name: str, user: str | None = None, rules: dict[str, object] | None = None) -> bool:
    page_name = (page_name or "").strip()
    if not page_name:
        return True
    user = user or frappe.session.user
    roles = _get_roles(user)
    if _is_admin_user(user, roles):
        return True

    menu_keys = page_menu_map().get(page_name)
    if not menu_keys:
        return True
    rules = rules if rules is not None else _menu_rule_map()
    visible_items = [
        item
        for menu_key in menu_keys
        if user_can_access_menu_key(menu_key, user=user, roles=roles, rules=rules)
        for item in [menu_item_by_key(menu_key)]
        if item
    ]
    if not visible_items:
        return False
    if not any(_required_doctypes_allowed(item.get("required_doctypes"), user=user) for item in visible_items):
        return False

    page_roles = _page_roles(page_name)
    if page_roles and not roles.intersection(page_roles):
        return False
    return True


def filter_sidebar_rows(rows: list[dict], user: str | None = None) -> list[dict]:
    user = user or frappe.session.user
    roles = _get_roles(user)
    if _is_admin_user(user, roles):
        return rows
    rules = _menu_rule_map()

    filtered: list[dict] = []
    pending_section: dict | None = None
    section_has_links = False

    def flush_empty_section() -> None:
        nonlocal pending_section, section_has_links
        if pending_section and not section_has_links and filtered and filtered[-1] is pending_section:
            filtered.pop()
        pending_section = None
        section_has_links = False

    for row in rows:
        row_type = row.get("type")
        if row_type == "Section Break":
            flush_empty_section()
            pending_section = row
            section_has_links = False
            filtered.append(row)
            continue

        if row_type != "Link":
            continue

        item = menu_item_for_row(row)
        if not item:
            continue
        if not user_can_access_menu_key(item["key"], user=user, roles=roles, rules=rules):
            continue
        if not _link_target_allowed(row, user=user, roles=roles, rules=rules):
            continue

        filtered.append(row)
        if pending_section:
            section_has_links = True

    flush_empty_section()
    return filtered


def apply_menu_access_to_bootinfo(bootinfo, user: str | None = None) -> None:
    user = user or frappe.session.user
    roles = _get_roles(user)
    bootinfo.orderlift_menu_access = get_boot_menu_access(user)
    bootinfo.orderlift_company_access = get_company_access_payload(user)
    bootinfo.orderlift_business_type_access = get_business_type_access_payload(user)

    workspace_sidebar = bootinfo.get("workspace_sidebar_item") or {}
    main_sidebar = _get_main_dashboard_sidebar(workspace_sidebar)
    if not main_sidebar or not isinstance(main_sidebar.get("items"), list):
        return

    if _is_orderlift_business_user(user, roles):
        bootinfo["workspace_sidebar_item"] = {"main dashboard": main_sidebar}
        workspace_sidebar = bootinfo["workspace_sidebar_item"]
    else:
        for section in get_menu_sections():
            workspace_sidebar.pop(section["label"], None)

    main_sidebar["items"] = filter_sidebar_rows(main_sidebar["items"], user=user)


def _get_main_dashboard_sidebar(workspace_sidebar: dict) -> dict | None:
    return workspace_sidebar.get("main dashboard") or workspace_sidebar.get("Main Dashboard")


def get_boot_menu_access(user: str | None = None) -> dict:
    user = user or frappe.session.user
    roles = _get_roles(user)
    rules = _menu_rule_map()
    visible_keys = []
    for item in iter_menu_items():
        if user_can_access_menu_key(item["key"], user=user, roles=roles, rules=rules) and _link_target_allowed(
            item,
            user=user,
            roles=roles,
            rules=rules,
        ):
            visible_keys.append(item["key"])
    return {
        "visible_menu_keys": visible_keys,
        "is_admin": _is_admin_user(user, roles),
    }


def _frappe_whitelist():
    whitelist = getattr(frappe, "whitelist", None)
    if whitelist:
        return whitelist()
    return lambda fn: fn


def get_company_access_payload(user: str | None = None, requested_company: str | None = None) -> dict:
    user = user or frappe.session.user
    unrestricted = user_can_access_all_companies(user)
    companies = get_allowed_companies(user) if not unrestricted else get_all_companies()
    user_default_company = get_user_default_company(user)
    return {
        "unrestricted": unrestricted,
        "companies": companies,
        "current_company": resolve_current_company(
            user=user,
            requested_company=requested_company,
            allowed_companies=companies,
        ),
        "user_default_company": user_default_company if user_default_company in companies else "",
        "company_currencies": get_company_currency_map(companies),
    }


def get_company_currency_map(companies: list[str] | tuple[str, ...] | None = None) -> dict[str, str]:
    companies = [company for company in (companies or []) if company]
    if not companies or not _doctype_available(COMPANY_DOCTYPE):
        return {}

    currencies: dict[str, str] = {}
    rows = frappe.get_all(
        COMPANY_DOCTYPE,
        filters={"name": ["in", companies]},
        fields=["name", "default_currency"],
        limit_page_length=0,
    )
    for row in rows:
        name = row.get("name") if hasattr(row, "get") else getattr(row, "name", "")
        currency = row.get("default_currency") if hasattr(row, "get") else getattr(row, "default_currency", "")
        if name:
            currencies[name] = currency or ""
    return currencies


@_frappe_whitelist()
def get_current_company_access_payload() -> dict:
    return get_company_access_payload(user=frappe.session.user)


@_frappe_whitelist()
def set_current_company(company: str) -> dict:
    company = (company or "").strip()
    if not company:
        frappe.throw("Company is required")
    if not user_can_access_company(company):
        frappe.throw(f"You do not have access to company {company}.")
    _set_user_default_company(company, user=frappe.session.user)
    frappe.clear_cache(user=frappe.session.user)
    return get_company_access_payload(requested_company=company)


def resolve_current_company(
    user: str | None = None,
    requested_company: str | None = None,
    allowed_companies: list[str] | None = None,
) -> str:
    user = user or frappe.session.user
    allowed_companies = allowed_companies if allowed_companies is not None else get_allowed_companies(user)
    requested_company = (requested_company or "").strip()
    if requested_company:
        if requested_company in allowed_companies:
            return requested_company
        frappe.throw(f"You do not have access to company {requested_company}.")

    default_company = get_user_default_company(user)
    if default_company in allowed_companies:
        return default_company
    return allowed_companies[0] if allowed_companies else ""


def get_user_default_company(user: str | None = None) -> str:
    defaults = getattr(frappe, "defaults", None)
    if not defaults or not hasattr(defaults, "get_user_default"):
        return ""
    with suppress(Exception):
        return (defaults.get_user_default("Company", user=user or frappe.session.user) or "").strip()
    with suppress(Exception):
        return (defaults.get_user_default("Company") or "").strip()
    return ""


def _set_user_default_company(company: str, user: str | None = None) -> None:
    defaults = getattr(frappe, "defaults", None)
    if not defaults or not hasattr(defaults, "set_user_default"):
        return
    user = user or frappe.session.user
    with suppress(Exception):
        defaults.set_user_default("Company", company, user=user)
        return
    with suppress(Exception):
        defaults.set_user_default("Company", company)


def get_all_companies() -> list[str]:
    if not _doctype_available(COMPANY_DOCTYPE):
        return []
    return frappe.get_all(COMPANY_DOCTYPE, pluck="name", order_by="name asc", limit_page_length=0)


def get_allowed_companies(user: str | None = None) -> list[str]:
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return get_all_companies()
    if not _doctype_available("User Permission"):
        return []
    permissions = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": COMPANY_DOCTYPE},
        fields=["for_value", "apply_to_all_doctypes", "applicable_for"],
        order_by="for_value asc",
        limit_page_length=0,
    )
    return [
        row.for_value
        for row in permissions
        if cint(row.get("apply_to_all_doctypes")) and not (row.get("applicable_for") or "").strip()
    ]


def user_can_access_all_companies(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return user == "Administrator"
    return bool(_get_roles(user).intersection(ADMIN_BYPASS_ROLES))


def user_can_access_company(company: str | None, user: str | None = None) -> bool:
    if not company:
        return True
    if user_can_access_all_companies(user):
        return True
    return company in set(get_allowed_companies(user))


def save_user_company_access(user: str, companies: list[str] | str, default_company: str | None = None) -> dict:
    user = (user or "").strip()
    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User {user} was not found.")

    company_names = _clean_list(companies)
    default_company = (default_company or "").strip()
    missing = [company for company in company_names if not frappe.db.exists(COMPANY_DOCTYPE, company)]
    if missing:
        frappe.throw(f"Unknown companies: {', '.join(missing)}")
    if default_company:
        if default_company not in company_names:
            frappe.throw(f"Default company must be one of the assigned companies: {default_company}")
        if not frappe.db.exists(COMPANY_DOCTYPE, default_company):
            frappe.throw(f"Unknown default company: {default_company}")

    existing = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": COMPANY_DOCTYPE},
        fields=["name", "apply_to_all_doctypes", "applicable_for"],
        limit_page_length=0,
    )
    for row in existing:
        if cint(row.get("apply_to_all_doctypes")) and not (row.get("applicable_for") or "").strip():
            frappe.delete_doc("User Permission", row.name, ignore_permissions=True)

    for company in company_names:
        doc = frappe.new_doc("User Permission")
        doc.user = user
        doc.allow = COMPANY_DOCTYPE
        doc.for_value = company
        doc.apply_to_all_doctypes = 1
        doc.is_default = 0
        doc.insert(ignore_permissions=True)

    if default_company:
        _set_user_default_company(default_company, user=user)

    frappe.clear_cache(user=user)
    return {"user": user, "companies": company_names, "default_company": default_company}


# ---------------------------------------------------------------------------
# Per-user business-type access (mirrors the company access model above).
#
# Stored as ``User Permission`` rows with ``allow="CRM Business Type"`` and
# ``apply_to_all_doctypes=1``. Opt-in: a user with no such permission is
# unrestricted (sees all business types within their allowed companies).
# ---------------------------------------------------------------------------


def get_business_type_access_payload(user: str | None = None) -> dict:
    user = user or frappe.session.user
    unrestricted = user_can_access_all_business_types(user)
    return {
        "unrestricted": unrestricted,
        "business_types": [] if unrestricted else get_allowed_business_types(user),
    }


def get_allowed_business_types(user: str | None = None) -> list[str]:
    user = user or frappe.session.user
    if not _doctype_available("User Permission"):
        return []
    permissions = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": BUSINESS_TYPE_DOCTYPE},
        fields=["for_value", "apply_to_all_doctypes", "applicable_for"],
        order_by="for_value asc",
        limit_page_length=0,
    )
    return [
        row.for_value
        for row in permissions
        if cint(row.get("apply_to_all_doctypes")) and not (row.get("applicable_for") or "").strip()
    ]


def user_can_access_all_business_types(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return True
    # Opt-in: no configured allow-list means no business-type restriction.
    return not get_allowed_business_types(user)


def user_can_access_business_type(business_type: str | None, user: str | None = None) -> bool:
    business_type = (business_type or "").strip()
    if not business_type:
        return True
    if user_can_access_all_business_types(user):
        return True
    return business_type in set(get_allowed_business_types(user))


def save_user_business_type_access(user: str, business_types: list[str] | str) -> dict:
    user = (user or "").strip()
    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User {user} was not found.")

    business_type_names = _clean_list(business_types)
    missing = [bt for bt in business_type_names if not frappe.db.exists(BUSINESS_TYPE_DOCTYPE, bt)]
    if missing:
        frappe.throw(f"Unknown business types: {', '.join(missing)}")

    existing = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": BUSINESS_TYPE_DOCTYPE},
        fields=["name", "apply_to_all_doctypes", "applicable_for"],
        limit_page_length=0,
    )
    for row in existing:
        if cint(row.get("apply_to_all_doctypes")) and not (row.get("applicable_for") or "").strip():
            frappe.delete_doc("User Permission", row.name, ignore_permissions=True)

    for business_type in business_type_names:
        doc = frappe.new_doc("User Permission")
        doc.user = user
        doc.allow = BUSINESS_TYPE_DOCTYPE
        doc.for_value = business_type
        doc.apply_to_all_doctypes = 1
        doc.is_default = 0
        doc.insert(ignore_permissions=True)

    frappe.clear_cache(user=user)
    return {"user": user, "business_types": business_type_names}


def _menu_rule_map() -> dict[str, object]:
    if not _doctype_available(MENU_ACCESS_DOCTYPE):
        return {}
    with suppress(Exception):
        rows = frappe.get_all(
            MENU_ACCESS_DOCTYPE,
            fields=["name", "menu_key"],
            limit_page_length=0,
        )
        return {row.menu_key: frappe.get_doc(MENU_ACCESS_DOCTYPE, row.name) for row in rows if row.get("menu_key")}
    return {}


def _rule_enabled(rule) -> bool:
    if rule is None:
        return True
    return bool(cint(rule.get("enabled")))


def _rule_roles(rule, menu_key: str) -> list[str]:
    if rule is None:
        return default_roles_for_key(menu_key)
    roles = _clean_list(rule.get("allowed_roles_json"))
    return roles


def _rule_denied_roles(rule) -> list[str]:
    if rule is None:
        return []
    return _clean_list(rule.get("denied_roles_json"))


def _roles_allow(allowed_roles: list[str], user_roles: set[str]) -> bool:
    if ALL_USERS_ROLE in allowed_roles:
        return True
    return bool(set(allowed_roles).intersection(user_roles))


def _prune_legacy_default_roles(roles: list[str]) -> list[str]:
    allowed_legacy = set(BUSINESS_ROLES) | {ALL_USERS_ROLE, "System Manager", "Developer"}
    return [
        role
        for role in roles
        if role not in LEGACY_DEFAULT_MENU_ROLES or role in allowed_legacy
    ]


def _sanitize_allowed_roles_for_item(item: dict, roles: list[str]) -> list[str]:
    roles = _prune_legacy_default_roles(roles)
    if item.get("section_key") != "administration":
        return roles

    allowed_admin_roles = set(ADMIN_ROLES) | {"Orderlift Admin", "Administrator", "System Manager", "Developer"}
    return [role for role in roles if role in allowed_admin_roles]


def _link_target_allowed(row: dict, *, user: str, roles: set[str], rules: dict[str, object] | None = None) -> bool:
    link_type = row.get("link_type")
    link_to = row.get("link_to")
    if not link_type or not link_to:
        return True
    if _is_admin_user(user, roles):
        return True
    if link_type == "DocType":
        with suppress(Exception):
            return bool(frappe.has_permission(link_to, "read", user=user))
        return False
    if link_type == "Page":
        if not user_can_access_page(link_to, user=user, rules=rules):
            return False
        return _page_required_doctypes_allowed(row, user=user)
    if link_type == "Report":
        report_roles = _child_roles("Report", link_to)
        return not report_roles or bool(roles.intersection(report_roles))
    return True


def _page_required_doctypes_allowed(row: dict, *, user: str) -> bool:
    item = menu_item_for_row(row) or {}
    return _required_doctypes_allowed(item.get("required_doctypes") or row.get("required_doctypes"), user=user)


def _required_doctypes_allowed(required_doctypes, *, user: str) -> bool:
    required_doctypes = _clean_list(required_doctypes)
    for doctype in required_doctypes:
        with suppress(Exception):
            if not frappe.has_permission(doctype, "read", user=user):
                return False
            continue
        return False
    return True


def _page_roles(page_name: str) -> set[str]:
    return _child_roles("Page", page_name)


def _child_roles(parenttype: str, parent: str) -> set[str]:
    if not parent:
        return set()
    with suppress(Exception):
        return set(
            frappe.get_all(
                "Has Role",
                filters={"parenttype": parenttype, "parent": parent},
                pluck="role",
                limit_page_length=0,
            )
        )
    return set()


def _get_roles(user: str | None = None) -> set[str]:
    user = user or frappe.session.user
    if user == "Administrator":
        return {"Administrator", "System Manager"}
    if user == "Guest":
        return set()
    with suppress(Exception):
        return set(frappe.get_roles(user) or [])
    return set()


def _is_admin_user(user: str, roles: set[str]) -> bool:
    return user == "Administrator" or bool(roles.intersection(ADMIN_BYPASS_ROLES))


def _is_orderlift_business_user(user: str, roles: set[str]) -> bool:
    if user == "Guest":
        return False
    return user == "Administrator" or bool(roles.intersection(BUSINESS_ROLES))


def _clean_list(value: str | list | tuple | set | None) -> list[str]:
    if isinstance(value, str):
        with suppress(ValueError, TypeError):
            decoded = json.loads(value or "[]")
            value = decoded
        if isinstance(value, str):
            value = [value]
    clean = []
    for item in value or []:
        item = (item or "").strip()
        if item and item not in clean:
            clean.append(item)
    return clean


def _doctype_available(doctype: str) -> bool:
    with suppress(Exception):
        return bool(frappe.db.exists("DocType", doctype))
    return False


def build_central_sidebar_rows() -> list[dict]:
    return apply_menu_rule_overrides(build_sidebar_rows())


def apply_menu_rule_overrides(rows: list[dict]) -> list[dict]:
    rules = _menu_rule_map()
    if not rules:
        return [_strip_internal_menu_key(row) for row in rows]

    result: list[dict] = []
    section: dict | None = None
    section_links: list[tuple[int, int, dict]] = []
    section_blocks: list[tuple[int, int, dict, list[tuple[int, int, dict]]]] = []
    position = 0

    def flush_section() -> None:
        nonlocal section, section_links
        if section:
            section_order = min((order for order, _position, _link_row in section_links), default=position)
            section_blocks.append((section_order, position, section, section_links))
        section = None
        section_links = []

    for row in rows:
        position += 1
        if row.get("type") == "Section Break":
            flush_section()
            section = dict(row)
            continue
        if row.get("type") != "Link":
            result.append(_strip_internal_menu_key(row))
            continue

        link_row = dict(row)
        item = menu_item_for_row(link_row)
        rule = rules.get(item["key"]) if item else None
        if rule:
            label = (rule.get("label") or "").strip()
            if label:
                link_row["label"] = label
            order = cint(rule.get("menu_order")) or position
        else:
            order = position
        link_row = _strip_internal_menu_key(link_row)
        if section:
            section_links.append((order, position, link_row))
        else:
            result.append(link_row)

    flush_section()
    for _section_order, _section_position, section_row, links in sorted(section_blocks, key=lambda item: (item[0], item[1])):
        result.append(section_row)
        for _order, _position, link_row in sorted(links, key=lambda item: (item[0], item[1])):
            result.append(link_row)
    return result


def _strip_internal_menu_key(row: dict) -> dict:
    clean = dict(row)
    clean.pop("_menu_key", None)
    return clean
