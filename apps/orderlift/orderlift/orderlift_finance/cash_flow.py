from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import flt

from orderlift.menu_access import (
    get_allowed_companies,
    get_session_company_context,
    has_interactive_company_session,
    resolve_current_company,
)


FINANCE_ROLES = {"Orderlift Admin", "Finance User", "Finance Admin", "System Manager"}
FORECAST_CONTROL_ROLES = {"Orderlift Admin", "Finance Admin", "System Manager"}
MAX_CONTEXT_ROWS = 500
MAX_FINANCIAL_ROWS = 5000
MAX_DETAIL_EVENTS = 2000
FRAPPE_SYSTEM_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
}
MONEY_FIELDS = (
    "ordered",
    "invoiced",
    "collected",
    "actual_cost",
    "supplier_paid",
    "net_cash",
    "committed_inflow",
    "committed_outflow",
    "forecast_outflow",
    "forecast_net",
    "funding_gap",
)
PROFIT_AMOUNT_FIELDS = (
    "ordered_revenue_ht",
    "ordered_revenue_ttc",
    "ordered_taxes",
    "invoiced_revenue_ht",
    "invoiced_revenue_ttc",
    "invoiced_taxes",
    "remaining_revenue_ht",
    "remaining_revenue_ttc",
    "expected_revenue_ht",
    "expected_revenue_ttc",
    "expected_taxes",
    "baseline_cost",
    "actual_cost_ht",
    "committed_cost",
    "forecast_cost",
    "expected_cost",
    "expected_profit",
    "actual_profit_to_date",
)


@frappe.whitelist()
def get_portfolio_data(filters: str | dict | None = None) -> dict:
    _user, company = _authorize()
    active_filters = _clean_filters(filters, company)
    data = _load_data(company, active_filters)
    model = build_cash_flow_model(data, company=company)
    portfolio_bounds = _horizon_bounds(
        active_filters.get("horizon") or "13_weeks",
        active_filters.get("from_date"),
        active_filters.get("to_date"),
        model["events"],
    )
    rows = [
        _context_for_horizon(row, model["events"], portfolio_bounds, model.get("accruals", []))
        for row in model["contexts"].values()
    ]
    rows = [row for row in rows if _matches_output_filters(row, active_filters)]
    visible_contexts = {(row["context_type"], row["context_name"]) for row in rows}
    events = [event for event in model["events"] if _event_context_key(event) in visible_contexts]
    portfolio_start = _as_date(portfolio_bounds["from_date"])
    portfolio_end = _as_date(portfolio_bounds["to_date"])
    monthly_events = [
        event
        for event in events
        if portfolio_start <= _as_date(event.get("date"), portfolio_start) <= portfolio_end
    ]

    return {
        "active_company": company,
        "company": company,
        "company_currency": data["company_currency"],
        "active_filters": active_filters,
        "modes": ["projects", "standalone_sales_orders"],
        "counts": {
            "projects": sum(row["context_type"] == "Project" for row in rows),
            "standalone_sales_orders": sum(row["context_type"] == "Sales Order" for row in rows),
            "customers": len({row["customer"] for row in rows if row["customer"]}),
            "contexts": len(rows),
        },
        "summary": _summarize(rows, model["data_quality"], events=events, bounds=portfolio_bounds),
        "kpis": _summarize(rows, model["data_quality"], events=events, bounds=portfolio_bounds),
        "project_rows": [row for row in rows if row["context_type"] == "Project"],
        "standalone_order_rows": [row for row in rows if row["context_type"] == "Sales Order"],
        "profitability_rows": rows,
        "cash_flow_rows": rows,
        "customer_rows": _group_rows(
            rows, "customer", "Customer", events=events, bounds=portfolio_bounds
        ),
        "monthly_rows": _monthly_performance(monthly_events, data["company_currency"]),
        "data_quality_rows": model["data_quality"],
        "data_quality": model["data_quality"],
        "detail_completeness": _detail_completeness(model["data_quality"]),
        "currencies": model["currencies"],
        "filter_options": _filter_options(rows, model["currencies"]),
    }


