import unittest

from orderlift.sales.utils.scenario_policy import resolve_scenario_rule


class TestScenarioPolicyResolver(unittest.TestCase):
    def test_item_and_sales_person_match_wins(self):
        rules = [
            {
                "pricing_scenario": "SCN-GLOBAL",
                "item_group": "Machines",
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
            {
                "pricing_scenario": "SCN-SP1-A1",
                "sales_person": "SP-001",
                "item": "A1",
                "priority": 10,
                "sequence": 90,
                "is_active": 1,
            },
        ]
        context = {"sales_person": "SP-001", "item": "A1", "item_group": "Machines"}
        rule = resolve_scenario_rule(rules, context)
        self.assertEqual(rule["pricing_scenario"], "SCN-SP1-A1")

    def test_fallback_rule_used(self):
        rules = [
            {"pricing_scenario": "SCN-FALLBACK", "priority": 10, "sequence": 90, "is_active": 1},
            {"pricing_scenario": "SCN-FR", "geography_type": "Country", "geography_value": "FR", "priority": 10, "sequence": 90, "is_active": 1},
        ]
        context = {"geography_type": "Country", "geography_value": "MA"}
        rule = resolve_scenario_rule(rules, context)
        self.assertEqual(rule["pricing_scenario"], "SCN-FALLBACK")

    def test_priority_break_tie(self):
        rules = [
            {"pricing_scenario": "SCN-P20", "item_group": "Machines", "priority": 20, "sequence": 90, "is_active": 1},
            {"pricing_scenario": "SCN-P5", "item_group": "Machines", "priority": 5, "sequence": 90, "is_active": 1},
        ]
        context = {"item_group": "Machines"}
        rule = resolve_scenario_rule(rules, context)
        self.assertEqual(rule["pricing_scenario"], "SCN-P5")


if __name__ == "__main__":
    unittest.main()
