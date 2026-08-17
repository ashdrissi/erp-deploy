"""Multi-source buying-price resolution and approved price-list publication."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, nowdate

from orderlift.menu_access import resolve_current_company
from orderlift.orderlift_sales.utils.price_list_scope import (
    get_visible_price_lists,
    validate_price_list_scope,
    validate_visible_price_list,
)
from orderlift.role_capabilities import CAPABILITY_PRIVILEGED_PRICING, user_has_capability


MANUAL_CHARGE_ITEM_CODES = {"OTHER-CHARGES", "TRANSPORTATION-CHARGE"}
DECISION_PENDING = "Pending"
DECISION_APPROVED = "Approved"
DECISION_SKIPPED = "Skipped"
DECISION_NO_CHANGE = "No Change"
REVIEW_FIELDS = (
    "custom_price_update_decision",
    "custom_update_price_list_on_submit",
    "custom_price_reviewed_by",
    "custom_price_reviewed_on",
    "custom_price_reviewed_rate",
    "custom_price_reviewed_loaded_rate",
    "custom_price_reviewed_source_buying_price_list",
    "custom_price_reviewed_source_currency",
    "custom_price_review_attestation",
)


@frappe.whitelist()
def get_purchase_order_price_candidates(doc: str | dict) -> dict:
    """Return the current lowest valid source for every populated draft row."""
    payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
    return {"rows": _resolve_document_candidates(payload)}


@frappe.whitelist()
def get_supplier_buying_price_lists(
    supplier: str,
    company: str,
    target_currency: str | None = None,
    reference_date: str | None = None,
) -> list[dict]:
    """Return selectable buying lists that contain active prices for this supplier."""
    supplier = _text(supplier)
    company = _text(company)
    if not supplier or not company:
        return []
    if not _supplier_allowed_for_company(supplier, company):
        return []
    target_currency = _text(target_currency) or _text(frappe.db.get_value("Company", company, "default_currency"))
    reference_date = _text(reference_date) or nowdate()

    conditions = ["(ip.supplier = %(supplier)s OR IFNULL(ip.supplier, '') = '')"]
    if _has_column("Item Price", "buying"):
        conditions.append("IFNULL(ip.buying, 0) = 1")
    if _has_column("Item Price", "enabled"):
        conditions.append("IFNULL(ip.enabled, 1) = 1")
    if _has_column("Price List", "enabled"):
        conditions.append("IFNULL(pl.enabled, 1) = 1")
    if _has_column("Price List", "custom_price_list_type"):
        conditions.append("pl.custom_price_list_type = 'Buying'")
    elif _has_column("Price List", "buying"):
        conditions.append("IFNULL(pl.buying, 0) = 1")
    if _has_column("Price List", "custom_company"):
        conditions.append("pl.custom_company = %(company)s")
    if _has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(reference_date)s)")
    if _has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(reference_date)s)")

    rows = frappe.db.sql(
        f"""
        SELECT ip.price_list, pl.currency AS source_currency, COUNT(*) AS item_price_count
        FROM `tabItem Price` ip
        INNER JOIN `tabPrice List` pl ON pl.name = ip.price_list
        WHERE {' AND '.join(conditions)}
        GROUP BY ip.price_list, pl.currency
        ORDER BY ip.price_list ASC
        """,
        {"supplier": supplier, "company": company, "reference_date": reference_date},
        as_dict=True,
    )
    allowed = []
    for row in rows:
        price_list = _text(row.get("price_list"))
        try:
            validate_visible_price_list(price_list, kind="buying", required=True, company=company)
        except Exception:
            continue
        source_currency = _text(row.get("source_currency"))
        allowed.append(
            {
                "price_list": price_list,
                "source_currency": source_currency,
                "exchange_rate": _resolve_exchange_rate(
                    source_currency, target_currency, reference_date, required=False
                ),
                "exchange_rate_source": "System",
                "item_price_count": cint(row.get("item_price_count")),
            }
        )
    return allowed


@frappe.whitelist()
def is_supplier_allowed_for_purchase_company(supplier: str, company: str) -> dict:
    return {"allowed": _supplier_allowed_for_company(supplier, company)}


@frappe.whitelist()
def get_currency_conversion_rate(source_currency: str, target_currency: str, reference_date: str | None = None) -> float:
    return _resolve_exchange_rate(_text(source_currency), _text(target_currency), _text(reference_date) or nowdate())


def can_manage_purchase_price_approvals(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    roles = set(frappe.get_roles(user) or [])
    return bool(
        roles.intersection({"Orderlift Admin", "System Manager", "Purchase Manager"})
        or user_has_capability(CAPABILITY_PRIVILEGED_PRICING, user=user, roles=roles)
    )


@frappe.whitelist()
def get_purchase_price_approval_access(
    company: str | None = None,
    target_currency: str | None = None,
    reference_date: str | None = None,
) -> dict:
    allowed = int(can_manage_purchase_price_approvals())
    price_lists = []
    company = _text(company) or resolve_current_company(user=frappe.session.user)
    target_currency = _text(target_currency) or _text(frappe.db.get_value("Company", company, "default_currency"))
    reference_date = _text(reference_date) or nowdate()
    if allowed:
        for price_list in get_visible_price_lists("buying", company=company, user=frappe.session.user):
            details = _price_list_exchange_details(price_list, target_currency, reference_date, required=False)
            price_lists.append(
                {
                    "price_list": price_list,
                    "currency": details["source_currency"],
                    "exchange_rate": details["exchange_rate"],
                }
            )
    return {
        "can_approve": allowed,
        "can_override_exchange_rate": allowed,
        "buying_price_lists": price_lists,
    }


@frappe.whitelist()
def get_purchase_order_price_reviews(status="Pending", supplier="", price_list="", item_code="") -> dict:
    """Return negotiated draft PO rows for the privileged multi-PO review page."""
    _require_price_approval_access()
    company = resolve_current_company(user=frappe.session.user)
    conditions = [
        "po.docstatus = 0",
        "po.company = %(company)s",
        "("
        "(IFNULL(poi.custom_loaded_buying_rate, 0) > 0 "
        "AND ABS(IFNULL(poi.rate, 0) - IFNULL(poi.custom_loaded_buying_rate, 0)) > 0.000001) "
        "OR (IFNULL(poi.custom_loaded_buying_rate, 0) <= 0 "
        "AND IFNULL(poi.rate, 0) > 0 AND IFNULL(poi.custom_source_item_price, '') = '')"
        ")",
    ]
    values = {"company": company}
    status = _text(status)
    if status and status != "All":
        conditions.append("IFNULL(poi.custom_price_update_decision, 'Pending') = %(status)s")
        values["status"] = status
    for fieldname, value, expression in (
        ("supplier", supplier, "po.supplier"),
        ("price_list", price_list, "poi.custom_source_buying_price_list"),
        ("item_code", item_code, "poi.item_code"),
    ):
        value = _text(value)
        if value:
            conditions.append(f"{expression} = %({fieldname})s")
            values[fieldname] = value
    rows = frappe.db.sql(
        f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date,
            po.supplier,
            po.supplier_name,
            po.company,
            po.currency,
            po.currency AS po_currency,
            poi.name AS purchase_order_item,
            poi.idx,
            poi.item_code,
            poi.item_name,
            poi.uom,
            poi.stock_uom,
            poi.conversion_factor,
            poi.custom_source_buying_price_list AS price_list,
            poi.custom_source_buying_rate AS source_rate,
            poi.custom_loaded_buying_currency AS source_currency,
            poi.custom_loaded_buying_uom AS source_uom,
            poi.custom_loaded_buying_rate AS loaded_rate,
            poi.rate AS negotiated_rate,
            poi.custom_price_variance_amount AS variance_amount,
            poi.custom_price_variance_percent AS variance_percent,
            CASE
                WHEN IFNULL(poi.custom_loaded_buying_rate, 0) <= 0
                    AND IFNULL(poi.custom_source_item_price, '') = ''
                THEN 'Create New Price'
                ELSE 'Update Existing Price'
            END AS review_type,
            IFNULL(poi.custom_price_update_decision, 'Pending') AS decision,
            poi.custom_price_reviewed_by AS reviewed_by,
            poi.custom_price_reviewed_on AS reviewed_on
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
        WHERE {' AND '.join(conditions)}
        ORDER BY po.transaction_date DESC, po.name DESC, poi.idx ASC
        """,
        values,
        as_dict=True,
    )
    target_options_by_context = {}
    for row in rows:
        context = (_text(row.get("po_currency")), _text(row.get("transaction_date")))
        if context not in target_options_by_context:
            target_options_by_context[context] = get_purchase_price_approval_access(
                company=company,
                target_currency=context[0],
                reference_date=context[1],
            )["buying_price_lists"]
        row["target_price_lists"] = target_options_by_context[context]
    access = get_purchase_price_approval_access(company=company)
    return {
        "rows": rows,
        "can_approve": 1,
        "company": company,
        "buying_price_lists": access["buying_price_lists"],
    }


