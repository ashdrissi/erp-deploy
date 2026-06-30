from __future__ import annotations

import base64
import hashlib
import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import flt, formatdate, nowdate

from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import STATIC_MODE, build_static_context
from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import get_latest_item_prices
from orderlift.orderlift_sales.utils.tax_inclusive import build_catalogue_ttc_price_map, company_default_sales_taxes_template
from orderlift.orderlift_sales.utils.price_list_scope import current_company, get_price_lists, get_visible_price_lists, validate_price_list_scope
from orderlift.startup_roles import RESTRICTED_COMMERCIAL_ROLES, STOCK_QUANTITY_VIEWER_ROLE
from orderlift.warehouse_access import stock_warehouse_condition


BASE_COLUMN_LABELS = {
    "_row_number": "N°",
    "item_code": "CODE",
    "image": "Image",
    "item_category": "Catégorie d'article",
    "item_group": "Groupe d'item",
    "item_name": "Nom d'Item",
    "brand": "Marque",
    "uom": "UOM",
    "stock_qty": "Qté Stock Totale",
    "stock_available": "Disponibilité Stock",
}
DEFAULT_PDF_COLUMNS = [
    "_row_number",
    "item_code",
    "image",
    "item_category",
    "item_group",
    "item_name",
    "brand",
    "uom",
]
PDF_IMAGE_TIMEOUT_SECONDS = 5
PDF_IMAGE_MAX_BYTES = 512 * 1024
PDF_IMAGE_HEADERS = {"User-Agent": "Mozilla/5.0"}
PDF_IMAGE_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
PDF_IMAGE_NEGATIVE_CACHE_TTL_SECONDS = 60 * 60
PDF_IMAGE_CACHE_MISS = "__orderlift_pdf_image_miss__"
PRIVILEGED_CATALOGUE_ROLES = {"Orderlift Admin", "Orderlift Business Admin", "Pricing Manager", "Sales Manager", "System Manager"}
RESTRICTED_AGENT_ROLES = RESTRICTED_COMMERCIAL_ROLES


@frappe.whitelist()
def get_catalogue_bootstrap():
    company = current_company()
    agent_context = _current_agent_catalogue_context(company)
    return {
        "current_company": company,
        "price_lists": _selling_price_lists(company, agent_context=agent_context),
        "benchmark_price_lists": _benchmark_price_lists(company),
        "restricted_agent": agent_context.get("restricted_agent", False),
        "hide_stock_qty": agent_context.get("hide_stock_qty", False),
        "agent_sales_person": agent_context.get("sales_person") or "",
        "item_groups": _link_options("Item Group"),
        "item_categories": _item_category_options(),
        "brands": _brand_options(company=company, agent_context=agent_context),
        "uoms": _link_options("UOM"),
    }


