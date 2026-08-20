import importlib
import json
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class Row(dict):
    __getattr__ = dict.get


class TestAnnexChain(unittest.TestCase):
    def test_annex_schema_has_freeze_and_hash_fields(self):
        payload = json.loads(
            (APP_ROOT / "orderlift" / "doctype" / "orderlift_annex_document" / "orderlift_annex_document.json").read_text()
        )
        fields = {row["fieldname"]: row for row in payload["fields"]}
        for fieldname in (
            "source_content_hash",
            "is_frozen",
            "content_hash",
            "frozen_on",
            "frozen_by",
        ):
            self.assertIn(fieldname, fields)
        self.assertIn("Opportunity Snapshot", fields["origin"]["options"])
        self.assertIn("Execution Copy", fields["origin"]["options"])
        self.assertIn("Submitted Copy", fields["origin"]["options"])

    def test_template_target_supports_general_execution_copy(self):
        payload = json.loads(
            (
                APP_ROOT
                / "orderlift"
                / "doctype"
                / "orderlift_document_template_target"
                / "orderlift_document_template_target.json"
            ).read_text()
        )
        fields = {row["fieldname"]: row for row in payload["fields"]}
        self.assertIn("allow_execution_copy", fields)
        self.assertIn("copy_after_submit", fields)
        self.assertIn("copy_to_doctypes", fields)
        self.assertTrue(fields["allow_import_from_sales_order"].get("hidden"))
        self.assertTrue(fields["allow_execution_copy"].get("hidden"))
        self.assertTrue(fields["copy_after_submit"].get("hidden"))

    def test_revision_has_fixed_annex_tab_and_hash_manifest(self):
        revision = json.loads(
            (
                APP_ROOT
                / "orderlift_sig"
                / "doctype"
                / "sales_order_technical_list_revision"
                / "sales_order_technical_list_revision.json"
            ).read_text()
        )
        fields = {row["fieldname"]: row for row in revision["fields"]}
        self.assertEqual(fields["fiches_annexes_tab"]["fieldtype"], "Tab Break")
        self.assertEqual(fields["fiches_annexes_html"]["fieldtype"], "HTML")

        manifest = json.loads(
            (
                APP_ROOT
                / "orderlift_sig"
                / "doctype"
                / "sales_order_technical_list_annex"
                / "sales_order_technical_list_annex.json"
            ).read_text()
        )
        manifest_fields = {row["fieldname"] for row in manifest["fields"]}
        self.assertIn("annex_content_hash", manifest_fields)
        self.assertIn("source_content_hash", manifest_fields)

    def test_lifecycle_hooks_and_fixed_tab_setup_are_wired(self):
        from orderlift import hooks

        self.assertIn("orderlift.annex_chain.after_migrate", hooks.after_migrate)
        self.assertIn("orderlift.annex_chain.on_quotation_submit", hooks.doc_events["Quotation"]["before_submit"])
        self.assertIn("orderlift.annex_chain.on_sales_order_submit", hooks.doc_events["Sales Order"]["before_submit"])
        self.assertIn("orderlift.annex_chain.sync_quotation_annexes", hooks.doc_events["Quotation"]["on_update"])
        self.assertIn("orderlift.annex_chain.sync_sales_order_annexes", hooks.doc_events["Sales Order"]["on_update"])
        self.assertIn("orderlift.annex_chain.sync_project_annexes", hooks.doc_events["Project"]["on_update"])

        source = (APP_ROOT / "annex_chain.py").read_text()
        for doctype in ("Quotation", "Sales Order", "Project"):
            self.assertIn(f'"{doctype}": [', source)
        self.assertIn('"custom_fiches_annexes_tab"', source)
        self.assertIn('"custom_fiches_annexes_html"', source)

    def test_content_hash_is_deterministic_and_value_sensitive(self):
        sys.modules.pop("orderlift.annex_chain", None)
        module = importlib.import_module("orderlift.annex_chain")
        annex = Row(
            template="Template",
            template_name="Template",
            status="Draft",
            reference_doctype="Quotation",
            reference_name="QTN-1",
            origin="Native",
            template_snapshot_json='{"fields": []}',
            values=[Row(field_key="a", field_label="A", fieldtype="Data", value="one", idx=1)],
        )
        first = module.compute_annex_content_hash(annex)
        second = module.compute_annex_content_hash(annex)
        self.assertEqual(first, second)
        annex["values"][0]["value"] = "two"
        self.assertNotEqual(first, module.compute_annex_content_hash(annex))

    def test_workspace_and_popup_use_exact_annex_identity(self):
        workspace = (APP_ROOT / "public" / "js" / "fiches_annexes_workspace_20260816a.js").read_text()
        dialog = (APP_ROOT / "public" / "js" / "document_annex_dialog_20260519a.js").read_text()
        css = (APP_ROOT / "public" / "css" / "fiches_annexes_workspace_20260816a.css").read_text()
        backend = (APP_ROOT / "document_templates.py").read_text()

        self.assertIn('role="tablist"', workspace)
        self.assertIn("ArrowLeft", workspace)
        self.assertIn("data-fa-source", workspace)
        self.assertIn("create_execution_copy", workspace)
        self.assertIn("onlyAnnex: Boolean(entry.template)", workspace)
        self.assertIn("annex_name: dialogOptions.annexName", dialog)
        self.assertIn("expected_modified", dialog)
        self.assertIn("if (!WORKSPACE_DOCTYPES.has(doctype))", dialog)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("annex_name: str | None = None", backend)
        self.assertIn("_template_payload_from_definition", backend)
        self.assertIn("expect_absent", dialog)
        self.assertIn("READ_ONLY_SNAPSHOT_ORIGINS", backend)

    def test_revision_imports_enforce_sales_order_lineage(self):
        backend = (APP_ROOT / "document_templates.py").read_text()
        self.assertIn("source_annex.reference_name != revision.sales_order", backend)
        self.assertIn("explicit_name != linked_name", backend)
        self.assertIn("lock_annex_reference(reference_doctype, reference_name)", backend)

    def test_annex_tab_always_anchors_to_the_end_of_the_form(self):
        source = (APP_ROOT / "annex_chain.py").read_text()
        anchor_body = source.split("def terminal_anchor", 1)[1].split("create_custom_fields(", 1)[0]
        self.assertIn("reversed(meta.fields)", anchor_body)
        self.assertNotIn("if meta.get_field(preferred)", anchor_body)
        self.assertIn("must land at the very end", anchor_body)

    def test_workspace_omits_technical_phase_when_no_revision_exists(self):
        source = (APP_ROOT / "annex_chain.py").read_text()
        workspace_source = source.split("def get_annex_workspace", 1)[1]
        project_block = workspace_source.split('elif reference_doctype == "Project":', 1)[1].split(
            "contexts =", 1
        )[0]
        self.assertIn("if selected_revisions:", project_block)
        self.assertIn('context.get("current_revision") or context.get("open_revision")', project_block)


if __name__ == "__main__":
    unittest.main()
