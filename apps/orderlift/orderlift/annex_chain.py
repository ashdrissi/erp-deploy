from __future__ import annotations

import hashlib
import json
import re

try:
    import frappe
    from frappe import _
    from frappe.utils import cint, now_datetime
except Exception:  # pragma: no cover - keeps pure hash helpers importable outside Frappe.
    class _FrappeStub:
        def whitelist(self, *args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda fn: fn

    frappe = _FrappeStub()

    def _(value):
        return value

    def cint(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def now_datetime():
        from datetime import datetime

        return datetime.now()


ANNEX_DOCTYPE = "Orderlift Annex Document"
TEMPLATE_DOCTYPE = "Orderlift Document Template"
TECHNICAL_LIST_DOCTYPE = "Sales Order Technical List"
TECHNICAL_REVISION_DOCTYPE = "Sales Order Technical List Revision"

CHAIN_DOCTYPES = {
    "Opportunity",
    "Quotation",
    "Sales Order",
    "Project",
    TECHNICAL_REVISION_DOCTYPE,
}
LOCKED_REFERENCE_DOCTYPES = {"Quotation", "Sales Order", TECHNICAL_REVISION_DOCTYPE}
SYNCED_ORIGINS = {"Opportunity Snapshot", "Quotation Snapshot"}
PROVENANCE_FIELDS = (
    "template",
    "company",
    "reference_doctype",
    "reference_name",
    "reference_key",
    "origin",
    "source_annex",
    "source_reference_doctype",
    "source_reference_name",
    "source_modified",
    "source_content_hash",
    "template_snapshot_json",
)


def after_migrate() -> None:
    """Install stable annex workspaces without depending on Technical List activation."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    managed = {"custom_fiches_annexes_tab", "custom_fiches_annexes_html"}

    def terminal_anchor(doctype: str, _preferred: str) -> str:
        # Always anchor to the last field of the rendered form. A Tab Break
        # inserted mid-form captures every later section, so the annexes tab
        # must land at the very end and start its own tab.
        meta = frappe.get_meta(doctype)
        return next(
            (field.fieldname for field in reversed(meta.fields) if field.fieldname not in managed),
            "name",
        )

    create_custom_fields(
        {
            "Quotation": [
                {
                    "fieldname": "custom_fiches_annexes_tab",
                    "label": "Fiches annexes",
                    "fieldtype": "Tab Break",
                    "insert_after": terminal_anchor("Quotation", "custom_commercial_presentation_snapshot"),
                },
                {
                    "fieldname": "custom_fiches_annexes_html",
                    "label": "Fiches annexes",
                    "fieldtype": "HTML",
                    "insert_after": "custom_fiches_annexes_tab",
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_fiches_annexes_tab",
                    "label": "Fiches annexes",
                    "fieldtype": "Tab Break",
                    "insert_after": terminal_anchor("Sales Order", "custom_technical_list_html"),
                },
                {
                    "fieldname": "custom_fiches_annexes_html",
                    "label": "Fiches annexes",
                    "fieldtype": "HTML",
                    "insert_after": "custom_fiches_annexes_tab",
                },
            ],
            "Project": [
                {
                    "fieldname": "custom_fiches_annexes_tab",
                    "label": "Fiches annexes",
                    "fieldtype": "Tab Break",
                    "insert_after": terminal_anchor("Project", "custom_technical_lists_html"),
                },
                {
                    "fieldname": "custom_fiches_annexes_html",
                    "label": "Fiches annexes",
                    "fieldtype": "HTML",
                    "insert_after": "custom_fiches_annexes_tab",
                },
            ],
        },
        update=True,
    )
    if frappe.db.has_column("Orderlift Document Template Target", "allow_execution_copy"):
        frappe.db.sql(
            """
            UPDATE `tabOrderlift Document Template Target`
            SET allow_execution_copy = 1
            WHERE IFNULL(allow_import_from_sales_order, 0) = 1
              AND IFNULL(allow_execution_copy, 0) = 0
            """
        )
    _backfill_annex_integrity()


def _backfill_annex_integrity() -> None:
    """Capture legacy definitions and hashes before documents enter the new lifecycle."""
    if not _doctype_available(ANNEX_DOCTYPE):
        return

    from orderlift.document_templates import _make_reference_key, build_template_snapshot

    fields = [
        "template_snapshot_json",
        "reference_key",
        "content_hash",
        "is_frozen",
        "frozen_on",
        "frozen_by",
    ]
    if any(not frappe.db.has_column(ANNEX_DOCTYPE, fieldname) for fieldname in fields):
        return

    for name in frappe.get_all(ANNEX_DOCTYPE, pluck="name", order_by="creation asc", limit_page_length=0):
        annex = frappe.get_doc(ANNEX_DOCTYPE, name)
        updates = {}
        if not annex.template_snapshot_json and frappe.db.exists(TEMPLATE_DOCTYPE, annex.template):
            definition = build_template_snapshot(frappe.get_doc(TEMPLATE_DOCTYPE, annex.template))
            annex.template_snapshot_json = json.dumps(definition, sort_keys=True, default=str)
            updates["template_snapshot_json"] = annex.template_snapshot_json

        if not annex.reference_key:
            reference_key = _make_reference_key(
                annex.reference_doctype,
                annex.reference_name,
                annex.template,
                annex.source_annex or "",
            )
            conflict = frappe.db.get_value(
                ANNEX_DOCTYPE,
                {"reference_key": reference_key, "name": ["!=", annex.name]},
                "name",
            )
            if not conflict:
                annex.reference_key = reference_key
                updates["reference_key"] = reference_key

        if _reference_is_locked(annex) and not cint(annex.is_frozen):
            annex.is_frozen = 1
            annex.frozen_on = annex.modified
            annex.frozen_by = annex.modified_by
            updates.update(
                {
                    "is_frozen": 1,
                    "frozen_on": annex.frozen_on,
                    "frozen_by": annex.frozen_by,
                }
            )

        if not annex.content_hash or updates:
            annex.content_hash = compute_annex_content_hash(annex)
            updates["content_hash"] = annex.content_hash
        if updates:
            frappe.db.set_value(ANNEX_DOCTYPE, annex.name, updates, update_modified=False)


def lock_annex_reference(reference_doctype: str, reference_name: str) -> None:
    """Serialize annex writes with submission of the owning document."""
    if not re.fullmatch(r"[A-Za-z0-9 _-]+", reference_doctype or ""):
        frappe.throw(_("Invalid annex reference type."))
    rows = frappe.db.sql(
        f"SELECT name FROM `tab{reference_doctype}` WHERE name = %s FOR UPDATE",
        (reference_name,),
    )
    if not rows:
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))


def _value(row, fieldname: str, default=None):
    if hasattr(row, "get"):
        value = row.get(fieldname)
    else:
        value = getattr(row, fieldname, None)
    return default if value is None else value


def _json_value(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return str(value)
    return parsed


def build_annex_content_payload(annex) -> dict:
    """Return the stable, business-content representation used for freezing."""
    values = []
    for row in _value(annex, "values", []) or []:
        values.append(
            {
                "field_key": _value(row, "field_key", "") or "",
                "field_label": _value(row, "field_label", "") or "",
                "fieldtype": _value(row, "fieldtype", "") or "",
                "value": "" if _value(row, "value") is None else str(_value(row, "value")),
                "file": _value(row, "file", "") or "",
                "content_hash": _value(row, "content_hash", "") or "",
                "captured_options": _value(row, "captured_options", "") or "",
                "captured_is_required": cint(_value(row, "captured_is_required", 0)),
                "captured_required_value_mode": _value(
                    row, "captured_required_value_mode", ""
                )
                or "",
                "captured_metadata": _json_value(_value(row, "captured_metadata_json", "")),
                "display_order": cint(_value(row, "display_order", 0)),
                "idx": cint(_value(row, "idx", 0)),
            }
        )
    values.sort(key=lambda row: (row["display_order"], row["idx"], row["field_key"]))
    return {
        "template": _value(annex, "template", "") or "",
        "template_name": _value(annex, "template_name", "") or "",
        "status": _value(annex, "status", "") or "",
        "is_complete": cint(_value(annex, "is_complete", 0)),
        "completed_by": _value(annex, "completed_by", "") or "",
        "completed_on": str(_value(annex, "completed_on", "") or ""),
        "company": _value(annex, "company", "") or "",
        "reference_doctype": _value(annex, "reference_doctype", "") or "",
        "reference_name": _value(annex, "reference_name", "") or "",
        "origin": _value(annex, "origin", "") or "Native",
        "source_annex": _value(annex, "source_annex", "") or "",
        "source_reference_doctype": _value(annex, "source_reference_doctype", "") or "",
        "source_reference_name": _value(annex, "source_reference_name", "") or "",
        "source_modified": str(_value(annex, "source_modified", "") or ""),
        "source_content_hash": _value(annex, "source_content_hash", "") or "",
        "template_snapshot": _json_value(_value(annex, "template_snapshot_json", "")),
        "values": values,
    }


def compute_annex_content_hash(annex) -> str:
    payload = json.dumps(
        build_annex_content_payload(annex),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _flag(annex, name: str) -> bool:
    return bool(_value(getattr(annex, "flags", {}), name, False))


def _reference_is_locked(annex) -> bool:
    doctype = (_value(annex, "reference_doctype", "") or "").strip()
    name = (_value(annex, "reference_name", "") or "").strip()
    if doctype not in LOCKED_REFERENCE_DOCTYPES or not name or not frappe.db.exists(doctype, name):
        return False
    return cint(frappe.db.get_value(doctype, name, "docstatus")) != 0


def validate_annex_integrity(annex, deleting: bool = False) -> None:
    """Enforce frozen content and stable ownership for the canonical annex."""
    previous = None if annex.is_new() else annex.get_doc_before_save()
    internal_change = _flag(annex, "annex_sync") or _flag(annex, "annex_freeze")

    if deleting:
        if not internal_change and (
            cint(_value(annex, "is_frozen", 0))
            or _reference_is_locked(annex)
            or _value(annex, "origin", "") in SYNCED_ORIGINS
        ):
            frappe.throw(_("Synchronized and frozen annexes cannot be deleted."))
        return

    if previous and not internal_change:
        changed_provenance = any(
            str(_value(previous, fieldname, "") or "")
            != str(_value(annex, fieldname, "") or "")
            for fieldname in PROVENANCE_FIELDS
        )
        if changed_provenance:
            frappe.throw(_("Annex ownership and provenance cannot be changed."))
    elif annex.is_new() and not internal_change and _value(annex, "origin", "") in SYNCED_ORIGINS:
        frappe.throw(_("Synchronized annexes can only be created by the document lifecycle."))

    current_hash = compute_annex_content_hash(annex)
    if (
        previous
        and not internal_change
        and _value(previous, "origin", "") in SYNCED_ORIGINS
        and current_hash
        != (_value(previous, "content_hash", "") or compute_annex_content_hash(previous))
    ):
        frappe.throw(_("Synchronized annexes can only be changed from their source document."))
    if previous and cint(_value(previous, "is_frozen", 0)):
        previous_hash = _value(previous, "content_hash", "") or compute_annex_content_hash(previous)
        if current_hash != previous_hash:
            frappe.throw(_("Frozen annex content cannot be changed."))
        annex.is_frozen = 1
        annex.frozen_on = _value(previous, "frozen_on")
        annex.frozen_by = _value(previous, "frozen_by")

    if _reference_is_locked(annex) and not internal_change:
        if annex.is_new() or not previous or current_hash != (
            _value(previous, "content_hash", "") or compute_annex_content_hash(previous)
        ):
            frappe.throw(_("Annexes owned by a submitted document are immutable."))

    annex.content_hash = current_hash


def freeze_annex(annex, *, frozen_on=None, frozen_by: str | None = None):
    """Freeze one annex idempotently and persist its canonical content hash."""
    if isinstance(annex, str):
        annex = frappe.get_doc(ANNEX_DOCTYPE, annex)
    current_hash = compute_annex_content_hash(annex)
    if cint(_value(annex, "is_frozen", 0)):
        if _value(annex, "content_hash", "") and annex.content_hash != current_hash:
            frappe.throw(_("Frozen annex {0} failed its content hash check.").format(annex.name))
        return annex

    annex.flags.annex_freeze = True
    annex.is_frozen = 1
    annex.frozen_on = frozen_on or now_datetime()
    annex.frozen_by = frozen_by or frappe.session.user
    annex.content_hash = current_hash
    annex.save(ignore_permissions=True)
    return annex


def freeze_reference_annexes(reference_doctype: str, reference_name: str) -> list[str]:
    lock_annex_reference(reference_doctype, reference_name)
    names = frappe.get_all(
        ANNEX_DOCTYPE,
        filters={
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "docstatus": ["<", 2],
        },
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )
    frozen_on = now_datetime()
    for name in names:
        freeze_annex(name, frozen_on=frozen_on)
    return names


def _source_opportunities(quotation) -> list[str]:
    names = []
    opportunity = (_value(quotation, "opportunity", "") or "").strip()
    if opportunity:
        names.append(opportunity)
    names.extend(
        (_value(row, "prevdoc_docname", "") or "").strip()
        for row in (_value(quotation, "items", []) or [])
        if (_value(row, "prevdoc_docname", "") or "").strip()
    )
    return [
        name
        for name in dict.fromkeys(names)
        if frappe.db.exists("Opportunity", name)
    ]


def _source_quotations(sales_order) -> list[str]:
    names = [
        (_value(row, "prevdoc_docname", "") or "").strip()
        for row in (_value(sales_order, "items", []) or [])
        if (_value(row, "prevdoc_docname", "") or "").strip()
    ]
    return [name for name in dict.fromkeys(names) if frappe.db.exists("Quotation", name)]


def _annexes_for_references(references: list[tuple[str, str]]) -> list:
    result = []
    for doctype, name in references:
        if not name or not frappe.has_permission(doctype, "read", doc=name):
            continue
        rows = frappe.get_all(
            ANNEX_DOCTYPE,
            filters={
                "reference_doctype": doctype,
                "reference_name": name,
                "docstatus": ["<", 2],
            },
            fields=["name"],
            order_by="creation asc",
            limit_page_length=0,
        )
        result.extend(frappe.get_doc(ANNEX_DOCTYPE, row.name) for row in rows)
    return result


def _definition_for_snapshot(source_annex, target_doctype: str, *, require_execution=False) -> dict:
    from orderlift.document_templates import (
        _target_definition,
        _template_definition_for_annex,
        build_template_snapshot,
    )

    template = frappe.get_doc(TEMPLATE_DOCTYPE, source_annex.template)
    current_definition = build_template_snapshot(template)
    current_target = _target_definition(current_definition, target_doctype)
    if require_execution and not (
        current_target.get("allow_import_from_sales_order")
        or current_target.get("allow_execution_copy")
    ):
        frappe.throw(
            _("Template {0} does not allow execution copies.").format(template.template_name)
        )

    definition = _template_definition_for_annex(source_annex, template)
    definition = json.loads(json.dumps(definition, default=str))
    definition["targets"] = [
        row
        for row in definition.get("targets") or []
        if row.get("target_doctype") != target_doctype
    ]
    definition["targets"].append(
        current_target or {"target_doctype": target_doctype, "allow_direct_creation": 0}
    )
    if target_doctype == TECHNICAL_REVISION_DOCTYPE:
        definition["revision_owned"] = True
    return definition


def _copy_snapshot_files(annex) -> None:
    from orderlift.document_templates import _copy_revision_annex_files

    _copy_revision_annex_files(annex)


def _synchronize_snapshot(
    target_doc,
    source_annex,
    origin: str,
    *,
    reset_status: bool = False,
    require_execution: bool = False,
):
    from orderlift.document_templates import (
        _append_annex_value,
        _make_reference_key,
        get_default_status,
    )

    reference_key = _make_reference_key(
        target_doc.doctype,
        target_doc.name,
        source_annex.template,
        source_annex.name,
    )
    existing_name = frappe.db.get_value(ANNEX_DOCTYPE, {"reference_key": reference_key}, "name")
    annex = frappe.get_doc(ANNEX_DOCTYPE, existing_name) if existing_name else frappe.new_doc(ANNEX_DOCTYPE)
    source_hash = _value(source_annex, "content_hash", "") or compute_annex_content_hash(source_annex)
    if existing_name and (
        origin == "Execution Copy"
        or _value(annex, "source_content_hash", "") == source_hash
    ):
        return annex
    if existing_name and cint(_value(annex, "is_frozen", 0)):
        frappe.throw(_("Frozen snapshot {0} cannot be synchronized.").format(annex.name))

    definition = _definition_for_snapshot(
        source_annex,
        target_doc.doctype,
        require_execution=require_execution,
    )
    annex.flags.annex_sync = True
    annex.template = source_annex.template
    annex.template_name = definition.get("template_name") or source_annex.template_name
    annex.reference_doctype = target_doc.doctype
    annex.reference_name = target_doc.name
    annex.reference_key = reference_key
    annex.origin = origin
    annex.source_annex = source_annex.name
    annex.source_reference_doctype = source_annex.reference_doctype
    annex.source_reference_name = source_annex.reference_name
    annex.source_modified = source_annex.modified
    annex.source_content_hash = source_hash
    annex.company = _value(target_doc, "company", "") or _value(source_annex, "company", "") or ""
    annex.template_snapshot_json = json.dumps(definition, sort_keys=True, default=str)
    annex.status = get_default_status(definition) if reset_status else source_annex.status
    annex.set("values", [])
    source_values = {
        _value(row, "field_key", ""): row for row in (_value(source_annex, "values", []) or [])
    }
    for field in definition.get("fields") or []:
        if field.get("fieldtype") in {"Section Break", "Column Break", "HTML"}:
            continue
        source_value = source_values.get(field.get("field_key"))
        _append_annex_value(
            annex,
            field,
            _value(source_value, "value", ""),
            source_value,
        )
    if annex.is_new():
        annex.insert(ignore_permissions=True)
    else:
        annex.save(ignore_permissions=True)
    _copy_snapshot_files(annex)
    return annex


def _remove_stale_snapshots(
    target_doc,
    origin: str,
    source_names: set[str],
    inaccessible_references: set[tuple[str, str]] | None = None,
) -> None:
    inaccessible_references = inaccessible_references or set()
    stale = frappe.get_all(
        ANNEX_DOCTYPE,
        filters={
            "reference_doctype": target_doc.doctype,
            "reference_name": target_doc.name,
            "origin": origin,
            "docstatus": ["<", 2],
        },
        fields=[
            "name",
            "source_annex",
            "source_reference_doctype",
            "source_reference_name",
            "is_frozen",
        ],
        limit_page_length=0,
    )
    for row in stale:
        source_reference = (row.source_reference_doctype or "", row.source_reference_name or "")
        if (
            row.source_annex in source_names
            or source_reference in inaccessible_references
            or cint(row.is_frozen)
        ):
            continue
        annex = frappe.get_doc(ANNEX_DOCTYPE, row.name)
        annex.flags.annex_sync = True
        annex.delete(ignore_permissions=True)


def _sync_reference_snapshots(
    target_doc,
    sources: list,
    origin: str,
    inaccessible_references: set[tuple[str, str]] | None = None,
) -> list[str]:
    if target_doc.doctype in LOCKED_REFERENCE_DOCTYPES:
        lock_annex_reference(target_doc.doctype, target_doc.name)
        if cint(frappe.db.get_value(target_doc.doctype, target_doc.name, "docstatus")) != 0:
            return []
    created = []
    source_names = {source.name for source in sources}
    _remove_stale_snapshots(target_doc, origin, source_names, inaccessible_references)
    for source in sources:
        created.append(_synchronize_snapshot(target_doc, source, origin).name)
    return created


def sync_quotation_annexes(doc, method=None, *, allow_submitted: bool = False) -> list[str]:
    if not doc or _value(doc, "doctype") != "Quotation" or not _value(doc, "name"):
        return []
    if cint(_value(doc, "docstatus", 0)) != 0 and not allow_submitted:
        return []
    opportunities = _source_opportunities(doc)
    references = [("Opportunity", name) for name in opportunities]
    inaccessible = {
        ("Opportunity", name)
        for name in opportunities
        if not frappe.has_permission("Opportunity", "read", doc=name)
    }
    sources = _annexes_for_references(references)
    return _sync_reference_snapshots(
        doc,
        sources,
        "Opportunity Snapshot",
        inaccessible_references=inaccessible,
    )


def sync_draft_quotations_for_opportunity(opportunity: str) -> list[str]:
    if not opportunity or not frappe.db.exists("Opportunity", opportunity):
        return []
    quotation_names = frappe.get_all(
        "Quotation",
        filters={"opportunity": opportunity, "docstatus": 0},
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )
    item_quotations = frappe.get_all(
        "Quotation Item",
        filters={"prevdoc_docname": opportunity, "parenttype": "Quotation"},
        pluck="parent",
        limit_page_length=0,
    )
    candidates = list(dict.fromkeys([*quotation_names, *item_quotations]))
    if candidates:
        quotation_names = frappe.get_all(
            "Quotation",
            filters={"name": ["in", candidates], "docstatus": 0},
            pluck="name",
            order_by="creation asc",
            limit_page_length=0,
        )
    updated = []
    for name in quotation_names:
        updated.extend(sync_quotation_annexes(frappe.get_doc("Quotation", name)))
    return updated


def on_annex_update(doc, method=None) -> None:
    if _flag(doc, "annex_sync") or _flag(doc, "annex_freeze"):
        return
    if _value(doc, "reference_doctype", "") == "Opportunity":
        sync_draft_quotations_for_opportunity(_value(doc, "reference_name", ""))
    elif _value(doc, "reference_doctype", "") == TECHNICAL_REVISION_DOCTYPE:
        from orderlift.orderlift_sig.technical_list import refresh_revision_annex_state

        refresh_revision_annex_state(_value(doc, "reference_name", ""))


def on_annex_delete(doc, method=None) -> None:
    if _flag(doc, "annex_sync") or _flag(doc, "annex_freeze"):
        return
    if _value(doc, "reference_doctype", "") == "Opportunity":
        sync_draft_quotations_for_opportunity(_value(doc, "reference_name", ""))
    elif _value(doc, "reference_doctype", "") == TECHNICAL_REVISION_DOCTYPE:
        from orderlift.orderlift_sig.technical_list import refresh_revision_annex_state

        refresh_revision_annex_state(_value(doc, "reference_name", ""))


def sync_sales_order_annexes(doc, method=None, *, allow_submitted: bool = False) -> list[str]:
    if not doc or _value(doc, "doctype") != "Sales Order" or not _value(doc, "name"):
        return []
    if cint(_value(doc, "docstatus", 0)) != 0 and not allow_submitted:
        return []
    sources = _annexes_for_references(
        [("Quotation", name) for name in _source_quotations(doc)]
    )
    return _sync_reference_snapshots(doc, sources, "Quotation Snapshot")


def on_quotation_submit(doc, method=None) -> list[str]:
    sync_quotation_annexes(doc, allow_submitted=True)
    return freeze_reference_annexes("Quotation", doc.name)


def on_sales_order_submit(doc, method=None) -> list[str]:
    return freeze_reference_annexes("Sales Order", doc.name)


def on_technical_revision_submit(doc, method=None) -> list[str]:
    if not doc or _value(doc, "doctype") != TECHNICAL_REVISION_DOCTYPE:
        return []
    return freeze_reference_annexes(TECHNICAL_REVISION_DOCTYPE, doc.name)


def _doctype_available(doctype: str) -> bool:
    if not frappe.db.exists("DocType", doctype):
        return False
    table_exists = getattr(frappe.db, "table_exists", None)
    if not table_exists:
        return True
    return bool(table_exists(doctype) or table_exists(f"tab{doctype}"))


def _technical_context(sales_order: str) -> dict:
    empty = {
        "available": False,
        "technical_list": "",
        "open_revision": "",
        "current_revision": "",
        "revisions": [],
    }
    if not (
        sales_order
        and _doctype_available(TECHNICAL_LIST_DOCTYPE)
        and _doctype_available(TECHNICAL_REVISION_DOCTYPE)
    ):
        return empty
    parent = frappe.db.get_value(
        TECHNICAL_LIST_DOCTYPE,
        {"sales_order": sales_order},
        ["name", "open_revision", "current_revision"],
        as_dict=True,
    )
    if not parent:
        return empty
    revisions = frappe.get_all(
        TECHNICAL_REVISION_DOCTYPE,
        filters={"technical_list": parent.name, "docstatus": ["<", 2]},
        pluck="name",
        order_by="revision_no asc",
        limit_page_length=0,
    )
    return {
        "available": True,
        "technical_list": parent.name,
        "open_revision": parent.open_revision or "",
        "current_revision": parent.current_revision or "",
        "revisions": revisions,
    }


def _project_sales_orders(project: str) -> list[str]:
    if not project:
        return []
    return frappe.get_list(
        "Sales Order",
        filters={"project": project, "docstatus": ["<", 2]},
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )


def _lineage(reference_doctype: str, reference_name: str) -> dict:
    opportunities = []
    quotations = []
    sales_orders = []
    projects = []
    revisions = []
    technical = {}

    if reference_doctype == "Opportunity":
        opportunities = [reference_name]
    elif reference_doctype == "Quotation":
        quotations = [reference_name]
        opportunities = _source_opportunities(frappe.get_doc("Quotation", reference_name))
    elif reference_doctype == "Sales Order":
        sales_orders = [reference_name]
    elif reference_doctype == "Project":
        projects = [reference_name]
        sales_orders = _project_sales_orders(reference_name)
        project = frappe.get_doc("Project", reference_name)
        source_opportunity = (_value(project, "custom_source_opportunity", "") or "").strip()
        if source_opportunity and frappe.db.exists("Opportunity", source_opportunity):
            opportunities.append(source_opportunity)
    elif reference_doctype == TECHNICAL_REVISION_DOCTYPE:
        revision = frappe.get_doc(TECHNICAL_REVISION_DOCTYPE, reference_name)
        revisions = [reference_name]
        if revision.sales_order:
            sales_orders = [revision.sales_order]

    for sales_order_name in sales_orders:
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        quotations.extend(_source_quotations(sales_order))
        project = (_value(sales_order, "project", "") or "").strip()
        if project and frappe.db.exists("Project", project):
            projects.append(project)
        context = _technical_context(sales_order_name)
        technical[sales_order_name] = context
        if reference_doctype != TECHNICAL_REVISION_DOCTYPE:
            revisions.extend(context["revisions"])

    for quotation_name in list(dict.fromkeys(quotations)):
        quotation = frappe.get_doc("Quotation", quotation_name)
        opportunities.extend(_source_opportunities(quotation))

    return {
        "opportunities": list(dict.fromkeys(opportunities)),
        "quotations": list(dict.fromkeys(quotations)),
        "sales_orders": list(dict.fromkeys(sales_orders)),
        "projects": list(dict.fromkeys(projects)),
        "revisions": list(dict.fromkeys(revisions)),
        "technical": technical,
    }


def _can_write(doctype: str, name: str) -> bool:
    return bool(name and frappe.has_permission(doctype, "write", doc=name))


def _docstatus(doctype: str, name: str) -> int:
    meta = frappe.get_meta(doctype)
    if not meta.is_submittable:
        return 0
    return cint(frappe.db.get_value(doctype, name, "docstatus"))


def _read_only_reason(annex) -> str:
    if cint(_value(annex, "is_frozen", 0)):
        return _("Frozen snapshot")
    if _docstatus(annex.reference_doctype, annex.reference_name) != 0:
        return _("Source document is submitted")
    if annex.origin in SYNCED_ORIGINS:
        return _("Synchronized from the source document")
    if not _can_write(annex.reference_doctype, annex.reference_name):
        return _("Read-only source")
    return ""


def _execution_target_allowed(annex) -> bool:
    if not _doctype_available(TECHNICAL_REVISION_DOCTYPE):
        return False
    try:
        from orderlift.document_templates import _revision_target

        template = frappe.get_doc(TEMPLATE_DOCTYPE, annex.template)
        target = _revision_target(template, TECHNICAL_REVISION_DOCTYPE)
        return bool(
            target.get("allow_execution_copy")
            or target.get("allow_import_from_sales_order")
        )
    except frappe.DoesNotExistError:
        return False


def _entry(annex, execution_revision: str = "", force_read_only: str = "") -> dict:
    reason = force_read_only or _read_only_reason(annex)
    can_copy = bool(
        execution_revision
        and annex.reference_doctype != TECHNICAL_REVISION_DOCTYPE
        and _execution_target_allowed(annex)
        and _docstatus(TECHNICAL_REVISION_DOCTYPE, execution_revision) == 0
        and _can_write(TECHNICAL_REVISION_DOCTYPE, execution_revision)
    )
    return {
        "key": annex.name,
        "annex": annex.name,
        "annex_name": annex.name,
        "template": annex.template,
        "template_name": annex.template_name,
        "status": annex.status or "",
        "is_complete": cint(annex.is_complete),
        "is_frozen": cint(_value(annex, "is_frozen", 0)),
        "content_hash": _value(annex, "content_hash", "") or "",
        "origin": annex.origin or "Native",
        "modified": annex.modified,
        "source_key": f"{annex.reference_doctype}::{annex.reference_name}",
        "source_doctype": annex.reference_doctype,
        "source_name": annex.reference_name,
        "source_label": f"{annex.reference_doctype} {annex.reference_name}",
        "editable": not reason,
        "read_only_reason": reason,
        "can_print": True,
        "can_copy_to_execution": can_copy,
        "execution_revision": execution_revision if can_copy else "",
    }


def _placeholder_entry(template, doctype: str, name: str, force_read_only: str = "") -> dict:
    from orderlift.document_templates import get_default_status

    editable = bool(not force_read_only and _docstatus(doctype, name) == 0 and _can_write(doctype, name))
    return {
        "key": f"placeholder::{doctype}::{name}::{template.name}",
        "annex": "",
        "annex_name": "",
        "template": template.name,
        "template_name": template.template_name,
        "status": get_default_status(template),
        "is_complete": 0,
        "is_frozen": 0,
        "origin": "Native",
        "modified": "",
        "source_key": f"{doctype}::{name}",
        "source_doctype": doctype,
        "source_name": name,
        "source_label": f"{doctype} {name}",
        "editable": editable,
        "read_only_reason": force_read_only or ("" if editable else _("Read-only source")),
        "can_print": False,
        "can_copy_to_execution": False,
        "execution_revision": "",
    }


def _phase(
    key: str,
    label: str,
    references: list[tuple[str, str]],
    lineage: dict,
    *,
    annex_filter=None,
    include_placeholders: bool = False,
    direct_only: bool = False,
    force_read_only: str = "",
) -> dict:
    from orderlift.document_templates import _active_templates_for_doctype, build_template_snapshot

    entries = []
    source_rows = []
    for doctype, name in references:
        if not name or not frappe.has_permission(doctype, "read", doc=name):
            continue
        execution_revision = ""
        if doctype == "Sales Order":
            execution_revision = lineage["technical"].get(name, {}).get("open_revision", "")
        elif len(lineage["sales_orders"]) == 1:
            execution_revision = lineage["technical"].get(
                lineage["sales_orders"][0], {}
            ).get("open_revision", "")
        annexes = _annexes_for_references([(doctype, name)])
        if annex_filter:
            annexes = [annex for annex in annexes if annex_filter(annex)]
        source_entries = [_entry(annex, execution_revision, force_read_only) for annex in annexes]
        if include_placeholders and not force_read_only:
            existing_direct_templates = {
                annex.template for annex in annexes if not (_value(annex, "source_annex", "") or "")
            }
            for template in _active_templates_for_doctype(doctype):
                target = next(
                    (
                        row
                        for row in build_template_snapshot(template).get("targets") or []
                        if row.get("target_doctype") == doctype
                    ),
                    {},
                )
                if not target.get("allow_direct_creation"):
                    continue
                if template.name not in existing_direct_templates:
                    source_entries.append(_placeholder_entry(template, doctype, name))
        entries.extend(source_entries)
        source_rows.append(
            {
                "key": f"{doctype}::{name}",
                "label": f"{doctype} {name}",
                "doctype": doctype,
                "name": name,
                "count": len(source_entries),
            }
        )
    return {
        "key": key,
        "label": label,
        "count": len(entries),
        "sources": source_rows,
        "entries": entries,
    }


@frappe.whitelist()
def get_annex_workspace(reference_doctype: str, reference_name: str) -> dict:
    reference_doctype = (reference_doctype or "").strip()
    reference_name = (reference_name or "").strip()
    if reference_doctype not in CHAIN_DOCTYPES:
        frappe.throw(_("Annex chain is not available for {0}.").format(reference_doctype))
    if reference_doctype == TECHNICAL_REVISION_DOCTYPE and not _doctype_available(
        TECHNICAL_REVISION_DOCTYPE
    ):
        return {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "phases": [],
            "capabilities": {
                "technical_lists_enabled": False,
                "execution_revision": "",
                "current_revision": "",
                "can_create_execution_copy": False,
            },
        }
    if not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("{0} {1} was not found.").format(reference_doctype, reference_name))
    source = frappe.get_doc(reference_doctype, reference_name)
    source.check_permission("read")
    lineage = _lineage(reference_doctype, reference_name)

    phases = []
    quotation_refs = [("Quotation", name) for name in lineage["quotations"]]
    sales_order_refs = [("Sales Order", name) for name in lineage["sales_orders"]]
    opportunity_snapshot = lambda annex: annex.origin == "Opportunity Snapshot"
    direct_owned = lambda annex: not (_value(annex, "source_annex", "") or "")

    if reference_doctype == "Quotation":
        if cint(source.docstatus) == 0 and lineage["opportunities"]:
            phases.append(
                _phase(
                    "crm",
                    _("CRM / Opportunity"),
                    [("Opportunity", name) for name in lineage["opportunities"]],
                    lineage,
                    include_placeholders=True,
                )
            )
        elif lineage["opportunities"]:
            phases.append(
                _phase(
                    "crm",
                    _("CRM / Opportunity"),
                    [("Quotation", reference_name)],
                    lineage,
                    annex_filter=opportunity_snapshot,
                    force_read_only=_("Frozen on Quotation submission"),
                )
            )
        phases.append(
            _phase(
                "quotation",
                _("Quotation"),
                [("Quotation", reference_name)],
                lineage,
                annex_filter=direct_owned,
                include_placeholders=cint(source.docstatus) == 0,
            )
        )
    elif reference_doctype == "Sales Order":
        if quotation_refs:
            phases.append(
                _phase("crm", _("CRM"), quotation_refs, lineage, annex_filter=opportunity_snapshot, force_read_only=_("Frozen Quotation snapshot"))
            )
            phases.append(
                _phase("quotation", _("Quotations"), quotation_refs, lineage, annex_filter=direct_owned, force_read_only=_("Source Quotation is read-only"))
            )
        phases.append(
            _phase(
                "sales-order",
                _("Sales Order"),
                [("Sales Order", reference_name)],
                lineage,
                annex_filter=direct_owned,
                include_placeholders=cint(source.docstatus) == 0,
            )
        )
    elif reference_doctype == TECHNICAL_REVISION_DOCTYPE:
        if quotation_refs:
            phases.append(_phase("crm", _("CRM"), quotation_refs, lineage, annex_filter=opportunity_snapshot, force_read_only=_("Upstream CRM snapshot")))
            phases.append(_phase("quotation", _("Quotations"), quotation_refs, lineage, annex_filter=direct_owned, force_read_only=_("Upstream Quotation")))
        if sales_order_refs:
            phases.append(_phase("sales-order", _("Sales Order"), sales_order_refs, lineage, annex_filter=direct_owned, force_read_only=_("Upstream Sales Order")))
        phases.append(
            _phase(
                "execution",
                _("Execution"),
                [(TECHNICAL_REVISION_DOCTYPE, reference_name)],
                lineage,
                include_placeholders=cint(source.docstatus) == 0,
                direct_only=True,
            )
        )
    elif reference_doctype == "Project":
        if quotation_refs:
            phases.append(_phase("crm", _("CRM"), quotation_refs, lineage, annex_filter=opportunity_snapshot, force_read_only=_("Frozen Quotation snapshot")))
            phases.append(_phase("quotation", _("Quotations"), quotation_refs, lineage, annex_filter=direct_owned, force_read_only=_("Source Quotation")))
        if sales_order_refs:
            phases.append(_phase("sales-order", _("Sales Orders"), sales_order_refs, lineage, annex_filter=direct_owned, force_read_only=_("Source Sales Order")))
        selected_revisions = []
        for sales_order_name in lineage["sales_orders"]:
            context = lineage["technical"].get(sales_order_name, {})
            revision = context.get("current_revision") or context.get("open_revision")
            if revision:
                selected_revisions.append(revision)
        if selected_revisions:
            phases.append(
                _phase(
                    "technical",
                    _("Technical Lists"),
                    [(TECHNICAL_REVISION_DOCTYPE, name) for name in dict.fromkeys(selected_revisions)],
                    lineage,
                    force_read_only=_("Technical Revision shown from Project"),
                )
            )
        phases.append(
            _phase(
                "project",
                _("Project"),
                [("Project", reference_name)],
                lineage,
                annex_filter=direct_owned,
                include_placeholders=True,
            )
        )

    contexts = [lineage["technical"].get(name, {}) for name in lineage["sales_orders"]]
    open_revisions = [row.get("open_revision") for row in contexts if row.get("open_revision")]
    current_revisions = [row.get("current_revision") for row in contexts if row.get("current_revision")]
    return {
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "phases": phases,
        "capabilities": {
            "technical_lists_enabled": _doctype_available(TECHNICAL_REVISION_DOCTYPE),
            "execution_revision": open_revisions[0] if len(open_revisions) == 1 else "",
            "current_revision": current_revisions[0] if len(current_revisions) == 1 else "",
            "can_create_execution_copy": bool(open_revisions),
        },
    }


@frappe.whitelist()
def create_execution_copy(revision: str, source_annex: str) -> dict:
    if not _doctype_available(TECHNICAL_REVISION_DOCTYPE):
        return {"available": False, "created": False, "annex": ""}
    if not frappe.db.exists(TECHNICAL_REVISION_DOCTYPE, revision):
        frappe.throw(_("Technical revision {0} was not found.").format(revision))
    target = frappe.get_doc(TECHNICAL_REVISION_DOCTYPE, revision)
    target.check_permission("write")
    lock_annex_reference(TECHNICAL_REVISION_DOCTYPE, revision)
    target.reload()
    if cint(target.docstatus) != 0:
        frappe.throw(_("Execution copies can only be created on a draft technical revision."))

    source = frappe.get_doc(ANNEX_DOCTYPE, source_annex)
    source.check_permission("read")
    lineage = _lineage(TECHNICAL_REVISION_DOCTYPE, revision)
    allowed_references = {
        *(('Opportunity', name) for name in lineage["opportunities"]),
        *(('Quotation', name) for name in lineage["quotations"]),
        *(('Sales Order', name) for name in lineage["sales_orders"]),
        *(('Project', name) for name in lineage["projects"]),
    }
    if (source.reference_doctype, source.reference_name) not in allowed_references:
        frappe.throw(_("The selected annex is not upstream of this technical revision."))

    annex = _synchronize_snapshot(
        target,
        source,
        "Execution Copy",
        reset_status=True,
        require_execution=True,
    )
    return {
        "available": True,
        "created": True,
        "annex": annex.name,
        "revision": revision,
        "source_annex": source.name,
        "content_hash": annex.content_hash,
    }


def initialize_revision_execution_copies(revision) -> list[str]:
    """Carry prior execution forward, or create configured defaults on revision one."""
    if isinstance(revision, str):
        revision = frappe.get_doc(TECHNICAL_REVISION_DOCTYPE, revision)
    if not revision or not revision.name or cint(revision.docstatus) != 0:
        return []

    sources = []
    based_on = (_value(revision, "based_on_revision", "") or "").strip()
    if based_on and frappe.db.exists(TECHNICAL_REVISION_DOCTYPE, based_on):
        sources = _annexes_for_references([(TECHNICAL_REVISION_DOCTYPE, based_on)])
        return [
            _synchronize_snapshot(revision, source, "Execution Copy", reset_status=True).name
            for source in sources
        ]

    lineage = _lineage(TECHNICAL_REVISION_DOCTYPE, revision.name)
    references = [
        *(("Quotation", name) for name in lineage["quotations"]),
        *(("Sales Order", name) for name in lineage["sales_orders"]),
    ]
    for source in _annexes_for_references(references):
        try:
            from orderlift.document_templates import _revision_target

            template = frappe.get_doc(TEMPLATE_DOCTYPE, source.template)
            target = _revision_target(template, TECHNICAL_REVISION_DOCTYPE)
            if not target.get("default_selected") or not (
                target.get("allow_execution_copy") or target.get("allow_import_from_sales_order")
            ):
                continue
            sources.append(source)
        except frappe.DoesNotExistError:
            continue
    return [
        _synchronize_snapshot(
            revision,
            source,
            "Execution Copy",
            reset_status=True,
            require_execution=True,
        ).name
        for source in sources
    ]


# Readable hook aliases for later lifecycle wiring.
sync_quotation_annex_snapshots = sync_quotation_annexes
sync_sales_order_annex_snapshots = sync_sales_order_annexes
freeze_quotation_annexes = on_quotation_submit
freeze_sales_order_annexes = on_sales_order_submit
freeze_technical_revision_annexes = on_technical_revision_submit
