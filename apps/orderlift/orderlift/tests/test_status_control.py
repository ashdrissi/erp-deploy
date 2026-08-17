import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestStatusControlConfiguration(unittest.TestCase):
    def test_project_and_sales_order_status_labels_are_editable_like_opportunity(self):
        config = (APP_ROOT / "orderlift_crm" / "status_config.py").read_text()
        project_block = config.split('"Project": {', 1)[1].split('"Sales Order": {', 1)[0]
        sales_order_block = config.split('"Sales Order": {', 1)[1].split('"Forecast Load Plan": {', 1)[0]
        opportunity_block = config.split('"Opportunity": {', 1)[1].split('"Project": {', 1)[0]

        self.assertNotIn('"allow_rename": False', opportunity_block)
        self.assertNotIn('"allow_rename": False', project_block)
        self.assertNotIn('"allow_rename": False', sales_order_block)
        self.assertIn('"display_label_field": "display_label"', project_block)
        self.assertIn('"display_label_field": "display_label"', sales_order_block)
        self.assertIn("rename_doc(status_doctype, current_name, internal_label", (APP_ROOT / "orderlift_crm" / "api" / "status_control.py").read_text())
        self.assertIn('"allow_rename": 1', (APP_ROOT / "orderlift_crm" / "doctype" / "project_status" / "project_status.json").read_text())
        self.assertIn('"allow_rename": 1', (APP_ROOT / "orderlift_crm" / "doctype" / "orderlift_order_status" / "orderlift_order_status.json").read_text())

    def test_first_active_status_becomes_default_for_every_pipeline(self):
        api = (APP_ROOT / "orderlift_crm" / "api" / "status_control.py").read_text()
        page = (APP_ROOT / "orderlift_crm" / "page" / "status_control" / "status_control.js").read_text()

        self.assertIn("is_new_status = doc.is_new()", api)
        self.assertIn("not _has_active_default_status(document_type, company)", api)
        self.assertIn("is_default = 1", api)
        self.assertIn("const hasActiveDefault = (STATE.data.statuses || []).some", page)
        self.assertIn("STATE.draft.is_default = hasActiveDefault ? 0 : 1", page)

    def test_delete_availability_and_endpoint_use_native_delete_permission(self):
        api = (APP_ROOT / "orderlift_crm" / "api" / "status_control.py").read_text()

        self.assertIn(
            '"allow_delete": bool(meta.get("allow_delete", True) and frappe.has_permission(status_doctype, ptype="delete"))',
            api,
        )
        delete_body = api.split("def delete_status(", 1)[1].split("@frappe.whitelist()", 1)[0]
        self.assertIn('frappe.has_permission(status_doctype, ptype="delete", throw=True)', delete_body)

    def test_auto_create_project_is_opportunity_status_only_and_saved(self):
        config = (APP_ROOT / "orderlift_crm" / "status_config.py").read_text()
        workflow = (APP_ROOT / "orderlift_crm" / "status_workflow.py").read_text()
        api = (APP_ROOT / "orderlift_crm" / "api" / "status_control.py").read_text()
        page = (APP_ROOT / "orderlift_crm" / "page" / "status_control" / "status_control.js").read_text()
        opportunity_block = config.split('"Opportunity": {', 1)[1].split('"Project": {', 1)[0]
        project_block = config.split('"Project": {', 1)[1].split('"Sales Order": {', 1)[0]

        self.assertIn('"auto_create_project_field": "custom_auto_create_project"', opportunity_block)
        self.assertNotIn("auto_create_project_field", project_block)
        self.assertIn('"auto_create_project": cint(', workflow)
        self.assertIn('data.get("auto_create_project", 0)', api)
        self.assertIn("data-field=\"auto_create_project\"", page)


if __name__ == "__main__":
    unittest.main()
