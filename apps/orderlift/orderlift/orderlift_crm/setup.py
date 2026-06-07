from __future__ import annotations

import json
import os

import frappe

from orderlift.orderlift_crm.status_config import (
    LOGISTICS_STATUS_SEEDS,
    OPPORTUNITY_STAGE_SEEDS,
    PROJECT_STATUS_SEEDS,
    SALES_ORDER_STATUS_SEEDS,
)
from orderlift.orderlift_crm.todo_priority import (
    LEGACY_TODO_PRIORITY_MAP,
    TODO_PRIORITY_OPTIONS_TEXT,
    normalize_todo_priority,
)


FIXTURE_FILES = [
    "custom_field_partner_campaign_crm.json",
    "custom_field_crm_classification.json",
    "custom_field_status_control.json",
]

DEFAULT_BUSINESS_TYPES = [
    ("Distribution", 10),
    ("Installation", 20),
    ("Maintenance", 30),
]

DEFAULT_COMPANY_BUSINESS_TYPES = {
    "Orderlift Maroc Distribution": ["Distribution"],
    "Orderlift Maroc Installation": ["Installation"],
}

DEFAULT_CRM_SEGMENTS = [
    ("Grossiste", "Distribution", 10),
    ("Revendeur", "Distribution", 20),
    ("Installateur", "Distribution", 30),
    ("Promoteur", "Installation", 40),
    ("Individu", "Installation", 50),
]

LEGACY_SEGMENT_MAP = {
    "Grossiste": ("Distribution", "Grossiste"),
    "Distributeur": ("Distribution", "Grossiste"),
    "Revendeur": ("Distribution", "Revendeur"),
    "Installateur": ("Distribution", "Installateur"),
    "Promoteur": ("Installation", "Promoteur"),
    "Particulier": ("Installation", "Individu"),
    "Individu": ("Installation", "Individu"),
}

DEFAULT_SEGMENTS = [
    ("Grossiste", "Distribution", 10),
    ("Distributeur", "Distribution", 20),
    ("Revendeur", "Distribution", 30),
    ("Installateur", "Distribution", 40),
    ("Promoteur", "Installation", 50),
    ("Particulier", "Installation", 60),
]

DEFAULT_TARGET_STATUSES = [
    ("To Contact", 10, "Gray", 0, 0, 0, 1),
    ("Contacted", 20, "Blue", 1, 0, 0, 0),
    ("Interested", 30, "Green", 1, 1, 0, 0),
    ("No Answer", 40, "Orange", 1, 0, 0, 0),
    ("Not Interested", 50, "Red", 1, 0, 0, 0),
    ("Prospect Created", 60, "Purple", 1, 1, 0, 0),
    ("Opportunity Created", 70, "Blue", 1, 1, 0, 0),
    ("Quotation Created", 80, "Green", 1, 1, 0, 0),
    ("Converted", 90, "Green", 1, 1, 1, 0),
]

DEFAULT_INSTALLATION_STAGES = [
    ("New", 10, "Blue", 0, 20),
    ("Qualified", 20, "Blue", 0, 35),
    ("Study", 30, "Purple", 0, 50),
    ("Site Visit", 40, "Orange", 0, 60),
    ("Quotation Sent", 50, "Blue", 0, 70),
    ("Negotiation", 60, "Orange", 0, 80),
    ("Won / Project", 70, "Green", 1, 100),
    ("Lost", 80, "Red", 1, 0),
]


def after_migrate():
    _sync_custom_fields()
    _setup_crm_layout_overrides()
    _setup_todo_priority_options()
    _retire_customer_group_ui()
    _migrate_portal_policies_to_crm()
    _hide_legacy_partner_classification_fields()
    _seed_business_types()
    _seed_company_business_types()
    _seed_crm_segments()
    _seed_partner_segments()
    _seed_target_statuses()
    _seed_installation_stages()
    _seed_opportunity_stages()
    _deactivate_legacy_sales_stages()
    _seed_project_statuses()
    _seed_sales_order_statuses()
    _seed_logistics_pipeline_statuses()
    _migrate_party_crm_segments()
    _migrate_opportunity_crm_classification()
    _migrate_campaign_crm_classification()
    _clear_party_campaign_shortcuts()
    _remove_obsolete_opportunity_workflow_fields()
    _migrate_opportunity_stages_to_sales_stage()
    _remove_installation_pipeline_page()
    _backfill_crm_classification()
    _rename_opportunities_with_business_abbreviation()
    frappe.db.commit()


