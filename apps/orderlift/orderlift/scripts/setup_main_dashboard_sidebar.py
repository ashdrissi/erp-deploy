from __future__ import annotations

import frappe


SECTIONS = [
    {
        "label": "Dashboards",
        "links": [
            {"type": "Link", "label": "CRM Dashboard", "link_type": "URL", "link_to": "", "url": "/app/crm-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "SAV Dashboard", "link_type": "URL", "link_to": "", "url": "/app/sav-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Logistics Dashboard", "link_type": "URL", "link_to": "", "url": "/app/logistics-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Stock Dashboard", "link_type": "URL", "link_to": "", "url": "/app/stock-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Pricing Dashboard", "link_type": "URL", "link_to": "", "url": "/app/pricing-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Finance Dashboard", "link_type": "URL", "link_to": "", "url": "/app/finance-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "HR Dashboard", "link_type": "URL", "link_to": "", "url": "/app/hr-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "B2B Portal Dashboard", "link_type": "URL", "link_to": "", "url": "/app/b2b-portal-dashboard", "child": 1, "icon": "dot"},
        ],
    },
    {
        "label": "SIG",
        "links": [
            {"type": "Link", "label": "SIG Dashboard", "link_type": "URL", "link_to": "", "url": "/sig-dashboard", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Project Map", "link_type": "URL", "link_to": "", "url": "/project-map", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Mobile QC", "link_type": "URL", "link_to": "", "url": "/sig-qc", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "QC Templates", "link_type": "DocType", "link_to": "QC Checklist Template", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Projects", "link_type": "DocType", "link_to": "Project", "child": 1, "icon": "dot"},
        ],
    },
    {
        "label": "B2B Portal",
        "links": [
            {"type": "Link", "label": "Portal Policies", "link_type": "DocType", "link_to": "Portal Customer Group Policy", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Portal Quote Requests", "link_type": "DocType", "link_to": "Portal Quote Request", "child": 1, "icon": "dot"},
            {"type": "Link", "label": "Portal Review Board", "link_type": "URL", "link_to": "", "url": "/app/portal-review-board", "child": 1, "icon": "dot"},
        ],
    },
]


@frappe.whitelist()
def run(workspace_name: str = "Main Dashboard"):
    ws = frappe.get_doc("Workspace Sidebar", workspace_name)
    items = []
    for row in ws.get("items", []):
        items.append(
            {
                "type": row.type,
                "label": row.label,
                "link_type": getattr(row, "link_type", None),
                "link_to": getattr(row, "link_to", None),
                "url": getattr(row, "url", None),
                "child": row.child,
                "icon": getattr(row, "icon", None),
            }
        )

    managed_labels = {section["label"] for section in SECTIONS}
    managed_link_labels = {link["label"] for section in SECTIONS for link in section["links"]}
    managed_link_targets = {
        link.get("link_to")
        for section in SECTIONS
        for link in section["links"]
        if link.get("link_to")
    }

    items = [
        row
        for row in items
        if row.get("label") not in managed_labels
        and row.get("label") not in managed_link_labels
        and row.get("link_to") not in managed_link_targets
    ]

    insert_at = len(items)
    settings_index = next((i for i, row in enumerate(items) if row.get("label") == "Settings"), None)
    if settings_index is not None:
        insert_at = settings_index

    next_index = insert_at
    for section in SECTIONS:
        items.insert(next_index, {"type": "Section Break", "label": section["label"], "child": 0, "icon": "dot"})
        next_index += 1
        for link in section["links"]:
            items.insert(next_index, link)
            next_index += 1

    ws.set("items", [])
    for item in items:
        ws.append("items", item)
    ws.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    return {
        "workspace": workspace_name,
        "links": [link["label"] for section in SECTIONS for link in section["links"]],
    }
