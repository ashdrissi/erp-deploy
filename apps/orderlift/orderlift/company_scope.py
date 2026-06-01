"""Multi-company + business-type scope layer.

Single source of truth for which doctypes are owned by a Company and which
field carries their business type. Provides:

* ``SCOPED_DOCTYPES`` registry consumed by ``company_access`` (permission
  queries / has_permission) and by ``hooks`` (doc_events).
* ``apply_company_scope`` — one generic ``validate`` handler that auto-fills and
  locks the owning company, defaults/validates the business type, and rejects
  business types not allowed by the record's company.
* ``after_migrate`` — creates the ``custom_company`` fields (for doctypes that
  lack a native ``company``) and backfills existing records to a default company.

Company is the ownership/security boundary; business type is a constraint that
lives inside a company. See ``orderlift/company_access.py`` and
``orderlift/orderlift_crm/company_business_type.py`` for the reused helpers.
"""

from __future__ import annotations

import json
import os

import frappe

try:
    from frappe import _
except ImportError:  # Unit tests use a small frappe stub without translation.
    def _(msg, *args, **kwargs):
        return msg

from orderlift.menu_access import (
    get_allowed_companies,
    resolve_current_company,
    user_can_access_all_companies,
)
from orderlift.orderlift_crm.company_business_type import (
    get_company_business_type_names,
    get_single_company_business_type,
    is_business_type_allowed_for_company,
)


# doctype -> {company_field, bt_field, segments_field}
#   company_field   : field storing the owning Company ("company" native, else "custom_company")
#   bt_field        : single business-type Link field, or None
#   segments_field  : CRM Segment Assignment child table whose rows carry a business type, or None
SCOPED_DOCTYPES: dict[str, dict] = {
    # Core ERPNext masters — custom_company added via fixture.
    "Customer": {"company_field": "custom_company", "bt_field": None, "segments_field": "custom_crm_segments"},
    "Supplier": {"company_field": "custom_company", "bt_field": None, "segments_field": None},
    "Price List": {"company_field": "custom_company", "bt_field": None, "segments_field": None},
    # Native company field.
    "Prospect": {"company_field": "company", "bt_field": None, "segments_field": "custom_crm_segments"},
    "Lead": {"company_field": "company", "bt_field": None, "segments_field": "custom_crm_segments"},
    "Opportunity": {"company_field": "company", "bt_field": "custom_crm_business_type", "segments_field": None},
    "Quotation": {"company_field": "company", "bt_field": "custom_crm_business_type", "segments_field": None},
    "Sales Order": {"company_field": "company", "bt_field": "custom_crm_business_type", "segments_field": None},
    "Project": {"company_field": "company", "bt_field": "custom_crm_business_type", "segments_field": None},
    "Pricing Benchmark Policy": {"company_field": "company", "bt_field": None, "segments_field": None},
    "Pricing Customs Policy": {"company_field": "company", "bt_field": None, "segments_field": None},
    # Orderlift doctypes — custom_company added via fixture.
    "Pricing Sheet": {"company_field": "custom_company", "bt_field": "crm_business_type", "segments_field": None},
    "Customer Segmentation Engine": {"company_field": "custom_company", "bt_field": "business_type_filter", "segments_field": None},
    "Partner Campaign": {"company_field": "custom_company", "bt_field": "business_type_filter", "segments_field": None},
    "Pricing Scenario": {"company_field": "custom_company", "bt_field": None, "segments_field": None},
    "Portal Customer Group Policy": {"company_field": "custom_company", "bt_field": "business_type", "segments_field": None},
    "Portal Quote Request": {"company_field": "custom_company", "bt_field": "business_type", "segments_field": None},
}

# Fixture file holding the custom_company field definitions (created on migrate).
_CUSTOM_FIELD_FIXTURE = "custom_field_company_scope.json"


def company_field_for(doctype: str) -> str:
    """Return the fieldname that stores the owning company for a scoped doctype."""
    config = SCOPED_DOCTYPES.get(doctype)
    return config["company_field"] if config else "company"


# ---------------------------------------------------------------------------
# Write-time guard (doc_events validate)
# ---------------------------------------------------------------------------