@frappe.whitelist()
def get_catalogue_rows(price_lists=None, benchmark_price_lists=None, filters=None):
    selected_price_lists = _validate_selling_price_lists(_clean_list(_parse_json(price_lists, [])))
    selected_benchmark_price_lists = _validate_benchmark_price_lists(_clean_list(_parse_json(benchmark_price_lists, [])))
    if not selected_price_lists:
        frappe.throw(_("Select at least one Selling Price List."))

    filters = _parse_json(filters, {}) or {}
    company = current_company()
    agent_context = _current_agent_catalogue_context(company)
    require_price_lists = selected_price_lists if agent_context.get("restricted_agent") else None
    item_rows = _query_items(filters, require_price_lists=require_price_lists, brand_price_lists=selected_price_lists)
    item_codes = [row.item_code for row in item_rows]
    if not item_codes:
        return _empty_payload(selected_price_lists, hide_stock_qty=agent_context.get("hide_stock_qty"))

    stock_map = _stock_qty_map(item_codes)
    price_maps = {
        price_list: get_latest_item_prices(item_codes, price_list, buying=False)
        for price_list in selected_price_lists
    }
    benchmark_maps = {
        price_list: get_latest_item_prices(item_codes, price_list, buying=None)
        for price_list in selected_benchmark_price_lists
    }
    brand_map = _item_price_brand_map(item_codes, selected_price_lists)
    price_list_meta = _price_list_meta(selected_price_lists)
    benchmark_price_list_meta = _price_list_meta(selected_benchmark_price_lists)
    primary_price_list = selected_price_lists[0] if selected_price_lists else ""
    ttc_maps = {
        price_list: build_catalogue_ttc_price_map(price_maps.get(price_list, {}), company)
        for price_list in selected_price_lists
    }
    company_tax_template = company_default_sales_taxes_template(company)
    show_missing_prices = _truthy(filters.get("show_missing_prices"), default=True)
    in_stock_only = False if agent_context.get("restricted_agent") else _truthy(filters.get("in_stock_only"), default=False)

    rows = []
    for row in item_rows:
        stock_qty = flt(stock_map.get(row.item_code) or 0)
        if in_stock_only and stock_qty <= 0:
            continue

        prices = {}
        ttc_prices = {}
        benchmark_prices = {}
        has_price = False
        for price_list in selected_price_lists:
            value = price_maps.get(price_list, {}).get(row.item_code)
            if value is None:
                prices[price_list] = None
                ttc_prices[price_list] = None
                continue
            prices[price_list] = flt(value)
            ttc_prices[price_list] = flt(ttc_maps.get(price_list, {}).get(row.item_code) or 0) if row.item_code in ttc_maps.get(price_list, {}) else None
            has_price = True
        for price_list in selected_benchmark_price_lists:
            value = benchmark_maps.get(price_list, {}).get(row.item_code)
            benchmark_prices[price_list] = None if value is None else flt(value)
        if agent_context.get("restricted_agent") and not has_price:
            continue
        if not show_missing_prices and not has_price:
            continue

        payload_row = {
            "item_code": row.item_code,
            "image": row.image or "",
            "item_category": row.item_category or "",
            "item_group": row.item_group or "",
            "item_name": row.item_name or row.item_code,
            "brand": brand_map.get(row.item_code) or row.brand or "",
            "uom": row.uom or "",
            "prices": prices,
            "ttc_prices": ttc_prices,
            "default_ttc_price": flt(ttc_prices.get(primary_price_list) or 0) if primary_price_list and ttc_prices.get(primary_price_list) is not None else None,
            "benchmark_prices": benchmark_prices,
            "stock_available": "OUI" if stock_qty > 0 else "NON",
        }
        if not agent_context.get("hide_stock_qty"):
            payload_row["stock_qty"] = stock_qty
        rows.append(payload_row)

    return {
        "price_lists": [price_list_meta.get(price_list) or {"name": price_list, "currency": ""} for price_list in selected_price_lists],
        "benchmark_price_lists": [benchmark_price_list_meta.get(price_list) or {"name": price_list, "currency": ""} for price_list in selected_benchmark_price_lists],
        "default_ttc_price_list": primary_price_list,
        "default_tax_template": company_tax_template,
        "rows": rows,
        "kpis": {
            "items": len(rows),
            "price_lists": len(selected_price_lists),
            "in_stock": sum(
                1
                for row in rows
                if (row.get("stock_available") == "OUI" if agent_context.get("hide_stock_qty") else flt(row.get("stock_qty")) > 0)
            ),
            "missing_price_rows": sum(1 for row in rows if not any(value is not None for value in (row.get("prices") or {}).values())),
            "hide_stock_qty": 1 if agent_context.get("hide_stock_qty") else 0,
        },
    }


@frappe.whitelist()
def download_catalogue_pdf(price_lists=None, benchmark_price_lists=None, filters=None, columns=None, table_search="", column_filters=None, item_codes=None):
    selected_price_lists = _validate_selling_price_lists(_clean_list(_parse_json(price_lists, [])))
    selected_benchmark_price_lists = _validate_benchmark_price_lists(_clean_list(_parse_json(benchmark_price_lists, [])))
    if not selected_price_lists:
        frappe.throw(_("Select at least one Selling Price List."))
    filters = _parse_json(filters, {}) or {}
    columns = _clean_list(_parse_json(columns, []))
    if _current_agent_catalogue_context(current_company()).get("hide_stock_qty"):
        filters["in_stock_only"] = False
        columns = [column for column in columns if column != "stock_qty"]
    column_filters = _parse_json(column_filters, {}) or {}
    item_codes = _clean_list(_parse_json(item_codes, []))
    payload = get_catalogue_rows(selected_price_lists, selected_benchmark_price_lists, filters)
    payload["rows"] = _filter_payload_rows(payload.get("rows") or [], table_search, column_filters)
    if item_codes:
        payload["rows"] = _filter_payload_item_codes(payload.get("rows") or [], item_codes)
    html = _render_pdf_html(payload, filters, columns)

    from frappe.utils.pdf import get_pdf

    frappe.local.response.filename = f"catalogue-prix-articles-{nowdate()}.pdf"
    frappe.local.response.filecontent = get_pdf(html, options=_pdf_options())
    frappe.local.response.type = "download"


def _pdf_options():
    return {
        "page-size": "A4",
        "orientation": "Landscape",
        "margin-top": "8mm",
        "margin-right": "8mm",
        "margin-bottom": "8mm",
        "margin-left": "8mm",
        "zoom": "0.72",
        "load-error-handling": "ignore",
        "load-media-error-handling": "ignore",
    }


