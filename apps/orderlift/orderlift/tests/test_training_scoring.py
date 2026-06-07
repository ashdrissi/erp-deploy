"""Pure-logic tests for the training leaderboard scoring math."""

import datetime
import sys
import types
import unittest


frappe_stub = sys.modules.get("frappe") or types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *a, **k: (lambda fn: fn)
frappe_stub.throw = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
frappe_stub.PermissionError = type("PermissionError", (Exception,), {})
frappe_stub._ = lambda value: value
frappe_stub.flags = types.SimpleNamespace()


class _DBStub:
    def get_value(self, *a, **k):
        return None

    def get_all(self, *a, **k):
        return []

    def count(self, *a, **k):
        return 0

    def exists(self, *a, **k):
        return False

    def escape(self, value):
        return f"'{value}'"

    def sql(self, *a, **k):
        return []


frappe_stub.db = _DBStub()
frappe_stub.get_all = lambda *a, **k: []
frappe_stub.get_list = lambda *a, **k: []
frappe_stub.get_doc = lambda *a, **k: None
frappe_stub.get_roles = lambda user=None: []
sys.modules["frappe"] = frappe_stub

utils_stub = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0: float(value or 0)


_FIXED_NOW = datetime.datetime(2026, 5, 14, 12, 0, 0)


def _fixed_now():
    return _FIXED_NOW


def _get_datetime(value):
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        return datetime.datetime.fromisoformat(value)
    return value


utils_stub.now_datetime = _fixed_now
utils_stub.get_datetime = _get_datetime
sys.modules["frappe.utils"] = utils_stub

frappe_stub.utils = utils_stub
frappe_stub._dict = dict

sys.modules.pop("orderlift.orderlift_hr.api.leaderboard", None)
hr_api_package = sys.modules.get("orderlift.orderlift_hr.api")
if hr_api_package and hasattr(hr_api_package, "leaderboard"):
    delattr(hr_api_package, "leaderboard")

from orderlift.orderlift_hr.api import leaderboard


def _reset_leaderboard_stubs():
    utils_stub.now_datetime = _fixed_now
    utils_stub.get_datetime = _get_datetime
    frappe_stub.utils = utils_stub
    leaderboard.now_datetime = _fixed_now
    leaderboard.frappe = frappe_stub


class TestRecencyScore(unittest.TestCase):
    def setUp(self):
        _reset_leaderboard_stubs()

    def test_no_activity_returns_zero(self):
        self.assertEqual(leaderboard._recency_score(None), 0.0)

    def test_today_returns_full_score(self):
        self.assertEqual(leaderboard._recency_score(_FIXED_NOW), 100.0)

    def test_within_seven_days_returns_full_score(self):
        six_days_ago = _FIXED_NOW - datetime.timedelta(days=6)
        self.assertEqual(leaderboard._recency_score(six_days_ago), 100.0)

    def test_thirty_days_returns_zero(self):
        thirty_days_ago = _FIXED_NOW - datetime.timedelta(days=30)
        self.assertEqual(leaderboard._recency_score(thirty_days_ago), 0.0)

    def test_decays_linearly_between_seven_and_thirty_days(self):
        # 18.5 days is exactly midway between day 7 and day 30 → ~50%
        midpoint = _FIXED_NOW - datetime.timedelta(days=18.5)
        score = leaderboard._recency_score(midpoint)
        self.assertAlmostEqual(score, 50.0, places=1)


class TestScoringWeights(unittest.TestCase):
    def setUp(self):
        _reset_leaderboard_stubs()

    def test_weights_sum_to_one(self):
        total = leaderboard.WEIGHT_MODULE + leaderboard.WEIGHT_QUIZ + leaderboard.WEIGHT_RECENCY
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_module_weight_is_dominant(self):
        self.assertGreater(leaderboard.WEIGHT_MODULE, leaderboard.WEIGHT_QUIZ)
        self.assertGreater(leaderboard.WEIGHT_QUIZ, leaderboard.WEIGHT_RECENCY)


if __name__ == "__main__":
    unittest.main()
