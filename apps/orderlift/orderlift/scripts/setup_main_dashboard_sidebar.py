from __future__ import annotations

import json
import re

import frappe

from orderlift.menu_access import build_central_sidebar_rows, sync_menu_access_rules
from orderlift.menu_registry import get_menu_sections


SIDEBAR_GROUPS = [
    {
        "section": "My Work",
        "create_after": "Dashboard",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "Administration",
        "create_after": "My Work",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Status Control", "link_type": "Page", "link_to": "status-control", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Access Command Center", "link_type": "Page", "link_to": "access-command-center", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "CRM & Customers",
        "create_after": "Administration",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "CRM Dashboard", "link_type": "Page", "link_to": "crm-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Projects List", "link_type": "DocType", "link_to": "Project", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Campaign Manager", "link_type": "Page", "link_to": "campaign-manager", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Campaign Builder", "link_type": "Page", "link_to": "campaign-editor", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Opportunity Pipeline", "link_type": "Page", "link_to": "opportunity-pipeline", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Sales",
        "create_after": "CRM & Customers",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Pricing Sheets", "link_type": "Page", "link_to": "pricing-sheet-manager", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Policies & Configs",
        "create_after": "Sales",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "SAV",
        "create_after": "Policies & Configs",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "Items & Price Lists",
        "create_after": "SAV",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Dimensioning Sets", "link_type": "Page", "link_to": "dimensioning-set-manager", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Finance",
        "create_after": "Items & Price Lists",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Sale Financial Dashboard", "link_type": "Page", "link_to": "sale-financial-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Purchasing",
        "create_after": "Finance",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "HR",
        "create_after": "Purchasing",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "Manufacturing",
        "create_after": "HR",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "Gestion de Projets",
        "create_after": "Manufacturing",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Project Pipeline", "link_type": "Page", "link_to": "project-pipeline", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Sales Order Pipeline", "link_type": "Page", "link_to": "sales-order-pipeline", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Warehouse & Stock",
        "create_after": "Gestion de Projets",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "Logistics",
        "create_after": "Warehouse & Stock",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Logistics Pipeline", "link_type": "Page", "link_to": "logistics-pipeline", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "B2B Portal",
        "create_after": "Logistics",
        "manage_section": True,
        "links": [],
    },
    {
        "section": "SIG",
        "create_after": "B2B Portal",
        "manage_section": True,
        "links": [],
    },
]

SECTION_ICONS = {
    "My Work": "user-round",
    "Administration": "users",
    "CRM & Customers": "book-user",
    "Sales": "shopping-cart",
    "Policies & Configs": "shield",
    "SAV": "life-buoy",
    "Items & Price Lists": "box",
    "Finance": "chart-no-axes-combined",
    "Purchasing": "shopping-basket",
    "HR": "file-user",
    "Manufacturing": "drill",
    "Gestion de Projets": "briefcase-business",
    "Warehouse & Stock": "package",
    "Logistics": "truck",
    "B2B Portal": "globe",
    "SIG": "map",
}

# Centralized navigation: this keeps older helper functions/tests pointed at the
# same registry that now builds the live Main Dashboard sidebar.
_CENTRAL_MENU_SECTIONS = get_menu_sections()
SIDEBAR_GROUPS = [
    {
        "section": section["label"],
        "create_after": None,
        "manage_section": True,
        "links": [
            {
                "type": "Link",
                "label": link["label"],
                "link_type": link.get("link_type") or "DocType",
                "link_to": link.get("link_to"),
                "url": link.get("url"),
                "child": 1,
                "icon": link.get("icon") or "dot",
            }
            for link in section.get("links", [])
        ],
    }
    for section in _CENTRAL_MENU_SECTIONS
]
SECTION_ICONS = {section["label"]: section.get("icon") or "folder" for section in _CENTRAL_MENU_SECTIONS}

REMOVED_SECTION_LABELS = {"Dashboards"}
REMOVED_LINK_LABELS = {"Container Load Plan", "Dimensioning Set Builder", "Operations Pipeline", "Forecast Load Plan", "Forecast Plans", "Pricing Sheet"}
REMOVED_LINK_TARGETS = {
    "Container Load Plan",
    "Dimensioning Set",
    "dimensioning-set-builder",
    "operations-pipeline",
    "Forecast Load Plan",
    "forecast-load-plan",
    "Pricing Sheet",
    "pricing-sheet",
}
SECTION_REMOVED_LINK_LABELS = {}
SECTION_REMOVED_LINK_TARGETS = {}
HIDDEN_DESKTOP_ICON_APPS = {"erpnext"}


