import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FrappeValidationError(Exception):
    pass


class FrappeLinkExistsError(FrappeValidationError):
    pass


class FakeDocStatus(int):
    def __new__(cls, value=0):
        return super().__new__(cls, int(value or 0))

    def is_cancelled(self):
        return self == 2

    def is_submitted(self):
        return self == 1


class FakeDB:
    def __init__(self):
        self.values = []
        self.exists_result = True
        self.get_values_calls = []
        self.exists_calls = []
        self.set_value_calls = []
        self.sql_calls = []
        self.savepoints = []
        self.rollbacks = []

    def get_values(self, *args, **kwargs):
        self.get_values_calls.append((args, kwargs))
        return list(self.values)

    def get_value(self, *args, **kwargs):
        return 0

    def exists(self, *args, **kwargs):
        self.exists_calls.append((args, kwargs))
        return self.exists_result

    def set_value(self, *args, **kwargs):
        self.set_value_calls.append((args, kwargs))

    def get_single_value(self, *args, **kwargs):
        return None

    def get_singles_dict(self, *args, **kwargs):
        return {}

    def savepoint(self, name):
        self.savepoints.append(name)

    def rollback(self, *, save_point=None, **kwargs):
        self.rollbacks.append(save_point)

    def sql(self, *args, **kwargs):
        self.sql_calls.append((args, kwargs))


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda message, *args, **kwargs: message
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
frappe_stub.PermissionError = type("PermissionError", (Exception,), {})
frappe_stub.LinkExistsError = FrappeLinkExistsError
frappe_stub.ValidationError = FrappeValidationError
frappe_stub.session = types.SimpleNamespace(user="user@example.com")
frappe_stub.db = FakeDB()
frappe_stub.parse_json = json.loads
frappe_stub.clear_last_message = lambda: None
frappe_stub.get_hooks = lambda key: []
frappe_stub.has_permission = lambda *args, **kwargs: True
frappe_stub.get_roles = lambda user=None: []
frappe_stub.get_doc = lambda doctype, name: types.SimpleNamespace(doctype=doctype, name=name)
frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(
    istable=False,
    issingle=False,
    is_submittable=False,
    get_field=lambda fieldname: types.SimpleNamespace(label=fieldname.replace("_", " ").title()),
)


def frappe_throw(message, exc=FrappeValidationError, *args, **kwargs):
    raise exc(message)


frappe_stub.throw = frappe_throw
frappe_stub.delete_doc = lambda doctype, name: None

model_stub = types.ModuleType("frappe.model")
delete_doc_stub = types.ModuleType("frappe.model.delete_doc")
delete_doc_stub.check_permission_and_not_submitted = lambda doc: None
docstatus_stub = types.ModuleType("frappe.model.docstatus")
docstatus_stub.DocStatus = FakeDocStatus
dynamic_links_stub = types.ModuleType("frappe.model.dynamic_links")
dynamic_links_stub.get_dynamic_link_map = lambda: {}
rename_doc_stub = types.ModuleType("frappe.model.rename_doc")
rename_doc_stub.get_link_fields = lambda doctype: []

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.model"] = model_stub
sys.modules["frappe.model.delete_doc"] = delete_doc_stub
sys.modules["frappe.model.docstatus"] = docstatus_stub
sys.modules["frappe.model.dynamic_links"] = dynamic_links_stub
sys.modules["frappe.model.rename_doc"] = rename_doc_stub


from orderlift import delete_blocker_helper


APP_ROOT = Path(__file__).resolve().parents[2]


def blocker(doctype, name, can_delete=True):
    return {
        "doctype": doctype,
        "name": name,
        "reasons": [],
        "can_delete": can_delete,
    }


def source_ledger(doctype, name):
    return {
        "doctype": doctype,
        "name": name,
        "reasons": [{"link_doctype": doctype, "fieldname": "voucher_no", "doctype_fieldname": "voucher_type"}],
    }


