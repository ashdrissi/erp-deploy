import json
import sys
import types
import unittest
from pathlib import Path


class AttrDict(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.validate_and_sanitize_search_inputs = lambda fn: fn
frappe_stub.session = types.SimpleNamespace(user="Administrator")
frappe_stub.flags = types.SimpleNamespace()
frappe_stub._dict = lambda value=None, **kwargs: AttrDict(value or {}, **kwargs)
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.logger = lambda *args, **kwargs: types.SimpleNamespace(info=lambda *a, **kw: None)
frappe_stub.db = types.SimpleNamespace(
    exists=lambda *args, **kwargs: True,
    get_value=lambda *args, **kwargs: None,
    has_column=lambda *args, **kwargs: True,
    set_value=lambda *args, **kwargs: None,
)
frappe_stub.defaults = types.SimpleNamespace(get_global_default=lambda *args, **kwargs: "USD")
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.cstr = lambda value="": str(value or "")
utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
utils_stub.now_datetime = lambda: "2026-06-01 12:00:00"
utils_stub.nowdate = lambda: "2026-06-01"
utils_stub.getdate = lambda value=None: value or "2026-06-01"
utils_stub.date_diff = lambda end, start: 0
sys.modules["frappe.utils"] = utils_stub

document_module = types.ModuleType("frappe.model.document")
document_module.Document = type("Document", (), {"get": lambda self, fieldname, default=None: getattr(self, fieldname, default)})
sys.modules["frappe.model"] = types.ModuleType("frappe.model")
sys.modules["frappe.model.document"] = document_module


def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub_module(
    "orderlift.sales.utils.customs_policy",
    compute_customs_amount=lambda *args, **kwargs: {},
    resolve_customs_rule=lambda *args, **kwargs: {},
)
_stub_module("orderlift.orderlift_logistics.utils.packaging_resolver", get_packaging_resolution=lambda *args, **kwargs: {})
_stub_module("orderlift.sales.utils.dimensioning", coerce_dimensioning_value=lambda field_type, value: value)
from orderlift.orderlift_sales.doctype.pricing_builder import pricing_builder
from orderlift.orderlift_sales.utils import item_price_tools, price_list_auto_rebuild
from orderlift.orderlift_logistics.utils import item_sequence
from orderlift.scripts import backfill_pricing_builder_selling_list_stamps

# This test imports Pricing Builder, which imports Pricing Sheet for helper functions.
# Remove that transitive module so pricing-sheet-specific tests can install their own stubs.
sys.modules.pop("orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet", None)
pricing_sheet_package = sys.modules.get("orderlift.orderlift_sales.doctype.pricing_sheet")
if pricing_sheet_package and hasattr(pricing_sheet_package, "pricing_sheet"):
    delattr(pricing_sheet_package, "pricing_sheet")


class TestPricingBuilderMetadata(unittest.TestCase):
    def tearDown(self):
        frappe_stub.flags = types.SimpleNamespace()
        frappe_stub.db.set_value = lambda *args, **kwargs: None
        frappe_stub.get_all = lambda *args, **kwargs: []
        frappe_stub.get_doc = lambda *args, **kwargs: None

    def test_extracts_rule_discount_metadata(self):
        metadata = pricing_builder.extract_benchmark_discount_metadata(
            {
                "target_margin_percent": 18,
                "is_fallback": False,
                "matched_rule": {
                    "ratio_min": 0.8,
                    "ratio_max": 1.2,
                    "target_margin_percent": 18,
                    "max_discount_percent": 6,
                    "item_group": "Rails",
                },
            },
            types.SimpleNamespace(fallback_max_discount_percent=4),
        )

        self.assertEqual(metadata["benchmark_is_fallback"], 0)
        self.assertEqual(metadata["benchmark_rule_max_discount_percent"], 6)
        self.assertEqual(metadata["fallback_max_discount_percent"], 4)
        self.assertEqual(metadata["policy_max_discount_percent"], 6)
        self.assertIn("Rails", metadata["benchmark_rule_label"])

    def test_stamps_item_price_from_builder_row(self):
        doc = _FakeItemPriceDoc()
        row = AttrDict(
            buying_list="Buy USD",
            pricing_scenario="Expenses A",
            customs_policy="Customs A",
            benchmark_policy="Margin A",
            benchmark_is_fallback=0,
            benchmark_rule_label="Rule A",
            benchmark_rule_max_discount_percent=7,
            fallback_max_discount_percent=3,
            policy_max_discount_percent=7,
            target_margin_percent=15,
            base_buy_price=100,
            override_selling_price=0,
        )

        pricing_builder.stamp_item_price_from_builder_row(doc, "PBU-00001", row)

        self.assertEqual(doc.custom_pricing_builder, "PBU-00001")
        self.assertEqual(doc.custom_source_buying_price_list, "Buy USD")
        self.assertEqual(doc.custom_benchmark_rule_max_discount_percent, 7)
        self.assertEqual(doc.custom_policy_max_discount_percent, 7)
        self.assertEqual(doc.custom_builder_price_overridden, 0)

    def test_auto_rebuild_updates_existing_stamped_selling_price(self):
        selling_doc = _FakeItemPriceDoc()
        statuses = {}

        frappe_stub.get_all = lambda doctype, **kwargs: _fake_get_all_for_rebuild(doctype)
        frappe_stub.get_doc = lambda doctype, name: _FakeBuilder() if doctype == "Pricing Builder" else selling_doc
        frappe_stub.db.set_value = lambda doctype, name, values, **kwargs: statuses.update({name: values})

        summary = price_list_auto_rebuild.rebuild_from_buying_item_price(
            types.SimpleNamespace(item_code="ITEM-001", price_list="Buy USD", buying=1)
        )

        self.assertEqual(summary["updated"], 1)
        self.assertEqual(selling_doc.price_list_rate, 150)
        self.assertEqual(selling_doc.custom_source_buying_price_list, "Buy USD")
        self.assertEqual(selling_doc.custom_benchmark_rule_max_discount_percent, 6)
        self.assertEqual(selling_doc.save_count, 1)
        self.assertIn("Retail", summary["price_lists"])

    def test_builds_item_calculation_breakdown_payload(self):
        payload = pricing_builder._build_calculation_breakdown(
            qty=2,
            base_buy=100,
            buying_list="Buy USD",
            pricing_scenario="Expenses A",
            customs_policy="Customs A",
            benchmark_policy="Margin A",
            pricing={
                "steps": [
                    {
                        "label": "Transport",
                        "type": "Percentage",
                        "value": 5,
                        "applies_to": "Base Price",
                        "scope": "Per Unit",
                        "basis": 100,
                        "delta_unit": 5,
                        "delta_line": 0,
                        "delta_sheet": 0,
                        "running_total": 105,
                    }
                ]
            },
            customs_calc={
                "applied": 20,
                "basis": "Value Per Kg x Weight x Rate Percent",
                "tariff_number": "ABC",
                "material": "ACIER",
                "base_value": 100,
                "value_per_kg": 10,
                "weight_kg": 10,
                "total_percent": 20,
                "component_display": "20",
            },
            benchmark_result={
                "target_margin_percent": 10,
                "is_fallback": False,
                "benchmark_reference": 150,
                "source_count": 2,
                "min_sources_required": 2,
                "method": "Median",
                "ratio": 0.8,
                "matched_rule": {"ratio_min": 0.7, "ratio_max": 0.9, "target_margin_percent": 10},
            },
            benchmark_policy_doc=types.SimpleNamespace(policy_name="Margin A"),
            discount_meta={
                "target_margin_percent": 10,
                "benchmark_is_fallback": 0,
                "benchmark_rule_label": "Ratio 0.70-0.90: 10% margin",
                "policy_max_discount_percent": 4,
            },
            margin_basis="Loaded Cost",
            landed_cost=115,
            component_summary={"policy_expense_unit": 5, "margin_unit": 11.5},
            projected_unit=126.5,
        )

        self.assertEqual(payload["summary"]["expenses_unit"], 5)
        self.assertEqual(payload["expenses"]["steps"][0]["label"], "Transport")
        self.assertEqual(payload["customs"]["unit"], 10)
        self.assertEqual(payload["margin"]["basis"], "Loaded Cost")
        self.assertEqual(payload["margin"]["policy_name"], "Margin A")

    def test_backfill_stamps_existing_selling_price_without_changing_rate_by_default(self):
        selling_doc = _FakeItemPriceDoc(price_list_rate=123)
        frappe_stub.get_all = lambda doctype, **kwargs: _fake_get_all_for_backfill(doctype)
        frappe_stub.get_doc = lambda doctype, name: _FakeBuilder() if doctype == "Pricing Builder" else selling_doc

        summary = backfill_pricing_builder_selling_list_stamps.run(builder="PBU-00001", dry_run=0)

        self.assertEqual(summary["stamped"], 1)
        self.assertEqual(summary["updated_prices"], 0)
        self.assertEqual(summary["missing_existing_item_prices"], 0)
        self.assertEqual(selling_doc.price_list_rate, 123)
        self.assertEqual(selling_doc.custom_pricing_builder, "PBU-00001")
        self.assertEqual(selling_doc.custom_source_buying_price_list, "Buy USD")
        self.assertEqual(selling_doc.save_count, 1)

    def test_backfill_can_update_existing_non_overridden_selling_price(self):
        selling_doc = _FakeItemPriceDoc(price_list_rate=123)
        frappe_stub.get_all = lambda doctype, **kwargs: _fake_get_all_for_backfill(doctype)
        frappe_stub.get_doc = lambda doctype, name: _FakeBuilder() if doctype == "Pricing Builder" else selling_doc

        summary = backfill_pricing_builder_selling_list_stamps.run(
            builder="PBU-00001",
            dry_run=0,
            update_prices=1,
        )

        self.assertEqual(summary["stamped"], 1)
        self.assertEqual(summary["updated_prices"], 1)
        self.assertEqual(selling_doc.price_list_rate, 150)
        self.assertEqual(selling_doc.custom_benchmark_rule_max_discount_percent, 6)

    def test_builder_page_autosave_waits_for_required_setup(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        self.assertIn("function autosaveBlockReason", page_js)
        self.assertIn("options.autosave", page_js)
        self.assertIn("Select or enter Selling Price List to enable autosave", page_js)
        self.assertIn("Add a Sourcing Rule to enable autosave", page_js)

    def test_zero_base_buy_price_is_not_ready(self):
        row = AttrDict(
            status="Ready",
            base_buy_price=0,
            override_selling_price=0,
            projected_price=0,
            published_price=0,
        )

        self.assertEqual(pricing_builder._effective_builder_status(row), "Missing Buy Price")
        summary = pricing_builder._build_summary([row])
        self.assertEqual(summary["ready_count"], 0)
        self.assertEqual(summary["missing_count"], 1)

    def test_item_price_defaults_uom_from_item_stock_uom(self):
        original_get_value = frappe_stub.db.get_value
        frappe_stub.db.get_value = lambda doctype, name, fieldname=None, **kwargs: "Nos" if doctype == "Item" and fieldname == "stock_uom" else None
        try:
            doc = AttrDict(item_code="ITEM-001", uom="")
            doc.meta = _FakeMeta()
            item_price_tools.apply_item_price_defaults(doc)
        finally:
            frappe_stub.db.get_value = original_get_value

        self.assertEqual(doc.uom, "Nos")

    def test_item_code_generation_treats_name_copied_code_as_empty(self):
        self.assertTrue(item_sequence._should_generate_item_code(AttrDict(item_code="Door Part", item_name="Door Part")))
        self.assertTrue(item_sequence._should_generate_item_code(AttrDict(item_code="", item_name="Door Part")))
        self.assertFalse(item_sequence._should_generate_item_code(AttrDict(item_code="POR-00001", item_name="Door Part")))

    def test_builder_override_map_preserves_exact_and_unique_item_override(self):
        overrides = pricing_builder._existing_override_map(
            [
                AttrDict(item="ITEM-001", buying_list="Buy USD", override_selling_price=123),
                AttrDict(item="ITEM-002", buying_list="Buy A", override_selling_price=10),
                AttrDict(item="ITEM-002", buying_list="Buy B", override_selling_price=20),
            ]
        )

        self.assertEqual(pricing_builder._existing_override(overrides, "ITEM-001", "Buy USD"), 123)
        self.assertEqual(pricing_builder._existing_override(overrides, "ITEM-001", "Other"), 123)
        self.assertEqual(pricing_builder._existing_override(overrides, "ITEM-002", "Other"), 0)
        self.assertEqual(pricing_builder._existing_override(overrides, "ITEM-002", "Buy A"), 10)

    def test_builder_warnings_are_summarized_for_storage(self):
        text = pricing_builder._warnings_html([f"ITEM-{idx}: " + ("x" * 500) for idx in range(120)])

        self.assertLessEqual(len(text), pricing_builder.MAX_WARNING_TOTAL_LENGTH)
        self.assertIn("more warning(s) omitted", text)
        self.assertIn("...", text)

    def test_catalogue_prix_articles_page_is_dynamic_selling_catalogue(self):
        app_root = Path(__file__).resolve().parents[2]
        page_dir = app_root / "orderlift" / "orderlift_sales" / "page" / "catalogue_prix_articles"
        page_py = (page_dir / "catalogue_prix_articles.py").read_text()
        page_js = (page_dir / "catalogue_prix_articles.js").read_text()
        page_json = (page_dir / "catalogue_prix_articles.json").read_text()
        menu_registry = (app_root / "orderlift" / "menu_registry.py").read_text()

        self.assertIn("catalogue-prix-articles", page_json)
        self.assertIn('validate_price_list_scope(price_list, kind="selling"', page_py)
        self.assertIn("SUM(actual_qty) AS stock_qty", page_py)
        self.assertIn("selectedPriceLists", page_js)
        self.assertIn("Catégorie d'article", page_js)
        self.assertIn("data-toggle-price-list-dropdown", page_js)
        self.assertIn("data-column-filter", page_js)
        self.assertIn("data-resize-column", page_js)
        self.assertIn("data-item-column", page_js)
        self.assertIn("data-select-item", page_js)
        self.assertIn("_row_number", page_js)
        self.assertIn("data-page-size", page_js)
        self.assertIn("cpa-image-frame", page_js)
        self.assertIn("STATE_STORAGE_KEY", page_js)
        self.assertIn("data-catalogue-filter", page_js)
        self.assertIn("selectedItemsInFilteredRows", page_js)
        self.assertNotIn("Max lignes", page_js)
        self.assertIn("Exporter CSV", page_js)
        self.assertIn("Générer PDF", page_js)
        self.assertIn("download_catalogue_pdf", page_py)
        self.assertIn("item_codes=None", page_py)
        self.assertIn("_filter_payload_item_codes", page_py)
        self.assertIn("build_static_context", page_py)
        self.assertIn("allocated to sales person", page_py)
        self.assertIn("EXISTS (", page_py)
        self.assertIn("required_price_lists", page_py)
        self.assertIn("hide_stock_qty", page_py)
        self.assertIn('payload_row["stock_qty"]', page_py)
        self.assertIn('columns = [column for column in columns if column != "stock_qty"]', page_py)
        self.assertIn("hideStockQty", page_js)
        self.assertIn('key !== "stock_qty"', page_js)
        self.assertIn("A4 landscape", page_py)
        self.assertIn('"zoom": "0.72"', page_py)
        self.assertIn("requests.get", page_py)
        self.assertIn("data:{content_type};base64", page_py)
        self.assertIn("font-size: 34px", page_py)
        self.assertIn("font-size: 8.5px", page_py)
        self.assertIn("_pdf_column_width", page_py)
        self.assertNotIn("LIMIT %(limit)s", page_py)
        self.assertIn("items.catalogue_prix_articles", menu_registry)

    def test_builder_page_preserves_items_table_scroll_on_render(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        self.assertIn("function getScrollState", page_js)
        self.assertIn("function restoreScrollState", page_js)
        self.assertIn(".pbb-items-scroll", page_js)
        self.assertIn("position:sticky", page_js)
        self.assertIn("itemsTop", page_js)
        self.assertIn("itemsLeft", page_js)
        self.assertIn("getAncestorScrollState", page_js)
        self.assertIn("preserveScroll: true", page_js)
        self.assertIn("requestAnimationFrame(restorePositions)", page_js)
        self.assertIn("render(page, { focusFilter: true, preserveScroll: true })", page_js)
        self.assertIn("preserveScroll: true });", page_js)
        self.assertNotIn("resetItemsTop: true, focusFilter", page_js)
        self.assertNotIn("resetItemsTop: true, focusColumnFilter", page_js)

    def test_builder_page_preserves_draft_sourcing_rules(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        self.assertIn("function syncVisibleInputs", page_js)
        self.assertIn("draftRuleRows", page_js)
        self.assertIn("isBlankSourcingRule", page_js)
        self.assertIn("Fill the Sourcing Rule to save it", page_js)

    def test_builder_page_shows_customs_packaging_breakdown(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.py"
        ).read_text()
        item_json = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder_item"
            / "pricing_builder_item.json"
        ).read_text()

        for fieldname in [
            "customs_weight_kg",
            "customs_line_weight_kg",
            "customs_package_weight_kg",
            "packaging_units_per_package",
            "packaging_package_count",
            "packaging_profile_source",
            "customs_basis",
        ]:
            self.assertIn(fieldname, page_js)
            self.assertIn(fieldname, page_py)
            self.assertIn(fieldname, item_json)

    def test_builder_page_has_column_configurator(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        self.assertIn("ITEM_TABLE_COLUMNS", page_js)
        self.assertIn("ITEM_COLUMN_STORAGE_KEY", page_js)
        self.assertIn("function columnConfigurator", page_js)
        self.assertIn("data-item-column", page_js)
        self.assertIn("data-reset-columns", page_js)
        self.assertIn("avg_benchmark", page_js)
        self.assertIn("customs_basis", page_js)

    def test_builder_page_has_advanced_item_table_controls(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        for marker in [
            "ITEM_COLUMN_CATEGORIES",
            "SOURCING_RULE_STORAGE_KEY",
            "data-toggle-rules",
            "data-sort-column",
            "data-resize-column",
            "data-column-filter",
            "data-column-reset-width",
            "pbb-column-width-badge",
            "data-column-up",
            "data-column-down",
            "data-open-item",
            "row_number",
            "function itemTableFooter",
            "function activeSourceBuyingLists",
            "pbb-items-footer",
            "Showing {0} of {1} loaded items",
            "Source buying lists: {0}",
            "function overrideCell",
            "data-apply-override",
            "function applyOverride",
            "Manual override validated",
            "pbb-override-apply",
            "pbb-item-popover",
            "pbb-item-popover-head",
            "pbb-item-popover-name",
            "listPriceCell",
            "function customsIssueRows",
            "Weight missing; customs calculated from buying amount",
            "pbb-sort-btn static",
            'data-resize-column="${escapeHtml(column.key)}"',
        ]:
            self.assertIn(marker, page_js)

    def test_pricing_builder_manager_filters_by_current_company(self):
        app_root = Path(__file__).resolve().parents[2]
        manager_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_manager"
            / "pricing_builder_manager.py"
        ).read_text()

        for marker in ["current_company", "_filter_builder_rows_by_company", "custom_company", "_price_list_company_map"]:
            self.assertIn(marker, manager_py)

    def test_builder_item_category_field_is_serialized(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.py"
        ).read_text()
        builder_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder"
            / "pricing_builder.py"
        ).read_text()
        item_json = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder_item"
            / "pricing_builder_item.json"
        ).read_text()

        for source in [page_js, page_py, builder_py, item_json]:
            self.assertIn("item_category", source)
        self.assertIn("custom_item_category", builder_py)

    def test_pricing_builder_item_calculation_breakdown_is_serialized(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.py"
        ).read_text()
        builder_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder"
            / "pricing_builder.py"
        ).read_text()
        item_json = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder_item"
            / "pricing_builder_item.json"
        ).read_text()

        for source in [page_py, builder_py, item_json]:
            self.assertIn("calculation_breakdown_json", source)
        for marker in [
            "parseCalculationBreakdown",
            "priceStory",
            "calculationSections",
            "expensesSection",
            "customsSection",
            "marginSection",
            "pbb-price-formula",
            "pbb-calc-section",
            "normalizeCurrencyText",
            "MAD",
        ]:
            self.assertIn(marker, page_js)

    def test_pricing_builder_manager_has_bulk_delete_and_duplicate(self):
        app_root = Path(__file__).resolve().parents[2]
        manager_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_manager"
            / "pricing_builder_manager.js"
        ).read_text()
        manager_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_manager"
            / "pricing_builder_manager.py"
        ).read_text()

        for marker in ["selectedBuilders", "data-select-builder", "data-delete-selected", "data-duplicate-selected"]:
            self.assertIn(marker, manager_js)
        self.assertIn("def delete_pricing_builders", manager_py)
        self.assertIn("def duplicate_pricing_builder", manager_py)
        self.assertIn("frappe.copy_doc", manager_py)

    def test_builder_page_has_total_margin_columns(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.py"
        ).read_text()
        item_json = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder_item"
            / "pricing_builder_item.json"
        ).read_text()

        for fieldname in ["total_margin_amount", "total_margin_pct", "margin_basis"]:
            self.assertIn(fieldname, page_js)
            self.assertIn(fieldname, page_py)
            self.assertIn(fieldname, item_json)

    def test_benchmark_policy_help_explains_margin_basis(self):
        app_root = Path(__file__).resolve().parents[2]
        policy_json = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_benchmark_policy"
            / "pricing_benchmark_policy.json"
        ).read_text()

        self.assertIn("margin = base_buy_price * margin%", policy_json)
        self.assertIn("margin = landed_cost * margin%", policy_json)
        self.assertIn("margin = landed_cost * margin% / (1 - margin%)", policy_json)
        self.assertIn("Total Margin includes margin plus tier and territory modifiers", policy_json)

    def test_benchmark_policy_allows_fallback_only_sources(self):
        app_root = Path(__file__).resolve().parents[2]
        policy = json.loads((
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_benchmark_policy"
            / "pricing_benchmark_policy.json"
        ).read_text())
        fields = {field["fieldname"]: field for field in policy["fields"]}

        self.assertFalse(fields["benchmark_sources"].get("reqd"))
        self.assertFalse(fields["benchmark_rules"].get("reqd"))
        self.assertIn("Leave sources empty", fields["sources_help_html"].get("options", ""))
        self.assertIn("Rules are required only when benchmark sources", fields["rules_help_html"].get("options", ""))

    def test_pricing_sheet_builder_has_total_margin_fields(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.js"
        ).read_text()
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.py"
        ).read_text()
        item_json = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_sheet_item"
            / "pricing_sheet_item.json"
        ).read_text()

        for fieldname in ["total_margin_unit_amount", "total_margin_total_amount", "total_margin_pct", "margin_basis"]:
            self.assertIn(fieldname, page_js)
            self.assertIn(fieldname, page_py)
            self.assertIn(fieldname, item_json)


