from __future__ import annotations

import json
import re

import frappe


SIDEBAR_GROUPS = [
    {
        "section": "CRM & Customers",
        "create_after": None,
        "manage_section": False,
        "links": [
            {"type": "Link", "label": "CRM Dashboard", "link_type": "Page", "link_to": "crm-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Sales",
        "create_after": None,
        "manage_section": False,
        "links": [
            {"type": "Link", "label": "Pricing Dashboard", "link_type": "Page", "link_to": "pricing-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "SAV",
        "create_after": "Agent Rules",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "SAV Dashboard", "link_type": "Page", "link_to": "sav-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "SAV Tickets", "link_type": "DocType", "link_to": "SAV Ticket", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Finance",
        "create_after": None,
        "manage_section": False,
        "links": [
            {"type": "Link", "label": "Finance Dashboard", "link_type": "Page", "link_to": "finance-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "HR",
        "create_after": None,
        "manage_section": False,
        "links": [
            {"type": "Link", "label": "HR Dashboard", "link_type": "Page", "link_to": "hr-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Warehouse & Stock",
        "create_after": None,
        "manage_section": False,
        "links": [
            {"type": "Link", "label": "Stock Dashboard", "link_type": "Page", "link_to": "stock-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "Logistics",
        "create_after": None,
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "Container Planning", "link_type": "Page", "link_to": "logistics-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Forecast Plans", "link_type": "Page", "link_to": "forecast-plans", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Container Profiles", "link_type": "DocType", "link_to": "Container Profile", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "B2B Portal",
        "create_after": "Logistics",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "B2B Portal Dashboard", "link_type": "Page", "link_to": "b2b-portal-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Portal Policies", "link_type": "DocType", "link_to": "Portal Customer Group Policy", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Portal Quote Requests", "link_type": "DocType", "link_to": "Portal Quote Request", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Portal Review Board", "link_type": "Page", "link_to": "portal-review-board", "child": 1, "icon": "dot"},
        ],
    },
    {
        "section": "SIG",
        "create_after": "B2B Portal",
        "manage_section": True,
        "links": [
            {"type": "Link", "label": "SIG Dashboard", "link_type": "Page", "link_to": "sig-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Project Map", "link_type": "Page", "link_to": "project-map", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Mobile QC", "link_type": "Page", "link_to": "sig-qc", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "QC Templates", "link_type": "DocType", "link_to": "QC Checklist Template", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Projects", "link_type": "DocType", "link_to": "Project", "child": 1, "icon": "dot"},
        ],
    },
]

REMOVED_SECTION_LABELS = {"Dashboards"}


@frappe.whitelist()
def run(workspace_name: str = "Main Dashboard"):
    sidebar = frappe.get_doc("Workspace Sidebar", workspace_name)
    current_items = [_sidebar_row(row) for row in sidebar.get("items", [])]
    updated_items = _build_sidebar_items(current_items)

    sidebar.set("items", [])
    for item in updated_items:
        sidebar.append("items", item)
    sidebar.save(ignore_permissions=True)

    _sync_workspace_shortcuts(workspace_name, updated_items)
    frappe.db.commit()
    frappe.clear_cache()
    return {
        "workspace": workspace_name,
        "links": [link["label"] for group in SIDEBAR_GROUPS for link in group["links"]],
    }


def _sidebar_row(row) -> dict:
    return {
        "type": row.type,
        "label": row.label,
        "link_type": getattr(row, "link_type", None),
        "link_to": getattr(row, "link_to", None),
        "url": getattr(row, "url", None),
        "child": row.child,
        "icon": getattr(row, "icon", None),
        "route_options": getattr(row, "route_options", None),
        "navigate_to_tab": getattr(row, "navigate_to_tab", None),
    }


def _build_sidebar_items(items: list[dict]) -> list[dict]:
    managed_labels = {
        group["section"]
        for group in SIDEBAR_GROUPS
        if group["manage_section"]
    }
    managed_labels.update(
        link["label"]
        for group in SIDEBAR_GROUPS
        for link in group["links"]
    )

    rows = [
        row
        for row in items
        if row.get("label") not in managed_labels
        and row.get("label") not in REMOVED_SECTION_LABELS
    ]

    for group in SIDEBAR_GROUPS:
        section = group["section"]
        if group["manage_section"] and not _has_label(rows, section):
            section_row = {
                "type": "Section Break",
                "label": section,
                "child": 0,
                "icon": "dot",
            }
            rows = _insert_after_label(rows, group["create_after"], [section_row])

    for group in SIDEBAR_GROUPS:
        section = group["section"]
        insert_index = _label_index(rows, section)
        if insert_index is None:
            continue

        for offset, link in enumerate(group["links"], start=1):
            rows.insert(insert_index + offset, dict(link))

    return rows


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
    managed_labels = [shortcut["label"] for shortcut in workspace_shortcuts]
    frappe.db.delete(
        "Workspace Shortcut",
        {"parent": workspace_name, "label": ["in", managed_labels]},
    )

    existing_rows = frappe.get_all(
        "Workspace Shortcut",
        filters={"parent": workspace_name},
        fields=["idx"],
        order_by="idx desc",
        limit=1,
    )
    start_idx = existing_rows[0]["idx"] if existing_rows else 0

    for offset, shortcut in enumerate(workspace_shortcuts, start=1):
        doc = frappe.get_doc(
            {
                "doctype": "Workspace Shortcut",
                "name": frappe.generate_hash(length=10),
                "parent": workspace_name,
                "parenttype": "Workspace",
                "parentfield": "shortcuts",
                "idx": start_idx + offset,
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
    content.extend(_build_workspace_content_blocks(sidebar_items))
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
