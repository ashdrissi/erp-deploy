import json
import unittest
from pathlib import Path

from orderlift.document_templates import (
    build_template_snapshot,
    get_annex_completion_diagnostics,
    get_missing_required_values,
    is_required_value_satisfied,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class TestTechnicalListAnnexes(unittest.TestCase):
    def test_target_and_reference_doctypes_are_dynamic_links(self):
        target = self._doctype("orderlift_document_template_target")
        annex = self._doctype("orderlift_annex_document")
        target_fields = {row["fieldname"]: row for row in target["fields"]}
        annex_fields = {row["fieldname"]: row for row in annex["fields"]}

        self.assertEqual(target_fields["target_doctype"]["fieldtype"], "Select")
        target_options = set(str(target_fields["target_doctype"]["options"] or "").split("\n"))
        self.assertEqual(
            target_options,
            {"Opportunity", "Quotation", "Sales Order", "Project", "Forecast Load Plan", "Sales Order Technical List Revision"},
        )
        self.assertEqual(annex_fields["reference_doctype"]["fieldtype"], "Link")
        self.assertEqual(annex_fields["reference_doctype"]["options"], "DocType")

    def test_revision_metadata_is_part_of_template_schema(self):
        target = self._doctype("orderlift_document_template_target")
        status = self._doctype("orderlift_document_template_status")
        field = self._doctype("orderlift_document_template_field")
        target_fields = {row["fieldname"] for row in target["fields"]}
        status_fields = {row["fieldname"] for row in status["fields"]}
        field_fields = {row["fieldname"]: row for row in field["fields"]}

        self.assertTrue(
            {
                "allow_direct_creation",
                "allow_execution_copy",
                "allow_import_from_sales_order",
                "required_for_revision",
                "must_be_complete",
                "default_selected",
                "display_order",
            }.issubset(target_fields)
        )
        self.assertIn("is_complete", status_fields)
        self.assertEqual(field_fields["required_value_mode"]["options"], "Present\nChecked")

    def test_annex_schema_freezes_provenance_and_file_metadata(self):
        annex = self._doctype("orderlift_annex_document")
        value = self._doctype("orderlift_annex_document_value")
        annex_fields = {row["fieldname"]: row for row in annex["fields"]}
        value_fields = {row["fieldname"]: row for row in value["fields"]}

        for fieldname in (
            "origin",
            "source_annex",
            "source_reference_doctype",
            "source_reference_name",
            "source_modified",
            "template_snapshot_json",
            "is_complete",
            "completed_by",
            "completed_on",
            "reference_key",
        ):
            self.assertIn(fieldname, annex_fields)
        self.assertTrue(annex_fields["reference_key"]["unique"])
        self.assertEqual(value_fields["file"]["options"], "File")
        self.assertIn("content_hash", value_fields)
        self.assertIn("captured_metadata_json", value_fields)

    def test_snapshot_and_completion_do_not_depend_on_status_names(self):
        template = {
            "name": "TEST",
            "template_name": "Test",
            "targets": [{"target_doctype": "Concurrent Revision", "must_be_complete": 1}],
            "fields": [
                {
                    "field_key": "serial",
                    "field_label": "Serial",
                    "fieldtype": "Data",
                    "is_required": 1,
                    "required_value_mode": "Present",
                },
                {
                    "field_key": "approved",
                    "field_label": "Approved",
                    "fieldtype": "Check",
                    "is_required": 1,
                    "required_value_mode": "Checked",
                },
            ],
            "statuses": [
                {"status_label": "Open", "is_default": 1, "is_complete": 0},
                {"status_label": "Locked", "is_complete": 1},
            ],
        }
        snapshot = build_template_snapshot(template)
        annex = {
            "status": "Locked",
            "template_snapshot_json": json.dumps(snapshot),
            "values": [
                {"field_key": "serial", "value": "A-1"},
                {"field_key": "approved", "value": "0"},
            ],
        }

        diagnostics = get_annex_completion_diagnostics(annex)

        self.assertFalse(diagnostics["is_complete"])
        self.assertEqual(diagnostics["missing_required_values"][0]["field_key"], "approved")
        annex["values"][1]["value"] = "1"
        self.assertTrue(get_annex_completion_diagnostics(annex)["is_complete"])

    def test_required_value_modes(self):
        self.assertFalse(is_required_value_satisfied("  ", "Present"))
        self.assertTrue(is_required_value_satisfied("0", "Present"))
        self.assertFalse(is_required_value_satisfied("0", "Checked"))
        self.assertTrue(is_required_value_satisfied("true", "Checked"))
        self.assertEqual(
            get_missing_required_values(
                {"fields": [{"field_key": "ok", "field_label": "OK", "is_required": 1, "required_value_mode": "Checked"}]},
                {"ok": 0},
            )[0]["field_key"],
            "ok",
        )

    def test_targets_and_template_deletion_are_not_hardcoded_or_cascaded(self):
        source = (APP_ROOT / "document_templates.py").read_text()

        self.assertNotIn("SUPPORTED_DOCUMENT_TEMPLATE_TARGETS", source)
        self.assertIn('filters={"is_active": 1}', source)
        self.assertIn('frappe.db.count("Orderlift Annex Document"', source)
        self.assertNotIn('frappe.delete_doc("Orderlift Annex Document"', source)

    def _doctype(self, name):
        path = APP_ROOT / "orderlift" / "doctype" / name / f"{name}.json"
        return json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
