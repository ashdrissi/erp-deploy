from __future__ import annotations

import hmac
import json
import re
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from orderlift.orderlift_logistics.technical_allocation import (
    allocated_stock_qty,
    allocation_key,
    budget_by_key,
    delivered_stock_qty,
    is_root_allocation,
    line_stock_qty,
    picked_stock_qty,
    remaining_for_adapter,
    revision_lines,
    row_stock_qty,
)


TECHNICAL_LIST_DOCTYPE = "Sales Order Technical List"
REVISION_DOCTYPE = "Sales Order Technical List Revision"
REVISION_ITEM_DOCTYPE = "Sales Order Technical List Item"

SAFE_ADAPTERS = {
    "revision_to_material_request": "Material Request",
    "revision_to_purchase_order": "Purchase Order",
    "revision_to_delivery_note": "Delivery Note",
    "revision_to_pick_list": "Pick List",
}
SUPPORTED_REFERENCES = {
    "Sales Order",
    TECHNICAL_LIST_DOCTYPE,
    REVISION_DOCTYPE,
}
SUPPORTED_PROCUREMENT_DOCTYPES = (
    "Material Request",
    "Request for Quotation",
    "Supplier Quotation",
    "Purchase Order",
    "Delivery Note",
    "Pick List",
)
PROCUREMENT_ITEM_DOCTYPES = {
    "Material Request": "Material Request Item",
    "Request for Quotation": "Request for Quotation Item",
    "Supplier Quotation": "Supplier Quotation Item",
    "Purchase Order": "Purchase Order Item",
    "Delivery Note": "Delivery Note Item",
    "Pick List": "Pick List Item",
}
# Parent doctype -> child table fieldname. Pick List uses "locations", not "items".
TARGET_CHILD_TABLES = {
    "Material Request": "items",
    "Purchase Order": "items",
    "Delivery Note": "items",
    "Pick List": "locations",
}

# Doctype -> (consumed-pool function name, over-cap message). Both consume the
# approved execution qty but from independent pools, so a pick and its own Delivery
# Note do not double-consume (spec rule 15). Keyed by doctype, distinct from
# technical_allocation.ADAPTER_POOLS which is keyed by adapter.
#
# The pool is held by name and resolved through this module's globals at call time.
# Storing the function object would freeze the binding into the dict, so patching
# delivered_stock_qty or picked_stock_qty on this module -- how the pools are
# substituted in tests, and the only way to see through the imported binding --
# would silently have no effect on the cap.
# Doctypes capped by a consumed-quantity pool rather than by procurement allowance.
# Both draw on the approved execution qty but from independent pools, so a pick and
# the Delivery Note it becomes do not double-consume it (spec rule 15).
POOLED_DOCTYPES = frozenset({"Delivery Note", "Pick List"})

COMPANY_ENABLED_FIELD = "custom_enable_sales_order_technical_lists"
COMPANY_EFFECTIVE_FROM_FIELD = "custom_technical_list_effective_from"
COMPANY_APPLY_ALL_FIELD = "custom_technical_list_apply_all_business_types"
COMPANY_BUSINESS_TYPES_FIELD = "custom_technical_list_business_types"
COMPANY_DEFAULT_ROUTE_FIELD = "custom_technical_list_default_procurement_route"

LINEAGE_FIELDS = {
    "custom_technical_list": "technical_list",
    "custom_technical_revision": "revision",
    "custom_technical_revision_item": "revision_item",
    "custom_technical_line_key": "line_key",
    "custom_technical_approval_hash": "approval_hash",
    "custom_technical_procurement_route": "route",
    "custom_technical_procurement_action": "action",
}
MAX_SELECTED_ROWS = 200


