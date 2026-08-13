import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from orderlift.tests.test_print_payment_terms import _Doc, _load_jinja_helpers


APP_ROOT = Path(__file__).resolve().parents[1]


def _load_print_controls():
    fake_frappe = types.ModuleType("frappe")
    fake_frappe._ = lambda value: value
    fake_frappe.ValidationError = type("ValidationError", (Exception,), {})

    def throw(message, **_kwargs):
        raise fake_frappe.ValidationError(message)

    fake_frappe.throw = throw
    fake_utils = types.ModuleType("frappe.utils")
    fake_utils.cint = lambda value: int(value or 0)

    module_name = "orderlift_test_commercial_print_controls"
    spec = importlib.util.spec_from_file_location(
        module_name,
        APP_ROOT / "orderlift_sales" / "print_controls.py",
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"frappe": fake_frappe, "frappe.utils": fake_utils}):
        spec.loader.exec_module(module)
    return module


class TestCommercialPrintDelivery(unittest.TestCase):
    def test_quotation_print_context_uses_opportunity_owner_contact(self):
        helpers = _load_jinja_helpers()

        def get_value(doctype, name_or_filters, fields, **kwargs):
            if doctype == "Opportunity":
                return _Doc(
                    title="Ascenseur complet",
                    opportunity_owner="sales@example.com",
                    owner="creator@example.com",
                )
            if doctype == "User":
                return _Doc(
                    full_name="Sales Person",
                    email="sales@example.com",
                    phone="0539000000",
                    mobile_no="0600000000",
                )
            return None

        helpers.frappe.db.get_value = get_value
        doc = _Doc(
            doctype="Quotation",
            opportunity="OPP-001",
            custom_opportunity_title="",
            custom_opportunity_owner="",
            owner="creator@example.com",
            valid_till="2026-08-31",
            custom_delivery_lead_time="4–6 weeks after confirmation",
        )

        context = helpers.get_sales_print_context(doc)

        self.assertEqual(context.subject, "Ascenseur complet")
        self.assertEqual(context.salesperson_name, "Sales Person")
        self.assertEqual(context.salesperson_phone, "0600000000")
        self.assertEqual(context.salesperson_email, "sales@example.com")
        self.assertEqual(context.valid_till, "2026-08-31")
        self.assertEqual(context.delivery_lead_time, "4–6 weeks after confirmation")

    def test_direct_quotation_falls_back_to_document_owner_without_subject(self):
        helpers = _load_jinja_helpers()
        helpers.frappe.db.get_value = lambda doctype, *_args, **_kwargs: (
            _Doc(
                full_name="Document Owner",
                email="owner@example.com",
                phone="0500000000",
                mobile_no="",
            )
            if doctype == "User"
            else None
        )
        doc = _Doc(
            doctype="Quotation",
            opportunity="",
            custom_opportunity_title="",
            custom_opportunity_owner="",
            owner="owner@example.com",
            valid_till="",
            custom_delivery_lead_time="",
        )

        context = helpers.get_sales_print_context(doc)

        self.assertEqual(context.subject, "")
        self.assertEqual(context.salesperson_name, "Document Owner")
        self.assertEqual(context.salesperson_phone, "0500000000")
        self.assertEqual(context.salesperson_email, "owner@example.com")

    def test_compact_party_context_removes_blank_lines_and_separates_contact_details(self):
        helpers = _load_jinja_helpers()
        doc = _Doc(
            address_display=(
                "47 AV OMAR BEN KHATTAB N21<br>\n"
                "TANGER<br>\n"
                "90000<br>Morocco<br>\n<br>\n"
                "Phone: +2126666666<br>Email: test@email.com<br>"
            ),
            contact_mobile="",
            contact_phone="",
            contact_email="",
        )

        context = helpers.get_compact_party_print_context(doc)

        self.assertEqual(
            context.address_lines,
            ["47 AV OMAR BEN KHATTAB N21", "TANGER", "90000", "Morocco"],
        )
        self.assertEqual(context.phone, "+2126666666")
        self.assertEqual(context.email, "test@email.com")

    def test_draft_transaction_print_is_rejected_server_side(self):
        controls = _load_print_controls()
        for doctype in sorted(controls.SUBMITTED_PRINT_REQUIRED_DOCTYPES):
            with self.subTest(doctype=doctype):
                with self.assertRaisesRegex(
                    controls.frappe.ValidationError,
                    "submitted before it can be printed",
                ):
                    controls.require_submitted_document_print(
                        _Doc(doctype=doctype, docstatus=0)
                    )

    def test_submitted_transaction_print_is_allowed_server_side(self):
        controls = _load_print_controls()
        for doctype in sorted(controls.SUBMITTED_PRINT_REQUIRED_DOCTYPES):
            with self.subTest(doctype=doctype):
                self.assertIsNone(
                    controls.require_submitted_document_print(
                        _Doc(doctype=doctype, docstatus=1)
                    )
                )

    def test_cancelled_transaction_print_is_rejected_server_side(self):
        controls = _load_print_controls()
        with self.assertRaisesRegex(
            controls.frappe.ValidationError,
            "submitted before it can be printed",
        ):
            controls.require_submitted_document_print(
                _Doc(doctype="Sales Order", docstatus=2)
            )

    def test_non_transactional_document_is_not_restricted(self):
        controls = _load_print_controls()
        self.assertIsNone(
            controls.require_submitted_document_print(
                _Doc(doctype="Customer", docstatus=0)
            )
        )

    def test_schema_hooks_and_client_controls_are_wired(self):
        setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()
        roles = (APP_ROOT / "scripts" / "setup_startup_roles.py").read_text()
        submitted_print_js = (
            APP_ROOT / "public" / "js" / "submitted_print_guard_20260728a.js"
        ).read_text()
        quotation_validity_js = (
            APP_ROOT / "public" / "js" / "quotation_valid_till_default_20260726a.js"
        ).read_text()
        opportunity_js = (
            APP_ROOT / "public" / "js" / "opportunity_lost_action_20260726a.js"
        ).read_text()

        self.assertGreaterEqual(setup.count('"fieldname": "custom_delivery_lead_time"'), 2)
        self.assertIn("get_sales_print_context", hooks)
        self.assertEqual(hooks.count("require_submitted_document_print"), 12)
        self.assertEqual(hooks.count("submitted_print_guard_20260728a.js"), 12)
        self.assertIn("quotation_valid_till_default_20260726a.js", hooks)
        self.assertIn("opportunity_lost_action_20260726a.js", hooks)
        self.assertIn('"Terms and Conditions": READ_ONLY', roles)
        self.assertIn('"Terms and Conditions": MASTER_MANAGER', roles)
        self.assertIn("frm.doc.docstatus", submitted_print_js)
        self.assertIn("frm.print_doc", submitted_print_js)
        self.assertIn('"Payment Entry"', submitted_print_js)
        self.assertIn('"Stock Entry"', submitted_print_js)
        self.assertIn("frappe.datetime.get_today()", quotation_validity_js)
        self.assertIn("add_days", quotation_validity_js)
        self.assertIn('frm.set_value("valid_till", validTill)', quotation_validity_js)
        self.assertIn('frm.remove_custom_button(__("Close"))', opportunity_js)
        self.assertIn('frm.trigger("set_as_lost_dialog")', opportunity_js)

    def test_print_templates_render_commercial_metadata_conditionally(self):
        for filename in ("orderlift_quotation.html", "orderlift_sales_document.html"):
            html = (APP_ROOT / "print_formats" / filename).read_text()
            self.assertIn("get_sales_print_context(doc)", html)
            self.assertIn("get_compact_party_print_context(doc)", html)
            self.assertIn("commercial.subject", html)
            self.assertIn("commercial.salesperson_phone", html)
            self.assertIn("commercial.salesperson_email", html)
            self.assertIn("commercial.delivery_lead_time", html)
            self.assertIn('class="ol-sales-contact"', html)
            self.assertIn('class="ol-client-contact"', html)
            self.assertIn("page-break-inside: avoid", html)


if __name__ == "__main__":
    unittest.main()