def _empty_payload(price_lists, benchmark_price_lists=None, hide_stock_qty=False):
    price_list_meta = _price_list_meta(price_lists)
    benchmark_price_list_meta = _price_list_meta(benchmark_price_lists or [])
    return {
        "price_lists": [price_list_meta.get(price_list) or {"name": price_list, "currency": ""} for price_list in price_lists],
        "benchmark_price_lists": [benchmark_price_list_meta.get(price_list) or {"name": price_list, "currency": ""} for price_list in (benchmark_price_lists or [])],
        "default_ttc_price_list": price_lists[0] if price_lists else "",
        "default_tax_template": company_default_sales_taxes_template(current_company()) if price_lists else "",
        "rows": [],
        "kpis": {
            "items": 0,
            "price_lists": len(price_lists),
            "in_stock": 0,
            "missing_price_rows": 0,
            "hide_stock_qty": 1 if hide_stock_qty else 0,
        },
    }


def _selling_price_lists(company, agent_context=None):
    visible = set(get_visible_price_lists("selling", company=company))
    rows = [row for row in get_price_lists("selling", fields=["name", "currency"], company=company) if row.name in visible]
    default_currency = frappe.defaults.get_global_default("currency")
    return [{"name": row.name, "currency": row.currency or default_currency} for row in rows]


def _benchmark_price_lists(company):
    visible = set(get_visible_price_lists("benchmark", company=company))
    rows = [row for row in get_price_lists("benchmark", fields=["name", "currency"], company=company) if row.name in visible]
    default_currency = frappe.defaults.get_global_default("currency")
    return [{"name": row.name, "currency": row.currency or default_currency} for row in rows]


def _validate_selling_price_lists(price_lists):
    allowed = set(get_visible_price_lists("selling", current_company()))
    out = []
    for price_list in price_lists:
        resolved = validate_price_list_scope(price_list, kind="selling", required=True)
        if resolved not in allowed:
            frappe.throw(
                _("Selling Price List {0} is not visible to current user {1}.").format(
                    resolved,
                    frappe.session.user or "-",
                )
            )
        out.append(resolved)
    return out


def _validate_benchmark_price_lists(price_lists):
    allowed = set(get_visible_price_lists("benchmark", current_company()))
    out = []
    for price_list in price_lists:
        resolved = validate_price_list_scope(price_list, kind="benchmark", required=True)
        if resolved not in allowed:
            frappe.throw(
                _("Benchmark Price List {0} is not visible to current user {1}.").format(
                    resolved,
                    frappe.session.user or "-",
                )
            )
        out.append(resolved)
    return out


def _query_items(filters, require_price_lists=None, brand_price_lists=None):
    has_item_brand = _has_column("Item", "brand")
    has_item_price_brand = _has_column("Item Price", "brand")
    brand_price_lists = _clean_list(brand_price_lists or [])
    fields = [
        "i.name AS item_code",
        "i.item_name",
        "i.item_group",
        "i.image",
        "i.stock_uom AS uom",
    ]
    if has_item_brand:
        fields.append("i.brand")
    else:
        fields.append("'' AS brand")
    if _has_column("Item", "custom_item_category"):
        fields.append("i.custom_item_category AS item_category")
    else:
        fields.append("'' AS item_category")

    conditions = []
    params = {}
    if _has_column("Item", "disabled"):
        conditions.append("ifnull(i.disabled, 0) = 0")

    search = (filters.get("search") or "").strip()
    if search:
        params["search"] = f"%{search}%"
        search_terms = ["i.name LIKE %(search)s", "i.item_name LIKE %(search)s", "i.item_group LIKE %(search)s"]
        if has_item_brand:
            search_terms.append("i.brand LIKE %(search)s")
        if has_item_price_brand and brand_price_lists:
            search_terms.append(
                "EXISTS ("
                "SELECT 1 FROM `tabItem Price` ip "
                "WHERE ip.item_code = i.name "
                "AND ip.price_list IN %(brand_price_lists)s "
                "AND ip.brand LIKE %(search)s"
                ")"
            )
            params["brand_price_lists"] = tuple(brand_price_lists)
        if _has_column("Item", "custom_item_category"):
            search_terms.append("i.custom_item_category LIKE %(search)s")
        conditions.append("(" + " OR ".join(search_terms) + ")")

    item_group = (filters.get("item_group") or "").strip()
    if item_group:
        conditions.append("i.item_group = %(item_group)s")
        params["item_group"] = item_group

    item_category = (filters.get("item_category") or "").strip()
    if item_category and _has_column("Item", "custom_item_category"):
        conditions.append("i.custom_item_category = %(item_category)s")
        params["item_category"] = item_category

    brand = (filters.get("brand") or "").strip()
    if brand:
        params["brand"] = brand
        brand_terms = []
        if has_item_brand:
            brand_terms.append("i.brand = %(brand)s")
        if has_item_price_brand and brand_price_lists:
            brand_terms.append(
                "EXISTS ("
                "SELECT 1 FROM `tabItem Price` ip "
                "WHERE ip.item_code = i.name "
                "AND ip.price_list IN %(brand_price_lists)s "
                "AND ip.brand = %(brand)s"
                ")"
            )
            params["brand_price_lists"] = tuple(brand_price_lists)
        conditions.append("(" + " OR ".join(brand_terms) + ")" if brand_terms else "1 = 0")

    uom = (filters.get("uom") or "").strip()
    if uom:
        conditions.append("i.stock_uom = %(uom)s")
        params["uom"] = uom

    require_price_lists = _clean_list(require_price_lists or [])
    if require_price_lists:
        conditions.append(
            "EXISTS ("
            "SELECT 1 FROM `tabItem Price` ip "
            "WHERE ip.item_code = i.name "
            "AND ip.price_list IN %(required_price_lists)s "
            "AND ifnull(ip.buying, 0) = 0"
            ")"
        )
        params["required_price_lists"] = tuple(require_price_lists)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return frappe.db.sql(
        f"""
        SELECT {', '.join(fields)}
        FROM `tabItem` i
        {where_sql}
        ORDER BY i.item_group ASC, i.name ASC
        """,
        params,
        as_dict=True,
    )


