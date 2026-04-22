from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


DEFAULT_STALE_DAYS = 90
DEFAULT_LOOKBACK_DAYS = 180
DEFAULT_MIN_SAVINGS_PERCENT = 5.0
PRICE_MATCH_TOLERANCE = 0.01

SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2}


@frappe.whitelist()
def get_pricing_alerts(doc=None, items=None):
    payload = _parse_payload(doc) or {}
    item_rows = _parse_items(items, payload)

    settings = _get_alert_settings()
    buying_price_list = (payload.get("buying_price_list") or "").strip()

    summary = {
        "price_list_count": 0,
        "price_list_name": buying_price_list,
        "last_purchase_count": 0,
        "manual_count": 0,
        "total_items": len(item_rows),
        "expired_count": 0,
        "stale_count": 0,
        "unknown_count": 0,
        "cheaper_suppliers_count": 0,
        "is_all_clean": True,
    }

    if not item_rows:
        return {"summary": summary, "alerts": [], "settings": settings}

    reference_date = getdate(payload.get("transaction_date") or nowdate())
    supplier = (payload.get("supplier") or "").strip()
    company = (payload.get("company") or "").strip()
    conversion_rate = flt(payload.get("conversion_rate") or 1) or 1

    alerts = []
    for row in item_rows:
        item_code = (row.get("item_code") or "").strip()
        item_name = (row.get("item_name") or "").strip() or item_code

        try:
            analysis = _analyze_item(
                row=row,
                buying_price_list=buying_price_list,
                supplier=supplier,
                company=company,
                conversion_rate=conversion_rate,
                reference_date=reference_date,
                settings=settings,
            )
        except Exception:
            frappe.log_error(
                title="Purchase Order Pricing Alerts Row Analysis Failed",
                message=(
                    f"Purchase pricing alert analysis failed for item {item_code or '[missing item]'}\n"
                    f"supplier={supplier or '[blank]'}\n"
                    f"buying_price_list={buying_price_list or '[blank]'}\n"
                    f"row={frappe.as_json(row)}\n\n"
                    f"{frappe.get_traceback()}"
                ),
            )
            analysis = {
                "source": "manual_no_reference",
                "alerts": [
                    _build_alert(
                        item_code=item_code,
                        item_name=item_name,
                        rate=flt(row.get("rate") or 0),
                        severity="warning",
                        alert_type="analysis_error",
                        source="manual_no_reference",
                        message=_("Pricing source analysis could not be completed for this row. Review the rate manually."),
                        extra={},
                    )
                ],
            }

        if analysis["source"] == "price_list":
            summary["price_list_count"] += 1
        elif analysis["source"] == "last_purchase":
            summary["last_purchase_count"] += 1
        else:
            summary["manual_count"] += 1

        for alert in analysis["alerts"]:
            alert_type = alert["type"]
            if alert_type == "expired_price_list":
                summary["expired_count"] += 1
            elif alert_type == "stale_last_purchase":
                summary["stale_count"] += 1
            elif alert_type == "no_reference":
                summary["unknown_count"] += 1
            elif alert_type == "better_supplier_available":
                summary["cheaper_suppliers_count"] += 1
            alerts.append(alert)

    alerts.sort(key=lambda row: (SEVERITY_ORDER.get(row["severity"], 99), row["item_code"], row["type"]))
    summary["is_all_clean"] = not alerts
    return {"summary": summary, "alerts": alerts, "settings": settings}


def _parse_payload(doc):
    if not doc:
        return {}
    if isinstance(doc, str):
        return frappe.parse_json(doc) or {}
    return doc


def _parse_items(items, payload):
    parsed = items
    if parsed is None:
        parsed = payload.get("items") or []
    if isinstance(parsed, str):
        parsed = frappe.parse_json(parsed) or []
    return [frappe._dict(row) for row in parsed if (row.get("item_code") or "").strip()]


def _get_alert_settings():
    return {
        "stale_days": cint(
            _get_single_value_if_exists(
                "Buying Settings", "custom_stale_purchase_threshold_days", DEFAULT_STALE_DAYS
            )
        ),
        "supplier_price_lookback_days": cint(
            _get_single_value_if_exists(
                "Buying Settings", "custom_supplier_price_lookback_days", DEFAULT_LOOKBACK_DAYS
            )
        ),
        "better_supplier_min_savings_percent": flt(
            _get_single_value_if_exists(
                "Buying Settings", "custom_better_supplier_min_savings_percent", DEFAULT_MIN_SAVINGS_PERCENT
            )
        ),
    }


