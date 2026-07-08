import json

import frappe
from frappe import _
from frappe.model.db_query import DatabaseQuery
from frappe.utils import cint, flt

from orderlift import company_access
from orderlift.orderlift_sales.doctype.agent_pricing_rules.agent_pricing_rules import (
    DYNAMIC_MODE,
    STATIC_MODE,
    build_dynamic_context,
    build_static_context,
)
from orderlift.menu_access import resolve_current_company
from orderlift.orderlift_sales.utils.price_list_scope import get_price_list_names, validate_price_list_scope
from orderlift.orderlift_sales.utils.tax_inclusive import company_default_sales_taxes_template

PRIVILEGED_PRICING_ROLES = {"Administrator", "Orderlift Admin", "Orderlift Business Admin", "Pricing Manager", "Sales Manager", "System Manager"}
SUPPORTED_PARTY_TYPES = {"Customer", "Lead", "Prospect"}


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
    "custom_applied_taxes",
    "custom_pu_ttc",
    "custom_pt_ttc",
    "commission_rate",
    "commission_amount",
    "margin_pct",
    "total_margin_pct",
    "margin_basis",
    "target_margin_percent",
    "builder_margin_percent",
    "builder_price_overridden",
    "pricing_builder",
    "builder_source_buying_price_list",
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
    "display_group",
    "qty",
    "resolved_selling_price_list",
    "manual_sell_unit_price",
    "final_sell_unit_price",
    "final_sell_total",
    "max_discount_percent_allowed",
    "discount_percent",
    "discounted_sell_unit_price",
    "discounted_sell_total",
    "custom_applied_taxes",
    "custom_pu_ttc",
    "custom_pt_ttc",
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
    "party_type",
    "party_name",
    "customer",
    "opportunity",
    "sales_person",
    "crm_business_type",
    "crm_segment",
    "geography_territory",
    "pricing_scenario",
    "benchmark_policy",
    "customs_policy",
    "taxes_and_charges_template",
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
    link_warning = _link_sheet_to_source_quotation(doc, payload)
    result = {"sheet": _serialize_sheet(doc), "name": doc.name}
    if link_warning:
        result["link_warning"] = link_warning
    return result


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
def get_opportunity_pricing_sheet_source(opportunity):
    return _get_opportunity_source_payload(opportunity)


@frappe.whitelist()
def get_quotation_pricing_sheet_source(quotation):
    quotation = (quotation or "").strip()
    if not quotation or not frappe.db.exists("Quotation", quotation):
        frappe.throw(_("Quotation {0} was not found.").format(quotation or ""))

    doc = frappe.get_doc("Quotation", quotation)
    doc.check_permission("read")
    party_type = (doc.get("quotation_to") or "Customer").strip()
    if party_type not in SUPPORTED_PARTY_TYPES:
        party_type = "Customer"
    return {
        "quotation": doc.name,
        "company": doc.get("company") or "",
        "party_type": party_type,
        "party_name": doc.get("party_name") or "",
        "customer": (doc.get("party_name") or "") if party_type == "Customer" else "",
        "opportunity": doc.get("opportunity") or "",
        "crm_business_type": doc.get("custom_crm_business_type") or "",
        "crm_segment": doc.get("custom_crm_segment") or "",
        "geography_territory": doc.get("territory") or "",
        "taxes_and_charges_template": doc.get("taxes_and_charges") or "",
        "selected_price_list": doc.get("selling_price_list") or "",
        "selected_selling_price_lists": _quotation_selling_price_list_rows(doc),
        "lines": _quotation_line_rows(doc),
        "title": _("Pricing Sheet - {0}").format(doc.name),
    }


@frappe.whitelist()
def create_pricing_sheet_from_opportunity(opportunity, pricing_mode=None):
    source = _get_opportunity_source_payload(opportunity)
    doc = _create_pricing_sheet_from_source(source, pricing_mode=pricing_mode)
    return {"pricing_sheet": doc.name, "sheet": _serialize_sheet(doc)}


@frappe.whitelist()
def create_pricing_sheet_from_quotation(quotation, pricing_mode=None, link_source_quotation=1):
    source = get_quotation_pricing_sheet_source(quotation)
    doc = _create_pricing_sheet_from_source(
        source,
        pricing_mode=pricing_mode,
        source_quotation=source.get("quotation") or "",
        link_source_quotation=cint(link_source_quotation),
    )
    return {"pricing_sheet": doc.name, "sheet": _serialize_sheet(doc)}


