import sys
import types
import unittest
from pathlib import Path


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.has_permission = lambda *args, **kwargs: True
frappe_stub.get_all = lambda *args, **kwargs: []
frappe_stub.db = types.SimpleNamespace(
    exists=lambda doctype, name=None: name == "Nos",
    get_value=lambda *args, **kwargs: "Nos" if args and args[0] == "UOM" else 0,
)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
sys.modules["frappe.utils"] = utils_stub

account_governance_stub = types.ModuleType("orderlift.orderlift_finance.account_governance")
account_governance_stub.get_company_account_map = lambda company, create_missing=False: {"sales_revenue": "Sales - OMI"}
account_governance_stub.get_company_cost_center = lambda company, create_missing=False: "Main - OMI"
sys.modules["orderlift.orderlift_finance.account_governance"] = account_governance_stub

from orderlift.orderlift_sales import sales_invoice_modes


APP_ROOT = Path(__file__).resolve().parents[1]


class DocStub(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get("name", "NEW-SINV")

    def get(self, key, default=None):
        return super().get(key, default)


class TestSalesInvoiceModes(unittest.TestCase):
    def setUp(self):
        self.original_get_all = sales_invoice_modes.frappe.get_all
        self.original_db = sales_invoice_modes.frappe.db
        self.original_tax_rate = sales_invoice_modes.sales_tax_template_total_rate

    def tearDown(self):
        sales_invoice_modes.frappe.get_all = self.original_get_all
        sales_invoice_modes.frappe.db = self.original_db
        sales_invoice_modes.sales_tax_template_total_rate = self.original_tax_rate

    def test_build_custom_invoice_payload_creates_text_only_row(self):
        payload = sales_invoice_modes.build_custom_invoice_payload(
            "Mesure spéciale",
            1200,
            "Sales - OMI",
            description="Custom work",
            cost_center="Main - OMI",
            uom="Nos",
        )

        self.assertEqual(payload["header"]["custom_invoice_mode"], "Custom")
        self.assertEqual(payload["row"]["item_code"], "")
        self.assertEqual(payload["row"]["item_name"], "Mesure spéciale")
        self.assertEqual(payload["row"]["rate"], 1200)
        self.assertEqual(payload["row"]["uom"], "Nos")
        self.assertEqual(payload["row"]["income_account"], "Sales - OMI")

    def test_build_advance_invoice_payload_converts_ttc_to_ht_from_tax_template(self):
        sales_invoice_modes.sales_tax_template_total_rate = lambda template: 20 if template == "VAT 20" else 0
        option = {"available_amount": 1200, "payment_entry": "PE-001", "designation": "Acompte"}

        payload = sales_invoice_modes.build_advance_invoice_payload(
            option,
            amount=1200,
            income_account="Sales - OMI",
            uom="Nos",
            taxes_and_charges="VAT 20",
        )

        self.assertAlmostEqual(payload["row"]["rate"], 1000)
        self.assertAlmostEqual(payload["row"]["amount"], 1000)
        self.assertAlmostEqual(payload["row"]["custom_pt_ttc"], 1200)
        self.assertAlmostEqual(payload["row"]["custom_applied_taxes"], 200)
        self.assertEqual(payload["row"]["uom"], "Nos")

    def test_build_advance_payload_caps_available_amount(self):
        option = {"available_amount": 500, "payment_entry": "PE-001", "designation": "Acompte"}

        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            sales_invoice_modes.build_advance_invoice_payload(option, amount=600, income_account="Sales - OMI")

    def test_validate_advance_invoice_rejects_item_coded_rows(self):
        doc = DocStub(
            custom_invoice_mode="Advance",
            custom_advance_payment_entry="PE-001",
            items=[{"item_code": "ITEM-001", "item_name": "Item", "amount": 10, "income_account": "Sales - OMI"}],
        )

        with self.assertRaisesRegex(ValueError, "text-only"):
            sales_invoice_modes.validate_invoice_mode(doc)

    def test_validate_custom_invoice_requires_income_account(self):
        doc = DocStub(
            custom_invoice_mode="Custom",
            items=[{"item_code": "", "item_name": "Custom", "amount": 10, "uom": "Nos", "income_account": ""}],
        )

        with self.assertRaisesRegex(ValueError, "Income Account"):
            sales_invoice_modes.validate_invoice_mode(doc)

    def test_sales_invoice_mode_script_is_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "sales_invoice_mode_20260812c.js").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()

        self.assertIn("sales_invoice_mode_20260812c.js", hooks)
        for label in ["Invoice Based on Items", "Invoice Based on Advance", "Custom Invoice"]:
            self.assertIn(label, script)
        self.assertIn('data-ol-si-mode="items"', script)
        self.assertIn('data-ol-si-mode="advance"', script)
        self.assertIn('data-ol-si-mode="custom"', script)
        self.assertIn("function hideStockFields(frm)", script)
        self.assertIn('"update_stock"', script)
        self.assertIn('label: __("Amount TTC")', script)
        self.assertIn('fieldname: "uom"', script)
        self.assertIn("taxes_and_charges: frm.doc.taxes_and_charges", script)
        for fieldname in [
            "custom_invoice_mode",
            "custom_advance_payment_entry",
            "custom_advance_sales_order",
            "custom_advance_payment_schedule_row",
        ]:
            self.assertIn(f'"fieldname": "{fieldname}"', pricing_setup)
        self.assertIn("orderlift.orderlift_sales.sales_invoice_modes.validate_invoice_mode", hooks)


if __name__ == "__main__":
    unittest.main()
