from __future__ import annotations

import hashlib
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


TECHNICAL_LIST_REVISION_DOCTYPE = "Sales Order Technical List Revision"
READ_ONLY_SNAPSHOT_ORIGINS = {"Opportunity Snapshot", "Quotation Snapshot"}

DOCUMENT_TEMPLATE_TARGET_DOCTYPES = [
    "Opportunity",
    "Quotation",
    "Sales Order",
    "Project",
    "Forecast Load Plan",
    TECHNICAL_LIST_REVISION_DOCTYPE,
]


def get_supported_document_template_targets() -> list[dict[str, str]]:
    """Return the distinct targets configured on active templates."""
    if not hasattr(frappe, "get_all"):
        return []

    active_templates = frappe.get_all(
        "Orderlift Document Template",
        filters={"is_active": 1},
        pluck="name",
        limit_page_length=0,
    )
    if not active_templates:
        return []
    rows = frappe.get_all(
        "Orderlift Document Template Target",
        filters={"parent": ["in", active_templates]},
        fields=["target_doctype", "display_order", "idx"],
        order_by="display_order asc, idx asc",
        limit_page_length=0,
    )
    targets = []
    seen = set()
    for row in rows:
        target_doctype = _row_get(row, "target_doctype")
        if target_doctype and target_doctype not in seen:
            seen.add(target_doctype)
            targets.append({"doctype": target_doctype, "label": get_document_template_target_label(target_doctype)})
    return targets


def get_document_template_target_label(doctype: str) -> str:
    return (doctype or "").strip()


def get_supported_target_doctypes() -> set[str]:
    return {target["doctype"] for target in get_supported_document_template_targets()}


def is_supported_template_target(doctype: str) -> bool:
    return doctype in get_supported_target_doctypes()


def _row_get(row, fieldname: str, default=None):
    if hasattr(row, "get"):
        value = row.get(fieldname)
    else:
        value = getattr(row, fieldname, None)
    return default if value is None else value


def normalize_field_key(label: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return key or "field"


def resolve_template_field_value(source_doc, field) -> str:
    """Return a safe, scalar value from a target document for one template field."""
    source_field = (field.get("source_field") or field.get("field_key") or "").strip()
    if not source_field:
        return ""

    current_doc = source_doc
    for index, fieldname in enumerate(source_field.split(".")):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", fieldname):
            return ""
        value = _get_document_value(current_doc, fieldname)
        if value in (None, ""):
            return ""
        if index == len(source_field.split(".")) - 1:
            if isinstance(value, bool):
                return "1" if value else "0"
            if isinstance(value, (str, int, float)):
                return str(value)
            return ""
        current_doc = _get_linked_document(current_doc, fieldname, value)
        if not current_doc:
            return ""
    return ""


def get_template_prefill_values(template_doc, source_doc, existing_values: dict | None = None) -> dict[str, str]:
    """Build form values without replacing values already saved on an annex."""
    values = dict(existing_values or {})
    for field in template_doc.get("fields") or []:
        if field.get("fieldtype") in {"Section Break", "Column Break", "HTML"}:
            continue
        field_key = field.get("field_key")
        if not field_key or field_key in values:
            continue
        values[field_key] = resolve_template_field_value(source_doc, field) or field.get("default_value") or ""
    return values


def _get_document_value(doc, fieldname: str):
    if fieldname == "name":
        return getattr(doc, "name", None) or (doc.get("name") if hasattr(doc, "get") else None)
    return doc.get(fieldname) if hasattr(doc, "get") else getattr(doc, fieldname, None)


def _get_linked_document(doc, fieldname: str, value):
    meta = getattr(doc, "meta", None)
    field = meta.get_field(fieldname) if meta and hasattr(meta, "get_field") else None
    if not field or field.fieldtype != "Link" or not field.options:
        return None

    import frappe

    if not frappe.has_permission(field.options, "read", doc=value):
        return None
    return frappe.get_doc(field.options, value)


def get_default_status(template_doc) -> str:
    statuses = list(template_doc.get("statuses") or [])
    for row in statuses:
        if row.get("is_default"):
            return row.get("status_label") or ""
    if statuses:
        return statuses[0].get("status_label") or ""
    return ""


def build_template_snapshot(template_doc) -> dict:
    """Build the immutable definition stored with a new annex."""
    return {
        "name": _row_get(template_doc, "name", ""),
        "template_name": _row_get(template_doc, "template_name", ""),
        "print_title": _row_get(template_doc, "print_title", ""),
        "print_header": _row_get(template_doc, "print_header", ""),
        "print_footer": _row_get(template_doc, "print_footer", ""),
        "targets": [
            {
                "target_doctype": _row_get(row, "target_doctype", ""),
                "allow_direct_creation": int(_row_get(row, "allow_direct_creation", 0) or 0),
                "allow_execution_copy": int(_row_get(row, "allow_execution_copy", 0) or 0),
                "allow_import_from_sales_order": int(_row_get(row, "allow_import_from_sales_order", 0) or 0),
                "required_for_revision": int(_row_get(row, "required_for_revision", 0) or 0),
                "must_be_complete": int(_row_get(row, "must_be_complete", 0) or 0),
                "default_selected": int(_row_get(row, "default_selected", 0) or 0),
                "display_order": _row_get(row, "display_order", _row_get(row, "idx", 0)) or 0,
            }
            for row in (_row_get(template_doc, "targets", []) or [])
        ],
        "fields": [
            {
                "field_key": _row_get(row, "field_key", ""),
                "field_label": _row_get(row, "field_label", ""),
                "fieldtype": _row_get(row, "fieldtype", "Data"),
                "options": _row_get(row, "options", ""),
                "source_field": _row_get(row, "source_field", ""),
                "is_required": int(_row_get(row, "is_required", 0) or 0),
                "required_value_mode": _row_get(row, "required_value_mode", "Present") or "Present",
                "default_value": _row_get(row, "default_value", ""),
                "display_order": _row_get(row, "display_order", _row_get(row, "idx", 0)) or 0,
            }
            for row in (_row_get(template_doc, "fields", []) or [])
        ],
        "statuses": [
            {
                "status_label": _row_get(row, "status_label", ""),
                "color": _row_get(row, "color", "Gray") or "Gray",
                "is_default": int(_row_get(row, "is_default", 0) or 0),
                "is_complete": int(_row_get(row, "is_complete", 0) or 0),
                "display_order": _row_get(row, "display_order", _row_get(row, "idx", 0)) or 0,
            }
            for row in (_row_get(template_doc, "statuses", []) or [])
        ],
    }


def parse_template_snapshot(snapshot_json: str | dict | None) -> dict:
    if isinstance(snapshot_json, dict):
        return snapshot_json
    if not snapshot_json:
        return {}
    try:
        value = json.loads(snapshot_json)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def is_required_value_satisfied(value, mode: str = "Present") -> bool:
    if mode == "Checked":
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "checked"}
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None and value != ""


