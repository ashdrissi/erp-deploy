import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
    DYNAMIC_MODE,
    STATIC_MODE,
    build_dynamic_context,
    build_static_context,
)
from orderlift.menu_access import resolve_current_company
from orderlift.orderlift_crm.company_business_type import get_company_business_type_names
from orderlift.orderlift_sales.utils.price_list_scope import get_price_list_names, validate_price_list_scope

PRIVILEGED_PRICING_ROLES = {"Administrator", "Orderlift Admin", "Orderlift Business Admin", "Pricing Manager", "Sales Manager", "System Manager"}
COMMERCIAL_PRICING_ROLES = {"Sales User", "Orderlift Commercial"}


LINE_FIELDS = [
    "name",
    "item",
    "item_name",
    "source_buying_price_list",
    "pricing_scenario",
    "resolved_pricing_scenario",
    "resolved_scenario_rule",
    "resolved_margin_rule",
    "scenario_source",
    "has_scenario_override",
    "has_line_override",
    "source_bundle",
    "dimensioning_set",
    "dimensioning_rule_label",
    "line_type",
    "bundle_group_id",
    "qty",
    "buy_price",
    "buy_price_missing",
    "buy_price_message",
    "display_group",
    "show_in_detail",
    "base_amount",
    "expense_unit_price",
    "expense_total",
    "customs_unit_amount",
    "margin_unit_amount",
    "customs_applied",
    "margin_total_amount",
    "total_margin_unit_amount",
    "total_margin_total_amount",
    "projected_unit_price",
    "projected_total_price",
    "manual_sell_unit_price",
    "is_manual_override",
    "final_sell_unit_price",
    "final_sell_total",
    "max_discount_percent_allowed",
    "discount_percent",
    "discount_amount",
    "discounted_sell_unit_price",
    "discounted_sell_total",
    "commission_rate",
    "commission_amount",
    "margin_pct",
    "total_margin_pct",
    "margin_basis",
    "customs_material",
    "customs_tariff_number",
    "customs_weight_kg",
    "customs_value_per_kg",
    "customs_base_value",
    "customs_total_percent",
    "customs_rate_per_kg",
    "customs_rate_percent",
    "customs_by_kg",
    "customs_by_percent",
    "packaging_profile_source",
    "tier_modifier_total",
    "zone_modifier_total",
    "customs_basis",
    "transport_allocation_mode",
    "transport_container_type",
    "transport_basis_total",
    "transport_numerator",
    "transport_allocated",
    "price_floor_violation",
    "benchmark_price",
    "benchmark_delta_abs",
    "benchmark_delta_pct",
    "benchmark_status",
    "benchmark_note",
    "benchmark_reference",
    "benchmark_source_count",
    "benchmark_ratio",
    "benchmark_method",
    "resolved_benchmark_rule",
    "margin_source",
    "tier_modifier_amount",
    "zone_modifier_amount",
    "breakdown_preview",
    "static_list_price",
    "resolved_selling_price_list",
    "pricing_breakdown_json",
]

AGENT_VISIBLE_LINE_FIELDS = {
    "name",
    "item",
    "item_name",
    "source_bundle",
    "dimensioning_set",
    "dimensioning_rule_label",
    "line_type",
    "bundle_group_id",
    "display_group",
    "qty",
    "manual_sell_unit_price",
    "final_sell_unit_price",
    "final_sell_total",
    "max_discount_percent_allowed",
    "discount_percent",
    "discounted_sell_total",
    "commission_rate",
    "commission_amount",
}

EDITABLE_LINE_FIELDS = [
    "item",
    "source_buying_price_list",
    "pricing_scenario",
    "source_bundle",
    "dimensioning_set",
    "dimensioning_rule_label",
    "line_type",
    "bundle_group_id",
    "qty",
    "buy_price",
    "display_group",
    "show_in_detail",
    "manual_sell_unit_price",
    "discount_percent",
]

SHEET_FIELDS = [
    "name",
    "sheet_name",
    "custom_company",
    "customer",
    "sales_person",
    "crm_business_type",
    "crm_segment",
    "geography_territory",
    "pricing_scenario",
    "benchmark_policy",
    "customs_policy",
    "selected_price_list",
    "output_mode",
    "dimensioning_set",
    "dimensioning_inputs_json",
    "resolved_mode",
    "total_buy",
    "total_expenses",
    "total_selling",
    "customs_total_applied",
    "projection_warnings",
    "creation",
    "owner",
    "modified",
    "modified_by",
]

