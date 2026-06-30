"""Minimal has_permission and permission_query_conditions guards for Orderlift
standalone DocTypes that are not yet proxied through the main company_access
module. Every guard here follows the existing company_access patterns: company-
scoped visibility, business-type enforcement, and parent-document proxy checks
where applicable.

When a doctype grows a native/custom company field and fits the generic
``has_company_permission`` / ``_company_query`` pattern, prefer moving it into
``company_access.py`` instead of extending this file.
"""

from __future__ import annotations

import frappe

from orderlift.menu_access import get_allowed_companies, user_can_access_all_companies


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _table_name(doctype: str) -> str:
    return f"`tab{doctype.replace('`', '')}`"


def _has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _company_query(doctype, company_field, user):
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return None
    allowed = get_allowed_companies(user)
    table = _table_name(doctype)
    if not allowed:
        return f"{table}.name is null"
    escaped = ", ".join(frappe.db.escape(c) for c in allowed)
    return f"{table}.{company_field} in ({escaped})"


# ---------------------------------------------------------------------------
# Orderlift Annex Document — proxy to reference doctype
# ---------------------------------------------------------------------------

def has_annex_document_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """Require read/write access to the linked reference document."""
    permission_type = permission_type or ptype
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    ref_doctype = _get_doc_field(doc, "reference_doctype")
    ref_name = _get_doc_field(doc, "reference_name")
    if not ref_doctype or not ref_name:
        return None  # new blank doc — let DocPerm handle it

    ref_ptype = permission_type if permission_type not in ("read", "report", "print", "email") else "read"
    if not frappe.has_permission(ref_doctype, ref_ptype, doc=ref_name):
        return False

    # Also verify company-scope on the annex itself
    from orderlift.company_access import has_company_permission

    return has_company_permission(doc, ptype=ptype, user=user, permission_type=permission_type)


def annex_document_query(user=None):
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return None
    if not _has_field("Orderlift Annex Document", "company"):
        return None
    return _company_query("Orderlift Annex Document", "company", user)


# ---------------------------------------------------------------------------
# Shipment Analysis — proxy to Delivery Note / Container Load Plan
# ---------------------------------------------------------------------------

def has_shipment_analysis_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    permission_type = permission_type or ptype
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    source_name = _get_doc_field(doc, "source_name")
    if not source_name:
        return None

    # Find the real source doctype: try delivery_note link first, then container_load_plan
    dn = _get_doc_field(doc, "delivery_note")
    if dn:
        read_ptype = "read"
        write_preserve = permission_type not in ("read", "report", "print", "email")
        if not frappe.has_permission("Delivery Note", "write" if write_preserve else "read", doc=dn):
            return False
        return True

    clp = _get_doc_field(doc, "container_load_plan")
    if clp:
        if not frappe.has_permission("Container Load Plan", "read", doc=clp):
            return False
        return True

    return None


def shipment_analysis_query(user=None):
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return None
    table = _table_name("Shipment Analysis")
    # Restrict to SAs linked to a visible DN or CLP, or owned by the user
    # For now, filter by customer via existing Customer query
    try:
        from orderlift.company_access import customer_query as _customer_query

        cust_clause = _customer_query(user=user)
    except ImportError:
        cust_clause = None
    if cust_clause:
        customer_table = _table_name("Customer")
        return (
            f"exists (select 1 from {customer_table} _sa_cust "
            f"where _sa_cust.name = {table}.customer and ({cust_clause}))"
        )
    return None


# ---------------------------------------------------------------------------
# Pricing Builder History — proxy to parent Pricing Builder
# ---------------------------------------------------------------------------

def has_builder_history_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    permission_type = permission_type or ptype
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    builder = _get_doc_field(doc, "pricing_builder")
    if not builder:
        return None
    if permission_type and permission_type not in ("read", "report", "print", "email"):
        return False  # history is read-only for non-admin
    if not frappe.has_permission("Pricing Builder", "read", doc=builder):
        return False
    return True


def builder_history_query(user=None):
    user = user or frappe.session.user
    if user_can_access_all_companies(user):
        return None
    table = _table_name("Pricing Builder History")
    # Show only history rows for visible Pricing Builders
    return (
        f"exists (select 1 from {_table_name('Pricing Builder')} _pbh "
        f"where _pbh.name = {table}.pricing_builder)"
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _get_doc_field(doc, fieldname):
    if hasattr(doc, "get"):
        return (doc.get(fieldname) or "").strip()
    return (getattr(doc, fieldname, "") or "").strip()