def get_missing_required_values(definition: dict, values: dict) -> list[dict]:
    missing = []
    for field in definition.get("fields") or []:
        if not field.get("is_required") or field.get("fieldtype") in {"Section Break", "Column Break", "HTML"}:
            continue
        mode = field.get("required_value_mode") or "Present"
        if not is_required_value_satisfied(values.get(field.get("field_key")), mode):
            missing.append(
                {
                    "field_key": field.get("field_key") or "",
                    "field_label": field.get("field_label") or field.get("field_key") or "",
                    "required_value_mode": mode,
                }
            )
    return missing


def get_annex_completion_diagnostics(annex, template_doc=None) -> dict:
    snapshot = parse_template_snapshot(_row_get(annex, "template_snapshot_json", ""))
    definition = snapshot or (build_template_snapshot(template_doc) if template_doc else {})
    values = {
        _row_get(row, "field_key", ""): _row_get(row, "value", "")
        for row in (_row_get(annex, "values", []) or [])
    }
    statuses = {row.get("status_label"): row for row in definition.get("statuses") or []}
    status = _row_get(annex, "status", "")
    status_definition = statuses.get(status) or {}
    missing = get_missing_required_values(definition, values) if status_definition.get("is_complete") else []
    return {
        "is_complete": bool(status_definition.get("is_complete") and not missing),
        "status": status,
        "status_is_complete": bool(status_definition.get("is_complete")),
        "status_is_valid": not statuses or status in statuses,
        "missing_required_values": missing,
    }


def _require_template_manager_access() -> None:
    import frappe
    from frappe import _

    if frappe.session.user == "Administrator":
        return
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"Orderlift Admin", "System Manager", "Administrator"}):
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
        fields=["target_doctype", "allow_direct_creation", "allow_execution_copy", "allow_import_from_sales_order", "required_for_revision", "must_be_complete", "default_selected", "display_order"],
        order_by="display_order asc, idx asc",
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
                "allow_direct_creation": int(target.allow_direct_creation or 0),
                "allow_execution_copy": int(target.allow_execution_copy or 0),
                "allow_import_from_sales_order": int(target.allow_import_from_sales_order or 0),
                "required_for_revision": int(target.required_for_revision or 0),
                "must_be_complete": int(target.must_be_complete or 0),
                "default_selected": int(target.default_selected or 0),
                "display_order": target.display_order or 0,
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
            {
                "target_doctype": row.target_doctype,
                "label": get_document_template_target_label(row.target_doctype),
                "allow_direct_creation": int(row.allow_direct_creation or 0),
                "allow_execution_copy": int(row.allow_execution_copy or 0),
                "allow_import_from_sales_order": int(row.allow_import_from_sales_order or 0),
                "required_for_revision": int(row.required_for_revision or 0),
                "must_be_complete": int(row.must_be_complete or 0),
                "default_selected": int(row.default_selected or 0),
                "display_order": row.display_order or row.idx,
            }
            for row in doc.targets or []
        ],
        "fields": [
            {
                "field_key": row.field_key,
                "field_label": row.field_label,
                "fieldtype": row.fieldtype,
                "options": row.options or "",
                "source_field": row.get("source_field") or "",
                "is_required": int(row.is_required or 0),
                "required_value_mode": row.required_value_mode or "Present",
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
                "is_complete": int(row.is_complete or 0),
                "display_order": row.display_order or row.idx,
            }
            for row in doc.statuses or []
        ],
    }