@frappe.whitelist()
def set_purchase_order_price_review_decisions(decisions, attestation=0) -> dict:
    """Approve or skip negotiated prices across one or more draft Purchase Orders."""
    _require_price_approval_access()
    decisions = frappe.parse_json(decisions) if isinstance(decisions, str) else decisions
    decisions = decisions or []
    if not isinstance(decisions, list) or not decisions:
        frappe.throw(_("Select at least one negotiated price to review."))

    grouped = {}
    for value in decisions:
        purchase_order = _text(value.get("purchase_order"))
        item_name = _text(value.get("purchase_order_item") or value.get("item_name"))
        decision = _text(value.get("decision"))
        if not purchase_order or not item_name or decision not in {DECISION_APPROVED, DECISION_SKIPPED}:
            frappe.throw(_("Each review row needs a Purchase Order, item row, and valid decision."))
        grouped.setdefault(purchase_order, []).append(
            (item_name, decision, _text(value.get("target_price_list")))
        )

    if any(decision == DECISION_APPROVED for rows in grouped.values() for _item, decision, _target in rows) and not cint(attestation):
        frappe.throw(_("Confirm that approved prices may create or update buying price list records."))

    active_company = resolve_current_company(user=frappe.session.user)
    reviewed_on = now_datetime()
    updated = 0
    for purchase_order, values in grouped.items():
        doc = frappe.get_doc("Purchase Order", purchase_order)
        if cint(doc.docstatus) != 0:
            frappe.throw(_("Purchase Order {0} is no longer a draft.").format(purchase_order))
        if _text(doc.company) != _text(active_company):
            frappe.throw(_("Purchase Order {0} is outside your active company.").format(purchase_order), frappe.PermissionError)
        rows_by_name = {row.name: row for row in doc.items}
        for item_name, decision, target_price_list in values:
            row = rows_by_name.get(item_name)
            if not row or not _requires_price_review(row):
                frappe.throw(_("Purchase Order row {0} no longer requires price approval.").format(item_name))
            if decision == DECISION_APPROVED and _is_manual_new_price(row):
                if not target_price_list:
                    frappe.throw(_("Select a target Buying Price List for item {0}.").format(row.item_code))
                validate_visible_price_list(
                    target_price_list,
                    kind="buying",
                    required=True,
                    company=doc.company,
                    user=frappe.session.user,
                )
                details = _price_list_exchange_details(
                    target_price_list,
                    _text(doc.currency),
                    _text(doc.transaction_date) or nowdate(),
                )
                row.custom_source_buying_price_list = target_price_list
                row.custom_loaded_buying_currency = details["source_currency"]
                row.custom_loaded_buying_uom = row.uom
                row.custom_source_buying_rate = 0
            elif decision == DECISION_APPROVED:
                target_price_list = _text(row.custom_source_buying_price_list)
                current_currency = (
                    _text(frappe.db.get_value("Price List", target_price_list, "currency"))
                    if target_price_list
                    else ""
                )
                if target_price_list and _text(row.custom_loaded_buying_currency) != current_currency:
                    frappe.throw(
                        _(
                            "The buying-price source for item {0} is stale. Reload prices and approve it again."
                        ).format(row.item_code)
                    )
            row.custom_price_update_decision = decision
            row.custom_update_price_list_on_submit = 1 if decision == DECISION_APPROVED else 0
            row.custom_price_reviewed_by = frappe.session.user
            row.custom_price_reviewed_on = reviewed_on
            row.custom_price_reviewed_rate = flt(row.rate)
            row.custom_price_reviewed_loaded_rate = flt(row.custom_loaded_buying_rate)
            row.custom_price_reviewed_source_buying_price_list = _text(row.custom_source_buying_price_list)
            row.custom_price_reviewed_source_currency = _text(row.custom_loaded_buying_currency)
            row.custom_price_review_attestation = 1 if decision == DECISION_APPROVED else 0
            updated += 1
        doc.save(ignore_permissions=True)
    return {"updated": updated}


