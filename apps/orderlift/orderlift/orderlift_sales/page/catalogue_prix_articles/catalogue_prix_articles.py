from __future__ import annotations

import base64
import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import flt, formatdate, nowdate

from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import STATIC_MODE, build_static_context
from orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet import get_latest_item_prices
from orderlift.orderlift_sales.utils.price_list_scope import current_company, get_price_lists, validate_price_list_scope


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
PRIVILEGED_CATALOGUE_ROLES = {"Orderlift Admin", "Orderlift Business Admin", "Pricing Manager", "Sales Manager", "System Manager"}
RESTRICTED_AGENT_ROLES = {"Sales User", "Orderlift Commercial"}


@frappe.whitelist()
def get_catalogue_bootstrap():
    company = current_company()
    agent_context = _current_agent_catalogue_context(company)
    return {
        "current_company": company,
        "price_lists": _selling_price_lists(company, agent_context=agent_context),
        "restricted_agent": agent_context.get("restricted_agent", False),
        "agent_sales_person": agent_context.get("sales_person") or "",
        "item_groups": _link_options("Item Group"),
        "item_categories": _item_category_options(),
        "brands": _brand_options(),
        "uoms": _link_options("UOM"),
    }


@frappe.whitelist()
def get_catalogue_rows(price_lists=None, filters=None):
    selected_price_lists = _validate_selling_price_lists(_clean_list(_parse_json(price_lists, [])))
    if not selected_price_lists:
        frappe.throw(_("Select at least one Selling Price List."))

    filters = _parse_json(filters, {}) or {}
    agent_context = _current_agent_catalogue_context(current_company())
    require_price_lists = selected_price_lists if agent_context.get("restricted_agent") else None
    item_rows = _query_items(filters, require_price_lists=require_price_lists)
    item_codes = [row.item_code for row in item_rows]
    if not item_codes:
        return _empty_payload(selected_price_lists, hide_stock_qty=agent_context.get("restricted_agent"))

    stock_map = _stock_qty_map(item_codes)
    price_maps = {
        price_list: get_latest_item_prices(item_codes, price_list, buying=False)
        for price_list in selected_price_lists
    }
    price_list_meta = _price_list_meta(selected_price_lists)
    show_missing_prices = _truthy(filters.get("show_missing_prices"), default=True)
    in_stock_only = False if agent_context.get("restricted_agent") else _truthy(filters.get("in_stock_only"), default=False)

    rows = []
    for row in item_rows:
        stock_qty = flt(stock_map.get(row.item_code) or 0)
        if in_stock_only and stock_qty <= 0:
            continue

        prices = {}
        has_price = False
        for price_list in selected_price_lists:
            value = price_maps.get(price_list, {}).get(row.item_code)
            if value is None:
                prices[price_list] = None
                continue
            prices[price_list] = flt(value)
            has_price = True
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
            "brand": row.brand or "",
            "uom": row.uom or "",
            "prices": prices,
            "stock_available": "OUI" if stock_qty > 0 else "NON",
        }
        if not agent_context.get("restricted_agent"):
            payload_row["stock_qty"] = stock_qty
        rows.append(payload_row)

    return {
        "price_lists": [price_list_meta.get(price_list) or {"name": price_list, "currency": ""} for price_list in selected_price_lists],
        "rows": rows,
        "kpis": {
            "items": len(rows),
            "price_lists": len(selected_price_lists),
            "in_stock": sum(
                1
                for row in rows
                if (row.get("stock_available") == "OUI" if agent_context.get("restricted_agent") else flt(row.get("stock_qty")) > 0)
            ),
            "missing_price_rows": sum(1 for row in rows if not any(value is not None for value in (row.get("prices") or {}).values())),
            "hide_stock_qty": 1 if agent_context.get("restricted_agent") else 0,
        },
    }


@frappe.whitelist()
def download_catalogue_pdf(price_lists=None, filters=None, columns=None, table_search="", column_filters=None, item_codes=None):
    selected_price_lists = _validate_selling_price_lists(_clean_list(_parse_json(price_lists, [])))
    if not selected_price_lists:
        frappe.throw(_("Select at least one Selling Price List."))
    filters = _parse_json(filters, {}) or {}
    columns = _clean_list(_parse_json(columns, []))
    if _current_agent_catalogue_context(current_company()).get("restricted_agent"):
        filters["in_stock_only"] = False
        columns = [column for column in columns if column != "stock_qty"]
    column_filters = _parse_json(column_filters, {}) or {}
    item_codes = _clean_list(_parse_json(item_codes, []))
    payload = get_catalogue_rows(selected_price_lists, filters)
    payload["rows"] = _filter_payload_rows(payload.get("rows") or [], table_search, column_filters)
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


