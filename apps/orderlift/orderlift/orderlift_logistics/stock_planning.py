from __future__ import annotations

from collections import defaultdict
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from orderlift.orderlift_logistics.doctype.stock_planning_settings.stock_planning_settings import (
    get_company_settings,
)


STATUS_NOT_DUE = "Not Due"
STATUS_PHYSICAL = "Covered by Physical Stock"
STATUS_INCOMING = "Covered by Incoming"
STATUS_WAITING_INCOMING = "Waiting Incoming"
STATUS_BACKUP_DUE = "Backup Check Due"
STATUS_PICK_DUE = "Pick List Due"
STATUS_DRAFT_PICK = "Draft Pick List Created"
STATUS_PARTIAL = "Partially Picked"
STATUS_RESERVED = "Fully Reserved"
STATUS_INCOMING_LATE = "Incoming Late"
STATUS_PROCUREMENT = "Procurement Required"
STATUS_PROCUREMENT_LATE = "Procurement Late"
STATUS_SHORTAGE = "Shortage"
STATUS_REPLAN = "Replan Needed"
STATUS_CANCELLED = "Cancelled"


def validate_sales_order_stock_dates(doc, method=None) -> None:
    """Require delivery dates only when stock planning is enabled for the company."""
    if not doc or cint(doc.get("docstatus")) == 2:
        return
    settings = get_company_settings(doc.get("company"))
    if not settings or not cint(settings.enabled):
        return

    stock_items = _stock_item_codes(row.get("item_code") for row in doc.get("items") or [])
    missing = []
    for row in doc.get("items") or []:
        if row.get("item_code") not in stock_items:
            continue
        if not row.get("delivery_date") and not doc.get("delivery_date"):
            missing.append(_row_label(row))
    if missing:
        frappe.throw(
            _("Delivery Date is required for stock items before confirming the Sales Order: {0}").format(
                ", ".join(missing[:10])
            )
        )


def sync_sales_order_demand_plans(doc, method=None) -> list[str]:
    """Create one system-managed demand plan per submitted stock Sales Order row."""
    if not doc or cint(doc.get("docstatus")) != 1:
        return []
    settings = get_company_settings(doc.get("company"))
    if not settings or not cint(settings.enabled):
        return []

    stock_items = _stock_item_codes(row.get("item_code") for row in doc.get("items") or [])
    names = []
    for row in doc.get("items") or []:
        if row.get("item_code") not in stock_items:
            continue
        delivery_date = row.get("delivery_date") or doc.get("delivery_date")
        if not delivery_date:
            continue
        plan = _get_or_new_plan(row.name)
        _apply_source_values(plan, doc, row, settings)
        plan.flags.ignore_permissions = True
        plan.save(ignore_permissions=True)
        names.append(plan.name)

    _enqueue_company_recalculation(doc.get("company"))
    return names


def cancel_sales_order_demand_plans(doc, method=None) -> None:
    if not doc:
        return
    names = frappe.get_all(
        "Stock Demand Plan",
        filters={"sales_order": doc.name, "source_cancelled": 0},
        pluck="name",
        limit_page_length=0,
    )
    if names:
        frappe.db.set_value(
            "Stock Demand Plan",
            {"name": ["in", names]},
            {
                "source_cancelled": 1,
                "planning_status": STATUS_CANCELLED,
                "next_action_date": None,
                "risk_message": _("Source Sales Order was cancelled."),
                "last_calculated_on": now_datetime(),
            },
            update_modified=False,
        )


def queue_supply_recalculation(doc, method=None) -> None:
    if not doc or not doc.get("company"):
        return
    _enqueue_company_recalculation(doc.get("company"))


def run_scheduled_planning() -> dict:
    companies = frappe.get_all(
        "Stock Planning Settings",
        filters={"enabled": 1},
        pluck="company",
        limit_page_length=0,
    )
    result = {}
    for company in companies:
        try:
            result[company] = recalculate_company(company, process_actions=True)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(
                title=f"Stock planning failed for {company}",
                message=frappe.get_traceback(),
            )
            result[company] = {"error": True}
    return result


@frappe.whitelist()
def recalculate_current_company() -> dict:
    from orderlift.menu_access import resolve_current_company

    company = resolve_current_company(user=frappe.session.user)
    if not company:
        frappe.throw(_("Select an active company first."))
    if not (
        frappe.has_permission("Stock Demand Plan", "read")
        and (frappe.has_permission("Pick List", "create") or frappe.session.user == "Administrator")
    ):
        frappe.throw(_("You are not permitted to run stock planning."), frappe.PermissionError)
    return recalculate_company(company, process_actions=True)


