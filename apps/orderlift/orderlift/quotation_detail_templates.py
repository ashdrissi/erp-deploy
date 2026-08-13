from __future__ import annotations

import json
import re
from html import unescape

try:
    import frappe
except Exception:  # pragma: no cover - lets plain unittest import constants without Frappe installed.
    class _FrappeStub:
        def whitelist(self, *args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda fn: fn

    frappe = _FrappeStub()


TEMPLATE_DOCTYPE = "Orderlift Quotation Detail Template"
BLOCK_DOCTYPE = "Orderlift Quotation Detail Template Block"
SNAPSHOT_VERSION = 1
BLOCK_TYPES = (
    "Page Break",
    "Heading",
    "Paragraph",
    "Key Value",
    "List",
    "Manual Area",
    "Quotation Field",
    "Annex Field",
)
LAYOUT_BLOCK_TYPES = {"Page Break", "Heading"}
VALUE_BLOCK_TYPES = {"Paragraph", "Key Value", "List", "Manual Area", "Quotation Field", "Annex Field"}
QUOTATION_TEMPLATE_FIELD = "custom_commercial_presentation_template"
QUOTATION_SNAPSHOT_FIELD = "custom_commercial_presentation_snapshot"


def supported_block_types() -> tuple[str, ...]:
    return BLOCK_TYPES


def normalize_block_key(label: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return key or "block"


def parse_json(value, default=None):
    if value in (None, ""):
        return default if default is not None else {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default if default is not None else {}


def _as_payload(data) -> dict:
    return parse_json(data, {}) if isinstance(data, str) else (data or {})


def _require_template_manager_access() -> None:
    import frappe
    from frappe import _

    if frappe.session.user == "Administrator":
        return
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"Orderlift Admin", "System Manager", "Administrator"}):
        frappe.throw(_("Only administrators can manage quotation detail templates."), frappe.PermissionError)


def _template_summary(row) -> dict:
    import frappe

    return {
        "name": row.name,
        "template_name": row.template_name,
        "is_active": int(row.is_active or 0),
        "company": row.company or "",
        "display_order": row.display_order or 0,
        "description": row.description or "",
        "block_count": frappe.db.count(BLOCK_DOCTYPE, {"parent": row.name}),
    }


def _block_payload(row) -> dict:
    return {
        "block_key": row.block_key,
        "block_label": row.block_label,
        "block_type": row.block_type,
        "source_field": row.source_field or "",
        "annex_template": row.annex_template or "",
        "annex_field_key": row.annex_field_key or "",
        "default_value": row.default_value or "",
        "options": row.options or "",
        "is_required": int(row.is_required or 0),
        "allow_manual_override": int(row.allow_manual_override or 0),
        "display_order": row.display_order or row.idx,
    }


def _template_payload(doc) -> dict:
    return {
        "name": doc.name,
        "template_name": doc.template_name,
        "is_active": int(doc.is_active or 0),
        "company": doc.company or "",
        "display_order": doc.display_order or 0,
        "description": doc.description or "",
        "blocks": [_block_payload(row) for row in doc.blocks or []],
    }


def get_available_quotation_templates(
    company: str | None = None,
    active_only: bool = True,
    quotation_doc=None,
) -> list[dict]:
    import frappe

    filters = {}
    if active_only:
        filters["is_active"] = 1
    rows = frappe.get_all(
        TEMPLATE_DOCTYPE,
        filters=filters,
        fields=["name", "template_name", "is_active", "company", "display_order", "description"],
        order_by="display_order asc, modified desc",
        limit_page_length=0,
    )
    company = (company or "").strip()
    templates = []
    for row in rows:
        if company and (row.company or "").strip() and row.company != company:
            continue
        if quotation_doc and _template_ineligibility_reason(row.name, quotation_doc):
            continue
        templates.append(_template_summary(row))
    return templates


@frappe.whitelist()
def get_quotation_template_manager_bootstrap() -> dict:
    import frappe

    _require_template_manager_access()
    rows = frappe.get_all(
        TEMPLATE_DOCTYPE,
        fields=["name", "template_name", "is_active", "company", "display_order", "description"],
        order_by="display_order asc, modified desc",
        limit_page_length=0,
    )
    return {
        "templates": [_template_summary(row) for row in rows],
        "block_types": list(BLOCK_TYPES),
        "quotation_fields": _quotation_field_options(),
        "annex_templates": _annex_template_options(),
        "allowed_companies": _allowed_company_options(),
    }


def _allowed_company_options() -> list[str]:
    from orderlift.menu_access import get_allowed_companies

    return get_allowed_companies()


def _quotation_field_options() -> list[dict]:
    import frappe

    skip_types = {"Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect", "HTML", "Button"}
    fields = [{"fieldname": "name", "label": "Document ID", "fieldtype": "Data", "options": ""}]
    meta = frappe.get_meta("Quotation")
    for field in meta.fields:
        if field.fieldtype in skip_types or not field.fieldname:
            continue
        fields.append(
            {
                "fieldname": field.fieldname,
                "label": field.label or field.fieldname,
                "fieldtype": field.fieldtype,
                "options": field.options or "",
            }
        )
    return fields


def _annex_template_options() -> list[dict]:
    import frappe

    rows = frappe.get_all(
        "Orderlift Document Template",
        filters={"is_active": 1},
        fields=["name", "template_name", "display_order"],
        order_by="display_order asc, modified desc",
        limit_page_length=0,
    )
    out = []
    for row in rows:
        fields = frappe.get_all(
            "Orderlift Document Template Field",
            filters={"parent": row.name, "fieldtype": ["not in", ["Section Break", "Column Break", "HTML"]]},
            fields=["field_key", "field_label", "fieldtype", "options", "display_order", "idx"],
            order_by="display_order asc, idx asc",
            limit_page_length=0,
        )
        out.append(
            {
                "name": row.name,
                "template_name": row.template_name,
                "fields": [
                    {
                        "field_key": field.field_key,
                        "field_label": field.field_label,
                        "fieldtype": field.fieldtype,
                        "options": field.options or "",
                    }
                    for field in fields
                ],
            }
        )
    return out


@frappe.whitelist()
def get_quotation_template(name: str) -> dict:
    import frappe

    _require_template_manager_access()
    return _template_payload(frappe.get_doc(TEMPLATE_DOCTYPE, name))


@frappe.whitelist()
def save_quotation_template(payload: str | dict) -> dict:
    import frappe
    from frappe import _
    from frappe.utils import cint

    _require_template_manager_access()
    data = _as_payload(payload)
    template_name = (data.get("template_name") or "").strip()
    if not template_name:
        frappe.throw(_("Template name is required."))

    name = (data.get("name") or "").strip()
    doc = frappe.get_doc(TEMPLATE_DOCTYPE, name) if name else frappe.new_doc(TEMPLATE_DOCTYPE)
    doc.template_name = template_name
    doc.is_active = cint(data.get("is_active"))
    doc.company = (data.get("company") or "").strip()
    doc.display_order = cint(data.get("display_order")) or 100
    doc.description = (data.get("description") or "").strip()

    doc.set("blocks", [])
    seen_keys = set()
    for index, row in enumerate(data.get("blocks") or [], start=1):
        block_label = (row.get("block_label") or "").strip()
        block_type = (row.get("block_type") or "Paragraph").strip()
        if not block_label and block_type != "Page Break":
            continue
        if block_type not in BLOCK_TYPES:
            frappe.throw(_("Unsupported block type: {0}").format(block_type))
        block_key = normalize_block_key(row.get("block_key") or block_label or block_type)
        base_key = block_key
        counter = 2
        while block_key in seen_keys:
            block_key = f"{base_key}_{counter}"
            counter += 1
        seen_keys.add(block_key)
        doc.append(
            "blocks",
            {
                "block_key": block_key,
                "block_label": block_label or block_type,
                "block_type": block_type,
                "source_field": (row.get("source_field") or "").strip(),
                "annex_template": (row.get("annex_template") or "").strip(),
                "annex_field_key": (row.get("annex_field_key") or "").strip(),
                "default_value": row.get("default_value") or "",
                "options": row.get("options") or "",
                "is_required": cint(row.get("is_required")),
                "allow_manual_override": 1 if row.get("allow_manual_override") in (None, "", 1, "1", True) else 0,
                "display_order": cint(row.get("display_order")) or index,
            },
        )

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"template": _template_payload(doc), **get_quotation_template_manager_bootstrap()}