def _current_agent_catalogue_context(company=None):
    if not _is_restricted_agent_user():
        return {"restricted_agent": False, "hide_stock_qty": False, "sales_person": "", "allowed_price_lists": []}

    sales_person = _current_user_sales_person()
    hide_stock_qty = _hide_stock_qty_for_current_user()
    if not sales_person:
        return {"restricted_agent": True, "hide_stock_qty": hide_stock_qty, "sales_person": "", "allowed_price_lists": []}

    context = build_static_context(sales_person=sales_person)
    if (context.get("pricing_mode") or "") != STATIC_MODE:
        return {"restricted_agent": True, "hide_stock_qty": hide_stock_qty, "sales_person": sales_person, "allowed_price_lists": []}

    allowed = _filter_scoped_price_lists(context.get("selling_price_lists") or [], company or current_company())
    return {"restricted_agent": True, "hide_stock_qty": hide_stock_qty, "sales_person": sales_person, "allowed_price_lists": allowed}


def _is_restricted_agent_user():
    user = frappe.session.user
    if not user or user == "Administrator":
        return False
    roles = set(frappe.get_roles(user) or [])
    return bool(roles & RESTRICTED_AGENT_ROLES) and not bool(roles & PRIVILEGED_CATALOGUE_ROLES)


def _hide_stock_qty_for_current_user():
    return STOCK_QUANTITY_VIEWER_ROLE not in set(frappe.get_roles(frappe.session.user) or [])


def _current_user_sales_person():
    if not frappe.db.exists("DocType", "Sales Person") or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": frappe.session.user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def _filter_scoped_price_lists(price_lists, company):
    scoped = {row["name"] for row in _selling_price_lists(company, agent_context={"restricted_agent": False})}
    return [price_list for price_list in _clean_list(price_lists) if price_list in scoped]


def _stock_qty_map(item_codes):
    if not item_codes:
        return {}
    params = {"item_codes": tuple(item_codes)}
    rows = frappe.db.sql(
        f"""
        SELECT item_code, SUM(actual_qty) AS stock_qty
        FROM `tabBin`
        WHERE item_code IN %(item_codes)s
        {stock_warehouse_condition("warehouse", params)}
        GROUP BY item_code
        """,
        params,
        as_dict=True,
    )
    return {row.item_code: flt(row.stock_qty) for row in rows}


def _price_list_meta(price_lists):
    if not price_lists:
        return {}
    default_currency = frappe.defaults.get_global_default("currency")
    rows = frappe.get_all(
        "Price List",
        filters={"name": ["in", price_lists]},
        fields=["name", "currency"],
        limit_page_length=0,
    )
    return {row.name: {"name": row.name, "currency": row.currency or default_currency} for row in rows}