def recalculate_company(company: str, *, process_actions: bool = True) -> dict:
    company = (company or "").strip()
    settings = get_company_settings(company)
    if not settings or not cint(settings.enabled):
        return {"company": company, "enabled": False, "plans": 0, "actions": []}

    _sync_missing_submitted_orders(company, settings)
    plans = _open_plan_docs(company)
    if not plans:
        return {"company": company, "enabled": True, "plans": 0, "actions": []}

    source_rows = _sales_order_rows(plans)
    pick_coverage = _pick_list_coverage(source_rows)
    logistics_dates = _forecast_plan_dates(company)
    incoming_by_item = _incoming_supply(company, logistics_dates)
    stock_by_item = _physical_stock(company, settings)
    today = getdate(nowdate())
    actions = []

    grouped = defaultdict(list)
    for plan in plans:
        source = source_rows.get(plan.sales_order_item)
        if not source or cint(source.get("docstatus")) != 1:
            _mark_cancelled(plan, _("Source Sales Order is no longer submitted."))
            continue
        _refresh_plan_source(plan, source, settings)
        grouped[plan.item_code].append(plan)

    for item_code, item_plans in grouped.items():
        item_plans.sort(key=_demand_priority)
        supply_pool = [dict(row) for row in incoming_by_item.get(item_code, [])]
        physical_pool = flt(stock_by_item.get(item_code, {}).get("available_qty"))

        for plan in item_plans:
            source = source_rows[plan.sales_order_item]
            coverage = pick_coverage.get(plan.sales_order_item, {})
            open_qty = _open_stock_qty(source)
            pick_list_qty = min(flt(coverage.get("pick_list_qty")), open_qty)
            reserved_qty = min(flt(coverage.get("reserved_qty")), open_qty)
            demand_to_plan = max(open_qty - pick_list_qty, 0)

            plan.physical_available_qty = physical_pool
            plan.hard_reserved_qty = flt(stock_by_item.get(item_code, {}).get("reserved_qty"))
            plan.draft_pick_list_qty = flt(coverage.get("draft_qty"))
            plan.pick_list_qty = pick_list_qty
            plan.reserved_qty = reserved_qty
            plan.remaining_qty = demand_to_plan
            plan.latest_pick_list = coverage.get("latest_pick_list") or ""
            plan.set("allocations", [])

            allocations = []
            if cint(plan.rely_on_incoming_stock) and demand_to_plan > 0:
                allocations = _allocate_safe_incoming(plan, demand_to_plan, supply_pool)
            incoming_allocated = sum(flt(row["allocated_qty"]) for row in allocations)
            plan.incoming_allocated_qty = incoming_allocated
            plan.incoming_expected_qty = incoming_allocated
            plan.incoming_date = _latest_allocation_date(allocations)
            plan.incoming_backup_check_date = (
                add_days(plan.incoming_date, -cint(plan.incoming_safety_days))
                if plan.incoming_date
                else None
            )
            for allocation in allocations:
                plan.append("allocations", allocation)

            action_qty, status, next_date, risk = _plan_action(
                plan,
                today=today,
                demand_to_plan=demand_to_plan,
                incoming_allocated=incoming_allocated,
                physical_available=physical_pool,
                reserved_qty=reserved_qty,
                open_qty=open_qty,
            )
            action_need = demand_to_plan if status == STATUS_BACKUP_DUE else max(
                demand_to_plan - incoming_allocated,
                0,
            )
            if action_qty > 0 and not cint(settings.partial_pick_list) and action_qty + 1e-9 < action_need:
                action_qty = 0
                status = STATUS_SHORTAGE
                next_date = today
                risk = _("Full quantity is unavailable and partial Pick Lists are disabled.")

            if action_qty > 0 and process_actions and settings.reservation_mode != "Manual Alert Only":
                created = _create_pick_list_for_plan(
                    plan,
                    source,
                    action_qty,
                    submit=settings.reservation_mode == "Create and Submit Pick List",
                )
                if created:
                    actions.append(created)
                    physical_pool = max(physical_pool - flt(created.get("qty")), 0)
                    plan.latest_pick_list = created["pick_list"]
                    plan.pick_list_qty += flt(created.get("qty"))
                    plan.draft_pick_list_qty += 0 if created.get("submitted") else flt(created.get("qty"))
                    plan.reserved_qty += flt(created.get("qty")) if created.get("submitted") else 0
                    plan.remaining_qty = max(plan.remaining_qty - flt(created.get("qty")), 0)
                    if plan.remaining_qty <= 0 and created.get("submitted"):
                        status = STATUS_RESERVED
                        risk = ""
                        next_date = None
                    elif plan.remaining_qty <= 0:
                        status = STATUS_DRAFT_PICK
                        risk = _("Draft Pick List {0} requires warehouse review and submission.").format(
                            created["pick_list"]
                        )
                        next_date = today
                    else:
                        status = STATUS_PARTIAL
                        risk = _("Pick List covers {0}; {1} remains open.").format(
                            _qty(created.get("qty")), _qty(plan.remaining_qty)
                        )
                        next_date = plan.incoming_date or today
                    allocations = _trim_incoming_allocations(
                        allocations,
                        keep_qty=plan.remaining_qty,
                        supply_pool=supply_pool,
                    )
                    incoming_allocated = sum(flt(row["allocated_qty"]) for row in allocations)
                    plan.set("allocations", [])
                    for allocation in allocations:
                        plan.append("allocations", allocation)
                    plan.incoming_allocated_qty = incoming_allocated
                    plan.incoming_expected_qty = incoming_allocated
                    plan.incoming_date = _latest_allocation_date(allocations)
                    plan.incoming_backup_check_date = (
                        add_days(plan.incoming_date, -cint(plan.incoming_safety_days))
                        if plan.incoming_date
                        else None
                    )
                else:
                    action_qty = 0
                    status = STATUS_SHORTAGE
                    risk = _("Physical stock exists in totals but no valid Pick List location could be created.")
                    next_date = today

            shortage = max(demand_to_plan - incoming_allocated - max(action_qty, 0), 0)
            plan.shortage_qty = shortage
            plan.planning_status = status
            plan.next_action_date = next_date
            plan.risk_message = risk
            plan.last_calculated_on = now_datetime()

            if (
                shortage > 0
                and today >= getdate(plan.stock_protection_date)
                and cint(settings.auto_create_material_request)
            ):
                material_request = _create_material_request_for_plan(
                    plan,
                    source,
                    shortage,
                    submit=cint(settings.auto_submit_material_request),
                )
                if material_request:
                    plan.latest_material_request = material_request["material_request"]
                    actions.append(material_request)

            _notify_actionable_status(plan)
            plan.flags.ignore_permissions = True
            plan.save(ignore_permissions=True)

    return {
        "company": company,
        "enabled": True,
        "plans": len(plans),
        "actions": actions,
    }


