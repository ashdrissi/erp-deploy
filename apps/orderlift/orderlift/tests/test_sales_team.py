import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
frappe_stub.defaults = types.SimpleNamespace(get_global_default=lambda key: "MAD" if key == "currency" else "")
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
sys.modules["frappe.utils"] = utils_stub

from orderlift.orderlift_sales.utils import sales_team


class Meta:
    def get_field(self, fieldname):
        return fieldname


class Doc:
    doctype = "Opportunity"
    meta = Meta()

    def __init__(self, rows=None):
        self.custom_sales_team = rows or []

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)

    def set(self, fieldname, value):
        setattr(self, fieldname, value)

    def get_doc_before_save(self):
        return None


class TestSalesTeam(unittest.TestCase):
    def test_single_member_starts_as_primary_at_100_percent(self):
        doc = Doc()
        sales_team.set_team(doc, ["Agent A"])

        self.assertEqual(doc.custom_sales_team[0]["sales_person"], "Agent A")
        self.assertEqual(doc.custom_sales_team[0]["allocated_percentage"], 100)
        self.assertEqual(doc.custom_sales_team[0]["is_primary"], 1)

    def test_equal_redistribution_preserves_exact_100_percent(self):
        rows = [
            {"sales_person": "Agent A", "allocated_percentage": 100, "is_primary": 1},
            {"sales_person": "Agent B", "allocated_percentage": 0, "is_primary": 0},
            {"sales_person": "Agent C", "allocated_percentage": 0, "is_primary": 0},
        ]
        sales_team.redistribute_equal(rows)

        self.assertAlmostEqual(sum(row["allocated_percentage"] for row in rows), 100)
        self.assertAlmostEqual(rows[0]["allocated_percentage"], 33.333333333)
        self.assertAlmostEqual(rows[-1]["allocated_percentage"], 33.333333334)

    def test_primary_is_first_marked_member(self):
        rows = [
            {"sales_person": "Agent A", "allocated_percentage": 50, "is_primary": 0},
            {"sales_person": "Agent B", "allocated_percentage": 50, "is_primary": 1},
        ]

        self.assertEqual(sales_team.primary_sales_person(rows), "Agent B")

    def test_legacy_salesperson_tracks_primary(self):
        doc = Doc(
            [
                {"sales_person": "Agent A", "allocated_percentage": 50, "is_primary": 0},
                {"sales_person": "Agent B", "allocated_percentage": 50, "is_primary": 1},
            ]
        )
        doc.doctype = "Pricing Sheet"
        doc.sales_person = "Agent A"
        sales_team.sync_legacy_sales_person(doc)

        self.assertEqual(doc.sales_person, "Agent B")


if __name__ == "__main__":
    unittest.main()