@frappe.whitelist()
def get_cash_flow_detail(
    context_type: str,
    context_name: str,
    horizon: str = "13_weeks",
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    _user, company = _authorize()
    context_type = _normalize_context_type(context_type)
    context_name = (context_name or "").strip()
    if not context_name:
        frappe.throw(_("A project or standalone Sales Order is required."))

    filters = {"context_type": context_type, "context_name": context_name}
    data = _load_data(company, filters)
    model = build_cash_flow_model(data, company=company)
    key = (context_type, context_name)
    identity = model["contexts"].get(key)
    if not identity:
        frappe.throw(_("The requested cash-flow context is unavailable."), frappe.PermissionError)

    events = [event for event in model["events"] if _event_context_key(event) == key]
    bounds = _horizon_bounds(horizon, from_date, to_date, events)
    identity = _context_for_horizon(identity, events, bounds, model.get("accruals", []))
    detail_events = sorted(_events_for_horizon_detail(events, bounds), key=_event_sort_key)
    bounded_events = detail_events[:MAX_DETAIL_EVENTS]
    buckets = _bucket_events(events, bounds, detail_events=bounded_events)
    all_receivables = [
        event for event in detail_events
        if event["layer"] == "committed" and event["direction"] == "inflow"
    ]
    all_payables = [
        event for event in detail_events
        if event["layer"] == "committed" and event["direction"] == "outflow"
    ]
    receivables = [
        event for event in bounded_events
        if event["layer"] == "committed" and event["direction"] == "inflow"
    ]
    payables = [
        event for event in bounded_events
        if event["layer"] == "committed" and event["direction"] == "outflow"
    ]
    quality = [
        row for row in model["data_quality"]
        if not row.get("context_name") or row.get("context_name") == context_name
    ]

    event_bounds = {
        "returned": len(bounded_events),
        "total": len(detail_events),
        "truncated": len(bounded_events) < len(detail_events),
        "limit": MAX_DETAIL_EVENTS,
        "from_date": bounds["from_date"],
        "to_date": bounds["to_date"],
        "includes_overdue_commitments": True,
    }
    if event_bounds["truncated"]:
        quality.append(
            _quality(
                "detail_events_truncated",
                _("Cash-flow event detail is truncated at {0} rows.").format(MAX_DETAIL_EVENTS),
                context_type=context_type,
                context_name=context_name,
                document_type="Cash Flow Event",
                limit=MAX_DETAIL_EVENTS,
                total=len(detail_events),
            )
        )

    profitability = _profitability_payload(identity)
    profitability["closure"]["can_manage"] = _can_control_forecasts()
    return {
        "identity": identity,
        "kpis": {field: identity[field] for field in MONEY_FIELDS},
        "profitability": profitability,
        "horizon": bounds,
        "weekly_buckets": buckets if bounds["interval"] == "week" else [],
        "monthly_buckets": buckets if bounds["interval"] == "month" else [],
        "buckets": buckets,
        "events": bounded_events,
        "bounded_events": event_bounds,
        "receivables": receivables,
        "payables": payables,
        "documents": _documents_for_context(data, model, key),
        "alerts": _alerts(identity, all_receivables, all_payables),
        "data_quality": quality,
        "detail_completeness": _detail_completeness(quality),
        "active_company": company,
        "company_currency": data["company_currency"],
        "filter_options": {"horizons": _horizon_options()},
    }


@frappe.whitelist()
def get_customer_performance(filters: str | dict | None = None) -> list[dict]:
    return get_portfolio_data(filters).get("customer_rows", [])


@frappe.whitelist()
def get_monthly_performance(filters: str | dict | None = None) -> list[dict]:
    return get_portfolio_data(filters).get("monthly_rows", [])


@frappe.whitelist()
def get_data_quality(filters: str | dict | None = None) -> list[dict]:
    return get_portfolio_data(filters).get("data_quality_rows", [])


@frappe.whitelist(methods=["POST"])
def set_forecast_finality(
    context_type: str,
    context_name: str,
    forecast: str,
    is_final=1,
) -> dict:
    user, company = _authorize()
    roles = set(frappe.get_roles(user) or [])
    if user != "Administrator" and not roles.intersection(FORECAST_CONTROL_ROLES):
        frappe.throw(_("Only Finance Admin or Orderlift Admin can finalize financial forecasts."), frappe.PermissionError)

    context_type = _normalize_context_type(context_type)
    context_name = (context_name or "").strip()
    forecast = (forecast or "").strip().lower()
    fieldname = {
        "revenue": "custom_revenue_forecast_final",
        "cost": "custom_cost_forecast_final",
    }.get(forecast)
    if not context_name or not fieldname:
        frappe.throw(_("A valid context and Revenue or Cost forecast are required."))

    doc = frappe.get_doc(context_type, context_name)
    doc.check_permission("read")
    if (doc.get("company") or "").strip() != company:
        frappe.throw(_("The financial context belongs to another company."), frappe.PermissionError)
    if context_type == "Sales Order" and (doc.get("project") or "").strip():
        frappe.throw(_("Finalize the Project forecast for a project-linked Sales Order."))
    if not doc.meta.get_field(fieldname):
        frappe.throw(_("Financial forecast fields are not installed. Run migrate first."))

    normalized_final = str(is_final).strip().lower()
    if normalized_final not in {"0", "1", "false", "true", "no", "yes"}:
        frappe.throw(_("Forecast finality must be true or false."))
    final_value = 1 if normalized_final in {"1", "true", "yes"} else 0
    doc.db_set(fieldname, final_value, notify=True)
    state = _("Final") if final_value else _("Open")
    doc.add_comment("Info", _("{0} forecast marked {1} from Project & Order Finance.").format(forecast.title(), state))
    return get_cash_flow_detail(context_type, context_name)


def classify_sales_orders(projects: list[dict], sales_orders: list[dict]) -> tuple[dict, list[dict]]:
    """Create mutually exclusive Project/standalone SO contexts."""
    contexts = {}
    quality = []
    projects_by_name = {_value(row, "name"): row for row in projects}
    for project in projects:
        name = _value(project, "name")
        if not name:
            continue
        contexts[("Project", name)] = _context_row(
            "Project",
            name,
            title=_value(project, "project_name") or name,
            customer=_value(project, "customer"),
            company=_value(project, "company"),
            workflow_status=_value(project, "custom_project_status") or _value(project, "status"),
            project_type=_value(project, "project_type"),
            business_type=_value(project, "custom_crm_business_type"),
            segment=_value(project, "custom_crm_segment"),
            revenue_forecast_final=_value(project, "custom_revenue_forecast_final"),
            cost_forecast_final=_value(project, "custom_cost_forecast_final"),
        )

    for order in sales_orders:
        name = _value(order, "name")
        project = (_value(order, "project") or "").strip()
        if project:
            if project not in projects_by_name:
                quality.append(
                    _quality(
                        "inaccessible_project",
                        _("Sales Order {0} links to a project outside the permitted active-company result.").format(name),
                        document_type="Sales Order",
                        document_name=name,
                    )
                )
            continue
        contexts[("Sales Order", name)] = _context_row(
            "Sales Order",
            name,
            title=_value(order, "title") or name,
            customer=_value(order, "customer"),
            company=_value(order, "company"),
            workflow_status=_value(order, "custom_orderlift_order_status") or _value(order, "status"),
            project_type="Standalone Sales Order",
            business_type=_value(order, "custom_crm_business_type"),
            segment=_value(order, "custom_crm_segment"),
            revenue_forecast_final=_value(order, "custom_revenue_forecast_final"),
            cost_forecast_final=_value(order, "custom_cost_forecast_final"),
        )
    return contexts, quality


def payment_direction(payment_type: str) -> tuple[str, int]:
    if (payment_type or "").strip() == "Receive":
        return "inflow", 1
    if (payment_type or "").strip() == "Pay":
        return "outflow", -1
    return "", 0


def funding_position(actual_net, committed_inflow, committed_outflow, forecast_outflow) -> dict:
    forecast_net = (
        flt(actual_net)
        + flt(committed_inflow)
        - flt(committed_outflow)
        - flt(forecast_outflow)
    )
    return {"forecast_net": forecast_net, "funding_gap": max(-forecast_net, 0.0)}


def chronological_funding_position(events: list[dict], bounds: dict) -> dict:
    """Return terminal and minimum positions for the selected as-of horizon.

    Actual cash through the horizon start is the opening position. Current open
    commitments already overdue at the start are applied first, then all events
    through the horizon end in deterministic chronological order.
    """
    start = _as_date(bounds["from_date"])
    end = _as_date(bounds["to_date"])
    opening = sum(
        flt(event["signed_amount"])
        for event in events
        if event["layer"] == "actual" and _as_date(event.get("date"), start) <= start
    )
    path_events = [
        event
        for event in events
        if (
            event["layer"] != "actual"
            and _as_date(event.get("date"), start) <= end
        )
        or (
            event["layer"] == "actual"
            and start < _as_date(event.get("date"), start) <= end
        )
    ]
    position = opening
    minimum = opening
    for event in sorted(path_events, key=_funding_event_sort_key):
        position += flt(event["signed_amount"])
        minimum = min(minimum, position)
    return {
        "opening_position": opening,
        "forecast_net": position,
        "minimum_position": minimum,
        "funding_gap": max(-minimum, 0.0),
    }


def replace_scheduled_amounts(
    schedules: list[dict], replacement_amount: float, *, fallback_date=None, fallback_amount=0
) -> list[dict]:
    """Consume invoices/direct advances from schedules before emitting residual commitments."""
    remaining_replacement = max(flt(replacement_amount), 0)
    rows = sorted(schedules, key=lambda row: (str(_value(row, "due_date") or ""), str(_value(row, "name") or "")))
    scheduled_total = sum(
        max(flt(_value(row, "scheduled_amount") if _value(row, "scheduled_amount") is not None else _value(row, "amount")), 0)
        for row in rows
    )
    unscheduled = max(flt(fallback_amount) - scheduled_total, 0)
    if unscheduled > 0.0001:
        rows.append(
            {
                "name": "schedule-residual",
                "due_date": fallback_date,
                "amount": unscheduled,
                "scheduled_amount": unscheduled,
                "is_schedule_residual": True,
            }
        )
    residual = []
    for row in rows:
        amount = max(flt(_value(row, "amount") or _value(row, "payment_amount")), 0)
        replaced = min(amount, remaining_replacement)
        remaining_replacement -= replaced
        if amount - replaced > 0.0001:
            residual.append({**dict(row), "amount": amount - replaced})
    return residual


def build_cash_flow_model(data: dict, *, company: str) -> dict:
    contexts, quality = classify_sales_orders(data.get("projects", []), data.get("sales_orders", []))
    quality.extend(data.get("data_quality", []))
    company_currency = data.get("company_currency") or ""
    sales_orders = {_value(row, "name"): row for row in data.get("sales_orders", [])}
    project_names = {name for context_type, name in contexts if context_type == "Project"}
    so_context = {}
    for name, order in sales_orders.items():
        project = (_value(order, "project") or "").strip()
        if project in project_names:
            so_context[name] = ("Project", project)
        elif not project and ("Sales Order", name) in contexts:
            so_context[name] = ("Sales Order", name)

    source_currencies = defaultdict(set)
    accruals = []
    for name, order in sales_orders.items():
        key = so_context.get(name)
        if not key:
            continue
        source_currencies[key].add(_value(order, "currency") or company_currency)
        ordered = _company_amount(order, "base_grand_total", "grand_total")
        ordered_ht = _company_net_amount(order)
        contexts[key]["ordered"] += ordered
        contexts[key]["ordered_revenue_ht"] += ordered_ht
        contexts[key]["ordered_revenue_ttc"] += ordered
        contexts[key]["ordered_taxes"] += ordered - ordered_ht
        accruals.append(_accrual(key, "ordered", ordered, _value(order, "transaction_date"), "Sales Order", name))

    forecast_by_so = defaultdict(float)
    costed_order_items = defaultdict(int)
    low_confidence_contexts = set()
    for item in data.get("sales_order_items", []):
        order_name = _value(item, "parent")
        order = sales_orders.get(order_name)
        key = so_context.get(order_name)
        if not order or not key:
            continue
        source_cost = flt(_value(item, "source_landed_cost")) * flt(_value(item, "qty"))
        costed_order_items[order_name] += 1
        if flt(_value(item, "qty")) and flt(_value(item, "source_landed_cost")) <= 0:
            low_confidence_contexts.add(key)
            contexts[key]["cost_data_complete"] = False
            quality.append(
                _quality(
                    "missing_landed_cost",
                    _("Sales Order {0} contains an item without Source Landed Cost.").format(order_name),
                    context_type=key[0],
                    context_name=key[1],
                    document_type="Sales Order",
                    document_name=order_name,
                )
            )
        company_cost = source_cost * _conversion_rate(order)
        forecast_by_so[order_name] += company_cost
        contexts[key]["baseline_cost"] += company_cost
    for order_name, key in so_context.items():
        if not costed_order_items[order_name]:
            low_confidence_contexts.add(key)
            contexts[key]["cost_data_complete"] = False
            quality.append(
                _quality(
                    "missing_landed_cost",
                    _("Sales Order {0} has no readable landed-cost item inputs.").format(order_name),
                    context_type=key[0],
                    context_name=key[1],
                    document_type="Sales Order",
                    document_name=order_name,
                )
            )

    si_allocations, si_quality = _invoice_allocations(
        data.get("sales_invoices", []),
        data.get("sales_invoice_items", []),
        so_context,
        project_names,
        custom_order_field="custom_advance_sales_order",
    )
    po_item_context = _purchase_order_item_context(data, project_names, so_context)
    po_item_parent = {
        _value(item, "name"): _value(item, "parent")
        for item in data.get("purchase_order_items", [])
        if _value(item, "name") and _value(item, "parent")
    }
    pi_allocations, pi_quality = _invoice_allocations(
        data.get("purchase_invoices", []),
        data.get("purchase_invoice_items", []),
        so_context,
        project_names,
        custom_order_field="custom_sales_order",
        po_item_context=po_item_context,
    )
    po_allocations, po_quality = _purchase_order_allocations(data, project_names, so_context)
    quality.extend(si_quality)
    quality.extend(pi_quality)
    quality.extend(po_quality)

    events = []
    invoice_coverage = defaultdict(float)
    purchase_invoice_coverage = defaultdict(float)
    purchase_invoice_net_coverage = defaultdict(float)
    for invoice in data.get("sales_invoices", []):
        name = _value(invoice, "name")
        shares = si_allocations.get(name, {})
        total = _signed_invoice_total(invoice)
        net_total = _signed_net_total(invoice)
        outstanding = _company_amount(invoice, "base_outstanding_amount", "outstanding_amount")
        source_outstanding = flt(_value(invoice, "outstanding_amount"))
        for key, share in shares.items():
            contexts[key]["invoiced"] += total * share
            contexts[key]["invoiced_revenue_ht"] += net_total * share
            contexts[key]["invoiced_revenue_ttc"] += total * share
            contexts[key]["invoiced_taxes"] += (total - net_total) * share
            source_currencies[key].add(_value(invoice, "currency") or company_currency)
            accruals.append(
                _accrual(key, "invoiced", total * share, _value(invoice, "posting_date"), "Sales Invoice", name)
            )
            if not _value(invoice, "custom_advance_payment_entry"):
                _add_invoice_coverage(
                    invoice_coverage,
                    data.get("sales_invoice_items", []),
                    name,
                    key,
                    total * share,
                    so_context,
                )
            if abs(outstanding * share) > 0.0001:
                direction = "inflow" if outstanding >= 0 else "outflow"
                events.append(
                    _event(
                        key,
                        layer="committed",
                        direction=direction,
                        event_type="Sales Invoice Outstanding",
                        event_date=_value(invoice, "due_date") or _value(invoice, "posting_date"),
                        amount=abs(outstanding * share),
                        company_currency=company_currency,
                        source_amount=abs(source_outstanding * share),
                        source_currency=_value(invoice, "currency") or company_currency,
                        reference_doctype="Sales Invoice",
                        reference_name=name,
                        confidence="High",
                    )
                )

    for invoice in data.get("purchase_invoices", []):
        name = _value(invoice, "name")
        shares = pi_allocations.get(name, {})
        total = _signed_invoice_total(invoice)
        net_total = _signed_net_total(invoice)
        outstanding = _company_amount(invoice, "base_outstanding_amount", "outstanding_amount")
        source_outstanding = flt(_value(invoice, "outstanding_amount"))
        for key, share in shares.items():
            contexts[key]["actual_cost"] += total * share
            contexts[key]["actual_cost_ht"] += net_total * share
            source_currencies[key].add(_value(invoice, "currency") or company_currency)
            accruals.append(
                _accrual(key, "actual_cost", total * share, _value(invoice, "posting_date"), "Purchase Invoice", name)
            )
            _add_purchase_invoice_coverage(
                purchase_invoice_coverage,
                data.get("purchase_invoice_items", []),
                name,
                key,
                total * share,
                po_allocations,
                so_context,
                project_names,
                po_item_context,
                po_item_parent,
            )
            _add_purchase_invoice_coverage(
                purchase_invoice_net_coverage,
                data.get("purchase_invoice_items", []),
                name,
                key,
                net_total * share,
                po_allocations,
                so_context,
                project_names,
                po_item_context,
                po_item_parent,
            )
            if abs(outstanding * share) > 0.0001:
                direction = "outflow" if outstanding >= 0 else "inflow"
                events.append(
                    _event(
                        key,
                        layer="committed",
                        direction=direction,
                        event_type="Purchase Invoice Outstanding",
                        event_date=_value(invoice, "due_date") or _value(invoice, "posting_date"),
                        amount=abs(outstanding * share),
                        company_currency=company_currency,
                        source_amount=abs(source_outstanding * share),
                        source_currency=_value(invoice, "currency") or company_currency,
                        reference_doctype="Purchase Invoice",
                        reference_name=name,
                        confidence="High",
                    )
                )

    payment_events, direct_so_advances, direct_po_advances, paid_sources, payment_quality = _payment_events(
        data,
        so_context,
        si_allocations,
        pi_allocations,
        po_allocations,
        company_currency,
    )
    events.extend(payment_events)
    quality.extend(payment_quality)
    events.extend(
        _inline_payment_events(
            data.get("sales_invoices", []), si_allocations, paid_sources, company_currency, "Sales Invoice"
        )
    )
    events.extend(
        _inline_payment_events(
            data.get("purchase_invoices", []), pi_allocations, paid_sources, company_currency, "Purchase Invoice"
        )
    )

    events.extend(
        _residual_order_events(
            data.get("sales_orders", []),
            data.get("sales_order_schedules", []),
            so_context,
            invoice_coverage,
            direct_so_advances,
            company_currency,
            direction="inflow",
            quality=quality,
            contexts=contexts,
        )
    )
    po_events, po_residual_quality = _residual_purchase_order_events(
        data.get("purchase_orders", []),
        data.get("purchase_order_schedules", []),
        po_allocations,
        purchase_invoice_coverage,
        direct_po_advances,
        company_currency,
    )
    events.extend(po_events)
    quality.extend(po_residual_quality)

    # Procurement accrual coverage is intentionally independent from cash
    # commitments. A PI total and its outstanding amount describe different
    # layers and must never both replace the landed-cost forecast.
    procurement_accrual = defaultdict(float)
    for order in data.get("purchase_orders", []):
        name = _value(order, "name")
        for key, share in po_allocations.get(name, {}).items():
            is_closed = (_value(order, "status") or "").lower() in {"closed", "cancelled"}
            if is_closed:
                procurement_accrual[key] += max(purchase_invoice_coverage[(name, key)], 0)
            else:
                procurement_accrual[key] += max(_company_amount(order, "base_grand_total", "grand_total") * share, 0)
            source_currencies[key].add(_value(order, "currency") or company_currency)
            if not is_closed:
                ordered_cost = max(_company_net_amount(order) * share, 0)
                invoiced_cost = max(purchase_invoice_net_coverage[(name, key)], 0)
                contexts[key]["committed_cost"] += max(ordered_cost - invoiced_cost, 0)
    direct_pi_coverage = _direct_purchase_invoice_accrual_coverage(
        data.get("purchase_invoices", []),
        data.get("purchase_invoice_items", []),
        pi_allocations,
        so_context,
        project_names,
        po_item_context,
    )
    for key, amount in direct_pi_coverage.items():
        procurement_accrual[key] += max(amount, 0)
    forecast_orders_by_context = defaultdict(list)
    for order_name, estimated_cost in forecast_by_so.items():
        key = so_context.get(order_name)
        if key and estimated_cost > 0:
            forecast_orders_by_context[key].append((order_name, estimated_cost))
    for key, estimates in forecast_orders_by_context.items():
        estimated_total = sum(amount for _, amount in estimates)
        uncovered_total = max(estimated_total - procurement_accrual[key], 0)
        for order_name, estimated_cost in estimates:
            uncovered = uncovered_total * estimated_cost / estimated_total if estimated_total else 0
            if uncovered <= 0.0001 or contexts[key].get("cost_forecast_final"):
                continue
            order = sales_orders[order_name]
            events.append(
                _event(
                    key,
                    layer="forecast",
                    direction="outflow",
                    event_type="Uncovered Landed Cost",
                    event_date=_value(order, "delivery_date") or _value(order, "transaction_date"),
                    amount=uncovered,
                    company_currency=company_currency,
                    source_amount=uncovered / _conversion_rate(order),
                    source_currency=_value(order, "currency") or company_currency,
                    reference_doctype="Sales Order",
                    reference_name=order_name,
                    confidence="Medium",
                )
            )

    _finalize_profitability(contexts)
    _add_profitability_quality(contexts, quality)
    _apply_events_to_contexts(contexts, events, source_currencies, company_currency)
    global_quality = any(
        row.get("code") in {"source_truncated", "unavailable_source"} and not row.get("context_name")
        for row in quality
    )
    for key in low_confidence_contexts:
        if key in contexts:
            contexts[key]["confidence"] = "Low"
    if global_quality:
        for context in contexts.values():
            context["confidence"] = "Low"
            context["profitability_complete"] = False
    currencies = sorted(
        {
            company_currency,
            *[currency for values in source_currencies.values() for currency in values],
            *[event.get("source_currency") for event in events],
        }
        - {"", None}
    )
    return {
        "contexts": contexts,
        "events": events,
        "accruals": accruals,
        "data_quality": quality,
        "currencies": currencies,
    }


def _authorize() -> tuple[str, str]:
    user = getattr(getattr(frappe, "session", None), "user", "")
    roles = set(frappe.get_roles(user) or [])
    if user != "Administrator" and not roles.intersection(FINANCE_ROLES):
        frappe.throw(_("You are not permitted to access finance cash flow."), frappe.PermissionError)
    frappe.has_permission("Sales Order", "read", throw=True)

    allowed = get_allowed_companies(user)
    if has_interactive_company_session(user):
        context = get_session_company_context(user=user, allowed_companies=allowed)
        company = (context.get("company") or "").strip()
        if not company:
            frappe.throw(_("Select an active company before opening cash flow."), frappe.PermissionError)
    else:
        company = resolve_current_company(user=user, allowed_companies=allowed)
    if not company or company not in allowed:
        frappe.throw(_("No permitted active company is available."), frappe.PermissionError)
    return user, company


def _can_control_forecasts(user: str | None = None) -> bool:
    user = user or getattr(getattr(frappe, "session", None), "user", "")
    return user == "Administrator" or bool(set(frappe.get_roles(user) or []).intersection(FORECAST_CONTROL_ROLES))


def _clean_filters(filters: str | dict | None, company: str) -> dict:
    if isinstance(filters, str):
        try:
            filters = json.loads(filters or "{}")
        except (TypeError, ValueError):
            filters = {}
    filters = dict(filters or {})
    requested_company = (filters.get("company") or "").strip()
    if requested_company and requested_company != company:
        frappe.throw(_("Cash flow is restricted to the active company."), frappe.PermissionError)
    context_type = (filters.get("context_type") or "").strip()
    if context_type:
        context_type = _normalize_context_type(context_type)
    return {
        "company": company,
        "context_type": context_type,
        "context_name": (filters.get("context_name") or "").strip(),
        "customer": (filters.get("customer") or "").strip(),
        "workflow_status": (filters.get("workflow_status") or filters.get("status") or "").strip(),
        "project_type": (filters.get("project_type") or "").strip(),
        "business_type": (filters.get("business_type") or "").strip(),
        "segment": (filters.get("segment") or filters.get("crm_segment") or "").strip(),
        "currency": (filters.get("currency") or "").strip(),
        "risk_status": (filters.get("risk_status") or "").strip(),
        "revenue_forecast_status": (filters.get("revenue_forecast_status") or "").strip(),
        "cost_forecast_status": (filters.get("cost_forecast_status") or "").strip(),
        "search": (filters.get("search") or "").strip()[:120],
        "horizon": (filters.get("horizon") or "13_weeks").strip(),
        "from_date": (filters.get("from_date") or "").strip(),
        "to_date": (filters.get("to_date") or "").strip(),
    }


def _normalize_context_type(value: str) -> str:
    normalized = (value or "").strip().lower().replace("_", " ")
    if normalized in {"project", "projects"}:
        return "Project"
    if normalized in {"sales order", "standalone sales order", "standalone sales orders"}:
        return "Sales Order"
    frappe.throw(_("Context Type must be Project or Sales Order."))


def _load_data(company: str, filters: dict) -> dict:
    quality = []
    project_filters = {"company": company}
    order_filters = {"company": company, "docstatus": 1}
    context_type = filters.get("context_type")
    context_name = filters.get("context_name")
    if context_name and context_type == "Project":
        project_filters["name"] = context_name
        order_filters["project"] = context_name
    elif context_name and context_type == "Sales Order":
        project_filters["name"] = "__standalone_only__"
        order_filters["name"] = context_name

    projects = _get_list(
        "Project",
        filters=project_filters,
        fields=[
            "name", "project_name", "customer", "company", "status", "custom_project_status",
            "project_type", "custom_crm_business_type", "custom_crm_segment",
            "custom_revenue_forecast_final", "custom_cost_forecast_final",
            "expected_start_date", "expected_end_date", "modified",
        ],
        limit=MAX_CONTEXT_ROWS,
        quality=quality,
    )
    sales_orders = _get_list(
        "Sales Order",
        filters=order_filters,
        fields=[
            "name", "title", "customer", "company", "project", "status",
            "custom_orderlift_order_status", "currency", "conversion_rate", "grand_total",
            "base_grand_total", "net_total", "base_net_total", "total_taxes_and_charges",
            "base_total_taxes_and_charges", "custom_crm_business_type", "custom_crm_segment",
            "custom_revenue_forecast_final", "custom_cost_forecast_final",
            "transaction_date", "delivery_date", "modified",
        ],
        limit=MAX_CONTEXT_ROWS,
        quality=quality,
    )
    projects, sales_orders = _filter_context_rows(projects, sales_orders, filters)
    project_names = {_value(row, "name") for row in projects}
    order_names = {
        _value(row, "name")
        for row in sales_orders
        if not _value(row, "project") or _value(row, "project") in project_names
    }
    sales_orders = [row for row in sales_orders if _value(row, "name") in order_names]

    data = {
        "company_currency": frappe.get_cached_value("Company", company, "default_currency") or "",
        "data_quality": quality,
        "include_unassigned": not any(
            filters.get(key)
            for key in ("context_name", "customer", "workflow_status", "project_type", "currency", "search")
        ),
        "projects": projects,
        "sales_orders": sales_orders,
        "sales_order_items": _children(
            "Sales Order Item",
            order_names,
            ["parent", "name", "qty", "source_landed_cost"],
            parent_doctype="Sales Order",
            quality=quality,
        ),
        "sales_order_schedules": _children(
            "Payment Schedule",
            order_names,
            ["parent", "name", "due_date", "payment_amount", "outstanding", "idx"],
            parent_doctype="Sales Order",
            parenttype="Sales Order",
            quality=quality,
        ),
    }
    _load_sales_invoices(data, company, order_names, project_names)
    _load_purchase_documents(data, company, project_names)
    _load_payments(data, company)
    return data


def _load_sales_invoices(data: dict, company: str, order_names: set[str], project_names: set[str]) -> None:
    quality = data["data_quality"]
    invoices = _get_list(
        "Sales Invoice",
        filters={"company": company, "docstatus": 1},
        fields=[
            "name", "customer", "company", "project", "posting_date", "due_date", "currency",
            "conversion_rate", "grand_total", "base_grand_total", "net_total", "base_net_total",
            "total_taxes_and_charges", "base_total_taxes_and_charges", "outstanding_amount",
            "base_outstanding_amount", "paid_amount", "base_paid_amount", "is_pos", "is_return",
            "return_against", "custom_advance_sales_order", "custom_advance_payment_entry",
            "modified",
        ],
        limit=MAX_FINANCIAL_ROWS,
        quality=quality,
    )
    names = {_value(row, "name") for row in invoices}
    items = _children(
        "Sales Invoice Item",
        names,
        ["parent", "name", "sales_order", "project", "amount", "base_amount", "net_amount", "base_net_amount"],
        parent_doctype="Sales Invoice",
        quality=quality,
    )
    relevant = {
        _value(row, "parent")
        for row in items
        if _value(row, "sales_order") in order_names or _value(row, "project") in project_names
    }
    relevant.update(
        _value(row, "name")
        for row in invoices
        if _value(row, "project") in project_names or _value(row, "custom_advance_sales_order") in order_names
    )
    if data.get("include_unassigned"):
        relevant.update(names)
    data["sales_invoices"] = [row for row in invoices if _value(row, "name") in relevant]
    data["sales_invoice_items"] = [row for row in items if _value(row, "parent") in relevant]


def _load_purchase_documents(data: dict, company: str, project_names: set[str]) -> None:
    quality = data["data_quality"]
    order_names = {_value(row, "name") for row in data.get("sales_orders", [])}
    purchase_orders = _get_list(
        "Purchase Order",
        filters={"company": company, "docstatus": 1},
        fields=[
            "name", "supplier", "company", "project", "status", "currency", "conversion_rate",
            "grand_total", "base_grand_total", "net_total", "base_net_total",
            "total_taxes_and_charges", "base_total_taxes_and_charges", "transaction_date", "schedule_date",
            "modified",
        ],
        limit=MAX_FINANCIAL_ROWS,
        quality=quality,
    )
    po_names = {_value(row, "name") for row in purchase_orders}
    po_items = _children(
        "Purchase Order Item",
        po_names,
        ["parent", "name", "project", "sales_order", "amount", "base_amount", "modified"],
        parent_doctype="Purchase Order",
        quality=quality,
    )
    relevant_po = {
        _value(row, "parent")
        for row in po_items
        if _value(row, "project") in project_names or _value(row, "sales_order") in order_names
    }
    relevant_po.update(
        _value(row, "name") for row in purchase_orders if _value(row, "project") in project_names
    )
    data["purchase_orders"] = [row for row in purchase_orders if _value(row, "name") in relevant_po]
    data["purchase_order_items"] = [row for row in po_items if _value(row, "parent") in relevant_po]
    relevant_po_items = {_value(row, "name") for row in data["purchase_order_items"]}
    data["purchase_order_schedules"] = _children(
        "Payment Schedule",
        relevant_po,
        ["parent", "name", "due_date", "payment_amount", "outstanding", "idx"],
        parent_doctype="Purchase Order",
        parenttype="Purchase Order",
        quality=quality,
    )

    purchase_invoices = _get_list(
        "Purchase Invoice",
        filters={"company": company, "docstatus": 1},
        fields=[
            "name", "supplier", "company", "project", "posting_date", "due_date", "currency",
            "conversion_rate", "grand_total", "base_grand_total", "net_total", "base_net_total",
            "total_taxes_and_charges", "base_total_taxes_and_charges", "outstanding_amount",
            "base_outstanding_amount", "paid_amount", "base_paid_amount", "is_paid", "is_return",
            "return_against",
            "modified",
        ],
        limit=MAX_FINANCIAL_ROWS,
        quality=quality,
    )
    pi_names = {_value(row, "name") for row in purchase_invoices}
    pi_items = _children(
        "Purchase Invoice Item",
        pi_names,
        [
            "parent", "name", "project", "purchase_order", "po_detail", "custom_sales_order",
            "amount", "base_amount", "net_amount", "base_net_amount",
        ],
        parent_doctype="Purchase Invoice",
        quality=quality,
    )
    relevant_pi = {
        _value(row, "parent")
        for row in pi_items
        if _value(row, "project") in project_names
        or _value(row, "custom_sales_order") in order_names
        or _value(row, "purchase_order") in relevant_po
        or _value(row, "po_detail") in relevant_po_items
    }
    relevant_pi.update(
        _value(row, "name") for row in purchase_invoices if _value(row, "project") in project_names
    )
    if data.get("include_unassigned"):
        relevant_pi.update(pi_names)
    data["purchase_invoices"] = [row for row in purchase_invoices if _value(row, "name") in relevant_pi]
    data["purchase_invoice_items"] = [row for row in pi_items if _value(row, "parent") in relevant_pi]


def _load_payments(data: dict, company: str) -> None:
    quality = data["data_quality"]
    payments = _get_list(
        "Payment Entry",
        filters={"company": company, "docstatus": 1, "payment_type": ["in", ["Receive", "Pay"]]},
        fields=[
            "name", "company", "payment_type", "posting_date", "party_type", "party", "paid_amount",
            "received_amount", "base_paid_amount", "base_received_amount",
            "custom_source_document_currency", "custom_source_payment_amount",
            "paid_from_account_currency", "paid_to_account_currency", "modified",
        ],
        limit=MAX_FINANCIAL_ROWS,
        quality=quality,
    )
    names = {_value(row, "name") for row in payments}
    references = _children(
        "Payment Entry Reference",
        names,
        [
            "parent", "name", "reference_doctype", "reference_name", "allocated_amount",
            "exchange_rate",
        ],
        parent_doctype="Payment Entry",
        parenttype="Payment Entry",
        quality=quality,
    )
    relevant_documents = {
        "Sales Order": {_value(row, "name") for row in data.get("sales_orders", [])},
        "Sales Invoice": {_value(row, "name") for row in data.get("sales_invoices", [])},
        "Purchase Order": {_value(row, "name") for row in data.get("purchase_orders", [])},
        "Purchase Invoice": {_value(row, "name") for row in data.get("purchase_invoices", [])},
    }
    context_refs = [
        row for row in references
        if _value(row, "reference_name") in relevant_documents.get(_value(row, "reference_doctype"), set())
    ]
    payment_names = {_value(row, "parent") for row in context_refs}
    data["payment_entries"] = [row for row in payments if _value(row, "name") in payment_names]
    data["payment_references"] = [row for row in references if _value(row, "parent") in payment_names]


def _get_list(
    doctype: str, *, filters: dict, fields: list[str], limit: int, quality: list[dict]
) -> list:
    if not _can_read(doctype, quality):
        return []
    available = _available_fields(doctype, fields)
    rows = frappe.get_list(
        doctype,
        filters=filters,
        fields=available,
        order_by="modified desc, name desc" if "modified" in available else "name desc",
        limit_page_length=limit + 1,
    )
    if len(rows) > limit:
        quality.append(
            _quality(
                "source_truncated",
                _("{0} results are truncated at {1} recent rows.").format(doctype, limit),
                document_type=doctype,
                limit=limit,
            )
        )
    return rows[:limit]


def _children(
    doctype: str,
    parents: set[str],
    fields: list[str],
    *,
    parent_doctype: str,
    parenttype: str | None = None,
    quality: list[dict],
) -> list:
    if not parents or not _can_read(parent_doctype, quality):
        return []
    if not frappe.db.exists("DocType", doctype):
        quality.append(
            _quality(
                "unavailable_source",
                _("Cash-flow source {0} is not installed.").format(doctype),
                document_type=doctype,
            )
        )
        return []
    filters = {"parent": ["in", sorted(parents)]}
    if parenttype and _has_field(doctype, "parenttype"):
        filters["parenttype"] = parenttype
    limit = MAX_FINANCIAL_ROWS * 10
    rows = frappe.get_list(
        doctype,
        filters=filters,
        fields=_available_fields(doctype, fields),
        order_by="parent asc, idx asc" if _has_field(doctype, "idx") else "parent asc",
        limit_page_length=limit + 1,
        parent_doctype=parent_doctype,
    )
    if len(rows) > limit:
        quality.append(
            _quality(
                "source_truncated",
                _("{0} results are truncated at {1} recent rows.").format(doctype, limit),
                document_type=doctype,
                limit=limit,
            )
        )
    return rows[:limit]


def _can_read(doctype: str, quality: list[dict]) -> bool:
    if not frappe.db.exists("DocType", doctype):
        quality.append(
            _quality(
                "unavailable_source",
                _("Cash-flow source {0} is not installed.").format(doctype),
                document_type=doctype,
            )
        )
        return False
    if not frappe.has_permission(doctype, "read"):
        quality.append(
            _quality(
                "unavailable_source",
                _("Cash-flow source {0} is unavailable under current read permissions.").format(doctype),
                document_type=doctype,
            )
        )
        return False
    return True


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _available_fields(doctype: str, fields: list[str]) -> list[str]:
    return [field for field in fields if field in FRAPPE_SYSTEM_FIELDS or _has_field(doctype, field)]


def _filter_context_rows(projects: list, sales_orders: list, filters: dict) -> tuple[list, list]:
    customer = filters.get("customer")
    status = filters.get("workflow_status")
    project_type = filters.get("project_type")
    currency = filters.get("currency")
    search = (filters.get("search") or "").lower()

    def matches(row, is_project=False):
        workflow_status = (
            _value(row, "custom_project_status") if is_project else _value(row, "custom_orderlift_order_status")
        ) or _value(row, "status")
        if customer and _value(row, "customer") != customer:
            return False
        if status and workflow_status != status:
            return False
        if project_type and (not is_project or _value(row, "project_type") != project_type):
            return False
        if currency and not is_project and _value(row, "currency") != currency:
            return False
        haystack = " ".join(
            str(_value(row, field) or "")
            for field in ("name", "project_name", "title", "customer", "status")
        ).lower()
        return not search or search in haystack

    filtered_projects = [row for row in projects if matches(row, is_project=True)]
    project_names = {_value(row, "name") for row in filtered_projects}
    filtered_orders = [
        row
        for row in sales_orders
        if (
            (_value(row, "project") and _value(row, "project") in project_names)
            or (not _value(row, "project") and matches(row))
        )
    ]
    return filtered_projects, filtered_orders


def _invoice_allocations(
    invoices: list[dict],
    items: list[dict],
    so_context: dict,
    project_names: set[str],
    *,
    custom_order_field: str,
    po_item_context: dict | None = None,
) -> tuple[dict, list[dict]]:
    by_parent = defaultdict(list)
    for item in items:
        by_parent[_value(item, "parent")].append(item)
    allocations = {}
    quality = []
    for invoice in invoices:
        name = _value(invoice, "name")
        weighted = defaultdict(float)
        total_weight = 0.0
        for item in by_parent.get(name, []):
            weight = abs(
                flt(
                    _value(item, "base_net_amount")
                    or _value(item, "base_amount")
                    or _value(item, "net_amount")
                    or _value(item, "amount")
                )
            )
            total_weight += weight
            key = _item_context(item, so_context, project_names, po_item_context)
            if key:
                weighted[key] += weight
        if not weighted:
            project = (_value(invoice, "project") or "").strip()
            order = (_value(invoice, custom_order_field) or "").strip()
            key = ("Project", project) if project in project_names else so_context.get(order)
            if key:
                weighted[key] = 1
                total_weight = 1
        if not weighted:
            quality.append(
                _quality(
                    "unassigned_invoice",
                    _("{0} {1} has no permitted Project or standalone Sales Order attribution.").format(
                        _value(invoice, "doctype") or "Invoice", name
                    ),
                    document_name=name,
                )
            )
            continue
        denominator = total_weight or sum(weighted.values()) or 1
        allocations[name] = {key: weight / denominator for key, weight in weighted.items()}
        assigned = sum(allocations[name].values())
        if assigned < 0.9999:
            quality.append(
                _quality(
                    "partially_unassigned_invoice",
                    _("Invoice {0} has rows without a cash-flow attribution.").format(name),
                    document_name=name,
                )
            )
    return allocations, quality


def _item_context(item: dict, so_context: dict, project_names: set[str], po_item_context: dict | None):
    project = (_value(item, "project") or "").strip()
    if project in project_names:
        return ("Project", project)
    order = (_value(item, "sales_order") or _value(item, "custom_sales_order") or "").strip()
    if order in so_context:
        return so_context[order]
    po_item = (_value(item, "po_detail") or "").strip()
    if po_item_context and po_item in po_item_context:
        return po_item_context[po_item]
    purchase_order = (_value(item, "purchase_order") or "").strip()
    if po_item_context and purchase_order in po_item_context:
        return po_item_context[purchase_order]
    return None


def _purchase_order_item_context(data: dict, project_names: set[str], so_context: dict) -> dict:
    orders = {_value(row, "name"): row for row in data.get("purchase_orders", [])}
    context = {}
    order_contexts = defaultdict(set)
    for item in data.get("purchase_order_items", []):
        order_name = _value(item, "parent")
        project = (_value(item, "project") or _value(orders.get(_value(item, "parent"), {}), "project") or "").strip()
        if project in project_names:
            key = ("Project", project)
            context[_value(item, "name")] = key
            order_contexts[order_name].add(key)
            continue
        sales_order = (_value(item, "sales_order") or "").strip()
        if sales_order in so_context:
            key = so_context[sales_order]
            context[_value(item, "name")] = key
            order_contexts[order_name].add(key)
    for order_name, keys in order_contexts.items():
        if len(keys) == 1:
            context[order_name] = next(iter(keys))
    return context


def _purchase_order_allocations(
    data: dict, project_names: set[str], so_context: dict
) -> tuple[dict, list[dict]]:
    orders = {_value(row, "name"): row for row in data.get("purchase_orders", [])}
    weighted = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)
    quality = []
    for item in data.get("purchase_order_items", []):
        order_name = _value(item, "parent")
        order = orders.get(order_name, {})
        project = (_value(item, "project") or _value(order, "project") or "").strip()
        amount = abs(flt(_value(item, "base_amount") or _value(item, "amount")))
        totals[order_name] += amount
        if project in project_names:
            weighted[order_name][("Project", project)] += amount
        else:
            sales_order = (_value(item, "sales_order") or "").strip()
            if sales_order in so_context:
                weighted[order_name][so_context[sales_order]] += amount
    allocations = {}
    for name, order in orders.items():
        if not weighted[name]:
            project = (_value(order, "project") or "").strip()
            if project in project_names:
                weighted[name][("Project", project)] = 1
                totals[name] = 1
        if weighted[name]:
            denominator = totals[name] or sum(weighted[name].values()) or 1
            allocations[name] = {key: amount / denominator for key, amount in weighted[name].items()}
        else:
            quality.append(
                _quality(
                    "unassigned_purchase_order",
                    _("Purchase Order {0} has no permitted Project or standalone Sales Order attribution.").format(name),
                    document_type="Purchase Order",
                    document_name=name,
                )
            )
    return allocations, quality


