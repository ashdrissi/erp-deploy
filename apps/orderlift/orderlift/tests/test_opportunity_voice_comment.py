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
        self.assertIn("crm_classification_20260628b.js", hooks)

    def test_opportunity_items_hide_pricing_fields(self):
        source = (APP_ROOT / "orderlift" / "public" / "js" / "crm_classification.js").read_text()
        setup = (APP_ROOT / "orderlift" / "orderlift_crm" / "setup.py").read_text()

        self.assertIn("hideOpportunityItemPricingFields", source)
        self.assertIn('frappe.ui.form.on("Opportunity Item"', source)
        self.assertIn("OPPORTUNITY_ITEM_PRICING_FIELDS", source)
        for fieldname in ["rate", "amount", "base_rate", "base_amount"]:
            self.assertIn(f'"{fieldname}"', source)
            self.assertIn(f'_upsert_property_setter("Opportunity Item", fieldname, "hidden", "1", "Check")', setup)
            self.assertIn(f'_upsert_property_setter("Opportunity Item", fieldname, "in_list_view", "0", "Check")', setup)
            self.assertIn(f'_upsert_property_setter("Opportunity Item", fieldname, "reqd", "0", "Check")', setup)
        self.assertIn('grid.update_docfield_property(fieldname, "hidden", 1)', source)
        self.assertIn('grid.update_docfield_property(fieldname, "in_list_view", 0)', source)
        self.assertIn('grid.update_docfield_property(fieldname, "reqd", 0)', source)

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

    def test_opportunity_preform_loads_party_defaults(self):
        source = (APP_ROOT / "orderlift" / "public" / "js" / "crm_classification.js").read_text()
        api = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "pipeline.py").read_text()

        self.assertIn("setupPreFormPartyDefaults", source)
        self.assertIn("get_party_defaults", source)
        self.assertIn("party_type", source)
        self.assertIn("party_name", source)
        self.assertIn('{ fieldname: "tier", label: __("Tier"), fieldtype: "Link", options: "Pricing Tier" }', source)
        self.assertIn('dialog.set_query("tier", () => ({ filters: { is_active: 1 } }))', source)
        for fieldname in ["client_name", "phone", "tier", "business_type", "segment", "territory", "address"]:
            self.assertIn(fieldname, source)
        self.assertIn("_primary_address_for_party", api)
        self.assertIn('"address": address or ""', api)

    def test_opportunity_delete_unlinks_prospect_child_rows(self):
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        source = (APP_ROOT / "orderlift" / "orderlift_crm" / "opportunity_hooks.py").read_text()

        self.assertIn('"on_trash": "orderlift.orderlift_crm.opportunity_hooks.cleanup_opportunity_delete_links"', hooks)
        self.assertIn("def cleanup_opportunity_delete_links", source)
        self.assertIn("def cleanup_prospect_opportunity_rows", source)
        self.assertIn('frappe.db.delete("Prospect Opportunity", {"opportunity": doc.name})', source)
        self.assertLess(
            source.index("cleanup_prospect_opportunity_rows(doc)"),
            source.index("if not is_auto_saved_draft_opportunity(doc):"),
        )

    def test_opportunity_delete_clears_campaign_target_link(self):
        source = (APP_ROOT / "orderlift" / "orderlift_crm" / "opportunity_hooks.py").read_text()

        self.assertIn("def cleanup_partner_campaign_opportunity_links", source)
        self.assertIn("Partner Campaign Target", source)
        self.assertIn("SET opportunity = NULL", source)
        self.assertIn("refresh_partner_campaign_opportunity_counts(campaigns)", source)
        self.assertLess(
            source.index("cleanup_partner_campaign_opportunity_links(doc)"),
            source.index("if not is_auto_saved_draft_opportunity(doc):"),
        )

    def test_quotation_delete_clears_campaign_target_link(self):
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        source = (APP_ROOT / "orderlift" / "orderlift_crm" / "opportunity_hooks.py").read_text()

        self.assertIn('"on_trash": "orderlift.orderlift_crm.opportunity_hooks.cleanup_quotation_delete_links"', hooks)
        self.assertIn("def cleanup_quotation_delete_links", source)
        self.assertIn("def cleanup_partner_campaign_quotation_links", source)
        self.assertIn("SET quotation = NULL", source)
        self.assertIn("refresh_partner_campaign_quotation_rollups(campaigns)", source)

    def test_quotation_form_allows_direct_opportunity_linking(self):
        source = (APP_ROOT / "orderlift" / "public" / "js" / "quotation_form_simplify_20260620a.js").read_text()
        pipeline = (
            APP_ROOT / "orderlift" / "orderlift_crm" / "page" / "opportunity_pipeline" / "opportunity_pipeline.js"
        ).read_text()

        self.assertIn("showOpportunityField", source)
        self.assertIn('frm.set_df_property("opportunity", "hidden", 0)', source)
        self.assertIn("applyOpportunityRouteOption", source)
        self.assertIn('frm.set_value("opportunity", opportunity)', source)
        self.assertIn("setupOpportunityQuery", source)
        self.assertIn('frm.set_query("opportunity"', source)
        self.assertIn('filters["company"] = company', source.replace("filters.company = company", 'filters["company"] = company'))
        self.assertIn('docstatus: ["<", 2]', source)
        self.assertIn("create_pricing_sheet_from_opportunity", pipeline)
        # Sales Order quick action prompts for a quotation, then opens a mapped SO.
        self.assertIn("get_opportunity_quotations", pipeline)
        self.assertIn("prepare_sales_order_from_quotation", pipeline)
        # Quotation/SO quick actions open an unsaved mapped doc (items carried;
        # user picks the price list and saves).
        self.assertIn("prepare_quotation_from_opportunity", pipeline)
        self.assertIn("frappe.model.open_mapped_doc", pipeline)
        self.assertIn('frappe.set_route("pricing-sheet-builder", sheet)', pipeline)

    def test_status_control_new_row_does_not_send_new_as_docname(self):
        source = (
            APP_ROOT / "orderlift" / "orderlift_crm" / "page" / "status_control" / "status_control.js"
        ).read_text()
        api = (APP_ROOT / "orderlift" / "orderlift_crm" / "api" / "status_control.py").read_text()

        self.assertIn('const isNewRow = String(row.data("row") || "") === "new"', source)
        self.assertIn('const rowName = isNewRow ? ""', source)
        self.assertIn('const docname = isNewRow ? ""', source)
        self.assertIn('if current_name == "new":', api)

    def test_opportunity_owner_sync_wires_pipeline_todo(self):
        hooks = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        source = (APP_ROOT / "orderlift" / "orderlift_crm" / "opportunity_hooks.py").read_text()
        access_py = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.py").read_text()
        access_js = (APP_ROOT / "orderlift" / "orderlift" / "page" / "access_command_center" / "access_command_center.js").read_text()
        crm_setup = (APP_ROOT / "orderlift" / "orderlift_crm" / "setup.py").read_text()

        self.assertIn('"orderlift.orderlift_crm.opportunity_hooks.sync_opportunity_assignment_todo"', hooks)
        self.assertIn("def sync_opportunity_assignment_todo", source)
        self.assertIn('pipeline._find_open_pipeline_todo("Opportunity", doc.name)', source)
        self.assertIn('pipeline._assign_pipeline_document(', source)
        self.assertIn("custom_owned_documents_only", access_py)
        self.assertIn("custom_owned_documents_only", access_js)
        self.assertIn("custom_owned_documents_only", crm_setup)

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
