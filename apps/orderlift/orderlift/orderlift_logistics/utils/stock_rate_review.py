from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, nowdate

from orderlift.menu_access import resolve_current_company
from orderlift.role_capabilities import (
    CAPABILITY_PRIVILEGED_PRICING,
    CAPABILITY_STOCK_RATE_MANAGEMENT,
    user_has_capability,
)
from orderlift.warehouse_access import get_allowed_warehouses


STATUS_NOT_REQUIRED = "Not Required"
STATUS_MISSING = "Missing Rate"
STATUS_PROVISIONAL = "Provisional Rate"
STATUS_APPROVED = "Approved Rate"

SOURCE_NOT_REQUIRED = "Not Required"
SOURCE_MISSING = "Missing"
SOURCE_PURCHASE_ORDER = "Purchase Order"
SOURCE_BUYING_PRICE_LIST = "Buying Price List"
SOURCE_LAST_PURCHASE = "Last Purchase"
SOURCE_MANUAL = "Manual"

RATE_STATUS_FIELD = "custom_stock_rate_status"
RATE_SOURCE_FIELD = "custom_stock_rate_source"
RATE_SOURCE_DETAIL_FIELD = "custom_stock_rate_source_detail"
SUGGESTED_RATE_FIELD = "custom_suggested_rate"

REVIEW_CONFIG = {
    "Stock Entry": {
        "child_doctype": "Stock Entry Detail",
        "rate_field": "basic_rate",
        "warehouse_fields": ("t_warehouse", "s_warehouse"),
    },
    "Purchase Receipt": {
        "child_doctype": "Purchase Receipt Item",
        "rate_field": "rate",
        "warehouse_fields": ("warehouse",),
    },
}


def can_manage_stock_rates(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    roles = set(frappe.get_roles(user) or [])
    return bool(
        user_has_capability(CAPABILITY_STOCK_RATE_MANAGEMENT, user=user, roles=roles)
        or user_has_capability(CAPABILITY_PRIVILEGED_PRICING, user=user, roles=roles)
    )


@frappe.whitelist()
def get_stock_entry_rate_suggestion(
    item_code,
    company,
    posting_date=None,
    uom=None,
    stock_uom=None,
    conversion_factor=1,
) -> dict:
    frappe.has_permission("Stock Entry", "create", throw=True)
    active_company = resolve_current_company(user=frappe.session.user)
    company = (company or "").strip()
    if not company or company != active_company:
        frappe.throw(_("Stock Entry company is outside your active company."), frappe.PermissionError)
    item_code = (item_code or "").strip()
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("A valid Item is required."))

    doc = frappe._dict({"company": company, "posting_date": posting_date or nowdate()})
    row = frappe._dict(
        {
            "item_code": item_code,
            "uom": uom or stock_uom or "",
            "stock_uom": stock_uom or uom or "",
            "conversion_factor": flt(conversion_factor) or 1,
        }
    )
    return _suggest_stock_entry_rate(doc, row)


def resolve_document_rates(doc, method=None) -> None:
    if getattr(doc, "doctype", "") == "Purchase Receipt":
        _resolve_purchase_receipt(doc)
    elif getattr(doc, "doctype", "") == "Stock Entry":
        _resolve_stock_entry(doc)


def validate_document_rates_for_submit(doc, method=None) -> None:
    missing = []
    for row in doc.get("items") or []:
        if not _row_requires_rate(doc, row):
            continue
        rate_field = REVIEW_CONFIG[doc.doctype]["rate_field"]
        if (
            row.get(RATE_STATUS_FIELD) == STATUS_MISSING
            or flt(row.get(rate_field)) <= 0
            or cint(row.get("allow_zero_valuation_rate"))
        ):
            missing.append(row)
    if not missing:
        return
    items = ", ".join((row.get("item_code") or f"row {row.idx}") for row in missing[:10])
    frappe.throw(
        _(
            "Quantities are saved, but stock cannot be posted without a value. "
            "Complete these rows in Stock Rate Review: {0}"
        ).format(items),
        title=_("Stock Rate Review Required"),
    )


def finalize_document_rate_status(doc, method=None) -> None:
    """Never persist the temporary zero-rate validation bypass used by drafts."""
    for row in doc.get("items") or []:
        if _row_requires_rate(doc, row):
            row.allow_zero_valuation_rate = 0


