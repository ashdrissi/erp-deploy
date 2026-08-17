from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt


TECHNICAL_LIST_DOCTYPE = "Sales Order Technical List"
REVISION_DOCTYPE = "Sales Order Technical List Revision"
REVISION_ITEM_DOCTYPE = "Sales Order Technical List Item"


def get_effective_demand_rows(
    company: str,
    *,
    warehouses: list[str] | tuple[str, ...] | set[str] | None = None,
    item_codes: list[str] | tuple[str, ...] | set[str] | None = None,
    sales_orders: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[dict]:
    """Return the stock demand source used by dashboards and planning.

    A submitted Sales Order uses its current submitted Technical List revision when one
    exists. Otherwise, it falls back to the submitted Sales Order Item rows.
    """
    company = (company or "").strip()
    if not company:
        return []

    params: dict[str, object] = {"company": company}
    extra = _filters(params, warehouses=warehouses, item_codes=item_codes, sales_orders=sales_orders)
    rows = []
    if _technical_schema_ready():
        rows.extend(_technical_revision_rows(params, extra))
    rows.extend(_sales_order_rows(params, extra, exclude_technical=_technical_schema_ready()))
    return [row for row in rows if flt(row.get("stock_qty")) > 0]


def get_effective_demand_by_item(company: str, **kwargs) -> dict[str, float]:
    result = defaultdict(float)
    for row in get_effective_demand_rows(company, **kwargs):
        result[row["item_code"]] += flt(row.get("stock_qty"))
    return dict(result)


def get_effective_demand_by_item_warehouse(company: str, **kwargs) -> dict[tuple[str, str], float]:
    result = defaultdict(float)
    for row in get_effective_demand_rows(company, **kwargs):
        warehouse = (row.get("warehouse") or "").strip()
        if not warehouse:
            continue
        result[(row["item_code"], warehouse)] += flt(row.get("stock_qty"))
    return dict(result)


def source_key(row) -> str:
    key = (row.get("demand_source_key") or "").strip()
    if key:
        return key
    if (row.get("source_type") or "") == "Technical List":
        return f"TLRI:{row.get('technical_revision_item') or row.get('name') or ''}"
    return f"SOI:{row.get('sales_order_item') or row.get('name') or ''}"


def _filters(params: dict, *, warehouses=None, item_codes=None, sales_orders=None) -> dict[str, str]:
    filters = {"technical": "", "sales_order": ""}
    warehouses = _clean_list(warehouses)
    item_codes = _clean_list(item_codes)
    sales_orders = _clean_list(sales_orders)
    if warehouses:
        params["warehouses"] = tuple(warehouses)
        filters["technical"] += " AND tli.warehouse IN %(warehouses)s"
        filters["sales_order"] += " AND COALESCE(soi.warehouse, so.set_warehouse) IN %(warehouses)s"
    if item_codes:
        params["item_codes"] = tuple(item_codes)
        filters["technical"] += " AND tli.item_code IN %(item_codes)s"
        filters["sales_order"] += " AND soi.item_code IN %(item_codes)s"
    if sales_orders:
        params["sales_orders"] = tuple(sales_orders)
        filters["technical"] += " AND rev.sales_order IN %(sales_orders)s"
        filters["sales_order"] += " AND so.name IN %(sales_orders)s"
    return filters


def _technical_revision_rows(params: dict, filters: dict[str, str]) -> list[dict]:
    return frappe.db.sql(
        f"""
        SELECT
            'Technical List' AS source_type,
            CONCAT('TLRI:', tli.name) AS demand_source_key,
            tl.name AS technical_list,
            rev.name AS technical_revision,
            tli.name AS technical_revision_item,
            rev.company,
            rev.sales_order,
            tli.sales_order_item,
            rev.customer,
            tli.item_code,
            tli.item_name,
            tli.description,
            tli.warehouse,
            tli.uom,
            tli.stock_uom,
            tli.conversion_factor,
            tli.required_date AS delivery_date,
            0 AS delivered_qty,
            GREATEST(
                COALESCE(tli.execution_stock_qty, 0)
                - CASE
                    WHEN tli.sales_order_item IS NOT NULL AND tli.sales_order_item != ''
                    THEN COALESCE(soi.delivered_qty, 0) * COALESCE(soi.conversion_factor, tli.conversion_factor, 1)
                    ELSE 0
                  END,
                0
            ) AS stock_qty,
            GREATEST(
                COALESCE(tli.execution_qty, 0)
                - CASE
                    WHEN tli.sales_order_item IS NOT NULL AND tli.sales_order_item != ''
                    THEN COALESCE(soi.delivered_qty, 0)
                    ELSE 0
                  END,
                0
            ) AS qty,
            so.docstatus
        FROM `tab{REVISION_ITEM_DOCTYPE}` tli
        INNER JOIN `tab{REVISION_DOCTYPE}` rev ON rev.name = tli.parent
        INNER JOIN `tab{TECHNICAL_LIST_DOCTYPE}` tl ON tl.name = rev.technical_list AND tl.current_revision = rev.name
        INNER JOIN `tabSales Order` so ON so.name = rev.sales_order
        LEFT JOIN `tabSales Order Item` soi ON soi.name = tli.sales_order_item
        WHERE rev.company = %(company)s
          AND rev.docstatus = 1
          AND so.docstatus = 1
          AND COALESCE(tli.execution_relevant, 0) = 1
          AND COALESCE(tli.is_stock_item, 0) = 1
          {filters['technical']}
        """,
        params,
        as_dict=True,
    )


def _sales_order_rows(params: dict, filters: dict[str, str], *, exclude_technical: bool) -> list[dict]:
    technical_join = ""
    technical_condition = ""
    if exclude_technical:
        technical_join = f"""
            LEFT JOIN `tab{TECHNICAL_LIST_DOCTYPE}` tl ON tl.sales_order = so.name
            LEFT JOIN `tab{REVISION_DOCTYPE}` rev ON rev.name = tl.current_revision AND rev.docstatus = 1
        """
        technical_condition = "AND rev.name IS NULL"
    return frappe.db.sql(
        f"""
        SELECT
            'Sales Order' AS source_type,
            CONCAT('SOI:', soi.name) AS demand_source_key,
            '' AS technical_list,
            '' AS technical_revision,
            '' AS technical_revision_item,
            so.company,
            so.name AS sales_order,
            soi.name AS sales_order_item,
            so.customer,
            soi.item_code,
            soi.item_name,
            soi.description,
            COALESCE(soi.warehouse, so.set_warehouse) AS warehouse,
            soi.uom,
            soi.stock_uom,
            soi.conversion_factor,
            COALESCE(soi.delivery_date, so.delivery_date) AS delivery_date,
            soi.delivered_qty,
            GREATEST(COALESCE(soi.stock_qty, 0) - COALESCE(soi.delivered_qty, 0) * COALESCE(soi.conversion_factor, 1), 0) AS stock_qty,
            GREATEST(COALESCE(soi.qty, 0) - COALESCE(soi.delivered_qty, 0), 0) AS qty,
            so.docstatus
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        INNER JOIN `tabItem` i ON i.name = soi.item_code
        {technical_join}
        WHERE so.company = %(company)s
          AND so.docstatus = 1
          AND i.is_stock_item = 1
          {technical_condition}
          {filters['sales_order']}
        """,
        params,
        as_dict=True,
    )


def _technical_schema_ready() -> bool:
    return all(frappe.db.exists("DocType", doctype) for doctype in (TECHNICAL_LIST_DOCTYPE, REVISION_DOCTYPE, REVISION_ITEM_DOCTYPE))


def _clean_list(values) -> list[str]:
    if not values:
        return []
    return sorted({str(value).strip() for value in values if str(value or "").strip()})
