import sys
import types
import unittest


deleted_docs = []
existing_docs = {
    "Delivery Note-custom_assigned_container_load_plan",
    "Delivery Trip-custom_container_load_plan",
}


def _exists(doctype, name):
    return doctype == "Custom Field" and name in existing_docs


def _delete_doc(doctype, name, ignore_permissions=False):
    deleted_docs.append((doctype, name, ignore_permissions))


frappe_stub = types.ModuleType("frappe")
frappe_stub.db = types.SimpleNamespace(exists=_exists)
frappe_stub.delete_doc = _delete_doc

custom_field_module = types.ModuleType("frappe.custom.doctype.custom_field.custom_field")
custom_field_module.create_custom_fields = lambda *args, **kwargs: None

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.custom"] = types.ModuleType("frappe.custom")
sys.modules["frappe.custom.doctype"] = types.ModuleType("frappe.custom.doctype")
sys.modules["frappe.custom.doctype.custom_field"] = types.ModuleType("frappe.custom.doctype.custom_field")
sys.modules["frappe.custom.doctype.custom_field.custom_field"] = custom_field_module


from orderlift.logistics import setup as logistics_setup


class TestLogisticsSetup(unittest.TestCase):
    def test_remove_retired_custom_fields_deletes_legacy_clp_fields(self):
        deleted_docs.clear()

        logistics_setup.remove_retired_custom_fields()

        self.assertEqual(
            deleted_docs,
            [
                ("Custom Field", "Delivery Note-custom_assigned_container_load_plan", True),
                ("Custom Field", "Delivery Trip-custom_container_load_plan", True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