@frappe.whitelist()
def run(workspace_name: str = "Main Dashboard"):
    frappe.only_for(["System Manager", "Orderlift Admin"])
    sidebar = frappe.get_doc("Workspace Sidebar", workspace_name)
    updated_items = [
        row
        for row in build_central_sidebar_rows()
        if row.get("type") != "Link" or _is_valid_sidebar_link(row)
    ]

    frappe.db.delete("Workspace Sidebar Item", {"parent": workspace_name})
    sidebar.set("items", [])
    for item in updated_items:
        sidebar.append("items", item)
    sidebar.save(ignore_permissions=True)

    _sync_workspace_shortcuts(workspace_name, updated_items)
    sync_menu_access_rules()
    removed_sidebars = _delete_secondary_orderlift_sidebars(workspace_name)
    hidden_desktop_icons = _hide_native_workspace_desktop_icons()
    frappe.db.commit()
    frappe.clear_cache()
    return {
        "workspace": workspace_name,
        "links": [link["label"] for group in SIDEBAR_GROUPS for link in group["links"]],
        "removed_sidebars": removed_sidebars,
        "hidden_desktop_icons": hidden_desktop_icons,
    }


def _hide_native_workspace_desktop_icons() -> list[str]:
    """Keep Desk's workspace switcher focused on the custom Main Dashboard."""
    if not frappe.db.table_exists("Desktop Icon"):
        return []

    icons = frappe.get_all(
        "Desktop Icon",
        filters={"app": ["in", sorted(HIDDEN_DESKTOP_ICON_APPS)], "hidden": 0},
        fields=["name"],
        limit_page_length=0,
    )
    hidden = [icon.name for icon in icons]
    for icon_name in hidden:
        frappe.db.set_value("Desktop Icon", icon_name, "hidden", 1, update_modified=False)
    if hidden:
        frappe.cache.delete_key("desktop_icons")
        frappe.cache.delete_key("bootinfo")
    return hidden


def _delete_secondary_orderlift_sidebars(workspace_name: str = "Main Dashboard") -> list[str]:
    """Remove section-specific sidebars so Desk cannot switch away from Main Dashboard."""
    section_labels = {section["label"] for section in get_menu_sections() if section.get("label") != workspace_name}
    removed = []
    for sidebar_name in sorted(section_labels):
        if not frappe.db.exists("Workspace Sidebar", sidebar_name):
            continue
        app, standard = frappe.db.get_value("Workspace Sidebar", sidebar_name, ["app", "standard"])
        if app != "orderlift" or int(standard or 0):
            continue
        frappe.delete_doc("Workspace Sidebar", sidebar_name, ignore_permissions=True, force=True)
        removed.append(sidebar_name)
    return removed


def _ensure_static_workspace_targets() -> None:
    for group in SIDEBAR_GROUPS:
        for link in group["links"]:
            if link.get("link_type") != "Workspace" or not link.get("link_to"):
                continue
            if frappe.db.exists("Workspace", link["link_to"]):
                continue
            workspace = frappe.new_doc("Workspace")
            workspace.name = link["link_to"]
            workspace.title = link["link_to"]
            workspace.label = link["link_to"]
            workspace.module = "Custom"
            workspace.icon = SECTION_ICONS.get(link["link_to"], "folder")
            workspace.public = 1
            workspace.is_hidden = 0
            workspace.parent_page = ""
            workspace.content = "[]"
            workspace.insert(ignore_permissions=True)


def _sidebar_row(row) -> dict:
    return {
        "type": row.type,
        "label": row.label,
        "link_type": getattr(row, "link_type", None),
        "link_to": getattr(row, "link_to", None),
        "url": getattr(row, "url", None),
        "child": row.child,
        "icon": getattr(row, "icon", None),
        "indent": getattr(row, "indent", None),
        "collapsible": getattr(row, "collapsible", None),
        "keep_closed": getattr(row, "keep_closed", None),
        "route_options": getattr(row, "route_options", None),
        "navigate_to_tab": getattr(row, "navigate_to_tab", None),
    }


def _build_sidebar_items(items: list[dict], managed_section_children: dict[str, list[dict]] | None = None) -> list[dict]:
    return build_central_sidebar_rows()


def _load_managed_section_children() -> dict[str, list[dict]]:
    # Section-specific sidebars are intentionally no longer sources of truth.
    # Main Dashboard now comes only from orderlift.menu_registry.
    return {}


def _is_valid_sidebar_link(row: dict) -> bool:
    link_type = row.get("link_type")
    link_to = row.get("link_to")
    url = row.get("url")

    if url:
        return True
    if not link_type or not link_to or not getattr(frappe, "db", None):
        return False

    target_doctype = {
        "Dashboard": "Dashboard",
        "DocType": "DocType",
        "Page": "Page",
        "Report": "Report",
        "Workspace": "Workspace",
    }.get(link_type)
    if not target_doctype:
        return False

    return bool(frappe.db.exists(target_doctype, link_to))


def _has_label(rows: list[dict], label: str) -> bool:
    return any(row.get("label") == label for row in rows)


def _label_index(rows: list[dict], label: str) -> int | None:
    for index, row in enumerate(rows):
        if row.get("label") == label:
            return index
    return None


def _insert_after_label(rows: list[dict], after_label: str | None, new_rows: list[dict]) -> list[dict]:
    if not after_label:
        return rows + list(new_rows)

    for index, row in enumerate(rows):
        if row.get("label") == after_label:
            return rows[: index + 1] + list(new_rows) + rows[index + 1 :]

    return rows + list(new_rows)