@frappe.whitelist()
def copy_quotation_template_to_company(name: str, company: str, template_name: str | None = None) -> dict:
    import frappe
    from frappe import _

    _require_template_manager_access()
    source = frappe.get_doc(TEMPLATE_DOCTYPE, (name or "").strip())
    target_company = (company or "").strip()
    if not target_company:
        frappe.throw(_("Target company is required."))
    if not frappe.db.exists("Company", target_company):
        frappe.throw(_("Company {0} was not found.").format(target_company))
    _require_company_scope(source.company or "")
    _require_company_scope(target_company)
    if (source.company or "").strip() == target_company:
        frappe.throw(_("Choose a different target company."))

    copy = frappe.new_doc(TEMPLATE_DOCTYPE)
    copy.template_name = _unique_template_name(template_name or f"{source.template_name} - {target_company}")
    copy.company = target_company
    copy.is_active = int(source.is_active or 0)
    copy.display_order = source.display_order or 100
    copy.description = source.description or ""
    for block in source.blocks or []:
        copy.append("blocks", _block_payload(block))
    copy.save(ignore_permissions=True)
    frappe.db.commit()
    return {"copied_template": _template_payload(copy), **get_quotation_template_manager_bootstrap()}


def _require_company_scope(company: str) -> None:
    import frappe
    from frappe import _

    company = (company or "").strip()
    if not company:
        return
    from orderlift.menu_access import user_can_access_company

    if not user_can_access_company(company):
        frappe.throw(_("You do not have access to company {0}.").format(company), frappe.PermissionError)


