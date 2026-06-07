import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: False, get_value=lambda *args, **kwargs: None)
frappe_stub.get_all = lambda *args, **kwargs: []
frappe_stub.get_doc = lambda *args, **kwargs: None
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)
frappe_utils_stub.nowdate = lambda: "2026-04-27"
frappe_utils_stub.today = lambda: "2026-04-27"
sys.modules["frappe.utils"] = frappe_utils_stub

frappe_model_stub = types.ModuleType("frappe.model")
frappe_document_stub = types.ModuleType("frappe.model.document")


class DocumentStub:
    def round_floats_in(self, doc, fieldnames=None):
        return None


frappe_document_stub.Document = DocumentStub
sys.modules["frappe.model"] = frappe_model_stub
sys.modules["frappe.model.document"] = frappe_document_stub

status_workflow_stub = types.ModuleType("orderlift.orderlift_crm.status_workflow")
status_workflow_stub.get_default_status_name = lambda document_type: "New"
status_workflow_stub.list_editable_statuses = lambda document_type, include_inactive=False: []
status_workflow_stub.resolve_status_column = lambda document_type, primary_status, legacy_status=None, statuses=None: primary_status or "__unassigned__"
sys.modules["orderlift.orderlift_crm.status_workflow"] = status_workflow_stub

from orderlift.orderlift_crm.api import campaign
from orderlift.orderlift_crm.doctype.partner_campaign.partner_campaign import clean_date_value


class TestPartnerCampaignDates(unittest.TestCase):
    def test_clean_date_value_removes_ui_placeholders(self):
        for value in [None, "", "-", "--", "—", "None", "null"]:
            self.assertIsNone(clean_date_value(value))

        self.assertEqual(clean_date_value("2026-04-27"), "2026-04-27")

    def test_campaign_target_payload_does_not_save_dash_as_date(self):
        original_snapshot = campaign.resolve_party_snapshot
        try:
            campaign.resolve_party_snapshot = lambda party_type, party_name: {
                "display_name": "Acme",
                "last_order_date": None,
            }

            payload = campaign._campaign_target_payload(
                {
                    "party_type": "Customer",
                    "party_name": "CUST-1",
                    "business_type": "Distribution",
                    "crm_segment": "Grossiste",
                    "email": "sales@example.com",
                    "mobile_no": "0612345678",
                    "target_status": "To Contact",
                    "last_contact_date": "-",
                    "last_order_date": "-",
                    "visit_date": "--",
                }
            )

            self.assertIsNone(payload["last_contact_date"])
            self.assertIsNone(payload["last_order_date"])
            self.assertIsNone(payload["visit_date"])
            self.assertEqual(payload["email"], "sales@example.com")
            self.assertEqual(payload["mobile_no"], "0612345678")
        finally:
            campaign.resolve_party_snapshot = original_snapshot

    def test_whatsapp_phone_normalization_defaults_to_morocco(self):
        self.assertEqual(campaign.normalize_whatsapp_phone("06 12 34 56 78"), "212612345678")
        self.assertEqual(campaign.normalize_whatsapp_phone("+212 6 12 34 56 78"), "212612345678")
        self.assertEqual(campaign.normalize_whatsapp_phone("001 555 0100", "1"), "15550100")

    def test_campaign_action_type_keeps_default_channel_valid(self):
        doc = types.SimpleNamespace(
            get=lambda fieldname, default=None: getattr(doc, fieldname, default),
            campaign_action_type="Visit",
            default_channel="Visit",
        )

        campaign._sync_default_channel_from_action_type(doc)

        self.assertEqual(doc.campaign_action_type, "Visit")
        self.assertEqual(doc.default_channel, "")

        doc.campaign_action_type = "Email"
        campaign._sync_default_channel_from_action_type(doc)
        self.assertEqual(doc.default_channel, "Email")

    def test_campaign_action_payload_preserves_visit_and_blanks_channel(self):
        payload = {"campaign_action_type": "Visit", "default_channel": "WhatsApp"}

        campaign._normalize_campaign_action_payload(payload)

        self.assertEqual(payload["campaign_action_type"], "Visit")
        self.assertEqual(payload["default_channel"], "")

    def test_campaign_action_payload_keeps_email_as_channel(self):
        payload = {"campaign_action_type": "Email", "default_channel": "WhatsApp"}

        campaign._normalize_campaign_action_payload(payload)

        self.assertEqual(payload["campaign_action_type"], "Email")
        self.assertEqual(payload["default_channel"], "Email")

    def test_legacy_automated_api_mode_maps_to_custom_webhook(self):
        self.assertEqual(campaign._normalize_whatsapp_mode("Automated API"), "Custom Webhook")
        self.assertEqual(campaign._normalize_whatsapp_mode("Twilio"), "Twilio")

    def test_campaign_short_code_and_opportunity_title_use_target(self):
        campaign_doc = types.SimpleNamespace(name="PC-2026-00042", campaign_name="April Campaign")
        target_row = types.SimpleNamespace(display_name="Acme Elevators", party_name="CUST-1")

        self.assertEqual(campaign._campaign_short_code(campaign_doc.name), "PC-00042")
        self.assertEqual(
            campaign._opportunity_title_for_campaign_target(campaign_doc, target_row),
            "Acme Elevators [PC-00042]",
        )

    def test_controlled_placeholder_rendering(self):
        rendered = campaign._render_template(
            "Hello {{ contact_name }}, campaign {{ campaign_code }} for {{ company }}",
            {"contact_name": "Sara", "campaign_code": "PC-00042", "company": "Acme"},
        )

        self.assertEqual(rendered, "Hello Sara, campaign PC-00042 for Acme")

    def test_sales_order_campaign_inheritance_does_not_require_prevdoc_doctype(self):
        original_db = campaign.frappe.db
        try:
            campaign.frappe.db = types.SimpleNamespace(
                exists=lambda doctype, name=None: doctype == "Quotation" and name == "QTN-1",
                get_value=lambda *args, **kwargs: None,
            )

            doc = types.SimpleNamespace(
                get=lambda fieldname, default=None: [types.SimpleNamespace(prevdoc_docname="QTN-1")] if fieldname == "items" else default,
            )

            self.assertEqual(campaign._linked_quotation_names_from_sales_order(doc), ["QTN-1"])
        finally:
            campaign.frappe.db = original_db

    def test_sales_order_campaign_inheritance_ignores_non_quotation_prevdoc(self):
        original_db = campaign.frappe.db
        try:
            campaign.frappe.db = types.SimpleNamespace(
                exists=lambda doctype, name=None: False,
                get_value=lambda *args, **kwargs: None,
            )

            doc = types.SimpleNamespace(
                get=lambda fieldname, default=None: [types.SimpleNamespace(prevdoc_docname="MAT-REQ-1")] if fieldname == "items" else default,
            )

            self.assertEqual(campaign._linked_quotation_names_from_sales_order(doc), [])
        finally:
            campaign.frappe.db = original_db


if __name__ == "__main__":
    unittest.main()