def _payment_events(
    data: dict,
    so_context: dict,
    si_allocations: dict,
    pi_allocations: dict,
    po_allocations: dict,
    company_currency: str,
) -> tuple[list, dict, dict, dict, list]:
    references = defaultdict(list)
    for row in data.get("payment_references", []):
        references[_value(row, "parent")].append(row)
    events = []
    direct_so_advances = defaultdict(float)
    direct_po_advances = defaultdict(float)
    invoice_payment_sources = defaultdict(lambda: defaultdict(float))
    payment_attributed = defaultdict(float)
    quality = []
    allocation_maps = {
        "Sales Invoice": si_allocations,
        "Purchase Invoice": pi_allocations,
        "Purchase Order": po_allocations,
    }
    for payment in data.get("payment_entries", []):
        name = _value(payment, "name")
        direction, sign = payment_direction(_value(payment, "payment_type"))
        if not direction:
            continue
        bank_amount = abs(
            flt(
                _value(payment, "base_received_amount")
                if direction == "inflow"
                else _value(payment, "base_paid_amount")
            )
        )
        payment_refs = references.get(name, [])
        weighted_refs = []
        all_reference_weight = 0.0
        has_unassigned_reference = False
        for ref in payment_refs:
            reference_doctype = _value(ref, "reference_doctype")
            reference_name = _value(ref, "reference_name")
            if reference_doctype == "Sales Order":
                shares = {so_context[reference_name]: 1} if reference_name in so_context else {}
            else:
                shares = allocation_maps.get(reference_doctype, {}).get(reference_name, {})
            weight = abs(flt(_value(ref, "allocated_amount")) * (flt(_value(ref, "exchange_rate")) or 1))
            all_reference_weight += weight
            if shares and weight:
                weighted_refs.append((ref, shares, weight))
            elif weight:
                has_unassigned_reference = True
        if not all_reference_weight or not weighted_refs or not bank_amount:
            quality.append(
                _quality(
                    "unassigned_payment",
                    _("Payment Entry {0} has no allocatable permitted reference.").format(name),
                    document_type="Payment Entry",
                    document_name=name,
                )
            )
            continue
        attributed_bank = min(bank_amount, all_reference_weight)
        allocation_factor = attributed_bank / all_reference_weight
        assigned_bank = sum(
            weight * allocation_factor * sum(shares.values())
            for _, shares, weight in weighted_refs
        )
        unassigned_bank = max(bank_amount - assigned_bank, 0)
        if has_unassigned_reference or unassigned_bank > 0.0001:
            quality.append(
                _quality(
                    "partially_unassigned_payment",
                    _("Payment Entry {0} leaves {1} of bank cash unattributed.").format(name, unassigned_bank),
                    document_type="Payment Entry",
                    document_name=name,
                    amount=unassigned_bank,
                    company_currency=company_currency,
                )
            )
        custom_source_amount = abs(flt(_value(payment, "custom_source_payment_amount")))
        source_currency = (
            _value(payment, "custom_source_document_currency")
            or (
                _value(payment, "paid_from_account_currency")
                if direction == "inflow"
                else _value(payment, "paid_to_account_currency")
            )
            or company_currency
        )
        for ref, shares, ref_weight in weighted_refs:
            reference_doctype = _value(ref, "reference_doctype")
            reference_name = _value(ref, "reference_name")
            for key, share in shares.items():
                amount = ref_weight * allocation_factor * share
                flow_group = "customer" if reference_doctype in {"Sales Invoice", "Sales Order"} else "supplier"
                source_amount = (
                    custom_source_amount * amount / bank_amount
                    if custom_source_amount
                    else abs(flt(_value(ref, "allocated_amount"))) * allocation_factor * share
                )
                events.append(
                    _event(
                        key,
                        layer="actual",
                        direction=direction,
                        event_type="Payment Entry",
                        event_date=_value(payment, "posting_date"),
                        amount=amount,
                        company_currency=company_currency,
                        source_amount=source_amount,
                        source_currency=source_currency,
                        reference_doctype="Payment Entry",
                        reference_name=name,
                        confidence="Actual",
                        flow_group=flow_group,
                        source_reference_doctype=reference_doctype,
                        source_reference_name=reference_name,
                    )
                )
                payment_attributed[name] += amount
                if reference_doctype in {"Sales Invoice", "Purchase Invoice"}:
                    invoice_payment_sources[(reference_doctype, reference_name)][name] += amount
                if reference_doctype == "Sales Order" and sign > 0:
                    direct_so_advances[(reference_name, key)] += amount
                elif reference_doctype == "Purchase Order" and sign < 0:
                    direct_po_advances[(reference_name, key)] += amount
    paid_sources = {"invoices": invoice_payment_sources, "payments": payment_attributed}
    return events, direct_so_advances, direct_po_advances, paid_sources, quality