def sync_purchase_order_buying_price_lists(doc, method=None) -> list[str]:
    """Sanitize ordered source rows and derive the native primary buying list."""
    if not doc or not _doc_has_field(doc, "selected_buying_price_lists"):
        return _native_parent_price_lists(doc)

    company = _text(doc.get("company"))
    supplier = _text(doc.get("supplier"))
    if supplier and company and not _supplier_allowed_for_company(supplier, company):
        supplier = ""
        doc.supplier = ""
        if _doc_has_field(doc, "supplier_name"):
            doc.supplier_name = ""
    target_currency = _text(doc.get("currency")) or _text(frappe.db.get_value("Company", company, "default_currency"))
    reference_date = _text(doc.get("transaction_date")) or nowdate()
    supplier_details = {
        row["price_list"]: row
        for row in get_supplier_buying_price_lists(
            supplier,
            company,
            target_currency=target_currency,
            reference_date=reference_date,
        )
    }
    supplier_lists = set(supplier_details)
    unique = set()
    valid_rows = []
    for index, row in enumerate(doc.get("selected_buying_price_lists") or [], start=1):
        price_list = _text(row.get("price_list"))
        if not price_list or price_list in unique or (supplier and price_list not in supplier_lists):
            continue
        try:
            validate_visible_price_list(price_list, kind="buying", required=True, company=company)
        except Exception:
            continue
        details = supplier_details.get(price_list) or _price_list_exchange_details(
            price_list, target_currency, reference_date
        )
        rate_source = _text(row.get("exchange_rate_source")) or "System"
        requested_rate = flt(row.get("exchange_rate"))
        source_currency_changed = bool(
            _text(row.get("source_currency"))
            and _text(row.get("source_currency")) != details["source_currency"]
        )
        if source_currency_changed:
            rate_source = "System"
            requested_rate = 0
        if details["source_currency"] == target_currency:
            exchange_rate = 1.0
            rate_source = "System"
        elif rate_source == "Manual" and requested_rate > 0:
            _validate_manual_exchange_rate_change(doc, price_list, requested_rate)
            exchange_rate = requested_rate
        else:
            exchange_rate = flt(details["exchange_rate"]) or _resolve_exchange_rate(
                details["source_currency"], target_currency, reference_date
            )
            rate_source = "System"
        unique.add(price_list)
        valid_rows.append(
            {
                "price_list": price_list,
                "source_currency": details["source_currency"],
                "exchange_rate": exchange_rate,
                "exchange_rate_source": rate_source,
                "sequence": cint(row.get("sequence") or index * 10) or index * 10,
                "is_active": cint(row.get("is_active") if row.get("is_active") is not None else 1),
            }
        )

    valid_rows.sort(key=lambda row: (row["sequence"], row["price_list"]))
    pair_rates = {}
    for row in valid_rows:
        pair = (row["source_currency"], target_currency)
        previous_rate = pair_rates.get(pair)
        if previous_rate is not None and not _numbers_match(previous_rate, row["exchange_rate"]):
            frappe.throw(
                _("Selected buying lists using {0} to {1} must use the same exchange rate.").format(*pair)
            )
        pair_rates[pair] = row["exchange_rate"]
    if not valid_rows:
        for index, row in enumerate(supplier_details.values(), start=1):
            price_list = _text(row.get("price_list"))
            if not price_list or price_list in unique:
                continue
            unique.add(price_list)
            valid_rows.append(
                {
                    "price_list": price_list,
                    "source_currency": _text(row.get("source_currency")),
                    "exchange_rate": flt(row.get("exchange_rate")) or 1.0,
                    "exchange_rate_source": row.get("exchange_rate_source") or "System",
                    "sequence": index * 10,
                    "is_active": 1,
                }
            )
    doc.set("selected_buying_price_lists", [])
    for row in valid_rows:
        doc.append("selected_buying_price_lists", row)

    active = [row["price_list"] for row in valid_rows if row["is_active"]]
    primary = (active or [row["price_list"] for row in valid_rows] or [""])[0]
    if _doc_has_field(doc, "buying_price_list"):
        doc.buying_price_list = primary
    return active


