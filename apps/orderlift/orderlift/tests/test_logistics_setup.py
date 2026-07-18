import sys
import types
import unittest
from pathlib import Path


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

    def test_purchase_order_grid_hides_internal_packaging_ids_and_shows_readable_snapshot(self):
        source = (Path(__file__).resolve().parents[1] / "logistics" / "setup.py").read_text()
        section = source.split('"Purchase Order Item": [', 1)[1].split('"Purchase Receipt": [', 1)[0]

        profile = section.split('"fieldname": "custom_packaging_profile"', 1)[1].split("},", 1)[0]
        source_field = section.split('"fieldname": "custom_packaging_profile_source"', 1)[1].split("},", 1)[0]
        self.assertIn('"in_list_view": 0', profile)
        self.assertIn('"in_list_view": 0', source_field)
        for fieldname in ("custom_packaging_type", "custom_packaging_uom", "custom_units_per_package", "custom_package_count"):
            field = section.split(f'"fieldname": "{fieldname}"', 1)[1].split("},", 1)[0]
            self.assertIn('"in_list_view": 1', field)


if __name__ == "__main__":
    unittest.main()
