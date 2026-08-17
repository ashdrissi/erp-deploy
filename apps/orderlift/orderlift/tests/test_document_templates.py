import json
import unittest
from pathlib import Path

from orderlift.document_templates import (
    _annex_is_read_only,
    _is_revision_owned,
    _target_allows_direct_creation,
    get_template_prefill_values,
    get_document_template_target_label,
    normalize_field_key,
    resolve_template_field_value,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class TestDocumentTemplates(unittest.TestCase):
    def test_supported_targets_are_configured_as_dynamic_doctype_links(self):
        target = self._read_doctype("orderlift_document_template_target")
        fields = {row["fieldname"]: row for row in target["fields"]}

        self.assertEqual(fields["target_doctype"]["fieldtype"], "Select")
        options = set(str(fields["target_doctype"]["options"] or "").split("\n"))
        self.assertTrue({"Opportunity", "Quotation", "Sales Order", "Project", "Forecast Load Plan", "Sales Order Technical List Revision"}.issubset(options))
        self.assertNotIn("DocType", options)
        self.assertEqual(get_document_template_target_label("Forecast Load Plan"), "Forecast Load Plan")

    def test_target_settings_explain_their_behavior(self):
        target = self._read_doctype("orderlift_document_template_target")
        fields = {row["fieldname"]: row for row in target["fields"]}
        for fieldname in (
            "allow_direct_creation",
            "allow_execution_copy",
            "required_for_revision",
            "must_be_complete",
            "default_selected",
        ):
            self.assertTrue(fields[fieldname].get("description"), fieldname)
        builder = (APP_ROOT / "orderlift" / "page" / "document_template_builder" / "document_template_builder.js").read_text()
        self.assertIn('check("required_for_revision", __("Required for Revision")', builder)
        self.assertIn('check("must_be_complete", __("Must Be Complete")', builder)
        self.assertIn('check("default_selected", __("Selected by Default")', builder)

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
        self.assertEqual(fields["reference_doctype"]["fieldtype"], "Link")
        self.assertEqual(fields["reference_doctype"]["options"], "DocType")
        self.assertEqual(fields["values"]["options"], "Orderlift Annex Document Value")

    def test_revision_ownership_metadata_does_not_lock_sales_order_annexes(self):
        definition = {
            "revision_owned": True,
            "targets": [
                {"target_doctype": "Sales Order", "allow_direct_creation": 1},
                {"target_doctype": "Sales Order Technical List Revision", "allow_direct_creation": 1},
            ],
        }

        self.assertFalse(
            _is_revision_owned({"reference_doctype": "Sales Order"}, definition)
        )
        self.assertTrue(
            _is_revision_owned(
                {"reference_doctype": "Sales Order Technical List Revision"},
                definition,
            )
        )

    def test_snapshot_origins_are_backend_read_only(self):
        self.assertTrue(_annex_is_read_only({"origin": "Opportunity Snapshot"}))
        self.assertTrue(_annex_is_read_only({"origin": "Quotation Snapshot"}))
        self.assertFalse(_annex_is_read_only({"origin": "Execution Copy"}))

    def test_direct_creation_uses_target_policy(self):
        template = {
            "is_active": 1,
            "targets": [{"target_doctype": "Quotation", "allow_direct_creation": 0}],
            "fields": [],
            "statuses": [],
        }
        self.assertFalse(_target_allows_direct_creation(template, "Quotation"))
        template["targets"][0]["allow_direct_creation"] = 1
        self.assertTrue(_target_allows_direct_creation(template, "Quotation"))

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
        self.assertIn("annex_print_template(doc)", source)
        self.assertNotIn("parse_json", source)
        self.assertNotIn("ORDER LIFT MOROCCO", source)
        self.assertNotIn("Responsable installation", source)
        self.assertNotIn("Projet N°", source)

    def test_bootstrap_offers_curated_business_targets(self):
        source = (APP_ROOT / "document_templates.py").read_text()
        self.assertIn('"available_targets": DOCUMENT_TEMPLATE_TARGET_DOCTYPES', source)
        self.assertIn('"Forecast Load Plan"', source)
        self.assertNotIn('"available_targets": frappe.get_all(\n            "DocType"', source)

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
        dialog = (APP_ROOT / "public" / "js" / "document_annex_dialog_20260519a.js").read_text()
        self.assertIn("bundle.read_only", dialog)
        self.assertIn("lecture seule", dialog)
        self.assertIn("expect_absent", dialog)

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

    def test_used_templates_are_protected_from_cascade_deletion(self):
        source = (APP_ROOT / "document_templates.py").read_text()

        delete_body = source.split("def delete_template", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('frappe.db.count("Orderlift Annex Document"', delete_body)
        self.assertIn("cannot be deleted", delete_body)
        self.assertNotIn('frappe.delete_doc("Orderlift Annex Document"', delete_body)

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
