from __future__ import annotations

import json

import frappe

from orderlift.scripts.setup_main_dashboard_sidebar import (
    _build_workspace_content_blocks,
    _build_workspace_shortcuts,
    _sidebar_row,
)


SECTION_WORKSPACE_SPECS = [
    {"section_label": "My Work", "workspace_name": "My Work", "module": "Custom", "icon": "user-round"},
    {"section_label": "Administration", "workspace_name": "Administration", "module": "Core", "icon": "users"},
    {"section_label": "CRM & Customers", "workspace_name": "CRM & Customers", "template_workspace": "CRM", "icon": "book-user"},
    {"section_label": "Sales", "workspace_name": "Sales", "template_workspace": "Selling", "icon": "shopping-cart"},
    {"section_label": "Policies & Configs", "workspace_name": "Policies & Configs", "module": "Custom", "icon": "shield"},
    {"section_label": "SAV", "workspace_name": "SAV", "module": "Custom", "icon": "life-buoy"},
    {"section_label": "Items & Price Lists", "workspace_name": "Items & Price Lists", "module": "Custom", "icon": "box"},
    {"section_label": "Finance", "workspace_name": "Finance", "template_workspace": "Invoicing", "icon": "chart-no-axes-combined"},
    {"section_label": "Purchasing", "workspace_name": "Purchasing", "template_workspace": "Buying", "icon": "shopping-basket"},
    {"section_label": "HR", "workspace_name": "HR", "module": "HR", "icon": "file-user"},
    {"section_label": "Manufacturing", "workspace_name": "Manufacturing", "template_workspace": "Manufacturing", "icon": "drill", "reuse_existing": True},
    {"section_label": "Gestion de Projets", "workspace_name": "Gestion de Projets", "template_workspace": "Projects", "icon": "briefcase-business"},
    {"section_label": "Warehouse & Stock", "workspace_name": "Warehouse & Stock", "template_workspace": "Stock", "icon": "package"},
    {"section_label": "Logistics", "workspace_name": "Logistics", "module": "Custom", "icon": "truck"},
    {"section_label": "B2B Portal", "workspace_name": "B2B Portal", "module": "Custom", "icon": "globe"},
    {"section_label": "SIG", "workspace_name": "SIG", "module": "Custom", "icon": "map"},
]


@frappe.whitelist()
def run(
    workspace_name: str = "CRM-Orderlift",
    section_label: str = "CRM & Customers",
    source_sidebar: str = "Main Dashboard",
    template_workspace: str | None = None,
    module: str | None = None,
    icon: str | None = None,
):
    spec = {
        "workspace_name": workspace_name,
        "section_label": section_label,
        "source_sidebar": source_sidebar,
        "template_workspace": template_workspace,
        "module": module,
        "icon": icon,
    }
    return _sync_workspace(spec)


@frappe.whitelist()
def sync_all(source_sidebar: str = "Main Dashboard"):
    results = []
    for spec in SECTION_WORKSPACE_SPECS:
        payload = {**spec, "source_sidebar": source_sidebar}
        results.append(_sync_workspace(payload))

    frappe.db.commit()
    frappe.clear_cache()
    return {"workspaces": results}


def _sync_workspace(spec: dict) -> dict:
    source_sidebar = spec.get("source_sidebar") or "Main Dashboard"
    section_label = spec["section_label"]
    workspace_name = spec.get("workspace_name") or section_label
    reuse_existing = bool(spec.get("reuse_existing"))

    section_rows = _extract_section_rows(source_sidebar, section_label)
    if not section_rows:
        frappe.throw(f"Could not find section '{section_label}' in sidebar '{source_sidebar}'.")

    section_icon = section_rows[0].get("icon") if section_rows else None
    module = spec.get("module")
    icon = spec.get("icon") or section_icon
    template_workspace = spec.get("template_workspace")

    if reuse_existing and frappe.db.exists("Workspace", workspace_name):
        workspace = frappe.get_doc("Workspace", workspace_name)
        return {
            "workspace": workspace.name,
            "section_label": section_label,
            "template_workspace": template_workspace,
            "module": workspace.module,
            "icon": workspace.icon,
            "route": f"/desk/dashboard-view/{workspace.name}",
            "shortcuts": [],
            "reused": True,
        }

    workspace = _ensure_workspace(workspace_name, template_workspace, module=module, icon=icon)
    _sync_workspace_sidebar(workspace.name, section_rows, icon=workspace.icon)
    _sync_workspace_shortcuts(workspace.name, section_rows)
    _sync_workspace_content(workspace, section_rows, template_workspace)

    return {
        "workspace": workspace.name,
        "section_label": section_label,
        "template_workspace": template_workspace,
        "module": workspace.module,
        "icon": workspace.icon,
        "route": f"/desk/dashboard-view/{workspace.name}",
        "shortcuts": [shortcut["label"] for shortcut in _build_workspace_shortcuts(section_rows)],
        "reused": False,
    }


