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

    def has_column(self, doctype, fieldname):
        return doctype == "Price List" and fieldname in {
            "custom_is_shared_from",
            "custom_company",
        }

    def exists(self, doctype, name):
        return doctype == "Price List" and bool(name)

    def set_value(self, doctype, name, fieldname, value=None, update_modified=True):
        if doctype == "Price List" and fieldname == "enabled" and value == 0:
            self.disabled.append(name)

    def get_value(self, doctype, filters, fieldname, order_by=None):
        if doctype != "Price List":
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


if __name__ == "__main__":
    unittest.main()
