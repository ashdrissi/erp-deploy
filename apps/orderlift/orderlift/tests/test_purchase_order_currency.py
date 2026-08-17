import importlib
import sys
import types
import unittest
from unittest import mock


MODULES = (
    "frappe",
    "frappe.utils",
    "orderlift.menu_access",
    "orderlift.orderlift_sales.utils.price_list_scope",
    "orderlift.role_capabilities",
    "orderlift.orderlift_sales.utils.purchase_order_pricing",
)
ORIGINAL_MODULES = {name: sys.modules.get(name) for name in MODULES}


class AttrDict(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value

    def set(self, key, value):
        self[key] = value

    def append(self, key, value):
        self.setdefault(key, []).append(AttrDict(value))

    def precision(self, fieldname):
        return 2 if fieldname == "rate" else 9


class ItemPriceStub(AttrDict):
    def save(self, ignore_permissions=False):
        self.saved = bool(ignore_permissions)

    def insert(self, ignore_permissions=False):
        self.inserted = bool(ignore_permissions)


class PurchaseOrderStub(ItemPriceStub):
    @property
    def items(self):
        return self["items"]


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda message, *args, **kwargs: message
frappe_stub.whitelist = lambda *args, **kwargs: (lambda function: function)
def _stub_throw(msg, exc=None):
    if exc is not None:
        raise exc(msg)
    raise Exception(msg)
frappe_stub.throw = _stub_throw
frappe_stub.PermissionError = PermissionError
frappe_stub.session = types.SimpleNamespace(user="buyer@example.com")
sys.modules["frappe"] = frappe_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value=0: int(value or 0)
frappe_utils_stub.flt = lambda value=0, precision=None: (
    round(float(value or 0), precision) if precision is not None else float(value or 0)
)
frappe_utils_stub.now_datetime = lambda: "2026-08-03 00:00:00"
frappe_utils_stub.nowdate = lambda: "2026-08-03"
sys.modules["frappe.utils"] = frappe_utils_stub

menu_access_stub = types.ModuleType("orderlift.menu_access")
menu_access_stub.resolve_current_company = lambda user=None: "Orderlift Maroc Distribution"
sys.modules["orderlift.menu_access"] = menu_access_stub

price_scope_stub = types.ModuleType("orderlift.orderlift_sales.utils.price_list_scope")
price_scope_stub.get_visible_price_lists = lambda *args, **kwargs: []
price_scope_stub.validate_price_list_scope = lambda value, **kwargs: value
price_scope_stub.validate_visible_price_list = lambda value, **kwargs: value
sys.modules["orderlift.orderlift_sales.utils.price_list_scope"] = price_scope_stub

role_capabilities_stub = types.ModuleType("orderlift.role_capabilities")
role_capabilities_stub.CAPABILITY_PRIVILEGED_PRICING = "privileged_pricing"
role_capabilities_stub.user_has_capability = lambda *args, **kwargs: False
sys.modules["orderlift.role_capabilities"] = role_capabilities_stub

sys.modules.pop("orderlift.orderlift_sales.utils.purchase_order_pricing", None)
purchase_order_pricing = importlib.import_module("orderlift.orderlift_sales.utils.purchase_order_pricing")

for module_name, original in ORIGINAL_MODULES.items():
    if original is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original


class TestPurchaseOrderCurrency(unittest.TestCase):
    def candidate(self, source_rate=100, exchange_rate=1, source_uom="Pc"):
        normalized = source_rate * exchange_rate
        return {
            "name": "IP-1",
            "price_list": "BUY-USD",
            "source_rate": source_rate,
            "source_currency": "USD",
            "source_exchange_rate": exchange_rate,
            "uom": source_uom,
            "normalized_rate": normalized,
            "rate": normalized,
        }

    def row(self, **values):
        row = AttrDict(
            item_code="ITEM-1",
            qty=1,
            uom="Pc",
            stock_uom="Pc",
            conversion_factor=1,
            rate=0,
            price_list_rate=0,
            custom_loaded_buying_rate=0,
            custom_price_update_decision="",
        )
        row.update(values)
        return row

    def test_same_currency_rate_is_not_converted(self):
        row = self.row()
        candidate = self.candidate(source_rate=100, exchange_rate=1)

        purchase_order_pricing._apply_candidate(row, candidate, force=False)

        self.assertEqual(row.custom_source_buying_rate, 100)
        self.assertEqual(row.custom_loaded_buying_rate, 100)
        self.assertEqual(row.price_list_rate, 100)
        self.assertEqual(row.rate, 100)

    def test_cross_currency_rate_is_converted_once(self):
        row = self.row()
        candidate = self.candidate(source_rate=100, exchange_rate=9.7)
        candidate["rate"] = 970

        purchase_order_pricing._apply_candidate(row, candidate, force=False)

        self.assertEqual(row.custom_source_buying_rate, 100)
        self.assertEqual(row.custom_loaded_buying_rate, 970)
        self.assertEqual(row.rate, 970)

    def test_source_uom_conversion_is_applied_after_currency(self):
        row = self.row(uom="Box", stock_uom="Pc", conversion_factor=10)
        candidate = self.candidate(source_rate=2, exchange_rate=9.7, source_uom="Pc")

        rate = purchase_order_pricing._candidate_rate_for_row(candidate, row)

        self.assertEqual(rate, 194)

    def test_negotiated_rate_survives_reference_refresh(self):
        row = self.row(
            rate=940,
            price_list_rate=970,
            custom_loaded_buying_rate=970,
            custom_price_update_decision="Approved",
        )
        candidate = self.candidate(source_rate=100, exchange_rate=9.8)
        candidate["rate"] = 980

        purchase_order_pricing._apply_candidate(row, candidate, force=False)

        self.assertEqual(row.rate, 940)
        self.assertEqual(row.price_list_rate, 980)
        self.assertEqual(row.custom_loaded_buying_rate, 980)
        self.assertEqual(row.custom_price_update_decision, "Pending")

    def test_loaded_reference_uses_native_rate_precision(self):
        row = self.row()
        candidate = self.candidate(source_rate=100.127275, exchange_rate=9.7)
        candidate["normalized_rate"] = 971.234567
        candidate["rate"] = purchase_order_pricing._candidate_rate_for_row(candidate, row)

        purchase_order_pricing._apply_candidate(row, candidate, force=False)

        self.assertEqual(row.rate, 971.23)
        self.assertEqual(row.price_list_rate, 971.23)
        self.assertEqual(row.custom_loaded_buying_rate, 971.23)
        self.assertEqual(row.custom_price_update_decision, "No Change")

    def test_negotiated_po_rate_converts_back_to_source_once(self):
        row = self.row(rate=940)

        source_rate = purchase_order_pricing._rate_in_source_context(row, "Pc", 9.4)

        self.assertAlmostEqual(source_rate, 100)

    def test_new_manual_rate_requires_review(self):
        row = self.row(rate=940, custom_source_item_price="", custom_loaded_buying_rate=0)

        purchase_order_pricing._mark_manual_new_price(row)

        self.assertTrue(purchase_order_pricing._is_manual_new_price(row))
        self.assertTrue(purchase_order_pricing._requires_price_review(row))
        self.assertEqual(row.custom_price_variance_amount, 0)

    def test_target_list_currency_rate_uses_source_to_po_exchange_rate(self):
        row = self.row(rate=970)

        source_rate = purchase_order_pricing._rate_in_source_context(row, "Pc", 9.7)

        self.assertAlmostEqual(source_rate, 100)

    def test_existing_item_price_is_updated_in_target_list_currency(self):
        source = ItemPriceStub(
            name="IP-EXISTING",
            supplier="SUP-1",
            currency="TRY",
            uom="Pc",
            price_list_rate=100,
        )
        db = types.SimpleNamespace(exists=lambda *args, **kwargs: True)
        doc = AttrDict(company="Orderlift Maroc Distribution", supplier="SUP-1")
        row = self.row(rate=1000)

        with (
            mock.patch.object(purchase_order_pricing.frappe, "db", db, create=True),
            mock.patch.object(purchase_order_pricing.frappe, "get_doc", return_value=source, create=True),
        ):
            result = purchase_order_pricing._update_item_price_from_row(
                doc,
                row,
                "BUY-TRY",
                source.name,
                0.2,
            )

        self.assertEqual(result, ("IP-EXISTING", 100, 5000, "Updated"))
        self.assertEqual(source.price_list_rate, 5000)
        self.assertTrue(source.saved)

    def test_new_item_price_uses_target_currency_and_po_supplier(self):
        created = ItemPriceStub(name="IP-NEW")
        db = types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda doctype, name, fieldname: "TRY" if fieldname == "currency" else None,
        )
        doc = AttrDict(
            company="Orderlift Maroc Distribution",
            supplier="SUP-1",
            transaction_date="2026-08-05",
        )
        row = self.row(rate=1000)

        with (
            mock.patch.object(purchase_order_pricing.frappe, "db", db, create=True),
            mock.patch.object(purchase_order_pricing.frappe, "new_doc", return_value=created, create=True),
        ):
            result = purchase_order_pricing._update_item_price_from_row(
                doc,
                row,
                "BUY-TRY",
                "",
                0.2,
            )

        self.assertEqual(result, ("IP-NEW", 0.0, 5000, "Created"))
        self.assertEqual(created.price_list, "BUY-TRY")
        self.assertEqual(created.price_list_rate, 5000)
        self.assertEqual(created.currency, "TRY")
        self.assertEqual(created.supplier, "SUP-1")
        self.assertTrue(created.inserted)

    def test_approval_endpoint_approves_existing_price_update(self):
        row = self.row(
            name="POI-1",
            rate=3200,
            custom_loaded_buying_rate=3000,
            custom_loaded_buying_currency="USD",
            custom_source_item_price="IP-EXISTING",
            custom_source_buying_price_list="BUY-USD",
        )
        doc = PurchaseOrderStub(
            name="PO-1",
            company="Orderlift Maroc Distribution",
            currency="USD",
            transaction_date="2026-08-05",
            docstatus=0,
            items=[row],
        )

        with (
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
            mock.patch.object(purchase_order_pricing.frappe, "get_doc", return_value=doc, create=True),
            mock.patch.object(
                purchase_order_pricing.frappe,
                "db",
                types.SimpleNamespace(get_value=lambda *args, **kwargs: "USD"),
                create=True,
            ),
        ):
            result = purchase_order_pricing.set_purchase_order_price_review_decisions(
                [{"purchase_order": "PO-1", "purchase_order_item": "POI-1", "decision": "Approved"}],
                attestation=1,
            )

        self.assertEqual(result, {"updated": 1})
        self.assertEqual(row.custom_price_update_decision, "Approved")
        self.assertEqual(row.custom_price_reviewed_rate, 3200)
        self.assertEqual(row.custom_price_reviewed_loaded_rate, 3000)
        self.assertEqual(row.custom_price_reviewed_source_buying_price_list, "BUY-USD")
        self.assertEqual(row.custom_price_reviewed_source_currency, "USD")
        self.assertTrue(doc.saved)

    def test_approval_endpoint_assigns_target_list_for_new_price(self):
        row = self.row(
            name="POI-NEW",
            rate=1000,
            uom="Pc",
            custom_loaded_buying_rate=0,
            custom_loaded_buying_currency="USD",
            custom_source_item_price="",
            custom_source_buying_price_list="",
        )
        doc = PurchaseOrderStub(
            name="PO-2",
            company="Orderlift Maroc Distribution",
            currency="MAD",
            transaction_date="2026-08-05",
            docstatus=0,
            items=[row],
        )

        with (
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
            mock.patch.object(purchase_order_pricing, "_price_list_exchange_details", return_value={"source_currency": "TRY", "exchange_rate": 0.2}),
            mock.patch.object(purchase_order_pricing.frappe, "get_doc", return_value=doc, create=True),
        ):
            result = purchase_order_pricing.set_purchase_order_price_review_decisions(
                [{
                    "purchase_order": "PO-2",
                    "purchase_order_item": "POI-NEW",
                    "decision": "Approved",
                    "target_price_list": "BUY-TRY",
                }],
                attestation=1,
            )

        self.assertEqual(result, {"updated": 1})
        self.assertEqual(row.custom_source_buying_price_list, "BUY-TRY")
        self.assertEqual(row.custom_loaded_buying_currency, "TRY")
        self.assertEqual(row.custom_price_reviewed_source_buying_price_list, "BUY-TRY")
        self.assertEqual(row.custom_price_reviewed_source_currency, "TRY")
        self.assertEqual(row.custom_price_update_decision, "Approved")
        self.assertTrue(doc.saved)

    def test_skip_stale_price_update_does_not_require_current_list_currency(self):
        row = self.row(
            name="POI-SKIP",
            rate=3200,
            custom_loaded_buying_rate=3000,
            custom_loaded_buying_currency="USD",
            custom_source_item_price="IP-EXISTING",
            custom_source_buying_price_list="BUY-LIST",
        )
        doc = PurchaseOrderStub(
            name="PO-SKIP",
            company="Orderlift Maroc Distribution",
            currency="MAD",
            transaction_date="2026-08-05",
            docstatus=0,
            items=[row],
        )

        with (
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
            mock.patch.object(purchase_order_pricing.frappe, "get_doc", return_value=doc, create=True),
        ):
            result = purchase_order_pricing.set_purchase_order_price_review_decisions(
                [{"purchase_order": "PO-SKIP", "purchase_order_item": "POI-SKIP", "decision": "Skipped"}],
            )

        self.assertEqual(result, {"updated": 1})
        self.assertEqual(row.custom_price_update_decision, "Skipped")
        self.assertEqual(row.custom_update_price_list_on_submit, 0)

    def test_source_list_change_invalidates_approval_even_when_rates_match(self):
        row = self.row(
            rate=2.5,
            custom_loaded_buying_rate=0,
            custom_source_buying_price_list="BUY-MAD",
            custom_loaded_buying_currency="USD",
            custom_price_update_decision="Approved",
            custom_price_reviewed_by="buyer@example.com",
            custom_price_reviewed_on="2026-08-05 12:00:00",
            custom_price_reviewed_rate=2.5,
            custom_price_reviewed_loaded_rate=0,
            custom_price_reviewed_source_buying_price_list="BUY-USD",
            custom_price_reviewed_source_currency="USD",
            custom_price_review_attestation=1,
        )

        with mock.patch.object(
            purchase_order_pricing,
            "can_manage_purchase_price_approvals",
            return_value=True,
        ), mock.patch.object(
            purchase_order_pricing.frappe,
            "db",
            types.SimpleNamespace(get_value=lambda *args, **kwargs: "MAD"),
            create=True,
        ):
            self.assertFalse(purchase_order_pricing._review_is_current(row))

    def test_price_list_currency_change_invalidates_unchanged_row_approval(self):
        row = self.row(
            rate=2.5,
            custom_loaded_buying_rate=0,
            custom_source_buying_price_list="BUY-LIST",
            custom_loaded_buying_currency="USD",
            custom_price_update_decision="Approved",
            custom_price_reviewed_by="buyer@example.com",
            custom_price_reviewed_on="2026-08-05 12:00:00",
            custom_price_reviewed_rate=2.5,
            custom_price_reviewed_loaded_rate=0,
            custom_price_reviewed_source_buying_price_list="BUY-LIST",
            custom_price_reviewed_source_currency="USD",
            custom_price_review_attestation=1,
        )

        with (
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
            mock.patch.object(
                purchase_order_pricing.frappe,
                "db",
                types.SimpleNamespace(get_value=lambda *args, **kwargs: "MAD"),
                create=True,
            ),
        ):
            self.assertFalse(purchase_order_pricing._review_is_current(row))

    def test_manual_new_price_refreshes_currency_from_selected_list(self):
        row = self.row(
            rate=2.5,
            uom="Pc",
            custom_source_buying_price_list="BUY-MAD",
            custom_loaded_buying_currency="USD",
            custom_price_update_decision="Approved",
        )
        db = types.SimpleNamespace(get_value=lambda *args, **kwargs: "MAD")

        with mock.patch.object(purchase_order_pricing.frappe, "db", db, create=True):
            purchase_order_pricing._mark_manual_new_price(row)

        self.assertEqual(row.custom_loaded_buying_currency, "MAD")
        self.assertEqual(row.custom_loaded_buying_uom, "Pc")
        self.assertEqual(row.custom_price_update_decision, "Pending")

    def test_validate_replaces_stale_source_currency_and_requires_reapproval(self):
        row = self.row(
            name="POI-STALE",
            rate=2.5,
            uom="Pc",
            custom_source_buying_price_list="BUY-MAD",
            custom_lock_buying_price_source=1,
            custom_source_item_price="",
            custom_loaded_buying_rate=0,
            custom_loaded_buying_currency="USD",
            custom_price_update_decision="Approved",
            custom_update_price_list_on_submit=1,
            custom_price_reviewed_by="buyer@example.com",
            custom_price_reviewed_on="2026-08-05 12:00:00",
            custom_price_reviewed_rate=2.5,
            custom_price_reviewed_loaded_rate=0,
            custom_price_reviewed_source_buying_price_list="BUY-USD",
            custom_price_reviewed_source_currency="USD",
            custom_price_review_attestation=1,
        )
        doc = PurchaseOrderStub(
            name="PO-STALE",
            company="Test Company",
            supplier="SUP-1",
            currency="MAD",
            transaction_date="2026-08-05",
            docstatus=0,
            items=[row],
        )
        db = types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda doctype, name, fieldname: "MAD" if doctype == "Price List" else None,
        )

        with (
            mock.patch.object(purchase_order_pricing.frappe, "db", db, create=True),
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
            mock.patch.object(purchase_order_pricing, "sync_purchase_order_buying_price_lists", return_value=["BUY-MAD"]),
            mock.patch.object(purchase_order_pricing, "get_visible_price_lists", return_value=["BUY-MAD"]),
            mock.patch.object(purchase_order_pricing, "_resolve_document_candidates", return_value={}),
        ):
            purchase_order_pricing.validate_purchase_order_buying_prices(doc)

        self.assertEqual(row.custom_loaded_buying_currency, "MAD")
        self.assertEqual(row.custom_price_update_decision, "Pending")
        self.assertEqual(row.custom_update_price_list_on_submit, 0)
        self.assertFalse(row.custom_price_reviewed_by)
        self.assertEqual(row.custom_price_reviewed_source_buying_price_list, "")
        self.assertEqual(row.custom_price_reviewed_source_currency, "")

    def test_approved_row_survives_validate_without_overwrite(self):
        row = self.row(
            name="POI-V",
            rate=3200,
            custom_loaded_buying_rate=0,
            custom_loaded_buying_currency="USD",
            custom_source_item_price="",
            custom_source_buying_price_list="BUY-USD",
            custom_price_update_decision="Approved",
            custom_update_price_list_on_submit=1,
            custom_price_reviewed_by="buyer@example.com",
            custom_price_reviewed_on="2026-08-05 12:00:00",
            custom_price_reviewed_rate=3200,
            custom_price_reviewed_loaded_rate=0,
            custom_price_reviewed_source_buying_price_list="BUY-USD",
            custom_price_reviewed_source_currency="USD",
            custom_price_review_attestation=1,
        )
        doc = PurchaseOrderStub(
            company="Orderlift Maroc Distribution",
            supplier="SUP-1",
            name="PO-V",
            docstatus=0,
            transaction_date="2026-08-05",
            items=[row],
        )
        price_scope_stub.get_visible_price_lists = lambda *args, **kwargs: ["BUY-USD"]
        candidate = {
            "name": "IP-CAND",
            "item_code": "ITEM-1",
            "price_list": "BUY-USD",
            "source_rate": 100,
            "source_currency": "USD",
            "source_exchange_rate": 1,
            "uom": "Pc",
            "normalized_rate": 100,
            "sequence": 0,
        }

        with (
            mock.patch.object(purchase_order_pricing, "_resolve_document_candidates", return_value={"POI-V": candidate}),
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
            mock.patch.object(purchase_order_pricing, "sync_purchase_order_buying_price_lists", return_value=["BUY-USD"]),
            mock.patch.object(purchase_order_pricing, "get_visible_price_lists", return_value=["BUY-USD"]),
            mock.patch.object(
                purchase_order_pricing.frappe,
                "db",
                types.SimpleNamespace(get_value=lambda *args, **kwargs: "USD"),
                create=True,
            ),
        ):
            purchase_order_pricing.validate_purchase_order_buying_prices(doc)

        self.assertEqual(row.custom_price_update_decision, "Approved")
        self.assertEqual(row.custom_update_price_list_on_submit, 1)
        self.assertEqual(row.rate, 3200)

    def test_sync_auto_selects_supplier_buying_lists_for_stale_draft(self):
        doc = PurchaseOrderStub(
            company="Orderlift Maroc Installation",
            supplier="SUP-1",
            currency="MAD",
            transaction_date="2026-08-05",
            buying_price_list="PRIX FOURNISSEUR MAD",
            selected_buying_price_lists=[],
            items=[],
        )

        with mock.patch.object(
            purchase_order_pricing,
            "get_supplier_buying_price_lists",
            return_value=[{
                "price_list": "BUY-INSTALL",
                "source_currency": "MAD",
                "exchange_rate": 1,
                "exchange_rate_source": "System",
            }],
        ):
            active = purchase_order_pricing.sync_purchase_order_buying_price_lists(doc)

        self.assertEqual(active, ["BUY-INSTALL"])
        self.assertEqual(doc.buying_price_list, "BUY-INSTALL")
        self.assertEqual([row.price_list for row in doc.selected_buying_price_lists], ["BUY-INSTALL"])

    def test_sync_discards_invalid_native_parent_buying_list_without_supplier(self):
        doc = PurchaseOrderStub(
            company="Orderlift Maroc Installation",
            supplier="",
            currency="MAD",
            transaction_date="2026-08-05",
            buying_price_list="PRIX FOURNISSEUR MAD",
            selected_buying_price_lists=[],
            items=[],
        )

        with (
            mock.patch.object(purchase_order_pricing, "get_supplier_buying_price_lists", return_value=[]),
            mock.patch.object(purchase_order_pricing, "validate_visible_price_list", side_effect=Exception("bad list")),
        ):
            active = purchase_order_pricing.sync_purchase_order_buying_price_lists(doc)

        self.assertEqual(active, [])
        self.assertEqual(doc.buying_price_list, "")
        self.assertEqual(doc.selected_buying_price_lists, [])

    def test_validate_clears_loaded_price_when_supplier_is_blank(self):
        row = self.row(
            name="POI-NO-SUP",
            rate=1000,
            amount=1000,
            price_list_rate=1000,
            custom_source_buying_price_list="PRIX FOURNISSEUR MAD",
            custom_source_item_price="IP-DIST",
            custom_loaded_buying_rate=1000,
            custom_loaded_buying_currency="MAD",
        )
        doc = PurchaseOrderStub(
            company="Orderlift Maroc Installation",
            supplier="",
            currency="MAD",
            transaction_date="2026-08-05",
            buying_price_list="PRIX FOURNISSEUR MAD",
            selected_buying_price_lists=[],
            items=[row],
            docstatus=0,
        )

        with (
            mock.patch.object(purchase_order_pricing, "get_supplier_buying_price_lists", return_value=[]),
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
        ):
            purchase_order_pricing.validate_purchase_order_buying_prices(doc)

        self.assertEqual(doc.buying_price_list, "")
        self.assertEqual(row.rate, 0)
        self.assertEqual(row.price_list_rate, 0)
        self.assertEqual(row.custom_source_buying_price_list, "")
        self.assertEqual(row.custom_source_item_price, "")

    def test_validate_replaces_row_source_outside_selected_dynamic_lists(self):
        row = self.row(
            name="POI-ROW-LEAK",
            rate=1000,
            amount=1000,
            price_list_rate=1000,
            custom_source_buying_price_list="PRIX FOURNISSEUR MAD",
            custom_source_item_price="IP-DIST",
            custom_loaded_buying_rate=1000,
            custom_loaded_buying_currency="MAD",
        )
        doc = PurchaseOrderStub(
            company="Orderlift Maroc Installation",
            supplier="SUP-INSTALL",
            currency="MAD",
            transaction_date="2026-08-05",
            buying_price_list="BUY-INSTALL",
            selected_buying_price_lists=[AttrDict(price_list="BUY-INSTALL", is_active=1, sequence=10)],
            items=[row],
            docstatus=0,
        )
        candidate = {
            "name": "IP-INSTALL",
            "item_code": "ITEM-1",
            "price_list": "BUY-INSTALL",
            "source_rate": 1085,
            "source_currency": "MAD",
            "source_exchange_rate": 1,
            "uom": "Pc",
            "normalized_rate": 1085,
            "rate": 1085,
            "sequence": 0,
        }

        with (
            mock.patch.object(purchase_order_pricing, "sync_purchase_order_buying_price_lists", return_value=["BUY-INSTALL"]),
            mock.patch.object(purchase_order_pricing, "get_visible_price_lists", return_value=["BUY-INSTALL"]),
            mock.patch.object(purchase_order_pricing, "_resolve_document_candidates", return_value={"POI-ROW-LEAK": candidate}),
            mock.patch.object(purchase_order_pricing, "can_manage_purchase_price_approvals", return_value=True),
        ):
            purchase_order_pricing.validate_purchase_order_buying_prices(doc)

        self.assertEqual(row.custom_source_buying_price_list, "BUY-INSTALL")
        self.assertEqual(row.custom_source_item_price, "IP-INSTALL")
        self.assertEqual(row.rate, 1085)

    def test_before_submit_guard_blocks_pending_decision(self):
        row = self.row(
            name="POI-P",
            rate=1000,
            custom_loaded_buying_rate=0,
            custom_source_item_price="",
            custom_price_update_decision="Pending",
        )
        doc = PurchaseOrderStub(
            company="Orderlift Maroc Distribution",
            name="PO-P",
            docstatus=0,
            items=[row],
        )

        with self.assertRaises(Exception):
            purchase_order_pricing.validate_purchase_order_price_update_decisions(doc)