def after_migrate() -> None:
    if not frappe.db.exists("DocType", "Stock Planning Settings"):
        return
    for company in frappe.get_all("Company", pluck="name", limit_page_length=0):
        get_company_settings(company, create_default=True)


def _get_or_new_plan(sales_order_item: str):
    name = frappe.db.get_value("Stock Demand Plan", {"sales_order_item": sales_order_item}, "name")
    return frappe.get_doc("Stock Demand Plan", name) if name else frappe.new_doc("Stock Demand Plan")


def _apply_source_values(plan, sales_order, row, settings) -> None:
    item_lead_time = cint(frappe.get_cached_value("Item", row.item_code, "lead_time_days"))
    procurement_delay = item_lead_time or cint(settings.default_procurement_delay_days)
    delivery_date = getdate(row.delivery_date or sales_order.delivery_date)
    plan.update(
        {
            "company": sales_order.company,
            "sales_order": sales_order.name,
            "sales_order_item": row.name,
            "customer": sales_order.customer,
            "item_code": row.item_code,
            "warehouse": row.warehouse or sales_order.set_warehouse,
            "stock_uom": row.stock_uom,
            "required_qty": flt(row.stock_qty) or flt(row.qty) * (flt(row.conversion_factor) or 1),
            "delivery_date": delivery_date,
            "procurement_delay_days": procurement_delay,
            "procurement_safety_days": cint(settings.procurement_safety_days),
            "stock_protection_date": add_days(
                delivery_date,
                -(procurement_delay + cint(settings.procurement_safety_days)),
            ),
            "rely_on_incoming_stock": cint(settings.rely_on_incoming_stock),
            "incoming_safety_days": cint(settings.incoming_safety_days),
            "latest_safe_incoming_date": add_days(delivery_date, -cint(settings.incoming_safety_days)),
            "source_cancelled": 0,
        }
    )


