"""Orderlift Sales Team propagation and commission eligibility helpers."""

from __future__ import annotations

from collections.abc import Iterable
import json

import frappe
from frappe import _

try:
    from frappe.utils import cint, flt
except ImportError:  # Unit tests may provide only a minimal frappe.utils stub.
    from frappe.utils import flt

    def cint(value=0):
        return int(value or 0)


TEAM_FIELD = "custom_sales_team"
TEAM_DOCTYPE = "Orderlift Sales Team Member"
TEAM_DOCTYPES = {"Opportunity", "Pricing Sheet", "Quotation", "Sales Order"}


@frappe.whitelist()
def get_commission_visibility(doctype: str, name: str = "", team_members: str = "") -> dict:
    """Return permission-safe commission visibility for a commercial document."""
    user = frappe.session.user
    if can_view_commission_details(user):
        return {"can_view": 1, "sales_person": "", "reason": "manager"}

    salesperson = sales_person_for_user(user)
    if not salesperson or not commission_enabled(salesperson):
        return {"can_view": 0, "sales_person": salesperson, "reason": "ineligible"}

    members = []
    if name and doctype in TEAM_DOCTYPES and frappe.db.exists(doctype, name):
        members = [row.get("sales_person") for row in _linked_team(doctype, name)]
    elif team_members:
        try:
            members = json.loads(team_members) if isinstance(team_members, str) else team_members
        except (TypeError, ValueError):
            members = []
    can_view = salesperson in {member for member in members if member}
    return {"can_view": int(can_view), "sales_person": salesperson, "reason": "team" if can_view else "not_team"}


def can_view_commission_details(user: str | None = None) -> bool:
    try:
        from orderlift.role_capabilities import (
            CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT,
            CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT,
            user_has_capability,
        )

        user = user or frappe.session.user
        return bool(
            user_has_capability(CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT, user=user)
            or user_has_capability(CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT, user=user)
        )
    except Exception:
        return False


def redact_sales_team(doc, method=None) -> None:
    """Remove team rows before serialization when the user cannot inspect them."""
    if not doc or not _has_team_field(doc) or _can_view_document_team(doc):
        return
    doc.set(TEAM_FIELD, [])


def preserve_hidden_sales_team(doc, method=None) -> None:
    """Restore persisted rows before save when document loading redacted them."""
    name = (doc.get("name") or "").strip()
    if not name or doc.get("__islocal") or not frappe.db.exists(doc.doctype, name):
        return
    persisted = _linked_team(doc.doctype, name)
    if not persisted or _can_view_members(persisted):
        return
    set_team_rows(doc, persisted)


def validate_agent_pricing_rules(doc, method=None) -> None:
    """Ensure the commission eligibility flag is always an explicit boolean."""
    if hasattr(doc, "commission_enabled"):
        doc.commission_enabled = cint(doc.commission_enabled)


def sync_opportunity_team(doc, method=None) -> None:
    if getattr(doc, "doctype", None) != "Opportunity":
        return
    if not _has_team_field(doc):
        return
    if not _team_rows(doc):
        salesperson = sales_person_for_user(doc.get("opportunity_owner") or doc.get("owner"))
        if salesperson and commission_enabled(salesperson):
            set_team(doc, [salesperson])
    validate_team(doc)


def sync_pricing_sheet_team(doc, method=None) -> None:
    if getattr(doc, "doctype", None) != "Pricing Sheet":
        return
    if not _has_team_field(doc):
        return
    if _has_field(doc, "custom_opportunity_owner") and doc.get("opportunity"):
        doc.custom_opportunity_owner = frappe.db.get_value(
            "Opportunity", doc.get("opportunity"), "opportunity_owner"
        ) or frappe.db.get_value("Opportunity", doc.get("opportunity"), "owner")
    if not _team_rows(doc):
        source = _linked_team("Opportunity", doc.get("opportunity"))
        if source:
            set_team_rows(doc, source)
        else:
            salesperson = doc.get("sales_person") or sales_person_for_user(frappe.session.user)
            if salesperson:
                set_team(doc, [salesperson])
    validate_team(doc)
    sync_legacy_sales_person(doc)


def sync_quotation_team(doc, method=None) -> None:
    if getattr(doc, "doctype", None) != "Quotation":
        return
    if not _has_team_field(doc):
        return
    if not _team_rows(doc):
        source = _linked_team("Pricing Sheet", doc.get("source_pricing_sheet"))
        source = source or _linked_team("Opportunity", doc.get("opportunity"))
        if source:
            set_team_rows(doc, source)
        else:
            salesperson = doc.get("commission_sales_person") or sales_person_for_user(doc.get("owner"))
            if salesperson:
                set_team(doc, [salesperson])
    validate_team(doc)
    sync_legacy_sales_person(doc)