class TestPurchaseOrderItemDetailsGuard(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.original_modules = {
            name: sys.modules.get(name)
            for name in (
                "frappe",
                "erpnext",
                "erpnext.stock",
                "erpnext.stock.get_item_details",
                "orderlift.orderlift_sales.utils.item_details_guard",
            )
        }

        frappe_stub = types.ModuleType("frappe")
        frappe_stub._ = lambda message, *args, **kwargs: message
        frappe_stub.whitelist = lambda *args, **kwargs: (lambda function: function)
        frappe_stub.parse_json = lambda value: value
        sys.modules["frappe"] = frappe_stub

        erpnext_stub = types.ModuleType("erpnext")
        stock_stub = types.ModuleType("erpnext.stock")
        get_item_details_stub = types.ModuleType("erpnext.stock.get_item_details")

        def insert_item_price(ctx):
            self.calls.append(("insert_item_price", ctx.get("doctype")))

        def get_item_details(ctx, doc=None, for_validate=False, overwrite_warehouse=True):
            get_item_details_stub.insert_item_price(ctx)
            return {
                "price_list": ctx.get("price_list") or "",
                "buying_price_list": ctx.get("buying_price_list") or "",
            }

        get_item_details_stub.insert_item_price = insert_item_price
        get_item_details_stub.get_item_details = get_item_details
        stock_stub.get_item_details = get_item_details_stub
        erpnext_stub.stock = stock_stub

        sys.modules["erpnext"] = erpnext_stub
        sys.modules["erpnext.stock"] = stock_stub
        sys.modules["erpnext.stock.get_item_details"] = get_item_details_stub

        sys.modules.pop("orderlift.orderlift_sales.utils.item_details_guard", None)
        self.guard = importlib.import_module("orderlift.orderlift_sales.utils.item_details_guard")

    def tearDown(self):
        for module_name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original

    def test_purchase_order_context_blocks_native_item_price_insert(self):
        result = self.guard.get_item_details(
            {"doctype": "Purchase Order", "item_code": "ITEM-1", "price_list": "BUY-USD", "buying_price_list": "BUY-USD"},
            doc={"doctype": "Purchase Order"},
        )

        self.assertEqual(result["price_list"], "")
        self.assertEqual(result["buying_price_list"], "")
        self.assertEqual(self.calls, [])

    def test_non_purchase_order_context_keeps_native_item_price_insert(self):
        result = self.guard.get_item_details(
            {"doctype": "Sales Order", "item_code": "ITEM-1", "price_list": "BUY-USD", "buying_price_list": "BUY-USD"},
            doc={"doctype": "Sales Order"},
        )

        self.assertEqual(result["price_list"], "BUY-USD")
        self.assertEqual(result["buying_price_list"], "BUY-USD")
        self.assertEqual(self.calls, [("insert_item_price", "Sales Order")])


if __name__ == "__main__":
    unittest.main()
