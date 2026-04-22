import frappe


CLIENT_SHELL_ROLE = "Orderlift Client User"
ROLE_NAME = "Orderlift Business Admin"
PROFILE_NAME = "Orderlift Business Admin"
LANDING_URL = "/desk/home-page?sidebar=Main+Dashboard"
ROLES_TO_REMOVE = [
    "Accounts User",
    "Customer",
    "Maintenance User",
    "Manufacturing User",
    "Projects User",
    "Purchase User",
    "Sales User",
    "Stock User",
    "Supplier",
]

PROFILE_ROLES = [
    "Analytics",
    "HR Manager",
    "Item Manager",
    "Maintenance Manager",
    "Manufacturing Manager",
    CLIENT_SHELL_ROLE,
    ROLE_NAME,
    "Orderlift Admin",
    "Projects Manager",
    "Purchase Manager",
    "Purchase Master Manager",
    "Sales Manager",
    "Sales Master Manager",
    "Stock Manager",
]

CUSTOM_DOCPERMS = {
    "User": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "report": 1,
            "export": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        },
        {
            "permlevel": 1,
            "read": 1,
            "write": 1,
        },
    ],
    "Role": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "report": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Role Profile": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "report": 1,
            "export": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        },
        {
            "permlevel": 1,
            "read": 1,
            "write": 1,
            "report": 1,
            "export": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        },
    ],
    "User Permission": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "report": 1,
            "export": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Workflow": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Workflow State": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Assignment Rule": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "report": 1,
            "export": 1,
            "share": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Event": [
        {
            "permlevel": 0,
            "read": 1,
        }
    ],
    "Sales Invoice": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "report": 1,
            "export": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Purchase Invoice": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "report": 1,
            "export": 1,
            "print": 1,
            "email": 1,
        }
    ],
    "Payment Entry": [
        {
            "permlevel": 0,
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "report": 1,
            "export": 1,
            "print": 1,
            "email": 1,
        }
    ],
}

PAGE_ROLES = {
    "permission-manager": [ROLE_NAME],
}

REPORT_ROLES = {
    "Sales Payment Summary": [ROLE_NAME],
}


def _ensure_role(role_name):
    if frappe.db.exists("Role", role_name):
        role = frappe.get_doc("Role", role_name)
    else:
        role = frappe.new_doc("Role")
        role.role_name = role_name
        role.is_custom = 1

    role.desk_access = 1
    role.disabled = 0
    role.two_factor_auth = 0
    role.save(ignore_permissions=True)
    return role.name


def _ensure_role_profile(profile_name, roles):
    if frappe.db.exists("Role Profile", profile_name):
        profile = frappe.get_doc("Role Profile", profile_name)
    else:
        profile = frappe.new_doc("Role Profile")
        profile.role_profile = profile_name

    profile.set("roles", [])
    for idx, role in enumerate(roles, start=1):
        profile.append("roles", {"role": role, "idx": idx})

    profile.save(ignore_permissions=True)
    return profile.name


def _ensure_custom_docperm(doctype_name, role_name, values):
    filters = {"parent": doctype_name, "role": role_name, "permlevel": values.get("permlevel", 0)}
    doc_name = frappe.db.exists("Custom DocPerm", filters)

    if doc_name:
        docperm = frappe.get_doc("Custom DocPerm", doc_name)
    else:
        docperm = frappe.get_doc(
            {
                "doctype": "Custom DocPerm",
                "parent": doctype_name,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role_name,
                "permlevel": values.get("permlevel", 0),
            }
        )

    flags = {
        "select": 0,
        "read": 0,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "mask": 0,
        "if_owner": 0,
        "impersonate": 0,
    }
    flags.update(values)

    for fieldname, value in flags.items():
        setattr(docperm, fieldname, value)

    if doc_name:
        docperm.save(ignore_permissions=True)
    else:
        docperm.insert(ignore_permissions=True)


def _ensure_page_role(page_name, role_name):
    page = frappe.get_doc("Page", page_name)
    existing_roles = {row.role for row in page.get("roles", [])}
    if role_name not in existing_roles:
        page.append("roles", {"role": role_name})
        page.save(ignore_permissions=True)


def _ensure_has_role(parenttype, parent, role_name):
    existing = frappe.db.exists(
        "Has Role", {"parenttype": parenttype, "parent": parent, "role": role_name}
    )
    if existing:
        return

    doc = frappe.get_doc(parenttype, parent)
    doc.append("roles", {"role": role_name})
    doc.save(ignore_permissions=True)


def _apply_profile_to_user(user_name):
    user = frappe.get_doc("User", user_name)
    # Route guards and docperms enforce the restricted shell. Blocking modules
    # breaks dashboards and workspace content by emptying allowed_modules.
    user.module_profile = None
    user.set("block_modules", [])
    user.default_workspace = "Main Dashboard"
    user.redirect_url = LANDING_URL
    user.search_bar = 1
    user.role_profile_name = None
    user.set("role_profiles", [])
    user.append("role_profiles", {"role_profile": PROFILE_NAME})

    frappe.db.delete("Has Role", {"parent": user.name, "parenttype": "User"})
    user.set("roles", [])
    for idx, role in enumerate(PROFILE_ROLES, start=1):
        user.append("roles", {"role": role, "idx": idx})

    user.save(ignore_permissions=True)
    frappe.db.sql(
        """
        delete from `tabBlock Module`
        where parent=%s and parenttype='User' and parentfield='block_modules'
        """,
        (user.name,),
    )
    user.remove_roles(*ROLES_TO_REMOVE)
    frappe.db.set_value("User", user.name, "role_profile_name", PROFILE_NAME, update_modified=False)
    user.reload()
    return {
        "user": user.name,
        "role_profile_name": user.role_profile_name,
        "module_profile": user.module_profile,
        "default_workspace": user.default_workspace,
        "redirect_url": user.redirect_url,
    }


@frappe.whitelist()
def ensure_business_admin_access(user_name=None):
    _ensure_role(CLIENT_SHELL_ROLE)
    _ensure_role(ROLE_NAME)
    _ensure_role_profile(PROFILE_NAME, PROFILE_ROLES)

    for doctype_name, permission_sets in CUSTOM_DOCPERMS.items():
        for permission_set in permission_sets:
            _ensure_custom_docperm(doctype_name, ROLE_NAME, permission_set)

    for page_name, roles in PAGE_ROLES.items():
        for role_name in roles:
            _ensure_page_role(page_name, role_name)

    for report_name, roles in REPORT_ROLES.items():
        for role_name in roles:
            _ensure_has_role("Report", report_name, role_name)

    user_summary = None
    if user_name:
        user_summary = _apply_profile_to_user(user_name)

    frappe.clear_cache()
    return {
        "role": ROLE_NAME,
        "role_profile": PROFILE_NAME,
        "profile_roles": PROFILE_ROLES,
        "custom_docperms": sorted(CUSTOM_DOCPERMS.keys()),
        "page_roles": PAGE_ROLES,
        "report_roles": REPORT_ROLES,
        "user": user_summary,
    }
