import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
frappe_stub.get_roles = lambda user=None: ["Sales User"]
frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
sys.modules["frappe.utils"] = utils_stub

from orderlift.orderlift_sales import sales_order_pricing_hooks
import orderlift.orderlift_sales.utils.price_list_scope as price_list_scope_mod


class MetaStub:
    def __init__(self, fields=None):
        self.fields = set(fields or [])

    def has_field(self, fieldname):
        return fieldname in self.fields

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


class DocStub(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.meta = MetaStub(set(kwargs) | ALL_FIELDS)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def set(self, key, value):
        self[key] = value

    def append(self, key, value):
        self.setdefault(key, []).append(DocStub(**value))


ALL_FIELDS = {
    "docstatus",
    "items",
    "source_pricing_sheet",
    "selected_selling_price_lists",
    "name",
    "idx",
    "item_code",
    "item_name",
    "qty",
    "price_list_rate",
    "rate",
    "discount_percentage",
    "amount",
    "net_rate",
    "net_amount",
    "prevdoc_doctype",
    "prevdoc_docname",
    "prevdoc_detail_docname",
    "source_pricing_sheet_line",
    "source_pricing_scenario",
    "source_pricing_override",
    "source_pricing_policy",
    "source_scenario_rule",
    "source_margin_rule",
    "source_sales_person",
    "source_geography",
    "source_customs_applied",
    "source_customs_basis",
    "source_selling_price_list",
    "source_price_list_sell_rate",
    "source_gross_sell_rate",
    "source_discount_percent",
    "source_max_discount_percent",
    "source_discount_amount",
    "source_discounted_sell_rate",
    "source_margin_percent",
    "source_margin_basis",
    "source_commission_rate",
    "source_commission_amount",
}


class TestSalesOrderPricingHooks(unittest.TestCase):
    def setUp(self):
        self.original_get_doc = getattr(sales_order_pricing_hooks.frappe, "get_doc", None)
        self.original_get_roles = sales_order_pricing_hooks.frappe.get_roles
        self.original_user = sales_order_pricing_hooks.frappe.session.user
        self.original_price_scope_frappe = price_list_scope_mod.frappe
        price_list_scope_mod.frappe = sales_order_pricing_hooks.frappe
        sales_order_pricing_hooks.frappe.get_roles = lambda user=None: ["Sales User"]
        sales_order_pricing_hooks.frappe.session.user = "sales@example.com"

    def tearDown(self):
        if self.original_get_doc is None:
            if hasattr(sales_order_pricing_hooks.frappe, "get_doc"):
                delattr(sales_order_pricing_hooks.frappe, "get_doc")
        else:
            sales_order_pricing_hooks.frappe.get_doc = self.original_get_doc
        sales_order_pricing_hooks.frappe.get_roles = self.original_get_roles
        sales_order_pricing_hooks.frappe.session.user = self.original_user
        price_list_scope_mod.frappe = self.original_price_scope_frappe

    def test_normal_user_sales_order_inherits_submitted_quotation_pricing(self):
        quote = self._quotation(docstatus=1)
        so = self._sales_order(rate=1, qty=3)
        sales_order_pricing_hooks.frappe.get_doc = lambda doctype, name: quote

        sales_order_pricing_hooks.copy_quotation_pricing_snapshot(so)
        sales_order_pricing_hooks.validate_sales_order_source_lock(so)
        sales_order_pricing_hooks.validate_sales_order_pricing_locked_to_quotation(so)

        row = so["items"][0]
        self.assertEqual(so["source_pricing_sheet"], "PS-001")
        self.assertEqual(row["rate"], 90)
        self.assertEqual(row["source_selling_price_list"], "Sell A")
        self.assertEqual(row["source_price_list_sell_rate"], 95)
        self.assertEqual(row["source_discount_percent"], 10)
        self.assertEqual(row["amount"], 270)

    def test_normal_user_cannot_save_direct_sales_order(self):
        so = DocStub(docstatus=0, items=[DocStub(item_code="ITEM-001", qty=1, rate=90, idx=1)])

        with self.assertRaisesRegex(ValueError, "submitted Quotation"):
            sales_order_pricing_hooks.validate_sales_order_source_lock(so)

    def test_normal_user_requires_submitted_quotation(self):
        quote = self._quotation(docstatus=0)
        so = self._sales_order()
        sales_order_pricing_hooks.frappe.get_doc = lambda doctype, name: quote

        with self.assertRaisesRegex(ValueError, "must be submitted"):
            sales_order_pricing_hooks.validate_sales_order_source_lock(so)

    def test_normal_user_cannot_exceed_quoted_quantity(self):
        quote = self._quotation(docstatus=1, qty=5)
        so = self._sales_order(qty=6)
        sales_order_pricing_hooks.frappe.get_doc = lambda doctype, name: quote

        with self.assertRaisesRegex(ValueError, "quantity cannot exceed"):
            sales_order_pricing_hooks.validate_sales_order_source_lock(so)

    def test_pricing_override_can_save_direct_sales_order(self):
        sales_order_pricing_hooks.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        so = DocStub(docstatus=0, items=[DocStub(item_code="ITEM-001", qty=1, rate=10, idx=1)])

        sales_order_pricing_hooks.validate_sales_order_source_lock(so)
        sales_order_pricing_hooks.validate_sales_order_item_discount_caps(so)

    def test_pricing_override_does_not_overwrite_manual_rate(self):
        sales_order_pricing_hooks.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        quote = self._quotation(docstatus=1)
        so = self._sales_order(rate=50, qty=3)
        sales_order_pricing_hooks.frappe.get_doc = lambda doctype, name: quote

        sales_order_pricing_hooks.copy_quotation_pricing_snapshot(so)

        row = so["items"][0]
        self.assertEqual(row["rate"], 50)
        self.assertEqual(row["source_selling_price_list"], "Sell A")

    def test_normal_user_discount_cap_is_enforced(self):
        so = self._sales_order(rate=70, qty=1)
        row = so["items"][0]
        row["source_gross_sell_rate"] = 100
        row["source_discount_percent"] = 30
        row["source_max_discount_percent"] = 10

        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            sales_order_pricing_hooks.validate_sales_order_item_discount_caps(so)

    def _quotation(self, docstatus=1, qty=5):
        quote_item = DocStub(
            name="QTN-ITEM-1",
            idx=1,
            item_code="ITEM-001",
            qty=qty,
            price_list_rate=100,
            rate=90,
            discount_percentage=10,
            amount=90 * qty,
            net_rate=90,
            net_amount=90 * qty,
            source_selling_price_list="Sell A",
            source_price_list_sell_rate=95,
            source_gross_sell_rate=100,
            source_discount_percent=10,
            source_max_discount_percent=15,
            source_discount_amount=10,
            source_discounted_sell_rate=90,
            source_margin_percent=20,
            source_margin_basis="Base Price",
        )
        return DocStub(
            name="QTN-001",
            docstatus=docstatus,
            source_pricing_sheet="PS-001",
            selected_selling_price_lists=[DocStub(price_list="Sell A", is_active=1, sequence=10)],
            items=[quote_item],
        )

    def _sales_order(self, rate=90, qty=3):
        return DocStub(
            docstatus=0,
            items=[
                DocStub(
                    idx=1,
                    item_code="ITEM-001",
                    qty=qty,
                    price_list_rate=rate,
                    rate=rate,
                    discount_percentage=0,
                    amount=rate * qty,
                    net_rate=rate,
                    net_amount=rate * qty,
                    prevdoc_doctype="Quotation",
                    prevdoc_docname="QTN-001",
                    prevdoc_detail_docname="QTN-ITEM-1",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
