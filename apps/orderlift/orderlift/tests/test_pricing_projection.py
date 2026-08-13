import unittest

from orderlift.sales.utils.pricing_projection import (
    apply_discount_and_commission,
    apply_expenses,
    calculate_agent_commission,
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

    def test_fixed_per_sheet_can_be_included_in_projected_totals(self):
        result = apply_expenses(
            base_unit=50,
            qty=4,
            expenses=[
                {"label": "Line fee", "type": "Fixed", "value": 20, "scope": "Per Line", "sequence": 10},
                {"label": "Sheet fee", "type": "Fixed", "value": 100, "scope": "Per Sheet", "sequence": 20},
            ],
            include_sheet_fixed=True,
        )

        self.assertAlmostEqual(result["projected_unit"], 80.0, places=4)
        self.assertAlmostEqual(result["projected_line"], 320.0, places=4)
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

    def test_discount_and_commission_use_unused_allowed_discount(self):
        result = apply_discount_and_commission(
            gross_unit_price=1000,
            qty=1,
            discount_percent=4,
            max_discount_percent=10,
            commission_rate=20,
        )
        self.assertAlmostEqual(result["discount_amount_per_unit"], 40, places=4)
        self.assertAlmostEqual(result["discounted_unit_price"], 960, places=4)
        self.assertAlmostEqual(result["unused_discount_percent"], 6, places=4)
        self.assertAlmostEqual(result["commission_base_amount"], 57.6, places=4)
        self.assertAlmostEqual(result["commission_amount"], 11.52, places=4)

    def test_discount_amount_is_per_unit_and_preserves_nine_decimal_precision(self):
        result = apply_discount_and_commission(
            gross_unit_price=123.123456789,
            qty=7,
            discount_percent=10,
            max_discount_percent=10,
            commission_rate=5,
        )

        self.assertAlmostEqual(result["discount_amount_per_unit"], 12.3123456789, places=9)
        self.assertAlmostEqual(result["discounted_unit_price"], 110.8111111101, places=9)

    def test_discount_and_commission_is_zero_when_full_discount_is_used(self):
        result = apply_discount_and_commission(
            gross_unit_price=1000,
            qty=1,
            discount_percent=10,
            max_discount_percent=10,
            commission_rate=20,
        )
        self.assertAlmostEqual(result["commission_amount"], 0, places=4)

    def test_agent_commission_has_no_uplift_when_manual_price_is_below_list(self):
        result = calculate_agent_commission(
            price_list_unit_price=100,
            actual_unit_price=95,
            qty=10,
            max_discount_percent=10,
            commission_rate=5,
        )

        self.assertAlmostEqual(result["discount_percent"], 5, places=4)
        self.assertAlmostEqual(result["base_commission_amount"], 2.375, places=4)
        self.assertAlmostEqual(result["uplift_commission_amount"], 0, places=4)
        self.assertAlmostEqual(result["commission_amount"], 2.375, places=4)

    def test_agent_commission_above_list_has_zero_discount_and_no_uplift(self):
        result = calculate_agent_commission(
            price_list_unit_price=100,
            actual_unit_price=110,
            qty=10,
            max_discount_percent=10,
            commission_rate=5,
        )

        self.assertAlmostEqual(result["discount_percent"], 0, places=4)
        self.assertAlmostEqual(result["commission_base_amount"], 110, places=4)
        self.assertAlmostEqual(result["base_commission_amount"], 5.5, places=4)
        self.assertAlmostEqual(result["uplift_commission_amount"], 0, places=4)
        self.assertAlmostEqual(result["commission_amount"], 5.5, places=4)

    def test_agent_commission_at_list_has_zero_discount(self):
        result = calculate_agent_commission(
            price_list_unit_price=100.123456789,
            actual_unit_price=100.123456789,
            qty=2,
            max_discount_percent=10,
            commission_rate=5,
        )

        self.assertEqual(result["discount_percent"], 0)
        self.assertAlmostEqual(result["commission_amount"], 1.00123456789, places=9)

    def test_agent_commission_preserves_nine_decimal_precision(self):
        price_list_unit_price = 100.123456789
        actual_unit_price = 95.987654321
        qty = 3.333333333
        max_discount_percent = 8.765432109
        commission_rate = 6.543210987
        used_discount_percent = max(
            ((price_list_unit_price - actual_unit_price) / price_list_unit_price) * 100,
            0,
        )
        expected_base = (
            actual_unit_price
            * qty
            * max(max_discount_percent - used_discount_percent, 0)
            / 100
        )
        expected_commission = expected_base * commission_rate / 100

        result = calculate_agent_commission(
            price_list_unit_price=price_list_unit_price,
            actual_unit_price=actual_unit_price,
            qty=qty,
            max_discount_percent=max_discount_percent,
            commission_rate=commission_rate,
        )

        self.assertAlmostEqual(result["discount_percent"], used_discount_percent, places=9)
        self.assertAlmostEqual(result["commission_base_amount"], expected_base, places=9)
        self.assertAlmostEqual(result["commission_amount"], expected_commission, places=9)

    def test_manual_above_list_without_discount_uses_actual_price_commission_base(self):
        result = apply_discount_and_commission(
            gross_unit_price=15034.98,
            discount_base_unit_price=20000,
            actual_unit_price=20000,
            qty=2,
            discount_percent=0,
            max_discount_percent=10,
            commission_rate=20,
        )

        self.assertAlmostEqual(result["discount_percent"], 0, places=4)
        self.assertAlmostEqual(result["discount_amount_per_unit"], 0, places=4)
        self.assertAlmostEqual(result["discounted_total"], 40000, places=4)
        self.assertAlmostEqual(result["uplift_commission_amount"], 0, places=4)
        self.assertAlmostEqual(result["commission_amount"], 800, places=4)

    def test_manual_above_list_with_discount_uses_per_unit_discount_and_actual_price(self):
        result = apply_discount_and_commission(
            gross_unit_price=15034.98,
            discount_base_unit_price=20000,
            actual_unit_price=19000,
            qty=2,
            discount_percent=5,
            max_discount_percent=10,
            commission_rate=20,
        )

        self.assertAlmostEqual(result["discount_percent"], 5, places=4)
        self.assertAlmostEqual(result["discount_amount_per_unit"], 1000, places=4)
        self.assertAlmostEqual(result["discounted_total"], 38000, places=4)
        self.assertAlmostEqual(result["uplift_commission_amount"], 0, places=4)
        self.assertAlmostEqual(result["commission_amount"], 380, places=4)

    def test_agent_commission_rejects_actual_price_below_discount_floor(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed 10.0%"):
            calculate_agent_commission(
                price_list_unit_price=100,
                actual_unit_price=89,
                qty=1,
                max_discount_percent=10,
                commission_rate=5,
            )

    def test_agent_commission_override_below_floor_has_no_commission(self):
        result = calculate_agent_commission(
            price_list_unit_price=100,
            actual_unit_price=89,
            qty=1,
            max_discount_percent=10,
            commission_rate=5,
            enforce_discount_cap=False,
        )

        self.assertAlmostEqual(result["base_commission_amount"], 0, places=4)
        self.assertAlmostEqual(result["uplift_commission_amount"], 0, places=4)
        self.assertAlmostEqual(result["commission_amount"], 0, places=4)

    def test_discount_rejects_values_above_allowed_max(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed 5.0%"):
            apply_discount_and_commission(
                gross_unit_price=132,
                qty=1,
                discount_percent=6,
                max_discount_percent=5,
                commission_rate=20,
            )

    def test_max_discount_uses_rule_when_not_fallback(self):
        self.assertEqual(
            resolve_max_discount_cap(
                rule_max_discount_percent=7,
                fallback_max_discount_percent=4,
                agent_max_discount_percent=12,
                is_fallback=False,
            ),
            7,
        )

    def test_max_discount_uses_fallback_cap_and_ignores_agent_cap(self):
        self.assertEqual(
            resolve_max_discount_cap(
                rule_max_discount_percent=0,
                fallback_max_discount_percent=6,
                agent_max_discount_percent=4,
                is_fallback=True,
            ),
            6,
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
