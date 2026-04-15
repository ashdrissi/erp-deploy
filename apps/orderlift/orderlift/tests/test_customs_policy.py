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

    def test_priority_break_tie(self):
        rules = [
            {"material": "STEEL", "rate_per_kg": 7, "rate_percent": 20, "priority": 20, "sequence": 90, "is_active": 1},
            {"material": "STEEL", "rate_per_kg": 9, "rate_percent": 10, "priority": 5, "sequence": 90, "is_active": 1},
        ]
        rule = resolve_customs_rule(rules, material="STEEL")
        self.assertEqual(rule["rate_per_kg"], 9)

    def test_compute_customs_uses_max_percent(self):
        calc = compute_customs_amount(base_amount=6000, qty=3, unit_weight_kg=50, rate_per_kg=7, rate_percent=20)
        self.assertEqual(calc["by_kg"], 1050)
        self.assertEqual(calc["by_percent"], 1200)
        self.assertEqual(calc["applied"], 1200)
        self.assertEqual(calc["basis"], "Percent")

    def test_compute_customs_uses_max_kg(self):
        calc = compute_customs_amount(base_amount=1000, qty=4, unit_weight_kg=20, rate_per_kg=5, rate_percent=10)
        self.assertEqual(calc["by_kg"], 400)
        self.assertEqual(calc["by_percent"], 100)
        self.assertEqual(calc["applied"], 400)
        self.assertEqual(calc["basis"], "Per Kg")

    def test_compute_customs_uses_tariff_value_and_component_percentages(self):
        calc = compute_customs_amount(
            base_amount=0,
            qty=100,
            unit_weight_kg=2,
            value_per_kg=13,
            rate_components="20 + 0.25 + 5",
        )
        self.assertEqual(calc["mode"], "tariff")
        self.assertEqual(calc["base_value"], 2600)
        self.assertEqual(calc["total_percent"], 25.25)
        self.assertEqual(calc["applied"], 656.5)
        self.assertEqual(calc["basis"], "Tariff Value x Percent")


if __name__ == "__main__":
    unittest.main()
