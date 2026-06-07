"""Pure-logic tests for the training permission helpers."""

import sys
import types
import unittest


frappe_stub = sys.modules.get("frappe") or types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="user@example.com")
frappe_stub.whitelist = lambda *a, **k: (lambda fn: fn)
frappe_stub.throw = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
frappe_stub.PermissionError = type("PermissionError", (Exception,), {})
frappe_stub._ = lambda value: value
frappe_stub.flags = types.SimpleNamespace()
frappe_stub.get_all = lambda *a, **k: []
frappe_stub.get_list = lambda *a, **k: []
frappe_stub.get_doc = lambda *a, **k: None
sys.modules["frappe"] = frappe_stub

utils_stub = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0: float(value or 0)
utils_stub.now_datetime = lambda: None
utils_stub.get_datetime = lambda v: v
sys.modules["frappe.utils"] = utils_stub


class FakeDB:
    def __init__(self):
        self.employee_user_map: dict[str, str] = {}

    def escape(self, value: str) -> str:
        safe = (value or "").replace("'", "''")
        return f"'{safe}'"

    def get_value(self, doctype, name, fieldname=None, **kwargs):
        if doctype == "Employee" and fieldname == "user_id":
            return self.employee_user_map.get(name)
        return None

    def get_all(self, *a, **k):
        return []

    def count(self, *a, **k):
        return 0

    def exists(self, *a, **k):
        return False


frappe_stub.utils = utils_stub
frappe_stub._dict = dict
frappe_stub.db = FakeDB()
frappe_stub.roles_map = {}


def _get_roles(user=None):
    return frappe_stub.roles_map.get(user, [])


frappe_stub.get_roles = _get_roles


from orderlift.orderlift_hr.api import training
from orderlift.orderlift_hr.api import assignment


def _install_stubs() -> None:
    """Pin our frappe stubs onto whatever frappe module the API modules captured.

    Other test files reassign `sys.modules["frappe"]`, which strands the
    earlier-imported `frappe` reference inside `assignment.py` / `training.py`.
    Set attributes on those module-bound references so the API code under test
    sees our roles_map and FakeDB regardless of cross-module pollution.
    """
    for module in (training.frappe, assignment.frappe, frappe_stub):
        module.db = frappe_stub.db
        module.get_roles = _get_roles
        module.session = frappe_stub.session
        module.roles_map = frappe_stub.roles_map
        module.PermissionError = frappe_stub.PermissionError
        module._ = frappe_stub._


class TestIsTrainingAdmin(unittest.TestCase):
    def setUp(self):
        # Other test modules reassign `sys.modules["frappe"]`, stranding the
        # frappe reference inside the API modules. Pin our stubs onto whichever
        # frappe object they captured.
        frappe_stub.db = FakeDB()
        frappe_stub.roles_map.clear()
        _install_stubs()

    def tearDown(self):
        frappe_stub.roles_map.clear()

    def test_orderlift_admin_is_admin(self):
        frappe_stub.roles_map["admin@example.com"] = ["Orderlift Admin"]
        self.assertTrue(assignment.is_training_admin("admin@example.com"))

    def test_system_manager_is_admin(self):
        frappe_stub.roles_map["mgr@example.com"] = ["System Manager"]
        self.assertTrue(assignment.is_training_admin("mgr@example.com"))

    def test_business_user_is_not_admin(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        self.assertFalse(assignment.is_training_admin("sales@example.com"))


class TestPermissionQueryConditions(unittest.TestCase):
    def setUp(self):
        # Other test modules reassign `sys.modules["frappe"]`, stranding the
        # frappe reference inside the API modules. Pin our stubs onto whichever
        # frappe object they captured.
        frappe_stub.db = FakeDB()
        frappe_stub.roles_map.clear()
        _install_stubs()

    def tearDown(self):
        frappe_stub.roles_map.clear()

    def test_admin_gets_unrestricted_query(self):
        frappe_stub.roles_map["admin@example.com"] = ["Orderlift Admin"]
        self.assertEqual(training.quiz_attempt_query("admin@example.com"), "")
        self.assertEqual(training.progress_query("admin@example.com"), "")

    def test_non_admin_quiz_attempt_query_filters_to_self(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        query = training.quiz_attempt_query("sales@example.com")
        self.assertIn("`tabTraining Quiz Attempt`.`user`", query)
        self.assertIn("'sales@example.com'", query)

    def test_non_admin_progress_query_filters_to_self(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        query = training.progress_query("sales@example.com")
        self.assertIn("`tabEmployee Training Progress`.`user`", query)
        self.assertIn("'sales@example.com'", query)

    def test_quote_escaping_in_username(self):
        frappe_stub.roles_map["o'malley@example.com"] = ["Sales User"]
        query = training.quiz_attempt_query("o'malley@example.com")
        self.assertIn("'o''malley@example.com'", query)


class TestHasPermission(unittest.TestCase):
    def setUp(self):
        # Other test modules reassign `sys.modules["frappe"]`, stranding the
        # frappe reference inside the API modules. Pin our stubs onto whichever
        # frappe object they captured.
        frappe_stub.db = FakeDB()
        frappe_stub.roles_map.clear()
        _install_stubs()

    def tearDown(self):
        frappe_stub.roles_map.clear()

    def test_admin_always_allowed(self):
        frappe_stub.roles_map["admin@example.com"] = ["Orderlift Admin"]
        doc = {"user": "other@example.com"}
        self.assertTrue(training.has_permission(doc, "read", "admin@example.com"))

    def test_owner_allowed_via_user_field(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        doc = {"user": "sales@example.com"}
        self.assertTrue(training.has_permission(doc, "read", "sales@example.com"))

    def test_owner_allowed_via_employee_link(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        frappe_stub.db.employee_user_map["EMP-001"] = "sales@example.com"
        doc = {"employee": "EMP-001"}
        self.assertTrue(training.has_permission(doc, "read", "sales@example.com"))

    def test_unrelated_user_denied(self):
        frappe_stub.roles_map["other@example.com"] = ["Sales User"]
        frappe_stub.db.employee_user_map["EMP-001"] = "sales@example.com"
        doc = {"user": "sales@example.com", "employee": "EMP-001"}
        self.assertFalse(training.has_permission(doc, "read", "other@example.com"))


if __name__ == "__main__":
    unittest.main()