def apply_purchase_order_buying_prices(doc, method=None, force=False) -> dict:
    """Refresh source snapshots without overwriting a negotiated draft rate."""
    if not doc or cint(doc.get("docstatus")) == 2:
        return {"rows": {}}

    price_lists = sync_purchase_order_buying_price_lists(doc)
    if not price_lists:
        return {"rows": {}}
    candidates = _resolve_document_candidates(doc, price_lists=price_lists)
    for row in doc.get("items") or []:
        item_code = _text(row.get("item_code"))
        if not item_code or _is_manual_charge(item_code):
            continue
        candidate = candidates.get(row.get("name") or row.get("idx") or item_code)
        if not candidate:
            continue
        _apply_candidate(row, candidate, force=force)
    _set_update_summary(doc)
    return {"rows": candidates}


def validate_purchase_order_buying_prices(doc, method=None) -> None:
    """Server-side source refresh and coverage validation for draft PO saves."""
    if not doc or cint(doc.get("docstatus")) == 2:
        return
    _protect_price_review_fields(doc)
    price_lists = sync_purchase_order_buying_price_lists(doc)
    if not _text(doc.get("supplier")):
        for row in doc.get("items") or []:
            _clear_buying_price_reference(row, clear_rate=True)
        _set_update_summary(doc)
        return
    selected_price_lists = set(price_lists)
    for row in doc.get("items") or []:
        row_price_list = _text(row.get("custom_source_buying_price_list"))
        if row_price_list and row_price_list not in selected_price_lists:
            _clear_buying_price_reference(row, clear_rate=True)
    item_rows = [
        row
        for row in (doc.get("items") or [])
        if _text(row.get("item_code")) and not _is_manual_charge(row.get("item_code"))
    ]
    if not item_rows:
        return
    candidates = _resolve_document_candidates(doc, price_lists=price_lists)
    available_lists = get_visible_price_lists("buying", company=_text(doc.get("company")), user=frappe.session.user)
    available_candidates = _resolve_document_candidates(doc, price_lists=available_lists)
    missing_rate = []
    available_unselected = []
    for row in item_rows:
        if _review_is_current(row):
            continue
        row_key = row.get("name") or row.get("idx") or _text(row.get("item_code"))
        candidate = candidates.get(row_key)
        if not candidate:
            source_item_price = _text(row.get("custom_source_item_price"))
            if source_item_price and frappe.db.exists("Item Price", source_item_price):
                source_list = _text(row.get("custom_source_buying_price_list")) or _text(
                    frappe.db.get_value("Item Price", source_item_price, "price_list")
                )
                available_unselected.append(
                    _("{0} ({1})").format(_text(row.get("item_code")), source_list or _("source list"))
                )
                continue
            available = available_candidates.get(row_key)
            if available:
                available_unselected.append(
                    _("{0} ({1})").format(_text(row.get("item_code")), available["price_list"])
                )
                continue
            if flt(row.get("rate")) <= 0:
                missing_rate.append(_text(row.get("item_code")))
                continue
            _mark_manual_new_price(row)
            continue
        _apply_candidate(row, candidate, force=False)
    if available_unselected:
        frappe.throw(
            _("These items already have a valid buying price in an unselected list: {0}. Re-add that list or select it as the row source.").format(
                ", ".join(sorted(set(available_unselected))[:10])
            )
        )
    if missing_rate:
        frappe.throw(
            _("Enter a positive direct buying rate for items with no valid price in any permitted Buying Price List: {0}").format(
                ", ".join(sorted(set(missing_rate))[:10])
            )
        )
    calculator = getattr(doc, "calculate_taxes_and_totals", None)
    if callable(calculator):
        calculator()
    _set_update_summary(doc)


def validate_purchase_order_price_update_decisions(doc, method=None) -> None:
    """Require an explicit submitter decision for each negotiated row."""
    if not doc or cint(doc.get("docstatus")) != 0:
        return
    pending = []
    for row in doc.get("items") or []:
        if not _requires_price_review(row):
            continue
        decision = _text(row.get("custom_price_update_decision"))
        if decision not in {DECISION_APPROVED, DECISION_SKIPPED} or not _review_is_current(row):
            pending.append(_text(row.get("item_code")) or str(row.get("idx") or "-"))
    if pending:
        frappe.throw(
            _("Choose whether to update the buying price list for negotiated items before submitting: {0}").format(
                ", ".join(pending[:10])
            )
        )


def publish_approved_purchase_order_prices(doc, method=None) -> None:
    """Update approved source prices and append a chart-ready immutable change log."""
    if not doc or cint(doc.get("docstatus")) != 1:
        return
    for row in doc.get("items") or []:
        if not _text(row.get("item_code")) or _is_manual_charge(row.get("item_code")):
            continue
        _publish_row_price_change(doc, row)


