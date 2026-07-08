import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
SALES_DOCTYPE_ROOT = APP_ROOT / "orderlift" / "orderlift_sales" / "doctype"


def load_doctype(folder, filename=None):
    filename = filename or folder
    return json.loads((SALES_DOCTYPE_ROOT / folder / f"{filename}.json").read_text())


class TestPricingCrmContextSchema(unittest.TestCase):
    def test_pricing_sheet_uses_crm_context_and_hides_customer_group(self):
        doc = load_doctype("pricing_sheet")
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["party_type"]["options"], "Customer\nLead\nProspect")
        self.assertEqual(fields["party_name"]["fieldtype"], "Dynamic Link")
        self.assertEqual(fields["party_name"]["options"], "party_type")
        self.assertEqual(fields["customer"].get("hidden"), 1)
        self.assertNotIn("reqd", fields["customer"])
        self.assertEqual(fields["crm_business_type"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment"]["options"], "CRM Segment")
        self.assertEqual(fields["customer_type"]["hidden"], 1)
        self.assertNotIn("reqd", fields["customer_type"])

    def test_tier_modifiers_are_scoped_by_crm_context(self):
        doc = load_doctype("pricing_tier_modifier")
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["business_type"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment"]["options"], "CRM Segment")
        self.assertEqual(fields["customer_group"]["hidden"], 1)

    def test_benchmark_rules_are_scoped_by_crm_context(self):
        doc = load_doctype("pricing_benchmark_rule")
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["business_type"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment"]["options"], "CRM Segment")
        self.assertEqual(fields["customer_type"]["hidden"], 1)

    def test_sheet_policy_mapping_can_scope_by_crm_context(self):
        doc = load_doctype("pricing_sheet_scenario_mapping")
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["business_type"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment"]["options"], "CRM Segment")

    def test_pricing_sheet_api_resolves_customer_crm_assignments(self):
        api_path = SALES_DOCTYPE_ROOT / "pricing_sheet" / "pricing_sheet.py"
        content = api_path.read_text()

        self.assertIn("SUPPORTED_PRICING_PARTY_TYPES", content)
        self.assertIn("def get_party_pricing_context", content)
        self.assertIn("def get_customer_pricing_context", content)
        self.assertIn("resolve_party_crm_pricing_context", content)
        self.assertIn('"CRM Segment Assignment"', content)
        self.assertIn("resolve_customer_crm_pricing_context", content)
        self.assertIn("calculate_customer_dynamic_tier", content)
        self.assertIn('"tier_mode"', content)
        self.assertIn('"tier_message"', content)

    def test_pricing_sheet_direct_lead_prospect_quotation_is_wired(self):
        source = (SALES_DOCTYPE_ROOT / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn("def _sync_party_fields", source)
        self.assertIn("def _pricing_party_type", source)
        self.assertIn("quotation.quotation_to = party_type", source)
        self.assertIn("quotation.party_name = party_name", source)
        self.assertIn('"Customer, Lead, or Prospect is required."', source)

    def test_pricing_sheet_builder_uses_permission_aware_party_query(self):
        builder_py = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.py"
        ).read_text()
        builder_js = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.js"
        ).read_text()

        self.assertIn("def party_query", builder_py)
        self.assertIn("DatabaseQuery(party_type).build_match_conditions", builder_py)
        self.assertIn("company_access.customer_query", builder_py)
        self.assertIn("company_access.lead_query", builder_py)
        self.assertIn("company_access.prospect_query", builder_py)
        self.assertIn('query: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.party_query"', builder_js)
        self.assertIn('selectField("party_type"', builder_js)
        self.assertIn('linkField("party_name"', builder_js)
        self.assertIn("routeOpportunity", builder_js)
        self.assertIn("routeAutoSave", builder_js)
        self.assertIn("applyRoutePrefill", builder_js)
        self.assertIn("applyQuotationContext", builder_js)
        self.assertIn("source_quotation", builder_js)
        self.assertIn("link_source_quotation", builder_js)
        self.assertIn("get_quotation_pricing_sheet_source", builder_py)
        self.assertIn("create_pricing_sheet_from_opportunity", builder_py)
        self.assertIn("create_pricing_sheet_from_quotation", builder_py)
        self.assertIn("_create_pricing_sheet_from_source", builder_py)
        self.assertIn("_builder_payload_from_source", builder_py)
        self.assertIn("_quotation_selling_price_list_rows", builder_py)
        self.assertIn("_quotation_line_rows", builder_py)
        self.assertIn('"selected_selling_price_lists": _quotation_selling_price_list_rows(doc)', builder_py)
        self.assertIn('"lines": _quotation_line_rows(doc)', builder_py)
        self.assertIn("STATE.sheet.selected_selling_price_lists = source.selected_selling_price_lists", builder_js)
        self.assertIn("STATE.sheet.lines = source.lines.map(normalizeSourceLine)", builder_js)
        self.assertIn("STATE.sheet.lines = source.items.map(normalizeSourceLine)", builder_js)
        self.assertIn("function normalizeSourceLine", builder_js)
        self.assertIn("_link_sheet_to_source_quotation", builder_py)
        self.assertIn("allow_source_pricing_sheet_update", builder_py)
        self.assertIn("Pricing Sheet created from opportunity", builder_js)
        self.assertIn("applyOpportunityContext(page)", builder_js)
        self.assertIn('STATE.sheet.pricing_mode = "Static"', builder_js)

    def test_status_control_exposes_company_pipeline_quick_actions(self):
        status_api = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "status_control.py").read_text()
        status_js = (APP_ROOT / "orderlift" / "orderlift_crm" / "page" / "status_control" / "status_control.js").read_text()
        status_config = (APP_ROOT / "orderlift" / "orderlift_crm" / "status_config.py").read_text()
        crm_setup = (APP_ROOT / "orderlift" / "orderlift_crm" / "setup.py").read_text()

        self.assertIn("PIPELINE_QUICK_ACTION_FIELDS", status_config)
        self.assertIn("PIPELINE_QUICK_ACTIONS", status_config)
        self.assertIn("get_company_pipeline_quick_actions", status_config)
        self.assertIn("save_company_pipeline_quick_action_keys", status_config)
        self.assertIn("save_quick_actions", status_api)
        self.assertIn('"available_quick_actions": pipeline_quick_action_catalog(document_type)', status_api)
        self.assertIn('"selected_quick_actions": get_company_pipeline_quick_action_keys(document_type, company=selected_company)', status_api)
        self.assertIn("quickActionsSection", status_js)
        self.assertIn("data-save-quick-actions", status_js)
        self.assertIn("custom_opportunity_pipeline_quick_actions", crm_setup)

    def test_pricing_sheet_quotation_generation_carries_context_fields(self):
        source = (SALES_DOCTYPE_ROOT / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn("quotation.taxes_and_charges = self.get(\"taxes_and_charges_template\")", source)
        self.assertIn("quotation.opportunity = self.get(\"opportunity\")", source)
        self.assertIn("quotation.territory = self.get(\"geography_territory\")", source)
        self.assertIn("def _apply_quotation_selected_price_lists", source)
        self.assertIn('quotation.set("selected_selling_price_lists", [])', source)

    def test_pricing_sheet_ui_displays_customer_tier_source(self):
        form_js = (APP_ROOT / "orderlift" / "public" / "js" / "pricing_sheet_form_20260501_110.js").read_text()
        builder_js = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.js"
        ).read_text()

        self.assertIn("Pricing Tier", form_js)
        self.assertIn("Tier Source", form_js)
        self.assertIn("customerPricingTierNotice", builder_js)
        self.assertIn("Tier Source", builder_js)

    def test_pricing_sheet_builder_static_mode_displays_static_price_basis(self):
        builder_js = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.js"
        ).read_text()

        self.assertIn('key === "buy_price" ? "static_list_price" : key', builder_js)
        self.assertIn('label: __("PU List HT")', builder_js)
        self.assertIn('return projected || Number(row.final_sell_unit_price || 0) || staticBaseUnit(row);', builder_js)

    def test_pricing_sheet_builder_separates_admin_static_columns(self):
        builder_js = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.js"
        ).read_text()

        self.assertIn("ADMIN_STATIC_LINE_COLUMNS", builder_js)
        self.assertIn("builder_margin_percent", builder_js)
        self.assertIn("target_margin_percent", builder_js)
        self.assertIn('`${COLUMN_STORAGE_KEY_PREFIX}.admin.${isStaticPricingMode() ? "static" : "dynamic"}`', builder_js)
        self.assertIn('return `${COLUMN_STORAGE_KEY_PREFIX}.agent`;', builder_js)

    def test_lead_and_prospect_manual_tiers_are_pricing_tier_links(self):
        setup_py = (APP_ROOT / "orderlift" / "sales" / "utils" / "pricing_setup.py").read_text()
        hooks_py = (APP_ROOT / "orderlift" / "hooks.py").read_text()

        self.assertIn('"Lead": _prospect_tier_fields(insert_after="custom_crm_segments")', setup_py)
        self.assertIn('"fieldtype": "Link"', setup_py)
        self.assertIn('"options": "Pricing Tier"', setup_py)
        self.assertIn('for doctype in ("Customer", "Prospect", "Lead")', setup_py)
        self.assertIn('"before_save": "orderlift.sales.utils.customer_tier.sync_customer_tier_mode"', hooks_py)
        self.assertIn('"Lead": "public/js/customer_tier_mode.js"', hooks_py)


if __name__ == "__main__":
    unittest.main()