class _FakeMeta:
    def has_field(self, fieldname):
        return True


class _FakeItemPriceDoc:
    def __init__(self, price_list_rate=0):
        self.meta = _FakeMeta()
        self.price_list_rate = price_list_rate
        self.save_count = 0

    def save(self, ignore_permissions=False):
        self.save_count += 1


class _FakeBuilder:
    name = "PBU-00001"
    selling_price_list_name = "Retail"
    sourcing_rules = [AttrDict(buying_price_list="Buy USD", is_active=1)]

    def calculate_items(self):
        self.builder_items = [
            AttrDict(
                item="ITEM-001",
                buying_list="Buy USD",
                status="Ready",
                projected_price=150,
                override_selling_price=0,
                pricing_scenario="Expenses A",
                customs_policy="Customs A",
                benchmark_policy="Margin A",
                benchmark_is_fallback=0,
                benchmark_rule_label="Rule A",
                benchmark_rule_max_discount_percent=6,
                fallback_max_discount_percent=3,
                policy_max_discount_percent=6,
                target_margin_percent=14,
                base_buy_price=100,
            )
        ]


def _fake_get_all_for_rebuild(doctype):
    if doctype == "Price List":
        return [AttrDict(name="Retail", custom_pricing_builder="PBU-00001")]
    if doctype == "Item Price":
        return [
            AttrDict(
                name="IP-SELL",
                price_list="Retail",
                custom_pricing_builder="PBU-00001",
                custom_builder_price_overridden=0,
            )
        ]
    return []


def _fake_get_all_for_backfill(doctype):
    if doctype == "Item Price":
        return [AttrDict(name="IP-SELL")]
    return []


if __name__ == "__main__":
    unittest.main()
