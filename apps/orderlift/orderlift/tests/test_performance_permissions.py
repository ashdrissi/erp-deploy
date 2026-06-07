"""Unit tests for Performance Metric Snapshot row-level permissions."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="alice@example.com")
frappe_stub.db = types.SimpleNamespace(
    get_value=lambda *a, **kw: None,
    escape=lambda v: f"'{v}'",
)
frappe_stub.get_roles = lambda user=None: []
frappe_stub.whitelist = lambda *a, **kw: (lambda fn: fn)
frappe_stub._ = lambda s: s
frappe_stub.throw = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
frappe_stub.utils = types.SimpleNamespace()

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = frappe_stub.utils


from orderlift.orderlift_hr.api import performance_permissions as pp  # noqa: E402


class _Snap:
    def __init__(self, user):
        self.user = user


class TestSnapshotQuery(unittest.TestCase):
    def test_admin_sees_everything(self):
        with patch.object(pp, "_admin", return_value=True):
            self.assertEqual(pp.snapshot_query("admin@x.com"), "")

    def test_non_admin_is_filtered_to_own_user(self):
        with patch.object(pp, "_admin", return_value=False):
            cond = pp.snapshot_query("alice@example.com")
        self.assertIn("alice@example.com", cond)
        self.assertIn("`tabPerformance Metric Snapshot`.`user`", cond)


class TestHasPermission(unittest.TestCase):
    def test_admin_always_allowed(self):
        with patch.object(pp, "_admin", return_value=True):
            self.assertTrue(pp.has_permission(_Snap("other@x.com"), user="admin@x.com"))

    def test_non_admin_sees_only_own_rows(self):
        with patch.object(pp, "_admin", return_value=False):
            self.assertTrue(pp.has_permission(_Snap("alice@example.com"), user="alice@example.com"))
            self.assertFalse(pp.has_permission(_Snap("other@example.com"), user="alice@example.com"))

    def test_blank_doc_is_allowed(self):
        with patch.object(pp, "_admin", return_value=False):
            self.assertTrue(pp.has_permission(None, user="anyone@example.com"))


if __name__ == "__main__":
    unittest.main()
