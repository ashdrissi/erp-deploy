from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


STATUS_BEHAVIOR_CUSTOM_FIELDS = {
    "Sales Stage": [
        {
            "fieldname": "custom_auto_collapse",
            "fieldtype": "Check",
            "label": "Collapse By Default",
            "insert_after": "custom_todo_priority",
        },
        {
            "fieldname": "custom_auto_close_opportunity",
            "fieldtype": "Check",
            "label": "Auto Close Opportunity",
            "insert_after": "custom_auto_collapse",
            "description": "When an Opportunity is moved to this status, set the native Opportunity status to Closed.",
        },
    ],
    "Project Status": [
        {
            "fieldname": "custom_auto_collapse",
            "fieldtype": "Check",
            "label": "Collapse By Default",
            "insert_after": "todo_priority",
        },
    ],
    "Orderlift Order Status": [
        {
            "fieldname": "custom_auto_collapse",
            "fieldtype": "Check",
            "label": "Collapse By Default",
            "insert_after": "todo_priority",
        },
    ],
    "Logistics Pipeline Status": [
        {
            "fieldname": "custom_auto_collapse",
            "fieldtype": "Check",
            "label": "Collapse By Default",
            "insert_after": "todo_priority",
        },
    ],
}


def execute():
    create_custom_fields(STATUS_BEHAVIOR_CUSTOM_FIELDS, update=True)
