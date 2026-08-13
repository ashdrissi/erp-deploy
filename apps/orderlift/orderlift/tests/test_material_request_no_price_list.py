import unittest
from pathlib import Path

from orderlift.orderlift_logistics.utils.material_request import clear_price_list_link


APP_ROOT = Path(__file__).resolve().parents[1]


class MetaStub:
    def __init__(self, fields):
        self.fields = set(fields)

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


class DocStub(dict):
    def __init__(self, fields=(), **values):
        super().__init__(**values)
        self.meta = MetaStub(fields)

    def set(self, fieldname, value):
        self[fieldname] = value


class TestMaterialRequestNoPriceList(unittest.TestCase):
    def test_price_list_values_are_cleared(self):
        row = DocStub(fields={"price_list_rate"}, item_code="AEC-00095", qty=56, price_list_rate=125)
        doc = DocStub(fields={"buying_price_list"}, buying_price_list="Standard Buying", items=[row])

        clear_price_list_link(doc)

        self.assertEqual(doc["buying_price_list"], "")
        self.assertEqual(row["price_list_rate"], 0)
        self.assertEqual(row["qty"], 56)

    def test_hook_and_hidden_fields_are_configured(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        setup = (APP_ROOT / "logistics" / "setup.py").read_text()

        self.assertIn('"Material Request": {', hooks)
        self.assertIn("material_request.clear_price_list_link", hooks)
        self.assertIn("def enforce_material_request_without_price_list", setup)
        self.assertIn('"Material Request", "buying_price_list", "hidden", "1"', setup)
        self.assertIn('"Material Request Item", "price_list_rate", "hidden", "1"', setup)
        self.assertIn("def repair_stale_global_buying_price_list", setup)
        self.assertIn('frappe.defaults.set_global_default("buying_price_list", replacement)', setup)
        self.assertIn("def clear_draft_material_request_price_lists", setup)
        self.assertIn('"buying_price_list": ["!=", ""]', setup)

    def test_list_action_maps_many_material_requests_to_one_purchase_order(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        utility = (APP_ROOT / "orderlift_logistics" / "utils" / "material_request.py").read_text()
        list_js = (APP_ROOT / "public" / "js" / "material_request_list_make_po_20260805a.js").read_text()

        self.assertIn('"Material Request": "public/js/material_request_list_make_po_20260805a.js"', hooks)
        for token in [
            "get_material_request_purchase_order_preview",
            "make_purchase_order_from_material_requests",
            "remaining_qty",
            '"material_request"',
            '"material_request_item"',
            'purchase_order.currency = supplier_currency',
            "_currency_rate(supplier_currency, company_currency",
        ]:
            self.assertIn(token, utility)
        for token in [
            "get_checked_items",
            "Create One Purchase Order",
            "make_purchase_order_from_material_requests",
            'frappe.set_route("Form", "Purchase Order", doc.name)',
        ]:
            self.assertIn(token, list_js)


if __name__ == "__main__":
    unittest.main()
