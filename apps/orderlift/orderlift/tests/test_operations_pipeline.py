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

        class _Meta:
            @staticmethod
            def get_field(fieldname):
                if fieldname == "items":
                    return types.SimpleNamespace(options="Sales Order Item")
                return None

        pipeline.frappe.get_meta = lambda doctype: _Meta()

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

        class _Meta:
            @staticmethod
            def get_field(fieldname):
                if fieldname == "references":
                    return types.SimpleNamespace(options="Payment Entry Reference")
                return None

        pipeline.frappe.get_meta = lambda doctype: _Meta()

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


if __name__ == "__main__":
    unittest.main()
