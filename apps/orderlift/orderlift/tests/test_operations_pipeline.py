import datetime
import sys
import types
import unittest


class _Row(types.SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.get_all = lambda *args, **kwargs: []
frappe_stub.get_meta = lambda *args, **kwargs: None
frappe_stub.get_doc = lambda *args, **kwargs: None
frappe_stub.db = types.SimpleNamespace()
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value: int(value or 0)
frappe_utils_stub.flt = lambda value: float(value or 0)


def _getdate(value):
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value)[:10])


frappe_utils_stub.getdate = _getdate
frappe_utils_stub.today = lambda: "2026-04-16"
sys.modules["frappe.utils"] = frappe_utils_stub


from orderlift.orderlift_logistics.page.operations_pipeline import operations_pipeline as pipeline


class TestOperationsPipeline(unittest.TestCase):
    def test_cards_filters_none_results_from_date_filter(self):
        docs = [
            _Row(name="LEAD-1", customer="Acme", status="Open", doc_date="2026-04-16", value=100),
            _Row(name="LEAD-2", customer="Old", status="Open", doc_date="2026-04-10", value=50),
        ]

        cards = pipeline._cards(docs, "Lead", "today")

        self.assertEqual([card["name"] for card in cards], ["LEAD-1"])

    def test_card_overdue_uses_deadline_instead_of_doc_date(self):
        without_deadline = _Row(name="SO-1", customer="Acme", status="Open", doc_date="2026-04-01", value=10)
        with_deadline = _Row(
            name="SO-2",
            customer="Acme",
            status="Open",
            doc_date="2026-04-16",
            deadline="2026-04-01",
            value=10,
        )

        self.assertFalse(pipeline._card(without_deadline, "Sales Order", None)["overdue"])
        self.assertTrue(pipeline._card(with_deadline, "Sales Order", None)["overdue"])

    def test_resolve_column_handles_open_opportunity_purchase_order_and_resolved_sav(self):
        self.assertEqual(
            pipeline._resolve_column({"doctype": "Opportunity", "status": "Open", "overdue": False}),
            "new_triage",
        )
        self.assertEqual(
            pipeline._resolve_column({"doctype": "Purchase Order", "status": "To Receive", "overdue": False}),
            "fulfilling",
        )
        self.assertEqual(
            pipeline._resolve_column({"doctype": "SAV Ticket", "status": "Resolved", "overdue": True}),
            "closed",
        )

    def test_find_upstream_refs_uses_child_table_doctype_from_meta(self):
        calls = []

        class _ParentMeta:
            @staticmethod
            def get_field(fieldname):
                if fieldname == "items":
                    return types.SimpleNamespace(options="Sales Order Item")
                return None

        class _ChildMeta:
            @staticmethod
            def get_field(fieldname):
                if fieldname == "prevdoc_docname":
                    return types.SimpleNamespace(fieldname="prevdoc_docname")
                return None

        pipeline._CHILD_TABLE_CACHE.clear()
        pipeline.frappe.get_meta = lambda doctype: _ParentMeta() if doctype == "Sales Order" else _ChildMeta()

        def _get_all(doctype, **kwargs):
            calls.append((doctype, kwargs))
            return [_Row(parent="SO-0001")]

        pipeline.frappe.get_all = _get_all

        refs = pipeline._find_upstream_refs("Sales Order", "items.prevdoc_docname", "QTN-0001")

        self.assertEqual(refs, ["SO-0001"])
        self.assertEqual(calls[0][0], "Sales Order Item")
        self.assertEqual(calls[0][1]["filters"]["prevdoc_docname"], "QTN-0001")

    def test_find_upstream_refs_uses_parent_name_for_direct_fields(self):
        calls = []

        pipeline._CHILD_TABLE_CACHE.clear()
        pipeline._is_child_table = lambda doctype: False

        def _get_all(doctype, **kwargs):
            calls.append((doctype, kwargs))
            return [_Row(name="SAL-ORD-0001")]

        pipeline.frappe.get_all = _get_all

        refs = pipeline._find_upstream_refs("Sales Order", "customer_name", "S5 - Lead")

        self.assertEqual(refs, ["SAL-ORD-0001"])
        self.assertEqual(calls[0][0], "Sales Order")
        self.assertEqual(calls[0][1]["fields"], ["name"])
        self.assertEqual(calls[0][1]["filters"]["customer_name"], "S5 - Lead")

    def test_find_upstream_refs_resolves_parent_child_field_syntax(self):
        calls = []

        class _ParentMeta:
            @staticmethod
            def get_field(fieldname):
                if fieldname == "references":
                    return types.SimpleNamespace(options="Payment Entry Reference")
                return None

        class _ChildMeta:
            @staticmethod
            def get_field(fieldname):
                if fieldname == "reference_name":
                    return types.SimpleNamespace(fieldname="reference_name")
                return None

        pipeline._CHILD_TABLE_CACHE.clear()
        pipeline.frappe.get_meta = lambda doctype: _ParentMeta() if doctype == "Payment Entry" else _ChildMeta()

        def _get_all(doctype, **kwargs):
            calls.append((doctype, kwargs))
            return [_Row(parent="ACC-PAY-0001")]

        pipeline.frappe.get_all = _get_all

        refs = pipeline._find_upstream_refs("Payment Entry", "references.reference_name", "ACC-SINV-0001")

        self.assertEqual(refs, ["ACC-PAY-0001"])
        self.assertEqual(calls[0][0], "Payment Entry Reference")
        self.assertEqual(calls[0][1]["filters"]["parenttype"], "Payment Entry")
        self.assertEqual(calls[0][1]["filters"]["reference_name"], "ACC-SINV-0001")

    def test_get_doc_date_uses_delivery_trip_departure_time(self):
        doc = types.SimpleNamespace(departure_time="2026-04-16 08:45:00", creation="2026-04-10 00:00:00")
        self.assertEqual(pipeline._get_doc_date("Delivery Trip", doc), "2026-04-16")

    def test_get_delivery_trip_customers_keeps_first_stop_customer(self):
        pipeline.frappe.get_all = lambda *args, **kwargs: [
            _Row(parent="DT-1", customer="First Customer", idx=1),
            _Row(parent="DT-1", customer="Second Customer", idx=2),
            _Row(parent="DT-2", customer="Third Customer", idx=1),
        ]

        customers = pipeline._get_delivery_trip_customers(["DT-1", "DT-2"])

        self.assertEqual(customers, {"DT-1": "First Customer", "DT-2": "Third Customer"})

    def test_get_trace_data_keeps_fulfillment_edges_in_business_order(self):
        docs = {
            ("Sales Invoice", "INV-1"): types.SimpleNamespace(
                name="INV-1",
                customer_name="Acme",
                status="Paid",
                posting_date="2026-04-16",
                grand_total=100,
                sales_order="SO-1",
                delivery_note="DN-1",
            ),
            ("Sales Order", "SO-1"): types.SimpleNamespace(
                name="SO-1",
                customer_name="Acme",
                status="Completed",
                transaction_date="2026-04-15",
                grand_total=100,
            ),
            ("Delivery Note", "DN-1"): types.SimpleNamespace(
                name="DN-1",
                customer_name="Acme",
                status="Completed",
                posting_date="2026-04-15",
                grand_total=100,
            ),
            ("Payment Entry", "PAY-1"): types.SimpleNamespace(
                name="PAY-1",
                status="Submitted",
                posting_date="2026-04-16",
                paid_amount=100,
            ),
        }

        original_fetch_doc = pipeline._fetch_doc
        original_find_upstream_refs = pipeline._find_upstream_refs
        original_doc_exists = pipeline._doc_exists
        original_get_all = pipeline.frappe.get_all
        try:
            pipeline._fetch_doc = lambda doctype, name: docs.get((doctype, name))
            pipeline._doc_exists = lambda doctype, name: (doctype, name) in docs
            pipeline.frappe.get_all = lambda *args, **kwargs: []

            def _find_upstream_refs(from_dt, from_field, target_name, target_doctype=None):
                if from_dt == "Payment Entry" and target_doctype == "Sales Invoice" and target_name == "INV-1":
                    return ["PAY-1"]
                return []

            pipeline._find_upstream_refs = _find_upstream_refs

            trace = pipeline.get_trace_data("Sales Invoice", "INV-1")

            self.assertIn({"from": "SO-1", "to": "INV-1", "relation": "fulfillment"}, trace["edges"])
            self.assertIn({"from": "DN-1", "to": "INV-1", "relation": "fulfillment"}, trace["edges"])
            self.assertIn({"from": "INV-1", "to": "PAY-1", "relation": "fulfillment"}, trace["edges"])
        finally:
            pipeline._fetch_doc = original_fetch_doc
            pipeline._find_upstream_refs = original_find_upstream_refs
            pipeline._doc_exists = original_doc_exists
            pipeline.frappe.get_all = original_get_all

    def test_get_trace_data_keeps_supplier_as_leaf_context(self):
        docs = {
            ("Purchase Order", "PO-1"): types.SimpleNamespace(
                name="PO-1",
                supplier="Supplier A",
                supplier_name="Supplier A",
                status="To Receive and Bill",
                transaction_date="2026-04-16",
                grand_total=250,
                items=[],
            ),
            ("Supplier", "Supplier A"): types.SimpleNamespace(
                name="Supplier A",
                supplier_name="Supplier A",
                creation="2026-04-01 10:00:00",
            ),
            ("Purchase Order", "PO-OLD"): types.SimpleNamespace(
                name="PO-OLD",
                supplier="Supplier A",
                supplier_name="Supplier A",
                status="Completed",
                transaction_date="2026-04-10",
                grand_total=100,
                items=[],
            ),
        }

        original_fetch_doc = pipeline._fetch_doc
        original_find_upstream_refs = pipeline._find_upstream_refs
        original_doc_exists = pipeline._doc_exists
        original_get_all = pipeline.frappe.get_all
        try:
            pipeline._fetch_doc = lambda doctype, name: docs.get((doctype, name))
            pipeline._doc_exists = lambda doctype, name: (doctype, name) in docs
            pipeline.frappe.get_all = lambda *args, **kwargs: []

            def _find_upstream_refs(from_dt, from_field, target_name, target_doctype=None):
                if from_dt == "Purchase Order" and target_doctype == "Supplier" and target_name == "Supplier A":
                    return ["PO-OLD"]
                return []

            pipeline._find_upstream_refs = _find_upstream_refs

            trace = pipeline.get_trace_data("Purchase Order", "PO-1")

            self.assertIn({"from": "PO-1", "to": "Supplier A", "relation": "sub-branch"}, trace["edges"])
            self.assertNotIn({"from": "Supplier A", "to": "PO-OLD", "relation": "fulfillment"}, trace["edges"])
            self.assertEqual([node["id"] for node in trace["nodes"]], ["PO-1", "Supplier A"])
        finally:
            pipeline._fetch_doc = original_fetch_doc
            pipeline._find_upstream_refs = original_find_upstream_refs
            pipeline._doc_exists = original_doc_exists
            pipeline.frappe.get_all = original_get_all


if __name__ == "__main__":
    unittest.main()