def _resolve_purchase_receipt(doc) -> None:
    statuses = []
    item_cache = {}
    for row in doc.get("items") or []:
        if not _requires_purchase_receipt_rate(row, item_cache):
            _set_rate_metadata(row, STATUS_NOT_REQUIRED, SOURCE_NOT_REQUIRED, 0, "")
            statuses.append(STATUS_NOT_REQUIRED)
            continue

        current_rate = flt(row.get("rate"))
        existing_source = (row.get(RATE_SOURCE_FIELD) or "").strip()
        row.allow_zero_valuation_rate = 0
        if current_rate > 0 and _has_server_rate_approval(doc, row):
            _set_rate_metadata(
                row,
                STATUS_APPROVED,
                existing_source or SOURCE_MANUAL,
                current_rate,
                row.get(RATE_SOURCE_DETAIL_FIELD) or "Reviewed rate",
            )
            statuses.append(STATUS_APPROVED)
            continue

        po_rate = _purchase_order_rate(row)
        if po_rate > 0:
            _set_purchase_receipt_rate(row, po_rate)
            _set_rate_metadata(
                row,
                STATUS_APPROVED,
                SOURCE_PURCHASE_ORDER,
                po_rate,
                row.get("purchase_order") or row.get("purchase_order_item") or "",
            )
            statuses.append(STATUS_APPROVED)
            continue

        suggestion = _suggest_purchase_receipt_rate(doc, row)
        if current_rate <= 0 and suggestion["rate"] > 0:
            _set_purchase_receipt_rate(row, suggestion["rate"])
            current_rate = suggestion["rate"]

        if current_rate > 0:
            if suggestion["rate"] > 0 and _rates_match(current_rate, suggestion["rate"]):
                source = suggestion["source"]
                detail = suggestion.get("detail") or ""
            else:
                source = SOURCE_MANUAL
                detail = "Existing document rate"
            status = STATUS_PROVISIONAL
            _set_rate_metadata(row, status, source, suggestion["rate"] or current_rate, detail)
            statuses.append(status)
            continue

        _set_rate_metadata(row, STATUS_MISSING, SOURCE_MISSING, suggestion["rate"], suggestion.get("detail") or "")
        statuses.append(STATUS_MISSING)

    _set_parent_status(doc, statuses)


def _resolve_stock_entry(doc) -> None:
    statuses = []
    for row in doc.get("items") or []:
        if not _requires_stock_entry_rate(doc, row):
            _set_rate_metadata(row, STATUS_NOT_REQUIRED, SOURCE_NOT_REQUIRED, 0, "")
            statuses.append(STATUS_NOT_REQUIRED)
            continue

        current_rate = flt(row.get("basic_rate"))
        existing_source = (row.get(RATE_SOURCE_FIELD) or "").strip()
        row.allow_zero_valuation_rate = 0
        if current_rate > 0 and _has_server_rate_approval(doc, row):
            _set_rate_metadata(
                row,
                STATUS_APPROVED,
                existing_source or SOURCE_MANUAL,
                current_rate,
                row.get(RATE_SOURCE_DETAIL_FIELD) or "Reviewed rate",
            )
            statuses.append(STATUS_APPROVED)
            continue

        suggestion = _suggest_stock_entry_rate(doc, row)
        if suggestion["rate"] > 0 and not cint(row.get("set_basic_rate_manually")):
            row.basic_rate = suggestion["rate"]
            current_rate = suggestion["rate"]

        if current_rate > 0:
            if cint(row.get("set_basic_rate_manually")):
                source = SOURCE_MANUAL
                detail = "Manual document rate"
            elif suggestion["rate"] > 0 and _rates_match(current_rate, suggestion["rate"]):
                source = suggestion["source"]
                detail = suggestion.get("detail") or ""
            else:
                row.basic_rate = 0
                row.allow_zero_valuation_rate = 1
                _set_rate_metadata(row, STATUS_MISSING, SOURCE_MISSING, 0, "No company-scoped rate found")
                statuses.append(STATUS_MISSING)
                continue
            status = STATUS_PROVISIONAL
            _set_rate_metadata(row, status, source, suggestion["rate"] or current_rate, detail)
            statuses.append(status)
            continue

        row.allow_zero_valuation_rate = 1
        _set_rate_metadata(row, STATUS_MISSING, SOURCE_MISSING, suggestion["rate"], suggestion.get("detail") or "")
        statuses.append(STATUS_MISSING)

    _set_parent_status(doc, statuses)


