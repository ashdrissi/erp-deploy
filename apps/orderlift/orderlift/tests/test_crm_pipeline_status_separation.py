import sys
import types
import unittest


class _Row(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class _FakeDoc:
    doctype = "Opportunity"

    def __init__(self):
        self.sales_stage = "New"
        self.status = "Open"
        self.name = "OPP-1"
        self.saved = False
        self.meta = types.SimpleNamespace(get_field=lambda fieldname: True)

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)

    def set(self, fieldname, value):
        setattr(self, fieldname, value)

    def save(self, ignore_permissions=False):
        self.saved = True

    def as_dict(self):
        return _Row(name=self.name, sales_stage=self.sales_stage, status=self.status)


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.get_all = lambda *args, **kwargs: []
frappe_stub.get_doc = lambda *args, **kwargs: None
frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda fieldname: True)
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
frappe_stub.ValidationError = Exception
frappe_stub.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [], exists=lambda *args, **kwargs: False, get_value=lambda *args, **kwargs: None, commit=lambda: None)
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)
frappe_utils_stub.nowdate = lambda: "2026-04-28"
sys.modules["frappe.utils"] = frappe_utils_stub

from orderlift.orderlift_crm import status_workflow
from orderlift.orderlift_crm.api import installation, pipeline
from orderlift.orderlift_crm.status_checks import StatusCheckBlockedError