MAPPING_FIELDS = [
    "name",
    "source_buying_price_list",
    "pricing_scenario",
    "customs_policy",
    "benchmark_policy",
    "business_type",
    "crm_segment",
    "priority",
    "is_active",
    "notes",
]

SELLING_PRICE_LIST_FIELDS = ["price_list", "sequence", "is_active"]


@frappe.whitelist()
def get_pricing_sheet_builder_payload(pricing_sheet=None):
    pricing_sheet = (pricing_sheet or "").strip()
    if pricing_sheet:
        doc = frappe.get_doc("Pricing Sheet", pricing_sheet)
        doc.check_permission("read")
        return {"sheet": _serialize_sheet(doc)}
    return {"sheet": _new_sheet_payload()}


@frappe.whitelist()
def save_pricing_sheet_builder_payload(payload):
    payload = _parse_payload(payload)
    doc = _doc_from_payload(payload)
    doc.save()
    return {"sheet": _serialize_sheet(doc), "name": doc.name}


@frappe.whitelist()
def recalculate_pricing_sheet_builder(pricing_sheet):
    doc = _get_writable_sheet(pricing_sheet)
    doc.save()
    return {"sheet": _serialize_sheet(doc)}


@frappe.whitelist()
def add_bundle_to_pricing_sheet(pricing_sheet, options=None):
    doc = _get_writable_sheet(pricing_sheet)
    options = _parse_payload(options) if options else {}
    _apply_builder_mode_flag(doc, options.get("pricing_mode"))
    doc.add_from_bundle(
        product_bundle=options.get("product_bundle"),
        multiplier=options.get("multiplier") or 1,
        replace_existing_lines=options.get("replace_existing_lines") or 0,
        default_show_in_detail=options.get("default_show_in_detail", 1),
        default_display_group_source=options.get("default_display_group_source") or "Item Group",
        line_mode=options.get("line_mode") or "Exploded",
        include_summary_in_detail=options.get("include_summary_in_detail", 1),
        include_components_in_detail=options.get("include_components_in_detail", 1),
    )
    doc.reload()
    return {"sheet": _serialize_sheet(doc)}


@frappe.whitelist()
def add_dimensioning_to_pricing_sheet(pricing_sheet, dimensioning_set=None, input_values_json=None, replace_existing_generated=1, pricing_mode=None):
    doc = _get_writable_sheet(pricing_sheet)
    _apply_builder_mode_flag(doc, pricing_mode)
    if dimensioning_set:
        doc.dimensioning_set = dimensioning_set
    doc.add_dimensioning_items(
        input_values_json=input_values_json,
        replace_existing_generated=replace_existing_generated,
    )
    doc.reload()
    return {"sheet": _serialize_sheet(doc)}


@frappe.whitelist()
def generate_builder_quotation(pricing_sheet, pricing_mode=None):
    doc = _get_writable_sheet(pricing_sheet)
    _apply_builder_mode_flag(doc, pricing_mode)
    doc.save()
    quotation = doc.generate_quotation()
    return {"quotation": quotation, "sheet": _serialize_sheet(doc)}


@frappe.whitelist()
def delete_pricing_sheet_builder(pricing_sheet):
    doc = _get_writable_sheet(pricing_sheet)
    frappe.delete_doc("Pricing Sheet", doc.name)
    return {"deleted": doc.name}


def _get_writable_sheet(pricing_sheet):
    if not pricing_sheet:
        frappe.throw(_("Save the Pricing Sheet before using this action."))
    doc = frappe.get_doc("Pricing Sheet", pricing_sheet)
    doc.check_permission("write")
    return doc


def _apply_builder_mode_flag(doc, pricing_mode):
    mode = (pricing_mode or "").strip()
    if mode in {"Static", "Dynamic"}:
        doc.flags.pricing_builder_mode = mode


