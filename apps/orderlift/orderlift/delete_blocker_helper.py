from __future__ import annotations

from collections import OrderedDict

import frappe
from frappe import _
from frappe.model.delete_doc import check_permission_and_not_submitted
from frappe.model.docstatus import DocStatus
from frappe.model.dynamic_links import get_dynamic_link_map
from frappe.model.rename_doc import get_link_fields


NON_CASCADE_REFERENCE_DOCTYPES = {
    "Address",
    "Company",
    "Contact",
    "Customer",
    "Item",
    "Lead",
    "Partner Campaign",
    "Prospect",
    "Sales Person",
    "Supplier",
}
NON_CASCADE_LEDGER_DOCTYPES = {
    "Advance Payment Ledger Entry",
    "GL Entry",
    "Payment Ledger Entry",
    "Stock Ledger Entry",
}


def _is_non_cascade_doctype(doctype):
    return doctype in NON_CASCADE_REFERENCE_DOCTYPES


def _is_ledger_doctype(doctype):
    return doctype in NON_CASCADE_LEDGER_DOCTYPES


def _is_source_voucher_ledger_blocker(blocker):
    if not _is_ledger_doctype(blocker.get("doctype")):
        return False
    for reason in blocker.get("reasons") or []:
        if _value(reason, "fieldname") == "voucher_no" and _value(reason, "doctype_fieldname") == "voucher_type":
            return True
    return False


def _is_unlinkable_reference_blocker(blocker):
    if blocker.get("doctype") not in NON_CASCADE_REFERENCE_DOCTYPES:
        return False
    for reason in blocker.get("reasons") or []:
        link_doctype = _value(reason, "link_doctype")
        fieldname = _value(reason, "fieldname")
        if link_doctype and fieldname:
            return True
    return False


def _value(row, fieldname, default=None):
    if isinstance(row, dict):
        return row.get(fieldname, default)
    return getattr(row, fieldname, default)


def _field_label(doctype, fieldname):
    try:
        field = frappe.get_meta(doctype).get_field(fieldname)
    except frappe.DoesNotExistError:
        frappe.clear_last_message()
        return fieldname
    return field.label if field and field.label else fieldname


def _add_blocker(blockers, doctype, name, reason):
    if not doctype or not name:
        return

    key = (str(doctype), str(name))
    blocker = blockers.setdefault(
        key,
        {
            "doctype": key[0],
            "name": key[1],
            "reasons": [],
        },
    )
    if reason not in blocker["reasons"]:
        blocker["reasons"].append(reason)


def _discover_static_blockers(doc, blockers, ignored_doctypes):
    for link_field in get_link_fields(doc.doctype):
        link_doctype = link_field["parent"]
        fieldname = link_field["fieldname"]
        is_single = bool(link_field["issingle"])

        if link_doctype in ignored_doctypes:
            continue

        try:
            meta = frappe.get_meta(link_doctype)
        except frappe.DoesNotExistError:
            frappe.clear_last_message()
            continue

        reason = {
            "link_doctype": link_doctype,
            "fieldname": fieldname,
            "field_label": _field_label(link_doctype, fieldname),
            "row": "",
        }

        if is_single:
            if frappe.db.get_single_value(link_doctype, fieldname) == doc.name:
                _add_blocker(blockers, link_doctype, link_doctype, reason)
            continue

        fields = ["name", "docstatus"]
        if meta.istable:
            fields.extend(["parent", "parenttype", "idx"])

        rows = frappe.db.get_values(link_doctype, {fieldname: doc.name}, fields, as_dict=True)
        for row in rows:
            parent_name = _value(row, "parent")
            reference_doctype = _value(row, "parenttype") if parent_name else link_doctype
            reference_name = parent_name or _value(row, "name")

            if reference_doctype in ignored_doctypes:
                continue
            if link_doctype == doc.doctype and reference_name == doc.name:
                continue

            row_reason = dict(reason)
            row_reason["row"] = _value(row, "idx", "") if parent_name else ""
            _add_blocker(blockers, reference_doctype, reference_name, row_reason)


