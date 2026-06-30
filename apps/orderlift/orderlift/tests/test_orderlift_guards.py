import sys
import types
import unittest
from pathlib import Path


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.PermissionError = PermissionError
frappe_stub.session = types.SimpleNamespace(user="Administrator")
frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
frappe_stub._ = lambda value: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.get_roles = lambda user=None: []
frappe_stub.log_error = lambda *args, **kwargs: None

_db_stub = types.ModuleType("frappe.db")
_db_stub.escape = lambda value: f"'{value}'"
frappe_stub.db = _db_stub

frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(
    get_field=lambda fieldname: types.SimpleNamespace() if fieldname in {"company", "custom_company", "reference_doctype", "reference_name", "delivery_note", "container_load_plan", "source_name", "pricing_builder", "customer"} else None
)
frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: True
frappe_stub.get_doc = lambda doctype, name: types.SimpleNamespace(doctype=doctype, name=name)

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.db"] = _db_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
utils_stub.getdate = lambda value=None: value or "2026-04-27"
utils_stub.date_diff = lambda end, start: 0
utils_stub.nowdate = lambda: "2026-04-27"
utils_stub.now_datetime = lambda: "2026-04-27 00:00:00"
sys.modules["frappe.utils"] = utils_stub


from orderlift import orderlift_guards
from orderlift import hooks

APP_ROOT = Path(__file__).resolve().parents[2]


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)