def _template_payload_from_definition(definition: dict) -> dict:
    """Render an existing annex from its frozen template definition."""
    return {
        "name": definition.get("name") or "",
        "template_name": definition.get("template_name") or definition.get("name") or "",
        "is_active": 0,
        "display_order": definition.get("display_order") or 0,
        "print_title": definition.get("print_title") or "",
        "print_header": definition.get("print_header") or "",
        "print_footer": definition.get("print_footer") or "",
        "show_signature_block": int(definition.get("show_signature_block") or 0),
        "targets": [
            {
                **row,
                "label": get_document_template_target_label(row.get("target_doctype") or ""),
            }
            for row in definition.get("targets") or []
        ],
        "fields": list(definition.get("fields") or []),
        "statuses": list(definition.get("statuses") or []),
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
        "available_targets": DOCUMENT_TEMPLATE_TARGET_DOCTYPES,
        "templates": [_template_summary(row) for row in rows],
    }


@frappe.whitelist()
def get_template(name: str) -> dict:
    import frappe

    _require_template_manager_access()
    return _template_payload(frappe.get_doc("Orderlift Document Template", name))


@frappe.whitelist()
def delete_template(name: str) -> dict:
    """Delete only templates that have never produced a historical annex."""
    import frappe
    from frappe import _

    _require_template_manager_access()
    template = frappe.get_doc("Orderlift Document Template", name)
    annex_count = frappe.db.count("Orderlift Annex Document", {"template": template.name})
    if annex_count:
        frappe.throw(
            _("This template is referenced by {0} annex document(s) and cannot be deleted.").format(annex_count)
        )
    frappe.delete_doc("Orderlift Document Template", template.name, force=1, ignore_permissions=True)
    frappe.db.commit()
    return {"template_name": template.template_name, "annex_count": 0}


@frappe.whitelist()
def update_template_targets(name: str, targets: str | list) -> dict:
    import frappe
    from frappe import _

    _require_template_manager_access()
    doc = frappe.get_doc("Orderlift Document Template", name)
    selected = json.loads(targets or "[]") if isinstance(targets, str) else (targets or [])

    existing = {
        row.target_doctype: {
            "target_doctype": row.target_doctype,
            "allow_direct_creation": row.allow_direct_creation,
            "allow_execution_copy": row.allow_execution_copy,
            "allow_import_from_sales_order": row.allow_import_from_sales_order,
            "required_for_revision": row.required_for_revision,
            "must_be_complete": row.must_be_complete,
            "default_selected": row.default_selected,
            "display_order": row.display_order,
        }
        for row in doc.targets or []
    }
    doc.set("targets", [])
    for target in selected:
        target_doctype = (target.get("target_doctype") if isinstance(target, dict) else target or "").strip()
        if not target_doctype:
            continue
        if not frappe.db.exists("DocType", target_doctype):
            frappe.throw(_("Target DocType {0} was not found.").format(target_doctype))
        values = existing.get(target_doctype, {"target_doctype": target_doctype})
        values["target_doctype"] = target_doctype
        doc.append("targets", values)

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
    doc.show_signature_block = 0

    doc.set("targets", [])
    seen_targets = set()
    for index, target in enumerate(data.get("targets") or [], start=1):
        target_doctype = (target.get("target_doctype") or target.get("doctype") or "").strip()
        if not target_doctype:
            frappe.throw(_("Every target must have a DocType."))
        if target_doctype in seen_targets:
            frappe.throw(_("Target DocType {0} is duplicated.").format(target_doctype))
        if not frappe.db.exists("DocType", target_doctype):
            frappe.throw(_("Target DocType {0} was not found.").format(target_doctype))
        seen_targets.add(target_doctype)
        doc.append(
            "targets",
            {
                "target_doctype": target_doctype,
                "allow_direct_creation": cint(target.get("allow_direct_creation", 1)),
                "allow_execution_copy": cint(target.get("allow_execution_copy")),
                "allow_import_from_sales_order": cint(target.get("allow_import_from_sales_order")),
                "required_for_revision": cint(target.get("required_for_revision")),
                "must_be_complete": cint(target.get("must_be_complete")),
                "default_selected": cint(target.get("default_selected")),
                "display_order": cint(target.get("display_order")) or index,
            },
        )
    if not doc.targets:
        frappe.throw(_("At least one target DocType is required."))

    doc.set("fields", [])
    seen_keys = set()
    for index, row in enumerate(data.get("fields") or [], start=1):
        field_label = (row.get("field_label") or "").strip()
        if not field_label:
            frappe.throw(_("Every template field must have a label."))
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
                "source_field": (row.get("source_field") or "").strip(),
                "is_required": cint(row.get("is_required")),
                "required_value_mode": "Checked"
                if row.get("fieldtype") == "Check" and row.get("required_value_mode") == "Checked"
                else "Present",
                "default_value": row.get("default_value") or "",
                "display_order": cint(row.get("display_order")) or index,
            },
        )

    doc.set("statuses", [])
    statuses = data.get("statuses") or []
    if not statuses:
        frappe.throw(_("At least one status is required."))
    default_seen = False
    seen_statuses = set()
    for index, row in enumerate(statuses, start=1):
        status_label = (row.get("status_label") or "").strip()
        if not status_label:
            frappe.throw(_("Every status must have a label."))
        if status_label in seen_statuses:
            frappe.throw(_("Status {0} is duplicated.").format(status_label))
        seen_statuses.add(status_label)
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
                "is_complete": cint(row.get("is_complete")),
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
        order_by="display_order asc, idx asc",
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