def _requires_purchase_receipt_rate(row, item_cache: dict) -> bool:
    item_code = (row.get("item_code") or "").strip()
    if not item_code or flt(row.get("qty")) <= 0:
        return False
    if item_code not in item_cache:
        item_cache[item_code] = cint(frappe.db.get_value("Item", item_code, "is_stock_item"))
    return bool(item_cache[item_code])


def _requires_stock_entry_rate(doc, row) -> bool:
    purpose = (doc.get("purpose") or doc.get("stock_entry_type") or "").strip()
    return bool(
        purpose == "Material Receipt"
        and (row.get("t_warehouse") or "").strip()
        and not (row.get("s_warehouse") or "").strip()
        and flt(row.get("transfer_qty") or row.get("qty")) > 0
    )


def _row_requires_rate(doc, row) -> bool:
    if doc.doctype == "Stock Entry":
        return _requires_stock_entry_rate(doc, row)
    if doc.doctype == "Purchase Receipt":
        return _requires_purchase_receipt_rate(row, {})
    return False


def _has_server_rate_approval(doc, row) -> bool:
    approved_rows = set(getattr(getattr(doc, "flags", None), "orderlift_stock_rate_review_rows", set()) or set())
    if row.name in approved_rows:
        return True
    if not row.name or getattr(row, "is_new", lambda: False)():
        return False
    values = frappe.db.get_value(
        REVIEW_CONFIG[doc.doctype]["child_doctype"],
        row.name,
        [RATE_STATUS_FIELD, RATE_SOURCE_FIELD, "custom_rate_reviewed_by"],
        as_dict=True,
    ) or {}
    return bool(
        values.get(RATE_STATUS_FIELD) == STATUS_APPROVED
        and values.get(RATE_SOURCE_FIELD) not in {SOURCE_MISSING, SOURCE_NOT_REQUIRED, ""}
        and (values.get("custom_rate_reviewed_by") or "").strip()
    )


def _purchase_order_rate(row) -> float:
    detail_name = (row.get("purchase_order_item") or "").strip()
    if not detail_name:
        return 0
    values = frappe.db.get_value("Purchase Order Item", detail_name, ["rate", "uom"], as_dict=True) or {}
    if values.get("uom") and row.get("uom") and values.get("uom") != row.get("uom"):
        return 0
    return flt(values.get("rate"))


def _suggest_purchase_receipt_rate(doc, row) -> dict:
    transaction_currency = (doc.get("currency") or "").strip()
    company_currency = _company_currency(doc.get("company"))
    price = _latest_buying_item_price(
        item_code=row.get("item_code"),
        price_list=doc.get("buying_price_list"),
        company=doc.get("company"),
        target_currency=transaction_currency or company_currency,
        target_uom=row.get("uom"),
        stock_uom=row.get("stock_uom"),
        target_conversion_factor=flt(row.get("conversion_factor")) or 1,
        posting_date=doc.get("posting_date") or nowdate(),
    )
    if price["rate"] > 0:
        return {
            "rate": price["rate"],
            "source": SOURCE_BUYING_PRICE_LIST,
            "detail": price["detail"],
        }

    purchase = _last_purchase_base_stock_rate(row.get("item_code"), doc.get("company"), doc.get("posting_date"))
    if purchase["rate"] <= 0:
        return {"rate": 0, "source": SOURCE_MISSING, "detail": ""}
    base_rate = purchase["rate"] * (flt(row.get("conversion_factor")) or 1)
    conversion_rate = flt(doc.get("conversion_rate")) or 1
    return {
        "rate": base_rate / conversion_rate,
        "source": SOURCE_LAST_PURCHASE,
        "detail": purchase["document"],
    }


def _suggest_stock_entry_rate(doc, row) -> dict:
    company_currency = _company_currency(doc.get("company"))
    price = _latest_buying_item_price(
        item_code=row.get("item_code"),
        price_list="",
        company=doc.get("company"),
        target_currency=company_currency,
        target_uom=row.get("stock_uom") or row.get("uom"),
        stock_uom=row.get("stock_uom") or row.get("uom"),
        target_conversion_factor=1,
        posting_date=doc.get("posting_date") or nowdate(),
    )
    if price["rate"] > 0:
        return {
            "rate": price["rate"],
            "source": SOURCE_BUYING_PRICE_LIST,
            "detail": price["detail"],
        }
    purchase = _last_purchase_base_stock_rate(row.get("item_code"), doc.get("company"), doc.get("posting_date"))
    return {
        "rate": purchase["rate"],
        "source": SOURCE_LAST_PURCHASE if purchase["rate"] > 0 else SOURCE_MISSING,
        "detail": purchase["document"],
    }


