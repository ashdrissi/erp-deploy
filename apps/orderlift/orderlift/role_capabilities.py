from __future__ import annotations

import frappe

from orderlift.startup_roles import CANONICAL_BUSINESS_ROLES


ROLE_CAPABILITY_FIELD = "custom_orderlift_capabilities"

CAPABILITY_PRIVILEGED_PRICING = "privileged_pricing"
CAPABILITY_QUOTATION_OVERRIDE = "quotation_override"
CAPABILITY_PURCHASING_ACCESS = "purchasing_access"
CAPABILITY_TODO_ALL_ACCESS = "todo_all_access"
CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT = "saved_other_charge_management"
CAPABILITY_STOCK_RATE_MANAGEMENT = "stock_rate_management"
CAPABILITY_STOCK_RESERVATION_MANAGEMENT = "stock_reservation_management"
CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT = "commission_assignment_management"
CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT = "commission_payout_management"
CAPABILITY_PIPELINE_ASSIGNMENT_MANAGEMENT = "pipeline_assignment_management"
CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT = "opportunity_pipeline_assignment"
CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT = "project_pipeline_assignment"
CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT = "sales_order_pipeline_assignment"
CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT = "purchase_agent_rules_management"
CAPABILITY_DELETE_SUBMITTED_BLOCKERS = "delete_submitted_blockers"
CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL = "party_company_access_approval"

PURCHASE_AGENT_RULES_DOCTYPE = "Purchase Agent Rules"

CAPABILITY_GROUPS = {
    "sales_pricing": "Sales & Pricing",
    "purchasing_stock": "Purchasing & Stock",
    "work_management": "Work Management",
}

ROLE_CAPABILITIES = {
    CAPABILITY_PRIVILEGED_PRICING: "Privileged Pricing",
    CAPABILITY_QUOTATION_OVERRIDE: "Pricing Override",
    CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT: "Manage Saved Other Charges",
    CAPABILITY_PURCHASING_ACCESS: "Purchasing Access",
    CAPABILITY_TODO_ALL_ACCESS: "All ToDos Access",
    CAPABILITY_STOCK_RATE_MANAGEMENT: "Stock Rate Management",
    CAPABILITY_STOCK_RESERVATION_MANAGEMENT: "Stock Reservation Management",
    CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT: "Commission Assignment Management",
    CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT: "Commission Payout Management",
    CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT: "Opportunity Pipeline Assignment",
    CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT: "Project Pipeline Assignment",
    CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT: "Sales Order Pipeline Assignment",
    CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT: "Manage Purchase Agent Rules",
    CAPABILITY_DELETE_SUBMITTED_BLOCKERS: "Delete Submitted Blockers",
    CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL: "Approve Party Company Access",
}

CAPABILITY_METADATA = {
    CAPABILITY_PRIVILEGED_PRICING: {
        "group": "sales_pricing",
        "description": "See privileged pricing, cost, margin, benchmark, and active-company price-list data.",
    },
    CAPABILITY_QUOTATION_OVERRIDE: {
        "group": "sales_pricing",
        "description": "Override quotation and pricing-sheet discounts, floor checks, and automatic repricing gates.",
    },
    CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT: {
        "group": "sales_pricing",
        "description": "Create, edit, disable, delete, import, and export reusable Other Charge templates.",
    },
    CAPABILITY_PURCHASING_ACCESS: {
        "group": "purchasing_stock",
        "description": "Access purchasing workflows, supplier buying data, and buying price-list operations.",
    },
    CAPABILITY_STOCK_RATE_MANAGEMENT: {
        "group": "purchasing_stock",
        "description": "Review and approve provisional or missing inventory valuation rates.",
    },
    CAPABILITY_STOCK_RESERVATION_MANAGEMENT: {
        "group": "purchasing_stock",
        "description": "Reserve customer stock through Pick Lists and manage stock allocation notifications.",
    },
    CAPABILITY_TODO_ALL_ACCESS: {
        "group": "work_management",
        "description": "View and manage ToDos beyond the user's own assignments.",
    },
    CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT: {
        "group": "work_management",
        "description": "Assign commission beneficiaries and view team commission records.",
    },
    CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT: {
        "group": "work_management",
        "description": "Approve commission payout state and mark commissions as paid.",
    },
    CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT: {
        "group": "work_management",
        "description": "Assign or unassign Opportunity pipeline cards.",
    },
    CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT: {
        "group": "work_management",
        "description": "Assign or unassign Project pipeline cards.",
    },
    CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT: {
        "group": "work_management",
        "description": "Assign or unassign Sales Order pipeline cards.",
    },
    CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT: {
        "group": "purchasing_stock",
        "description": "Create and maintain company-scoped Buying Price List allowances for purchasing users.",
    },
    CAPABILITY_DELETE_SUBMITTED_BLOCKERS: {
        "group": "work_management",
        "description": "Cancel and delete submitted documents through the explicit Delete Blockers helper only.",
    },
    CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL: {
        "group": "work_management",
        "description": "Approve reuse of Lead, Prospect, and Customer records by another internal company.",
    },
}

