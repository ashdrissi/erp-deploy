import json
import unittest
from pathlib import Path

from orderlift.document_templates import (
    get_document_template_target_label,
    get_supported_document_template_targets,
    normalize_field_key,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class TestDocumentTemplates(unittest.TestCase):
    def test_supported_targets_include_shipment_plan_display_label(self):
        targets = {row["doctype"]: row["label"] for row in get_supported_document_template_targets()}

        self.assertEqual(targets["Opportunity"], "Opportunity")
        self.assertEqual(targets["Project"], "Project")
        self.assertEqual(targets["Quotation"], "Quotation")
        self.assertEqual(targets["Sales Order"], "Sales Order")
        self.assertEqual(targets["Forecast Load Plan"], "Shipment Plan")
        self.assertEqual(get_document_template_target_label("Forecast Load Plan"), "Shipment Plan")

    def test_normalize_field_key_is_stable(self):
        self.assertEqual(normalize_field_key("Fiche de Mesure / Hauteur"), "fiche_de_mesure_hauteur")
        self.assertEqual(normalize_field_key(""), "field")

    def test_template_doctype_schema_contains_required_tables(self):
        doc = self._read_doctype("orderlift_document_template")
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(doc["document_type"], "Setup")
        self.assertEqual(fields["targets"]["options"], "Orderlift Document Template Target")
        self.assertEqual(fields["fields"]["options"], "Orderlift Document Template Field")
        self.assertEqual(fields["statuses"]["options"], "Orderlift Document Template Status")

    def test_template_field_schema_supports_layout_and_advanced_types(self):
        doc = self._read_doctype("orderlift_document_template_field")
        fields = {row["fieldname"]: row for row in doc["fields"]}
        options = fields["fieldtype"]["options"]

        self.assertIn("Section Break", options)
        self.assertIn("Column Break", options)
        self.assertIn("Link", options)
        self.assertIn("Attach", options)
        self.assertIn("Datetime", options)

    def test_annex_doctype_schema_links_to_supported_reference(self):
        doc = self._read_doctype("orderlift_annex_document")
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["template"]["options"], "Orderlift Document Template")
        self.assertEqual(fields["reference_name"]["fieldtype"], "Dynamic Link")
        self.assertEqual(fields["reference_name"]["options"], "reference_doctype")
        self.assertIn("Forecast Load Plan", fields["reference_doctype"]["options"])
        self.assertEqual(fields["values"]["options"], "Orderlift Annex Document Value")

    def test_generic_print_format_targets_annex_document(self):
        path = APP_ROOT / "orderlift" / "print_format" / "orderlift_annex_document" / "orderlift_annex_document.json"
        doc = json.loads(path.read_text())

        self.assertEqual(doc["doctype"], "Print Format")
        self.assertEqual(doc["doc_type"], "Orderlift Annex Document")
        self.assertEqual(doc["name"], "Orderlift Annex Document")

    def test_template_builder_is_separate_page(self):
        manager = json.loads((APP_ROOT / "orderlift" / "page" / "document_template_manager" / "document_template_manager.json").read_text())
        builder = json.loads((APP_ROOT / "orderlift" / "page" / "document_template_builder" / "document_template_builder.json").read_text())

        self.assertEqual(manager["page_name"], "document-template-manager")
        self.assertEqual(builder["page_name"], "document-template-builder")
        self.assertEqual(builder["title"], "Document Template Builder")

    def _read_doctype(self, name):
        path = APP_ROOT / "orderlift" / "doctype" / name / f"{name}.json"
        return json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
