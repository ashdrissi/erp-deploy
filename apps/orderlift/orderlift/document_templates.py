from __future__ import annotations

import json
import re

try:
    import frappe
except Exception:  # pragma: no cover - lets plain unittest import mapping helpers without Frappe installed.
    class _FrappeStub:
        def whitelist(self, *args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda fn: fn

    frappe = _FrappeStub()


SUPPORTED_DOCUMENT_TEMPLATE_TARGETS = (
    {"doctype": "Opportunity", "label": "Opportunity"},
    {"doctype": "Project", "label": "Project"},
    {"doctype": "Quotation", "label": "Quotation"},
    {"doctype": "Sales Order", "label": "Sales Order"},
    {"doctype": "Forecast Load Plan", "label": "Shipment Plan"},
)


def get_supported_document_template_targets() -> list[dict[str, str]]:
    return [dict(target) for target in SUPPORTED_DOCUMENT_TEMPLATE_TARGETS]


def get_document_template_target_label(doctype: str) -> str:
    for target in SUPPORTED_DOCUMENT_TEMPLATE_TARGETS:
        if target["doctype"] == doctype:
            return target["label"]
    return doctype


def get_supported_target_doctypes() -> set[str]:
    return {target["doctype"] for target in SUPPORTED_DOCUMENT_TEMPLATE_TARGETS}


def is_supported_template_target(doctype: str) -> bool:
    return doctype in get_supported_target_doctypes()


def normalize_field_key(label: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return key or "field"


def get_default_status(template_doc) -> str:
    statuses = list(template_doc.get("statuses") or [])
    for row in statuses:
        if row.get("is_default"):
            return row.get("status_label") or "Draft"
    if statuses:
        return statuses[0].get("status_label") or "Draft"
    return "Draft"


def _require_template_manager_access() -> None:
    import frappe
    from frappe import _

    if frappe.session.user == "Administrator":
        return
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"Orderlift Admin", "System Manager", "Administrator", "Developer"}):
        frappe.throw(_("Only administrators can manage document templates."), frappe.PermissionError)


def _require_supported_reference(reference_doctype: str, reference_name: str | None = None) -> None:
    import frappe
    from frappe import _

    reference_doctype = (reference_doctype or "").strip()
    if not is_supported_template_target(reference_doctype):
        frappe.throw(_("Document templates are not enabled for {0}.").format(reference_doctype))
    if reference_name and not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))


def _as_payload(data) -> dict:
    return json.loads(data or "{}") if isinstance(data, str) else (data or {})


def _template_summary(row) -> dict:
    import frappe

    targets = frappe.get_all(
        "Orderlift Document Template Target",
        filters={"parent": row.name},
        fields=["target_doctype"],
        order_by="idx asc",
    )
    return {
        "name": row.name,
        "template_name": row.template_name,
        "is_active": int(row.is_active or 0),
        "display_order": row.display_order or 0,
        "field_count": frappe.db.count("Orderlift Document Template Field", {"parent": row.name}),
        "status_count": frappe.db.count("Orderlift Document Template Status", {"parent": row.name}),
        "targets": [
            {
                "doctype": target.target_doctype,
                "label": get_document_template_target_label(target.target_doctype),
            }
            for target in targets
        ],
    }


def _template_payload(doc) -> dict:
    return {
        "name": doc.name,
        "template_name": doc.template_name,
        "is_active": int(doc.is_active or 0),
        "display_order": doc.display_order or 0,
        "print_title": doc.print_title or "",
        "print_header": doc.print_header or "",
        "print_footer": doc.print_footer or "",
        "show_signature_block": int(doc.show_signature_block or 0),
        "targets": [
            {"target_doctype": row.target_doctype, "label": get_document_template_target_label(row.target_doctype)}
            for row in doc.targets or []
        ],
        "fields": [
            {
                "field_key": row.field_key,
                "field_label": row.field_label,
                "fieldtype": row.fieldtype,
                "options": row.options or "",
                "is_required": int(row.is_required or 0),
                "default_value": row.default_value or "",
                "display_order": row.display_order or row.idx,
            }
            for row in doc.fields or []
        ],
        "statuses": [
            {
                "status_label": row.status_label,
                "color": row.color or "Gray",
                "is_default": int(row.is_default or 0),
                "display_order": row.display_order or row.idx,
            }
            for row in doc.statuses or []
        ],
    }


