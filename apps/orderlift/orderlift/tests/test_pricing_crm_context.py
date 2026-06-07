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

        self.assertIn("def get_customer_pricing_context", content)
        self.assertIn('"CRM Segment Assignment"', content)
        self.assertIn("resolve_customer_crm_pricing_context", content)
        self.assertIn("calculate_customer_dynamic_tier", content)
        self.assertIn('"tier_mode"', content)
        self.assertIn('"tier_message"', content)

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
        self.assertIn('label: __("Static List Price")', builder_js)
        self.assertIn('return projected || Number(row.final_sell_unit_price || 0) || staticBaseUnit(row);', builder_js)


if __name__ == "__main__":
    unittest.main()
