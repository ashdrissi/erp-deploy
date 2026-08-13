from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestSalesOrderConnectedDocuments(unittest.TestCase):
    def test_sales_order_documents_tab_is_created_after_migrate(self):
        setup = (APP_ROOT / "orderlift_crm" / "setup.py").read_text()

        self.assertIn("_ensure_sales_order_documents_tab()", setup)
        self.assertIn('"Sales Order": [', setup)
        self.assertIn('"fieldname": "custom_documents_tab"', setup)
        self.assertIn('"fieldname": "custom_documents_html"', setup)
        self.assertIn('"insert_after": "party_account_currency"', setup)

    def test_sales_order_form_renders_permission_filtered_document_chain(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "sales_order_connected_documents_20260724a.js").read_text()
        api = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()

        self.assertIn('"public/js/sales_order_connected_documents_20260724a.js"', hooks)
        for token in [
            'frappe.ui.form.on("Sales Order"',
            "custom_documents_html",
            "get_sales_order_documents",
            "Linked Documents",
            "data-open-doc",
        ]:
            self.assertIn(token, script)
        for token in [
            "def get_sales_order_documents(sales_order: str) -> dict:",
            'frappe.has_permission("Sales Order", ptype="read", doc=sales_order)',
            "frappe.has_permission(doctype, ptype=\"read\", doc=row.get(\"name\"))",
            '"Quotation"',
            '"Project"',
            '"Material Request"',
            '"Purchase Order"',
            '"Pick List"',
            '"Delivery Note"',
            '"Sales Invoice"',
            '"Payment Entry"',
        ]:
            self.assertIn(token, api)


if __name__ == "__main__":
    unittest.main()