def _inline_payment_events(
    invoices: list[dict],
    allocations: dict,
    paid_sources: dict,
    company_currency: str,
    doctype: str,
) -> list[dict]:
    events = []
    direction = "inflow" if doctype == "Sales Invoice" else "outflow"
    flow_group = "customer" if doctype == "Sales Invoice" else "supplier"
    for invoice in invoices:
        name = _value(invoice, "name")
        paid = abs(flt(_value(invoice, "base_paid_amount")))
        source_payments = dict(paid_sources.get("invoices", {}).get((doctype, name), {}))
        advance_payment = (_value(invoice, "custom_advance_payment_entry") or "").strip()
        if advance_payment and advance_payment not in source_payments:
            source_payments[advance_payment] = flt(paid_sources.get("payments", {}).get(advance_payment))
        residual_paid = max(paid - sum(source_payments.values()), 0)
        if residual_paid <= 0.0001:
            continue
        event_direction = direction
        if bool(_value(invoice, "is_return")):
            event_direction = "outflow" if direction == "inflow" else "inflow"
        for key, share in allocations.get(name, {}).items():
            events.append(
                _event(
                    key,
                    layer="actual",
                    direction=event_direction,
                    event_type="Inline Invoice Payment",
                    event_date=_value(invoice, "posting_date"),
                    amount=residual_paid * share,
                    company_currency=company_currency,
                    source_amount=(
                        abs(flt(_value(invoice, "paid_amount"))) * residual_paid / paid * share
                        if paid
                        else 0
                    ),
                    source_currency=_value(invoice, "currency") or company_currency,
                    reference_doctype=doctype,
                    reference_name=name,
                    confidence="Actual",
                    flow_group=flow_group,
                )
            )
    return events


