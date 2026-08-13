import sys
import types
import unittest
from unittest.mock import patch


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value: value
frappe_stub.whitelist = lambda *args, **kwargs: (
    (lambda method: method) if not args else args[0]
)
frappe_stub.PermissionError = PermissionError
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(
    RuntimeError(message)
)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
utils_stub.today = lambda: "2026-07-18"
sys.modules["frappe.utils"] = utils_stub

model_stub = types.ModuleType("frappe.model")
document_stub = types.ModuleType("frappe.model.document")


class Document:
    pass


document_stub.Document = Document
sys.modules["frappe.model"] = model_stub
sys.modules["frappe.model.document"] = document_stub

from orderlift.sales.utils import commission_calculator
from orderlift.orderlift_sales.doctype.sales_commission.sales_commission import (
    SalesCommission,
)


class DbStub:
    def __init__(self, qitem=None, values=None):
        self.qitem = qitem or {}
        self.values = values or {}
        self.set_calls = []

    def get_value(self, doctype, name_or_filters=None, fieldname=None, *args, **kwargs):
        if isinstance(name_or_filters, dict):
            return self.qitem
        key = (
            doctype,
            name_or_filters,
            tuple(fieldname) if isinstance(fieldname, list) else fieldname,
        )
        if key in self.values:
            return self.values[key]
        return self.qitem

    def set_value(self, doctype, name, values, **kwargs):
        self.set_calls.append((doctype, name, values, kwargs))


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)