def _resolve_document_candidates(doc, *, price_lists: list[str] | None = None) -> dict:
    price_lists = price_lists if price_lists is not None else _active_price_lists(doc)
    if not price_lists:
        return {}
    company = _text(_value(doc, "company"))
    # Drop lists the user can no longer use instead of throwing: a stale or
    # unshared list must fall through to the missing-price flow ("enter a direct
    # buying rate"), not a bare permission error. Mirrors the skip in
    # sync_purchase_order_buying_price_lists.
    visible = []
    for price_list in price_lists:
        try:
            validate_visible_price_list(price_list, kind="buying", required=True, company=company)
        except Exception:
            continue
        visible.append(price_list)
    price_lists = visible
    if not price_lists:
        return {}
    supplier = _text(_value(doc, "supplier"))
    currency = _text(_value(doc, "currency"))
    reference_date = _text(_value(doc, "transaction_date")) or nowdate()
    rows = [
        row
        for row in (_value(doc, "items") or [])
        if _text(_value(row, "item_code")) and not _is_manual_charge(_value(row, "item_code"))
    ]
    if not rows:
        return {}
    item_codes = sorted({_text(_value(row, "item_code")) for row in rows})
    price_list_contexts = _price_list_contexts(doc, price_lists, currency, reference_date)
    candidates_by_item = _load_candidates(item_codes, price_list_contexts, supplier, reference_date)
    resolved = {}
    for row in rows:
        compatible = [
            candidate
            for candidate in candidates_by_item.get(_text(_value(row, "item_code")), [])
            if _candidate_matches_row(candidate, row)
        ]
        explicit_source = (
            _text(_value(row, "custom_source_buying_price_list"))
            if cint(_value(row, "custom_lock_buying_price_source"))
            else ""
        )
        if explicit_source:
            compatible = [candidate for candidate in compatible if candidate["price_list"] == explicit_source]
        if not compatible:
            continue
        compatible.sort(key=lambda candidate: (candidate["normalized_rate"], candidate["sequence"], candidate["name"]))
        selected = dict(compatible[0])
        selected["rate"] = _candidate_rate_for_row(selected, row)
        selected["row_key"] = _value(row, "name") or _value(row, "idx") or _text(_value(row, "item_code"))
        resolved[selected["row_key"]] = selected
    return resolved


def _active_price_lists(doc) -> list[str]:
    rows = list(_value(doc, "selected_buying_price_lists") or [])
    selected = []
    for row in sorted(rows, key=lambda value: (cint(_value(value, "sequence") or 0), _text(_value(value, "price_list")))):
        price_list = _text(_value(row, "price_list"))
        if price_list and cint(_value(row, "is_active") if _value(row, "is_active") is not None else 1) and price_list not in selected:
            selected.append(price_list)
    return selected


def _native_parent_price_lists(doc) -> list[str]:
    price_list = _text(_value(doc, "buying_price_list"))
    return [price_list] if price_list else []


def _load_candidates(item_codes, price_list_contexts, supplier, reference_date) -> dict[str, list[dict]]:
    price_lists = list(price_list_contexts)
    fields = ["name", "item_code", "price_list", "price_list_rate"]
    for fieldname in ("supplier", "uom", "currency", "valid_from", "valid_upto"):
        if _has_column("Item Price", fieldname):
            fields.append(fieldname)
    if frappe.db.has_column("Item Price", "packing_unit"):
        fields.append("packing_unit")
    filters = {"item_code": ["in", item_codes], "price_list": ["in", price_lists]}
    if _has_column("Item Price", "buying"):
        filters["buying"] = 1
    if _has_column("Item Price", "enabled"):
        filters["enabled"] = 1
    rows = frappe.db.get_all(
        "Item Price",
        filters=filters,
        fields=fields,
        order_by="valid_from desc, modified desc",
        limit_page_length=0,
    )
    sequence = {name: index for index, name in enumerate(price_lists)}
    grouped = {}
    for row in rows:
        if not _is_active_on(row, reference_date) or (_text(row.get("supplier")) not in {"", supplier}):
            continue
        context = price_list_contexts[row.price_list]
        source_currency = _text(row.get("currency")) or context["source_currency"]
        if source_currency != context["source_currency"]:
            frappe.throw(
                _("Item Price {0} currency {1} does not match Price List {2} currency {3}.").format(
                    row.name, source_currency, row.price_list, context["source_currency"]
                )
            )
        source_rate = flt(row.price_list_rate)
        normalized = source_rate * flt(context["exchange_rate"])
        if normalized <= 0:
            continue
        grouped.setdefault(row.item_code, []).append(
            {
                "name": row.name,
                "item_code": row.item_code,
                "price_list": row.price_list,
                "source_rate": source_rate,
                "source_currency": source_currency,
                "source_exchange_rate": flt(context["exchange_rate"]),
                "uom": _text(row.get("uom")),
                "supplier": _text(row.get("supplier")),
                "packing_unit": cint(getattr(row, "packing_unit", 0) or 0),
                "normalized_rate": normalized,
                "sequence": sequence.get(row.price_list, len(price_lists)),
            }
        )
    return grouped


def _candidate_matches_row(candidate, row) -> bool:
    row_uom = _text(_value(row, "uom"))
    stock_uom = _text(_value(row, "stock_uom"))
    source_uom = candidate["uom"]
    if source_uom and source_uom not in {row_uom, stock_uom}:
        return False
    packing_unit = candidate["packing_unit"]
    qty = flt(_value(row, "qty"))
    if packing_unit > 0 and qty > 0 and not _multiple_of(qty, packing_unit):
        return False
    return True


def _candidate_rate_for_row(candidate, row) -> float:
    rate = flt(candidate["normalized_rate"])
    source_uom = candidate["uom"]
    row_uom = _text(_value(row, "uom"))
    stock_uom = _text(_value(row, "stock_uom"))
    conversion_factor = flt(_value(row, "conversion_factor")) or 1
    if source_uom and source_uom == stock_uom and row_uom and row_uom != stock_uom:
        rate *= conversion_factor
    return _round_rate_for_row(rate, row)


