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

        self.assertEqual(fields["demand_source_key"]["unique"], 1)
        self.assertTrue(fields["demand_source_key"]["hidden"])
        self.assertIn("technical_revision_item", fields)
        self.assertNotIn("unique", fields["sales_order_item"])
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
        planner = (APP_ROOT / "orderlift_logistics" / "stock_planning.py").read_text()

        self.assertIn("validate_sales_order_stock_dates", hooks)
        self.assertIn("sync_sales_order_demand_plans", hooks)
        self.assertIn("run_scheduled_planning", hooks)
        self.assertIn("populate_quotation_stock_snapshot", hooks)
        self.assertIn('"Pick List": "orderlift.orderlift_logistics.pick_list_override.OrderliftPickListMixin"', hooks)
        self.assertIn('"stock.planning_settings"', menu)
        self.assertIn('"link_type": "Page", "link_to": "stock-planning-settings-control"', menu)
        self.assertIn('"stock.demand_plan"', menu)
        self.assertIn('__("Confirmed Order Stock Planning")', dashboard)
        self.assertIn('/app/stock-planning-settings-control', dashboard)
        self.assertIn("renderStockPlanning", dashboard)
        self.assertIn("def simulate_reservation_outcome", planner)
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


class TestSimulateReservationOutcome(unittest.TestCase):
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
        frappe_stub.get_cached_value = lambda *args, **kwargs: None
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
    def _demand_row(**overrides):
        values = {
            "demand_source_key": "SOI:SOI-00001",
            "source_type": "Sales Order",
            "sales_order": "SO-00001",
            "sales_order_item": "SOI-00001",
            "customer": "CUST-001",
            "item_code": "ITEM-001",
            "warehouse": "Main",
            "stock_uom": "Nos",
            "uom": "Nos",
            "stock_qty": 10,
            "qty": 10,
            "delivered_qty": 0,
            "conversion_factor": 1,
            "delivery_date": date(2026, 10, 15),
            "docstatus": 1,
        }
        values.update(overrides)
        return values

    def _stub_engine(self, rows, physical, incoming=None, settings=None):
        self.module.get_company_settings = lambda *args, **kwargs: settings
        self.module._pick_list_coverage = lambda source_rows: {}
        self.module._forecast_plan_dates = lambda company: {}

        def fake_demand(company, *, warehouses=None, item_codes=None, sales_orders=None):
            out = list(rows)
            if item_codes:
                out = [row for row in out if row["item_code"] in set(item_codes)]
            return out

        self.module.get_effective_demand_rows = fake_demand
        self.module._incoming_supply = lambda company, logistics_dates: incoming or {}
        self.module._physical_stock = lambda company, settings, *, warehouses=None: physical

    def test_reserves_available_stock_at_protection_date(self):
        rows = [self._demand_row()]
        self._stub_engine(rows, physical={"ITEM-001": {"available_qty": 20, "reserved_qty": 0}})

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            today=date(2026, 10, 8),
        )

        self.assertEqual(outcome["ITEM-001"]["to_be_reserved"], 10)
        self.assertEqual(outcome["ITEM-001"]["usable_incoming"], 0)
        self.assertEqual(outcome["ITEM-001"]["shortage"], 0)

    def test_not_due_before_protection_date(self):
        rows = [self._demand_row()]
        self._stub_engine(rows, physical={"ITEM-001": {"available_qty": 20, "reserved_qty": 0}})

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            today=date(2026, 9, 15),
        )

        self.assertEqual(outcome["ITEM-001"]["to_be_reserved"], 0)
        self.assertEqual(outcome["ITEM-001"]["usable_incoming"], 0)
        self.assertEqual(outcome["ITEM-001"]["shortage"], 10)

    def test_partial_disabled_zeroes_action_and_flags_shortage(self):
        rows = [self._demand_row()]
        settings = types.SimpleNamespace(
            enabled=0,
            reservation_mode="Create Draft Pick List",
            partial_pick_list=0,
            reservation_buffer_days=15,
            rely_on_incoming_stock=1,
            incoming_safety_days=15,
            procurement_safety_days=7,
            default_procurement_delay_days=0,
            protected_stock_floor_mode="None",
            alert_days_before_action=3,
            auto_create_material_request=0,
            auto_submit_material_request=0,
        )
        self._stub_engine(
            rows,
            physical={"ITEM-001": {"available_qty": 6, "reserved_qty": 0}},
            settings=settings,
        )

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            today=date(2026, 10, 8),
        )

        self.assertEqual(outcome["ITEM-001"]["to_be_reserved"], 0)
        self.assertEqual(outcome["ITEM-001"]["shortage"], 10)

    def test_safe_incoming_is_usable_when_no_physical_backup(self):
        rows = [self._demand_row()]
        incoming = {
            "ITEM-001": [
                {
                    "purchase_order": "PO-1",
                    "purchase_order_item": "POI-1",
                    "forecast_load_plan": "",
                    "available_qty": 10,
                    "expected_date": date(2026, 9, 29),
                    "status": "Submitted Purchase Order",
                }
            ]
        }
        self._stub_engine(
            rows,
            physical={"ITEM-001": {"available_qty": 0, "reserved_qty": 0}},
            incoming=incoming,
        )

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            today=date(2026, 10, 8),
        )

        self.assertEqual(outcome["ITEM-001"]["usable_incoming"], 10)
        self.assertEqual(outcome["ITEM-001"]["to_be_reserved"], 0)
        self.assertEqual(outcome["ITEM-001"]["shortage"], 0)

    def test_unsafe_incoming_is_not_usable(self):
        rows = [self._demand_row()]
        incoming = {
            "ITEM-001": [
                {
                    "purchase_order": "PO-LATE",
                    "purchase_order_item": "POI-LATE",
                    "available_qty": 10,
                    "expected_date": date(2026, 10, 10),
                    "status": "Submitted Purchase Order",
                }
            ]
        }
        self._stub_engine(
            rows,
            physical={"ITEM-001": {"available_qty": 0, "reserved_qty": 0}},
            incoming=incoming,
        )

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            today=date(2026, 10, 8),
        )

        self.assertEqual(outcome["ITEM-001"]["usable_incoming"], 0)
        self.assertEqual(outcome["ITEM-001"]["to_be_reserved"], 0)
        self.assertEqual(outcome["ITEM-001"]["shortage"], 10)

    def test_disabled_settings_still_apply(self):
        rows = [self._demand_row()]
        settings = types.SimpleNamespace(
            enabled=0,
            reservation_mode="Create Draft Pick List",
            partial_pick_list=1,
            reservation_buffer_days=15,
            rely_on_incoming_stock=0,
            incoming_safety_days=15,
            procurement_safety_days=7,
            default_procurement_delay_days=0,
            protected_stock_floor_mode="None",
            alert_days_before_action=3,
            auto_create_material_request=0,
            auto_submit_material_request=0,
        )
        incoming = {
            "ITEM-001": [
                {
                    "purchase_order": "PO-1",
                    "purchase_order_item": "POI-1",
                    "available_qty": 10,
                    "expected_date": date(2026, 9, 29),
                    "status": "Submitted Purchase Order",
                }
            ]
        }
        self._stub_engine(
            rows,
            physical={"ITEM-001": {"available_qty": 0, "reserved_qty": 0}},
            incoming=incoming,
            settings=settings,
        )

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            today=date(2026, 10, 8),
        )

        self.assertEqual(outcome["ITEM-001"]["usable_incoming"], 0)
        self.assertEqual(outcome["ITEM-001"]["shortage"], 10)

    def test_item_codes_scope_the_outcome(self):
        rows = [
            self._demand_row(),
            self._demand_row(
                demand_source_key="SOI:SOI-00002",
                sales_order="SO-00002",
                sales_order_item="SOI-00002",
                item_code="ITEM-002",
            ),
        ]
        self._stub_engine(
            rows,
            physical={
                "ITEM-001": {"available_qty": 20, "reserved_qty": 0},
                "ITEM-002": {"available_qty": 20, "reserved_qty": 0},
            },
        )

        outcome = self.module.simulate_reservation_outcome(
            "Orderlift",
            item_codes=["ITEM-001"],
            today=date(2026, 10, 8),
        )

        self.assertEqual(set(outcome), {"ITEM-001"})
        self.assertEqual(outcome["ITEM-001"]["to_be_reserved"], 10)


if __name__ == "__main__":
    unittest.main()
