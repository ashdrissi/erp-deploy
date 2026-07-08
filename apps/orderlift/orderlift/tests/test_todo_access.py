import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="agent@example.com")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.get_roles = lambda user=None: []
frappe_stub.db = types.SimpleNamespace(escape=lambda value: "'" + str(value).replace("'", "''") + "'")
frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
sys.modules["frappe"] = frappe_stub


from orderlift import todo_access
from orderlift import role_capabilities


class TestTodoAccess(unittest.TestCase):
    def setUp(self):
        self._todo_capability = todo_access.user_has_capability
        self._role_capability = role_capabilities.user_has_capability
        self._session_user = frappe_stub.session.user

    def tearDown(self):
        todo_access.user_has_capability = self._todo_capability
        role_capabilities.user_has_capability = self._role_capability
        frappe_stub.session.user = self._session_user

    def test_regular_user_query_is_allocated_to_user(self):
        todo_access.user_has_capability = lambda capability, user=None: False

        self.assertEqual(todo_access.todo_query("agent@example.com"), "`tabToDo`.allocated_to = 'agent@example.com'")

    def test_all_todo_capability_removes_query_filter(self):
        todo_access.user_has_capability = lambda capability, user=None: capability == role_capabilities.CAPABILITY_TODO_ALL_ACCESS

        self.assertIsNone(todo_access.todo_query("admin@example.com"))

    def test_regular_user_cannot_open_someone_elses_todo(self):
        todo_access.user_has_capability = lambda capability, user=None: False
        doc = types.SimpleNamespace(name="todo-1", allocated_to="other@example.com", is_new=lambda: False)

        self.assertFalse(todo_access.has_todo_permission(doc, user="agent@example.com", permission_type="read"))

    def test_regular_user_can_open_allocated_todo(self):
        todo_access.user_has_capability = lambda capability, user=None: False
        doc = types.SimpleNamespace(name="todo-1", allocated_to="agent@example.com", is_new=lambda: False)

        self.assertTrue(todo_access.has_todo_permission(doc, user="agent@example.com", permission_type="read"))


if __name__ == "__main__":
    unittest.main()
