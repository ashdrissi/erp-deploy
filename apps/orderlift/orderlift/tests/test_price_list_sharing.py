import importlib
import sys
import types
import unittest


STUBBED_MODULES = (
    "frappe",
    "frappe.utils",
    "orderlift.role_capabilities",
    "orderlift.orderlift_sales.utils.price_list_scope",
    "orderlift.orderlift_sales.utils.price_list_sharing",
)


class RowStub(types.SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


class PriceListDocStub:
    doctype = "Price List"
    name = "Source Selling"
    custom_price_list_type = "Selling"
    custom_company = "Orderlift Maroc Distribution"
    buying = 0
    selling = 1

    def __init__(self, rows=None, before=None):
        self.custom_price_list_sharing = rows or []
        self._before = before

    def get(self, key):
        return getattr(self, key)

    def get_doc_before_save(self):
        return self._before


class DbStub:
    def __init__(self):
        self.disabled = []
        self.existing_shared = "Source Selling (Orderlift Maroc Installation)"
        self.owner_companies = {
            "Source Selling": "Orderlift Maroc Distribution",
        }
        self.shared_from = {}
        self.source_buying_lists = {}

    def has_column(self, doctype, fieldname):
        return doctype == "Price List" and fieldname in {
            "custom_is_shared_from",
            "custom_company",
        }

    def exists(self, doctype, name):
        if doctype == "DocType":
            return name in {"Price List", "Price List Sharing"}
        return doctype == "Price List" and bool(name)

    def set_value(self, doctype, name, fieldname, value=None, update_modified=True):
        if doctype == "Price List" and fieldname == "enabled" and value == 0:
            self.disabled.append(name)

    def get_value(self, doctype, filters, fieldname, order_by=None, as_dict=False):
        if doctype != "Price List":
            return ""
        if isinstance(fieldname, list):
            values = {}
            if isinstance(filters, str):
                values["custom_company"] = self.owner_companies.get(filters, "")
                values["custom_is_shared_from"] = self.shared_from.get(filters, "")
            return values if as_dict else values
        if fieldname == "custom_company":
            if isinstance(filters, str):
                return self.owner_companies.get(filters, "Unrelated Company")
            return ""
        if fieldname == "custom_is_shared_from":
            if isinstance(filters, str):
                return self.shared_from.get(filters, "")
            return ""
        if fieldname == "custom_source_buying_price_lists":
            if isinstance(filters, str):
                return self.source_buying_lists.get(filters, "")
            return ""
        if filters == {
            "custom_is_shared_from": "Source Selling",
            "custom_company": "Orderlift Maroc Installation",
        }:
            return self.existing_shared
        return ""


class TestPriceListSharing(unittest.TestCase):
    def setUp(self):
        self.original_modules = {name: sys.modules.get(name) for name in STUBBED_MODULES}
        for name in STUBBED_MODULES:
            sys.modules.pop(name, None)

        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda value, *args, **kwargs: value
        frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
        frappe_stub.defaults = types.SimpleNamespace(get_global_default=lambda key: "MAD")
        frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
        frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
        frappe_stub.get_roles = lambda user=None: ["Sales User"]
        self.sharing_rows = []

        def _fake_get_all(doctype, filters=None, fields=None, **kwargs):
            if doctype != "Price List Sharing":
                return []
            rows = []
            for row in self.sharing_rows:
                if filters and filters.get("parent") and row.parent != filters["parent"]:
                    continue
                if filters and filters.get("is_active") == 1 and not getattr(row, "is_active", 1):
                    continue
                out = {}
                for field in fields or []:
                    out[field] = getattr(row, field, "")
                rows.append(out)
            return rows

        frappe_stub.get_all = _fake_get_all
        sys.modules["frappe"] = frappe_stub

        utils_stub = types.ModuleType("frappe.utils")
        utils_stub.cint = lambda value=0: int(float(value or 0))
        utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
        utils_stub.now_datetime = lambda: "2026-08-15 12:00:00"
        sys.modules["frappe.utils"] = utils_stub

        self.price_list_sharing = importlib.import_module(
            "orderlift.orderlift_sales.utils.price_list_sharing"
        )
        self.db = DbStub()
        self.price_list_sharing.frappe.db = self.db

    def tearDown(self):
        for name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def test_removed_sharing_row_disables_previous_shared_list_before_save(self):
        before = PriceListDocStub(rows=[RowStub(name="ROW-1", shared_price_list="Shared Buying")])
        doc = PriceListDocStub(rows=[], before=before)

        self.price_list_sharing.ensure_shared_price_lists(doc)

        self.assertEqual(self.db.disabled, ["Shared Buying"])

    def test_shared_list_name_reuses_existing_source_target_mirror(self):
        shared_name = self.price_list_sharing._shared_list_name(
            "Source Selling",
            "Orderlift Maroc Installation",
        )

        self.assertEqual(shared_name, "Source Selling (Orderlift Maroc Installation)")

    def test_resolve_shared_companies_from_price_lists(self):
        self.sharing_rows = [
            RowStub(parent="Source Selling", company="Orderlift Maroc Installation", is_active=1),
            RowStub(parent="Source Selling", company="Orderlift Maroc Distribution", is_active=1),
            RowStub(parent="Source Selling", company="", is_active=1),
            RowStub(parent="Source Selling", company="Orderlift Maroc Installation", is_active=1),
            RowStub(parent="Source Selling", company="Orderlift Maroc Transit", is_active=0),
        ]

        companies = self.price_list_sharing.resolve_shared_companies_from_price_lists(
            "Orderlift Maroc Distribution",
            ["Source Selling", "Unrelated List"],
        )

        self.assertEqual(companies, ["Orderlift Maroc Installation"])

    def test_resolve_shared_companies_follows_source_buying_lists(self):
        self.db.owner_companies = {
            "Inst Selling": "Orderlift Maroc Installation",
            "Mirror Buying": "Orderlift Maroc Installation",
            "Source Selling": "Orderlift Maroc Distribution",
        }
        self.db.shared_from = {"Mirror Buying": "Source Selling"}
        self.db.source_buying_lists = {"Inst Selling": "Mirror Buying"}

        companies = self.price_list_sharing.resolve_shared_companies_from_price_lists(
            "Orderlift Maroc Installation",
            ["Inst Selling"],
        )

        self.assertEqual(companies, ["Orderlift Maroc Distribution"])

    def test_resolve_shared_stock_companies_from_doc(self):
        self.sharing_rows = [
            RowStub(parent="Source Selling", company="Orderlift Maroc Installation", is_active=1),
        ]
        doc = types.SimpleNamespace(
            company="Orderlift Maroc Distribution",
            selling_price_list="Source Selling",
            selected_selling_price_lists=[RowStub(price_list="Source Selling")],
            items=[RowStub(source_selling_price_list="Source Selling")],
            lines=[],
        )

        companies = self.price_list_sharing.resolve_shared_stock_companies(doc)

        self.assertEqual(companies, ["Orderlift Maroc Installation"])

    def test_resolve_shared_stock_companies_without_lists_is_empty(self):
        doc = types.SimpleNamespace(
            company="Orderlift Maroc Distribution",
            selling_price_list="",
            selected_selling_price_lists=[],
            items=[],
            lines=[],
        )

        self.assertEqual(self.price_list_sharing.resolve_shared_stock_companies(doc), [])

    def test_resolve_shared_companies_from_buying_price_lists(self):
        self.db.owner_companies = {
            "Source Selling": "Orderlift Maroc Distribution",
            "Mirror Buying": "Orderlift Maroc Installation",
            "Own List": "Orderlift Maroc Installation",
        }
        self.db.shared_from = {
            "Mirror Buying": "Source Selling",
            "Self Mirror": "Own List",
        }

        companies = self.price_list_sharing.resolve_shared_companies_from_buying_price_lists(
            "Orderlift Maroc Installation",
            ["Mirror Buying", "Plain Buying", "Self Mirror"],
        )

        self.assertEqual(companies, ["Orderlift Maroc Distribution"])

    def test_resolve_shared_stock_companies_unions_both_directions(self):
        self.sharing_rows = [
            RowStub(parent="Inst Selling", company="Orderlift Maroc Distribution", is_active=1),
        ]
        self.db.owner_companies = {
            "Source Selling": "Orderlift Maroc Distribution",
            "Inst Selling": "Orderlift Maroc Installation",
            "Mirror Buying": "Orderlift Maroc Installation",
        }
        self.db.shared_from = {"Mirror Buying": "Source Selling"}
        doc = types.SimpleNamespace(
            company="Orderlift Maroc Installation",
            selling_price_list="Inst Selling",
            selected_selling_price_lists=[RowStub(price_list="Inst Selling")],
            selected_buying_price_lists=[RowStub(price_list="Mirror Buying")],
            buying_price_list="",
            custom_source_buying_price_lists=[],
            items=[],
            lines=[],
        )

        companies = self.price_list_sharing.resolve_shared_stock_companies(doc)

        self.assertEqual(companies, ["Orderlift Maroc Distribution"])


if __name__ == "__main__":
    unittest.main()
