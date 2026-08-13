import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args or not callable(args[0]) else args[0]
frappe_stub.get_system_settings = lambda fieldname: 2
frappe_stub.get_cached_value = lambda doctype, name, fieldname: "MAD" if doctype == "Company" else None

custom_field_module = types.ModuleType("frappe.custom.doctype.custom_field.custom_field")
custom_field_module.create_custom_fields = lambda *args, **kwargs: None
utils_module = types.ModuleType("frappe.utils")
utils_module.flt = lambda value, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.custom"] = types.ModuleType("frappe.custom")
sys.modules["frappe.custom.doctype"] = types.ModuleType("frappe.custom.doctype")
sys.modules["frappe.custom.doctype.custom_field"] = types.ModuleType("frappe.custom.doctype.custom_field")
sys.modules["frappe.custom.doctype.custom_field.custom_field"] = custom_field_module
sys.modules["frappe.utils"] = utils_module


from orderlift.orderlift_finance import payment_entry_currency


class FakeDB:
    def __init__(self):
        self.account_currencies = {
            "Bank - MAD": "MAD",
            "Receivable - MAD": "MAD",
            "Payable - MAD": "MAD",
            "Receivable - USD": "USD",
        }
        self.reference_currencies = {
            ("Purchase Order", "PO-USD"): "USD",
            ("Purchase Invoice", "PI-USD"): "USD",
            ("Sales Order", "SO-MAD"): "MAD",
            ("Sales Invoice", "SI-USD"): "USD",
        }

    def get_value(self, doctype, name, fieldname):
        if doctype == "Account" and fieldname == "account_currency":
            return self.account_currencies.get(name)
        if fieldname == "currency":
            return self.reference_currencies.get((doctype, name))
        return None


class FakeRow:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)

    def get(self, fieldname):
        return getattr(self, fieldname, None)


class FakeDoc(FakeRow):
    def __init__(self, **values):
        references = values.pop("references", [])
        super().__init__(**values)
        self.references = references

    def get(self, fieldname):
        if fieldname == "references":
            return self.references
        return super().get(fieldname)

    def set(self, fieldname, value):
        setattr(self, fieldname, value)

    def precision(self, fieldname):
        return 9 if fieldname == payment_entry_currency.SOURCE_RATE_FIELD else 2


class TestPaymentEntryCurrency(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(payment_entry_currency.frappe, "db", None)
        self.original_cached_value = payment_entry_currency.frappe.get_cached_value
        payment_entry_currency.frappe.db = FakeDB()
        payment_entry_currency.frappe.get_cached_value = (
            lambda doctype, name, fieldname: "MAD" if doctype == "Company" else None
        )

    def tearDown(self):
        payment_entry_currency.frappe.db = self.original_db
        payment_entry_currency.frappe.get_cached_value = self.original_cached_value

    def test_usd_purchase_order_payment_is_entered_in_usd_and_stored_in_mad(self):
        reference = FakeRow(
            name="REF-1",
            reference_doctype="Purchase Order",
            reference_name="PO-USD",
            outstanding_amount=7289.45,
            allocated_amount=7289.45,
        )
        doc = FakeDoc(
            company="Demo Company",
            payment_type="Pay",
            paid_from="Bank - MAD",
            paid_to="Payable - MAD",
            paid_from_account_currency="MAD",
            paid_to_account_currency="MAD",
            custom_source_document_currency="USD",
            custom_source_payment_amount=751.49,
            custom_source_to_company_exchange_rate=9.7,
            references=[reference],
        )

        payment_entry_currency.apply_source_currency_payment(doc)

        self.assertEqual(doc.custom_converted_company_amount, 7289.45)
        self.assertEqual(doc.paid_amount, 7289.45)
        self.assertEqual(doc.received_amount, 7289.45)
        self.assertEqual(doc.source_exchange_rate, 1)
        self.assertEqual(doc.target_exchange_rate, 1)
        self.assertEqual(reference.allocated_amount, 7289.45)

    def test_same_currency_source_does_not_enable_custom_source_payment(self):
        payment_entry = FakeDoc(
            company="Demo Company",
            payment_type="Receive",
            base_paid_amount=154974,
            custom_source_document_currency=None,
            custom_source_payment_amount=0,
            custom_source_to_company_exchange_rate=0,
            custom_converted_company_amount=0,
        )
        source_doc = FakeDoc(currency="MAD")

        payment_entry_currency.initialize_source_currency_payment(payment_entry, source_doc)

        self.assertIsNone(payment_entry.custom_source_document_currency)
        self.assertEqual(payment_entry.custom_source_payment_amount, 0)
        self.assertEqual(payment_entry.custom_source_to_company_exchange_rate, 0)
        self.assertEqual(payment_entry.custom_converted_company_amount, 0)

    def test_customer_receipt_keeps_source_amount_when_receivable_is_in_source_currency(self):
        reference = FakeRow(
            name="REF-1",
            reference_doctype="Sales Invoice",
            reference_name="SI-USD",
            outstanding_amount=100,
            allocated_amount=100,
        )
        doc = FakeDoc(
            company="Demo Company",
            payment_type="Receive",
            paid_from="Receivable - USD",
            paid_to="Bank - MAD",
            paid_from_account_currency="USD",
            paid_to_account_currency="MAD",
            custom_source_document_currency="USD",
            custom_source_payment_amount=100,
            custom_source_to_company_exchange_rate=9.7,
            references=[reference],
        )

        payment_entry_currency.apply_source_currency_payment(doc)

        self.assertEqual(doc.paid_amount, 100)
        self.assertEqual(doc.received_amount, 970)
        self.assertEqual(doc.source_exchange_rate, 9.7)
        self.assertEqual(doc.target_exchange_rate, 1)
        self.assertEqual(reference.allocated_amount, 100)

    def test_company_currency_payment_forces_rate_one(self):
        reference = FakeRow(
            name="REF-1",
            reference_doctype="Sales Order",
            reference_name="SO-MAD",
            outstanding_amount=250,
            allocated_amount=250,
        )
        doc = FakeDoc(
            company="Demo Company",
            payment_type="Receive",
            paid_from="Receivable - MAD",
            paid_to="Bank - MAD",
            paid_from_account_currency="MAD",
            paid_to_account_currency="MAD",
            custom_source_document_currency="MAD",
            custom_source_payment_amount=250,
            custom_source_to_company_exchange_rate=7,
            references=[reference],
        )

        payment_entry_currency.apply_source_currency_payment(doc)

        self.assertEqual(doc.custom_source_to_company_exchange_rate, 1)
        self.assertEqual(doc.custom_converted_company_amount, 250)

    def test_source_payment_cannot_exceed_reference_outstanding(self):
        reference = FakeRow(
            name="REF-1",
            reference_doctype="Purchase Invoice",
            reference_name="PI-USD",
            outstanding_amount=500,
            allocated_amount=500,
        )
        doc = FakeDoc(
            company="Demo Company",
            payment_type="Pay",
            paid_from="Bank - MAD",
            paid_to="Payable - MAD",
            paid_from_account_currency="MAD",
            paid_to_account_currency="MAD",
            custom_source_document_currency="USD",
            custom_source_payment_amount=100,
            custom_source_to_company_exchange_rate=9.7,
            references=[reference],
        )

        with self.assertRaises(Exception):
            payment_entry_currency.apply_source_currency_payment(doc)


if __name__ == "__main__":
    unittest.main()