def _doc_from_payload(payload):
    name = (payload.get("name") or "").strip()
    if name and frappe.db.exists("Pricing Sheet", name):
        doc = frappe.get_doc("Pricing Sheet", name)
        doc.check_permission("write")
    else:
        doc = frappe.new_doc("Pricing Sheet")
        doc.naming_series = payload.get("naming_series") or "PSH-.#####"

    _apply_builder_mode_flag(doc, payload.get("pricing_mode") or "Dynamic")

    doc.sheet_name = (payload.get("sheet_name") or doc.sheet_name or _("New Pricing Sheet")).strip()
    _apply_builder_company(doc)
    locked_sales_person = _locked_current_user_sales_person()
    for fieldname in [
        "customer",
        "crm_business_type",
        "crm_segment",
        "geography_territory",
        "selected_price_list",
        "benchmark_policy",
        "dimensioning_set",
    ]:
        if fieldname in payload:
            setattr(doc, fieldname, (payload.get(fieldname) or "").strip())
    if locked_sales_person is not None:
        doc.sales_person = locked_sales_person
    elif "sales_person" in payload:
        doc.sales_person = (payload.get("sales_person") or "").strip()

    if doc.flags.pricing_builder_mode == "Dynamic":
        doc.selected_price_list = ""
        doc.benchmark_policy = ""
        doc.set("selected_selling_price_lists", [])
    else:
        doc.set("selected_selling_price_lists", [])
        selling_rows = _selling_price_list_rows(payload)
        if not selling_rows:
            selling_rows = _default_static_selling_price_list_rows(doc.sales_person)
        for row in selling_rows:
            doc.append("selected_selling_price_lists", row)
        doc.selected_price_list = selling_rows[0]["price_list"] if selling_rows else (doc.selected_price_list or "")
    doc.pricing_scenario = ""
    doc.customs_policy = ""

    doc.output_mode = "Avec details"
    doc.dimensioning_inputs_json = payload.get("dimensioning_inputs_json") or ""

    doc.set("scenario_mappings", [])
    for mapping in payload.get("scenario_mappings") or []:
        row = _mapping_row(mapping)
        if row:
            doc.append("scenario_mappings", row)

    doc.set("lines", [])
    for line in payload.get("lines") or []:
        if not (line.get("item") or "").strip():
            continue
        row = {fieldname: line.get(fieldname) for fieldname in EDITABLE_LINE_FIELDS if fieldname in line}
        source_buying_price_list = (row.get("source_buying_price_list") or "").strip()
        if source_buying_price_list:
            validate_price_list_scope(source_buying_price_list, kind="buying", required=True)
        row["qty"] = flt(row.get("qty") or 1) or 1
        row["show_in_detail"] = 1
        row["line_type"] = row.get("line_type") or "Standard"
        doc.append("lines", row)
    _validate_builder_customer_scope(doc)
    return doc


def _serialize_sheet(doc):
    user_context = _get_user_context(getattr(doc, "sales_person", ""))
    data = {fieldname: getattr(doc, fieldname, None) for fieldname in SHEET_FIELDS}
    data["is_new"] = 0
    data["pricing_mode"] = "Static" if data.get("resolved_mode") == "Static" else "Dynamic"
    data["user_context"] = user_context
    if user_context.get("is_restricted_agent"):
        data["selected_price_list"] = ""
        data["pricing_scenario"] = ""
        data["benchmark_policy"] = ""
        data["customs_policy"] = ""
        data["selected_selling_price_lists"] = []
    else:
        data["selected_selling_price_lists"] = [_serialize_selling_price_list(row) for row in (doc.selected_selling_price_lists or [])]
        if not data["selected_selling_price_lists"] and (data.get("selected_price_list") or "").strip():
            data["selected_selling_price_lists"] = [{"price_list": data["selected_price_list"], "sequence": 10, "is_active": 1}]
    data["scenario_mappings"] = [] if user_context.get("is_restricted_agent") else [_serialize_mapping(row) for row in (doc.scenario_mappings or [])]
    data["lines"] = [_serialize_line(row, user_context) for row in (doc.lines or [])]
    data["quotation_preview"] = doc.get_quotation_preview()
    data["history"] = _get_sheet_history(doc)
    return data


