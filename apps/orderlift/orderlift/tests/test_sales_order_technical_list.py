import ast
import importlib
import json
import sys
import types
import unittest
from datetime import date, datetime
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SIG_ROOT = APP_ROOT / "orderlift_sig"
DOCTYPE_ROOT = SIG_ROOT / "doctype"


class AttrDict(dict):
    __getattr__ = dict.get


class TestSalesOrderTechnicalListSchema(unittest.TestCase):
    def _doctype(self, folder):
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text())

    def test_parent_is_unique_non_submittable_sales_order_snapshot(self):
        payload = self._doctype("sales_order_technical_list")
        fields = {row["fieldname"]: row for row in payload["fields"]}

        self.assertNotIn("is_submittable", payload)
        self.assertEqual(fields["sales_order"]["options"], "Sales Order")
        self.assertEqual(fields["sales_order"]["reqd"], 1)
        self.assertEqual(fields["sales_order"]["unique"], 1)
        self.assertEqual(fields["sales_order"]["set_only_once"], 1)
        for fieldname in ("company", "customer", "project", "business_type"):
            self.assertEqual(fields[fieldname]["read_only"], 1)
        self.assertEqual(fields["current_revision"]["options"], "Sales Order Technical List Revision")
        self.assertEqual(fields["open_revision"]["options"], "Sales Order Technical List Revision")
        self.assertIn("readiness_summary", fields)

    def test_revision_is_submittable_and_uses_workflow_state_link(self):
        payload = self._doctype("sales_order_technical_list_revision")
        fields = {row["fieldname"]: row for row in payload["fields"]}

        self.assertEqual(payload["is_submittable"], 1)
        self.assertEqual(fields["workflow_state"]["fieldtype"], "Link")
        self.assertEqual(fields["workflow_state"]["options"], "Workflow State")
        self.assertEqual(fields["items"]["options"], "Sales Order Technical List Item")
        self.assertEqual(fields["annexes"]["options"], "Sales Order Technical List Annex")
        self.assertEqual(fields["source_hash"]["read_only"], 1)
        self.assertEqual(fields["approval_hash"]["read_only"], 1)

    def test_item_schema_uses_integrated_source_snapshots(self):
        payload = self._doctype("sales_order_technical_list_item")
        fields = {row["fieldname"]: row for row in payload["fields"]}

        self.assertEqual(payload["istable"], 1)
        self.assertEqual(payload["field_order"][0], "item_code")
        self.assertEqual(fields["line_key"]["reqd"], 1)
        self.assertEqual(fields["line_key"]["hidden"], 1)
        self.assertEqual(fields["sales_order_item"]["hidden"], 1)
        self.assertEqual(fields["sales_order_qty"]["read_only"], 1)
        self.assertEqual(fields["execution_qty"]["reqd"], 1)
        self.assertEqual(fields["execution_qty"]["default"], "1")
        self.assertNotEqual(fields["execution_qty"].get("read_only"), 1)
        self.assertEqual(fields["item_code"]["options"], "Item")
        self.assertEqual(fields["uom"]["in_list_view"], 1)
        for fieldname in ("item_name", "description", "is_stock_item"):
            self.assertEqual(fields[fieldname]["read_only"], 1)
        self.assertNotIn("item", fields)
        self.assertNotIn("source_qty", fields)
        self.assertEqual(fields["procurement_route"]["fieldtype"], "Link")
        self.assertEqual(fields["procurement_route"]["options"], "Technical Procurement Route")
        self.assertNotIn("change_status", fields)
        self.assertNotIn("line_status", fields)

    def test_annex_child_freezes_requirement_and_completion_metadata(self):
        payload = self._doctype("sales_order_technical_list_annex")
        fields = {row["fieldname"]: row for row in payload["fields"]}

        self.assertEqual(payload["istable"], 1)
        for fieldname in (
            "template",
            "annex",
            "source_annex",
            "origin",
            "required_for_revision",
            "must_be_complete",
            "annex_status",
            "is_complete",
            "display_order",
        ):
            self.assertIn(fieldname, fields)
        self.assertEqual(fields["template"]["read_only"], 1)
        self.assertEqual(fields["annex"]["read_only"], 1)

    def test_permissions_use_canonical_roles(self):
        allowed = {
            "Orderlift Admin",
            "System Manager",
            "Installation User",
            "Sales Manager",
            "Sales User",
            "Logistics User",
            "Purchase Manager",
            "Purchase User",
            "Stock Manager",
        }
        for folder in ("sales_order_technical_list", "sales_order_technical_list_revision"):
            payload = self._doctype(folder)
            self.assertTrue({row["role"] for row in payload["permissions"]}.issubset(allowed))


