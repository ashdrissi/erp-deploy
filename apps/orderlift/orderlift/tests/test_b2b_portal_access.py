import unittest
import types
import sys
from unittest.mock import patch

frappe_stub = types.ModuleType("frappe")
frappe_stub.db = types.SimpleNamespace(
    get_value=None,
    sql=None,
    has_column=lambda doctype, fieldname: False,
    exists=lambda doctype, name=None: False,
)
frappe_stub.get_roles = None
frappe_stub.get_all = None
frappe_stub.session = types.SimpleNamespace(user="test@example.com")
frappe_stub._dict = dict
frappe_stub.PermissionError = Exception
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda *args, **kwargs: (_ for _ in ()).throw(Exception(args[0] if args else "error"))
frappe_stub._ = lambda msg: msg
sys.modules["frappe"] = frappe_stub

from orderlift.client_portal.utils import access


class TestB2BPortalAccess(unittest.TestCase):
    @patch("orderlift.client_portal.utils.access.frappe.db.get_value")
    def test_policy_name_uses_legacy_fallback_when_crm_fields_absent(self, mock_get_value):
        mock_get_value.return_value = "All Customer Groups"
        self.assertEqual(access._get_policy_name("Commercial"), "All Customer Groups")
        self.assertEqual(mock_get_value.call_count, 1)

    @patch("orderlift.client_portal.utils.access.frappe.db.get_value")
    def test_policy_name_prefers_crm_segment_policy(self, mock_get_value):
        old_has_column = access.frappe.db.has_column
        access.frappe.db.has_column = lambda doctype, fieldname: True
        mock_get_value.side_effect = ["Distribution Grossiste"]
        try:
            self.assertEqual(
                access._get_policy_name("All Customer Groups", business_type="Distribution", crm_segment="Grossiste"),
                "Distribution Grossiste",
            )
        finally:
            access.frappe.db.has_column = old_has_column
        self.assertEqual(mock_get_value.call_count, 1)

    @patch("orderlift.client_portal.utils.access.frappe.get_roles")
    @patch("orderlift.client_portal.utils.access.frappe.db.get_value")
    def test_is_b2b_only_user_true_for_website_portal_user(self, mock_get_value, mock_get_roles):
        mock_get_value.return_value = "Website User"
        mock_get_roles.return_value = ["B2B Portal Client"]
        self.assertTrue(access.is_b2b_only_user("portal@example.com"))

    @patch("orderlift.client_portal.utils.access.frappe.get_roles")
    @patch("orderlift.client_portal.utils.access.frappe.db.get_value")
    def test_is_b2b_only_user_false_for_internal_role_mix(self, mock_get_value, mock_get_roles):
        mock_get_value.return_value = "Website User"
        mock_get_roles.return_value = ["B2B Portal Client", "Sales Manager"]
        self.assertFalse(access.is_b2b_only_user("hybrid@example.com"))

    @patch("orderlift.client_portal.utils.access.frappe.get_roles")
    @patch("orderlift.client_portal.utils.access.frappe.db.get_value")
    def test_is_b2b_only_user_true_even_before_user_type_sync(self, mock_get_value, mock_get_roles):
        mock_get_value.return_value = "System User"
        mock_get_roles.return_value = ["B2B Portal Client", "Customer"]
        self.assertTrue(access.is_b2b_only_user("portal-stale@example.com"))

    @patch("orderlift.client_portal.utils.access.frappe.get_all")
    @patch("orderlift.client_portal.utils.access.frappe.db.get_value")
    @patch("orderlift.client_portal.utils.access.frappe.db.sql")
    def test_resolve_customer_falls_back_to_customer_primary_contact(self, mock_sql, mock_get_value, mock_get_all):
        mock_sql.return_value = []
        mock_get_value.return_value = "Customer A"
        mock_get_all.return_value = []
        self.assertEqual(access._resolve_customer("CONTACT-0001"), "Customer A")


if __name__ == "__main__":
    unittest.main()
