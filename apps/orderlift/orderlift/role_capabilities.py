from __future__ import annotations

import frappe


ROLE_CAPABILITY_FIELD = "custom_orderlift_capabilities"

CAPABILITY_PRIVILEGED_PRICING = "privileged_pricing"
CAPABILITY_QUOTATION_OVERRIDE = "quotation_override"
CAPABILITY_PURCHASING_ACCESS = "purchasing_access"
CAPABILITY_TODO_ALL_ACCESS = "todo_all_access"

ROLE_CAPABILITIES = {
    CAPABILITY_PRIVILEGED_PRICING: "Privileged Pricing",
    CAPABILITY_QUOTATION_OVERRIDE: "Pricing Override",
    CAPABILITY_PURCHASING_ACCESS: "Purchasing Access",
    CAPABILITY_TODO_ALL_ACCESS: "All ToDos Access",
}

DEFAULT_ROLE_CAPABILITIES = {
    "Orderlift Admin": [
        CAPABILITY_PRIVILEGED_PRICING,
        CAPABILITY_QUOTATION_OVERRIDE,
        CAPABILITY_PURCHASING_ACCESS,
        CAPABILITY_TODO_ALL_ACCESS,
    ],
    "Orderlift Business Admin": [CAPABILITY_PRIVILEGED_PRICING, CAPABILITY_QUOTATION_OVERRIDE],
    "Pricing Manager": [CAPABILITY_PRIVILEGED_PRICING],
    "Sales Manager": [CAPABILITY_PRIVILEGED_PRICING],
    "Purchase Manager": [CAPABILITY_PRIVILEGED_PRICING, CAPABILITY_PURCHASING_ACCESS],
    "Purchase User": [CAPABILITY_PURCHASING_ACCESS],
    "Purchasing User": [CAPABILITY_PURCHASING_ACCESS],
    "Stock Manager": [CAPABILITY_PURCHASING_ACCESS],
    "System Manager": [
        CAPABILITY_PRIVILEGED_PRICING,
        CAPABILITY_QUOTATION_OVERRIDE,
        CAPABILITY_PURCHASING_ACCESS,
        CAPABILITY_TODO_ALL_ACCESS,
    ],
}

HARDCODED_CAPABILITY_ROLES = {"Orderlift Admin", "System Manager"}
_logged_capability_mismatches: set[tuple[str, str, bool, bool]] = set()


def capability_options() -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in ROLE_CAPABILITIES.items()]


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
    capability_allowed = user_has_capability(capability, user=user, roles=roles)
    if capability_allowed != bool(legacy_allowed):
        _log_capability_mismatch(capability, bool(legacy_allowed), capability_allowed, user=user, context=context)
    if _use_role_capabilities():
        return capability_allowed
    return bool(legacy_allowed)


def seed_default_role_capabilities() -> None:
    if not _has_role_capability_field():
        return
    for role, capabilities in DEFAULT_ROLE_CAPABILITIES.items():
        if not frappe.db.exists("Role", role):
            continue
        current = frappe.db.get_value("Role", role, ROLE_CAPABILITY_FIELD)
        if (current or "").strip():
            continue
        frappe.db.set_value(
            "Role",
            role,
            ROLE_CAPABILITY_FIELD,
            serialize_capabilities(capabilities),
            update_modified=False,
        )


def _use_role_capabilities() -> bool:
    return bool(getattr(getattr(frappe, "conf", None), "orderlift_use_role_capabilities", 0))


def _has_role_capability_field() -> bool:
    try:
        return bool(frappe.get_meta("Role").get_field(ROLE_CAPABILITY_FIELD))
    except Exception:
        return False


def _log_capability_mismatch(capability: str, legacy_allowed: bool, capability_allowed: bool, *, user: str | None, context: str) -> None:
    user = user or getattr(getattr(frappe, "session", None), "user", "") or "Unknown"
    key = (user, capability, legacy_allowed, capability_allowed)
    if key in _logged_capability_mismatches:
        return
    _logged_capability_mismatches.add(key)
    try:
        frappe.log_error(
            "\n".join(
                [
                    f"user={user}",
                    f"capability={capability}",
                    f"legacy_allowed={int(legacy_allowed)}",
                    f"capability_allowed={int(capability_allowed)}",
                    f"context={context or 'unknown'}",
                ]
            ),
            "Orderlift role capability mismatch",
        )
    except Exception:
        pass
