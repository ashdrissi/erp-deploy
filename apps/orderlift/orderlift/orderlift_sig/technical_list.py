from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime


TECHNICAL_LIST_DOCTYPE = "Sales Order Technical List"
REVISION_DOCTYPE = "Sales Order Technical List Revision"
ITEM_DOCTYPE = "Sales Order Technical List Item"
ANNEX_ROW_DOCTYPE = "Sales Order Technical List Annex"
ANNEX_DOCTYPE = "Orderlift Annex Document"
TEMPLATE_DOCTYPE = "Orderlift Document Template"
TEMPLATE_TARGET_DOCTYPE = "Orderlift Document Template Target"

COMPANY_FIELDS = {
    "enabled": "custom_enable_sales_order_technical_lists",
    "effective_from": "custom_technical_list_effective_from",
    "apply_all_business_types": "custom_technical_list_apply_all_business_types",
    "business_types": "custom_technical_list_business_types",
    "require_project": "custom_technical_list_require_project",
    "auto_create": "custom_technical_list_auto_create",
    "allow_additions": "custom_technical_list_allow_additions",
    "allow_exclusions": "custom_technical_list_allow_exclusions",
    "require_change_reason": "custom_technical_list_require_change_reason",
    "include_non_stock_items": "custom_technical_list_include_non_stock_items",
    "default_procurement_route": "custom_technical_list_default_procurement_route",
    "use_stock_planning": "custom_technical_list_use_stock_planning",
    "use_delivery": "custom_technical_list_use_delivery",
}

SOURCE_ITEM_FIELDS = (
    "name",
    "item_code",
    "item_name",
    "description",
    "qty",
    "uom",
    "conversion_factor",
    "stock_uom",
    "warehouse",
    "delivery_date",
)

APPROVAL_ITEM_FIELDS = (
    "line_key",
    "sales_order_item",
    "item_code",
    "item_name",
    "description",
    "is_stock_item",
    "sales_order_qty",
    "execution_qty",
    "variance_qty",
    "uom",
    "conversion_factor",
    "stock_uom",
    "execution_stock_qty",
    "warehouse",
    "required_date",
    "procurement_route",
    "change_reason",
    "technical_notes",
    "execution_relevant",
)

APPROVAL_ANNEX_FIELDS = (
    "template",
    "annex",
    "source_annex",
    "origin",
    "required_for_revision",
    "must_be_complete",
    "annex_status",
    "is_complete",
    "source_modified",
    "annex_content_hash",
    "source_content_hash",
    "display_order",
)


