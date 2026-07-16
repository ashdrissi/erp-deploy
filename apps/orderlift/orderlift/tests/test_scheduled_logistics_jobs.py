import importlib.util
import sys
import types
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[1]


class Row(types.SimpleNamespace):
    pass


def _load_module(module_name, relative_path, frappe, utils):
    spec = importlib.util.spec_from_file_location(module_name, APP_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    previous = {name: sys.modules.get(name) for name in ("frappe", "frappe.utils")}
    with patch.dict(sys.modules, {"frappe": frappe, "frappe.utils": utils}):
        spec.loader.exec_module(module)
    for name, value in previous.items():
        if value is not None:
            sys.modules[name] = value
    return module


class TestWeeklyEfficiencyDigest(unittest.TestCase):
    def test_digest_queries_only_existing_fields_and_sends_one_email(self):
        sent = []
        frappe = types.ModuleType("frappe")

        def get_all(doctype, **kwargs):
            if doctype == "Forecast Load Plan":
                self.assertNotIn("limiting_factor", kwargs["fields"])
                return [
                    Row(
                        name="FLP-001",
                        plan_label="July shipment",
                        destination_zone="Casablanca",
                        status="Ready",
                        weight_utilization_pct=80,
                        volume_utilization_pct=60,
                        departure_date="2026-07-18",
                    )
                ]
            if doctype == "Has Role":
                return [Row(parent="admin@example.com")]
            raise AssertionError(f"Unexpected doctype: {doctype}")

        frappe.get_all = get_all
        frappe.db = types.SimpleNamespace(get_value=lambda *_args, **_kwargs: "admin@example.com")
        frappe.sendmail = lambda **kwargs: sent.append(kwargs)

        utils = types.ModuleType("frappe.utils")
        utils.today = lambda: "2026-07-16"
        utils.add_days = lambda _value, days: str(date(2026, 7, 16) + timedelta(days=days))
        utils.flt = lambda value=0: float(value or 0)

        module = _load_module(
            "orderlift_test_efficiency_digest",
            "orderlift_logistics/utils/efficiency_digest.py",
            frappe,
            utils,
        )
        module.send_weekly_efficiency_digest()

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["recipients"], ["admin@example.com"])
        self.assertIn("July shipment", sent[0]["message"])
        self.assertIn("80.0%", sent[0]["message"])


class StockDB:
    def __init__(self, *, total_qty=0, last_movement=None, zero_stock_since=None, reorder_qty=0):
        self.total_qty = total_qty
        self.last_movement = last_movement
        self.zero_stock_since = zero_stock_since
        self.reorder_qty = reorder_qty

    def sql(self, query, *_args, **_kwargs):
        if "tabBin" in query:
            return [Row(qty=self.total_qty)]
        if "MAX(posting_date)" in query:
            return [Row(last_date=self.last_movement)]
        if "MIN(posting_date)" in query:
            return [Row(earliest_zero_date=self.zero_stock_since)]
        if "tabItem Reorder" in query:
            return [Row(max_reorder_qty=self.reorder_qty)]
        raise AssertionError(f"Unexpected query: {query}")


class TestStockAnalyzer(unittest.TestCase):
    def _load(self, db):
        frappe = types.ModuleType("frappe")
        frappe.db = db
        utils = types.ModuleType("frappe.utils")
        utils.nowdate = lambda: "2026-07-16"
        utils.add_days = lambda value, days: str(datetime.strptime(value, "%Y-%m-%d").date() + timedelta(days=days))
        utils.getdate = lambda value: value if isinstance(value, date) else datetime.strptime(value, "%Y-%m-%d").date()
        utils.flt = lambda value=0: float(value or 0)
        return _load_module(
            "orderlift_test_stock_analyzer",
            "logistics/utils/stock_analyzer.py",
            frappe,
            utils,
        )

    def test_database_dates_are_normalized_before_threshold_comparisons(self):
        module = self._load(
            StockDB(
                total_qty=0,
                last_movement=date(2026, 1, 1),
                zero_stock_since=date(2026, 1, 1),
                reorder_qty=10,
            )
        )

        self.assertEqual(
            module._analyze_item("ITEM-001"),
            {"slow_moving": True, "overstock": False, "dormant": True},
        )

    def test_recent_string_dates_and_overstock_are_classified_without_type_errors(self):
        module = self._load(
            StockDB(
                total_qty=31,
                last_movement="2026-07-15",
                zero_stock_since=None,
                reorder_qty=10,
            )
        )

        self.assertEqual(
            module._analyze_item("ITEM-002"),
            {"slow_moving": False, "overstock": True, "dormant": False},
        )

    def test_stock_report_resolves_role_users_to_valid_email_addresses(self):
        db = StockDB()
        db.get_value = lambda doctype, name, fieldname: {
            "Administrator": "admin@example.com",
            "stock@example.com": "stock@example.com",
        }.get(name, "") if doctype == "User" and fieldname == "email" else ""
        module = self._load(db)
        sent = []
        module.frappe.get_all = lambda doctype, **_kwargs: (
            [Row(parent="Administrator"), Row(parent="stock@example.com")]
            if doctype == "Has Role"
            else []
        )
        module.frappe.sendmail = lambda **kwargs: sent.append(kwargs)

        module._send_analysis_report({"slow_moving": [], "overstock": [], "dormant": []})

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["recipients"], ["admin@example.com", "stock@example.com"])


if __name__ == "__main__":
    unittest.main()
