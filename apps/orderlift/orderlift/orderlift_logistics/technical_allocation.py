"""Allocation and pool helpers for Sales Order technical lists.

One question, answered per pool: how much of an approved revision line remains?
There are independent pools -- procurement allowance (Material Requests and direct
Purchase Orders) and delivery allowance (Delivery Notes) -- and each adapter in
``technical_procurement`` consumes exactly one of them.

This module must NOT import from ``technical_procurement``: that module imports
from here, and the reverse would be a cycle. ``REVISION_DOCTYPE`` and the small
``_get`` / ``_text`` / ``_meta`` accessors are therefore duplicated here rather
than imported back.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import cint, flt

# Duplicated from technical_procurement to avoid a circular import.
REVISION_DOCTYPE = "Sales Order Technical List Revision"

# Only Material Requests and direct Purchase Orders consume procurement allowance.
# Read by allocated_stock_qty and nothing else: it joins on child.sales_order,
# which only these two child doctypes have. Deliveries have their own pool.
ALLOCATION_ITEM_DOCTYPES = {
    "Material Request": "Material Request Item",
    "Purchase Order": "Purchase Order Item",
}

ADAPTER_POOLS = {
    "revision_to_material_request": "procurement",
    "revision_to_purchase_order": "procurement",
    "revision_to_delivery_note": "delivery",
    "revision_to_pick_list": "picking",
}


def revision_lines(revision):
    return {line.name: line for line in (revision.items or []) if line.name}


def line_stock_qty(line):
    return flt(line.execution_stock_qty)


def row_stock_qty(row):
    return flt(_get(row, "stock_qty")) or flt(_get(row, "qty")) * (
        flt(_get(row, "conversion_factor")) or 1
    )


def allocation_key(row):
    key = _text(_get(row, "sales_order_item"))
    return key or f"item::{_text(_get(row, "item_code"))}"


def remaining_by_line(revision):
    allocated = allocated_stock_qty(revision.name)
    result = {}
    for line in revision.items or []:
        if not cint(line.execution_relevant):
            continue
        result[line.name] = max(line_stock_qty(line) - allocated.get(allocation_key(line), 0), 0)
    return result


def is_root_allocation(doc, row):
    doctype = _text(_get(doc, "doctype"))
    return doctype == "Material Request" or (
        doctype == "Purchase Order" and not _text(_get(row, "material_request_item"))
    )


def allocated_stock_qty(revision_name, *, exclude_doctype="", exclude_name=""):
    revision = frappe.get_doc(REVISION_DOCTYPE, revision_name)
    totals = defaultdict(float)
    for parent_doctype, child_doctype in ALLOCATION_ITEM_DOCTYPES.items():
        meta = _meta(child_doctype)
        if not meta or not meta.get_field("sales_order_item"):
            continue
        fields = ["sales_order_item", "qty"]
        for optional in ("stock_qty", "conversion_factor", "material_request_item", "item_code"):
            if meta.get_field(optional):
                fields.append(optional)
        select = ", ".join(f"child.`{fieldname}`" for fieldname in fields)
        conditions = []
        parameters = [revision.sales_order]
        if parent_doctype == "Purchase Order" and meta.get_field("material_request_item"):
            conditions.append("COALESCE(child.material_request_item, '') = ''")
        if parent_doctype == exclude_doctype and exclude_name:
            conditions.append("parent_doc.name != %s")
            parameters.append(exclude_name)
        extra = "".join(f" AND {condition}" for condition in conditions)
        rows = frappe.db.sql(
            f"""
            SELECT {select}
              FROM `tab{child_doctype}` child
              INNER JOIN `tab{parent_doctype}` parent_doc ON parent_doc.name = child.parent
             WHERE parent_doc.docstatus < 2
               AND child.sales_order = %s{extra}
            """,
            tuple(parameters),
            as_dict=True,
        )
        for row in rows:
            totals[allocation_key(row)] += row_stock_qty(row)
    return totals


def delivered_stock_qty(technical_list, *, exclude_doctype="", exclude_name=""):
    """Stock qty already delivered per allocation key for a whole Technical List.

    Anchored on custom_technical_list rather than the revision: the Technical List
    is stable for the life of the Sales Order while revisions are immutable
    snapshots, so counting per revision would reset delivered totals to zero every
    time engineering approves a new one. It is also anchored on the Technical List
    rather than against_sales_order because engineering additions carry no Sales
    Order link and would otherwise escape the cap entirely.

    Return rows are deliberately NOT excluded. Their qty is negative, so summing
    them credits the quantity back to the delivery pool, which is exactly right: a
    refused delivery leaves the line deliverable again. Do not add an is_return
    filter here -- validate_procurement_document skips returns, this must not.
    """
    totals = defaultdict(float)
    meta = _meta("Delivery Note Item")
    if not meta or not meta.get_field("custom_technical_list"):
        return totals
    conditions = []
    parameters = [technical_list]
    if exclude_doctype == "Delivery Note" and exclude_name:
        conditions.append("parent_doc.name != %s")
        parameters.append(exclude_name)
    extra = "".join(f" AND {condition}" for condition in conditions)
    rows = frappe.db.sql(
        f"""
        SELECT child.so_detail AS sales_order_item,
               child.item_code,
               child.qty,
               child.stock_qty,
               child.conversion_factor
          FROM `tabDelivery Note Item` child
          INNER JOIN `tabDelivery Note` parent_doc ON parent_doc.name = child.parent
         WHERE parent_doc.docstatus < 2
           AND child.custom_technical_list = %s{extra}
        """,
        tuple(parameters),
        as_dict=True,
    )
    for row in rows:
        totals[allocation_key(row)] += row_stock_qty(row)
    return totals


def delivery_budget_by_key(revision):
    """Approved deliverable stock qty per allocation key.

    Summed over the whole revision, not over one document's rows: distinct lines
    can share a key (additions collapse to "item::<item_code>") and the delivered
    pool is keyed the same way, so a per-document budget would shrink the shared
    bucket to a single line's quantity.
    """
    budget = defaultdict(float)
    for line in revision.items or []:
        if not cint(line.execution_relevant):
            continue
        budget[allocation_key(line)] += line_stock_qty(line)
    return budget


def delivery_remaining_by_line(revision):
    """Remaining deliverable stock qty per execution-relevant revision line.

    Both the budget and the delivered pool are keyed by allocation key, and distinct
    lines can share one key, so the shared remainder is apportioned rather than
    subtracted from every line. Apportionment walks the revision's
    execution-relevant lines in order and gives each line up to its own
    execution_stock_qty out of what is left of the bucket: earlier lines fill first,
    and the total handed out for a key equals that key's remainder exactly.
    """
    delivered = delivered_stock_qty(revision.technical_list)
    available = {
        key: max(total - delivered.get(key, 0), 0)
        for key, total in delivery_budget_by_key(revision).items()
    }
    result = {}
    for line in revision.items or []:
        if not cint(line.execution_relevant):
            continue
        key = allocation_key(line)
        share = min(line_stock_qty(line), available.get(key, 0))
        available[key] = available.get(key, 0) - share
        result[line.name] = share
    return result


def remaining_for_adapter(adapter_key, revision, cache):
    """Remaining qty per revision line for the pool the adapter consumes.

    Each pool runs SQL, so results are memoised in the caller's cache dict. An
    unknown adapter falls back to the procurement pool, matching the pre-existing
    default.
    """
    pool = ADAPTER_POOLS.get(adapter_key, "procurement")
    if pool not in cache:
        if pool == "delivery":
            cache[pool] = delivery_remaining_by_line(revision)
        else:
            cache[pool] = remaining_by_line(revision)
    return cache[pool]


# --- tiny accessors, duplicated from technical_procurement to avoid a cycle ---


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


def _meta(doctype):
    if not doctype:
        return None
    try:
        return frappe.get_meta(doctype)
    except Exception:
        return None