def _add_invoice_coverage(
    coverage: dict,
    items: list[dict],
    invoice_name: str,
    key,
    amount: float,
    so_context: dict,
) -> None:
    weights = defaultdict(float)
    for item in items:
        order_name = _value(item, "sales_order")
        if _value(item, "parent") != invoice_name or so_context.get(order_name) != key:
            continue
        weights[order_name] += abs(
            flt(_value(item, "base_net_amount") or _value(item, "base_amount") or _value(item, "amount"))
        )
    order_names = set(weights)
    if not order_names and key[0] == "Sales Order":
        order_names = {key[1]}
        weights[key[1]] = 1
    total_weight = sum(weights.values()) or len(order_names) or 1
    for order_name in order_names:
        coverage[(order_name, key)] += amount * (weights[order_name] or 1) / total_weight


def _add_purchase_invoice_coverage(
    coverage: dict,
    items: list[dict],
    invoice_name: str,
    key,
    amount: float,
    po_allocations: dict,
    so_context: dict,
    project_names: set[str],
    po_item_context: dict,
    po_item_parent: dict,
) -> None:
    weights = defaultdict(float)
    context_weight = 0.0
    for item in items:
        if _value(item, "parent") != invoice_name:
            continue
        item_key = _item_context(item, so_context, project_names, po_item_context)
        if item_key != key:
            continue
        weight = _item_weight(item)
        context_weight += weight
        order_name = (_value(item, "purchase_order") or po_item_parent.get(_value(item, "po_detail")) or "").strip()
        if order_name and key in po_allocations.get(order_name, {}):
            weights[order_name] += weight
    total_weight = context_weight or 1
    for order_name, weight in weights.items():
        coverage[(order_name, key)] += amount * weight / total_weight


def _direct_purchase_invoice_accrual_coverage(
    invoices: list[dict],
    items: list[dict],
    allocations: dict,
    so_context: dict,
    project_names: set[str],
    po_item_context: dict,
) -> dict:
    """Count only PI accrual not already represented by an attributed PO."""
    items_by_parent = defaultdict(list)
    for item in items:
        items_by_parent[_value(item, "parent")].append(item)
    coverage = defaultdict(float)
    for invoice in invoices:
        name = _value(invoice, "name")
        shares = allocations.get(name, {})
        if not shares:
            continue
        invoice_items = items_by_parent.get(name, [])
        total_weight = sum(_item_weight(item) for item in invoice_items)
        invoice_total = _signed_invoice_total(invoice)
        if invoice_items and total_weight:
            for item in invoice_items:
                if _value(item, "purchase_order") or _value(item, "po_detail"):
                    continue
                key = _item_context(item, so_context, project_names, po_item_context)
                if key:
                    coverage[key] += invoice_total * _item_weight(item) / total_weight
        else:
            for key, share in shares.items():
                coverage[key] += invoice_total * share
    return coverage


def _item_weight(item: dict) -> float:
    return abs(
        flt(
            _value(item, "base_net_amount")
            or _value(item, "base_amount")
            or _value(item, "net_amount")
            or _value(item, "amount")
        )
    )


def _validate_payment_schedule(
    schedules: list[dict], document_total: float, doctype: str, name: str, quality: list[dict]
) -> None:
    scheduled = sum(max(flt(row.get("scheduled_amount")), 0) for row in schedules)
    outstanding = sum(max(flt(row.get("amount")), 0) for row in schedules)
    tolerance = max(abs(flt(document_total)) * 0.0001, 0.01)
    if scheduled > flt(document_total) + tolerance:
        quality.append(
            _quality(
                "payment_schedule_overallocated",
                _("{0} {1} payment schedule exceeds the document total.").format(doctype, name),
                document_type=doctype,
                document_name=name,
            )
        )
    elif schedules and scheduled < flt(document_total) - tolerance:
        quality.append(
            _quality(
                "payment_schedule_residual",
                _("{0} {1} has an unscheduled residual cash amount.").format(doctype, name),
                document_type=doctype,
                document_name=name,
                amount=flt(document_total) - scheduled,
            )
        )
    if outstanding > flt(document_total) + tolerance:
        quality.append(
            _quality(
                "payment_schedule_outstanding_invalid",
                _("{0} {1} schedule outstanding exceeds the document total.").format(doctype, name),
                document_type=doctype,
                document_name=name,
            )
        )