def _discover_dynamic_blockers(doc, blockers, ignored_doctypes):
    for link_field in get_dynamic_link_map().get(doc.doctype, []):
        link_doctype = link_field.parent
        if link_doctype in ignored_doctypes:
            continue

        meta = frappe.get_meta(link_doctype)
        reason = {
            "link_doctype": link_doctype,
            "fieldname": link_field.fieldname,
            "doctype_fieldname": link_field.options,
            "field_label": _field_label(link_doctype, link_field.fieldname),
            "row": "",
        }

        if meta.issingle:
            reference = frappe.db.get_singles_dict(link_doctype)
            if (
                reference.get(link_field.options) == doc.doctype
                and reference.get(link_field.fieldname) == doc.name
                and not DocStatus(reference.get("docstatus")).is_cancelled()
            ):
                _add_blocker(blockers, link_doctype, link_doctype, reason)
            continue

        fields = ["name", "docstatus"]
        if meta.istable:
            fields.extend(["parent", "parenttype", "idx"])

        filters = {
            link_field.options: doc.doctype,
            link_field.fieldname: doc.name,
        }
        rows = frappe.db.get_values(link_doctype, filters, fields, as_dict=True)
        for row in rows:
            if DocStatus(_value(row, "docstatus")).is_cancelled():
                continue

            parent_name = _value(row, "parent")
            reference_doctype = _value(row, "parenttype") if parent_name else link_doctype
            reference_name = parent_name or _value(row, "name")
            if reference_doctype in ignored_doctypes:
                continue

            row_reason = dict(reason)
            row_reason["row"] = _value(row, "idx", "") if parent_name else ""
            _add_blocker(blockers, reference_doctype, reference_name, row_reason)


def _discover_blockers(doc):
    """Mirror Frappe's current static and dynamic delete-link checks."""
    blockers = OrderedDict()
    ignored_doctypes = set(frappe.get_hooks("ignore_links_on_delete"))
    _discover_static_blockers(doc, blockers, ignored_doctypes)
    _discover_dynamic_blockers(doc, blockers, ignored_doctypes)
    return list(blockers.values())


def _discover_blocker_hierarchy(parent):
    """Discover every readable downstream blocker as a deduplicated dependency graph."""
    root_key = (parent.doctype, parent.name)
    blockers = OrderedDict()
    dependencies = OrderedDict({root_key: []})
    queue = [(parent, root_key, 0)]
    expanded = set()

    while queue:
        doc, parent_key, depth = queue.pop(0)
        if parent_key in expanded:
            continue
        expanded.add(parent_key)
        dependencies.setdefault(parent_key, [])

        for direct in _discover_blockers(doc):
            key = (direct["doctype"], direct["name"])
            if key == root_key:
                continue
            if _is_source_voucher_ledger_blocker(direct):
                continue
            if key not in dependencies[parent_key]:
                dependencies[parent_key].append(key)

            row = blockers.get(key)
            if row is None:
                row = {
                    **direct,
                    "depth": depth + 1,
                    "blocking_documents": [],
                }
                blockers[key] = row
            else:
                row["depth"] = min(row["depth"], depth + 1)
                for reason in direct.get("reasons") or []:
                    if reason not in row["reasons"]:
                        row["reasons"].append(reason)

            blocking_document = {"doctype": parent_key[0], "name": parent_key[1]}
            if blocking_document not in row["blocking_documents"]:
                row["blocking_documents"].append(blocking_document)

            dependencies.setdefault(key, [])
            if _is_ledger_doctype(key[0]):
                continue
            if key in expanded or not frappe.has_permission(key[0], "read", doc=key[1]):
                continue
            if _is_non_cascade_doctype(key[0]):
                continue
            try:
                blocker_doc = frappe.get_doc(key[0], key[1])
            except frappe.DoesNotExistError:
                frappe.clear_last_message()
                continue
            queue.append((blocker_doc, key, depth + 1))

    return list(blockers.values()), dependencies


def _dependency_first_order(root_key, dependencies):
    """Return each blocker once, deepest dependencies before the documents they block."""
    ordered = []
    visited = set()
    visiting = set()

    def visit(key):
        if key in visited or key in visiting:
            return
        visiting.add(key)
        for dependency in dependencies.get(key, []):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
        if key != root_key:
            ordered.append(key)

    visit(root_key)
    return ordered