def _item_price_brand_map(item_codes, price_lists):
    item_codes = _clean_list(item_codes or [])
    price_lists = _clean_list(price_lists or [])
    if not item_codes or not price_lists or not _has_column("Item Price", "brand"):
        return {}

    conditions = [
        "ip.item_code IN %(item_codes)s",
        "ip.price_list = %(price_list)s",
        "ifnull(ip.brand, '') != ''",
    ]
    if _has_column("Item Price", "enabled"):
        conditions.append("ip.enabled = 1")
    if _has_column("Item Price", "valid_from"):
        conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
    if _has_column("Item Price", "valid_upto"):
        conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")

    order_by = "ip.item_code ASC, ip.modified DESC"
    if _has_column("Item Price", "valid_from"):
        order_by = "ip.item_code ASC, ip.valid_from DESC, ip.modified DESC"

    out = {}
    for price_list in price_lists:
        rows = frappe.db.sql(
            f"""
            SELECT ip.item_code, ip.brand
            FROM `tabItem Price` ip
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_by}
            """,
            {"item_codes": tuple(item_codes), "price_list": price_list, "today": nowdate()},
            as_dict=True,
        )
        for row in rows:
            out.setdefault(row.item_code, row.brand)
    return out


def _link_options(doctype):
    if not frappe.db.exists("DocType", doctype):
        return []
    return frappe.get_all(doctype, pluck="name", order_by="name asc", limit_page_length=0)


def _item_category_options():
    if frappe.db.exists("DocType", "Item Category"):
        fields = ["name"]
        if _has_column("Item Category", "item_group"):
            fields.append("item_group")
        return frappe.get_all("Item Category", fields=fields, order_by="name asc", limit_page_length=0)
    if not _has_column("Item", "custom_item_category"):
        return []
    return [
        row.custom_item_category
        for row in frappe.db.sql(
            """
            SELECT DISTINCT custom_item_category
            FROM `tabItem`
            WHERE ifnull(custom_item_category, '') != ''
            ORDER BY custom_item_category ASC
            """,
            as_dict=True,
        )
    ]


def _brand_options(company=None, agent_context=None):
    options = set()
    if frappe.db.exists("DocType", "Brand"):
        options.update(_link_options("Brand"))
    if _has_column("Item", "brand"):
        options.update(
            row.brand
            for row in frappe.db.sql(
                """
                SELECT DISTINCT brand
                FROM `tabItem`
                WHERE ifnull(brand, '') != ''
                ORDER BY brand ASC
                """,
                as_dict=True,
            )
        )

    price_lists = [
        row.get("name")
        for row in _selling_price_lists(company or current_company(), agent_context=agent_context)
        if row.get("name")
    ]
    if _has_column("Item Price", "brand") and price_lists:
        conditions = [
            "ip.price_list IN %(price_lists)s",
            "ifnull(ip.brand, '') != ''",
        ]
        if _has_column("Item Price", "enabled"):
            conditions.append("ip.enabled = 1")
        if _has_column("Item Price", "valid_from"):
            conditions.append("(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)")
        if _has_column("Item Price", "valid_upto"):
            conditions.append("(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)")
        options.update(
            row.brand
            for row in frappe.db.sql(
                f"""
                SELECT DISTINCT ip.brand
                FROM `tabItem Price` ip
                WHERE {' AND '.join(conditions)}
                ORDER BY ip.brand ASC
                """,
                {"price_lists": tuple(price_lists), "today": nowdate()},
                as_dict=True,
            )
        )
    return sorted(options)


