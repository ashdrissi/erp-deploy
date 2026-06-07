import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub


from orderlift.scripts import ensure_orderlift_admin_permissions


class TestAdminPermissionsSetup(unittest.TestCase):
    def test_orderlift_admin_has_item_category_filter_access(self):
        permissions = ensure_orderlift_admin_permissions.ADMIN_DOCTYPE_PERMISSIONS["Item Category"]

        self.assertEqual(permissions["read"], 1)
        self.assertEqual(permissions["select"], 1)
        self.assertEqual(permissions["write"], 1)

    def test_default_flags_include_select(self):
        permissions = ensure_orderlift_admin_permissions._with_default_flags({"read": 1})

        self.assertEqual(permissions["select"], 0)


if __name__ == "__main__":
    unittest.main()