def _apply_candidate(row, candidate, *, force: bool) -> None:
    loaded_before = flt(_value(row, "custom_loaded_buying_rate"))
    current_rate = flt(_value(row, "rate"))
    negotiated = loaded_before > 0 and not _numbers_match(current_rate, loaded_before)
    if force or current_rate <= 0 or not negotiated:
        _set(row, "rate", candidate["rate"])
        _set(row, "amount", candidate["rate"] * flt(_value(row, "qty")))
        current_rate = candidate["rate"]
    _set(row, "price_list_rate", candidate["rate"])
    _set(row, "custom_source_buying_price_list", candidate["price_list"])
    _set(row, "custom_source_item_price", candidate["name"])
    _set(row, "custom_source_buying_rate", candidate["source_rate"])
    _set(row, "custom_loaded_buying_rate", candidate["rate"])
    _set(row, "custom_loaded_buying_currency", candidate["source_currency"])
    _set(row, "custom_loaded_buying_uom", candidate["uom"])
    _set(row, "custom_price_variance_amount", current_rate - candidate["rate"])
    variance = ((current_rate - candidate["rate"]) / candidate["rate"] * 100.0) if candidate["rate"] else 0.0
    _set(row, "custom_price_variance_percent", variance)
    if not _requires_price_review(row):
        _set(row, "custom_price_update_decision", DECISION_NO_CHANGE)
        _set(row, "custom_update_price_list_on_submit", 0)
        _clear_price_review(row)
    elif _text(_value(row, "custom_price_update_decision")) not in {DECISION_APPROVED, DECISION_SKIPPED} or not _review_is_current(row):
        _set(row, "custom_price_update_decision", DECISION_PENDING)
        _clear_price_review(row)


def _publish_row_price_change(doc, row) -> None:
    if not _requires_price_review(row):
        return
    decision = _text(row.get("custom_price_update_decision"))
    existing_log = frappe.db.get_value(
        "Buying Price Change Log",
        {"purchase_order": doc.name, "purchase_order_item": row.name},
        "name",
    )
    if existing_log:
        _set(row, "custom_price_update_log", existing_log)
        return

    price_list = _text(row.get("custom_source_buying_price_list"))
    source_name = _text(row.get("custom_source_item_price"))
    old_rate = flt(row.get("custom_loaded_buying_rate"))
    source_currency = _text(row.get("custom_loaded_buying_currency"))
    old_source_rate = flt(row.get("custom_source_buying_rate"))
    new_source_rate = old_source_rate
    source_exchange_rate = (
        _selected_exchange_rate(doc, price_list, source_currency)
        if price_list
        else 1.0
    )
    item_price = None
    change_type = DECISION_SKIPPED
    if decision == DECISION_APPROVED and cint(row.get("custom_update_price_list_on_submit")):
        item_price, old_source_rate, new_source_rate, change_type = _update_item_price_from_row(
            doc, row, price_list, source_name, source_exchange_rate
        )
    log = frappe.get_doc(
        {
            "doctype": "Buying Price Change Log",
            "company": doc.company,
            "supplier": doc.supplier,
            "item_code": row.item_code,
            "price_list": price_list,
            "item_price": item_price or "",
            "uom": row.uom,
            "source_uom": row.get("custom_loaded_buying_uom") or row.uom,
            "currency": doc.currency,
            "source_currency": source_currency,
            "source_exchange_rate": source_exchange_rate,
            "old_rate": old_rate,
            "new_rate": flt(row.rate),
            "delta_amount": flt(row.rate) - old_rate if old_rate else 0.0,
            "delta_percent": ((flt(row.rate) - old_rate) / old_rate * 100.0) if old_rate else 0.0,
            "change_type": change_type,
            "source_loaded_rate": flt(row.get("custom_loaded_buying_rate")),
            "old_source_rate": old_source_rate,
            "new_source_rate": new_source_rate,
            "source_item_price": source_name,
            "purchase_order": doc.name,
            "purchase_order_item": row.name,
            "approved_by": row.get("custom_price_reviewed_by") or frappe.session.user,
            "approved_on": row.get("custom_price_reviewed_on") or now_datetime(),
        }
    )
    log.insert(ignore_permissions=True)
    _set(row, "custom_price_update_log", log.name)
    if row.name:
        frappe.db.set_value(
            "Purchase Order Item",
            row.name,
            "custom_price_update_log",
            log.name,
            update_modified=False,
        )


def _update_item_price_from_row(doc, row, price_list, source_name, source_exchange_rate):
    if not price_list:
        frappe.throw(_("A negotiated price needs a selected buying price list."))
    validate_price_list_scope(price_list, kind="buying", required=True, company=_text(doc.company))
    source = frappe.get_doc("Item Price", source_name) if source_name and frappe.db.exists("Item Price", source_name) else None
    if source and _text(source.supplier) not in {"", _text(doc.supplier)}:
        source = None
    source_currency = _text(source.currency) if source else _text(frappe.db.get_value("Price List", price_list, "currency"))
    source_uom = _text(source.uom) if source else _text(row.uom)
    rate = _rate_in_source_context(row, source_uom, source_exchange_rate)
    if source:
        old_rate = flt(source.price_list_rate)
        source.price_list_rate = rate
        source.save(ignore_permissions=True)
        return source.name, old_rate, rate, "Updated"

    item_price = frappe.new_doc("Item Price")
    item_price.item_code = row.item_code
    item_price.price_list = price_list
    item_price.price_list_rate = rate
    item_price.currency = source_currency
    item_price.uom = source_uom
    item_price.supplier = doc.supplier
    item_price.buying = 1
    item_price.selling = 0
    item_price.valid_from = doc.transaction_date or nowdate()
    item_price.insert(ignore_permissions=True)
    return item_price.name, 0.0, rate, "Created"


def _rate_in_source_context(row, source_uom, source_exchange_rate) -> float:
    source_exchange_rate = flt(source_exchange_rate)
    if source_exchange_rate <= 0:
        frappe.throw(_("A positive source-to-PO exchange rate is required before updating the buying price."))
    rate = flt(row.rate) / source_exchange_rate
    row_uom = _text(row.uom)
    stock_uom = _text(row.stock_uom)
    if source_uom and source_uom == stock_uom and row_uom and row_uom != stock_uom:
        rate /= flt(row.conversion_factor) or 1
    return rate


