import sys
import types
import unittest


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

    def test_sale_financial_totals_keep_transaction_currencies_separate(self):
        rows = sale_financial_dashboard._currency_totals(
            [{"currency": "MAD", "amount": 1000}, {"currency": "USD", "amount": 200}],
            [{"currency": "USD", "amount": 50}, {"currency": "TRY", "amount": 300}],
        )
        by_currency = {row["currency"]: row for row in rows}

        self.assertEqual(by_currency["MAD"]["revenue"], 1000)
        self.assertEqual(by_currency["USD"]["revenue"], 200)
        self.assertEqual(by_currency["USD"]["charges"], 50)
        self.assertEqual(by_currency["TRY"]["charges"], 300)

    def test_sale_financial_filters_normalize_business_context(self):
        filters = sale_financial_dashboard._clean_filters(
            '{"company":"Orderlift Turkey","business_type":"Maintenance","search":"  ABC  "}'
        )

        self.assertEqual(filters["company"], "Orderlift Turkey")
        self.assertEqual(filters["business_type"], "Maintenance")
        self.assertEqual(filters["search"], "ABC")
        self.assertEqual(reporting.normalize_business_type("Maintenance"), "Maintenance")

    def test_sale_financial_row_filter_matches_business_filters(self):
        filters = {
            "company": "Orderlift Maroc Installation",
            "business_type": "Installation",
            "crm_segment": "Promoteur",
            "currency": "MAD",
            "sales_status": "To Deliver",
            "search": "acme",
        }
        row = {
            "company": "Orderlift Maroc Installation",
            "business_type": "Installation",
            "segment": "Promoteur",
            "currency": "MAD",
            "workflow_status": "To Deliver",
            "customer": "ACME Towers",
        }

        self.assertTrue(
            sale_financial_dashboard._matches_filters(
                row,
                filters,
                status_filter="sales_status",
                search_fields=("customer",),
            )
        )

        filters["crm_segment"] = "Installateur"
        self.assertFalse(
            sale_financial_dashboard._matches_filters(
                row,
                filters,
                status_filter="sales_status",
                search_fields=("customer",),
            )
        )

    def test_sale_financial_segment_summary_aggregates_workload_and_amounts(self):
        rows = sale_financial_dashboard._segment_summary(
            [{"segment": "Promoteur", "currency": "MAD", "amount": 1000}],
            [{"segment": "Promoteur"}, {"segment": "Installateur"}],
            [{"segment": "Promoteur", "currency": "MAD", "amount": 250}],
        )
        by_segment = {row["label"]: row for row in rows}

        self.assertEqual(by_segment["Promoteur"]["sales_orders"], 1)
        self.assertEqual(by_segment["Promoteur"]["projects"], 1)
        self.assertEqual(by_segment["Promoteur"]["purchase_orders"], 1)
        self.assertEqual(by_segment["Promoteur"]["amounts"][0]["margin"], 750)


if __name__ == "__main__":
    unittest.main()
