import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
sys.modules["frappe.utils"] = utils_stub

from orderlift.sales.utils import commission_calculator


class DbStub:
    def __init__(self, qitem=None):
        self.qitem = qitem or {}

    def get_value(self, *args, **kwargs):
        return self.qitem


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)


class TestCommissionCalculator(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(commission_calculator.frappe, "db", None)

    def tearDown(self):
        if self.original_db is None:
            if hasattr(commission_calculator.frappe, "db"):
                delattr(commission_calculator.frappe, "db")
        else:
            commission_calculator.frappe.db = self.original_db

    def test_blank_quotation_commission_snapshot_recalculates_with_uplift(self):
        commission_calculator.frappe.db = DbStub(
            {
                "source_sales_person": "Agent A",
                "source_commission_rate": 5,
                "source_commission_amount": 0,
                "source_discount_amount": 0,
                "source_gross_sell_rate": 100,
                "source_discounted_sell_rate": 110,
                "source_max_discount_percent": 10,
                "qty": 10,
            }
        )
        sales_order = types.SimpleNamespace(
            name="SO-001",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            items=[Row(quotation_item="QTN-ITEM-1", qty=10)],
        )

        rows = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["salesperson"], "Agent A")
        self.assertAlmostEqual(rows[0]["commission_amount"], 25)

    def test_sales_order_item_snapshot_recalculates_without_uplift_below_list(self):
        commission_calculator.frappe.db = DbStub({})
        sales_order = types.SimpleNamespace(
            name="SO-001",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            items=[
                Row(
                    qty=10,
                    source_sales_person="Agent A",
                    source_commission_rate=5,
                    source_commission_amount=0,
                    source_gross_sell_rate=100,
                    source_discounted_sell_rate=95,
                    source_max_discount_percent=10,
                )
            ],
        )

        rows = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["commission_amount"], 2.5)


if __name__ == "__main__":
    unittest.main()
