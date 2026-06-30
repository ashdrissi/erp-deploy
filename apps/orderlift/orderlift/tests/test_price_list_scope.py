import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.session = types.SimpleNamespace(user="test@example.com")
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
sys.modules["frappe.utils"] = utils_stub

from orderlift.orderlift_sales.utils import price_list_scope


class TestPriceListScope(unittest.TestCase):
    def setUp(self):
        self.rows = {
            "Buy OL": {"name": "Buy OL", "buying": 1, "selling": 0, "custom_company": "Orderlift"},
            "Sell OL": {"name": "Sell OL", "buying": 0, "selling": 1, "custom_company": "Orderlift"},
            "Buy Other": {"name": "Buy Other", "buying": 1, "selling": 0, "custom_company": "OtherCo"},
        }

        class DbStub:
            def has_column(_, doctype, fieldname):
                return doctype == "Price List" and fieldname in {"enabled", "buying", "selling", "custom_company"}

            def get_value(_, doctype, name, fields, as_dict=False):
                if isinstance(name, dict):
                    row = next(
                        (
                            row
                            for row in self.rows.values()
                            if all(row.get(key) == value for key, value in name.items())
                        ),
                        None,
                    )
                else:
                    row = self.rows.get(name)
                if not row:
                    return None
                if isinstance(fields, str):
                    return row.get(fields)
                return {field: row.get(field) for field in fields} if as_dict else row.get(fields[0])

        def get_all(doctype, filters=None, fields=None, pluck=None, **kwargs):
            out = []
            for row in self.rows.values():
                if filters and any(row.get(key) != value for key, value in filters.items() if key != "enabled"):
                    continue
                out.append(row.get(pluck) if pluck else types.SimpleNamespace(**{field: row.get(field) for field in fields}))
            return sorted(out, key=lambda value: value if isinstance(value, str) else value.name)

        self.original_db = getattr(price_list_scope.frappe, "db", None)
        self.original_get_all = getattr(price_list_scope.frappe, "get_all", None)
        self.original_throw = getattr(price_list_scope.frappe, "throw", None)
        self.original_resolve_current_company = price_list_scope.resolve_current_company
        price_list_scope.frappe.db = DbStub()
        price_list_scope.frappe.get_all = get_all
        price_list_scope.frappe.throw = frappe_stub.throw
        price_list_scope.resolve_current_company = lambda user=None: "Orderlift"

    def tearDown(self):
        price_list_scope.frappe.db = self.original_db
        price_list_scope.resolve_current_company = self.original_resolve_current_company
        if self.original_get_all:
            price_list_scope.frappe.get_all = self.original_get_all
        else:
            delattr(price_list_scope.frappe, "get_all")
        if self.original_throw:
            price_list_scope.frappe.throw = self.original_throw
        else:
            delattr(price_list_scope.frappe, "throw")

    def test_get_price_list_names_filters_by_type_and_current_company(self):
        self.assertEqual(price_list_scope.get_price_list_names("buying"), ["Buy OL"])
        self.assertEqual(price_list_scope.get_price_list_names("selling"), ["Sell OL"])

    def test_validate_price_list_scope_rejects_other_company(self):
        with self.assertRaisesRegex(ValueError, "does not belong to company Orderlift"):
            price_list_scope.validate_price_list_scope("Buy Other", kind="buying", required=True)

    def test_validate_price_list_scope_rejects_wrong_type(self):
        with self.assertRaisesRegex(ValueError, "is not a buying price list"):
            price_list_scope.validate_price_list_scope("Sell OL", kind="buying", required=True)

    def test_benchmark_price_list_keeps_native_selling_flag_for_erpnext_validation(self):
        doc = types.SimpleNamespace(custom_price_list_type="Benchmark", buying=1, selling=0)

        explicit = price_list_scope.normalize_price_list_type(doc)

        self.assertEqual(explicit, "Benchmark")
        self.assertEqual(doc.buying, 0)
        self.assertEqual(doc.selling, 1)

    def test_explicit_benchmark_type_overrides_native_selling_flag(self):
        self.assertEqual(
            price_list_scope.get_price_list_type(values={"custom_price_list_type": "Benchmark", "buying": 0, "selling": 1}),
            "Benchmark",
        )

    def test_duplicate_name_validation_reports_existing_company_and_active_company(self):
        doc = types.SimpleNamespace(name="new-price-list-1", price_list_name="Buy Other")

        with self.assertRaisesRegex(ValueError, "already exists under company OtherCo"):
            price_list_scope.validate_price_list_unique_name_context(doc)

    def test_duplicate_name_validation_allows_current_doc(self):
        doc = types.SimpleNamespace(name="Buy OL", price_list_name="Buy OL")

        price_list_scope.validate_price_list_unique_name_context(doc)


if __name__ == "__main__":
    unittest.main()