def _empty_payload(price_lists, hide_stock_qty=False):
    price_list_meta = _price_list_meta(price_lists)
    return {
        "price_lists": [price_list_meta.get(price_list) or {"name": price_list, "currency": ""} for price_list in price_lists],
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
    rows = get_price_lists("selling", fields=["name", "currency"], company=company)
    allowed = set((agent_context or {}).get("allowed_price_lists") or [])
    if (agent_context or {}).get("restricted_agent"):
        rows = [row for row in rows if row.name in allowed]
    default_currency = frappe.defaults.get_global_default("currency") or "MAD"
    return [{"name": row.name, "currency": row.currency or default_currency} for row in rows]


def _validate_selling_price_lists(price_lists):
    agent_context = _current_agent_catalogue_context(current_company())
    allowed = set(agent_context.get("allowed_price_lists") or [])
    out = []
    for price_list in price_lists:
        resolved = validate_price_list_scope(price_list, kind="selling", required=True)
        if agent_context.get("restricted_agent") and resolved not in allowed:
            frappe.throw(
                _("Selling Price List {0} is not allocated to sales person {1}.").format(
                    resolved,
                    agent_context.get("sales_person") or "-",
                )
            )
        out.append(resolved)
    return out


def _query_items(filters, require_price_lists=None):
    fields = [
        "i.name AS item_code",
        "i.item_name",
        "i.item_group",
        "i.image",
        "i.stock_uom AS uom",
    ]
    if _has_column("Item", "brand"):
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
        if _has_column("Item", "brand"):
            search_terms.append("i.brand LIKE %(search)s")
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
    if brand and _has_column("Item", "brand"):
        conditions.append("i.brand = %(brand)s")
        params["brand"] = brand

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
        return {"restricted_agent": False, "sales_person": "", "allowed_price_lists": []}

    sales_person = _current_user_sales_person()
    if not sales_person:
        return {"restricted_agent": True, "sales_person": "", "allowed_price_lists": []}

    context = build_static_context(sales_person=sales_person)
    if (context.get("pricing_mode") or "") != STATIC_MODE:
        return {"restricted_agent": True, "sales_person": sales_person, "allowed_price_lists": []}

    allowed = _filter_scoped_price_lists(context.get("selling_price_lists") or [], company or current_company())
    return {"restricted_agent": True, "sales_person": sales_person, "allowed_price_lists": allowed}


def _is_restricted_agent_user():
    user = frappe.session.user
    if not user or user == "Administrator":
        return False
    roles = set(frappe.get_roles(user) or [])
    return bool(roles & RESTRICTED_AGENT_ROLES) and not bool(roles & PRIVILEGED_CATALOGUE_ROLES)


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
    rows = frappe.db.sql(
        """
        SELECT item_code, SUM(actual_qty) AS stock_qty
        FROM `tabBin`
        WHERE item_code IN %(item_codes)s
        GROUP BY item_code
        """,
        {"item_codes": tuple(item_codes)},
        as_dict=True,
    )
    return {row.item_code: flt(row.stock_qty) for row in rows}


def _price_list_meta(price_lists):
    if not price_lists:
        return {}
    default_currency = frappe.defaults.get_global_default("currency") or "MAD"
    rows = frappe.get_all(
        "Price List",
        filters={"name": ["in", price_lists]},
        fields=["name", "currency"],
        limit_page_length=0,
    )
    return {row.name: {"name": row.name, "currency": row.currency or default_currency} for row in rows}


def _link_options(doctype):
    if not frappe.db.exists("DocType", doctype):
        return []
    return frappe.get_all(doctype, pluck="name", order_by="name asc", limit_page_length=0)


def _item_category_options():
    if frappe.db.exists("DocType", "Item Category"):
        return _link_options("Item Category")
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


def _brand_options():
    if frappe.db.exists("DocType", "Brand"):
        return _link_options("Brand")
    if not _has_column("Item", "brand"):
        return []
    return [
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
    ]


def _render_pdf_html(payload, filters, columns):
    price_lists = payload.get("price_lists") or []
    rows = payload.get("rows") or []
    resolved_columns = _resolve_pdf_columns(columns, price_lists)
    colgroup = _pdf_colgroup(resolved_columns)
    header_cells = "".join(f"<th>{_escape(label)}</th>" for _key, label in resolved_columns)
    image_cache = {}
    body_rows = "".join(
        _render_pdf_row(row, resolved_columns, price_lists, index + 1, image_cache)
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
        if any(value not in _column_filter_text(row, key) for key, value in clean_filters.items()):
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
    return " ".join(str(value or "") for value in values).lower()


def _column_filter_text(row, key):
    if key.startswith("price:"):
        price_list = key.split(":", 1)[1]
        value = (row.get("prices") or {}).get(price_list)
        return "" if value is None else str(value).lower()
    if key == "stock_qty":
        return _format_qty(row.get("stock_qty")).lower()
    return str(row.get(key) or "").lower()


def _resolve_pdf_columns(columns, price_lists):
    available = set(BASE_COLUMN_LABELS)
    for row in price_lists or []:
        if row.get("name"):
            available.add(f"price:{row.get('name')}")
    selected = [column for column in columns if column in available]
    if not selected:
        selected = list(DEFAULT_PDF_COLUMNS)
        selected.extend(f"price:{row.get('name')}" for row in price_lists or [] if row.get("name"))
        selected.extend(["stock_qty", "stock_available"])
    out = []
    for column in selected:
        if column.startswith("price:"):
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
    if key.startswith("price:"):
        return 7
    return 8


def _render_pdf_row(row, columns, price_lists, row_number, image_cache):
    price_currency = {price_list.get("name"): price_list.get("currency") or "" for price_list in price_lists or []}
    cells = []
    for key, _label in columns:
        if key == "_row_number":
            cells.append(f"<td class=\"center\">{row_number}</td>")
            continue
        if key == "image":
            cells.append(f"<td class=\"center\">{_pdf_image_html(row.get('image'), image_cache)}</td>")
            continue
        if key.startswith("price:"):
            price_list = key.split(":", 1)[1]
            value = (row.get("prices") or {}).get(price_list)
            display = "-" if value is None else _format_money(value, price_currency.get(price_list))
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
    image_cache[url] = ""
    try:
        response = requests.get(url, timeout=PDF_IMAGE_TIMEOUT_SECONDS, headers=PDF_IMAGE_HEADERS)
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            return ""
        content = response.content or b""
        if not content or len(content) > PDF_IMAGE_MAX_BYTES:
            return ""
        image_cache[url] = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
    except Exception:
        frappe.logger("orderlift").warning("Catalogue PDF image fetch failed", exc_info=True)
    return image_cache[url]


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
