import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift.scripts import setup_main_dashboard_sidebar


class TestSigSidebarSetup(unittest.TestCase):
    def test_build_sidebar_items_places_dashboards_under_related_sections(self):
        rows = [
            {"label": "Dashboard", "type": "Link", "child": 0},
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(rows)
        labels = [row["label"] for row in updated]

        self.assertEqual(labels[labels.index("Administration") + 1], "Status Control")
        self.assertEqual(labels[labels.index("Administration") + 2], "Document Templates")
        self.assertEqual(labels[labels.index("Administration") + 3], "Access Command Center")
        self.assertEqual(labels[labels.index("CRM & Customers") + 1], "CRM Dashboard")
        self.assertEqual(labels[labels.index("CRM & Customers") + 2], "Projects List")
        self.assertEqual(labels[labels.index("Finance") + 1], "Sale Financial Dashboard")
        self.assertEqual(labels[labels.index("Gestion de Projets") + 1], "Project Pipeline")
        self.assertEqual(labels[labels.index("Gestion de Projets") + 2], "Sales Order Pipeline")
        self.assertEqual(labels[labels.index("Logistics") + 1], "Logistics Pipeline")
        for section in setup_main_dashboard_sidebar.SECTION_ICONS:
            section_index = next(
                index
                for index, row in enumerate(updated)
                if row.get("type") == "Section Break" and row.get("label") == section
            )
            if section_index + 1 < len(updated):
                self.assertNotEqual(updated[section_index + 1].get("label"), section)

    def test_insert_after_label_appends_when_anchor_missing(self):
        rows = [{"label": "One"}, {"label": "Two"}]
        updated = setup_main_dashboard_sidebar._insert_after_label(rows, "Missing", [{"label": "Three"}])
        self.assertEqual([row["label"] for row in updated], ["One", "Two", "Three"])

    def test_build_workspace_shortcuts_preserves_sidebar_link_types(self):
        rows = [
            {"label": "Finance", "type": "Section Break", "child": 0},
            {"label": "Sale Financial Dashboard", "type": "Link", "link_type": "Page", "link_to": "sale-financial-dashboard", "child": 1},
            {"label": "Sales Invoices", "type": "Link", "link_type": "DocType", "link_to": "Sales Invoice", "child": 1},
            {"label": "Sales Payment Summary", "type": "Link", "link_type": "Report", "link_to": "Sales Payment Summary", "child": 1},
        ]

        shortcuts = setup_main_dashboard_sidebar._build_workspace_shortcuts(rows)
        mapped = {row["label"]: row for row in shortcuts}

        self.assertEqual(mapped["Sale Financial Dashboard"]["type"], "Page")
        self.assertEqual(mapped["Sales Invoices"]["type"], "DocType")
        self.assertEqual(mapped["Sales Payment Summary"]["type"], "Report")

    def test_build_sidebar_items_removes_redundant_workspace_detail(self):
        rows = [
            {"label": "Logistics", "type": "Section Break", "child": 0},
            {
                "label": "Forecast Plans",
                "type": "Link",
                "link_type": "Page",
                "link_to": "forecast-plans",
                "child": 1,
            },
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(rows)
        labels = [row["label"] for row in updated]

        self.assertNotIn("Forecast Plans", labels)
        logistics_index = labels.index("Logistics")
        self.assertNotEqual(labels[logistics_index + 1], "Logistics")

    def test_build_sidebar_items_ignores_section_sidebar_children(self):
        rows = [
            {"label": "Dashboard", "type": "Link", "child": 0},
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(
            rows,
            {
                "Sales": [
                    {
                        "label": "Quotation",
                        "type": "Link",
                        "link_type": "DocType",
                        "link_to": "Quotation",
                        "child": 1,
                        "icon": "shopping-cart",
                    },
                    {
                        "label": "Sale Order",
                        "type": "Link",
                        "link_type": "DocType",
                        "link_to": "Sales Order",
                        "child": 1,
                        "icon": "shopping-cart",
                    },
                ]
            },
        )
        labels = [row["label"] for row in updated]

        sales_index = labels.index("Sales")
        self.assertEqual(labels[sales_index + 1], "Pricing Sheets")
        self.assertNotIn("Sale Order", labels)

        items_index = labels.index("Items & Price Lists")
        self.assertIn("Dimensioning Sets", labels[items_index + 1:])

    def test_build_sidebar_items_uses_section_icons_and_collapses_main_dashboard_groups(self):
        rows = [
            {"label": "Dashboard", "type": "Link", "child": 0},
        ]

        updated = setup_main_dashboard_sidebar._build_sidebar_items(rows)
        finance_index = next(
            index
            for index, row in enumerate(updated)
            if row["label"] == "Finance" and row["type"] == "Section Break"
        )
        finance_section = updated[finance_index]

        self.assertEqual(finance_section["icon"], setup_main_dashboard_sidebar.SECTION_ICONS["Finance"])
        self.assertEqual(finance_section["indent"], 1)
        self.assertEqual(finance_section["collapsible"], 1)
        self.assertEqual(finance_section["keep_closed"], 1)

        crm_dashboard = next(row for row in updated if row.get("label") == "CRM Dashboard")
        self.assertEqual(crm_dashboard["icon"], "dot")

    def test_load_managed_section_children_is_disabled(self):
        self.assertEqual(setup_main_dashboard_sidebar._load_managed_section_children(), {})

    def test_build_workspace_content_blocks_groups_shortcuts_by_section(self):
        rows = [
            {"label": "Finance", "type": "Section Break", "child": 0},
            {"label": "Sale Financial Dashboard", "type": "Link", "link_type": "Page", "link_to": "sale-financial-dashboard", "child": 1},
            {"label": "Sales Invoices", "type": "Link", "link_type": "DocType", "link_to": "Sales Invoice", "child": 1},
            {"label": "B2B Portal", "type": "Section Break", "child": 0},
            {"label": "B2B Portal Dashboard", "type": "Link", "link_type": "Page", "link_to": "b2b-portal-dashboard", "child": 1},
        ]

        blocks = setup_main_dashboard_sidebar._build_workspace_content_blocks(rows)
        ids = [block["id"] for block in blocks]
        shortcut_names = [block["data"].get("shortcut_name") for block in blocks if block["type"] == "shortcut"]

        self.assertIn("main_dashboard_shortcuts_finance_header", ids)
        self.assertIn("main_dashboard_shortcuts_b2b_portal_header", ids)
        self.assertEqual(shortcut_names, ["Sale Financial Dashboard", "Sales Invoices", "B2B Portal Dashboard"])

    def test_build_workspace_shortcuts_preserves_workspace_links(self):
        rows = [
            {"label": "CRM & Customers", "type": "Section Break", "child": 0},
            {"label": "CRM & Customers", "type": "Link", "link_type": "Workspace", "link_to": "CRM & Customers", "child": 1},
        ]

        shortcuts = setup_main_dashboard_sidebar._build_workspace_shortcuts(rows)

        self.assertEqual(shortcuts, [{"label": "CRM & Customers", "type": "Workspace", "link_to": "CRM & Customers"}])


if __name__ == "__main__":
    unittest.main()
