import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[1]


class TestSchedulerContract(unittest.TestCase):
    def test_unimplemented_crm_scheduler_is_not_registered(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertNotIn("orderlift.crm.utils.notification_scheduler.run_daily", hooks)

    def test_legacy_crm_scheduler_reports_that_it_is_disabled(self):
        fake_frappe = types.ModuleType("frappe")
        module_path = APP_ROOT / "crm" / "utils" / "notification_scheduler.py"
        spec = importlib.util.spec_from_file_location("orderlift_test_notification_scheduler", module_path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            spec.loader.exec_module(module)

        self.assertEqual(
            module.run_daily(),
            {
                "disabled": True,
                "reason": "CRM notification rules and contact schedules are not configured.",
            },
        )


if __name__ == "__main__":
    unittest.main()