def sync_sales_order_team(doc, method=None) -> None:
    if getattr(doc, "doctype", None) != "Sales Order":
        return
    if not _has_team_field(doc):
        return
    if not _team_rows(doc):
        source = _linked_team("Quotation", _source_quotation_from_items(doc))
        if source:
            set_team_rows(doc, source)
        else:
            salesperson = _source_sales_person_from_items(doc)
            if salesperson:
                set_team(doc, [salesperson])
    validate_team(doc)


def validate_team(doc) -> None:
    """Validate membership, primary selection, and a 100% allocation."""
    rows = _team_rows(doc)
    if not rows:
        return

    seen = set()
    for row in rows:
        salesperson = _row_value(row, "sales_person")
        if not salesperson:
            frappe.throw(_("Sales Team rows require a Sales Person."))
        if salesperson in seen:
            frappe.throw(_("Sales Person {0} appears more than once in the Sales Team.").format(salesperson))
        seen.add(salesperson)
        if not _sales_person_enabled(salesperson):
            frappe.throw(_("Sales Person {0} is disabled.").format(salesperson))
        if not commission_enabled(salesperson):
            frappe.throw(_("Sales Person {0} is not eligible for commissions.").format(salesperson))
        percentage = flt(_row_value(row, "allocated_percentage"))
        if percentage < 0:
            frappe.throw(_("Sales Team contribution cannot be negative."))

    _normalize_primary(rows)
    _redistribute_if_membership_changed(doc, rows)
    total = sum(flt(_row_value(row, "allocated_percentage")) for row in rows)
    if abs(total - 100) > 0.000001:
        frappe.throw(_("Sales Team contributions must total 100%. Current total: {0}.").format(total))


def sync_legacy_sales_person(doc) -> None:
    primary = primary_sales_person(doc)
    if not primary:
        return
    if getattr(doc, "doctype", None) == "Pricing Sheet" and _has_field(doc, "sales_person"):
        doc.sales_person = primary
    if getattr(doc, "doctype", None) == "Quotation" and _has_field(doc, "commission_sales_person"):
        doc.commission_sales_person = primary


def sync_team_commission_preview(doc, method=None) -> None:
    rows = _team_rows(doc)
    if not rows:
        return
    primary = primary_sales_person(rows)
    rate = commission_rate(primary)
    if getattr(doc, "doctype", None) == "Pricing Sheet":
        total = sum(flt(_row_value(row, "commission_amount")) for row in (doc.get("lines") or []))
    elif getattr(doc, "doctype", None) in {"Quotation", "Sales Order"}:
        total = sum(flt(_row_value(row, "source_commission_amount")) for row in (doc.get("items") or []))
    else:
        total = 0.0
    for row in rows:
        percentage = flt(_row_value(row, "allocated_percentage"))
        _set_row_value(row, "commission_rate", rate)
        _set_row_value(row, "commission_amount", total * percentage / 100)


def set_team(doc, salespeople: Iterable[str]) -> None:
    names = list(dict.fromkeys(name.strip() for name in salespeople if (name or "").strip()))
    if not names:
        return
    rows = []
    for index, salesperson in enumerate(names):
        rows.append(
            {
                "sales_person": salesperson,
                "allocated_percentage": 100 if len(names) == 1 else 0,
                "is_primary": 1 if index == 0 else 0,
            }
        )
    if len(names) > 1:
        redistribute_equal(rows)
    doc.set(TEAM_FIELD, rows)


def set_team_rows(doc, rows: Iterable[dict]) -> None:
    values = []
    for row in rows:
        salesperson = (row.get("sales_person") or "").strip()
        if not salesperson:
            continue
        values.append(
            {
                "sales_person": salesperson,
                "allocated_percentage": flt(row.get("allocated_percentage") or 0),
                "is_primary": cint(row.get("is_primary")),
                "commission_rate": flt(row.get("commission_rate") or 0),
                "commission_amount": flt(row.get("commission_amount") or 0),
            }
        )
    if values:
        doc.set(TEAM_FIELD, values)


def redistribute_equal(rows: list) -> None:
    if not rows:
        return
    share = round(100 / len(rows), 9)
    for index, row in enumerate(rows):
        value = 100 - share * (len(rows) - 1) if index == len(rows) - 1 else share
        _set_row_value(row, "allocated_percentage", value)


def commission_enabled(salesperson: str) -> bool:
    if not salesperson or not frappe.db.exists("Agent Pricing Rules", {"sales_person": salesperson}):
        return False
    if not frappe.db.has_column("Agent Pricing Rules", "commission_enabled"):
        return True
    value = frappe.db.get_value("Agent Pricing Rules", {"sales_person": salesperson}, "commission_enabled")
    return bool(cint(value))


def commission_rate(salesperson: str) -> float:
    if not salesperson:
        return 0.0
    return flt(
        frappe.db.get_value("Agent Pricing Rules", {"sales_person": salesperson}, "commission_rate") or 0
    )


