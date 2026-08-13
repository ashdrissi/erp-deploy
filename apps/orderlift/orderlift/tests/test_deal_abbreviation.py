import ast
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestDealAbbreviationContract(unittest.TestCase):
    def test_backend_contract_is_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        module = (APP_ROOT / "orderlift_crm" / "deal_abbreviation.py").read_text()

        self.assertIn('"*": {', hooks)
        self.assertIn("sync_deal_abbreviation", hooks)
        self.assertIn("prepare_deal_abbreviation_name", hooks)
        self.assertIn("sync_submitted_deal_abbreviation", hooks)
        self.assertIn("propagate_opportunity_deal_abbreviation", hooks)
        self.assertIn("orderlift.orderlift_crm.deal_abbreviation.after_migrate", hooks)
        self.assertIn('DEAL_ABBREVIATION_FIELD = "custom_deal_abbreviation"', module)
        self.assertIn('DEAL_SOURCE_FIELD = "custom_deal_opportunity"', module)
        self.assertIn('return f"{doc.name}~{abbreviation}"', module)
        self.assertIn('abbreviation == "MIXED"', module)
        self.assertIn("_amended_deal_name", module)
        self.assertIn("_source_marker(opportunities)", module)
        self.assertIn('frappe.has_permission("Opportunity", "read"', module)
        self.assertIn('doc.check_permission("create" if _document_is_new(doc) else "write")', module)

    def test_fields_are_optional_and_only_anchor_documents_are_editable(self):
        module = (APP_ROOT / "orderlift_crm" / "deal_abbreviation.py").read_text()

        self.assertIn('EDITABLE_DOCTYPES = {"Opportunity", "Sales Order", "Project"}', module)
        self.assertIn('"reqd": 0', module)
        self.assertIn('"read_only": 0 if doctype in EDITABLE_DOCTYPES else 1', module)
        self.assertIn('"allow_on_submit": 1', module)
        self.assertIn('"fieldtype": "Small Text"', module)

    def test_ui_flag_and_opportunity_preform_are_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "deal_abbreviation_20260725a.js").read_text()
        crm_script = (APP_ROOT / "public" / "js" / "crm_classification_20260723a.js").read_text()
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()

        self.assertIn("deal_abbreviation_20260725a.js", hooks)
        self.assertIn('const FIELDNAME = "custom_deal_abbreviation"', script)
        self.assertIn('Deal / ${value}', script)
        self.assertIn('fieldname: "deal_abbreviation"', crm_script)
        self.assertIn('"custom_deal_abbreviation", values.get("deal_abbreviation")', pipeline)

    def test_existing_documents_are_backfilled_without_renaming(self):
        module = (APP_ROOT / "orderlift_crm" / "deal_abbreviation.py").read_text()

        backfill = module.split("def backfill_deal_abbreviations", 1)[1]
        self.assertIn("frappe.db.set_value", backfill)
        self.assertNotIn("rename_doc", backfill)

    def test_after_rename_hook_uses_frappe_signature_and_opportunity_scope(self):
        hooks_source = (APP_ROOT / "hooks.py").read_text()
        module_source = (APP_ROOT / "orderlift_crm" / "deal_abbreviation.py").read_text()

        module_tree = ast.parse(module_source)
        handler = next(
            node
            for node in module_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "update_renamed_deal_opportunity"
        )
        self.assertEqual(
            [argument.arg for argument in handler.args.args[:5]],
            ["doc", "method", "old", "new", "merge"],
        )

        hooks_tree = ast.parse(hooks_source)
        doc_events_node = next(
            node.value
            for node in hooks_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "doc_events" for target in node.targets)
        )
        doc_events = ast.literal_eval(doc_events_node)
        handler_path = "orderlift.orderlift_crm.deal_abbreviation.update_renamed_deal_opportunity"
        self.assertNotIn("after_rename", doc_events["*"])
        self.assertEqual(doc_events["Opportunity"]["after_rename"], handler_path)


if __name__ == "__main__":
    unittest.main()
