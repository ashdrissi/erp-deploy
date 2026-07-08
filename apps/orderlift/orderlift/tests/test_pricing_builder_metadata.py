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
frappe_stub.parse_json = lambda value: json.loads(value) if isinstance(value, str) else value
frappe_stub.db = types.SimpleNamespace(
    exists=lambda *args, **kwargs: True,
    get_value=lambda *args, **kwargs: None,
    has_column=lambda *args, **kwargs: True,
    set_value=lambda *args, **kwargs: None,
    sql=lambda *args, **kwargs: [],
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
naming_module = types.ModuleType("frappe.model.naming")
naming_module.make_autoname = lambda pattern: "PBU-00001"
sys.modules["frappe.model.naming"] = naming_module


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
from orderlift.orderlift_sales.page.pricing_builder_builder import pricing_builder_builder
from orderlift.orderlift_sales.utils import item_price_tools, price_list_auto_rebuild, price_list_scope
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
        frappe_stub.db.exists = lambda *args, **kwargs: True
        frappe_stub.db.sql = lambda *args, **kwargs: []
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
            final_margin_pct=12.5,
            base_buy_price=100,
            override_selling_price=0,
        )

        pricing_builder.stamp_item_price_from_builder_row(doc, "PBU-00001", row)

        self.assertEqual(doc.custom_pricing_builder, "PBU-00001")
        self.assertEqual(doc.custom_source_buying_price_list, "Buy USD")
        self.assertEqual(doc.custom_benchmark_rule_max_discount_percent, 7)
        self.assertEqual(doc.custom_policy_max_discount_percent, 7)
        self.assertEqual(doc.custom_target_margin_percent, 15)
        self.assertEqual(doc.custom_final_margin_percent, 12.5)
        self.assertEqual(doc.custom_builder_price_overridden, 0)

    def test_override_margin_percent_uses_actual_override_profit(self):
        margin_pct = pricing_builder._override_margin_percent(
            override_price=140,
            margin_basis="Base Price",
            base_buy=100,
            cost_before_margin=115,
            fallback_percent=20,
        )

        self.assertEqual(margin_pct, 25)

    def test_override_margin_percent_can_be_negative(self):
        margin_pct = pricing_builder._override_margin_percent(
            override_price=110,
            margin_basis="Base Price",
            base_buy=100,
            cost_before_margin=115,
            fallback_percent=20,
        )

        self.assertEqual(margin_pct, -5)

    def test_stamp_recalculates_override_margin_percent(self):
        doc = _FakeItemPriceDoc()
        row = AttrDict(
            buying_list="Buy USD",
            pricing_scenario="Expenses A",
            customs_policy="Customs A",
            benchmark_policy="Margin A",
            target_margin_percent=20,
            final_margin_pct=20,
            base_buy_price=100,
            projected_price=120,
            margin_amount=20,
            override_selling_price=140,
            margin_basis="Base Price",
        )

        pricing_builder.stamp_item_price_from_builder_row(doc, "PBU-00001", row)

        self.assertEqual(doc.custom_final_margin_percent, 40)
        self.assertEqual(doc.custom_builder_price_overridden, 1)

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

    def test_direct_selling_item_price_edit_marks_override_and_syncs_builder(self):
        set_values = []
        doc = _FakeItemPriceDoc(price_list_rate=175)
        doc.name = "IP-SELL"
        doc.item_code = "ITEM-001"
        doc.price_list = "Retail"
        doc.selling = 1
        doc.buying = 0
        doc.custom_pricing_builder = "PBU-00001"
        doc.custom_source_buying_price_list = "Buy USD"
        doc.custom_builder_price_overridden = 0
        doc._before = types.SimpleNamespace(price_list_rate=150)

        frappe_stub.get_all = lambda doctype, **kwargs: [AttrDict(name="PBI-00001")]
        frappe_stub.db.set_value = lambda *args, **kwargs: set_values.append((args, kwargs))

        item_price_tools.mark_direct_builder_price_override(doc)
        item_price_tools.sync_builder_override_from_item_price(doc)

        self.assertEqual(doc.custom_builder_price_overridden, 1)
        self.assertEqual(len(set_values), 1)
        self.assertEqual(set_values[0][0][:4], ("Pricing Builder Item", "PBI-00001", "override_selling_price", 175.0))

    def test_builder_publish_item_price_save_does_not_mark_manual_override(self):
        doc = _FakeItemPriceDoc(price_list_rate=175)
        doc.item_code = "ITEM-001"
        doc.price_list = "Retail"
        doc.selling = 1
        doc.buying = 0
        doc.custom_pricing_builder = "PBU-00001"
        doc.custom_source_buying_price_list = "Buy USD"
        doc.custom_builder_price_overridden = 0
        doc._before = types.SimpleNamespace(price_list_rate=150)

        frappe_stub.flags.orderlift_pricing_builder_publish = True

        item_price_tools.mark_direct_builder_price_override(doc)

        self.assertEqual(doc.custom_builder_price_overridden, 0)

    def test_price_list_save_preserves_previous_builder_stamp(self):
        doc = AttrDict(
            name="Retail",
            price_list_name="Retail",
            buying=0,
            selling=1,
            custom_price_list_type="Selling",
            custom_pricing_builder="",
        )
        doc.meta = _FakeMeta()
        doc.get_doc_before_save = lambda: types.SimpleNamespace(custom_pricing_builder="PBU-00001")

        price_list_scope.preserve_price_list_builder_stamp(doc)

        self.assertEqual(doc.custom_pricing_builder, "PBU-00001")

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

    def test_pricing_builder_target_currency_field_exists(self):
        app_root = Path(__file__).resolve().parents[2]
        builder_json = json.loads((
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder"
            / "pricing_builder.json"
        ).read_text())
        fields = {field["fieldname"]: field for field in builder_json["fields"]}

        self.assertIn("target_currency", builder_json["field_order"])
        self.assertEqual(fields["target_currency"]["fieldtype"], "Link")
        self.assertEqual(fields["target_currency"]["options"], "Currency")

    def test_new_selling_price_list_uses_selected_target_currency(self):
        created = []
        original_exists = frappe_stub.db.exists
        original_new_doc = getattr(frappe_stub, "new_doc", None)
        original_apply_company = pricing_builder.apply_price_list_company

        def fake_exists(doctype, name=None, *args, **kwargs):
            if doctype == "Price List":
                return False
            if doctype == "Currency":
                return name in {"TRY", "USD"}
            return False

        frappe_stub.db.exists = fake_exists
        frappe_stub.new_doc = lambda doctype: _FakePriceListDoc()
        pricing_builder.apply_price_list_company = lambda doc: None
        _FakePriceListDoc.inserted = []
        try:
            price_list_name = pricing_builder._ensure_selling_price_list("Retail TRY", target_currency="TRY")
        finally:
            frappe_stub.db.exists = original_exists
            pricing_builder.apply_price_list_company = original_apply_company
            if original_new_doc is None:
                delattr(frappe_stub, "new_doc")
            else:
                frappe_stub.new_doc = original_new_doc

        self.assertEqual(price_list_name, "Retail TRY")
        self.assertEqual(len(_FakePriceListDoc.inserted), 1)
        created.extend(_FakePriceListDoc.inserted)
        _FakePriceListDoc.inserted = []
        self.assertEqual(created[0].currency, "TRY")
        self.assertEqual(created[0].selling, 1)
        self.assertEqual(created[0].buying, 0)

    def test_existing_selling_price_list_keeps_configured_currency(self):
        original_exists = frappe_stub.db.exists
        original_get_value = frappe_stub.db.get_value
        original_validate = pricing_builder.validate_price_list_scope
        original_new_doc = getattr(frappe_stub, "new_doc", None)

        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: doctype == "Price List" and name == "Retail EUR"
        frappe_stub.db.get_value = lambda doctype, name, fieldname=None, **kwargs: "EUR" if doctype == "Price List" and fieldname == "currency" else None
        pricing_builder.validate_price_list_scope = lambda *args, **kwargs: True
        frappe_stub.new_doc = lambda doctype: (_ for _ in ()).throw(AssertionError("existing list must not be recreated"))
        try:
            self.assertEqual(pricing_builder._resolve_builder_target_currency("Retail EUR", "TRY"), "EUR")
            self.assertEqual(pricing_builder._ensure_selling_price_list("Retail EUR", target_currency="TRY"), "Retail EUR")
        finally:
            frappe_stub.db.exists = original_exists
            frappe_stub.db.get_value = original_get_value
            pricing_builder.validate_price_list_scope = original_validate
            if original_new_doc is None:
                delattr(frappe_stub, "new_doc")
            else:
                frappe_stub.new_doc = original_new_doc

    def test_builder_references_include_currency_metadata(self):
        original_current_company = pricing_builder_builder.current_company
        original_get_price_list_names = pricing_builder_builder.get_price_list_names
        original_exists = frappe_stub.db.exists
        original_has_column = frappe_stub.db.has_column
        original_get_value = frappe_stub.db.get_value
        original_get_all = getattr(frappe_stub, "get_all", None)

        pricing_builder_builder.current_company = lambda: "Orderlift Turkey"
        pricing_builder_builder.get_price_list_names = lambda kind=None, company=None: ["Buy USD"] if kind == "buying" else ["Retail TRY"]
        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: (
            (doctype == "Company" and name == "Orderlift Turkey") or (doctype == "DocType" and name == "Currency")
        )
        frappe_stub.db.has_column = lambda doctype, fieldname: doctype == "Price List" and fieldname in {"currency", "custom_company"}
        frappe_stub.db.get_value = lambda doctype, name, fieldname=None, **kwargs: "TRY" if doctype == "Company" and fieldname == "default_currency" else None

        def fake_get_all(doctype, **kwargs):
            if doctype == "Currency":
                return ["TRY", "USD"]
            if doctype == "Price List":
                names = set((kwargs.get("filters") or {}).get("name", [None, []])[1])
                if "Buy USD" in names:
                    return [AttrDict(name="Buy USD", currency="USD", custom_company="Orderlift Turkey")]
                return [AttrDict(name="Retail TRY", currency="TRY", custom_company="Orderlift Turkey")]
            return []

        frappe_stub.get_all = fake_get_all
        try:
            refs = pricing_builder_builder._references()
        finally:
            pricing_builder_builder.current_company = original_current_company
            pricing_builder_builder.get_price_list_names = original_get_price_list_names
            frappe_stub.db.exists = original_exists
            frappe_stub.db.has_column = original_has_column
            frappe_stub.db.get_value = original_get_value
            if original_get_all is None:
                delattr(frappe_stub, "get_all")
            else:
                frappe_stub.get_all = original_get_all

        self.assertEqual(refs["current_company"], "Orderlift Turkey")
        self.assertEqual(refs["company_currency"], "TRY")
        self.assertEqual(refs["currencies"], ["TRY", "USD"])
        self.assertEqual(refs["selling_price_list_meta"]["Retail TRY"]["currency"], "TRY")
        self.assertEqual(refs["buying_price_list_meta"]["Buy USD"]["currency"], "USD")

    def test_builder_page_shows_target_currency_controls(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        self.assertIn('data-parent-field="target_currency"', page_js)
        self.assertIn("function targetCurrency", page_js)
        self.assertIn("function defaultTargetCurrency", page_js)
        self.assertIn("function priceListLabel", page_js)
        self.assertIn("STATE.refs.company_currency", page_js)
        self.assertIn("Target Currency: {0}", page_js)
        self.assertIn("New list will be created in {0} for {1}.", page_js)
        self.assertIn('pbb-price-list-mode existing', page_js)
        self.assertIn('pbb-price-list-mode new', page_js)
        self.assertIn("function exchangeRatePanel", page_js)
        self.assertIn('<details class="pbb-rate-details">', page_js)
        self.assertIn("Exchange Rates Used", page_js)
        self.assertIn("synced from system Currency Exchange records", page_js)
        self.assertIn("pbb-price-list-mode.existing", page_js)
        self.assertIn("minmax(360px,.72fr)", page_js)

    def test_builder_page_flushes_save_and_publishes_exact_selected_rows(self):
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

        self.assertIn("let savePromise = null", page_js)
        self.assertIn("async function saveLatest", page_js)
        self.assertIn("clearTimeout(autosaveTimer)", page_js)
        self.assertIn("selected_rows: selectedOnly ? rowsToPublish : null", page_js)
        self.assertIn("function selectedPublishRows", page_js)
        self.assertIn("function selectedPublishRow", page_js)
        self.assertIn("function previewNewPriceCell", page_js)
        self.assertIn("Manual override", page_js)
        self.assertIn("def publish_builder_page_doc(name, selected_only=1, selected_rows=None)", page_py)
        self.assertIn("selected_rows=selected_rows", page_py)
        self.assertIn("def _selected_publish_keys", builder_py)
        self.assertIn("selected_keys = _selected_publish_keys(selected_rows)", builder_py)
        self.assertIn("def _existing_selected_map", builder_py)

    def test_builder_exchange_rate_summary_reads_system_rates(self):
        original_exists = frappe_stub.db.exists
        original_get_value = frappe_stub.db.get_value
        original_get_doc = getattr(frappe_stub, "get_doc", None)
        original_get_all = getattr(frappe_stub, "get_all", None)

        doc = AttrDict(
            selling_price_list_name="",
            target_currency="MAD",
            sourcing_rules=[AttrDict(is_active=1, buying_price_list="Buy USD", benchmark_policy="Bench A")],
        )
        policy = AttrDict(benchmark_sources=[AttrDict(is_active=1, price_list="Benchmark EUR")])

        def fake_exists(doctype, name=None, *args, **kwargs):
            if doctype == "Currency":
                return name == "MAD"
            if doctype == "Pricing Benchmark Policy":
                return name == "Bench A"
            if doctype == "DocType":
                return name == "Currency Exchange"
            return False

        def fake_get_value(doctype, name, fieldname=None, **kwargs):
            if doctype == "Price List" and fieldname == "currency":
                return {"Buy USD": "USD", "Benchmark EUR": "EUR"}.get(name)
            return None

        def fake_get_all(doctype, **kwargs):
            if doctype != "Currency Exchange":
                return []
            filters = kwargs.get("filters") or {}
            pair = (filters.get("from_currency"), filters.get("to_currency"))
            if pair == ("USD", "MAD"):
                return [AttrDict(name="USD-MAD-1", date="2026-07-01", exchange_rate=10.0)]
            if pair == ("EUR", "MAD"):
                return [AttrDict(name="EUR-MAD-1", date="2026-07-02", exchange_rate=11.0)]
            return []

        frappe_stub.db.exists = fake_exists
        frappe_stub.db.get_value = fake_get_value
        frappe_stub.get_doc = lambda doctype, name: policy
        frappe_stub.get_all = fake_get_all
        pricing_builder.get_price_list_currency.cache_clear()
        pricing_builder.get_exchange_rate_info_for_pair.cache_clear()
        try:
            summary = pricing_builder.builder_exchange_rate_summary(doc)
        finally:
            pricing_builder.get_price_list_currency.cache_clear()
            pricing_builder.get_exchange_rate_info_for_pair.cache_clear()
            frappe_stub.db.exists = original_exists
            frappe_stub.db.get_value = original_get_value
            if original_get_doc is None:
                delattr(frappe_stub, "get_doc")
            else:
                frappe_stub.get_doc = original_get_doc
            if original_get_all is None:
                delattr(frappe_stub, "get_all")
            else:
                frappe_stub.get_all = original_get_all

        by_list = {row["price_list"]: row for row in summary["rates"]}
        self.assertEqual(summary["target_currency"], "MAD")
        self.assertEqual(by_list["Buy USD"]["exchange_rate"], 10.0)
        self.assertEqual(by_list["Buy USD"]["source_name"], "USD-MAD-1")
        self.assertEqual(by_list["Benchmark EUR"]["exchange_rate"], 11.0)
        self.assertEqual(by_list["Benchmark EUR"]["usage"], "Benchmark")

    def test_builder_calculation_threads_target_currency_to_price_lookups(self):
        app_root = Path(__file__).resolve().parents[2]
        builder_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder"
            / "pricing_builder.py"
        ).read_text()
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.py"
        ).read_text()

        self.assertIn("target_currency = _resolve_builder_target_currency", builder_py)
        self.assertIn("target_currency=target_currency", builder_py)
        self.assertIn("def builder_exchange_rate_summary", builder_py)
        self.assertIn('"exchange_rate_summary": builder_exchange_rate_summary(doc)', page_py)

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

    def test_item_price_delete_cleanup_only_removes_mirror_rows(self):
        deleted = []
        original_exists = frappe_stub.db.exists
        original_delete = getattr(frappe_stub.db, "delete", None)
        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: doctype == "DocType" and name in {
            "Orderlift Item Buying Price",
            "Orderlift Item Selling Price",
            "Partner Campaign Item",
        }
        frappe_stub.db.delete = lambda doctype, filters=None, **kwargs: deleted.append((doctype, filters))
        try:
            item_price_tools.cleanup_item_price_mirror_rows(AttrDict(name="ITEM-PRICE-001"))
        finally:
            frappe_stub.db.exists = original_exists
            if original_delete is None:
                delattr(frappe_stub.db, "delete")
            else:
                frappe_stub.db.delete = original_delete

        self.assertEqual(
            deleted,
            [
                ("Orderlift Item Buying Price", {"item_price": "ITEM-PRICE-001"}),
                ("Orderlift Item Selling Price", {"item_price": "ITEM-PRICE-001"}),
            ],
        )
        self.assertNotIn(("Partner Campaign Item", {"source_item_price": "ITEM-PRICE-001"}), deleted)

    def test_item_price_delete_cleanup_hook_is_registered(self):
        from orderlift import hooks

        on_trash = hooks.doc_events["Item Price"]["on_trash"]
        self.assertIn(
            "orderlift.orderlift_sales.utils.item_price_tools.cleanup_item_price_mirror_rows",
            on_trash if isinstance(on_trash, list) else [on_trash],
        )

    def test_pricing_builder_delete_cleanup_removes_history_before_link_check(self):
        deleted = []
        sql_calls = []
        original_exists = frappe_stub.db.exists
        original_delete = getattr(frappe_stub.db, "delete", None)
        original_has_column = frappe_stub.db.has_column
        original_sql = getattr(frappe_stub.db, "sql", None)
        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: doctype == "DocType" and name == "Pricing Builder History"
        frappe_stub.db.delete = lambda doctype, filters=None, **kwargs: deleted.append((doctype, filters))
        frappe_stub.db.has_column = lambda doctype, fieldname: (
            (doctype == "Item Price" and fieldname == "custom_pricing_builder")
            or (doctype == "Pricing Sheet Item" and fieldname == "pricing_builder")
            or (doctype == "Price List" and fieldname == "custom_pricing_builder")
        )
        frappe_stub.db.sql = lambda query, params=None, **kwargs: sql_calls.append((query, params))
        try:
            pricing_builder.cleanup_pricing_builder_history(AttrDict(name="PBU-00005"))
        finally:
            frappe_stub.db.exists = original_exists
            frappe_stub.db.has_column = original_has_column
            if original_delete is None:
                delattr(frappe_stub.db, "delete")
            else:
                frappe_stub.db.delete = original_delete
            if original_sql is None:
                delattr(frappe_stub.db, "sql")
            else:
                frappe_stub.db.sql = original_sql

        self.assertEqual(deleted, [("Pricing Builder History", {"pricing_builder": "PBU-00005"})])
        self.assertEqual(len(sql_calls), 3)
        self.assertIn("custom_pricing_builder", sql_calls[0][0])
        self.assertIn("pricing_builder", sql_calls[1][0])
        self.assertIn("custom_pricing_builder", sql_calls[2][0])
        self.assertEqual(sql_calls[0][1], ("PBU-00005",))
        self.assertEqual(sql_calls[1][1], ("PBU-00005",))
        self.assertEqual(sql_calls[2][1], ("PBU-00005",))

    def test_pricing_builder_delete_cleanup_hook_is_registered_on_trash(self):
        from orderlift import hooks

        self.assertEqual(
            hooks.doc_events["Pricing Builder"]["on_trash"],
            "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.cleanup_pricing_builder_history",
        )

    def test_item_delete_cleanup_removes_builder_tool_rows(self):
        deleted = []
        original_exists = frappe_stub.db.exists
        original_delete = getattr(frappe_stub.db, "delete", None)
        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: doctype == "DocType" and name in {
            "Pricing Builder Item",
            "Pricing Builder Manual Item",
        }
        frappe_stub.db.delete = lambda doctype, filters=None, **kwargs: deleted.append((doctype, filters))
        try:
            pricing_builder.cleanup_item_builder_rows(AttrDict(name="SEFD-00013"))
        finally:
            frappe_stub.db.exists = original_exists
            if original_delete is None:
                delattr(frappe_stub.db, "delete")
            else:
                frappe_stub.db.delete = original_delete

        self.assertEqual(
            deleted,
            [
                ("Pricing Builder Item", {"item": "SEFD-00013"}),
                ("Pricing Builder Manual Item", {"item": "SEFD-00013"}),
            ],
        )

    def test_item_delete_cleanup_hook_is_registered_on_trash(self):
        from orderlift import hooks

        self.assertEqual(
            hooks.doc_events["Item"]["on_trash"],
            "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.cleanup_item_builder_rows",
        )

    def test_builder_page_snapshot_skips_deleted_item_rows(self):
        original_get_all = getattr(frappe_stub, "get_all", None)
        frappe_stub.get_all = lambda doctype, **kwargs: ["ITEM-001"] if doctype == "Item" else []
        doc = _FakeBuilderPageDoc()
        try:
            pricing_builder_builder._apply_snapshot(
                doc,
                {
                    "builder_name": "Retail Builder",
                    "builder_items": [
                        {"item": "ITEM-001", "selected": 1},
                        {"item": "SEFD-00013", "selected": 1},
                    ],
                },
            )
        finally:
            if original_get_all is None:
                delattr(frappe_stub, "get_all")
            else:
                frappe_stub.get_all = original_get_all

        self.assertEqual([row.item for row in doc.builder_items], ["ITEM-001"])

    def test_item_list_stock_totals_scope_to_current_company_warehouses(self):
        calls = {}
        original_current_company = item_price_tools.current_company
        original_has_column = frappe_stub.db.has_column
        original_sql = getattr(frappe_stub.db, "sql", None)
        original_has_permission = getattr(frappe_stub, "has_permission", None)

        def fake_sql(query, params, as_dict=False):
            calls["query"] = query
            calls["params"] = params
            return [AttrDict(item_code="ITEM-001", stock_qty=7)]

        item_price_tools.current_company = lambda: "Orderlift Maroc Distribution"
        frappe_stub.db.has_column = lambda doctype, fieldname: doctype == "Warehouse" and fieldname == "disabled"
        frappe_stub.db.sql = fake_sql
        frappe_stub.has_permission = lambda *args, **kwargs: True
        try:
            out = item_price_tools.get_item_list_stock_totals(json.dumps(["ITEM-001", "ITEM-002", "ITEM-001", ""]))
        finally:
            item_price_tools.current_company = original_current_company
            frappe_stub.db.has_column = original_has_column
            if original_sql is None:
                delattr(frappe_stub.db, "sql")
            else:
                frappe_stub.db.sql = original_sql
            if original_has_permission is None:
                delattr(frappe_stub, "has_permission")
            else:
                frappe_stub.has_permission = original_has_permission

        self.assertEqual(out["current_company"], "Orderlift Maroc Distribution")
        self.assertEqual(out["rows"], {"ITEM-001": 7.0, "ITEM-002": 0})
        self.assertIn("INNER JOIN `tabWarehouse`", calls["query"])
        self.assertIn("w.company = %(company)s", calls["query"])
        self.assertEqual(calls["params"]["company"], "Orderlift Maroc Distribution")

    def test_transaction_stock_snapshot_returns_allowed_warehouse_rows_and_totals(self):
        calls = {}
        original_current_company = item_price_tools.current_company
        original_has_column = frappe_stub.db.has_column
        original_sql = getattr(frappe_stub.db, "sql", None)
        original_has_permission = getattr(frappe_stub, "has_permission", None)
        original_stock_condition = item_price_tools.stock_warehouse_condition

        def fake_stock_condition(field_sql, params, user=None, key="allowed_warehouses"):
            self.assertEqual(field_sql, "w.name")
            params[key] = ("Main - OMD", "Reserve - OMD")
            return f" AND {field_sql} IN %({key})s"

        def fake_sql(query, params, as_dict=False):
            calls["query"] = query
            calls["params"] = params
            return [
                AttrDict(item_code="ITEM-001", item_name="Motor", warehouse="Main - OMD", actual_qty=2),
                AttrDict(item_code="ITEM-001", item_name="Motor", warehouse="Reserve - OMD", actual_qty=5),
                AttrDict(item_code="ITEM-002", item_name="Door", warehouse="Main - OMD", actual_qty=0),
            ]

        item_price_tools.current_company = lambda: "Wrong Session Company"
        item_price_tools.stock_warehouse_condition = fake_stock_condition
        frappe_stub.db.has_column = lambda doctype, fieldname: doctype == "Warehouse" and fieldname == "disabled"
        frappe_stub.db.sql = fake_sql
        frappe_stub.has_permission = lambda *args, **kwargs: True
        try:
            out = item_price_tools.get_transaction_stock_snapshot(
                json.dumps(["ITEM-001", "ITEM-002", "ITEM-001", ""]),
                company="Orderlift Maroc Distribution",
            )
        finally:
            item_price_tools.current_company = original_current_company
            item_price_tools.stock_warehouse_condition = original_stock_condition
            frappe_stub.db.has_column = original_has_column
            if original_sql is None:
                delattr(frappe_stub.db, "sql")
            else:
                frappe_stub.db.sql = original_sql
            if original_has_permission is None:
                delattr(frappe_stub, "has_permission")
            else:
                frappe_stub.has_permission = original_has_permission

        self.assertEqual(out["current_company"], "Orderlift Maroc Distribution")
        self.assertEqual(out["totals"], {"ITEM-001": 7.0, "ITEM-002": 0.0})
        self.assertEqual(len(out["rows"]), 3)
        self.assertIn("INNER JOIN `tabWarehouse` w", calls["query"])
        self.assertIn("LEFT JOIN `tabBin` b", calls["query"])
        self.assertIn("w.name IN %(allowed_warehouses)s", calls["query"])
        self.assertEqual(calls["params"]["allowed_warehouses"], ("Main - OMD", "Reserve - OMD"))

    def test_item_onload_populates_read_only_company_warehouse_stock_table(self):
        original_current_company = item_price_tools.current_company
        original_has_column = frappe_stub.db.has_column
        original_sql = getattr(frappe_stub.db, "sql", None)
        original_exists = frappe_stub.db.exists

        def fake_sql(query, params, as_dict=False):
            self.assertIn("FROM `tabWarehouse` w", query)
            self.assertIn("LEFT JOIN `tabBin` b", query)
            self.assertEqual(params, {"item_code": "ITEM-001", "company": "Orderlift Maroc Distribution"})
            return [AttrDict(warehouse="Main - OMD", actual_qty=3), AttrDict(warehouse="Reserve - OMD", actual_qty=4)]

        doc = AttrDict(name="ITEM-001", item_code="ITEM-001", stock_uom="Nos")
        doc.meta = _FakeMeta()
        doc.set = lambda fieldname, value: doc.__setitem__(fieldname, value)
        item_price_tools.current_company = lambda: "Orderlift Maroc Distribution"
        frappe_stub.db.has_column = lambda doctype, fieldname: doctype == "Warehouse" and fieldname == "disabled"
        frappe_stub.db.sql = fake_sql
        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: True
        try:
            item_price_tools._load_item_stock_snapshot(doc, "ITEM-001")
        finally:
            item_price_tools.current_company = original_current_company
            frappe_stub.db.has_column = original_has_column
            frappe_stub.db.exists = original_exists
            if original_sql is None:
                delattr(frappe_stub.db, "sql")
            else:
                frappe_stub.db.sql = original_sql

        self.assertEqual(
            doc["custom_company_warehouse_stock"],
            [
                {"warehouse": "Main - OMD", "actual_qty": 3.0},
                {"warehouse": "Reserve - OMD", "actual_qty": 4.0},
            ],
        )
        self.assertEqual(doc["custom_company_stock_total"], 7.0)
        self.assertEqual(doc["custom_current_company_stock_qty"], 7.0)

    def test_item_list_price_list_filter_returns_items_for_one_allowed_list(self):
        calls = {}
        original_get_value = frappe_stub.db.get_value
        original_has_column = frappe_stub.db.has_column
        original_sql = getattr(frappe_stub.db, "sql", None)
        original_validate = item_price_tools.validate_price_list_scope
        original_access = item_price_tools.get_item_price_access
        original_has_permission = getattr(frappe_stub, "has_permission", None)

        def fake_get_value(doctype, name, fields=None, **kwargs):
            if doctype == "Price List" and name == "Retail":
                return AttrDict(name="Retail", selling=1, buying=0)
            return None

        def fake_sql(query, params, as_dict=False):
            calls["query"] = query
            calls["params"] = params
            return [AttrDict(item_code="ITEM-001"), AttrDict(item_code="ITEM-002")]

        frappe_stub.db.get_value = fake_get_value
        frappe_stub.db.has_column = lambda doctype, fieldname: (
            (doctype == "Price List" and fieldname in {"selling", "buying"})
            or (doctype == "Item Price" and fieldname in {"selling", "enabled"})
            or (doctype == "Item" and fieldname == "disabled")
        )
        frappe_stub.db.sql = fake_sql
        frappe_stub.has_permission = lambda *args, **kwargs: True
        item_price_tools.validate_price_list_scope = lambda price_list, **kwargs: price_list
        item_price_tools.get_item_price_access = lambda kind: {"permitted": True, "price_lists": ["Retail"], "restricted": False}
        try:
            out = item_price_tools.get_items_for_price_list("Retail")
        finally:
            frappe_stub.db.get_value = original_get_value
            frappe_stub.db.has_column = original_has_column
            item_price_tools.validate_price_list_scope = original_validate
            item_price_tools.get_item_price_access = original_access
            if original_sql is None:
                delattr(frappe_stub.db, "sql")
            else:
                frappe_stub.db.sql = original_sql
            if original_has_permission is None:
                delattr(frappe_stub, "has_permission")
            else:
                frappe_stub.has_permission = original_has_permission

        self.assertEqual(out["price_list"], "Retail")
        self.assertEqual(out["price_type"], "selling")
        self.assertEqual(out["item_codes"], ["ITEM-001", "ITEM-002"])
        self.assertIn("ip.price_list = %(price_list)s", calls["query"])
        self.assertIn("ifnull(ip.selling, 0) = 1", calls["query"])
        self.assertEqual(calls["params"], {"price_list": "Retail"})

    def test_item_code_generation_treats_name_copied_code_as_empty(self):
        self.assertTrue(item_sequence._should_generate_item_code(AttrDict(item_code="Door Part", item_name="Door Part")))
        self.assertTrue(item_sequence._should_generate_item_code(AttrDict(item_code="", item_name="Door Part")))
        self.assertTrue(item_sequence._should_generate_item_code(AttrDict(item_code="AUTO", item_name="Door Part")))
        self.assertFalse(item_sequence._should_generate_item_code(AttrDict(item_code="POR-00001", item_name="Door Part")))

    def test_item_generation_hook_runs_before_naming(self):
        from orderlift import hooks

        self.assertEqual(
            hooks.doc_events["Item"]["before_naming"],
            "orderlift.orderlift_logistics.utils.item_sequence.apply_item_category_defaults",
        )

    def test_item_code_preview_does_not_consume_sequence(self):
        calls = []
        original_get_value = frappe_stub.db.get_value
        original_exists = frappe_stub.db.exists
        original_set_value = frappe_stub.db.set_value
        frappe_stub.db.get_value = lambda doctype, name, fields=None, **kwargs: AttrDict(
            abbreviation="POR",
            sequence_digits=5,
            current_sequence=7,
            is_active=1,
        ) if doctype == "Item Category" else None
        frappe_stub.db.exists = lambda doctype, name=None, *args, **kwargs: False
        frappe_stub.db.set_value = lambda *args, **kwargs: calls.append((args, kwargs))
        try:
            preview = item_sequence.preview_next_item_code("Porte")
        finally:
            frappe_stub.db.get_value = original_get_value
            frappe_stub.db.exists = original_exists
            frappe_stub.db.set_value = original_set_value

        self.assertEqual(preview["item_code"], "POR-00008")
        self.assertEqual(calls, [])

    def test_item_doctype_scripts_are_filesystem_resolvable(self):
        from orderlift import hooks

        app_root = Path(__file__).resolve().parents[2]
        paths = [hooks.doctype_js["Item"], hooks.doctype_list_js["Item"]]
        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn("?", path)
                self.assertTrue((app_root / "orderlift" / path).exists())

    def test_item_form_uses_native_layout_not_dom_price_cards(self):
        app_root = Path(__file__).resolve().parents[2]
        form_js = (app_root / "orderlift" / "public" / "js" / "item_form_prices_20260608a.js").read_text()
        setup_py = (app_root / "orderlift" / "logistics" / "setup.py").read_text()
        buying_table = json.loads(
            (app_root / "orderlift" / "orderlift_sales" / "doctype" / "orderlift_item_buying_price" / "orderlift_item_buying_price.json").read_text()
        )
        selling_table = json.loads(
            (app_root / "orderlift" / "orderlift_sales" / "doctype" / "orderlift_item_selling_price" / "orderlift_item_selling_price.json").read_text()
        )
        warehouse_stock_table = json.loads(
            (app_root / "orderlift" / "orderlift_sales" / "doctype" / "orderlift_item_warehouse_stock" / "orderlift_item_warehouse_stock.json").read_text()
        )

        self.assertIn("preview_next_item_code", form_js)
        self.assertNotIn("orderlift-item-price-card", form_js)
        self.assertNotIn("moveForeignTradeDetails", form_js)
        self.assertIn("custom_buying_item_prices", setup_py)
        self.assertIn("custom_selling_item_prices", setup_py)
        self.assertIn('("Item-custom_customs_material", "customs_tariff_number", 19)', setup_py)
        for table in (buying_table, selling_table):
            rate = next(field for field in table["fields"] if field["fieldname"] == "price_list_rate")
            currency = next(field for field in table["fields"] if field["fieldname"] == "currency")
            self.assertEqual(rate["fieldtype"], "Float")
            self.assertEqual(currency["fetch_from"], "price_list.currency")
            self.assertEqual(currency["read_only"], 1)

        quick_js = (app_root / "orderlift" / "public" / "js" / "item_list_price_helper_20260608g.js").read_text()
        self.assertIn('data-quick-field="currency"', quick_js)
        self.assertIn("readonly", quick_js)
        self.assertNotIn('currency: String($(this).find(\'[data-quick-field="currency"]\')', quick_js)
        self.assertIn("get_item_list_stock_totals", quick_js)
        self.assertIn("get_items_for_price_list", quick_js)
        self.assertIn("data-orderlift-price-list-filter", quick_js)
        self.assertNotIn('fieldname: "orderlift_price_list_filter"', quick_js)
        self.assertIn("placePriceListControl", quick_js)
        self.assertIn("filterControlTarget", quick_js)
        self.assertNotIn("toolbarTarget", quick_js)
        self.assertIn("__orderlift_selected_item_codes", quick_js)
        self.assertIn("ol-item-selection-badge", quick_js)
        self.assertIn("{0} selected", quick_js)
        self.assertIn("scheduleSelectionSync", quick_js)
        self.assertIn("itemCodeForContainer", quick_js)
        self.assertIn("data-docname", quick_js)
        self.assertIn("custom_current_company_stock_qty", quick_js)
        self.assertIn("get_item_stock_snapshot", form_js)
        self.assertIn('frm.set_query("custom_item_category"', form_js)
        self.assertIn('query: "orderlift.orderlift_logistics.utils.item_sequence.item_category_query"', form_js)
        self.assertIn('filters: { item_group: frm.doc.item_group || "" }', form_js)
        self.assertIn("clearCategoryIfGroupChanged", form_js)
        self.assertIn("syncItemGroupFromCategory", form_js)
        self.assertIn("quickEntryDialogSetCategoryQuery", form_js)
        self.assertIn("quickEntrySyncGroupFromCategory", form_js)
        self.assertIn("quickEntryClearCategoryIfGroupChanged", form_js)
        self.assertIn("frappe.ui.form.ItemQuickEntryForm", form_js)
        self.assertIn("wireQuickEntryCategoryControls", form_js)
        self.assertIn("frm.refresh_field", form_js)

        hooks_py = (app_root / "orderlift" / "hooks.py").read_text()
        self.assertIn('/assets/orderlift/js/item_form_prices_20260608a.js?v=20260618a', hooks_py)

        setup_py_text = setup_py
        self.assertIn("custom_current_company_stock_qty", setup_py_text)
        self.assertIn("Stock (Company Session)", setup_py_text)
        self.assertIn('"read_only": 1', setup_py_text)
        self.assertIn('"in_list_view": 1', setup_py_text)
        self.assertIn("custom_company_warehouse_stock", setup_py_text)
        self.assertIn("Orderlift Item Warehouse Stock", setup_py_text)
        self.assertIn("custom_company_stock_total", setup_py_text)
        self.assertEqual(warehouse_stock_table["istable"], 1)
        self.assertTrue(all(field.get("read_only") for field in warehouse_stock_table["fields"]))

        category_json = json.loads(
            (app_root / "orderlift" / "orderlift_logistics" / "doctype" / "item_category" / "item_category.json").read_text()
        )
        category_py = (app_root / "orderlift" / "orderlift_logistics" / "doctype" / "item_category" / "item_category.py").read_text()
        sequence_py = (app_root / "orderlift" / "orderlift_logistics" / "utils" / "item_sequence.py").read_text()
        category_fields = {field["fieldname"]: field for field in category_json["fields"]}
        self.assertEqual(category_fields["item_group"]["options"], "Item Group")
        self.assertIn('frappe.db.exists("Item Group", self.item_group)', category_py)
        self.assertIn("category_group", sequence_py)
        self.assertIn("def item_category_query", sequence_py)
        self.assertIn("ifnull(item_group, '') != ''", sequence_py)
        self.assertIn("backfill_item_category_item_groups", setup_py_text)
        self.assertIn("Ambiguous Item Category item_group backfill skipped", setup_py_text)

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

    def test_builder_selected_map_preserves_exact_selection(self):
        selected = pricing_builder._existing_selected_map(
            [
                AttrDict(item="ITEM-001", buying_list="Buy USD", selected=1),
                AttrDict(item="ITEM-001", buying_list="Buy EUR", selected=0),
                AttrDict(item="ITEM-002", buying_list="", selected=1),
            ]
        )

        self.assertEqual(pricing_builder._existing_selected(selected, "ITEM-001", "Buy USD"), 1)
        self.assertEqual(pricing_builder._existing_selected(selected, "ITEM-001", "Buy EUR"), 0)
        self.assertEqual(pricing_builder._existing_selected(selected, "ITEM-002", "Any"), 1)

    def test_builder_selected_publish_keys_parse_exact_rows(self):
        keys = pricing_builder._selected_publish_keys(
            json.dumps([
                {"item": "ITEM-001", "buying_list": "Buy USD"},
                {"item": "ITEM-002", "buying_list": ""},
            ])
        )

        self.assertEqual(keys, {("ITEM-001", "Buy USD"), ("ITEM-002", "")})

    def test_builder_imports_overridden_item_prices_into_override_map(self):
        frappe_stub.get_all = lambda doctype, **kwargs: [
            AttrDict(item_code="ITEM-001", custom_source_buying_price_list="Buy USD", price_list_rate=175)
        ]

        overrides = pricing_builder._published_item_price_override_map("Retail", "PBU-00001")

        self.assertEqual(pricing_builder._existing_override(overrides, "ITEM-001", "Buy USD"), 175)

    def test_builder_warnings_are_summarized_for_storage(self):
        text = pricing_builder._warnings_html([f"ITEM-{idx}: issue {idx} " + ("x" * 500) for idx in range(120)])

        self.assertLessEqual(len(text), pricing_builder.MAX_WARNING_TOTAL_LENGTH)
        self.assertIn("more warning(s) omitted", text)
        self.assertIn("...", text)

    def test_builder_warnings_are_grouped_by_message(self):
        text = pricing_builder._warnings_html([
            "ITEM-001: Missing benchmark data",
            "ITEM-002: Missing benchmark data",
            "ITEM-003: Other issue",
        ])

        self.assertIn("Missing benchmark data: affected articles ITEM-001, ITEM-002", text)
        self.assertIn("Other issue: affected articles ITEM-003", text)
        self.assertNotIn("ITEM-001: Missing benchmark data", text)

    def test_builder_publish_carries_source_buying_brand(self):
        app_root = Path(__file__).resolve().parents[2]
        builder_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder"
            / "pricing_builder.py"
        ).read_text()

        self.assertIn("_builder_source_brand_map", builder_py)
        self.assertIn("_set_builder_source_brand", builder_py)
        self.assertIn("backfill_selling_item_price_brands", builder_py)
        self.assertIn("doc.brand = brand_map.get((item_code, buying_list))", builder_py)

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
        self.assertIn("getScrollState", page_js)
        self.assertIn("getAncestorScrollState", page_js)
        self.assertIn("restoreScrollState", page_js)
        self.assertIn("preserveScroll: true", page_js)
        self.assertIn("preventScroll: true", page_js)
        self.assertIn("minWidth: 96", page_js)
        self.assertIn("cpa-table td.cpa-wrap", page_js)
        self.assertIn("data-resize-column", page_js)
        self.assertIn("data-item-column", page_js)
        self.assertIn("data-select-item", page_js)
        self.assertIn("ttc_prices", page_py)
        self.assertIn("build_catalogue_ttc_price_map", page_py)
        self.assertIn("company_default_sales_taxes_template", page_py)
        self.assertIn("price_ht:", page_js)
        self.assertIn("price_ttc:", page_js)
        self.assertIn('__("HT")', page_js)
        self.assertIn('__("TTC")', page_js)
        self.assertIn("_is_price_ttc_key", page_py)
        self.assertIn('toggleSelectedItem($(this).attr("data-select-item"), this.checked); render(page, { preserveScroll: true });', page_js)
        self.assertIn('togglePageSelection(paginatedRows(filteredRows()).rows, this.checked); render(page, { preserveScroll: true });', page_js)
        self.assertIn("_row_number", page_js)
        self.assertIn("data-page-size", page_js)
        self.assertIn("cpa-image-frame", page_js)
        self.assertIn("STATE_STORAGE_KEY", page_js)
        self.assertIn("data-catalogue-filter", page_js)
        self.assertIn("selectedItemsInFilteredRows", page_js)
        self.assertIn("Array.from(selected).filter", page_js)
        self.assertIn("selectedItems: STATE.selectedItems || []", page_js)
        self.assertIn("Array.isArray(saved.selectedItems)", page_js)
        self.assertNotIn("pruneSelectedItems();", page_js)
        self.assertIn("loadRows(page, { preserveScroll: true })", page_js)
        self.assertIn("function columnFilterPlaceholder", page_js)
        self.assertIn("function catalogueFilterOptions", page_js)
        self.assertIn("normalizeBootItemCategories", page_js)
        self.assertIn("pruneCatalogueCategoryFilter", page_js)
        self.assertIn('["item_group", "item_category"].includes(column.key)', page_js)
        self.assertIn("selectedBenchmarkPriceLists", page_js)
        self.assertIn("benchmarkPriceLists", page_js)
        self.assertIn("function matchesNumericColumnFilter", page_js)
        self.assertIn("function parseNumericColumnFilter", page_js)
        self.assertIn("Filtrer ex. >0", page_js)
        self.assertIn('fields.append("item_group")', page_py)
        self.assertIn("_matches_numeric_column_filter", page_py)
        self.assertIn("_parse_numeric_column_filter", page_py)
        self.assertIn("_is_numeric_filter_key", page_py)
        self.assertNotIn("Max lignes", page_js)
        self.assertIn("Exporter CSV", page_js)
        self.assertIn("Générer PDF", page_js)
        self.assertIn("download_catalogue_pdf", page_py)
        self.assertIn("benchmark_price_lists=None", page_py)
        self.assertIn("item_codes=None", page_py)
        self.assertIn("_filter_payload_item_codes", page_py)
        self.assertLess(
            page_py.index('payload["rows"] = _filter_payload_rows'),
            page_py.index('payload["rows"] = _filter_payload_item_codes'),
        )
        self.assertIn("if item_codes:", page_py)
        self.assertIn("build_static_context", page_py)
        self.assertIn("not visible to current user", page_py)
        self.assertIn("EXISTS (", page_py)
        self.assertIn("required_price_lists", page_py)
        self.assertIn("brand_price_lists", page_py)
        self.assertIn("benchmark_price_lists", page_py)
        self.assertIn("_item_price_brand_map", page_py)
        self.assertIn("brand_map.get(row.item_code) or row.brand", page_py)
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

    def test_customs_value_delta_tax_is_wired(self):
        app_root = Path(__file__).resolve().parents[2]
        policy_json = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "pricing_customs_policy" / "pricing_customs_policy.json").read_text()
        policy_py = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "pricing_customs_policy" / "pricing_customs_policy.py").read_text()
        sheet_py = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn("customs_delta_tax_section", policy_json)
        self.assertIn("enable_customs_value_delta_tax", policy_json)
        self.assertIn("customs_value_delta_tax_template", policy_json)
        self.assertIn("def _validate_delta_tax_template", policy_py)
        self.assertIn("def _apply_customs_value_delta_tax", sheet_py)
        self.assertIn('customs_calc["applied"] = flt(customs_calc.get("applied") or 0) + flt(amount)', sheet_py)
        self.assertIn("Customs Value Delta Tax", sheet_py)
        self.assertIn("sales_tax_template_total_rate", sheet_py)

    def test_builder_item_serialization_exposes_customs_delta_tax_fields(self):
        row = AttrDict(
            item="AEC-00039",
            item_name="ARCADE",
            calculation_breakdown_json=json.dumps(
                {
                    "customs": {
                        "customs_value_delta": 3432.5,
                        "customs_value_delta_tax_rate": 20,
                        "customs_value_delta_tax_amount": 686.5,
                    }
                }
            ),
        )

        out = pricing_builder_builder._serialize_builder_item(row)

        self.assertEqual(out["customs_value_delta"], 3432.5)
        self.assertEqual(out["customs_value_delta_tax_rate"], 20)
        self.assertEqual(out["customs_value_delta_tax_amount"], 686.5)

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
        self.assertIn('th[data-column="item_category"] .pbb-column-resizer', page_js)
        self.assertIn("z-index:24!important", page_js)
        self.assertIn("minWidth: 96", page_js)
        self.assertIn("width:${width}px;min-width:${minWidth}px", page_js)
        self.assertIn("pbb-warning-details", page_js)
        self.assertIn("<details class=\"pbb-warning-details\">", page_js)
        self.assertIn("AUTO_RECALCULATE_STORAGE_KEY", page_js)
        self.assertIn("data-auto-recalculate", page_js)
        self.assertIn("function builderItemFilterOptions", page_js)
        self.assertIn("pruneBuilderItemCategoryFilter", page_js)
        self.assertIn('["item_group", "item_category"].includes(column.key)', page_js)
        self.assertIn("compare_recalculated_builder_page_doc", page_js)
        self.assertIn("startOpenRefreshFlow", page_js)
        self.assertIn("AUTO_RECALCULATE_INTERVAL_MS", page_js)
        self.assertIn("setInterval(() => autoRecalculateNow(page), AUTO_RECALCULATE_INTERVAL_MS)", page_js)
        self.assertIn("stopAutoRecalculateLoop", page_js)
        self.assertIn("on_page_hide", page_js)
        self.assertIn("Auto recalculate enabled while this builder is open", page_js)
        self.assertIn("noRoute: true", page_js)
        page_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.py"
        ).read_text()
        self.assertIn("def compare_recalculated_builder_page_doc", page_py)
        self.assertIn("def _compare_builder_snapshots", page_py)
        self.assertNotIn("resetItemsTop: true, focusFilter", page_js)
        self.assertNotIn("resetItemsTop: true, focusColumnFilter", page_js)

    def test_builder_page_supports_numeric_column_filter_operators(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_builder"
            / "pricing_builder_builder.js"
        ).read_text()

        self.assertIn("function itemColumnSupportsNumericFilter", page_js)
        self.assertIn("function parseNumericColumnFilter", page_js)
        self.assertIn("function matchesNumericColumnFilter", page_js)
        self.assertIn('placeholder="${escapeHtml(itemFilterPlaceholder(column))}"', page_js)
        for operator in ['parsed.operator === ">"', 'parsed.operator === ">="', 'parsed.operator === "<"', 'parsed.operator === "<="']:
            self.assertIn(operator, page_js)
        self.assertIn("Math.abs(actual - parsed.value)", page_js)

    def test_pricing_builder_form_filters_category_by_item_group(self):
        app_root = Path(__file__).resolve().parents[2]
        form_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "doctype"
            / "pricing_builder"
            / "pricing_builder.js"
        ).read_text()

        self.assertIn("pb-filter-item-group", form_js)
        self.assertIn("pb-filter-item-category", form_js)
        self.assertIn("uniqueBuilderValues", form_js)
        self.assertIn("row.item_group === selectedGroup", form_js)
        self.assertIn("frm.__builderFilterState.item_category = \"\"", form_js)

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

    def test_pricing_builder_manager_can_recalculate_selected_builders(self):
        app_root = Path(__file__).resolve().parents[2]
        manager_py = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_manager"
            / "pricing_builder_manager.py"
        ).read_text()
        manager_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_builder_manager"
            / "pricing_builder_manager.js"
        ).read_text()

        self.assertIn("def recalculate_pricing_builders", manager_py)
        self.assertIn("calculate_builder_page_doc", manager_py)
        self.assertIn("data-recalculate-selected", manager_js)
        self.assertIn("data-recalculate", manager_js)
        self.assertIn("function recalculateBuilders", manager_js)

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
        self.assertIn("cleanup_pricing_builder_history(doc)", manager_py)
        self.assertIn("def duplicate_pricing_builder", manager_py)
        self.assertIn("frappe.copy_doc", manager_py)

    def test_derived_delete_links_are_ignored(self):
        from orderlift import hooks

        self.assertIn("Orderlift Item Buying Price", hooks.ignore_links_on_delete)
        self.assertIn("Orderlift Item Selling Price", hooks.ignore_links_on_delete)
        self.assertIn("Pricing Builder Item", hooks.ignore_links_on_delete)
        self.assertIn("Pricing Builder Manual Item", hooks.ignore_links_on_delete)
        self.assertIn("Pricing Builder History", hooks.ignore_links_on_delete)

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

    def test_pricing_sheet_builder_auto_prices_after_line_changes(self):
        app_root = Path(__file__).resolve().parents[2]
        page_js = (
            app_root
            / "orderlift"
            / "orderlift_sales"
            / "page"
            / "pricing_sheet_builder"
            / "pricing_sheet_builder.js"
        ).read_text()

        self.assertIn("function scheduleAutoPrice(page)", page_js)
        self.assertIn("async function autoSaveAndPrice(page)", page_js)
        self.assertIn("await save(page, { silent: true, freeze: false })", page_js)
        self.assertIn('if (event.type === "change") scheduleAutoPrice(page);', page_js)
        self.assertIn("scheduleAutoPrice(page);\n            }, getLineLinkQuery(field, line));", page_js)

    def test_price_list_scope_supports_benchmark_type_and_attributed_visibility(self):
        app_root = Path(__file__).resolve().parents[2]
        scope_py = (app_root / "orderlift" / "orderlift_sales" / "utils" / "price_list_scope.py").read_text()
        access_py = (app_root / "orderlift" / "company_access.py").read_text()
        setup_py = (app_root / "orderlift" / "sales" / "utils" / "pricing_setup.py").read_text()
        agent_py = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "agent_pricing_rules" / "agent_pricing_rules.py").read_text()
        agent_json = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "agent_pricing_rules" / "agent_pricing_rules.json").read_text()
        benchmark_js = (app_root / "orderlift" / "public" / "js" / "pricing_benchmark_policy_form.js").read_text()
        agent_js = (app_root / "orderlift" / "public" / "js" / "agent_pricing_rules.js").read_text()
        hook_text = (app_root / "orderlift" / "hooks.py").read_text()

        self.assertIn('PRICE_LIST_TYPE_FIELD = "custom_price_list_type"', scope_py)
        self.assertIn('BENCHMARK_PRICE_LIST = "Benchmark"', scope_py)
        self.assertIn('def validate_price_list_type(doc, method=None):', scope_py)
        self.assertIn('validate_price_list_scope(row.get("benchmark_price_list"), kind="benchmark", required=True)', agent_py)
        self.assertIn('"benchmark_price_lists": [r.benchmark_price_list for r in benchmark_lists]', agent_py)
        self.assertIn('allocated_benchmark_price_lists', agent_json)
        self.assertIn('Agent Allocated Benchmark Price List', agent_json)
        self.assertIn('PRICE_LIST_TYPE_FIELD', setup_py)
        self.assertIn('ERPNext still keeps it natively saveable as a selling list', setup_py)
        self.assertIn('get_visible_price_lists(company=_active_company_for_query(user), user=user)', access_py)
        self.assertIn('"Item Price": "orderlift.company_access.item_price_query"', hook_text)
        self.assertIn('benchmarkPriceListFilters', benchmark_js)
        self.assertIn('custom_price_list_type: "Benchmark"', benchmark_js)
        self.assertIn('benchmark_price_list', agent_js)
        self.assertIn('benchmarkOrTransactionalFilters("Benchmark")', agent_js)
        self.assertIn('orderlift.orderlift_sales.utils.price_list_scope.validate_price_list_type', hook_text)
        self.assertIn('"before_insert": [', hook_text)
        self.assertIn('"before_validate": [', hook_text)
        self.assertIn('orderlift.orderlift_sales.utils.price_list_scope.validate_price_list_unique_name_context', hook_text)
        self.assertIn('price_list_type_queries_20260703c.js', hook_text)

    def test_pricing_sheet_builder_static_agents_can_choose_allocated_lists(self):
        app_root = Path(__file__).resolve().parents[2]
        builder_py = (app_root / "orderlift" / "orderlift_sales" / "page" / "pricing_sheet_builder" / "pricing_sheet_builder.py").read_text()
        builder_js = (app_root / "orderlift" / "orderlift_sales" / "page" / "pricing_sheet_builder" / "pricing_sheet_builder.js").read_text()
        sheet_py = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn('"can_edit_pricing_source": (not is_restricted) or (agent_mode == STATIC_MODE and bool(selling_price_lists))', builder_py)
        self.assertIn('"can_edit_pricing_mode": not is_restricted', builder_py)
        self.assertIn('def _locked_current_user_agent_pricing_mode', builder_py)
        self.assertIn('doc.flags.pricing_builder_mode = locked_mode', builder_py)
        self.assertIn('function pricingSourceSection(sheet, mode, canEditPricingSource, canEditPricingMode)', builder_js)
        self.assertIn('Pricing mode is managed by your assigned agent rule.', builder_js)
        self.assertIn('!canEditPricingMode', builder_js)
        self.assertIn('"resolved_selling_price_list"', builder_py)
        self.assertIn('if (kind === "selling" && isRestrictedAgent())', builder_js)
        self.assertIn('resolved_selling_price_list', builder_js)
        self.assertIn('first active list by sequence wins', builder_js)
        self.assertIn('Static duplicate Item Price for {0} found in lists {1}; configured list {2} was used.', sheet_py)
        self.assertIn('query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.priced_item_query"', builder_js)
        self.assertIn('item_group: values.item_group || ""', builder_js)
        self.assertIn('conditions.append("i.item_group = %(item_group)s")', sheet_py)

    def test_sales_commission_preserves_snapshot_amount_from_sales_order(self):
        app_root = Path(__file__).resolve().parents[2]
        commission_py = (app_root / "orderlift" / "orderlift_sales" / "doctype" / "sales_commission" / "sales_commission.py").read_text()
        calculator_py = (app_root / "orderlift" / "sales" / "utils" / "commission_calculator.py").read_text()

        self.assertIn('if self.sales_order:', commission_py)
        self.assertIn('return', commission_py)
        self.assertIn('bucket["commission_amount"] += prorated_commission', calculator_py)


