from __future__ import annotations

import json
from uuid import uuid4

import frappe

from orderlift.orderlift_logistics import technical_procurement
from orderlift.orderlift_sig import technical_list


def run() -> dict:
    """Exercise the live lifecycle and roll every created record back."""
    original_user = frappe.session.user
    frappe.set_user("Administrator")
    try:
        sales_order = _eligible_sales_order()
        if not sales_order:
            return {"skipped": True, "reason": "No submitted project-linked Sales Order with items was found."}

        company = frappe.get_doc("Company", sales_order.company)
        action = frappe.db.get_value(
            "Technical Procurement Action",
            {"adapter_key": "revision_to_material_request", "is_active": 1},
            "name",
        )
        if not action:
            return {"skipped": True, "reason": "Material Request technical adapter is missing."}

        route = frappe.new_doc("Technical Procurement Route")
        route.route_name = f"LIVE-TECH-{uuid4().hex[:10]}"
        route.company = company.name
        route.enabled = 1
        route.is_default = 0
        route.append("steps", {"action": action, "sequence": 10})
        route.insert()

        settings = {
            "custom_enable_sales_order_technical_lists": 1,
            "custom_technical_list_effective_from": None,
            "custom_technical_list_apply_all_business_types": 1,
            "custom_technical_list_require_project": 1,
            "custom_technical_list_auto_create": 0,
            "custom_technical_list_allow_additions": 1,
            "custom_technical_list_allow_exclusions": 1,
            "custom_technical_list_require_change_reason": 1,
            "custom_technical_list_include_non_stock_items": 1,
            "custom_technical_list_default_procurement_route": route.name,
        }
        frappe.db.set_value("Company", company.name, settings, update_modified=False)
        frappe.clear_document_cache("Company", company.name)

        template = frappe.new_doc("Orderlift Document Template")
        template.template_name = f"LIVE-TECH-ANNEX-{uuid4().hex[:10]}"
        template.is_active = 1
        template.append("targets", {"target_doctype": "Sales Order", "display_order": 10})
        template.append(
            "targets",
            {
                "target_doctype": "Sales Order Technical List Revision",
                "allow_direct_creation": 0,
                "allow_import_from_sales_order": 1,
                "required_for_revision": 1,
                "must_be_complete": 1,
                "default_selected": 1,
                "display_order": 10,
            },
        )
        template.append(
            "fields",
            {
                "field_label": "Live Technical Evidence",
                "fieldtype": "Data",
                "is_required": 1,
                "display_order": 10,
            },
        )
        template.append(
            "statuses",
            {"status_label": "Working", "is_default": 1, "is_complete": 0, "display_order": 10},
        )
        template.append(
            "statuses",
            {"status_label": "Released", "is_default": 0, "is_complete": 1, "display_order": 20},
        )
        template.insert()

        source_annex = frappe.new_doc("Orderlift Annex Document")
        source_annex.template = template.name
        source_annex.reference_doctype = "Sales Order"
        source_annex.reference_name = sales_order.name
        source_annex.company = company.name
        source_annex.status = "Working"
        source_annex.append(
            "values",
            {
                "field_key": "live_technical_evidence",
                "field_label": "Live Technical Evidence",
                "fieldtype": "Data",
                "value": "CRM source remains unchanged",
                "captured_is_required": 1,
                "captured_required_value_mode": "Present",
                "display_order": 10,
            },
        )
        source_annex.insert()

        created = technical_list.create_for_sales_order(sales_order.name)
        revision = frappe.get_doc(
            "Sales Order Technical List Revision", created["revision"]["name"]
        )
        warehouse = frappe.db.get_value(
            "Warehouse",
            {"company": company.name, "is_group": 0, "disabled": 0},
            "name",
        )
        for row in revision.items:
            if row.is_stock_item and not row.warehouse:
                if not warehouse:
                    return {
                        "skipped": True,
                        "reason": f"No enabled leaf Warehouse exists for {company.name}.",
                    }
                row.warehouse = warehouse
            row.procurement_route = route.name
        imported_annexes = frappe.get_all(
            "Orderlift Annex Document",
            filters={
                "reference_doctype": revision.doctype,
                "reference_name": revision.name,
                "source_annex": source_annex.name,
            },
            pluck="name",
        )
        if len(imported_annexes) != 1:
            raise AssertionError("Configured Sales Order annex was not imported exactly once.")
        imported_annex = frappe.get_doc("Orderlift Annex Document", imported_annexes[0])
        if imported_annex.name == source_annex.name or imported_annex.status != "Working":
            raise AssertionError("Imported annex is not an independent draft snapshot.")
        imported_annex.status = "Released"
        imported_annex.save()
        revision.save()

        initial_quantities_match = all(
            row.sales_order_qty == row.execution_qty for row in revision.items
        )
        if not initial_quantities_match:
            raise AssertionError("Initial execution quantities do not match Sales Order quantities.")
        operational_probe = frappe._dict(
            doctype="Pick List",
            docstatus=0,
            locations=[frappe._dict(sales_order=sales_order.name)],
        )
        blocked_before_approval = False
        try:
            technical_procurement.validate_operational_document(operational_probe)
        except frappe.ValidationError as error:
            blocked_before_approval = "No approved Technical List yet" in str(error)
        if not blocked_before_approval:
            raise AssertionError("Pick List was not blocked before Technical List approval.")
        revision.submit()
        revision.reload()
        technical_procurement.validate_operational_document(operational_probe)

        actions = technical_procurement.get_available_actions(
            "Sales Order Technical List Revision", revision.name
        )
        material_request_action = next(
            (
                row
                for row in actions.get("actions") or []
                if row.get("adapter_key") == "revision_to_material_request"
            ),
            None,
        )
        if not material_request_action:
            raise AssertionError("Submitted current revision did not expose Material Request creation.")
        result = technical_procurement.create_material_request(
            revision.name,
            json.dumps(material_request_action["row_ids"]),
        )
        material_request = frappe.get_doc(result["doctype"], result["name"])
        if material_request.docstatus != 0:
            raise AssertionError("Technical procurement did not create a draft Material Request.")
        if not all(row.custom_technical_revision == revision.name for row in material_request.items):
            raise AssertionError("Material Request lineage was not preserved.")

        return {
            "passed": True,
            "sales_order": sales_order.name,
            "company": company.name,
            "technical_list": created["name"],
            "revision": revision.name,
            "item_count": len(revision.items),
            "approval_hash": bool(revision.approval_hash),
            "imported_annex": imported_annex.name,
            "source_annex_unchanged": frappe.db.get_value(
                "Orderlift Annex Document", source_annex.name, "status"
            ) == "Working",
            "material_request": material_request.name,
            "lineage_rows": len(material_request.items),
            "operational_gate": True,
        }
    finally:
        frappe.db.rollback()
        frappe.set_user(original_user)


def _eligible_sales_order():
    rows = frappe.get_all(
        "Sales Order",
        filters={"docstatus": 1, "project": ["is", "set"]},
        fields=["name"],
        order_by="modified desc",
        limit=100,
    )
    for row in rows:
        doc = frappe.get_doc("Sales Order", row.name)
        if doc.items and doc.company and doc.project:
            return doc
    return None