def _get_user_context(sales_person=None):
    roles = set(frappe.get_roles(frappe.session.user) or [])
    is_privileged = bool(roles & PRIVILEGED_PRICING_ROLES)
    is_commercial = bool(roles & COMMERCIAL_PRICING_ROLES) and not is_privileged
    sales_person = (sales_person or _get_current_user_sales_person() or "").strip()
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name") if sales_person else ""
    agent_values = _get_agent_context(agent_name)
    static_context = build_static_context(sales_person=sales_person) if sales_person else {}
    dynamic_context = build_dynamic_context(sales_person=sales_person) if sales_person else {}
    current_company = _current_company()
    scoped_selling_price_lists = _enabled_selling_price_lists(current_company)
    scoped_buying_price_lists = _enabled_buying_price_lists(current_company)
    selling_price_lists = _filter_scoped_names(static_context.get("selling_price_lists") or [], scoped_selling_price_lists)
    allowed_buying_price_lists = _filter_scoped_names(
        dynamic_context.get("allowed_buying_price_lists") or [], scoped_buying_price_lists
    )
    all_selling_price_lists = [] if is_commercial else scoped_selling_price_lists
    return {
        "current_company": current_company,
        "sales_person": sales_person,
        "agent_rule": agent_name or "",
        "agent_pricing_mode": agent_values.get("pricing_mode") or "",
        "is_restricted_agent": is_commercial,
        "can_view_sensitive_pricing": not is_commercial,
        "can_edit_pricing_source": not is_commercial,
        "can_edit_sales_person": is_privileged,
        "commission_rate": flt(agent_values.get("commission_rate") or 0),
        "static_pricing_mode": STATIC_MODE,
        "dynamic_pricing_mode": DYNAMIC_MODE,
        "selling_price_lists": selling_price_lists,
        "all_selling_price_lists": all_selling_price_lists,
        "allowed_buying_price_lists": allowed_buying_price_lists,
    }


def _get_current_user_sales_person():
    if not frappe.db.exists("DocType", "Sales Person") or not frappe.db.has_column("Sales Person", "user"):
        return ""
    filters = {"user": frappe.session.user}
    if frappe.db.has_column("Sales Person", "enabled"):
        filters["enabled"] = 1
    return frappe.db.get_value("Sales Person", filters, "name") or ""


def _locked_current_user_sales_person():
    roles = set(frappe.get_roles(frappe.session.user) or [])
    if roles & PRIVILEGED_PRICING_ROLES:
        return None
    return _get_current_user_sales_person()


def _get_agent_context(agent_name):
    if not agent_name:
        return {}
    values = frappe.db.get_value(
        "Agent Pricing Rules",
        agent_name,
        ["pricing_mode", "commission_rate"],
        as_dict=True,
    ) or {}
    return values


def _get_sheet_history(doc):
    events = []
    if doc.name and frappe.db.exists("DocType", "Version"):
        versions = frappe.get_all(
            "Version",
            filters={"ref_doctype": "Pricing Sheet", "docname": doc.name},
            fields=["name", "owner", "modified", "data"],
            order_by="modified desc",
            limit_page_length=8,
        )
        for row in versions:
            events.append(
                {
                    "label": _("Changed"),
                    "actor": row.owner or "",
                    "modified": str(row.modified or ""),
                    "summary": _version_summary(row.get("data")),
                }
            )

    if not getattr(doc, "creation", None):
        return events

    events.append(
        {
            "label": _("Created"),
            "actor": doc.owner or "",
            "modified": str(doc.creation or ""),
            "summary": _("Pricing Sheet created."),
        }
    )
    return events[:9]


def _version_summary(data):
    try:
        parsed = json.loads(data or "{}")
    except Exception:
        return _("Pricing Sheet updated.")

    changed = parsed.get("changed") or []
    row_changed = parsed.get("row_changed") or []
    row_added = parsed.get("row_added") or parsed.get("added") or []
    row_removed = parsed.get("row_removed") or parsed.get("removed") or []
    parts = []
    if changed:
        labels = [str(row[0]).replace("_", " ").title() for row in changed[:4] if row]
        if labels:
            parts.append(_("Fields: {0}").format(", ".join(labels)))
    if row_changed:
        parts.append(_("Rows changed: {0}").format(len(row_changed)))
    if row_added:
        parts.append(_("Rows added: {0}").format(len(row_added)))
    if row_removed:
        parts.append(_("Rows removed: {0}").format(len(row_removed)))
    return "; ".join(parts) if parts else _("Pricing Sheet updated.")


def _serialize_mapping(row):
    data = {fieldname: getattr(row, fieldname, None) for fieldname in MAPPING_FIELDS}
    data["priority"] = cint(data.get("priority") or 10)
    data["is_active"] = 1 if cint(data.get("is_active", 1)) else 0
    return data


