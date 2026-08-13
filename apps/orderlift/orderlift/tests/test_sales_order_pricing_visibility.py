import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="stock@example.com")
frappe_stub.has_permission = lambda doctype, ptype=None, user=None: False
sys.modules["frappe"] = frappe_stub

from orderlift.orderlift_sales.utils import sales_order_pricing_visibility


class Doc(dict):
    def __getattr__(self, key):
        return self.get(key)

    def set(self, key, value):
        self[key] = value


class TestSalesOrderPricingVisibility(unittest.TestCase):
    def tearDown(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None: False

    def test_read_only_sales_order_prices_are_redacted(self):
        doc = Doc(
            doctype="Sales Order",
            total=100,
            grand_total=120,
            in_words="One hundred twenty",
            items=[Doc(item_code="A", qty=2, rate=50, amount=100, source_margin_percent=20)],
            taxes=[Doc(rate=20, tax_amount=20)],
            payment_schedule=[Doc(payment_amount=120)],
        )

        sales_order_pricing_visibility.redact_sales_order_prices(doc)

        self.assertIsNone(doc["total"])
        self.assertIsNone(doc["grand_total"])
        self.assertEqual(doc["in_words"], "")
        self.assertEqual(doc["items"][0]["item_code"], "A")
        self.assertEqual(doc["items"][0]["qty"], 2)
        self.assertIsNone(doc["items"][0]["rate"])
        self.assertIsNone(doc["items"][0]["amount"])
        self.assertIsNone(doc["items"][0]["source_margin_percent"])
        self.assertEqual(doc["taxes"], [])
        self.assertEqual(doc["payment_schedule"], [])

    def test_editable_sales_order_prices_are_preserved(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None: ptype == "write"
        doc = Doc(doctype="Sales Order", total=100, items=[Doc(item_code="A", qty=2, rate=50)])

        sales_order_pricing_visibility.redact_sales_order_prices(doc)

        self.assertEqual(doc["total"], 100)
        self.assertEqual(doc["items"][0]["rate"], 50)


if __name__ == "__main__":
    unittest.main()