def _residual_order_events(
    orders: list[dict],
    schedules: list[dict],
    so_context: dict,
    invoice_coverage: dict,
    direct_advances: dict,
    company_currency: str,
    *,
    direction: str,
    quality: list[dict] | None = None,
    contexts: dict | None = None,
) -> list[dict]:
    quality = quality if quality is not None else []
    by_parent = defaultdict(list)
    for schedule in schedules:
        by_parent[_value(schedule, "parent")].append(schedule)
    events = []
    for order in orders:
        name = _value(order, "name")
        key = so_context.get(name)
        if not key or (_value(order, "status") or "").lower() in {"closed", "cancelled"}:
            continue
        if contexts and contexts.get(key, {}).get("revenue_forecast_final"):
            continue
        rate = _conversion_rate(order)
        company_total = _company_amount(order, "base_grand_total", "grand_total")
        replacement = max(invoice_coverage[(name, key)], 0) + max(direct_advances[(name, key)], 0)
        order_schedules = by_parent.get(name, [])
        uses_outstanding = any(_value(row, "outstanding") not in (None, "") for row in order_schedules)
        normalized_schedules = [
            {
                "name": _value(row, "name"),
                "due_date": _value(row, "due_date"),
                "amount": flt(
                    _value(row, "outstanding")
                    if _value(row, "outstanding") not in (None, "")
                    else _value(row, "payment_amount")
                ) * rate,
                "scheduled_amount": flt(_value(row, "payment_amount")) * rate,
            }
            for row in order_schedules
        ]
        _validate_payment_schedule(normalized_schedules, company_total, "Sales Order", name, quality)
        residual = replace_scheduled_amounts(
            normalized_schedules,
            0 if uses_outstanding else replacement,
            fallback_date=_value(order, "delivery_date") or _value(order, "transaction_date"),
            fallback_amount=company_total,
        )
        for row in residual:
            amount = flt(row["amount"])
            events.append(
                _event(
                    key,
                    layer="committed",
                    direction=direction,
                    event_type="Sales Order Residual Schedule",
                    event_date=row.get("due_date") or _value(order, "delivery_date"),
                    amount=amount,
                    company_currency=company_currency,
                    source_amount=amount / rate,
                    source_currency=_value(order, "currency") or company_currency,
                    reference_doctype="Sales Order",
                    reference_name=name,
                    confidence="Medium",
                )
            )
    return events


def _residual_purchase_order_events(
    orders: list[dict],
    schedules: list[dict],
    allocations: dict,
    invoice_coverage: dict,
    direct_advances: dict,
    company_currency: str,
) -> tuple[list[dict], list[dict]]:
    by_parent = defaultdict(list)
    for schedule in schedules:
        by_parent[_value(schedule, "parent")].append(schedule)
    events = []
    quality = []
    for order in orders:
        name = _value(order, "name")
        if (_value(order, "status") or "").lower() in {"closed", "cancelled"}:
            continue
        rate = _conversion_rate(order)
        total = _company_amount(order, "base_grand_total", "grand_total")
        order_schedules = by_parent.get(name, [])
        uses_outstanding = any(_value(row, "outstanding") not in (None, "") for row in order_schedules)
        normalized_schedules = [
            {
                "name": _value(row, "name"),
                "due_date": _value(row, "due_date"),
                "amount": flt(
                    _value(row, "outstanding")
                    if _value(row, "outstanding") not in (None, "")
                    else _value(row, "payment_amount")
                ) * rate,
                "scheduled_amount": flt(_value(row, "payment_amount")) * rate,
            }
            for row in order_schedules
        ]
        _validate_payment_schedule(normalized_schedules, total, "Purchase Order", name, quality)
        for key, share in allocations.get(name, {}).items():
            schedules_for_context = [
                {
                    **row,
                    "amount": flt(row["amount"]) * share,
                    "scheduled_amount": flt(row["scheduled_amount"]) * share,
                }
                for row in normalized_schedules
            ]
            invoice_replacement = max(invoice_coverage[(name, key)], 0)
            advance_replacement = max(direct_advances[(name, key)], 0)
            confidence = "Medium"
            if invoice_replacement and advance_replacement and not uses_outstanding:
                # We cannot prove whether a direct PO advance was later absorbed
                # by the PI. Ignore the uncertain overlap rather than understating
                # the remaining supplier cash requirement.
                replacement = invoice_replacement
                confidence = "Low"
                quality.append(
                    _quality(
                        "ambiguous_po_replacement_overlap",
                        _("Purchase Order {0} has both invoice and direct-advance coverage; the advance was not used to reduce residual cash.").format(name),
                        context_type=key[0],
                        context_name=key[1],
                        document_type="Purchase Order",
                        document_name=name,
                    )
                )
            else:
                replacement = invoice_replacement + advance_replacement
            residual = replace_scheduled_amounts(
                schedules_for_context,
                0 if uses_outstanding else replacement,
                fallback_date=_value(order, "schedule_date") or _value(order, "transaction_date"),
                fallback_amount=total * share,
            )
            for row in residual:
                amount = flt(row["amount"])
                events.append(
                    _event(
                        key,
                        layer="committed",
                        direction="outflow",
                        event_type="Purchase Order Residual Schedule",
                        event_date=row.get("due_date") or _value(order, "schedule_date"),
                        amount=amount,
                        company_currency=company_currency,
                        source_amount=amount / rate,
                        source_currency=_value(order, "currency") or company_currency,
                        reference_doctype="Purchase Order",
                        reference_name=name,
                        confidence=confidence,
                    )
                )
    return events, quality


def _apply_events_to_contexts(
    contexts: dict, events: list[dict], source_currencies: dict, company_currency: str
) -> None:
    for event in events:
        key = _event_context_key(event)
        context = contexts.get(key)
        if not context:
            continue
        source_currency = event.get("source_currency")
        if source_currency:
            source_currencies[key].add(source_currency)
        amount = flt(event["amount"])
        signed = flt(event["signed_amount"])
        if event["layer"] == "actual":
            context["net_cash"] += signed
            if event.get("flow_group") == "customer":
                context["collected"] += signed
            elif event.get("flow_group") == "supplier":
                context["supplier_paid"] -= signed
        elif event["layer"] == "committed":
            field = "committed_inflow" if event["direction"] == "inflow" else "committed_outflow"
            context[field] += amount
        elif event["layer"] == "forecast" and event["direction"] == "outflow":
            context["forecast_outflow"] += amount

    today = date.today()
    for key, context in contexts.items():
        context_events = [event for event in events if _event_context_key(event) == key]
        position = chronological_funding_position(
            context_events, _horizon_bounds("lifetime", None, None, context_events)
        )
        context.update(position)
        currencies = sorted(source_currencies.get(key) or {company_currency})
        context["source_currencies"] = currencies
        context["source_currency"] = currencies[0] if len(currencies) == 1 else "Mixed"
        context["currency"] = company_currency
        context["company_currency"] = company_currency
        future = [
            event for event in context_events
            if event["layer"] != "actual" and _as_date(event.get("date"), today) >= today
        ]
        next_event = min(future, key=_event_sort_key) if future else None
        context["next_cash_event"] = (
            {
                "date": next_event["date"],
                "direction": next_event["direction"],
                "amount": next_event["amount"],
                "event_type": next_event["event_type"],
                "currency": company_currency,
            }
            if next_event
            else None
        )
        overdue = any(
            event["layer"] == "committed"
            and flt(event["amount"]) > 0
            and _as_date(event.get("date"), today) < today
            for event in context_events
        )
        if context["funding_gap"] > 0:
            context["risk_status"] = "Funding Gap"
        elif overdue:
            context["risk_status"] = "Overdue"
        else:
            context["risk_status"] = "On Track"
        context["risk"] = context["risk_status"]
        context["confidence"] = _context_confidence(context_events)


def _event(
    key,
    *,
    layer: str,
    direction: str,
    event_type: str,
    event_date,
    amount,
    company_currency: str,
    source_amount,
    source_currency: str,
    reference_doctype: str,
    reference_name: str,
    confidence: str,
    flow_group: str = "",
    source_reference_doctype: str = "",
    source_reference_name: str = "",
) -> dict:
    amount = flt(amount)
    sign = 1 if direction == "inflow" else -1
    return {
        "id": "|".join(
            [layer, event_type, reference_doctype, reference_name, key[0], key[1], str(event_date or "")]
        ),
        "context_type": key[0],
        "context_name": key[1],
        "layer": layer,
        "direction": direction,
        "event_type": event_type,
        "date": str(event_date or ""),
        "amount": amount,
        "signed_amount": amount * sign,
        "company_currency": company_currency,
        "source_amount": flt(source_amount),
        "source_currency": source_currency or company_currency,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "route": _document_route(reference_doctype, reference_name),
        "confidence": confidence,
        "flow_group": flow_group,
        "source_reference_doctype": source_reference_doctype,
        "source_reference_name": source_reference_name,
    }


def _context_row(
    context_type: str,
    name: str,
    *,
    title: str,
    customer: str,
    company: str,
    workflow_status: str,
    project_type: str,
    business_type: str = "",
    segment: str = "",
    revenue_forecast_final=0,
    cost_forecast_final=0,
) -> dict:
    route = _document_route(context_type, name)
    return {
        "context_type": context_type,
        "context_name": name,
        "name": name,
        "title": title or name,
        "customer": customer or "",
        "company": company or "",
        "currency": "",
        "company_currency": "",
        "workflow_status": workflow_status or "No Status",
        "status": workflow_status or "No Status",
        "project_type": project_type or ("Project" if context_type == "Project" else "Standalone Sales Order"),
        "business_type": business_type or "",
        "segment": segment or "",
        **{field: 0.0 for field in MONEY_FIELDS},
        **{field: 0.0 for field in PROFIT_AMOUNT_FIELDS},
        "expected_profit_pct": 0.0,
        "actual_profit_pct": 0.0,
        "cost_data_complete": True,
        "profitability_complete": True,
        "revenue_forecast_final": bool(revenue_forecast_final),
        "cost_forecast_final": bool(cost_forecast_final),
        "next_cash_event": None,
        "risk_status": "On Track",
        "risk": "On Track",
        "confidence": "High",
        "link": route,
        "detail_route": f"/app/sale-financial-workspace/{context_type}/{name}",
    }


def _quality(code: str, message: str, **values) -> dict:
    return {"code": code, "severity": "Warning", "message": message, **values}


def _accrual(key, field: str, amount: float, posting_date, doctype: str, name: str) -> dict:
    return {
        "context_type": key[0],
        "context_name": key[1],
        "field": field,
        "amount": flt(amount),
        "date": str(posting_date or ""),
        "reference_doctype": doctype,
        "reference_name": name,
    }


def _signed_invoice_total(invoice: dict) -> float:
    total = _company_amount(invoice, "base_grand_total", "grand_total")
    if _value(invoice, "is_return"):
        return -abs(total)
    return total


def _signed_net_total(document: dict) -> float:
    total = _company_net_amount(document)
    if _value(document, "is_return"):
        return -abs(total)
    return total


def _company_amount(row: dict, base_field: str, source_field: str) -> float:
    base_value = _value(row, base_field)
    if base_value not in (None, ""):
        return flt(base_value)
    return flt(_value(row, source_field)) * _conversion_rate(row)


