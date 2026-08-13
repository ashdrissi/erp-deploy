import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestCrmMigrateSafety(unittest.TestCase):
    def test_after_migrate_does_not_seed_pipeline_statuses(self):
        source = (APP_ROOT / "orderlift_crm" / "setup.py").read_text()
        body = source.split("def after_migrate():", 1)[1].split("\ndef ", 1)[0]

        for function_name in (
            "_seed_opportunity_stages()",
            "_deactivate_legacy_sales_stages()",
            "_seed_project_statuses()",
            "_seed_sales_order_statuses()",
            "_seed_logistics_pipeline_statuses()",
        ):
            self.assertNotIn(function_name, body)


if __name__ == "__main__":
    unittest.main()
