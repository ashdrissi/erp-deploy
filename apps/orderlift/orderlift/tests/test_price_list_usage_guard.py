import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
frappe_stub.get_roles = lambda user=None: ["Sales User"]
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
utils_stub.nowdate = lambda: "2026-06-20"
sys.modules["frappe.utils"] = utils_stub

from orderlift.orderlift_sales.utils import price_list_usage_guard
import orderlift.orderlift_sales.utils.price_list_scope as price_list_scope_mod


class MetaStub:
    def __init__(self, fields):
        self.fields = set(fields)

    def has_field(self, fieldname):
        return fieldname in self.fields

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


class DocStub(dict):
    doctype = "Quotation"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.meta = MetaStub({"selling_price_list", "selected_selling_price_lists", "source_pricing_sheet"})

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def set(self, key, value):
        self[key] = value


class DbStub:
    def __init__(self, item_price_rows=None):
        self.item_price_rows = item_price_rows or []

    def has_column(self, doctype, fieldname):
        if doctype != "Item Price":
            return False
        return fieldname in {
            "selling",
            "enabled",
            "valid_from",
            "valid_upto",
            "custom_policy_max_discount_percent",
            "custom_benchmark_rule_max_discount_percent",
            "custom_fallback_max_discount_percent",
            "custom_pricing_builder",
            "custom_source_buying_price_list",
            "custom_benchmark_policy",
            "custom_benchmark_is_fallback",
            "custom_benchmark_rule_label",
            "custom_final_margin_percent",
            "custom_last_builder_buy_rate",
            "custom_builder_expense_amount",
            "custom_builder_customs_amount",
            "custom_builder_margin_basis",
            "custom_target_margin_percent",
        }

    def sql(self, query, params=None, pluck=False, as_dict=False):
        rows = [row for row in self.item_price_rows if row["price_list"] in params["price_lists"]]
        rows = [row for row in rows if row["item_code"] in params["item_codes"]]
        return [row["item_code"] for row in rows] if pluck else rows


