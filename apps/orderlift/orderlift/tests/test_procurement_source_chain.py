import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeDB:
    def get_all(self, *args, **kwargs):
        return []


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda message, *args, **kwargs: message
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.parse_json = lambda value: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.has_permission = lambda *args, **kwargs: True
frappe_stub.get_list = lambda doctype, filters=None, pluck=None, **kwargs: filters["name"][1]
frappe_stub.db = FakeDB()

custom_stub = types.ModuleType("frappe.custom")
doctype_stub = types.ModuleType("frappe.custom.doctype")
custom_field_package_stub = types.ModuleType("frappe.custom.doctype.custom_field")
custom_field_stub = types.ModuleType("frappe.custom.doctype.custom_field.custom_field")
custom_field_stub.create_custom_fields = lambda *args, **kwargs: None

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.custom"] = custom_stub
sys.modules["frappe.custom.doctype"] = doctype_stub
sys.modules["frappe.custom.doctype.custom_field"] = custom_field_package_stub
sys.modules["frappe.custom.doctype.custom_field.custom_field"] = custom_field_stub


from orderlift.orderlift_logistics import source_chain


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProcurementSourceChain(unittest.TestCase):
    def setUp(self):
        frappe_stub.get_list = lambda doctype, filters=None, pluck=None, **kwargs: filters["name"][1]

    def test_purchase_invoice_resolves_sales_order_through_po_and_mr_items(self):
        document = {
            "doctype": "Purchase Invoice",
            "name": "PINV-1",
            "items": [{"idx": 1, "item_code": "MOTOR", "purchase_order": "PO-1", "po_detail": "POI-1"}],
        }
        lookup = {
            "Purchase Receipt Item": {},
            "Purchase Order Item": {
                "POI-1": {"material_request": "MR-1", "material_request_item": "MRI-1"},
            },
            "Material Request Item": {
                "MRI-1": {"sales_order": "SO-1", "sales_order_item": "SOI-1"},
            },
            "Sales Order Item": {"SOI-1": {"parent": "SO-1", "prevdoc_docname": "QTN-1"}},
            "Quotation": {"QTN-1": {"opportunity": "OPP-1"}},
        }

        with patch.object(source_chain, "_rows_by_name", side_effect=lambda doctype, *args: lookup[doctype]):
            result = source_chain.get_upstream_source_chain(document)

        stages = result["groups"][0]["stages"]
        self.assertEqual(
            [(stage["doctype"], stage["documents"][0]["name"]) for stage in stages],
            [
                ("Opportunity", "OPP-1"),
                ("Quotation", "QTN-1"),
                ("Sales Order", "SO-1"),
                ("Material Request", "MR-1"),
                ("Purchase Order", "PO-1"),
                ("Purchase Invoice", "PINV-1"),
            ],
        )

    def test_supplier_based_po_recovers_sales_order_item_from_material_request_item(self):
        rows = source_chain._prepare_rows(
            {
                "doctype": "Purchase Order",
                "name": "PO-1",
                "items": [{"idx": 1, "item_code": "MOTOR", "material_request": "MR-1", "material_request_item": "MRI-1", "sales_order": "SO-1"}],
            },
            False,
        )
        lookup = {
            "Purchase Receipt Item": {},
            "Purchase Order Item": {},
            "Material Request Item": {"MRI-1": {"sales_order": "SO-1", "sales_order_item": "SOI-1"}},
        }

        with patch.object(source_chain, "_rows_by_name", side_effect=lambda doctype, *args: lookup[doctype]):
            source_chain._resolve_item_references(rows)

        self.assertEqual(rows[0]["refs"]["sales_order"], "SO-1")
        self.assertEqual(rows[0]["refs"]["sales_order_item"], "SOI-1")

    def test_manual_item_is_returned_without_a_source_group(self):
        result = source_chain.get_upstream_source_chain(
            {
                "doctype": "Purchase Order",
                "name": "PO-1",
                "items": [{"idx": 1, "item_code": "MANUAL-ITEM", "qty": 2}],
            }
        )

        self.assertEqual(result["state"], "manual")
        self.assertEqual(result["groups"], [])
        self.assertEqual(result["manual_rows"][0]["item_code"], "MANUAL-ITEM")

    def test_restricted_source_returns_identifier_without_document_access(self):
        document = {
            "doctype": "Material Request",
            "name": "MR-1",
            "items": [{"idx": 1, "item_code": "MOTOR", "sales_order": "SO-SECRET"}],
        }
        frappe_stub.get_list = lambda doctype, filters=None, pluck=None, **kwargs: [] if doctype == "Sales Order" else filters["name"][1]

        result = source_chain.get_upstream_source_chain(document)

        sales_stage = next(stage for stage in result["groups"][0]["stages"] if stage["doctype"] == "Sales Order")
        self.assertTrue(sales_stage["restricted"])
        self.assertEqual(sales_stage["documents"], [{"name": "SO-SECRET"}])

    def test_read_permission_error_marks_source_restricted(self):
        document = {
            "doctype": "Material Request",
            "name": "MR-1",
            "items": [{"idx": 1, "item_code": "MOTOR", "sales_order": "SO-SECRET"}],
        }
        frappe_stub.get_list = lambda doctype, **kwargs: (_ for _ in ()).throw(PermissionError())

        result = source_chain.get_upstream_source_chain(document)

        sales_stage = next(stage for stage in result["groups"][0]["stages"] if stage["doctype"] == "Sales Order")
        self.assertTrue(sales_stage["restricted"])
        self.assertEqual(sales_stage["documents"], [{"name": "SO-SECRET"}])

    def test_setup_creates_read_only_html_sections_for_all_procurement_forms(self):
        created = {}

        with patch.object(source_chain, "create_custom_fields", side_effect=lambda fields, **kwargs: created.update(fields)):
            source_chain.ensure_source_chain_fields()

        self.assertEqual(set(created), set(source_chain.SUPPORTED_DOCTYPES))
        for fields in created.values():
            self.assertEqual(fields[0]["fieldname"], "custom_upstream_source_chain_section")
            self.assertEqual(fields[1]["fieldname"], "custom_upstream_source_chain_html")
            self.assertEqual(fields[1]["fieldtype"], "HTML")
            self.assertEqual(fields[1]["print_hide"], 1)

    def test_hooks_and_client_script_are_wired_for_all_forms(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "procurement_source_chain_20260726a.js").read_text()

        self.assertIn("orderlift.orderlift_logistics.source_chain.after_migrate", hooks)
        self.assertEqual(hooks.count("procurement_source_chain_20260726a.js"), 4)
        for token in [
            "get_upstream_source_chain",
            "Material Request",
            "Purchase Order",
            "Purchase Receipt",
            "Purchase Invoice",
            "You do not have access to this document",
        ]:
            self.assertIn(token, script)
        self.assertNotIn('set_value("project"', script)
        self.assertNotIn('set_value("cost_center"', script)


if __name__ == "__main__":
    unittest.main()
