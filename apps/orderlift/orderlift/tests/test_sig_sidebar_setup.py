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
            {"label": "Dashboards", "type": "Section Break", "child": 0},
            {"label": "CRM Dashboard", "type": "Link", "child": 1},
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(rows)
        labels = [row["label"] for row in updated]

        self.assertLess(labels.index("CRM & Customers"), labels.index("CRM Dashboard"))
        self.assertEqual(labels[labels.index("CRM & Customers") + 1], "CRM Dashboard")
        self.assertEqual(labels[labels.index("Sales") + 1], "Pricing Dashboard")
        self.assertEqual(labels[labels.index("SAV") + 1], "SAV Dashboard")
        self.assertEqual(labels[labels.index("SAV") + 2], "SAV Tickets")
        self.assertEqual(labels[labels.index("Finance") + 1], "Finance Dashboard")
        self.assertEqual(labels[labels.index("HR") + 1], "HR Dashboard")
        self.assertEqual(labels[labels.index("Warehouse & Stock") + 1], "Stock Dashboard")
        self.assertEqual(labels[labels.index("Logistics") + 1], "Container Planning")
        self.assertEqual(labels[labels.index("B2B Portal") + 1], "B2B Portal Dashboard")
        self.assertEqual(labels[labels.index("SIG") + 1], "SIG Dashboard")
        self.assertNotIn("Dashboards", labels)

    def test_insert_after_label_appends_when_anchor_missing(self):
        rows = [{"label": "One"}, {"label": "Two"}]
        updated = setup_main_dashboard_sidebar._insert_after_label(rows, "Missing", [{"label": "Three"}])
        self.assertEqual([row["label"] for row in updated], ["One", "Two", "Three"])

    def test_build_workspace_shortcuts_preserves_sidebar_link_types(self):
        rows = [
            {"label": "Finance", "type": "Section Break", "child": 0},
            {"label": "Finance Dashboard", "type": "Link", "link_type": "Page", "link_to": "finance-dashboard", "child": 1},
            {"label": "Sales Invoices", "type": "Link", "link_type": "DocType", "link_to": "Sales Invoice", "child": 1},
            {"label": "Payments Dashboard", "type": "Link", "link_type": "Dashboard", "link_to": "Payments", "child": 1},
            {"label": "Sales Payment Summary", "type": "Link", "link_type": "Report", "link_to": "Sales Payment Summary", "child": 1},
        ]

        shortcuts = setup_main_dashboard_sidebar._build_workspace_shortcuts(rows)
        mapped = {row["label"]: row for row in shortcuts}

        self.assertEqual(mapped["Finance Dashboard"]["type"], "Page")
        self.assertEqual(mapped["Sales Invoices"]["type"], "DocType")
        self.assertEqual(mapped["Payments Dashboard"]["type"], "Dashboard")
        self.assertEqual(mapped["Sales Payment Summary"]["type"], "Report")

    def test_sav_section_moves_above_items_and_price_lists(self):
        rows = [
            {"label": "Sales", "type": "Section Break", "child": 0},
            {"label": "Pricing Sheet", "type": "Link", "child": 1},
            {"label": "Policies & Configs", "type": "Section Break", "child": 0},
            {"label": "Agent Rules", "type": "Link", "child": 1},
            {"label": "Items & Price Lists", "type": "Section Break", "child": 0},
            {"label": "Item Price", "type": "Link", "child": 1},
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(rows)
        labels = [row["label"] for row in updated]

        self.assertEqual(labels[labels.index("Agent Rules") + 1], "SAV")
        self.assertEqual(labels[labels.index("SAV") + 1], "SAV Dashboard")
        self.assertEqual(labels[labels.index("SAV") + 2], "SAV Tickets")
        self.assertLess(labels.index("SAV"), labels.index("Items & Price Lists"))

    def test_build_workspace_content_blocks_groups_shortcuts_by_section(self):
        rows = [
            {"label": "Finance", "type": "Section Break", "child": 0},
            {"label": "Finance Dashboard", "type": "Link", "link_type": "Page", "link_to": "finance-dashboard", "child": 1},
            {"label": "Sales Invoices", "type": "Link", "link_type": "DocType", "link_to": "Sales Invoice", "child": 1},
            {"label": "HR", "type": "Section Break", "child": 0},
            {"label": "HR Dashboard", "type": "Link", "link_type": "Page", "link_to": "hr-dashboard", "child": 1},
        ]

        blocks = setup_main_dashboard_sidebar._build_workspace_content_blocks(rows)
        ids = [block["id"] for block in blocks]
        shortcut_names = [block["data"].get("shortcut_name") for block in blocks if block["type"] == "shortcut"]

        self.assertIn("main_dashboard_shortcuts_finance_header", ids)
        self.assertIn("main_dashboard_shortcuts_hr_header", ids)
        self.assertEqual(shortcut_names, ["Finance Dashboard", "Sales Invoices", "HR Dashboard"])


if __name__ == "__main__":
    unittest.main()