DEFAULT_ROLE_CAPABILITIES = {
    **{role: [] for role in CANONICAL_BUSINESS_ROLES},
    "System Manager": list(ROLE_CAPABILITIES),
    "Orderlift Admin": list(ROLE_CAPABILITIES),
    "Sales Manager": [
        CAPABILITY_QUOTATION_OVERRIDE,
        CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT,
        CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT,
        CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT,
        CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT,
        CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL,
    ],
    "Purchase User": [CAPABILITY_PURCHASING_ACCESS],
    "Purchase Manager": [CAPABILITY_PURCHASING_ACCESS],
    "Stock User": [CAPABILITY_STOCK_RESERVATION_MANAGEMENT],
    "Stock Manager": [CAPABILITY_STOCK_RATE_MANAGEMENT, CAPABILITY_STOCK_RESERVATION_MANAGEMENT],
    "Logistics User": [CAPABILITY_STOCK_RESERVATION_MANAGEMENT],
    "Finance Admin": [CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT],
    "Pricing Configuration": [
        CAPABILITY_PRIVILEGED_PRICING,
        CAPABILITY_PURCHASING_ACCESS,
        CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT,
    ],
}

DEFAULT_CAPABILITY_UPGRADES = {
    "Orderlift Admin": [CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT, CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL],
}

HARDCODED_CAPABILITY_ROLES = {"System Manager"}


def capability_options() -> list[dict[str, str]]:
    rows = []
    for value, label in ROLE_CAPABILITIES.items():
        metadata = CAPABILITY_METADATA.get(value, {})
        group = metadata.get("group") or "sales_pricing"
        rows.append(
            {
                "value": value,
                "label": label,
                "group": group,
                "group_label": CAPABILITY_GROUPS.get(group, group),
                "description": metadata.get("description") or "",
            }
        )
    return rows


@frappe.whitelist()
def get_capability_options() -> list[dict[str, str]]:
    frappe.has_permission("Role", "read", throw=True)
    return capability_options()


def normalize_capabilities(value) -> list[str]:
    if isinstance(value, str):
        raw_values = value.replace(",", "\n").splitlines()
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = []
    return list(dict.fromkeys(item for item in ((entry or "").strip() for entry in raw_values) if item in ROLE_CAPABILITIES))


def serialize_capabilities(capabilities) -> str:
    return "\n".join(normalize_capabilities(capabilities))


def migrate_legacy_pipeline_assignment_capabilities() -> None:
    if not _has_role_capability_field():
        return
    replacement = [
        CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT,
        CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT,
        CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT,
    ]
    rows = frappe.get_all(
        "Role",
        filters={ROLE_CAPABILITY_FIELD: ["like", f"%{CAPABILITY_PIPELINE_ASSIGNMENT_MANAGEMENT}%"]},
        fields=["name", ROLE_CAPABILITY_FIELD],
        limit_page_length=0,
    )
    for row in rows:
        raw = (row.get(ROLE_CAPABILITY_FIELD) or "").replace(",", "\n").splitlines()
        values = [value.strip() for value in raw if value.strip() != CAPABILITY_PIPELINE_ASSIGNMENT_MANAGEMENT]
        values.extend(replacement)
        frappe.db.set_value(
            "Role",
            row.name,
            ROLE_CAPABILITY_FIELD,
            serialize_capabilities(values),
            update_modified=False,
        )


def normalize_role_capabilities(doc, method=None) -> None:
    if not getattr(doc, "meta", None) or not doc.meta.get_field(ROLE_CAPABILITY_FIELD):
        return
    doc.set(ROLE_CAPABILITY_FIELD, serialize_capabilities(doc.get(ROLE_CAPABILITY_FIELD)))


def sync_purchase_agent_rule_permissions_for_role(doc, method=None) -> None:
    """Keep Purchase Agent Rules DocPerms aligned with the management capability."""
    role = (getattr(doc, "name", None) or getattr(doc, "role_name", None) or "").strip()
    if role:
        _sync_purchase_agent_rule_permissions(role)


def sync_purchase_agent_rule_permissions() -> None:
    if not frappe.db.exists("DocType", PURCHASE_AGENT_RULES_DOCTYPE):
        return
    for role in frappe.get_all("Role", pluck="name", limit_page_length=0):
        _sync_purchase_agent_rule_permissions(role)