def _refresh_plan_source(plan, source, settings) -> None:
    delivery_date = getdate(source.get("delivery_date") or plan.delivery_date)
    item_lead_time = cint(frappe.get_cached_value("Item", source["item_code"], "lead_time_days"))
    procurement_delay = item_lead_time or cint(settings.default_procurement_delay_days)
    plan.item_code = source["item_code"]
    plan.warehouse = source.get("warehouse") or ""
    plan.stock_uom = source.get("stock_uom") or ""
    plan.required_qty = flt(source.get("stock_qty")) or flt(source.get("qty")) * (
        flt(source.get("conversion_factor")) or 1
    )
    plan.delivery_date = delivery_date
    plan.procurement_delay_days = procurement_delay
    plan.procurement_safety_days = cint(settings.procurement_safety_days)
    plan.stock_protection_date = add_days(
        delivery_date,
        -(procurement_delay + cint(settings.procurement_safety_days)),
    )
    plan.rely_on_incoming_stock = cint(settings.rely_on_incoming_stock)
    plan.incoming_safety_days = cint(settings.incoming_safety_days)
    plan.latest_safe_incoming_date = add_days(delivery_date, -cint(settings.incoming_safety_days))


def _sync_missing_submitted_orders(company: str, settings) -> None:
    rows = frappe.db.sql(
        """
        SELECT soi.name, soi.parent, soi.item_code, soi.qty, soi.stock_qty, soi.stock_uom,
               soi.conversion_factor, soi.delivery_date, soi.warehouse,
               so.customer, so.delivery_date AS parent_delivery_date, so.set_warehouse
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        INNER JOIN `tabItem` i ON i.name = soi.item_code
        LEFT JOIN `tabStock Demand Plan` sdp ON sdp.sales_order_item = soi.name
        WHERE so.company = %(company)s
          AND so.docstatus = 1
          AND i.is_stock_item = 1
          AND sdp.name IS NULL
        """,
        {"company": company},
        as_dict=True,
    )
    for row in rows:
        delivery_date = row.delivery_date or row.parent_delivery_date
        if not delivery_date:
            continue
        plan = frappe.new_doc("Stock Demand Plan")
        lead_time = cint(frappe.get_cached_value("Item", row.item_code, "lead_time_days"))
        delay = lead_time or cint(settings.default_procurement_delay_days)
        plan.update(
            {
                "company": company,
                "sales_order": row.parent,
                "sales_order_item": row.name,
                "customer": row.customer,
                "item_code": row.item_code,
                "warehouse": row.warehouse or row.set_warehouse,
                "stock_uom": row.stock_uom,
                "required_qty": flt(row.stock_qty) or flt(row.qty) * (flt(row.conversion_factor) or 1),
                "delivery_date": delivery_date,
                "procurement_delay_days": delay,
                "procurement_safety_days": cint(settings.procurement_safety_days),
                "stock_protection_date": add_days(
                    delivery_date,
                    -(delay + cint(settings.procurement_safety_days)),
                ),
                "rely_on_incoming_stock": cint(settings.rely_on_incoming_stock),
                "incoming_safety_days": cint(settings.incoming_safety_days),
                "latest_safe_incoming_date": add_days(delivery_date, -cint(settings.incoming_safety_days)),
                "planning_status": STATUS_NOT_DUE,
            }
        )
        plan.insert(ignore_permissions=True)


def _open_plan_docs(company: str) -> list:
    names = frappe.get_all(
        "Stock Demand Plan",
        filters={"company": company, "source_cancelled": 0},
        pluck="name",
        order_by="delivery_date asc, creation asc",
        limit_page_length=0,
    )
    return [frappe.get_doc("Stock Demand Plan", name) for name in names]


def _sales_order_rows(plans: list) -> dict:
    names = [plan.sales_order_item for plan in plans if plan.sales_order_item]
    if not names:
        return {}
    rows = frappe.db.sql(
        """
        SELECT soi.name, soi.parent, soi.item_code, soi.qty, soi.stock_qty, soi.delivered_qty,
               soi.stock_uom, soi.uom, soi.conversion_factor, soi.delivery_date, soi.warehouse,
               soi.description, soi.item_name, so.docstatus, so.customer, so.company,
               so.delivery_date AS parent_delivery_date, so.set_warehouse
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.name IN %(names)s
        """,
        {"names": tuple(names)},
        as_dict=True,
    )
    for row in rows:
        row.delivery_date = row.delivery_date or row.parent_delivery_date
        row.warehouse = row.warehouse or row.set_warehouse
    return {row.name: row for row in rows}