def _get_single_value_if_exists(doctype, fieldname, default):
    meta = frappe.get_meta(doctype)
    if not meta.get_field(fieldname):
        return default
    return frappe.db.get_single_value(doctype, fieldname) or default


def _analyze_item(*, row, buying_price_list, supplier, company, conversion_rate, reference_date, settings):
    item_code = (row.get("item_code") or "").strip()
    item_name = (row.get("item_name") or "").strip() or item_code
    uom = (row.get("uom") or "").strip()
    stock_uom = (row.get("stock_uom") or uom).strip()
    qty = flt(row.get("qty") or 0)
    current_rate = flt(row.get("rate") or 0)
    price_list_rate = flt(row.get("price_list_rate") or 0)
    last_purchase_rate = flt(row.get("last_purchase_rate") or 0)
    discount_percentage = flt(row.get("discount_percentage") or 0)
    discount_amount = flt(row.get("discount_amount") or 0)
    conversion_factor = flt(row.get("conversion_factor") or 1) or 1
    base_rate = flt(row.get("base_rate") or 0) or (current_rate * conversion_rate)

    price_context = _get_price_list_context(
        item_code=item_code,
        buying_price_list=buying_price_list,
        supplier=supplier,
        uom=uom,
        stock_uom=stock_uom,
        qty=qty,
        reference_date=reference_date,
    )
    last_purchase_context = _get_last_purchase_context(item_code=item_code, company=company)
    source = _resolve_rate_source(
        current_rate=current_rate,
        price_list_rate=price_list_rate,
        discount_percentage=discount_percentage,
        discount_amount=discount_amount,
        qty=qty,
        last_purchase_rate=last_purchase_rate,
    )

    alerts = []

    if source == "price_list" and price_context["state"] == "expired":
        expired = price_context["expired_record"] or {}
        alerts.append(
            _build_alert(
                item_code=item_code,
                item_name=item_name,
                rate=current_rate,
                severity="warning",
                alert_type="expired_price_list",
                source=source,
                message=_("Item Price from {0} expired on {1}.").format(
                    buying_price_list or _("the selected price list"), expired.get("valid_upto") or _("unknown date")
                ),
                extra={
                    "price_list": buying_price_list,
                    "valid_upto": expired.get("valid_upto"),
                },
            )
        )

    if source == "last_purchase" and last_purchase_context:
        days_since = cint(last_purchase_context.get("days_since") or 0)
        if days_since > settings["stale_days"]:
            alerts.append(
                _build_alert(
                    item_code=item_code,
                    item_name=item_name,
                    rate=current_rate,
                    severity="warning",
                    alert_type="stale_last_purchase",
                    source=source,
                    message=_("Using last purchase rate from {0} days ago ({1}).").format(
                        days_since, last_purchase_context.get("transaction_date")
                    ),
                    extra={
                        "transaction_date": last_purchase_context.get("transaction_date"),
                        "supplier": last_purchase_context.get("supplier"),
                        "days_since": days_since,
                        "threshold_days": settings["stale_days"],
                    },
                )
            )

    if source == "manual_override":
        alerts.append(
            _build_alert(
                item_code=item_code,
                item_name=item_name,
                rate=current_rate,
                severity="warning",
                alert_type="manual_override",
                source=source,
                message=_("Rate was adjusted manually and no longer matches the detected reference source."),
                extra={
                    "price_list_rate": price_list_rate,
                    "last_purchase_rate": last_purchase_rate,
                },
            )
        )
    elif source == "manual_no_reference":
        alerts.append(
            _build_alert(
                item_code=item_code,
                item_name=item_name,
                rate=current_rate,
                severity="danger",
                alert_type="no_reference",
                source=source,
                message=_("No Item Price or last purchase reference was found for this rate."),
                extra={},
            )
        )

    if price_context["state"] == "packing_unit_mismatch" and source != "price_list":
        alerts.append(
            _build_alert(
                item_code=item_code,
                item_name=item_name,
                rate=current_rate,
                severity="info",
                alert_type="packing_unit_mismatch",
                source=source,
                message=_("A price list exists, but the quantity does not match the Item Price packing increment."),
                extra={"packing_unit": price_context["packing_unit"]},
            )
        )

    current_base_rate_per_stock = _normalize_base_rate_per_stock(base_rate, conversion_factor)
    better_supplier = _get_better_supplier_offer(
        item_code=item_code,
        current_supplier=supplier,
        current_company=company,
        current_base_rate_per_stock=current_base_rate_per_stock,
        reference_date=reference_date,
        lookback_days=settings["supplier_price_lookback_days"],
        min_savings_percent=settings["better_supplier_min_savings_percent"],
    )
    if better_supplier:
        alerts.append(
            _build_alert(
                item_code=item_code,
                item_name=item_name,
                rate=current_rate,
                severity="info",
                alert_type="better_supplier_available",
                source=source,
                message=_("{0} recently bought this from {1} at {2}% lower ({3} on {4}).").format(
                    company or _("Another buyer"),
                    better_supplier["supplier"],
                    _format_percent(better_supplier["savings_percent"]),
                    frappe.format_value(better_supplier["base_rate_per_stock"] * conversion_factor, {"fieldtype": "Currency"}),
                    better_supplier["transaction_date"],
                ),
                extra=better_supplier,
            )
        )

    return {"source": source, "alerts": alerts}


