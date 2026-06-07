import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args or not callable(args[0]) else args[0]
frappe_stub.session = types.SimpleNamespace(user="business@example.com")
frappe_stub.get_roles = lambda user=None: ["Orderlift Admin"]
sys.modules["frappe"] = frappe_stub


from orderlift.orderlift_finance import account_governance


class FakeMeta:
    def __init__(self, fields):
        self.fields = set(fields)

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


class FakeRow:
    def __init__(self, **values):
        fields = set(values.keys()) | {"name", "idx"}
        self.meta = FakeMeta(fields)
        for key, value in values.items():
            setattr(self, key, value)

    def get(self, fieldname):
        return getattr(self, fieldname, None)


class FakeDoc(FakeRow):
    def __init__(self, doctype, before=None, **values):
        self.doctype = doctype
        self._before = before
        items = values.pop("items", [])
        taxes = values.pop("taxes", [])
        deductions = values.pop("deductions", [])
        super().__init__(**values)
        self.meta = FakeMeta(set(values.keys()) | {"items", "taxes", "deductions"})
        self.items = items
        self.taxes = taxes
        self.deductions = deductions

    def get(self, fieldname):
        if fieldname == "items":
            return self.items
        if fieldname == "taxes":
            return self.taxes
        if fieldname == "deductions":
            return self.deductions
        return super().get(fieldname)

    def get_doc_before_save(self):
        return self._before


class FakeDB:
    accounts = {
        "Receivable - D": "Demo Company",
        "Payable - D": "Demo Company",
        "Bank - D": "Demo Company",
        "Cash - D": "Demo Company",
        "Sales Revenue - D": "Demo Company",
        "Purchases - D": "Demo Company",
        "Operating Expenses - D": "Demo Company",
        "Other Revenue - D": "Demo Company",
        "Wrong - X": "Other Company",
    }
    account_rows = {
        "Receivable - D": {"company": "Demo Company", "is_group": 0, "root_type": "Asset", "account_name": "Accounts Receivable", "account_type": "Receivable"},
        "Payable - D": {"company": "Demo Company", "is_group": 0, "root_type": "Liability", "account_name": "Accounts Payable", "account_type": "Payable"},
        "Bank - D": {"company": "Demo Company", "is_group": 0, "root_type": "Asset", "account_name": "Bank", "account_type": "Bank"},
        "Cash - D": {"company": "Demo Company", "is_group": 0, "root_type": "Asset", "account_name": "Cash", "account_type": "Cash"},
        "Sales Revenue - D": {"company": "Demo Company", "is_group": 0, "root_type": "Income", "account_name": "Sales Revenue", "account_type": "Income Account"},
        "Purchases - D": {"company": "Demo Company", "is_group": 0, "root_type": "Expense", "account_name": "Purchases / COGS", "account_type": "Expense Account"},
        "Operating Expenses - D": {"company": "Demo Company", "is_group": 0, "root_type": "Expense", "account_name": "Operating Expenses", "account_type": "Expense Account"},
        "Other Revenue - D": {"company": "Demo Company", "is_group": 0, "root_type": "Income", "account_name": "Other Revenue", "account_type": "Income Account"},
        "Wrong - X": {"company": "Other Company", "is_group": 0, "root_type": "Expense", "account_name": "Wrong", "account_type": "Expense Account"},
    }
    company_defaults = {
        "default_receivable_account": "Receivable - D",
        "default_payable_account": "Payable - D",
        "default_bank_account": "Bank - D",
        "default_cash_account": "Cash - D",
        "default_income_account": "Sales Revenue - D",
        "default_expense_account": "Operating Expenses - D",
        "cost_center": "",
    }
    cost_center_rows = {
        "Main - D": {"company": "Demo Company", "is_group": 0, "disabled": 0},
        "Project - D": {"company": "Demo Company", "is_group": 0, "disabled": 0},
        "Wrong - X": {"company": "Other Company", "is_group": 0, "disabled": 0},
    }

    def __init__(self):
        self.account_rows = dict(type(self).account_rows)
        self.accounts = dict(type(self).accounts)
        self.company_defaults = dict(type(self).company_defaults)
        self.cost_center_rows = dict(type(self).cost_center_rows)

    def exists(self, doctype, name):
        if doctype == "DocType":
            return True
        return False

    def get_value(self, doctype, name, fieldname, as_dict=False):
        if doctype == "Account" and fieldname == "company":
            return self.accounts.get(name)
        if doctype == "Company":
            if fieldname == "is_group":
                return 0
            if fieldname == "abbr":
                return "D"
            return self.company_defaults.get(fieldname, "")
        if doctype == "Cost Center":
            row = self.cost_center_rows.get(name)
            if not row:
                return None
            if as_dict:
                return types.SimpleNamespace(**{field: row.get(field) for field in fieldname})
            return row.get(fieldname)
        return None

    def set_value(self, doctype, name, fieldname, value, update_modified=True):
        if doctype == "Company":
            self.company_defaults[fieldname] = value


