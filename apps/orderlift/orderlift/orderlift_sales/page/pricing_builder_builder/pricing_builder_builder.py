import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt, get_datetime

from orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder import builder_exchange_rate_summary, publish_builder_doc
from orderlift.orderlift_sales.utils.price_list_scope import current_company, get_price_list_names, validate_price_list_scope


PARENT_FIELDS = ["builder_name", "selling_price_list_name", "target_currency", "item_group", "default_qty", "max_items"]
RULE_FIELDS = ["buying_price_list", "pricing_scenario", "customs_policy", "benchmark_policy", "is_active"]
ITEM_FIELDS = [
    "selected",
    "item",
    "item_name",
    "item_group",
    "item_category",
    "material",
    "customs_tariff_number",
    "buying_list",
    "origin",
    "base_buy_price",
    "expenses",
    "customs_base_value",
    "customs_value_per_kg",
    "customs_amount",
    "customs_weight_kg",
    "customs_line_weight_kg",
    "customs_unit_weight_kg",
    "customs_package_weight_kg",
    "packaging_units_per_package",
    "packaging_package_count",
    "packaging_profile_source",
    "customs_basis",
    "margin_amount",
    "total_margin_amount",
    "avg_benchmark",
    "projected_price",
    "override_selling_price",
    "final_margin_pct",
    "total_margin_pct",
    "target_margin_percent",
    "margin_basis",
    "benchmark_is_fallback",
    "benchmark_rule_label",
    "benchmark_rule_max_discount_percent",
    "fallback_max_discount_percent",
    "policy_max_discount_percent",
    "published_price",
    "status",
    "status_note",
    "pricing_scenario",
    "customs_policy",
    "benchmark_policy",
    "calculation_breakdown_json",
]


@frappe.whitelist()
def get_builder_page_data(name=None):
    name = (name or "").strip()
    doc = frappe.get_doc("Pricing Builder", name) if name and name != "new" else _new_builder_doc()
    doc.check_permission("read") if not doc.is_new() else frappe.has_permission("Pricing Builder", "create", throw=True)
    return {"doc": _serialize_doc(doc), "references": _references(), "history": _get_history(doc.name if not doc.is_new() else "")}


@frappe.whitelist()
def save_builder_page_doc(payload, create_history=1, history_label=None):
    payload = frappe.parse_json(payload) or {}
    _validate_price_list_references(payload)
    name = (payload.get("name") or "").strip()
    if name and name != "new" and frappe.db.exists("Pricing Builder", name):
        doc = frappe.get_doc("Pricing Builder", name)
        doc.check_permission("write")
        _assert_current_version(doc, payload)
    else:
        frappe.has_permission("Pricing Builder", "create", throw=True)
        doc = frappe.new_doc("Pricing Builder")
        doc.naming_series = "PBU-.#####"

    for fieldname in PARENT_FIELDS:
        if _has_meta_field(doc, fieldname):
            doc.set(fieldname, payload.get(fieldname))
    doc.default_qty = flt(doc.default_qty or 1) or 1
    doc.max_items = cint(doc.max_items or 0)

    doc.set("sourcing_rules", [])
    for row in payload.get("sourcing_rules") or []:
        clean = {field: row.get(field) for field in RULE_FIELDS}
        clean["is_active"] = 1 if cint(clean.get("is_active", 1)) else 0
        if any(clean.get(field) for field in ["buying_price_list", "pricing_scenario", "customs_policy", "benchmark_policy"]):
            doc.append("sourcing_rules", clean)

    doc.set("builder_items", [])
    valid_items = _valid_builder_item_codes(payload.get("builder_items") or [])
    for row in payload.get("builder_items") or []:
        clean = {field: row.get(field) for field in ITEM_FIELDS}
        clean["selected"] = 1 if cint(clean.get("selected")) else 0
        if clean.get("item") and clean.get("item") in valid_items:
            doc.append("builder_items", clean)

    doc.save(ignore_permissions=True)
    if cint(create_history):
        _create_history(doc, history_label or _("Saved"))
    return {"doc": _serialize_doc(doc), "history": _get_history(doc.name)}


