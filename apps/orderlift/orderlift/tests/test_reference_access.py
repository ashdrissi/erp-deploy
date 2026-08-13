import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestReferenceAccess(unittest.TestCase):
    def test_reference_service_preserves_select_read_boundary(self):
        source = (APP_ROOT / "reference_access.py").read_text()

        self.assertIn('ptype="select"', source)
        self.assertIn("permitted = frappe.get_list(", source)
        self.assertIn("permitted_names = frappe.get_list(", source)
        self.assertIn("return frappe.get_all(", source)
        self.assertLess(source.index("permitted_names = frappe.get_list("), source.index("return frappe.get_all("))

    def test_select_is_non_mutating_for_company_scope(self):
        source = (APP_ROOT / "company_access.py").read_text()

        self.assertIn('READ_ONLY_PERMISSION_TYPES = {"read", "select", "report", "print", "email"}', source)

    def test_select_only_option_consumers_use_reference_service(self):
        consumers = [
            "orderlift_crm/api/campaign.py",
            "orderlift_crm/api/installation.py",
            "orderlift_crm/status_workflow.py",
            "orderlift_crm/company_business_type.py",
            "orderlift_sales/doctype/pricing_tier/pricing_tier.py",
        ]

        for relative_path in consumers:
            with self.subTest(path=relative_path):
                self.assertIn("orderlift.reference_access", (APP_ROOT / relative_path).read_text())


if __name__ == "__main__":
    unittest.main()
