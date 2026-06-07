"""Generic engine for admin-defined metrics: source_type = 'Doc Query'.

Configuration comes from the Performance Metric definition:
- source_doctype: any DocType
- aggregate: count | sum | avg | min | max
- value_field: required for non-count aggregates
- employee_link_field: column to match against the employee or their user_id
- filters_json: additional dict-style filters (parsed by the registry caller)
- date_field (in params): the date field used for from/to window (defaults to creation)
"""

from __future__ import annotations

import json
from statistics import mean

import frappe

from orderlift.orderlift_hr.metrics.base import MetricResult, register, resolve_user


def _parse_filters(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@register("generic.doc_query")
def generic_doc_query(employee, from_date, to_date, params):
    params = params or {}
    doctype = params.get("source_doctype")
    aggregate = (params.get("aggregate") or "count").lower()
    value_field = params.get("value_field")
    employee_link_field = params.get("employee_link_field") or "owner"
    date_field = params.get("date_field") or "creation"
    unit = params.get("unit") or ("count" if aggregate == "count" else "")
    if not doctype:
        return MetricResult(status="Error", error="source_doctype missing", unit=unit)

    user = resolve_user(employee)
    link_value = user if employee_link_field in ("owner", "modified_by") else (
        user or employee
    )

    filters = _parse_filters(params.get("filters_json"))
    filters[employee_link_field] = link_value
    if from_date and to_date:
        filters[date_field] = ["between", [from_date, to_date]]

    fields = ["name"]
    if aggregate != "count" and value_field:
        fields.append(value_field)

    try:
        rows = frappe.get_all(doctype, filters=filters, fields=fields, limit_page_length=0)
    except Exception as exc:
        return MetricResult(status="Error", error=str(exc), unit=unit)

    if aggregate == "count":
        return MetricResult(value=float(len(rows)), unit=unit or "count")

    if not value_field:
        return MetricResult(status="Error", error="value_field required", unit=unit)

    numbers = [float(getattr(r, value_field, None) or 0.0) for r in rows]
    if not numbers:
        return MetricResult(value=0.0, unit=unit)

    if aggregate == "sum":
        return MetricResult(value=sum(numbers), unit=unit)
    if aggregate == "avg":
        return MetricResult(value=mean(numbers), unit=unit)
    if aggregate == "min":
        return MetricResult(value=min(numbers), unit=unit)
    if aggregate == "max":
        return MetricResult(value=max(numbers), unit=unit)

    return MetricResult(status="Error", error=f"Unsupported aggregate: {aggregate}", unit=unit)
