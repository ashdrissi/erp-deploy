import shutil
import subprocess
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestDeskEntryRedirect(unittest.TestCase):
    def test_history_wrapper_preserves_omitted_url_argument(self):
        if not shutil.which("node"):
            self.skipTest("node is required for Desk asset tests")

        runner = APP_ROOT / "tests" / "desk_entry_redirect_history_scenarios.js"
        script = APP_ROOT / "public" / "js" / "desk_entry_redirect_20260728a.js"
        result = subprocess.run(
            ["node", str(runner), str(script)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"ok":true', result.stdout)


if __name__ == "__main__":
    unittest.main()
