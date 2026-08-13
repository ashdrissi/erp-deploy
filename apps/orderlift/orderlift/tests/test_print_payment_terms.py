import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[1]


class _Doc(dict):
    __getattr__ = dict.get


def _load_jinja_helpers():
    fake_frappe = types.ModuleType("frappe")
    fake_frappe._ = lambda value: value
    fake_frappe._dict = lambda value=None, **kwargs: _Doc(value or kwargs)
    fake_frappe.defaults = types.SimpleNamespace(get_global_default=lambda _key: "MAD")
    fake_frappe.db = types.SimpleNamespace()

    fake_utils = types.ModuleType("frappe.utils")
    fake_utils.flt = lambda value: float(value or 0)
    fake_utils.formatdate = lambda value: str(value)

    fake_tax = types.ModuleType("orderlift.orderlift_sales.utils.tax_inclusive")
    fake_tax.quote_item_inclusive_totals = lambda _doc: []

    module_name = "orderlift_test_jinja_helpers"
    spec = importlib.util.spec_from_file_location(module_name, APP_ROOT / "utils" / "jinja_helpers.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "frappe": fake_frappe,
            "frappe.utils": fake_utils,
            "orderlift.orderlift_sales.utils.tax_inclusive": fake_tax,
        },
    ):
        spec.loader.exec_module(module)
    return module


class TestPrintPaymentTerms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = _load_jinja_helpers()

    def test_commercial_terms_include_percentage_and_optional_payment_mode(self):
        doc = _Doc(
            currency="MAD",
            payment_terms_template="50% à la commande / 50% à la livraison",
            payment_schedule=[
                {
                    "payment_term": "À la commande",
                    "description": "Acompte exigible à la commande",
                    "invoice_portion": 50,
                    "payment_amount": 5000,
                    "due_date": "2026-08-01",
                    "mode_of_payment": "Wire Transfer",
                },
                {
                    "payment_term": "À la livraison",
                    "invoice_portion": 50,
                    "payment_amount": 5000,
                    "due_date": "2026-09-01",
                    "mode_of_payment": "",
                },
            ],
        )

        self.assertEqual(
            self.helpers.get_print_payment_terms(doc),
            [
                "À la commande - 50% - Mode of Payment: Wire Transfer",
                "À la livraison - 50%",
            ],
        )

    def test_without_details_uses_set_quantity_and_per_set_unit_price(self):
        included = _Doc(
            name="ROW-1",
            idx=1,
            qty=3,
            rate=90,
            amount=300,
            net_amount=270,
            custom_presentation_role="Include in commercial summary",
        )
        separate = _Doc(
            name="ROW-2",
            idx=2,
            qty=1,
            rate=20,
            amount=20,
            net_amount=20,
            custom_presentation_role="Print separately",
        )
        doc = _Doc(
            custom_presentation_mode="Without details",
            custom_commercial_designation="3 electric elevators",
            custom_dimensioning_multiplier=3,
            items=[included, separate],
            taxes=[],
            taxes_and_charges="",
            net_total=290,
            total=320,
            total_taxes_and_charges=0,
            grand_total=290,
        )

        context = self.helpers.get_commercial_print_context(doc)
        summary = context["items"][0]

        self.assertEqual(summary.qty, 3)
        self.assertEqual(summary.rate, 90)
        self.assertEqual(summary.amount, 270)
        self.assertEqual(summary.custom_pu_ttc, 90)
        self.assertEqual(summary.custom_pt_ttc, 270)
        self.assertIs(context["items"][1], separate)

    def test_ttc_print_context_adds_template_tax_to_same_ht_unit_base(self):
        row = _Doc(
            name="ROW-1",
            idx=1,
            qty=2,
            rate=50,
            amount=100,
            net_amount=100,
            custom_applied_taxes=999,
            custom_pu_ttc=999,
            custom_pt_ttc=999,
        )
        doc = _Doc(
            items=[row],
            taxes_and_charges="VAT 20%",
            taxes=[_Doc(charge_type="On Net Total", rate=20)],
            net_total=100,
            total=100,
            total_taxes_and_charges=20,
            grand_total=120,
        )
        original = self.helpers.quote_item_inclusive_totals
        self.helpers.quote_item_inclusive_totals = lambda _doc: [{"tax_amount": 20}]
        try:
            context = self.helpers.get_ttc_print_context(doc)
        finally:
            self.helpers.quote_item_inclusive_totals = original

        self.assertEqual(context["rows_by_name"]["ROW-1"]["unit_ht"], 50)
        self.assertEqual(context["rows_by_name"]["ROW-1"]["unit"], 60)
        self.assertEqual(context["rows_by_name"]["ROW-1"]["total"], 120)

    def test_implicit_erpnext_100_percent_schedule_is_not_printed_as_an_agreement(self):
        doc = _Doc(
            currency="MAD",
            payment_terms_template="",
            payment_schedule=[
                {
                    "payment_term": "",
                    "description": "",
                    "invoice_portion": 100,
                    "payment_amount": 10000,
                    "due_date": "2026-08-01",
                    "mode_of_payment": "",
                }
            ],
        )

        self.assertEqual(self.helpers.get_print_payment_terms(doc), [])

    def test_template_name_is_used_when_no_schedule_rows_exist(self):
        doc = _Doc(
            currency="MAD",
            payment_terms_template="50% à la commande / 50% à la livraison",
            payment_schedule=[],
        )

        self.assertEqual(
            self.helpers.get_print_payment_terms(doc),
            ["50% à la commande / 50% à la livraison"],
        )

    def test_active_sales_templates_render_dynamic_payment_terms_at_the_bottom(self):
        for filename in (
            "orderlift_quotation.html",
            "orderlift_quotation_tr.html",
            "orderlift_sales_document.html",
            "orderlift_sales_document_tr.html",
        ):
            html = (APP_ROOT / "print_formats" / filename).read_text()
            self.assertIn("get_print_payment_terms(doc)", html)
            self.assertIn("if payment_terms", html)
            self.assertIn("payment_terms | join(' / ')", html)
            self.assertNotIn("40% à la commande", html)
            self.assertNotIn("50 % à la livraison totale du matériel", html)
            self.assertNotIn("10% Mise en marche", html)

    def test_payment_schedule_amount_sync_is_loaded_on_commercial_documents(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        js = (APP_ROOT / "public" / "js" / "payment_schedule_sync_20260724a.js").read_text()

        self.assertGreaterEqual(hooks.count("public/js/payment_schedule_sync_20260724a.js"), 3)
        self.assertIn('frappe.ui.form.on("Payment Schedule"', js)
        self.assertIn("invoice_portion(frm, cdt, cdn)", js)
        self.assertIn("payment_amount", js)
        self.assertIn("rounded_total", js)
        self.assertIn("Recalculate Payment Schedule", js)
        self.assertIn('if (frm.doctype === "Sales Order") return;', js)

    def test_standard_payment_terms_template_avoids_duplicate_due_dates(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        setup = (APP_ROOT / "scripts" / "setup_payment_terms.py").read_text()

        self.assertIn("orderlift.scripts.setup_payment_terms.after_migrate", hooks)
        self.assertIn('STANDARD_TEMPLATE = "50% à la commande / 50% à la livraison"', setup)
        self.assertIn('"payment_term": "À la livraison"', setup)
        self.assertIn('"credit_days": 30', setup)


if __name__ == "__main__":
    unittest.main()