def apply_company_scope(doc, method=None) -> None:
    config = SCOPED_DOCTYPES.get(getattr(doc, "doctype", None))
    if not config:
        return

    company_field = config["company_field"]
    if not _meta_has_field(doc.doctype, company_field):
        return

    _apply_company(doc, company_field)
    company = (doc.get(company_field) or "").strip()

    bt_field = config.get("bt_field")
    if bt_field and _meta_has_field(doc.doctype, bt_field):
        _apply_business_type(doc, company, bt_field)

    segments_field = config.get("segments_field")
    if segments_field and _meta_has_field(doc.doctype, segments_field):
        _validate_segments(doc, company, segments_field)


def _apply_company(doc, company_field: str) -> None:
    user = frappe.session.user
    unrestricted = user_can_access_all_companies(user)
    current = (doc.get(company_field) or "").strip()

    if _is_new_doc(doc):
        if not current:
            active = resolve_current_company(user=user)
            if active:
                doc.set(company_field, active)
        return

    # Existing record: lock the company against change for restricted users.
    if unrestricted:
        return
    old = (frappe.db.get_value(doc.doctype, doc.name, company_field) or "").strip()
    if not old:
        return
    if current and current != old:
        frappe.throw(
            _("Company is locked for this record and cannot be changed to {0}.").format(current)
        )
    if not current:
        doc.set(company_field, old)


def _apply_business_type(doc, company: str, bt_field: str) -> None:
    value = (doc.get(bt_field) or "").strip()
    if not value:
        single = get_single_company_business_type(company)
        if single:
            doc.set(bt_field, single)
        return
    if not is_business_type_allowed_for_company(company, value):
        frappe.throw(_business_type_error(value, company))


def _validate_segments(doc, company: str, segments_field: str) -> None:
    allowed = get_company_business_type_names(company)
    if not allowed:
        return
    allowed_set = set(allowed)
    for row in doc.get(segments_field) or []:
        business_type = (row.get("business_type") or "").strip()
        if business_type and business_type not in allowed_set:
            frappe.throw(_business_type_error(business_type, company))


def _business_type_error(business_type: str, company: str) -> str:
    allowed = ", ".join(get_company_business_type_names(company)) or "—"
    return _("Business Type {0} is not allowed for company {1}. Allowed business types: {2}").format(
        business_type, company or "—", allowed
    )


# ---------------------------------------------------------------------------
# Migration: create custom_company fields, then backfill existing records
# ---------------------------------------------------------------------------


def after_migrate() -> None:
    sync_custom_fields()
    backfill_company()
    frappe.db.commit()


def sync_custom_fields() -> None:
    path = os.path.join(os.path.dirname(__file__), "fixtures", _CUSTOM_FIELD_FIXTURE)
    if not os.path.exists(path):
        frappe.logger().warning("company_scope: fixture not found: %s", path)
        return
    with open(path) as fixture_file:
        fields = json.load(fixture_file)
    for field_def in fields:
        dt = field_def.get("dt")
        fieldname = field_def.get("fieldname")
        if not dt or not fieldname:
            continue
        if not frappe.db.exists("DocType", dt):
            continue
        existing = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
        doc = frappe.get_doc("Custom Field", existing) if existing else frappe.new_doc("Custom Field")
        for key, value in field_def.items():
            if key != "doctype":
                setattr(doc, key, value)
        doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)


def backfill_company() -> None:
    """Assign a default company to scoped records that still have none."""
    default_company = _default_company()
    if not default_company:
        return
    for doctype, config in SCOPED_DOCTYPES.items():
        company_field = config["company_field"]
        if not frappe.db.exists("DocType", doctype):
            continue
        if not _meta_has_field(doctype, company_field):
            continue
        frappe.db.sql(
            f"UPDATE `tab{doctype}` SET `{company_field}` = %s "
            f"WHERE COALESCE(`{company_field}`, '') = ''",
            (default_company,),
        )


def _default_company() -> str:
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if company:
        return company
    return frappe.db.get_value("Company", {}, "name", order_by="creation asc") or ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta_has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _is_new_doc(doc) -> bool:
    try:
        return bool(doc.is_new())
    except Exception:
        return not bool(getattr(doc, "name", None))