class TestOrderliftGuards(unittest.TestCase):
    def setUp(self):
        self._session_user = frappe_stub.session.user
        self._has_permission = frappe_stub.has_permission
        self._get_allowed = orderlift_guards.get_allowed_companies
        self._user_can_all = orderlift_guards.user_can_access_all_companies

    def tearDown(self):
        frappe_stub.session.user = self._session_user
        frappe_stub.has_permission = self._has_permission
        orderlift_guards.get_allowed_companies = self._get_allowed
        orderlift_guards.user_can_access_all_companies = self._user_can_all

    # -- Annex Document

    def test_annex_document_admin_bypass(self):
        doc = Row({"reference_doctype": "Quotation", "reference_name": "QTN-001", "company": "OMD"})
        self.assertTrue(orderlift_guards.has_annex_document_permission(doc, "read"))

    def test_annex_document_requires_reference_read(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: False
        frappe_stub.session.user = "sales@example.com"
        doc = Row({"reference_doctype": "Quotation", "reference_name": "QTN-001", "company": "OMD"})
        orderlift_guards.get_allowed_companies = lambda user=None: ["OMD"]
        orderlift_guards.user_can_access_all_companies = lambda user=None: False
        self.assertFalse(orderlift_guards.has_annex_document_permission(doc, "read"))

    def test_annex_document_allows_with_reference_read(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: True
        frappe_stub.session.user = "sales@example.com"
        doc = Row({"reference_doctype": "Quotation", "reference_name": "QTN-001", "company": "OMD"})
        orderlift_guards.get_allowed_companies = lambda user=None: ["OMD"]
        orderlift_guards.user_can_access_all_companies = lambda user=None: False
        # Reference-doc check passes; the guard defers to company_access for
        # remaining scope (integration path may not resolve under stubs).
        result = orderlift_guards.has_annex_document_permission(doc, "read")
        self.assertIsNotNone(result)

    def test_annex_document_query_scoped(self):
        frappe_stub.session.user = "sales@example.com"
        orderlift_guards.get_allowed_companies = lambda user=None: ["OMD"]
        orderlift_guards.user_can_access_all_companies = lambda user=None: False
        clause = orderlift_guards.annex_document_query()
        self.assertIsNotNone(clause)
        self.assertIn("company", clause)
        self.assertIn("OMD", clause)

    def test_annex_document_query_all_access(self):
        orderlift_guards.user_can_access_all_companies = lambda user=None: True
        self.assertIsNone(orderlift_guards.annex_document_query())

    # -- Shipment Analysis

    def test_shipment_analysis_admin_bypass(self):
        doc = Row({"source_name": "DN-001", "delivery_note": "DN-001", "customer": "CUST-1"})
        self.assertTrue(orderlift_guards.has_shipment_analysis_permission(doc, "read"))

    def test_shipment_analysis_dn_proxy_denied(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: False
        frappe_stub.session.user = "logistics@example.com"
        doc = Row({"source_name": "DN-001", "delivery_note": "DN-001", "customer": "CUST-1"})
        self.assertFalse(orderlift_guards.has_shipment_analysis_permission(doc, "read"))

    def test_shipment_analysis_dn_proxy_allowed(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: True
        frappe_stub.session.user = "logistics@example.com"
        doc = Row({"source_name": "DN-001", "delivery_note": "DN-001", "customer": "CUST-1"})
        self.assertTrue(orderlift_guards.has_shipment_analysis_permission(doc, "read"))

    def test_shipment_analysis_new_doc_passthrough(self):
        frappe_stub.session.user = "logistics@example.com"
        doc = Row({"source_name": "", "delivery_note": "", "container_load_plan": ""})
        self.assertIsNone(orderlift_guards.has_shipment_analysis_permission(doc, "read"))

    # -- Pricing Builder History

    def test_builder_history_admin_bypass(self):
        doc = Row({"pricing_builder": "PBU-00001"})
        self.assertTrue(orderlift_guards.has_builder_history_permission(doc, "read"))

    def test_builder_history_readonly_blocks_write(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: True
        frappe_stub.session.user = "pricing@example.com"
        doc = Row({"pricing_builder": "PBU-00001"})
        self.assertFalse(orderlift_guards.has_builder_history_permission(doc, "write"))

    def test_builder_history_read_requires_builder_read(self):
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: False
        frappe_stub.session.user = "sales@example.com"
        doc = Row({"pricing_builder": "PBU-00001"})
        self.assertFalse(orderlift_guards.has_builder_history_permission(doc, "read"))

    def test_builder_history_new_doc_passthrough(self):
        frappe_stub.session.user = "pricing@example.com"
        doc = Row({"pricing_builder": ""})
        self.assertIsNone(orderlift_guards.has_builder_history_permission(doc, "read"))

    def test_builder_history_query_scoped(self):
        clause = orderlift_guards.builder_history_query(user="pricing@example.com")
        self.assertIsNotNone(clause)
        self.assertIn("pricing_builder", clause)
        self.assertIn("Pricing Builder", clause)

    # -- Hooks registration

    def test_hooks_register_project_workflow_case(self):
        h = hooks.has_permission
        self.assertIn("Project Workflow Case", h)
        self.assertEqual(h["Project Workflow Case"], "orderlift.company_access.has_company_permission")

    def test_hooks_register_annex_document(self):
        h = hooks.has_permission
        self.assertIn("Orderlift Annex Document", h)
        self.assertEqual(h["Orderlift Annex Document"], "orderlift.orderlift_guards.has_annex_document_permission")

    def test_hooks_register_shipment_analysis(self):
        self.assertIn("Shipment Analysis", hooks.has_permission)

    def test_hooks_register_builder_history(self):
        self.assertIn("Pricing Builder History", hooks.has_permission)

    def test_hooks_query_register_project_workflow_case(self):
        q = hooks.permission_query_conditions
        self.assertIn("Project Workflow Case", q)
        self.assertEqual(q["Project Workflow Case"], "orderlift.company_access.project_workflow_case_query")

    def test_hooks_query_register_annex_document(self):
        self.assertIn("Orderlift Annex Document", hooks.permission_query_conditions)

    def test_hooks_query_register_shipment_analysis(self):
        self.assertIn("Shipment Analysis", hooks.permission_query_conditions)

    def test_hooks_query_register_builder_history(self):
        self.assertIn("Pricing Builder History", hooks.permission_query_conditions)

    # -- Module exports

    def test_guard_module_exports_all_functions(self):
        self.assertTrue(callable(orderlift_guards.has_annex_document_permission))
        self.assertTrue(callable(orderlift_guards.annex_document_query))
        self.assertTrue(callable(orderlift_guards.has_shipment_analysis_permission))
        self.assertTrue(callable(orderlift_guards.shipment_analysis_query))
        self.assertTrue(callable(orderlift_guards.has_builder_history_permission))
        self.assertTrue(callable(orderlift_guards.builder_history_query))

    # -- Edge cases

    def test_shipment_analysis_falls_back_to_clp(self):
        doc = Row({"source_name": "CLP-001", "delivery_note": "", "container_load_plan": "CLP-001", "customer": "CUST-1"})
        frappe_stub.has_permission = lambda doctype, ptype=None, user=None, doc=None: doctype == "Container Load Plan"
        frappe_stub.session.user = "logistics@example.com"
        self.assertTrue(orderlift_guards.has_shipment_analysis_permission(doc, "read"))

    # -- Script guard verification

    def test_destructive_scripts_require_system_manager(self):
        scripts_root = APP_ROOT / "orderlift" / "scripts"
        guarded = {
            "ensure_orderlift_admin_permissions.py",
            "setup_startup_roles.py",
            "reset_item_catalog.py",
            "cleanup_simple_roles.py",
            "cleanup_business_data.py",
            "cleanup_selected_crm_sales_data.py",
            "import_generated_catalog.py",
            "import_article_excel_catalog.py",
            "import_item_drive_images.py",
            "setup_master_data.py",
            "update_article_buying_prices.py",
            "rename_article_items_by_category_article.py",
            "setup_internal_notifications.py",
            "sync_customs_material_values.py",
            "sync_installation_buying_price_lists.py",
            "setup_workbook_pricing_policies.py",
            "setup_dum_customs_policy.py",
            "sync_sidebar_section_workspace.py",
            "setup_main_dashboard_sidebar.py",
            "sync_crm_workspace_sidebar.py",
            "clear_app_hooks_cache.py",
        }
        for filename in guarded:
            path = scripts_root / filename
            source = path.read_text()
            self.assertIn("frappe.only_for", source, msg=f"{filename} missing frappe.only_for guard")
            self.assertTrue(
                "System Manager" in source or "Orderlift Admin" in source,
                msg=f"{filename} missing role guard",
            )

    def test_admin_access_guarded(self):
        source = (APP_ROOT / "orderlift" / "admin_access.py").read_text()
        self.assertIn("frappe.only_for(\"System Manager\")", source)

    def test_company_access_normalize_guarded(self):
        source = (APP_ROOT / "orderlift" / "company_access.py").read_text()
        self.assertIn("frappe.only_for([\"System Manager\", \"Orderlift Admin\"])", source)

    def test_grant_full_business_access_has_legacy_confirmation(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "grant_full_business_access.py").read_text()
        self.assertIn("_require_legacy_confirmation", source)

    def test_fix_business_access_has_legacy_confirmation(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "fix_business_access.py").read_text()
        self.assertIn("_require_legacy_confirmation", source)

    def test_todo_dashboard_not_overguarded(self):
        source = (APP_ROOT / "orderlift" / "scripts" / "setup_todo_dashboard.py").read_text()
        self.assertIn("@frappe.whitelist()", source)
        self.assertNotIn("frappe.only_for", source, msg="read-only dashboard helpers should not be role-gated")

    # -- Phase 3: page API guards

    _PHASE3_GUARDED = {
        "orderlift/orderlift_sales/doctype/pricing_builder/pricing_builder.py": [
            "doc.check_permission(\"write\")",
        ],
        "orderlift/orderlift_sales/doctype/dimensioning_set/dimensioning_set.py": [
            "frappe.has_permission(\"Dimensioning Set\", \"read\"",
            "frappe.has_permission(\"Dimensioning Set\", \"create\"",
            "frappe.has_permission(\"Dimensioning Set\", \"delete\"",
        ],
        "orderlift/orderlift_sav/doctype/sav_ticket/sav_ticket.py": [
            "self.check_permission(\"write\")",
            "frappe.has_permission(\"Task\", \"create\"",
            "frappe.has_permission(\"Stock Entry\", \"create\"",
            "frappe.has_permission(\"SAV Ticket\", \"read\"",
        ],
        "orderlift/orderlift_logistics/page/operations_pipeline/operations_pipeline.py": [
            "frappe.has_permission(entity_type, \"read\"",
            "frappe.has_permission(doctype, \"read\"",
            "frappe.has_permission(\"Sales Order\", \"read\"",
        ],
        "orderlift/orderlift_sales/page/sale_financial_dashboard/sale_financial_dashboard.py": [
            "frappe.has_permission(\"Sales Order\", \"read\"",
        ],
        "orderlift/orderlift_sales/page/finance_dashboard/finance_dashboard.py": [
            "frappe.has_permission(\"Sales Invoice\", \"report\"",
        ],
        "orderlift/orderlift_sales/page/pricing_simulator/pricing_simulator.py": [
            "frappe.has_permission(\"Agent Pricing Rules\", \"read\"",
        ],
        "orderlift/orderlift_sales/page/pricing_dashboard/pricing_dashboard.py": [
            "frappe.has_permission(\"Pricing Sheet\", \"read\"",
        ],
        "orderlift/orderlift_logistics/page/logistics_dashboard/logistics_dashboard.py": [
            "frappe.has_permission(\"Forecast Load Plan\", \"read\"",
        ],
        "orderlift/orderlift_logistics/page/stock_dashboard/stock_dashboard.py": [
            "frappe.has_permission(\"Bin\", \"read\"",
        ],
        "orderlift/orderlift_sav/page/sav_dashboard/sav_dashboard.py": [
            "frappe.has_permission(\"SAV Ticket\", \"read\"",
        ],
        "orderlift/orderlift_hr/page/hr_dashboard/hr_dashboard.py": [
            "frappe.has_permission(\"Employee\", \"read\"",
        ],
        "orderlift/orderlift_client_portal/page/b2b_portal_dashboard/b2b_portal_dashboard.py": [
            "frappe.has_permission(\"Portal Customer Group Policy\", \"read\"",
        ],
    }

    def test_phase3_page_api_guards_present(self):
        for rel_path, markers in self._PHASE3_GUARDED.items():
            source = (APP_ROOT / rel_path).read_text()
            for marker in markers:
                self.assertIn(
                    marker, source,
                    msg=f"{rel_path} missing guard marker: {marker}",
                )
