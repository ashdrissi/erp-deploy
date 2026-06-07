import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message: (_ for _ in ()).throw(Exception(message))
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift.sales.utils import sales_order_defaults


class FakeMeta:
    def __init__(self, fields):
        self.fields = set(fields)

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


class FakeRow:
    def __init__(self, **values):
        self.meta = FakeMeta(values.keys())
        for key, value in values.items():
            setattr(self, key, value)

    def get(self, fieldname):
        return getattr(self, fieldname, None)


class FakeDoc(FakeRow):
    def __init__(self, **values):
        items = values.pop("items", [])
        super().__init__(**values)
        self.items = items

    def get(self, fieldname):
        if fieldname == "items":
            return self.items
        return super().get(fieldname)


class FakeDB:
    companies = {"Orderlift Maroc Installation": "OMI", "Orderlift": "OL"}
    cost_centers = {
        "Main - OL": {"company": "Orderlift", "is_group": 0, "disabled": 0},
        "Main - OMI": {"company": "Orderlift Maroc Installation", "is_group": 0, "disabled": 0},
    }
    warehouses = {
        "Main Warehouse - OL": {"company": "Orderlift", "is_group": 0, "disabled": 0},
        "Main Warehouse - OMI": {"company": "Orderlift Maroc Installation", "is_group": 0, "disabled": 0},
    }

    def get_value(self, doctype, name, fields, as_dict=False):
        if doctype == "Company" and fields == "abbr":
            return self.companies.get(name, "")
        source = self.cost_centers if doctype == "Cost Center" else self.warehouses if doctype == "Warehouse" else {}
        row = source.get(name)
        if not row:
            return None
        if as_dict:
            return types.SimpleNamespace(**{field: row.get(field) for field in fields})
        return row.get(fields)


class TestSalesOrderDefaults(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(sales_order_defaults.frappe, "db", None)
        self.original_get_all = getattr(sales_order_defaults.frappe, "get_all", None)
        self.original_get_meta = getattr(sales_order_defaults.frappe, "get_meta", None)
        sales_order_defaults.frappe.db = FakeDB()
        sales_order_defaults.frappe.get_all = self.fake_get_all
        sales_order_defaults.frappe.get_meta = lambda doctype: FakeMeta(["custom_orderlift_base_warehouse"])

    def tearDown(self):
        sales_order_defaults.frappe.db = self.original_db
        sales_order_defaults.frappe.get_all = self.original_get_all
        sales_order_defaults.frappe.get_meta = self.original_get_meta

    def fake_get_all(self, doctype, filters=None, pluck=None, order_by=None, limit_page_length=None):
        filters = filters or {}
        if doctype == "Cost Center":
            source = FakeDB.cost_centers
        elif doctype == "Warehouse":
            source = FakeDB.warehouses
        else:
            return []
        rows = [name for name, row in source.items() if all(row.get(key) == value for key, value in filters.items())]
        return sorted(rows)[:limit_page_length or len(rows)] if pluck == "name" else []

    def test_preferred_defaults_use_company_abbreviation(self):
        self.assertEqual(sales_order_defaults.get_default_cost_center("Orderlift Maroc Installation"), "Main - OMI")
        self.assertEqual(sales_order_defaults.get_default_warehouse("Orderlift Maroc Installation"), "Main Warehouse - OMI")

    def test_replaces_blank_or_wrong_company_values(self):
        row = FakeRow(cost_center="Main - OL", warehouse="")
        doc = FakeDoc(company="Orderlift Maroc Installation", set_warehouse="Main Warehouse - OL", items=[row])

        sales_order_defaults.apply_company_defaults(doc)

        self.assertEqual(doc.set_warehouse, "Main Warehouse - OMI")
        self.assertEqual(row.cost_center, "Main - OMI")
        self.assertEqual(row.warehouse, "Main Warehouse - OMI")

    def test_keeps_valid_company_values(self):
        row = FakeRow(cost_center="Main - OMI", warehouse="Main Warehouse - OMI")
        doc = FakeDoc(company="Orderlift Maroc Installation", set_warehouse="Main Warehouse - OMI", items=[row])

        sales_order_defaults.apply_company_defaults(doc)

        self.assertEqual(doc.set_warehouse, "Main Warehouse - OMI")
        self.assertEqual(row.cost_center, "Main - OMI")
        self.assertEqual(row.warehouse, "Main Warehouse - OMI")


if __name__ == "__main__":
    unittest.main()