def _serialize_line(row, user_context=None):
    user_context = user_context or {}
    data = {fieldname: getattr(row, fieldname, None) for fieldname in LINE_FIELDS if fieldname != "item_name"}
    data["item_name"] = frappe.db.get_value("Item", row.item, "item_name") if row.item else ""
    for fieldname in [
        "qty",
        "buy_price",
        "base_amount",
        "expense_unit_price",
        "expense_total",
        "customs_unit_amount",
        "margin_unit_amount",
        "customs_applied",
        "margin_total_amount",
        "total_margin_unit_amount",
        "total_margin_total_amount",
        "projected_unit_price",
        "projected_total_price",
        "manual_sell_unit_price",
        "final_sell_unit_price",
        "final_sell_total",
        "max_discount_percent_allowed",
        "discount_percent",
        "discount_amount",
        "discounted_sell_unit_price",
        "discounted_sell_total",
        "commission_rate",
        "commission_amount",
        "margin_pct",
        "total_margin_pct",
        "customs_weight_kg",
        "customs_value_per_kg",
        "customs_base_value",
        "customs_total_percent",
        "customs_rate_per_kg",
        "customs_rate_percent",
        "customs_by_kg",
        "customs_by_percent",
        "tier_modifier_total",
        "zone_modifier_total",
        "transport_basis_total",
        "transport_numerator",
        "transport_allocated",
        "benchmark_price",
        "benchmark_delta_abs",
        "benchmark_delta_pct",
        "benchmark_reference",
        "benchmark_source_count",
        "benchmark_ratio",
        "tier_modifier_amount",
        "zone_modifier_amount",
        "static_list_price",
    ]:
        data[fieldname] = flt(data.get(fieldname))
    data["show_in_detail"] = 1 if cint(data.get("show_in_detail", 1)) else 0
    data["buy_price_missing"] = 1 if cint(data.get("buy_price_missing")) else 0
    data["has_scenario_override"] = 1 if cint(data.get("has_scenario_override")) else 0
    data["has_line_override"] = 1 if cint(data.get("has_line_override")) else 0
    data["is_manual_override"] = 1 if cint(data.get("is_manual_override")) else 0
    data["price_floor_violation"] = 1 if cint(data.get("price_floor_violation")) else 0
    if user_context.get("is_restricted_agent"):
        data = {fieldname: data.get(fieldname) for fieldname in AGENT_VISIBLE_LINE_FIELDS}
    return data


def _new_sheet_payload():
    current_company = _current_company()
    user_context = _get_user_context()
    return {
        "name": "",
        "is_new": 1,
        "sheet_name": "",
        "custom_company": current_company,
        "customer": "",
        "sales_person": user_context.get("sales_person") or "",
        "crm_business_type": "",
        "crm_segment": "",
        "geography_territory": "",
        "pricing_scenario": "",
        "benchmark_policy": "",
        "customs_policy": "",
        "selected_price_list": "",
        "selected_selling_price_lists": [],
        "pricing_mode": "Dynamic",
        "output_mode": "Avec details",
        "dimensioning_set": "",
        "dimensioning_inputs_json": "",
        "resolved_mode": "Draft",
        "total_buy": 0,
        "total_expenses": 0,
        "total_selling": 0,
        "customs_total_applied": 0,
        "projection_warnings": "",
        "user_context": user_context,
        "history": [],
        "scenario_mappings": [],
        "lines": [],
        "quotation_preview": {"line_count": 0, "detailed_count": 0, "grouped_count": 0, "warnings": ""},
    }


def _mapping_row(mapping):
    has_policy_value = any(
        (mapping.get(fieldname) or "").strip()
        for fieldname in [
            "source_buying_price_list",
            "pricing_scenario",
            "customs_policy",
            "benchmark_policy",
            "notes",
        ]
    )
    if not has_policy_value:
        return None

    source_buying_price_list = (mapping.get("source_buying_price_list") or "").strip()
    if source_buying_price_list:
        validate_price_list_scope(source_buying_price_list, kind="buying", required=True)

    return {
        "source_buying_price_list": source_buying_price_list,
        "pricing_scenario": (mapping.get("pricing_scenario") or "").strip(),
        "customs_policy": (mapping.get("customs_policy") or "").strip(),
        "benchmark_policy": (mapping.get("benchmark_policy") or "").strip(),
        "business_type": "",
        "crm_segment": "",
        "priority": cint(mapping.get("priority") or 10),
        "is_active": 1 if cint(mapping.get("is_active", 1)) else 0,
        "notes": mapping.get("notes") or "",
    }


def _selling_price_list_rows(payload):
    rows = []
    seen = set()
    for idx, row in enumerate(payload.get("selected_selling_price_lists") or [], start=1):
        price_list = (row.get("price_list") or "").strip()
        if not price_list or price_list in seen:
            continue
        validate_price_list_scope(price_list, kind="selling", required=True)
        seen.add(price_list)
        rows.append({
            "price_list": price_list,
            "sequence": cint(row.get("sequence") or idx * 10),
            "is_active": 1 if cint(row.get("is_active", 1)) else 0,
        })
    legacy = (payload.get("selected_price_list") or "").strip()
    if legacy and legacy not in seen:
        validate_price_list_scope(legacy, kind="selling", required=True)
        rows.append({"price_list": legacy, "sequence": len(rows) * 10 + 10, "is_active": 1})
    return rows


