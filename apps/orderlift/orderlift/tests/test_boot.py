import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub.session = types.SimpleNamespace(user="Guest")
frappe_stub.get_roles = lambda user=None: []
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub

werkzeug_stub = types.ModuleType("werkzeug")
werkzeug_wrappers_stub = types.ModuleType("werkzeug.wrappers")
werkzeug_wrappers_stub.Response = type("Response", (), {})
sys.modules["werkzeug"] = werkzeug_stub
sys.modules["werkzeug.wrappers"] = werkzeug_wrappers_stub


from orderlift.boot import _strip_demo_navbar_items


class TestBootHelpers(unittest.TestCase):
    def test_strip_demo_navbar_items_removes_delete_demo_data(self):
        bootinfo = {
            "navbar_settings": {
                "settings_dropdown": [
                    {"item_label": "Delete Demo Data"},
                    {"item_label": "Reload"},
                    {"label": "Delete Demo Data"},
                ]
            }
        }

        _strip_demo_navbar_items(bootinfo)

        self.assertEqual(bootinfo["navbar_settings"]["settings_dropdown"], [{"item_label": "Reload"}])

    def test_strip_demo_navbar_items_supports_document_settings(self):
        navbar_settings = types.SimpleNamespace(
            settings_dropdown=[{"item_label": "Delete Demo Data"}, {"item_label": "Reload"}]
        )

        _strip_demo_navbar_items({"navbar_settings": navbar_settings})

        self.assertEqual(navbar_settings.settings_dropdown, [{"item_label": "Reload"}])


if __name__ == "__main__":
    unittest.main()
