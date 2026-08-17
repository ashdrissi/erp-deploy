import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestNativeProjectLifecycle(unittest.TestCase):
    def test_migration_is_registered_before_legacy_field_retirement(self):
        patches = (APP_ROOT / "patches.txt").read_text()
        migrate = "orderlift.patches.v1_0.migrate_native_project_lifecycle"
        retire = "orderlift.patches.v1_0.retire_legacy_project_lifecycle_fields"

        self.assertIn(migrate, patches)
        self.assertIn(retire, patches)
        self.assertLess(patches.index(migrate), patches.index(retire))

    def test_fixtures_use_native_project_fields_and_configurable_project_type(self):
        crm_fields = json.loads((APP_ROOT / "fixtures" / "custom_field_crm_classification.json").read_text())
        project_fields = json.loads((APP_ROOT / "fixtures" / "custom_field_project_sig.json").read_text())
        sales_order_fields = json.loads((APP_ROOT / "fixtures" / "custom_field_sales_order_sig.json").read_text())
        qc_template = json.loads(
            (APP_ROOT / "orderlift_sig" / "doctype" / "qc_checklist_template" / "qc_checklist_template.json").read_text()
        )

        crm_by_name = {(row["dt"], row["fieldname"]): row for row in crm_fields}
        self.assertEqual(crm_by_name[("Opportunity", "custom_project_type")]["fieldtype"], "Link")
        self.assertEqual(crm_by_name[("Opportunity", "custom_project_type")]["options"], "Project Type")
        self.assertNotIn(("Opportunity", "custom_project_type_ol"), crm_by_name)
        self.assertNotIn("custom_project_type_ol", {row["fieldname"] for row in project_fields})
        self.assertNotIn("custom_installation_project", {row["fieldname"] for row in sales_order_fields})
        template_type = next(row for row in qc_template["fields"] if row["fieldname"] == "project_type")
        self.assertEqual(template_type["fieldtype"], "Link")
        self.assertEqual(template_type["options"], "Project Type")

    def test_active_runtime_uses_native_sales_order_and_project_type_fields(self):
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()
        linkage = (APP_ROOT / "orderlift_crm" / "project_linkage.py").read_text()
        dashboard = (APP_ROOT / "orderlift_sig" / "api" / "dashboard_api.py").read_text()
        map_api = (APP_ROOT / "orderlift_sig" / "api" / "map_api.py").read_text()

        self.assertNotIn("custom_installation_project", pipeline)
        self.assertNotIn("custom_installation_project", linkage)
        self.assertNotIn("custom_project_type_ol", dashboard)
        self.assertNotIn("custom_project_type_ol", map_api)
        self.assertIn('"project": ["is", "not set"]', pipeline)
        self.assertNotIn('or "Installation"', pipeline)
        self.assertNotIn('return "Distribution"', pipeline)

    def test_pipeline_business_type_options_are_data_driven(self):
        opportunity_page = (
            APP_ROOT / "orderlift_crm" / "page" / "opportunity_pipeline" / "opportunity_pipeline.js"
        ).read_text()
        project_page = (
            APP_ROOT / "orderlift_crm" / "page" / "project_pipeline" / "project_pipeline.js"
        ).read_text()

        self.assertNotIn('["All", "Distribution", "Installation"', opportunity_page)
        self.assertNotIn('card.business_type || "Installation"', project_page)

    def test_migration_has_dry_run_diagnostics_and_conflict_guards(self):
        migration = (APP_ROOT / "patches" / "v1_0" / "migrate_native_project_lifecycle.py").read_text()
        retirement = (APP_ROOT / "patches" / "v1_0" / "retire_legacy_project_lifecycle_fields.py").read_text()

        self.assertIn("def run(dry_run: int = 1)", migration)
        self.assertIn('"sales_order_conflicts"', migration)
        self.assertIn("FOR UPDATE", (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text())
        self.assertIn("sales_orders_to_migrate", retirement)
        self.assertIn('summary.get("projects_to_migrate")', retirement)

    def test_transition_has_no_early_commit_before_response_construction(self):
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()
        transition = pipeline.split("def update_opportunity_stage(", 1)[1].split("@frappe.whitelist()", 1)[0]

        self.assertNotIn("frappe.db.commit()", transition)
        self.assertLess(transition.index("FOR UPDATE"), transition.index("_validate_status_for_document"))


if __name__ == "__main__":
    unittest.main()
