from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.menu_access import MENU_ACCESS_DOCTYPE, sync_menu_access_rules
from orderlift.menu_registry import iter_menu_items


ACCESS_ROLES = {"Orderlift Admin", "System Manager", "Administrator", "Developer"}


@frappe.whitelist()
def get_menu_editor_data() -> dict:
    _require_menu_editor_access()
    sync_menu_access_rules()

    rules = _rule_map()
    sections: list[dict] = []
    current_section = None

    for item in iter_menu_items(include_home=False):
        rule = rules.get(item["key"])
        section_label = item.get("section") or _("Unassigned")
        if not current_section or current_section["label"] != section_label:
            current_section = {"key": item.get("section_key") or section_label, "label": section_label, "items": []}
            sections.append(current_section)
        current_section["items"].append(
            {
                "key": item["key"],
                "default_label": item.get("label") or "",
                "label": (rule.get("label") if rule else None) or item.get("label") or "",
                "menu_order": cint(rule.get("menu_order")) if rule else 0,
                "enabled": 1 if not rule else cint(rule.get("enabled")),
                "section": section_label,
            }
        )

    for section in sections:
        section["items"].sort(key=lambda row: (cint(row.get("menu_order")), row.get("default_label") or ""))
        section["menu_order"] = min((cint(row.get("menu_order")) for row in section["items"]), default=0)
    sections.sort(key=lambda section: (cint(section.get("menu_order")), section.get("label") or ""))

    return {"sections": sections}


@frappe.whitelist()
def save_menu_editor_data(items: str | list[dict]) -> dict:
    _require_menu_editor_access()
    sync_menu_access_rules()
    payload = json.loads(items or "[]") if isinstance(items, str) else items or []
    known_items = {item["key"]: item for item in iter_menu_items(include_home=False)}
    changed = 0

    for row in payload:
        key = (row.get("key") or "").strip()
        if key not in known_items:
            frappe.throw(_("Unknown menu item: {0}").format(key))
        label = (row.get("label") or "").strip()
        if not label:
            frappe.throw(_("Label is required for {0}.").format(known_items[key].get("label") or key))
        if len(label) > 120:
            frappe.throw(_("Label is too long for {0}.").format(known_items[key].get("label") or key))
        order = cint(row.get("menu_order"))
        if order < 1:
            frappe.throw(_("Menu order must be greater than zero for {0}.").format(label))

        doc_name = frappe.db.exists(MENU_ACCESS_DOCTYPE, key)
        if not doc_name:
            continue
        existing = frappe.db.get_value(MENU_ACCESS_DOCTYPE, doc_name, ["label", "menu_order"], as_dict=True) or {}
        if (existing.get("label") or "") == label and cint(existing.get("menu_order")) == order:
            continue
        frappe.db.set_value(MENU_ACCESS_DOCTYPE, doc_name, {"label": label, "menu_order": order})
        changed += 1

    from orderlift.scripts.setup_main_dashboard_sidebar import run as rebuild_main_sidebar

    rebuild_main_sidebar("Main Dashboard")
    frappe.db.commit()
    frappe.clear_cache()
    return {"changed": changed, **get_menu_editor_data()}


def _require_menu_editor_access() -> None:
    if frappe.session.user == "Administrator":
        return
    if not ACCESS_ROLES.intersection(set(frappe.get_roles(frappe.session.user))):
        frappe.throw(_("Only access managers can edit the Main Dashboard menu."), frappe.PermissionError)


def _rule_map() -> dict[str, object]:
    rows = frappe.get_all(
        MENU_ACCESS_DOCTYPE,
        fields=["name", "menu_key", "label", "menu_order", "enabled"],
        limit_page_length=0,
    )
    return {row.menu_key: row for row in rows if row.get("menu_key")}
