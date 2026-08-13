import json
import unittest
from pathlib import Path

from orderlift.quotation_detail_templates import (
    BLOCK_TYPES,
    QUOTATION_SNAPSHOT_FIELD,
    QUOTATION_TEMPLATE_FIELD,
    build_print_context,
    normalize_block_key,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class TestQuotationDetailTemplates(unittest.TestCase):
    def test_doctype_schema_supports_blocks_and_company_scope(self):
        template = self._read_doctype("orderlift_quotation_detail_template")
        block = self._read_doctype("orderlift_quotation_detail_template_block")
        template_fields = {row["fieldname"]: row for row in template["fields"]}
        block_fields = {row["fieldname"]: row for row in block["fields"]}

        self.assertEqual(template_fields["blocks"]["options"], "Orderlift Quotation Detail Template Block")
        self.assertEqual(template_fields["company"]["options"], "Company")
        self.assertIn("Annex Field", block_fields["block_type"]["options"])
        self.assertEqual(block_fields["annex_template"]["options"], "Orderlift Document Template")

    def test_block_key_and_print_context_are_stable(self):
        self.assertEqual(normalize_block_key("Description Technique / Charge"), "description_technique_charge")
        doc = {
            QUOTATION_SNAPSHOT_FIELD: json.dumps(
                {
                    "template": "Orderlift Proposal - Ascenseur",
                    "template_name": "Orderlift Proposal - Ascenseur",
                    "blocks": [
                        {"key": "title", "label": "Title", "type": "Heading", "value": "DESCRIPTION"},
                        {"key": "list", "label": "List", "type": "List", "value": "A\nB"},
                    ],
                }
            )
        }

        context = build_print_context(doc)

        self.assertTrue(context["enabled"])
        self.assertEqual(context["template_name"], "Orderlift Proposal - Ascenseur")
        self.assertEqual(context["blocks"][1]["items"], ["A", "B"])

    def test_manager_has_quotation_and_annex_tabs(self):
        manager = (APP_ROOT / "orderlift" / "page" / "document_template_manager" / "document_template_manager.js").read_text()

        self.assertIn('activeTab: "quotation"', manager)
        self.assertIn('tabButton("quotation"', manager)
        self.assertIn('tabButton("annexes"', manager)
        self.assertIn("get_quotation_template_manager_bootstrap", manager)
        self.assertIn("data-copy-quotation-template", manager)
        self.assertIn("copy_quotation_template_to_company", manager)
        self.assertIn("allowedCompanies", manager)

    def test_builder_page_and_quotation_form_are_wired(self):
        page = json.loads((APP_ROOT / "orderlift" / "page" / "quotation_detail_template_builder" / "quotation_detail_template_builder.json").read_text())
        hooks = (APP_ROOT / "hooks.py").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_detail_template_dialog_20260809d.js").read_text()

        self.assertEqual(page["page_name"], "quotation-detail-template-builder")
        self.assertIn("quotation_detail_template_dialog_20260809d.js", hooks)
        self.assertIn("get_quotation_detail_print_context", hooks)
        self.assertIn(QUOTATION_TEMPLATE_FIELD, pricing_setup)
        self.assertIn(QUOTATION_SNAPSHOT_FIELD, pricing_setup)
        self.assertIn("custom_commercial_presentation_editor", pricing_setup)
        self.assertIn("save_quotation_detail_snapshot", script)
        self.assertIn("custom_commercial_presentation_template(frm)", script)
        self.assertIn("refreshTemplateAvailability", script)
        self.assertIn("renderInlineEditor", script)
        self.assertIn("inlineSummaryMarkup", script)
        self.assertIn("Commercial Presentation and Details", script)
        self.assertIn("ol-quote-detail-inline", script)
        self.assertIn("Live Preview", script)
        self.assertIn("optionLines", script)

    def test_quotation_template_eligibility_checks_annex_activation(self):
        source = (APP_ROOT / "quotation_detail_templates.py").read_text()

        self.assertIn("_template_ineligibility_reason", source)
        self.assertIn("_annex_template_enabled_for_any_reference", source)
        self.assertIn("fallback_reason", source)
        self.assertIn("Orderlift Document Template Target", source)

    def test_quotation_detail_builder_has_preview_and_overflow_safe_rows(self):
        source = (APP_ROOT / "orderlift" / "page" / "quotation_detail_template_builder" / "quotation_detail_template_builder.js").read_text()

        self.assertIn('data-preview-template', source)
        self.assertIn('Quotation Detail Preview', source)
        self.assertIn('min-width:0', source)
        self.assertIn('input[type="checkbox"]', source)
        self.assertIn('accent-color:#2563eb', source)
        self.assertIn('annexTemplateOptions', source)
        self.assertIn('annexFieldOptions', source)
        self.assertIn('quotationFieldOptions', source)
        self.assertIn('Resolved by source', source)
        self.assertIn('usesExternalSource', source)
        self.assertIn('sourceContentNotice', source)
        self.assertIn('Source-backed blocks do not use default text or option lists.', source)
        self.assertIn('allowedCompanies', source)
        self.assertIn('companyOptions', source)
        self.assertIn('oqtb-block-toolbar', source)
        self.assertIn('oqtb-add-break', source)
        self.assertIn('toolbarGroup', source)
        self.assertIn('oqtb-toolbar-group', source)
        self.assertIn('Quotation Field', source)
        self.assertIn('Annex Field', source)
        self.assertIn('oqtb-palette-title', source)
        self.assertIn('blockIcon', source)
        self.assertIn('type-source', source)
        self.assertIn('typeClass', source)
        self.assertIn('oqtb-builder-layout', source)
        self.assertIn('expanded .oqtb-block-card-body', source)
        self.assertIn('oqtb-page-break-panel', source)
        self.assertIn('oqtb-subsection-grid', source)
        self.assertIn('appearance: none !important', source)
        self.assertIn('background-image: url("data:image/svg+xml', source)
        self.assertIn('linear-gradient(135deg,#4f6ef7,#7c5cf5)', source)

    def test_builder_bootstrap_exposes_selectable_sources(self):
        source = (APP_ROOT / "quotation_detail_templates.py").read_text()

        self.assertIn('"quotation_fields"', source)
        self.assertIn('"annex_templates"', source)
        self.assertIn('"allowed_companies"', source)
        self.assertIn("_quotation_field_options", source)
        self.assertIn("_annex_template_options", source)

    def test_print_formats_replace_item_table_with_detail_offer_when_enabled(self):
        for relative in ("print_formats/orderlift_quotation.html", "print_formats/orderlift_quotation_tr.html"):
            with self.subTest(format=relative):
                source = (APP_ROOT / relative).read_text()

                self.assertIn("render_quotation_detail_offer_pages", source)
                self.assertIn("{% if ol_detail.enabled %}", source)
                self.assertIn("{{ render_quotation_detail_offer_pages() }}", source)
                self.assertIn("{{ render_totals_and_signatures() }}", source)
                self.assertIn("ol-detail-proposal", source)
                self.assertNotIn("{{ render_quotation_detail_pages() }}", source)
                self.assertNotIn("Orderlift Proposal - Ascenseur", source)

    def test_copy_template_to_company_enforces_company_scope(self):
        source = (APP_ROOT / "quotation_detail_templates.py").read_text()

        self.assertIn("def copy_quotation_template_to_company", source)
        self.assertIn("_require_company_scope(target_company)", source)
        self.assertIn("_require_company_scope(source.company or \"\")", source)
        self.assertIn("_unique_template_name", source)

    def test_one_shot_script_is_not_registered_after_migrate(self):
        script = (APP_ROOT / "scripts" / "setup_quotation_detail_template.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("This is intentionally not registered", script)
        self.assertIn("Orderlift Proposal - Ascenseur", script)
        self.assertNotIn("setup_quotation_detail_template", hooks)
        self.assertIn("Annex Field", BLOCK_TYPES)

    def _read_doctype(self, name):
        path = APP_ROOT / "orderlift" / "doctype" / name / f"{name}.json"
        return json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