def _annex_payload(annex, template_doc, source_doc) -> dict:
    values = {row.field_key: row.value for row in annex.values} if annex else {}
    definition = _template_definition_for_annex(annex, template_doc) if annex else template_doc
    return {
        "name": annex.name if annex else "",
        "status": annex.status if annex else get_default_status(template_doc),
        "origin": annex.origin if annex else "Native",
        "is_complete": int(annex.is_complete or 0) if annex else 0,
        "completed_by": annex.completed_by if annex else "",
        "completed_on": annex.completed_on if annex else "",
        "is_frozen": int(annex.is_frozen or 0) if annex else 0,
        "content_hash": annex.content_hash if annex else "",
        "modified": annex.modified if annex else "",
        "values": get_template_prefill_values(definition, source_doc, values),
    }


def _template_definition_for_annex(annex, template_doc=None) -> dict:
    snapshot = parse_template_snapshot(_row_get(annex, "template_snapshot_json", ""))
    if snapshot:
        return snapshot
    if template_doc is None and _row_get(annex, "template"):
        import frappe

        template_doc = frappe.get_doc("Orderlift Document Template", annex.template)
    return build_template_snapshot(template_doc) if template_doc else {}


def _target_definition(definition: dict, reference_doctype: str) -> dict:
    return next(
        (row for row in definition.get("targets") or [] if row.get("target_doctype") == reference_doctype),
        {},
    )


def _target_allows_direct_creation(template_doc, reference_doctype: str) -> bool:
    target = _target_definition(build_template_snapshot(template_doc), reference_doctype)
    return bool(_row_get(template_doc, "is_active", 0) and target.get("allow_direct_creation"))


def _annex_is_read_only(annex) -> bool:
    return bool(
        annex
        and (
            int(_row_get(annex, "is_frozen", 0) or 0)
            or _row_get(annex, "origin", "") in READ_ONLY_SNAPSHOT_ORIGINS
        )
    )


def _is_revision_owned(annex, definition: dict) -> bool:
    if _row_get(annex, "reference_doctype", "") != TECHNICAL_LIST_REVISION_DOCTYPE:
        return False
    if definition.get("revision_owned"):
        return True
    target = _target_definition(definition, _row_get(annex, "reference_doctype", ""))
    return any(
        target.get(fieldname)
        for fieldname in (
            "allow_direct_creation",
            "allow_execution_copy",
            "allow_import_from_sales_order",
            "required_for_revision",
            "must_be_complete",
            "default_selected",
        )
    )


def _make_reference_key(reference_doctype: str, reference_name: str, template: str, source_annex: str = "") -> str:
    identity = json.dumps(
        [reference_doctype or "", reference_name or "", template or "", source_annex or "direct"],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def validate_annex_document(annex, deleting: bool = False) -> None:
    import frappe
    from frappe import _
    from frappe.utils import now_datetime

    reference_doctype = (_row_get(annex, "reference_doctype", "") or "").strip()
    reference_name = (_row_get(annex, "reference_name", "") or "").strip()
    if not frappe.db.exists("DocType", reference_doctype):
        frappe.throw(_("Reference DocType {0} was not found.").format(reference_doctype))
    if not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))

    template_doc = frappe.get_doc("Orderlift Document Template", annex.template)
    if not _row_get(annex, "template_snapshot_json") and annex.is_new():
        annex.template_snapshot_json = json.dumps(build_template_snapshot(template_doc), sort_keys=True, default=str)
    definition = _template_definition_for_annex(annex, template_doc)
    target = _target_definition(definition, reference_doctype)
    if not target:
        frappe.throw(_("Template {0} is not enabled for {1}.").format(template_doc.template_name, reference_doctype))

    if _is_revision_owned(annex, definition):
        reference_docstatus = int(frappe.db.get_value(reference_doctype, reference_name, "docstatus") or 0)
        if reference_docstatus != 0 and not getattr(annex.flags, "annex_freeze", False):
            frappe.throw(_("Annexes owned by a non-draft revision are immutable."))

    if deleting:
        return

    annex.template_name = definition.get("template_name") or template_doc.template_name
    annex.origin = annex.origin or "Native"
    annex.status = annex.status or get_default_status(definition)
    statuses = {row.get("status_label"): row for row in definition.get("statuses") or []}
    if statuses and annex.status not in statuses:
        frappe.throw(_("Status {0} is not valid for this annex definition.").format(annex.status))

    diagnostics = get_annex_completion_diagnostics(annex, template_doc)
    if statuses.get(annex.status, {}).get("is_complete") and diagnostics["missing_required_values"]:
        labels = ", ".join(row["field_label"] for row in diagnostics["missing_required_values"])
        frappe.throw(_("Complete the required annex values: {0}.").format(labels))

    was_complete = False
    if not annex.is_new():
        previous = annex.get_doc_before_save()
        was_complete = bool(previous and previous.is_complete)
    annex.is_complete = int(diagnostics["is_complete"])
    if annex.is_complete and not was_complete:
        annex.completed_by = frappe.session.user
        annex.completed_on = now_datetime()
    elif not annex.is_complete:
        annex.completed_by = None
        annex.completed_on = None
    if annex.is_new() and not annex.reference_key:
        annex.reference_key = _make_reference_key(
            reference_doctype,
            reference_name,
            annex.template,
            annex.source_annex or "",
        )