def _sync_custom_fields():
    fixtures_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))
    for filename in FIXTURE_FILES:
        path = os.path.join(fixtures_dir, filename)
        if not os.path.exists(path):
            frappe.logger().warning("orderlift_crm.setup: fixture not found: %s", path)
            continue

        with open(path) as fixture_file:
            fields = json.load(fixture_file)
        _upsert_custom_fields(fields)


def _upsert_custom_fields(fields: list[dict]) -> int:
    count = 0
    for field_def in fields:
        fieldname = field_def.get("fieldname")
        dt = field_def.get("dt")
        if not fieldname or not dt:
            continue

        existing = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
        doc = frappe.get_doc("Custom Field", existing) if existing else frappe.new_doc("Custom Field")

        for key, value in field_def.items():
            if key != "doctype":
                setattr(doc, key, value)

        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)
        count += 1
    return count


def _setup_todo_priority_options():
    if not frappe.db.exists("DocType", "ToDo"):
        return

    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": "ToDo", "field_name": "priority", "property": "options"},
        "name",
    )
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = "ToDo"
    setter.doctype_or_field = "DocField"
    setter.field_name = "priority"
    setter.property = "options"
    setter.property_type = "Text"
    setter.value = TODO_PRIORITY_OPTIONS_TEXT
    if existing:
        setter.save(ignore_permissions=True)
    else:
        setter.insert(ignore_permissions=True)

    for old_value, new_value in LEGACY_TODO_PRIORITY_MAP.items():
        frappe.db.sql("UPDATE `tabToDo` SET priority = %s WHERE priority = %s", (new_value, old_value))


def _setup_crm_layout_overrides():
    if _doctype_has_field("Opportunity", "title"):
        _upsert_property_setter("Opportunity", "title", "hidden", "0", "Check")
        _upsert_property_setter("Opportunity", "title", "insert_after", "customer_name", "Data")
    if _doctype_has_field("Opportunity", "organization_details_section"):
        _upsert_property_setter("Opportunity", "organization_details_section", "collapsible", "1", "Check")
        _upsert_property_setter("Opportunity", "organization_details_section", "collapsible_depends_on", "eval:0", "Code")
    if _doctype_has_field("Opportunity", "probability"):
        _upsert_property_setter("Opportunity", "probability", "hidden", "1", "Check")
    if _doctype_has_field("Opportunity", "section_break_14"):
        _upsert_property_setter("Opportunity", "section_break_14", "collapsible", "1", "Check")
        _upsert_property_setter("Opportunity", "section_break_14", "collapsible_depends_on", "eval:1", "Code")
    if not _doctype_has_field("Project", "customer_details"):
        return
    _upsert_property_setter("Project", "customer_details", "collapsible", "0", "Check")
    if _doctype_has_field("Project", "custom_crm_segment"):
        _upsert_property_setter("Project", "customer_details", "insert_after", "custom_crm_segment", "Data")


def _backfill_crm_classification():
    from orderlift.orderlift_crm.classification import (
        BUSINESS_FIELD,
        SEGMENT_FIELD,
        sync_project_crm_classification,
        sync_quotation_crm_classification,
        sync_sales_order_crm_classification,
    )

    syncers = {
        "Quotation": sync_quotation_crm_classification,
        "Sales Order": sync_sales_order_crm_classification,
        "Project": sync_project_crm_classification,
    }
    for doctype, syncer in syncers.items():
        if not (_doctype_has_field(doctype, BUSINESS_FIELD) and _doctype_has_field(doctype, SEGMENT_FIELD)):
            continue
        for name in frappe.get_all(doctype, pluck="name", limit_page_length=0):
            doc = frappe.get_doc(doctype, name)
            before = (doc.get(BUSINESS_FIELD) or "", doc.get(SEGMENT_FIELD) or "")
            syncer(doc)
            after = (doc.get(BUSINESS_FIELD) or "", doc.get(SEGMENT_FIELD) or "")
            if after == before:
                continue
            frappe.db.set_value(
                doctype,
                name,
                {BUSINESS_FIELD: after[0], SEGMENT_FIELD: after[1]},
                update_modified=False,
            )