class TestPriceListUsageGuard(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(price_list_usage_guard.frappe, "db", None)
        self.original_validate_visible_price_list = price_list_usage_guard.validate_visible_price_list
        self.original_get_roles = price_list_usage_guard.frappe.get_roles
        self.original_user = price_list_usage_guard.frappe.session.user
        self.original_price_scope_frappe = price_list_scope_mod.frappe
        price_list_usage_guard.frappe.db = DbStub()
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Sales User"]
        price_list_usage_guard.frappe.session.user = "sales@example.com"
        price_list_scope_mod.frappe = price_list_usage_guard.frappe
        price_list_usage_guard.validate_visible_price_list = (
            lambda price_list, kind=None, required=False, company=None: price_list
        )

    def tearDown(self):
        if self.original_db is None:
            delattr(price_list_usage_guard.frappe, "db")
        else:
            price_list_usage_guard.frappe.db = self.original_db
        price_list_usage_guard.validate_visible_price_list = self.original_validate_visible_price_list
        price_list_usage_guard.frappe.get_roles = self.original_get_roles
        price_list_usage_guard.frappe.session.user = self.original_user
        price_list_scope_mod.frappe = self.original_price_scope_frappe

    def test_quotation_items_require_allowed_selling_price_list(self):
        doc = DocStub(
            selected_selling_price_lists=[],
            items=[{"item_code": "ITEM-001", "rate": 100}],
        )

        with self.assertRaisesRegex(ValueError, "Selling Price List is required"):
            price_list_usage_guard.validate_quotation_price_list(doc)

    def test_privileged_business_role_still_needs_sales_pricing_source(self):
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Pricing Manager"]
        doc = DocStub(
            selected_selling_price_lists=[],
            items=[{"item_code": "ITEM-001", "rate": 100}],
        )

        with self.assertRaisesRegex(ValueError, "Selling Price List is required"):
            price_list_usage_guard.validate_quotation_price_list(doc)

    def test_source_pricing_sheet_without_policy_snapshot_does_not_bypass_price_list(self):
        doc = DocStub(
            source_pricing_sheet="PS-001",
            selected_selling_price_lists=[],
            items=[{"item_code": "ITEM-001", "rate": 100}],
        )

        with self.assertRaisesRegex(ValueError, "Selling Price List is required"):
            price_list_usage_guard.validate_quotation_price_list(doc)

    def test_source_pricing_sheet_with_policy_snapshot_can_skip_static_price_list(self):
        doc = DocStub(
            source_pricing_sheet="PS-001",
            selected_selling_price_lists=[],
            items=[{"item_code": "ITEM-001", "rate": 100, "source_gross_sell_rate": 100}],
        )

        price_list_usage_guard.validate_quotation_price_list(doc)

    def test_quotation_rate_cannot_go_below_selected_list_discount_floor(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 100,
                    "custom_policy_max_discount_percent": 10,
                }
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 80, "idx": 1}],
        )

        with self.assertRaisesRegex(ValueError, "below the allowed net rate"):
            price_list_usage_guard.validate_quotation_price_list(doc)

    def test_quotation_rate_at_selected_list_discount_floor_is_allowed(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 100,
                    "custom_policy_max_discount_percent": 10,
                }
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 90, "idx": 1}],
        )

        price_list_usage_guard.validate_quotation_price_list(doc)

    def test_quotation_rate_can_match_later_selected_selling_price_list(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell High",
                    "price_list_rate": 200,
                    "custom_policy_max_discount_percent": 10,
                },
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell Low",
                    "price_list_rate": 100,
                    "custom_policy_max_discount_percent": 10,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[
                {"price_list": "Sell High", "is_active": 1, "sequence": 10},
                {"price_list": "Sell Low", "is_active": 1, "sequence": 20},
            ],
            items=[{"item_code": "ITEM-001", "rate": 100, "idx": 1}],
        )

        price_list_usage_guard.validate_quotation_price_list(doc)

    def test_quotation_row_source_selling_price_list_uses_that_list_floor(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell High",
                    "price_list_rate": 200,
                    "custom_policy_max_discount_percent": 10,
                },
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell Low",
                    "price_list_rate": 100,
                    "custom_policy_max_discount_percent": 10,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[
                {"price_list": "Sell High", "is_active": 1, "sequence": 10},
                {"price_list": "Sell Low", "is_active": 1, "sequence": 20},
            ],
            items=[
                {
                    "item_code": "ITEM-001",
                    "source_selling_price_list": "Sell Low",
                    "rate": 80,
                    "idx": 1,
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "Sell Low"):
            price_list_usage_guard.validate_quotation_price_list(doc)

    def test_quotation_row_source_selling_price_list_must_be_selected_and_priced(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell High",
                    "price_list_rate": 200,
                    "custom_policy_max_discount_percent": 10,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell High", "is_active": 1, "sequence": 10}],
            items=[
                {
                    "item_code": "ITEM-001",
                    "source_selling_price_list": "Sell Low",
                    "rate": 200,
                    "idx": 1,
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "not priced in selected Selling Price List Sell Low"):
            price_list_usage_guard.validate_quotation_price_list(doc)

    def test_server_reprices_stale_row_when_one_selected_list_remains(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell Min",
                    "price_list_rate": 15033.213,
                    "custom_policy_max_discount_percent": 0,
                },
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell Normal",
                    "price_list_rate": 16408.743,
                    "custom_policy_max_discount_percent": 10,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell Min", "is_active": 1, "sequence": 10}],
            items=[
                {
                    "item_code": "ITEM-001",
                    "source_selling_price_list": "Sell Normal",
                    "source_discount_percent": 10,
                    "rate": 14767.8687,
                    "qty": 1,
                    "idx": 1,
                }
            ],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertEqual(row["source_selling_price_list"], "Sell Min")
        self.assertEqual(row["source_discount_percent"], 0)
        self.assertAlmostEqual(row["rate"], 15033.213)
        self.assertAlmostEqual(row["source_discounted_sell_rate"], 15033.213)
        price_list_usage_guard.validate_quotation_price_list(doc)

    def test_server_keeps_valid_lower_list_row_without_stale_source(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell High",
                    "price_list_rate": 200,
                    "custom_policy_max_discount_percent": 10,
                },
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell Low",
                    "price_list_rate": 100,
                    "custom_policy_max_discount_percent": 10,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[
                {"price_list": "Sell High", "is_active": 1, "sequence": 10},
                {"price_list": "Sell Low", "is_active": 1, "sequence": 20},
            ],
            items=[{"item_code": "ITEM-001", "rate": 100, "qty": 1, "idx": 1}],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertEqual(row["rate"], 100)
        self.assertNotIn("source_selling_price_list", row)

    def test_admin_override_bypasses_selling_price_list_requirement(self):
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        doc = DocStub(
            selected_selling_price_lists=[],
            items=[{"item_code": "ITEM-001", "rate": 100}],
        )

        price_list_usage_guard.validate_quotation_price_list(doc)

    def test_admin_override_allows_rate_below_floor(self):
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 100,
                    "custom_policy_max_discount_percent": 10,
                }
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 10, "idx": 1}],
        )

        price_list_usage_guard.validate_quotation_price_list(doc)

    def test_admin_override_skips_auto_repricing(self):
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell Min",
                    "price_list_rate": 15033,
                    "custom_policy_max_discount_percent": 0,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell Min", "is_active": 1, "sequence": 10}],
            items=[
                {
                    "item_code": "ITEM-001",
                    "source_selling_price_list": "Sell Normal",
                    "source_discount_percent": 10,
                    "rate": 50,
                    "qty": 1,
                    "idx": 1,
                }
            ],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertEqual(row["rate"], 50)
        self.assertEqual(row["source_discount_percent"], 10)

    def test_admin_override_bypasses_sales_order_validates(self):
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Orderlift Admin"]
        price_list_usage_guard.frappe.db = DbStub()
        doc = DocStub(
            selling_price_list="Sell A",
            items=[{"item_code": "ITEM-001", "rate": 10}],
        )

        with self.assertRaisesRegex(ValueError, "not priced in Selling Price List"):
            price_list_usage_guard.validate_sales_order_price_list(doc)

    def test_commercial_sales_order_cannot_bypass(self):
        price_list_usage_guard.frappe.get_roles = lambda user=None: ["Sales User"]
        price_list_usage_guard.frappe.db = DbStub()
        doc = DocStub(
            selling_price_list="Sell A",
            items=[{"item_code": "ITEM-001", "rate": 10}],
        )

        with self.assertRaisesRegex(ValueError, "not priced in Selling Price List"):
            price_list_usage_guard.validate_sales_order_price_list(doc)

    def test_builder_stamped_quotation_item_gets_margin_from_stamp_base_price_basis(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 140,
                    "custom_policy_max_discount_percent": 0,
                    "custom_pricing_builder": "PBU-01",
                    "custom_last_builder_buy_rate": 100,
                    "custom_builder_expense_amount": 10,
                    "custom_builder_customs_amount": 5,
                    "custom_builder_margin_basis": "Base Price",
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 140, "qty": 1, "idx": 1}],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertEqual(row["source_margin_percent"], 25)
        self.assertEqual(row["source_margin_basis"], "Base Price")

    def test_builder_stamped_quotation_item_margin_loaded_cost_basis(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 138,
                    "custom_policy_max_discount_percent": 0,
                    "custom_pricing_builder": "PBU-01",
                    "custom_last_builder_buy_rate": 100,
                    "custom_builder_expense_amount": 10,
                    "custom_builder_customs_amount": 5,
                    "custom_builder_margin_basis": "Loaded Cost",
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 138, "qty": 1, "idx": 1}],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertEqual(row["source_margin_basis"], "Loaded Cost")
        self.assertAlmostEqual(row["source_margin_percent"], 20)

    def test_builder_stamped_quotation_item_margin_negative_below_cost(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 90,
                    "custom_policy_max_discount_percent": 0,
                    "custom_pricing_builder": "PBU-01",
                    "custom_last_builder_buy_rate": 100,
                    "custom_builder_expense_amount": 10,
                    "custom_builder_customs_amount": 5,
                    "custom_builder_margin_basis": "Base Price",
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 90, "qty": 1, "idx": 1}],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertEqual(row["source_margin_percent"], -25)

    def test_unstamped_quotation_item_skips_margin(self):
        price_list_usage_guard.frappe.db = DbStub(
            [
                {
                    "item_code": "ITEM-001",
                    "price_list": "Sell A",
                    "price_list_rate": 120,
                    "custom_policy_max_discount_percent": 10,
                },
            ]
        )
        doc = DocStub(
            selected_selling_price_lists=[{"price_list": "Sell A", "is_active": 1, "sequence": 10}],
            items=[{"item_code": "ITEM-001", "rate": 120, "qty": 1, "idx": 1}],
        )

        price_list_usage_guard.reprice_quotation_items_from_selected_price_lists(doc)

        row = doc["items"][0]
        self.assertNotIn("source_margin_percent", row)
        self.assertNotIn("source_margin_basis", row)


if __name__ == "__main__":
    unittest.main()
