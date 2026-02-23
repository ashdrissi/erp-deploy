import unittest

from orderlift.sales.utils.pricing_projection import apply_expenses


class TestPricingProjection(unittest.TestCase):
    def test_percentage_and_fixed_sequence(self):
        result = apply_expenses(
            base_unit=100,
            qty=2,
            expenses=[
                {"label": "Freight", "type": "Percentage", "value": 10, "applies_to": "Base Price", "sequence": 10},
                {"label": "Margin", "type": "Percentage", "value": 10, "applies_to": "Running Total", "sequence": 20},
                {"label": "Handling", "type": "Fixed", "value": 5, "scope": "Per Unit", "sequence": 30},
            ],
        )
        self.assertAlmostEqual(result["projected_unit"], 126.0, places=4)
        self.assertAlmostEqual(result["projected_line"], 252.0, places=4)

    def test_fixed_per_line_and_per_sheet(self):
        result = apply_expenses(
            base_unit=50,
            qty=4,
            expenses=[
                {"label": "Line fee", "type": "Fixed", "value": 20, "scope": "Per Line", "sequence": 10},
                {"label": "Sheet fee", "type": "Fixed", "value": 100, "scope": "Per Sheet", "sequence": 20},
            ],
        )
        self.assertAlmostEqual(result["projected_unit"], 55.0, places=4)
        self.assertAlmostEqual(result["projected_line"], 240.0, places=4)
        self.assertAlmostEqual(result["sheet_fixed_total"], 100.0, places=4)

    def test_negative_percentage_discount(self):
        result = apply_expenses(
            base_unit=200,
            qty=1,
            expenses=[
                {"label": "Discount", "type": "Percentage", "value": -15, "applies_to": "Running Total", "sequence": 10}
            ],
        )
        self.assertAlmostEqual(result["projected_unit"], 170.0, places=4)

    def test_override_metadata_propagates_in_steps(self):
        result = apply_expenses(
            base_unit=100,
            qty=1,
            expenses=[
                {
                    "label": "Margin",
                    "type": "Percentage",
                    "value": 20,
                    "applies_to": "Running Total",
                    "sequence": 10,
                    "expense_key": "10|margin|percentage|running total|per unit",
                    "is_overridden": 1,
                    "override_source": "line",
                }
            ],
        )
        self.assertEqual(result["steps"][0].get("is_overridden"), 1)
        self.assertEqual(
            result["steps"][0].get("expense_key"),
            "10|margin|percentage|running total|per unit",
        )
        self.assertEqual(result["steps"][0].get("override_source"), "line")


if __name__ == "__main__":
    unittest.main()
