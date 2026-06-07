import importlib
import sys
import types
import unittest


class AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class TestHomePageDashboardAccess(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name)
            for name in [
                "frappe",
                "frappe.utils",
                "orderlift.menu_access",
                "orderlift.orderlift_logistics.page.home_page.home_page",
            ]
        }

        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda value: value
        frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
        frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
        frappe_stub.has_permission = lambda *args, **kwargs: False
        frappe_stub.get_list = lambda *args, **kwargs: []
        frappe_stub.db = types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            count=lambda *args, **kwargs: 0,
            sql=lambda *args, **kwargs: self.fail("Unauthorized dashboard SQL was executed"),
        )
        sys.modules["frappe"] = frappe_stub

        utils_stub = types.ModuleType("frappe.utils")
        utils_stub.flt = lambda value=0: float(value or 0)
        utils_stub.nowdate = lambda: "2026-05-19"
        utils_stub.add_days = lambda date, days: "2026-05-22"
        utils_stub.get_first_day = lambda date: "2026-05-01"
        utils_stub.get_last_day = lambda date: "2026-05-31"
        utils_stub.formatdate = lambda date, fmt=None: date
        sys.modules["frappe.utils"] = utils_stub

        menu_access_stub = types.ModuleType("orderlift.menu_access")
        menu_access_stub.user_can_access_menu_key = lambda menu_key: False
        sys.modules["orderlift.menu_access"] = menu_access_stub

        sys.modules.pop("orderlift.orderlift_logistics.page.home_page.home_page", None)
        self.home_page = importlib.import_module("orderlift.orderlift_logistics.page.home_page.home_page")

    def tearDown(self):
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_dashboard_helpers_return_empty_data_without_module_access(self):
        access = {key: False for key in [
            "pricing",
            "pricing_admin",
            "sales",
            "finance",
            "stock",
            "logistics",
            "purchasing",
            "sav",
        ]}

        self.assertEqual(self.home_page._get_pricing_summary(access), {})
        self.assertEqual(self.home_page._get_recent_pricing_items(access), [])
        self.assertEqual(self.home_page._get_stock_summary(access), {})
        self.assertEqual(self.home_page._get_sales_summary(access), {})
        self.assertEqual(self.home_page._get_global_alerts(access), [])
        self.assertEqual(self.home_page._get_pending_actions(access), [])
        self.assertEqual(self.home_page._get_recent_activity(access), [])
        self.assertEqual(
            self.home_page._get_global_kpis(access),
            {
                "sales_month": 0.0,
                "open_quotes": 0,
                "total_stock": 0,
                "stockouts": 0,
                "pending_transfers": 0,
                "pricing_sheets_month": 0,
                "open_tickets": 0,
            },
        )

    def test_pricing_access_hides_admin_policy_data_for_regular_sales_user(self):
        self.home_page._can_read = lambda doctype: True
        self.home_page._permitted_count = lambda doctype, filters=None: {
            "Pricing Sheet": 2,
            "Pricing Benchmark Policy": 3,
            "Pricing Customs Policy": 4,
            "Pricing Scenario": 5,
        }[doctype]
        self.home_page.frappe.get_list = lambda doctype, **kwargs: [
            AttrDict(name=f"{doctype}-1", sheet_name="Agent Sheet", scenario_name="Scenario", modified="2026-05-19")
        ]

        regular_access = {"pricing": True, "pricing_admin": False}
        self.assertEqual(self.home_page._get_pricing_summary(regular_access), {"total_sheets": 2})
        self.assertEqual(
            [item["meta"] for item in self.home_page._get_recent_pricing_items(regular_access)],
            ["Pricing Sheet"],
        )

        admin_access = {"pricing": True, "pricing_admin": True}
        self.assertEqual(
            self.home_page._get_pricing_summary(admin_access),
            {
                "total_sheets": 2,
                "benchmark_policies": 3,
                "customs_policies": 4,
                "scenarios": 5,
            },
        )
        self.assertIn(
            "Pricing Scenario",
            [item["meta"] for item in self.home_page._get_recent_pricing_items(admin_access)],
        )


if __name__ == "__main__":
    unittest.main()
