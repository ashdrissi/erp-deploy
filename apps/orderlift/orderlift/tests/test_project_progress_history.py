import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProjectProgressHistory(unittest.TestCase):
    def test_project_update_progress_fields_are_provisioned_and_queried(self):
        fixture_path = APP_ROOT / "fixtures" / "custom_field_project_sig.json"
        fields = json.loads(fixture_path.read_text())
        project_update_fields = {
            row.get("fieldname")
            for row in fields
            if row.get("dt") == "Project Update"
        }

        self.assertIn("custom_progress", project_update_fields)
        self.assertIn("custom_progress_details", project_update_fields)

        script = (APP_ROOT / "public" / "js" / "project_sig.js").read_text()
        wrapper = (APP_ROOT / "public" / "js" / "project_sig_20260429c.js").read_text()
        self.assertIn('"custom_progress"', script)
        self.assertIn('"custom_progress_details"', script)
        self.assertNotIn('"progress", "progress_details"', script)
        self.assertIn("project_sig.js?v=20260718a", wrapper)


if __name__ == "__main__":
    unittest.main()