def _extract_section_rows(source_sidebar: str, section_label: str) -> list[dict]:
    sidebar = frappe.get_doc("Workspace Sidebar", source_sidebar)
    rows = [_sidebar_row(row) for row in sidebar.get("items", [])]

    collecting = False
    section_rows: list[dict] = []
    for row in rows:
        row_type = row.get("type")
        label = row.get("label")

        if not collecting:
            if row_type == "Section Break" and label == section_label:
                collecting = True
                section_rows.append(row)
            continue

        if row_type in {"Section Break", "Sidebar Item Group"} and label != section_label:
            break

        section_rows.append(row)

    return section_rows


def _ensure_workspace(
    workspace_name: str,
    template_workspace: str | None,
    *,
    module: str | None = None,
    icon: str | None = None,
):
    template = frappe.get_doc("Workspace", template_workspace) if template_workspace and frappe.db.exists("Workspace", template_workspace) else None

    if frappe.db.exists("Workspace", workspace_name):
        workspace = frappe.get_doc("Workspace", workspace_name)
    else:
        workspace = frappe.new_doc("Workspace")
        workspace.name = workspace_name

    workspace.title = workspace_name
    workspace.label = workspace_name
    workspace.module = module or (template.module if template else "Custom")
    workspace.icon = icon or (template.icon if template else "folder")
    workspace.public = 1
    workspace.is_hidden = 0
    workspace.parent_page = ""
    workspace.content = workspace.content or "[]"
    workspace.save(ignore_permissions=True)
    return workspace


def _sync_workspace_sidebar(workspace_name: str, section_rows: list[dict], *, icon: str | None = None) -> None:
    if frappe.db.exists("Workspace Sidebar", workspace_name):
        sidebar = frappe.get_doc("Workspace Sidebar", workspace_name)
    else:
        sidebar = frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "name": workspace_name,
                "title": workspace_name,
                "header_icon": icon or "folder",
                "module": "",
                "standard": 0,
                "app": "orderlift",
            }
        )
        sidebar.insert(ignore_permissions=True)
        sidebar = frappe.get_doc("Workspace Sidebar", workspace_name)

    sidebar.title = workspace_name
    sidebar.header_icon = icon or sidebar.header_icon or "folder"

    sidebar_rows = [_sidebar_row(row) for row in sidebar.get("items", [])]
    section_links = [row for row in section_rows if row.get("type") == "Link"]
    home_row = {
        "type": "Link",
        "label": "Home",
        "link_type": "Workspace",
        "link_to": workspace_name,
        "child": 0,
        "icon": sidebar.header_icon or "folder",
    }

    updated_rows = [home_row]
    seen = {"Home"}
    for row in section_links:
        label = row.get("label")
        if not label or label in seen:
            continue
        updated_rows.append({**row, "child": 1})
        seen.add(label)

    # Preserve manual non-home rows that are not duplicates.
    for row in sidebar_rows:
        label = row.get("label")
        if not label or label in seen:
            continue
        if row.get("type") != "Link":
            continue
        updated_rows.append(row)
        seen.add(label)

    sidebar.set("items", [])
    for idx, row in enumerate(updated_rows, start=1):
        row["idx"] = idx
        sidebar.append("items", row)
    sidebar.save(ignore_permissions=True)


def _sync_workspace_shortcuts(workspace_name: str, section_rows: list[dict]) -> None:
    frappe.db.delete("Workspace Shortcut", {"parent": workspace_name})

    for idx, shortcut in enumerate(_build_workspace_shortcuts(section_rows), start=1):
        doc = frappe.get_doc(
            {
                "doctype": "Workspace Shortcut",
                "name": frappe.generate_hash(length=10),
                "parent": workspace_name,
                "parenttype": "Workspace",
                "parentfield": "shortcuts",
                "idx": idx,
                "label": shortcut["label"],
                "type": shortcut["type"],
                "link_to": shortcut.get("link_to"),
                "url": shortcut.get("url"),
            }
        )
        doc.db_insert()


def _sync_workspace_content(workspace, section_rows: list[dict], template_workspace: str | None) -> None:
    generated_blocks = _build_workspace_content_blocks(section_rows)
    prefix_blocks, suffix_blocks = _split_template_content(template_workspace)
    workspace.content = json.dumps(prefix_blocks + generated_blocks + suffix_blocks)
    workspace.save(ignore_permissions=True)


def _split_template_content(template_workspace: str | None) -> tuple[list[dict], list[dict]]:
    if not template_workspace or not frappe.db.exists("Workspace", template_workspace):
        return [], []

    template_content = frappe.db.get_value("Workspace", template_workspace, "content") or "[]"
    try:
        blocks = json.loads(template_content)
    except Exception:
        return [], []

    prefix: list[dict] = []
    suffix: list[dict] = []
    skipping_shortcuts = False
    consumed_shortcuts = False

    for block in blocks:
        block_type = block.get("type")
        header_text = str((block.get("data") or {}).get("text") or "")

        if block_type == "header" and "Your Shortcuts" in header_text:
            skipping_shortcuts = True
            consumed_shortcuts = True
            continue

        if skipping_shortcuts:
            if block_type == "header":
                skipping_shortcuts = False
                suffix.append(block)
            elif block_type != "shortcut":
                continue
            continue

        if consumed_shortcuts:
            suffix.append(block)
        else:
            prefix.append(block)

    return prefix, suffix
