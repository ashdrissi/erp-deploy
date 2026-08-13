import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPaymentTermsPolicy(unittest.TestCase):
    def test_agent_rules_define_allowed_payment_terms(self):
        parent = json.loads(
            (APP_ROOT / "orderlift_sales" / "doctype" / "agent_pricing_rules" / "agent_pricing_rules.json").read_text()
        )
        child = json.loads(
            (
                APP_ROOT
                / "orderlift_sales"
                / "doctype"
                / "agent_allowed_payment_terms"
                / "agent_allowed_payment_terms.json"
            ).read_text()
        )

        fields = {field["fieldname"]: field for field in parent["fields"]}
        self.assertEqual(fields["allowed_payment_terms"]["options"], "Agent Allowed Payment Terms")
        self.assertEqual(child["istable"], 1)
        self.assertIn("payment_terms_template", child["field_order"])
        self.assertIn("is_default", child["field_order"])

    def test_runtime_policy_uses_editable_capability_not_commercial_role_names(self):
        source = (APP_ROOT / "orderlift_sales" / "payment_terms_policy.py").read_text()

        self.assertIn("CAPABILITY_QUOTATION_OVERRIDE", source)
        self.assertIn('"Orderlift Admin" in roles', source)
        self.assertNotIn('"Sales User"', source)
        self.assertNotIn('"Sales Manager"', source)
        self.assertIn('doc.set("payment_schedule", [])', source)
        self.assertIn("get_payment_terms(", source)

    def test_sales_order_ui_is_capability_based_and_restricts_templates(self):
        source = (APP_ROOT / "public" / "js" / "sales_order_pricing_visibility_20260803a.js").read_text()

        self.assertIn("orderlift_capabilities?.quotation_override", source)
        self.assertIn('frm.set_query("payment_terms_template"', source)
        self.assertIn('frm.set_df_property("payment_schedule", "read_only"', source)
        self.assertIn("grid.cannot_add_rows = !canOverride", source)
        self.assertIn("policy.allowedTemplates", source)

    def test_setup_seeds_existing_agents_and_reference_permissions(self):
        setup = (APP_ROOT / "scripts" / "setup_payment_terms.py").read_text()
        permissions = (APP_ROOT / "scripts" / "setup_startup_roles.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("def _seed_agent_payment_terms", setup)
        self.assertIn('"Payment Term": SELECT_ONLY', permissions)
        self.assertIn('"Payment Term": MASTER_MANAGER', permissions)
        self.assertIn("apply_sales_order_payment_terms_policy", hooks)


if __name__ == "__main__":
    unittest.main()
