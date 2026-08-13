from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestCommercialPresentation(unittest.TestCase):
    def test_presentation_helper_keeps_summary_and_separate_roles(self):
        source = (APP_ROOT / "orderlift_sales" / "utils" / "commercial_presentation.py").read_text()

        self.assertIn('WITHOUT_DETAILS = "Without details"', source)
        self.assertIn('INCLUDE_IN_SUMMARY = "Include in commercial summary"', source)
        self.assertIn('PRINT_SEPARATELY = "Print separately"', source)
        self.assertIn("calculate_commercial_total", source)
        self.assertIn("custom_commercial_designation", source)
        self.assertIn("custom_dimensioning_multiplier", source)
        self.assertIn("normalize_dimensioning_multiplier", source)

    def test_print_context_creates_only_a_render_time_summary(self):
        source = (APP_ROOT / "utils" / "jinja_helpers.py").read_text()

        self.assertIn("def get_commercial_print_context", source)
        self.assertIn('"name": "__commercial_summary__"', source)
        self.assertIn('"items": [summary, *separate]', source)
        self.assertIn('"rate": amount_ht / commercial_qty', source)

    def test_pricing_sheet_always_generates_detailed_quotation_rows(self):
        source = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn("self._append_detailed_quotation_items(quotation)", source)
        self.assertNotIn('if output_mode in ("sans details", "sans détails"):\n            self._append_grouped_quotation_items(quotation)', source)

    def test_opportunity_and_quotation_use_shared_dimensioning_tool(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn('"Opportunity": [', hooks)
        self.assertIn('"public/js/dimensioning_document_tool_20260724d.js"', hooks)

        tool = (APP_ROOT / "public" / "js" / "dimensioning_document_tool_20260724d.js").read_text()
        self.assertIn('const MULTIPLIER_FIELD = "custom_dimensioning_multiplier"', tool)
        self.assertNotIn("data-dimensioning-multiplier", tool)
        self.assertIn("Number(frm.doc[MULTIPLIER_FIELD] || 1)", tool)
        self.assertIn('x ${__("Qty")}=', tool)

    def test_opportunity_dimensioning_multiplier_is_not_reset_after_adding_items(self):
        tool = (APP_ROOT / "public" / "js" / "dimensioning_document_tool_20260724d.js").read_text()

        self.assertNotIn("await frm.set_value(SET_FIELD, config.name);", tool)
        self.assertEqual(tool.count("set_value(MULTIPLIER_FIELD, 1);"), 1)

    def test_pricing_sheet_dimensioning_multiplier_is_persisted_and_forwarded(self):
        schema = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.json").read_text()
        model = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()
        builder = (APP_ROOT / "orderlift_sales" / "page" / "pricing_sheet_builder" / "pricing_sheet_builder.py").read_text()

        self.assertIn('"fieldname": "dimensioning_multiplier"', schema)
        self.assertIn("row[\"qty\"] = flt(row.get(\"qty\")) * multiplier", model)
        self.assertIn('"dimensioning_multiplier",', builder)
        self.assertIn('"presentation_role",', builder)

    def test_presentation_inheritance_checks_source_document_access(self):
        source = (APP_ROOT / "orderlift_sales" / "utils" / "commercial_presentation.py").read_text()

        self.assertIn('first_source.check_permission("read")', source)
        self.assertIn('source.check_permission("read")', source)

    def test_quotation_header_is_not_inherited_from_opportunity(self):
        source = (APP_ROOT / "orderlift_sales" / "utils" / "commercial_presentation.py").read_text()

        self.assertIn("_should_copy_header_from_source", source)
        self.assertIn('return doc.doctype != "Quotation"', source)
        self.assertIn("Opportunity only controls item-level presentation roles", source)

    def test_opportunity_has_no_commercial_presentation_header_fields(self):
        source = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        opportunity_block = source.split('"Opportunity": [', 1)[1].split('"Opportunity Item": [', 1)[0]

        self.assertNotIn('"fieldname": "custom_presentation_mode"', opportunity_block)
        self.assertNotIn('"fieldname": "custom_commercial_designation"', opportunity_block)
        self.assertNotIn('"fieldname": "custom_commercial_presentation_template"', opportunity_block)
        self.assertIn("_remove_opportunity_commercial_presentation_header_fields", source)

    def test_print_generator_includes_without_details_price_modes(self):
        source = (APP_ROOT / "scripts" / "update_pf.py").read_text()

        self.assertIn('"PU HT Without Details"', source)
        self.assertIn('"PU TTC Without Details"', source)
        self.assertIn('"Prix Unitaire Without Details"', source)


if __name__ == "__main__":
    unittest.main()