def _company_net_amount(row: dict) -> float:
    base_net = _value(row, "base_net_total")
    if base_net not in (None, ""):
        return flt(base_net)
    net = _value(row, "net_total")
    if net not in (None, ""):
        return flt(net) * _conversion_rate(row)
    base_grand = _company_amount(row, "base_grand_total", "grand_total")
    base_taxes = _value(row, "base_total_taxes_and_charges")
    if base_taxes not in (None, ""):
        return base_grand - flt(base_taxes)
    taxes = _value(row, "total_taxes_and_charges")
    if taxes not in (None, ""):
        return base_grand - flt(taxes) * _conversion_rate(row)
    return base_grand


def _conversion_rate(row: dict) -> float:
    return flt(_value(row, "conversion_rate")) or 1.0


def _value(row, fieldname: str):
    if row is None:
        return None
    if hasattr(row, "get"):
        return row.get(fieldname)
    return getattr(row, fieldname, None)


def _event_context_key(event: dict) -> tuple[str, str]:
    return event["context_type"], event["context_name"]


def _event_sort_key(event: dict):
    return str(event.get("date") or "9999-12-31"), event.get("event_type") or "", event.get("id") or ""


def _funding_event_sort_key(event: dict):
    return (
        str(event.get("date") or "9999-12-31"),
        0 if event.get("direction") == "outflow" else 1,
        event.get("event_type") or "",
        event.get("id") or "",
    )


def _context_confidence(events: list[dict]) -> str:
    values = {event.get("confidence") for event in events}
    if "Low" in values:
        return "Low"
    if "Medium" in values:
        return "Medium"
    return "High"


def _document_route(doctype: str, name: str) -> str:
    slug = (doctype or "").strip().lower().replace(" ", "-")
    return f"/app/{slug}/{name}" if slug and name else ""


def _finalize_profitability(contexts: dict) -> None:
    for context in contexts.values():
        ordered_ht = flt(context.get("ordered_revenue_ht"))
        ordered_ttc = flt(context.get("ordered_revenue_ttc"))
        invoiced_ht = flt(context.get("invoiced_revenue_ht"))
        invoiced_ttc = flt(context.get("invoiced_revenue_ttc"))

        if context.get("revenue_forecast_final"):
            remaining_ht = 0.0
            remaining_ttc = 0.0
        else:
            remaining_ht = max(ordered_ht - invoiced_ht, 0.0)
            remaining_ttc = max(ordered_ttc - invoiced_ttc, 0.0)
        context["remaining_revenue_ht"] = remaining_ht
        context["remaining_revenue_ttc"] = remaining_ttc
        context["expected_revenue_ht"] = invoiced_ht + remaining_ht
        context["expected_revenue_ttc"] = invoiced_ttc + remaining_ttc
        context["expected_taxes"] = context["expected_revenue_ttc"] - context["expected_revenue_ht"]

        actual_cost = flt(context.get("actual_cost_ht"))
        committed_cost = flt(context.get("committed_cost"))
        forecast_cost = 0.0
        if not context.get("cost_forecast_final"):
            forecast_cost = max(flt(context.get("baseline_cost")) - actual_cost - committed_cost, 0.0)
        context["forecast_cost"] = forecast_cost
        context["expected_cost"] = actual_cost + committed_cost + forecast_cost
        context["expected_profit"] = context["expected_revenue_ht"] - context["expected_cost"]
        context["actual_profit_to_date"] = invoiced_ht - actual_cost
        context["profitability_complete"] = bool(
            context.get("cost_forecast_final") or context.get("cost_data_complete")
        )
        _refresh_profit_percentages(context)


def _add_profitability_quality(contexts: dict, quality: list[dict]) -> None:
    for key, context in contexts.items():
        if (
            context.get("revenue_forecast_final")
            and flt(context.get("ordered_revenue_ht")) > flt(context.get("invoiced_revenue_ht")) + 0.01
        ):
            quality.append(
                _quality(
                    "revenue_closed_uninvoiced",
                    _("Revenue forecast is final while submitted Sales Orders remain partly uninvoiced."),
                    context_type=key[0],
                    context_name=key[1],
                    amount=flt(context.get("ordered_revenue_ht")) - flt(context.get("invoiced_revenue_ht")),
                    company_currency=context.get("company_currency") or context.get("currency") or "",
                )
            )
        covered_cost = flt(context.get("actual_cost_ht")) + flt(context.get("committed_cost"))
        if covered_cost > flt(context.get("baseline_cost")) + 0.01:
            quality.append(
                _quality(
                    "cost_overrun",
                    _("Actual and committed costs exceed the Sales Order baseline cost."),
                    context_type=key[0],
                    context_name=key[1],
                    amount=covered_cost - flt(context.get("baseline_cost")),
                    company_currency=context.get("company_currency") or context.get("currency") or "",
                )
            )


def _refresh_profit_percentages(values: dict) -> None:
    expected_revenue = flt(values.get("expected_revenue_ht"))
    actual_revenue = flt(values.get("invoiced_revenue_ht"))
    values["expected_profit_pct"] = (
        round(flt(values.get("expected_profit")) / expected_revenue * 100, 2)
        if expected_revenue
        else 0.0
    )
    values["actual_profit_pct"] = (
        round(flt(values.get("actual_profit_to_date")) / actual_revenue * 100, 2)
        if actual_revenue
        else 0.0
    )


def _profitability_payload(context: dict) -> dict:
    return {
        "currency": context.get("company_currency") or context.get("currency") or "",
        "expected": {
            "revenue_ht": flt(context.get("expected_revenue_ht")),
            "revenue_ttc": flt(context.get("expected_revenue_ttc")),
            "taxes": flt(context.get("expected_taxes")),
            "cost": flt(context.get("expected_cost")),
            "profit": flt(context.get("expected_profit")),
            "profit_pct": flt(context.get("expected_profit_pct")),
            "complete": bool(context.get("profitability_complete")),
        },
        "actual": {
            "revenue_ht": flt(context.get("invoiced_revenue_ht")),
            "revenue_ttc": flt(context.get("invoiced_revenue_ttc")),
            "taxes": flt(context.get("invoiced_taxes")),
            "cost": flt(context.get("actual_cost_ht")),
            "profit": flt(context.get("actual_profit_to_date")),
            "profit_pct": flt(context.get("actual_profit_pct")),
        },
        "revenue": {
            "ordered_ht": flt(context.get("ordered_revenue_ht")),
            "ordered_ttc": flt(context.get("ordered_revenue_ttc")),
            "invoiced_ht": flt(context.get("invoiced_revenue_ht")),
            "invoiced_ttc": flt(context.get("invoiced_revenue_ttc")),
            "remaining_ht": flt(context.get("remaining_revenue_ht")),
            "remaining_ttc": flt(context.get("remaining_revenue_ttc")),
        },
        "costs": {
            "baseline": flt(context.get("baseline_cost")),
            "actual": flt(context.get("actual_cost_ht")),
            "committed": flt(context.get("committed_cost")),
            "forecast": flt(context.get("forecast_cost")),
            "expected": flt(context.get("expected_cost")),
        },
        "cash": {field: flt(context.get(field)) for field in MONEY_FIELDS},
        "closure": {
            "revenue_final": bool(context.get("revenue_forecast_final")),
            "cost_final": bool(context.get("cost_forecast_final")),
        },
    }


def _summarize(
    rows: list[dict],
    quality: list[dict] | None = None,
    *,
    events: list[dict] | None = None,
    bounds: dict | None = None,
) -> dict:
    summary = {
        field: sum(flt(row.get(field)) for row in rows)
        for field in (*MONEY_FIELDS, *PROFIT_AMOUNT_FIELDS)
    }
    summary["profitability_complete"] = bool(rows) and all(
        row.get("profitability_complete") for row in rows
    )
    summary["incomplete_profitability"] = sum(
        not row.get("profitability_complete") for row in rows
    )
    _refresh_profit_percentages(summary)
    quality = quality or []
    overdue = sum(row.get("risk_status") == "Overdue" for row in rows)
    summary.update(
        {
            "projects": sum(row.get("context_type") == "Project" for row in rows),
            "standalone_sales_orders": sum(row.get("context_type") == "Sales Order" for row in rows),
            "at_risk": sum(row.get("risk_status") != "On Track" for row in rows),
            "overdue": overdue,
            "expected_outflow": summary["committed_outflow"] + summary["forecast_outflow"],
            "completeness": max(100.0 - (len(quality) / max(len(rows), 1) * 100.0), 0.0),
        }
    )
    if events is not None and bounds:
        # Portfolio liquidity is one consolidated chronological path. Summing
        # independent context gaps overstates cash needed when contexts offset.
        summary.update(chronological_funding_position(events, bounds))
    return summary


def _detail_completeness(quality: list[dict]) -> dict:
    unavailable = sorted(
        {row.get("document_type") for row in quality if row.get("code") == "unavailable_source"}
        - {None, ""}
    )
    truncated = sorted(
        {row.get("document_type") for row in quality if row.get("code") in {"source_truncated", "detail_events_truncated"}}
        - {None, ""}
    )
    is_truncated = any(
        row.get("code") in {"source_truncated", "detail_events_truncated"} for row in quality
    )
    return {
        "complete": not unavailable and not is_truncated,
        "unavailable_sources": unavailable,
        "truncated_sources": truncated,
        "truncated": is_truncated,
        "issue_count": len(quality),
    }


def _group_rows(
    rows: list[dict],
    fieldname: str,
    context_type: str,
    *,
    events: list[dict] | None = None,
    bounds: dict | None = None,
) -> list[dict]:
    grouped = {}
    for row in rows:
        name = row.get(fieldname) or "Unassigned"
        target = grouped.setdefault(
            name,
            {
                "context_type": context_type,
                "context_name": name,
                "name": name,
                "title": name,
                "customer": name if fieldname == "customer" else "",
                "company": row.get("company") or "",
                "currency": row.get("company_currency") or "",
                "company_currency": row.get("company_currency") or "",
                "source_currency": row.get("source_currency") or "",
                "workflow_status": "",
                "project_type": "",
                **{field: 0.0 for field in MONEY_FIELDS},
                **{field: 0.0 for field in PROFIT_AMOUNT_FIELDS},
                "expected_profit_pct": 0.0,
                "actual_profit_pct": 0.0,
                "profitability_complete": True,
                "next_cash_event": None,
                "risk_status": "On Track",
                "risk": "On Track",
                "confidence": "High",
                "link": _document_route(context_type, name) if name != "Unassigned" else "",
                "detail_route": "",
                "context_count": 0,
                "_context_keys": set(),
            },
        )
        target["context_count"] += 1
        target["_context_keys"].add((row.get("context_type"), row.get("context_name")))
        for money_field in MONEY_FIELDS:
            target[money_field] += flt(row.get(money_field))
        for profit_field in PROFIT_AMOUNT_FIELDS:
            target[profit_field] += flt(row.get(profit_field))
        if not row.get("profitability_complete"):
            target["profitability_complete"] = False
        if row.get("next_cash_event") and (
            not target["next_cash_event"]
            or str(row["next_cash_event"]["date"]) < str(target["next_cash_event"]["date"])
        ):
            target["next_cash_event"] = row["next_cash_event"]
        if row.get("risk_status") == "Funding Gap":
            target["risk_status"] = "Funding Gap"
        elif row.get("risk_status") == "Overdue" and target["risk_status"] == "On Track":
            target["risk_status"] = "Overdue"
        target["risk"] = target["risk_status"]
        if row.get("confidence") == "Low":
            target["confidence"] = "Low"
        elif row.get("confidence") == "Medium" and target["confidence"] == "High":
            target["confidence"] = "Medium"
    for target in grouped.values():
        _refresh_profit_percentages(target)
        if events is not None and bounds:
            group_events = [
                event for event in events if _event_context_key(event) in target["_context_keys"]
            ]
            target.update(chronological_funding_position(group_events, bounds))
        target.pop("_context_keys", None)
    return sorted(grouped.values(), key=lambda row: row["name"])


