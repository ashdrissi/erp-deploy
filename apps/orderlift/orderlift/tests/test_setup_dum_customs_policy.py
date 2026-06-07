import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
sys.modules["frappe.utils"] = utils_stub


from orderlift.scripts import setup_dum_customs_policy


class TestSetupDumCustomsPolicy(unittest.TestCase):
    def test_build_policy_rows_prefers_dum_value(self):
        rows = [
            {
                "excel_row": 4,
                "CODE HS (10 DIG)": " 8431 310000 ",
                "MATERIAU": "acier epoxy",
                "VAL. DOUANE DH/KG (SOURCE DUM)": "12,5",
                "VALEUR THORIQUE DH/KG": "99",
            }
        ]

        policy_rows, warnings = setup_dum_customs_policy._build_policy_rows(rows)

        self.assertEqual(warnings, [])
        self.assertEqual(policy_rows[0]["tariff_number"], "8431310000")
        self.assertEqual(policy_rows[0]["material"], "ACIER")
        self.assertEqual(policy_rows[0]["value_per_kg"], 12.5)
        self.assertEqual(policy_rows[0]["rate_components"], "")
        self.assertEqual(policy_rows[0]["rate_per_kg"], 0.0)
        self.assertEqual(policy_rows[0]["rate_percent"], 20.25)
        self.assertEqual(policy_rows[0]["is_active"], 1)

    def test_build_policy_rows_uses_theoretical_fallback(self):
        rows = [
            {
                "excel_row": 5,
                "CODE HS (10 DIG)": "3925900000",
                "MATERIAU": "PVC",
                "VAL. DOUANE DH/KG (SOURCE DUM)": "",
                "VALEUR THORIQUE DH/KG": "7.75",
            }
        ]

        policy_rows, warnings = setup_dum_customs_policy._build_policy_rows(rows)

        self.assertEqual(warnings, [])
        self.assertEqual(policy_rows[0]["material"], "PLASTIQUE")
        self.assertEqual(policy_rows[0]["value_per_kg"], 7.75)
        self.assertIn("Value source: theoretical", policy_rows[0]["notes"])

    def test_build_policy_rows_flags_missing_value_as_active_zero_by_default(self):
        rows = [
            {
                "excel_row": 6,
                "CODE HS (10 DIG)": "3819009000",
                "MATERIAU": "HUILE",
                "VAL. DOUANE DH/KG (SOURCE DUM)": "",
                "VALEUR THORIQUE DH/KG": "",
            }
        ]

        policy_rows, warnings = setup_dum_customs_policy._build_policy_rows(rows)

        self.assertEqual(policy_rows[0]["value_per_kg"], 0.0)
        self.assertEqual(policy_rows[0]["is_active"], 1)
        self.assertEqual(warnings[0]["tariff_number"], "3819009000")
        self.assertIn("active zero-value", warnings[0]["message"])

    def test_build_article_placeholders_adds_missing_pairs_only(self):
        article_rows = [
            {"HS CODE (10 DIGIT)": "8501528000", "DOUANE MATERIAL": "ACIER"},
            {"HS CODE (10 DIGIT)": "3925900000", "DOUANE MATERIAL": "PVC"},
        ]
        policy_rows = [{"tariff_number": "8501528000", "material": "ACIER"}]

        placeholders, warnings = setup_dum_customs_policy._build_article_placeholders(article_rows, policy_rows)

        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0]["tariff_number"], "3925900000")
        self.assertEqual(placeholders[0]["material"], "PLASTIQUE")
        self.assertEqual(placeholders[0]["is_active"], 0)
        self.assertEqual(placeholders[0]["is_article_placeholder"], 1)
        self.assertIn("inactive placeholder", warnings[0]["message"])


if __name__ == "__main__":
    unittest.main()
