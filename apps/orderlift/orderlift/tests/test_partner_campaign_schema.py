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
        self.assertIn("Opportunity-custom_first_contact_date", classification_names)
        self.assertIn("Quotation-custom_crm_business_type", classification_names)
        self.assertIn("Quotation-custom_crm_segment", classification_names)
        self.assertIn("custom_crm_segments", classification_fieldnames)
        self.assertIn("Sales Stage-custom_sequence", status_names)
        self.assertIn("Sales Stage-custom_assigned_user", status_names)
        self.assertIn("Sales Stage-custom_todo_priority", status_names)
        self.assertIn("Sales Stage-custom_confirmation_message", status_names)
        self.assertIn("Project Status-custom_confirmation_message", status_names)
        self.assertIn("Orderlift Order Status-custom_confirmation_message", status_names)
        self.assertIn("Project-custom_project_status", status_names)
        self.assertIn("Project-custom_crm_business_type", status_names)
        self.assertIn("Project-custom_crm_segment", status_names)
        self.assertIn("Sales Order-custom_orderlift_order_status", status_names)
        self.assertIn("Sales Order-custom_crm_business_type", status_names)
        self.assertIn("Sales Order-custom_crm_segment", status_names)
        self.assertIn("custom_color", status_fieldnames)
        self.assertIn("custom_assigned_user", status_fieldnames)
        self.assertIn("custom_todo_priority", status_fieldnames)
        self.assertIn("custom_confirmation_message", status_fieldnames)
        self.assertIn("custom_orderlift_order_status", status_fieldnames)

        sales_stage_assignment = next(row for row in status_fields if row["name"] == "Sales Stage-custom_assigned_user")
        self.assertEqual(sales_stage_assignment["options"], "User")

        classification_by_name = {row["name"]: row for row in classification_fields}
        status_by_name = {row["name"]: row for row in status_fields}
        self.assertEqual(classification_by_name["Lead-custom_crm_classification_section"]["insert_after"], "company_name")
        self.assertEqual(classification_by_name["Lead-custom_crm_classification_section"]["collapsible"], 0)
        self.assertEqual(classification_by_name["Opportunity-custom_crm_business_type"]["insert_after"], "party_name")
        self.assertEqual(classification_by_name["Quotation-custom_crm_business_type"]["insert_after"], "party_name")
        self.assertEqual(status_by_name["Sales Order-custom_orderlift_order_status"]["insert_after"], "customer_name")
        self.assertEqual(status_by_name["Sales Order-custom_crm_business_type"]["insert_after"], "custom_orderlift_order_status")
        self.assertEqual(status_by_name["Project-custom_crm_business_type"]["insert_after"], "custom_project_status")

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
        self.assertEqual(fields["archived"]["fieldtype"], "Check")
        self.assertEqual(fields["business_type_filter"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment_filter"]["options"], "CRM Segment")
        self.assertIn("Visit", fields["campaign_action_type"]["options"])
        self.assertIn("Other", fields["campaign_action_type"]["options"])
        self.assertNotIn("Visit", fields["default_channel"]["options"])
        self.assertNotIn("Other", fields["default_channel"]["options"])
        self.assertEqual(fields["whatsapp_mode"]["fieldtype"], "Select")
        self.assertIn("Twilio", fields["whatsapp_mode"]["options"])
        self.assertIn("Custom Webhook", fields["whatsapp_mode"]["options"])
        self.assertIn("visit_subject", fields)
        self.assertIn("visit_agenda", fields)
        self.assertIn("other_notes", fields)

    def test_campaign_manager_supports_deleted_campaign_restore_flow(self):
        api = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py").read_text()
        manager = (
            APP_ROOT
            / "orderlift"
            / "orderlift_crm"
            / "page"
            / "campaign_manager"
            / "campaign_manager.js"
        ).read_text()

        self.assertIn("def restore_campaign", api)
        self.assertIn("include_archived", api)
        self.assertIn("_latest_campaign_name(include_archived=include_archived)", api)
        self.assertIn("data-show-deleted-campaigns", manager)
        self.assertIn("data-restore-campaign", manager)
        self.assertIn('__("Delete")', manager)

    def test_campaign_manager_ignores_selected_campaign_without_doc_permission(self):
        api = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py").read_text()

        self.assertIn("and _campaign_has_permission(campaign)", api)
        self.assertIn("def _campaign_has_permission", api)
        self.assertIn("_campaign_business_type_in_scope(row.name) and _campaign_has_permission(row.name)", api)

    def test_crm_classification_inheritance_is_wired_to_transactions(self):
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        setup = (APP_ROOT / "orderlift" / "orderlift_crm" / "setup.py").read_text()
        classification = (APP_ROOT / "orderlift" / "orderlift_crm" / "classification.py").read_text()

        self.assertIn('("Maintenance", 30)', setup)
        self.assertIn("_backfill_crm_classification()", setup)
        self.assertIn("sync_quotation_crm_classification", hooks)
        self.assertIn("sync_sales_order_crm_classification", hooks)
        self.assertIn("sync_project_crm_classification", hooks)
        self.assertIn('"Prospect": {', hooks)
        self.assertIn("sync_customer_tier_mode", hooks)
        self.assertIn('"Prospect": "public/js/customer_tier_mode.js', hooks)
        self.assertIn("classification_from_document(\"Quotation\", quotation)", classification)
        self.assertIn("classification_from_document(\"Sales Order\", sales_order)", classification)

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

    def test_project_contracts_tab_fields_exist(self):
        fixture_path = APP_ROOT / "orderlift" / "fixtures" / "custom_field_project_sig.json"
        fields = {row["fieldname"]: row for row in json.loads(fixture_path.read_text())}

        self.assertEqual(fields["custom_contracts_tab"]["fieldtype"], "Tab Break")
        self.assertEqual(fields["custom_contracts_section"]["insert_after"], "custom_contracts_tab")
        self.assertEqual(fields["custom_contracts_html"]["fieldtype"], "HTML")

    def test_status_doctypes_have_assigned_user_and_todo_priority(self):
        for doctype in ["project_status", "orderlift_order_status"]:
            path = APP_ROOT / "orderlift" / "orderlift_crm" / "doctype" / doctype / f"{doctype}.json"
            doc = json.loads(path.read_text())
            fields = {row["fieldname"]: row for row in doc["fields"]}
            self.assertEqual(fields["assigned_user"]["fieldtype"], "Link")
            self.assertEqual(fields["assigned_user"]["options"], "User")
            self.assertEqual(fields["todo_priority"]["fieldtype"], "Select")
            self.assertIn("Important Urgent", fields["todo_priority"]["options"])

    def test_logistics_pipeline_status_is_setup_document(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_logistics"
            / "doctype"
            / "logistics_pipeline_status"
            / "logistics_pipeline_status.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(doc["document_type"], "Setup")
        self.assertEqual(doc["module"], "Orderlift Logistics")
        self.assertEqual(fields["assigned_user"]["options"], "User")
        self.assertIn("Non Important Non Urgent", fields["todo_priority"]["options"])
        self.assertEqual(fields["confirmation_message"]["fieldtype"], "Small Text")

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
        self.assertEqual(fields["email"]["fieldtype"], "Data")
        self.assertEqual(fields["mobile_no"]["fieldtype"], "Data")
        self.assertEqual(fields["visit_todo"]["options"], "ToDo")
        self.assertEqual(fields["last_email_queue"]["options"], "Email Queue")

    def test_whatsapp_settings_supports_twilio_and_custom_webhook(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_crm"
            / "doctype"
            / "orderlift_whatsapp_settings"
            / "orderlift_whatsapp_settings.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(doc["issingle"], 1)
        self.assertEqual(doc["document_type"], "Setup")
        self.assertIn("Twilio", fields["provider"]["options"])
        self.assertIn("Custom Webhook", fields["provider"]["options"])
        self.assertEqual(fields["twilio_auth_token"]["fieldtype"], "Password")
        self.assertEqual(fields["custom_webhook_secret"]["fieldtype"], "Password")

    def test_party_legacy_partner_fields_are_hidden(self):
        fixture_path = APP_ROOT / "orderlift" / "fixtures" / "custom_field_partner_campaign_crm.json"
        rows = json.loads(fixture_path.read_text())
        fields = {(row["dt"], row["fieldname"]): row for row in rows}

        for doctype in ["Lead", "Prospect", "Customer"]:
            section = fields[(doctype, "custom_partner_campaign_section")]
            self.assertEqual(section["hidden"], 1)

            segment = fields[(doctype, "custom_partner_segment")]
            self.assertEqual(segment["label"], "Legacy Partner Segment")
            self.assertEqual(segment["hidden"], 1)
            self.assertEqual(segment["read_only"], 1)
            self.assertEqual(segment["in_list_view"], 0)
            self.assertEqual(segment["in_standard_filter"], 0)

            campaign = fields[(doctype, "custom_partner_campaign")]
            self.assertEqual(campaign["hidden"], 1)
            self.assertEqual(campaign["read_only"], 1)
            self.assertEqual(campaign["in_standard_filter"], 0)

            target = fields[(doctype, "custom_partner_campaign_target")]
            self.assertEqual(target["hidden"], 1)
            self.assertEqual(target["read_only"], 1)

        opportunity_segment = fields[("Opportunity", "custom_partner_segment")]
        self.assertEqual(opportunity_segment["label"], "Legacy Partner Segment")
        self.assertEqual(opportunity_segment["hidden"], 1)
        self.assertEqual(opportunity_segment["read_only"], 1)
        self.assertEqual(opportunity_segment["in_standard_filter"], 0)

    def test_campaign_api_uses_crm_segment_filter_for_initial_targets(self):
        api_path = APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py"
        content = api_path.read_text()

        self.assertIn('business_type=doc.get("business_type_filter")', content)
        self.assertIn("segment=_campaign_crm_segment_filter(doc)", content)
        self.assertIn("FROM `tabCRM Segment Assignment`", content)

    def test_campaign_visit_todo_uses_orderlift_priority_options(self):
        api_path = APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py"
        content = api_path.read_text()

        self.assertIn("from orderlift.orderlift_crm.todo_priority import DEFAULT_TODO_PRIORITY", content)
        self.assertIn('"priority": DEFAULT_TODO_PRIORITY', content)
        self.assertNotIn('"priority": "Medium"', content)

    def test_native_todo_assignments_normalize_legacy_priority(self):
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        hook_path = APP_ROOT / "orderlift" / "orderlift_crm" / "todo_hooks.py"
        hook_content = hook_path.read_text()

        self.assertIn('"ToDo": {', hooks)
        self.assertIn("normalize_todo_priority_on_validate", hooks)
        self.assertIn("normalize_todo_priority", hook_content)

    def test_campaign_email_and_whatsapp_have_preflight_guards(self):
        api_path = APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py"
        content = api_path.read_text()

        self.assertIn("def get_campaign_send_preflight", content)
        self.assertIn("def render_campaign_content_from_payload", content)
        self.assertIn("_ensure_campaign_can_send(doc, [row.name], \"Email\"", content)
        self.assertIn("_ensure_campaign_can_send(doc, [row.name], \"WhatsApp\"", content)
        self.assertIn("EMAIL_RE", content)
        self.assertIn("ALLOWED_TEMPLATE_KEYS", content)
        self.assertIn("_webhook_url_is_allowed", content)

    def test_campaign_api_uses_shared_price_list_scope(self):
        api_path = APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py"
        content = api_path.read_text()

        self.assertIn("get_item_price_access", content)
        self.assertIn("validate_price_list_scope", content)
        self.assertIn("def _allowed_selling_price_lists", content)
        self.assertIn("def _validate_campaign_price_list", content)
        self.assertIn('filters={"enabled": 1, "selling": 1, "name": ["in", allowed]}', content)
        self.assertIn('filters["price_list"] = price_list if price_list else ["in", allowed_price_lists]', content)

    def test_campaign_api_hides_numeric_stock_without_capability(self):
        api_path = APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py"
        content = api_path.read_text()

        self.assertIn("STOCK_QUANTITY_VIEWER_ROLE", content)
        self.assertIn("def _can_view_stock_qty", content)
        self.assertIn('data.pop("available_qty_snapshot", None)', content)
        self.assertIn('"display_available_qty": 1 if display_available_qty else 0', content)
        self.assertIn("if item.display_available_qty and show_stock_qty", content)

    def test_campaign_api_respects_business_type_and_direct_access_scope(self):
        api_path = APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "campaign.py"
        content = api_path.read_text()

        self.assertIn("get_allowed_business_types", content)
        self.assertIn("user_can_access_all_business_types", content)
        self.assertIn("def _get_campaign_doc", content)
        self.assertIn("def _effective_business_type_filter", content)
        self.assertIn("def _validate_campaign_target_scope", content)
        self.assertIn("business_type in %s", content)
        self.assertIn("_get_campaign_doc(campaign, ptype=\"write\")", content)

    def test_campaign_pages_surface_preflight_and_rendered_preview(self):
        editor = (APP_ROOT / "orderlift" / "orderlift_crm" / "page" / "campaign_editor" / "campaign_editor.js").read_text()
        manager = (APP_ROOT / "orderlift" / "orderlift_crm" / "page" / "campaign_manager" / "campaign_manager.js").read_text()

        self.assertIn("render_campaign_content_from_payload", editor)
        self.assertIn("get_campaign_send_preflight", editor)
        self.assertIn("Preview as target", editor)
        self.assertIn("ensureCampaignActionReady", manager)
        self.assertIn("showBulkActionResult", manager)
        self.assertIn("Campaign is not ready", manager)

    def test_status_config_declares_single_primary_status_per_document(self):
        config_path = APP_ROOT / "orderlift" / "orderlift_crm" / "status_config.py"
        content = config_path.read_text()
        self.assertIn('"Opportunity": {', content)
        self.assertIn('"target_field": "sales_stage"', content)
        self.assertIn('"Project": {', content)
        self.assertIn('"target_field": "custom_project_status"', content)
        self.assertIn('"Sales Order": {', content)
        self.assertIn('"target_field": "custom_orderlift_order_status"', content)
        self.assertIn('"Forecast Load Plan": {', content)
        self.assertIn('"target_field": "status"', content)


if __name__ == "__main__":
    unittest.main()