class TestDeleteBlockerDiscovery(unittest.TestCase):
    def setUp(self):
        frappe_stub.db = FakeDB()
        frappe_stub.has_permission = lambda *args, **kwargs: True
        frappe_stub.get_hooks = lambda key: []
        frappe_stub.session.user = "user@example.com"

    def test_static_links_include_all_matching_records(self):
        doc = types.SimpleNamespace(doctype="Customer", name="CUST-1")
        frappe_stub.db.values = [
            {"name": "QTN-1", "docstatus": 0},
            {"name": "QTN-2", "docstatus": 2},
        ]
        link_fields = [{"parent": "Quotation", "fieldname": "customer", "issingle": 0}]

        with patch.object(delete_blocker_helper, "get_link_fields", return_value=link_fields):
            result = delete_blocker_helper._discover_blockers(doc)

        self.assertEqual([(row["doctype"], row["name"]) for row in result], [
            ("Quotation", "QTN-1"),
            ("Quotation", "QTN-2"),
        ])

    def test_dynamic_links_ignore_cancelled_records(self):
        doc = types.SimpleNamespace(doctype="Customer", name="CUST-1")
        frappe_stub.db.values = [
            {"name": "NOTE-1", "docstatus": 0},
            {"name": "NOTE-2", "docstatus": 2},
        ]
        field = types.SimpleNamespace(
            parent="Note",
            options="reference_doctype",
            fieldname="reference_name",
        )

        with patch.object(delete_blocker_helper, "get_dynamic_link_map", return_value={"Customer": [field]}):
            result = delete_blocker_helper._discover_blockers(doc)

        self.assertEqual([(row["doctype"], row["name"]) for row in result], [("Note", "NOTE-1")])

    def test_duplicate_links_are_combined_with_all_reasons(self):
        doc = types.SimpleNamespace(doctype="Customer", name="CUST-1")
        frappe_stub.db.values = [{"name": "QTN-1", "docstatus": 0}]
        link_fields = [
            {"parent": "Quotation", "fieldname": "customer", "issingle": 0},
            {"parent": "Quotation", "fieldname": "party_name", "issingle": 0},
        ]

        with patch.object(delete_blocker_helper, "get_link_fields", return_value=link_fields):
            result = delete_blocker_helper._discover_blockers(doc)

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["reasons"]), 2)

    def test_ignored_link_doctype_is_not_returned(self):
        doc = types.SimpleNamespace(doctype="Customer", name="CUST-1")
        frappe_stub.db.values = [{"name": "TODO-1", "docstatus": 0}]
        frappe_stub.get_hooks = lambda key: ["ToDo"]
        link_fields = [{"parent": "ToDo", "fieldname": "reference_name", "issingle": 0}]

        with patch.object(delete_blocker_helper, "get_link_fields", return_value=link_fields):
            result = delete_blocker_helper._discover_blockers(doc)

        self.assertEqual(result, [])

    def test_outgoing_parent_links_are_not_delete_blockers(self):
        doc = types.SimpleNamespace(
            doctype="Quotation",
            name="QTN-1",
            customer="CUST-1",
            opportunity="OPP-1",
        )

        with patch.object(delete_blocker_helper, "get_link_fields", return_value=[]):
            result = delete_blocker_helper._discover_blockers(doc)

        self.assertEqual(result, [])
        self.assertEqual(frappe_stub.db.get_values_calls, [])

    def test_restricted_blocker_details_are_not_returned(self):
        rows = [
            {"doctype": "Quotation", "name": "VISIBLE", "reasons": []},
            {"doctype": "Sales Order", "name": "SECRET", "reasons": []},
        ]
        frappe_stub.has_permission = lambda doctype, ptype, doc=None: doc != "SECRET"

        visible, restricted = delete_blocker_helper._classify_blockers(rows)

        self.assertEqual(restricted, 1)
        self.assertEqual([row["name"] for row in visible], ["VISIBLE"])
        self.assertNotIn("SECRET", repr(visible))

    def test_non_privileged_submitted_blocker_has_exact_lock_reason(self):
        rows = [{"doctype": "Quotation", "name": "QTN-1", "reasons": []}]

        with (
            patch.object(delete_blocker_helper, "_can_override_submitted_deletion", return_value=False),
            patch.object(delete_blocker_helper, "_is_submitted", return_value=True),
        ):
            visible, restricted = delete_blocker_helper._classify_blockers(rows)

        self.assertEqual(restricted, 0)
        self.assertFalse(visible[0]["can_delete"])
        self.assertEqual(visible[0]["lock_reason"], "submitted")

    def test_privileged_blocker_can_override_submission_and_delete_permission(self):
        rows = [{"doctype": "Quotation", "name": "QTN-1", "reasons": []}]
        frappe_stub.has_permission = lambda doctype, ptype, doc=None: ptype == "read"

        with (
            patch.object(delete_blocker_helper, "_can_override_submitted_deletion", return_value=True),
            patch.object(delete_blocker_helper, "_is_submitted", return_value=True),
        ):
            visible, restricted = delete_blocker_helper._classify_blockers(rows)

        self.assertEqual(restricted, 0)
        self.assertTrue(visible[0]["can_delete"])
        self.assertEqual(visible[0]["override_reasons"], ["delete_permission", "submitted"])

    def test_master_records_are_not_cascade_deletable(self):
        rows = [
            {"doctype": "Prospect", "name": "PROSPECT-1", "reasons": []},
            {"doctype": "Customer", "name": "CUSTOMER-1", "reasons": []},
            {"doctype": "Contact", "name": "CONTACT-1", "reasons": []},
        ]

        with patch.object(delete_blocker_helper, "_can_override_submitted_deletion", return_value=True):
            visible, restricted = delete_blocker_helper._classify_blockers(rows)

        self.assertEqual(restricted, 0)
        self.assertEqual([row["lock_reason"] for row in visible], ["reference_doctype"] * 3)
        self.assertFalse(any(row["can_delete"] for row in visible))

    def test_ledger_records_are_not_cascade_deletable(self):
        rows = [
            {"doctype": "Advance Payment Ledger Entry", "name": "APLE-1", "reasons": []},
            {"doctype": "GL Entry", "name": "GLE-1", "reasons": []},
            {"doctype": "Payment Ledger Entry", "name": "PLE-1", "reasons": []},
        ]

        with patch.object(delete_blocker_helper, "_can_override_submitted_deletion", return_value=True):
            visible, restricted = delete_blocker_helper._classify_blockers(rows)

        self.assertEqual(restricted, 0)
        self.assertEqual([row["lock_reason"] for row in visible], ["ledger_doctype"] * 3)
        self.assertFalse(any(row["can_delete"] for row in visible))

    def test_hierarchy_discovers_shared_nested_blockers_once_and_orders_dependencies_first(self):
        root = types.SimpleNamespace(doctype="Purchase Receipt", name="PR-1")
        docs = {
            ("Purchase Invoice", "PI-1"): types.SimpleNamespace(doctype="Purchase Invoice", name="PI-1"),
            ("Payment Request", "PRQ-1"): types.SimpleNamespace(doctype="Payment Request", name="PRQ-1"),
            ("Payment Entry", "PE-1"): types.SimpleNamespace(doctype="Payment Entry", name="PE-1"),
        }
        direct = {
            ("Purchase Receipt", "PR-1"): [
                {"doctype": "Purchase Invoice", "name": "PI-1", "reasons": []},
            ],
            ("Purchase Invoice", "PI-1"): [
                {"doctype": "Payment Request", "name": "PRQ-1", "reasons": []},
                {"doctype": "Payment Entry", "name": "PE-1", "reasons": []},
            ],
            ("Payment Request", "PRQ-1"): [
                {"doctype": "Payment Entry", "name": "PE-1", "reasons": []},
            ],
            ("Payment Entry", "PE-1"): [],
        }

        with (
            patch.object(
                delete_blocker_helper,
                "_discover_blockers",
                side_effect=lambda doc: direct[(doc.doctype, doc.name)],
            ),
            patch.object(
                frappe_stub,
                "get_doc",
                side_effect=lambda doctype, name: docs[(doctype, name)],
            ),
        ):
            rows, dependencies = delete_blocker_helper._discover_blocker_hierarchy(root)
            order = delete_blocker_helper._dependency_first_order(
                (root.doctype, root.name),
                dependencies,
            )

        self.assertEqual(
            {(row["doctype"], row["name"]) for row in rows},
            {("Purchase Invoice", "PI-1"), ("Payment Request", "PRQ-1"), ("Payment Entry", "PE-1")},
        )
        self.assertEqual(order, [
            ("Payment Entry", "PE-1"),
            ("Payment Request", "PRQ-1"),
            ("Purchase Invoice", "PI-1"),
        ])

    def test_hierarchy_does_not_expand_master_record_blockers(self):
        root = types.SimpleNamespace(doctype="Opportunity", name="OPP-1")
        direct = {
            ("Opportunity", "OPP-1"): [
                {"doctype": "Prospect", "name": "PROSPECT-1", "reasons": []},
                {"doctype": "Quotation", "name": "QTN-1", "reasons": []},
            ],
            ("Prospect", "PROSPECT-1"): [
                {"doctype": "Opportunity", "name": "OPP-OTHER", "reasons": []},
            ],
            ("Quotation", "QTN-1"): [],
        }
        docs = {
            ("Quotation", "QTN-1"): types.SimpleNamespace(doctype="Quotation", name="QTN-1"),
        }

        with (
            patch.object(
                delete_blocker_helper,
                "_discover_blockers",
                side_effect=lambda doc: direct[(doc.doctype, doc.name)],
            ),
            patch.object(
                frappe_stub,
                "get_doc",
                side_effect=lambda doctype, name: docs[(doctype, name)],
            ),
        ):
            rows, dependencies = delete_blocker_helper._discover_blocker_hierarchy(root)

        self.assertEqual(
            {(row["doctype"], row["name"]) for row in rows},
            {("Prospect", "PROSPECT-1"), ("Quotation", "QTN-1")},
        )
        self.assertNotIn(("Opportunity", "OPP-OTHER"), dependencies)

    def test_hierarchy_skips_ledger_rows_as_source_voucher_artifacts(self):
        root = types.SimpleNamespace(doctype="Opportunity", name="OPP-1")
        direct = {
            ("Opportunity", "OPP-1"): [
                {"doctype": "Sales Invoice", "name": "SINV-1", "reasons": []},
            ],
            ("Sales Invoice", "SINV-1"): [
                source_ledger("GL Entry", "GLE-1"),
                source_ledger("Payment Ledger Entry", "PLE-1"),
            ],
        }
        docs = {
            ("Sales Invoice", "SINV-1"): types.SimpleNamespace(doctype="Sales Invoice", name="SINV-1"),
        }

        with (
            patch.object(
                delete_blocker_helper,
                "_discover_blockers",
                side_effect=lambda doc: direct[(doc.doctype, doc.name)],
            ),
            patch.object(
                frappe_stub,
                "get_doc",
                side_effect=lambda doctype, name: docs[(doctype, name)],
            ),
        ):
            rows, dependencies = delete_blocker_helper._discover_blocker_hierarchy(root)

        self.assertEqual(
            {(row["doctype"], row["name"]) for row in rows},
            {("Sales Invoice", "SINV-1")},
        )
        self.assertEqual(dependencies[("Sales Invoice", "SINV-1")], [])

    def test_hierarchy_keeps_non_source_ledger_rows_as_locked_blockers(self):
        root = types.SimpleNamespace(doctype="Item", name="ITEM-1")
        direct = {
            ("Item", "ITEM-1"): [
                {
                    "doctype": "Stock Ledger Entry",
                    "name": "SLE-1",
                    "reasons": [{"link_doctype": "Stock Ledger Entry", "fieldname": "item_code"}],
                },
            ],
        }

        with patch.object(
            delete_blocker_helper,
            "_discover_blockers",
            side_effect=lambda doc: direct[(doc.doctype, doc.name)],
        ):
            rows, dependencies = delete_blocker_helper._discover_blocker_hierarchy(root)

        self.assertEqual([(row["doctype"], row["name"]) for row in rows], [("Stock Ledger Entry", "SLE-1")])
        self.assertEqual(dependencies[("Stock Ledger Entry", "SLE-1")], [])


