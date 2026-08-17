import sys
import types
import unittest


class _Row(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class _FakeTodoDoc:
    def __init__(self, store, data):
        self._store = store
        self.__dict__.update(data)

    def insert(self, ignore_permissions=False):
        if not getattr(self, "name", None):
            self.name = f"TODO-{len(self._store) + 1}"
        self._store.append(self._as_dict())
        return self

    def save(self, ignore_permissions=False):
        for row in self._store:
            if row["name"] == self.name:
                row.update(self._as_dict())
                return self
        self._store.append(self._as_dict())
        return self

    def _as_dict(self):
        return {key: value for key, value in self.__dict__.items() if key != "_store"}


class _FakeFrappe:
    def __init__(self):
        self.todos = []
        self.notifications = []
        self.shares = []
        self.users = {
            "sales@example.com": {"enabled": 1, "full_name": "Sales User"},
            "old@example.com": {"enabled": 1, "full_name": "Old User"},
            "new@example.com": {"enabled": 1, "full_name": "New User"},
            "project@example.com": {"enabled": 1, "full_name": "Project User"},
        }
        self.db = types.SimpleNamespace(
            exists=self.exists,
            get_value=self.get_value,
            set_value=self.set_value,
            commit=lambda: None,
        )
        self.session = types.SimpleNamespace(user="manager@example.com")
        self.ValidationError = Exception
        self.PermissionError = Exception

    def _(self, value, *args, **kwargs):
        return value

    def whitelist(self, *args, **kwargs):
        return lambda fn: fn

    def throw(self, message, *args, **kwargs):
        raise Exception(message)

    def has_permission(self, doctype, ptype=None, user=None, doc=None):
        return True

    def get_all(self, doctype, filters=None, fields=None, order_by=None, limit_page_length=None):
        if doctype != "ToDo":
            return []
        filters = filters or {}
        rows = []
        for todo in self.todos:
            if all(todo.get(key) == value for key, value in filters.items()):
                rows.append(_Row(todo.copy()))
        return rows

    def get_doc(self, doctype_or_data, name=None):
        if isinstance(doctype_or_data, dict):
            if doctype_or_data.get("doctype") == "Notification Log":
                return _FakeTodoDoc(self.notifications, doctype_or_data)
            return _FakeTodoDoc(self.todos, doctype_or_data)
        if doctype_or_data == "ToDo":
            for todo in self.todos:
                if todo["name"] == name:
                    return _FakeTodoDoc(self.todos, todo.copy())
        return types.SimpleNamespace(name=name, get=lambda fieldname, default=None: "Qualified")

    def get_meta(self, doctype):
        return types.SimpleNamespace(get_field=lambda fieldname: True)

    def get_roles(self, user=None):
        return ["Opportunity Assigner"]

    def exists(self, doctype, name=None):
        if doctype == "User":
            return name in self.users
        return True

    def get_value(self, doctype, name, fieldname, *args, **kwargs):
        if doctype == "User":
            return self.users.get(name, {}).get(fieldname)
        return None

    def set_value(self, doctype, name, fieldname, value, update_modified=True):
        for todo in self.todos:
            if doctype == "ToDo" and todo["name"] == name:
                todo[fieldname] = value

frappe_stub = _FakeFrappe()
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)
frappe_utils_stub.nowdate = lambda: "2026-04-27"
sys.modules["frappe.utils"] = frappe_utils_stub

from orderlift.orderlift_crm.api import pipeline