def _unique_template_name(base_name: str) -> str:
    import frappe

    clean = (base_name or "").strip() or "Quotation Detail Template"
    if not frappe.db.exists(TEMPLATE_DOCTYPE, clean):
        return clean
    counter = 2
    while frappe.db.exists(TEMPLATE_DOCTYPE, f"{clean} ({counter})"):
        counter += 1
    return f"{clean} ({counter})"


@frappe.whitelist()
def delete_quotation_template(name: str) -> dict:
    import frappe

    _require_template_manager_access()
    template = frappe.get_doc(TEMPLATE_DOCTYPE, name)
    frappe.delete_doc(TEMPLATE_DOCTYPE, template.name, force=1, ignore_permissions=True)
    frappe.db.commit()
    return {"template_name": template.template_name}


@frappe.whitelist()
def get_quotation_detail_editor(quotation: str, template: str | None = None) -> dict:
    import frappe

    quotation = (quotation or "").strip()
    if not quotation:
        frappe.throw("Quotation is required.")
    doc = frappe.get_doc("Quotation", quotation)
    doc.check_permission("read")

    company = doc.get("company") or ""
    templates = get_available_quotation_templates(company=company, active_only=True, quotation_doc=doc)
    selected_template = (template or doc.get(QUOTATION_TEMPLATE_FIELD) or "").strip()
    selected_ineligibility_reason = ""
    if selected_template and not any(row["name"] == selected_template for row in templates):
        selected_ineligibility_reason = _template_ineligibility_reason(selected_template, doc)
        selected_template = ""

    snapshot = parse_json(doc.get(QUOTATION_SNAPSHOT_FIELD), {})
    manual_values = _snapshot_values(snapshot) if snapshot.get("template") == selected_template else {}
    template_payload = None
    blocks = []
    if selected_template:
        template_doc = frappe.get_doc(TEMPLATE_DOCTYPE, selected_template)
        template_payload = _template_payload(template_doc)
        blocks = _build_editor_blocks(template_doc, doc, manual_values)

    return {
        "quotation": doc.name,
        "company": company,
        "docstatus": int(doc.docstatus or 0),
        "templates": templates,
        "selected_template": selected_template,
        "template": template_payload,
        "blocks": blocks,
        "has_snapshot": bool(snapshot),
        "fallback_reason": selected_ineligibility_reason or ("" if templates else _no_template_fallback_reason()),
    }


