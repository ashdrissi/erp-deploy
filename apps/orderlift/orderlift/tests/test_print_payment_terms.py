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


if __name__ == "__main__":
    unittest.main()
