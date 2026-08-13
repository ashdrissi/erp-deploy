import importlib.util
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from orderlift.tests.test_print_payment_terms import _load_jinja_helpers


APP_ROOT = Path(__file__).resolve().parents[1]
MOROCCO_COMPANIES = {
    "Orderlift Maroc Distribution",
    "Orderlift Maroc Installation",
}
REQUESTED_DOCTYPES = {
    "Quotation",
    "Sales Order",
    "Delivery Note",
    "Sales Invoice",
    "Purchase Order",
    "Purchase Invoice",
}


def _load_print_format_updater():
    fake_frappe = types.ModuleType("frappe")
    module_name = "orderlift_test_update_pf"
    spec = importlib.util.spec_from_file_location(module_name, APP_ROOT / "scripts" / "update_pf.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"frappe": fake_frappe}):
        spec.loader.exec_module(module)
    return module


class TestPrintFormatBranding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = _load_jinja_helpers()
        cls.updater = _load_print_format_updater()
        cls.templates = {
            name: (APP_ROOT / "print_formats" / name).read_text()
            for name in (
                "orderlift_quotation.html",
                "orderlift_sales_document.html",
                "orderlift_purchase_document.html",
            )
        }

    def test_morocco_legal_footer_details_are_exact_and_company_scoped(self):
        self.helpers.frappe.db.get_value = lambda *_args, **_kwargs: {
            "company_name": "Database Company",
            "email": "database@example.com",
            "tax_id": "DB-TAX",
            "default_currency": "MAD",
        }

        for company in MOROCCO_COMPANIES:
            info = self.helpers.get_company_info(company)
            self.assertEqual(info["legal_name"], "ORDER LIFT MOROCCO")
            self.assertEqual(
                info["legal_address"],
                "Tanja Balia lots méditerrané 475 rue plage Essalam Nr 15 Tanger, Maroc",
            )
            self.assertEqual(
                info["bank_line"],
                "Attijariwafa Banque - Agence : D.A.M Tanger Tarik Ibn Ziad - "
                "RIB : 007 640 0001735000002530 41",
            )
            self.assertEqual(info["registration_number"], "162443")
            self.assertEqual(info["tax_id"], "003698266000073")
            self.assertEqual(info["email"], "info@orderlift.net")

        generic = self.helpers.get_company_info("Orderlift")
        self.assertEqual(generic["legal_name"], "")
        self.assertEqual(generic["bank_line"], "")
        self.assertEqual(generic["email"], "database@example.com")

    def test_templates_render_complete_footer_and_unlabeled_morocco_stamp(self):
        for html in self.templates.values():
            self.assertIn("ol_is_morocco_company", html)
            self.assertIn("co.legal_name", html)
            self.assertIn("co.legal_address", html)
            self.assertIn("co.bank_line", html)
            self.assertIn("co.registration_number", html)
            self.assertIn("/assets/orderlift/images/orderlift_morocco_stamp.png", html)
            self.assertIn("ol-sig-placeholder-morocco", html)
            self.assertIn("if not ol_is_morocco_company", html)
            self.assertIn("not (ol_is_morocco_company and ol_without_details_bool)", html)
            self.assertIn("ol_hide_price_columns_bool", html)
            self.assertGreaterEqual(html.count("if not ol_hide_price_columns_bool"), 2)
            self.assertIn("MAX_FIRST_TOTALS = 3 if ol_is_morocco_company else 4", html)
            self.assertIn("MAX_FIRST = 7", html)
            self.assertIn(
                "MAX_NORMAL = (10 if ol_hide_price_columns_bool else 9) if ol_is_morocco_company else 11",
                html,
            )
            self.assertIn("MAX_LAST = 3 if ol_is_morocco_company else 4", html)
            self.assertIn("first_page_count = total_items - 1", html)

    def test_invoice_and_delivery_dates_use_posting_date(self):
        sales = self.templates["orderlift_sales_document.html"]
        purchase = self.templates["orderlift_purchase_document.html"]

        self.assertIn(
            "doc.posting_date if (is_delivery_note or is_sales_invoice) else doc.transaction_date",
            sales,
        )
        self.assertIn(
            "doc.posting_date if (is_purchase_invoice or is_purchase_receipt) else doc.transaction_date",
            purchase,
        )
        self.assertIn('frappe.utils.formatdate(primary_date)', sales)
        self.assertIn('frappe.utils.formatdate(primary_date)', purchase)
        self.assertIn("doc.delivery_date != primary_date", sales)
        self.assertIn("doc.due_date != primary_date", sales)
        self.assertIn("doc.schedule_date != primary_date", purchase)
        self.assertIn("doc.due_date != primary_date", purchase)
        self.assertIn("if not ol_is_morocco_company", sales)
        self.assertIn("if not ol_is_morocco_company", purchase)

    def test_scoped_updater_selects_exactly_144_print_formats(self):
        companies = self.updater._filter_configs(
            self.updater._COMPANIES,
            "name",
            MOROCCO_COMPANIES,
            "company",
        )
        doctypes = self.updater._filter_configs(
            self.updater._DOC_CONFIG,
            "doc_type",
            REQUESTED_DOCTYPES,
            "doctype",
        )

        self.assertEqual({row["name"] for row in companies}, MOROCCO_COMPANIES)
        self.assertEqual({row["doc_type"] for row in doctypes}, REQUESTED_DOCTYPES)
        format_count = sum(
            len(self.updater._modes_for_company(company, config["doc_type"]))
            for company in companies
            for config in doctypes
        )
        self.assertEqual(format_count, 144)
        self.assertEqual(
            {mode[0] for mode in self.updater._MOROCCO_ONLY_MODES},
            {
                "PU HT Without Prices",
                "PU TTC Without Prices",
                "Prix Unitaire Without Prices",
            },
        )

        generic = next(row for row in self.updater._COMPANIES if row["name"] == "Orderlift")
        morocco = next(
            row for row in self.updater._COMPANIES
            if row["name"] == "Orderlift Maroc Distribution"
        )
        self.assertEqual(self.updater._modes_for_company(generic, "Quotation"), self.updater._MODES)
        self.assertEqual(
            self.updater._modes_for_company(morocco, "Purchase Receipt"),
            self.updater._MODES,
        )
        self.assertEqual(
            len(self.updater._modes_for_company(morocco, "Quotation")),
            12,
        )
        self.assertEqual(
            self.updater._normalize_filter("Quotation, Sales Invoice"),
            {"Quotation", "Sales Invoice"},
        )
        with self.assertRaisesRegex(ValueError, "Unknown print format company"):
            self.updater._filter_configs(self.updater._COMPANIES, "name", {"Unknown"}, "company")

    def test_without_prices_mode_hides_line_prices_but_keeps_mode_totals(self):
        rendered = self.updater._prepend_variables(
            self.templates["orderlift_quotation.html"],
            "HT",
            "true",
            "true",
            hide_price_columns=True,
        )

        self.assertIn("{% set orderlift_hide_price_columns = true %}", rendered)
        self.assertIn("if not ol_hide_price_columns_bool", rendered)
        self.assertIn("render_totals_and_signatures()", rendered)
        self.assertIn('_("Total HT")', rendered)
        self.assertIn('_("TOTAL TTC")', rendered)

    def test_stamp_asset_has_complete_pdf_extraction_dimensions(self):
        asset = APP_ROOT / "public" / "images" / "orderlift_morocco_stamp.png"
        with asset.open("rb") as handle:
            header = handle.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (502, 298))


if __name__ == "__main__":
    unittest.main()