class TestCommissionCalculator(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(commission_calculator.frappe, "db", None)
        self.original_get_all = getattr(commission_calculator.frappe, "get_all", None)
        self.original_get_doc = getattr(commission_calculator.frappe, "get_doc", None)
        self.original_log_error = getattr(commission_calculator.frappe, "log_error", None)

    def tearDown(self):
        if self.original_db is None:
            if hasattr(commission_calculator.frappe, "db"):
                delattr(commission_calculator.frappe, "db")
        else:
            commission_calculator.frappe.db = self.original_db
        if self.original_get_all is None:
            if hasattr(commission_calculator.frappe, "get_all"):
                delattr(commission_calculator.frappe, "get_all")
        else:
            commission_calculator.frappe.get_all = self.original_get_all
        if self.original_get_doc is None:
            if hasattr(commission_calculator.frappe, "get_doc"):
                delattr(commission_calculator.frappe, "get_doc")
        else:
            commission_calculator.frappe.get_doc = self.original_get_doc
        if self.original_log_error is None:
            if hasattr(commission_calculator.frappe, "log_error"):
                delattr(commission_calculator.frappe, "log_error")
        else:
            commission_calculator.frappe.log_error = self.original_log_error

    def test_complete_production_commission_example(self):
        """Document the calculation and Approved -> To Pay lifecycle in one scenario."""
        state = {"per_billed": 50, "outstanding_amount": 950}

        class LifecycleDb:
            def get_value(self, doctype, name_or_filters=None, fieldname=None, *args, **kwargs):
                if doctype == "Sales Order" and fieldname == "per_billed":
                    return state["per_billed"]
                return {}

        lifecycle_db = LifecycleDb()
        lifecycle_db.set_calls = []

        def set_value(doctype, name, values, **kwargs):
            lifecycle_db.set_calls.append((doctype, name, values, kwargs))

        lifecycle_db.set_value = set_value
        commission_calculator.frappe.db = lifecycle_db
        sales_order = types.SimpleNamespace(
            name="SO-COMMISSION-EXAMPLE",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            currency="MAD",
            items=[
                Row(
                    qty=10,
                    source_sales_person="Agent A",
                    source_commission_rate=5,
                    source_price_list_sell_rate=100,
                    price_list_rate=100,
                    rate=95,
                    source_max_discount_percent=10,
                )
            ],
        )

        payloads = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        # Unused discount allowance: 10% maximum - 5% used = 5%.
        # Payout base: (95 * 10) * 5% unused allowance = 47.50 MAD.
        # Commission: 47.50 * 5% agent rate = 2.375 MAD.
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["salesperson"], "Agent A")
        self.assertEqual(payloads[0]["currency"], "MAD")
        self.assertEqual(payloads[0]["status"], "Approved")
        self.assertAlmostEqual(payloads[0]["base_amount"], 47.5)
        self.assertAlmostEqual(payloads[0]["commission_amount"], 2.375)

        commission = types.SimpleNamespace(
            name="COMM-COMMISSION-EXAMPLE",
            docstatus=1,
            status="Approved",
            sales_invoice="",
            save_calls=0,
        )

        def save_commission(ignore_permissions=False):
            commission.save_calls += 1

        commission.save = save_commission

        def get_all(doctype, **kwargs):
            if doctype == "Sales Invoice Item":
                return ["SINV-COMMISSION-EXAMPLE"]
            if doctype == "Sales Invoice":
                return [
                    Row(
                        name="SINV-COMMISSION-EXAMPLE",
                        outstanding_amount=state["outstanding_amount"],
                        posting_date="2026-07-13",
                    )
                ]
            if doctype == "Sales Commission":
                return ["COMM-COMMISSION-EXAMPLE"]
            return []

        commission_calculator.frappe.get_all = get_all
        commission_calculator.frappe.get_doc = lambda doctype, name: commission

        # A partially billed order cannot become payable.
        commission_calculator._sync_sales_order_commissions(sales_order.name)
        self.assertEqual(commission.status, "Approved")
        self.assertEqual(commission.sales_invoice, "")
        self.assertEqual(commission.save_calls, 0)

        # Full billing is still insufficient while the invoice has an outstanding balance.
        state["per_billed"] = 100
        commission_calculator._sync_sales_order_commissions(sales_order.name)
        self.assertEqual(commission.status, "Approved")
        self.assertEqual(commission.sales_invoice, "")

        # Once fully billed and fully paid, the commission becomes payable.
        state["outstanding_amount"] = 0
        commission_calculator._sync_sales_order_commissions(sales_order.name)
        self.assertEqual(commission.status, "To Pay")
        self.assertEqual(commission.sales_invoice, "SINV-COMMISSION-EXAMPLE")
        self.assertTrue(lifecycle_db.set_calls)

        # Cancelling/reposting a payment safely returns it to Approved.
        state["outstanding_amount"] = 950
        commission_calculator._sync_sales_order_commissions(sales_order.name)
        self.assertEqual(commission.status, "Approved")
        self.assertEqual(commission.sales_invoice, "")

    def test_primary_commission_pool_is_split_across_team(self):
        commission_calculator.frappe.db = DbStub()
        sales_order = types.SimpleNamespace(
            name="SO-TEAM-001",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            currency="MAD",
            custom_sales_team=[
                Row(sales_person="Agent A", allocated_percentage=50, is_primary=1),
                Row(sales_person="Agent B", allocated_percentage=50, is_primary=0),
            ],
            items=[
                Row(
                    qty=10,
                    source_commission_rate=5,
                    source_price_list_sell_rate=100,
                    price_list_rate=100,
                    rate=95,
                    source_max_discount_percent=10,
                )
            ],
        )

        with patch.object(commission_calculator, "team_rows", return_value=sales_order.custom_sales_team), patch.object(
            commission_calculator, "primary_sales_person", return_value="Agent A"
        ), patch.object(commission_calculator, "commission_rate", return_value=5):
            payloads = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        self.assertEqual([row["salesperson"] for row in payloads], ["Agent A", "Agent B"])
        self.assertAlmostEqual(payloads[0]["commission_amount"], 1.1875)
        self.assertAlmostEqual(payloads[1]["commission_amount"], 1.1875)
        self.assertEqual(payloads[0]["custom_primary_commission_rate"], 5)
        self.assertEqual(payloads[0]["custom_contribution_percent"], 50)

    def test_quotation_snapshot_above_list_has_no_uplift(self):
        commission_calculator.frappe.db = DbStub(
            {
                "source_sales_person": "Agent A",
                "source_commission_rate": 5,
                "source_price_list_sell_rate": 100,
                "price_list_rate": 100,
                "rate": 110,
                "source_max_discount_percent": 10,
                "qty": 10,
            }
        )
        sales_order = types.SimpleNamespace(
            name="SO-001",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            items=[Row(quotation_item="QTN-ITEM-1", qty=10)],
        )

        rows = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["salesperson"], "Agent A")
        self.assertAlmostEqual(rows[0]["base_amount"], 110)
        self.assertAlmostEqual(rows[0]["commission_amount"], 5.5)

    def test_sales_order_item_snapshot_uses_native_price_list_fallback_and_rate(self):
        commission_calculator.frappe.db = DbStub({})
        sales_order = types.SimpleNamespace(
            name="SO-001",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            items=[
                Row(
                    qty=10,
                    source_sales_person="Agent A",
                    source_commission_rate=5,
                    price_list_rate=100,
                    rate=95,
                    source_max_discount_percent=10,
                )
            ],
        )

        rows = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["base_amount"], 47.5)
        self.assertAlmostEqual(rows[0]["commission_amount"], 2.375)

    def test_sales_order_snapshot_preserves_nine_decimal_precision(self):
        commission_calculator.frappe.db = DbStub({})
        price_list_unit_price = 100.123456789
        actual_unit_price = 95.987654321
        qty = 3.333333333
        max_discount_percent = 8.765432109
        commission_rate = 6.543210987
        used_discount_percent = max(
            ((price_list_unit_price - actual_unit_price) / price_list_unit_price) * 100,
            0,
        )
        expected_base = (
            actual_unit_price
            * qty
            * max(max_discount_percent - used_discount_percent, 0)
            / 100
        )
        expected_commission = expected_base * commission_rate / 100
        sales_order = types.SimpleNamespace(
            name="SO-PRECISE",
            project="PROJ-001",
            customer="CUST-001",
            company="Orderlift",
            items=[
                Row(
                    qty=qty,
                    source_sales_person="Agent A",
                    source_commission_rate=commission_rate,
                    source_price_list_sell_rate=price_list_unit_price,
                    price_list_rate=1,
                    rate=actual_unit_price,
                    source_max_discount_percent=max_discount_percent,
                )
            ],
        )

        rows = commission_calculator._build_sales_order_snapshot_commissions(sales_order)

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["base_amount"], expected_base, places=9)
        self.assertAlmostEqual(rows[0]["commission_amount"], expected_commission, places=9)

    def test_sales_order_must_be_completely_billed_before_commission_is_payable(self):
        commission_calculator.frappe.db = DbStub(
            values={
                ("Sales Order", "SO-PARTIAL", "per_billed"): 50,
                ("Sales Order", "SO-COMPLETE", "per_billed"): 100,
            }
        )

        self.assertFalse(commission_calculator._sales_order_is_fully_billed("SO-PARTIAL"))
        self.assertTrue(commission_calculator._sales_order_is_fully_billed("SO-COMPLETE"))

    def test_payment_entry_only_collects_sales_invoice_references(self):
        payment = types.SimpleNamespace(
            references=[
                types.SimpleNamespace(reference_doctype="Sales Invoice", reference_name="SINV-001"),
                types.SimpleNamespace(reference_doctype="Purchase Invoice", reference_name="PINV-001"),
                types.SimpleNamespace(reference_doctype="Sales Invoice", reference_name="SINV-001"),
                types.SimpleNamespace(reference_doctype="Sales Invoice", reference_name="SINV-002"),
            ]
        )

        self.assertEqual(
            commission_calculator._payment_entry_sales_invoices(payment),
            ["SINV-001", "SINV-002"],
        )

    def test_snapshot_base_is_actual_unused_discount_monetary_base(self):
        result = commission_calculator._calculate_snapshot_commission(
            {
                "source_price_list_sell_rate": 100,
                "price_list_rate": 1000,
                "rate": 90,
                "source_max_discount_percent": 15,
                "source_commission_rate": 20,
            },
            qty=5,
        )

        self.assertAlmostEqual(result["base_amount"], 22.5)
        self.assertAlmostEqual(result["commission_amount"], 4.5)

    def test_fully_billed_order_is_not_payable_while_an_invoice_is_outstanding(self):
        commission_calculator.frappe.db = DbStub(
            values={("Sales Order", "SO-001", "per_billed"): 100}
        )

        def get_all(doctype, **kwargs):
            if doctype == "Sales Invoice Item":
                return ["SINV-001", "SINV-002"]
            return [
                Row(name="SINV-002", outstanding_amount=10, posting_date="2026-07-02"),
                Row(name="SINV-001", outstanding_amount=0, posting_date="2026-07-01"),
            ]

        commission_calculator.frappe.get_all = get_all

        result = commission_calculator.sales_order_commission_eligibility("SO-001")

        self.assertFalse(result["eligible"])
        self.assertEqual(result["latest_invoice"], "")

    def test_fully_billed_order_is_payable_when_every_invoice_is_paid(self):
        commission_calculator.frappe.db = DbStub(
            values={("Sales Order", "SO-001", "per_billed"): 100}
        )

        def get_all(doctype, **kwargs):
            if doctype == "Sales Invoice Item":
                return ["SINV-001", "SINV-002"]
            return [
                Row(name="SINV-002", outstanding_amount=0, posting_date="2026-07-02"),
                Row(name="SINV-001", outstanding_amount=0, posting_date="2026-07-01"),
            ]

        commission_calculator.frappe.get_all = get_all

        result = commission_calculator.sales_order_commission_eligibility("SO-001")

        self.assertTrue(result["eligible"])
        self.assertEqual(result["latest_invoice"], "SINV-002")

    def test_submitted_commission_transition_uses_controlled_db_update_not_save(self):
        db = DbStub()
        commission_calculator.frappe.db = db
        commission = types.SimpleNamespace(
            name="COM-001",
            docstatus=1,
            status="Approved",
            sales_invoice="",
            payment_date=None,
            payment_reference="",
            save_calls=0,
        )
        commission.save = lambda **kwargs: setattr(
            commission, "save_calls", commission.save_calls + 1
        )
        commission_calculator.frappe.get_doc = lambda doctype, name: commission

        changed = commission_calculator.transition_commission_lifecycle(
            "COM-001",
            "To Pay",
            sales_invoice="SINV-001",
            reason="Full customer payment",
        )

        self.assertTrue(changed)
        self.assertEqual(commission.save_calls, 0)
        self.assertEqual(commission.status, "To Pay")
        self.assertEqual(commission.sales_invoice, "SINV-001")
        self.assertEqual(
            db.set_calls,
            [
                (
                    "Sales Commission",
                    "COM-001",
                    {"status": "To Pay", "sales_invoice": "SINV-001"},
                    {"update_modified": True},
                )
            ],
        )

    def test_replayed_sales_order_hook_does_not_resave_submitted_snapshot(self):
        commission_calculator.frappe.db = DbStub("COM-001")
        commission = types.SimpleNamespace(
            name="COM-001",
            docstatus=1,
            status="Approved",
            save_calls=0,
        )
        commission.save = lambda **kwargs: setattr(
            commission, "save_calls", commission.save_calls + 1
        )
        commission_calculator.frappe.get_doc = lambda *args, **kwargs: commission
        payload = {
            "doctype": "Sales Commission",
            "sales_order": "SO-001",
            "salesperson": "Agent A",
            "company": "Orderlift",
            "customer": "CUST-001",
            "project": "",
            "commission_rate": 5,
            "base_amount": 50,
            "commission_amount": 2.5,
        }

        with patch.object(
            commission_calculator,
            "_build_sales_order_snapshot_commissions",
            return_value=[payload],
        ):
            commission_calculator.create_sales_order_commissions(
                types.SimpleNamespace(name="SO-001")
            )

        self.assertEqual(commission.save_calls, 0)

    def test_new_sales_order_commission_submit_uses_snapshot_update_flag(self):
        commission_calculator.frappe.db = DbStub(qitem=None)
        payload = {
            "doctype": "Sales Commission",
            "sales_order": "SO-001",
            "salesperson": "Agent A",
            "company": "Orderlift",
            "customer": "CUST-001",
            "project": "",
            "commission_rate": 5,
            "base_amount": 50,
            "commission_amount": 2.5,
        }
        checks = []

        class CommissionStub:
            def __init__(self):
                self.flags = types.SimpleNamespace()

            def insert(self, ignore_permissions=False):
                checks.append(("insert", ignore_permissions, self.flags.orderlift_commission_snapshot_update))

            def submit(self):
                checks.append(("submit", self.flags.orderlift_commission_snapshot_update))

        commission = CommissionStub()
        commission_calculator.frappe.get_doc = lambda data: commission

        with patch.object(
            commission_calculator,
            "_build_sales_order_snapshot_commissions",
            return_value=[payload],
        ):
            commission_calculator.create_sales_order_commissions(
                types.SimpleNamespace(name="SO-001")
            )

        self.assertEqual(checks, [("insert", True, True), ("submit", True)])

    def test_paid_commission_cannot_be_reverted_by_lifecycle_helper(self):
        db = DbStub()
        commission_calculator.frappe.db = db
        commission_calculator.frappe.get_doc = lambda doctype, name: types.SimpleNamespace(
            name=name,
            docstatus=1,
            status="Paid",
            sales_invoice="SINV-001",
            payment_date="2026-07-18",
            payment_reference="PAY-001",
        )

        with self.assertRaises(ValueError):
            commission_calculator.transition_commission_lifecycle(
                "COM-001", "Approved"
            )

        self.assertEqual(db.set_calls, [])

    def test_payment_entry_commission_sync_failure_is_logged_not_raised(self):
        commission_calculator.frappe.get_all = lambda doctype, **kwargs: ["SO-001"]
        errors = []
        commission_calculator.frappe.log_error = lambda **kwargs: errors.append(kwargs)
        payment = types.SimpleNamespace(
            doctype="Payment Entry",
            name="ACC-PAY-001",
            references=[
                types.SimpleNamespace(
                    reference_doctype="Sales Invoice",
                    reference_name="SINV-001",
                )
            ],
        )

        with patch.object(
            commission_calculator,
            "_sync_sales_order_commissions",
            side_effect=RuntimeError("simulated sync failure"),
        ):
            commission_calculator.sync_commissions_from_payment_entry(payment)

        self.assertEqual(len(errors), 1)
        self.assertIn("ACC-PAY-001", errors[0]["title"])