def _retire_customer_group_ui():
    _ensure_default_customer_group()
    for doctype in ["Customer", "Prospect"]:
        if not _doctype_has_field(doctype, "customer_group"):
            continue
        for property_name, value, property_type in [
            ("hidden", "1", "Check"),
            ("read_only", "1", "Check"),
            ("in_list_view", "0", "Check"),
            ("in_standard_filter", "0", "Check"),
        ]:
            _upsert_property_setter(doctype, "customer_group", property_name, value, property_type)


def _migrate_portal_policies_to_crm():
    if not frappe.db.exists("DocType", "Portal Customer Group Policy"):
        return
    if not _db_has_column("Portal Customer Group Policy", "policy_name"):
        return
    rows = frappe.get_all(
        "Portal Customer Group Policy",
        fields=["name", "policy_name", "customer_group"],
        limit_page_length=0,
    )
    for row in rows:
        updates = {}
        if not (row.get("policy_name") or "").strip():
            updates["policy_name"] = row.get("name") or row.get("customer_group") or "Portal CRM Policy"
        if _db_has_column("Portal Customer Group Policy", "customer_group") and not (row.get("customer_group") or "").strip():
            updates["customer_group"] = "All Customer Groups"
        if updates:
            frappe.db.set_value("Portal Customer Group Policy", row.name, updates, update_modified=False)


def _ensure_default_customer_group():
    if not frappe.db.exists("DocType", "Customer Group"):
        return
    if frappe.db.exists("Customer Group", "All Customer Groups"):
        return
    doc = frappe.new_doc("Customer Group")
    doc.customer_group_name = "All Customer Groups"
    if doc.meta.get_field("is_group"):
        doc.is_group = 1
    doc.insert(ignore_permissions=True, ignore_mandatory=True)


def _upsert_property_setter(doctype: str, fieldname: str, property_name: str, value, property_type: str):
    existing = frappe.db.get_value(
        "Property Setter",
        {"doc_type": doctype, "field_name": fieldname, "property": property_name},
        "name",
    )
    setter = frappe.get_doc("Property Setter", existing) if existing else frappe.new_doc("Property Setter")
    setter.doc_type = doctype
    setter.doctype_or_field = "DocField"
    setter.field_name = fieldname
    setter.property = property_name
    setter.property_type = property_type
    setter.value = value
    if existing:
        setter.save(ignore_permissions=True)
    else:
        setter.insert(ignore_permissions=True)


def _db_has_column(doctype: str, fieldname: str) -> bool:
    has_column = getattr(frappe.db, "has_column", None)
    return bool(has_column and has_column(doctype, fieldname))


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
    if not frappe.db.exists("DocType", doctype):
        return False
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _hide_legacy_partner_classification_fields():
    party_updates = {
        "custom_partner_campaign_section": {"label": "Legacy Partner Campaign", "hidden": 1},
        "custom_partner_segment": {
            "label": "Legacy Partner Segment",
            "hidden": 1,
            "read_only": 1,
            "in_list_view": 0,
            "in_standard_filter": 0,
        },
        "custom_partner_campaign": {
            "label": "Legacy Partner Campaign",
            "hidden": 1,
            "read_only": 1,
            "in_standard_filter": 0,
        },
        "custom_partner_campaign_target": {
            "label": "Legacy Partner Campaign Target",
            "hidden": 1,
            "read_only": 1,
            "in_standard_filter": 0,
        },
    }
    for doctype in ["Lead", "Prospect", "Customer"]:
        for fieldname, values in party_updates.items():
            _update_custom_field_properties(doctype, fieldname, values)

    _update_custom_field_properties(
        "Opportunity",
        "custom_partner_segment",
        {
            "label": "Legacy Partner Segment",
            "hidden": 1,
            "read_only": 1,
            "in_list_view": 0,
            "in_standard_filter": 0,
        },
    )


