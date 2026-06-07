import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, nowdate

from orderlift.orderlift_sales.utils.price_list_scope import current_company


@frappe.whitelist()
def get_pricing_builder_manager_data(search=None):
    filters = []
    or_filters = []
    search = (search or "").strip()
    company = (current_company() or "").strip()
    if search:
        or_filters = [
            ["Pricing Builder", "name", "like", f"%{search}%"],
            ["Pricing Builder", "builder_name", "like", f"%{search}%"],
            ["Pricing Builder", "selling_price_list_name", "like", f"%{search}%"],
        ]

    rows = frappe.get_list(
        "Pricing Builder",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "builder_name",
            "selling_price_list_name",
            "default_qty",
            "max_items",
            "total_items",
            "ready_items",
            "changed_items",
            "new_items",
            "missing_items",
            "warnings_html",
            "modified",
            "owner",
        ],
        order_by="modified desc",
        limit_page_length=0,
    )
    rows = _filter_builder_rows_by_company(rows, company)
    return {"builders": [_serialize_row(row) for row in rows[:100]], "kpis": _get_kpis(company), "current_company": company}


@frappe.whitelist()
def delete_pricing_builders(pricing_builders=None):
    names = _parse_names(pricing_builders)
    if not names:
        frappe.throw(_("Select at least one Pricing Builder to delete."))
    deleted = []
    errors = []
    for name in names:
        try:
            doc = frappe.get_doc("Pricing Builder", name)
            doc.check_permission("delete")
            frappe.delete_doc("Pricing Builder", name)
            deleted.append(name)
        except Exception as exc:
            errors.append(_("{0}: {1}").format(name, frappe.bold(str(exc))))
    if errors and not deleted:
        frappe.throw("<br>".join(errors))
    return {"deleted": deleted, "errors": errors}


@frappe.whitelist()
def duplicate_pricing_builder(name):
    name = (name or "").strip()
    if not name:
        frappe.throw(_("Pricing Builder is required."))
    source = frappe.get_doc("Pricing Builder", name)
    source.check_permission("read")
    frappe.has_permission("Pricing Builder", "create", throw=True)

    duplicate = frappe.copy_doc(source)
    duplicate.naming_series = "PBU-.#####"
    duplicate.builder_name = _unique_copy_value(
        source.builder_name or source.name,
        lambda value: frappe.db.exists("Pricing Builder", {"builder_name": value}),
    )
    duplicate.selling_price_list_name = _unique_copy_value(
        source.selling_price_list_name or duplicate.builder_name,
        _selling_target_exists,
    )
    duplicate.insert()
    return {"builder": _serialize_row(frappe.get_doc("Pricing Builder", duplicate.name))}


def _parse_names(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = [value]
    else:
        parsed = value
    out = []
    seen = set()
    for name in parsed or []:
        name = (name or "").strip()
        if name and name not in seen:
            out.append(name)
            seen.add(name)
    return out


def _unique_copy_value(value, exists):
    base = (value or _("Pricing Builder")).strip()
    for index in range(1, 100):
        candidate = _("{0} Copy").format(base) if index == 1 else _("{0} Copy {1}").format(base, index)
        if not exists(candidate):
            return candidate
    frappe.throw(_("Unable to create a unique copy name for {0}.").format(base))


def _selling_target_exists(value):
    return bool(
        frappe.db.exists("Price List", value)
        or frappe.db.exists("Pricing Builder", {"selling_price_list_name": value})
    )


def _serialize_row(row):
    warnings = (row.warnings_html or "").strip()
    return {
        "name": row.name,
        "builder_name": row.builder_name or row.name,
        "selling_price_list_name": row.selling_price_list_name or "",
        "default_qty": flt(row.default_qty or 1),
        "max_items": cint(row.max_items or 0),
        "total_items": cint(row.total_items or 0),
        "ready_items": cint(row.ready_items or 0),
        "changed_items": cint(row.changed_items or 0),
        "new_items": cint(row.new_items or 0),
        "missing_items": cint(row.missing_items or 0),
        "warning_count": len([line for line in warnings.splitlines() if line.strip()]),
        "warnings": warnings,
        "modified": row.modified,
        "owner": row.owner or "",
    }


def _get_kpis(company=None):
    rows = frappe.get_all(
        "Pricing Builder",
        fields=["name", "selling_price_list_name", "total_items", "ready_items", "missing_items", "creation"],
        limit_page_length=0,
    )
    rows = _filter_builder_rows_by_company(rows, (company or "").strip())
    first_day = get_first_day(nowdate())
    return {
        "total_builders": len(rows),
        "builders_this_month": sum(1 for row in rows if str(row.creation or "") >= str(first_day)),
        "total_items": sum(cint(row.total_items or 0) for row in rows),
        "ready_items": sum(cint(row.ready_items or 0) for row in rows),
        "missing_items": sum(cint(row.missing_items or 0) for row in rows),
    }


def _filter_builder_rows_by_company(rows, company):
    if not rows or not company or not frappe.db.has_column("Price List", "custom_company"):
        return list(rows or [])
    price_lists = sorted({(row.selling_price_list_name or "").strip() for row in rows if (row.selling_price_list_name or "").strip()})
    company_map = _price_list_company_map(price_lists)
    filtered = []
    for row in rows:
        target = (row.selling_price_list_name or "").strip()
        if not target:
            filtered.append(row)
            continue
        price_list_company = company_map.get(target)
        if price_list_company is None or price_list_company == company:
            filtered.append(row)
    return filtered


def _price_list_company_map(price_lists):
    if not price_lists:
        return {}
    rows = frappe.get_all(
        "Price List",
        filters={"name": ["in", price_lists]},
        fields=["name", "custom_company"],
        limit_page_length=0,
    )
    return {row.name: (row.custom_company or "").strip() for row in rows}