def _is_submitted(doctype, name):
    meta = frappe.get_meta(doctype)
    if not meta.is_submittable:
        return False
    if meta.issingle:
        docstatus = frappe.db.get_single_value(doctype, "docstatus")
    else:
        docstatus = frappe.db.get_value(doctype, name, "docstatus")
    return DocStatus(docstatus).is_submitted()


def _can_override_submitted_deletion(user=None):
    from orderlift.role_capabilities import CAPABILITY_DELETE_SUBMITTED_BLOCKERS, user_has_capability

    return user_has_capability(CAPABILITY_DELETE_SUBMITTED_BLOCKERS, user=user)


def _is_protected_standard_doctype(doctype, name):
    if frappe.session.user != "Administrator" and doctype == "DocType":
        return not frappe.db.get_value("DocType", name, "custom")
    return False


def _delete_state(doctype, name, allow_override=False):
    has_delete_permission = frappe.has_permission(doctype, "delete", doc=name)
    submitted = _is_submitted(doctype, name)

    if _is_protected_standard_doctype(doctype, name):
        return {
            "can_delete": False,
            "lock_reason": "standard_doctype",
            "override_reasons": [],
        }
    if _is_non_cascade_doctype(doctype) and doctype in NON_CASCADE_REFERENCE_DOCTYPES:
        return {
            "can_delete": False,
            "lock_reason": "reference_doctype",
            "override_reasons": [],
        }
    if _is_ledger_doctype(doctype):
        return {
            "can_delete": False,
            "lock_reason": "ledger_doctype",
            "override_reasons": [],
        }

    override_reasons = []
    if not has_delete_permission:
        override_reasons.append("delete_permission")
    if submitted:
        override_reasons.append("submitted")

    if override_reasons and not allow_override:
        return {
            "can_delete": False,
            "lock_reason": override_reasons[0],
            "override_reasons": [],
        }
    return {
        "can_delete": True,
        "lock_reason": "",
        "override_reasons": override_reasons,
    }


def _classify_blockers(blockers):
    visible = []
    restricted_count = 0
    allow_override = _can_override_submitted_deletion()

    for blocker in blockers:
        doctype = blocker["doctype"]
        name = blocker["name"]
        if not frappe.has_permission(doctype, "read", doc=name):
            restricted_count += 1
            continue

        visible.append({**blocker, **_delete_state(doctype, name, allow_override=allow_override)})

    return visible, restricted_count


def _get_parent(doctype, name):
    doctype = (doctype or "").strip()
    name = (name or "").strip()
    if not doctype or not name:
        frappe.throw(_("Document type and name are required."))

    doc = frappe.get_doc(doctype, name)
    if _can_override_submitted_deletion():
        if not frappe.has_permission(doctype, "read", doc=name):
            frappe.throw(_("You are not permitted to read this document."), frappe.PermissionError)
        if _is_protected_standard_doctype(doctype, name):
            frappe.throw(_("Standard DocTypes cannot be deleted through this helper."), frappe.PermissionError)
        return doc
    check_permission_and_not_submitted(doc)
    return doc


@frappe.whitelist()
def get_delete_blockers(doctype, name):
    parent = _get_parent(doctype, name)
    direct_parent_blockers = _discover_blockers(parent)
    blockers, dependencies = _discover_blocker_hierarchy(parent)
    visible, restricted_count = _classify_blockers(blockers)
    allow_override = _can_override_submitted_deletion()

    return {
        "parent": {
            "doctype": parent.doctype,
            "name": parent.name,
            "submitted": _is_submitted(parent.doctype, parent.name),
        },
        "blockers": visible,
        "delete_override_enabled": allow_override,
        "hierarchy_depth": max((row.get("depth", 0) for row in blockers), default=0),
        "source_ledger_blocker_count": (
            sum(1 for row in direct_parent_blockers if _is_source_voucher_ledger_blocker(row))
            if allow_override else 0
        ),
        "restricted_blocker_count": restricted_count,
        "non_deletable_blocker_count": sum(not row["can_delete"] for row in visible),
    }


