import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.PermissionError = PermissionError
frappe_stub.session = types.SimpleNamespace(user="Administrator")
frappe_stub._ = lambda value: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.get_roles = lambda user=None: []
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
utils_stub.getdate = lambda value=None: value or "2026-04-27"
utils_stub.date_diff = lambda end, start: 0
utils_stub.nowdate = lambda: "2026-04-27"
utils_stub.now_datetime = lambda: "2026-04-27 00:00:00"
sys.modules["frappe.utils"] = utils_stub


from orderlift.orderlift.page.access_command_center import access_command_center


class TestAccessCommandCenterHelpers(unittest.TestCase):
    def setUp(self):
        self._session_user = frappe_stub.session.user
        self._get_roles = frappe_stub.get_roles

    def tearDown(self):
        frappe_stub.session.user = self._session_user
        frappe_stub.get_roles = self._get_roles

    def test_coerce_permission_flags_normalizes_supported_flags(self):
        flags = access_command_center._coerce_permission_flags(
            {"read": "1", "write": 1, "delete": 0, "export": None, "unknown": 1}
        )

        self.assertEqual(flags["read"], 1)
        self.assertEqual(flags["write"], 1)
        self.assertEqual(flags["delete"], 0)
        self.assertEqual(flags["export"], 0)
        self.assertNotIn("unknown", flags)

    def test_access_level_prioritizes_admin_roles(self):
        self.assertEqual(access_command_center._access_level(["Sales User", "System Manager"]), "Admin Level")
        self.assertEqual(access_command_center._access_level(["Orderlift Admin"]), "High Access")
        self.assertEqual(access_command_center._access_level(["Sales User"]), "Managed Access")
        self.assertEqual(access_command_center._access_level([]), "No Access")

    def test_clean_list_deduplicates_json_role_payload(self):
        roles = access_command_center._clean_list('["Sales User", "Sales User", "System Manager", ""]')

        self.assertEqual(roles, ["Sales User", "System Manager"])

    def test_permission_levels_include_zero_and_custom_levels(self):
        levels = access_command_center._permission_levels_for_matrix({1: {"read": 1}}, {2: {"write": 1}})

        self.assertEqual(levels, [0, 1, 2])

    def test_critical_user_detection_protects_administrator(self):
        self.assertTrue(access_command_center._is_critical_user("Administrator"))
        self.assertFalse(access_command_center._is_critical_user("demo@example.com"))

    def test_role_name_validation_requires_name(self):
        with self.assertRaises(ValueError):
            access_command_center._validate_role_name("   ")

    def test_business_admin_visible_roles_exclude_superadmin_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        roles = access_command_center._visible_role_names()

        self.assertIn("Sales User", roles)
        self.assertNotIn("System Manager", roles)
        self.assertNotIn("Developer", roles)

    def test_business_admin_visible_roles_include_custom_business_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_custom_roles = access_command_center._custom_business_role_names
        access_command_center._custom_business_role_names = lambda: ["testt"]
        try:
            roles = access_command_center._visible_role_names()
        finally:
            access_command_center._custom_business_role_names = original_custom_roles

        self.assertIn("Sales User", roles)
        self.assertIn("testt", roles)
        self.assertNotIn("System Manager", roles)

    def test_superadmin_visible_roles_include_superadmin_roles(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        roles = access_command_center._visible_role_names()

        self.assertIn("System Manager", roles)
        self.assertIn("Developer", roles)

    def test_business_admin_role_scope_rejects_superadmin_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        with self.assertRaises(ValueError):
            access_command_center._assert_role_scope(["Sales User", "System Manager"])

    def test_business_admin_role_scope_accepts_custom_business_roles(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_custom_roles = access_command_center._custom_business_role_names
        access_command_center._custom_business_role_names = lambda: ["testt"]
        try:
            access_command_center._assert_role_scope(["Sales User", "testt"])
        finally:
            access_command_center._custom_business_role_names = original_custom_roles

    def test_business_admin_cannot_see_backend_finance_permission_doctypes(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]

        self.assertFalse(access_command_center._permission_doctype_visible("Account", "Orderlift Admin"))
        self.assertFalse(access_command_center._permission_doctype_visible("Cost Center", "Finance User"))
        self.assertTrue(access_command_center._permission_doctype_visible("Sales Invoice", "Finance User"))

    def test_superadmin_sees_backend_finance_permissions_only_for_superadmin_roles(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        self.assertTrue(access_command_center._permission_doctype_visible("Account", "System Manager"))
        self.assertTrue(access_command_center._permission_doctype_visible("Cost Center", "Developer"))
        self.assertFalse(access_command_center._permission_doctype_visible("Account", "Orderlift Admin"))

    def test_business_role_permission_edit_rejects_backend_finance_doctypes(self):
        frappe_stub.session.user = "manager@example.com"
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        with self.assertRaises(ValueError):
            access_command_center._validate_permission_edit("Finance User", "Cost Center", {"read": 1})

    def test_visible_user_filters_exclude_hidden_users(self):
        original_hidden_users = access_command_center._hidden_users_for_session
        access_command_center._hidden_users_for_session = lambda: {"Administrator", "Guest"}
        try:
            filters = access_command_center._visible_user_filters({"enabled": 1})
        finally:
            access_command_center._hidden_users_for_session = original_hidden_users

        hidden_filter = next(row for row in filters if row[:3] == ["User", "name", "not in"])
        self.assertEqual(set(hidden_filter[3]), {"Administrator", "Guest"})
        self.assertIn(["User", "enabled", "=", 1], filters)

    def test_business_admin_user_scope_rejects_hidden_users(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        original_hidden_users = access_command_center._hidden_users_for_session
        access_command_center._hidden_users_for_session = lambda: {"Administrator", "Guest"}
        try:
            with self.assertRaises(ValueError):
                access_command_center._assert_user_scope("Guest")
        finally:
            access_command_center._hidden_users_for_session = original_hidden_users

    def test_business_admin_summary_treats_visible_roles_as_custom(self):
        frappe_stub.session.user = "orderlift.admin@example.com"
        frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
        originals = {
            "count_visible_users": access_command_center._count_visible_users,
            "summary_roles": access_command_center._summary_roles,
            "count_visible_admin_users": access_command_center._count_visible_admin_users,
            "has_field": access_command_center._has_field,
        }
        original_db = getattr(frappe_stub, "db", None)
        access_command_center._count_visible_users = lambda extra=None: 4 if not extra else (3 if extra.get("enabled") else 1)
        access_command_center._summary_roles = lambda: [{"name": "Orderlift Admin", "is_custom": 0}, {"name": "Sales User", "is_custom": 1}]
        access_command_center._count_visible_admin_users = lambda: 1
        access_command_center._has_field = lambda doctype, fieldname: True
        frappe_stub.db = types.SimpleNamespace(exists=lambda *args, **kwargs: False)
        try:
            summary = access_command_center._get_summary()
        finally:
            access_command_center._count_visible_users = originals["count_visible_users"]
            access_command_center._summary_roles = originals["summary_roles"]
            access_command_center._count_visible_admin_users = originals["count_visible_admin_users"]
            access_command_center._has_field = originals["has_field"]
            if original_db is None:
                delattr(frappe_stub, "db")
            else:
                frappe_stub.db = original_db

        self.assertEqual(summary["system_roles"], 0)
        self.assertEqual(summary["custom_roles"], 2)

    def test_business_admin_audit_filter_hides_superadmin_activity(self):
        originals = {
            "is_superadmin_session": access_command_center._is_superadmin_session,
            "hidden_users_for_session": access_command_center._hidden_users_for_session,
        }
        access_command_center._is_superadmin_session = lambda: False
        access_command_center._hidden_users_for_session = lambda: {"ashdrissi@gmail.com", "Administrator", "Guest"}
        try:
            self.assertFalse(access_command_center._audit_event_visible({"actor": "ashdrissi@gmail.com", "target_type": "User", "target": "orderlift.admin@ecomepivot.com"}))
            self.assertFalse(access_command_center._audit_event_visible({"actor": "orderlift.admin@ecomepivot.com", "target_type": "User", "target": "Administrator"}))
            self.assertFalse(access_command_center._audit_event_visible({"actor": "orderlift.admin@ecomepivot.com", "target_type": "Role", "target": "System Manager"}))
            self.assertTrue(access_command_center._audit_event_visible({"actor": "orderlift.admin@ecomepivot.com", "target_type": "Role", "target": "Sales User"}))
        finally:
            access_command_center._is_superadmin_session = originals["is_superadmin_session"]
            access_command_center._hidden_users_for_session = originals["hidden_users_for_session"]


if __name__ == "__main__":
    unittest.main()
