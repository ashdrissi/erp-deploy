import importlib
import sys
import types
import unittest


class RoleRow:
    def __init__(self, role):
        self.role = role


class UserDoc(dict):
    def __init__(self, name, roles, role_profile_name=""):
        super().__init__(role_profile_name=role_profile_name)
        self.name = name
        self.roles = [RoleRow(role) for role in roles]
        self.save_count = 0

    def get(self, key, default=None):
        if key == "roles":
            return self.roles
        return super().get(key, default)

    def set(self, key, value):
        if key == "roles":
            self.roles = []
        else:
            self[key] = value

    def append(self, key, value):
        self.roles.append(RoleRow(value["role"]))

    @property
    def role_profile_name(self):
        return self.get("role_profile_name", "")

    @role_profile_name.setter
    def role_profile_name(self, value):
        self["role_profile_name"] = value

    def save(self, ignore_permissions=False):
        self.save_count += 1


class DbStub:
    def __init__(self, users):
        self.users = users
        self.commits = 0

    def exists(self, doctype, name):
        if doctype == "User":
            return name in self.users
        if doctype == "DocType" and name == "Sales Person":
            return True
        return False

    def has_column(self, doctype, fieldname):
        return doctype == "Sales Person" and fieldname == "user"

    def get_value(self, doctype, filters, fieldname):
        if doctype == "Sales Person" and filters.get("user") == "haitem@orderlift.net":
            return "Haitem"
        return ""

    def commit(self):
        self.commits += 1


def load_module(users):
    frappe = types.ModuleType("frappe")
    frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe.only_for = lambda roles: None
    frappe.db = DbStub(users)
    frappe.get_doc = lambda doctype, name: users[name]
    frappe.get_all = lambda *args, **kwargs: []
    frappe.delete_doc = lambda *args, **kwargs: None
    frappe.clear_cache = lambda: None
    sys.modules["frappe"] = frappe

    utils = types.ModuleType("frappe.utils")
    utils.cint = lambda value=0: int(value or 0)
    sys.modules["frappe.utils"] = utils

    sys.modules.pop("orderlift.scripts.normalize_simplified_user_roles", None)
    module = importlib.import_module("orderlift.scripts.normalize_simplified_user_roles")
    return module, frappe


class TestSimplifiedUserRoles(unittest.TestCase):
    def test_target_map_is_exact(self):
        module, _frappe = load_module({})

        self.assertEqual(module.TARGET_USER_ROLES["ashdrissi@gmail.com"], ["System Manager"])
        self.assertEqual(module.TARGET_USER_ROLES["bilalorderlift@gmail.com"], ["Sales User", "Purchase User", "Stock User"])
        self.assertEqual(module.TARGET_USER_ROLES["orderlift.admin@ecomepivot.com"], ["Orderlift Admin"])
        self.assertEqual(module.TARGET_USER_ROLES["ashdrissi1@gmail.com"], [])

    def test_dry_run_makes_zero_writes_and_reports_mapping_gaps(self):
        bilal = UserDoc("bilalorderlift@gmail.com", ["All", "Logistics User", "Quotation Creator"], "Legacy Profile")
        orderlift_admin = UserDoc("orderlift.admin@ecomepivot.com", ["Orderlift Admin"])
        module, frappe = load_module({bilal.name: bilal, orderlift_admin.name: orderlift_admin})

        result = module.run()

        self.assertTrue(result["dry_run"])
        self.assertEqual(bilal.save_count, 0)
        self.assertEqual(orderlift_admin.save_count, 0)
        self.assertEqual(frappe.db.commits, 0)
        self.assertIn("bilalorderlift@gmail.com", result["missing_sales_person_mappings"])
        bilal_result = next(row for row in result["users"] if row["user"] == bilal.name)
        self.assertEqual(bilal_result["desired_roles"], ["Sales User", "Purchase User", "Stock User"])
        self.assertIn("Logistics User", bilal_result["removed_roles"])

    def test_apply_preserves_implicit_roles_and_clears_profile(self):
        bilal = UserDoc("bilalorderlift@gmail.com", ["All", "Logistics User", "Quotation Creator"], "Legacy Profile")
        module, frappe = load_module({bilal.name: bilal})

        result = module.run(dry_run=0)

        self.assertFalse(result["dry_run"])
        self.assertEqual([row.role for row in bilal.roles], ["All", "Sales User", "Purchase User", "Stock User"])
        self.assertEqual(bilal.role_profile_name, "")
        self.assertEqual(bilal.save_count, 1)
        self.assertEqual(frappe.db.commits, 1)


if __name__ == "__main__":
    unittest.main()