def _get_price_list_context(*, item_code, buying_price_list, supplier, uom, stock_uom, qty, reference_date):
    context = {"state": "none", "active_record": None, "expired_record": None, "packing_unit": 0}
    if not buying_price_list:
        return context

    rows = frappe.get_all(
        "Item Price",
        filters={"item_code": item_code, "price_list": buying_price_list},
        fields=["name", "supplier", "uom", "price_list_rate", "valid_from", "valid_upto", "packing_unit", "currency"],
        order_by="valid_from desc, creation desc",
        limit_page_length=0,
    )
    if not rows:
        return context

    allowed_uoms = {"", uom or "", stock_uom or ""}
    filtered = [row for row in rows if (row.uom or "") in allowed_uoms and ((row.supplier or "") in {"", supplier or ""})]
    if not filtered:
        return context

    exact_uom_rows = [row for row in filtered if (row.uom or "") == (uom or "")]
    preferred_rows = exact_uom_rows or filtered

    packing_unit_mismatch = False
    for row in preferred_rows:
        if not _is_active_on_reference_date(row, reference_date):
            continue
        if not _matches_packing_unit(row, qty):
            packing_unit_mismatch = True
            context["packing_unit"] = cint(row.packing_unit or 0)
            continue
        context["state"] = "active"
        context["active_record"] = row
        return context

    expired = [row for row in preferred_rows if row.valid_upto and getdate(row.valid_upto) < reference_date]
    if expired:
        context["state"] = "expired"
        context["expired_record"] = expired[0]
        return context

    if packing_unit_mismatch:
        context["state"] = "packing_unit_mismatch"

    return context


def _get_last_purchase_context(*, item_code, company):
    filters = [item_code]
    company_clause = " and po.company = %s" if company else ""
    if company:
        filters.append(company)

    rows = frappe.db.sql(
        f"""
        select
            po.supplier,
            po.transaction_date,
            poi.rate,
            poi.base_rate,
            poi.conversion_factor
        from `tabPurchase Order Item` poi
        inner join `tabPurchase Order` po on po.name = poi.parent
        where po.docstatus = 1
          and poi.item_code = %s
          {company_clause}
        order by po.transaction_date desc, poi.modified desc
        limit 1
        """,
        filters,
        as_dict=True,
    )
    if not rows:
        return None

    row = rows[0]
    row["days_since"] = (getdate(nowdate()) - getdate(row.transaction_date)).days
    return row


