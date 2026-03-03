"""Unit tests for benchmark_policy resolver.

These tests run without Frappe context — they test the pure computation
logic (median/avg/weighted, ratio-band matching, fallback behaviour).
"""

import sys
import types
import unittest

# Mock frappe.utils so tests run without Frappe bench
_frappe_utils = types.ModuleType("frappe.utils")
_frappe_utils.flt = lambda v, precision=None: float(v or 0)
_frappe_utils.cint = lambda v: int(v or 0)
_frappe = types.ModuleType("frappe")
_frappe.utils = _frappe_utils
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe_utils)

from orderlift.sales.utils.benchmark_policy import (
    resolve_benchmark_margin,
    _compute_reference,
    _match_benchmark_rule,
    _fetch_benchmark_prices,
)


class TestComputeReference(unittest.TestCase):
    """Test median, average, and weighted average computations."""

    def test_median_odd(self):
        self.assertEqual(_compute_reference([4100, 4200, 4300], "Median"), 4200)

    def test_median_even(self):
        self.assertEqual(_compute_reference([4100, 4200, 4300, 5200], "Median"), 4250)

    def test_median_single(self):
        self.assertEqual(_compute_reference([100], "Median"), 100)

    def test_average(self):
        self.assertAlmostEqual(
            _compute_reference([4100, 4200, 4300, 5200], "Average"), 4450.0
        )

    def test_weighted_average(self):
        result = _compute_reference([100, 200], "Weighted Average", weights=[2, 1])
        self.assertAlmostEqual(result, 133.33, places=1)

    def test_weighted_average_equal_weights(self):
        result = _compute_reference([100, 200], "Weighted Average", weights=[1, 1])
        self.assertAlmostEqual(result, 150.0)

    def test_empty_prices(self):
        self.assertEqual(_compute_reference([], "Median"), 0.0)


class TestMatchBenchmarkRule(unittest.TestCase):
    """Test ratio-band matching with scope filters and specificity."""

    def _rules(self):
        return [
            {"ratio_min": 0, "ratio_max": 0.6, "target_margin_percent": 30, "is_active": 1, "priority": 10, "sequence": 90, "idx": 1},
            {"ratio_min": 0.6, "ratio_max": 0.8, "target_margin_percent": 18, "is_active": 1, "priority": 10, "sequence": 90, "idx": 2},
            {"ratio_min": 0.8, "ratio_max": 0, "target_margin_percent": 8, "is_active": 1, "priority": 10, "sequence": 90, "idx": 3},
        ]

    def test_low_ratio(self):
        rule = _match_benchmark_rule(0.3, self._rules())
        self.assertEqual(rule["target_margin_percent"], 30)

    def test_mid_ratio(self):
        rule = _match_benchmark_rule(0.7, self._rules())
        self.assertEqual(rule["target_margin_percent"], 18)

    def test_high_ratio(self):
        rule = _match_benchmark_rule(0.9, self._rules())
        self.assertEqual(rule["target_margin_percent"], 8)

    def test_very_high_ratio(self):
        """ratio_max=0 means unlimited."""
        rule = _match_benchmark_rule(5.0, self._rules())
        self.assertEqual(rule["target_margin_percent"], 8)

    def test_exact_boundary(self):
        """Ratio exactly at 0.6 should match second band (min inclusive)."""
        rule = _match_benchmark_rule(0.6, self._rules())
        self.assertEqual(rule["target_margin_percent"], 18)

    def test_inactive_rule_skipped(self):
        rules = [
            {"ratio_min": 0, "ratio_max": 0, "target_margin_percent": 50, "is_active": 0, "priority": 10, "idx": 1},
            {"ratio_min": 0, "ratio_max": 0, "target_margin_percent": 10, "is_active": 1, "priority": 10, "idx": 2},
        ]
        rule = _match_benchmark_rule(0.5, rules)
        self.assertEqual(rule["target_margin_percent"], 10)

    def test_scope_filter_item(self):
        rules = [
            {"ratio_min": 0, "ratio_max": 0, "target_margin_percent": 25, "is_active": 1, "item": "PIPE-100", "priority": 10, "idx": 1},
            {"ratio_min": 0, "ratio_max": 0, "target_margin_percent": 10, "is_active": 1, "priority": 10, "idx": 2},
        ]
        # With matching item
        rule = _match_benchmark_rule(0.5, rules, context={"item": "PIPE-100"})
        self.assertEqual(rule["target_margin_percent"], 25)
        # Without matching item
        rule = _match_benchmark_rule(0.5, rules, context={"item": "OTHER"})
        self.assertEqual(rule["target_margin_percent"], 10)

    def test_no_match(self):
        rules = [{"ratio_min": 0, "ratio_max": 0.5, "target_margin_percent": 30, "is_active": 1, "priority": 10, "idx": 1}]
        rule = _match_benchmark_rule(0.8, rules)
        self.assertIsNone(rule)


class TestFetchBenchmarkPrices(unittest.TestCase):
    """Test benchmark price gathering from price map."""

    def test_basic(self):
        sources = [
            {"price_list": "A", "label": "Comp A", "weight": 1, "is_active": 1},
            {"price_list": "B", "label": "Comp B", "weight": 1, "is_active": 1},
        ]
        price_map = {
            "A": {"ITEM-1": 100, "ITEM-2": 200},
            "B": {"ITEM-1": 110, "ITEM-2": 190},
        }
        prices, labels = _fetch_benchmark_prices("ITEM-1", sources, price_map=price_map)
        self.assertEqual(prices, [100, 110])
        self.assertEqual(labels, ["Comp A", "Comp B"])

    def test_inactive_source_skipped(self):
        sources = [
            {"price_list": "A", "label": "Comp A", "weight": 1, "is_active": 0},
            {"price_list": "B", "label": "Comp B", "weight": 1, "is_active": 1},
        ]
        price_map = {"A": {"ITEM-1": 100}, "B": {"ITEM-1": 110}}
        prices, labels = _fetch_benchmark_prices("ITEM-1", sources, price_map=price_map)
        self.assertEqual(prices, [110])

    def test_missing_item(self):
        sources = [{"price_list": "A", "label": "A", "weight": 1, "is_active": 1}]
        price_map = {"A": {"OTHER": 100}}
        prices, labels = _fetch_benchmark_prices("ITEM-1", sources, price_map=price_map)
        self.assertEqual(prices, [])


