import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.session = types.SimpleNamespace(user="Administrator")
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub

from orderlift import data_import_access, menu_registry, role_capabilities
from orderlift.scripts import ensure_orderlift_admin_permissions, setup_startup_roles
from orderlift.startup_roles import CANONICAL_BUSINESS_ROLES


class TestSimplifiedAccessModel(unittest.TestCase):
    def test_canonical_role_set_is_exact(self):
        self.assertEqual(
            CANONICAL_BUSINESS_ROLES,
            [
                "Orderlift Admin",
                "Sales User",
                "Sales Manager",
                "Purchase User",
                "Purchase Manager",
                "Stock User",
                "Stock Manager",
                "Finance User",
                "Finance Admin",
                "Pricing Configuration",
                "Installation User",
                "Service User",
                "Logistics User",
            ],
        )

    def test_sales_select_only_references_and_no_item_price(self):
        permissions = setup_startup_roles.SALES_USER_PERMISSIONS

        self.assertEqual(setup_startup_roles._with_default_flags(permissions["Price List"])["select"], 1)
        self.assertEqual(setup_startup_roles._with_default_flags(permissions["Price List"])["read"], 0)
        self.assertEqual(setup_startup_roles._with_default_flags(permissions["Dimensioning Set"])["select"], 1)
        self.assertEqual(setup_startup_roles._with_default_flags(permissions["Dimensioning Set"])["read"], 0)
        self.assertNotIn("Item Price", permissions)

    def test_purchase_and_stock_users_have_no_item_price(self):
        self.assertEqual(setup_startup_roles.PURCHASE_USER_PERMISSIONS["Price List"], setup_startup_roles.SELECT_ONLY)
        self.assertEqual(
            setup_startup_roles.PURCHASE_USER_PERMISSIONS["Purchase Taxes and Charges Template"],
            setup_startup_roles.SELECT_ONLY,
        )
        self.assertEqual(setup_startup_roles.PURCHASE_USER_PERMISSIONS["Opportunity"], setup_startup_roles.SELECT_ONLY)
        self.assertEqual(setup_startup_roles.PURCHASE_USER_PERMISSIONS["Company"], setup_startup_roles.READ_ONLY)
        self.assertNotIn("Item Price", setup_startup_roles.PURCHASE_USER_PERMISSIONS)
        self.assertNotIn("Price List", setup_startup_roles.STOCK_USER_PERMISSIONS)
        self.assertNotIn("Item Price", setup_startup_roles.STOCK_USER_PERMISSIONS)
        self.assertNotIn("Stock Settings", setup_startup_roles.STOCK_USER_PERMISSIONS)

    def test_each_manager_permission_map_is_a_self_contained_superset(self):
        for user_map, manager_map in (
            (setup_startup_roles.SALES_USER_PERMISSIONS, setup_startup_roles.SALES_MANAGER_PERMISSIONS),
            (setup_startup_roles.PURCHASE_USER_PERMISSIONS, setup_startup_roles.PURCHASE_MANAGER_PERMISSIONS),
            (setup_startup_roles.STOCK_USER_PERMISSIONS, setup_startup_roles.STOCK_MANAGER_PERMISSIONS),
            (setup_startup_roles.FINANCE_USER_PERMISSIONS, setup_startup_roles.FINANCE_ADMIN_PERMISSIONS),
        ):
            for doctype, user_flags in user_map.items():
                self.assertIn(doctype, manager_map)
                normalized_user = setup_startup_roles._with_default_flags(user_flags)
                normalized_manager = setup_startup_roles._with_default_flags(manager_map[doctype])
                for flag, enabled in normalized_user.items():
                    if enabled:
                        self.assertEqual(normalized_manager[flag], 1, (doctype, flag))

    def test_capability_defaults_are_exact(self):
        defaults = role_capabilities.DEFAULT_ROLE_CAPABILITIES

        self.assertEqual(set(defaults["Orderlift Admin"]), set(role_capabilities.ROLE_CAPABILITIES))
        self.assertEqual(set(defaults["System Manager"]), set(role_capabilities.ROLE_CAPABILITIES))
        self.assertEqual(
            set(defaults["Sales Manager"]),
            {
                role_capabilities.CAPABILITY_QUOTATION_OVERRIDE,
                role_capabilities.CAPABILITY_COMMISSION_ASSIGNMENT_MANAGEMENT,
                role_capabilities.CAPABILITY_OPPORTUNITY_PIPELINE_ASSIGNMENT,
                role_capabilities.CAPABILITY_PROJECT_PIPELINE_ASSIGNMENT,
                role_capabilities.CAPABILITY_SALES_ORDER_PIPELINE_ASSIGNMENT,
            },
        )
        self.assertEqual(defaults["Purchase User"], [role_capabilities.CAPABILITY_PURCHASING_ACCESS])
        self.assertEqual(defaults["Purchase Manager"], [role_capabilities.CAPABILITY_PURCHASING_ACCESS])
        self.assertEqual(
            set(defaults["Stock Manager"]),
            {
                role_capabilities.CAPABILITY_STOCK_RATE_MANAGEMENT,
                role_capabilities.CAPABILITY_STOCK_RESERVATION_MANAGEMENT,
            },
        )
        self.assertEqual(defaults["Stock User"], [role_capabilities.CAPABILITY_STOCK_RESERVATION_MANAGEMENT])
        self.assertEqual(defaults["Logistics User"], [role_capabilities.CAPABILITY_STOCK_RESERVATION_MANAGEMENT])
        self.assertEqual(defaults["Finance Admin"], [role_capabilities.CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT])
        self.assertEqual(
            set(defaults["Pricing Configuration"]),
            {
                role_capabilities.CAPABILITY_PRIVILEGED_PRICING,
                role_capabilities.CAPABILITY_PURCHASING_ACCESS,
                role_capabilities.CAPABILITY_SAVED_OTHER_CHARGE_MANAGEMENT,
            },
        )
        for role in ("Sales User", "Finance User", "Installation User", "Service User"):
            self.assertEqual(defaults[role], [])

    def test_only_system_manager_is_a_hardcoded_capability_role(self):
        self.assertEqual(role_capabilities.HARDCODED_CAPABILITY_ROLES, {"System Manager"})
        self.assertTrue(
            role_capabilities.user_has_capability(
                role_capabilities.CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT,
                user="system@example.com",
                roles={"System Manager"},
            )
        )
        self.assertFalse(
            role_capabilities.user_has_capability(
                role_capabilities.CAPABILITY_COMMISSION_PAYOUT_MANAGEMENT,
                user="business@example.com",
                roles={"Orderlift Admin"},
            )
        )

    def test_orderlift_admin_has_no_protected_docperm_baseline(self):
        protected = ensure_orderlift_admin_permissions.PROTECTED_DOCTYPES | {
            "Permission Manager",
            "Role Permission for Page and Report",
        }
        self.assertFalse(protected.intersection(setup_startup_roles.ORDERLIFT_ADMIN_PERMISSIONS))

    def test_shared_desk_support_permissions_are_explicit(self):
        common = setup_startup_roles.COMMON_TRANSACTION_SUPPORT_PERMISSIONS
        pricing = setup_startup_roles.PRICING_CONFIGURATION_PERMISSIONS

        self.assertEqual(common["Notification Log"], setup_startup_roles.READ_ONLY)
        self.assertEqual(common["File"], setup_startup_roles.FILE_ACCESS)
        self.assertEqual(common["ToDo"], setup_startup_roles.TODO_ACCESS)
        self.assertEqual(common["Gender"], setup_startup_roles.READ_ONLY)
        self.assertEqual(common["Salutation"], setup_startup_roles.READ_ONLY)
        self.assertEqual(common["Tag"], setup_startup_roles.TAG_ACCESS)
        self.assertEqual(common["Tag Link"], setup_startup_roles.TAG_ACCESS)
        self.assertEqual(common["Email Template"], setup_startup_roles.READ_ONLY)
        for doctype, permissions in common.items():
            self.assertIn(doctype, pricing)
            self.assertEqual(pricing[doctype], permissions)
        self.assertEqual(pricing["Data Import"], setup_startup_roles.MASTER_MANAGER)
        self.assertEqual(pricing["Data Import Log"], setup_startup_roles.READ_ONLY)
        self.assertNotIn("Error Log", setup_startup_roles.ORDERLIFT_ADMIN_PERMISSIONS)

    def test_importable_doctype_query_returns_only_permitted_parent_doctypes(self):
        original_has_permission = getattr(frappe_stub, "has_permission", None)
        original_get_all = getattr(frappe_stub, "get_all", None)
        calls = []

        def has_permission(doctype, ptype=None, throw=False, **kwargs):
            calls.append((doctype, ptype, throw))
            return doctype in {"Data Import", "Item", "Customer"}

        frappe_stub.has_permission = has_permission
        frappe_stub.get_all = lambda *args, **kwargs: [
            {"name": "Customer", "module": "Selling"},
            {"name": "Error Log", "module": "Core"},
            {"name": "Item", "module": "Stock"},
        ]
        try:
            result = data_import_access.get_importable_doctypes(start=0, page_len=20)
        finally:
            if original_has_permission is None:
                delattr(frappe_stub, "has_permission")
            else:
                frappe_stub.has_permission = original_has_permission
            if original_get_all is None:
                delattr(frappe_stub, "get_all")
            else:
                frappe_stub.get_all = original_get_all

        self.assertEqual(result, [["Customer", "Selling"], ["Item", "Stock"]])
        self.assertIn(("Data Import", "read", True), calls)
        self.assertIn(("Error Log", "import", False), calls)

    def test_system_manager_has_the_business_baseline_without_orderlift_admin(self):
        for doctype, permissions in setup_startup_roles.ORDERLIFT_ADMIN_PERMISSIONS.items():
            system_permissions = setup_startup_roles.SYSTEM_MANAGER_BUSINESS_PERMISSIONS[doctype]
            for flag, enabled in permissions.items():
                if enabled:
                    self.assertEqual(system_permissions.get(flag), 1, (doctype, flag))
        self.assertIn("Sales Order", setup_startup_roles.SYSTEM_MANAGER_BUSINESS_PERMISSIONS)
        self.assertIn("Purchase Receipt", setup_startup_roles.SYSTEM_MANAGER_BUSINESS_PERMISSIONS)
        self.assertIn("Account", setup_startup_roles.SYSTEM_MANAGER_BUSINESS_PERMISSIONS)
        self.assertNotIn("Account", setup_startup_roles.ORDERLIFT_ADMIN_PERMISSIONS)

    def test_pricing_menu_is_configuration_only_and_simulator_is_removed(self):
        self.assertIsNone(menu_registry.menu_item_by_key("sales.pricing_simulator"))
        for key in (
            "items.item_price",
            "items.price_list",
            "items.buying_price_builder",
            "items.static_pricing_builder",
            "items.dimensioning_sets",
        ):
            self.assertEqual(
                menu_registry.menu_item_by_key(key)["roles"],
                menu_registry.PRICING_CONFIGURATION_ROLES,
            )


if __name__ == "__main__":
    unittest.main()
