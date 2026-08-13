from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


STATE_PENDING = "Pending Approval"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"
STATE_SUBMITTED = "Submitted"

ACTION_APPROVE = "Approve"
ACTION_REJECT = "Reject"
ACTION_REOPEN = "Reopen"
ACTION_SUBMIT = "Submit"

APPROVER_ROLES = ("Orderlift Admin", "System Manager")

WORKFLOW_DEFINITIONS = (
    {
        "name": "Orderlift Purchase Order Approval",
        "document_type": "Purchase Order",
        "field_insert_after": "status",
        "editor_roles": ("Purchase User", "Purchase Manager", *APPROVER_ROLES),
    },
    {
        "name": "Orderlift Sales Order Approval",
        "document_type": "Sales Order",
        "field_insert_after": "status",
        "editor_roles": ("Sales User", "Sales Manager", *APPROVER_ROLES),
    },
    {
        "name": "Orderlift Quotation Approval",
        "document_type": "Quotation",
        "field_insert_after": "status",
        "editor_roles": ("Sales User", "Sales Manager", *APPROVER_ROLES),
    },
)

WORKFLOW_STATES = (
    {"name": STATE_PENDING, "style": "Warning"},
    {"name": STATE_APPROVED, "style": "Success"},
    {"name": STATE_REJECTED, "style": "Danger"},
    {"name": STATE_SUBMITTED, "style": "Success"},
)

WORKFLOW_ACTIONS = (ACTION_APPROVE, ACTION_REJECT, ACTION_REOPEN, ACTION_SUBMIT)


@frappe.whitelist()
def run(dry_run: int = 1, force: int = 0) -> dict:
    """Create inactive approval workflow drafts for purchase and sales documents.

    This is intentionally explicit and not called from after_migrate. Existing
    Orderlift workflow records are preserved unless force=1 is passed.
    """
    frappe.only_for(["System Manager", "Orderlift Admin"])
    dry_run = cint(dry_run)
    force = cint(force)
    result = {
        "dry_run": bool(dry_run),
        "force": bool(force),
        "is_active": 0,
        "states": [],
        "actions": [],
        "fields": [],
        "workflows": [],
        "skipped": [],
        "missing_roles": [],
    }

    _ensure_workflow_states(result, dry_run=dry_run)
    _ensure_workflow_actions(result, dry_run=dry_run)
    _ensure_workflow_state_fields(result, dry_run=dry_run)

    existing_roles = set(frappe.get_all("Role", pluck="name", limit_page_length=0))
    for definition in WORKFLOW_DEFINITIONS:
        result["missing_roles"].extend(
            _missing_roles(definition["editor_roles"], existing_roles)
        )
        _ensure_workflow(definition, result, dry_run=dry_run, force=force)

    result["missing_roles"] = sorted(set(result["missing_roles"]))
    if not dry_run:
        frappe.clear_cache()
        frappe.db.commit()
    return result


def _ensure_workflow_states(result: dict, *, dry_run: int) -> None:
    for row in WORKFLOW_STATES:
        name = row["name"]
        if frappe.db.exists("Workflow State", name):
            result["states"].append({"name": name, "action": "exists"})
            continue
        result["states"].append({"name": name, "action": "create"})
        if dry_run:
            continue
        doc = frappe.new_doc("Workflow State")
        doc.workflow_state_name = name
        doc.style = row["style"]
        doc.insert(ignore_permissions=True)


def _ensure_workflow_actions(result: dict, *, dry_run: int) -> None:
    for action in WORKFLOW_ACTIONS:
        if frappe.db.exists("Workflow Action Master", action):
            result["actions"].append({"name": action, "action": "exists"})
            continue
        result["actions"].append({"name": action, "action": "create"})
        if dry_run:
            continue
        doc = frappe.new_doc("Workflow Action Master")
        doc.workflow_action_name = action
        doc.insert(ignore_permissions=True)


def _ensure_workflow_state_fields(result: dict, *, dry_run: int) -> None:
    fields = {}
    for definition in WORKFLOW_DEFINITIONS:
        doctype = definition["document_type"]
        if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": "workflow_state"}):
            result["fields"].append({"doctype": doctype, "fieldname": "workflow_state", "action": "exists"})
            continue
        result["fields"].append({"doctype": doctype, "fieldname": "workflow_state", "action": "create"})
        fields.setdefault(doctype, []).append(
            {
                "fieldname": "workflow_state",
                "label": "Workflow State",
                "fieldtype": "Link",
                "options": "Workflow State",
                "insert_after": definition["field_insert_after"],
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1,
            }
        )
    if fields and not dry_run:
        create_custom_fields(fields, update=False, ignore_validate=True)


def _ensure_workflow(definition: dict, result: dict, *, dry_run: int, force: int) -> None:
    workflow_name = definition["name"]
    existing = frappe.db.exists("Workflow", workflow_name)
    if existing and not force:
        result["workflows"].append(
            {
                "name": workflow_name,
                "document_type": definition["document_type"],
                "action": "exists_skipped",
                "is_active": 0,
            }
        )
        return

    action = "update" if existing else "create"
    result["workflows"].append(
        {
            "name": workflow_name,
            "document_type": definition["document_type"],
            "action": action,
            "is_active": 0,
        }
    )
    if dry_run:
        return

    doc = frappe.get_doc("Workflow", workflow_name) if existing else frappe.new_doc("Workflow")
    doc.workflow_name = workflow_name
    doc.document_type = definition["document_type"]
    doc.workflow_state_field = "workflow_state"
    doc.is_active = 0
    doc.override_status = 0
    doc.send_email_alert = 0
    if doc.meta.get_field("enable_action_confirmation"):
        doc.enable_action_confirmation = 0
    doc.set("states", [])
    doc.set("transitions", [])
    for state in _state_rows(definition):
        doc.append("states", state)
    for transition in _transition_rows(definition):
        doc.append("transitions", transition)
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)


def _state_rows(definition: dict) -> list[dict]:
    editor_roles = _dedupe(definition["editor_roles"])
    rows = []
    for state, doc_status, roles in (
        (STATE_PENDING, 0, editor_roles),
        (STATE_APPROVED, 0, APPROVER_ROLES),
        (STATE_REJECTED, 0, editor_roles),
        (STATE_SUBMITTED, 1, APPROVER_ROLES),
    ):
        for role in roles:
            rows.append({"state": state, "doc_status": str(doc_status), "allow_edit": role})
    return rows


def _transition_rows(definition: dict) -> list[dict]:
    editor_roles = _dedupe(definition["editor_roles"])
    rows = []
    rows.extend(_transition(STATE_PENDING, ACTION_APPROVE, STATE_APPROVED, APPROVER_ROLES))
    rows.extend(_transition(STATE_PENDING, ACTION_REJECT, STATE_REJECTED, APPROVER_ROLES))
    rows.extend(_transition(STATE_REJECTED, ACTION_REOPEN, STATE_PENDING, editor_roles))
    rows.extend(_transition(STATE_APPROVED, ACTION_SUBMIT, STATE_SUBMITTED, APPROVER_ROLES))
    return rows


def _transition(state: str, action: str, next_state: str, roles: tuple[str, ...] | list[str]) -> list[dict]:
    return [
        {
            "state": state,
            "action": action,
            "next_state": next_state,
            "allowed": role,
            "allow_self_approval": 0,
        }
        for role in roles
    ]


def _missing_roles(roles: tuple[str, ...] | list[str], existing_roles: set[str]) -> list[str]:
    return [role for role in _dedupe(roles) if role not in existing_roles]


def _dedupe(values: tuple[str, ...] | list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