def _latest_buying_item_price(
    *,
    item_code,
    price_list,
    company,
    target_currency,
    target_uom,
    stock_uom,
    target_conversion_factor,
    posting_date,
) -> dict:
    item_code = (item_code or "").strip()
    if not item_code:
        return {"rate": 0, "detail": ""}
    price_lists = _buying_price_lists(company, preferred=price_list)
    if not price_lists:
        return {"rate": 0, "detail": ""}
    filters = {"item_code": item_code, "price_list": ["in", price_lists]}
    if frappe.db.has_column("Item Price", "buying"):
        filters["buying"] = 1
    if frappe.db.has_column("Item Price", "enabled"):
        filters["enabled"] = 1
    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=["name", "price_list", "price_list_rate", "currency", "uom", "valid_from", "valid_upto", "modified"],
        order_by="valid_from desc, modified desc",
        limit_page_length=0,
    )
    for price_list_name in price_lists:
        for row in rows:
            if row.price_list != price_list_name:
                continue
            if row.valid_from and str(row.valid_from) > str(posting_date):
                continue
            if row.valid_upto and str(row.valid_upto) < str(posting_date):
                continue
            row_uom = (row.uom or stock_uom or "").strip()
            rate = flt(row.price_list_rate)
            if rate <= 0:
                continue
            if row_uom == (stock_uom or "").strip() and target_uom != stock_uom:
                rate *= flt(target_conversion_factor) or 1
            elif row_uom and target_uom and row_uom != target_uom:
                continue
            source_currency = (row.currency or frappe.db.get_value("Price List", row.price_list, "currency") or "").strip()
            converted_rate = _convert_currency(rate, source_currency, target_currency, posting_date)
            detail = row.price_list
            if source_currency and target_currency and source_currency != target_currency:
                detail += f" ({source_currency} -> {target_currency})"
            return {"rate": converted_rate, "detail": detail}
    return {"rate": 0, "detail": ""}


def _buying_price_lists(company, preferred="") -> list[str]:
    filters = {}
    if frappe.db.has_column("Price List", "custom_company") and company:
        filters["custom_company"] = company
    if frappe.db.has_column("Price List", "custom_price_list_type"):
        filters["custom_price_list_type"] = "Buying"
    else:
        filters["buying"] = 1
    if frappe.db.has_column("Price List", "enabled"):
        filters["enabled"] = 1
    names = frappe.get_all("Price List", filters=filters, pluck="name", order_by="modified desc", limit_page_length=0)
    preferred = (preferred or "").strip()
    if preferred in names:
        names.remove(preferred)
        names.insert(0, preferred)
    return names


def _last_purchase_base_stock_rate(item_code, company, posting_date=None) -> dict:
    if not item_code or not company:
        return {"rate": 0, "document": ""}
    rows = frappe.db.sql(
        """
        SELECT pr.name, pri.base_net_rate, pri.base_rate, pri.conversion_factor
        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
        WHERE pri.item_code = %(item_code)s
          AND pr.company = %(company)s
          AND pr.docstatus = 1
          AND ifnull(pr.is_return, 0) = 0
          AND pr.posting_date <= %(posting_date)s
          AND coalesce(pri.base_net_rate, pri.base_rate, 0) > 0
        ORDER BY pr.posting_date DESC, pr.posting_time DESC, pr.modified DESC
        LIMIT 1
        """,
        {"item_code": item_code, "company": company, "posting_date": posting_date or nowdate()},
        as_dict=True,
    )
    if not rows:
        return {"rate": 0, "document": ""}
    rate = flt(rows[0].base_net_rate or rows[0].base_rate)
    return {
        "rate": rate / (flt(rows[0].conversion_factor) or 1),
        "document": rows[0].name,
    }


def _convert_currency(rate, source_currency, target_currency, posting_date) -> float:
    rate = flt(rate)
    if rate <= 0 or not source_currency or not target_currency or source_currency == target_currency:
        return rate
    try:
        from erpnext.setup.utils import get_exchange_rate

        return rate * flt(get_exchange_rate(source_currency, target_currency, posting_date))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Stock rate currency conversion failed")
        return 0