def _resolve_rate_source(*, current_rate, price_list_rate, discount_percentage, discount_amount, qty, last_purchase_rate):
    effective_price_list_rate = _get_effective_price_list_rate(
        price_list_rate=price_list_rate,
        discount_percentage=discount_percentage,
        discount_amount=discount_amount,
        qty=qty,
    )

    if price_list_rate > 0 and _rate_matches(current_rate, effective_price_list_rate):
        return "price_list"

    if last_purchase_rate > 0 and _rate_matches(current_rate, last_purchase_rate):
        return "last_purchase"

    if price_list_rate > 0 or last_purchase_rate > 0:
        return "manual_override"

    return "manual_no_reference"


def _get_effective_price_list_rate(*, price_list_rate, discount_percentage, discount_amount, qty):
    rate = flt(price_list_rate)
    if rate <= 0:
        return 0.0

    if flt(discount_percentage):
        return rate * (1 - (flt(discount_percentage) / 100.0))

    if flt(discount_amount) and flt(qty):
        return rate - (flt(discount_amount) / flt(qty))

    return rate


def _rate_matches(left, right):
    left = flt(left)
    right = flt(right)
    if left == right:
        return True
    tolerance = max(0.01, abs(right) * PRICE_MATCH_TOLERANCE)
    return abs(left - right) <= tolerance


def _is_active_on_reference_date(row, reference_date):
    valid_from = getdate(row.valid_from) if row.valid_from else None
    valid_upto = getdate(row.valid_upto) if row.valid_upto else None
    if valid_from and valid_from > reference_date:
        return False
    if valid_upto and valid_upto < reference_date:
        return False
    return True


def _matches_packing_unit(row, qty):
    packing_unit = cint(row.packing_unit or 0)
    if packing_unit <= 0 or flt(qty) <= 0:
        return True
    remainder = flt(qty) % packing_unit
    return abs(remainder) <= 0.000001 or abs(remainder - packing_unit) <= 0.000001


def _normalize_base_rate_per_stock(base_rate, conversion_factor):
    conversion_factor = flt(conversion_factor or 1) or 1
    return flt(base_rate) / conversion_factor


def _get_better_supplier_offer(*, item_code, current_supplier, current_company, current_base_rate_per_stock, reference_date, lookback_days, min_savings_percent):
    if not current_supplier or current_base_rate_per_stock <= 0:
        return None

    earliest_date = reference_date - timedelta(days=cint(lookback_days or DEFAULT_LOOKBACK_DAYS))
    filters = [item_code, current_supplier, earliest_date]
    company_clause = " and po.company = %s" if current_company else ""
    if current_company:
        filters.append(current_company)

    rows = frappe.db.sql(
        f"""
        select
            po.supplier,
            po.transaction_date,
            poi.rate,
            poi.base_rate,
            poi.conversion_factor,
            poi.uom,
            poi.parent
        from `tabPurchase Order Item` poi
        inner join `tabPurchase Order` po on po.name = poi.parent
        where po.docstatus = 1
          and poi.item_code = %s
          and po.supplier != %s
          and po.transaction_date >= %s
          {company_clause}
          and poi.base_rate > 0
        order by (poi.base_rate / ifnull(nullif(poi.conversion_factor, 0), 1)) asc, po.transaction_date desc
        limit 10
        """,
        filters,
        as_dict=True,
    )
    if not rows:
        return None

    best = rows[0]
    best_rate_per_stock = _normalize_base_rate_per_stock(best.base_rate, best.conversion_factor)
    if best_rate_per_stock <= 0 or best_rate_per_stock >= current_base_rate_per_stock:
        return None

    savings_percent = ((current_base_rate_per_stock - best_rate_per_stock) / current_base_rate_per_stock) * 100.0
    if savings_percent < flt(min_savings_percent or DEFAULT_MIN_SAVINGS_PERCENT):
        return None

    return {
        "supplier": best.supplier,
        "transaction_date": best.transaction_date,
        "purchase_order": best.parent,
        "base_rate_per_stock": best_rate_per_stock,
        "savings_percent": savings_percent,
    }


def _build_alert(*, item_code, item_name, rate, severity, alert_type, source, message, extra):
    payload = {
        "item_code": item_code,
        "item_name": item_name,
        "rate": flt(rate),
        "severity": severity,
        "type": alert_type,
        "source": source,
        "message": message,
    }
    payload.update(extra or {})
    return payload


def _format_percent(value):
    number = flt(value)
    return f"{number:.1f}".rstrip("0").rstrip(".")
