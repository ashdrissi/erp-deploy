import importlib
import json
import sys
import types
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class AttrDict(dict):
    __getattr__ = dict.get


class TestStockPlanningContract(unittest.TestCase):
    def test_settings_are_company_scoped_and_include_examples(self):
        path = (
            APP_ROOT
            / "orderlift_logistics"
            / "doctype"
            / "stock_planning_settings"
            / "stock_planning_settings.json"
        )
        payload = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in payload["fields"]}

        self.assertEqual(payload["autoname"], "field:company")
        self.assertEqual(fields["company"]["unique"], 1)
        self.assertEqual(fields["enabled"]["default"], "0")
        self.assertEqual(fields["reservation_mode"]["default"], "Create Draft Pick List")
        self.assertEqual(fields["rely_on_incoming_stock"]["default"], "1")
        self.assertEqual(fields["incoming_safety_days"]["default"], "15")
        self.assertEqual(fields["procurement_safety_days"]["default"], "7")
        self.assertEqual(fields["examples_section"]["collapsible"], 1)
        self.assertIn("Competing Sales Orders", fields["examples_html"]["options"])

    def test_demand_plan_is_read_only_and_tracks_incoming_once(self):
        path = (
            APP_ROOT
            / "orderlift_logistics"
            / "doctype"
            / "stock_demand_plan"
            / "stock_demand_plan.json"
        )
        payload = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in payload["fields"]}

        self.assertEqual(fields["sales_order_item"]["unique"], 1)
        self.assertEqual(fields["allocations"]["options"], "Stock Demand Allocation")
        self.assertIn("incoming_backup_check_date", fields)
        self.assertIn("latest_safe_incoming_date", fields)
        self.assertTrue(all(not row.get("create") and not row.get("write") for row in payload["permissions"]))

    def test_hooks_menu_access_and_scheduler_are_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        menu = (APP_ROOT / "menu_registry.py").read_text()
        dashboard = (
            APP_ROOT
            / "orderlift_logistics"
            / "page"
            / "stock_dashboard"
            / "stock_dashboard.js"
        ).read_text()
        settings_page = (
            APP_ROOT
            / "orderlift_logistics"
            / "page"
            / "stock_planning_settings_control"
            / "stock_planning_settings_control.js"
        ).read_text()

        self.assertIn("validate_sales_order_stock_dates", hooks)
        self.assertIn("sync_sales_order_demand_plans", hooks)
        self.assertIn("run_scheduled_planning", hooks)
        self.assertIn('"Pick List": "orderlift.orderlift_logistics.pick_list_override.OrderliftPickListMixin"', hooks)
        self.assertIn('"stock.planning_settings"', menu)
        self.assertIn('"link_type": "Page", "link_to": "stock-planning-settings-control"', menu)
        self.assertIn('"stock.demand_plan"', menu)
        self.assertIn('__("Confirmed Order Stock Planning")', dashboard)
        self.assertIn('/app/stock-planning-settings-control', dashboard)
        self.assertIn("renderStockPlanning", dashboard)
        self.assertIn('frappe.pages[PAGE_NAME].on_page_load', settings_page)
        self.assertIn('data-company', settings_page)
        self.assertIn('Backup check', settings_page)
        self.assertIn('Planner never creates Stock Reservation Entries directly', settings_page)