def _company_currency(company) -> str:
    return frappe.db.get_value("Company", company, "default_currency") if company else ""


def _set_purchase_receipt_rate(row, rate) -> None:
    row.rate = flt(rate)
    if flt(row.get("price_list_rate")) <= 0:
        row.price_list_rate = flt(rate)


def _set_rate_metadata(row, status, source, suggested_rate, source_detail="") -> None:
    row.set(RATE_STATUS_FIELD, status)
    row.set(RATE_SOURCE_FIELD, source)
    row.set(RATE_SOURCE_DETAIL_FIELD, source_detail)
    row.set(SUGGESTED_RATE_FIELD, flt(suggested_rate))


def _rates_match(left, right) -> bool:
    left = flt(left)
    right = flt(right)
    return abs(left - right) <= max(0.005, max(abs(left), abs(right)) * 0.000001)


def _set_parent_status(doc, statuses) -> None:
    if STATUS_MISSING in statuses:
        status = STATUS_MISSING
    elif STATUS_PROVISIONAL in statuses:
        status = STATUS_PROVISIONAL
    elif STATUS_APPROVED in statuses:
        status = STATUS_APPROVED
    else:
        status = STATUS_NOT_REQUIRED
    doc.set(RATE_STATUS_FIELD, status)


@frappe.whitelist()
def get_review_payload(filters=None) -> dict:
    _require_rate_access()
    filters = _parse_json(filters, {})
    rows = _review_rows(filters)
    return {
        "rows": rows,
        "kpis": {
            "missing": sum(row["status"] == STATUS_MISSING for row in rows),
            "provisional": sum(row["status"] == STATUS_PROVISIONAL for row in rows),
            "ready": len(
                {
                    (row["doctype"], row["document"])
                    for row in rows
                    if row["docstatus"] == 0 and row["parent_status"] != STATUS_MISSING
                }
            ),
            "submitted_provisional": sum(row["docstatus"] == 1 and row["status"] == STATUS_PROVISIONAL for row in rows),
        },
        "can_submit": {doctype: bool(frappe.has_permission(doctype, "submit")) for doctype in REVIEW_CONFIG},
    }


@frappe.whitelist()
def save_rates(rows) -> dict:
    _require_rate_access()
    rows = _parse_json(rows, [])
    grouped = defaultdict(list)
    for row in rows:
        doctype = (row.get("doctype") or "").strip()
        document = (row.get("document") or "").strip()
        if doctype in REVIEW_CONFIG and document:
            grouped[(doctype, document)].append(row)

    updated_rows = updated_documents = 0
    for (doctype, document), changes in grouped.items():
        doc = frappe.get_doc(doctype, document)
        _assert_document_scope(doc)
        if cint(doc.docstatus) != 0:
            frappe.throw(_("Submitted document {0} cannot have its valuation rate changed.").format(document))
        children = {row.name: row for row in doc.get("items") or []}
        rate_field = REVIEW_CONFIG[doctype]["rate_field"]
        approved_row_names = set()
        for change in changes:
            child = children.get(change.get("row_name"))
            rate = flt(change.get("rate"))
            if not child or rate <= 0:
                continue
            if not _row_requires_rate(doc, child):
                continue
            child.set(rate_field, rate)
            if doctype == "Purchase Receipt" and flt(child.get("price_list_rate")) <= 0:
                child.price_list_rate = rate
            _set_rate_metadata(child, STATUS_APPROVED, SOURCE_MANUAL, rate, f"Reviewed by {frappe.session.user}")
            child.custom_rate_reviewed_by = frappe.session.user
            child.custom_rate_reviewed_on = now_datetime()
            approved_row_names.add(child.name)
            updated_rows += 1
        doc.flags.orderlift_stock_rate_review_rows = approved_row_names
        doc.flags.ignore_permissions = True
        doc.save()
        updated_documents += 1
    return {"updated_rows": updated_rows, "updated_documents": updated_documents}