class TestCrmPipelineStatusSeparation(unittest.TestCase):
    def setUp(self):
        pipeline.frappe = frappe_stub
        installation.frappe = frappe_stub
        status_workflow.frappe = frappe_stub

    def test_opportunity_stage_uses_stored_pipeline_status_only(self):
        statuses = [
            {"name": "New", "is_default": 1},
            {"name": "Quotation Sent", "is_default": 0},
            {"name": "Won / Project", "is_default": 0},
            {"name": "Lost", "is_default": 0},
        ]
        docs = [
            {"doctype": "Quotation"},
            {"doctype": "Sales Order"},
            {"doctype": "Project"},
        ]

        stage = pipeline._resolve_opportunity_stage(_Row(sales_stage="New", status="Converted"), docs, statuses)

        self.assertEqual(stage, "New")

    def test_opportunity_stage_defaults_without_legacy_or_linked_doc_inference(self):
        statuses = [
            {"name": "New", "is_default": 1},
            {"name": "Quotation Sent", "is_default": 0},
            {"name": "Lost", "is_default": 0},
        ]
        docs = [{"doctype": "Quotation"}]

        stage = pipeline._resolve_opportunity_stage(_Row(sales_stage="", status="Lost"), docs, statuses)

        self.assertEqual(stage, "New")

    def test_legacy_installation_stage_uses_stored_status_only(self):
        stage_names = ["New", "Quotation Sent", "Won / Project", "Lost"]
        docs = [{"label": "Quotation"}, {"label": "Sales Order"}]

        self.assertEqual(
            installation._resolve_stage(_Row(custom_installation_stage="New", sales_stage="New", status="Converted"), docs, stage_names),
            "New",
        )
        self.assertEqual(
            installation._resolve_stage(_Row(custom_installation_stage="", sales_stage="", status="Lost"), docs, stage_names),
            "New",
        )

    def test_primary_status_initialization_uses_default_not_legacy_status(self):
        doc = _FakeDoc()
        doc.sales_stage = ""
        doc.status = "Lost"
        original_get_default = status_workflow.get_default_status_name
        try:
            status_workflow.get_default_status_name = lambda document_type: "New"

            status_workflow.ensure_primary_status(doc)

            self.assertEqual(doc.sales_stage, "New")
            self.assertEqual(doc.status, "Lost")
        finally:
            status_workflow.get_default_status_name = original_get_default

    def test_successful_pipeline_move_changes_pipeline_status_not_legacy_status(self):
        doc = _FakeDoc()
        assignment_calls = []
        original_get_doc = pipeline.frappe.get_doc
        original_validate = pipeline._validate_status_for_document
        original_sync = pipeline.sync_pipeline_status_assignment
        original_log = pipeline._log_status_change
        original_list = pipeline.list_editable_statuses
        original_card = pipeline._opportunity_card
        try:
            pipeline.frappe.get_doc = lambda doctype, name: doc
            pipeline._validate_status_for_document = lambda document_type, stage, document: {
                "name": stage,
                "assigned_user": "sales@example.com",
            }
            pipeline.sync_pipeline_status_assignment = lambda *args, **kwargs: assignment_calls.append(args) or {"user": "sales@example.com"}
            pipeline._log_status_change = lambda *args, **kwargs: None
            pipeline.list_editable_statuses = lambda *args, **kwargs: [{"name": "Qualified", "is_active": 1}]
            pipeline._opportunity_card = lambda row, statuses: {"stage": row.get("sales_stage"), "legacy_status": row.get("status")}

            result = pipeline.update_opportunity_stage("OPP-1", "Qualified")

            self.assertEqual(doc.sales_stage, "Qualified")
            self.assertEqual(doc.status, "Open")
            self.assertTrue(doc.saved)
            self.assertEqual(result["legacy_status"], "Open")
            self.assertEqual(len(assignment_calls), 1)
        finally:
            pipeline.frappe.get_doc = original_get_doc
            pipeline._validate_status_for_document = original_validate
            pipeline.sync_pipeline_status_assignment = original_sync
            pipeline._log_status_change = original_log
            pipeline.list_editable_statuses = original_list
            pipeline._opportunity_card = original_card

    def test_pipeline_move_can_auto_close_opportunity(self):
        doc = _FakeDoc()
        original_get_doc = pipeline.frappe.get_doc
        original_validate = pipeline._validate_status_for_document
        original_sync = pipeline.sync_pipeline_status_assignment
        original_log = pipeline._log_status_change
        original_list = pipeline.list_editable_statuses
        original_card = pipeline._opportunity_card
        try:
            pipeline.frappe.get_doc = lambda doctype, name: doc
            pipeline._validate_status_for_document = lambda document_type, stage, document: {
                "name": stage,
                "auto_close_opportunity": 1,
            }
            pipeline.sync_pipeline_status_assignment = lambda *args, **kwargs: {}
            pipeline._log_status_change = lambda *args, **kwargs: None
            pipeline.list_editable_statuses = lambda *args, **kwargs: [{"name": "Lost", "is_active": 1}]
            pipeline._opportunity_card = lambda row, statuses: {"stage": row.get("sales_stage"), "legacy_status": row.get("status")}

            result = pipeline.update_opportunity_stage("OPP-1", "Lost")

            self.assertEqual(doc.sales_stage, "Lost")
            self.assertEqual(doc.status, "Closed")
            self.assertTrue(doc.saved)
            self.assertEqual(result["legacy_status"], "Closed")
        finally:
            pipeline.frappe.get_doc = original_get_doc
            pipeline._validate_status_for_document = original_validate
            pipeline.sync_pipeline_status_assignment = original_sync
            pipeline._log_status_change = original_log
            pipeline.list_editable_statuses = original_list
            pipeline._opportunity_card = original_card

    def test_status_lookup_matches_prefixed_and_short_stage_names(self):
        doc = _FakeDoc()
        doc.company = "Orderlift Maroc Distribution"
        original_list = pipeline.list_editable_statuses
        try:
            pipeline.list_editable_statuses = lambda *args, **kwargs: [
                {
                    "name": "Orderlift Maroc Distribution - 2. Prise de mesure en cours",
                    "label": "2. Prise de mesure en cours",
                    "is_active": 1,
                    "required_checks": [],
                }
            ]

            status = pipeline._validate_status_for_document("Opportunity", "Distribution - 2. Prise de mesure en cours", doc)
            self.assertEqual(
                status["name"],
                "Orderlift Maroc Distribution - 2. Prise de mesure en cours",
            )

            status = pipeline._validate_status_for_document("Opportunity", "Orderlift Maroc Distribution - 2. Prise de mesure en cours", doc)
            self.assertEqual(
                status["name"],
                "Orderlift Maroc Distribution - 2. Prise de mesure en cours",
            )
        finally:
            pipeline.list_editable_statuses = original_list

    def test_blocked_pipeline_move_does_not_change_status_or_todos(self):
        doc = _FakeDoc()
        original_get_doc = pipeline.frappe.get_doc
        original_validate = pipeline._validate_status_for_document
        original_sync = pipeline.sync_pipeline_status_assignment
        original_get_status_meta = pipeline.get_status_meta
        try:
            pipeline.frappe.get_doc = lambda doctype, name: doc
            pipeline._validate_status_for_document = lambda *args, **kwargs: (_ for _ in ()).throw(
                StatusCheckBlockedError("Opportunity", doc.name, {"label": "Qualified"}, ["has_quotation"])
            )
            pipeline.sync_pipeline_status_assignment = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ToDo sync should not run"))
            pipeline.get_status_meta = lambda document_type: {"target_doctype": document_type}

            result = pipeline.update_opportunity_stage("OPP-1", "Qualified")

            self.assertEqual(result["blocked"], 1)
            self.assertEqual(result["record"], "OPP-1")
            self.assertIn("quotation", result["missing_checks"][0].lower())
            self.assertEqual(doc.sales_stage, "New")
            self.assertEqual(doc.status, "Open")
            self.assertFalse(doc.saved)
        finally:
            pipeline.frappe.get_doc = original_get_doc
            pipeline._validate_status_for_document = original_validate
            pipeline.sync_pipeline_status_assignment = original_sync
            pipeline.get_status_meta = original_get_status_meta


if __name__ == "__main__":
    unittest.main()