def _assert_current_version(doc, payload):
    client_modified = str((payload or {}).get("modified") or "").strip()
    server_modified = str(doc.get("modified") or "").strip()
    if not client_modified or not server_modified or get_datetime(client_modified) == get_datetime(server_modified):
        return
    frappe.throw(
        _("This Pricing Builder changed after this page was opened. Reload it before saving so newer changes are not overwritten."),
        getattr(frappe, "TimestampMismatchError", Exception),
    )


@frappe.whitelist()
def calculate_builder_page_doc(name):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.check_permission("write")
    doc.calculate_items()
    doc.save(ignore_permissions=True)
    _create_history(doc, _("Calculated"))
    return {"doc": _serialize_doc(doc), "history": _get_history(doc.name)}


@frappe.whitelist()
def compare_recalculated_builder_page_doc(name):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.check_permission("read")
    before = _serialize_doc(doc)
    doc.calculate_items()
    after = _serialize_doc(doc)
    summary = _compare_builder_snapshots(before, after)
    return {"changed": any(summary.values()), "summary": summary, "doc": after}


@frappe.whitelist()
def publish_builder_page_doc(name, selected_only=1, selected_rows=None):
    out = publish_builder_doc(name, selected_only=selected_only, selected_rows=selected_rows)
    doc = frappe.get_doc("Pricing Builder", name)
    _create_history(doc, _("Published"))
    return {"publish": out, "doc": _serialize_doc(doc), "history": _get_history(doc.name)}


@frappe.whitelist()
def rollback_builder_history(name, history_name):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.check_permission("write")
    history = frappe.get_doc("Pricing Builder History", history_name)
    if history.pricing_builder != name:
        frappe.throw(_("Selected history point does not belong to this Pricing Builder."))
    snapshot = frappe.parse_json(history.snapshot_json or "{}")
    if not snapshot:
        frappe.throw(_("Selected history point has no snapshot."))
    _apply_snapshot(doc, snapshot)
    doc.save(ignore_permissions=True)
    _create_history(doc, _("Rollback to {0}").format(history.name))
    return {"doc": _serialize_doc(doc), "history": _get_history(doc.name)}


def _new_builder_doc():
    doc = frappe.new_doc("Pricing Builder")
    doc.naming_series = "PBU-.#####"
    doc.default_qty = 1
    doc.max_items = 0
    if _has_meta_field(doc, "target_currency"):
        doc.target_currency = _company_default_currency()
    return doc


def _serialize_doc(doc):
    return {
        "name": doc.name if not doc.is_new() else "new",
        "is_new": 1 if doc.is_new() else 0,
        "builder_name": doc.get("builder_name") or "",
        "selling_price_list_name": doc.get("selling_price_list_name") or "",
        "target_currency": doc.get("target_currency") if _has_meta_field(doc, "target_currency") else "",
        "item_group": doc.get("item_group") if _has_meta_field(doc, "item_group") else "",
        "default_qty": flt(doc.get("default_qty") or 1) or 1,
        "max_items": cint(doc.get("max_items") or 0),
        "total_items": cint(doc.get("total_items") or 0),
        "ready_items": cint(doc.get("ready_items") or 0),
        "changed_items": cint(doc.get("changed_items") or 0),
        "new_items": cint(doc.get("new_items") or 0),
        "missing_items": cint(doc.get("missing_items") or 0),
        "warnings_html": doc.get("warnings_html") or "",
        "exchange_rate_summary": builder_exchange_rate_summary(doc),
        "modified": doc.get("modified") or "",
        "sourcing_rules": [_serialize_child(row, RULE_FIELDS) for row in doc.get("sourcing_rules") or []],
        "builder_items": [_serialize_builder_item(row) for row in doc.get("builder_items") or []],
    }


