import unittest

from orderlift.sales.utils.customs_policy import compute_customs_amount, resolve_customs_rule


class TestCustomsPolicyResolver(unittest.TestCase):
    def test_exact_tariff_number_wins_over_legacy_material(self):
        rules = [
            {"material": "STEEL", "rate_per_kg": 7, "rate_percent": 20, "priority": 10, "sequence": 90, "is_active": 1},
            {
                "tariff_number": "213123",
                "value_per_kg": 13,
                "rate_components": "20 + 0.25 + 5",
                "priority": 10,
                "sequence": 10,
                "is_active": 1,
            },
        ]
        rule = resolve_customs_rule(rules, tariff_number="213123", material="STEEL")
        self.assertEqual(rule["tariff_number"], "213123")

    def test_tariff_and_material_wins_over_tariff_only(self):
        rules = [
            {"tariff_number": "213123", "value_per_kg": 13, "priority": 10, "sequence": 20, "is_active": 1},
            {
                "tariff_number": "213123",
                "material": "PLASTIQUE",
                "value_per_kg": 33,
                "priority": 10,
                "sequence": 10,
                "is_active": 1,
            },
        ]
        rule = resolve_customs_rule(rules, tariff_number="213123", material="PLASTIQUE")
        self.assertEqual(rule["value_per_kg"], 33)

    def test_tariff_material_rule_does_not_match_different_material(self):
        rules = [
            {"tariff_number": "213123", "material": "ACIER", "value_per_kg": 13, "is_active": 1},
            {"tariff_number": "213123", "material": "PLASTIQUE", "value_per_kg": 33, "is_active": 1},
        ]
        rule = resolve_customs_rule(rules, tariff_number="213123", material="CUIVRE")
        self.assertIsNone(rule)

    def test_blank_rule_fallback_used_for_tariff_number(self):
        rules = [
            {"tariff_number": "", "value_per_kg": 9, "rate_components": "20 + 5", "priority": 10, "sequence": 90, "is_active": 1},
            {"tariff_number": "999999", "value_per_kg": 13, "rate_components": "25", "priority": 10, "sequence": 10, "is_active": 1},
        ]
        rule = resolve_customs_rule(rules, tariff_number="213123")
        self.assertEqual(rule["value_per_kg"], 9)

    def test_exact_material_wins_over_fallback(self):
        rules = [
            {"material": "", "rate_per_kg": 1, "rate_percent": 3, "priority": 10, "sequence": 90, "is_active": 1},
            {
                "material": "STEEL",
                "rate_per_kg": 7,
                "rate_percent": 20,
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
        ]
        rule = resolve_customs_rule(rules, material="STEEL")
        self.assertEqual(rule["rate_per_kg"], 7)

    def test_fallback_used_when_no_material_match(self):
        rules = [
            {"material": "", "rate_per_kg": 2, "rate_percent": 5, "priority": 10, "sequence": 90, "is_active": 1},
            {
                "material": "ALUM",
                "rate_per_kg": 4,
                "rate_percent": 8,
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
        ]
        rule = resolve_customs_rule(rules, material="INOX")
        self.assertEqual(rule["rate_per_kg"], 2)

    def test_legacy_steel_material_matches_acier_rule(self):
        rules = [
            {"tariff_number": "7308909000", "material": "ACIER", "value_per_kg": 13, "is_active": 1},
        ]
        rule = resolve_customs_rule(rules, tariff_number="7308909000", material="STEEL")
        self.assertEqual(rule["value_per_kg"], 13)

    def test_carte_material_matches_acier_carte_rule(self):
        rules = [
            {"tariff_number": "8534000000", "material": "ACIER (CARTE)", "value_per_kg": 50, "is_active": 1},
        ]
        rule = resolve_customs_rule(rules, tariff_number="8534000000", material="CARTE")
        self.assertEqual(rule["value_per_kg"], 50)

    def test_priority_break_tie(self):
        rules = [
            {"material": "STEEL", "rate_per_kg": 7, "rate_percent": 20, "priority": 20, "sequence": 90, "is_active": 1},
            {"material": "STEEL", "rate_per_kg": 9, "rate_percent": 10, "priority": 5, "sequence": 90, "is_active": 1},
        ]
        rule = resolve_customs_rule(rules, material="STEEL")
        self.assertEqual(rule["rate_per_kg"], 9)

    def test_compute_customs_uses_customs_material_value_weight_and_percent(self):
        calc = compute_customs_amount(
            base_amount=6000,
            qty=3,
            unit_weight_kg=50,
            rate_per_kg=7,
            rate_percent=20,
            value_per_kg=13,
        )
        self.assertEqual(calc["mode"], "customs_material")
        self.assertEqual(calc["base_value"], 1950)
        self.assertEqual(calc["by_kg"], 0.0)
        self.assertEqual(calc["by_percent"], 390)
        self.assertEqual(calc["applied"], 390)
        self.assertEqual(calc["basis"], "Value Per Kg x Weight x Rate Percent")

    def test_compute_customs_converts_legacy_component_percentages(self):
        calc = compute_customs_amount(
            base_amount=0,
            qty=100,
            unit_weight_kg=2,
            value_per_kg=13,
            rate_components="20 + 0.25 + 5",
        )
        self.assertEqual(calc["mode"], "customs_material")
        self.assertEqual(calc["base_value"], 2600)
        self.assertEqual(calc["total_percent"], 25.25)
        self.assertEqual(calc["applied"], 656.5)
        self.assertEqual(calc["basis"], "Value Per Kg x Weight x Rate Percent")

    def test_compute_customs_can_fallback_to_buying_amount_when_weight_missing(self):
        calc = compute_customs_amount(
            base_amount=1000,
            qty=1,
            unit_weight_kg=0,
            value_per_kg=13,
            rate_components="20 + 5",
            base_amount_fallback=True,
        )

        self.assertEqual(calc["mode"], "buying_amount_fallback")
        self.assertEqual(calc["base_value"], 1000)
        self.assertEqual(calc["total_percent"], 25)
        self.assertEqual(calc["applied"], 250)
        self.assertEqual(calc["basis"], "Buying Amount x Rate Percent (Weight Fallback)")


if __name__ == "__main__":
    unittest.main()