def _update_custom_field_properties(doctype: str, fieldname: str, values: dict):
    custom_field = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
    if custom_field:
        frappe.db.set_value("Custom Field", custom_field, values, update_modified=False)


def _seed_partner_segments():
    if not frappe.db.exists("DocType", "Partner Segment"):
        return
    for segment_name, family, sequence in DEFAULT_SEGMENTS:
        _upsert_doc(
            "Partner Segment",
            segment_name,
            {
                "segment_name": segment_name,
                "segment_family": family,
                "sequence": sequence,
                "is_active": 1,
            },
        )


def _seed_business_types():
    if not frappe.db.exists("DocType", "CRM Business Type"):
        return
    for type_name, sequence in DEFAULT_BUSINESS_TYPES:
        _insert_doc_if_missing(
            "CRM Business Type",
            type_name,
            {
                "type_name": type_name,
                "abbreviation": _business_type_abbreviation(type_name),
                "sequence": sequence,
                "is_active": 1,
            },
        )
        if frappe.db.has_column("CRM Business Type", "abbreviation"):
            frappe.db.set_value(
                "CRM Business Type",
                type_name,
                "abbreviation",
                _business_type_abbreviation(type_name),
                update_modified=False,
            )


def _seed_company_business_types():
    if not (frappe.db.exists("DocType", "Company") and frappe.db.exists("DocType", "Company Business Type")):
        return
    if not _doctype_has_field("Company", "custom_crm_business_types"):
        return
    for company, business_types in DEFAULT_COMPANY_BUSINESS_TYPES.items():
        if not frappe.db.exists("Company", company):
            continue
        doc = frappe.get_doc("Company", company)
        existing = {row.get("business_type") for row in doc.get("custom_crm_business_types") or [] if row.get("business_type")}
        changed = False
        for idx, business_type in enumerate(business_types, start=1):
            if not frappe.db.exists("CRM Business Type", business_type) or business_type in existing:
                continue
            doc.append(
                "custom_crm_business_types",
                {"business_type": business_type, "is_default": 1 if idx == 1 and not existing else 0},
            )
            existing.add(business_type)
            changed = True
        if changed:
            doc.save(ignore_permissions=True)


def _seed_crm_segments():
    if not frappe.db.exists("DocType", "CRM Segment"):
        return
    for segment_name, business_type, sequence in DEFAULT_CRM_SEGMENTS:
        _insert_doc_if_missing(
            "CRM Segment",
            segment_name,
            {
                "segment_name": segment_name,
                "business_type": business_type,
                "sequence": sequence,
                "is_active": 1,
            },
        )


def _seed_target_statuses():
    if not frappe.db.exists("DocType", "Partner Campaign Status"):
        return
    for label, sequence, color, contacted, interested, converted, is_default in DEFAULT_TARGET_STATUSES:
        _insert_doc_if_missing(
            "Partner Campaign Status",
            label,
            {
                "status_label": label,
                "sequence": sequence,
                "color": color,
                "is_active": 1,
                "counts_as_contacted": contacted,
                "counts_as_interested": interested,
                "counts_as_converted": converted,
                "is_default": is_default,
            },
        )


def _seed_installation_stages():
    if not frappe.db.exists("DocType", "Installation Stage"):
        return
    for stage, sequence, color, is_closed, probability in DEFAULT_INSTALLATION_STAGES:
        _insert_doc_if_missing(
            "Installation Stage",
            stage,
            {
                "stage_name": stage,
                "sequence": sequence,
                "color": color,
                "is_active": 1,
                "is_closed": is_closed,
                "default_probability": probability,
                "skip_allowed": 1,
            },
        )


