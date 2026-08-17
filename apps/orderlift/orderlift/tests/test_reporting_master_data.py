import sys
import types
import unittest
import json
from pathlib import Path


class _Row(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class _DbStub:
    def exists(self, doctype, name=None):
        if doctype == "DocType":
            return name in {
                "Company",
                "Currency",
                "Warehouse",
                "Sales Order",
                "Purchase Order",
                "Project",
                "Opportunity",
                "Purchase Order Item",
            }
        return False

    def get_value(self, *args, **kwargs):
        return None


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.db = _DbStub()
frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda fieldname: True)
frappe_stub.get_all = lambda *args, **kwargs: []
frappe_stub.new_doc = lambda doctype: types.SimpleNamespace(doctype=doctype, meta=types.SimpleNamespace(get_field=lambda fieldname: True))
frappe_stub.delete_doc = lambda *args, **kwargs: None
frappe_stub.clear_cache = lambda *args, **kwargs: None
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)
sys.modules["frappe.utils"] = frappe_utils_stub

custom_field_module = types.ModuleType("frappe.custom.doctype.custom_field.custom_field")
custom_field_module.create_custom_fields = lambda *args, **kwargs: None
sys.modules["frappe.custom"] = types.ModuleType("frappe.custom")
sys.modules["frappe.custom.doctype"] = types.ModuleType("frappe.custom.doctype")
sys.modules["frappe.custom.doctype.custom_field"] = types.ModuleType("frappe.custom.doctype.custom_field")
sys.modules["frappe.custom.doctype.custom_field.custom_field"] = custom_field_module

from orderlift.orderlift_sales import reporting
from orderlift.orderlift_sales.page.sale_financial_dashboard import sale_financial_dashboard
from orderlift.scripts import setup_master_data


class TestReportingMasterData(unittest.TestCase):
    def test_sales_payment_follow_up_reports_traceable_invoice_balances(self):
        root = Path(__file__).resolve().parents[1]
        report = root / "orderlift_sales" / "report" / "sales_payment_follow_up"
        source = (report / "sales_payment_follow_up.py").read_text()
        client = (report / "sales_payment_follow_up.js").read_text()
        report_definition = json.loads(
            (report / "sales_payment_follow_up.json").read_text()
        )

        for token in [
            "sales_orders",
            "projects",
            "payment_modes",
            "paid_amount",
            "outstanding_amount",
            "get_allowed_companies",
        ]:
            self.assertIn(token, source)
        self.assertIn("outstanding_only", client)
        self.assertNotIn('filters={"disabled": 0}', source)
        self.assertEqual(
            {row["role"] for row in report_definition["roles"]},
            {
                "Finance User",
                "Finance Admin",
                "Orderlift Admin",
                "System Manager",
            },
        )

    def test_target_companies_and_currencies_match_orderlift_operating_model(self):
        by_name = {row["name"]: row for row in setup_master_data.TARGET_COMPANIES}

        self.assertEqual(by_name["Orderlift"]["currency"], "MAD")
        self.assertEqual(by_name["Orderlift Maroc Distribution"]["currency"], "MAD")
        self.assertEqual(by_name["Orderlift Maroc Installation"]["currency"], "MAD")
        self.assertEqual(by_name["Orderlift Turkey"]["currency"], "TRY")
        self.assertIn("USD", setup_master_data.TARGET_CURRENCIES)
        self.assertNotIn("Orderlift", setup_master_data.OPERATING_COMPANY_NAMES)

    def test_base_warehouse_names_use_company_abbreviation(self):
        self.assertEqual(setup_master_data._warehouse_docname("Main Warehouse", "OMD"), "Main Warehouse - OMD")

    def test_vat_setup_prefers_exact_20_percent_account_over_any_tax_account(self):
        original_exists = setup_master_data._exists
        original_get_all = setup_master_data.frappe.get_all
        try:
            setup_master_data._exists = lambda doctype, name=None: (
                doctype == "DocType" and name == "Account"
            ) or (doctype == "Account" and name == "VAT 20% - OMD")
            setup_master_data.frappe.get_all = lambda *args, **kwargs: [
                _Row(name="VAT 10% - OMD")
            ]

            account = setup_master_data._get_or_create_tax_account(
                {"name": "Orderlift Maroc Distribution", "abbr": "OMD"},
                {"created": []},
            )
        finally:
            setup_master_data._exists = original_exists
            setup_master_data.frappe.get_all = original_get_all

        self.assertEqual(account, "VAT 20% - OMD")

    def test_margin_percent_keeps_zero_revenue_safe(self):
        self.assertEqual(reporting.margin_percent(0, 100), 0.0)
        self.assertEqual(reporting.margin_percent(1000, 250), 75.0)

    def test_reporting_companies_are_read_from_marker_field(self):
        calls = []

        def get_all(doctype, **kwargs):
            calls.append((doctype, kwargs))
            return [_Row(name="Orderlift Turkey", abbr="OTR", default_currency="TRY")]

        original_get_all = reporting.frappe.get_all
        try:
            reporting.frappe.get_all = get_all
            companies = reporting.get_reporting_companies()
        finally:
            reporting.frappe.get_all = original_get_all

        self.assertEqual(companies, [{"name": "Orderlift Turkey", "abbr": "OTR", "currency": "TRY"}])
        self.assertEqual(calls[0][1]["filters"][reporting.REPORTING_COMPANY_FIELD], 1)

    def test_sale_financial_page_is_a_cash_flow_facade(self):
        self.assertEqual(
            sale_financial_dashboard.PAGE_ROLES,
            ("Orderlift Admin", "System Manager", "Finance User", "Finance Admin"),
        )
        self.assertTrue(callable(sale_financial_dashboard.get_portfolio_data))
        self.assertTrue(callable(sale_financial_dashboard.get_cash_flow_detail))


if __name__ == "__main__":
    unittest.main()