def after_migrate() -> None:
    """Install immutable lineage fields and the safe adapter registry."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    custom_fields = {}
    for target_doctype in PROCUREMENT_ITEM_DOCTYPES.values():
        target_meta = frappe.get_meta(target_doctype)
        anchor = next(
            (
                fieldname
                for fieldname in ("sales_order_item", "material_request_item", "item_code")
                if target_meta.get_field(fieldname)
            ),
            "item_code",
        )
        fields = [
            {
                "fieldname": "custom_technical_lineage_section",
                "label": "Technical List Source",
                "fieldtype": "Section Break",
                "insert_after": anchor,
                "collapsible": 1,
                "read_only": 1,
            }
        ]
        fields.extend(
            [
                {
                    "fieldname": "custom_technical_list",
                    "label": "Technical List",
                    "fieldtype": "Link",
                    "options": TECHNICAL_LIST_DOCTYPE,
                    "insert_after": "custom_technical_lineage_section",
                    "read_only": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_technical_revision",
                    "label": "Technical Revision",
                    "fieldtype": "Link",
                    "options": REVISION_DOCTYPE,
                    "insert_after": "custom_technical_list",
                    "read_only": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_technical_revision_item",
                    "label": "Technical Revision Item",
                    "fieldtype": "Data",
                    "insert_after": "custom_technical_revision",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_technical_line_key",
                    "label": "Technical Line Key",
                    "fieldtype": "Data",
                    "insert_after": "custom_technical_revision_item",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_technical_approval_hash",
                    "label": "Technical Approval Hash",
                    "fieldtype": "Data",
                    "insert_after": "custom_technical_line_key",
                    "read_only": 1,
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_technical_procurement_route",
                    "label": "Technical Procurement Route",
                    "fieldtype": "Link",
                    "options": "Technical Procurement Route",
                    "insert_after": "custom_technical_approval_hash",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_technical_procurement_action",
                    "label": "Technical Procurement Action",
                    "fieldtype": "Link",
                    "options": "Technical Procurement Action",
                    "insert_after": "custom_technical_procurement_route",
                    "read_only": 1,
                },
            ]
        )
        custom_fields[target_doctype] = fields
    create_custom_fields(custom_fields, update=True)
    _ensure_safe_actions()
    _ensure_internal_material_request_route()
    _ensure_ungated_route_steps()


def _ensure_safe_actions() -> None:
    labels = {
        "revision_to_material_request": _("Create Material Request"),
        "revision_to_purchase_order": _("Create Purchase Order"),
        "revision_to_delivery_note": _("Create Delivery Note"),
        "revision_to_pick_list": _("Create Pick List"),
    }
    for sequence, (adapter_key, target_doctype) in enumerate(SAFE_ADAPTERS.items(), 10):
        name = frappe.db.get_value(
            "Technical Procurement Action", {"adapter_key": adapter_key}, "name"
        )
        if name:
            continue
        doc = frappe.new_doc("Technical Procurement Action")
        doc.action_label = labels[adapter_key]
        doc.adapter_key = adapter_key
        doc.target_doctype = target_doctype
        doc.sequence = sequence
        doc.is_active = 1
        doc.insert()


def _ensure_internal_material_request_route() -> str:
    route_name = "Approved Technical List to Material Request"
    action = frappe.db.get_value(
        "Technical Procurement Action",
        {"adapter_key": "revision_to_material_request", "is_active": 1},
        "name",
    )
    if not action:
        return ""
    route = frappe.db.exists("Technical Procurement Route", route_name)
    if route:
        doc = frappe.get_doc("Technical Procurement Route", route)
    else:
        doc = frappe.new_doc("Technical Procurement Route")
        doc.route_name = route_name
    doc.company = ""
    doc.enabled = 1
    other_default = frappe.db.exists(
        "Technical Procurement Route",
        {"enabled": 1, "is_default": 1, "company": ["is", "not set"], "name": ["!=", route_name]},
    )
    doc.is_default = 0 if other_default else 1
    doc.description = _("Internal standard route. Technical List users do not configure this route.")
    doc.set("steps", [])
    doc.append("steps", {"action": action, "sequence": 10})
    doc.save()
    company_meta = _meta("Company")
    if company_meta and company_meta.get_field(COMPANY_DEFAULT_ROUTE_FIELD):
        for company in frappe.get_all(
            "Company",
            filters={COMPANY_DEFAULT_ROUTE_FIELD: ["is", "not set"]},
            pluck="name",
            limit_page_length=0,
        ):
            frappe.db.set_value(
                "Company",
                company,
                COMPANY_DEFAULT_ROUTE_FIELD,
                doc.name,
                update_modified=False,
            )
    return doc.name


UNGATED_ADAPTERS = ("revision_to_delivery_note", "revision_to_pick_list")


def _ensure_ungated_route_steps() -> None:
    """Append the delivery and picking actions to every enabled route that lacks them.

    Both are ungated by design (spec rule 7): stock may already be on hand, so
    neither delivery nor picking must wait on a purchase. A company can set
    required_previous_action on its own route later if it wants procurement first.
    """
    actions = []
    for adapter_key in UNGATED_ADAPTERS:
        action = frappe.db.get_value(
            "Technical Procurement Action",
            {"adapter_key": adapter_key},
            "name",
        )
        if action:
            actions.append(action)
    if not actions:
        return
    routes = frappe.get_all(
        "Technical Procurement Route", filters={"enabled": 1}, pluck="name"
    )
    for route_name in routes:
        route = frappe.get_doc("Technical Procurement Route", route_name)
        changed = False
        for action in actions:
            if any(_text(step.action) == action for step in route.steps or []):
                continue
            sequence = max([cint(step.sequence) for step in route.steps or []] or [0]) + 10
            route.append(
                "steps",
                {"action": action, "sequence": sequence, "required_previous_action": ""},
            )
            changed = True
        if changed:
            route.save()


@frappe.whitelist()
def get_available_actions(reference_doctype: str, reference_name: str) -> dict:
    reference, technical_list, revision = _resolve_current_revision(
        _text(reference_doctype), _text(reference_name)
    )
    if not technical_list or not revision:
        return _action_payload(reference, technical_list, revision, [])

    _validate_revision(revision, technical_list)
    sales_order = frappe.get_doc("Sales Order", revision.sales_order)
    sales_order.check_permission("read")
    if not _technical_policy_applies(sales_order):
        return _action_payload(reference, technical_list, revision, [])

    # Each action is filtered against the pool its own adapter consumes: a line can
    # be fully procured and still undelivered, so filtering the whole payload
    # against the procurement pool would drop procured lines from the delivery
    # action as well. Each pool runs SQL, so both are computed lazily and cached.
    pools = {}

    grouped = {}
    for line in revision.items or []:
        if not cint(line.execution_relevant):
            continue
        route = _route_for_line(revision, line)
        if not route:
            continue
        for step, action in _route_actions(route):
            if remaining_for_adapter(action.adapter_key, revision, pools).get(line.name, 0) <= 0:
                continue
            # A Pick List carries stock rows only (spec rule 14), so a services-only
            # revision must offer no Create Pick List button at all.
            if action.adapter_key == "revision_to_pick_list" and not _is_pickable_line(line):
                continue
            required = _get(step, "required_previous_action")
            if required and not _previous_action_satisfied(revision.name, line.name, required):
                continue
            key = (route.name, action.name)
            entry = grouped.setdefault(
                key,
                {
                    "name": action.name,
                    "label": _get(action, "action_label"),
                    "adapter_key": action.adapter_key,
                    "target_doctype": SAFE_ADAPTERS[action.adapter_key],
                    "sequence": cint(_get(step, "sequence")) or cint(action.sequence),
                    "route": route.name,
                    "row_ids": [],
                    "line_keys": [],
                },
            )
            entry["row_ids"].append(line.name)
            entry["line_keys"].append(line.line_key)

    actions = sorted(
        grouped.values(),
        key=lambda row: (cint(row["sequence"]), row["route"], row["name"]),
    )
    return _action_payload(reference, technical_list, revision, actions)


@frappe.whitelist()
def get_sales_order_gate_status(sales_order: str) -> dict:
    source = frappe.get_doc("Sales Order", _text(sales_order))
    source.check_permission("read")
    applies = _technical_policy_applies(source)
    technical_list = None
    revision = None
    if applies and _technical_schema_ready():
        technical_list_name = frappe.db.get_value(
            TECHNICAL_LIST_DOCTYPE, {"sales_order": source.name}, "name"
        )
        if technical_list_name:
            technical_list = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, technical_list_name)
            if technical_list.current_revision:
                candidate = frappe.get_doc(REVISION_DOCTYPE, technical_list.current_revision)
                try:
                    _validate_revision(candidate, technical_list)
                    revision = candidate
                except Exception:
                    revision = None
    return {
        "applies": applies,
        "approved": bool(revision),
        "technical_list": technical_list.name if technical_list else "",
        "revision": revision.name if revision else "",
        "message": "" if revision or not applies else _no_approved_revision_message("document"),
    }


@frappe.whitelist()
def create_material_request(revision, selected_row_ids=None, quantities=None) -> dict:
    return _create_from_revision(
        "revision_to_material_request",
        revision,
        selected_row_ids,
        quantities,
    )


@frappe.whitelist()
def create_purchase_order(
    revision,
    selected_row_ids=None,
    quantities=None,
    supplier: str | None = None,
) -> dict:
    return _create_from_revision(
        "revision_to_purchase_order",
        revision,
        selected_row_ids,
        quantities,
        supplier=_text(supplier),
    )


@frappe.whitelist()
def create_delivery_note(revision, selected_row_ids=None, quantities=None) -> dict:
    return _create_from_revision(
        "revision_to_delivery_note",
        revision,
        selected_row_ids,
        quantities,
    )


@frappe.whitelist()
def create_pick_list(revision, selected_row_ids=None, quantities=None) -> dict:
    return _create_from_revision(
        "revision_to_pick_list",
        revision,
        selected_row_ids,
        quantities,
    )


def _consumed_stock_qty(doctype, technical_list, *, exclude_doctype="", exclude_name=""):
    """Qty already consumed from the pool this doctype draws on.

    Resolved per call rather than held in a lookup table: a table would capture the
    function object at import time, so patching either pool in a test would no longer
    reach this code path and a cap test could pass while capping nothing.
    """
    pool = delivered_stock_qty if doctype == "Delivery Note" else picked_stock_qty
    return pool(
        technical_list, exclude_doctype=exclude_doctype, exclude_name=exclude_name
    )


def validate_procurement_document(doc, method=None) -> None:
    """Validate technical lineage while leaving unrelated native procurement untouched."""
    doctype = _text(_get(doc, "doctype"))
    if not doc or doctype not in SUPPORTED_PROCUREMENT_DOCTYPES:
        return
    if cint(_get(doc, "docstatus")) == 2:
        return
    # A Sales Return copies the lineage fields (they are not no_copy) onto rows with
    # negative qty, so _validate_target_row would reject every return ever made
    # through this feature with "quantity must be greater than zero".
    # delivery_note_reservation_guard bails on is_return for the same reason.
    if cint(_get(doc, "is_return")):
        return

    # Pick List keeps its rows in "locations": a hardcoded doc.items read would see
    # an empty list and silently validate nothing at all.
    rows = _get(doc, TARGET_CHILD_TABLES.get(doctype, "items")) or []
    linked_rows = []
    for row in rows:
        revision_name = _text(_get(row, "custom_technical_revision"))
        revision_item = _text(_get(row, "custom_technical_revision_item"))
        if _has_technical_lineage(row):
            if not revision_name or not revision_item:
                frappe.throw(
                    _("Row {0}: technical revision and revision item are required.").format(
                        _row_label(row)
                    )
                )
            linked_rows.append((row, revision_name, revision_item))

    if linked_rows and not _technical_schema_ready():
        frappe.throw(_("Sales Order technical-list schema is not installed."))

    revisions = {}
    initial = {}
    for revision_name in sorted({name for _row, name, _item in linked_rows}):
        revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
        revision.check_permission("read")
        initial[revision_name] = revision
    for technical_list in sorted({_text(doc.technical_list) for doc in initial.values()}):
        _lock_document(TECHNICAL_LIST_DOCTYPE, technical_list)
    for revision_name in sorted(initial):
        _lock_document(REVISION_DOCTYPE, revision_name)
        revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
        parent = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, revision.technical_list)
        parent.check_permission("read")
        _validate_revision(revision, parent)
        revisions[revision_name] = revision

    line_totals = defaultdict(float)
    root_totals = defaultdict(float)
    for row in rows:
        revision_name = _text(_get(row, "custom_technical_revision"))
        revision_item = _text(_get(row, "custom_technical_revision_item"))
        if revision_name or revision_item:
            revision = revisions[revision_name]
            source_line = revision_lines(revision).get(revision_item)
            if not source_line:
                frappe.throw(
                    _("Row {0}: the technical revision item does not exist.").format(
                        _row_label(row)
                    )
                )
            _validate_target_row(doc, row, revision, source_line)
            stock_qty = row_stock_qty(row)
            key = (revision_name, revision_item)
            line_totals[key] += stock_qty
            if is_root_allocation(doc, row):
                root_totals[key] += stock_qty
            if line_totals[key] > line_stock_qty(source_line) + 1e-9:
                frappe.throw(
                    _("Row {0}: quantity exceeds the technical revision item.").format(
                        _row_label(row)
                    )
                )
            continue

        source = _procurement_source(doc, row)
        if source and _technical_policy_applies(source):
            _require_current_approved_revision(source, doctype)
            frappe.throw(
                _(
                    "Row {0}: create {1} from the approved Technical List instead of directly from the Sales Order."
                ).format(_row_label(row), doctype)
            )

    # Delivery and picking are each capped by their own pool, not the procurement
    # pool: is_root_allocation is False for both, so the block below would leave
    # them with no cumulative cap at all.
    #
    # Requested quantities are aggregated by allocation key rather than checked per
    # revision line, because distinct lines can share one key: engineering additions
    # collapse to "item::<item_code>". Checking each line separately against the same
    # pool bucket would let one document ship that bucket's whole budget once per
    # line. The budget is likewise the sum over the lines sharing the key -- taken
    # from the whole revision, not from this document's rows, or splitting one
    # delivery into two would shrink the shared bucket to a single line's quantity
    # and block work the cap allows.
    if doctype in POOLED_DOCTYPES:
        consumed_by_list = {}
        budget_by_revision = {}
        requested = defaultdict(float)
        labels = {}
        for (revision_name, revision_item), total in line_totals.items():
            revision = revisions[revision_name]
            technical_list = _text(revision.technical_list)
            if technical_list not in consumed_by_list:
                consumed_by_list[technical_list] = _consumed_stock_qty(
                    doctype,
                    technical_list,
                    exclude_doctype=doctype,
                    exclude_name=_text(_get(doc, "name")),
                )
            if revision_name not in budget_by_revision:
                budget_by_revision[revision_name] = budget_by_key(revision)
            source_line = revision_lines(revision)[revision_item]
            key = (technical_list, revision_name, allocation_key(source_line))
            requested[key] += total
            labels.setdefault(key, _row_label(source_line))
        for key, total in requested.items():
            technical_list, revision_name, alloc_key = key
            existing = consumed_by_list[technical_list].get(alloc_key, 0)
            allowed = budget_by_revision[revision_name].get(alloc_key, 0)
            if existing + total > allowed + 1e-9:
                # Kept as two literal _() calls so the translation extractor finds
                # them; a message held in a table is invisible to it.
                if doctype == "Delivery Note":
                    frappe.throw(
                        _("Row {0}: quantity exceeds the remaining delivery quantity.").format(
                            labels[key]
                        )
                    )
                frappe.throw(
                    _("Row {0}: quantity exceeds the remaining pickable quantity.").format(
                        labels[key]
                    )
                )
        return

    allocated_by_revision = {}
    for revision_name, revision_item in root_totals:
        if revision_name not in allocated_by_revision:
            allocated_by_revision[revision_name] = allocated_stock_qty(
                revision_name,
                exclude_doctype=doctype,
                exclude_name=_text(_get(doc, "name")),
            )
        source_qty = line_stock_qty(revision_lines(revisions[revision_name])[revision_item])
        existing = allocated_by_revision[revision_name].get(revision_item, 0)
        if existing + root_totals[(revision_name, revision_item)] > source_qty + 1e-9:
            frappe.throw(
                _("Technical procurement quantity exceeds the revision item's remaining quantity.")
            )


def validate_operational_document(doc, method=None) -> None:
    """Gate native Pick List and Delivery Note flows on Technical List approval."""
    if not doc or cint(_get(doc, "docstatus")) == 2:
        return
    for row in _get(doc, "items") or _get(doc, "locations") or []:
        sales_order = _operational_sales_order(row)
        if not sales_order:
            continue
        source = frappe.get_doc("Sales Order", sales_order)
        source.check_permission("read")
        if _technical_policy_applies(source):
            _require_current_approved_revision(source, _text(_get(doc, "doctype")))


def _create_from_revision(
    adapter_key,
    revision_name,
    selected_row_ids,
    quantities,
    *,
    supplier="",
):
    if not _technical_schema_ready():
        frappe.throw(_("Sales Order technical-list schema is not installed."))
    target_doctype = SAFE_ADAPTERS[adapter_key]
    frappe.has_permission(target_doctype, "create", throw=True)
    selection = _normalise_selection(selected_row_ids, quantities)
    revision, technical_list, sales_order = _load_locked_revision(_text(revision_name))
    if not _technical_policy_applies(sales_order):
        frappe.throw(_("Technical lists do not apply to this Sales Order."))

    lines = revision_lines(revision)
    missing = sorted(set(selection) - set(lines))
    if missing:
        frappe.throw(_("Unknown technical revision items: {0}.").format(", ".join(missing)))

    selected_lines = [lines[name] for name in selection]
    if adapter_key == "revision_to_pick_list":
        # Services cannot be picked and reach delivery through the Delivery Note
        # instead (spec rule 14). A real revision mixes both, so a service line is
        # dropped rather than rejected -- throwing would make Create Pick List
        # unusable on any realistic revision.
        selected_lines = [line for line in selected_lines if _is_pickable_line(line)]
        if not selected_lines:
            frappe.throw(
                _("None of the selected rows can be picked: only stock items are pickable.")
            )
    route_actions = _adapter_actions_for_lines(revision, selected_lines, adapter_key)
    # Delivery consumes its own pool: a line can be fully procured and still
    # undelivered, and vice versa when stock was already on hand.
    remaining = remaining_for_adapter(adapter_key, revision, {})
    prepared = []
    for line in selected_lines:
        _validate_source_line(revision, line)
        factor = flt(line.conversion_factor)
        requested = selection[line.name]
        requested_stock_qty = (
            flt(requested) * factor if requested is not None else remaining.get(line.name, 0)
        )
        if requested_stock_qty <= 0:
            frappe.throw(_("Row {0} has no remaining quantity.").format(_row_label(line)))
        if requested_stock_qty > remaining.get(line.name, 0) + 1e-9:
            frappe.throw(
                _("Row {0}: requested quantity exceeds the remaining quantity.").format(
                    _row_label(line)
                )
            )
        route, action = route_actions[line.name]
        prepared.append((line, requested_stock_qty, route, action))

    target = _build_target(
        target_doctype,
        revision,
        technical_list,
        sales_order,
        prepared,
        supplier=supplier,
    )
    target.insert()
    if cint(target.docstatus) != 0:
        frappe.throw(_("Technical procurement adapters may only create draft documents."))
    return {
        "doctype": target.doctype,
        "name": target.name,
        "docstatus": cint(target.docstatus),
        "technical_list": technical_list.name,
        "revision": revision.name,
        "routes": sorted({route.name for _line, _qty, route, _action in prepared}),
        "actions": sorted({action.name for _line, _qty, _route, action in prepared}),
    }


def _load_locked_revision(revision_name):
    if not revision_name:
        frappe.throw(_("Select a technical-list revision."))
    revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
    revision.check_permission("read")
    technical_list = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, revision.technical_list)
    technical_list.check_permission("read")

    _lock_document(TECHNICAL_LIST_DOCTYPE, technical_list.name)
    technical_list = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, technical_list.name)
    if technical_list.current_revision != revision_name:
        frappe.throw(_("Only the technical list's current revision can be procured."))
    _lock_document(REVISION_DOCTYPE, revision_name)
    revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
    _validate_revision(revision, technical_list)
    sales_order = frappe.get_doc("Sales Order", revision.sales_order)
    sales_order.check_permission("read")
    return revision, technical_list, sales_order


def _resolve_current_revision(reference_doctype, reference_name):
    if reference_doctype not in SUPPORTED_REFERENCES or not reference_name:
        frappe.throw(
            _("Select a Sales Order, Sales Order Technical List, or Technical List Revision.")
        )
    if reference_doctype != "Sales Order" and not _technical_schema_ready():
        frappe.throw(_("Sales Order technical-list schema is not installed."))
    reference = frappe.get_doc(reference_doctype, reference_name)
    reference.check_permission("read")
    if not _technical_schema_ready():
        return reference, None, None

    if reference_doctype == "Sales Order":
        technical_list_name = frappe.db.get_value(
            TECHNICAL_LIST_DOCTYPE, {"sales_order": reference.name}, "name"
        )
        if not technical_list_name:
            return reference, None, None
        technical_list = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, technical_list_name)
    elif reference_doctype == TECHNICAL_LIST_DOCTYPE:
        technical_list = reference
    else:
        technical_list = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, reference.technical_list)
    technical_list.check_permission("read")

    if not technical_list.current_revision:
        return reference, technical_list, None
    revision = frappe.get_doc(REVISION_DOCTYPE, technical_list.current_revision)
    revision.check_permission("read")
    _validate_revision(revision, technical_list)
    return reference, technical_list, revision


def _validate_revision(revision, technical_list):
    if cint(revision.docstatus) != 1:
        frappe.throw(_("Technical-list revision {0} must be submitted.").format(revision.name))
    if revision.technical_list != technical_list.name:
        frappe.throw(_("Technical revision does not belong to its technical list."))
    if technical_list.current_revision != revision.name:
        frappe.throw(_("Only the technical list's current revision can be procured."))
    for fieldname in ("sales_order", "company", "project", "business_type"):
        if _text(_get(revision, fieldname)) != _text(_get(technical_list, fieldname)):
            frappe.throw(
                _("Technical revision field {0} does not match its technical list.").format(
                    fieldname
                )
            )
    sales_order = frappe.get_doc("Sales Order", revision.sales_order)
    sales_order.check_permission("read")
    if cint(sales_order.docstatus) != 1:
        frappe.throw(_("The technical revision Sales Order must remain submitted."))
    expected_business_type = _source_business_type(sales_order)
    for fieldname, expected in (
        ("company", sales_order.company),
        ("project", _get(sales_order, "project")),
        ("business_type", expected_business_type),
    ):
        if _text(_get(revision, fieldname)) != _text(expected):
            frappe.throw(
                _("Technical revision field {0} does not match its Sales Order.").format(
                    fieldname
                )
            )
    if not revision.approval_hash:
        frappe.throw(_("The submitted technical revision has no approval hash."))
    expected_hash = _recalculate_approval_hash(revision)
    if expected_hash is not None and not hmac.compare_digest(
        _text(revision.approval_hash), _text(expected_hash)
    ):
        frappe.throw(_("The technical revision approval hash is no longer valid."))


def _require_current_approved_revision(source, target_doctype: str):
    technical_list_name = frappe.db.get_value(
        TECHNICAL_LIST_DOCTYPE, {"sales_order": source.name}, "name"
    ) if _technical_schema_ready() else ""
    if not technical_list_name:
        frappe.throw(_no_approved_revision_message(target_doctype))
    technical_list = frappe.get_doc(TECHNICAL_LIST_DOCTYPE, technical_list_name)
    if not technical_list.current_revision:
        frappe.throw(_no_approved_revision_message(target_doctype))
    revision = frappe.get_doc(REVISION_DOCTYPE, technical_list.current_revision)
    try:
        _validate_revision(revision, technical_list)
    except Exception:
        frappe.throw(_no_approved_revision_message(target_doctype))
    return revision


def _no_approved_revision_message(target_doctype: str) -> str:
    label = target_doctype if target_doctype and target_doctype != "document" else _("this document")
    return _("No approved Technical List yet. Submit the Technical List before creating {0}.").format(label)


def _recalculate_approval_hash(revision):
    try:
        from orderlift.orderlift_sig import technical_list as technical_list_core
    except ImportError:
        return None
    helper = getattr(technical_list_core, "_approval_hash", None)
    if not callable(helper):
        return None
    return helper(revision)


def _technical_policy_applies(source):
    company = _text(_get(source, "company"))
    if not company:
        return False
    company_meta = _meta("Company")
    if not company_meta or not company_meta.get_field(COMPANY_ENABLED_FIELD):
        return False
    if not cint(frappe.db.get_value("Company", company, COMPANY_ENABLED_FIELD)):
        return False

    effective_from = ""
    if company_meta.get_field(COMPANY_EFFECTIVE_FROM_FIELD):
        effective_from = _text(
            frappe.db.get_value("Company", company, COMPANY_EFFECTIVE_FROM_FIELD)
        )
    source_date = _source_date(source)
    if effective_from and (not source_date or getdate(source_date) < getdate(effective_from)):
        return False

    apply_all = bool(
        company_meta.get_field(COMPANY_APPLY_ALL_FIELD)
        and cint(frappe.db.get_value("Company", company, COMPANY_APPLY_ALL_FIELD))
    )
    if apply_all:
        return True

    business_type = _source_business_type(source)
    if not business_type or not company_meta.get_field(COMPANY_BUSINESS_TYPES_FIELD):
        return False
    company_doc = frappe.get_doc("Company", company)
    configured = {
        _text(_get(row, "business_type"))
        for row in (_get(company_doc, COMPANY_BUSINESS_TYPES_FIELD) or [])
        if _text(_get(row, "business_type"))
    }
    return business_type in configured


def _source_date(source):
    for fieldname in ("transaction_date", "expected_start_date", "start_date", "creation"):
        value = _get(source, fieldname)
        if value:
            return value
    return None


def _source_business_type(source):
    return _text(
        _get(source, "custom_crm_business_type") or _get(source, "business_type")
    )


def _route_for_line(revision, line):
    requested = _text(line.procurement_route) or _company_default_route(revision.company)
    return _effective_route(revision.company, requested)


def _company_default_route(company):
    meta = _meta("Company")
    if not meta or not meta.get_field(COMPANY_DEFAULT_ROUTE_FIELD):
        return ""
    return _text(frappe.db.get_value("Company", company, COMPANY_DEFAULT_ROUTE_FIELD))


def _effective_route(company, requested=""):
    if not _doctype_exists("Technical Procurement Route"):
        return None
    if requested:
        route = frappe.get_doc("Technical Procurement Route", requested)
        if not cint(route.enabled):
            return None
        if route.company and route.company != company:
            return None
        return route

    rows = frappe.get_all(
        "Technical Procurement Route",
        filters={"enabled": 1, "is_default": 1},
        fields=["name", "company"],
        order_by="modified desc",
        limit_page_length=0,
    )
    candidates = [row for row in rows if not _get(row, "company") or row.company == company]
    candidates.sort(key=lambda row: (0 if _get(row, "company") == company else 1, row.name))
    return frappe.get_doc("Technical Procurement Route", candidates[0].name) if candidates else None


def _route_actions(route):
    action_names = [_text(_get(step, "action")) for step in (route.steps or [])]
    action_names = [name for name in action_names if name]
    if not action_names:
        return []
    rows = frappe.get_all(
        "Technical Procurement Action",
        filters={"name": ["in", action_names], "is_active": 1},
        fields=["name", "action_label", "adapter_key", "target_doctype", "sequence"],
        limit_page_length=0,
    )
    actions = {
        row.name: row
        for row in rows
        if row.adapter_key in SAFE_ADAPTERS
        and row.target_doctype == SAFE_ADAPTERS[row.adapter_key]
        and _lineage_schema_ready(row.target_doctype)
    }
    steps = sorted(route.steps or [], key=lambda row: (cint(row.sequence), cint(row.idx)))
    return [(step, actions[step.action]) for step in steps if step.action in actions]


def _adapter_actions_for_lines(revision, lines, adapter_key):
    result = {}
    for line in lines:
        route = _route_for_line(revision, line)
        if not route:
            frappe.throw(
                _("Row {0} has no enabled technical procurement route.").format(
                    _row_label(line)
                )
            )
        selected = None
        for step, action in _route_actions(route):
            if action.adapter_key != adapter_key:
                continue
            required = _get(step, "required_previous_action")
            if required and not _previous_action_satisfied(revision.name, line.name, required):
                frappe.throw(
                    _("Row {0} has not completed its required previous action.").format(
                        _row_label(line)
                    )
                )
            selected = action
            break
        if not selected:
            frappe.throw(
                _("The effective route does not enable this action for row {0}.").format(
                    _row_label(line)
                )
            )
        result[line.name] = (route, selected)
    return result


def _previous_action_satisfied(revision_name, revision_item, action_name):
    adapter_key = frappe.db.get_value("Technical Procurement Action", action_name, "adapter_key")
    target_doctype = SAFE_ADAPTERS.get(adapter_key)
    if not target_doctype:
        return False
    child_doctype = PROCUREMENT_ITEM_DOCTYPES.get(target_doctype)
    if not child_doctype:
        return False
    meta = _meta(child_doctype)
    if not meta or not all(
        meta.get_field(fieldname)
        for fieldname in (
            "custom_technical_revision",
            "custom_technical_revision_item",
            "custom_technical_procurement_action",
        )
    ):
        return False
    rows = frappe.db.sql(
        f"""
        SELECT child.name
          FROM `tab{child_doctype}` child
          INNER JOIN `tab{target_doctype}` parent_doc ON parent_doc.name = child.parent
         WHERE parent_doc.docstatus < 2
           AND child.custom_technical_revision = %s
           AND child.custom_technical_revision_item = %s
           AND child.custom_technical_procurement_action = %s
         LIMIT 1
        """,
        (revision_name, revision_item, action_name),
    )
    return bool(rows)


def _build_target(
    target_doctype,
    revision,
    technical_list,
    sales_order,
    prepared,
    *,
    supplier="",
):
    target = frappe.new_doc(target_doctype)
    schedule_dates = [_safe_schedule_date(line.required_date) for line, _qty, _route, _action in prepared]
    schedule_dates = [value for value in schedule_dates if value]
    schedule_date = max(schedule_dates) if schedule_dates else nowdate()
    values = {
        "company": revision.company,
        "project": revision.project,
        "transaction_date": nowdate(),
        "schedule_date": schedule_date,
        "material_request_type": "Purchase",
    }
    if target_doctype == "Purchase Order":
        supplier = supplier or _single_line_supplier(prepared)
        if not supplier or not frappe.db.exists("Supplier", supplier):
            frappe.throw(_("Select a valid Supplier for the direct Purchase Order."))
        supplier_doc = frappe.get_doc("Supplier", supplier)
        supplier_doc.check_permission("read")
        supplier_meta = getattr(supplier_doc, "meta", None)
        if supplier_meta and supplier_meta.get_field("custom_company"):
            supplier_company = _text(_get(supplier_doc, "custom_company"))
            if supplier_company and supplier_company != revision.company:
                frappe.throw(_("Supplier does not belong to the technical revision company."))
        values["supplier"] = supplier
    if target_doctype == "Delivery Note":
        customer = _text(_get(sales_order, "customer"))
        if not customer:
            frappe.throw(_("The Sales Order has no Customer."))
        values["customer"] = customer
        values["posting_date"] = nowdate()
    if target_doctype == "Pick List":
        customer = _text(_get(sales_order, "customer"))
        if not customer:
            frappe.throw(_("The Sales Order has no Customer."))
        values["customer"] = customer
        # pick_list_reservation and pick_list_override both early-return on any
        # other purpose, so a technical Pick List must be a Delivery one.
        values["purpose"] = "Delivery"
    _set_known_fields(target, values)

    item_meta = _meta(PROCUREMENT_ITEM_DOCTYPES.get(target_doctype))
    for line, stock_qty, route, action in prepared:
        lineage = {
            "technical_list": technical_list.name,
            "revision": revision.name,
            "revision_item": line.name,
            "line_key": line.line_key,
            "approval_hash": revision.approval_hash,
            "route": route.name,
            "action": action.name,
        }
        if target_doctype == "Delivery Note":
            row_values = _delivery_row_values(revision, line, stock_qty)
        elif target_doctype == "Pick List":
            row_values = _pick_list_row_values(revision, line, stock_qty)
        else:
            row_values = _procurement_row_values(revision, line, stock_qty, schedule_date)
        row_values.update(_lineage_values(item_meta, lineage))
        target.append(TARGET_CHILD_TABLES[target_doctype], _filter_fields(item_meta, row_values))
    return target


def _procurement_row_values(revision, line, stock_qty, schedule_date):
    factor = flt(line.conversion_factor)
    return {
        "item_code": line.item_code,
        "item_name": line.item_name,
        "description": line.description,
        "qty": stock_qty / factor,
        "stock_qty": stock_qty,
        "uom": line.uom,
        "conversion_factor": factor,
        "stock_uom": line.stock_uom,
        "warehouse": line.warehouse,
        "schedule_date": _safe_schedule_date(line.required_date or schedule_date),
        "project": revision.project,
        "sales_order": revision.sales_order,
        "sales_order_item": line.sales_order_item,
    }


def _delivery_row_values(revision, line, stock_qty):
    """Delivery Note Item row for one revision line.

    against_sales_order/so_detail are the Delivery Note's equivalents of
    sales_order/sales_order_item and are what native delivered-qty tracking reads.
    Engineering additions have no Sales Order line, so both stay empty and the row
    can never reach an invoice.

    The contract rate is copied from the Sales Order Item rather than left for
    ERPNext's set_missing_values to fetch: otherwise the bon de livraison prints the
    current price list rate instead of what was actually sold, and any negotiated
    discount reads as a rate mismatch to the price-list usage guard. Additions carry
    zero -- they are absorbed, never billed, so any other value would mislead.
    """
    factor = flt(line.conversion_factor)
    sales_order_item = _text(line.sales_order_item)
    pricing = {"rate": 0, "price_list_rate": 0}
    if sales_order_item:
        source = frappe.db.get_value(
            "Sales Order Item",
            sales_order_item,
            ["rate", "price_list_rate", "discount_percentage", "discount_amount"],
            as_dict=True,
        )
        if source:
            pricing = {
                "rate": flt(_get(source, "rate")),
                "price_list_rate": flt(_get(source, "price_list_rate")),
                "discount_percentage": flt(_get(source, "discount_percentage")),
                "discount_amount": flt(_get(source, "discount_amount")),
            }
    return {
        "item_code": line.item_code,
        "item_name": line.item_name,
        "description": line.description,
        "qty": stock_qty / factor,
        "stock_qty": stock_qty,
        "uom": line.uom,
        "conversion_factor": factor,
        "stock_uom": line.stock_uom,
        "warehouse": line.warehouse,
        "project": revision.project,
        "against_sales_order": _text(revision.sales_order) if sales_order_item else "",
        "so_detail": sales_order_item,
        **pricing,
    }


def _pick_list_row_values(revision, line, stock_qty):
    """Pick List Item row for one revision line.

    Pick List Item uses sales_order/sales_order_item like the procurement doctypes,
    and has no project field. Engineering additions carry no Sales Order line, so
    both stay empty -- pick_list_override only caps rows that have one, which is
    what lets an addition be picked at all.
    """
    factor = flt(line.conversion_factor)
    sales_order_item = _text(line.sales_order_item)
    return {
        "item_code": line.item_code,
        "item_name": line.item_name,
        "description": line.description,
        "qty": stock_qty / factor,
        "stock_qty": stock_qty,
        "uom": line.uom,
        "conversion_factor": factor,
        "stock_uom": line.stock_uom,
        "warehouse": line.warehouse,
        "sales_order": _text(revision.sales_order) if sales_order_item else "",
        "sales_order_item": sales_order_item,
    }


def _is_pickable_line(line):
    """Only stock items can be picked (spec rule 14).

    Pick List Item has no is_stock_item field, so pickability comes from the revision
    line, falling back to the Item master when the cached flag is unset.
    """
    value = _get(line, "is_stock_item")
    if value is not None and value != "":
        return bool(cint(value))
    return bool(cint(frappe.db.get_value("Item", _text(line.item_code), "is_stock_item")))


def _single_line_supplier(prepared):
    suppliers = {_text(_get(line, "supplier")) for line, _qty, _route, _action in prepared}
    suppliers.discard("")
    return next(iter(suppliers)) if len(suppliers) == 1 else ""


def _safe_schedule_date(value):
    if not value:
        return getdate(nowdate())
    return max(getdate(value), getdate(nowdate()))


def _validate_source_line(revision, line):
    if not cint(line.execution_relevant):
        frappe.throw(_("Row {0} is not execution relevant.").format(_row_label(line)))
    item_code = _text(line.item_code)
    item = frappe.db.get_value(
        "Item", item_code, ["name", "stock_uom", "is_stock_item", "disabled"], as_dict=True
    )
    if not item or cint(_get(item, "disabled")):
        frappe.throw(_("Row {0}: select an enabled Item.").format(_row_label(line)))
    if _text(line.stock_uom) != _text(_get(item, "stock_uom")):
        frappe.throw(_("Row {0}: Stock UOM must match the Item.").format(_row_label(line)))
    if not line.uom or not frappe.db.exists("UOM", line.uom) or flt(line.conversion_factor) <= 0:
        frappe.throw(
            _("Row {0}: select a valid UOM and conversion factor.").format(_row_label(line))
        )
    expected_stock_qty = flt(line.execution_qty) * flt(line.conversion_factor)
    if flt(line.execution_qty) <= 0 or abs(flt(line.execution_stock_qty) - expected_stock_qty) > 1e-9:
        frappe.throw(_("Row {0}: execution quantity is inconsistent.").format(_row_label(line)))
    _validate_warehouse(line.warehouse, revision.company, bool(cint(_get(item, "is_stock_item"))), line)
    if line.sales_order_item:
        source = frappe.db.get_value(
            "Sales Order Item",
            line.sales_order_item,
            ["parent", "item_code", "qty"],
            as_dict=True,
        ) or {}
        if source.get("parent") != revision.sales_order or source.get("item_code") != item_code:
            frappe.throw(_("Row {0}: Sales Order item does not match.").format(_row_label(line)))
        if abs(flt(line.sales_order_qty) - flt(source.get("qty"))) > 1e-9:
            frappe.throw(
                _("Row {0}: Sales Order quantity does not match.").format(_row_label(line))
            )
    elif flt(line.sales_order_qty):
        frappe.throw(
            _("Row {0}: added items cannot have a Sales Order quantity.").format(
                _row_label(line)
            )
        )


def _validate_target_row(doc, row, revision, source_line):
    _validate_source_line(revision, source_line)
    row_meta = getattr(row, "meta", None) or _meta(
        PROCUREMENT_ITEM_DOCTYPES[_text(_get(doc, "doctype"))]
    )
    expected = {
        "technical_list": revision.technical_list,
        "revision": revision.name,
        "revision_item": source_line.name,
        "line_key": source_line.line_key,
        "approval_hash": revision.approval_hash,
    }
    for fieldname, value_key in LINEAGE_FIELDS.items():
        if value_key in expected and row_meta and row_meta.get_field(fieldname):
            if _text(_get(row, fieldname)) != _text(expected[value_key]):
                frappe.throw(
                    _("Row {0}: {1} does not match the approved technical revision.").format(
                        _row_label(row), fieldname
                    )
                )
    for fieldname in (
        "custom_technical_procurement_route",
        "custom_technical_procurement_action",
    ):
        if row_meta and row_meta.get_field(fieldname) and not _text(_get(row, fieldname)):
            frappe.throw(_("Row {0}: technical route and action are required.").format(_row_label(row)))

    if _text(_get(doc, "company")) != _text(revision.company):
        frappe.throw(_("Row {0}: company does not match the technical revision.").format(_row_label(row)))
    if _text(_get(row, "item_code")) != _text(source_line.item_code):
        frappe.throw(_("Row {0}: Item does not match the technical revision item.").format(_row_label(row)))
    if _text(_get(row, "uom")) != _text(source_line.uom):
        frappe.throw(_("Row {0}: UOM does not match the technical revision item.").format(_row_label(row)))
    if abs((flt(_get(row, "conversion_factor")) or 1) - flt(source_line.conversion_factor)) > 1e-9:
        frappe.throw(
            _("Row {0}: conversion factor does not match the technical revision item.").format(
                _row_label(row)
            )
        )
    if _text(_get(row, "stock_uom")) != _text(source_line.stock_uom):
        frappe.throw(_("Row {0}: Stock UOM does not match the technical revision item.").format(_row_label(row)))
    if row_stock_qty(row) <= 0:
        frappe.throw(_("Row {0}: quantity must be greater than zero.").format(_row_label(row)))

    is_stock_item = bool(cint(frappe.db.get_value("Item", source_line.item_code, "is_stock_item")))
    if is_stock_item and _text(_get(row, "warehouse")) != _text(source_line.warehouse):
        frappe.throw(_("Row {0}: Warehouse does not match the technical revision item.").format(_row_label(row)))
    if not is_stock_item and _text(_get(row, "warehouse")) and _text(
        _get(row, "warehouse")
    ) != _text(source_line.warehouse):
        frappe.throw(
            _("Row {0}: Warehouse does not match the technical revision item.").format(
                _row_label(row)
            )
        )
    project = _target_project(doc, row)
    # Scoped to doctypes that actually have the field: skipping the check for any
    # empty value would let a cleared project through on Material Request, Purchase
    # Order and Delivery Note, which all carry it. Only a genuinely fieldless target
    # is tolerated.
    if revision.project and project != revision.project and _target_has_project_field(doc, row_meta):
        frappe.throw(_("Row {0}: Project does not match the technical revision.").format(_row_label(row)))
    sales_order = _target_sales_order(row)
    if sales_order and sales_order != revision.sales_order:
        frappe.throw(_("Row {0}: Sales Order does not match the technical revision.").format(_row_label(row)))


def _target_has_project_field(doc, row_meta):
    """Whether the target carries a project field on its row or its parent."""
    if row_meta and row_meta.get_field("project"):
        return True
    doctype = _text(_get(doc, "doctype"))
    parent_meta = getattr(doc, "meta", None) or _meta(doctype)
    if parent_meta and parent_meta.get_field("project"):
        return True
    child_meta = _meta(PROCUREMENT_ITEM_DOCTYPES.get(doctype))
    return bool(child_meta and child_meta.get_field("project"))


def _validate_warehouse(warehouse, company, required, row):
    warehouse = _text(warehouse)
    if required and not warehouse:
        frappe.throw(_("Row {0}: Warehouse is required for stock items.").format(_row_label(row)))
    if not warehouse:
        return
    warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
    if not warehouse_company or warehouse_company != company:
        frappe.throw(_("Row {0}: Warehouse must belong to the revision company.").format(_row_label(row)))


def _procurement_source(doc, row):
    sales_order = _target_sales_order(row)
    if sales_order:
        source = frappe.get_doc("Sales Order", sales_order)
        source.check_permission("read")
        return source
    project = _text(_get(row, "project")) or _text(_get(doc, "project"))
    if project:
        source = frappe.get_doc("Project", project)
        source.check_permission("read")
        return source
    return None


def _target_sales_order(row):
    # Delivery Note Item uses against_sales_order/so_detail; the procurement
    # doctypes use sales_order/sales_order_item. _operational_sales_order already
    # normalises both, so delegate rather than duplicating the fallbacks.
    sales_order = _operational_sales_order(row)
    if sales_order:
        return sales_order
    material_request_item = _text(_get(row, "material_request_item"))
    if material_request_item:
        meta = _meta("Material Request Item")
        fields = [name for name in ("sales_order", "sales_order_item") if meta and meta.get_field(name)]
        source = (
            frappe.db.get_value("Material Request Item", material_request_item, fields, as_dict=True)
            if fields
            else None
        ) or {}
        sales_order = _text(source.get("sales_order"))
        if not sales_order and source.get("sales_order_item"):
            sales_order = _text(
                frappe.db.get_value("Sales Order Item", source.get("sales_order_item"), "parent")
            )
    return sales_order


def _operational_sales_order(row):
    sales_order = _text(_get(row, "sales_order")) or _text(_get(row, "against_sales_order"))
    sales_order_item = _text(_get(row, "sales_order_item")) or _text(_get(row, "so_detail"))
    if not sales_order and sales_order_item:
        sales_order = _text(frappe.db.get_value("Sales Order Item", sales_order_item, "parent"))
    return sales_order


def _target_project(doc, row):
    project = _text(_get(row, "project")) or _text(_get(doc, "project"))
    material_request_item = _text(_get(row, "material_request_item"))
    if not project and material_request_item:
        meta = _meta("Material Request Item")
        if meta and meta.get_field("project"):
            project = _text(
                frappe.db.get_value("Material Request Item", material_request_item, "project")
            )
    return project


def _normalise_selection(selected_row_ids, quantities=None):
    selected = _parse_json(selected_row_ids)
    parsed_quantities = _parse_json(quantities)
    embedded = {}
    if isinstance(selected, dict):
        embedded = selected
        selected = list(selected)
    elif isinstance(selected, list) and selected and isinstance(selected[0], dict):
        embedded = {
            _text(row.get("row_id") or row.get("name")): row.get("qty") for row in selected
        }
        selected = list(embedded)
    elif not isinstance(selected, (list, tuple)):
        selected = [selected] if selected else []
    names = [_text(name) for name in selected if _text(name)]
    if not names:
        frappe.throw(_("Select at least one technical revision item."))
    if len(names) > MAX_SELECTED_ROWS:
        frappe.throw(_("Select no more than {0} rows.").format(MAX_SELECTED_ROWS))
    if len(names) != len(set(names)):
        frappe.throw(_("A technical revision item cannot be selected twice."))

    quantity_map = embedded
    if isinstance(parsed_quantities, dict):
        quantity_map = parsed_quantities
    elif isinstance(parsed_quantities, (list, tuple)):
        if len(parsed_quantities) != len(names):
            frappe.throw(_("Quantities must match the selected rows."))
        quantity_map = dict(zip(names, parsed_quantities))
    result = {}
    for name in names:
        value = quantity_map.get(name) if isinstance(quantity_map, dict) else None
        if value in (None, ""):
            result[name] = None
            continue
        value = flt(value)
        if value <= 0:
            frappe.throw(_("Selected quantities must be greater than zero."))
        result[name] = value
    return result


def _has_technical_lineage(row):
    return any(_text(_get(row, fieldname)) for fieldname in LINEAGE_FIELDS)


def _lineage_values(meta, values):
    if not meta:
        return {}
    return {
        fieldname: values[value_key]
        for fieldname, value_key in LINEAGE_FIELDS.items()
        if meta.get_field(fieldname) and values.get(value_key) not in (None, "")
    }


def _lineage_schema_ready(target_doctype):
    meta = _meta(PROCUREMENT_ITEM_DOCTYPES.get(target_doctype))
    return bool(
        meta
        and meta.get_field("custom_technical_revision")
        and meta.get_field("custom_technical_revision_item")
    )


def _set_known_fields(doc, values):
    for fieldname, value in values.items():
        if value not in (None, "") and doc.meta.get_field(fieldname):
            doc.set(fieldname, value)


def _filter_fields(meta, values):
    return {
        fieldname: value
        for fieldname, value in values.items()
        if meta and meta.get_field(fieldname) and value is not None
    }


def _lock_document(doctype, name):
    if not name or not _doctype_exists(doctype):
        frappe.throw(_("Technical-list schema is not installed."))
    if not re.fullmatch(r"[A-Za-z0-9 _-]+", doctype):
        frappe.throw(_("Invalid technical-list document type."))
    rows = frappe.db.sql(
        f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE",
        (name,),
    )
    if not rows:
        frappe.throw(_("Technical-list source {0} does not exist.").format(name))


def _doctype_exists(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _technical_schema_ready():
    return _doctype_exists(TECHNICAL_LIST_DOCTYPE) and _doctype_exists(REVISION_DOCTYPE)


def _meta(doctype):
    if not doctype:
        return None
    try:
        return frappe.get_meta(doctype)
    except Exception:
        return None


def _parse_json(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        frappe.throw(_("Invalid technical procurement selection."))


def _get(doc, fieldname, default=None):
    if isinstance(doc, dict):
        return doc.get(fieldname, default)
    getter = getattr(doc, "get", None)
    if getter:
        value = getter(fieldname)
        return default if value is None else value
    return getattr(doc, fieldname, default)


def _text(value):
    return str(value or "").strip()


def _row_label(row):
    return _get(row, "idx") or _get(row, "name") or "?"


def _action_payload(reference, technical_list, revision, actions):
    routes = sorted({row["route"] for row in actions})
    return {
        "reference_doctype": reference.doctype,
        "reference_name": reference.name,
        "sales_order": technical_list.sales_order if technical_list else "",
        "technical_list": technical_list.name if technical_list else "",
        "revision": revision.name if revision else "",
        "approval_hash": revision.approval_hash if revision else "",
        "route": routes[0] if len(routes) == 1 else "",
        "routes": routes,
        "actions": actions,
    }
