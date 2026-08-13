import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.session = types.SimpleNamespace(user="warehouse@example.com")
frappe_stub.PermissionError = PermissionError
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn) if args and not callable(args[0]) else (args[0] if args else (lambda fn: fn))
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.get_roles = lambda user=None: ["Logistics User"]
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
utils_stub.flt = lambda value=0, *args, **kwargs: float(value or 0)
utils_stub.now_datetime = lambda: "2026-07-21 12:00:00"
utils_stub.nowdate = lambda: "2026-07-21"
sys.modules["frappe.utils"] = utils_stub

menu_access_stub = types.ModuleType("orderlift.menu_access")
menu_access_stub.resolve_current_company = lambda user=None: "Orderlift"
sys.modules["orderlift.menu_access"] = menu_access_stub

role_capabilities_stub = types.ModuleType("orderlift.role_capabilities")
role_capabilities_stub.CAPABILITY_PRIVILEGED_PRICING = "privileged_pricing"
role_capabilities_stub.CAPABILITY_STOCK_RATE_MANAGEMENT = "stock_rate_management"
role_capabilities_stub.user_has_capability = lambda capability, user=None, roles=None: (
    capability == "privileged_pricing" and "Pricing Configuration" in (roles or set())
) or (
    capability == "stock_rate_management" and "Stock Manager" in (roles or set())
)
sys.modules["orderlift.role_capabilities"] = role_capabilities_stub

warehouse_access_stub = types.ModuleType("orderlift.warehouse_access")
warehouse_access_stub.get_allowed_warehouses = lambda: ["Main - O"]
sys.modules["orderlift.warehouse_access"] = warehouse_access_stub

from orderlift.orderlift_logistics.utils import stock_rate_review


