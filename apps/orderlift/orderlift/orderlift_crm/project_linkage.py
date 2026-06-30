"""Keep the Opportunity → Quotation → Sales Order → Project chain stitched together.

A Project carries its originating Opportunity in ``custom_source_opportunity``.
When a Project is created from an Opportunity (or from a Sales Order whose source
opportunity we can resolve), every Sales Order that belongs to the same
opportunity should point back at that Project so delivery/billing/follow-up share
one project context. The propagation runs from both ends so it works regardless
of whether the Project or the Sales Order is created first.

Quotations are *not* hard-linked here — they stay reachable through the shared
opportunity (see ``_project_related_docs`` in ``api/pipeline.py``).
"""

from __future__ import annotations

import frappe

from orderlift.orderlift_crm.api.pipeline import _sales_order_source_opportunity

PROJECT_OPP_FIELD = "custom_source_opportunity"


# ---------------------------------------------------------------------------
# Doc event hooks — wired in hooks.py
# ---------------------------------------------------------------------------

def link_opportunity_family_to_project(doc, method=None) -> None:
    """Project after_insert / on_update: attach the source opportunity's Sales
    Orders to this Project."""
    if method == "on_update" and not doc.has_value_changed(PROJECT_OPP_FIELD):
        return
    opportunity = (doc.get(PROJECT_OPP_FIELD) or "").strip()
    if not opportunity:
        return
    _attach_opportunity_sales_orders(opportunity, doc.name)


def link_sales_order_to_project(doc, method=None) -> None:
    """Sales Order validate: if its source opportunity already has a Project,
    point this order at that Project (when not already set)."""
    if doc.get("custom_installation_project") and doc.get("project"):
        return
    opportunity = _opportunity_from_sales_order_doc(doc)
    if not opportunity:
        return
    project = _project_for_opportunity(opportunity)
    if not project:
        return
    _set_so_project_on_doc(doc, project)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opportunity_from_sales_order_doc(doc) -> str | None:
    """Resolve the source opportunity for an (possibly unsaved) Sales Order.

    Reads the in-memory item rows first (child rows aren't in the DB yet on a new
    doc), then falls back to the DB-based resolver for existing orders.
    """
    quotation_names = {
        (row.get("prevdoc_docname") or "").strip()
        for row in (doc.get("items") or [])
        if row.get("prevdoc_docname")
    }
    for quotation in quotation_names:
        if not quotation:
            continue
        opportunity = frappe.db.get_value("Quotation", quotation, "opportunity")
        if opportunity:
            return opportunity
    if doc.name:
        return _sales_order_source_opportunity(doc.name)
    return None


def _project_for_opportunity(opportunity: str) -> str | None:
    rows = frappe.get_all(
        "Project",
        filters={PROJECT_OPP_FIELD: opportunity},
        fields=["name"],
        order_by="creation asc",
        limit_page_length=1,
    )
    return rows[0].name if rows else None


def _attach_opportunity_sales_orders(opportunity: str, project: str) -> None:
    rows = frappe.db.sql(
        """
        SELECT DISTINCT so.name
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        INNER JOIN `tabQuotation` q ON q.name = soi.prevdoc_docname
        WHERE so.docstatus < 2 AND q.opportunity = %s
          AND (COALESCE(so.project, '') = '' OR COALESCE(so.custom_installation_project, '') = '')
        """,
        (opportunity, ),
        as_dict=True,
    )
    for row in rows:
        _set_so_project_by_name(row.name, project)


def _set_so_project_on_doc(doc, project: str) -> None:
    if doc.meta.get_field("custom_installation_project") and not doc.get("custom_installation_project"):
        doc.custom_installation_project = project
    if doc.meta.get_field("project") and not doc.get("project"):
        doc.project = project


def _set_so_project_by_name(sales_order: str, project: str) -> None:
    current = frappe.db.get_value(
        "Sales Order",
        sales_order,
        ["project", "custom_installation_project"],
        as_dict=True,
    ) or {}
    updates = {}
    if not current.get("custom_installation_project"):
        updates["custom_installation_project"] = project
    if not current.get("project"):
        updates["project"] = project
    if updates:
        frappe.db.set_value("Sales Order", sales_order, updates, update_modified=False)
