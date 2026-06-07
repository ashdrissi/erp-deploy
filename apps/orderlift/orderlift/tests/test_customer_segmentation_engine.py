import json
import sys
import types
import unittest
from pathlib import Path


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
frappe_stub._ = lambda message: message
frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.flt = lambda value, precision=None: float(value or 0)
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.getdate = lambda value: value
frappe_utils_stub.date_diff = lambda end, start: 0
frappe_utils_stub.now_datetime = lambda: "2026-04-27 00:00:00"
frappe_utils_stub.nowdate = lambda: "2026-04-27"
frappe_model_stub = types.ModuleType("frappe.model")
frappe_document_stub = types.ModuleType("frappe.model.document")
frappe_document_stub.Document = object
frappe_stub.utils = frappe_utils_stub
sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = frappe_utils_stub
sys.modules["frappe.model"] = frappe_model_stub
sys.modules["frappe.model.document"] = frappe_document_stub

from orderlift.orderlift_sales.doctype.customer_segmentation_engine import customer_segmentation_engine as cse_module
from orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine import (
    CustomerSegmentationEngine,
)


APP_ROOT = Path(__file__).resolve().parents[2]


class TestCustomerSegmentationEngine(unittest.TestCase):
    def test_doctype_uses_crm_filters_and_hides_customer_group_filter(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "customer_segmentation_engine"
            / "customer_segmentation_engine.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["target_customer_type"]["label"], "Legacy Customer Group Filter")
        self.assertEqual(fields["target_customer_type"]["options"], "Customer Group")
        self.assertEqual(fields["target_customer_type"]["hidden"], 1)
        self.assertEqual(fields["business_type_filter"]["options"], "CRM Business Type")
        self.assertEqual(fields["crm_segment_filter"]["options"], "CRM Segment")

    def test_doctype_exposes_global_modifier_tables(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "customer_segmentation_engine"
            / "customer_segmentation_engine.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["tier_modifiers"]["options"], "Pricing Tier Modifier")
        self.assertEqual(fields["zone_modifiers"]["options"], "Pricing Zone Modifier")

    def test_segmentation_rule_assigns_pricing_tier_link(self):
        path = (
            APP_ROOT
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "customer_segmentation_rule"
            / "customer_segmentation_rule.json"
        )
        doc = json.loads(path.read_text())
        fields = {row["fieldname"]: row for row in doc["fields"]}

        self.assertEqual(fields["designated_segment"]["fieldtype"], "Link")
        self.assertEqual(fields["designated_segment"]["options"], "Pricing Tier")

    def test_get_target_customers_filters_by_crm_assignment(self):
        class DbStub:
            def __init__(self):
                self.sql_values = None
                self.sql_query = None

            def exists(self, doctype, name):
                return doctype == "DocType" and name == "CRM Segment Assignment"

            def has_column(self, doctype, fieldname):
                return False

            def sql(self, query, values, as_dict=False):
                self.sql_query = query
                self.sql_values = values
                return [{"name": "CUST-001", "customer_name": "Customer 1"}]

        db_stub = DbStub()
        old_db = getattr(cse_module.frappe, "db", None)
        cse_module.frappe.db = db_stub
        try:
            engine = CustomerSegmentationEngine()
            engine.target_customer_type = "Commercial"
            engine.business_type_filter = "Distribution"
            engine.crm_segment_filter = "Grossiste"

            rows = engine._get_target_customers()
        finally:
            if old_db is None:
                delattr(cse_module.frappe, "db")
            else:
                cse_module.frappe.db = old_db

        self.assertEqual(rows, [{"name": "CUST-001", "customer_name": "Customer 1"}])
        self.assertIn("tabCRM Segment Assignment", db_stub.sql_query)
        self.assertEqual(
            db_stub.sql_values,
            {
                "disabled": 0,
                "business_type": "Distribution",
                "crm_segment": "Grossiste",
            },
        )

    def test_resolve_global_pricing_modifiers_uses_company_engine(self):
        class DbStub:
            def __init__(self):
                self.filters = None

            def has_column(self, doctype, fieldname):
                return doctype == "Customer Segmentation Engine" and fieldname == "custom_company"

            def get_value(self, doctype, filters, fieldname):
                self.filters = filters
                return "CSEG-001" if doctype == "Customer Segmentation Engine" else None

        engine = types.SimpleNamespace(
            tier_modifiers=[
                types.SimpleNamespace(
                    idx=1,
                    is_active=1,
                    business_type="Distribution",
                    crm_segment="Grossiste",
                    tier="Gold",
                    modifier_amount=-3,
                    modifier_type="Percentage",
                )
            ],
            zone_modifiers=[
                types.SimpleNamespace(
                    idx=1,
                    is_active=1,
                    territory="Casablanca",
                    modifier_amount=25,
                    modifier_type="Fixed",
                )
            ],
        )
        db_stub = DbStub()
        old_db = getattr(cse_module.frappe, "db", None)
        old_get_doc = getattr(cse_module.frappe, "get_doc", None)
        cse_module.frappe.db = db_stub
        cse_module.frappe.get_doc = lambda doctype, name: engine
        try:
            tier_mod, zone_mod, warning = cse_module.resolve_global_pricing_modifiers(
                company="Orderlift Maroc Distribution",
                tier="Gold",
                business_type="Distribution",
                crm_segment="Grossiste",
                territory="Casablanca",
            )
        finally:
            if old_db is None:
                delattr(cse_module.frappe, "db")
            else:
                cse_module.frappe.db = old_db
            if old_get_doc is None:
                delattr(cse_module.frappe, "get_doc")
            else:
                cse_module.frappe.get_doc = old_get_doc

        self.assertEqual(db_stub.filters["custom_company"], "Orderlift Maroc Distribution")
        self.assertEqual(tier_mod["amount"], -3)
        self.assertEqual(tier_mod["type"], "Percentage")
        self.assertEqual(zone_mod["amount"], 25)
        self.assertEqual(warning, "")


if __name__ == "__main__":
    unittest.main()
