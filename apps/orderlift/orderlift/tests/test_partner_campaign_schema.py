import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]


class TestPartnerCampaignSchema(unittest.TestCase):
    def test_custom_field_fixture_uses_custom_prefix_and_required_links(self):
        fixture_path = APP_ROOT / "orderlift" / "fixtures" / "custom_field_partner_campaign_crm.json"
        fields = json.loads(fixture_path.read_text())
        classification_fixture_path = APP_ROOT / "orderlift" / "fixtures" / "custom_field_crm_classification.json"
        classification_fields = json.loads(classification_fixture_path.read_text())
        status_fixture_path = APP_ROOT / "orderlift" / "fixtures" / "custom_field_status_control.json"
        status_fields = json.loads(status_fixture_path.read_text())

        names = {row["name"] for row in fields}
        fieldnames = {row["fieldname"] for row in fields}
        classification_names = {row["name"] for row in classification_fields}
        classification_fieldnames = {row["fieldname"] for row in classification_fields}
        status_names = {row["name"] for row in status_fields}
        status_fieldnames = {row["fieldname"] for row in status_fields}

        self.assertTrue(all(row["fieldname"].startswith("custom_") for row in fields))
        self.assertTrue(all(row["fieldname"].startswith("custom_") for row in classification_fields))
        self.assertTrue(all(row["fieldname"].startswith("custom_") for row in status_fields))
        self.assertIn("Opportunity-custom_installation_stage", names)
        self.assertIn("Item Price-custom_supplier_payment_mode", names)
        self.assertIn("custom_partner_campaign", fieldnames)
        self.assertIn("custom_partner_campaign_target", fieldnames)
        self.assertIn("Lead-custom_crm_segments", classification_names)
        self.assertIn("Prospect-custom_crm_segments", classification_names)
        self.assertIn("Customer-custom_crm_segments", classification_names)
        self.assertIn("Opportunity-custom_crm_business_type", classification_names)
        self.assertIn("Opportunity-custom_crm_segment", classification_names)
        self.assertIn("custom_crm_segments", classification_fieldnames)
        self.assertIn("Sales Stage-custom_sequence", status_names)
        self.assertIn("Project-custom_project_status", status_names)
        self.assertIn("Sales Order-custom_orderlift_order_status", status_names)
        self.assertIn("custom_color", status_fieldnames)
        self.assertIn("custom_orderlift_order_status", status_fieldnames)

    def test_partner_campaign_doctype_has_required_child_tables_and_kpis(self):
        doctype_path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_crm"
            / "doctype"
            / "partner_campaign"
            / "partner_campaign.json"
        )
        doc = json.loads(doctype_path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["items"]["options"], "Partner Campaign Item")
        self.assertEqual(fields["targets"]["options"], "Partner Campaign Target")
        self.assertEqual(fields["price_list_filter"]["options"], "Price List")
        self.assertEqual(fields["item_group_filter"]["options"], "Item Group")
        self.assertIn("opportunity_count", fields)
        self.assertIn("quotation_amount", fields)
        self.assertIn("sales_order_amount", fields)
        self.assertEqual(fields["business_type_filter"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment_filter"]["options"], "CRM Segment")

    def test_config_doctypes_are_setup_documents(self):
        for doctype in [
            "partner_campaign_status",
            "installation_stage",
            "partner_segment",
            "crm_business_type",
            "crm_segment",
            "project_status",
            "orderlift_order_status",
        ]:
            path = APP_ROOT / "orderlift" / "orderlift_crm" / "doctype" / doctype / f"{doctype}.json"
            doc = json.loads(path.read_text())
            self.assertEqual(doc["document_type"], "Setup")
            self.assertEqual(doc["module"], "Orderlift CRM")

    def test_crm_segment_assignment_is_child_table(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_crm"
            / "doctype"
            / "crm_segment_assignment"
            / "crm_segment_assignment.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}
        self.assertEqual(doc["istable"], 1)
        self.assertEqual(fields["business_type"]["options"], "CRM Business Type")
        self.assertEqual(fields["segment"]["options"], "CRM Segment")

    def test_campaign_target_uses_crm_classification(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_crm"
            / "doctype"
            / "partner_campaign_target"
            / "partner_campaign_target.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}
        self.assertEqual(fields["business_type"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment"]["options"], "CRM Segment")

    def test_status_config_declares_single_primary_status_per_document(self):
        config_path = APP_ROOT / "orderlift" / "orderlift_crm" / "status_config.py"
        content = config_path.read_text()
        self.assertIn('"Opportunity": {', content)
        self.assertIn('"target_field": "sales_stage"', content)
        self.assertIn('"Project": {', content)
        self.assertIn('"target_field": "custom_project_status"', content)
        self.assertIn('"Sales Order": {', content)
        self.assertIn('"target_field": "custom_orderlift_order_status"', content)


if __name__ == "__main__":
    unittest.main()
