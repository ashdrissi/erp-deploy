import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt

from orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder import publish_builder_doc
from orderlift.orderlift_sales.utils.price_list_scope import current_company, get_price_list_names, validate_price_list_scope


PARENT_FIELDS = ["builder_name", "selling_price_list_name", "item_group", "default_qty", "max_items"]
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
    for row in payload.get("builder_items") or []:
        clean = {field: row.get(field) for field in ITEM_FIELDS}
        clean["selected"] = 1 if cint(clean.get("selected")) else 0
        if clean.get("item"):
            doc.append("builder_items", clean)

    doc.save(ignore_permissions=True)
    if cint(create_history):
        _create_history(doc, history_label or _("Saved"))
    return {"doc": _serialize_doc(doc), "history": _get_history(doc.name)}


@frappe.whitelist()
def calculate_builder_page_doc(name):
    doc = frappe.get_doc("Pricing Builder", name)
    doc.check_permission("write")
    doc.calculate_items()
    doc.save(ignore_permissions=True)
    _create_history(doc, _("Calculated"))
    return {"doc": _serialize_doc(doc), "history": _get_history(doc.name)}


@frappe.whitelist()
def publish_builder_page_doc(name, selected_only=1):
    out = publish_builder_doc(name, selected_only=selected_only)
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
    return doc


def _serialize_doc(doc):
    return {
        "name": doc.name if not doc.is_new() else "new",
        "is_new": 1 if doc.is_new() else 0,
        "builder_name": doc.get("builder_name") or "",
        "selling_price_list_name": doc.get("selling_price_list_name") or "",
        "item_group": doc.get("item_group") if _has_meta_field(doc, "item_group") else "",
        "default_qty": flt(doc.get("default_qty") or 1) or 1,
        "max_items": cint(doc.get("max_items") or 0),
        "total_items": cint(doc.get("total_items") or 0),
        "ready_items": cint(doc.get("ready_items") or 0),
        "changed_items": cint(doc.get("changed_items") or 0),
        "new_items": cint(doc.get("new_items") or 0),
        "missing_items": cint(doc.get("missing_items") or 0),
        "warnings_html": doc.get("warnings_html") or "",
        "modified": doc.get("modified") or "",
        "sourcing_rules": [_serialize_child(row, RULE_FIELDS) for row in doc.get("sourcing_rules") or []],
        "builder_items": [_serialize_child(row, ITEM_FIELDS) for row in doc.get("builder_items") or []],
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
    for row in snapshot.get("builder_items") or []:
        doc.append("builder_items", {field: row.get(field) for field in ITEM_FIELDS})


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


def _references():
    company = current_company()
    return {
        "current_company": company,
        "buying_price_lists": get_price_list_names("buying", company=company),
        "selling_price_lists": get_price_list_names("selling", company=company),
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