def _pick_list_coverage(source_rows: dict) -> dict:
    if not source_rows:
        return {}
    rows = frappe.db.sql(
        """
        SELECT pli.sales_order_item,
               SUM(CASE WHEN pl.docstatus < 2 THEN COALESCE(pli.stock_qty, 0) ELSE 0 END) AS pick_list_qty,
               SUM(CASE WHEN pl.docstatus = 0 THEN COALESCE(pli.stock_qty, 0) ELSE 0 END) AS draft_qty,
               SUM(CASE WHEN pl.docstatus = 1 THEN COALESCE(pli.stock_reserved_qty, 0) ELSE 0 END) AS reserved_qty
        FROM `tabPick List Item` pli
        INNER JOIN `tabPick List` pl ON pl.name = pli.parent
        WHERE pli.sales_order_item IN %(items)s
          AND pl.purpose = 'Delivery'
          AND pl.docstatus < 2
        GROUP BY pli.sales_order_item
        """,
        {"items": tuple(source_rows)},
        as_dict=True,
    )
    result = {row.sales_order_item: dict(row) for row in rows}
    latest = frappe.db.sql(
        """
        SELECT pli.sales_order_item, pl.name
        FROM `tabPick List Item` pli
        INNER JOIN `tabPick List` pl ON pl.name = pli.parent
        WHERE pli.sales_order_item IN %(items)s AND pl.docstatus < 2
        ORDER BY pl.creation DESC
        """,
        {"items": tuple(source_rows)},
        as_dict=True,
    )
    for row in latest:
        result.setdefault(row.sales_order_item, {})
        result[row.sales_order_item].setdefault("latest_pick_list", row.name)
    return result


def _physical_stock(company: str, settings) -> dict:
    rows = frappe.db.sql(
        """
        SELECT b.item_code,
               SUM(GREATEST(COALESCE(b.actual_qty, 0) - COALESCE(b.reserved_stock, 0), 0)) AS available_qty,
               SUM(COALESCE(b.reserved_stock, 0)) AS reserved_qty,
               SUM(COALESCE(ir.warehouse_reorder_level, 0)) AS reorder_floor
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        LEFT JOIN `tabItem Reorder` ir ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
        WHERE w.company = %(company)s
          AND COALESCE(w.disabled, 0) = 0
          AND COALESCE(w.is_group, 0) = 0
        GROUP BY b.item_code
        """,
        {"company": company},
        as_dict=True,
    )
    draft_rows = frappe.db.sql(
        """
        SELECT pli.item_code, SUM(COALESCE(pli.stock_qty, 0)) AS draft_qty
        FROM `tabPick List Item` pli
        INNER JOIN `tabPick List` pl ON pl.name = pli.parent
        WHERE pl.company = %(company)s AND pl.docstatus = 0 AND pl.purpose = 'Delivery'
        GROUP BY pli.item_code
        """,
        {"company": company},
        as_dict=True,
    )
    draft_by_item = {row.item_code: flt(row.draft_qty) for row in draft_rows}
    result = {}
    for row in rows:
        available = max(flt(row.available_qty) - draft_by_item.get(row.item_code, 0), 0)
        if settings.protected_stock_floor_mode == "Item Reorder Level":
            available = max(available - flt(row.reorder_floor), 0)
        result[row.item_code] = {
            "available_qty": available,
            "reserved_qty": flt(row.reserved_qty),
        }
    return result