@frappe.whitelist()
def import_opportunity_items_to_pricing_sheet(pricing_sheet, opportunity=None, replace_existing=0, pricing_mode=None):
    doc = _get_writable_sheet(pricing_sheet)
    _apply_builder_mode_flag(doc, pricing_mode)
    opportunity = (opportunity or doc.get("opportunity") or "").strip()
    if not opportunity:
        frappe.throw(_("Choose an Opportunity before loading items."))

    source = _get_opportunity_source_payload(opportunity)
    _apply_opportunity_source_to_doc(doc, source)
    if cint(replace_existing):
        doc.set("lines", [])
    for row in source.get("items") or []:
        doc.append(
            "lines",
            {
                "item": row.get("item") or "",
                "qty": flt(row.get("qty") or 1) or 1,
                "display_group": row.get("display_group") or _("Opportunity"),
                "show_in_detail": 1,
                "line_type": "Standard",
            },
        )
    if not source.get("items"):
        frappe.throw(_("Opportunity {0} has no item rows to import.").format(opportunity))
    doc.save()
    doc.reload()
    return {"sheet": _serialize_sheet(doc), "imported_count": len(source.get("items") or [])}


@frappe.whitelist()
def get_pricing_sheet_quotation_options(pricing_sheet):
    doc = _get_writable_sheet(pricing_sheet)
    return {"quotations": doc.get_linked_quotations()}


@frappe.whitelist()
def generate_builder_quotation(pricing_sheet, pricing_mode=None, target_quotation=None):
    doc = _get_writable_sheet(pricing_sheet)
    _apply_builder_mode_flag(doc, pricing_mode)
    doc.save()
    quotation = doc.generate_quotation(target_quotation=target_quotation)
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


def _link_sheet_to_source_quotation(doc, payload):
    if not cint(payload.get("link_source_quotation") or 0):
        return ""
    quotation = (payload.get("source_quotation") or "").strip()
    if not quotation:
        return ""
    if not frappe.db.exists("Quotation", quotation) or not frappe.db.has_column("Quotation", "source_pricing_sheet"):
        return ""

    qdoc = frappe.get_doc("Quotation", quotation)
    qdoc.check_permission("write")
    current = (qdoc.get("source_pricing_sheet") or "").strip()
    if current == doc.name:
        return ""
    if current:
        return _("Quotation already linked to Pricing Sheet {0}; link was not changed.").format(current)

    qdoc.flags.allow_source_pricing_sheet_update = True
    qdoc.source_pricing_sheet = doc.name
    qdoc.save()
    return ""


def _apply_builder_mode_flag(doc, pricing_mode):
    locked_mode = _locked_current_user_agent_pricing_mode()
    if locked_mode:
        doc.flags.pricing_builder_mode = locked_mode
        return
    mode = (pricing_mode or "").strip()
    if mode in {"Static", "Dynamic"}:
        doc.flags.pricing_builder_mode = mode


def _quotation_selling_price_list_rows(doc) -> list[dict]:
    rows = []
    seen = set()
    if doc.meta.get_field("selected_selling_price_lists"):
        source_rows = doc.get("selected_selling_price_lists") or []
        source_rows = sorted(source_rows, key=lambda row: (cint(row.get("sequence") or 0) or 999999, cint(row.get("idx") or 0)))
        for idx, row in enumerate(source_rows, start=1):
            price_list = (row.get("price_list") or "").strip()
            if not price_list or price_list in seen:
                continue
            seen.add(price_list)
            rows.append(
                {
                    "price_list": price_list,
                    "sequence": cint(row.get("sequence") or idx * 10),
                    "is_active": 1 if cint(row.get("is_active", 1)) else 0,
                }
            )

    selling_price_list = (doc.get("selling_price_list") or "").strip()
    if selling_price_list and selling_price_list not in seen:
        rows.insert(0, {"price_list": selling_price_list, "sequence": 10, "is_active": 1})
    return rows