def after_migrate() -> None:
    """Install configurable Company policy and read-only source dashboards."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    technical_company_fields = {
        "custom_technical_list_tab",
        "custom_technical_list_applicability_section",
        "custom_technical_list_editing_section",
        "custom_technical_list_execution_section",
        *COMPANY_FIELDS.values(),
    }
    company_anchor = next(
        (
            field.fieldname
            for field in reversed(frappe.get_meta("Company").fields)
            if field.fieldname not in technical_company_fields
        ),
        "default_currency",
    )
    sales_order_anchor = (
        "custom_documents_html"
        if _meta_has_field("Sales Order", "custom_documents_html")
        else "party_account_currency"
    )
    project_anchor = (
        "custom_documents_html"
        if _meta_has_field("Project", "custom_documents_html")
        else "custom_qc_checklist"
    )
    create_custom_fields(
        {
            "Company": [
                {
                    "fieldname": "custom_technical_list_tab",
                    "label": "Technical Lists",
                    "fieldtype": "Tab Break",
                    "insert_after": company_anchor,
                },
                {
                    "fieldname": COMPANY_FIELDS["enabled"],
                    "label": "Enable Sales Order Technical Lists",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "custom_technical_list_tab",
                },
                {
                    "fieldname": COMPANY_FIELDS["effective_from"],
                    "label": "Technical List Effective From",
                    "fieldtype": "Date",
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']}",
                    "insert_after": COMPANY_FIELDS["enabled"],
                    "description": "Sales Orders before this date keep their existing procurement flow.",
                },
                {
                    "fieldname": COMPANY_FIELDS["require_project"],
                    "label": "Require Project",
                    "fieldtype": "Check",
                    "default": "1",
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']}",
                    "insert_after": COMPANY_FIELDS["effective_from"],
                },
                {
                    "fieldname": COMPANY_FIELDS["auto_create"],
                    "label": "Create Draft Technical List Automatically",
                    "fieldtype": "Check",
                    "default": "1",
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']}",
                    "insert_after": COMPANY_FIELDS["require_project"],
                },
                {
                    "fieldname": "custom_technical_list_applicability_section",
                    "label": "Applicability",
                    "fieldtype": "Section Break",
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']}",
                    "insert_after": COMPANY_FIELDS["auto_create"],
                },
                {
                    "fieldname": COMPANY_FIELDS["apply_all_business_types"],
                    "label": "Apply to All Business Types",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "custom_technical_list_applicability_section",
                },
                {
                    "fieldname": COMPANY_FIELDS["business_types"],
                    "label": "Applicable Business Types",
                    "fieldtype": "Table",
                    "options": "Technical List Business Type",
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']} && !doc.{COMPANY_FIELDS['apply_all_business_types']}",
                    "insert_after": COMPANY_FIELDS["apply_all_business_types"],
                },
                {
                    "fieldname": "custom_technical_list_editing_section",
                    "label": "Editing Rules",
                    "fieldtype": "Section Break",
                    "hidden": 1,
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']}",
                    "insert_after": COMPANY_FIELDS["business_types"],
                },
                {
                    "fieldname": COMPANY_FIELDS["allow_additions"],
                    "label": "Allow Design Item Additions",
                    "fieldtype": "Check",
                    "default": "1",
                    "hidden": 1,
                    "insert_after": "custom_technical_list_editing_section",
                },
                {
                    "fieldname": COMPANY_FIELDS["allow_exclusions"],
                    "label": "Allow Source Item Exclusions",
                    "fieldtype": "Check",
                    "default": "1",
                    "hidden": 1,
                    "insert_after": COMPANY_FIELDS["allow_additions"],
                },
                {
                    "fieldname": COMPANY_FIELDS["require_change_reason"],
                    "label": "Require Change Reason",
                    "fieldtype": "Check",
                    "default": "1",
                    "hidden": 1,
                    "insert_after": COMPANY_FIELDS["allow_exclusions"],
                },
                {
                    "fieldname": COMPANY_FIELDS["include_non_stock_items"],
                    "label": "Include Non-stock and Service Items",
                    "fieldtype": "Check",
                    "default": "1",
                    "hidden": 1,
                    "insert_after": COMPANY_FIELDS["require_change_reason"],
                },
                {
                    "fieldname": "custom_technical_list_execution_section",
                    "label": "Execution",
                    "fieldtype": "Section Break",
                    "hidden": 1,
                    "depends_on": f"eval:doc.{COMPANY_FIELDS['enabled']}",
                    "insert_after": COMPANY_FIELDS["include_non_stock_items"],
                },
                {
                    "fieldname": COMPANY_FIELDS["default_procurement_route"],
                    "label": "Default Technical Procurement Route",
                    "fieldtype": "Link",
                    "options": "Technical Procurement Route",
                    "hidden": 1,
                    "insert_after": "custom_technical_list_execution_section",
                },
                {
                    "fieldname": COMPANY_FIELDS["use_stock_planning"],
                    "label": "Use Approved Technical List for Stock Planning",
                    "fieldtype": "Check",
                    "default": "0",
                    "hidden": 1,
                    "insert_after": COMPANY_FIELDS["default_procurement_route"],
                },
                {
                    "fieldname": COMPANY_FIELDS["use_delivery"],
                    "label": "Use Approved Technical List for Delivery",
                    "fieldtype": "Check",
                    "default": "0",
                    "hidden": 1,
                    "insert_after": COMPANY_FIELDS["use_stock_planning"],
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_technical_list_tab",
                    "label": "Technical List",
                    "fieldtype": "Tab Break",
                    "insert_after": sales_order_anchor,
                },
                {
                    "fieldname": "custom_technical_list_html",
                    "label": "Technical List",
                    "fieldtype": "HTML",
                    "insert_after": "custom_technical_list_tab",
                },
            ],
            "Project": [
                {
                    "fieldname": "custom_technical_lists_tab",
                    "label": "Technical Lists",
                    "fieldtype": "Tab Break",
                    "insert_after": project_anchor,
                },
                {
                    "fieldname": "custom_technical_lists_html",
                    "label": "Technical Lists",
                    "fieldtype": "HTML",
                    "insert_after": "custom_technical_lists_tab",
                },
            ],
        },
        update=True,
    )
    _backfill_internal_company_defaults()


def validate_company_settings(doc, method=None) -> None:
    if not _meta_has_field("Company", COMPANY_FIELDS["enabled"]):
        return
    business_types = [
        (_value(row, "business_type") or "").strip()
        for row in _children(doc, COMPANY_FIELDS["business_types"])
        if (_value(row, "business_type") or "").strip()
    ]
    if len(business_types) != len(set(business_types)):
        frappe.throw(_("Applicable Technical List Business Types cannot be duplicated."))
    if cint(_value(doc, COMPANY_FIELDS["enabled"])) and not cint(
        _value(doc, COMPANY_FIELDS["apply_all_business_types"])
    ) and not business_types:
        frappe.throw(
            _("Select at least one Technical List Business Type or enable Apply to All Business Types.")
        )
    for key in ("allow_additions", "allow_exclusions", "include_non_stock_items"):
        setattr(doc, COMPANY_FIELDS[key], 1)
    route = (_value(doc, COMPANY_FIELDS["default_procurement_route"]) or "").strip()
    if not route:
        route = _internal_material_request_route()
        if route:
            setattr(doc, COMPANY_FIELDS["default_procurement_route"], route)
    if route:
        route_company = frappe.db.get_value("Technical Procurement Route", route, "company")
        if route_company and route_company != doc.name:
            frappe.throw(_("The default Technical Procurement Route belongs to another company."))


def _backfill_internal_company_defaults() -> None:
    route = _internal_material_request_route()
    values = {
        COMPANY_FIELDS["allow_additions"]: 1,
        COMPANY_FIELDS["allow_exclusions"]: 1,
        COMPANY_FIELDS["include_non_stock_items"]: 1,
    }
    for company in frappe.get_all("Company", pluck="name", limit_page_length=0):
        updates = dict(values)
        if route and not frappe.db.get_value("Company", company, COMPANY_FIELDS["default_procurement_route"]):
            updates[COMPANY_FIELDS["default_procurement_route"]] = route
        frappe.db.set_value("Company", company, updates, update_modified=False)


def _internal_material_request_route() -> str:
    if not frappe.db.exists("DocType", "Technical Procurement Route"):
        return ""
    route = frappe.db.get_value(
        "Technical Procurement Route",
        {"name": "Approved Technical List to Material Request", "enabled": 1},
        "name",
    )
    if route:
        return route
    return frappe.db.get_value(
        "Technical Procurement Route",
        {"enabled": 1, "is_default": 1, "company": ["is", "not set"]},
        "name",
        order_by="modified desc",
    ) or ""


def validate_technical_list(doc) -> None:
    sales_order = _get_sales_order(doc.sales_order)
    _assert_company_eligible(sales_order)
    existing = frappe.db.exists(
        TECHNICAL_LIST_DOCTYPE,
        {"sales_order": sales_order.name, "name": ["!=", doc.name or ""]},
    )
    if existing:
        frappe.throw(_("Sales Order {0} already has technical list {1}.").format(sales_order.name, existing))

    snapshots = _sales_order_snapshots(sales_order)
    for fieldname, value in snapshots.items():
        setattr(doc, fieldname, value)


def validate_revision(doc, for_submit: bool = False) -> None:
    prepare_revision_items(doc)
    parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, doc.technical_list)
    sales_order = _get_sales_order(doc.sales_order)
    _assert_company_eligible(sales_order)
    _lock_parent(parent.name)

    if parent.sales_order != sales_order.name:
        frappe.throw(_("The revision Sales Order must match its technical list."))
    snapshots = _sales_order_snapshots(sales_order)
    for fieldname, expected in snapshots.items():
        if (getattr(doc, fieldname, None) or "") != (expected or ""):
            frappe.throw(_("Revision field {0} does not match the Sales Order snapshot.").format(fieldname))
        if (getattr(parent, fieldname, None) or "") != (getattr(doc, fieldname, None) or ""):
            frappe.throw(_("Revision field {0} does not match its technical list.").format(fieldname))

    _validate_revision_number(doc)
    _enforce_one_open_revision(doc)
    policy = _company_policy(doc.company)
    item_metadata = _item_metadata(
        {_value(row, "item_code") for row in _children(sales_order, "items")}
        | {_value(row, "item_code") for row in _children(doc, "items")}
    )
    eligible_source_items = _eligible_source_items(sales_order, policy, item_metadata)
    source_items = {_value(row, "name"): row for row in eligible_source_items}
    source_values = {
        _value(row, "name"): _source_item_values(sales_order, row, item_metadata, policy)
        for row in eligible_source_items
    }
    _validate_items(doc, source_items, source_values, policy, item_metadata)

    if for_submit:
        _synchronize_revision_annex_rows(doc)
    _validate_annexes(doc, for_submit=for_submit)
    readiness = _apply_readiness(doc)

    if for_submit:
        current_source_hash = _source_hash(sales_order)
        if (doc.source_hash or "") != current_source_hash:
            frappe.throw(_("The Sales Order source changed. Sync the draft revision before submitting."))
        if not readiness["is_ready"]:
            frappe.throw(_("The technical list revision is not ready: {0}").format(readiness["summary"]))


def prepare_revision_items(doc) -> None:
    """Populate hidden identity and Item defaults before mandatory child checks."""
    rows = _children(doc, "items")
    metadata = _item_metadata({_value(row, "item_code") for row in rows})
    default_route = ""
    if _value(doc, "company"):
        default_route = _company_policy(_value(doc, "company"))["default_procurement_route"]
    for row in rows:
        if not _value(row, "line_key"):
            row.line_key = _value(row, "sales_order_item") or _new_added_line_key()
        item = metadata.get(_value(row, "item_code"), {})
        if item:
            row.item_name = _value(row, "item_name") or item.get("item_name") or _value(row, "item_code")
            row.description = _value(row, "description") or item.get("description") or ""
            row.is_stock_item = cint(item.get("is_stock_item"))
            row.stock_uom = item.get("stock_uom") or _value(row, "stock_uom") or _value(row, "uom")
            row.uom = _value(row, "uom") or row.stock_uom
            if flt(_value(row, "conversion_factor")) <= 0:
                row.conversion_factor = _item_conversion_factor(
                    _value(row, "item_code"), row.uom, row.stock_uom
                )
        if _value(row, "execution_qty") in (None, ""):
            row.execution_qty = flt(_value(row, "sales_order_qty")) or 1
        if _value(row, "execution_relevant") in (None, ""):
            row.execution_relevant = 1
        if not _value(row, "procurement_route") and default_route:
            row.procurement_route = default_route


def _item_conversion_factor(item_code: str, uom: str, stock_uom: str) -> float:
    if not item_code or not uom or uom == stock_uom:
        return 1
    return flt(
        frappe.db.get_value(
            "UOM Conversion Detail",
            {"parent": item_code, "uom": uom},
            "conversion_factor",
        )
    ) or 1


def submit_revision(doc) -> None:
    _lock_parent(doc.technical_list)
    # Hash the persisted revision, not the in-memory doc. The in-memory rows
    # can drift from what was written (e.g. re-synced annex content hashes),
    # and the procurement gate recalculates the hash from the database.
    persisted = frappe.get_doc(REVISION_DOCTYPE, doc.name)
    approval_hash = _approval_hash(persisted)
    doc.approval_hash = approval_hash
    frappe.db.set_value(REVISION_DOCTYPE, doc.name, "approval_hash", approval_hash, update_modified=False)
    frappe.db.set_value(
        TECHNICAL_LIST_DOCTYPE,
        doc.technical_list,
        {"current_revision": doc.name, "open_revision": None},
        update_modified=False,
    )
    _refresh_parent_summary(doc.technical_list)


def validate_revision_cancellation(doc) -> None:
    references = _downstream_revision_references(doc.name)
    if not references:
        return
    sample = ", ".join(f"{row['doctype']} {row['name']}" for row in references[:5])
    frappe.throw(_("Revision {0} has downstream technical references: {1}.").format(doc.name, sample))


def cancel_revision(doc) -> None:
    _lock_parent(doc.technical_list)
    parent_values = frappe.db.get_value(
        TECHNICAL_LIST_DOCTYPE,
        doc.technical_list,
        ["current_revision", "open_revision"],
        as_dict=True,
    ) or {}
    updates = {}
    if parent_values.get("current_revision") == doc.name:
        updates["current_revision"] = _latest_revision(doc.technical_list, docstatus=1, exclude=doc.name)
    if parent_values.get("open_revision") == doc.name:
        updates["open_revision"] = _latest_revision(doc.technical_list, docstatus=0, exclude=doc.name)
    if updates:
        frappe.db.set_value(TECHNICAL_LIST_DOCTYPE, doc.technical_list, updates, update_modified=False)
    _refresh_parent_summary(doc.technical_list)


def cleanup_revision_pointers(revision) -> None:
    """Clear parent pointers left dangling after a revision is deleted."""
    technical_list_name = (_value(revision, "technical_list", "") or "").strip()
    revision_name = (_value(revision, "name", "") or "").strip()
    if (
        not technical_list_name
        or not revision_name
        or not frappe.db.exists(TECHNICAL_LIST_DOCTYPE, technical_list_name)
    ):
        return
    parent_values = frappe.db.get_value(
        TECHNICAL_LIST_DOCTYPE,
        technical_list_name,
        ["current_revision", "open_revision"],
        as_dict=True,
    ) or {}
    updates = {}
    if parent_values.get("current_revision") == revision_name:
        updates["current_revision"] = _latest_revision(technical_list_name, docstatus=1, exclude=revision_name)
    if parent_values.get("open_revision") == revision_name:
        updates["open_revision"] = _latest_revision(technical_list_name, docstatus=0, exclude=revision_name)
    if updates:
        frappe.db.set_value(TECHNICAL_LIST_DOCTYPE, technical_list_name, updates, update_modified=False)
    _refresh_parent_summary(technical_list_name)


def on_sales_order_submit_or_project_link(doc, method=None):
    if not doc:
        return None
    if _value(doc, "doctype") == "Project":
        results = []
        for name in frappe.get_all(
            "Sales Order",
            filters={"project": doc.name, "docstatus": 1},
            pluck="name",
            limit_page_length=0,
        ):
            results.append(on_sales_order_submit_or_project_link(frappe.get_doc("Sales Order", name)))
        return results
    if _value(doc, "doctype") != "Sales Order" or cint(_value(doc, "docstatus")) != 1:
        return None
    savepoint = ""
    try:
        policy = _company_policy(_value(doc, "company"))
        if not policy["enabled"] or not policy["auto_create"]:
            return None
        savepoint = f"technical_list_auto_{uuid.uuid4().hex[:10]}"
        frappe.db.savepoint(savepoint)
        eligible, reason = _company_eligibility(doc)
        if not eligible:
            return {"created": False, "reason": reason}
        result = _get_or_create_for_sales_order(doc, ignore_permissions=True)
        return {"created": True, "technical_list": result.get("name"), "revision": result.get("revision")}
    except Exception as exc:
        if savepoint:
            frappe.db.rollback(save_point=savepoint)
        message = frappe.get_traceback()
        frappe.log_error(
            title=_("Automatic technical list creation failed for {0}").format(doc.name),
            message=message,
        )
        return {"created": False, "reason": str(exc)}


@frappe.whitelist()
def create_for_sales_order(sales_order: str) -> dict:
    source = _get_sales_order(sales_order)
    source.check_permission("read")
    _assert_company_eligible(source)
    return _get_or_create_for_sales_order(source)


def _get_or_create_for_sales_order(source, ignore_permissions: bool = False) -> dict:

    parent_name = frappe.db.exists(TECHNICAL_LIST_DOCTYPE, {"sales_order": source.name})
    if parent_name:
        parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, parent_name)
        if not ignore_permissions:
            parent.check_permission("read")
    else:
        snapshots = _sales_order_snapshots(source)
        parent = frappe.get_doc({
            "doctype": TECHNICAL_LIST_DOCTYPE,
            "sales_order": source.name,
            **snapshots,
        })
        try:
            parent.insert(ignore_permissions=ignore_permissions)
        except frappe.DuplicateEntryError:
            parent_name = frappe.db.exists(TECHNICAL_LIST_DOCTYPE, {"sales_order": source.name})
            if not parent_name:
                raise
            parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, parent_name)
            if not ignore_permissions:
                parent.check_permission("read")

    if not parent.current_revision and not parent.open_revision:
        if not ignore_permissions:
            parent.check_permission("write")
        revision = _create_revision(parent, source, ignore_permissions=ignore_permissions)
        parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, parent.name)
    else:
        revision_name = parent.open_revision or parent.current_revision
        revision = frappe.get_doc(REVISION_DOCTYPE, revision_name) if revision_name else None

    result = _technical_list_summary(parent)
    result["revision"] = _revision_summary(revision) if revision else None
    return result


@frappe.whitelist()
def create_revision(technical_list: str) -> dict:
    parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, technical_list)
    parent.check_permission("write")
    _lock_parent(parent.name)
    existing = _latest_revision(parent.name, docstatus=0)
    if existing:
        frappe.throw(_("Technical list {0} already has open revision {1}.").format(parent.name, existing))
    source = _get_sales_order(parent.sales_order)
    revision = _create_revision(parent, source)
    return _revision_summary(revision)


@frappe.whitelist()
def sync_revision(revision: str) -> dict:
    doc = frappe.get_doc(REVISION_DOCTYPE, revision)
    doc.check_permission("write")
    if cint(doc.docstatus) != 0:
        frappe.throw(_("Only an open draft revision can be synchronized."))
    source = _get_sales_order(doc.sales_order)
    _sync_revision_source(doc, source)
    doc.save()
    _set_parent_open_revision(doc)
    return _revision_summary(doc)


@frappe.whitelist()
def get_sales_order_summary(sales_order: str) -> dict:
    source = frappe.get_doc("Sales Order", sales_order)
    source.check_permission("read")
    eligible, reason = _company_eligibility(source)
    parent_name = frappe.db.exists(TECHNICAL_LIST_DOCTYPE, {"sales_order": source.name})
    parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, parent_name) if parent_name else None
    if parent:
        parent.check_permission("read")
    summary = _technical_list_summary(parent) if parent else None
    if summary:
        summary["active_revision"] = _active_revision_display(parent)
    return {
        "sales_order": source.name,
        "docstatus": cint(source.docstatus),
        "company": source.company,
        "customer": source.customer,
        "project": _value(source, "project") or "",
        "business_type": _sales_order_business_type(source),
        "eligible": eligible,
        "eligibility_reason": reason,
        "technical_list": summary,
    }


@frappe.whitelist()
def get_project_summaries(project: str) -> list[dict]:
    project_doc = frappe.get_doc("Project", project)
    project_doc.check_permission("read")
    rows = frappe.get_list(
        TECHNICAL_LIST_DOCTYPE,
        filters={"project": project},
        fields=["name"],
        order_by="modified desc",
        limit_page_length=0,
    )
    result = []
    for row in rows:
        parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, row.name)
        summary = _technical_list_summary(parent)
        summary["active_revision"] = _active_revision_display(parent)
        result.append(summary)
    return result


@frappe.whitelist()
def get_revision_actions(revision: str) -> dict:
    doc = frappe.get_doc(REVISION_DOCTYPE, revision)
    doc.check_permission("read")
    readiness = _readiness(doc)
    sales_order = frappe.get_doc("Sales Order", doc.sales_order)
    policy = _company_policy(doc.company)
    item_metadata = _item_metadata({_value(row, "item_code") for row in _children(sales_order, "items")})
    source_items = {
        row.name: _source_item_values(sales_order, row, item_metadata, policy)
        for row in _eligible_source_items(sales_order, policy, item_metadata)
    }
    workflow_actions = []
    workflow = frappe.db.get_value("Workflow", {"document_type": REVISION_DOCTYPE, "is_active": 1}, "name")
    if workflow:
        from frappe.model.workflow import get_transitions

        workflow_actions = [
            {
                "action": _value(row, "action"),
                "next_state": _value(row, "next_state"),
                "allowed": _value(row, "allowed"),
            }
            for row in get_transitions(doc)
        ]
    return {
        "revision": doc.name,
        "docstatus": cint(doc.docstatus),
        "workflow_state": doc.workflow_state or "",
        "readiness": readiness,
        "workflow_actions": workflow_actions,
        "can_sync": cint(doc.docstatus) == 0 and doc.has_permission("write"),
        "can_submit": cint(doc.docstatus) == 0 and readiness["is_ready"] and doc.has_permission("submit"),
        "can_cancel": cint(doc.docstatus) == 1 and doc.has_permission("cancel"),
        "item_changes": [
            _item_change_payload(row, source_items.get(_value(row, "sales_order_item")))
            for row in _children(doc, "items")
        ],
    }


@frappe.whitelist()
def get_revision_readiness(revision: str) -> dict:
    doc = frappe.get_doc(REVISION_DOCTYPE, revision)
    doc.check_permission("read")
    return _readiness(doc)


def _create_revision(parent, source, ignore_permissions: bool = False):
    _lock_parent(parent.name)
    existing = _latest_revision(parent.name, docstatus=0)
    if existing:
        frappe.throw(_("Technical list {0} already has open revision {1}.").format(parent.name, existing))

    current = frappe.get_doc(REVISION_DOCTYPE, parent.current_revision) if parent.current_revision else None
    revision = frappe.get_doc({
        "doctype": REVISION_DOCTYPE,
        "technical_list": parent.name,
        "sales_order": source.name,
        "revision_no": _next_revision_number(parent.name),
        "based_on_revision": current.name if current else None,
        **_sales_order_snapshots(source),
    })
    if current:
        _copy_revision_items(current, revision)
    else:
        _initialize_items(revision, source)
    _sync_revision_source(revision, source)
    revision.insert(ignore_permissions=ignore_permissions)
    return revision


def _copy_revision_items(source, target) -> None:
    for row in _children(source, "items"):
        target.append("items", {field: _value(row, field) for field in APPROVAL_ITEM_FIELDS})


def _initialize_items(revision, sales_order) -> None:
    policy = _company_policy(sales_order.company)
    item_metadata = _item_metadata({_value(row, "item_code") for row in _children(sales_order, "items")})
    for row in _eligible_source_items(sales_order, policy, item_metadata):
        values = _source_item_values(sales_order, row, item_metadata, policy)
        values.update({
            "execution_qty": values["sales_order_qty"],
            "execution_stock_qty": values["sales_order_qty"] * values["conversion_factor"],
            "procurement_route": policy["default_procurement_route"],
            "execution_relevant": 1,
        })
        revision.append("items", values)


def _sync_revision_source(revision, sales_order) -> None:
    snapshots = _sales_order_snapshots(sales_order)
    for fieldname, value in snapshots.items():
        setattr(revision, fieldname, value)
    revision.sales_order = sales_order.name
    policy = _company_policy(sales_order.company)
    all_item_codes = {_value(row, "item_code") for row in _children(sales_order, "items")}
    all_item_codes.update(_value(row, "item_code") for row in _children(revision, "items"))
    item_metadata = _item_metadata(all_item_codes)
    source_rows = _eligible_source_items(sales_order, policy, item_metadata)
    eligible_source_names = {_value(row, "name") for row in source_rows}

    retained_rows = [
        row
        for row in _children(revision, "items")
        if not _value(row, "sales_order_item") or _value(row, "sales_order_item") in eligible_source_names
    ]
    if hasattr(revision, "set"):
        revision.set("items", retained_rows)
    else:
        revision.items = retained_rows

    existing = {
        _value(row, "sales_order_item"): row
        for row in _children(revision, "items")
        if _value(row, "sales_order_item")
    }
    for source_row in source_rows:
        values = _source_item_values(sales_order, source_row, item_metadata, policy)
        row = existing.get(source_row.name)
        if not row:
            values.update({
                "execution_qty": values["sales_order_qty"],
                "execution_stock_qty": values["sales_order_qty"] * values["conversion_factor"],
                "procurement_route": policy["default_procurement_route"],
                "execution_relevant": 1,
            })
            revision.append("items", values)
            continue
        execution_qty = _value(row, "execution_qty")
        for fieldname, value in values.items():
            setattr(row, fieldname, value)
        row.execution_qty = execution_qty
        row.variance_qty = flt(execution_qty) - flt(row.sales_order_qty)
        row.execution_stock_qty = flt(execution_qty) * flt(row.conversion_factor)

    if _is_persisted_revision(revision):
        _synchronize_revision_annex_rows(revision)
    revision.source_hash = _source_hash(sales_order)
    revision.source_synced_on = now_datetime()
    _apply_readiness(revision)


def _source_item_values(sales_order, row, item_metadata: dict, policy: dict) -> dict:
    conversion_factor = flt(_value(row, "conversion_factor") or 1)
    item_code = _value(row, "item_code")
    item = item_metadata.get(item_code, {})
    return {
        "line_key": _stable_line_key(sales_order.name, row),
        "sales_order_item": row.name,
        "item_code": item_code,
        "item_name": _value(row, "item_name") or item.get("item_name") or item_code,
        "description": _value(row, "description") or item.get("description") or "",
        "is_stock_item": cint(item.get("is_stock_item")),
        "sales_order_qty": flt(_value(row, "qty")),
        "variance_qty": 0,
        "uom": _value(row, "uom"),
        "conversion_factor": conversion_factor,
        "stock_uom": _value(row, "stock_uom") or _value(row, "uom"),
        "warehouse": _value(row, "warehouse") or _value(sales_order, "set_warehouse"),
        "required_date": _value(row, "delivery_date") or _value(sales_order, "delivery_date"),
    }


def _stable_line_key(sales_order: str, source_row) -> str:
    source_name = (_value(source_row, "name") or "").strip()
    if source_name:
        return source_name
    material = "|".join(
        str(value or "")
        for value in (sales_order, _value(source_row, "idx"), _value(source_row, "item_code"))
    )
    return f"SOI-{hashlib.sha256(material.encode()).hexdigest()[:20]}"


def _new_added_line_key() -> str:
    return f"ADD-{uuid.uuid4().hex}"


def _validate_items(doc, source_items: dict, source_values: dict, policy: dict, item_metadata: dict) -> None:
    if not _children(doc, "items"):
        frappe.throw(_("A technical list revision must contain at least one item."))
    line_keys = set()
    source_rows = set()
    for index, row in enumerate(_children(doc, "items"), 1):
        if not _value(row, "line_key"):
            if _value(row, "sales_order_item"):
                row.line_key = _value(row, "sales_order_item")
            else:
                row.line_key = _new_added_line_key()
        if row.line_key in line_keys:
            frappe.throw(_("Technical list row {0} duplicates line key {1}.").format(index, row.line_key))
        line_keys.add(row.line_key)

        source_name = _value(row, "sales_order_item")
        source_row = source_items.get(source_name) if source_name else None
        if source_name:
            if source_name in source_rows:
                frappe.throw(_("Sales Order item {0} appears more than once.").format(source_name))
            source_rows.add(source_name)
            if not source_row:
                frappe.throw(_("Technical list row {0} does not belong to the source Sales Order.").format(index))
            expected = source_values[source_name]
            if row.line_key != expected["line_key"]:
                frappe.throw(_("Line key on row {0} must match its Sales Order item.").format(index))
            if flt(row.sales_order_qty) != flt(expected["sales_order_qty"]):
                frappe.throw(_("Sales Order quantity on row {0} must match the source document.").format(index))
            if (_value(row, "item_code") or "") != (expected["item_code"] or ""):
                frappe.throw(_("Item on source row {0} must match the Sales Order.").format(index))
            for snapshot_field in ("item_name", "description", "is_stock_item"):
                if (_value(row, snapshot_field) or "") != (expected[snapshot_field] or ""):
                    frappe.throw(_("Item snapshot {0} is stale on technical list row {1}.").format(snapshot_field, index))
        else:
            row.sales_order_qty = 0
            if not policy["allow_additions"]:
                frappe.throw(_("Company policy does not allow technical-list item additions."))
            item = item_metadata.get(_value(row, "item_code"), {})
            row.item_name = item.get("item_name") or _value(row, "item_code")
            row.description = item.get("description") or ""
            row.is_stock_item = cint(item.get("is_stock_item"))
            if not row.is_stock_item and not policy["include_non_stock_items"]:
                frappe.throw(_("Company policy does not allow non-stock technical-list items."))

        if flt(row.sales_order_qty) < 0 or flt(row.execution_qty) < 0:
            frappe.throw(_("Quantities cannot be negative on technical list row {0}.").format(index))
        if flt(row.conversion_factor) <= 0:
            frappe.throw(_("Conversion factor must be positive on technical list row {0}.").format(index))
        if not cint(row.execution_relevant) and flt(row.execution_qty) > 0:
            frappe.throw(_("An excluded row cannot have a positive execution quantity (row {0}).").format(index))

        row.variance_qty = flt(row.execution_qty) - flt(row.sales_order_qty)
        row.execution_stock_qty = flt(row.execution_qty) * flt(row.conversion_factor)
        change_type = _derive_item_change_type(row, expected if source_name else None)
        if change_type == "excluded" and not policy["allow_exclusions"]:
            frappe.throw(_("Company policy does not allow technical-list item exclusions."))
        if change_type != "unchanged" and policy["require_change_reason"] and not (_value(row, "change_reason") or "").strip():
            frappe.throw(_("A change reason is required on technical list row {0}.").format(index))


def _derive_item_change_type(row, source_row=None) -> str:
    if not _value(row, "sales_order_item"):
        return "added"
    if not cint(_value(row, "execution_relevant")) or (
        flt(_value(row, "sales_order_qty")) > 0 and flt(_value(row, "execution_qty")) == 0
    ):
        return "excluded"
    if flt(_value(row, "execution_qty")) != flt(_value(row, "sales_order_qty")):
        return "modified"
    if source_row:
        for technical_field in ("warehouse", "required_date", "uom", "conversion_factor"):
            left = _value(row, technical_field)
            right = _value(source_row, technical_field)
            if technical_field == "conversion_factor":
                if flt(left) != flt(right or 1):
                    return "modified"
            elif (left or "") != (right or ""):
                return "modified"
    return "unchanged"


def _item_change_payload(row, source_row=None) -> dict:
    return {
        "line_key": _value(row, "line_key"),
        "sales_order_item": _value(row, "sales_order_item"),
        "change_type": _derive_item_change_type(row, source_row),
        "sales_order_qty": flt(_value(row, "sales_order_qty")),
        "execution_qty": flt(_value(row, "execution_qty")),
        "variance_qty": flt(_value(row, "variance_qty")),
    }


def _validate_annexes(doc, for_submit: bool = False) -> None:
    for index, row in enumerate(_children(doc, "annexes"), 1):
        template = (_value(row, "template") or "").strip()
        if not (_value(row, "origin") or "").strip():
            row.origin = "Manual"
        if not template:
            frappe.throw(_("Annex row {0} requires template metadata.").format(index))
        annex = _value(row, "annex")
        source_annex = _value(row, "source_annex")
        if source_annex and not frappe.db.exists(ANNEX_DOCTYPE, source_annex):
            frappe.throw(_("Source annex {0} was not found.").format(source_annex))
        if annex:
            _validate_linked_annex(doc, row, annex)

    if for_submit:
        diagnostics = _dynamic_annex_diagnostics(doc)
        if not diagnostics.get("available"):
            frappe.throw(_("Dynamic annex completion diagnostics are unavailable for this revision."))


def _validate_linked_annex(revision, row, annex_name: str) -> None:
    fields = [
        field
        for field in ("template", "company", "reference_doctype", "reference_name", "source_annex", "origin")
        if _meta_has_field(ANNEX_DOCTYPE, field)
    ]
    values = frappe.db.get_value(ANNEX_DOCTYPE, annex_name, fields, as_dict=True)
    if not values:
        frappe.throw(_("Annex {0} was not found.").format(annex_name))
    if values.get("template") and values.get("template") != row.template:
        frappe.throw(_("Annex {0} uses a different template.").format(annex_name))
    if values.get("company") and values.get("company") != revision.company:
        frappe.throw(_("Annex {0} belongs to a different company.").format(annex_name))
    if values.get("reference_doctype") != REVISION_DOCTYPE or values.get("reference_name") != revision.name:
        frappe.throw(_("Annex {0} is not owned by this technical-list revision.").format(annex_name))
    if (values.get("source_annex") or "") != (_value(row, "source_annex") or ""):
        frappe.throw(_("Annex {0} source provenance does not match the revision manifest.").format(annex_name))


def initialize_revision_manifest(revision) -> None:
    if not revision.name:
        return
    _set_parent_open_revision(revision)
    from orderlift.annex_chain import initialize_revision_execution_copies
    from orderlift.document_templates import initialize_technical_revision_manifest

    initialize_revision_execution_copies(revision)

    manifest = initialize_technical_revision_manifest(
        REVISION_DOCTYPE,
        revision.name,
        sales_order_name=revision.sales_order,
        create_defaults=0 if revision.based_on_revision else 1,
    )
    _synchronize_revision_annex_rows(revision, manifest=manifest)
    readiness = _apply_readiness(revision)
    for row in _children(revision, "annexes"):
        if not _value(row, "name"):
            row.db_insert()
    frappe.db.set_value(
        REVISION_DOCTYPE,
        revision.name,
        {
            "required_annex_count": readiness["required_annex_count"],
            "completed_annex_count": readiness["completed_annex_count"],
            "is_ready": cint(readiness["is_ready"]),
            "readiness_summary": readiness["summary"],
        },
        update_modified=False,
    )
    _refresh_parent_summary(revision.technical_list)


def refresh_revision_annex_state(revision_name: str) -> None:
    """Refresh persisted manifest rows and readiness after an Annex API change."""
    if not revision_name or not frappe.db.exists(REVISION_DOCTYPE, revision_name):
        return
    revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
    if cint(revision.docstatus) != 0:
        return
    _synchronize_revision_annex_rows(revision)
    readiness = _apply_readiness(revision)
    frappe.db.set_value(
        REVISION_DOCTYPE,
        revision.name,
        {
            "required_annex_count": readiness["required_annex_count"],
            "completed_annex_count": readiness["completed_annex_count"],
            "is_ready": cint(readiness["is_ready"]),
            "readiness_summary": readiness["summary"],
        },
        update_modified=False,
    )
    _refresh_parent_summary(revision.technical_list)


def _synchronize_revision_annex_rows(revision, manifest: dict | None = None) -> None:
    if not _is_persisted_revision(revision):
        return
    from orderlift.document_templates import get_annex_completion_diagnostics, parse_template_snapshot

    targets = _revision_template_targets()
    annex_names = frappe.get_all(
        ANNEX_DOCTYPE,
        filters={
            "reference_doctype": REVISION_DOCTYPE,
            "reference_name": revision.name,
            "docstatus": ["<", 2],
        },
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )
    rows = []
    represented_templates = set()
    for annex_name in annex_names:
        annex = frappe.get_doc(ANNEX_DOCTYPE, annex_name)
        definition = parse_template_snapshot(_value(annex, "template_snapshot_json"))
        frozen_target = next(
            (
                target
                for target in definition.get("targets") or []
                if target.get("target_doctype") == REVISION_DOCTYPE
            ),
            targets.get(annex.template, {}),
        )
        diagnostics = get_annex_completion_diagnostics(annex)
        rows.append({
            "template": annex.template,
            "annex": annex.name,
            "source_annex": _value(annex, "source_annex"),
            "origin": _value(annex, "origin") or "Native",
            "required_for_revision": cint(frozen_target.get("required_for_revision")),
            "must_be_complete": cint(frozen_target.get("must_be_complete")),
            "annex_status": diagnostics.get("status") or "",
            "is_complete": cint(diagnostics.get("is_complete")),
            "source_modified": _value(annex, "source_modified") or _value(annex, "modified"),
            "annex_content_hash": _value(annex, "content_hash") or "",
            "source_content_hash": _value(annex, "source_content_hash") or "",
            "display_order": frozen_target.get("display_order") or 100,
        })
        represented_templates.add(annex.template)

    missing_templates = {
        row.get("template")
        for row in (manifest or {}).get("diagnostics", {}).get("missing_templates", [])
        if row.get("template")
    }
    missing_templates.update(
        template
        for template, target in targets.items()
        if cint(target.get("required_for_revision")) and template not in represented_templates
    )
    for template in missing_templates:
        target = targets.get(template, {})
        rows.append({
            "template": template,
            "origin": "Template Requirement",
            "required_for_revision": 1,
            "must_be_complete": cint(target.get("must_be_complete")),
            "display_order": target.get("display_order") or 100,
        })
    rows.sort(key=lambda row: (cint(row.get("display_order")) or 100, row.get("template") or "", row.get("annex") or ""))
    revision.set("annexes", [])
    for row in rows:
        revision.append("annexes", row)


def _revision_template_targets() -> dict[str, dict]:
    if not frappe.db.exists("DocType", TEMPLATE_TARGET_DOCTYPE):
        return {}
    fields = ["parent"]
    for fieldname in ("required_for_revision", "must_be_complete", "default_selected", "display_order"):
        if _meta_has_field(TEMPLATE_TARGET_DOCTYPE, fieldname):
            fields.append(fieldname)
    rows = frappe.get_all(
        TEMPLATE_TARGET_DOCTYPE,
        filters={"target_doctype": REVISION_DOCTYPE},
        fields=fields,
        order_by="display_order asc, idx asc" if "display_order" in fields else "idx asc",
        limit_page_length=0,
    )
    return {row.parent: dict(row) for row in rows if row.parent}


def _readiness(doc) -> dict:
    issues = []
    if not _children(doc, "items"):
        issues.append(_("No technical items are defined."))
    required_templates = {
        template
        for template, target in _revision_template_targets().items()
        if cint(target.get("required_for_revision"))
    }
    if not required_templates:
        required_templates = {
            _value(row, "template")
            for row in _children(doc, "annexes")
            if cint(_value(row, "required_for_revision")) and _value(row, "template")
        }
    diagnostics = _dynamic_annex_diagnostics(doc)
    if diagnostics.get("available"):
        missing_templates = {row.get("template") for row in diagnostics.get("missing_templates") or []}
        incomplete_templates = {row.get("template") for row in diagnostics.get("incomplete_annexes") or []}
        for row in diagnostics.get("missing_templates") or []:
            issues.append(_("Annex {0} is required.").format(row.get("template_name") or row.get("template")))
        for row in diagnostics.get("incomplete_annexes") or []:
            issues.append(_("Annex {0} is incomplete.").format(row.get("template_name") or row.get("template")))
        required = len(required_templates)
        completed = len(required_templates - missing_templates - incomplete_templates)
    else:
        required = len(required_templates)
        completed = 0
        annex_rows = _children(doc, "annexes")
        for template in required_templates:
            matching = [row for row in annex_rows if _value(row, "template") == template]
            if not matching or not any(_value(row, "annex") for row in matching):
                issues.append(_("Annex {0} is required.").format(template))
                continue
            if any(
                _value(row, "annex")
                and cint(_value(row, "must_be_complete"))
                and not cint(_value(row, "is_complete"))
                for row in matching
            ):
                issues.append(_("Annex {0} is incomplete.").format(template))
                continue
            completed += 1
        for row in annex_rows:
            if (
                _value(row, "template") not in required_templates
                and _value(row, "annex")
                and cint(_value(row, "must_be_complete"))
                and not cint(_value(row, "is_complete"))
            ):
                issues.append(_("Annex {0} is incomplete.").format(_value(row, "template")))
    summary = _("{0} of {1} required annexes ready.").format(completed, required)
    if issues:
        summary = f"{summary} {' '.join(issues)}"
    return {
        "required_annex_count": required,
        "completed_annex_count": completed,
        "is_ready": not issues,
        "summary": summary,
        "issues": issues,
    }


def _dynamic_annex_diagnostics(doc) -> dict:
    if not _is_persisted_revision(doc):
        return {"available": False, "is_complete": False, "missing_templates": [], "incomplete_annexes": []}
    from orderlift.document_templates import get_technical_revision_completion_diagnostics

    return get_technical_revision_completion_diagnostics(REVISION_DOCTYPE, doc.name)


def _apply_readiness(doc) -> dict:
    readiness = _readiness(doc)
    doc.required_annex_count = readiness["required_annex_count"]
    doc.completed_annex_count = readiness["completed_annex_count"]
    doc.is_ready = cint(readiness["is_ready"])
    doc.readiness_summary = readiness["summary"]
    return readiness


def _sales_order_snapshots(sales_order) -> dict:
    return {
        "company": sales_order.company,
        "customer": sales_order.customer,
        "project": _value(sales_order, "project") or "",
        "business_type": _sales_order_business_type(sales_order),
    }


def _sales_order_business_type(sales_order) -> str:
    if _meta_has_field("Sales Order", "custom_crm_business_type"):
        return (_value(sales_order, "custom_crm_business_type") or "").strip()
    return ""


def _get_sales_order(name: str):
    sales_order = frappe.get_doc("Sales Order", name)
    if cint(sales_order.docstatus) != 1:
        frappe.throw(_("Sales Order {0} must be submitted before creating a technical list.").format(name))
    return sales_order


def _company_eligibility(sales_order) -> tuple[bool, str]:
    company = sales_order.company
    business_type = _sales_order_business_type(sales_order)
    if _meta_has_field("Company", "disabled") and cint(_company_value(company, "disabled")):
        return False, _("The Sales Order company is disabled.")
    if _meta_has_field("Company", "is_group") and cint(_company_value(company, "is_group")):
        return False, _("Group companies cannot own technical lists.")

    policy = _company_policy(company)
    if not policy["enabled"]:
        return False, _("Technical lists are disabled for this company configuration.")
    effective_from = policy["effective_from"]
    transaction_date = _value(sales_order, "transaction_date")
    if effective_from and (not transaction_date or getdate(transaction_date) < getdate(effective_from)):
        return False, _("The Sales Order predates the company's technical-list effective date.")
    if policy["require_project"] and not (_value(sales_order, "project") or "").strip():
        return False, _("A Project is required before creating a technical list.")
    if not policy["apply_all_business_types"]:
        if not business_type or business_type not in set(policy["business_types"]):
            return False, _("The Sales Order business type is not enabled for technical lists in this company.")
    return True, ""


def _assert_company_eligible(sales_order) -> None:
    eligible, reason = _company_eligibility(sales_order)
    if not eligible:
        frappe.throw(reason)


def _company_policy(company: str) -> dict:
    policy = {
        "enabled": False,
        "effective_from": None,
        "apply_all_business_types": False,
        "business_types": [],
        "require_project": False,
        "auto_create": False,
        "allow_additions": False,
        "allow_exclusions": False,
        "require_change_reason": False,
        "include_non_stock_items": False,
        "default_procurement_route": "",
        "use_stock_planning": False,
        "use_delivery": False,
    }
    check_keys = {
        "enabled",
        "apply_all_business_types",
        "require_project",
        "auto_create",
        "allow_additions",
        "allow_exclusions",
        "require_change_reason",
        "include_non_stock_items",
        "use_stock_planning",
        "use_delivery",
    }
    for key, fieldname in COMPANY_FIELDS.items():
        if key == "business_types" or not _meta_has_field("Company", fieldname):
            continue
        value = _company_value(company, fieldname)
        policy[key] = bool(cint(value)) if key in check_keys else value
    if not policy["apply_all_business_types"]:
        policy["business_types"] = _company_technical_list_business_types(company)
    return policy


def _company_technical_list_business_types(company: str) -> list[str]:
    fieldname = COMPANY_FIELDS["business_types"]
    if not _meta_has_field("Company", fieldname):
        return []
    field = frappe.get_meta("Company").get_field(fieldname)
    child_doctype = field.options
    if not child_doctype or not frappe.db.exists("DocType", child_doctype) or not _meta_has_field(child_doctype, "business_type"):
        return []
    rows = frappe.get_all(
        child_doctype,
        filters={"parenttype": "Company", "parent": company, "parentfield": fieldname},
        fields=["business_type", "idx"],
        order_by="idx asc",
        limit_page_length=0,
    )
    return [_value(row, "business_type") for row in rows if _value(row, "business_type")]


def _company_value(company: str, fieldname: str):
    return frappe.db.get_value("Company", company, fieldname)


def _item_metadata(item_codes) -> dict[str, dict]:
    item_codes = sorted({code for code in item_codes if code})
    if not item_codes:
        return {}
    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_name", "description", "is_stock_item", "stock_uom"],
        limit_page_length=0,
    )
    return {row.name: dict(row) for row in rows}


def _eligible_source_items(sales_order, policy: dict, item_metadata: dict) -> list:
    if policy["include_non_stock_items"]:
        return list(_children(sales_order, "items"))
    return [
        row
        for row in _children(sales_order, "items")
        if cint(item_metadata.get(_value(row, "item_code"), {}).get("is_stock_item"))
    ]


def _source_hash(sales_order) -> str:
    payload = {
        "sales_order": sales_order.name,
        **_sales_order_snapshots(sales_order),
        "set_warehouse": _value(sales_order, "set_warehouse"),
        "delivery_date": _value(sales_order, "delivery_date"),
        "items": [
            {field: _hash_value(_value(row, field)) for field in SOURCE_ITEM_FIELDS}
            for row in _children(sales_order, "items")
        ],
    }
    return _hash_payload(payload)


def _approval_hash(doc) -> str:
    payload = {
        "technical_list": doc.technical_list,
        "sales_order": doc.sales_order,
        "revision_no": cint(doc.revision_no),
        "docstatus": cint(doc.docstatus),
        "based_on_revision": doc.based_on_revision or "",
        "company": doc.company,
        "customer": doc.customer or "",
        "project": doc.project or "",
        "business_type": doc.business_type or "",
        "source_hash": doc.source_hash or "",
        "workflow_state": doc.workflow_state or "",
        "notes": doc.notes or "",
        "items": [
            {field: _hash_value(_value(row, field)) for field in APPROVAL_ITEM_FIELDS}
            for row in _children(doc, "items")
        ],
        "annexes": [
            {field: _hash_value(_value(row, field)) for field in APPROVAL_ANNEX_FIELDS}
            for row in _children(doc, "annexes")
        ],
    }
    return _hash_payload(payload)


def _hash_payload(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _hash_value(value):
    if isinstance(value, float):
        return format(value, ".12g")
    return value


def _validate_revision_number(doc) -> None:
    if cint(doc.revision_no) <= 0:
        frappe.throw(_("Revision number must be positive."))
    duplicate = frappe.db.exists(
        REVISION_DOCTYPE,
        {
            "technical_list": doc.technical_list,
            "revision_no": cint(doc.revision_no),
            "name": ["!=", doc.name or ""],
            "docstatus": ["<", 2],
        },
    )
    if duplicate:
        frappe.throw(_("Revision number {0} already exists for this technical list.").format(doc.revision_no))


def _enforce_one_open_revision(doc) -> None:
    if cint(doc.docstatus) != 0:
        return
    existing = frappe.db.exists(
        REVISION_DOCTYPE,
        {
            "technical_list": doc.technical_list,
            "docstatus": 0,
            "name": ["!=", doc.name or ""],
        },
    )
    if existing:
        frappe.throw(_("Technical list {0} already has open revision {1}.").format(doc.technical_list, existing))


def _next_revision_number(technical_list: str) -> int:
    rows = frappe.get_all(
        REVISION_DOCTYPE,
        filters={"technical_list": technical_list},
        fields=["revision_no"],
        order_by="revision_no desc",
        limit=1,
    )
    return cint(rows[0].revision_no) + 1 if rows else 1


def _latest_revision(technical_list: str, docstatus: int, exclude: str | None = None) -> str | None:
    filters: dict[str, Any] = {"technical_list": technical_list, "docstatus": docstatus}
    if exclude:
        filters["name"] = ["!=", exclude]
    rows = frappe.get_all(
        REVISION_DOCTYPE,
        filters=filters,
        pluck="name",
        order_by="revision_no desc",
        limit=1,
    )
    return rows[0] if rows else None


def _set_parent_open_revision(revision) -> None:
    frappe.db.set_value(
        TECHNICAL_LIST_DOCTYPE,
        revision.technical_list,
        "open_revision",
        revision.name,
        update_modified=False,
    )
    _refresh_parent_summary(revision.technical_list)


def _refresh_parent_summary(technical_list: str) -> None:
    parent = frappe.db.get_value(
        TECHNICAL_LIST_DOCTYPE,
        technical_list,
        ["current_revision", "open_revision"],
        as_dict=True,
    ) or {}
    active_name = parent.get("open_revision") or parent.get("current_revision")
    active = None
    if active_name:
        active = frappe.db.get_value(
            REVISION_DOCTYPE,
            active_name,
            ["docstatus", "workflow_state", "required_annex_count", "completed_annex_count", "is_ready", "readiness_summary"],
            as_dict=True,
        )
    status = "No Revision"
    if active:
        status = active.get("workflow_state") or ("Draft" if cint(active.get("docstatus")) == 0 else "Submitted")
    frappe.db.set_value(
        TECHNICAL_LIST_DOCTYPE,
        technical_list,
        {
            "revision_count": frappe.db.count(REVISION_DOCTYPE, {"technical_list": technical_list, "docstatus": ["<", 2]}),
            "status": status,
            "required_annex_count": cint(active.get("required_annex_count")) if active else 0,
            "completed_annex_count": cint(active.get("completed_annex_count")) if active else 0,
            "is_ready": cint(active.get("is_ready")) if active else 0,
            "readiness_summary": active.get("readiness_summary") if active else "",
        },
        update_modified=False,
    )


def _technical_list_summary(parent) -> dict:
    if not parent:
        return {}
    return {
        "name": parent.name,
        "sales_order": parent.sales_order,
        "company": parent.company,
        "customer": parent.customer or "",
        "project": parent.project or "",
        "business_type": parent.business_type or "",
        "current_revision": parent.current_revision or "",
        "open_revision": parent.open_revision or "",
        "revision_count": cint(parent.revision_count),
        "status": parent.status or "",
        "required_annex_count": cint(parent.required_annex_count),
        "completed_annex_count": cint(parent.completed_annex_count),
        "is_ready": bool(cint(parent.is_ready)),
        "readiness_summary": parent.readiness_summary or "",
    }


def _active_revision_display(parent) -> dict | None:
    revision_name = parent.open_revision or parent.current_revision
    if not revision_name:
        return None
    revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
    revision.check_permission("read")
    template_names = {
        row.name: row.template_name
        for row in frappe.get_all(
            "Orderlift Document Template",
            filters={"name": ["in", sorted({row.template for row in revision.annexes or [] if row.template})]},
            fields=["name", "template_name"],
            limit_page_length=0,
        )
    } if revision.annexes else {}
    return {
        "name": revision.name,
        "revision_no": cint(revision.revision_no),
        "docstatus": cint(revision.docstatus),
        "workflow_state": revision.workflow_state or "",
        "is_current": revision.name == parent.current_revision,
        "is_open": revision.name == parent.open_revision,
        "required_annex_count": cint(revision.required_annex_count),
        "completed_annex_count": cint(revision.completed_annex_count),
        "is_ready": bool(cint(revision.is_ready)),
        "items": [
            {
                "name": row.name,
                "line_key": row.line_key,
                "sales_order_item": row.sales_order_item or "",
                "item_code": row.item_code,
                "item_name": row.item_name or "",
                "sales_order_qty": flt(row.sales_order_qty),
                "execution_qty": flt(row.execution_qty),
                "variance_qty": flt(row.variance_qty),
                "uom": row.uom or "",
                "warehouse": row.warehouse or "",
                "required_date": row.required_date,
                "execution_relevant": bool(cint(row.execution_relevant)),
                "change_type": _derive_item_change_type(row),
            }
            for row in revision.items or []
        ],
        "annexes": [
            {
                "template": row.template,
                "template_name": template_names.get(row.template) or row.template,
                "annex": row.annex or "",
                "source_annex": row.source_annex or "",
                "origin": row.origin or "",
                "status": row.annex_status or "",
                "is_complete": bool(cint(row.is_complete)),
                "required": bool(cint(row.required_for_revision)),
            }
            for row in revision.annexes or []
        ],
    }


def _revision_summary(doc) -> dict:
    readiness = _readiness(doc)
    return {
        "name": doc.name,
        "technical_list": doc.technical_list,
        "sales_order": doc.sales_order,
        "revision_no": cint(doc.revision_no),
        "based_on_revision": doc.based_on_revision or "",
        "docstatus": cint(doc.docstatus),
        "workflow_state": doc.workflow_state or "",
        "source_hash": doc.source_hash or "",
        "approval_hash": doc.approval_hash or "",
        "source_synced_on": doc.source_synced_on,
        "readiness": readiness,
    }


def _downstream_revision_references(revision: str) -> list[dict]:
    links = []
    for row in frappe.get_all(
        "DocField",
        filters={"fieldtype": ["in", ["Link", "Dynamic Link"]]},
        fields=["parent", "fieldname", "fieldtype", "options"],
        limit_page_length=0,
    ):
        links.append({"doctype": row.parent, "fieldname": row.fieldname, "fieldtype": row.fieldtype, "options": row.options})
    for row in frappe.get_all(
        "Custom Field",
        filters={"fieldtype": ["in", ["Link", "Dynamic Link"]]},
        fields=["dt", "fieldname", "fieldtype", "options"],
        limit_page_length=0,
    ):
        links.append({"doctype": row.dt, "fieldname": row.fieldname, "fieldtype": row.fieldtype, "options": row.options})

    references = []
    seen = set()
    for link in links:
        doctype = link["doctype"]
        fieldname = link["fieldname"]
        if (doctype, fieldname) in {
            (TECHNICAL_LIST_DOCTYPE, "current_revision"),
            (TECHNICAL_LIST_DOCTYPE, "open_revision"),
            (ANNEX_DOCTYPE, "reference_name"),
        }:
            continue
        if not frappe.db.exists("DocType", doctype) or not _meta_has_field(doctype, fieldname):
            continue
        filters = {fieldname: revision}
        if link["fieldtype"] == "Link":
            if link["options"] != REVISION_DOCTYPE:
                continue
        else:
            type_field = link["options"]
            if not type_field or not _meta_has_field(doctype, type_field):
                continue
            filters[type_field] = REVISION_DOCTYPE
        meta = frappe.get_meta(doctype)
        if getattr(meta, "is_submittable", False) or _meta_has_field(doctype, "docstatus"):
            filters["docstatus"] = ["<", 2]
        if not frappe.db.table_exists(doctype):
            continue
        rows = frappe.get_all(doctype, filters=filters, fields=["name"], limit=5) or []
        for row in rows:
            key = (doctype, row.name)
            if key not in seen:
                seen.add(key)
                references.append({"doctype": doctype, "name": row.name, "fieldname": fieldname})
    return references


def _lock_parent(technical_list: str) -> None:
    if not technical_list:
        return
    frappe.db.sql(
        f"select name from `tab{TECHNICAL_LIST_DOCTYPE}` where name=%s for update",
        technical_list,
    )


def _is_persisted_revision(doc) -> bool:
    name = _value(doc, "name")
    if not name:
        return False
    try:
        return bool(frappe.db.exists(REVISION_DOCTYPE, name))
    except (AttributeError, TypeError):
        return False


def _meta_has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _value(row, fieldname: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(fieldname, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        value = getter(fieldname)
        return default if value is None else value
    return getattr(row, fieldname, default)


def _children(doc, fieldname: str) -> list:
    value = _value(doc, fieldname, [])
    return value if isinstance(value, (list, tuple)) else []