def _incoming_supply(company: str, logistics_dates: dict) -> dict:
    rows = frappe.db.sql(
        """
        SELECT poi.name, poi.parent, poi.item_code, poi.stock_qty, poi.received_qty,
               poi.conversion_factor, poi.schedule_date, po.schedule_date AS parent_schedule_date
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
        WHERE po.company = %(company)s
          AND po.docstatus = 1
          AND po.status NOT IN ('Closed', 'Completed', 'Cancelled')
        ORDER BY COALESCE(poi.schedule_date, po.schedule_date) ASC, po.creation ASC, poi.idx ASC
        """,
        {"company": company},
        as_dict=True,
    )
    result = defaultdict(list)
    for row in rows:
        pending = max(
            flt(row.stock_qty) - flt(row.received_qty) * (flt(row.conversion_factor) or 1),
            0,
        )
        if pending <= 0:
            continue
        logistics = logistics_dates.get(row.parent) or {}
        expected_date = logistics.get("expected_date") or row.schedule_date or row.parent_schedule_date
        if not expected_date:
            continue
        result[row.item_code].append(
            {
                "purchase_order": row.parent,
                "purchase_order_item": row.name,
                "forecast_load_plan": logistics.get("forecast_load_plan") or "",
                "available_qty": pending,
                "expected_date": getdate(expected_date),
                "status": logistics.get("status") or "Submitted Purchase Order",
            }
        )
    return result


def _forecast_plan_dates(company: str) -> dict:
    if not frappe.db.exists("DocType", "Forecast Load Plan"):
        return {}
    rows = frappe.db.sql(
        """
        SELECT fpi.source_name AS purchase_order, flp.name, flp.deadline, flp.status, flp.modified
        FROM `tabForecast Plan Item` fpi
        INNER JOIN `tabForecast Load Plan` flp ON flp.name = fpi.parent
        WHERE fpi.source_doctype = 'Purchase Order'
          AND flp.company = %(company)s
          AND flp.flow_scope = 'Inbound'
          AND flp.status != 'Cancelled'
          AND flp.deadline IS NOT NULL
        ORDER BY flp.modified DESC
        """,
        {"company": company},
        as_dict=True,
    )
    result = {}
    for row in rows:
        result.setdefault(
            row.purchase_order,
            {
                "forecast_load_plan": row.name,
                "expected_date": row.deadline,
                "status": row.status,
            },
        )
    return result


def _allocate_safe_incoming(plan, demand_qty: float, supply_pool: list[dict]) -> list[dict]:
    remaining = flt(demand_qty)
    allocations = []
    safe_date = getdate(plan.latest_safe_incoming_date)
    for supply in supply_pool:
        if remaining <= 0:
            break
        if flt(supply.get("available_qty")) <= 0:
            continue
        if getdate(supply["expected_date"]) > safe_date:
            continue
        allocated = min(remaining, flt(supply["available_qty"]))
        if allocated <= 0:
            continue
        supply["available_qty"] = flt(supply["available_qty"]) - allocated
        remaining -= allocated
        allocations.append(
            {
                "purchase_order": supply["purchase_order"],
                "purchase_order_item": supply["purchase_order_item"],
                "forecast_load_plan": supply.get("forecast_load_plan") or "",
                "allocated_qty": allocated,
                "expected_date": supply["expected_date"],
                "status": supply.get("status") or "Expected",
            }
        )
    return allocations


def _trim_incoming_allocations(
    allocations: list[dict],
    *,
    keep_qty: float,
    supply_pool: list[dict],
) -> list[dict]:
    remaining = max(flt(keep_qty), 0)
    kept = []
    supply_by_item = {row["purchase_order_item"]: row for row in supply_pool}
    for allocation in allocations:
        allocated = flt(allocation.get("allocated_qty"))
        keep = min(allocated, remaining)
        release = allocated - keep
        if release > 0:
            supply = supply_by_item.get(allocation.get("purchase_order_item"))
            if supply:
                supply["available_qty"] = flt(supply.get("available_qty")) + release
        if keep > 0:
            row = dict(allocation)
            row["allocated_qty"] = keep
            kept.append(row)
            remaining -= keep
    return kept