class TestDeleteBlockerAction(unittest.TestCase):
    def setUp(self):
        frappe_stub.db = FakeDB()
        frappe_stub.delete_doc = lambda doctype, name: None
        self.parent = types.SimpleNamespace(doctype="Customer", name="CUST-1")
        override_patch = patch.object(delete_blocker_helper, "_can_override_submitted_deletion", return_value=False)
        override_patch.start()
        self.addCleanup(override_patch.stop)

    def action_patches(self, current, visible=None, restricted=0):
        root_key = (self.parent.doctype, self.parent.name)
        dependencies = {root_key: [(row["doctype"], row["name"]) for row in current]}
        dependencies.update({(row["doctype"], row["name"]): [] for row in current})
        return (
            patch.object(delete_blocker_helper, "_get_parent", return_value=self.parent),
            patch.object(
                delete_blocker_helper,
                "_discover_blocker_hierarchy",
                side_effect=[(current, dependencies), ([], {root_key: []})],
            ),
            patch.object(
                delete_blocker_helper,
                "_classify_blockers",
                return_value=(visible if visible is not None else [blocker(row["doctype"], row["name"]) for row in current], restricted),
            ),
        )

    def test_preview_with_no_blockers_keeps_native_delete_path_available(self):
        with patch.object(delete_blocker_helper, "_get_parent", return_value=self.parent):
            with patch.object(
                delete_blocker_helper,
                "_discover_blocker_hierarchy",
                return_value=([], {(self.parent.doctype, self.parent.name): []}),
            ):
                result = delete_blocker_helper.get_delete_blockers("Customer", "CUST-1")

        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["restricted_blocker_count"], 0)

    def test_privileged_preview_reports_hidden_source_ledger_blockers(self):
        direct_blockers = [
            source_ledger("GL Entry", "GLE-1"),
            source_ledger("Payment Ledger Entry", "PLE-1"),
        ]

        with (
            patch.object(delete_blocker_helper, "_can_override_submitted_deletion", return_value=True),
            patch.object(delete_blocker_helper, "_get_parent", return_value=self.parent),
            patch.object(delete_blocker_helper, "_discover_blockers", return_value=direct_blockers),
            patch.object(
                delete_blocker_helper,
                "_discover_blocker_hierarchy",
                return_value=([], {(self.parent.doctype, self.parent.name): []}),
            ),
        ):
            result = delete_blocker_helper.get_delete_blockers("Payment Entry", "PE-1")

        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["source_ledger_blocker_count"], 2)

    def test_parent_delete_permission_is_required_for_preview(self):
        with patch.object(
            delete_blocker_helper,
            "check_permission_and_not_submitted",
            side_effect=frappe_stub.PermissionError("denied"),
        ):
            with self.assertRaises(frappe_stub.PermissionError):
                delete_blocker_helper.get_delete_blockers("Customer", "CUST-1")

    def test_forged_or_stale_selection_is_rejected_before_deletion(self):
        current = [{"doctype": "Quotation", "name": "QTN-1", "reasons": []}]
        deleted = []
        frappe_stub.delete_doc = lambda doctype, name: deleted.append((doctype, name))
        parent_patch, discover_patch, classify_patch = self.action_patches(current)

        with parent_patch, discover_patch, classify_patch:
            with self.assertRaises(FrappeValidationError):
                delete_blocker_helper.delete_blockers_and_parent(
                    "Customer",
                    "CUST-1",
                    [{"doctype": "Quotation", "name": "QTN-FORGED"}],
                )

        self.assertEqual(deleted, [])

    def test_non_deletable_or_restricted_blocker_stops_action(self):
        current = [{"doctype": "Quotation", "name": "QTN-1", "reasons": []}]
        visible = [blocker("Quotation", "QTN-1", can_delete=False)]
        parent_patch, discover_patch, classify_patch = self.action_patches(current, visible=visible)

        with parent_patch, discover_patch, classify_patch:
            with self.assertRaises(frappe_stub.PermissionError):
                delete_blocker_helper.delete_blockers_and_parent(
                    "Customer",
                    "CUST-1",
                    [{"doctype": "Quotation", "name": "QTN-1"}],
                )

    def test_selected_blockers_and_parent_use_native_delete(self):
        current = [
            {"doctype": "Quotation", "name": "QTN-1", "reasons": []},
            {"doctype": "Sales Order", "name": "SO-1", "reasons": []},
        ]
        deleted = []
        frappe_stub.delete_doc = lambda doctype, name: deleted.append((doctype, name))
        parent_patch, discover_patch, classify_patch = self.action_patches(current)

        with parent_patch, discover_patch, classify_patch:
            result = delete_blocker_helper.delete_blockers_and_parent(
                "Customer",
                "CUST-1",
                [
                    {"doctype": "Quotation", "name": "QTN-1"},
                    {"doctype": "Sales Order", "name": "SO-1"},
                ],
            )

        self.assertEqual(deleted[-1], ("Customer", "CUST-1"))
        self.assertEqual(len(result["deleted_blockers"]), 2)
        self.assertNotIn("orderlift_delete_blockers_and_parent", frappe_stub.db.rollbacks)

    def test_reference_master_blockers_are_unlinked_not_deleted(self):
        current = [
            {"doctype": "Quotation", "name": "QTN-1", "reasons": []},
            {
                "doctype": "Prospect",
                "name": "PROSPECT-1",
                "reasons": [{"link_doctype": "Prospect Opportunity", "fieldname": "opportunity", "row": 2}],
            },
        ]
        visible = [
            blocker("Quotation", "QTN-1"),
            {
                **blocker("Prospect", "PROSPECT-1", can_delete=False),
                "lock_reason": "reference_doctype",
                "reasons": [{"link_doctype": "Prospect Opportunity", "fieldname": "opportunity", "row": 2}],
            },
        ]
        deleted = []
        unlinked = []
        frappe_stub.delete_doc = lambda doctype, name: deleted.append((doctype, name))
        parent_patch, discover_patch, classify_patch = self.action_patches(current, visible=visible)

        with (
            parent_patch,
            discover_patch,
            classify_patch,
            patch.object(delete_blocker_helper, "_unlink_reference_blockers", side_effect=lambda rows, parent: unlinked.extend(rows) or [{"doctype": "Prospect", "name": "PROSPECT-1"}]),
        ):
            result = delete_blocker_helper.delete_blockers_and_parent(
                "Customer",
                "CUST-1",
                [{"doctype": "Quotation", "name": "QTN-1"}],
            )

        self.assertEqual(deleted, [("Quotation", "QTN-1"), ("Customer", "CUST-1")])
        self.assertEqual([row["name"] for row in unlinked], ["PROSPECT-1"])
        self.assertEqual(result["unlinked_references"], [{"doctype": "Prospect", "name": "PROSPECT-1"}])

    def test_deleting_quotation_does_not_cascade_delete_linked_customer(self):
        self.parent = types.SimpleNamespace(doctype="Quotation", name="QTN-1")
        current = [
            {"doctype": "Sales Order", "name": "SO-1", "reasons": []},
            {
                "doctype": "Customer",
                "name": "CUST-1",
                "reasons": [{"link_doctype": "Customer Quotation", "fieldname": "quotation", "row": 1}],
            },
        ]
        visible = [
            blocker("Sales Order", "SO-1"),
            {
                **blocker("Customer", "CUST-1", can_delete=False),
                "lock_reason": "reference_doctype",
                "reasons": [{"link_doctype": "Customer Quotation", "fieldname": "quotation", "row": 1}],
            },
        ]
        deleted = []
        unlinked = []
        frappe_stub.delete_doc = lambda doctype, name: deleted.append((doctype, name))
        parent_patch, discover_patch, classify_patch = self.action_patches(current, visible=visible)

        with (
            parent_patch,
            discover_patch,
            classify_patch,
            patch.object(delete_blocker_helper, "_unlink_reference_blockers", side_effect=lambda rows, parent: unlinked.extend(rows) or [{"doctype": "Customer", "name": "CUST-1"}]),
        ):
            result = delete_blocker_helper.delete_blockers_and_parent(
                "Quotation",
                "QTN-1",
                [{"doctype": "Sales Order", "name": "SO-1"}],
            )

        self.assertEqual(deleted, [("Sales Order", "SO-1"), ("Quotation", "QTN-1")])
        self.assertEqual([row["name"] for row in unlinked], ["CUST-1"])
        self.assertEqual(result["deleted_parent"], {"doctype": "Quotation", "name": "QTN-1"})
        self.assertEqual(result["unlinked_references"], [{"doctype": "Customer", "name": "CUST-1"}])

    def test_dynamic_reference_unlink_filters_by_link_doctype_and_name(self):
        parent = types.SimpleNamespace(doctype="Lead", name="LEAD-1")
        frappe_stub.db = FakeDB()
        frappe_stub.db.values = [{"name": "DYNAMIC-LINK-1"}]
        blocker_row = {
            "doctype": "Contact",
            "name": "CONTACT-1",
            "reasons": [
                {
                    "link_doctype": "Dynamic Link",
                    "fieldname": "link_name",
                    "doctype_fieldname": "link_doctype",
                    "row": 1,
                }
            ],
        }

        with patch.object(
            frappe_stub,
            "get_meta",
            return_value=types.SimpleNamespace(istable=True),
        ):
            result = delete_blocker_helper._unlink_reference_blockers([blocker_row], parent)

        filters = frappe_stub.db.get_values_calls[0][0][1]
        self.assertEqual(filters["parent"], "CONTACT-1")
        self.assertEqual(filters["parenttype"], "Contact")
        self.assertEqual(filters["link_name"], "LEAD-1")
        self.assertEqual(filters["link_doctype"], "Lead")
        self.assertEqual(result[0]["link_row"], "DYNAMIC-LINK-1")

    def test_static_reference_unlink_clears_master_link_field(self):
        parent = types.SimpleNamespace(doctype="Customer", name="CUST-1")
        frappe_stub.db = FakeDB()
        blocker_row = {
            "doctype": "Lead",
            "name": "LEAD-1",
            "reasons": [
                {
                    "link_doctype": "Lead",
                    "fieldname": "customer",
                    "field_label": "From Customer",
                    "row": "",
                }
            ],
        }

        with patch.object(
            frappe_stub,
            "get_meta",
            return_value=types.SimpleNamespace(istable=False),
        ):
            result = delete_blocker_helper._unlink_reference_blockers([blocker_row], parent)

        self.assertEqual(frappe_stub.db.exists_calls[0][0], ("Lead", {"name": "LEAD-1", "customer": "CUST-1"}))
        self.assertEqual(frappe_stub.db.set_value_calls[0][0], ("Lead", "LEAD-1", "customer", None))
        self.assertEqual(result[0]["link_field"], "customer")

    def test_interdependent_selected_blockers_are_retried(self):
        current = [
            {"doctype": "A", "name": "A-1", "reasons": []},
            {"doctype": "B", "name": "B-1", "reasons": []},
        ]
        calls = []
        failed_once = {"value": False}

        def delete_doc(doctype, name):
            calls.append((doctype, name))
            if doctype == "A" and not failed_once["value"]:
                failed_once["value"] = True
                raise FrappeLinkExistsError("A is linked to B")

        frappe_stub.delete_doc = delete_doc
        parent_patch, discover_patch, classify_patch = self.action_patches(current)

        with parent_patch, discover_patch, classify_patch:
            delete_blocker_helper.delete_blockers_and_parent(
                "Customer",
                "CUST-1",
                [{"doctype": "A", "name": "A-1"}, {"doctype": "B", "name": "B-1"}],
            )

        self.assertEqual(calls, [
            ("A", "A-1"),
            ("B", "B-1"),
            ("A", "A-1"),
            ("Customer", "CUST-1"),
        ])

    def test_privileged_delete_cancels_submitted_document_before_deleting(self):
        events = []

        class SubmittedDoc:
            meta = types.SimpleNamespace(is_submittable=True)
            flags = types.SimpleNamespace(ignore_permissions=False)
            docstatus = 1

            def cancel(self):
                events.append("cancel")
                self.docstatus = 2

        doc = SubmittedDoc()
        frappe_stub.get_doc = lambda doctype, name: doc
        frappe_stub.delete_doc = lambda doctype, name, **kwargs: events.append((doctype, name, kwargs))

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=[]):
            delete_blocker_helper._delete_document("Quotation", "QTN-1", allow_override=True)

        self.assertTrue(doc.flags.ignore_permissions)
        self.assertEqual(events, ["cancel", ("Quotation", "QTN-1", {"ignore_permissions": True, "force": False})])

    def test_privileged_delete_removes_exact_source_voucher_ledgers(self):
        doc = types.SimpleNamespace(
            meta=types.SimpleNamespace(is_submittable=True),
            flags=types.SimpleNamespace(ignore_permissions=False),
            docstatus=2,
        )
        deleted = []
        frappe_stub.get_doc = lambda doctype, name: doc
        frappe_stub.delete_doc = lambda doctype, name, **kwargs: deleted.append((doctype, name, kwargs))

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=[
            source_ledger("GL Entry", "GLE-1"),
            source_ledger("Stock Ledger Entry", "SLE-1"),
            source_ledger("Payment Ledger Entry", "PLE-1"),
        ]):
            delete_blocker_helper._delete_document(
                "Purchase Receipt",
                "PR-1",
                allow_override=True,
                allowed_link_keys={("Purchase Order", "PO-1")},
            )

        self.assertEqual(deleted, [
            ("Purchase Receipt", "PR-1", {"ignore_permissions": True, "force": True}),
        ])
        self.assertEqual(len(frappe_stub.db.sql_calls), 4)
        self.assertEqual(frappe_stub.db.sql_calls[0][0][1], ("Purchase Receipt", "PR-1"))
        self.assertEqual(frappe_stub.db.sql_calls[1][0][1], ("Purchase Receipt", "PR-1"))
        self.assertEqual(
            frappe_stub.db.sql_calls[2][0][1],
            ("Purchase Receipt", "PR-1", "Purchase Receipt", "PR-1"),
        )
        self.assertEqual(
            frappe_stub.db.sql_calls[3][0][1],
            ("Purchase Receipt", "PR-1", "Purchase Receipt", "PR-1"),
        )
        self.assertIn("voucher_type=%s and voucher_no=%s", frappe_stub.db.sql_calls[0][0][0])
        self.assertIn("against_voucher_type=%s", frappe_stub.db.sql_calls[2][0][0])

    def test_privileged_direct_parent_delete_forces_when_only_ledgers_block(self):
        doc = types.SimpleNamespace(
            meta=types.SimpleNamespace(is_submittable=True),
            flags=types.SimpleNamespace(ignore_permissions=False),
            docstatus=2,
        )
        events = []
        frappe_stub.get_doc = lambda doctype, name: doc
        frappe_stub.delete_doc = lambda doctype, name, **kwargs: events.append((doctype, name, kwargs))

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=[
            source_ledger("GL Entry", "GLE-1"),
        ]):
            delete_blocker_helper._delete_document("Payment Entry", "PE-1", allow_override=True)

        self.assertEqual(events, [
            ("Payment Entry", "PE-1", {"ignore_permissions": True, "force": True}),
        ])

    def test_privileged_delete_removes_only_generated_cancel_blockers(self):
        events = []

        class SubmittedDoc:
            meta = types.SimpleNamespace(is_submittable=True)
            flags = types.SimpleNamespace(ignore_permissions=False)
            docstatus = 1
            ignore_linked_doctypes = ()

            def cancel(self):
                events.append("cancel invoice")
                self.docstatus = 2
                self.ignore_linked_doctypes = ("GL Entry",)

        invoice = SubmittedDoc()
        ledger = types.SimpleNamespace(
            meta=types.SimpleNamespace(is_submittable=False),
            flags=types.SimpleNamespace(ignore_permissions=False),
            docstatus=0,
        )
        frappe_stub.get_doc = lambda doctype, name: invoice if doctype == "Purchase Invoice" else ledger
        frappe_stub.delete_doc = lambda doctype, name, **kwargs: events.append((doctype, name))

        def blockers(doc):
            if doc is invoice and doc.docstatus == 2 and ("GL Entry", "GLE-REV") not in events:
                return [
                    {"doctype": "GL Entry", "name": "GLE-REV", "reasons": []},
                ]
            return []

        with patch.object(delete_blocker_helper, "_discover_blockers", side_effect=blockers):
            generated = delete_blocker_helper._delete_document(
                "Purchase Invoice",
                "PI-1",
                allow_override=True,
            )

        self.assertEqual(generated, [{"doctype": "GL Entry", "name": "GLE-REV"}])
        self.assertEqual(events, ["cancel invoice", ("GL Entry", "GLE-REV"), ("Purchase Invoice", "PI-1")])

    def test_privileged_delete_forces_only_allowed_internal_graph_links(self):
        events = []
        log_doc = types.SimpleNamespace(
            meta=types.SimpleNamespace(is_submittable=False),
            flags=types.SimpleNamespace(ignore_permissions=False),
            docstatus=0,
        )
        frappe_stub.get_doc = lambda doctype, name: log_doc
        frappe_stub.delete_doc = lambda doctype, name, **kwargs: events.append((doctype, name, kwargs))

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=[
            {"doctype": "Purchase Order", "name": "PO-1", "reasons": []},
        ]):
            delete_blocker_helper._delete_document(
                "Buying Price Change Log",
                "BPL-1",
                allow_override=True,
                allowed_link_keys={("Purchase Order", "PO-1")},
            )

        self.assertEqual(events, [("Buying Price Change Log", "BPL-1", {"ignore_permissions": True, "force": True})])

    def test_privileged_delete_rejects_unselected_external_graph_links(self):
        log_doc = types.SimpleNamespace(
            meta=types.SimpleNamespace(is_submittable=False),
            flags=types.SimpleNamespace(ignore_permissions=False),
            docstatus=0,
        )
        frappe_stub.get_doc = lambda doctype, name: log_doc

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=[
            {"doctype": "Purchase Order", "name": "PO-OTHER", "reasons": []},
        ]):
            with self.assertRaises(FrappeValidationError):
                delete_blocker_helper._delete_document(
                    "Buying Price Change Log",
                    "BPL-1",
                    allow_override=True,
                    allowed_link_keys={("Purchase Order", "PO-1")},
                )

    def test_unexpected_link_check_ignores_ledgers_but_keeps_business_documents(self):
        doc = types.SimpleNamespace(doctype="Purchase Receipt", name="PR-1")
        discovered = [
            source_ledger("GL Entry", "GLE-1"),
            source_ledger("Stock Ledger Entry", "SLE-1"),
            source_ledger("Payment Ledger Entry", "PLE-1"),
            {"doctype": "Purchase Invoice", "name": "PI-NEW", "reasons": []},
        ]

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=discovered):
            unexpected = delete_blocker_helper._unexpected_link_blockers(doc, set())

        self.assertEqual([(row["doctype"], row["name"]) for row in unexpected], [
            ("Purchase Invoice", "PI-NEW"),
        ])

    def test_unexpected_link_check_keeps_non_source_ledger_blockers(self):
        doc = types.SimpleNamespace(doctype="Item", name="ITEM-1")
        discovered = [
            {
                "doctype": "Stock Ledger Entry",
                "name": "SLE-1",
                "reasons": [{"link_doctype": "Stock Ledger Entry", "fieldname": "item_code"}],
            },
        ]

        with patch.object(delete_blocker_helper, "_discover_blockers", return_value=discovered):
            unexpected = delete_blocker_helper._unexpected_link_blockers(doc, set())

        self.assertEqual([(row["doctype"], row["name"]) for row in unexpected], [
            ("Stock Ledger Entry", "SLE-1"),
        ])

    def test_failure_rolls_back_the_whole_action(self):
        current = [{"doctype": "Quotation", "name": "QTN-1", "reasons": []}]
        frappe_stub.delete_doc = lambda doctype, name: (_ for _ in ()).throw(RuntimeError("protected"))
        parent_patch, discover_patch, classify_patch = self.action_patches(current)

        with parent_patch, discover_patch, classify_patch:
            with self.assertRaises(RuntimeError):
                delete_blocker_helper.delete_blockers_and_parent(
                    "Customer",
                    "CUST-1",
                    [{"doctype": "Quotation", "name": "QTN-1"}],
                )

        self.assertIn("orderlift_delete_blockers_and_parent", frappe_stub.db.rollbacks)

    def test_global_asset_is_registered(self):
        hooks_source = (APP_ROOT / "orderlift" / "hooks.py").read_text()
        self.assertIn("delete_blocker_helper_20260804b.js?v=20260805e", hooks_source)

        asset = (APP_ROOT / "orderlift" / "public" / "js" / "delete_blocker_helper_20260804b.js").read_text()
        self.assertIn("frappe.model.delete_doc = wrappedDeleteDoc", asset)
        self.assertIn("frappe.ui.BulkOperations.prototype.delete", asset)
        self.assertIn("patchBulkDelete", asset)
        self.assertIn("ol-delete-blocker-select-all", asset)
        self.assertIn("Select all deletable", asset)
        self.assertIn("$primary.hide()", asset)
        self.assertIn("frappe.confirm", asset)
        self.assertIn("Dependency level {0}", asset)
        self.assertIn("deepest-first", asset)
        self.assertIn("Reference/master record", asset)
        self.assertIn("ledger rows are removed automatically with their exact source voucher", asset)
        self.assertIn("generated ledger row(s) linked to this source voucher", asset)
        self.assertIn("and {1} generated ledger row(s) will be removed", asset)
        self.assertIn("source_ledger_blocker_count", asset)
        self.assertIn("will be unlinked", asset)
        self.assertIn("Unlink {0} reference(s) and delete {1}", asset)


if __name__ == "__main__":
    unittest.main()
