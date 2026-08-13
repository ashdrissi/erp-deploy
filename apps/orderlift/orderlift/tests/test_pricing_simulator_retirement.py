import ast
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[2]
ORDERLIFT_ROOT = APP_ROOT / "orderlift"


class TestPricingSimulatorRetirement(unittest.TestCase):
    def test_shortcuts_and_delivery_references_are_removed(self):
        paths = [
            ORDERLIFT_ROOT / "orderlift_sales" / "page" / "pricing_dashboard" / "pricing_dashboard.js",
            ORDERLIFT_ROOT / "orderlift" / "page" / "orderlift_home" / "orderlift_home.js",
            ORDERLIFT_ROOT / "orderlift_logistics" / "page" / "home_page" / "home_page.js",
            ORDERLIFT_ROOT / "orderlift" / "page" / "business_delivery" / "business_delivery.js",
        ]

        for path in paths:
            source = path.read_text()
            self.assertNotIn("pricing-simulator", source, msg=str(path))
            self.assertNotIn("Pricing Simulator", source, msg=str(path))

    def test_page_roles_are_empty_and_route_is_explicitly_retired(self):
        page = json.loads(
            (ORDERLIFT_ROOT / "orderlift_sales" / "page" / "pricing_simulator" / "pricing_simulator.json").read_text()
        )
        menu_access = (ORDERLIFT_ROOT / "menu_access.py").read_text()
        route_guard = (ORDERLIFT_ROOT / "restricted_user_guard.py").read_text()

        self.assertEqual(page["roles"], [])
        self.assertIn("from orderlift.retired_pages import RETIRED_PAGE_NAMES", menu_access)
        retired_pages = (ORDERLIFT_ROOT / "retired_pages.py").read_text()
        self.assertIn('"pricing-simulator": "/desk/home-page"', retired_pages)
        self.assertIn("if page_name in RETIRED_PAGE_NAMES:", menu_access)
        self.assertIn("RETIRED_PAGE_SLUGS = RETIRED_PAGE_NAMES", route_guard)
        self.assertIn("if slug in RETIRED_PAGE_SLUGS:", route_guard)

        workbench = json.loads(
            (
                ORDERLIFT_ROOT
                / "orderlift_sales"
                / "doctype"
                / "pricing_simulator_workbench"
                / "pricing_simulator_workbench.json"
            ).read_text()
        )
        self.assertEqual(workbench["permissions"], [])

    def test_retired_route_redirects_without_affecting_other_admin_pages(self):
        frappe_stub = types.ModuleType("frappe")
        frappe_stub.session = types.SimpleNamespace(user="Administrator")
        frappe_stub.flags = types.SimpleNamespace()
        frappe_stub.local = types.SimpleNamespace(
            request=types.SimpleNamespace(path="/app/pricing-simulator"),
            response={},
            flags=types.SimpleNamespace(),
        )
        frappe_stub.get_roles = lambda user=None: ["System Manager"]

        menu_access_stub = types.ModuleType("orderlift.menu_access")
        menu_access_stub.user_can_access_page = lambda page_name, user=None: True
        werkzeug_stub = types.ModuleType("werkzeug")
        werkzeug_wrappers_stub = types.ModuleType("werkzeug.wrappers")
        werkzeug_wrappers_stub.Response = type("Response", (), {})
        path = ORDERLIFT_ROOT / "restricted_user_guard.py"
        spec = importlib.util.spec_from_file_location("restricted_user_guard_retirement_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(
            sys.modules,
            {
                "frappe": frappe_stub,
                "orderlift.menu_access": menu_access_stub,
                "werkzeug": werkzeug_stub,
                "werkzeug.wrappers": werkzeug_wrappers_stub,
            },
        ):
            spec.loader.exec_module(module)

        module.guard_orderlift_menu_routes()
        self.assertEqual(frappe_stub.local.response["location"], "/desk/home-page")

        frappe_stub.flags = types.SimpleNamespace()
        frappe_stub.local = types.SimpleNamespace(
            request=types.SimpleNamespace(path="/app/pricing-dashboard"),
            response={},
            flags=types.SimpleNamespace(),
        )
        module.guard_orderlift_menu_routes()
        self.assertEqual(frappe_stub.local.response, {})

    def test_all_whitelisted_simulator_apis_call_retirement_guard_first(self):
        expected = {
            ORDERLIFT_ROOT / "orderlift_sales" / "page" / "pricing_simulator" / "pricing_simulator.py": {
                "get_simulation_defaults",
                "run_pricing_simulation",
            },
            ORDERLIFT_ROOT
            / "orderlift_sales"
            / "doctype"
            / "pricing_simulator_workbench"
            / "pricing_simulator_workbench.py": {
                "load_defaults",
                "run_simulation",
                "load_defaults_doc",
                "run_simulation_doc",
                "run_simulation_preview",
            },
        }

        for path, function_names in expected.items():
            tree = ast.parse(path.read_text())
            functions = {
                node.name: node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in function_names
            }
            self.assertEqual(set(functions), function_names)
            for name, node in functions.items():
                first = node.body[0]
                self.assertIsInstance(first, ast.Expr, msg=name)
                self.assertIsInstance(first.value, ast.Call, msg=name)
                self.assertEqual(getattr(first.value.func, "id", ""), "deny_pricing_simulator_access", msg=name)

    def test_legacy_dashboard_apis_are_retired_before_data_access(self):
        expected = {
            ORDERLIFT_ROOT / "orderlift" / "page" / "orderlift_home" / "orderlift_home.py": (
                "get_dashboard_data",
                "orderlift-home",
            ),
            ORDERLIFT_ROOT / "orderlift_sales" / "page" / "finance_dashboard" / "finance_dashboard.py": (
                "get_dashboard_data",
                "finance-dashboard",
            ),
            ORDERLIFT_ROOT / "orderlift_logistics" / "page" / "operations_pipeline" / "operations_pipeline.py": (
                "get_pipeline_data",
                "operations-pipeline",
            ),
        }
        for path, (function_name, page_name) in expected.items():
            tree = ast.parse(path.read_text())
            function = next(
                node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == function_name
            )
            body = function.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            first = body[0]
            self.assertIsInstance(first, ast.Expr, msg=str(path))
            self.assertEqual(getattr(first.value.func, "id", ""), "deny_retired_page", msg=str(path))
            self.assertEqual(first.value.args[0].value, page_name)

    def test_retirement_guard_raises_permission_error_with_clear_message(self):
        class RetiredPermissionError(PermissionError):
            pass

        frappe_stub = types.ModuleType("frappe")
        frappe_stub.PermissionError = RetiredPermissionError
        frappe_stub._ = lambda value: value

        def throw(message, exc):
            raise exc(message)

        frappe_stub.throw = throw
        path = ORDERLIFT_ROOT / "orderlift_sales" / "utils" / "pricing_simulator_retirement.py"
        spec = importlib.util.spec_from_file_location("pricing_simulator_retirement_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frappe": frappe_stub}):
            spec.loader.exec_module(module)

        with self.assertRaisesRegex(RetiredPermissionError, "Pricing Simulator has been retired"):
            module.deny_pricing_simulator_access()

    def test_pricing_builder_uses_neutral_item_group_helpers(self):
        builder = (
            ORDERLIFT_ROOT / "orderlift_sales" / "doctype" / "pricing_builder" / "pricing_builder.py"
        ).read_text()
        helper = (ORDERLIFT_ROOT / "orderlift_sales" / "utils" / "item_group.py").read_text()

        self.assertNotIn("page.pricing_simulator", builder)
        self.assertIn("from orderlift.orderlift_sales.utils.item_group import", builder)
        self.assertIn("def is_item_group_node", helper)
        self.assertIn("def descendant_leaf_item_groups", helper)

    def test_home_translation_copy_no_longer_mentions_simulator(self):
        translations = (ORDERLIFT_ROOT / "scripts" / "setup_french_translations.py").read_text()

        self.assertNotIn('"Sheets · Policies · Simulator"', translations)
        self.assertNotIn('"Price sheets, policies, simulator"', translations)
        self.assertIn('"Policies · Scenarios · Builders"', translations)
        self.assertIn('"Price sheets, policies, builders"', translations)
        self.assertIn('"Pricing Simulator has been retired. Use Pricing Sheet Builder instead."', translations)


if __name__ == "__main__":
    unittest.main()