class TestResolveBenchmarkMargin(unittest.TestCase):
    """Integration test for the full resolve flow."""

    def _standard_setup(self):
        sources = [
            {"price_list": "A", "label": "A", "weight": 1, "is_active": 1},
            {"price_list": "B", "label": "B", "weight": 1, "is_active": 1},
        ]
        rules = [
            {"ratio_min": 0, "ratio_max": 0.6, "target_margin_percent": 30, "is_active": 1, "priority": 10, "sequence": 90, "idx": 1},
            {"ratio_min": 0.6, "ratio_max": 0.8, "target_margin_percent": 18, "is_active": 1, "priority": 10, "sequence": 90, "idx": 2},
            {"ratio_min": 0.8, "ratio_max": 0, "target_margin_percent": 8, "is_active": 1, "priority": 10, "sequence": 90, "idx": 3},
        ]
        price_map = {
            "A": {"ITEM-1": 4200},
            "B": {"ITEM-1": 4300},
        }
        return sources, rules, price_map

    def test_strong_cost_advantage(self):
        """Low ratio → high margin."""
        sources, rules, price_map = self._standard_setup()
        # landed_cost = 2000, benchmark median = 4250, ratio = 0.47
        result = resolve_benchmark_margin(
            "ITEM-1", 2000, sources, rules,
            method="Median", min_sources=2, fallback_margin=10,
            price_map=price_map,
        )
        self.assertFalse(result["is_fallback"])
        self.assertEqual(result["target_margin_percent"], 30)
        self.assertAlmostEqual(result["benchmark_reference"], 4250)
        self.assertAlmostEqual(result["ratio"], 2000 / 4250, places=3)

    def test_weak_cost_position(self):
        """High ratio → compressed margin."""
        sources, rules, price_map = self._standard_setup()
        # landed_cost = 4000, benchmark median = 4250, ratio = 0.94
        result = resolve_benchmark_margin(
            "ITEM-1", 4000, sources, rules,
            method="Median", min_sources=2, fallback_margin=10,
            price_map=price_map,
        )
        self.assertFalse(result["is_fallback"])
        self.assertEqual(result["target_margin_percent"], 8)

    def test_insufficient_sources_fallback(self):
        """Fewer sources than required → fallback."""
        sources = [{"price_list": "A", "label": "A", "weight": 1, "is_active": 1}]
        rules = [{"ratio_min": 0, "ratio_max": 0, "target_margin_percent": 30, "is_active": 1, "priority": 10, "idx": 1}]
        price_map = {"A": {"ITEM-1": 4200}}
        result = resolve_benchmark_margin(
            "ITEM-1", 2000, sources, rules,
            method="Median", min_sources=2, fallback_margin=15,
            price_map=price_map,
        )
        self.assertTrue(result["is_fallback"])
        self.assertEqual(result["target_margin_percent"], 15)
        self.assertTrue(len(result["warnings"]) > 0)

    def test_no_matching_rule_fallback(self):
        """No rule matches the ratio → fallback."""
        sources = [
            {"price_list": "A", "label": "A", "weight": 1, "is_active": 1},
            {"price_list": "B", "label": "B", "weight": 1, "is_active": 1},
        ]
        rules = [
            {"ratio_min": 0, "ratio_max": 0.5, "target_margin_percent": 30, "is_active": 1, "priority": 10, "idx": 1},
        ]
        price_map = {"A": {"ITEM-1": 4200}, "B": {"ITEM-1": 4300}}
        # ratio = 4000/4250 = 0.94, doesn't match 0-0.5 band
        result = resolve_benchmark_margin(
            "ITEM-1", 4000, sources, rules,
            method="Median", min_sources=2, fallback_margin=12,
            price_map=price_map,
        )
        self.assertTrue(result["is_fallback"])
        self.assertEqual(result["target_margin_percent"], 12)

    def test_zero_benchmark_fallback(self):
        """All sources return 0 → fallback."""
        sources = [
            {"price_list": "A", "label": "A", "weight": 1, "is_active": 1},
            {"price_list": "B", "label": "B", "weight": 1, "is_active": 1},
        ]
        rules = [{"ratio_min": 0, "ratio_max": 0, "target_margin_percent": 30, "is_active": 1, "priority": 10, "idx": 1}]
        price_map = {"A": {"ITEM-1": 0}, "B": {"ITEM-1": 0}}
        result = resolve_benchmark_margin(
            "ITEM-1", 2000, sources, rules,
            method="Median", min_sources=2, fallback_margin=10,
            price_map=price_map,
        )
        self.assertTrue(result["is_fallback"])

    def test_average_method(self):
        """Average should use arithmetic mean instead of median."""
        sources, rules, price_map = self._standard_setup()
        result = resolve_benchmark_margin(
            "ITEM-1", 2000, sources, rules,
            method="Average", min_sources=2, fallback_margin=10,
            price_map=price_map,
        )
        self.assertAlmostEqual(result["benchmark_reference"], 4250)
        self.assertFalse(result["is_fallback"])


if __name__ == "__main__":
    unittest.main()