def _seed_opportunity_stages():
    if not frappe.db.exists("DocType", "Sales Stage"):
        return
    for row in OPPORTUNITY_STAGE_SEEDS:
        _insert_doc_if_missing(
            "Sales Stage",
            row["label"],
            {
                "stage_name": row["label"],
                "custom_sequence": row["sequence"],
                "custom_color": row["color"],
                "custom_is_active": 1,
                "custom_is_default": row["is_default"],
                "custom_applies_distribution": row["distribution"],
                "custom_applies_installation": row["installation"],
                "custom_company": row.get("company"),
                "custom_display_label": row.get("display_label"),
                "custom_todo_priority": normalize_todo_priority(row.get("todo_priority")),
            },
        )


def _deactivate_legacy_sales_stages():
    if not frappe.db.exists("DocType", "Sales Stage"):
        return
    active_labels = {row["label"] for row in OPPORTUNITY_STAGE_SEEDS}
    for stage_name in frappe.get_all("Sales Stage", pluck="name", limit_page_length=0):
        if stage_name in active_labels:
            continue
        doc = frappe.get_doc("Sales Stage", stage_name)
        if doc.meta.get_field("custom_is_active"):
            doc.custom_is_active = 0
        if doc.meta.get_field("custom_sequence") and not doc.custom_sequence:
            doc.custom_sequence = 999
        if doc.meta.get_field("custom_color") and not doc.custom_color:
            doc.custom_color = "Gray"
        doc.save(ignore_permissions=True)


def _seed_project_statuses():
    if not frappe.db.exists("DocType", "Project Status"):
        return
    for row in PROJECT_STATUS_SEEDS:
        _insert_doc_if_missing(
            "Project Status",
            row["label"],
            {
                "status_label": row["label"],
                "sequence": row["sequence"],
                "color": row["color"],
                "is_active": 1,
                "is_default": row["is_default"],
                "applies_distribution": row["distribution"],
                "applies_installation": row["installation"],
                "company": row.get("company"),
                "todo_priority": normalize_todo_priority(row.get("todo_priority")),
            },
        )


def _seed_sales_order_statuses():
    if not frappe.db.exists("DocType", "Orderlift Order Status"):
        return
    for row in SALES_ORDER_STATUS_SEEDS:
        _insert_doc_if_missing(
            "Orderlift Order Status",
            row["label"],
            {
                "status_label": row["label"],
                "sequence": row["sequence"],
                "color": row["color"],
                "is_active": 1,
                "is_default": row["is_default"],
                "applies_distribution": row["distribution"],
                "applies_installation": row["installation"],
                "todo_priority": normalize_todo_priority(row.get("todo_priority")),
            },
        )


def _seed_logistics_pipeline_statuses():
    if not frappe.db.exists("DocType", "Logistics Pipeline Status"):
        return
    for row in LOGISTICS_STATUS_SEEDS:
        _insert_doc_if_missing(
            "Logistics Pipeline Status",
            row["label"],
            {
                "status_label": row["label"],
                "sequence": row["sequence"],
                "color": row["color"],
                "is_active": 1,
                "is_default": row["is_default"],
                "todo_priority": normalize_todo_priority(row.get("todo_priority")),
            },
        )


def _migrate_opportunity_stages_to_sales_stage():
    if not frappe.db.exists("DocType", "Opportunity"):
        return
    opportunity_meta = frappe.get_meta("Opportunity")
    if not opportunity_meta.get_field("sales_stage"):
        return

    stage_names = {row["label"] for row in OPPORTUNITY_STAGE_SEEDS}
    rows = frappe.get_all(
        "Opportunity",
        fields=["name", "status", "sales_stage", "custom_installation_stage"],
        limit_page_length=0,
    )
    for row in rows:
        desired_stage = None
        legacy_stage = (row.get("custom_installation_stage") or "").strip()
        current_stage = (row.get("sales_stage") or "").strip()
        legacy_status = row.get("status") or ""
        if legacy_stage in stage_names:
            desired_stage = legacy_stage
        elif legacy_status == "Lost" and "Lost" in stage_names:
            desired_stage = "Lost"
        elif legacy_status == "Converted" and "Won / Project" in stage_names:
            desired_stage = "Won / Project"
        elif current_stage in stage_names:
            desired_stage = current_stage
        else:
            desired_stage = next((seed["label"] for seed in OPPORTUNITY_STAGE_SEEDS if seed.get("is_default")), None)

        if current_stage == desired_stage:
            continue
        frappe.db.set_value("Opportunity", row.name, "sales_stage", desired_stage, update_modified=False)


