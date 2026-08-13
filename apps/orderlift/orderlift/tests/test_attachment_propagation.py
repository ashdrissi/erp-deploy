import importlib.util
import sys
import types
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = APP_ROOT / "orderlift_crm" / "attachment_propagation.py"


class Meta:
    def get_field(self, fieldname):
        return fieldname == "content_hash"


class FileDoc(dict):
    def __init__(self):
        super().__init__()
        self.doctype = "File"
        self.meta = Meta()

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        if key in {"doctype", "meta"}:
            object.__setattr__(self, key, value)
        else:
            self[key] = value

    def insert(self, **kwargs):
        self["name"] = self.get("name") or f"FILE-{len(self._frappe.files) + 1}"
        self._frappe.files.append(dict(self))
        return self


class DbStub:
    def __init__(self, frappe):
        self.frappe = frappe

    def exists(self, doctype, filters):
        if doctype == "Quotation" and isinstance(filters, str):
            return filters == "QTN-1"
        if doctype != "File" or not isinstance(filters, dict):
            return False
        return any(all(row.get(key) == value for key, value in filters.items()) for row in self.frappe.files)


class Doc(dict):
    doctype = "Sales Order"
    name = "SO-1"

    def get(self, key, default=None):
        return super().get(key, default)


def load_module():
    frappe = types.ModuleType("frappe")
    frappe.files = [
        {
            "name": "FILE-SOURCE",
            "file_name": "site-photo.pdf",
            "file_url": "/files/site-photo.pdf",
            "is_private": 1,
            "folder": "Home/Attachments",
            "content_hash": "abc",
            "attached_to_doctype": "Opportunity",
            "attached_to_name": "OPP-1",
            "is_folder": 0,
        }
    ]
    frappe.db = DbStub(frappe)

    def get_all(doctype, filters=None, fields=None, **kwargs):
        return [
            {field: row.get(field) for field in fields}
            for row in frappe.files
            if doctype == "File" and all(row.get(key) == value for key, value in filters.items())
        ]

    def new_doc(doctype):
        doc = FileDoc()
        doc._frappe = frappe
        return doc

    frappe.get_all = get_all
    frappe.new_doc = new_doc
    previous = sys.modules.get("frappe")
    sys.modules["frappe"] = frappe
    try:
        spec = importlib.util.spec_from_file_location("attachment_propagation_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("frappe", None)
        else:
            sys.modules["frappe"] = previous
    return module, frappe


class TestAttachmentPropagation(unittest.TestCase):
    def test_copy_attachments_is_idempotent(self):
        module, frappe = load_module()

        copied = module.copy_attachments("Opportunity", "OPP-1", "Quotation", "QTN-1")
        copied_again = module.copy_attachments("Opportunity", "OPP-1", "Quotation", "QTN-1")

        target_files = [row for row in frappe.files if row.get("attached_to_doctype") == "Quotation"]
        self.assertEqual(copied, 1)
        self.assertEqual(copied_again, 0)
        self.assertEqual(len(target_files), 1)
        self.assertEqual(target_files[0]["file_url"], "/files/site-photo.pdf")

    def test_hooks_are_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("copy_opportunity_attachments_to_quotation", hooks)
        self.assertIn("copy_quotation_attachments_to_sales_order", hooks)
        self.assertIn("copy_sales_order_attachments_to_downstream", hooks)


if __name__ == "__main__":
    unittest.main()