class RowStub(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.idx = kwargs.get("idx", 1)
        self.name = kwargs.get("name", f"ROW-{self.idx}")

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        if key in {"idx", "name"}:
            object.__setattr__(self, key, value)
        else:
            self[key] = value

    def set(self, key, value):
        self[key] = value


class DocStub(dict):
    def __init__(self, doctype, **kwargs):
        super().__init__(**kwargs)
        self.doctype = doctype

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def set(self, key, value):
        self[key] = value


class DbStub:
    def __init__(self, po_rate=0):
        self.po_rate = po_rate

    def get_value(self, doctype, name, fields=None, as_dict=False):
        if doctype == "Item":
            return 1
        if doctype == "Purchase Order Item":
            return {"rate": self.po_rate, "uom": "Nos"}
        if doctype == "Company":
            return "MAD"
        return None


class TestStockRateReview(unittest.TestCase):
    def setUp(self):
        self.original_db = getattr(stock_rate_review.frappe, "db", None)
        self.original_pr_suggestion = stock_rate_review._suggest_purchase_receipt_rate
        self.original_se_suggestion = stock_rate_review._suggest_stock_entry_rate
        self.original_can_manage = stock_rate_review.can_manage_stock_rates
        self.original_get_roles = stock_rate_review.frappe.get_roles
        stock_rate_review.frappe.db = DbStub()
        stock_rate_review.can_manage_stock_rates = lambda user=None: False

    def tearDown(self):
        if self.original_db is None:
            delattr(stock_rate_review.frappe, "db")
        else:
            stock_rate_review.frappe.db = self.original_db
        stock_rate_review._suggest_purchase_receipt_rate = self.original_pr_suggestion
        stock_rate_review._suggest_stock_entry_rate = self.original_se_suggestion
        stock_rate_review.can_manage_stock_rates = self.original_can_manage
        stock_rate_review.frappe.get_roles = self.original_get_roles

    def test_purchase_order_rate_is_approved_and_filled(self):
        stock_rate_review.frappe.db = DbStub(po_rate=125)
        row = RowStub(item_code="MOTOR", qty=2, rate=0, uom="Nos", purchase_order_item="POI-1")
        doc = DocStub("Purchase Receipt", items=[row], company="Orderlift")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.rate, 125)
        self.assertEqual(row.custom_stock_rate_source, stock_rate_review.SOURCE_PURCHASE_ORDER)
        self.assertEqual(row.custom_stock_rate_status, stock_rate_review.STATUS_APPROVED)
        self.assertEqual(doc.custom_stock_rate_status, stock_rate_review.STATUS_APPROVED)

    def test_bilal_purchase_and_stock_user_roles_do_not_unlock_stock_rates(self):
        stock_rate_review.can_manage_stock_rates = self.original_can_manage
        stock_rate_review.frappe.get_roles = lambda user=None: ["Sales User", "Purchase User", "Stock User"]

        self.assertFalse(stock_rate_review.can_manage_stock_rates("bilalorderlift@gmail.com"))

    def test_buying_price_fallback_is_provisional(self):
        stock_rate_review._suggest_purchase_receipt_rate = lambda doc, row: {
            "rate": 80,
            "source": stock_rate_review.SOURCE_BUYING_PRICE_LIST,
        }
        row = RowStub(item_code="MOTOR", qty=2, rate=0, uom="Nos")
        doc = DocStub("Purchase Receipt", items=[row], company="Orderlift")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.rate, 80)
        self.assertEqual(row.custom_stock_rate_status, stock_rate_review.STATUS_PROVISIONAL)
        self.assertEqual(doc.custom_stock_rate_status, stock_rate_review.STATUS_PROVISIONAL)

    def test_missing_purchase_rate_stays_draft_status(self):
        stock_rate_review._suggest_purchase_receipt_rate = lambda doc, row: {
            "rate": 0,
            "source": stock_rate_review.SOURCE_MISSING,
        }
        row = RowStub(item_code="MOTOR", qty=2, rate=0, uom="Nos")
        doc = DocStub("Purchase Receipt", items=[row], company="Orderlift")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.custom_stock_rate_status, stock_rate_review.STATUS_MISSING)
        self.assertEqual(row.allow_zero_valuation_rate, 0)
        with self.assertRaisesRegex(ValueError, "stock cannot be posted without a value"):
            stock_rate_review.validate_document_rates_for_submit(doc)

    def test_missing_material_receipt_uses_temporary_draft_bypass_only(self):
        stock_rate_review._suggest_stock_entry_rate = lambda doc, row: {
            "rate": 0,
            "source": stock_rate_review.SOURCE_MISSING,
            "detail": "",
        }
        row = RowStub(
            item_code="MOTOR",
            qty=2,
            transfer_qty=2,
            basic_rate=0,
            allow_zero_valuation_rate=0,
            t_warehouse="Main - O",
        )
        doc = DocStub("Stock Entry", items=[row], company="Orderlift", purpose="Material Receipt")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.custom_stock_rate_status, stock_rate_review.STATUS_MISSING)
        self.assertEqual(row.allow_zero_valuation_rate, 1)
        stock_rate_review.finalize_document_rate_status(doc)
        self.assertEqual(row.allow_zero_valuation_rate, 0)

    def test_material_receipt_uses_provisional_buying_rate(self):
        stock_rate_review._suggest_stock_entry_rate = lambda doc, row: {
            "rate": 42,
            "source": stock_rate_review.SOURCE_LAST_PURCHASE,
        }
        row = RowStub(item_code="MOTOR", qty=3, transfer_qty=3, basic_rate=0, t_warehouse="Main - O")
        doc = DocStub("Stock Entry", items=[row], company="Orderlift", purpose="Material Receipt")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.basic_rate, 42)
        self.assertEqual(row.custom_stock_rate_status, stock_rate_review.STATUS_PROVISIONAL)

    def test_material_receipt_replaces_unscoped_native_fallback(self):
        stock_rate_review._suggest_stock_entry_rate = lambda doc, row: {
            "rate": 10132.2,
            "source": stock_rate_review.SOURCE_BUYING_PRICE_LIST,
            "detail": "PRIX FOURNISSEUR TRY Weight (TRY -> MAD)",
        }
        row = RowStub(
            item_code="MET-00013",
            qty=1,
            transfer_qty=1,
            basic_rate=16418.493,
            set_basic_rate_manually=0,
            t_warehouse="Main - O",
        )
        doc = DocStub("Stock Entry", items=[row], company="Orderlift", purpose="Material Receipt")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.basic_rate, 10132.2)
        self.assertEqual(row.custom_suggested_rate, 10132.2)
        self.assertEqual(row.custom_stock_rate_source, stock_rate_review.SOURCE_BUYING_PRICE_LIST)
        self.assertEqual(
            row.custom_stock_rate_source_detail,
            "PRIX FOURNISSEUR TRY Weight (TRY -> MAD)",
        )

    def test_material_receipt_preserves_explicit_manual_rate(self):
        stock_rate_review._suggest_stock_entry_rate = lambda doc, row: {
            "rate": 10132.2,
            "source": stock_rate_review.SOURCE_BUYING_PRICE_LIST,
            "detail": "PRIX FOURNISSEUR TRY Weight (TRY -> MAD)",
        }
        row = RowStub(
            item_code="MET-00013",
            qty=1,
            transfer_qty=1,
            basic_rate=16418.493,
            set_basic_rate_manually=1,
            t_warehouse="Main - O",
        )
        doc = DocStub("Stock Entry", items=[row], company="Orderlift", purpose="Material Receipt")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.basic_rate, 16418.493)
        self.assertEqual(row.custom_suggested_rate, 10132.2)
        self.assertEqual(row.custom_stock_rate_source, stock_rate_review.SOURCE_MANUAL)

    def test_material_transfer_does_not_require_manual_rate_review(self):
        row = RowStub(
            item_code="MOTOR",
            qty=3,
            transfer_qty=3,
            basic_rate=0,
            s_warehouse="Main - O",
            t_warehouse="Transit - O",
        )
        doc = DocStub("Stock Entry", items=[row], company="Orderlift", purpose="Material Transfer")

        stock_rate_review.resolve_document_rates(doc)

        self.assertEqual(row.custom_stock_rate_status, stock_rate_review.STATUS_NOT_REQUIRED)
        self.assertEqual(doc.custom_stock_rate_status, stock_rate_review.STATUS_NOT_REQUIRED)

    def test_positive_rate_cannot_bypass_zero_valuation_guard(self):
        row = RowStub(
            item_code="MOTOR",
            qty=3,
            transfer_qty=3,
            basic_rate=42,
            allow_zero_valuation_rate=1,
            custom_stock_rate_status=stock_rate_review.STATUS_PROVISIONAL,
            t_warehouse="Main - O",
        )
        doc = DocStub("Stock Entry", items=[row], company="Orderlift", purpose="Material Receipt")

        with self.assertRaisesRegex(ValueError, "stock cannot be posted without a value"):
            stock_rate_review.validate_document_rates_for_submit(doc)


if __name__ == "__main__":
    unittest.main()