def _migrate_party_crm_segments():
    for doctype in ["Lead", "Prospect", "Customer"]:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        if not meta.get_field("custom_crm_segments") or not meta.get_field("custom_partner_segment"):
            continue
        for row in frappe.get_all(doctype, fields=["name", "custom_partner_segment"], limit_page_length=0):
            segment_value = row.get("custom_partner_segment")
            business_type, crm_segment = _resolve_crm_segment(segment_value)
            if not business_type or not crm_segment:
                continue
            if _party_has_segment(doctype, row.name, crm_segment):
                continue
            doc = frappe.get_doc(doctype, row.name)
            doc.append(
                "custom_crm_segments",
                {
                    "business_type": business_type,
                    "segment": crm_segment,
                    "is_primary": 1,
                },
            )
            doc.save(ignore_permissions=True)


def _migrate_opportunity_crm_classification():
    if not frappe.db.exists("DocType", "Opportunity"):
        return
    meta = frappe.get_meta("Opportunity")
    if not meta.get_field("custom_crm_business_type") or not meta.get_field("custom_crm_segment"):
        return
    fields = ["name", "custom_partner_segment"]
    if meta.get_field("custom_crm_business_type"):
        fields.append("custom_crm_business_type")
    if meta.get_field("custom_crm_segment"):
        fields.append("custom_crm_segment")
    for row in frappe.get_all("Opportunity", fields=fields, limit_page_length=0):
        if row.get("custom_crm_business_type") and row.get("custom_crm_segment"):
            continue
        business_type, crm_segment = _resolve_crm_segment(row.get("custom_partner_segment"))
        if not business_type or not crm_segment:
            continue
        updates = {}
        if not row.get("custom_crm_business_type"):
            updates["custom_crm_business_type"] = business_type
        if not row.get("custom_crm_segment"):
            updates["custom_crm_segment"] = crm_segment
        if updates:
            frappe.db.set_value("Opportunity", row.name, updates, update_modified=False)


def _migrate_campaign_crm_classification():
    if not frappe.db.exists("DocType", "Partner Campaign"):
        return
    campaign_meta = frappe.get_meta("Partner Campaign")
    has_campaign_fields = campaign_meta.get_field("business_type_filter") and campaign_meta.get_field("crm_segment_filter")
    for campaign_name in frappe.get_all("Partner Campaign", pluck="name", limit_page_length=0):
        campaign = frappe.get_doc("Partner Campaign", campaign_name)
        changed = False
        if has_campaign_fields and not campaign.get("crm_segment_filter") and campaign.get("partner_segment_filter"):
            business_type, crm_segment = _resolve_crm_segment(campaign.partner_segment_filter)
            if business_type and crm_segment:
                campaign.business_type_filter = business_type
                campaign.crm_segment_filter = crm_segment
                changed = True
        for target in campaign.get("targets") or []:
            if target.get("business_type") and target.get("crm_segment"):
                continue
            business_type, crm_segment = _resolve_crm_segment(target.get("partner_segment"))
            if business_type and crm_segment:
                target.business_type = target.get("business_type") or business_type
                target.crm_segment = target.get("crm_segment") or crm_segment
                changed = True
        if changed:
            campaign.save(ignore_permissions=True)


def _clear_party_campaign_shortcuts():
    for doctype in ["Lead", "Prospect", "Customer"]:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        fields = [fieldname for fieldname in ["custom_partner_campaign", "custom_partner_campaign_target"] if meta.get_field(fieldname)]
        if not fields:
            continue
        for fieldname in fields:
            frappe.db.sql(
                f"UPDATE `tab{doctype}` SET {fieldname} = NULL WHERE COALESCE({fieldname}, '') != ''"
            )


def _remove_obsolete_opportunity_workflow_fields():
    obsolete_fields = [
        "custom_study_required",
        "custom_site_visit_required",
        "custom_next_action",
    ]
    for fieldname in obsolete_fields:
        custom_field = frappe.db.get_value("Custom Field", {"dt": "Opportunity", "fieldname": fieldname}, "name")
        if custom_field:
            frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True, force=True)


