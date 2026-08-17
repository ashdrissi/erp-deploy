from __future__ import annotations

import frappe

from orderlift.menu_access import LEGACY_PREFERRED_COMPANY_DEFAULT_KEY


def execute():
    _backfill_preferred_companies()
    _retire_native_company_session_default()


def _backfill_preferred_companies() -> None:
    rows = frappe.get_all(
        "DefaultValue",
        filters={"defkey": ["in", ["Company", "company"]]},
        fields=["parent", "defkey", "defvalue", "modified"],
        order_by="parent asc, modified desc",
        limit_page_length=0,
    )
    preferred_by_user = {}
    for row in rows:
        user = (row.get("parent") or "").strip()
        company = (row.get("defvalue") or "").strip()
        if not user or not company or not frappe.db.exists("User", user) or not frappe.db.exists("Company", company):
            continue
        current = preferred_by_user.get(user)
        is_primary_key = row.get("defkey") == "Company"
        if current is None or (is_primary_key and not current["is_primary_key"]):
            preferred_by_user[user] = {"company": company, "is_primary_key": is_primary_key}

    for user, candidate in preferred_by_user.items():
        if frappe.db.exists("DefaultValue", {"parent": user, "defkey": LEGACY_PREFERRED_COMPANY_DEFAULT_KEY}):
            continue
        frappe.defaults.set_user_default(LEGACY_PREFERRED_COMPANY_DEFAULT_KEY, candidate["company"], user=user)


def _retire_native_company_session_default() -> None:
    if not frappe.db.exists("DocType", "Session Default Settings"):
        return
    settings = frappe.get_single("Session Default Settings")
    retained = [row for row in settings.get("session_defaults") or [] if row.get("ref_doctype") != "Company"]
    if len(retained) == len(settings.get("session_defaults") or []):
        return
    settings.set("session_defaults", retained)
    settings.flags.ignore_permissions = True
    settings.save()
