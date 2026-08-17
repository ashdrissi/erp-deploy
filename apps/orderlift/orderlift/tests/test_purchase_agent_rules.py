import importlib
import sys
import types
import unittest
from pathlib import Path


STUBBED_MODULES = (
    "frappe",
    "frappe.utils",
    "orderlift.reference_access",
    "orderlift.menu_access",
    "orderlift.role_capabilities",
    "orderlift.orderlift_sales.utils.price_list_scope",
)
ORIGINAL_MODULES = {name: sys.modules.get(name) for name in STUBBED_MODULES}


class FakeDB:
    def __init__(self):
        self.rules = []
        self.rows = []

    def exists(self, doctype, name=None, *args, **kwargs):
        return doctype == "DocType" and name == "Purchase Agent Rules"

    def has_column(self, doctype, fieldname):
        return fieldname in {"enabled", "custom_price_list_type", "custom_company", "buying", "selling"}

    def get_all(self, doctype, filters=None, fields=None, pluck=None, **kwargs):
        if doctype == "Purchase Agent Rules":
            return list(self.rules)
        if doctype == "Purchase Agent Allowed Buying Price List":
            return list(self.rows)
        return []


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="buyer@example.com")
frappe_stub._ = lambda message, *args, **kwargs: message
frappe_stub.get_roles = lambda user=None: []
frappe_stub.get_all = lambda doctype, filters=None, fields=None, pluck=None, **kwargs: [
    {"name": "BUY-A"},
    {"name": "BUY-B"},
] if doctype == "Price List" and not pluck else (["BUY-A", "BUY-B"] if doctype == "Price List" else [])
frappe_stub.db = FakeDB()
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = frappe_utils_stub

reference_access_stub = types.ModuleType("orderlift.reference_access")
reference_access_stub.require_reference_use = lambda *args, **kwargs: args[1] if len(args) > 1 else ""
sys.modules["orderlift.reference_access"] = reference_access_stub

menu_access_stub = types.ModuleType("orderlift.menu_access")
menu_access_stub.resolve_current_company = lambda user=None: "Orderlift"
sys.modules["orderlift.menu_access"] = menu_access_stub

role_capabilities_stub = types.ModuleType("orderlift.role_capabilities")
role_capabilities_stub.CAPABILITY_PRIVILEGED_PRICING = "privileged_pricing"
role_capabilities_stub.CAPABILITY_PURCHASING_ACCESS = "purchasing_access"
role_capabilities_stub.CAPABILITY_QUOTATION_OVERRIDE = "quotation_override"
role_capabilities_stub.role_capability_decision = lambda capability, legacy_allowed, **kwargs: capability in CAPABILITIES
CAPABILITIES = set()
sys.modules["orderlift.role_capabilities"] = role_capabilities_stub


sys.modules.pop("orderlift.orderlift_sales.utils.price_list_scope", None)
price_list_scope = importlib.import_module("orderlift.orderlift_sales.utils.price_list_scope")

for module_name, original in ORIGINAL_MODULES.items():
    if original is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPurchaseAgentRulesPriceScope(unittest.TestCase):
    def setUp(self):
        CAPABILITIES.clear()
        frappe_stub.db.rules = []
        frappe_stub.db.rows = []

    def test_non_privileged_user_without_policy_cannot_see_buying_lists(self):
        CAPABILITIES.add("purchasing_access")

        visible = price_list_scope.get_visible_price_lists("buying", company="Orderlift", user="buyer@example.com")

        self.assertEqual(visible, [])

    def test_policy_limits_non_privileged_user_to_active_allowed_lists(self):
        CAPABILITIES.add("purchasing_access")
        frappe_stub.db.rules = ["PAR-00001"]
        frappe_stub.db.rows = [
            {"buying_price_list": "BUY-A"},
            {"buying_price_list": "BUY-MISSING"},
        ]

        visible = price_list_scope.get_visible_price_lists("buying", company="Orderlift", user="buyer@example.com")

        self.assertEqual(visible, ["BUY-A"])

    def test_privileged_pricing_bypasses_purchase_policy_allowance(self):
        CAPABILITIES.add("privileged_pricing")

        visible = price_list_scope.get_visible_price_lists("buying", company="Orderlift", user="buyer@example.com")

        self.assertEqual(visible, ["BUY-A", "BUY-B"])

    def test_item_price_access_hides_buying_grid_without_policy(self):
        CAPABILITIES.add("purchasing_access")

        access = price_list_scope.get_item_price_access("buying", company="Orderlift")

        self.assertFalse(access["permitted"])
        self.assertEqual(access["reason"], "no_purchase_agent_rule")


class TestPurchaseAgentRulesContract(unittest.TestCase):
    def test_doctypes_are_company_scoped_and_capability_gated(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        scope = (APP_ROOT / "company_scope.py").read_text()
        access = (APP_ROOT / "company_access.py").read_text()
        controller = (
            APP_ROOT
            / "orderlift_logistics"
            / "doctype"
            / "purchase_agent_rules"
            / "purchase_agent_rules.py"
        ).read_text()

        self.assertIn('"Purchase Agent Rules": {"company_field": "company"', scope)
        self.assertIn('"Purchase Agent Rules": "orderlift.company_access.purchase_agent_rules_query"', hooks)
        self.assertIn("has_purchase_agent_rules_permission", hooks)
        self.assertIn("CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT", controller)
        self.assertIn("get_price_list_type", controller)
        self.assertIn("BUYING_PRICE_LIST", controller)
        self.assertIn("if not cint(row.is_active):", controller)
        self.assertIn("continue", controller)
        self.assertNotIn("Purchase Manager", controller)

    def test_menu_uses_capability_not_purchase_role_names(self):
        registry = (APP_ROOT / "menu_registry.py").read_text()
        menu_access_source = (APP_ROOT / "menu_access.py").read_text()

        self.assertIn('"label": "Sales Agent Rules"', registry)
        self.assertIn('"key": "policies.purchase_agent_rules"', registry)
        self.assertIn('"required_capability": "purchase_agent_rules_management"', registry)
        self.assertIn("_required_capability_allowed", menu_access_source)

    def test_purchase_policy_schema_has_only_buying_allowance_fields(self):
        parent = (
            APP_ROOT
            / "orderlift_logistics"
            / "doctype"
            / "purchase_agent_rules"
            / "purchase_agent_rules.json"
        ).read_text()
        child = (
            APP_ROOT
            / "orderlift_logistics"
            / "doctype"
            / "purchase_agent_allowed_buying_price_list"
            / "purchase_agent_allowed_buying_price_list.json"
        ).read_text()

        for fieldname in ["purchase_user", "company", "enabled", "allowed_buying_price_lists"]:
            self.assertIn(f'"fieldname": "{fieldname}"', parent)
        for fieldname in ["buying_price_list", "is_active", "is_default", "priority"]:
            self.assertIn(f'"fieldname": "{fieldname}"', child)
        self.assertNotIn("sales_person", parent)
        self.assertNotIn("commission_rate", parent)
        self.assertNotIn("selling_price_list", child)


if __name__ == "__main__":
    unittest.main()