def _remove_installation_pipeline_page():
    for doctype in ["Workspace Sidebar Item", "Workspace Shortcut"]:
        if not frappe.db.exists("DocType", doctype):
            continue
        for filters in [
            {"label": "Installation Pipeline"},
            {"link_to": "installation-pipeline"},
            {"url": "/app/installation-pipeline"},
            {"url": "/desk/installation-pipeline"},
        ]:
            frappe.db.delete(doctype, filters)

    if frappe.db.exists("Page", "installation-pipeline"):
        previous_in_migrate = getattr(frappe.flags, "in_migrate", False)
        frappe.flags.in_migrate = True
        try:
            frappe.delete_doc("Page", "installation-pipeline", ignore_permissions=True, force=True)
        finally:
            frappe.flags.in_migrate = previous_in_migrate


def _rename_opportunities_with_business_abbreviation():
    if not frappe.db.exists("DocType", "Opportunity"):
        return
    meta = frappe.get_meta("Opportunity")
    if not meta.get_field("custom_crm_business_type"):
        return
    rows = frappe.get_all(
        "Opportunity",
        filters={"name": ["like", "CRM-OPP-%"]},
        fields=["name", "custom_crm_business_type"],
        limit_page_length=0,
    )
    for row in rows:
        business_type = (row.get("custom_crm_business_type") or "").strip()
        if not business_type or _opportunity_name_has_business_abbreviation(row.name):
            continue
        new_name = _opportunity_name_with_business_abbreviation(row.name, business_type)
        if not new_name or frappe.db.exists("Opportunity", new_name):
            continue
        frappe.rename_doc("Opportunity", row.name, new_name, force=True, merge=False)


def _opportunity_name_has_business_abbreviation(name: str) -> bool:
    parts = (name or "").split("-")
    return len(parts) >= 5 and parts[0] == "CRM" and parts[1] == "OPP" and parts[2].isdigit()


def _opportunity_name_with_business_abbreviation(name: str, business_type: str) -> str:
    parts = (name or "").split("-")
    if len(parts) != 4 or parts[0] != "CRM" or parts[1] != "OPP" or not parts[2].isdigit():
        return ""
    return f"CRM-OPP-{parts[2]}-{_business_type_abbreviation(business_type)}-{parts[3]}"


def _party_has_segment(doctype: str, name: str, segment: str) -> bool:
    return bool(
        frappe.db.exists(
            "CRM Segment Assignment",
            {
                "parenttype": doctype,
                "parent": name,
                "segment": segment,
            },
        )
    )


def _resolve_crm_segment(segment: str | None) -> tuple[str | None, str | None]:
    if not segment:
        return None, None
    mapped = LEGACY_SEGMENT_MAP.get(segment) or (None, segment)
    business_type, crm_segment = mapped
    if not business_type and frappe.db.exists("CRM Segment", crm_segment):
        business_type = frappe.db.get_value("CRM Segment", crm_segment, "business_type")
    if not business_type or not crm_segment or not frappe.db.exists("CRM Segment", crm_segment):
        return None, None
    return business_type, crm_segment


def _upsert_doc(doctype: str, name: str, values: dict):
    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        for key, value in values.items():
            setattr(doc, key, value)
        doc.save(ignore_permissions=True)
        return doc

    doc = frappe.new_doc(doctype)
    for key, value in values.items():
        setattr(doc, key, value)
    doc.insert(ignore_permissions=True)
    return doc


def _insert_doc_if_missing(doctype: str, name: str, values: dict):
    if frappe.db.exists(doctype, name):
        return frappe.get_doc(doctype, name)
    doc = frappe.new_doc(doctype)
    for key, value in values.items():
        setattr(doc, key, value)
    doc.insert(ignore_permissions=True)
    return doc


def _business_type_abbreviation(type_name: str | None) -> str:
    return "".join(ch for ch in (type_name or "").strip().lower() if ch.isalnum())[:4] or "type"
