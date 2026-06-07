import unittest
from pathlib import Path

from orderlift.orderlift_sales.utils.buying_price_builder import (
    calculate_preview_rows,
    normalize_formula_rules,
)


class TestBuyingPriceBuilder(unittest.TestCase):
    def test_formula_rule_applies_different_percent_per_target(self):
        rows = calculate_preview_rows(
            [
                {"item_code": "BASE", "item_name": "Base", "list_price": 100},
                {"item_code": "TGT-10", "item_name": "Target 10", "list_price": 90},
                {"item_code": "TGT-25", "item_name": "Target 25", "list_price": 90},
            ],
            formula_rules=[
                {
                    "name": "Variant rule",
                    "source": "BASE",
                    "checked": True,
                    "targets": [
                        {"code": "TGT-10", "pct": 10},
                        {"code": "TGT-25", "pct": 25},
                    ],
                }
            ],
        )
        by_code = {row["item_code"]: row for row in rows}
        self.assertEqual(by_code["TGT-10"]["final_price"], 110)
        self.assertEqual(by_code["TGT-25"]["final_price"], 125)
        self.assertEqual(by_code["TGT-10"]["formula_rule"], "Variant rule")

    def test_fixed_percent_can_apply_to_selected_rows_only(self):
        rows = calculate_preview_rows(
            [
                {"item_code": "A", "list_price": 100},
                {"item_code": "B", "list_price": 200},
            ],
            fixed_percent={"scope": "selected", "item_codes": ["B"], "pct": 10},
        )
        by_code = {row["item_code"]: row for row in rows}
        self.assertEqual(by_code["A"]["final_price"], 100)
        self.assertEqual(by_code["B"]["final_price"], 220)

    def test_manual_price_overrides_fixed_percent(self):
        rows = calculate_preview_rows(
            [{"item_code": "A", "list_price": 100}],
            manual_prices={"A": 130},
            fixed_percent={"scope": "all", "pct": 10},
        )
        self.assertEqual(rows[0]["final_price"], 130)

    def test_normalize_formula_rules_accepts_legacy_single_target(self):
        rules = normalize_formula_rules([
            {"label": "Legacy", "source": "A", "target": "B", "pct": 7, "checked": 1}
        ])
        self.assertEqual(rules[0]["name"], "Legacy")
        self.assertEqual(rules[0]["targets"], [{"code": "B", "pct": 7.0}])

    def test_builder_page_can_select_all_available_price_lists(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "buying_price_builder"
            / "buying_price_builder.js"
        ).read_text()

        self.assertIn("select-all-price-lists", page_js)
        self.assertIn("function selectAllPriceLists", page_js)
        self.assertIn("getPriceListNames", page_js)


if __name__ == "__main__":
    unittest.main()
