import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestLogisticsQuantityOnly(unittest.TestCase):
    def test_quantity_only_guard_is_wired_for_logistics_documents(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        for doctype in ("Purchase Receipt", "Delivery Note", "Pick List"):
            self.assertIn(f'"{doctype}"', hooks)
        self.assertGreaterEqual(hooks.count("logistics_quantity_only_20260804a.js"), 3)

    def test_guard_hides_parent_and_child_price_fields_for_every_user(self):
        script = (APP_ROOT / "public" / "js" / "logistics_quantity_only_20260804a.js").read_text()

        for token in (
            'const DOCTYPES = ["Purchase Receipt", "Delivery Note", "Pick List"]',
            '"buying_price_list"',
            '"selling_price_list"',
            '"grand_total"',
            '"taxes"',
            '"rate"',
            '"amount"',
            '"custom_pu_ttc"',
            '"custom_pt_ttc"',
            'grid.update_docfield_property(fieldname, "hidden", 1)',
            'grid.update_docfield_property(fieldname, "in_list_view", 0)',
        ):
            self.assertIn(token, script)
        self.assertNotIn("orderlift_capabilities", script)
        self.assertNotIn("frappe.user.has_role", script)
        self.assertIn("__orderliftLogisticsQuantityOnly20260804aRegistered", script)

    def test_logistics_prints_force_quantity_only_for_movement_documents(self):
        purchase = (APP_ROOT / "print_formats" / "orderlift_purchase_document.html").read_text()
        purchase_tr = (APP_ROOT / "print_formats" / "orderlift_purchase_document_tr.html").read_text()
        sales = (APP_ROOT / "print_formats" / "orderlift_sales_document.html").read_text()
        sales_tr = (APP_ROOT / "print_formats" / "orderlift_sales_document_tr.html").read_text()

        self.assertIn("ol_hide_price_columns_bool = is_purchase_receipt or", purchase)
        self.assertIn("ol_hide_price_columns_bool = is_purchase_receipt", purchase_tr)
        self.assertIn("ol_hide_price_columns_bool = is_delivery_note or", sales)
        self.assertIn("ol_hide_price_columns_bool = is_delivery_note", sales_tr)
        for template in (purchase, purchase_tr, sales, sales_tr):
            self.assertIn("if not ol_hide_price_columns_bool", template)


if __name__ == "__main__":
    unittest.main()
