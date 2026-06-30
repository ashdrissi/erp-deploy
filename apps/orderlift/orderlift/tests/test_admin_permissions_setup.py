import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = frappe_stub


from orderlift.scripts import ensure_orderlift_admin_permissions


class TestAdminPermissionsSetup(unittest.TestCase):
    def test_orderlift_admin_has_item_category_filter_access(self):
        permissions = ensure_orderlift_admin_permissions.ADMIN_DOCTYPE_PERMISSIONS["Item Category"]

        self.assertEqual(permissions["read"], 1)
        self.assertEqual(permissions["select"], 1)
        self.assertEqual(permissions["write"], 1)

    def test_orderlift_admin_has_partner_campaign_access(self):
        permissions = ensure_orderlift_admin_permissions.ADMIN_DOCTYPE_PERMISSIONS["Partner Campaign"]

        self.assertEqual(permissions["read"], 1)
        self.assertEqual(permissions["write"], 1)
        self.assertEqual(permissions["create"], 1)
        self.assertEqual(permissions["report"], 1)
        self.assertEqual(permissions["share"], 0)

    def test_orderlift_admin_has_training_admin_access(self):
        for doctype in [
            "Performance Metric",
            "Performance Metric Snapshot",
            "Performance Profile",
            "Training Level",
            "Training Module",
            "Training Quiz",
            "Training Quiz Attempt",
            "Training Quiz Question",
        ]:
            permissions = ensure_orderlift_admin_permissions.ADMIN_DOCTYPE_PERMISSIONS[doctype]
            self.assertEqual(permissions["read"], 1)
            self.assertEqual(permissions["write"], 1)
            self.assertEqual(permissions["create"], 1)

    def test_orderlift_admin_has_classification_and_menu_rule_access(self):
        for doctype in [
            "CRM Business Type",
            "CRM Segment",
            "Installation Stage",
            "Orderlift Menu Access Rule",
            "Partner Segment",
        ]:
            permissions = ensure_orderlift_admin_permissions.ADMIN_DOCTYPE_PERMISSIONS[doctype]
            self.assertEqual(permissions["read"], 1)
            self.assertEqual(permissions["write"], 1)
            self.assertEqual(permissions["create"], 1)

    def test_orderlift_admin_has_pricing_catalog_access(self):
        for doctype in [
            "Item",
            "Item Price",
            "Price List",
            "Pricing Builder",
            "Pricing Sheet",
            "Pricing Scenario",
            "Pricing Customs Policy",
            "Pricing Benchmark Policy",
        ]:
            permissions = ensure_orderlift_admin_permissions.ADMIN_DOCTYPE_PERMISSIONS[doctype]
            self.assertEqual(permissions["read"], 1)
            self.assertEqual(permissions["write"], 1)
            self.assertEqual(permissions["create"], 1)
            self.assertEqual(permissions["delete"], 1)
            self.assertEqual(permissions["select"], 1)

    def test_default_flags_include_select(self):
        permissions = ensure_orderlift_admin_permissions._with_default_flags({"read": 1})

        self.assertEqual(permissions["select"], 0)

    def test_managed_doctype_share_is_forced_off(self):
        permissions = ensure_orderlift_admin_permissions._permission_flags_for_doctype("Company", {"read": 1, "share": 1})

        self.assertEqual(permissions["share"], 0)
        self.assertEqual(permissions["if_owner"], 0)

        campaign_target = ensure_orderlift_admin_permissions._permission_flags_for_doctype(
            "Partner Campaign Target", {"read": 1, "share": 1}
        )
        self.assertEqual(campaign_target["share"], 0)

    def test_unmanaged_doctype_share_is_not_forced_off(self):
        permissions = ensure_orderlift_admin_permissions._permission_flags_for_doctype("CRM Segment", {"read": 1, "share": 1})

        self.assertEqual(permissions["share"], 1)


if __name__ == "__main__":
    unittest.main()
