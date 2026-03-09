import unittest

from orderlift.sales.utils.dimensioning import (
    coerce_dimensioning_value,
    evaluate_formula,
    validate_dimensioning_key,
    validate_formula,
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

    def test_coerce_dimensioning_values(self):
        self.assertEqual(coerce_dimensioning_value("Int", "4"), 4)
        self.assertEqual(coerce_dimensioning_value("Float", "4.5"), 4.5)
        self.assertTrue(coerce_dimensioning_value("Check", "true"))
        self.assertEqual(coerce_dimensioning_value("Data", 12), "12")


if __name__ == "__main__":
    unittest.main()
