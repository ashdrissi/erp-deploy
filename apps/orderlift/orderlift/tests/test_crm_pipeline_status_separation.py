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
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(Exception(message))
frappe_stub.ValidationError = Exception
frappe_stub.PermissionError = PermissionError
frappe_stub.has_permission = lambda *args, **kwargs: True
frappe_stub.db = types.SimpleNamespace(
    sql=lambda *args, **kwargs: [],
    exists=lambda *args, **kwargs: False,
    get_value=lambda *args, **kwargs: None,
    set_value=lambda *args, **kwargs: None,
    commit=lambda: None,
)
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)
frappe_utils_stub.nowdate = lambda: "2026-04-28"
sys.modules["frappe.utils"] = frappe_utils_stub

from orderlift.orderlift_crm import status_workflow
from orderlift.orderlift_crm import project_linkage
from orderlift.orderlift_crm.api import installation, pipeline
from orderlift.orderlift_crm.status_checks import StatusCheckBlockedError
from orderlift.orderlift_crm import status_checks


class TestCrmPipelineStatusSeparation(unittest.TestCase):
    def setUp(self):
        pipeline.frappe = frappe_stub
        installation.frappe = frappe_stub
        status_workflow.frappe = frappe_stub
        project_linkage.frappe = frappe_stub

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

    def test_pipeline_move_auto_creates_project_after_checks_and_returns_it(self):
        doc = _FakeDoc()
        original_get_doc = pipeline.frappe.get_doc
        original_validate = pipeline._validate_status_for_document
        original_ensure_project = pipeline._ensure_opportunity_project
        original_sync = pipeline.sync_pipeline_status_assignment
        original_log = pipeline._log_status_change
        original_list = pipeline.list_editable_statuses
        original_card = pipeline._opportunity_card
        try:
            pipeline.frappe.get_doc = lambda doctype, name: doc
            pipeline._validate_status_for_document = lambda *args, **kwargs: {
                "name": "Won",
                "auto_create_project": 1,
            }
            pipeline._ensure_opportunity_project = lambda opportunity: {
                "name": "PROJ-1",
                "project_name": "Project One",
                "created": 1,
                "sales_orders_linked": 2,
            }
            pipeline.sync_pipeline_status_assignment = lambda *args, **kwargs: {}
            pipeline._log_status_change = lambda *args, **kwargs: None
            pipeline.list_editable_statuses = lambda *args, **kwargs: [{"name": "Won", "is_active": 1}]
            pipeline._opportunity_card = lambda row, statuses: {"stage": row.get("sales_stage")}

            result = pipeline.update_opportunity_stage("OPP-1", "Won")

            self.assertEqual(doc.sales_stage, "Won")
            self.assertEqual(result["project"]["name"], "PROJ-1")
            self.assertEqual(result["project"]["sales_orders_linked"], 2)
        finally:
            pipeline.frappe.get_doc = original_get_doc
            pipeline._validate_status_for_document = original_validate
            pipeline._ensure_opportunity_project = original_ensure_project
            pipeline.sync_pipeline_status_assignment = original_sync
            pipeline._log_status_change = original_log
            pipeline.list_editable_statuses = original_list
            pipeline._opportunity_card = original_card

    def test_opportunity_payment_check_can_combine_with_submitted_order(self):
        context = {
            "quotations": [],
            "sales_orders": [{"name": "SO-1", "docstatus": 1}],
            "projects": [],
            "payment_entries": [{"name": "PAY-1", "allocated_amount": 100}],
        }

        self.assertTrue(status_checks._run_opportunity_check("has_submitted_sales_order", context))
        self.assertTrue(status_checks._run_opportunity_check("has_submitted_payment", context))

    def test_cancelled_documents_are_visible_only_to_cancellation_checks(self):
        context = {
            "quotations": [{"name": "Q-OPEN", "docstatus": 1, "status": "Open"}],
            "all_quotations": [
                {"name": "Q-OPEN", "docstatus": 1, "status": "Open"},
                {"name": "Q-CANCELLED", "docstatus": 2, "status": "Cancelled"},
            ],
            "sales_orders": [{"name": "SO-OPEN", "docstatus": 1, "status": "To Deliver"}],
            "all_sales_orders": [
                {"name": "SO-OPEN", "docstatus": 1, "status": "To Deliver"},
                {"name": "SO-CANCELLED", "docstatus": 2, "status": "Cancelled"},
            ],
            "projects": [],
            "payment_entries": [],
        }

        self.assertTrue(status_checks._run_opportunity_check("has_quotation", context))
        self.assertTrue(status_checks._run_opportunity_check("has_sales_order", context))
        self.assertFalse(status_checks._run_opportunity_check("no_quotation_cancelled", context))
        self.assertFalse(status_checks._run_opportunity_check("no_sales_order_cancelled", context))

    def test_status_context_fetches_cancelled_rows_separately_from_active_attachments(self):
        calls = []
        original_quotations = status_checks._linked_quotations
        original_sales_orders = status_checks._linked_sales_orders
        original_projects = status_checks._linked_projects
        original_invoices = status_checks._sales_invoices_for_sales_orders
        original_payments = status_checks._project_payment_entries
        try:
            status_checks._linked_quotations = lambda opportunity, include_cancelled=False: [
                {"name": "Q-OPEN", "docstatus": 1, "status": "Open"},
                {"name": "Q-CANCELLED", "docstatus": 2, "status": "Cancelled"},
            ]

            def sales_orders(opportunity, quotation_names, include_cancelled=False):
                calls.append((tuple(quotation_names), include_cancelled))
                rows = [{"name": "SO-OPEN", "docstatus": 1, "status": "To Deliver"}]
                if include_cancelled:
                    rows.append({"name": "SO-CANCELLED", "docstatus": 2, "status": "Cancelled"})
                return rows

            status_checks._linked_sales_orders = sales_orders
            status_checks._linked_projects = lambda rows: []
            status_checks._sales_invoices_for_sales_orders = lambda names: []
            status_checks._project_payment_entries = lambda orders, invoices: []

            context = status_checks._opportunity_check_context(types.SimpleNamespace(name="OPP-1"))

            self.assertEqual(
                calls,
                [
                    (("Q-OPEN", "Q-CANCELLED"), True),
                    (("Q-OPEN",), False),
                ],
            )
            self.assertEqual([row["name"] for row in context["sales_orders"]], ["SO-OPEN"])
            self.assertFalse(status_checks._run_opportunity_check("no_quotation_cancelled", context))
            self.assertFalse(status_checks._run_opportunity_check("no_sales_order_cancelled", context))
        finally:
            status_checks._linked_quotations = original_quotations
            status_checks._linked_sales_orders = original_sales_orders
            status_checks._linked_projects = original_projects
            status_checks._sales_invoices_for_sales_orders = original_invoices
            status_checks._project_payment_entries = original_payments

    def test_payment_check_query_requires_customer_receipt_and_positive_allocation(self):
        queries = []
        original_db = status_checks.frappe.db
        try:
            status_checks.frappe.db = types.SimpleNamespace(
                exists=lambda *args, **kwargs: True,
                sql=lambda query, *args, **kwargs: queries.append(query) or [],
            )

            rows = status_checks._project_payment_entries(["SO-1"], ["SINV-1"])

            self.assertEqual(rows, [])
            query = queries[0]
            self.assertIn("pe.payment_type = 'Receive'", query)
            self.assertIn("pe.party_type = 'Customer'", query)
            self.assertIn("per.allocated_amount > 0", query)
        finally:
            status_checks.frappe.db = original_db

    def test_auto_project_blocks_multiple_projects_for_one_opportunity(self):
        opportunity = types.SimpleNamespace(name="OPP-1")
        original_orders = pipeline._opportunity_sales_orders
        original_source = pipeline._sales_order_source_opportunity
        original_has_field = pipeline._has_field
        original_get_all = pipeline.frappe.get_all
        original_db = pipeline.frappe.db
        try:
            pipeline._opportunity_sales_orders = lambda name: [_Row(name="SO-1", project="PROJ-1")]
            pipeline._sales_order_source_opportunity = lambda name: "OPP-1"
            pipeline._has_field = lambda *args: True
            pipeline.frappe.get_all = lambda *args, **kwargs: [_Row(name="PROJ-1"), _Row(name="PROJ-2")]
            pipeline.frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [])

            with self.assertRaisesRegex(Exception, "multiple Projects"):
                pipeline._ensure_opportunity_project(opportunity)
        finally:
            pipeline._opportunity_sales_orders = original_orders
            pipeline._sales_order_source_opportunity = original_source
            pipeline._has_field = original_has_field
            pipeline.frappe.get_all = original_get_all
            pipeline.frappe.db = original_db

    def test_future_sales_order_from_opportunity_uses_native_project(self):
        class SalesOrder(dict):
            name = "SO-NEW"
            meta = types.SimpleNamespace(get_field=lambda fieldname: fieldname == "project")

            def __setattr__(self, key, value):
                if key in {"name", "meta"}:
                    super().__setattr__(key, value)
                else:
                    self[key] = value

        doc = SalesOrder(
            opportunity="OPP-1",
            project="",
            company="COMP-1",
            customer="CUST-1",
            items=[],
        )
        project = _Row(name="PROJ-1", company="COMP-1", customer="CUST-1")
        original_project_for_opportunity = project_linkage._project_for_opportunity
        original_get_doc = project_linkage.frappe.get_doc
        try:
            project_linkage._project_for_opportunity = lambda opportunity: "PROJ-1"
            project_linkage.frappe.get_doc = lambda doctype, name: project

            project_linkage.link_sales_order_to_project(doc)

            self.assertEqual(doc["project"], "PROJ-1")
            self.assertNotIn("custom_installation_project", doc)
        finally:
            project_linkage._project_for_opportunity = original_project_for_opportunity
            project_linkage.frappe.get_doc = original_get_doc

    def test_sales_order_source_rejects_header_and_quotation_conflict(self):
        class SalesOrder(dict):
            name = "SO-MIXED"

        doc = SalesOrder(
            opportunity="OPP-HEADER",
            items=[{"prevdoc_docname": "Q-OTHER"}],
        )
        original_get_value = project_linkage.frappe.db.get_value
        try:
            project_linkage.frappe.db.get_value = lambda doctype, name, fieldname, **kwargs: (
                "OPP-QUOTATION" if doctype == "Quotation" else None
            )

            with self.assertRaisesRegex(Exception, "conflicting source Opportunities"):
                project_linkage._opportunity_from_sales_order_doc(doc)
        finally:
            project_linkage.frappe.db.get_value = original_get_value

    def test_sales_order_source_rejects_conflicts_across_all_quotation_items(self):
        class SalesOrder(dict):
            name = "SO-MIXED-QUOTATIONS"

        doc = SalesOrder(
            opportunity="",
            items=[
                {"prevdoc_docname": "Q-ONE"},
                {"prevdoc_docname": "Q-TWO"},
            ],
        )
        original_get_value = project_linkage.frappe.db.get_value
        try:
            project_linkage.frappe.db.get_value = lambda doctype, name, fieldname, **kwargs: {
                "Q-ONE": "OPP-1",
                "Q-TWO": "OPP-2",
            }.get(name)

            with self.assertRaisesRegex(Exception, "OPP-1, OPP-2"):
                project_linkage._opportunity_from_sales_order_doc(doc)
        finally:
            project_linkage.frappe.db.get_value = original_get_value

    def test_fanout_discovery_includes_direct_source_and_ignores_cancelled_quotations(self):
        queries = []
        original_db = project_linkage.frappe.db
        original_has_field = project_linkage._has_field
        try:
            project_linkage._has_field = lambda *args: True
            project_linkage.frappe.db = types.SimpleNamespace(
                sql=lambda query, *args, **kwargs: queries.append(query) or [],
            )

            project_linkage.opportunity_sales_orders("OPP-1")

            query = queries[0]
            self.assertIn("so.opportunity = %(opportunity)s", query)
            self.assertIn("q.docstatus < 2", query)
            self.assertIn("so.docstatus < 2", query)
        finally:
            project_linkage.frappe.db = original_db
            project_linkage._has_field = original_has_field

    def test_system_fanout_denies_inaccessible_sales_order_before_mutation(self):
        class Doc(dict):
            def __init__(self, doctype, name, **values):
                super().__init__(values)
                self.doctype = doctype
                self.name = name

        project = Doc("Project", "PROJ-1", company="COMP-1", customer="CUST-1")
        sales_order = Doc("Sales Order", "SO-1", company="COMP-1", customer="CUST-1", project="")
        writes = []
        original_get_doc = project_linkage.frappe.get_doc
        original_has_permission = project_linkage.frappe.has_permission
        original_set_value = project_linkage.frappe.db.set_value
        original_company_access = project_linkage.user_can_access_company
        try:
            project_linkage.frappe.get_doc = lambda doctype, name: sales_order
            project_linkage.frappe.has_permission = lambda *args, **kwargs: False
            project_linkage.frappe.db.set_value = lambda *args, **kwargs: writes.append(args)
            project_linkage.user_can_access_company = lambda company: True

            with self.assertRaisesRegex(Exception, "permission"):
                project_linkage.link_sales_orders_to_project_as_system(project, [{"name": "SO-1"}])

            self.assertEqual(writes, [])
        finally:
            project_linkage.frappe.get_doc = original_get_doc
            project_linkage.frappe.has_permission = original_has_permission
            project_linkage.frappe.db.set_value = original_set_value
            project_linkage.user_can_access_company = original_company_access

    def test_system_fanout_preflights_all_order_company_and_customer_values(self):
        class Doc(dict):
            def __init__(self, doctype, name, **values):
                super().__init__(values)
                self.doctype = doctype
                self.name = name

        project = Doc("Project", "PROJ-1", company="COMP-1", customer="CUST-1")
        orders = {
            "SO-1": Doc("Sales Order", "SO-1", company="COMP-1", customer="CUST-1", project=""),
            "SO-2": Doc("Sales Order", "SO-2", company="COMP-2", customer="CUST-1", project=""),
        }
        writes = []
        original_get_doc = project_linkage.frappe.get_doc
        original_has_permission = project_linkage.frappe.has_permission
        original_set_value = project_linkage.frappe.db.set_value
        original_company_access = project_linkage.user_can_access_company
        try:
            project_linkage.frappe.get_doc = lambda doctype, name: orders[name]
            project_linkage.frappe.has_permission = lambda *args, **kwargs: True
            project_linkage.frappe.db.set_value = lambda *args, **kwargs: writes.append(args)
            project_linkage.user_can_access_company = lambda company: True

            with self.assertRaisesRegex(Exception, "Company does not match"):
                project_linkage.link_sales_orders_to_project_as_system(
                    project,
                    [{"name": "SO-1"}, {"name": "SO-2"}],
                )

            self.assertEqual(writes, [])
        finally:
            project_linkage.frappe.get_doc = original_get_doc
            project_linkage.frappe.has_permission = original_has_permission
            project_linkage.frappe.db.set_value = original_set_value
            project_linkage.user_can_access_company = original_company_access

    def test_blank_source_project_rejects_mixed_attached_opportunity_families(self):
        original_families = project_linkage.project_opportunity_families
        try:
            project_linkage.project_opportunity_families = lambda project: {"OPP-1", "OPP-2"}

            with self.assertRaisesRegex(Exception, "mixed Opportunity families"):
                project_linkage.assert_project_opportunity_family("PROJ-SHARED", "OPP-1")
        finally:
            project_linkage.project_opportunity_families = original_families

    def test_auto_create_does_not_claim_blank_shared_project(self):
        project = _Row(name="PROJ-SHARED", custom_source_opportunity="")
        opportunity = types.SimpleNamespace(name="OPP-1")
        original_orders = pipeline._opportunity_sales_orders
        original_has_field = pipeline._has_field
        original_get_doc = pipeline.frappe.get_doc
        original_db = pipeline.frappe.db
        original_families = project_linkage.project_opportunity_families
        try:
            pipeline._opportunity_sales_orders = lambda name: [_Row(name="SO-1", project="PROJ-SHARED")]
            pipeline._has_field = lambda *args: False
            pipeline.frappe.get_doc = lambda doctype, name: project
            pipeline.frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [])
            project_linkage.project_opportunity_families = lambda name: {"OPP-1", "OPP-2"}

            with self.assertRaisesRegex(Exception, "mixed Opportunity families"):
                pipeline._ensure_opportunity_project(opportunity)

            self.assertEqual(project["custom_source_opportunity"], "")
        finally:
            pipeline._opportunity_sales_orders = original_orders
            pipeline._has_field = original_has_field
            pipeline.frappe.get_doc = original_get_doc
            pipeline.frappe.db = original_db
            project_linkage.project_opportunity_families = original_families

    def test_opportunity_is_locked_before_final_status_checks(self):
        doc = _FakeDoc()
        events = []
        original_db = pipeline.frappe.db
        original_get_doc = pipeline.frappe.get_doc
        original_validate = pipeline._validate_status_for_document
        original_sync = pipeline.sync_pipeline_status_assignment
        original_log = pipeline._log_status_change
        original_list = pipeline.list_editable_statuses
        original_card = pipeline._opportunity_card
        try:
            pipeline.frappe.db = types.SimpleNamespace(
                sql=lambda *args, **kwargs: events.append("lock") or [],
                savepoint=lambda *args, **kwargs: None,
                rollback=lambda *args, **kwargs: None,
            )
            pipeline.frappe.get_doc = lambda *args: doc
            pipeline._validate_status_for_document = lambda *args: events.append("checks") or {"name": "Qualified"}
            pipeline.sync_pipeline_status_assignment = lambda *args, **kwargs: {}
            pipeline._log_status_change = lambda *args, **kwargs: None
            pipeline.list_editable_statuses = lambda *args, **kwargs: [{"name": "Qualified", "is_active": 1}]
            pipeline._opportunity_card = lambda row, statuses: {"stage": row.get("sales_stage")}

            pipeline.update_opportunity_stage("OPP-1", "Qualified")

            self.assertEqual(events[:2], ["lock", "checks"])
        finally:
            pipeline.frappe.db = original_db
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
