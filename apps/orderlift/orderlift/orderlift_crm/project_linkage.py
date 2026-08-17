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

from orderlift.menu_access import user_can_access_company

PROJECT_OPP_FIELD = "custom_source_opportunity"


def sync_project_source_context(doc, method=None) -> None:
    sales_order = (doc.get("sales_order") or "").strip()
    opportunity = (doc.get(PROJECT_OPP_FIELD) or "").strip()
    if sales_order and not opportunity:
        opportunity = sales_order_source_opportunity(sales_order) or ""
        if opportunity and doc.meta.get_field(PROJECT_OPP_FIELD):
            doc.set(PROJECT_OPP_FIELD, opportunity)

    source = frappe.get_doc("Sales Order", sales_order) if sales_order and frappe.db.exists("Sales Order", sales_order) else None
    if not source and opportunity and frappe.db.exists("Opportunity", opportunity):
        source = frappe.get_doc("Opportunity", opportunity)
    if not source:
        return
    _copy_source_context_to_project(source, doc)


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
    if doc.get("project"):
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
    opportunities = set()
    direct = (doc.get("opportunity") or "").strip()
    if direct:
        opportunities.add(direct)
    quotation_names = {
        (row.get("prevdoc_docname") or "").strip()
        for row in (doc.get("items") or [])
        if row.get("prevdoc_docname")
    }
    for quotation in sorted(quotation_names):
        opportunity = frappe.db.get_value("Quotation", quotation, "opportunity")
        if opportunity:
            opportunities.add(opportunity)
    if not opportunities and not quotation_names and getattr(doc, "name", None):
        opportunities.update(_sales_order_opportunities(doc.name))
    return _require_single_opportunity(opportunities, getattr(doc, "name", None) or "new Sales Order")


def sales_order_source_opportunity(sales_order: str | None) -> str | None:
    if not sales_order:
        return None
    return _require_single_opportunity(_sales_order_opportunities(sales_order), sales_order)


def _sales_order_opportunities(sales_order: str) -> set[str]:
    opportunities = set()
    if frappe.db.exists("DocType", "Quotation"):
        rows = frappe.db.sql(
            """
            SELECT DISTINCT q.opportunity
            FROM `tabSales Order Item` soi
            INNER JOIN `tabQuotation` q ON q.name = soi.prevdoc_docname
            WHERE soi.parent = %s
              AND COALESCE(q.opportunity, '') != ''
            """,
            (sales_order,),
            as_dict=True,
        )
        opportunities.update(row.get("opportunity") for row in rows if row.get("opportunity"))
    if _has_field("Sales Order", "opportunity"):
        direct = frappe.db.get_value("Sales Order", sales_order, "opportunity")
        if direct:
            opportunities.add(direct)
    return opportunities


def _require_single_opportunity(opportunities: set[str], sales_order: str) -> str | None:
    if len(opportunities) > 1:
        frappe.throw(
            frappe._("Sales Order {0} has conflicting source Opportunities: {1}").format(
                sales_order, ", ".join(sorted(opportunities))
            )
        )
    return next(iter(opportunities)) if opportunities else None


def _project_for_opportunity(opportunity: str) -> str | None:
    rows = frappe.get_all(
        "Project",
        filters={PROJECT_OPP_FIELD: opportunity},
        fields=["name"],
        order_by="creation asc",
        limit_page_length=2,
    )
    if len(rows) > 1:
        frappe.throw(
            frappe._("Opportunity {0} is linked to multiple Projects: {1}").format(
                opportunity, ", ".join(row.name for row in rows)
            )
        )
    return rows[0].name if rows else None


def opportunity_sales_orders(opportunity: str, include_cancelled: bool = False) -> list[dict]:
    direct_condition = ""
    if _has_field("Sales Order", "opportunity"):
        direct_condition = "OR so.opportunity = %(opportunity)s"
    cancelled_condition = "" if include_cancelled else "AND so.docstatus < 2"
    return frappe.db.sql(
        f"""
        SELECT DISTINCT so.name, so.project, so.company, so.customer, so.docstatus
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Order Item` soi ON soi.parent = so.name
        LEFT JOIN `tabQuotation` q ON q.name = soi.prevdoc_docname
        WHERE ((q.opportunity = %(opportunity)s AND q.docstatus < 2) {direct_condition})
          {cancelled_condition}
        ORDER BY so.name
        """,
        {"opportunity": opportunity},
        as_dict=True,
    )


def project_opportunity_families(project: str) -> set[str]:
    rows = frappe.db.sql(
        """
        SELECT so.name
        FROM `tabSales Order` so
        WHERE so.docstatus < 2 AND so.project = %s
        ORDER BY so.name
        """,
        (project,),
        as_dict=True,
    )
    return {
        opportunity
        for row in rows
        for opportunity in [sales_order_source_opportunity(row.get("name"))]
        if opportunity
    }


def assert_project_opportunity_family(project: str, opportunity: str) -> None:
    families = project_opportunity_families(project)
    if len(families) > 1:
        frappe.throw(
            frappe._("Project {0} is already shared by mixed Opportunity families: {1}").format(
                project, ", ".join(sorted(families))
            )
        )
    if families and opportunity not in families:
        frappe.throw(
            frappe._("Project {0} is already attached to Opportunity {1} Sales Orders.").format(
                project, next(iter(families))
            )
        )