@frappe.whitelist()
def get_annex_bundle(reference_doctype: str, reference_name: str, annex_name: str | None = None) -> dict:
    import frappe

    annex_name = (annex_name or "").strip()
    if not annex_name:
        _require_supported_reference(reference_doctype, reference_name)
    elif not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))
    source = frappe.get_doc(reference_doctype, reference_name)
    source.check_permission("read")
    if annex_name:
        annex = frappe.get_doc("Orderlift Annex Document", annex_name)
        annex.check_permission("read")
        if annex.reference_doctype != reference_doctype or annex.reference_name != reference_name:
            frappe.throw(_("The requested annex does not belong to this source document."))
        template_doc = frappe.get_doc("Orderlift Document Template", annex.template)
        definition = _template_definition_for_annex(annex, template_doc)
        return {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "read_only": bool(
                _annex_is_read_only(annex)
                or (
                    reference_doctype in {"Quotation", "Sales Order", TECHNICAL_LIST_REVISION_DOCTYPE}
                    and int(source.docstatus or 0) != 0
                )
                or not source.has_permission("write")
            ),
            "templates": [
                {
                    "template": _template_payload_from_definition(definition),
                    "annex": _annex_payload(annex, template_doc, source),
                }
            ],
        }
    templates = []
    for template_doc in _active_templates_for_doctype(reference_doctype):
        existing_name = frappe.db.get_value(
            "Orderlift Annex Document",
            {
                "template": template_doc.name,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "source_annex": ["is", "not set"],
                "docstatus": ["<", 2],
            },
            "name",
        )
        annex = frappe.get_doc("Orderlift Annex Document", existing_name) if existing_name else None
        if not annex and not _target_allows_direct_creation(template_doc, reference_doctype):
            continue
        templates.append({"template": _template_payload(template_doc), "annex": _annex_payload(annex, template_doc, source)})
    return {
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "read_only": (
            reference_doctype in {"Quotation", "Sales Order", TECHNICAL_LIST_REVISION_DOCTYPE}
            and int(source.docstatus or 0) != 0
        )
        or not source.has_permission("write")
        or any(_annex_is_read_only(row["annex"]) for row in templates),
        "templates": templates,
    }


@frappe.whitelist()
def save_annex_document(
    reference_doctype: str,
    reference_name: str,
    template: str,
    status: str | None = None,
    values: str | dict | None = None,
    annex_name: str | None = None,
    expected_modified: str | None = None,
    expect_absent: int = 0,
) -> dict:
    import frappe
    from frappe import _
    from frappe.utils import cint
    from orderlift.annex_chain import lock_annex_reference

    annex_name = (annex_name or "").strip()
    if not annex_name:
        _require_supported_reference(reference_doctype, reference_name)
    elif not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))
    source = frappe.get_doc(reference_doctype, reference_name)
    source.check_permission("write")
    lock_annex_reference(reference_doctype, reference_name)
    source.reload()
    template_doc = frappe.get_doc("Orderlift Document Template", template)

    existing_name = annex_name or frappe.db.get_value(
        "Orderlift Annex Document",
        {
            "template": template,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "source_annex": ["is", "not set"],
            "docstatus": ["<", 2],
        },
        "name",
    )
    annex = frappe.get_doc("Orderlift Annex Document", existing_name) if existing_name else frappe.new_doc("Orderlift Annex Document")
    if cint(expect_absent) and existing_name:
        frappe.throw(_("This annex was created after it was opened. Reload it before saving."))
    if existing_name and (
        annex.template != template
        or annex.reference_doctype != reference_doctype
        or annex.reference_name != reference_name
    ):
        frappe.throw(_("The requested annex does not match this document and template."))
    if expected_modified and existing_name and str(annex.modified) != str(expected_modified):
        frappe.throw(_("This annex changed after it was opened. Reload it before saving."))
    if existing_name and _annex_is_read_only(annex):
        frappe.throw(_("Synchronized and frozen annexes are read-only."))
    if not existing_name and not _target_allows_direct_creation(template_doc, reference_doctype):
        frappe.throw(_("This template does not allow direct creation for {0}.").format(reference_doctype))
    annex.template = template
    annex.template_name = template_doc.template_name
    annex.reference_doctype = reference_doctype
    annex.reference_name = reference_name
    if annex.is_new():
        annex.origin = "Native"
        annex.template_snapshot_json = json.dumps(build_template_snapshot(template_doc), sort_keys=True, default=str)
    definition = _template_definition_for_annex(annex, template_doc)
    annex.status = (status or annex.status or get_default_status(definition)).strip()
    annex.company = source.get("company") or ""

    submitted_values = _as_payload(values)
    existing_values = {row.field_key: row.value for row in annex.values} if not annex.is_new() else {}
    resolved_values = get_template_prefill_values(definition, source, existing_values)
    resolved_values.update(submitted_values)
    annex.set("values", [])
    for field in definition.get("fields") or []:
        if field.get("fieldtype") in {"Section Break", "Column Break", "HTML"}:
            continue
        _append_annex_value(annex, field, resolved_values.get(field.get("field_key"), ""))
    annex.save(ignore_permissions=True)
    return {"annex": _annex_payload(annex, template_doc, source)}


