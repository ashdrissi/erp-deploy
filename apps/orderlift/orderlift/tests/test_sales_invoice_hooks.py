import sys
import types
import unittest


utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
sys.modules["frappe.utils"] = utils_stub

from orderlift.orderlift_sales import sales_invoice_hooks


class MetaStub:
    def __init__(self, fields):
        self.fields = set(fields)

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


class RowStub:
    def __init__(self, allow_zero_valuation_rate=0):
        self.meta = MetaStub({"allow_zero_valuation_rate"})
        self.allow_zero_valuation_rate = allow_zero_valuation_rate


class DocStub(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class TestSalesInvoiceHooks(unittest.TestCase):
    def test_non_stock_invoice_allows_zero_valuation_rate(self):
        row = RowStub(allow_zero_valuation_rate=0)
        doc = DocStub(update_stock=0, items=[row, {"allow_zero_valuation_rate": 0}])

        sales_invoice_hooks.prepare_non_stock_sales_invoice_items(doc)

        self.assertEqual(row.allow_zero_valuation_rate, 1)
        self.assertEqual(doc["items"][1]["allow_zero_valuation_rate"], 1)

    def test_stock_updating_invoice_preserves_native_validation(self):
        row = RowStub(allow_zero_valuation_rate=0)
        doc = DocStub(update_stock=1, items=[row, {"allow_zero_valuation_rate": 0}])

        sales_invoice_hooks.prepare_non_stock_sales_invoice_items(doc)

        self.assertEqual(row.allow_zero_valuation_rate, 0)
        self.assertEqual(doc["items"][1]["allow_zero_valuation_rate"], 0)

    def test_missing_rows_or_fields_are_safe(self):
        sales_invoice_hooks.prepare_non_stock_sales_invoice_items(DocStub(update_stock=0, items=[{}]))
        sales_invoice_hooks.prepare_non_stock_sales_invoice_items(DocStub(update_stock=0, items=[]))
        sales_invoice_hooks.prepare_non_stock_sales_invoice_items(None)


if __name__ == "__main__":
    unittest.main()