@frappe.whitelist()
def approve_current_rates(rows) -> dict:
    _require_rate_access()
    rows = _parse_json(rows, [])
    grouped = defaultdict(list)
    for row in rows:
        if row.get("doctype") in REVIEW_CONFIG and row.get("document") and row.get("row_name"):
            grouped[(row["doctype"], row["document"])].append(row["row_name"])

    approved = 0
    for (doctype, document), row_names in grouped.items():
        doc = frappe.get_doc(doctype, document)
        _assert_document_scope(doc)
        rate_field = REVIEW_CONFIG[doctype]["rate_field"]
        for child in doc.get("items") or []:
            if child.name not in row_names or flt(child.get(rate_field)) <= 0:
                continue
            if cint(doc.docstatus) == 0:
                _set_rate_metadata(
                    child,
                    STATUS_APPROVED,
                    child.get(RATE_SOURCE_FIELD) or SOURCE_MANUAL,
                    child.get(rate_field),
                    child.get(RATE_SOURCE_DETAIL_FIELD) or f"Reviewed by {frappe.session.user}",
                )
                child.custom_rate_reviewed_by = frappe.session.user
                child.custom_rate_reviewed_on = now_datetime()
            else:
                frappe.db.set_value(
                    REVIEW_CONFIG[doctype]["child_doctype"],
                    child.name,
                    {
                        RATE_STATUS_FIELD: STATUS_APPROVED,
                        SUGGESTED_RATE_FIELD: flt(child.get(rate_field)),
                        "custom_rate_reviewed_by": frappe.session.user,
                        "custom_rate_reviewed_on": now_datetime(),
                    },
                    update_modified=False,
                )
            approved += 1
        if cint(doc.docstatus) == 0:
            doc.flags.orderlift_stock_rate_review_rows = set(row_names)
            _set_parent_status(doc, [row.get(RATE_STATUS_FIELD) for row in doc.get("items") or []])
            doc.flags.ignore_permissions = True
            doc.save()
        else:
            _recompute_persisted_parent_status(doc)
    return {"approved_rows": approved}


@frappe.whitelist()
def refresh_suggestions() -> dict:
    _require_rate_access()
    documents = {(row["doctype"], row["document"]) for row in _review_rows({}) if row["docstatus"] == 0}
    refreshed = 0
    for doctype, document in documents:
        doc = frappe.get_doc(doctype, document)
        _assert_document_scope(doc)
        resolve_document_rates(doc)
        doc.flags.ignore_permissions = True
        doc.save()
        refreshed += 1
    return {"refreshed_documents": refreshed}


@frappe.whitelist()
def submit_documents(documents) -> dict:
    _require_rate_access()
    documents = _parse_json(documents, [])
    submitted = []
    for row in documents:
        doctype = (row.get("doctype") or "").strip()
        document = (row.get("document") or "").strip()
        if doctype not in REVIEW_CONFIG or not document:
            continue
        doc = frappe.get_doc(doctype, document)
        _assert_document_scope(doc)
        if cint(doc.docstatus) != 0:
            continue
        if not frappe.has_permission(doctype, "submit", doc=doc):
            frappe.throw(_("You do not have submit permission for {0} {1}.").format(doctype, document), frappe.PermissionError)
        validate_document_rates_for_submit(doc)
        doc.submit()
        submitted.append(document)
    return {"submitted": submitted}