class TestCrmPipelineAssignment(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeFrappe()
        pipeline.frappe = self.fake
        pipeline.nowdate = lambda: "2026-04-27"
        pipeline.user_has_capability = lambda capability: True

    def test_assignment_reuses_existing_pipeline_todo_for_same_user(self):
        first = pipeline._assign_pipeline_document("Opportunity", "OPP-1", "sales@example.com", "Qualified")
        second = pipeline._assign_pipeline_document("Opportunity", "OPP-1", "sales@example.com", "Qualified")

        self.assertEqual(first["todo"], second["todo"])
        self.assertEqual(len([todo for todo in self.fake.todos if todo["status"] == "Open"]), 1)
        self.assertEqual(self.fake.todos[0]["allocated_to"], "sales@example.com")
        self.assertEqual(self.fake.todos[0]["assigned_by"], "manager@example.com")
        self.assertEqual(self.fake.todos[0]["priority"], "Important Non Urgent")
        self.assertEqual(self.fake.shares, [])

    def test_assignment_uses_status_todo_priority(self):
        pipeline._assign_pipeline_document(
            "Opportunity",
            "OPP-1",
            "sales@example.com",
            "Qualified",
            priority="Important Urgent",
        )

        self.assertEqual(self.fake.todos[0]["priority"], "Important Urgent")

    def test_status_assignment_reuses_same_user_pipeline_todo(self):
        self.fake.todos.append(
            {
                "name": "TODO-OLD",
                "allocated_to": "sales@example.com",
                "reference_type": "Opportunity",
                "reference_name": "OPP-1",
                "description": "[Orderlift Pipeline] Opportunity OPP-1 moved to New.",
                "status": "Open",
                "priority": "Important Non Urgent",
            }
        )
        self.fake.todos.append(
            {
                "name": "TODO-OTHER",
                "allocated_to": "sales@example.com",
                "reference_type": "Opportunity",
                "reference_name": "OPP-1",
                "description": "Call customer about documents.",
                "status": "Open",
            }
        )

        result = pipeline.sync_pipeline_status_assignment(
            "Opportunity",
            "OPP-1",
            {"assigned_user": "sales@example.com", "todo_priority": "Non Important Urgent"},
            "Qualified",
        )

        by_name = {todo["name"]: todo for todo in self.fake.todos}
        self.assertEqual(by_name["TODO-OLD"]["status"], "Open")
        self.assertEqual(by_name["TODO-OTHER"]["status"], "Open")
        self.assertEqual(result["todo"], "TODO-OLD")
        self.assertEqual(by_name["TODO-OLD"]["priority"], "Non Important Urgent")
        self.assertEqual(by_name["TODO-OLD"]["assigned_by"], "manager@example.com")
        self.assertEqual(self.fake.notifications, [])

    def test_status_without_configured_user_preserves_manual_assignment(self):
        self.fake.todos.append(
            {
                "name": "TODO-MANUAL",
                "allocated_to": "sales@example.com",
                "reference_type": "Opportunity",
                "reference_name": "OPP-1",
                "description": "[Orderlift Pipeline] Opportunity OPP-1 assigned manually.",
                "status": "Open",
            }
        )

        result = pipeline.sync_pipeline_status_assignment("Opportunity", "OPP-1", {}, "Qualified")

        self.assertEqual(result["todo"], "TODO-MANUAL")
        self.assertEqual(result["user"], "sales@example.com")
        self.assertEqual(self.fake.todos[0]["status"], "Open")

    def test_direct_form_status_change_syncs_configured_assignment(self):
        original_list_statuses = pipeline.list_editable_statuses
        original_sync = pipeline.sync_pipeline_status_assignment
        calls = []
        doc = _Row(
            doctype="Project",
            name="PROJ-1",
            company="Orderlift",
            custom_project_status="Purchasing",
            has_value_changed=lambda fieldname: fieldname == "custom_project_status",
        )
        try:
            pipeline.list_editable_statuses = lambda *args, **kwargs: [
                {"name": "Purchasing", "assigned_user": "project@example.com"}
            ]
            pipeline.sync_pipeline_status_assignment = lambda *args: calls.append(args)

            pipeline.sync_pipeline_assignment_on_update(doc)
        finally:
            pipeline.list_editable_statuses = original_list_statuses
            pipeline.sync_pipeline_status_assignment = original_sync

        self.assertEqual(
            calls,
            [("Project", "PROJ-1", {"name": "Purchasing", "assigned_user": "project@example.com"}, "Purchasing")],
        )

    def test_assignment_closes_previous_pipeline_assignment_only(self):
        self.fake.todos.append(
            {
                "name": "TODO-OLD",
                "allocated_to": "old@example.com",
                "reference_type": "Project",
                "reference_name": "PROJ-1",
                "description": "[Orderlift Pipeline] Project PROJ-1 moved to Purchasing.",
                "status": "Open",
            }
        )
        self.fake.todos.append(
            {
                "name": "TODO-OTHER",
                "allocated_to": "old@example.com",
                "reference_type": "Project",
                "reference_name": "PROJ-1",
                "description": "Call customer about delivery.",
                "status": "Open",
            }
        )

        pipeline._assign_pipeline_document("Project", "PROJ-1", "new@example.com", "Purchasing")

        by_name = {todo["name"]: todo for todo in self.fake.todos}
        self.assertEqual(by_name["TODO-OLD"]["status"], "Closed")
        self.assertEqual(by_name["TODO-OTHER"]["status"], "Open")
        self.assertEqual(by_name["TODO-3"]["allocated_to"], "new@example.com")
        self.assertEqual(len(self.fake.notifications), 1)
        self.assertEqual(self.fake.notifications[0]["for_user"], "new@example.com")
        self.assertEqual(self.fake.notifications[0]["type"], "Assignment")

    def test_card_assignment_uses_actual_open_pipeline_todo_only(self):
        assignment = pipeline._assignment_for_card(
            "Project",
            "PROJ-1",
            "Purchasing",
            [{"name": "Purchasing", "assigned_user": "project@example.com"}],
        )

        self.assertEqual(assignment["user"], "")
        self.assertEqual(assignment["label"], "")
        self.assertEqual(assignment["source"], "")

    def test_manual_assignment_api_returns_assignment_payload(self):
        original_card_for_document = pipeline._card_for_document
        try:
            pipeline._card_for_document = lambda document_type, document_name: {"name": document_name}

            result = pipeline.assign_pipeline_document("Opportunity", "OPP-1", "sales@example.com")

            self.assertEqual(result["assignment"]["user"], "sales@example.com")
            self.assertEqual(result["card"]["assignment"]["label"], "Sales User")
        finally:
            pipeline._card_for_document = original_card_for_document

    def test_manual_assignment_requires_pipeline_assignment_capability(self):
        pipeline.user_has_capability = lambda capability: False

        with self.assertRaisesRegex(Exception, "do not have permission"):
            pipeline.assign_pipeline_document("Opportunity", "OPP-1", "sales@example.com")

    def test_manual_assignment_uses_document_specific_capability(self):
        original_card_for_document = pipeline._card_for_document
        calls = []
        try:
            pipeline._card_for_document = lambda document_type, document_name: {"name": document_name}
            pipeline.user_has_capability = lambda capability: calls.append(capability) or True
            for document_type, expected in pipeline.PIPELINE_ASSIGNMENT_CAPABILITIES.items():
                pipeline.assign_pipeline_document(document_type, f"{document_type}-1", "sales@example.com")
            self.assertEqual(calls, list(pipeline.PIPELINE_ASSIGNMENT_CAPABILITIES.values()))
        finally:
            pipeline._card_for_document = original_card_for_document

    def test_manual_unassign_api_closes_pipeline_todos_only(self):
        self.fake.todos.append(
            {
                "name": "TODO-PIPELINE",
                "allocated_to": "sales@example.com",
                "reference_type": "Opportunity",
                "reference_name": "OPP-1",
                "description": "[Orderlift Pipeline] Opportunity OPP-1 moved to Qualified.",
                "status": "Open",
            }
        )
        self.fake.todos.append(
            {
                "name": "TODO-OTHER",
                "allocated_to": "sales@example.com",
                "reference_type": "Opportunity",
                "reference_name": "OPP-1",
                "description": "Follow up customer docs.",
                "status": "Open",
            }
        )
        original_card_for_document = pipeline._card_for_document
        try:
            pipeline._card_for_document = lambda document_type, document_name: {"name": document_name}

            result = pipeline.assign_pipeline_document("Opportunity", "OPP-1", "")

            by_name = {todo["name"]: todo for todo in self.fake.todos}
            self.assertEqual(by_name["TODO-PIPELINE"]["status"], "Closed")
            self.assertEqual(by_name["TODO-OTHER"]["status"], "Open")
            self.assertEqual(result["assignment"]["user"], "")
        finally:
            pipeline._card_for_document = original_card_for_document


if __name__ == "__main__":
    unittest.main()