def _file_metadata(value) -> tuple[str, str]:
    import frappe

    value = str(value or "").strip()
    if not value:
        return "", ""
    row = frappe.db.get_value("File", {"file_url": value}, ["name", "content_hash"], as_dict=True)
    if not row and frappe.db.exists("File", value):
        row = frappe.db.get_value("File", value, ["name", "content_hash"], as_dict=True)
    if row:
        frappe.get_doc("File", row.name).check_permission("read")
    return (_row_get(row, "name", ""), _row_get(row, "content_hash", "")) if row else ("", "")


def _append_annex_value(annex, field: dict, value, source_value=None) -> None:
    fieldtype = field.get("fieldtype") or "Data"
    file_name = _row_get(source_value, "file", "") if source_value else ""
    content_hash = _row_get(source_value, "content_hash", "") if source_value else ""
    if fieldtype in {"Attach", "Attach Image", "Signature"} and not file_name:
        file_name, content_hash = _file_metadata(value)
    metadata = {
        "field_key": field.get("field_key") or "",
        "field_label": field.get("field_label") or "",
        "fieldtype": fieldtype,
        "options": field.get("options") or "",
        "is_required": int(field.get("is_required") or 0),
        "required_value_mode": field.get("required_value_mode") or "Present",
        "display_order": field.get("display_order") or 0,
    }
    annex.append(
        "values",
        {
            "field_key": metadata["field_key"],
            "field_label": metadata["field_label"],
            "fieldtype": metadata["fieldtype"],
            "value": "" if value is None else str(value),
            "file": file_name,
            "content_hash": content_hash,
            "captured_options": metadata["options"],
            "captured_is_required": metadata["is_required"],
            "captured_required_value_mode": metadata["required_value_mode"],
            "captured_metadata_json": json.dumps(metadata, sort_keys=True),
            "display_order": metadata["display_order"],
        },
    )


def _revision_reference(
    reference_doctype: str,
    reference_name: str,
    permission_type: str = "write",
):
    import frappe
    from frappe import _

    if reference_doctype != TECHNICAL_LIST_REVISION_DOCTYPE:
        return None
    if not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))
    revision = frappe.get_doc(reference_doctype, reference_name)
    revision.check_permission(permission_type)
    if permission_type == "write":
        from orderlift.annex_chain import lock_annex_reference

        lock_annex_reference(reference_doctype, reference_name)
        revision.reload()
        if int(revision.docstatus or 0) != 0:
            frappe.throw(_("Technical annexes can only be changed on a draft revision."))
    return revision


def _revision_target(template_doc, reference_doctype: str) -> dict:
    return _target_definition(build_template_snapshot(template_doc), reference_doctype)


def _existing_revision_annex(reference_doctype: str, reference_name: str, template: str, source_annex: str = ""):
    import frappe

    reference_key = _make_reference_key(reference_doctype, reference_name, template, source_annex)
    name = frappe.db.get_value("Orderlift Annex Document", {"reference_key": reference_key}, "name")
    return frappe.get_doc("Orderlift Annex Document", name) if name else None


def _create_direct_revision_annex(revision, template_doc):
    import frappe

    existing = _existing_revision_annex(revision.doctype, revision.name, template_doc.name)
    if existing:
        return existing
    annex = frappe.new_doc("Orderlift Annex Document")
    annex.template = template_doc.name
    annex.template_name = template_doc.template_name
    annex.reference_doctype = revision.doctype
    annex.reference_name = revision.name
    annex.reference_key = _make_reference_key(revision.doctype, revision.name, template_doc.name)
    annex.origin = "Native"
    annex.company = revision.get("company") or ""
    definition = build_template_snapshot(template_doc)
    definition["revision_owned"] = True
    annex.template_snapshot_json = json.dumps(definition, sort_keys=True, default=str)
    annex.status = get_default_status(definition)
    initial_values = get_template_prefill_values(definition, revision)
    for field in definition.get("fields") or []:
        if field.get("fieldtype") not in {"Section Break", "Column Break", "HTML"}:
            _append_annex_value(annex, field, initial_values.get(field.get("field_key"), ""))
    annex.insert(ignore_permissions=True)
    return annex