def _review_rows(filters) -> list[dict]:
    company = resolve_current_company(user=frappe.session.user)
    if not company:
        return []
    allowed_warehouses = set(get_allowed_warehouses())
    if not allowed_warehouses:
        return []
    out = []
    for doctype, config in REVIEW_CONFIG.items():
        if filters.get("doctype") and filters.get("doctype") != doctype:
            continue
        parents = frappe.get_all(
            doctype,
            filters={
                "company": company,
                "docstatus": ["in", [0, 1]],
                RATE_STATUS_FIELD: ["in", [STATUS_MISSING, STATUS_PROVISIONAL, STATUS_APPROVED]],
            },
            fields=["name", "docstatus", "posting_date", "company", RATE_STATUS_FIELD],
            order_by="posting_date desc, modified desc",
            limit_page_length=0,
        )
        parent_map = {row.name: row for row in parents if cint(row.docstatus) == 0 or row.get(RATE_STATUS_FIELD) == STATUS_PROVISIONAL}
        if not parent_map:
            continue
        child_fields = [
            "name", "parent", "idx", "item_code", "item_name", "qty", "stock_uom",
            config["rate_field"], RATE_STATUS_FIELD, RATE_SOURCE_FIELD, RATE_SOURCE_DETAIL_FIELD,
            SUGGESTED_RATE_FIELD,
            *config["warehouse_fields"],
        ]
        children = frappe.get_all(
            config["child_doctype"],
            filters={"parent": ["in", list(parent_map)]},
            fields=list(dict.fromkeys(child_fields)),
            order_by="parent asc, idx asc",
            limit_page_length=0,
        )
        document_details = _document_details(doctype, list(parent_map))
        for child in children:
            warehouse = next(((child.get(field) or "").strip() for field in config["warehouse_fields"] if child.get(field)), "")
            if not warehouse or warehouse not in allowed_warehouses:
                continue
            status = child.get(RATE_STATUS_FIELD) or STATUS_NOT_REQUIRED
            if status == STATUS_NOT_REQUIRED:
                continue
            if filters.get("status") and filters.get("status") != status:
                continue
            parent = parent_map[child.parent]
            details = document_details.get(child.parent, {})
            search = (filters.get("search") or "").strip().lower()
            if search and search not in " ".join((child.parent, child.item_code or "", child.item_name or "", details.get("party") or "")).lower():
                continue
            out.append(
                {
                    "doctype": doctype,
                    "document": child.parent,
                    "row_name": child.name,
                    "docstatus": cint(parent.docstatus),
                    "parent_status": parent.get(RATE_STATUS_FIELD),
                    "posting_date": str(parent.posting_date or ""),
                    "party": details.get("party") or "",
                    "purpose": details.get("purpose") or "",
                    "item_code": child.item_code or "",
                    "item_name": child.item_name or child.item_code or "",
                    "qty": flt(child.qty),
                    "uom": child.stock_uom or "",
                    "warehouse": warehouse,
                    "current_rate": flt(child.get(config["rate_field"])),
                    "suggested_rate": flt(child.get(SUGGESTED_RATE_FIELD)),
                    "status": status,
                    "source": child.get(RATE_SOURCE_FIELD) or "",
                    "source_detail": child.get(RATE_SOURCE_DETAIL_FIELD) or "",
                    "editable": cint(parent.docstatus) == 0,
                }
            )
    return out


def _document_details(doctype, names) -> dict:
    if not names:
        return {}
    if doctype == "Purchase Receipt":
        rows = frappe.get_all("Purchase Receipt", filters={"name": ["in", names]}, fields=["name", "supplier_name", "supplier"])
        return {row.name: {"party": row.supplier_name or row.supplier or "", "purpose": "Purchase Receipt"} for row in rows}
    rows = frappe.get_all("Stock Entry", filters={"name": ["in", names]}, fields=["name", "purpose", "stock_entry_type"])
    return {row.name: {"party": "", "purpose": row.purpose or row.stock_entry_type or ""} for row in rows}


def _assert_document_scope(doc) -> None:
    company = resolve_current_company(user=frappe.session.user)
    if not company or doc.get("company") != company:
        frappe.throw(_("Document is outside your active company."), frappe.PermissionError)
    allowed = set(get_allowed_warehouses())
    if not allowed:
        frappe.throw(_("No warehouse access is configured."), frappe.PermissionError)
    config = REVIEW_CONFIG[doc.doctype]
    for row in doc.get("items") or []:
        warehouses = {(row.get(field) or "").strip() for field in config["warehouse_fields"] if row.get(field)}
        if not warehouses or not warehouses.issubset(allowed):
            frappe.throw(_("Document contains a warehouse outside your access."), frappe.PermissionError)


def _recompute_persisted_parent_status(doc) -> None:
    statuses = frappe.get_all(
        REVIEW_CONFIG[doc.doctype]["child_doctype"],
        filters={"parent": doc.name},
        pluck=RATE_STATUS_FIELD,
        limit_page_length=0,
    )
    if STATUS_MISSING in statuses:
        status = STATUS_MISSING
    elif STATUS_PROVISIONAL in statuses:
        status = STATUS_PROVISIONAL
    elif STATUS_APPROVED in statuses:
        status = STATUS_APPROVED
    else:
        status = STATUS_NOT_REQUIRED
    frappe.db.set_value(doc.doctype, doc.name, RATE_STATUS_FIELD, status, update_modified=False)


def _require_rate_access() -> None:
    if not can_manage_stock_rates():
        frappe.throw(_("You do not have permission to review stock rates."), frappe.PermissionError)


def _parse_json(value, default):
    if isinstance(value, str):
        return json.loads(value or ("[]" if isinstance(default, list) else "{}"))
    return value if value is not None else default
