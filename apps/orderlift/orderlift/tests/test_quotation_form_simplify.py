from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestQuotationFormSimplify(unittest.TestCase):
    def test_quotation_form_simplifier_is_wired_and_hides_native_discount_tax_fields(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260602c.js").read_text()

        self.assertIn('"Quotation": "public/js/quotation_form_simplify_20260602c.js', hooks)
        self.assertIn("v=20260602c", hooks)
        for fieldname in [
            "additional_discount_section",
            "apply_discount_on",
            "coupon_code",
            "additional_discount_percentage",
            "discount_amount",
            "referral_sales_partner",
            "taxes_section",
            "taxes_and_charges_calculation",
            "other_charges_calculation",
            "tax_breakup",
        ]:
            self.assertIn(fieldname, script)

    def test_quotation_form_has_bulk_quantity_action_for_selected_items(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260602c.js").read_text()

        for token in [
            "Bulk Quantity",
            "addBulkQuantityGridButton",
            "grid.add_custom_button",
            ".grid-add-multiple-rows",
            "data-orderlift-bulk-quantity",
            "getSelectedItemRows",
            "get_selected_children",
            "Apply Quantity to Selected Items",
            'frappe.model.set_value(row.doctype, row.name, "qty", qty)',
            'frm.refresh_field("items")',
        ]:
            self.assertIn(token, script)

    def test_global_bulk_quantity_watcher_is_wired_for_current_desk_shell(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_bulk_quantity_20260602a.js").read_text()

        self.assertIn("quotation_bulk_quantity_20260602a.js?v=20260602a", hooks)
        for token in [
            "data-orderlift-quotation-bulk-quantity",
            ".grid-add-multiple-rows",
            "window.cur_frm",
            "frm.doctype !== \"Quotation\"",
            "setInterval(attachBulkQuantityButton, 1000)",
            "frappe.model.set_value(row.doctype, row.name, \"qty\", qty)",
        ]:
            self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