class TestSalesOrderTechnicalListSourceContract(unittest.TestCase):
    def test_service_is_syntax_valid_and_does_not_inspect_roles_or_labels(self):
        path = SIG_ROOT / "technical_list.py"
        source = path.read_text()
        ast.parse(source)

        self.assertNotIn("frappe.get_roles", source)
        self.assertNotIn("frappe.user_roles", source)
        self.assertNotIn("frappe.db.commit", source)
        self.assertNotIn("Distribution", source)
        self.assertNotIn("Installation\"", source)
        for api in (
            "create_for_sales_order",
            "create_revision",
            "sync_revision",
            "get_sales_order_summary",
            "get_project_summaries",
            "get_revision_actions",
            "get_revision_readiness",
        ):
            self.assertIn(f"def {api}(", source)
        self.assertIn("def on_sales_order_submit_or_project_link(", source)

    def test_service_uses_exact_company_fields_and_revision_annex_target(self):
        source = (SIG_ROOT / "technical_list.py").read_text()
        exact_fields = (
            "custom_enable_sales_order_technical_lists",
            "custom_technical_list_effective_from",
            "custom_technical_list_apply_all_business_types",
            "custom_technical_list_business_types",
            "custom_technical_list_require_project",
            "custom_technical_list_auto_create",
            "custom_technical_list_allow_additions",
            "custom_technical_list_allow_exclusions",
            "custom_technical_list_require_change_reason",
            "custom_technical_list_include_non_stock_items",
            "custom_technical_list_default_procurement_route",
            "custom_technical_list_use_stock_planning",
            "custom_technical_list_use_delivery",
        )
        for fieldname in exact_fields:
            self.assertIn(f'"{fieldname}"', source)
        self.assertIn('filters={"target_doctype": REVISION_DOCTYPE}', source)
        self.assertIn("initialize_technical_revision_manifest(", source)
        self.assertIn('"reference_doctype": REVISION_DOCTYPE', source)

    def test_change_reason_is_not_forced_by_company_settings(self):
        source = (SIG_ROOT / "technical_list.py").read_text()
        forced = source.split('for key in ("allow_additions"', 1)[1].split("):", 1)[0]
        self.assertNotIn("require_change_reason", forced)
        backfill = source.split("def _backfill_internal_company_defaults", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("require_change_reason", backfill)
        self.assertIn('"require_change_reason": False', source)

    def test_submit_hash_uses_persisted_revision(self):
        source = (SIG_ROOT / "technical_list.py").read_text()
        body = source.split("def submit_revision", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("persisted = frappe.get_doc(REVISION_DOCTYPE, doc.name)", body)
        self.assertIn("_approval_hash(persisted)", body)
        self.assertNotIn("_synchronize_revision_annex_rows(doc)\n    approval_hash", body)

    def test_downstream_reference_scan_is_none_safe(self):
        source = (SIG_ROOT / "technical_list.py").read_text()
        body = source.split("def _downstream_revision_references", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("frappe.get_all(doctype, filters=filters, fields=[\"name\"], limit=5) or []", body)
        self.assertIn("frappe.db.table_exists(doctype)", body)

    def test_controllers_delegate_lifecycle_hooks(self):
        revision = (
            DOCTYPE_ROOT
            / "sales_order_technical_list_revision"
            / "sales_order_technical_list_revision.py"
        ).read_text()
        for hook in ("after_insert", "before_validate", "validate", "before_submit", "on_submit", "before_cancel", "on_cancel", "after_delete"):
            self.assertIn(f"def {hook}(self)", revision)
        self.assertIn("technical_list.cleanup_revision_pointers(self)", revision)

        client = (
            DOCTYPE_ROOT
            / "sales_order_technical_list_revision"
            / "sales_order_technical_list_revision.js"
        ).read_text()
        self.assertIn('frappe.ui.form.on("Sales Order Technical List Item"', client)
        self.assertIn("items_add(frm, cdt, cdn)", client)
        self.assertIn("async item_code(frm, cdt, cdn)", client)
        self.assertIn("newDesignLineKey()", client)


class TestSalesOrderTechnicalListPureRules(unittest.TestCase):
    MODULE_NAMES = ("frappe", "frappe.utils", "frappe.model", "frappe.model.document", "orderlift.orderlift_sig.technical_list")

    def setUp(self):
        self.original_modules = {name: sys.modules.get(name) for name in self.MODULE_NAMES}
        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda message, *args, **kwargs: message
        frappe_stub.whitelist = lambda *args, **kwargs: args[0] if args and callable(args[0]) else lambda fn: fn
        frappe_stub.db = types.SimpleNamespace(
            savepoint=lambda _name: None,
            rollback=lambda **_kwargs: None,
        )
        sys.modules["frappe"] = frappe_stub

        utils_stub = types.ModuleType("frappe.utils")
        utils_stub.cint = lambda value=0: int(value or 0)
        utils_stub.flt = lambda value=0: float(value or 0)
        utils_stub.getdate = self._getdate
        utils_stub.now_datetime = lambda: "NOW"
        sys.modules["frappe.utils"] = utils_stub

        model_stub = types.ModuleType("frappe.model")
        document_stub = types.ModuleType("frappe.model.document")
        document_stub.Document = object
        sys.modules["frappe.model"] = model_stub
        sys.modules["frappe.model.document"] = document_stub
        sys.modules.pop("orderlift.orderlift_sig.technical_list", None)
        self.module = importlib.import_module("orderlift.orderlift_sig.technical_list")

    def tearDown(self):
        for name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    @staticmethod
    def _getdate(value=None):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date() if value else date.today()

    def test_stable_source_line_key_uses_sales_order_item_name(self):
        row = AttrDict(name="SO-ITEM-0001", idx=1, item_code="ITEM-1")
        self.assertEqual(self.module._stable_line_key("SO-0001", row), "SO-ITEM-0001")
        self.assertEqual(self.module._stable_line_key("SO-0001", row), "SO-ITEM-0001")

    def test_change_type_is_derived_not_stored(self):
        unchanged = AttrDict(sales_order_item="ROW-1", sales_order_qty=2, execution_qty=2, execution_relevant=1)
        modified = AttrDict(sales_order_item="ROW-1", sales_order_qty=2, execution_qty=3, execution_relevant=1)
        excluded = AttrDict(sales_order_item="ROW-1", sales_order_qty=2, execution_qty=0, execution_relevant=0)
        added = AttrDict(sales_order_item=None, sales_order_qty=0, execution_qty=1, execution_relevant=1)

        self.assertEqual(self.module._derive_item_change_type(unchanged), "unchanged")
        self.assertEqual(self.module._derive_item_change_type(modified), "modified")
        self.assertEqual(self.module._derive_item_change_type(excluded), "excluded")
        self.assertEqual(self.module._derive_item_change_type(added), "added")

    def test_source_hash_is_deterministic_and_sensitive_to_source_quantity(self):
        first = AttrDict(
            name="SO-0001",
            company="Orderlift",
            customer="CUST-1",
            project="PROJ-1",
            items=[AttrDict(name="ROW-1", item_code="ITEM-1", qty=2, uom="Nos", conversion_factor=1, stock_uom="Nos")],
        )
        self.module._sales_order_business_type = lambda _doc: "TYPE-1"
        digest = self.module._source_hash(first)
        self.assertEqual(digest, self.module._source_hash(first))
        first["items"][0]["qty"] = 3
        self.assertNotEqual(digest, self.module._source_hash(first))

    def test_sync_preserves_existing_execution_quantity(self):
        class Revision(types.SimpleNamespace):
            def append(self, fieldname, values):
                getattr(self, fieldname).append(AttrDict(values))

        existing = AttrDict(
            line_key="ROW-1",
            sales_order_item="ROW-1",
            item_code="ITEM-1",
            item_name="Item 1",
            description="Source item",
            is_stock_item=1,
            sales_order_qty=2,
            execution_qty=7,
            execution_relevant=1,
            uom="Nos",
            conversion_factor=1,
            stock_uom="Nos",
        )
        revision = Revision(items=[existing], annexes=[])
        source = types.SimpleNamespace(
            name="SO-0001",
            company="Orderlift",
            customer="CUST-1",
            project="PROJ-1",
            delivery_date="2026-09-01",
            items=[
                types.SimpleNamespace(
                    name="ROW-1",
                    item_code="ITEM-1",
                    qty=3,
                    uom="Nos",
                    conversion_factor=1,
                    stock_uom="Nos",
                    warehouse="Stores",
                    delivery_date="2026-09-02",
                )
            ],
        )
        self.module._sales_order_business_type = lambda _doc: "TYPE-1"
        self.module._company_policy = lambda _company: {
            "include_non_stock_items": False,
            "default_procurement_route": "ROUTE-1",
            "use_delivery": False,
        }
        self.module._item_metadata = lambda _codes: {
            "ITEM-1": {"item_name": "Item 1", "description": "Source item", "is_stock_item": 1}
        }
        self.module._revision_template_targets = lambda: {}
        self.module._dynamic_annex_diagnostics = lambda _doc: {"available": False}

        self.module._sync_revision_source(revision, source)

        self.assertEqual(existing.sales_order_qty, 3)
        self.assertEqual(existing.execution_qty, 7)
        self.assertEqual(existing.variance_qty, 4)
        self.assertEqual(existing.required_date, "2026-09-02")

    def test_new_design_item_receives_hidden_identity_and_item_defaults(self):
        row = types.SimpleNamespace(
            line_key="",
            sales_order_item="",
            item_code="ITEM-NEW",
            item_name="",
            description="",
            is_stock_item=0,
            sales_order_qty=0,
            execution_qty=None,
            execution_relevant=None,
            uom="",
            stock_uom="",
            conversion_factor=0,
            procurement_route="",
        )
        doc = types.SimpleNamespace(company="Orderlift", items=[row])
        self.module._item_metadata = lambda _codes: {
            "ITEM-NEW": {
                "item_name": "New Item",
                "description": "Technical item",
                "is_stock_item": 1,
                "stock_uom": "Nos",
            }
        }
        self.module._company_policy = lambda _company: {"default_procurement_route": "STANDARD-MR"}

        self.module.prepare_revision_items(doc)

        self.assertTrue(row.line_key.startswith("ADD-"))
        self.assertEqual(row.item_name, "New Item")
        self.assertEqual(row.uom, "Nos")
        self.assertEqual(row.stock_uom, "Nos")
        self.assertEqual(row.conversion_factor, 1)
        self.assertEqual(row.execution_qty, 1)
        self.assertEqual(row.execution_relevant, 1)
        self.assertEqual(row.procurement_route, "STANDARD-MR")

    def test_readiness_uses_frozen_flags_not_status_labels(self):
        doc = AttrDict(
            items=[AttrDict(line_key="ROW-1")],
            annexes=[
                AttrDict(template="A", annex="ANNEX-1", required_for_revision=1, must_be_complete=1, is_complete=1),
                AttrDict(template="B", annex="ANNEX-2", required_for_revision=1, must_be_complete=0, is_complete=0),
            ],
        )
        self.module._revision_template_targets = lambda: {
            "A": {"required_for_revision": 1},
            "B": {"required_for_revision": 1},
        }
        self.module._dynamic_annex_diagnostics = lambda _doc: {"available": False}
        readiness = self.module._readiness(doc)
        self.assertTrue(readiness["is_ready"])
        self.assertEqual(readiness["required_annex_count"], 2)
        self.assertEqual(readiness["completed_annex_count"], 2)

    def test_company_policy_defaults_disabled_when_metadata_is_absent(self):
        self.module._meta_has_field = lambda *_args: False
        self.module._company_technical_list_business_types = lambda _company: []

        policy = self.module._company_policy("Orderlift")

        self.assertFalse(policy["enabled"])
        self.assertFalse(policy["auto_create"])
        self.assertFalse(policy["include_non_stock_items"])
        self.assertFalse(policy["require_change_reason"])

    def test_company_eligibility_uses_effective_date_project_and_exact_business_type(self):
        policy = {
            "enabled": True,
            "effective_from": "2026-08-01",
            "apply_all_business_types": False,
            "business_types": ["TYPE-ALLOWED"],
            "require_project": True,
        }
        self.module._company_policy = lambda _company: policy
        self.module._meta_has_field = lambda *_args: False
        self.module._sales_order_business_type = lambda doc: doc.business_type
        sales_order = types.SimpleNamespace(
            company="Orderlift",
            transaction_date="2026-08-15",
            project="PROJ-1",
            business_type="TYPE-ALLOWED",
        )

        self.assertEqual(self.module._company_eligibility(sales_order), (True, ""))
        sales_order.business_type = "TYPE-OTHER"
        self.assertFalse(self.module._company_eligibility(sales_order)[0])
        sales_order.business_type = "TYPE-ALLOWED"
        sales_order.project = ""
        self.assertFalse(self.module._company_eligibility(sales_order)[0])
        sales_order.project = "PROJ-1"
        sales_order.transaction_date = "2026-07-31"
        self.assertFalse(self.module._company_eligibility(sales_order)[0])

    def test_non_stock_source_items_follow_exact_company_setting(self):
        stock = AttrDict(name="ROW-1", item_code="STOCK")
        service = AttrDict(name="ROW-2", item_code="SERVICE")
        sales_order = AttrDict(items=[stock, service])
        metadata = {"STOCK": {"is_stock_item": 1}, "SERVICE": {"is_stock_item": 0}}

        included = self.module._eligible_source_items(
            sales_order,
            {"include_non_stock_items": False},
            metadata,
        )
        self.assertEqual([row.name for row in included], ["ROW-1"])
        included = self.module._eligible_source_items(
            sales_order,
            {"include_non_stock_items": True},
            metadata,
        )
        self.assertEqual([row.name for row in included], ["ROW-1", "ROW-2"])

    def test_auto_create_hook_is_quiet_when_disabled_and_logs_enabled_errors(self):
        sales_order = AttrDict(doctype="Sales Order", docstatus=1, name="SO-1", company="Orderlift")
        self.module._company_policy = lambda _company: {"enabled": False, "auto_create": False}
        self.module._get_or_create_for_sales_order = lambda *_args, **_kwargs: self.fail("creation must not run")
        self.assertIsNone(self.module.on_sales_order_submit_or_project_link(sales_order))

        logged = []
        self.module._company_policy = lambda _company: {"enabled": True, "auto_create": True}
        self.module._company_eligibility = lambda _doc: (True, "")
        self.module._get_or_create_for_sales_order = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        self.module.frappe.get_traceback = lambda: "TRACE"
        self.module.frappe.log_error = lambda **kwargs: logged.append(kwargs)
        result = self.module.on_sales_order_submit_or_project_link(sales_order)
        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "boom")
        self.assertEqual(logged[0]["message"], "TRACE")

    def test_approval_hash_captures_submitted_docstatus(self):
        values = {
            "technical_list": "TL-1",
            "sales_order": "SO-1",
            "revision_no": 1,
            "based_on_revision": "",
            "company": "Orderlift",
            "customer": "CUST-1",
            "project": "PROJ-1",
            "business_type": "TYPE-1",
            "source_hash": "SOURCE",
            "workflow_state": "",
            "notes": "",
            "items": [],
            "annexes": [],
        }
        draft = AttrDict(values, docstatus=0)
        submitted = AttrDict(values, docstatus=1)
        self.assertNotEqual(self.module._approval_hash(draft), self.module._approval_hash(submitted))


if __name__ == "__main__":
    unittest.main()