@frappe.whitelist()
def get_template_manager_bootstrap() -> dict:
    import frappe

    _require_template_manager_access()
    rows = frappe.get_all(
        "Orderlift Document Template",
        fields=["name", "template_name", "is_active", "display_order"],
        order_by="display_order asc, modified desc",
        limit_page_length=0,
    )
    return {
        "targets": get_supported_document_template_targets(),
        "templates": [_template_summary(row) for row in rows],
    }


@frappe.whitelist()
def get_template(name: str) -> dict:
    import frappe

    _require_template_manager_access()
    return _template_payload(frappe.get_doc("Orderlift Document Template", name))


@frappe.whitelist()
def update_template_targets(name: str, targets: str | list) -> dict:
    import frappe
    from frappe import _

    _require_template_manager_access()
    doc = frappe.get_doc("Orderlift Document Template", name)
    selected = json.loads(targets or "[]") if isinstance(targets, str) else (targets or [])

    doc.set("targets", [])
    for target in selected:
        target_doctype = (target.get("target_doctype") if isinstance(target, dict) else target or "").strip()
        if not target_doctype:
            continue
        if not is_supported_template_target(target_doctype):
            frappe.throw(_("Unsupported template target: {0}").format(target_doctype))
        doc.append("targets", {"target_doctype": target_doctype})

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return get_template_manager_bootstrap()


@frappe.whitelist()
def save_template(payload: str | dict) -> dict:
    import frappe
    from frappe import _
    from frappe.utils import cint

    _require_template_manager_access()
    data = _as_payload(payload)
    template_name = (data.get("template_name") or "").strip()
    if not template_name:
        frappe.throw(_("Template name is required."))

    name = (data.get("name") or "").strip()
    doc = frappe.get_doc("Orderlift Document Template", name) if name else frappe.new_doc("Orderlift Document Template")
    doc.template_name = template_name
    doc.is_active = cint(data.get("is_active"))
    doc.display_order = cint(data.get("display_order")) or 100
    doc.print_title = (data.get("print_title") or "").strip()
    doc.print_header = data.get("print_header") or ""
    doc.print_footer = data.get("print_footer") or ""
    doc.show_signature_block = cint(data.get("show_signature_block"))

    doc.set("targets", [])
    for target in data.get("targets") or []:
        target_doctype = (target.get("target_doctype") or target.get("doctype") or "").strip()
        if not target_doctype:
            continue
        if not is_supported_template_target(target_doctype):
            frappe.throw(_("Unsupported template target: {0}").format(target_doctype))
        doc.append("targets", {"target_doctype": target_doctype})

    doc.set("fields", [])
    seen_keys = set()
    for index, row in enumerate(data.get("fields") or [], start=1):
        field_label = (row.get("field_label") or "").strip()
        if not field_label:
            continue
        field_key = normalize_field_key(row.get("field_key") or field_label)
        base_key = field_key
        counter = 2
        while field_key in seen_keys:
            field_key = f"{base_key}_{counter}"
            counter += 1
        seen_keys.add(field_key)
        doc.append(
            "fields",
            {
                "field_key": field_key,
                "field_label": field_label,
                "fieldtype": row.get("fieldtype") or "Data",
                "options": row.get("options") or "",
                "is_required": cint(row.get("is_required")),
                "default_value": row.get("default_value") or "",
                "display_order": cint(row.get("display_order")) or index,
            },
        )

    doc.set("statuses", [])
    statuses = data.get("statuses") or []
    if not statuses:
        statuses = [{"status_label": "Draft", "color": "Gray", "is_default": 1, "display_order": 1}]
    default_seen = False
    for index, row in enumerate(statuses, start=1):
        status_label = (row.get("status_label") or "").strip()
        if not status_label:
            continue
        is_default = cint(row.get("is_default"))
        if is_default and not default_seen:
            default_seen = True
        elif is_default:
            is_default = 0
        doc.append(
            "statuses",
            {
                "status_label": status_label,
                "color": row.get("color") or "Gray",
                "is_default": is_default,
                "display_order": cint(row.get("display_order")) or index,
            },
        )
    if doc.statuses and not any(row.is_default for row in doc.statuses):
        doc.statuses[0].is_default = 1

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"template": _template_payload(doc), **get_template_manager_bootstrap()}