def _plan_action(
    plan,
    *,
    today: date,
    demand_to_plan: float,
    incoming_allocated: float,
    physical_available: float,
    reserved_qty: float,
    open_qty: float,
) -> tuple[float, str, date | None, str]:
    if open_qty <= 0:
        return 0, STATUS_RESERVED, None, ""
    if reserved_qty >= open_qty:
        return 0, STATUS_RESERVED, None, ""
    if demand_to_plan <= 0:
        return 0, STATUS_DRAFT_PICK, today, _("Pick List requires submission or completion.")

    protection_date = getdate(plan.stock_protection_date)
    incoming_covers = incoming_allocated + 1e-9 >= demand_to_plan
    backup_date = getdate(plan.incoming_backup_check_date) if plan.incoming_backup_check_date else None

    if today < protection_date:
        if incoming_covers:
            return 0, STATUS_INCOMING, min(protection_date, backup_date or protection_date), ""
        if physical_available + 1e-9 >= demand_to_plan:
            return 0, STATUS_PHYSICAL, protection_date, ""
        return 0, STATUS_NOT_DUE, protection_date, _(
            "Confirmed demand is not covered yet; procurement check is scheduled for the stock protection date."
        )

    if incoming_covers and backup_date and today < backup_date:
        return 0, STATUS_WAITING_INCOMING, backup_date, _(
            "Incoming quantity is allocated. Backup stock check is scheduled for {0}."
        ).format(backup_date)

    if incoming_covers and backup_date and today >= backup_date:
        qty = min(demand_to_plan, physical_available)
        if qty > 0:
            return qty, STATUS_BACKUP_DUE, today, _(
                "Incoming has not been received by its safety date; protect available physical stock."
            )
        return 0, STATUS_WAITING_INCOMING, plan.incoming_date, _(
            "Incoming has not been received and no physical backup stock is available."
        )

    uncovered = max(demand_to_plan - incoming_allocated, 0)
    qty = min(uncovered, physical_available)
    if qty > 0:
        return qty, STATUS_PICK_DUE, today, ""
    if incoming_allocated > 0:
        return 0, STATUS_INCOMING_LATE, plan.incoming_date, _(
            "Only part of the demand is covered by safe incoming stock."
        )
    status = STATUS_PROCUREMENT if today == protection_date else STATUS_PROCUREMENT_LATE
    return 0, status, today, _(
        "No physical or safely dated incoming stock covers this confirmed demand."
    )


def _create_pick_list_for_plan(plan, source, stock_qty: float, *, submit: bool) -> dict | None:
    stock_qty = flt(stock_qty)
    if stock_qty <= 0:
        return None
    conversion_factor = flt(source.get("conversion_factor")) or 1
    pick_list = frappe.new_doc("Pick List")
    pick_list.company = plan.company
    pick_list.purpose = "Delivery"
    pick_list.customer = source.get("customer") or plan.customer
    pick_list.parent_warehouse = ""
    pick_list.append(
        "locations",
        {
            "item_code": plan.item_code,
            "item_name": source.get("item_name"),
            "description": source.get("description"),
            "qty": stock_qty / conversion_factor,
            "stock_qty": stock_qty,
            "uom": source.get("uom") or plan.stock_uom,
            "stock_uom": plan.stock_uom,
            "conversion_factor": conversion_factor,
            "warehouse": source.get("warehouse"),
            "sales_order": plan.sales_order,
            "sales_order_item": plan.sales_order_item,
        },
    )
    pick_list.set_item_locations()
    _cap_pick_list_qty(pick_list, plan.sales_order_item, stock_qty)
    if not pick_list.locations:
        return None
    actual_qty = sum(flt(row.stock_qty) for row in pick_list.locations)
    if actual_qty <= 0:
        return None
    pick_list.insert(ignore_permissions=True)
    if submit:
        pick_list.submit()
    return {
        "type": "Pick List",
        "pick_list": pick_list.name,
        "qty": actual_qty,
        "submitted": cint(pick_list.docstatus) == 1,
    }


def _cap_pick_list_qty(pick_list, sales_order_item: str, target_stock_qty: float) -> None:
    remaining = flt(target_stock_qty)
    kept = []
    for row in pick_list.locations:
        if row.sales_order_item != sales_order_item or remaining <= 0:
            continue
        row_qty = min(flt(row.stock_qty), remaining)
        if row_qty <= 0:
            continue
        row.stock_qty = row_qty
        row.qty = row_qty / (flt(row.conversion_factor) or 1)
        if flt(row.picked_qty) > row_qty:
            row.picked_qty = row_qty
        remaining -= row_qty
        kept.append(row)
    pick_list.set("locations", kept)


def _create_material_request_for_plan(plan, source, stock_qty: float, *, submit: bool) -> dict | None:
    existing = frappe.db.get_value(
        "Material Request Item",
        {
            "sales_order_item": plan.sales_order_item,
            "docstatus": ["<", 2],
        },
        "parent",
    )
    if existing:
        return None
    conversion_factor = flt(source.get("conversion_factor")) or 1
    material_request = frappe.new_doc("Material Request")
    material_request.company = plan.company
    material_request.material_request_type = "Purchase"
    material_request.transaction_date = nowdate()
    material_request.schedule_date = plan.delivery_date
    material_request.append(
        "items",
        {
            "item_code": plan.item_code,
            "qty": flt(stock_qty) / conversion_factor,
            "uom": source.get("uom") or plan.stock_uom,
            "stock_uom": plan.stock_uom,
            "conversion_factor": conversion_factor,
            "schedule_date": plan.delivery_date,
            "warehouse": source.get("warehouse"),
            "sales_order": plan.sales_order,
            "sales_order_item": plan.sales_order_item,
        },
    )
    material_request.insert(ignore_permissions=True)
    if submit:
        material_request.submit()
    return {
        "type": "Material Request",
        "material_request": material_request.name,
        "qty": flt(stock_qty),
        "submitted": cint(material_request.docstatus) == 1,
    }