class TestFinanceAccountGovernance(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(account_governance.frappe, "db", None)
        self.original_get_roles = getattr(account_governance.frappe, "get_roles", None)
        self.original_get_meta = getattr(account_governance.frappe, "get_meta", None)
        self.original_get_all = getattr(account_governance.frappe, "get_all", None)
        account_governance.frappe.db = FakeDB()
        account_governance.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        account_governance.frappe.get_all = self.fake_get_all
        account_governance.frappe.get_meta = lambda doctype: FakeMeta(
            [
                "default_receivable_account",
                "default_payable_account",
                "default_bank_account",
                "default_cash_account",
                "default_income_account",
                "default_expense_account",
                "round_off_account",
                "write_off_account",
                "cost_center",
                "is_group",
            ]
        )

    def tearDown(self):
        account_governance.frappe.db = self.original_db
        account_governance.frappe.get_roles = self.original_get_roles
        account_governance.frappe.get_meta = self.original_get_meta
        account_governance.frappe.get_all = self.original_get_all

    def fake_get_all(self, doctype, filters=None, pluck=None, order_by=None, limit_page_length=None):
        if doctype == "Account":
            source = account_governance.frappe.db.account_rows
        elif doctype == "Cost Center":
            source = account_governance.frappe.db.cost_center_rows
        else:
            return []
        filters = filters or {}
        matches = []
        for name, row in source.items():
            if self._row_matches(row, filters):
                matches.append(name)
        matches = sorted(matches)
        return matches[: limit_page_length or len(matches)] if pluck == "name" else []

    def _row_matches(self, row, filters):
        for fieldname, expected in filters.items():
            value = row.get(fieldname)
            if isinstance(expected, list) and expected[:1] == ["like"]:
                needle = str(expected[1]).replace("%", "")
                if needle not in str(value or ""):
                    return False
            elif value != expected:
                return False
        return True

    def test_only_superadmin_can_write_accounts(self):
        self.assertTrue(account_governance.has_account_permission(ptype="read", user="business@example.com"))
        self.assertFalse(account_governance.has_account_permission(ptype="write", user="business@example.com"))

        account_governance.frappe.get_roles = lambda user=None: ["System Manager"]
        self.assertTrue(account_governance.has_account_permission(ptype="write", user="admin@example.com"))

    def test_only_superadmin_can_write_cost_centers(self):
        self.assertTrue(account_governance.has_cost_center_permission(ptype="read", user="business@example.com"))
        self.assertFalse(account_governance.has_cost_center_permission(ptype="write", user="business@example.com"))

        account_governance.frappe.get_roles = lambda user=None: ["System Manager"]
        self.assertTrue(account_governance.has_cost_center_permission(ptype="write", user="admin@example.com"))

    def test_sales_invoice_defaults_accounts_from_company(self):
        item = FakeRow(income_account="", expense_account="Wrong - X", cost_center="Project - D")
        tax = FakeRow(cost_center="Project - D")
        doc = FakeDoc("Sales Invoice", company="Demo Company", debit_to="", items=[item], taxes=[tax])

        account_governance.apply_document_account_defaults(doc)

        self.assertEqual(doc.debit_to, "Receivable - D")
        self.assertEqual(item.income_account, "Sales Revenue - D")
        self.assertEqual(item.expense_account, "Purchases - D")
        self.assertEqual(item.cost_center, "Main - D")
        self.assertEqual(tax.cost_center, "Main - D")

    def test_company_cost_center_prefers_main_and_updates_default(self):
        cost_center = account_governance.get_company_cost_center("Demo Company")

        self.assertEqual(cost_center, "Main - D")
        self.assertEqual(account_governance.frappe.db.company_defaults["cost_center"], "Main - D")

    def test_sales_order_cost_center_is_forced_to_company_default(self):
        item = FakeRow(cost_center="Project - D")
        doc = FakeDoc("Sales Order", company="Demo Company", items=[item])

        account_governance.apply_document_account_defaults(doc)

        self.assertEqual(item.cost_center, "Main - D")

    def test_business_user_same_company_account_is_forced_to_default(self):
        item = FakeRow(income_account="Other Revenue - D", expense_account="Purchases - D")
        doc = FakeDoc("Sales Invoice", company="Demo Company", debit_to="Receivable - D", items=[item])

        account_governance.apply_document_account_defaults(doc)

        self.assertEqual(item.income_account, "Sales Revenue - D")

    def test_purchase_and_salary_fallback_to_operating_expense(self):
        db = account_governance.frappe.db
        original_accounts = db.account_rows
        original_defaults = db.company_defaults
        try:
            db.account_rows = {
                key: value
                for key, value in original_accounts.items()
                if key not in {"Purchases - D"}
            }
            db.company_defaults = {
                key: value
                for key, value in original_defaults.items()
                if key != "default_expense_account"
            }
            account_map = account_governance.get_company_account_map("Demo Company")
        finally:
            db.account_rows = original_accounts
            db.company_defaults = original_defaults

        self.assertEqual(account_map["operating_expenses"], "Operating Expenses - D")
        self.assertEqual(account_map["purchases"], "Operating Expenses - D")
        self.assertEqual(account_map["salary_expense"], "Operating Expenses - D")

    def test_cash_customer_payment_defaults_to_cash_and_receivable(self):
        doc = FakeDoc(
            "Payment Entry",
            company="Demo Company",
            payment_type="Receive",
            party_type="Customer",
            mode_of_payment="Cash",
            paid_from="",
            paid_to="",
        )

        account_governance.apply_document_account_defaults(doc)

        self.assertEqual(doc.paid_from, "Receivable - D")
        self.assertEqual(doc.paid_to, "Cash - D")

    def test_non_superadmin_cannot_change_account_fields_after_save(self):
        before = FakeDoc("Sales Invoice", company="Demo Company", debit_to="Receivable - D")
        doc = FakeDoc("Sales Invoice", before=before, company="Demo Company", debit_to="Wrong - X")

        with self.assertRaises(Exception):
            account_governance.protect_account_fields(doc)

    def test_non_superadmin_cannot_change_cost_center_fields_after_save(self):
        before = FakeDoc("Sales Order", company="Demo Company", items=[FakeRow(cost_center="Main - D")])
        doc = FakeDoc("Sales Order", before=before, company="Demo Company", items=[FakeRow(cost_center="Project - D")])

        with self.assertRaises(Exception):
            account_governance.protect_account_fields(doc)


if __name__ == "__main__":
    unittest.main()