def _set_update_summary(doc) -> None:
    if not _doc_has_field(doc, "custom_buying_price_update_summary"):
        return
    changed = [row for row in (doc.get("items") or []) if _requires_price_review(row)]
    doc.custom_buying_price_update_summary = json.dumps(
        {"negotiated_rows": len(changed), "pending_rows": sum(_text(row.get("custom_price_update_decision")) == DECISION_PENDING for row in changed)}
    )


def _is_changed_from_loaded(row) -> bool:
    loaded = flt(_value(row, "custom_loaded_buying_rate"))
    return loaded > 0 and not _numbers_match(flt(_value(row, "rate")), loaded)


def _is_manual_new_price(row) -> bool:
    return (
        flt(_value(row, "rate")) > 0
        and flt(_value(row, "custom_loaded_buying_rate")) <= 0
        and not _text(_value(row, "custom_source_item_price"))
    )


def _requires_price_review(row) -> bool:
    return _is_changed_from_loaded(row) or _is_manual_new_price(row)


def _mark_manual_new_price(row) -> None:
    _set(row, "custom_source_item_price", "")
    _set(row, "custom_source_buying_rate", 0)
    _set(row, "custom_loaded_buying_rate", 0)
    price_list = _text(_value(row, "custom_source_buying_price_list"))
    source_currency = _text(frappe.db.get_value("Price List", price_list, "currency")) if price_list else ""
    _set(row, "custom_loaded_buying_currency", source_currency)
    _set(row, "custom_loaded_buying_uom", _text(_value(row, "uom")))
    _set(row, "custom_price_variance_amount", 0)
    _set(row, "custom_price_variance_percent", 0)
    if not _review_is_current(row):
        _set(row, "custom_price_update_decision", DECISION_PENDING)
        _clear_price_review(row)


def _review_is_current(row) -> bool:
    decision = _text(_value(row, "custom_price_update_decision"))
    if decision not in {DECISION_APPROVED, DECISION_SKIPPED}:
        return False
    if not _value(row, "custom_price_reviewed_by") or not _value(row, "custom_price_reviewed_on"):
        return False
    if not cint(_value(row, "custom_price_review_attestation")) and decision == DECISION_APPROVED:
        return False
    if not _numbers_match(_value(row, "custom_price_reviewed_rate"), _value(row, "rate")):
        return False
    if not _numbers_match(_value(row, "custom_price_reviewed_loaded_rate"), _value(row, "custom_loaded_buying_rate")):
        return False
    if _text(_value(row, "custom_price_reviewed_source_buying_price_list")) != _text(
        _value(row, "custom_source_buying_price_list")
    ):
        return False
    if _text(_value(row, "custom_price_reviewed_source_currency")) != _text(
        _value(row, "custom_loaded_buying_currency")
    ):
        return False
    price_list = _text(_value(row, "custom_source_buying_price_list"))
    if price_list:
        current_currency = _text(frappe.db.get_value("Price List", price_list, "currency"))
        if current_currency != _text(_value(row, "custom_loaded_buying_currency")):
            return False
    return can_manage_purchase_price_approvals(_value(row, "custom_price_reviewed_by"))


def _clear_price_review(row) -> None:
    _set(row, "custom_update_price_list_on_submit", 0)
    for fieldname in REVIEW_FIELDS[2:]:
        if fieldname.endswith(("_by", "_on")):
            value = None
        elif fieldname in {
            "custom_price_reviewed_source_buying_price_list",
            "custom_price_reviewed_source_currency",
        }:
            value = ""
        else:
            value = 0
        _set(row, fieldname, value)


def _clear_buying_price_reference(row, *, clear_rate: bool = False) -> None:
    had_loaded_price = bool(
        _text(_value(row, "custom_source_buying_price_list"))
        or _text(_value(row, "custom_source_item_price"))
        or flt(_value(row, "custom_loaded_buying_rate"))
        or flt(_value(row, "price_list_rate"))
    )
    _set(row, "price_list_rate", 0)
    _set(row, "custom_source_buying_price_list", "")
    _set(row, "custom_source_item_price", "")
    _set(row, "custom_lock_buying_price_source", 0)
    _set(row, "custom_source_buying_rate", 0)
    _set(row, "custom_loaded_buying_rate", 0)
    _set(row, "custom_loaded_buying_currency", "")
    _set(row, "custom_loaded_buying_uom", "")
    _set(row, "custom_price_variance_amount", 0)
    _set(row, "custom_price_variance_percent", 0)
    _clear_price_review(row)
    if clear_rate and had_loaded_price:
        _set(row, "rate", 0)
        _set(row, "amount", 0)


def _supplier_company(supplier: str) -> str:
    has_column = getattr(getattr(frappe, "db", None), "has_column", None)
    if not supplier or not callable(has_column) or not has_column("Supplier", "custom_company"):
        return ""
    return _text(frappe.db.get_value("Supplier", supplier, "custom_company"))


def _supplier_allowed_for_company(supplier: str, company: str) -> bool:
    supplier = _text(supplier)
    company = _text(company)
    if not supplier or not company:
        return False
    if not _supplier_company(supplier):
        return True
    from orderlift.orderlift_crm.party_management import party_has_company_access

    return party_has_company_access("Supplier", supplier, company)