class _FakeMeta:
    def has_field(self, fieldname):
        return True


class _FakeBuilderPageMeta:
    fields = [AttrDict(fieldname=fieldname) for fieldname in pricing_builder_builder.PARENT_FIELDS + [
        "total_items",
        "ready_items",
        "changed_items",
        "new_items",
        "missing_items",
        "warnings_html",
    ]]


class _FakeBuilderPageDoc(AttrDict):
    def __init__(self):
        super().__init__()
        self.meta = _FakeBuilderPageMeta()
        self.builder_items = []

    def set(self, fieldname, value):
        self[fieldname] = value
        setattr(self, fieldname, value)

    def append(self, fieldname, value):
        row = AttrDict(value)
        self.setdefault(fieldname, []).append(row)
        setattr(self, fieldname, self[fieldname])
        return row


class _FakeItemPriceDoc:
    def __init__(self, price_list_rate=0):
        self.meta = _FakeMeta()
        self.price_list_rate = price_list_rate
        self.save_count = 0
        self.flags = types.SimpleNamespace()
        self._before = None

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)

    def get_doc_before_save(self):
        return self._before

    def save(self, ignore_permissions=False):
        self.save_count += 1


class _FakePriceListDoc:
    inserted = []

    def __init__(self):
        self.name = "Retail TRY"
        self.price_list_name = ""
        self.title = ""
        self.enabled = 0
        self.selling = 0
        self.buying = 1
        self.currency = ""
        self.custom_company = ""

    def insert(self, ignore_permissions=False):
        self.name = self.price_list_name or self.name
        self.__class__.inserted.append(self)


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
                final_margin_pct=14,
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