def _clone_revision_annex(revision, source_annex, template_doc):
    import frappe
    from orderlift.annex_chain import compute_annex_content_hash

    existing = _existing_revision_annex(
        revision.doctype,
        revision.name,
        template_doc.name,
        source_annex.name,
    )
    if existing:
        return existing
    definition = _template_definition_for_annex(source_annex, template_doc)
    current_target = _revision_target(template_doc, revision.doctype)
    definition["targets"] = [
        row for row in definition.get("targets") or [] if row.get("target_doctype") != revision.doctype
    ]
    definition["targets"].append(current_target)
    definition["revision_owned"] = True
    annex = frappe.new_doc("Orderlift Annex Document")
    annex.template = template_doc.name
    annex.template_name = definition.get("template_name") or source_annex.template_name
    annex.reference_doctype = revision.doctype
    annex.reference_name = revision.name
    annex.reference_key = _make_reference_key(revision.doctype, revision.name, template_doc.name, source_annex.name)
    annex.origin = "Sales Order Snapshot"
    annex.source_annex = source_annex.name
    annex.source_reference_doctype = source_annex.reference_doctype
    annex.source_reference_name = source_annex.reference_name
    annex.source_modified = source_annex.modified
    annex.source_content_hash = _row_get(source_annex, "content_hash", "") or compute_annex_content_hash(
        source_annex
    )
    annex.company = revision.get("company") or source_annex.company or ""
    annex.template_snapshot_json = json.dumps(definition, sort_keys=True, default=str)
    # Imported CRM annexes become editable draft snapshots. Their source status
    # remains available through source_annex without pre-approving the revision.
    annex.status = get_default_status(definition)
    source_values = {row.field_key: row for row in source_annex.values or []}
    for field in definition.get("fields") or []:
        if field.get("fieldtype") in {"Section Break", "Column Break", "HTML"}:
            continue
        source_value = source_values.get(field.get("field_key"))
        _append_annex_value(annex, field, _row_get(source_value, "value", ""), source_value)
    annex.insert(ignore_permissions=True)
    _copy_revision_annex_files(annex)
    return annex


def _copy_revision_annex_files(annex) -> None:
    import frappe
    from frappe.utils.file_manager import save_file

    changed = False
    for value in annex.values or []:
        if not value.file or not frappe.db.exists("File", value.file):
            continue
        source_doc = frappe.get_doc("File", value.file)
        source = source_doc.as_dict()
        existing = frappe.db.get_value(
            "File",
            {
                "attached_to_doctype": "Orderlift Annex Document",
                "attached_to_name": annex.name,
                "file_url": source.file_url,
                "is_folder": 0,
            },
            "name",
        )
        if not existing:
            file_doc = save_file(
                source.file_name,
                source_doc.get_content(),
                "Orderlift Annex Document",
                annex.name,
                is_private=int(source.is_private or 0),
            )
            existing = file_doc.name
        else:
            file_doc = frappe.get_doc("File", existing)
        value.file = existing
        value.content_hash = source.content_hash or value.content_hash
        value.value = file_doc.file_url
        changed = True
    if changed:
        annex.save(ignore_permissions=True)


@frappe.whitelist()
def create_direct_technical_annex(reference_doctype: str, reference_name: str, template: str) -> dict:
    import frappe
    from frappe import _

    revision = _revision_reference(reference_doctype, reference_name)
    if revision is None:
        return {"available": False, "annex": ""}
    template_doc = frappe.get_doc("Orderlift Document Template", template)
    target = _revision_target(template_doc, reference_doctype)
    if not template_doc.is_active or not target or not target.get("allow_direct_creation"):
        frappe.throw(_("This template does not allow direct creation for {0}.").format(reference_doctype))
    annex = _create_direct_revision_annex(revision, template_doc)
    return {"available": True, "annex": annex.name}


@frappe.whitelist()
def clone_selected_sales_order_annexes(
    reference_doctype: str,
    reference_name: str,
    annex_names: str | list,
) -> dict:
    import frappe
    from frappe import _

    revision = _revision_reference(reference_doctype, reference_name)
    if revision is None:
        return {"available": False, "annexes": []}
    selected = json.loads(annex_names or "[]") if isinstance(annex_names, str) else (annex_names or [])
    created = []
    for name in dict.fromkeys(selected):
        source_annex = frappe.get_doc("Orderlift Annex Document", name)
        source_annex.check_permission("read")
        if source_annex.reference_doctype != "Sales Order":
            frappe.throw(_("Annex {0} is not owned by a Sales Order.").format(source_annex.name))
        if source_annex.reference_name != revision.sales_order:
            frappe.throw(_("Annex {0} is not owned by this revision's Sales Order.").format(source_annex.name))
        template_doc = frappe.get_doc("Orderlift Document Template", source_annex.template)
        target = _revision_target(template_doc, reference_doctype)
        if not template_doc.is_active or not target or not (
            target.get("allow_execution_copy") or target.get("allow_import_from_sales_order")
        ):
            frappe.throw(_("Template {0} does not allow Sales Order import for {1}.").format(template_doc.template_name, reference_doctype))
        created.append(_clone_revision_annex(revision, source_annex, template_doc).name)
    return {"available": True, "annexes": created}


def _eligible_sales_order_annexes(reference_doctype: str, sales_order_name: str | None) -> list[dict]:
    import frappe

    if not sales_order_name or not frappe.db.exists("Sales Order", sales_order_name):
        return []
    frappe.get_doc("Sales Order", sales_order_name).check_permission("read")
    rows = frappe.get_all(
        "Orderlift Annex Document",
        filters={"reference_doctype": "Sales Order", "reference_name": sales_order_name, "docstatus": ["<", 2]},
        fields=["name", "template", "template_name", "status", "is_complete", "modified"],
        order_by="creation asc",
        limit_page_length=0,
    )
    eligible = []
    for row in rows:
        template_doc = frappe.get_doc("Orderlift Document Template", row.template)
        target = _revision_target(template_doc, reference_doctype)
        if target.get("allow_execution_copy") or target.get("allow_import_from_sales_order"):
            eligible.append(
                {
                    "annex": row.name,
                    "template": row.template,
                    "template_name": row.template_name,
                    "status": row.status,
                    "is_complete": int(row.is_complete or 0),
                    "source_modified": row.modified,
                    "default_selected": int(target.get("default_selected") or 0),
                    "display_order": target.get("display_order") or 0,
                }
            )
    return sorted(eligible, key=lambda row: (row["display_order"], row["template_name"], row["annex"]))


