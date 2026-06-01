import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]


class TestOpportunityVoiceComment(unittest.TestCase):
    def test_backend_validates_audio_file_and_same_opportunity_attachment(self):
        source = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "voice_comment.py").read_text()

        self.assertIn("def add_opportunity_voice_comment", source)
        self.assertIn('frappe.has_permission("Opportunity", "write"', source)
        self.assertIn('attached_to_doctype != "Opportunity"', source)
        self.assertIn('attached_to_name != opportunity', source)
        self.assertIn("SUPPORTED_AUDIO_EXTENSIONS", source)
        self.assertIn("<audio controls", source)
        self.assertIn("def _append_opportunity_note", source)
        self.assertIn('opportunity_doc.append("notes"', source)

    def test_opportunity_form_records_uploads_and_adds_voice_comment(self):
        source = (APP_ROOT / "orderlift" / "public" / "js" / "crm_classification.js").read_text()
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()

        self.assertIn("Voice Comment", source)
        self.assertIn("Record Voice Note", source)
        self.assertIn("data-voice-comment-action", source)
        self.assertIn("data-voice-note-tab-action", source)
        self.assertIn("timeline_actions_wrapper", source)
        self.assertIn("notes_html", source)
        self.assertIn(".new-note-btn", source)
        self.assertIn("MutationObserver", source)
        self.assertIn(".comment-box", source)
        self.assertIn("ol-voice-comment-inline", source)
        self.assertIn("navigator.mediaDevices.getUserMedia", source)
        self.assertIn("new MediaRecorder", source)
        self.assertIn('/api/method/upload_file', source)
        self.assertIn("orderlift.orderlift_crm.api.voice_comment.add_opportunity_voice_comment", source)
        self.assertIn("crm_classification.js?v=20260601a", hooks)

    def test_opportunity_preform_company_scope_and_quick_actions_are_wired(self):
        source = (APP_ROOT / "orderlift" / "public" / "js" / "crm_classification.js").read_text()
        pipeline = (APP_ROOT / "orderlift" / "orderlift_crm" / "page" / "opportunity_pipeline" / "opportunity_pipeline.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "pipeline.py").read_text()
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()

        self.assertIn("showOpportunityPreFormIfNeeded", source)
        self.assertIn("create_opportunity_from_preform", source)
        self.assertIn("get_company_business_type_payload", source)
        self.assertIn("custom_quick_actions_html", source)
        self.assertIn("setupOpportunityResponsiveComments", source)
        self.assertIn("ol-opportunity-form", source)
        self.assertIn("comment-content.row", source)
        self.assertIn("Attachments", source)
        self.assertIn("Assign", source)
        self.assertIn("window.orderliftShowOpportunityPreForm", pipeline)
        self.assertIn("def create_opportunity_from_preform", api)
        self.assertIn("def _create_preform_party", api)
        self.assertIn("def _create_preform_customer", api)
        self.assertIn("assign_opportunity_name", hooks)

    def test_company_business_type_schema_and_naming_are_wired(self):
        fixture = (APP_ROOT / "orderlift" / "fixtures" / "custom_field_crm_classification.json").read_text()
        campaign_fixture = (APP_ROOT / "orderlift" / "fixtures" / "custom_field_partner_campaign_crm.json").read_text()
        setup = (APP_ROOT / "orderlift" / "orderlift_crm" / "setup.py").read_text()
        naming = (APP_ROOT / "orderlift" / "orderlift_crm" / "opportunity_hooks.py").read_text()
        access_api = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()
        access_js = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()

        self.assertIn("Company-custom_crm_business_types", fixture)
        self.assertIn("Opportunity-custom_probability_level", fixture)
        self.assertIn("Opportunity-custom_sig_tab", fixture)
        self.assertIn('"insert_after": "custom_quick_actions_html"', fixture)
        self.assertIn('"Opportunity-custom_qc_tab"', fixture)
        self.assertIn('"hidden": 1', fixture)
        self.assertIn('"Opportunity-custom_contracts_section"', fixture)
        self.assertIn('"collapsible_depends_on": "eval:1"', fixture)
        self.assertIn('"insert_after": "custom_geocode_status"', campaign_fixture)
        self.assertIn("DEFAULT_COMPANY_BUSINESS_TYPES", setup)
        self.assertIn('"section_break_14", "collapsible_depends_on", "eval:1"', setup)
        self.assertIn("_rename_opportunities_with_business_abbreviation", setup)
        self.assertIn("business_type_abbreviation", naming)
        self.assertIn("custom_crm_business_type", naming)
        self.assertIn("get_company_business_type_names", access_api)
        self.assertIn("acc-company-business-types", access_js)


if __name__ == "__main__":
    unittest.main()