def _active_templates_for_doctype(reference_doctype: str) -> list:
    import frappe

    template_names = frappe.get_all(
        "Orderlift Document Template Target",
        filters={"target_doctype": reference_doctype},
        pluck="parent",
        order_by="idx asc",
    )
    if not template_names:
        return []
    rows = frappe.get_all(
        "Orderlift Document Template",
        filters={"name": ["in", template_names], "is_active": 1},
        fields=["name", "display_order"],
        order_by="display_order asc, modified desc",
        limit_page_length=0,
    )
    return [frappe.get_doc("Orderlift Document Template", row.name) for row in rows]


def _annex_payload(annex, template_doc) -> dict:
    values = {row.field_key: row.value for row in annex.values} if annex else {}
    return {
        "name": annex.name if annex else "",
        "status": annex.status if annex else get_default_status(template_doc),
        "values": values,
    }


@frappe.whitelist()
def get_annex_bundle(reference_doctype: str, reference_name: str) -> dict:
    import frappe

    _require_supported_reference(reference_doctype, reference_name)
    source = frappe.get_doc(reference_doctype, reference_name)
    source.check_permission("read")
    templates = []
    for template_doc in _active_templates_for_doctype(reference_doctype):
        existing_name = frappe.db.get_value(
            "Orderlift Annex Document",
            {
                "template": template_doc.name,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "docstatus": ["<", 2],
            },
            "name",
        )
        annex = frappe.get_doc("Orderlift Annex Document", existing_name) if existing_name else None
        templates.append({"template": _template_payload(template_doc), "annex": _annex_payload(annex, template_doc)})
    return {"reference_doctype": reference_doctype, "reference_name": reference_name, "templates": templates}


@frappe.whitelist()
def save_annex_document(
    reference_doctype: str,
    reference_name: str,
    template: str,
    status: str | None = None,
    values: str | dict | None = None,
) -> dict:
    import frappe
    from frappe import _

    _require_supported_reference(reference_doctype, reference_name)
    source = frappe.get_doc(reference_doctype, reference_name)
    source.check_permission("write")
    template_doc = frappe.get_doc("Orderlift Document Template", template)
    target_doctypes = {row.target_doctype for row in template_doc.targets or []}
    if reference_doctype not in target_doctypes:
        frappe.throw(_("Template {0} is not enabled for {1}.").format(template_doc.template_name, reference_doctype))

    allowed_statuses = {row.status_label for row in template_doc.statuses or []}
    clean_status = (status or get_default_status(template_doc)).strip()
    if allowed_statuses and clean_status not in allowed_statuses:
        frappe.throw(_("Status {0} is not valid for template {1}.").format(clean_status, template_doc.template_name))

    existing_name = frappe.db.get_value(
        "Orderlift Annex Document",
        {"template": template, "reference_doctype": reference_doctype, "reference_name": reference_name, "docstatus": ["<", 2]},
        "name",
    )
    annex = frappe.get_doc("Orderlift Annex Document", existing_name) if existing_name else frappe.new_doc("Orderlift Annex Document")
    annex.template = template
    annex.template_name = template_doc.template_name
    annex.reference_doctype = reference_doctype
    annex.reference_name = reference_name
    annex.status = clean_status
    annex.company = source.get("company") or ""

    submitted_values = _as_payload(values)
    annex.set("values", [])
    for field in template_doc.fields or []:
        if field.fieldtype in {"Section Break", "Column Break", "HTML"}:
            continue
        annex.append(
            "values",
            {
                "field_key": field.field_key,
                "field_label": field.field_label,
                "fieldtype": field.fieldtype,
                "value": str(submitted_values.get(field.field_key, "")),
                "display_order": field.display_order or field.idx,
            },
        )
    annex.save(ignore_permissions=True)
    frappe.db.commit()
    return {"annex": _annex_payload(annex, template_doc)}
