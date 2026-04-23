from __future__ import annotations

import json

import frappe


TARGET_LABEL = "CRM Dashboard"
TARGET_LINK_TYPE = "Page"
TARGET_LINK_TO = "crm-dashboard"
TARGET_ROUTE_OPTIONS = json.dumps({"sidebar": "CRM"})


@frappe.whitelist()
def run(workspace_name: str = "CRM"):
    sidebar = frappe.get_doc("Workspace Sidebar", workspace_name)

    target_row = None
    insert_after_idx = 0
    duplicate_rows = []

    for row in sidebar.get("items", []):
        if row.label == "Home":
            insert_after_idx = row.idx or 0

        if row.label == TARGET_LABEL:
            if target_row is None:
                target_row = row
            else:
                duplicate_rows.append(row)

    for row in duplicate_rows:
        sidebar.remove(row)

    if target_row is None:
        target_row = sidebar.append(
            "items",
            {
                "type": "Link",
                "label": TARGET_LABEL,
                "child": 1,
                "icon": "dot",
            },
        )
        target_row.idx = (insert_after_idx or 0) + 1

    target_row.type = "Link"
    target_row.link_type = TARGET_LINK_TYPE
    target_row.link_to = TARGET_LINK_TO
    target_row.url = None
    target_row.route_options = TARGET_ROUTE_OPTIONS
    target_row.child = 1
    target_row.icon = "dot"

    _normalize_idx(sidebar)
    sidebar.save(ignore_permissions=True)

    frappe.db.commit()
    frappe.clear_cache()
    return {
        "workspace": workspace_name,
        "label": TARGET_LABEL,
        "link_type": TARGET_LINK_TYPE,
        "link_to": TARGET_LINK_TO,
        "route_options": TARGET_ROUTE_OPTIONS,
    }


def _normalize_idx(sidebar) -> None:
    ordered = sorted(list(sidebar.get("items", [])), key=lambda row: row.idx or 0)
    for idx, row in enumerate(ordered, start=1):
        row.idx = idx
