import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub


from orderlift.scripts import setup_main_dashboard_sidebar


class TestSigSidebarSetup(unittest.TestCase):
    def test_build_sidebar_items_places_dashboards_under_related_sections(self):
        rows = [
            {"label": "CRM & Customers", "type": "Section Break", "child": 0},
            {"label": "Customer", "type": "Link", "child": 1},
            {"label": "Sales", "type": "Section Break", "child": 0},
            {"label": "Pricing Simulator", "type": "Link", "child": 1},
            {"label": "Finance", "type": "Section Break", "child": 0},
            {"label": "Payments Dashboard", "type": "Link", "child": 1},
            {"label": "HR", "type": "Section Break", "child": 0},
            {"label": "Warehouse & Stock", "type": "Section Break", "child": 0},
            {"label": "Logistics", "type": "Section Break", "child": 0},
            {"label": "Settings", "type": "Section Break", "child": 0},
            {"label": "Dashboards", "type": "Section Break", "child": 0},
            {"label": "CRM Dashboard", "type": "Link", "child": 1},
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(rows)
        labels = [row["label"] for row in updated]

        self.assertLess(labels.index("CRM & Customers"), labels.index("CRM Dashboard"))
        self.assertEqual(labels[labels.index("CRM & Customers") + 1], "CRM Dashboard")
        self.assertEqual(labels[labels.index("Sales") + 1], "Pricing Dashboard")
        self.assertEqual(labels[labels.index("SAV") + 1], "SAV Dashboard")
        self.assertEqual(labels[labels.index("Finance") + 1], "Finance Dashboard")
        self.assertEqual(labels[labels.index("HR") + 1], "HR Dashboard")
        self.assertEqual(labels[labels.index("Warehouse & Stock") + 1], "Stock Dashboard")
        self.assertEqual(labels[labels.index("Logistics") + 1], "Logistics Dashboard")
        self.assertEqual(labels[labels.index("B2B Portal") + 1], "B2B Portal Dashboard")
        self.assertEqual(labels[labels.index("SIG") + 1], "SIG Dashboard")
        self.assertNotIn("Dashboards", labels)

    def test_insert_after_label_appends_when_anchor_missing(self):
        rows = [{"label": "One"}, {"label": "Two"}]
        updated = setup_main_dashboard_sidebar._insert_after_label(rows, "Missing", [{"label": "Three"}])
        self.assertEqual([row["label"] for row in updated], ["One", "Two", "Three"])


if __name__ == "__main__":
    unittest.main()
