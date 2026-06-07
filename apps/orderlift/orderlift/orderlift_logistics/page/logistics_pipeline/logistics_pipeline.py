from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from orderlift.menu_access import get_company_access_payload
from orderlift.orderlift_crm.api.pipeline import (
    _assignment_for_card,
    _log_status_change,
    sync_pipeline_status_assignment,
)
from orderlift.orderlift_crm.status_config import UNASSIGNED_STATUS
from orderlift.orderlift_crm.status_workflow import list_editable_statuses, resolve_status_column
from orderlift.orderlift_logistics.services.forecast_planning import advance_status


@frappe.whitelist()
def get_logistics_pipeline_data(
    search: str | None = None,
    company: str | None = None,
    flow_scope: str | None = None,
    shipping_responsibility: str | None = None,
) -> dict:
    company = _resolve_pipeline_company(company)
    statuses = list_editable_statuses("Forecast Load Plan", include_inactive=False, company=company)
    cards = _forecast_load_plan_cards(
        statuses,
        search=search,
        company=company,
        flow_scope=flow_scope,
        shipping_responsibility=shipping_responsibility,
    )
    return {
        "columns": _build_columns(statuses, cards),
        "kpis": {
            "primary_label": _("Containers"),
            "primary_value": len(cards),
            "secondary_label": _("In Transit"),
            "secondary_value": len([card for card in cards if card.get("stage") == "In Transit"]),
            "tertiary_label": _("Over Capacity"),
            "tertiary_value": len([card for card in cards if "Over capacity" in card.get("risk_flags", [])]),
            "quaternary_label": _("Overdue"),
            "quaternary_value": len([card for card in cards if "Overdue" in card.get("risk_flags", [])]),
        },
        "filters": {
            "companies": _allowed_pipeline_companies(),
            "flow_scopes": sorted({card.get("flow_scope") for card in cards if card.get("flow_scope")}),
            "shipping_responsibilities": sorted(
                {card.get("shipping_responsibility") for card in cards if card.get("shipping_responsibility")}
            ),
        },
        "selected_company": company,
    }


@frappe.whitelist()
def update_logistics_stage(plan: str, stage: str) -> dict:
    doc = frappe.get_doc("Forecast Load Plan", plan)
    status_info = _status_info(stage, doc.get("company"))
    previous = doc.status
    result = advance_status(plan, stage)
    if isinstance(result, dict) and result.get("validation"):
        return {"validation": result["validation"]}

    doc = frappe.get_doc("Forecast Load Plan", plan)
    assignment = sync_pipeline_status_assignment("Forecast Load Plan", doc.name, status_info, stage)
    frappe.db.commit()
    _log_status_change("Forecast Load Plan", doc.name, previous, stage)
    card = _forecast_load_plan_card(
        doc.as_dict(),
        list_editable_statuses("Forecast Load Plan", include_inactive=False, company=doc.get("company")),
    )
    card["assignment"] = assignment
    return {"card": card}


