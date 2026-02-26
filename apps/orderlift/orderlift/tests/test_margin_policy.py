import unittest

from orderlift.sales.utils.margin_policy import resolve_margin_rule


class TestMarginPolicyResolver(unittest.TestCase):
    def test_exact_match_wins(self):
        rules = [
            {"customer_type": "Installateur", "tier": "", "margin_percent": 10, "priority": 10, "sequence": 90, "is_active": 1},
            {
                "customer_type": "Installateur",
                "tier": "Eco",
                "margin_percent": 18,
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
        ]
        rule = resolve_margin_rule(rules, customer_type="Installateur", tier="Eco")
        self.assertEqual(rule["margin_percent"], 18)

    def test_customer_fallback_when_tier_missing(self):
        rules = [
            {"customer_type": "Installateur", "tier": "", "margin_percent": 11, "priority": 10, "sequence": 90, "is_active": 1},
            {"customer_type": "", "tier": "", "margin_percent": 7, "priority": 10, "sequence": 90, "is_active": 1},
        ]
        rule = resolve_margin_rule(rules, customer_type="Installateur", tier="Luxe")
        self.assertEqual(rule["margin_percent"], 11)

    def test_global_fallback_when_no_customer_match(self):
        rules = [
            {"customer_type": "", "tier": "", "margin_percent": 9, "priority": 10, "sequence": 90, "is_active": 1},
            {"customer_type": "Distributeur", "tier": "", "margin_percent": 16, "priority": 10, "sequence": 90, "is_active": 1},
        ]
        rule = resolve_margin_rule(rules, customer_type="Installateur", tier="Eco")
        self.assertEqual(rule["margin_percent"], 9)

    def test_priority_break_tie(self):
        rules = [
            {"customer_type": "", "tier": "", "margin_percent": 9, "priority": 20, "sequence": 90, "is_active": 1},
            {"customer_type": "", "tier": "", "margin_percent": 12, "priority": 5, "sequence": 90, "is_active": 1},
        ]
        rule = resolve_margin_rule(rules, customer_type="Installateur", tier="Eco")
        self.assertEqual(rule["margin_percent"], 12)

    def test_item_and_sales_person_specific_rule(self):
        rules = [
            {
                "item_group": "Motors",
                "sales_person": "SP-001",
                "margin_percent": 11,
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
            {
                "item": "A1",
                "sales_person": "SP-001",
                "margin_percent": 18,
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
        ]
        rule = resolve_margin_rule(
            rules,
            context={
                "item": "A1",
                "item_group": "Motors",
                "sales_person": "SP-001",
            },
        )
        self.assertEqual(rule["margin_percent"], 18)


if __name__ == "__main__":
    unittest.main()