def _parse_selected_blockers(selected_blockers):
    selected = frappe.parse_json(selected_blockers) if isinstance(selected_blockers, str) else selected_blockers
    if selected is None:
        return set()
    if not isinstance(selected, list):
        frappe.throw(_("Selected blockers must be a list."))

    keys = []
    for row in selected:
        if not isinstance(row, dict):
            frappe.throw(_("Each selected blocker must contain a document type and name."))
        doctype = str(row.get("doctype") or "").strip()
        name = str(row.get("name") or "").strip()
        if not doctype or not name:
            frappe.throw(_("Each selected blocker must contain a document type and name."))
        keys.append((doctype, name))

    if len(keys) != len(set(keys)):
        frappe.throw(_("The blocker selection contains duplicate documents."))
    return set(keys)


def _unexpected_link_blockers(doc, allowed_link_keys, blockers=None):
    allowed_link_keys = set(allowed_link_keys or set())
    return [
        blocker
        for blocker in (blockers if blockers is not None else _discover_blockers(doc))
        if not _is_source_voucher_ledger_blocker(blocker)
        and (blocker["doctype"], blocker["name"]) not in allowed_link_keys
    ]


def _delete_source_voucher_ledgers(doctype, name):
    """Remove generated ledger rows owned by an exact source voucher."""
    for ledger_doctype in ("GL Entry", "Stock Ledger Entry"):
        frappe.db.sql(
            f"delete from `tab{ledger_doctype}` where voucher_type=%s and voucher_no=%s",
            (doctype, name),
        )

    for ledger_doctype in ("Payment Ledger Entry", "Advance Payment Ledger Entry"):
        frappe.db.sql(
            f"""
            delete from `tab{ledger_doctype}`
            where (voucher_type=%s and voucher_no=%s)
                or (against_voucher_type=%s and against_voucher_no=%s and delinked=1)
            """,
            (doctype, name, doctype, name),
        )


def _delete_document(doctype, name, allow_override=False, allowed_link_keys=None):
    generated_deleted = []
    if allow_override:
        doc = frappe.get_doc(doctype, name)
        if doc.meta.is_submittable and DocStatus(doc.docstatus).is_submitted():
            doc.flags.ignore_permissions = True
            doc.cancel()
            ignored_after_cancel = set(_value(doc, "ignore_linked_doctypes", ()) or ())
            for blocker in _discover_blockers(doc):
                if blocker["doctype"] not in ignored_after_cancel:
                    continue
                nested = _delete_document(
                    blocker["doctype"],
                    blocker["name"],
                    allow_override=True,
                    allowed_link_keys={(doctype, name)},
                )
                generated_deleted.extend(nested)
                generated_deleted.append({"doctype": blocker["doctype"], "name": blocker["name"]})

        direct_blockers = _discover_blockers(doc)
        has_source_ledger_blockers = any(_is_source_voucher_ledger_blocker(blocker) for blocker in direct_blockers)
        unexpected = _unexpected_link_blockers(doc, allowed_link_keys, blockers=direct_blockers)
        if unexpected:
            frappe.throw(_("The blocking documents changed. Review the updated list before deleting."))
        frappe.delete_doc(doctype, name, ignore_permissions=True, force=bool(allowed_link_keys) or has_source_ledger_blockers)
        _delete_source_voucher_ledgers(doctype, name)
        return generated_deleted
    frappe.delete_doc(doctype, name)
    return generated_deleted


def _delete_selected_blockers(blocker_keys, allow_override=False, allowed_link_keys=None):
    pending = list(blocker_keys)
    deleted = []
    first_link_error = None

    while pending:
        next_pending = []
        made_progress = False

        for index, (doctype, name) in enumerate(pending):
            attempt_savepoint = f"orderlift_delete_blocker_{len(deleted)}_{index}"
            frappe.db.savepoint(attempt_savepoint)
            try:
                generated = _delete_document(
                    doctype,
                    name,
                    allow_override=allow_override,
                    allowed_link_keys=allowed_link_keys,
                )
            except frappe.LinkExistsError as exc:
                frappe.db.rollback(save_point=attempt_savepoint)
                first_link_error = first_link_error or exc
                next_pending.append((doctype, name))
            else:
                deleted.extend(generated)
                deleted.append({"doctype": doctype, "name": name})
                made_progress = True

        if not made_progress:
            raise first_link_error
        pending = next_pending

    return deleted