def _quotation_line_rows(doc) -> list[dict]:
    lines = []
    for row in doc.get("items") or []:
        item = (row.get("item_code") or "").strip()
        if not item:
            continue
        gross_rate = flt(
            row.get("source_gross_sell_rate")
            or row.get("price_list_rate")
            or row.get("rate")
            or 0
        )
        line = {
            "item": item,
            "item_name": row.get("item_name") or item,
            "qty": flt(row.get("qty") or 1) or 1,
            "manual_sell_unit_price": gross_rate,
            "discount_percent": flt(row.get("source_discount_percent") or row.get("discount_percentage") or 0),
            "display_group": row.get("item_group") or _("Quotation"),
            "show_in_detail": 1,
            "line_type": "Standard",
        }
        lines.append(line)
    return lines


def _create_pricing_sheet_from_source(source: dict, pricing_mode=None, source_quotation: str = "", link_source_quotation: int = 0):
    payload = _builder_payload_from_source(source, pricing_mode=pricing_mode)
    doc = _doc_from_payload(payload)
    doc.save()
    if source_quotation:
        _link_sheet_to_source_quotation(
            doc,
            {
                "source_quotation": source_quotation,
                "link_source_quotation": 1 if cint(link_source_quotation) else 0,
            },
        )
    doc.reload()
    return doc


def _builder_payload_from_source(source: dict, pricing_mode=None) -> dict:
    payload = _new_sheet_payload()
    source = source or {}
    inferred_mode = (pricing_mode or "").strip()
    if inferred_mode not in {"Static", "Dynamic"}:
        inferred_mode = "Static" if (source.get("selected_selling_price_lists") or source.get("selected_price_list")) else "Dynamic"

    payload.update(
        {
            "sheet_name": _source_sheet_name(source),
            "custom_company": source.get("company") or payload.get("custom_company") or "",
            "party_type": source.get("party_type") or payload.get("party_type") or "Customer",
            "party_name": source.get("party_name") or source.get("customer") or "",
            "customer": source.get("customer") or "",
            "opportunity": source.get("opportunity") or "",
            "crm_business_type": source.get("crm_business_type") or "",
            "crm_segment": source.get("crm_segment") or "",
            "geography_territory": source.get("geography_territory") or "",
            "taxes_and_charges_template": source.get("taxes_and_charges_template") or "",
            "selected_price_list": source.get("selected_price_list") or "",
            "selected_selling_price_lists": source.get("selected_selling_price_lists") or [],
            "lines": source.get("lines") or source.get("items") or [],
            "pricing_mode": inferred_mode,
        }
    )
    return payload


def _source_sheet_name(source: dict) -> str:
    title = (source.get("title") or "").strip()
    if title:
        return title if title.lower().startswith(_("Pricing Sheet").lower()) else _("Pricing Sheet - {0}").format(title)
    label = (source.get("quotation") or source.get("opportunity") or source.get("party_name") or "").strip()
    return _("Pricing Sheet - {0}").format(label) if label else _("New Pricing Sheet")


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
        "party_type",
        "party_name",
        "customer",
        "opportunity",
        "crm_business_type",
        "crm_segment",
        "geography_territory",
        "selected_price_list",
        "benchmark_policy",
        "taxes_and_charges_template",
        "dimensioning_set",
    ]:
        if fieldname in payload:
            setattr(doc, fieldname, (payload.get(fieldname) or "").strip())
    if not (doc.get("taxes_and_charges_template") or "").strip():
        doc.taxes_and_charges_template = company_default_sales_taxes_template(doc.get("custom_company") or "")
    _sync_builder_party_fields(doc)
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
    _validate_builder_party_scope(doc)
    return doc


def _serialize_sheet(doc):
    user_context = _get_user_context(getattr(doc, "sales_person", ""))
    _sync_builder_party_fields(doc)
    data = {fieldname: getattr(doc, fieldname, None) for fieldname in SHEET_FIELDS}
    data["is_new"] = 0
    data["pricing_mode"] = "Static" if data.get("resolved_mode") == "Static" else "Dynamic"
    data["user_context"] = user_context
    selected_selling_price_lists = [_serialize_selling_price_list(row) for row in (doc.selected_selling_price_lists or [])]
    if not selected_selling_price_lists and (data.get("selected_price_list") or "").strip():
        selected_selling_price_lists = [{"price_list": data["selected_price_list"], "sequence": 10, "is_active": 1}]
    if user_context.get("is_restricted_agent"):
        if (user_context.get("agent_pricing_mode") or "").strip() != STATIC_MODE:
            data["selected_price_list"] = ""
            selected_selling_price_lists = []
        data["pricing_scenario"] = ""
        data["benchmark_policy"] = ""
        data["customs_policy"] = ""
    data["selected_selling_price_lists"] = selected_selling_price_lists
    data["scenario_mappings"] = [] if user_context.get("is_restricted_agent") else [_serialize_mapping(row) for row in (doc.scenario_mappings or [])]
    data["lines"] = [_serialize_line(row, user_context) for row in (doc.lines or [])]
    data["quotation_preview"] = doc.get_quotation_preview()
    data["history"] = _get_sheet_history(doc)
    return data