def _sync_workspace_shortcuts(workspace_name: str, sidebar_items: list[dict]) -> None:
    workspace_shortcuts = _build_workspace_shortcuts(sidebar_items)
    frappe.db.delete("Workspace Shortcut", {"parent": workspace_name})

    for offset, shortcut in enumerate(workspace_shortcuts, start=1):
        doc = frappe.get_doc(
            {
                "doctype": "Workspace Shortcut",
                "name": frappe.generate_hash(length=10),
                "parent": workspace_name,
                "parenttype": "Workspace",
                "parentfield": "shortcuts",
                "idx": offset,
                "label": shortcut["label"],
                "type": shortcut["type"],
                "link_to": shortcut.get("link_to"),
                "url": shortcut.get("url"),
            }
        )
        doc.db_insert()

    workspace_content = frappe.db.get_value("Workspace", workspace_name, "content") or "[]"
    try:
        content = json.loads(workspace_content)
    except Exception:
        content = []

    content = [
        block
        for block in content
        if not str(block.get("id", "")).startswith("main_dashboard_shortcuts_")
        and not str(block.get("id", "")).startswith("sig_main_dashboard_")
        and not str(block.get("id", "")).startswith("logistics_main_dashboard_")
    ]
    # Main Dashboard shortcuts cannot be safely role-filtered as static Workspace
    # content, so the role-aware sidebar is the canonical navigation surface.
    frappe.db.set_value("Workspace", workspace_name, "content", json.dumps(content), update_modified=False)


def _build_workspace_shortcuts(sidebar_items: list[dict]) -> list[dict]:
    shortcuts = []
    seen_labels = set()

    for row in sidebar_items:
        if row.get("type") != "Link":
            continue

        shortcut = _shortcut_from_sidebar_row(row)
        if not shortcut or shortcut["label"] in seen_labels:
            continue

        seen_labels.add(shortcut["label"])
        shortcuts.append(shortcut)

    return shortcuts


def _is_removed_link(row: dict) -> bool:
    return row.get("label") in REMOVED_LINK_LABELS or row.get("link_to") in REMOVED_LINK_TARGETS


def _is_removed_section_link(section: str, row: dict) -> bool:
    return row.get("label") in SECTION_REMOVED_LINK_LABELS.get(section, set()) or row.get("link_to") in SECTION_REMOVED_LINK_TARGETS.get(section, set())


def _delete_workspace_shortcuts(
    workspace_name: str,
    *,
    labels: list[str] | None = None,
    link_targets: list[str] | None = None,
) -> None:
    filters = {"parent": workspace_name}
    if labels:
        filters["label"] = ["in", labels]
    if link_targets:
        filters["link_to"] = ["in", link_targets]

    names = frappe.get_all("Workspace Shortcut", filters=filters, pluck="name")
    if not names:
        return

    frappe.db.delete("Workspace Shortcut", {"name": ["in", names]})


def _shortcut_from_sidebar_row(row: dict) -> dict | None:
    link_type = row.get("link_type")
    url = row.get("url")
    link_to = row.get("link_to")

    if link_type and link_to:
        return {
            "label": row["label"],
            "type": link_type,
            "link_to": link_to,
        }

    if url:
        return {
            "label": row["label"],
            "type": "URL",
            "url": url,
        }

    return None


def _build_workspace_content_blocks(sidebar_items: list[dict]) -> list[dict]:
    blocks = []
    section_label = "Overview"
    section_shortcuts = []
    section_index = 0

    def flush_section() -> None:
        nonlocal section_shortcuts, section_index
        if not section_shortcuts:
            return

        section_slug = _slugify(section_label or f"section-{section_index}")
        blocks.append(
            {
                "id": f"main_dashboard_shortcuts_{section_slug}_header",
                "type": "header",
                "data": {"text": f'<span class="h4"><b>{section_label}</b></span>', "col": 12},
            }
        )
        blocks.append(
            {
                "id": f"main_dashboard_shortcuts_{section_slug}_spacer",
                "type": "spacer",
                "data": {"col": 12},
            }
        )

        for shortcut_index, shortcut_name in enumerate(section_shortcuts, start=1):
            blocks.append(
                {
                    "id": f"main_dashboard_shortcuts_{section_slug}_{shortcut_index}",
                    "type": "shortcut",
                    "data": {"shortcut_name": shortcut_name, "col": 4},
                }
            )

        section_shortcuts = []
        section_index += 1

    for row in sidebar_items:
        row_type = row.get("type")

        if row_type == "Section Break":
            flush_section()
            section_label = row.get("label") or "Overview"
            continue

        if row_type != "Link":
            continue

        shortcut = _shortcut_from_sidebar_row(row)
        if shortcut:
            section_shortcuts.append(shortcut["label"])

    flush_section()
    return blocks


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "section").strip().lower()).strip("_") or "section"
