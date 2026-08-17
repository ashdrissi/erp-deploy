import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPartyModelSchema(unittest.TestCase):
    def test_all_parties_share_company_access_and_tax_fields(self):
        company_fields = json.loads((APP_ROOT / "fixtures" / "custom_field_company_scope.json").read_text())
        crm_fields = json.loads((APP_ROOT / "fixtures" / "custom_field_crm_classification.json").read_text())
        by_key = {(row.get("dt"), row.get("fieldname")): row for row in company_fields + crm_fields}

        for doctype in ("Lead", "Prospect", "Customer", "Supplier"):
            self.assertIn((doctype, "custom_company"), by_key)
            self.assertEqual(
                by_key[(doctype, "custom_internal_company_access")]["options"],
                "Party Internal Company Access",
            )
        for doctype in ("Lead", "Prospect", "Customer"):
            for fieldname in (
                "custom_company_communication_section",
                "custom_general_email",
                "custom_general_mobile",
                "custom_general_phone",
                "custom_general_whatsapp",
            ):
                self.assertIn((doctype, fieldname), by_key)
            self.assertEqual(by_key[(doctype, "custom_party_workspace_section")]["fieldtype"], "Section Break")
            self.assertIn((doctype, "custom_party_workspace_html"), by_key)
        self.assertEqual(by_key[("Lead", "custom_tax_id")]["label"], "ICE / Tax ID")
        self.assertEqual(by_key[("Prospect", "custom_tax_id")]["label"], "ICE / Tax ID")

    def test_internal_company_access_primary_column_is_hidden(self):
        doctype = json.loads(
            (APP_ROOT / "orderlift_crm" / "doctype" / "party_internal_company_access" / "party_internal_company_access.json").read_text()
        )
        fields = {row.get("fieldname"): row for row in doctype.get("fields", [])}
        self.assertEqual(fields["is_primary"].get("hidden"), 1)
        self.assertNotEqual(fields["is_primary"].get("in_list_view"), 1)

    def test_downstream_site_and_tax_fields_are_defined(self):
        fields = json.loads((APP_ROOT / "fixtures" / "custom_field_crm_classification.json").read_text())
        keys = {(row.get("dt"), row.get("fieldname")) for row in fields}
        for doctype in ("Opportunity", "Pricing Sheet", "Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "Project"):
            expected = "custom_site_address_name"
            self.assertIn((doctype, expected), keys)
        for doctype in ("Opportunity", "Pricing Sheet", "Project"):
            self.assertIn((doctype, "custom_customer_tax_id"), keys)
        for fieldname in (
            "custom_party_contact",
            "custom_party_contact_email",
            "custom_party_contact_mobile",
            "custom_billing_address_name",
            "custom_shipping_address_name",
        ):
            self.assertIn(("Project", fieldname), keys)

    def test_form_and_conversion_hooks_are_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        party_js = (APP_ROOT / "public" / "js" / "party_form_simplify_20260812a.js").read_text()
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()

        self.assertIn("party_form_simplify_20260812a.js", hooks)
        self.assertIn("apply_sales_order_party_context", hooks)
        self.assertIn("sync_downstream_sales_party_context", hooks)
        self.assertIn("prepare_project_from_opportunity", pipeline)
        self.assertIn("Convert to Customer", party_js)
        self.assertIn("save_party_address", party_js)
        self.assertIn("save_party_contact", party_js)
        self.assertIn("Linked Deals", party_js)
        self.assertIn('"Supplier": "public/js/party_form_simplify_20260812a.js"', hooks)
        self.assertIn('frm.doc.supplier_name', party_js)
        self.assertIn("_ensure_party_field_order", (APP_ROOT / "orderlift_crm" / "setup.py").read_text())


if __name__ == "__main__":
    unittest.main()
