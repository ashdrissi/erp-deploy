import sys
import types
import unittest


class _Row(types.SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return hasattr(self, key)


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.get_all = lambda *args, **kwargs: []
frappe_stub.get_doc = lambda *args, **kwargs: None
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda fieldname: True)
frappe_stub.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [], exists=lambda *args, **kwargs: False, get_value=lambda *args, **kwargs: None)
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)
frappe_utils_stub.nowdate = lambda: "2026-04-27"
sys.modules["frappe.utils"] = frappe_utils_stub

from orderlift.orderlift_crm.api import pipeline


class TestCrmPipelineFilters(unittest.TestCase):
    def test_opportunity_pipeline_filters_by_crm_segment_field(self):
        calls = []

        def get_all(doctype, **kwargs):
            calls.append((doctype, kwargs))
            return []

        original_get_all = pipeline.frappe.get_all
        original_has_field = pipeline._has_field
        try:
            pipeline.frappe.get_all = get_all
            pipeline._has_field = lambda doctype, fieldname: True

            pipeline._opportunity_cards(
                business_type="Distribution",
                segment="Grossiste",
                statuses=[],
            )

            self.assertEqual(calls[0][0], "Opportunity")
            self.assertEqual(calls[0][1]["filters"]["custom_crm_business_type"], "Distribution")
            self.assertEqual(calls[0][1]["filters"]["custom_crm_segment"], "Grossiste")
        finally:
            pipeline.frappe.get_all = original_get_all
            pipeline._has_field = original_has_field

    def test_project_pipeline_derives_crm_segment_from_source_opportunity(self):
        original_has_field = pipeline._has_field
        original_project_related_docs = pipeline._project_related_docs
        original_db = pipeline.frappe.db
        try:
            pipeline._has_field = lambda doctype, fieldname: fieldname in {
                "custom_source_opportunity",
                "custom_crm_business_type",
                "custom_crm_segment",
            }
            pipeline._project_related_docs = lambda project: []
            pipeline.frappe.db = types.SimpleNamespace(
                exists=lambda doctype, name=None: doctype == "Opportunity" and name == "OPP-1",
                get_value=lambda doctype, name, fields, as_dict=False: {
                    "custom_crm_business_type": "Installation",
                    "custom_crm_segment": "Promoteur",
                },
            )

            card = pipeline._project_card(
                _Row(
                    name="PROJ-1",
                    project_name="Villa Lift",
                    customer="Customer A",
                    company="Orderlift",
                    status="Open",
                    custom_project_status="Advance Paid",
                    custom_source_opportunity="OPP-1",
                ),
                [{"name": "Advance Paid", "is_active": 1}],
            )

            self.assertEqual(card["business_type"], "Installation")
            self.assertEqual(card["crm_segment"], "Promoteur")
            self.assertIn("Promoteur", card["tags"])
        finally:
            pipeline._has_field = original_has_field
            pipeline._project_related_docs = original_project_related_docs
            pipeline.frappe.db = original_db

    def test_sales_order_pipeline_derives_crm_segment_from_campaign_target(self):
        original_sales_order_related_docs = pipeline._sales_order_related_docs
        original_db = pipeline.frappe.db
        try:
            pipeline._sales_order_related_docs = lambda sales_order, project_name: []
            pipeline.frappe.db = types.SimpleNamespace(
                exists=lambda doctype, name=None: doctype == "DocType" and name == "Partner Campaign Target",
                get_value=lambda doctype, name, fields, as_dict=False: {
                    "business_type": "Distribution",
                    "crm_segment": "Grossiste",
                },
            )

            card = pipeline._sales_order_card(
                _Row(
                    name="SO-1",
                    customer="Customer A",
                    company="Orderlift",
                    owner="owner@example.com",
                    status="To Deliver",
                    grand_total=1000,
                    per_delivered=0,
                    per_billed=0,
                    project="",
                    custom_orderlift_order_status="Confirmed",
                    custom_partner_campaign_target="TARGET-1",
                ),
                [{"name": "Confirmed", "is_active": 1}],
            )

            self.assertEqual(card["business_type"], "Distribution")
            self.assertEqual(card["crm_segment"], "Grossiste")
            self.assertIn("Grossiste", card["tags"])
        finally:
            pipeline._sales_order_related_docs = original_sales_order_related_docs
            pipeline.frappe.db = original_db

    def test_source_opportunity_queries_do_not_reference_prevdoc_doctype(self):
        calls = []
        original_db = pipeline.frappe.db
        try:
            pipeline.frappe.db = types.SimpleNamespace(
                exists=lambda doctype, name=None: True,
                sql=lambda query, params, as_dict=False: calls.append(query) or [],
            )

            self.assertIsNone(pipeline._project_source_opportunity("PROJ-1"))
            self.assertIsNone(pipeline._sales_order_source_opportunity("SO-1"))

            self.assertEqual(len(calls), 2)
            self.assertNotIn("prevdoc_doctype", "\n".join(calls))
            self.assertIn("prevdoc_docname", "\n".join(calls))
        finally:
            pipeline.frappe.db = original_db


if __name__ == "__main__":
    unittest.main()