@frappe.whitelist()
def customer_query(doctype, txt, searchfield, start, page_len, filters=None):
    filters = frappe._dict(filters or {})
    company = _current_company()
    business_type = (filters.get("business_type") or "").strip()
    crm_segment = (filters.get("crm_segment") or "").strip()
    allowed_business_types = [business_type] if business_type else get_company_business_type_names(company)

    conditions = []
    values = {
        "txt": f"%{txt or ''}%",
        "start": cint(start),
        "page_len": cint(page_len) or 20,
    }
    if frappe.db.has_column("Customer", "disabled"):
        conditions.append("ifnull(c.disabled, 0) = 0")
    if company and frappe.db.has_column("Customer", "custom_company"):
        conditions.append("c.custom_company = %(company)s")
        values["company"] = company
    if allowed_business_types and frappe.db.exists("DocType", "CRM Segment Assignment"):
        values["business_types"] = tuple(allowed_business_types)
        segment_clause = ""
        if crm_segment:
            segment_clause = "AND csa.segment = %(crm_segment)s"
            values["crm_segment"] = crm_segment
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM `tabCRM Segment Assignment` csa
                WHERE csa.parenttype = 'Customer'
                    AND csa.parent = c.name
                    AND csa.business_type IN %(business_types)s
                    {segment_clause}
            )
            """.format(segment_clause=segment_clause)
        )
    conditions.append("(c.name LIKE %(txt)s OR c.customer_name LIKE %(txt)s)")
    where_clause = " AND ".join(conditions)
    return frappe.db.sql(
        f"""
        SELECT c.name, c.customer_name
        FROM `tabCustomer` c
        WHERE {where_clause}
        ORDER BY c.customer_name asc, c.name asc
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )


def _apply_builder_company(doc):
    if not frappe.get_meta("Pricing Sheet").get_field("custom_company"):
        return
    current_company = _current_company()
    if doc.is_new() or not (doc.get("custom_company") or "").strip():
        doc.custom_company = current_company


def _validate_builder_customer_scope(doc):
    customer = (doc.get("customer") or "").strip()
    if not customer:
        return
    company = (doc.get("custom_company") or _current_company()).strip()
    if company and frappe.db.has_column("Customer", "custom_company"):
        customer_company = (frappe.db.get_value("Customer", customer, "custom_company") or "").strip()
        if customer_company and customer_company != company:
            frappe.throw(_("Customer {0} belongs to company {1}, not the active Pricing Sheet company {2}.").format(customer, customer_company, company))

    business_type = (doc.get("crm_business_type") or "").strip()
    allowed_business_types = [business_type] if business_type else get_company_business_type_names(company)
    if not allowed_business_types or not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return
    if not frappe.db.exists(
        "CRM Segment Assignment",
        {
            "parenttype": "Customer",
            "parent": customer,
            "business_type": ["in", allowed_business_types],
        },
    ):
        frappe.throw(_("Customer {0} does not match the active company business type for this Pricing Sheet.").format(customer))


def _current_company():
    return resolve_current_company(user=frappe.session.user)


def _default_static_selling_price_list_rows(sales_person=None):
    context = _get_user_context(sales_person)
    price_lists = context.get("selling_price_lists") or []
    if not price_lists and context.get("can_edit_pricing_source"):
        price_lists = context.get("all_selling_price_lists") or []
    return [
        {"price_list": price_list, "sequence": (idx + 1) * 10, "is_active": 1}
        for idx, price_list in enumerate(price_lists)
        if price_list
    ]


def _enabled_selling_price_lists(company=None):
    return get_price_list_names("selling", company=company)


def _enabled_buying_price_lists(company=None):
    return get_price_list_names("buying", company=company)


def _filter_scoped_names(names, allowed_names):
    allowed = set(allowed_names or [])
    return [name for name in names or [] if name and name in allowed]


def _serialize_selling_price_list(row):
    return {
        "price_list": getattr(row, "price_list", "") or "",
        "sequence": cint(getattr(row, "sequence", 0) or 0),
        "is_active": 1 if cint(getattr(row, "is_active", 1)) else 0,
    }


def _parse_payload(payload):
    if isinstance(payload, str):
        payload = json.loads(payload or "{}")
    return payload or {}