class TestStockPlanningRules(unittest.TestCase):
    MODULE_NAMES = (
        "frappe",
        "frappe.utils",
        "orderlift.orderlift_logistics.doctype.stock_planning_settings.stock_planning_settings",
        "orderlift.orderlift_logistics.stock_planning",
    )

    def setUp(self):
        self.original_modules = {name: sys.modules.get(name) for name in self.MODULE_NAMES}
        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda message, *args, **kwargs: message
        frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args else args[0]
        sys.modules["frappe"] = frappe_stub

        utils_stub = types.ModuleType("frappe.utils")
        utils_stub.add_days = lambda value, days: self._getdate(value) + timedelta(days=int(days))
        utils_stub.cint = lambda value=0: int(value or 0)
        utils_stub.flt = lambda value=0: float(value or 0)
        utils_stub.getdate = self._getdate
        utils_stub.now_datetime = datetime.now
        utils_stub.nowdate = lambda: "2026-08-09"
        sys.modules["frappe.utils"] = utils_stub

        settings_stub = types.ModuleType(
            "orderlift.orderlift_logistics.doctype.stock_planning_settings.stock_planning_settings"
        )
        settings_stub.get_company_settings = lambda *args, **kwargs: None
        sys.modules[
            "orderlift.orderlift_logistics.doctype.stock_planning_settings.stock_planning_settings"
        ] = settings_stub
        sys.modules.pop("orderlift.orderlift_logistics.stock_planning", None)
        self.module = importlib.import_module("orderlift.orderlift_logistics.stock_planning")

    def tearDown(self):
        for name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    @staticmethod
    def _getdate(value=None):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        return date.today()

    @staticmethod
    def _plan(**overrides):
        values = {
            "stock_protection_date": date(2026, 8, 24),
            "incoming_backup_check_date": None,
            "incoming_date": None,
            "latest_safe_incoming_date": date(2026, 9, 30),
            "incoming_safety_days": 15,
            "creation": "2026-08-09 10:00:00",
            "delivery_date": date(2026, 10, 15),
            "name": "SDP-00001",
        }
        values.update(overrides)
        return AttrDict(values)

    def test_no_incoming_creates_pick_list_at_protection_date(self):
        qty, status, next_date, _risk = self.module._plan_action(
            self._plan(),
            today=date(2026, 8, 24),
            demand_to_plan=10,
            incoming_allocated=0,
            physical_available=20,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 10)
        self.assertEqual(status, self.module.STATUS_PICK_DUE)
        self.assertEqual(next_date, date(2026, 8, 24))

    def test_uncovered_demand_before_cutoff_is_not_due(self):
        qty, status, next_date, _risk = self.module._plan_action(
            self._plan(),
            today=date(2026, 8, 9),
            demand_to_plan=10,
            incoming_allocated=0,
            physical_available=0,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 0)
        self.assertEqual(status, self.module.STATUS_NOT_DUE)
        self.assertEqual(next_date, date(2026, 8, 24))

    def test_uncovered_demand_becomes_procurement_required_on_cutoff(self):
        qty, status, _next_date, _risk = self.module._plan_action(
            self._plan(),
            today=date(2026, 8, 24),
            demand_to_plan=10,
            incoming_allocated=0,
            physical_available=0,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 0)
        self.assertEqual(status, self.module.STATUS_PROCUREMENT)

    def test_reliable_incoming_waits_until_backup_date(self):
        plan = self._plan(
            incoming_date=date(2026, 9, 29),
            incoming_backup_check_date=date(2026, 9, 14),
        )
        qty, status, next_date, _risk = self.module._plan_action(
            plan,
            today=date(2026, 8, 24),
            demand_to_plan=10,
            incoming_allocated=10,
            physical_available=20,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 0)
        self.assertEqual(status, self.module.STATUS_WAITING_INCOMING)
        self.assertEqual(next_date, date(2026, 9, 14))

    def test_backup_date_creates_partial_pick_list(self):
        plan = self._plan(
            incoming_date=date(2026, 9, 29),
            incoming_backup_check_date=date(2026, 9, 14),
        )
        qty, status, _next_date, _risk = self.module._plan_action(
            plan,
            today=date(2026, 9, 14),
            demand_to_plan=10,
            incoming_allocated=10,
            physical_available=6,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 6)
        self.assertEqual(status, self.module.STATUS_BACKUP_DUE)

    def test_no_physical_backup_keeps_waiting_and_flags_risk(self):
        plan = self._plan(
            incoming_date=date(2026, 9, 29),
            incoming_backup_check_date=date(2026, 9, 14),
        )
        qty, status, next_date, risk = self.module._plan_action(
            plan,
            today=date(2026, 9, 14),
            demand_to_plan=10,
            incoming_allocated=10,
            physical_available=0,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 0)
        self.assertEqual(status, self.module.STATUS_WAITING_INCOMING)
        self.assertEqual(next_date, date(2026, 9, 29))
        self.assertIn("no physical backup", risk)

    def test_competing_orders_cannot_reuse_incoming_quantity(self):
        pool = [
            {
                "purchase_order": "PO-1",
                "purchase_order_item": "POI-1",
                "forecast_load_plan": "",
                "available_qty": 10,
                "expected_date": date(2026, 9, 29),
                "status": "Submitted Purchase Order",
            }
        ]
        first = self.module._allocate_safe_incoming(self._plan(), 10, pool)
        second = self.module._allocate_safe_incoming(self._plan(name="SDP-00002"), 5, pool)

        self.assertEqual(sum(row["allocated_qty"] for row in first), 10)
        self.assertEqual(second, [])
        self.assertEqual(pool[0]["available_qty"], 0)

    def test_incoming_after_safe_date_is_not_allocated(self):
        pool = [
            {
                "purchase_order": "PO-LATE",
                "purchase_order_item": "POI-LATE",
                "available_qty": 10,
                "expected_date": date(2026, 10, 10),
                "status": "Submitted Purchase Order",
            }
        ]

        allocations = self.module._allocate_safe_incoming(self._plan(), 10, pool)

        self.assertEqual(allocations, [])
        self.assertEqual(pool[0]["available_qty"], 10)

    def test_received_incoming_becomes_immediate_physical_pick_after_cutoff(self):
        qty, status, _next_date, _risk = self.module._plan_action(
            self._plan(),
            today=date(2026, 9, 10),
            demand_to_plan=10,
            incoming_allocated=0,
            physical_available=10,
            reserved_qty=0,
            open_qty=10,
        )

        self.assertEqual(qty, 10)
        self.assertEqual(status, self.module.STATUS_PICK_DUE)


if __name__ == "__main__":
    unittest.main()