class TestSalesCommissionPayout(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(frappe_stub, "db", None)
        self.original_msgprint = getattr(frappe_stub, "msgprint", None)
        self.original_get_doc = getattr(frappe_stub, "get_doc", None)
        frappe_stub.msgprint = lambda *args, **kwargs: None

    def tearDown(self):
        if self.original_db is None:
            if hasattr(frappe_stub, "db"):
                delattr(frappe_stub, "db")
        else:
            frappe_stub.db = self.original_db
        if self.original_msgprint is None:
            if hasattr(frappe_stub, "msgprint"):
                delattr(frappe_stub, "msgprint")
        else:
            frappe_stub.msgprint = self.original_msgprint
        if self.original_get_doc is None:
            if hasattr(frappe_stub, "get_doc"):
                delattr(frappe_stub, "get_doc")
        else:
            frappe_stub.get_doc = self.original_get_doc

    def _commission(self, status):
        commission = SalesCommission()
        commission.name = "COM-001"
        commission.docstatus = 1
        commission.status = status
        commission.sales_order = ""
        commission.sales_invoice = "SINV-001"
        commission.payment_date = None
        commission.payment_reference = ""
        commission._can_manage_payouts = lambda: True
        commission.save = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("ordinary save must not be called")
        )
        return commission

    def test_mark_as_paid_rejects_approved_commission(self):
        with self.assertRaises(RuntimeError):
            self._commission("Approved").mark_as_paid()

    def test_mark_as_paid_persists_lifecycle_fields_without_save(self):
        db = DbStub()
        frappe_stub.db = db
        commission = self._commission("To Pay")
        frappe_stub.get_doc = lambda doctype, name: commission

        commission.mark_as_paid(
            payment_date="2026-07-18",
            payment_reference="BANK-001",
        )

        self.assertEqual(commission.status, "Paid")
        self.assertEqual(commission.payment_date, "2026-07-18")
        self.assertEqual(commission.payment_reference, "BANK-001")
        self.assertEqual(
            db.set_calls,
            [
                (
                    "Sales Commission",
                    "COM-001",
                    {
                        "status": "Paid",
                        "payment_date": "2026-07-18",
                        "payment_reference": "BANK-001",
                    },
                    {"update_modified": True},
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
