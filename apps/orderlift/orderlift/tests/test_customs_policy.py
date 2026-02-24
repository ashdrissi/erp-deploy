import unittest

from orderlift.sales.utils.customs_policy import compute_customs_amount, resolve_customs_rule


class TestCustomsPolicyResolver(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