def _sync_purchase_agent_rule_permissions(role: str) -> None:
    if not frappe.db.exists("Role", role) or not frappe.db.exists("DocType", PURCHASE_AGENT_RULES_DOCTYPE):
        return

    filters = {"parent": PURCHASE_AGENT_RULES_DOCTYPE, "role": role, "permlevel": 0}
    existing = frappe.db.exists("Custom DocPerm", filters)
    can_manage = CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT in get_role_capabilities(role)
    if not can_manage:
        if existing:
            frappe.delete_doc("Custom DocPerm", existing, ignore_permissions=True)
        return

    if existing:
        return

    permission = frappe.new_doc("Custom DocPerm")
    permission.parent = PURCHASE_AGENT_RULES_DOCTYPE
    permission.parenttype = "DocType"
    permission.parentfield = "permissions"
    permission.role = role
    permission.permlevel = 0
    permission.read = 1
    permission.select = 1
    permission.write = 1
    permission.create = 1
    permission.report = 1
    permission.print = 1
    permission.email = 1
    permission.delete = 0
    permission.export = 0
    permission.set("import", 0)
    permission.insert(ignore_permissions=True)


def get_role_capabilities(role: str) -> list[str]:
    role = (role or "").strip()
    if not role or not _has_role_capability_field():
        return []
    try:
        value = frappe.db.get_value("Role", role, ROLE_CAPABILITY_FIELD)
    except Exception:
        return []
    return normalize_capabilities(value)


def user_has_capability(capability: str, user: str | None = None, roles: set[str] | None = None) -> bool:
    capability = (capability or "").strip()
    if capability not in ROLE_CAPABILITIES:
        return False
    user = user or getattr(getattr(frappe, "session", None), "user", "")
    if user == "Administrator":
        return True
    roles = set(roles if roles is not None else (frappe.get_roles(user) or []))
    if roles & HARDCODED_CAPABILITY_ROLES:
        return True
    return any(capability in get_role_capabilities(role) for role in roles)


def role_capability_decision(
    capability: str,
    legacy_allowed: bool,
    *,
    user: str | None = None,
    roles: set[str] | None = None,
    context: str = "",
) -> bool:
    return user_has_capability(capability, user=user, roles=roles)


def seed_default_role_capabilities() -> None:
    if not _has_role_capability_field():
        return
    for role, capabilities in DEFAULT_ROLE_CAPABILITIES.items():
        if not frappe.db.exists("Role", role):
            continue
        current = frappe.db.get_value("Role", role, ROLE_CAPABILITY_FIELD)
        current_capabilities = normalize_capabilities(current)
        if current_capabilities or not capabilities:
            continue
        frappe.db.set_value(
            "Role",
            role,
            ROLE_CAPABILITY_FIELD,
            serialize_capabilities(capabilities),
            update_modified=False,
        )


def upgrade_canonical_role_capabilities() -> None:
    """Apply additive defaults and remove legacy page-derived pipeline grants."""
    if not _has_role_capability_field():
        return
    pipeline_capabilities = {
        CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT,
        CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT,
        CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT,
    }
    for role in CANONICAL_BUSINESS_ROLES:
        if not frappe.db.exists("Role", role):
            continue
        current = set(get_role_capabilities(role))
        desired_defaults = set(DEFAULT_ROLE_CAPABILITIES.get(role, []))
        current.difference_update(pipeline_capabilities - desired_defaults)
        current.update(desired_defaults)
        current.update(DEFAULT_CAPABILITY_UPGRADES.get(role, []))
        value = serialize_capabilities(current)
        if value != (frappe.db.get_value("Role", role, ROLE_CAPABILITY_FIELD) or ""):
            frappe.db.set_value("Role", role, ROLE_CAPABILITY_FIELD, value, update_modified=False)


@frappe.whitelist()
def normalize_managed_role_capabilities(dry_run: int = 1) -> dict:
    """Overwrite canonical role capability values with the approved exact defaults."""
    frappe.only_for("System Manager")
    dry_run = bool(int(dry_run or 0))
    result = {"dry_run": dry_run, "updated": [], "missing_roles": []}
    if not _has_role_capability_field():
        return {**result, "skipped": "Role capability field is unavailable"}
    for role in [*CANONICAL_BUSINESS_ROLES, "System Manager"]:
        if not frappe.db.exists("Role", role):
            result["missing_roles"].append(role)
            continue
        desired = serialize_capabilities(DEFAULT_ROLE_CAPABILITIES.get(role, []))
        current = serialize_capabilities(frappe.db.get_value("Role", role, ROLE_CAPABILITY_FIELD))
        if current == desired:
            continue
        result["updated"].append({"role": role, "from": current, "to": desired})
        if not dry_run:
            frappe.db.set_value("Role", role, ROLE_CAPABILITY_FIELD, desired, update_modified=False)
    if not dry_run and result["updated"]:
        frappe.clear_cache()
        frappe.db.commit()
    return result


def _has_role_capability_field() -> bool:
    try:
        return bool(frappe.get_meta("Role").get_field(ROLE_CAPABILITY_FIELD))
    except Exception:
        return False