def _stock_item_codes(item_codes) -> set[str]:
    item_codes = sorted({(item_code or "").strip() for item_code in item_codes if (item_code or "").strip()})
    if not item_codes:
        return set()
    return set(
        frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes], "is_stock_item": 1},
            pluck="name",
            limit_page_length=0,
        )
    )


def _open_stock_qty(source) -> float:
    conversion_factor = flt(source.get("conversion_factor")) or 1
    return max((flt(source.get("qty")) - flt(source.get("delivered_qty"))) * conversion_factor, 0)


def _demand_priority(plan) -> tuple:
    return (
        getdate(plan.delivery_date) if plan.delivery_date else date.max,
        plan.creation or "",
        plan.name or "",
    )


def _latest_allocation_date(allocations: list[dict]):
    dates = [getdate(row["expected_date"]) for row in allocations if row.get("expected_date")]
    return max(dates) if dates else None


def _mark_cancelled(plan, message: str) -> None:
    plan.source_cancelled = 1
    plan.planning_status = STATUS_CANCELLED
    plan.next_action_date = None
    plan.risk_message = message
    plan.last_calculated_on = now_datetime()
    plan.save(ignore_permissions=True)


def _notify_actionable_status(plan) -> None:
    actionable = {
        STATUS_BACKUP_DUE,
        STATUS_PICK_DUE,
        STATUS_PARTIAL,
        STATUS_INCOMING_LATE,
        STATUS_PROCUREMENT,
        STATUS_PROCUREMENT_LATE,
        STATUS_SHORTAGE,
        STATUS_REPLAN,
    }
    if plan.planning_status not in actionable or plan.last_alert_status == plan.planning_status:
        return
    recipients = _planning_alert_recipients(plan.company, plan.planning_status)
    if not recipients:
        return
    subject = _("Stock Planning {0}: {1}").format(plan.planning_status, plan.item_code)
    for user in recipients:
        frappe.get_doc(
            {
                "doctype": "Notification Log",
                "subject": subject,
                "for_user": user,
                "type": "Alert",
                "document_type": "Stock Demand Plan",
                "document_name": plan.name,
                "email_content": plan.risk_message or "",
            }
        ).insert(ignore_permissions=True)
    plan.last_alert_status = plan.planning_status
    plan.last_alert_on = now_datetime()


def _planning_alert_recipients(company: str, status: str) -> list[str]:
    from orderlift.menu_access import user_can_access_company
    from orderlift.role_capabilities import (
        CAPABILITY_PURCHASING_ACCESS,
        CAPABILITY_STOCK_RESERVATION_MANAGEMENT,
        user_has_capability,
    )

    purchasing_statuses = {STATUS_PROCUREMENT, STATUS_PROCUREMENT_LATE, STATUS_INCOMING_LATE}
    capability = (
        CAPABILITY_PURCHASING_ACCESS
        if status in purchasing_statuses
        else CAPABILITY_STOCK_RESERVATION_MANAGEMENT
    )
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        pluck="name",
        limit_page_length=0,
    )
    return sorted(
        user
        for user in users
        if user != "Administrator"
        and user_has_capability(capability, user=user)
        and user_can_access_company(company, user=user)
    )


def _enqueue_company_recalculation(company: str) -> None:
    if not company:
        return
    frappe.enqueue(
        "orderlift.orderlift_logistics.stock_planning.recalculate_company",
        queue="short",
        enqueue_after_commit=True,
        job_name=f"stock-planning-{company}",
        company=company,
        process_actions=True,
    )


def _row_label(row) -> str:
    return _("Row #{0} {1}").format(row.get("idx") or "-", row.get("item_code") or "")


def _qty(value) -> str:
    value = flt(value)
    return str(int(value)) if value.is_integer() else f"{value:.2f}"