def _get_opportunity_source_payload(opportunity):
    opportunity = (opportunity or "").strip()
    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        frappe.throw(_("Opportunity {0} was not found.").format(opportunity or ""))

    doc = frappe.get_doc("Opportunity", opportunity)
    doc.check_permission("read")
    party_type = (doc.get("opportunity_from") or "Customer").strip()
    party_name = (doc.get("party_name") or "").strip()
    if party_type not in SUPPORTED_PARTY_TYPES:
        party_type = "Customer"
    company = (doc.get("company") or "").strip()
    current_company = _current_company()
    if company and current_company and company != current_company:
        frappe.throw(_("Opportunity {0} belongs to company {1}, not the active company {2}.").format(doc.name, company, current_company))

    return {
        "opportunity": doc.name,
        "title": doc.get("title") or doc.name,
        "company": company,
        "party_type": party_type,
        "party_name": party_name,
        "customer": party_name if party_type == "Customer" else "",
        "customer_name": doc.get("customer_name") or party_name,
        "crm_business_type": doc.get("custom_crm_business_type") or "",
        "crm_segment": doc.get("custom_crm_segment") or "",
        "geography_territory": doc.get("territory") or "",
        "items": _opportunity_item_rows(doc),
    }


def _opportunity_item_rows(doc):
    rows = []
    for row in doc.get("items") or []:
        item_code = (row.get("item_code") or row.get("item") or "").strip()
        if not item_code or not frappe.db.exists("Item", item_code):
            continue
        item_name, item_group = frappe.db.get_value("Item", item_code, ["item_name", "item_group"]) or ("", "")
        display_group = item_group or _("Opportunity")
        rows.append(
            {
                "item": item_code,
                "item_name": row.get("item_name") or item_name or item_code,
                "qty": flt(row.get("qty") or 1) or 1,
                "display_group": display_group,
            }
        )
    return rows


def _apply_opportunity_source_to_doc(doc, source):
    doc.opportunity = source.get("opportunity") or ""
    if source.get("company") and frappe.get_meta("Pricing Sheet").get_field("custom_company"):
        doc.custom_company = source.get("company")
    if source.get("party_type"):
        doc.party_type = source.get("party_type")
    if source.get("party_name"):
        doc.party_name = source.get("party_name")
    if source.get("customer"):
        doc.customer = source.get("customer")
    if source.get("crm_business_type"):
        doc.crm_business_type = source.get("crm_business_type")
    if source.get("crm_segment"):
        doc.crm_segment = source.get("crm_segment")
    if source.get("geography_territory"):
        doc.geography_territory = source.get("geography_territory")