def primary_sales_person(doc_or_rows) -> str:
    rows = _team_rows(doc_or_rows) if not isinstance(doc_or_rows, (list, tuple)) else doc_or_rows
    for row in rows:
        if cint(_row_value(row, "is_primary")):
            return _row_value(row, "sales_person")
    return _row_value(rows[0], "sales_person") if rows else ""


def team_rows(doc) -> list[dict]:
    return [
        {
            "sales_person": _row_value(row, "sales_person"),
            "allocated_percentage": flt(_row_value(row, "allocated_percentage")),
            "is_primary": cint(_row_value(row, "is_primary")),
            "commission_rate": flt(_row_value(row, "commission_rate")),
            "commission_amount": flt(_row_value(row, "commission_amount")),
        }
        for row in _team_rows(doc)
    ]


def _linked_team(doctype: str, name: str | None) -> list[dict]:
    if not name or not frappe.db.exists(doctype, name):
        return []
    rows = frappe.db.get_all(
        TEAM_DOCTYPE,
        filters={"parent": name, "parenttype": doctype, "parentfield": TEAM_FIELD},
        fields=["sales_person", "allocated_percentage", "is_primary", "commission_rate", "commission_amount"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )
    result = [
        {
            "sales_person": row.get("sales_person"),
            "allocated_percentage": flt(row.get("allocated_percentage")),
            "is_primary": cint(row.get("is_primary")),
        }
        for row in rows
    ]
    if result or doctype != "Opportunity":
        return result

    owner = frappe.db.get_value("Opportunity", name, "opportunity_owner") or frappe.db.get_value(
        "Opportunity", name, "owner"
    )
    salesperson = sales_person_for_user(owner)
    if not salesperson or not commission_enabled(salesperson):
        return []
    return [{"sales_person": salesperson, "allocated_percentage": 100, "is_primary": 1}]


def _source_sales_person_from_items(doc) -> str:
    for row in doc.get("items") or []:
        salesperson = _row_value(row, "source_sales_person")
        if salesperson:
            return salesperson
    return ""


def _source_quotation_from_items(doc) -> str:
    for row in doc.get("items") or []:
        source_doctype = (_row_value(row, "prevdoc_doctype") or "").strip()
        source_name = (_row_value(row, "prevdoc_docname") or "").strip()
        if source_name and source_doctype in {"", "Quotation"}:
            return source_name
    return ""


def _can_view_members(rows) -> bool:
    if can_view_commission_details():
        return True
    salesperson = sales_person_for_user(frappe.session.user)
    if not salesperson or not commission_enabled(salesperson):
        return False
    return salesperson in {_row_value(row, "sales_person") for row in rows}


def _can_view_document_team(doc) -> bool:
    if can_view_commission_details():
        return True
    rows = _team_rows(doc)
    if not rows and doc.get("name") and frappe.db.exists(doc.doctype, doc.get("name")):
        rows = _linked_team(doc.doctype, doc.get("name"))
    return _can_view_members(rows)


def sales_person_for_user(user: str | None) -> str:
    user = (user or "").strip()
    if not user or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def _sales_person_enabled(salesperson: str) -> bool:
    if not frappe.db.has_column("Sales Person", "enabled"):
        return True
    return bool(frappe.db.get_value("Sales Person", salesperson, "enabled"))


def _normalize_primary(rows: list) -> None:
    primary = [row for row in rows if cint(_row_value(row, "is_primary"))]
    if len(primary) > 1:
        for row in primary[1:]:
            _set_row_value(row, "is_primary", 0)
    if not primary:
        _set_row_value(rows[0], "is_primary", 1)


def _redistribute_if_membership_changed(doc, rows: list) -> None:
    if isinstance(doc, (list, tuple)) or not hasattr(doc, "get_doc_before_save"):
        return
    try:
        before = doc.get_doc_before_save()
    except Exception:
        before = None
    if not before:
        return
    previous = {_row_value(row, "sales_person") for row in _team_rows(before)}
    current = {_row_value(row, "sales_person") for row in rows}
    if previous != current and len(rows) > 1:
        redistribute_equal(rows)


def _team_rows(doc) -> list:
    if isinstance(doc, (list, tuple)):
        return list(doc)
    return list(doc.get(TEAM_FIELD) or [])


def _has_team_field(doc) -> bool:
    return _has_field(doc, TEAM_FIELD)


def _has_field(doc, fieldname: str) -> bool:
    meta = getattr(doc, "meta", None)
    return bool(meta and meta.get_field(fieldname))


def _row_value(row, fieldname: str, default=""):
    getter = getattr(row, "get", None)
    return getter(fieldname, default) if callable(getter) else getattr(row, fieldname, default)


def _set_row_value(row, fieldname: str, value) -> None:
    setter = getattr(row, "set", None)
    if callable(setter):
        setter(fieldname, value)
    elif isinstance(row, dict):
        row[fieldname] = value
    else:
        setattr(row, fieldname, value)
