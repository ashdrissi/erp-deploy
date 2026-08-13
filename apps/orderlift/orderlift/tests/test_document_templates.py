import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from orderlift.document_templates import (
    delete_template,
    get_template_prefill_values,
    get_document_template_target_label,
    get_supported_document_template_targets,
    normalize_field_key,
    resolve_template_field_value,
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
        self.assertNotIn("reqd", fields["targets"])
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
        self.assertIn("Signature", options)
        self.assertIn("Datetime", options)
        self.assertIn("source_field", fields)
        self.assertTrue(fields["field_key"]["read_only"])

    def test_template_field_prefill_uses_explicit_mapping_then_matching_key(self):
        source = {"customer_name": "Orderlift Maroc", "name": "PROJ-0001"}

        self.assertEqual(
            resolve_template_field_value(source, {"field_key": "client", "source_field": "customer_name"}),
            "Orderlift Maroc",
        )
        self.assertEqual(resolve_template_field_value(source, {"field_key": "name"}), "PROJ-0001")

    def test_template_prefill_preserves_existing_values_and_uses_defaults(self):
        template = {
            "fields": [
                {"field_key": "client", "fieldtype": "Data", "source_field": "customer_name"},
                {"field_key": "project", "fieldtype": "Data"},
                {"field_key": "comment", "fieldtype": "Text", "default_value": "To complete"},
                {"field_key": "section", "fieldtype": "Section Break"},
            ]
        }
        values = get_template_prefill_values(
            template,
            {"customer_name": "Orderlift Maroc", "project": "PROJ-0001"},
            {"client": "Manual client"},
        )

        self.assertEqual(values["client"], "Manual client")
        self.assertEqual(values["project"], "PROJ-0001")
        self.assertEqual(values["comment"], "To complete")
        self.assertNotIn("section", values)

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

    def test_annex_print_format_is_dynamic(self):
        source = (APP_ROOT / "orderlift" / "print_format" / "orderlift_annex_document" / "orderlift_annex_document.html").read_text()

        self.assertIn("ol-annex-page", source)
        self.assertIn("ol-annex-check-option", source)
        self.assertIn(".ol-annex-box.checked:after", source)
        self.assertNotIn("✓", source)
        self.assertIn('field.fieldtype == "Signature"', source)
        self.assertIn('field.fieldtype == "Column Break"', source)
        self.assertIn("template.print_header", source)
        self.assertIn("template.print_footer", source)
        self.assertIn("company.company_name", source)
        self.assertNotIn("ORDER LIFT MOROCCO", source)
        self.assertNotIn("Responsable installation", source)
        self.assertNotIn("Projet N°", source)

    def test_template_builder_is_separate_page(self):
        manager = json.loads((APP_ROOT / "orderlift" / "page" / "document_template_manager" / "document_template_manager.json").read_text())
        builder = json.loads((APP_ROOT / "orderlift" / "page" / "document_template_builder" / "document_template_builder.json").read_text())

        self.assertEqual(manager["page_name"], "document-template-manager")
        self.assertEqual(builder["page_name"], "document-template-builder")
        self.assertEqual(builder["title"], "Document Template Builder")

    def test_template_manager_uses_reference_style_hooks(self):
        source = (APP_ROOT / "orderlift" / "page" / "document_template_manager" / "document_template_manager.js").read_text()

        self.assertIn("odtm-search", source)
        self.assertIn("odtm-metric-icon", source)
        self.assertIn("odtm-row-icon", source)
        self.assertIn("function icon", source)
        self.assertIn("linear-gradient(135deg,#4f6ef7,#7c5cf5)", source)
        self.assertIn('appearance: none !important', source)
        self.assertIn('background-image: url("data:image/svg+xml', source)

    def test_annex_editors_support_dynamic_columns_and_uploads(self):
        for filename in ("document_annex_dialog_20260519a.js", "document_annex_tabs_20260519a.js"):
            with self.subTest(filename=filename):
                source = (APP_ROOT / "public" / "js" / filename).read_text()
                self.assertIn("splitFieldLayout", source)
                self.assertIn('field.fieldtype === "Column Break"', source)
                self.assertIn("frappe.ui.FileUploader", source)
                self.assertIn('"Attach Image", "Signature"', source)

    def test_template_builder_exposes_target_selection_and_source_mapping(self):
        source = (APP_ROOT / "orderlift" / "page" / "document_template_builder" / "document_template_builder.js").read_text()

        self.assertIn('["targets", "Target Documents"]', source)
        self.assertIn('STATE.activeStep === "targets"', source)
        self.assertIn('"source_field"', source)
        self.assertIn('data-preview-template', source)
        self.assertIn('Annex Template Preview', source)
        self.assertIn('min-width:0', source)
        self.assertIn('input[type="checkbox"]', source)
        self.assertIn('accent-color:#2563eb', source)
        self.assertIn('expandedFields', source)
        self.assertIn('data-toggle-field', source)
        self.assertIn('odtb-order-pill', source)
        self.assertIn('odtb-field-card.expanded .odtb-field-card-body', source)
        self.assertIn('appearance: none !important', source)
        self.assertIn('background-image: url("data:image/svg+xml', source)
        self.assertIn('Signature', source)
        self.assertIn('data-add-layout="Column Break"', source)
        self.assertIn('data-add-layout="HTML"', source)
        self.assertIn('Key (automatic)', source)
        self.assertIn('Advanced Settings', source)
        self.assertIn('previewFieldsMarkup', source)
        self.assertNotIn('ORDER LIFT MOROCCO', source)
        self.assertNotIn('info@orderlift.net', source)
        self.assertNotIn('Tanja Balia', source)

    def test_standard_project_template_seed_contains_both_supplied_forms(self):
        source = (APP_ROOT / "scripts" / "setup_document_templates.py").read_text()

        self.assertIn('"Prise des mesures"', source)
        self.assertIn('"Information du Projet"', source)
        self.assertIn('{"target_doctype": "Project"}', source)
        self.assertIn('"Voile de gaine en béton"', source)

    def test_delete_template_cascades_annexes_before_the_template(self):
        deleted = []
        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda message: message
        frappe_stub.PermissionError = PermissionError
        frappe_stub.session = types.SimpleNamespace(user="Administrator")
        frappe_stub.db = types.SimpleNamespace(commit=lambda: None)
        frappe_stub.get_doc = lambda doctype, name: types.SimpleNamespace(name=name, template_name="Test Template")
        frappe_stub.get_all = lambda *args, **kwargs: ["ANNEX-0001", "ANNEX-0002"]
        frappe_stub.delete_doc = lambda *args, **kwargs: deleted.append((args, kwargs))

        with patch.dict(sys.modules, {"frappe": frappe_stub}):
            result = delete_template("Test Template")

        self.assertEqual(result, {"template_name": "Test Template", "annex_count": 2})
        self.assertEqual([row[0][:2] for row in deleted], [
            ("Orderlift Annex Document", "ANNEX-0001"),
            ("Orderlift Annex Document", "ANNEX-0002"),
            ("Orderlift Document Template", "Test Template"),
        ])
        self.assertTrue(all(row[1]["force"] for row in deleted))
        self.assertTrue(all(row[1]["ignore_permissions"] for row in deleted))

    def test_template_pages_require_typed_confirmation_for_cascade_delete(self):
        manager = (APP_ROOT / "orderlift" / "page" / "document_template_manager" / "document_template_manager.js").read_text()
        builder = (APP_ROOT / "orderlift" / "page" / "document_template_builder" / "document_template_builder.js").read_text()

        for source in (manager, builder):
            self.assertIn('data-delete-template', source)
            self.assertIn('Type the template name to confirm', source)
            self.assertIn('orderlift.document_templates.delete_template', source)

    def _read_doctype(self, name):
        path = APP_ROOT / "orderlift" / "doctype" / name / f"{name}.json"
        return json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
