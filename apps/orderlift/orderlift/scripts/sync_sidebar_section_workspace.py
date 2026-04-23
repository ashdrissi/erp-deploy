from __future__ import annotations

import json

import frappe

from orderlift.scripts.setup_main_dashboard_sidebar import (
    _build_workspace_content_blocks,
    _build_workspace_shortcuts,
    _shortcut_from_sidebar_row,
    _sidebar_row,
)


@frappe.whitelist()
def run(
    workspace_name: str = "CRM-Orderlift",
    section_label: str = "CRM & Customers",
    source_sidebar: str = "Main Dashboard",
    template_workspace: str = "CRM",
):
    section_rows = _extract_section_rows(source_sidebar, section_label)
    if not section_rows:
        frappe.throw(f"Could not find section '{section_label}' in sidebar '{source_sidebar}'.")

    workspace = _ensure_workspace(workspace_name, template_workspace)
    _sync_workspace_shortcuts(workspace.name, section_rows)
    _sync_workspace_content(workspace, section_rows, template_workspace)

    frappe.db.commit()
    frappe.clear_cache()
    return {
        "workspace": workspace.name,
        "template_workspace": template_workspace,
        "section_label": section_label,
        "shortcuts": [shortcut["label"] for shortcut in _build_workspace_shortcuts(section_rows)],
        "route": f"/desk/dashboard-view/{workspace.name}",
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


def _ensure_workspace(workspace_name: str, template_workspace: str):
    template = frappe.get_doc("Workspace", template_workspace)
    if frappe.db.exists("Workspace", workspace_name):
        workspace = frappe.get_doc("Workspace", workspace_name)
    else:
        workspace = frappe.new_doc("Workspace")
        workspace.name = workspace_name

    workspace.title = workspace_name
    workspace.label = workspace_name
    workspace.module = template.module or "CRM"
    workspace.icon = template.icon or "crm"
    workspace.public = 1
    workspace.is_hidden = 0
    workspace.parent_page = ""
    workspace.content = workspace.content or "[]"
    workspace.save(ignore_permissions=True)
    return workspace


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


def _sync_workspace_content(workspace, section_rows: list[dict], template_workspace: str) -> None:
    generated_blocks = _build_workspace_content_blocks(section_rows)
    prefix_blocks, suffix_blocks = _split_template_content(template_workspace)
    workspace.content = json.dumps(prefix_blocks + generated_blocks + suffix_blocks)
    workspace.save(ignore_permissions=True)


def _split_template_content(template_workspace: str) -> tuple[list[dict], list[dict]]:
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
