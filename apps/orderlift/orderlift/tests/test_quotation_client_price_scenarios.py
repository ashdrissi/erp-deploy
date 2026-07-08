import shutil
import subprocess
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestQuotationClientPriceScenarios(unittest.TestCase):
    def test_client_price_inputs_recalculate_linked_fields(self):
        if not shutil.which("node"):
            self.skipTest("node is required for client-side Quotation scenario tests")

        scenario_runner = APP_ROOT / "tests" / "quotation_price_scenarios.js"
        quotation_script = APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js"
        result = subprocess.run(
            ["node", str(scenario_runner), str(quotation_script)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"ok": true', result.stdout)
        self.assertIn('"pu_ht": 200', result.stdout)
        self.assertIn('"remise_percent": 12.5', result.stdout)
        self.assertIn('"pt_ttc_net": 630', result.stdout)


if __name__ == "__main__":
    unittest.main()