def _apply_snapshot(doc, snapshot):
    for fieldname in PARENT_FIELDS:
        if _has_meta_field(doc, fieldname):
            doc.set(fieldname, snapshot.get(fieldname))
    doc.default_qty = flt(doc.default_qty or 1) or 1
    doc.max_items = cint(doc.max_items or 0)
    for fieldname in ["total_items", "ready_items", "changed_items", "new_items", "missing_items", "warnings_html"]:
        if _has_meta_field(doc, fieldname):
            doc.set(fieldname, snapshot.get(fieldname))
    doc.set("sourcing_rules", [])
    for row in snapshot.get("sourcing_rules") or []:
        doc.append("sourcing_rules", {field: row.get(field) for field in RULE_FIELDS})
    doc.set("builder_items", [])
    valid_items = _valid_builder_item_codes(snapshot.get("builder_items") or [])
    for row in snapshot.get("builder_items") or []:
        clean = {field: row.get(field) for field in ITEM_FIELDS}
        if clean.get("item") and clean.get("item") in valid_items:
            doc.append("builder_items", clean)


def _has_meta_field(doc, fieldname):
    return any(field.fieldname == fieldname for field in doc.meta.fields)


def _serialize_child(row, fields):
    data = {}
    for field in fields:
        value = row.get(field)
        if field in {"selected", "is_active"}:
            data[field] = 1 if cint(value) else 0
        elif field in {
            "base_buy_price",
            "expenses",
            "customs_base_value",
            "customs_value_per_kg",
            "customs_amount",
            "customs_weight_kg",
            "customs_line_weight_kg",
            "customs_unit_weight_kg",
            "customs_package_weight_kg",
            "packaging_units_per_package",
            "packaging_package_count",
            "margin_amount",
            "total_margin_amount",
            "avg_benchmark",
            "projected_price",
            "override_selling_price",
            "final_margin_pct",
            "total_margin_pct",
            "target_margin_percent",
            "benchmark_rule_max_discount_percent",
            "fallback_max_discount_percent",
            "policy_max_discount_percent",
            "published_price",
        }:
            data[field] = flt(value or 0)
        elif field == "benchmark_is_fallback":
            data[field] = 1 if cint(value) else 0
        else:
            data[field] = value or ""
    return data


def _serialize_builder_item(row):
    data = _serialize_child(row, ITEM_FIELDS)
    _apply_customs_delta_fields(data)
    return data


def _apply_customs_delta_fields(data):
    try:
        breakdown = frappe.parse_json(data.get("calculation_breakdown_json") or "{}") or {}
    except Exception:
        breakdown = {}
    if not isinstance(breakdown, dict):
        return
    customs = breakdown.get("customs") or {}
    if not isinstance(customs, dict):
        return
    for fieldname in ("customs_value_delta", "customs_value_delta_tax_rate", "customs_value_delta_tax_amount"):
        data[fieldname] = flt(customs.get(fieldname) or 0)


def _valid_builder_item_codes(rows):
    item_codes = sorted({(row.get("item") or "").strip() for row in rows or [] if (row.get("item") or "").strip()})
    if not item_codes:
        return set()
    return set(frappe.get_all("Item", filters={"name": ["in", item_codes]}, pluck="name", limit_page_length=0))


def _compare_builder_snapshots(before, after):
    before_items = _builder_item_snapshot_map(before.get("builder_items") or [])
    after_items = _builder_item_snapshot_map(after.get("builder_items") or [])
    keys = sorted(set(before_items) | set(after_items))
    price_changes = 0
    status_changes = 0
    calculated_fields = [
        "base_buy_price",
        "expenses",
        "customs_amount",
        "margin_amount",
        "avg_benchmark",
        "projected_price",
        "published_price",
    ]
    for key in keys:
        old = before_items.get(key) or {}
        new = after_items.get(key) or {}
        if any(abs(flt(old.get(fieldname)) - flt(new.get(fieldname))) > 0.000001 for fieldname in calculated_fields):
            price_changes += 1
        if (old.get("status") or "") != (new.get("status") or "") or (old.get("status_note") or "") != (new.get("status_note") or ""):
            status_changes += 1
    return {
        "total_items_changed": 1 if len(before_items) != len(after_items) else 0,
        "price_changes": price_changes,
        "status_changes": status_changes,
        "warning_changed": 1 if (before.get("warnings_html") or "") != (after.get("warnings_html") or "") else 0,
    }


