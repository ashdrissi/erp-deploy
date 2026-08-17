import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPurchaseOrderBuyingSources(unittest.TestCase):
    def test_schema_captures_ordered_sources_and_negotiated_price_audit(self):
        setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        logistics_setup = (APP_ROOT / "logistics" / "setup.py").read_text()
        selection = json.loads(
            (
                APP_ROOT
                / "orderlift_sales"
                / "doctype"
                / "pricing_sheet_price_list_selection"
                / "pricing_sheet_price_list_selection.json"
            ).read_text()
        )
        log = json.loads(
            (APP_ROOT / "orderlift_sales" / "doctype" / "buying_price_change_log" / "buying_price_change_log.json").read_text()
        )

        for fieldname in [
            "selected_buying_price_lists",
            "custom_source_buying_price_list",
            "custom_source_item_price",
            "custom_lock_buying_price_source",
            "custom_source_buying_rate",
            "custom_loaded_buying_rate",
            "custom_price_variance_amount",
            "custom_price_variance_percent",
            "custom_update_price_list_on_submit",
            "custom_price_update_decision",
            "custom_price_update_log",
            "custom_default_purchase_taxes_template",
        ]:
            self.assertIn(f'"fieldname": "{fieldname}"', setup)

        self.assertEqual(log["name"], "Buying Price Change Log")
        self.assertEqual(selection["name"], "Pricing Sheet Price List Selection")
        self.assertEqual(selection["fields"][0]["label"], "Price List")
        for fieldname in ["source_currency", "exchange_rate", "exchange_rate_source"]:
            self.assertIn(fieldname, selection["field_order"])
        self.assertIn("purchase_order", log["field_order"])
        self.assertIn("old_rate", log["field_order"])
        self.assertIn("new_rate", log["field_order"])
        self.assertIn("change_type", log["field_order"])
        for fieldname in ["source_currency", "source_exchange_rate", "old_source_rate", "new_source_rate"]:
            self.assertIn(fieldname, log["field_order"])
        controller = (APP_ROOT / "orderlift_sales" / "doctype" / "buying_price_change_log" / "buying_price_change_log.py").read_text()
        self.assertIn("Buying Price Change Log records are immutable.", controller)
        self.assertIn("disable_native_purchase_price_auto_insert", logistics_setup)
        self.assertIn("auto_insert_price_list_rate_if_missing", logistics_setup)

    def test_server_resolver_preserves_negotiated_rate_and_logs_approved_update(self):
        source = (APP_ROOT / "orderlift_sales" / "utils" / "purchase_order_pricing.py").read_text()

        for token in [
            "sync_purchase_order_buying_price_lists",
            "validate_purchase_order_buying_prices",
            "get_purchase_order_price_candidates",
            "get_supplier_buying_price_lists",
            "supplier_lists",
            "_candidate_matches_row",
            "if _has_column(\"Item Price\", \"enabled\")",
            "compatible.sort(key=lambda candidate: (candidate[\"normalized_rate\"]",
            "negotiated = loaded_before > 0 and not _numbers_match(current_rate, loaded_before)",
            "publish_approved_purchase_order_prices",
            "Buying Price Change Log",
            "custom_price_update_decision",
            "custom_update_price_list_on_submit",
            "custom_price_reviewed_by",
            "custom_price_reviewed_on",
            "custom_price_reviewed_rate",
            "custom_price_reviewed_loaded_rate",
            "custom_price_reviewed_source_buying_price_list",
            "custom_price_reviewed_source_currency",
            "custom_price_review_attestation",
            "_update_item_price_from_row",
            "get_purchase_order_price_reviews",
            "set_purchase_order_price_review_decisions",
            "can_manage_purchase_price_approvals",
            "_review_is_current",
            "_protect_price_review_fields",
            "if _review_is_current(row):",
            "source_rate * flt(context[\"exchange_rate\"])",
            "rate = flt(row.rate) / source_exchange_rate",
            "custom_source_buying_rate",
            "source_exchange_rate",
            "exchange_rate_source",
            "Only Purchase Managers or privileged pricing users can override buying-list exchange rates.",
            "custom_lock_buying_price_source",
            "same_target_currency",
            "_is_manual_new_price",
            "_requires_price_review",
            "_mark_manual_new_price",
            "get_visible_price_lists(\"buying\"",
            "already have a valid buying price in an unselected list",
            "target_price_list",
            "validate_price_list_scope(price_list, kind=\"buying\"",
            "item_price.currency = source_currency",
            "item_price.supplier = doc.supplier",
            "rate = flt(row.rate) / source_exchange_rate",
        ]:
            self.assertIn(token, source)

        self.assertNotIn("_convert_currency(flt(row.rate)", source)

    def test_purchase_tax_template_is_authoritative_before_ttc_sync(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        tax_source = (APP_ROOT / "orderlift_sales" / "utils" / "tax_inclusive.py").read_text()

        self.assertIn("apply_purchase_order_tax_template", hooks)
        self.assertLess(
            hooks.index("apply_purchase_order_tax_template"),
            hooks.index("sync_purchase_order_tax_inclusive_fields"),
        )
        for token in [
            "company_default_purchase_taxes_template",
            "get_company_default_purchase_taxes_template",
            "_validate_purchase_tax_template_company",
            "_copy_purchase_tax_template_rows",
            '"Purchase Taxes and Charges Template"',
        ]:
            self.assertIn(token, tax_source)
        purchase_tax_function = tax_source.split("def apply_purchase_order_tax_template", 1)[1].split("def quote_item_inclusive_totals", 1)[0]
        self.assertIn("_clear_tax_rows(doc)", purchase_tax_function)
        self.assertNotIn("company_default_purchase_taxes_template(company)", purchase_tax_function)
        self.assertNotIn("Purchase Taxes Template {0} has no tax rows", purchase_tax_function)

    def test_purchase_order_ui_loads_sources_and_requires_submit_decision(self):
        source = (APP_ROOT / "public" / "js" / "purchase_order_buying_sources_20260815d.js").read_text()
        alerts = (APP_ROOT / "public" / "js" / "purchase_order_pricing_alerts_20260813a.js").read_text()
        review_page = (APP_ROOT / "orderlift_sales" / "page" / "buying_price_review" / "buying_price_review.js").read_text()
        review_backend = (APP_ROOT / "orderlift_sales" / "page" / "buying_price_review" / "buying_price_review.py").read_text()
        pricing_backend = (APP_ROOT / "orderlift_sales" / "utils" / "purchase_order_pricing.py").read_text()

        for token in [
            "Load Buying Prices",
            "selectedBuyingLists",
            "syncSupplierBuyingPriceLists",
            "supplierFilters",
            "resetSupplierIfOutsideCompany",
            "clearBuyingPriceRow(row, { clearRate: true })",
            "clearAllBuyingPriceRows(frm, { clearRate: true })",
            "__orderliftSupplierBuyingLists",
            "custom_source_buying_price_list",
            "get_purchase_order_price_candidates",
            "Approve Negotiated Buying Prices",
            "custom_update_price_list_on_submit",
            "custom_price_update_decision",
            "handlePurchaseCurrencyChange",
            "handleManualExchangeRate",
            "custom_source_buying_rate",
            "can_override_exchange_rate",
            "hideRedundantNativePriceListCurrency",
            "frm.toggle_display(fieldname, false)",
            "clearBuyingPriceSourceSnapshot",
            "custom_price_reviewed_source_buying_price_list",
            "custom_price_reviewed_source_currency",
        ]:
            self.assertIn(token, source)
        self.assertNotIn("get_currency_conversion_rate", source)
        self.assertNotIn('Number(row.rate || 0) * rate', source)
        for token in [
            "Pricing Alerts & Approvals",
            "set_purchase_order_price_review_decisions",
            "Approve & Update Price List",
            "Create New Price",
            "Select target list",
            "target_price_list",
            "ol-po-price-review-card",
            "ol-po-conversion-preview",
            "convertedTargetPrice",
            "maximumFractionDigits: 2",
            'ol-po-price-metrics ${isNew ? "is-new" : ""}',
            "livePriceDifference(row)",
            "custom_price_reviewed_source_buying_price_list",
            "custom_price_reviewed_source_currency",
        ]:
            self.assertIn(token, alerts)
        for token in [
            "custom_source_buying_price_list",
            "custom_loaded_buying_rate",
            "custom_source_buying_rate",
            "Current list price",
            "PO unit price",
            "Difference from loaded",
            "Price UOM",
        ]:
            self.assertIn(token, alerts)
        for token in ["source_rate", "source_currency", "po_currency", "List price", "Loaded in PO"]:
            self.assertIn(token, review_page)
        for token in [
            "Create New Price",
            "Target Price List",
            "Target list price",
            "target_price_list",
            "target_price_lists",
            "convertedTargetPrice",
            "review_selected",
        ]:
            self.assertIn(token, review_page)
        for token in ["target_price_lists", "stock_uom", "conversion_factor"]:
            self.assertIn(token, pricing_backend)
        self.assertIn("purchaseOrderSelectedBuyingPriceLists", price_list_queries := (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text())
        self.assertIn('if (frm.doctype === "Purchase Order")', price_list_queries)
        supplier_filter = source.split("function supplierFilters", 1)[1].split("function buyingListFilters", 1)[0]
        self.assertNotIn("custom_company", supplier_filter)
        supplier_reset = source.split("function resetSupplierIfOutsideCompany", 1)[1].split(
            "function clearRowSourceLocks", 1
        )[0]
        self.assertIn("is_supplier_allowed_for_purchase_company", supplier_reset)
        self.assertNotIn('frappe.db.get_value("Supplier", supplier, "custom_company")', supplier_reset)
        self.assertIn("_supplier_allowed_for_company", pricing_backend)
        self.assertIn("party_has_company_access(\"Supplier\", supplier, company)", pricing_backend)
        self.assertIn("not _supplier_allowed_for_company(supplier, company)", pricing_backend)
        self.assertIn("set_purchase_order_price_review_decisions", review_backend)

    def test_material_request_po_mapper_initializes_buying_lists(self):
        source = (APP_ROOT / "orderlift_logistics" / "utils" / "material_request.py").read_text()
        mapper = source.split("def make_purchase_order_from_material_requests", 1)[1].split(
            "def _purchase_order_source_rows", 1
        )[0]

        self.assertIn("get_supplier_buying_price_lists", mapper)
        self.assertIn("_supplier_allowed_for_company", mapper)
        self.assertIn("not _supplier_allowed_for_company(supplier, company)", mapper)
        self.assertLess(
            mapper.index("get_supplier_buying_price_lists"),
            mapper.index("sync_purchase_order_buying_price_lists(purchase_order)"),
        )
        self.assertIn("sync_purchase_order_buying_price_lists", mapper)
        self.assertLess(
            mapper.index("sync_purchase_order_buying_price_lists(purchase_order)"),
            mapper.index("payload = purchase_order.as_dict()"),
        )

    def test_purchase_order_item_details_guard_disables_native_auto_item_price_insert(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        guard = (APP_ROOT / "orderlift_sales" / "utils" / "item_details_guard.py").read_text()

        self.assertIn("override_whitelisted_methods", hooks)
        self.assertIn("erpnext.stock.get_item_details.get_item_details", hooks)
        self.assertIn("orderlift.orderlift_sales.utils.item_details_guard.get_item_details", hooks)
        self.assertIn("without native Item Price auto-insert for Purchase Orders", guard)
        self.assertIn('(\"price_list\", \"buying_price_list\")', guard)
        self.assertIn('_set_value(guarded_ctx, fieldname, "")', guard)
        self.assertIn("_suppress_native_item_price_insert", guard)


if __name__ == "__main__":
    unittest.main()