@frappe.whitelist()
def save_quotation_detail_snapshot(quotation: str, template: str, values: str | dict | None = None) -> dict:
    import frappe
    from frappe import _

    quotation = (quotation or "").strip()
    template = (template or "").strip()
    if not quotation or not template:
        frappe.throw(_("Quotation and template are required."))

    doc = frappe.get_doc("Quotation", quotation)
    doc.check_permission("write")
    if int(doc.docstatus or 0) != 0:
        frappe.throw(_("Commercial presentation can only be edited on draft Quotations."))
    template_doc = frappe.get_doc(TEMPLATE_DOCTYPE, template)
    if not int(template_doc.is_active or 0):
        frappe.throw(_("Template {0} is not active.").format(template_doc.template_name))
    if (template_doc.company or "").strip() and template_doc.company != (doc.get("company") or ""):
        frappe.throw(_("Template {0} is not enabled for company {1}.").format(template_doc.template_name, doc.get("company") or ""))
    ineligibility_reason = _template_ineligibility_reason(template_doc, doc)
    if ineligibility_reason:
        frappe.throw(ineligibility_reason)

    submitted_values = _as_payload(values)
    blocks = _build_snapshot_blocks(template_doc, doc, submitted_values)
    missing = [row["label"] for row in blocks if row.get("required") and not (row.get("value") or "").strip()]
    if missing:
        frappe.throw(_("Required commercial presentation content is missing: {0}").format(", ".join(missing[:5])))

    snapshot = {
        "version": SNAPSHOT_VERSION,
        "template": template_doc.name,
        "template_name": template_doc.template_name,
        "company": doc.get("company") or "",
        "blocks": blocks,
    }
    doc.set(QUOTATION_TEMPLATE_FIELD, template_doc.name)
    doc.set(QUOTATION_SNAPSHOT_FIELD, json.dumps(snapshot, ensure_ascii=False))
    doc.save()
    frappe.db.commit()
    return {"snapshot": snapshot}


def build_print_context(doc) -> dict:
    snapshot = parse_json(doc.get(QUOTATION_SNAPSHOT_FIELD), {})
    blocks = snapshot.get("blocks") if isinstance(snapshot, dict) else []
    if not isinstance(blocks, list):
        blocks = []
    clean_blocks = []
    for row in blocks:
        if not isinstance(row, dict):
            continue
        block_type = row.get("type") or "Paragraph"
        if block_type not in BLOCK_TYPES:
            continue
        value = row.get("value") or ""
        clean_blocks.append({
            "key": row.get("key") or "",
            "label": row.get("label") or "",
            "type": block_type,
            "value": value,
            "items": _list_items(value),
        })
    return {
        "enabled": bool(clean_blocks),
        "template": snapshot.get("template") or "",
        "template_name": snapshot.get("template_name") or "",
        "blocks": clean_blocks,
    }


def _build_editor_blocks(template_doc, quotation_doc, manual_values: dict) -> list[dict]:
    rows = []
    for block in template_doc.blocks or []:
        resolved = _resolve_block_value(block, quotation_doc)
        manual = manual_values.get(block.block_key)
        value = manual if manual is not None else resolved["value"]
        rows.append({
            **_block_payload(block),
            "value": value,
            "resolved_value": resolved["value"],
            "source": resolved["source"],
        })
    return rows


def _no_template_fallback_reason() -> str:
    return "No active commercial presentation template is available for this quotation. Use Commercial Designation as a text fallback."


def _template_ineligibility_reason(template, quotation_doc) -> str:
    import frappe

    template_doc = frappe.get_doc(TEMPLATE_DOCTYPE, template) if isinstance(template, str) else template
    if not template_doc or not int(template_doc.get("is_active") or 0):
        return "The selected commercial presentation template is inactive."
    quotation_company = (quotation_doc.get("company") or "").strip()
    template_company = (template_doc.get("company") or "").strip()
    if template_company and template_company != quotation_company:
        return "The selected commercial presentation template is not enabled for this quotation company."

    reference_doctypes = {"Quotation"}
    if (quotation_doc.get("opportunity") or "").strip():
        reference_doctypes.add("Opportunity")
    for annex_template in _required_annex_templates(template_doc):
        if not _annex_template_enabled_for_any_reference(annex_template, reference_doctypes):
            return (
                f"Commercial template {template_doc.template_name} requires annex template {annex_template}, "
                "but that annex template is inactive or not enabled for this quotation flow."
            )
    return ""


def _required_annex_templates(template_doc) -> list[str]:
    names = []
    seen = set()
    for block in template_doc.blocks or []:
        if (block.block_type or "") != "Annex Field":
            continue
        annex_template = (block.annex_template or "").strip()
        if not annex_template or annex_template in seen:
            continue
        seen.add(annex_template)
        names.append(annex_template)
    return names


