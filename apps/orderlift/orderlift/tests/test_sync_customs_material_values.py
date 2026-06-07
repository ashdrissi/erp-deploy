import sys
import types
import unittest


frappe_stub = sys.modules.get("frappe") or types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
sys.modules["frappe"] = frappe_stub

utils_stub = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
utils_stub.flt = lambda value=0: float(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift.scripts import sync_customs_material_values


class TestSyncCustomsMaterialValues(unittest.TestCase):
    def test_build_article_rows_uses_hs_code_and_material_value(self):
        rows = [
            {"excel_row": 2, "HS CODE (10 DIGIT)": "8534 000000", "DOUANE MATERIAL": "ACIER (CARTE )"},
            {"excel_row": 3, "HS CODE (10 DIGIT)": "8534 000000", "DOUANE MATERIAL": "ACIER (CARTE )"},
            {"excel_row": 4, "HS CODE (10 DIGIT)": "8544429090", "DOUANE MATERIAL": "CUIVRE"},
        ]

        policy_rows, warnings = sync_customs_material_values._build_article_policy_rows(
            rows, include_material_fallbacks=0
        )

        self.assertEqual(warnings, [])
        self.assertEqual(len(policy_rows), 2)
        carte_row = next(row for row in policy_rows if row["tariff_number"] == "8534000000")
        self.assertEqual(carte_row["material"], "ACIER (CARTE )")
        self.assertEqual(carte_row["value_per_kg"], 50)
        self.assertEqual(carte_row["rate_percent"], 20.25)
        self.assertEqual(carte_row["rate_per_kg"], 0)
        self.assertIn("Rows matched: 2", carte_row["notes"])

    def test_build_article_rows_adds_fallbacks_for_workbook_variants(self):
        rows = [
            {"excel_row": 2, "HS CODE (10 DIGIT)": "8534000000", "DOUANE MATERIAL": "ACIER (CARTE )"},
        ]

        policy_rows, warnings = sync_customs_material_values._build_article_policy_rows(rows)

        self.assertEqual(warnings, [])
        fallbacks = {row["material"] for row in policy_rows if row["source"] == "material_fallback"}
        self.assertIn("ACIER (CARTE )", fallbacks)
        self.assertIn("ACIER (CARTE)", fallbacks)

    def test_build_article_rows_warns_and_skips_unknown_materials(self):
        rows = [
            {"excel_row": 2, "HS CODE (10 DIGIT)": "7007198000", "DOUANE MATERIAL": "VERRE"},
        ]

        policy_rows, warnings = sync_customs_material_values._build_article_policy_rows(
            rows, include_material_fallbacks=0
        )

        self.assertEqual(policy_rows, [])
        self.assertEqual(warnings[0]["type"], "unknown_material")
        self.assertEqual(warnings[0]["material"], "VERRE")


if __name__ == "__main__":
    unittest.main()