def _render_pdf_html(payload, filters, columns):
    price_lists = payload.get("price_lists") or []
    benchmark_price_lists = payload.get("benchmark_price_lists") or []
    rows = payload.get("rows") or []
    resolved_columns = _resolve_pdf_columns(columns, price_lists, benchmark_price_lists)
    colgroup = _pdf_colgroup(resolved_columns)
    header_cells = "".join(f"<th>{_escape(label)}</th>" for _key, label in resolved_columns)
    image_cache = {}
    body_rows = "".join(
        _render_pdf_row(row, resolved_columns, price_lists, index + 1, image_cache, benchmark_price_lists)
        for index, row in enumerate(rows)
    )
    if not body_rows:
        body_rows = f"<tr><td colspan=\"{len(resolved_columns)}\" class=\"empty\">{_escape(_('No catalogue rows found.'))}</td></tr>"

    company = _escape(current_company() or "Orderlift")
    selected_lists = ", ".join(row.get("name") for row in price_lists if row.get("name")) or "-"
    filters_text = _pdf_filters_text(filters)
    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4 landscape; margin: 8mm; }}
            body {{ font-family: Arial, sans-serif; color: #111827; font-size: 5px; line-height: 1.08; }}
            .header {{ display: table; width: 100%; table-layout: fixed; margin-bottom: 5px; }}
            .title-block {{ display: table-cell; width: 68%; vertical-align: top; padding-right: 12px; }}
            .meta-block {{ display: table-cell; width: 32%; vertical-align: top; }}
            h1 {{ margin: 0 0 5px; font-size: 34px; line-height: 1.1; }}
            .meta {{ color: #475569; line-height: 1.25; font-size: 12px; }}
            table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
            th {{ background: #f1f5f9; color: #334155; font-size: 8.5px; font-weight: 800; line-height: 1.12; text-transform: uppercase; }}
            th, td {{ border: 1px solid #cbd5e1; padding: 1.2px 1.8px; vertical-align: middle; word-wrap: break-word; overflow-wrap: anywhere; line-height: 1.08; }}
            td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
            td.center {{ text-align: center; }}
            img {{ width: 28px; height: 28px; object-fit: contain; }}
            .image-placeholder {{ display: inline-block; border: 1px solid #cbd5e1; border-radius: 3px; padding: 1px 2px; color: #64748b; font-size: 4.5px; }}
            .pill {{ display: inline-block; border-radius: 999px; padding: 1px 3px; font-weight: 700; font-size: 5px; }}
            .yes {{ background: #dcfce7; color: #166534; }}
            .no {{ background: #fee2e2; color: #991b1b; }}
            .empty {{ text-align: center; color: #64748b; padding: 18px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title-block">
                <h1>{_escape(_('Catalogue Prix Articles'))}</h1>
                <div class="meta">{company}<br>{_escape(_('Date'))}: {_escape(formatdate(nowdate()))}</div>
            </div>
            <div class="meta meta-block">
                <strong>{_escape(_('Selling Price Lists'))}</strong><br>{_escape(selected_lists)}<br>
                <strong>{_escape(_('Filters'))}</strong><br>{_escape(filters_text)}
            </div>
        </div>
        <table>
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header_cells}</tr></thead>
            <tbody>{body_rows}</tbody>
        </table>
    </body>
    </html>
    """


def _filter_payload_rows(rows, table_search, column_filters):
    table_search = (table_search or "").strip().lower()
    clean_filters = {
        key: (str(value) if value is not None else "").strip().lower()
        for key, value in (column_filters or {}).items()
        if (str(value) if value is not None else "").strip()
    }
    if not table_search and not clean_filters:
        return rows

    out = []
    for row in rows:
        if table_search and table_search not in _row_search_text(row):
            continue
        blocked = False
        for key, value in clean_filters.items():
            if _is_numeric_filter_key(key) and _numeric_filter_has_operator(value):
                if not _matches_numeric_column_filter(_column_filter_number(row, key), value):
                    blocked = True
                    break
                continue
            if value not in _column_filter_text(row, key):
                blocked = True
                break
        if blocked:
            continue
        out.append(row)
    return out


def _filter_payload_item_codes(rows, item_codes):
    if not item_codes:
        return rows
    selected = set(item_codes)
    return [row for row in rows if row.get("item_code") in selected]


def _row_search_text(row):
    values = [
        row.get("item_code"),
        row.get("item_name"),
        row.get("item_category"),
        row.get("item_group"),
        row.get("brand"),
        row.get("uom"),
        row.get("stock_available"),
        _format_qty(row.get("stock_qty")),
    ]
    values.extend(str(value) for value in (row.get("prices") or {}).values() if value is not None)
    values.extend(str(value) for value in (row.get("ttc_prices") or {}).values() if value is not None)
    return " ".join(str(value or "") for value in values).lower()


def _column_filter_text(row, key):
    if _is_price_ht_key(key):
        value = (row.get("prices") or {}).get(_price_column_list(key))
        return "" if value is None else str(value).lower()
    if _is_price_ttc_key(key):
        value = (row.get("ttc_prices") or {}).get(_price_column_list(key))
        return "" if value is None else str(value).lower()
    if key == "stock_qty":
        return _format_qty(row.get("stock_qty")).lower()
    return str(row.get(key) or "").lower()


def _is_numeric_filter_key(key):
    key = str(key or "")
    return key == "stock_qty" or _is_price_ht_key(key) or _is_price_ttc_key(key)


def _column_filter_number(row, key):
    key = str(key or "")
    if _is_price_ht_key(key):
        return (row.get("prices") or {}).get(_price_column_list(key))
    if _is_price_ttc_key(key):
        return (row.get("ttc_prices") or {}).get(_price_column_list(key))
    if key == "stock_qty":
        return row.get("stock_qty")
    return None


def _numeric_filter_has_operator(value):
    return bool(re.match(r"^\s*(>=|<=|>|<|=)", str(value or "")))


def _matches_numeric_column_filter(actual_value, expression):
    parsed = _parse_numeric_column_filter(expression)
    if not parsed:
        return str(expression or "").lower() in str(actual_value or "").lower()
    if actual_value in (None, ""):
        return False
    operator, expected = parsed
    actual = flt(str(actual_value).replace(",", "."))
    if operator == ">":
        return actual > expected
    if operator == ">=":
        return actual >= expected
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    return abs(actual - expected) < 0.0000001


def _parse_numeric_column_filter(expression):
    match = re.match(r"^(>=|<=|>|<|=)\s*(-?\d+(?:[.,]\d+)?)$", str(expression or "").strip())
    if not match:
        return None
    return match.group(1), flt(match.group(2).replace(",", "."))


def _is_price_ht_key(key):
    key = str(key or "")
    return key.startswith("price_ht:") or key.startswith("price:")


def _is_price_ttc_key(key):
    return str(key or "").startswith("price_ttc:")


def _price_column_list(key):
    return str(key or "").split(":", 1)[1] if ":" in str(key or "") else ""


def _resolve_pdf_columns(columns, price_lists, benchmark_price_lists=None):
    available = set(BASE_COLUMN_LABELS)
    for row in price_lists or []:
        if row.get("name"):
            available.add(f"price:{row.get('name')}")
            available.add(f"price_ht:{row.get('name')}")
            available.add(f"price_ttc:{row.get('name')}")
    for row in benchmark_price_lists or []:
        if row.get("name"):
            available.add(f"benchmark:{row.get('name')}")
    selected = [column for column in columns if column in available]
    if not selected:
        selected = list(DEFAULT_PDF_COLUMNS)
        for row in price_lists or []:
            if row.get("name"):
                selected.extend([f"price_ht:{row.get('name')}", f"price_ttc:{row.get('name')}"])
        selected.extend(f"benchmark:{row.get('name')}" for row in benchmark_price_lists or [] if row.get("name"))
        selected.extend(["stock_qty", "stock_available"])
    out = []
    for column in selected:
        if _is_price_ht_key(column):
            out.append((column, f"{_price_column_list(column)} HT"))
        elif _is_price_ttc_key(column):
            out.append((column, f"{_price_column_list(column)} TTC"))
        elif column.startswith("benchmark:"):
            out.append((column, column.split(":", 1)[1]))
        else:
            out.append((column, BASE_COLUMN_LABELS.get(column, column)))
    return out


def _pdf_colgroup(columns):
    weights = [_pdf_column_width(key) for key, _label in columns]
    total = sum(weights) or 1
    return "".join(
        f"<col style=\"width:{(weight / total) * 100:.2f}%\">"
        for weight in weights
    )


def _pdf_column_width(key):
    if key == "_row_number":
        return 3
    if key == "image":
        return 5
    if key == "item_code":
        return 8
    if key == "item_name":
        return 18
    if key in {"item_category", "item_group"}:
        return 12
    if key in {"brand", "uom", "stock_qty", "stock_available"}:
        return 6
    if _is_price_ht_key(key) or _is_price_ttc_key(key) or key.startswith("benchmark:"):
        return 7
    return 8


def _render_pdf_row(row, columns, price_lists, row_number, image_cache, benchmark_price_lists=None):
    price_currency = {price_list.get("name"): price_list.get("currency") or "" for price_list in price_lists or []}
    benchmark_price_currency = {price_list.get("name"): price_list.get("currency") or "" for price_list in benchmark_price_lists or []}
    cells = []
    for key, _label in columns:
        if key == "_row_number":
            cells.append(f"<td class=\"center\">{row_number}</td>")
            continue
        if key == "image":
            cells.append(f"<td class=\"center\">{_pdf_image_html(row.get('image'), image_cache)}</td>")
            continue
        if _is_price_ht_key(key):
            price_list = _price_column_list(key)
            value = (row.get("prices") or {}).get(price_list)
            display = "-" if value is None else _format_money(value, price_currency.get(price_list))
            cells.append(f"<td class=\"num\">{_escape(display)}</td>")
            continue
        if _is_price_ttc_key(key):
            price_list = _price_column_list(key)
            value = (row.get("ttc_prices") or {}).get(price_list)
            display = "-" if value is None else _format_money(value, price_currency.get(price_list))
            cells.append(f"<td class=\"num\">{_escape(display)}</td>")
            continue
        if key.startswith("benchmark:"):
            price_list = key.split(":", 1)[1]
            value = (row.get("benchmark_prices") or {}).get(price_list)
            display = "-" if value is None else _format_money(value, benchmark_price_currency.get(price_list))
            cells.append(f"<td class=\"num\">{_escape(display)}</td>")
            continue
        if key == "stock_qty":
            cells.append(f"<td class=\"num\">{_escape(_format_qty(row.get('stock_qty')))}</td>")
            continue
        if key == "stock_available":
            available = row.get("stock_available") or "NON"
            css_class = "yes" if available == "OUI" else "no"
            cells.append(f"<td class=\"center\"><span class=\"pill {css_class}\">{_escape(available)}</span></td>")
            continue
        cells.append(f"<td>{_escape(row.get(key) or '')}</td>")
    return f"<tr>{''.join(cells)}</tr>"


def _pdf_image_html(image, image_cache):
    image = (image or "").strip()
    if not image:
        return "-"
    if image.startswith("data:image/"):
        return f"<img src=\"{_escape(image)}\" alt=\"\">"
    data_uri = _pdf_image_data_uri(image, image_cache)
    if data_uri:
        return f"<img src=\"{_escape(data_uri)}\" alt=\"\">"
    return f"<span class=\"image-placeholder\">{_escape(_('Image'))}</span>"


def _pdf_image_data_uri(image, image_cache):
    url = _pdf_image_url(image)
    if not url:
        return ""
    if url in image_cache:
        return image_cache[url]
    cached = _get_cached_pdf_image(url)
    if cached is not None:
        image_cache[url] = "" if cached == PDF_IMAGE_CACHE_MISS else cached
        return image_cache[url]

    image_cache[url] = ""
    try:
        response = requests.get(url, timeout=PDF_IMAGE_TIMEOUT_SECONDS, headers=PDF_IMAGE_HEADERS)
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            _set_cached_pdf_image(url, PDF_IMAGE_CACHE_MISS, PDF_IMAGE_NEGATIVE_CACHE_TTL_SECONDS)
            return ""
        content = response.content or b""
        if not content or len(content) > PDF_IMAGE_MAX_BYTES:
            _set_cached_pdf_image(url, PDF_IMAGE_CACHE_MISS, PDF_IMAGE_NEGATIVE_CACHE_TTL_SECONDS)
            return ""
        image_cache[url] = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
        _set_cached_pdf_image(url, image_cache[url], PDF_IMAGE_CACHE_TTL_SECONDS)
    except Exception:
        _set_cached_pdf_image(url, PDF_IMAGE_CACHE_MISS, PDF_IMAGE_NEGATIVE_CACHE_TTL_SECONDS)
        frappe.logger("orderlift").warning("Catalogue PDF image fetch failed", exc_info=True)
    return image_cache[url]


def _pdf_image_cache_key(url):
    return "orderlift:catalogue_pdf_image:" + hashlib.sha256(url.encode("utf-8")).hexdigest()


def _get_cached_pdf_image(url):
    try:
        return frappe.cache().get_value(_pdf_image_cache_key(url), shared=True)
    except Exception:
        return None


def _set_cached_pdf_image(url, value, ttl_seconds):
    try:
        frappe.cache().set_value(_pdf_image_cache_key(url), value, expires_in_sec=ttl_seconds, shared=True)
    except Exception:
        pass


def _pdf_image_url(image):
    image = (image or "").strip()
    if not image:
        return ""
    if image.startswith(("http://", "https://")):
        return re.sub(r"([?&]sz=)w\d+", r"\1w96", image)
    if image.startswith("/"):
        get_url = getattr(frappe.utils, "get_url", None)
        if callable(get_url):
            return get_url(image)
    return ""


def _pdf_filters_text(filters):
    labels = {
        "search": _("Search"),
        "item_category": _("Item Category"),
        "item_group": _("Item Group"),
        "brand": _("Brand"),
        "uom": _("UOM"),
        "in_stock_only": _("In Stock Only"),
        "show_missing_prices": _("Show Missing Prices"),
    }
    parts = []
    for key, label in labels.items():
        value = filters.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, bool):
            value = _("Yes") if value else _("No")
        parts.append(f"{label}: {value}")
    return "; ".join(parts) or "-"


def _format_money(value, currency):
    currency = (currency or "").strip()
    suffix = f" {currency}" if currency else ""
    return f"{flt(value):,.2f}{suffix}"


def _format_qty(value):
    return f"{flt(value):,.3f}".rstrip("0").rstrip(".")


def _escape(value):
    return frappe.utils.escape_html(str(value or ""))


def _has_column(doctype, fieldname):
    checker = getattr(frappe.db, "has_column", None)
    return bool(checker(doctype, fieldname)) if callable(checker) else True


def _parse_json(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _clean_list(values):
    out = []
    seen = set()
    for value in values or []:
        text = (str(value) if value is not None else "").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "oui", "on"}
    return bool(value)