def _unlink_reference_blockers(reference_blockers, parent):
    unlinked = []
    for blocker in reference_blockers:
        for reason in blocker.get("reasons") or []:
            link_doctype = _value(reason, "link_doctype")
            fieldname = _value(reason, "fieldname")
            doctype_fieldname = _value(reason, "doctype_fieldname")
            if not link_doctype or not fieldname:
                continue
            try:
                meta = frappe.get_meta(link_doctype)
            except frappe.DoesNotExistError:
                frappe.clear_last_message()
                continue
            if not meta.istable:
                if link_doctype != blocker["doctype"]:
                    continue
                filters = {"name": blocker["name"], fieldname: parent.name}
                if doctype_fieldname:
                    filters[doctype_fieldname] = parent.doctype
                if not frappe.db.exists(link_doctype, filters):
                    continue
                frappe.db.set_value(link_doctype, blocker["name"], fieldname, None, update_modified=False)
                if doctype_fieldname:
                    frappe.db.set_value(link_doctype, blocker["name"], doctype_fieldname, None, update_modified=False)
                unlinked.append(
                    {
                        "doctype": blocker["doctype"],
                        "name": blocker["name"],
                        "link_doctype": link_doctype,
                        "link_field": fieldname,
                    }
                )
                continue
            filters = {
                "parent": blocker["name"],
                "parenttype": blocker["doctype"],
                fieldname: parent.name,
            }
            if doctype_fieldname:
                filters[doctype_fieldname] = parent.doctype
            rows = frappe.db.get_values(link_doctype, filters, ["name"], as_dict=True)
            for row in rows:
                row_name = _value(row, "name")
                if not row_name:
                    continue
                frappe.db.sql(f"delete from `tab{link_doctype}` where name=%s", row_name)
                unlinked.append(
                    {
                        "doctype": blocker["doctype"],
                        "name": blocker["name"],
                        "link_doctype": link_doctype,
                        "link_row": row_name,
                    }
                )
    return unlinked


@frappe.whitelist()
def delete_blockers_and_parent(doctype, name, selected_blockers=None):
    parent = _get_parent(doctype, name)
    allow_override = _can_override_submitted_deletion()
    selected_keys = _parse_selected_blockers(selected_blockers)
    current_blockers, dependencies = _discover_blocker_hierarchy(parent)
    visible, restricted_count = _classify_blockers(current_blockers)
    unlinkable_references = [row for row in visible if not row["can_delete"] and _is_unlinkable_reference_blocker(row)]
    non_deletable = [
        row for row in visible
        if not row["can_delete"] and not _is_unlinkable_reference_blocker(row)
    ]
    deletable_keys = {(row["doctype"], row["name"]) for row in visible if row["can_delete"]}

    if restricted_count or non_deletable:
        frappe.throw(
            _("The document still has blockers that you are not permitted to delete."),
            frappe.PermissionError,
        )
    if selected_keys != deletable_keys:
        frappe.throw(_("The blocking documents changed. Review the updated list before deleting."))

    savepoint = "orderlift_delete_blockers_and_parent"
    frappe.db.savepoint(savepoint)
    try:
        unlinked_references = _unlink_reference_blockers(unlinkable_references, parent)
        deletion_order = _dependency_first_order((parent.doctype, parent.name), dependencies)
        deletion_order = [key for key in deletion_order if key in selected_keys]
        allowed_link_keys = set(deletion_order)
        allowed_link_keys.add((parent.doctype, parent.name))
        deleted = _delete_selected_blockers(
            deletion_order,
            allow_override=allow_override,
            allowed_link_keys=allowed_link_keys,
        )
        remaining, _remaining_dependencies = _discover_blocker_hierarchy(parent)
        if remaining:
            frappe.throw(_("The blocking documents changed. Review the updated list before deleting."))
        deleted.extend(_delete_document(parent.doctype, parent.name, allow_override=allow_override))
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise

    return {
        "deleted_parent": {"doctype": parent.doctype, "name": parent.name},
        "deleted_blockers": deleted,
        "unlinked_references": unlinked_references,
        "privileged_override_used": allow_override,
    }
