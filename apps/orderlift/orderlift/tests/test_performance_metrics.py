"""Unit tests for the performance metric registry helpers (no DB)."""

from __future__ import annotations

import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.db = types.SimpleNamespace(get_value=lambda *a, **kw: None)
frappe_stub.get_all = lambda *a, **kw: []
frappe_stub.whitelist = lambda *a, **kw: (lambda fn: fn)
frappe_stub.get_roles = lambda user=None: []
frappe_stub._ = lambda s: s
frappe_stub.throw = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))


utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda v=0: int(v or 0)


def _get_datetime(v):
    from datetime import datetime

    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


utils_stub.get_datetime = _get_datetime
utils_stub.now_datetime = lambda: __import__("datetime").datetime.now()
utils_stub.flt = lambda v=0, n=None: float(v or 0)

frappe_stub.utils = utils_stub
sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = utils_stub


from orderlift.orderlift_hr.metrics.base import (  # noqa: E402
    MetricResult,
    format_display,
    hours_between,
    normalise_score,
)


class TestMetricResult(unittest.TestCase):
    def test_defaults(self):
        r = MetricResult()
        self.assertEqual(r.value, 0.0)
        self.assertEqual(r.status, "Computed")
        self.assertEqual(r.details, {})


class TestNormaliseScore(unittest.TestCase):
    def test_no_target_returns_100_when_value_present(self):
        self.assertEqual(normalise_score(5, None), 100.0)
        self.assertEqual(normalise_score(0, None), 0.0)

    def test_higher_is_better_linear(self):
        self.assertAlmostEqual(normalise_score(50, 100, direction="Higher is better"), 50.0)
        self.assertEqual(normalise_score(150, 100, direction="Higher is better"), 100.0)

    def test_lower_is_better_linear(self):
        self.assertAlmostEqual(normalise_score(50, 100, direction="Lower is better"), 100.0)
        self.assertAlmostEqual(normalise_score(200, 100, direction="Lower is better"), 50.0)

    def test_threshold_pass_fail(self):
        self.assertEqual(
            normalise_score(80, 75, direction="Higher is better", curve="Threshold (pass/fail)"),
            100.0,
        )
        self.assertEqual(
            normalise_score(70, 75, direction="Higher is better", curve="Threshold (pass/fail)"),
            0.0,
        )

    def test_stepped_buckets(self):
        score = normalise_score(70, 100, curve="Stepped")
        self.assertIn(score, (50.0, 75.0))


class TestFormatDisplay(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(format_display(87.5, "%"), "87.5%")

    def test_count(self):
        self.assertEqual(format_display(12.0, "count"), "12")

    def test_euro(self):
        self.assertEqual(format_display(1234.5, "\u20ac"), "\u20ac 1,234")

    def test_hours(self):
        self.assertEqual(format_display(4.25, "hours"), "4.2 hours")


class TestHoursBetween(unittest.TestCase):
    def test_zero_on_missing(self):
        self.assertEqual(hours_between(None, None), 0.0)

    def test_hours_difference(self):
        h = hours_between("2026-05-14 00:00:00", "2026-05-14 06:00:00")
        self.assertAlmostEqual(h, 6.0)


class TestRegistryLoading(unittest.TestCase):
    def test_registry_has_builtin_metrics(self):
        from orderlift.orderlift_hr.metrics import REGISTRY  # imported lazily

        # Sales metrics
        self.assertIn("sales.so_count", REGISTRY)
        self.assertIn("sales.conversion_rate", REGISTRY)
        # CRM metrics
        self.assertIn("crm.opportunity_win_rate", REGISTRY)
        # Generic engine
        self.assertIn("generic.doc_query", REGISTRY)


if __name__ == "__main__":
    unittest.main()
