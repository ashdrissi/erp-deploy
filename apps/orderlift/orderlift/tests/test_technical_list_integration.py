import json
import unittest
from pathlib import Path

from orderlift import hooks


APP_ROOT = Path(__file__).resolve().parents[1]


class TestTechnicalListIntegration(unittest.TestCase):
    def test_hooks_wire_lifecycle_procurement_and_assets(self):
        sales_order = hooks.doc_events["Sales Order"]
        self.assertIn(
            "orderlift.orderlift_sig.technical_list.on_sales_order_submit_or_project_link",
            sales_order["on_submit"],
        )
        guard = "orderlift.orderlift_logistics.technical_procurement.validate_procurement_document"
        for doctype in ("Material Request", "Request for Quotation", "Purchase Order"):
            self.assertIn(guard, hooks.doc_events[doctype]["before_validate"])
        self.assertIn(guard, hooks.doc_events["Supplier Quotation"]["before_validate"])
        self.assertIn(
            "orderlift.company_scope.apply_transaction_company_scope",
            hooks.doc_events["Supplier Quotation"]["before_validate"],
        )
        operational_guard = "orderlift.orderlift_logistics.technical_procurement.validate_operational_document"
        self.assertEqual(hooks.doc_events["Pick List"]["before_validate"], operational_guard)
        self.assertIn(operational_guard, hooks.doc_events["Delivery Note"]["before_validate"])
        self.assertNotIn(
            "technical_procurement",
            json.dumps(hooks.doc_events.get("Sales Invoice", {})),
        )
        self.assertIn(
            "public/js/sales_order_technical_list_20260815f.js",
            hooks.doctype_js["Sales Order"],
        )
        self.assertIn(
            "public/js/project_technical_lists_20260815d.js",
            hooks.doctype_js["Project"],
        )

    def test_migration_installs_company_policy_and_lineage(self):
        self.assertIn("orderlift.orderlift_sig.technical_list.after_migrate", hooks.after_migrate)
        self.assertIn(
            "orderlift.orderlift_logistics.technical_procurement.after_migrate",
            hooks.after_migrate,
        )
        core = (APP_ROOT / "orderlift_sig" / "technical_list.py").read_text()
        for fieldname in (
            "custom_enable_sales_order_technical_lists",
            "custom_technical_list_business_types",
            "custom_technical_list_default_procurement_route",
        ):
            self.assertIn(fieldname, core)
        procurement = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        for fieldname in (
            "custom_technical_list",
            "custom_technical_revision",
            "custom_technical_revision_item",
            "custom_technical_approval_hash",
        ):
            self.assertIn(fieldname, procurement)
        self.assertIn('route_name = "Approved Technical List to Material Request"', procurement)

    def test_client_settings_and_sales_order_actions_are_simplified(self):
        core = (APP_ROOT / "orderlift_sig" / "technical_list.py").read_text()
        editing = core.split('"fieldname": "custom_technical_list_editing_section"', 1)[1]
        execution = core.split('"fieldname": "custom_technical_list_execution_section"', 1)[1]
        self.assertIn('"hidden": 1', editing.split("},", 1)[0])
        self.assertIn('"hidden": 1', execution.split("},", 1)[0])
        self.assertIn("_backfill_internal_company_defaults()", core)

        sales_order_js = (APP_ROOT / "public" / "js" / "sales_order_technical_list_20260815f.js").read_text()
        project_js = (APP_ROOT / "public" / "js" / "project_technical_lists_20260815d.js").read_text()
        self.assertNotIn("removeNativeProcurementButtons", sales_order_js)
        self.assertIn("installNativeCreateGuard", sales_order_js)
        self.assertIn("No approved Technical List yet", sales_order_js)
        self.assertIn("executionItemsMarkup", sales_order_js)
        self.assertIn("data-tl-annexes", sales_order_js)
        self.assertNotIn("data-tl-item-search", sales_order_js)
        self.assertNotIn("data-tl-item-filter", sales_order_js)
        self.assertIn("@media(max-width:680px)", sales_order_js)
        self.assertIn("@media(prefers-reduced-motion:reduce)", sales_order_js)
        self.assertIn("--tl-muted:#334155", sales_order_js)
        self.assertIn("ol-project-tl-card ol-sales-tl-card", sales_order_js)
        self.assertIn("data-tl-toggle-items", sales_order_js)
        self.assertIn("Number(this.dataset.index) >= 6", sales_order_js)
        self.assertIn("Create Revision", sales_order_js)
        self.assertIn("No revision created yet", sales_order_js)
        self.assertIn("missingRevisionMarkup", sales_order_js)
        self.assertIn("itemsMarkup", project_js)
        self.assertIn("data-project-annexes", project_js)
        self.assertIn("data-technical-annexes", project_js)
        self.assertIn("data-project-toggle-items", project_js)
        self.assertIn("Number(this.dataset.index) >= 6", project_js)
        self.assertIn("color:#111827", project_js)

    def test_manager_and_dynamic_annex_targets_exist(self):
        page = json.loads(
            (
                APP_ROOT
                / "orderlift_sig"
                / "page"
                / "technical_list_manager"
                / "technical_list_manager.json"
            ).read_text()
        )
        self.assertEqual(page["page_name"], "technical-list-manager")
        target = json.loads(
            (
                APP_ROOT
                / "orderlift"
                / "doctype"
                / "orderlift_document_template_target"
                / "orderlift_document_template_target.json"
            ).read_text()
        )
        fields = {row["fieldname"]: row for row in target["fields"]}
        self.assertEqual(fields["target_doctype"]["fieldtype"], "Select")
        target_options = set(str(fields["target_doctype"]["options"] or "").split("\n"))
        self.assertIn("Sales Order Technical List Revision", target_options)
        self.assertNotIn("DocType", target_options)
        self.assertIn("required_for_revision", fields)
        self.assertIn("allow_import_from_sales_order", fields)

    def test_manager_skips_transition_lookup_without_an_active_workflow(self):
        manager = (
            APP_ROOT
            / "orderlift_sig"
            / "page"
            / "technical_list_manager"
            / "technical_list_manager.py"
        ).read_text()
        transition_helper = manager.split("def _available_transitions", 1)[1].split(
            "def _route_for_created_result", 1
        )[0]

        self.assertIn("frappe.db.get_value(", transition_helper)
        self.assertIn('"Workflow"', transition_helper)
        self.assertIn("if not workflow:\n        return []", transition_helper)


if __name__ == "__main__":
    unittest.main()