def _monthly_performance(events: list[dict], company_currency: str) -> list[dict]:
    rows = {}
    for event in events:
        event_date = _as_date(event.get("date"))
        month = event_date.strftime("%Y-%m")
        row = rows.setdefault(
            month,
            {
                "month": month,
                "label": event_date.strftime("%b %Y"),
                "company_currency": company_currency,
                "currency": company_currency,
                "actual_inflow": 0.0,
                "actual_outflow": 0.0,
                "committed_inflow": 0.0,
                "committed_outflow": 0.0,
                "forecast_outflow": 0.0,
                "net": 0.0,
            },
        )
        field = f"{event['layer']}_{event['direction']}"
        if field in row:
            row[field] += flt(event["amount"])
        row["net"] += flt(event["signed_amount"])
    return [rows[key] for key in sorted(rows)]


def _filter_options(rows: list[dict], currencies: list[str]) -> dict:
    workflow_statuses = sorted({row["workflow_status"] for row in rows if row.get("workflow_status")})
    return {
        "companies": sorted({row["company"] for row in rows if row.get("company")}),
        "customers": sorted({row["customer"] for row in rows if row.get("customer")}),
        "context_types": ["Project", "Sales Order"],
        "workflow_statuses": workflow_statuses,
        "statuses": workflow_statuses,
        "project_types": sorted({row["project_type"] for row in rows if row.get("project_type")}),
        "business_types": sorted({row["business_type"] for row in rows if row.get("business_type")}),
        "segments": sorted({row["segment"] for row in rows if row.get("segment")}),
        "risk_statuses": ["On Track", "Overdue", "Funding Gap"],
        "currencies": currencies,
        "horizons": _horizon_options(),
    }


def _matches_output_filters(row: dict, filters: dict) -> bool:
    if filters.get("context_type") and row.get("context_type") != filters["context_type"]:
        return False
    if filters.get("context_name") and row.get("context_name") != filters["context_name"]:
        return False
    if filters.get("customer") and row.get("customer") != filters["customer"]:
        return False
    if filters.get("workflow_status") and row.get("workflow_status") != filters["workflow_status"]:
        return False
    if filters.get("project_type") and row.get("project_type") != filters["project_type"]:
        return False
    if filters.get("business_type") and row.get("business_type") != filters["business_type"]:
        return False
    if filters.get("segment") and row.get("segment") != filters["segment"]:
        return False
    if filters.get("currency") and filters["currency"] not in set(row.get("source_currencies") or []):
        return False
    if filters.get("risk_status") and row.get("risk_status") != filters["risk_status"]:
        return False
    if filters.get("revenue_forecast_status"):
        expected = filters["revenue_forecast_status"].lower() == "final"
        if bool(row.get("revenue_forecast_final")) != expected:
            return False
    if filters.get("cost_forecast_status"):
        expected = filters["cost_forecast_status"].lower() == "final"
        if bool(row.get("cost_forecast_final")) != expected:
            return False
    search = (filters.get("search") or "").lower()
    if search:
        text = " ".join(
            str(row.get(key) or "")
            for key in ("name", "title", "customer", "workflow_status", "project_type")
        ).lower()
        if search not in text:
            return False
    return True


def _horizon_options() -> list[dict]:
    return [
        {"value": "13_weeks", "label": "13 weeks"},
        {"value": "monthly", "label": "12 months"},
        {"value": "lifetime", "label": "Lifetime"},
    ]


def _context_for_horizon(
    context: dict, events: list[dict], bounds: dict, accruals: list[dict] | None = None
) -> dict:
    row = dict(context)
    key = (row["context_type"], row["context_name"])
    start = _as_date(bounds["from_date"])
    end = _as_date(bounds["to_date"])
    context_events = [event for event in events if _event_context_key(event) == key]
    forward_events = [
        event
        for event in context_events
        if event["layer"] != "actual"
        and _as_date(event.get("date"), start) <= end
    ]
    actual_events = [
        event
        for event in context_events
        if event["layer"] == "actual" and _as_date(event.get("date"), start) <= end
    ]
    context_accruals = [
        row
        for row in accruals or []
        if (row.get("context_type"), row.get("context_name")) == key
        and _as_date(row.get("date"), start) <= end
    ]
    for field in ("ordered", "invoiced", "actual_cost"):
        row[field] = sum(flt(item["amount"]) for item in context_accruals if item.get("field") == field)
    row["net_cash"] = sum(flt(event["signed_amount"]) for event in actual_events)
    row["collected"] = sum(
        flt(event["signed_amount"]) for event in actual_events if event.get("flow_group") == "customer"
    )
    row["supplier_paid"] = -sum(
        flt(event["signed_amount"]) for event in actual_events if event.get("flow_group") == "supplier"
    )
    row["committed_inflow"] = sum(
        flt(event["amount"])
        for event in forward_events
        if event["layer"] == "committed" and event["direction"] == "inflow"
    )
    row["committed_outflow"] = sum(
        flt(event["amount"])
        for event in forward_events
        if event["layer"] == "committed" and event["direction"] == "outflow"
    )
    row["forecast_outflow"] = sum(
        flt(event["amount"])
        for event in forward_events
        if event["layer"] == "forecast" and event["direction"] == "outflow"
    )
    row.update(chronological_funding_position(context_events, bounds))
    upcoming = [
        event
        for event in forward_events
        if _as_date(event.get("date"), start) >= start
    ]
    next_event = min(upcoming, key=_event_sort_key) if upcoming else None
    row["next_cash_event"] = (
        {
            "date": next_event["date"],
            "direction": next_event["direction"],
            "amount": next_event["amount"],
            "event_type": next_event["event_type"],
            "currency": row.get("company_currency") or "",
        }
        if next_event
        else None
    )
    overdue = any(
        event["layer"] == "committed"
        and flt(event["amount"]) > 0
        and _as_date(event.get("date"), start) < start
        for event in forward_events
    )
    row["risk_status"] = "Funding Gap" if row["funding_gap"] > 0 else "Overdue" if overdue else "On Track"
    row["risk"] = row["risk_status"]
    return row


def _horizon_bounds(horizon: str, from_date, to_date, events: list[dict]) -> dict:
    horizon = (horizon or "13_weeks").strip().lower()
    today = date.today()
    if from_date or to_date:
        start = _as_date(from_date, today)
        end = _as_date(to_date, start + timedelta(days=90))
        interval = "week" if (end - start).days <= 120 else "month"
        mode = "custom"
    elif horizon in {"13_weeks", "13-week", "weekly"}:
        start = today
        end = today + timedelta(days=90)
        interval = "week"
        mode = "13_weeks"
    elif horizon in {"monthly", "12_months"}:
        start = today.replace(day=1)
        end = _add_months(start, 12) - timedelta(days=1)
        interval = "month"
        mode = "monthly"
    elif horizon == "lifetime":
        dates = [_as_date(event.get("date"), today) for event in events]
        start = min(dates or [today]).replace(day=1)
        end = max(dates or [today])
        interval = "month"
        mode = "lifetime"
    else:
        frappe.throw(_("Horizon must be 13_weeks, monthly, lifetime, or a custom date range."))
    if end < start:
        frappe.throw(_("To Date must not be before From Date."))
    return {"mode": mode, "from_date": str(start), "to_date": str(end), "interval": interval}


def _events_for_horizon_detail(events: list[dict], bounds: dict) -> list[dict]:
    """Return the event rows represented within the selected liquidity path."""
    start = _as_date(bounds["from_date"])
    end = _as_date(bounds["to_date"])
    return [
        event
        for event in events
        if _as_date(event.get("date"), start) <= end
        and (event["layer"] != "actual" or _as_date(event.get("date"), start) > start)
    ]


def _bucket_events(
    events: list[dict], bounds: dict, *, detail_events: list[dict] | None = None
) -> list[dict]:
    start = _as_date(bounds["from_date"])
    end = _as_date(bounds["to_date"])
    interval = bounds["interval"]
    company_currency = next((event.get("company_currency") for event in events if event.get("company_currency")), "")
    actual_net = sum(
        flt(event["signed_amount"])
        for event in events
        if event["layer"] == "actual" and _as_date(event.get("date"), start) <= start
    )
    overdue = [
        event for event in events
        if event["layer"] != "actual" and _as_date(event.get("date"), start) < start
    ]
    periods = []
    cursor = start
    while cursor <= end:
        period_end = min(
            cursor + timedelta(days=6) if interval == "week" else _add_months(cursor.replace(day=1), 1) - timedelta(days=1),
            end,
        )
        periods.append((cursor, period_end))
        cursor = period_end + timedelta(days=1)
    position = actual_net
    output = []
    detail_event_objects = (
        {id(event) for event in detail_events} if detail_events is not None else None
    )
    for index, (period_start, period_end) in enumerate(periods):
        bucket_events = [
            event for event in events
            if period_start <= _as_date(event.get("date"), period_start) <= period_end
            and not (event["layer"] == "actual" and _as_date(event.get("date"), period_start) <= start)
        ]
        if index == 0:
            bucket_events = overdue + bucket_events
        bucket_events = sorted(bucket_events, key=_funding_event_sort_key)
        row = {
            "from_date": str(period_start),
            "to_date": str(period_end),
            "label": (
                f"W{period_start.isocalendar().week} {period_start.year}"
                if interval == "week"
                else period_start.strftime("%b %Y")
            ),
            "opening_position": position,
            "company_currency": company_currency,
            "currency": company_currency,
            "actual_inflow": 0.0,
            "actual_outflow": 0.0,
            "committed_inflow": 0.0,
            "committed_outflow": 0.0,
            "forecast_outflow": 0.0,
            "events": sorted(
                (
                    event
                    for event in bucket_events
                    if detail_event_objects is None or id(event) in detail_event_objects
                ),
                key=_event_sort_key,
            ),
        }
        minimum_position = position
        for event in bucket_events:
            field = f"{event['layer']}_{event['direction']}"
            if field in row:
                row[field] += flt(event["amount"])
            position += flt(event["signed_amount"])
            minimum_position = min(minimum_position, position)
        row["closing_position"] = position
        row["funding_gap"] = max(-minimum_position, 0.0)
        output.append(row)
    return output


def _documents_for_context(data: dict, model: dict, key) -> list[dict]:
    documents = {(key[0], key[1])}
    for event in model["events"]:
        if _event_context_key(event) != key:
            continue
        documents.add((event["reference_doctype"], event["reference_name"]))
        if event.get("source_reference_doctype") and event.get("source_reference_name"):
            documents.add((event["source_reference_doctype"], event["source_reference_name"]))
    return [
        {
            "doctype": doctype,
            "name": name,
            "route": _document_route(doctype, name),
        }
        for doctype, name in sorted(documents)
    ]


def _alerts(identity: dict, receivables: list[dict], payables: list[dict]) -> list[dict]:
    today = date.today()
    alerts = []
    overdue_receivables = sum(
        flt(row["amount"]) for row in receivables if _as_date(row.get("date"), today) < today
    )
    overdue_payables = sum(
        flt(row["amount"]) for row in payables if _as_date(row.get("date"), today) < today
    )
    if overdue_receivables:
        alerts.append({"type": "overdue_receivables", "severity": "Warning", "amount": overdue_receivables})
    if overdue_payables:
        alerts.append({"type": "overdue_payables", "severity": "Warning", "amount": overdue_payables})
    if flt(identity.get("funding_gap")):
        alerts.append({"type": "funding_gap", "severity": "Critical", "amount": identity["funding_gap"]})
    return alerts


def _as_date(value, default: date | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return default or date.today()


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)