def _builder_item_snapshot_map(rows):
    out = {}
    for row in rows or []:
        key = ((row.get("item") or "").strip(), (row.get("buying_list") or "").strip())
        if key[0]:
            out[key] = row
    return out


def _references():
    company = current_company()
    buying_meta = _price_list_meta("buying", company=company)
    selling_meta = _price_list_meta("selling", company=company)
    return {
        "current_company": company,
        "company_currency": _company_default_currency(company),
        "currencies": _currency_names(),
        "buying_price_lists": list(buying_meta),
        "selling_price_lists": list(selling_meta),
        "buying_price_list_meta": buying_meta,
        "selling_price_list_meta": selling_meta,
        "pricing_scenarios": _names("Pricing Scenario"),
        "customs_policies": _names("Pricing Customs Policy", {"is_active": 1}),
        "benchmark_policies": _names("Pricing Benchmark Policy", {"is_active": 1}),
        "item_groups": _names("Item Group"),
    }


def _names(doctype, filters=None):
    if not frappe.db.exists("DocType", doctype):
        return []
    clean_filters = {}
    for key, value in (filters or {}).items():
        if frappe.db.has_column(doctype, key):
            clean_filters[key] = value
    return frappe.get_all(doctype, filters=clean_filters, pluck="name", order_by="name asc", limit_page_length=500)


def _price_list_meta(kind, company=None):
    names = get_price_list_names(kind, company=company)
    if not names:
        return {}
    fields = ["name"]
    if frappe.db.has_column("Price List", "currency"):
        fields.append("currency")
    if frappe.db.has_column("Price List", "custom_company"):
        fields.append("custom_company")
    rows = frappe.get_all(
        "Price List",
        filters={"name": ["in", names]},
        fields=fields,
        order_by="name asc",
        limit_page_length=0,
    )
    default_currency = frappe.defaults.get_global_default("currency") or ""
    return {
        row.name: {
            "name": row.name,
            "currency": row.get("currency") or default_currency,
            "company": row.get("custom_company") or company or "",
        }
        for row in rows
    }


def _company_default_currency(company=None):
    company = company or current_company()
    if company and frappe.db.exists("Company", company):
        return frappe.db.get_value("Company", company, "default_currency") or frappe.defaults.get_global_default("currency") or ""
    return frappe.defaults.get_global_default("currency") or ""


def _currency_names():
    if not frappe.db.exists("DocType", "Currency"):
        return []
    return frappe.get_all("Currency", pluck="name", order_by="name asc", limit_page_length=0)


def _validate_price_list_references(payload):
    target_selling_list = (payload.get("selling_price_list_name") or "").strip()
    if target_selling_list and frappe.db.exists("Price List", target_selling_list):
        validate_price_list_scope(target_selling_list, kind="selling", required=True)
    for row in payload.get("sourcing_rules") or []:
        buying_list = (row.get("buying_price_list") or "").strip()
        if buying_list:
            validate_price_list_scope(buying_list, kind="buying", required=True)


def _create_history(doc, action):
    if doc.is_new() or not frappe.db.exists("DocType", "Pricing Builder History"):
        return
    history = frappe.new_doc("Pricing Builder History")
    history.name = make_autoname("PBH-.#####")
    history.pricing_builder = doc.name
    history.action = (action or _("Saved"))[:140]
    history.summary = _history_summary(doc)
    history.snapshot_json = frappe.as_json(_serialize_doc(doc))
    history.insert(ignore_permissions=True)


def _get_history(name):
    if not name or not frappe.db.exists("DocType", "Pricing Builder History"):
        return []
    rows = frappe.get_all(
        "Pricing Builder History",
        filters={"pricing_builder": name},
        fields=["name", "creation", "owner", "action", "summary"],
        order_by="creation desc",
        limit_page_length=30,
    )
    return [dict(row) for row in rows]


def _history_summary(doc):
    return _("{0} items | {1} ready | {2} changed | {3} missing").format(
        cint(doc.get("total_items") or 0),
        cint(doc.get("ready_items") or 0),
        cint(doc.get("changed_items") or 0),
        cint(doc.get("missing_items") or 0),
    )
