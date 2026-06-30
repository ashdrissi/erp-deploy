import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift.scripts import sync_page_roles_from_menu_registry


class TestPageRoleSync(unittest.TestCase):
    def test_menu_page_role_map_merges_duplicate_page_links(self):
        page_roles = sync_page_roles_from_menu_registry.menu_page_role_map()

        self.assertIn("sales-order-pipeline", page_roles)
        self.assertIn("Sales User", page_roles["sales-order-pipeline"])
        self.assertIn("Installation User", page_roles["sales-order-pipeline"])
        self.assertIn("campaign-editor", page_roles)
        self.assertIn("Campaign Manager", page_roles["campaign-editor"])
        self.assertNotIn("Sales User", page_roles["campaign-editor"])
        self.assertIn("campaign-manager", page_roles)
        self.assertIn("Campaign Manager", page_roles["campaign-manager"])
        self.assertNotIn("Sales User", page_roles["campaign-manager"])
        self.assertIn("project-pipeline", page_roles)
        self.assertIn("Sales User", page_roles["project-pipeline"])

    def test_menu_page_role_map_preserves_order_without_duplicates(self):
        page_roles = sync_page_roles_from_menu_registry.menu_page_role_map()

        self.assertEqual(len(page_roles["project-pipeline"]), len(set(page_roles["project-pipeline"])))

    def test_campaign_page_roles_are_strict(self):
        strict_page_roles = sync_page_roles_from_menu_registry.strict_menu_page_role_map()

        self.assertEqual(strict_page_roles["campaign-manager"], ["Orderlift Admin", "Campaign Manager"])
        self.assertEqual(strict_page_roles["campaign-editor"], ["Orderlift Admin", "Campaign Manager"])

    def test_sync_script_updates_page_and_menu_rule_roles(self):
        source = sync_page_roles_from_menu_registry.__loader__.get_source(
            sync_page_roles_from_menu_registry.__name__
        )

        self.assertIn("menu_rules_added", source)
        self.assertIn("menu_rules_removed", source)
        self.assertIn("allowed_roles_json", source)
        self.assertIn("sync_menu_access_rules", source)


if __name__ == "__main__":
    unittest.main()