def _protect_price_review_fields(doc) -> None:
    if can_manage_purchase_price_approvals():
        return
    before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    previous = {row.name: row for row in (before.items if before else [])}
    for row in doc.get("items") or []:
        old = previous.get(row.name)
        if not old:
            _clear_price_review(row)
            if _is_changed_from_loaded(row):
                _set(row, "custom_price_update_decision", DECISION_PENDING)
            continue
        if _review_is_current(old):
            _set(row, "custom_source_buying_price_list", _value(old, "custom_source_buying_price_list"))
            _set(row, "custom_loaded_buying_currency", _value(old, "custom_loaded_buying_currency"))
            _set(row, "custom_loaded_buying_uom", _value(old, "custom_loaded_buying_uom"))
        for fieldname in REVIEW_FIELDS:
            _set(row, fieldname, _value(old, fieldname))


def _require_price_approval_access() -> None:
    if not can_manage_purchase_price_approvals():
        frappe.throw(_("Only privileged pricing users can approve negotiated buying prices."), frappe.PermissionError)


def _resolve_exchange_rate(source_currency, target_currency, rate_date, required=True) -> float:
    if not source_currency or not target_currency:
        frappe.throw(_("Source currency and Purchase Order currency are required to load buying prices."))
    if source_currency == target_currency:
        return 1.0
    try:
        from erpnext.setup.utils import get_exchange_rate

        rate = flt(get_exchange_rate(source_currency, target_currency, rate_date))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Purchase order price currency conversion failed")
        rate = 0.0
    if rate <= 0:
        if not required:
            return 0.0
        frappe.throw(
            _("No {0} to {1} exchange rate is available for {2}.").format(
                source_currency, target_currency, rate_date
            )
        )
    return rate


def _price_list_exchange_details(price_list, target_currency, reference_date, required=True) -> dict:
    source_currency = _text(frappe.db.get_value("Price List", price_list, "currency"))
    return {
        "source_currency": source_currency,
        "exchange_rate": _resolve_exchange_rate(
            source_currency,
            target_currency,
            reference_date,
            required=required,
        ),
    }


def _price_list_contexts(doc, price_lists, target_currency, reference_date) -> dict[str, dict]:
    selected_rows = {
        _text(_value(row, "price_list")): row for row in (_value(doc, "selected_buying_price_lists") or [])
    }
    contexts = {}
    for price_list in price_lists:
        source_currency = _text(frappe.db.get_value("Price List", price_list, "currency"))
        selected = selected_rows.get(price_list)
        rate_source = _text(_value(selected, "exchange_rate_source")) if selected else ""
        selected_rate = flt(_value(selected, "exchange_rate")) if selected else 0
        if source_currency != target_currency and rate_source == "Manual" and selected_rate > 0:
            exchange_rate = selected_rate
        else:
            exchange_rate = _resolve_exchange_rate(source_currency, target_currency, reference_date)
        contexts[price_list] = {"source_currency": source_currency, "exchange_rate": exchange_rate}
    return contexts


def _selected_exchange_rate(doc, price_list, source_currency) -> float:
    target_currency = _text(doc.currency)
    reference_date = _text(doc.transaction_date) or nowdate()
    contexts = _price_list_contexts(doc, [price_list], target_currency, reference_date)
    context = contexts[price_list]
    if source_currency and context["source_currency"] != source_currency:
        frappe.throw(
            _(
                "The buying-price source for Price List {0} is stale ({1} snapshot, {2} current). Reload prices and approve it again."
            ).format(price_list, source_currency, context["source_currency"])
        )
    return flt(context["exchange_rate"])


def _validate_manual_exchange_rate_change(doc, price_list, exchange_rate) -> None:
    if can_manage_purchase_price_approvals():
        return
    before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    same_target_currency = bool(before and _text(before.get("currency")) == _text(doc.get("currency")))
    for row in (before.get("selected_buying_price_lists") if before else []) or []:
        if (
            same_target_currency
            and _text(row.get("price_list")) == price_list
            and _text(row.get("exchange_rate_source")) == "Manual"
            and _numbers_match(row.get("exchange_rate"), exchange_rate)
        ):
            return
    frappe.throw(
        _("Only Purchase Managers or privileged pricing users can override buying-list exchange rates."),
        frappe.PermissionError,
    )


def _round_rate_for_row(value, row) -> float:
    precision_getter = getattr(row, "precision", None)
    precision = precision_getter("rate") if callable(precision_getter) else None
    precision = cint(precision) if precision is not None else 9
    return flt(value, precision)


def _is_active_on(row, reference_date) -> bool:
    return (not row.get("valid_from") or str(row.get("valid_from")) <= str(reference_date)) and (
        not row.get("valid_upto") or str(row.get("valid_upto")) >= str(reference_date)
    )


def _multiple_of(value, unit) -> bool:
    remainder = flt(value) % cint(unit)
    return abs(remainder) <= 0.000001 or abs(remainder - cint(unit)) <= 0.000001


def _is_manual_charge(item_code) -> bool:
    return _text(item_code) in MANUAL_CHARGE_ITEM_CODES


def _numbers_match(left, right) -> bool:
    return abs(flt(left) - flt(right)) <= 0.000001


def _doc_has_field(doc, fieldname) -> bool:
    getter = getattr(getattr(doc, "meta", None), "get_field", None)
    return bool(getter(fieldname)) if callable(getter) else True


def _has_column(doctype, fieldname) -> bool:
    return bool(getattr(frappe, "db", None) and frappe.db.has_column(doctype, fieldname))


def _value(doc, fieldname, default=None):
    getter = getattr(doc, "get", None)
    return getter(fieldname, default) if callable(getter) else getattr(doc, fieldname, default)


def _set(doc, fieldname, value) -> None:
    setter = getattr(doc, "set", None)
    if callable(setter):
        setter(fieldname, value)
    else:
        setattr(doc, fieldname, value)


def _text(value) -> str:
    return str(value or "").strip()
