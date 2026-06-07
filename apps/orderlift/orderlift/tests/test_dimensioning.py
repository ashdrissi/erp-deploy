import unittest

from orderlift.sales.utils.dimensioning import (
    coerce_dimensioning_value,
    evaluate_formula,
    evaluate_structured_condition,
    evaluate_structured_quantity,
    validate_dimensioning_key,
    validate_formula,
    validate_structured_condition,
    validate_structured_quantity,
)


class TestDimensioning(unittest.TestCase):
    def test_validate_dimensioning_key(self):
        self.assertEqual(validate_dimensioning_key("floors_count"), "floors_count")
        with self.assertRaises(ValueError):
            validate_dimensioning_key("3floors")

    def test_formula_supports_math_and_functions(self):
        variables = {"floors": 5, "doors": 2}
        self.assertEqual(evaluate_formula("3 * floors + max(doors, 1)", variables), 17)

    def test_formula_supports_conditionals(self):
        variables = {"floors": 4, "premium": True}
        self.assertEqual(evaluate_formula("10 if premium and floors > 3 else 0", variables), 10)

    def test_validate_formula_rejects_unknown_names(self):
        with self.assertRaises(ValueError):
            validate_formula("3 * unknown_value", {"floors"})

    def test_formula_helpers_cover_workbook_rules(self):
        variables = {"levels": 4, "motor_brand": "AKİŞ", "lift_type": "VVF"}

        self.assertEqual(evaluate_formula('ifelse(contains("MOTEUR AKİŞ MAX4", motor_brand), levels, 0)', variables), 4)
        self.assertTrue(evaluate_formula('one_of(lift_type, "VVF", "2V")', variables))
        self.assertEqual(evaluate_formula('concat("(", levels)', variables), "(4")
        self.assertEqual(evaluate_formula("int(3.8)", variables), 3)

    def test_coerce_dimensioning_values(self):
        self.assertEqual(coerce_dimensioning_value("Int", "4"), 4)
        self.assertEqual(coerce_dimensioning_value("Float", "4.5"), 4.5)
        self.assertTrue(coerce_dimensioning_value("Check", "true"))
        self.assertEqual(coerce_dimensioning_value("Data", 12), "12")

    def test_structured_condition_manual_value(self):
        rule = {
            "condition_mode": "based",
            "question_key": "levels",
            "operator": ">=",
            "compare_source": "manual",
            "manual_value": "4",
        }

        self.assertTrue(evaluate_structured_condition(rule, {"levels": 5}, {"levels": "Int"}))
        self.assertFalse(evaluate_structured_condition(rule, {"levels": 3}, {"levels": "Int"}))

    def test_structured_condition_question_value(self):
        rule = {
            "condition_mode": "based",
            "question_key": "door_count",
            "operator": "==",
            "compare_source": "question",
            "compare_question_key": "levels",
        }

        self.assertTrue(evaluate_structured_condition(rule, {"door_count": 4, "levels": 4}))
        self.assertFalse(evaluate_structured_condition(rule, {"door_count": 3, "levels": 4}))

    def test_structured_quantity_modes(self):
        self.assertEqual(evaluate_structured_quantity({"quantity_mode": "fixed", "fixed_qty": "2"}, {}), 2)
        self.assertEqual(
            evaluate_structured_quantity({"quantity_mode": "question", "quantity_question_key": "levels"}, {"levels": 4}),
            4,
        )

    def test_structured_validation_rejects_text_greater_than(self):
        rule = {
            "condition_mode": "based",
            "question_key": "family",
            "operator": ">",
            "compare_source": "manual",
            "manual_value": "PORTE",
        }

        with self.assertRaises(ValueError):
            validate_structured_condition(rule, {"family": "Select"})

    def test_structured_validation_rejects_text_quantity_question(self):
        with self.assertRaises(ValueError):
            validate_structured_quantity(
                {"quantity_mode": "question", "quantity_question_key": "family"},
                {"family": "Select"},
            )


if __name__ == "__main__":
    unittest.main()