def _forecast_load_plan_cards(
    statuses: list[dict],
    search: str | None = None,
    company: str | None = None,
    flow_scope: str | None = None,
    shipping_responsibility: str | None = None,
) -> list[dict]:
    filters = {}
    if company and company != "All":
        filters["company"] = company
    if flow_scope and flow_scope != "All":
        filters["flow_scope"] = flow_scope
    if shipping_responsibility and shipping_responsibility != "All":
        filters["shipping_responsibility"] = shipping_responsibility

    rows = frappe.get_all(
        "Forecast Load Plan",
        filters=filters,
        fields=[
            "name",
            "plan_label",
            "company",
            "container_profile",
            "route_origin",
            "route_destination",
            "flow_scope",
            "shipping_responsibility",
            "destination_zone",
            "departure_date",
            "deadline",
            "status",
            "total_weight_kg",
            "total_volume_m3",
            "weight_utilization_pct",
            "volume_utilization_pct",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=200,
    )
    cards = [_forecast_load_plan_card(row, statuses) for row in rows]
    if search:
        needle = search.strip().lower()
        cards = [
            card
            for card in cards
            if needle
            in f"{card.get('name')} {card.get('title')} {card.get('container_profile')} {card.get('route')} {card.get('destination_zone')}".lower()
        ]
    return cards


def _forecast_load_plan_card(row, statuses: list[dict]) -> dict:
    name = row.get("name")
    stage = resolve_status_column("Forecast Load Plan", row.get("status"), statuses=statuses)
    assignment = _assignment_for_card("Forecast Load Plan", name, stage, statuses)
    item_summary = _plan_item_summary(name)
    risks = _risk_flags(row)
    route = " -> ".join([value for value in [row.get("route_origin"), row.get("route_destination")] if value])
    return {
        "name": name,
        "title": row.get("plan_label") or name,
        "subtitle": row.get("container_profile") or _("No container profile"),
        "container_profile": row.get("container_profile") or "",
        "company": row.get("company") or "",
        "flow_scope": row.get("flow_scope") or "",
        "shipping_responsibility": row.get("shipping_responsibility") or "",
        "destination_zone": row.get("destination_zone") or "",
        "route": route,
        "departure_date": row.get("departure_date"),
        "deadline": row.get("deadline"),
        "stage": stage,
        "weight_utilization_pct": flt(row.get("weight_utilization_pct")),
        "volume_utilization_pct": flt(row.get("volume_utilization_pct")),
        "total_weight_kg": flt(row.get("total_weight_kg")),
        "total_volume_m3": flt(row.get("total_volume_m3")),
        "item_count": item_summary["item_count"],
        "total_item_count": item_summary["total_item_count"],
        "source_doc_count": item_summary["source_doc_count"],
        "risk_flags": risks,
        "assigned_user": assignment.get("user") or "",
        "assigned_user_label": assignment.get("label") or "",
        "assignment_source": assignment.get("source") or "",
    }


def _plan_item_summary(plan_name: str | None) -> dict:
    if not plan_name:
        return {"item_count": 0, "total_item_count": 0, "source_doc_count": 0}
    rows = frappe.get_all(
        "Forecast Plan Item",
        filters={"parenttype": "Forecast Load Plan", "parent": plan_name},
        fields=["source_doctype", "source_name", "selected"],
        limit_page_length=0,
    )
    source_docs = {
        f"{row.get('source_doctype')}::{row.get('source_name')}"
        for row in rows
        if row.get("source_doctype") and row.get("source_name")
    }
    return {
        "item_count": len([row for row in rows if cint(row.get("selected"))]),
        "total_item_count": len(rows),
        "source_doc_count": len(source_docs),
    }


def _risk_flags(row) -> list[str]:
    risks = []
    status = row.get("status")
    if not row.get("container_profile") and status not in {"Delivered", "Cancelled"}:
        risks.append("Missing container")
    if flt(row.get("weight_utilization_pct")) > 100 or flt(row.get("volume_utilization_pct")) > 100:
        risks.append("Over capacity")
    if row.get("deadline") and status not in {"Delivered", "Cancelled"} and getdate(row.get("deadline")) < getdate(today()):
        risks.append("Overdue")
    return risks


def _build_columns(statuses: list[dict], cards: list[dict]) -> list[dict]:
    columns = []
    for status in statuses:
        columns.append(
            {
                "name": status["name"],
                "label": status.get("label") or status["name"],
                "color": status.get("color") or "Blue",
                "assigned_user": status.get("assigned_user") or "",
                "todo_priority": status.get("todo_priority") or "",
                "auto_collapse": cint(status.get("auto_collapse")),
                "confirmation_message": status.get("confirmation_message") or "",
                "cards": [card for card in cards if card.get("stage") == status["name"]],
            }
        )
    unassigned = [card for card in cards if card.get("stage") == UNASSIGNED_STATUS]
    if unassigned:
        columns.append(
            {
                "name": UNASSIGNED_STATUS,
                "label": _("Unassigned"),
                "color": "Gray",
                "assigned_user": "",
                "todo_priority": "",
                "cards": unassigned,
            }
        )
    return columns


def _status_info(stage: str, company: str | None) -> dict:
    statuses = {
        status["name"]: status
        for status in list_editable_statuses("Forecast Load Plan", include_inactive=False, company=company)
    }
    status_info = statuses.get(stage)
    if not status_info:
        frappe.throw(_("Status {0} is not active for Logistics Pipeline.").format(stage))
    return status_info


def _resolve_pipeline_company(company: str | None = None) -> str:
    company = (company or "").strip()
    payload = get_company_access_payload(requested_company=company if company != "All" else None)
    allowed = payload.get("companies") or []
    if company and company != "All":
        return company
    current_company = payload.get("current_company") or ""
    if current_company:
        return current_company
    frappe.throw(_("No company is available for your user."))


def _allowed_pipeline_companies() -> list[str]:
    return get_company_access_payload().get("companies") or []
