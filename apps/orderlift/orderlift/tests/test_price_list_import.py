import sys
import types
import unittest
from pathlib import Path


class AttrDict(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


class FakeField:
    def __init__(self, fieldname, fieldtype="Data"):
        self.fieldname = fieldname
        self.fieldtype = fieldtype


class FakeMeta:
    def __init__(self, fields):
        self.fields = [FakeField(fieldname, fieldtype) for fieldname, fieldtype in fields]

    def has_field(self, fieldname):
        return any(field.fieldname == fieldname for field in self.fields)

    def get_field(self, fieldname):
        return next((field for field in self.fields if field.fieldname == fieldname), None)


PRICE_LIST_META = FakeMeta(
    [
        ("price_list_name", "Data"),
        ("title", "Data"),
        ("custom_company", "Link"),
        ("currency", "Link"),
        ("enabled", "Check"),
        ("buying", "Check"),
        ("selling", "Check"),
        ("custom_auto_rebuild_from_source_buying_prices", "Check"),
        ("custom_pricing_builder", "Link"),
    ]
)
ITEM_PRICE_META = FakeMeta(
    [
        ("item_code", "Link"),
        ("price_list", "Link"),
        ("price_list_rate", "Currency"),
        ("currency", "Link"),
        ("uom", "Link"),
        ("buying", "Check"),
        ("selling", "Check"),
        ("custom_source_buying_price_list", "Link"),
        ("custom_benchmark_rule_max_discount_percent", "Percent"),
    ]
)


class FakeDoc(AttrDict):
    def __init__(self, doctype, **values):
        super().__init__(**values)
        self.doctype = doctype
        self.meta = PRICE_LIST_META if doctype == "Price List" else ITEM_PRICE_META

    def get(self, fieldname, default=None):
        return super().get(fieldname, default)

    def set(self, fieldname, value):
        self[fieldname] = value

    def insert(self, ignore_permissions=False):
        if self.doctype == "Price List":
            self.name = self.price_list_name
            DB["Price List"][self.name] = self
            return self
        if self.doctype == "Item Price":
            self.name = f"IP-{len(DB['Item Price']) + 1:05d}"
            DB["Item Price"][self.name] = self
            return self
        return self


DB = {"Price List": {}, "Item Price": {}}
ITEM_STOCK_UOMS = {}
ITEM_UOM_CONVERSIONS = set()

frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub

sys.modules.pop("orderlift.orderlift_sales.utils.price_list_import", None)
from orderlift.orderlift_sales.utils import price_list_import


class TestPriceListImport(unittest.TestCase):
    def setUp(self):
        DB["Price List"] = {
            "Source USD": FakeDoc(
                "Price List",
                name="Source USD",
                price_list_name="Source USD",
                title="Source USD",
                custom_company="Orderlift Distribution",
                currency="USD",
                enabled=1,
                buying=1,
                selling=0,
                custom_auto_rebuild_from_source_buying_prices=1,
                custom_pricing_builder="PBU-00001",
            )
        }
        DB["Item Price"] = {
            "IP-SRC-1": FakeDoc(
                "Item Price",
                name="IP-SRC-1",
                item_code="ITEM-001",
                price_list="Source USD",
                price_list_rate=100,
                currency="USD",
                uom="Nos",
                buying=1,
                selling=0,
                custom_source_buying_price_list="Source USD",
                custom_benchmark_rule_max_discount_percent=6,
            ),
            "IP-SRC-2": FakeDoc(
                "Item Price",
                name="IP-SRC-2",
                item_code="ITEM-002",
                price_list="Source USD",
                price_list_rate=200,
                currency="USD",
                uom="Nos",
                buying=1,
                selling=0,
            ),
        }
        ITEM_STOCK_UOMS.clear()
        ITEM_STOCK_UOMS.update({"ITEM-001": "Nos", "ITEM-002": "Nos"})
        ITEM_UOM_CONVERSIONS.clear()
        frappe_stub.get_meta = lambda doctype: PRICE_LIST_META if doctype == "Price List" else ITEM_PRICE_META
        frappe_stub.new_doc = lambda doctype: FakeDoc(doctype)
        frappe_stub.get_doc = self._get_doc
        frappe_stub.get_all = self._get_all
        frappe_stub.db = types.SimpleNamespace(exists=self._exists, get_value=self._get_value)
        price_list_import.resolve_current_company = lambda **kwargs: "Orderlift Installation"
        price_list_import.user_can_access_company = lambda company, user=None: company in {
            "Orderlift Distribution",
            "Orderlift Installation",
        }
        price_list_import.get_allowed_companies = lambda user=None: [
            "Orderlift Distribution",
            "Orderlift Installation",
        ]

    def test_import_creates_new_company_price_list_and_item_prices(self):
        result = price_list_import.import_price_list_from_existing(
            source_price_list="Source USD",
            target_price_list_name="Source USD - Installation",
            target_company="Orderlift Installation",
        )

        self.assertEqual(result["price_list"], "Source USD - Installation")
        self.assertEqual(result["item_prices_created"], 2)
        target = DB["Price List"]["Source USD - Installation"]
        self.assertEqual(target.custom_company, "Orderlift Installation")
        self.assertEqual(target.currency, "USD")
        self.assertEqual(target.custom_auto_rebuild_from_source_buying_prices, 0)
        copied = [doc for doc in DB["Item Price"].values() if doc.price_list == "Source USD - Installation"]
        self.assertEqual(len(copied), 2)
        self.assertEqual(copied[0].custom_benchmark_rule_max_discount_percent, 6)
        self.assertEqual(copied[0].uom, "Nos")

    def test_import_clears_stale_copied_item_price_uom(self):
        DB["Item Price"]["IP-SRC-2"].uom = "Pc"

        price_list_import.import_price_list_from_existing(
            source_price_list="Source USD",
            target_price_list_name="Source USD - Installation",
            target_company="Orderlift Installation",
        )

        copied_by_item = {
            doc.item_code: doc for doc in DB["Item Price"].values() if doc.price_list == "Source USD - Installation"
        }
        self.assertEqual(copied_by_item["ITEM-001"].uom, "Nos")
        self.assertEqual(copied_by_item["ITEM-002"].uom, "")

    def test_import_allows_same_target_company_with_unique_name(self):
        result = price_list_import.import_price_list_from_existing(
            source_price_list="Source USD",
            target_price_list_name="Source USD Copy",
            target_company="Orderlift Distribution",
        )

        self.assertEqual(result["price_list"], "Source USD Copy")
        self.assertEqual(DB["Price List"]["Source USD Copy"].custom_company, "Orderlift Distribution")
        copied = [doc for doc in DB["Item Price"].values() if doc.price_list == "Source USD Copy"]
        self.assertEqual(len(copied), 2)

    def test_price_list_ui_has_item_prices_report_and_source_label(self):
        app_root = Path(__file__).resolve().parents[2]
        form_js = app_root / "orderlift" / "public" / "js" / "price_list_import_20260602c.js"
        list_js = app_root / "orderlift" / "public" / "js" / "price_list_import_list_20260602a.js"
        form_source = form_js.read_text()
        list_source = list_js.read_text()

        self.assertIn("View Item Prices", form_source)
        self.assertIn('frappe.set_route("List", "Item Price", "Report")', form_source)
        self.assertIn("priceListSourceHtml", list_source)
        self.assertIn("custom_pricing_builder", list_source)
        self.assertIn("Manual", list_source)

    def _exists(self, doctype, name=None, *args, **kwargs):
        if doctype == "UOM Conversion Detail" and isinstance(name, dict):
            return (name.get("parent"), name.get("uom")) in ITEM_UOM_CONVERSIONS
        if isinstance(name, dict):
            return False
        return name in DB.get(doctype, {})

    def _get_value(self, doctype, name, fieldname):
        if doctype == "Item" and fieldname == "stock_uom":
            return ITEM_STOCK_UOMS.get(name)
        return None

    def _get_doc(self, doctype, name):
        return DB[doctype][name]

    def _get_all(self, doctype, filters=None, fields=None, **kwargs):
        rows = []
        for doc in DB.get(doctype, {}).values():
            if filters and any(doc.get(key) != value for key, value in filters.items()):
                continue
            if fields == ["name"]:
                rows.append(AttrDict(name=doc.name))
            else:
                rows.append(doc)
        return rows


if __name__ == "__main__":
    unittest.main()