def _annex_template_enabled_for_any_reference(annex_template: str, reference_doctypes: set[str]) -> bool:
    import frappe

    if not frappe.db.exists("Orderlift Document Template", annex_template):
        return False
    if not int(frappe.db.get_value("Orderlift Document Template", annex_template, "is_active") or 0):
        return False
    return bool(
        frappe.db.exists(
            "Orderlift Document Template Target",
            {"parent": annex_template, "target_doctype": ["in", list(reference_doctypes)]},
        )
    )


def _build_snapshot_blocks(template_doc, quotation_doc, submitted_values: dict) -> list[dict]:
    rows = []
    for block in template_doc.blocks or []:
        resolved = _resolve_block_value(block, quotation_doc)
        value = str(submitted_values.get(block.block_key, resolved["value"]) or "")
        if not block.allow_manual_override and resolved["value"]:
            value = resolved["value"]
        rows.append({
            "key": block.block_key,
            "label": block.block_label,
            "type": block.block_type,
            "value": value,
            "required": int(block.is_required or 0),
            "source": resolved["source"],
        })
    return rows


def _snapshot_values(snapshot: dict) -> dict[str, str]:
    return {
        str(row.get("key") or ""): str(row.get("value") or "")
        for row in snapshot.get("blocks") or []
        if isinstance(row, dict) and row.get("key")
    }


def _resolve_block_value(block, quotation_doc) -> dict:
    block_type = block.block_type or "Paragraph"
    if block_type == "Page Break":
        return {"value": "", "source": "layout"}
    if block_type == "Heading":
        return {"value": block.default_value or block.block_label or "", "source": "template"}
    if block_type == "Quotation Field":
        value = _resolve_doc_value(quotation_doc, block.source_field or block.block_key)
        return {"value": value or block.default_value or "", "source": "quotation" if value else "default"}
    if block_type == "Annex Field":
        value, source = _resolve_annex_value(quotation_doc, block.annex_template, block.annex_field_key)
        return {"value": value or block.default_value or "", "source": source if value else "default"}
    if block_type == "List":
        return {"value": block.default_value or block.options or "", "source": "template"}
    return {"value": block.default_value or "", "source": "manual" if block_type == "Manual Area" else "template"}


def _resolve_doc_value(doc, source_field: str) -> str:
    source_field = (source_field or "").strip()
    if not source_field:
        return ""
    current_doc = doc
    parts = source_field.split(".")
    for index, fieldname in enumerate(parts):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", fieldname):
            return ""
        value = current_doc.get(fieldname) if hasattr(current_doc, "get") else getattr(current_doc, fieldname, None)
        if value in (None, ""):
            return ""
        if index == len(parts) - 1:
            return _stringify(value)
        linked = _linked_doc(current_doc, fieldname, value)
        if not linked:
            return ""
        current_doc = linked
    return ""


def _linked_doc(doc, fieldname: str, value):
    import frappe

    meta = getattr(doc, "meta", None)
    field = meta.get_field(fieldname) if meta and hasattr(meta, "get_field") else None
    if not field or field.fieldtype != "Link" or not field.options:
        return None
    if not frappe.has_permission(field.options, "read", doc=value):
        return None
    return frappe.get_doc(field.options, value)


def _resolve_annex_value(quotation_doc, template: str, field_key: str) -> tuple[str, str]:
    import frappe

    template = (template or "").strip()
    field_key = (field_key or "").strip()
    if not template or not field_key:
        return "", ""
    references = [("Quotation", quotation_doc.name)]
    opportunity = (quotation_doc.get("opportunity") or "").strip()
    if opportunity:
        references.append(("Opportunity", opportunity))
    for reference_doctype, reference_name in references:
        annex_name = frappe.db.get_value(
            "Orderlift Annex Document",
            {
                "template": template,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "docstatus": ["<", 2],
            },
            "name",
        )
        if not annex_name:
            continue
        annex = frappe.get_doc("Orderlift Annex Document", annex_name)
        if not annex.has_permission("read"):
            continue
        for row in annex.values or []:
            if row.field_key == field_key:
                return _stringify(row.value), f"{reference_doctype} annex {annex.name}"
    return "", ""


def _stringify(value) -> str:
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    return unescape(str(value or "")).strip()


def _list_items(value: str) -> list[str]:
    return [row.strip(" -\t") for row in str(value or "").splitlines() if row.strip(" -\t")]