def _get_user_context(sales_person=None):
    roles = set(frappe.get_roles(frappe.session.user) or [])
    is_privileged = bool(roles & PRIVILEGED_PRICING_ROLES)
    is_restricted = not is_privileged
    sales_person = (sales_person or _get_current_user_sales_person() or "").strip()
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name") if sales_person else ""
    agent_values = _get_agent_context(agent_name)
    static_context = build_static_context(sales_person=sales_person) if sales_person else {}
    dynamic_context = build_dynamic_context(sales_person=sales_person) if sales_person else {}
    current_company = _current_company()
    scoped_selling_price_lists = _enabled_selling_price_lists(current_company)
    scoped_buying_price_lists = _enabled_buying_price_lists(current_company)
    selling_price_lists = _filter_scoped_names(static_context.get("selling_price_lists") or [], scoped_selling_price_lists)
    benchmark_price_lists = _filter_scoped_names(static_context.get("benchmark_price_lists") or [], scoped_selling_price_lists)
    allowed_buying_price_lists = _filter_scoped_names(
        dynamic_context.get("allowed_buying_price_lists") or [], scoped_buying_price_lists
    )
    all_selling_price_lists = [] if is_restricted else scoped_selling_price_lists
    agent_mode = agent_values.get("pricing_mode") or ""
    return {
        "current_company": current_company,
        "sales_person": sales_person,
        "agent_rule": agent_name or "",
        "agent_pricing_mode": agent_mode,
        "is_restricted_agent": is_restricted,
        "can_view_sensitive_pricing": not is_restricted,
        "can_edit_pricing_source": (not is_restricted) or (agent_mode == STATIC_MODE and bool(selling_price_lists)),
        "can_edit_pricing_mode": not is_restricted,
        "can_edit_sales_person": is_privileged,
        "commission_rate": flt(agent_values.get("commission_rate") or 0),
        "static_pricing_mode": STATIC_MODE,
        "dynamic_pricing_mode": DYNAMIC_MODE,
        "selling_price_lists": selling_price_lists,
        "benchmark_price_lists": benchmark_price_lists,
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


def _locked_current_user_agent_pricing_mode():
    roles = set(frappe.get_roles(frappe.session.user) or [])
    if roles & PRIVILEGED_PRICING_ROLES:
        return ""
    sales_person = _get_current_user_sales_person()
    agent_name = frappe.db.get_value("Agent Pricing Rules", {"sales_person": sales_person}, "name") if sales_person else ""
    agent_mode = (_get_agent_context(agent_name).get("pricing_mode") or "").strip() if agent_name else ""
    return agent_mode if agent_mode in {STATIC_MODE, DYNAMIC_MODE} else ""


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
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
        "commission_rate",
        "commission_amount",
        "margin_pct",
        "total_margin_pct",
        "target_margin_percent",
        "builder_margin_percent",
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
    data["builder_price_overridden"] = 1 if cint(data.get("builder_price_overridden")) else 0
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
        "party_type": "Customer",
        "party_name": "",
        "customer": "",
        "opportunity": "",
        "sales_person": user_context.get("sales_person") or "",
        "crm_business_type": "",
        "crm_segment": "",
        "geography_territory": "",
        "pricing_scenario": "",
        "benchmark_policy": "",
        "customs_policy": "",
        "taxes_and_charges_template": company_default_sales_taxes_template(current_company),
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
    filters.party_type = "Customer"
    return party_query(doctype, txt, searchfield, start, page_len, filters)


@frappe.whitelist()
def party_query(doctype, txt, searchfield, start, page_len, filters=None):
    filters = frappe._dict(filters or {})
    party_type = (filters.get("party_type") or doctype or "Customer").strip()
    if party_type not in SUPPORTED_PARTY_TYPES:
        frappe.throw(_("Party Type must be Customer, Lead, or Prospect."))
    table = _table_name(party_type)
    display_expr = _party_display_expr(party_type, table)
    company = (filters.get("company") or _current_company()).strip()
    business_type = (filters.get("business_type") or "").strip()
    crm_segment = (filters.get("crm_segment") or "").strip()

    conditions = []
    values = {
        "txt": f"%{txt or ''}%",
        "start": cint(start),
        "page_len": cint(page_len) or 20,
    }

    scope_clause = _party_scope_clause(party_type, user=frappe.session.user)
    if scope_clause:
        conditions.append(scope_clause)
    match_clause = DatabaseQuery(party_type).build_match_conditions(as_condition=True)
    if match_clause:
        conditions.append(match_clause)

    if frappe.db.has_column(party_type, "disabled"):
        conditions.append(f"ifnull({table}.disabled, 0) = 0")
    company_field = _party_company_field(party_type)
    if company and company_field:
        conditions.append(f"{table}.{company_field} = %(company)s")
        values["company"] = company

    if (business_type or crm_segment) and frappe.db.exists("DocType", "CRM Segment Assignment"):
        segment_conditions = [
            "csa.parenttype = %(party_type)s",
            f"csa.parent = {table}.name",
        ]
        values["party_type"] = party_type
        if business_type:
            segment_conditions.append("csa.business_type = %(business_type)s")
            values["business_type"] = business_type
        if crm_segment:
            segment_conditions.append("csa.segment = %(crm_segment)s")
            values["crm_segment"] = crm_segment
        conditions.append(
            "EXISTS (SELECT 1 FROM `tabCRM Segment Assignment` csa WHERE "
            + " AND ".join(segment_conditions)
            + ")"
        )
    conditions.append(f"({table}.name LIKE %(txt)s OR {display_expr} LIKE %(txt)s)")
    where_clause = " AND ".join(conditions)
    return frappe.db.sql(
        f"""
        SELECT {table}.name, {display_expr}
        FROM {table}
        WHERE {where_clause}
        ORDER BY {display_expr} asc, {table}.name asc
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


def _sync_builder_party_fields(doc):
    party_type = (doc.get("party_type") or "").strip() or "Customer"
    party_name = (doc.get("party_name") or "").strip()
    customer = (doc.get("customer") or "").strip()
    if party_type not in SUPPORTED_PARTY_TYPES:
        frappe.throw(_("Party Type must be Customer, Lead, or Prospect."))
    if not party_name and customer:
        party_type = "Customer"
        party_name = customer
    doc.party_type = party_type
    doc.party_name = party_name
    doc.customer = party_name if party_type == "Customer" else ""


def _validate_builder_party_scope(doc):
    _sync_builder_party_fields(doc)
    party_type = (doc.get("party_type") or "Customer").strip()
    party_name = (doc.get("party_name") or "").strip()
    if not party_name:
        frappe.throw(_("Choose a Customer, Lead, or Prospect for this Pricing Sheet."))
    if not frappe.db.exists(party_type, party_name):
        frappe.throw(_("{0} {1} was not found.").format(party_type, party_name))

    if not _party_is_visible(party_type, party_name, user=frappe.session.user):
        frappe.throw(_("You do not have access to {0} {1}.").format(party_type, party_name), frappe.PermissionError)

    if not doc.get("custom_company") and _party_company_field(party_type):
        company = (frappe.db.get_value(party_type, party_name, _party_company_field(party_type)) or "").strip()
        if company and frappe.get_meta("Pricing Sheet").get_field("custom_company"):
            doc.custom_company = company

    company = (doc.get("custom_company") or _current_company()).strip()
    company_field = _party_company_field(party_type)
    if company and company_field:
        party_company = (frappe.db.get_value(party_type, party_name, company_field) or "").strip()
        if party_company and party_company != company:
            frappe.throw(_("{0} {1} belongs to company {2}, not the active Pricing Sheet company {3}.").format(party_type, party_name, party_company, company))

    business_type = (doc.get("crm_business_type") or "").strip()
    if not business_type:
        return
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return
    if not frappe.db.exists(
        "CRM Segment Assignment",
        {
            "parenttype": party_type,
            "parent": party_name,
            "business_type": business_type,
        },
    ):
        frappe.throw(_("{0} {1} does not match the selected business type for this Pricing Sheet.").format(party_type, party_name))


def _party_is_visible(party_type, party_name, user=None):
    user = user or frappe.session.user
    table = _table_name(party_type)
    conditions = [f"{table}.name = %(party_name)s"]
    scope_clause = _party_scope_clause(party_type, user=user)
    if scope_clause:
        conditions.append(scope_clause)
    match_clause = DatabaseQuery(party_type, user=user).build_match_conditions(as_condition=True)
    if match_clause:
        conditions.append(match_clause)
    return bool(
        frappe.db.sql(
            f"select {table}.name from {table} where {' and '.join(f'({clause})' for clause in conditions)} limit 1",
            {"party_name": party_name},
        )
    )


def _party_scope_clause(party_type, user=None):
    if party_type == "Customer":
        return company_access.customer_query(user=user)
    if party_type == "Lead":
        return company_access.lead_query(user=user)
    if party_type == "Prospect":
        return company_access.prospect_query(user=user)
    return None


def _party_company_field(party_type):
    for fieldname in ("custom_company", "company"):
        if frappe.db.has_column(party_type, fieldname):
            return fieldname
    return ""


def _party_display_expr(party_type, table):
    fields_by_type = {
        "Customer": ["customer_name"],
        "Lead": ["lead_name", "company_name"],
        "Prospect": ["company_name", "prospect_name"],
    }
    fields = [field for field in fields_by_type.get(party_type, []) if frappe.db.has_column(party_type, field)]
    parts = [f"nullif({table}.{field}, '')" for field in fields]
    parts.append(f"{table}.name")
    return f"coalesce({', '.join(parts)})"


def _table_name(doctype):
    return f"`tab{doctype.replace('`', '')}`"


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