def _attach_opportunity_sales_orders(opportunity: str, project: str) -> None:
    assert_project_opportunity_family(project, opportunity)
    link_sales_orders_to_project_as_system(
        project,
        opportunity_sales_orders(opportunity),
        expected_opportunity=opportunity,
    )


def _set_so_project_on_doc(doc, project: str) -> None:
    if not doc.meta.get_field("project") or doc.get("project"):
        return
    project_doc = frappe.get_doc("Project", project)
    _validate_project_order_consistency(project_doc, doc)
    doc.project = project


def _set_so_project_by_name(sales_order: str, project: str) -> None:
    link_sales_orders_to_project_as_system(project, [{"name": sales_order}])


def link_sales_orders_to_project_as_system(
    project,
    sales_orders: list[dict],
    expected_opportunity: str | None = None,
) -> int:
    """Set native Project links after explicit authorization and consistency checks.

    The final database write intentionally bypasses submitted-document field guards,
    but never document permissions, company access, or customer/company consistency.
    Every candidate is preflighted before any Sales Order is changed.
    """
    project_doc = frappe.get_doc("Project", project) if isinstance(project, str) else project
    candidates = []
    seen = set()
    for row in sales_orders:
        name = (row.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        sales_order = frappe.get_doc("Sales Order", name)
        if not frappe.has_permission("Sales Order", ptype="write", doc=sales_order):
            frappe.throw(
                frappe._("You do not have permission to link Sales Order {0} to a Project.").format(name),
                frappe.PermissionError,
            )
        if not user_can_access_company(sales_order.get("company")):
            frappe.throw(
                frappe._("You do not have access to Sales Order {0} company {1}.").format(
                    name, sales_order.get("company") or ""
                ),
                frappe.PermissionError,
            )
        if expected_opportunity:
            source_opportunity = _opportunity_from_sales_order_doc(sales_order)
            if source_opportunity != expected_opportunity:
                frappe.throw(
                    frappe._("Sales Order {0} does not belong exclusively to Opportunity {1}.").format(
                        name, expected_opportunity
                    )
                )
        _validate_project_order_consistency(project_doc, sales_order)
        current = (sales_order.get("project") or "").strip()
        if current and current != project_doc.name:
            frappe.throw(
                frappe._("Sales Order {0} is already linked to Project {1}.").format(name, current)
            )
        candidates.append((name, current))

    changed = 0
    for name, current in candidates:
        if current:
            continue
        frappe.db.set_value("Sales Order", name, "project", project_doc.name, update_modified=False)
        changed += 1
    return changed


def _validate_project_order_consistency(project, sales_order) -> None:
    for fieldname, label in (("company", frappe._("Company")), ("customer", frappe._("Customer"))):
        project_value = (project.get(fieldname) or "").strip()
        order_value = (sales_order.get(fieldname) or "").strip()
        if project_value != order_value:
            frappe.throw(
                frappe._("Sales Order {0} {1} does not match Project {2}.").format(
                    sales_order.name, label, project.name
                )
            )


def _copy_source_context_to_project(source, project) -> None:
    values = {
        "customer": source.get("customer"),
        "company": source.get("company"),
        "custom_crm_business_type": source.get("custom_crm_business_type"),
        "custom_crm_segment": source.get("custom_crm_segment"),
        "custom_customer_tax_id": source.get("tax_id") or source.get("custom_customer_tax_id"),
        "custom_site_address_name": source.get("custom_site_address_name"),
        "custom_party_contact": source.get("contact_person"),
        "custom_party_contact_email": source.get("contact_email"),
        "custom_party_contact_mobile": source.get("contact_mobile"),
        "custom_billing_address_name": source.get("customer_address"),
        "custom_shipping_address_name": source.get("shipping_address_name"),
        "project_type": source.get("custom_project_type") or source.get("project_type"),
    }
    if source.doctype == "Opportunity":
        from orderlift.orderlift_crm.api.pipeline import _customer_for_opportunity_party
        from orderlift.orderlift_crm.party_propagation import resolve_party_context

        customer = _customer_for_opportunity_party(source)
        context = resolve_party_context("Customer", customer.name, source_doc=source)
        values["customer"] = customer.name
        values["custom_customer_tax_id"] = customer.get("tax_id") or source.get("custom_customer_tax_id")
        values["custom_party_contact"] = context.get("contact_name")
        values["custom_party_contact_email"] = context.get("email")
        values["custom_party_contact_mobile"] = context.get("mobile") or context.get("phone")
        values["custom_billing_address_name"] = context.get("billing_address_name")
        values["custom_shipping_address_name"] = context.get("shipping_address_name")
    elif source.doctype == "Sales Order":
        opportunity = _opportunity_from_sales_order_doc(source)
        if opportunity:
            values["project_type"] = frappe.db.get_value("Opportunity", opportunity, "custom_project_type")
    for fieldname, value in values.items():
        if value and project.meta.get_field(fieldname) and not project.get(fieldname):
            project.set(fieldname, value)
    address_name = values.get("custom_site_address_name") or source.get("shipping_address_name")
    if address_name and frappe.db.exists("Address", address_name):
        from frappe.contacts.doctype.address.address import get_address_display

        address = frappe.get_doc("Address", address_name)
        if project.meta.get_field("custom_site_address") and not project.get("custom_site_address"):
            project.custom_site_address = get_address_display(address.as_dict()) or address.get("address_line1") or ""
        if project.meta.get_field("custom_city") and not project.get("custom_city"):
            project.custom_city = address.get("city") or ""


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))
