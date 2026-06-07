"""Pure-logic tests for quiz attempt limits and score percentage math."""

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
frappe_stub.get_all = lambda *a, **k: []
frappe_stub.get_list = lambda *a, **k: []
frappe_stub.get_doc = lambda *a, **k: None
frappe_stub.get_roles = lambda user=None: []
sys.modules["frappe"] = frappe_stub

utils_stub = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0: float(value or 0)
utils_stub.now_datetime = lambda: None
utils_stub.get_datetime = lambda v: v
sys.modules["frappe.utils"] = utils_stub


class FakeDB:
    def __init__(self, attempts_used: int = 0):
        self.attempts_used = attempts_used

    def count(self, doctype, filters):
        return self.attempts_used

    def get_value(self, *a, **k):
        return None

    def get_all(self, *a, **k):
        return []

    def exists(self, *a, **k):
        return False

    def escape(self, value):
        return f"'{value}'"


frappe_stub.utils = utils_stub
frappe_stub._dict = dict
frappe_stub.db = FakeDB()


from orderlift.orderlift_hr.api import training


class TestAttemptsRemaining(unittest.TestCase):
    def setUp(self):
        # Tests share the frappe stub across modules — reassign db each time so
        # other test modules' FakeDB stubs don't leak in via import order.
        frappe_stub.db = FakeDB(attempts_used=0)

    def test_unlimited_attempts_returns_none(self):
        quiz = types.SimpleNamespace(
            name="TQZ-0001", unlimited_attempts=1, max_attempts=3
        )
        used, remaining = training._attempts_remaining(quiz, employee="EMP-001")
        self.assertEqual(used, 0)
        self.assertIsNone(remaining)

    def test_no_employee_returns_zero_used_no_remaining(self):
        quiz = types.SimpleNamespace(
            name="TQZ-0001", unlimited_attempts=0, max_attempts=3
        )
        used, remaining = training._attempts_remaining(quiz, employee=None)
        self.assertEqual(used, 0)
        self.assertIsNone(remaining)

    def test_returns_remaining_when_under_cap(self):
        frappe_stub.db.attempts_used = 1
        quiz = types.SimpleNamespace(
            name="TQZ-0001", unlimited_attempts=0, max_attempts=3
        )
        used, remaining = training._attempts_remaining(quiz, employee="EMP-001")
        self.assertEqual(used, 1)
        self.assertEqual(remaining, 2)

    def test_returns_zero_when_at_cap(self):
        frappe_stub.db.attempts_used = 3
        quiz = types.SimpleNamespace(
            name="TQZ-0001", unlimited_attempts=0, max_attempts=3
        )
        used, remaining = training._attempts_remaining(quiz, employee="EMP-001")
        self.assertEqual(used, 3)
        self.assertEqual(remaining, 0)

    def test_clamps_negative_remaining_to_zero(self):
        frappe_stub.db.attempts_used = 5
        quiz = types.SimpleNamespace(
            name="TQZ-0001", unlimited_attempts=0, max_attempts=3
        )
        used, remaining = training._attempts_remaining(quiz, employee="EMP-001")
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
