import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestApprovalWorkflowSeeder(unittest.TestCase):
    def test_seeder_is_explicit_inactive_and_scoped(self):
        source = (APP_ROOT / "scripts" / "setup_approval_workflows.py").read_text()

        for token in [
            '"Orderlift Purchase Order Approval"',
            '"Orderlift Sales Order Approval"',
            '"Orderlift Quotation Approval"',
            '"Purchase Order"',
            '"Sales Order"',
            '"Quotation"',
            '"Pending Approval"',
            '"Approved"',
            '"Rejected"',
            '"Submitted"',
            '"Approve"',
            '"Reject"',
            '"Reopen"',
            '"Submit"',
            '"Orderlift Admin"',
            '"System Manager"',
        ]:
            self.assertIn(token, source)

        self.assertIn("def run(dry_run: int = 1, force: int = 0)", source)
        self.assertIn("doc.is_active = 0", source)
        self.assertIn('"is_active": 0', source)
        self.assertNotIn('"Item"', source)

    def test_seeder_is_not_migrate_hooked(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertNotIn("setup_approval_workflows", hooks)


if __name__ == "__main__":
    unittest.main()