def _linked_sales_order(revision, explicit_name: str | None = None) -> str:
    import frappe
    from frappe import _

    linked_name = (revision.get("sales_order") or "").strip()
    explicit_name = (explicit_name or "").strip()
    if explicit_name and explicit_name != linked_name:
        frappe.throw(_("The Sales Order must match the technical revision."))
    return linked_name


def _revision_annex_manifest(reference_doctype: str, reference_name: str) -> list[dict]:
    import frappe

    return frappe.get_all(
        "Orderlift Annex Document",
        filters={"reference_doctype": reference_doctype, "reference_name": reference_name, "docstatus": ["<", 2]},
        fields=["name", "template", "template_name", "origin", "source_annex", "status", "is_complete", "completed_by", "completed_on"],
        order_by="creation asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def initialize_technical_revision_manifest(
    reference_doctype: str,
    reference_name: str,
    sales_order_name: str | None = None,
    create_defaults: int = 1,
) -> dict:
    import frappe
    from frappe.utils import cint

    revision = _revision_reference(reference_doctype, reference_name)
    if revision is None:
        return {"available": False, "direct_templates": [], "sales_order_annexes": [], "annexes": []}
    direct_templates = []
    created = []
    for template_doc in _active_templates_for_doctype(reference_doctype):
        target = _revision_target(template_doc, reference_doctype)
        if not target.get("allow_direct_creation"):
            continue
        direct_templates.append(
            {
                "template": template_doc.name,
                "template_name": template_doc.template_name,
                "required_for_revision": int(target.get("required_for_revision") or 0),
                "must_be_complete": int(target.get("must_be_complete") or 0),
                "default_selected": int(target.get("default_selected") or 0),
                "display_order": target.get("display_order") or 0,
            }
        )
        if cint(create_defaults) and target.get("default_selected"):
            created.append(_create_direct_revision_annex(revision, template_doc).name)
    source_annexes = _eligible_sales_order_annexes(
        reference_doctype,
        _linked_sales_order(revision, sales_order_name),
    )
    if cint(create_defaults):
        selected = [row["annex"] for row in source_annexes if row["default_selected"]]
        for source_name in selected:
            source = frappe.get_doc("Orderlift Annex Document", source_name)
            source.check_permission("read")
            created.append(_clone_revision_annex(revision, source, frappe.get_doc("Orderlift Document Template", source.template)).name)
    return {
        "available": True,
        "direct_templates": sorted(direct_templates, key=lambda row: (row["display_order"], row["template_name"])),
        "sales_order_annexes": source_annexes,
        "annexes": _revision_annex_manifest(reference_doctype, reference_name),
        "created_annexes": list(dict.fromkeys(created)),
        "diagnostics": get_technical_revision_completion_diagnostics(reference_doctype, reference_name),
    }


@frappe.whitelist()
def get_technical_revision_completion_diagnostics(reference_doctype: str, reference_name: str) -> dict:
    import frappe

    revision = _revision_reference(reference_doctype, reference_name, permission_type="read")
    if revision is None:
        return {"available": False, "is_complete": False, "missing_templates": [], "incomplete_annexes": []}
    annex_names = frappe.get_all(
        "Orderlift Annex Document",
        filters={"reference_doctype": reference_doctype, "reference_name": reference_name, "docstatus": ["<", 2]},
        pluck="name",
        limit_page_length=0,
    )
    annexes = [frappe.get_doc("Orderlift Annex Document", name) for name in annex_names]
    by_template = {}
    incomplete_annexes = []
    for annex in annexes:
        by_template.setdefault(annex.template, []).append(annex)
        diagnostics = get_annex_completion_diagnostics(annex)
        definition = _template_definition_for_annex(annex)
        target = _target_definition(definition, reference_doctype)
        if target.get("must_be_complete") and not diagnostics["is_complete"]:
            incomplete_annexes.append(
                {
                    "annex": annex.name,
                    "template": annex.template,
                    "template_name": annex.template_name,
                    "status": diagnostics["status"],
                    "status_is_complete": diagnostics["status_is_complete"],
                    "missing_required_values": diagnostics["missing_required_values"],
                }
            )
    missing_templates = []
    for template_doc in _active_templates_for_doctype(reference_doctype):
        target = _revision_target(template_doc, reference_doctype)
        if target.get("required_for_revision") and template_doc.name not in by_template:
            missing_templates.append(
                {"template": template_doc.name, "template_name": template_doc.template_name}
            )
    return {
        "available": True,
        "is_complete": not missing_templates and not incomplete_annexes,
        "annex_count": len(annexes),
        "missing_templates": missing_templates,
        "incomplete_annexes": incomplete_annexes,
    }


# Short aliases keep server integrations readable while the technical-list module is developed independently.
clone_sales_order_annexes_to_revision = clone_selected_sales_order_annexes
get_revision_annex_completion_diagnostics = get_technical_revision_completion_diagnostics
