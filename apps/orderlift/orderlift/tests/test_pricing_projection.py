import unittest

from orderlift.sales.utils.pricing_projection import (
    apply_discount_and_commission,
    apply_expenses,
    resolve_max_discount_cap,
)


class TestPricingProjection(unittest.TestCase):
    def test_percentage_and_fixed_sequence(self):
        result = apply_expenses(
            base_unit=100,
            qty=2,
            expenses=[
                {"label": "Freight", "type": "Percentage", "value": 10, "applies_to": "Base Price", "sequence": 10},
                {"label": "Margin", "type": "Percentage", "value": 10, "applies_to": "Base Price", "sequence": 20},
                {"label": "Handling", "type": "Fixed", "value": 5, "scope": "Per Unit", "sequence": 30},
            ],
        )
        self.assertAlmostEqual(result["projected_unit"], 125.0, places=4)
        self.assertAlmostEqual(result["projected_line"], 250.0, places=4)

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
        self.assertAlmostEqual(result["projected_line"], 220.0, places=4)
        self.assertAlmostEqual(result["sheet_fixed_total"], 100.0, places=4)

    def test_per_line_fixed_not_double_counted_for_single_qty(self):
        result = apply_expenses(
            base_unit=720,
            qty=1,
            expenses=[
                {"label": "Transport", "type": "Fixed", "value": 38.052, "scope": "Per Line", "sequence": 10},
            ],
        )
        self.assertAlmostEqual(result["projected_unit"], 758.052, places=6)
        self.assertAlmostEqual(result["projected_line"], 758.052, places=6)

    def test_negative_percentage_discount(self):
        result = apply_expenses(
            base_unit=200,
            qty=1,
            expenses=[
                {"label": "Discount", "type": "Percentage", "value": -15, "applies_to": "Base Price", "sequence": 10}
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
                    "applies_to": "Base Price",
                    "sequence": 10,
                    "expense_key": "10|margin|percentage|base price|per unit",
                    "is_overridden": 1,
                    "override_source": "line",
                }
            ],
        )
        self.assertEqual(result["steps"][0].get("is_overridden"), 1)
        self.assertEqual(
            result["steps"][0].get("expense_key"),
            "10|margin|percentage|base price|per unit",
        )
        self.assertEqual(result["steps"][0].get("override_source"), "line")

    def test_percentage_step_rejects_non_base_price_basis(self):
        with self.assertRaisesRegex(ValueError, "must apply to Base Price"):
            apply_expenses(
                base_unit=100,
                qty=1,
                expenses=[
                    {
                        "label": "Bad Loaded Cost Expense",
                        "type": "Percentage",
                        "value": 5,
                        "applies_to": "Loaded Cost",
                        "scope": "Per Unit",
                        "sequence": 10,
                    }
                ],
            )

    def test_fixed_step_allows_non_base_price_basis_for_margin_compatibility(self):
        result = apply_expenses(
            base_unit=100,
            qty=1,
            expenses=[
                {
                    "label": "Dynamic Margin (Loaded Cost)",
                    "type": "Fixed",
                    "value": 12,
                    "applies_to": "Loaded Cost",
                    "scope": "Per Unit",
                    "sequence": 90,
                }
            ],
        )
        self.assertAlmostEqual(result["projected_unit"], 112.0, places=4)
        self.assertEqual(result["steps"][0].get("applies_to"), "Loaded Cost")

    def test_discount_and_commission_apply_from_sell_price(self):
        result = apply_discount_and_commission(
            gross_unit_price=132,
            qty=1,
            discount_percent=5,
            max_discount_percent=15,
            commission_rate=20,
        )
        self.assertAlmostEqual(result["discount_amount"], 6.6, places=4)
        self.assertAlmostEqual(result["discounted_unit_price"], 125.4, places=4)
        self.assertAlmostEqual(result["commission_amount"], 1.32, places=4)

    def test_discount_rejects_values_above_allowed_max(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed 5.0%"):
            apply_discount_and_commission(
                gross_unit_price=132,
                qty=1,
                discount_percent=6,
                max_discount_percent=5,
                commission_rate=20,
            )

    def test_max_discount_uses_rule_before_agent_when_not_fallback(self):
        self.assertEqual(
            resolve_max_discount_cap(
                rule_max_discount_percent=7,
                fallback_max_discount_percent=4,
                agent_max_discount_percent=12,
                is_fallback=False,
            ),
            7,
        )

    def test_max_discount_uses_stricter_fallback_and_agent_caps(self):
        self.assertEqual(
            resolve_max_discount_cap(
                rule_max_discount_percent=0,
                fallback_max_discount_percent=6,
                agent_max_discount_percent=4,
                is_fallback=True,
            ),
            4,
        )

    def test_max_discount_uses_fallback_cap_when_agent_cap_missing(self):
        self.assertEqual(
            resolve_max_discount_cap(
                rule_max_discount_percent=0,
                fallback_max_discount_percent=6,
                agent_max_discount_percent=0,
                is_fallback=True,
            ),
            6,
        )


if __name__ == "__main__":
    unittest.main()
