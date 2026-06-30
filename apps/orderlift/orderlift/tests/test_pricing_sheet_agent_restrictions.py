import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.validate_and_sanitize_search_inputs = lambda fn: fn
frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
frappe_stub.roles_map = {}
frappe_stub.get_roles = lambda user=None: frappe_stub.roles_map.get(user or frappe_stub.session.user, [])
frappe_stub.get_meta = lambda doctype: types.SimpleNamespace(get_field=lambda f: types.SimpleNamespace())
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
frappe_stub.log_error = lambda *args, **kwargs: None
frappe_stub.logger = lambda *args, **kwargs: types.SimpleNamespace(info=lambda *a, **kw: None)
frappe_stub.db = types.SimpleNamespace(
    exists=lambda *args, **kwargs: False,
    get_value=lambda *args, **kwargs: None,
    has_column=lambda *args, **kwargs: False,
)
sys.modules["frappe"] = frappe_stub

# Ensure price_list_scope / role_capabilities are re-imported with current stub
for mod in list(sys.modules):
    if mod.startswith("orderlift.role_capabilities") or mod.endswith(".price_list_scope"):
        del sys.modules[mod]

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
utils_stub.cstr = lambda value="": str(value or "")
utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
utils_stub.now_datetime = lambda: "2026-05-19 00:00:00"
utils_stub.nowdate = lambda: "2026-05-19"
utils_stub.getdate = lambda value=None: value or "2026-05-19"
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

sys.modules.pop("orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet", None)
pricing_sheet_package = sys.modules.get("orderlift.orderlift_sales.doctype.pricing_sheet")
if pricing_sheet_package and hasattr(pricing_sheet_package, "pricing_sheet"):
    delattr(pricing_sheet_package, "pricing_sheet")

from orderlift.orderlift_sales.doctype.pricing_sheet import pricing_sheet
from orderlift.orderlift_sales.doctype.customer_segmentation_engine import customer_segmentation_engine as cse_module


class TestPricingSheetAgentRestrictions(unittest.TestCase):
    def setUp(self):
        frappe_stub._ = lambda value: value
        frappe_stub.session = types.SimpleNamespace(user="sales@example.com")
        frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
        frappe_stub.roles_map = {}
        frappe_stub.get_roles = lambda user=None: frappe_stub.roles_map.get(user or frappe_stub.session.user, [])
        frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
        frappe_stub.logger = lambda *args, **kwargs: types.SimpleNamespace(info=lambda *a, **kw: None)
        frappe_stub.log_error = lambda *args, **kwargs: None
        frappe_stub.db = types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            has_column=lambda *args, **kwargs: False,
        )
        pricing_sheet.frappe = frappe_stub

    def tearDown(self):
        frappe_stub.roles_map.clear()
        frappe_stub.session.user = "sales@example.com"
        frappe_stub.conf = types.SimpleNamespace(orderlift_use_role_capabilities=0)
        frappe_stub.db.has_column = lambda *args, **kwargs: False
        frappe_stub.db.get_value = lambda *args, **kwargs: None

    def test_sales_user_is_restricted_commercial_pricing_role(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        sheet = pricing_sheet.PricingSheet()

        self.assertTrue(sheet._is_restricted_agent_user())

    def test_commercial_agent_can_generate_quotation_without_extra_role(self):
        frappe_stub.roles_map["sales@example.com"] = ["Commercial Agent"]
        sheet = pricing_sheet.PricingSheet()

        self.assertTrue(sheet._is_restricted_agent_user())
        self.assertTrue(sheet._can_create_quotation_as_commercial_user())

    def test_sales_user_still_needs_quotation_creator_capability(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User"]
        sheet = pricing_sheet.PricingSheet()

        self.assertFalse(sheet._can_create_quotation_as_commercial_user())

        frappe_stub.roles_map["sales@example.com"] = ["Sales User", "Quotation Creator"]
        self.assertTrue(sheet._can_create_quotation_as_commercial_user())

    def test_pricing_admin_with_sales_user_is_not_restricted(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User", "Orderlift Admin"]
        sheet = pricing_sheet.PricingSheet()

        self.assertFalse(sheet._is_restricted_agent_user())

    def test_pricing_manager_with_sales_user_is_not_restricted(self):
        frappe_stub.roles_map["sales@example.com"] = ["Sales User", "Pricing Manager"]
        sheet = pricing_sheet.PricingSheet()

        self.assertFalse(sheet._is_restricted_agent_user())

    def test_restricted_static_agent_defaults_to_first_allocated_selling_list(self):
        sheet = pricing_sheet.PricingSheet()
        sheet.sales_person = "SP-BILAL"
        sheet.selected_price_list = ""

        sheet._enforce_restricted_static_agent_context(
            {"pricing_mode": pricing_sheet.STATIC_MODE, "selling_price_lists": ["Retail Agent", "Install Agent"]}
        )

        self.assertEqual(sheet.selected_price_list, "Retail Agent")

    def test_restricted_static_agent_rejects_unallocated_selling_list(self):
        sheet = pricing_sheet.PricingSheet()
        sheet.sales_person = "SP-BILAL"
        sheet.selected_price_list = "Unapproved List"

        with self.assertRaisesRegex(ValueError, "not allowed"):
            sheet._enforce_restricted_static_agent_context(
                {"pricing_mode": pricing_sheet.STATIC_MODE, "selling_price_lists": ["Retail Agent"]}
            )

    def test_restricted_commercial_user_requires_static_agent_rule(self):
        sheet = pricing_sheet.PricingSheet()
        sheet.sales_person = "SP-BILAL"
        sheet.selected_price_list = ""

        with self.assertRaisesRegex(ValueError, "No Agent Pricing Rules"):
            sheet._enforce_restricted_static_agent_context({"pricing_mode": "", "selling_price_lists": []})

        with self.assertRaisesRegex(ValueError, "Published Selling Price List"):
            sheet._enforce_restricted_static_agent_context(
                {"pricing_mode": pricing_sheet.DYNAMIC_MODE, "selling_price_lists": []}
            )

    def test_dynamic_customer_without_matching_global_tier_modifier_gets_warning(self):
        original_resolver = pricing_sheet.resolve_global_pricing_modifiers
        original_get_doc = getattr(frappe_stub, "get_doc", None)

        def has_column(doctype, fieldname):
            return (
                doctype == "Customer" and fieldname == "enable_dynamic_segmentation"
            ) or (
                doctype == "Customer Segmentation Engine" and fieldname == "custom_company"
            )

        def get_value(doctype, name_or_filters, fieldname=None, *args, **kwargs):
            if doctype == "Customer" and fieldname == "enable_dynamic_segmentation":
                return 1
            if doctype == "Customer" and fieldname == "territory":
                return ""
            if doctype == "Customer Segmentation Engine":
                return "CSEG-001"
            return None

        frappe_stub.db.has_column = has_column
        frappe_stub.db.get_value = get_value
        frappe_stub.get_doc = lambda doctype, name: _FakePolicy(
            "Company Segmentation",
            tier_modifiers=[{"is_active": 1, "tier": "Gold", "business_type": "Distribution", "crm_segment": "Grossiste"}],
            zone_modifiers=[],
        )
        pricing_sheet.resolve_global_pricing_modifiers = lambda **kwargs: (None, None, "")
        sheet = pricing_sheet.PricingSheet()
        sheet.customer = "CUST-001"
        sheet.custom_company = "Orderlift Maroc Distribution"
        sheet.tier = "New"
        sheet.crm_business_type = "Distribution"
        sheet.crm_segment = "Grossiste"
        sheet.geography_territory = ""

        try:
            tier_mod, zone_mod, warning = sheet._resolve_segmentation_modifiers()
        finally:
            pricing_sheet.resolve_global_pricing_modifiers = original_resolver
            if original_get_doc is None:
                delattr(frappe_stub, "get_doc")
            else:
                frappe_stub.get_doc = original_get_doc

        self.assertIsNone(tier_mod)
        self.assertIsNone(zone_mod)
        self.assertIn("no active global tier modifier matched Pricing Tier New", warning)

    def test_matching_global_tier_modifier_suppresses_warning(self):
        original_resolver = pricing_sheet.resolve_global_pricing_modifiers
        captured = {}
        pricing_sheet.resolve_global_pricing_modifiers = lambda **kwargs: captured.update(kwargs) or (
            {"amount": 5, "type": "Percentage", "label": "Tier: New"},
            None,
            "",
        )
        sheet = pricing_sheet.PricingSheet()
        sheet.customer = "CUST-001"
        sheet.custom_company = "Orderlift Maroc Distribution"
        sheet.tier = "New"
        sheet.crm_business_type = "Distribution"
        sheet.crm_segment = "Grossiste"
        sheet.geography_territory = ""

        try:
            tier_mod, zone_mod, warning = sheet._resolve_segmentation_modifiers()
        finally:
            pricing_sheet.resolve_global_pricing_modifiers = original_resolver

        self.assertEqual(captured["company"], "Orderlift Maroc Distribution")
        self.assertEqual(tier_mod["amount"], 5)
        self.assertIsNone(zone_mod)
        self.assertEqual(warning, "")

    def test_storage_allocation_uses_item_volume_rate_and_duration(self):
        sheet = pricing_sheet.PricingSheet()
        row = types.SimpleNamespace(item="ITEM-001")

        calc = sheet._compute_storage_for_row(
            row=row,
            qty=3,
            item_details={"ITEM-001": {"custom_volume_m3": 2}},
            storage_config={"is_active": 1, "cost_per_m3_per_month": 40, "duration_months": 1.5},
        )

        self.assertEqual(calc["line_volume_m3"], 6)
        self.assertEqual(calc["applied"], 360)
        self.assertEqual(calc["warning"], "")

    def test_storage_allocation_injects_fixed_line_expense(self):
        sheet = pricing_sheet.PricingSheet()

        expenses = sheet._inject_storage_expense(
            [],
            {"applied": 120, "line_volume_m3": 4, "cost_per_m3_per_month": 10, "duration_months": 3},
        )

        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0]["label"], "Storage Allocation")
        self.assertEqual(expenses[0]["value"], 120)
        self.assertEqual(expenses[0]["scope"], "Per Line")
        self.assertEqual(expenses[0]["override_source"], "storage_policy")

    def test_customs_uses_packaging_weight_per_unit(self):
        original_packaging = pricing_sheet.get_packaging_resolution
        original_resolve_rule = pricing_sheet.resolve_customs_rule
        original_compute = pricing_sheet.compute_customs_amount

        pricing_sheet.get_packaging_resolution = lambda **kwargs: {
            "weight_kg": 20,
            "units_per_package": 10,
            "stock_qty": kwargs.get("qty") or 0,
            "package_count": 1,
            "resolved_source": "default",
            "customs_tariff_number": "842810",
        }
        pricing_sheet.resolve_customs_rule = lambda *args, **kwargs: {
            "value_per_kg": 12,
            "rate_percent": 25,
            "rate_components": ""
        }

        def compute_customs_amount(**kwargs):
            return {
                "mode": "value_per_kg",
                "base_value": kwargs["unit_weight_kg"] * kwargs["value_per_kg"],
                "total_percent": kwargs["rate_percent"],
                "by_kg": 0,
                "by_percent": kwargs["unit_weight_kg"] * kwargs["value_per_kg"] * kwargs["rate_percent"] / 100,
                "applied": kwargs["unit_weight_kg"] * kwargs["value_per_kg"] * kwargs["rate_percent"] / 100,
                "basis": "value_per_kg",
            }

        pricing_sheet.compute_customs_amount = compute_customs_amount
        try:
            sheet = pricing_sheet.PricingSheet()
            row = types.SimpleNamespace(item="ITEM-001", qty=1, custom_packaging_profile="")
            policy = types.SimpleNamespace(
                is_active=1,
                customs_rules=[types.SimpleNamespace(
                    tariff_number="842810",
                    material="",
                    value_per_kg=12,
                    rate_components="",
                    rate_percent=25,
                    sequence=1,
                    priority=1,
                    is_active=1,
                    idx=1,
                )],
            )

            calc = sheet._compute_customs_for_row(
                row,
                base_amount=100,
                item_details={"ITEM-001": {"customs_tariff_number": "842810", "custom_weight_kg": 0}},
                customs_policy=policy,
            )

            self.assertEqual(calc["unit_weight_kg"], 2)
            self.assertEqual(calc["weight_kg"], 2)
            self.assertEqual(calc["package_weight_kg"], 20)
            self.assertEqual(calc["units_per_package"], 10)
            self.assertEqual(calc["applied"], 6)
        finally:
            pricing_sheet.get_packaging_resolution = original_packaging
            pricing_sheet.resolve_customs_rule = original_resolve_rule
            pricing_sheet.compute_customs_amount = original_compute

    def test_customs_missing_weight_falls_back_to_buying_amount(self):
        original_packaging = pricing_sheet.get_packaging_resolution
        original_resolve_rule = pricing_sheet.resolve_customs_rule
        original_compute = pricing_sheet.compute_customs_amount
        captured = {}

        pricing_sheet.get_packaging_resolution = lambda **kwargs: {}
        pricing_sheet.resolve_customs_rule = lambda *args, **kwargs: {
            "value_per_kg": 12,
            "rate_percent": 25,
            "rate_components": "",
        }

        def compute_customs_amount(**kwargs):
            captured.update(kwargs)
            return {
                "mode": "buying_amount_fallback",
                "base_value": kwargs["base_amount"],
                "total_percent": kwargs["rate_percent"],
                "by_kg": 0,
                "by_percent": kwargs["base_amount"] * kwargs["rate_percent"] / 100,
                "applied": kwargs["base_amount"] * kwargs["rate_percent"] / 100,
                "basis": "Buying Amount x Rate Percent (Weight Fallback)",
            }

        pricing_sheet.compute_customs_amount = compute_customs_amount
        try:
            sheet = pricing_sheet.PricingSheet()
            row = types.SimpleNamespace(item="ITEM-001", qty=1, custom_packaging_profile="")
            policy = types.SimpleNamespace(
                is_active=1,
                customs_rules=[types.SimpleNamespace(
                    tariff_number="842810",
                    material="",
                    value_per_kg=12,
                    rate_components="",
                    rate_percent=25,
                    sequence=1,
                    priority=1,
                    is_active=1,
                    idx=1,
                )],
            )

            calc = sheet._compute_customs_for_row(
                row,
                base_amount=100,
                item_details={"ITEM-001": {"customs_tariff_number": "842810", "custom_weight_kg": 0}},
                customs_policy=policy,
            )

            self.assertTrue(captured["base_amount_fallback"])
            self.assertEqual(calc["base_value"], 100)
            self.assertEqual(calc["applied"], 25)
            self.assertIn("buying amount", calc["warning"])
            self.assertEqual(calc["basis"], "Buying Amount x Rate Percent (Weight Fallback)")
        finally:
            pricing_sheet.get_packaging_resolution = original_packaging
            pricing_sheet.resolve_customs_rule = original_resolve_rule
            pricing_sheet.compute_customs_amount = original_compute

    def test_margin_percent_uses_configured_basis(self):
        self.assertEqual(
            pricing_sheet.compute_margin_percent_for_basis(10, "Base Price", 100, 120),
            10,
        )
        self.assertEqual(
            pricing_sheet.compute_margin_percent_for_basis(12, "Loaded Cost", 100, 120),
            10,
        )
        sale_basis_margin = 120 * 0.10 / (1 - 0.10)
        self.assertAlmostEqual(
            pricing_sheet.compute_margin_percent_for_basis(sale_basis_margin, "Sale Price", 100, 120),
            10,
            places=6,
        )

    def test_sync_customer_context_refreshes_dynamic_segmentation_tier(self):
        original_calculator = getattr(cse_module, "calculate_customer_dynamic_tier", None)
        original_context = pricing_sheet.resolve_customer_crm_pricing_context
        calls = []

        def has_column(doctype, fieldname):
            return doctype == "Customer" and fieldname == "enable_dynamic_segmentation"

        def get_value(doctype, name, fieldname=None, *args, **kwargs):
            if doctype == "Customer" and fieldname == ["tier", "enable_dynamic_segmentation"]:
                return {"tier": "Eco", "enable_dynamic_segmentation": 1}
            return None

        def calculate_customer_dynamic_tier(customer=None, apply=0):
            calls.append({"customer": customer, "apply": apply})
            return {"tier": "New", "status": "matched"}

        frappe_stub.db.has_column = has_column
        frappe_stub.db.get_value = get_value
        cse_module.calculate_customer_dynamic_tier = calculate_customer_dynamic_tier
        pricing_sheet.resolve_customer_crm_pricing_context = lambda *args, **kwargs: {
            "selected": {"business_type": "Installation", "crm_segment": "Individu"}
        }
        sheet = pricing_sheet.PricingSheet()
        sheet.customer = "CUST-001"

        try:
            sheet._sync_customer_context()
        finally:
            pricing_sheet.resolve_customer_crm_pricing_context = original_context
            if original_calculator is None:
                delattr(cse_module, "calculate_customer_dynamic_tier")
            else:
                cse_module.calculate_customer_dynamic_tier = original_calculator

        self.assertEqual(sheet.tier, "New")
        self.assertEqual(sheet.crm_business_type, "Installation")
        self.assertEqual(sheet.crm_segment, "Individu")
        self.assertEqual(calls, [{"customer": "CUST-001", "apply": 1}])

    def test_static_recalculate_does_not_calculate_margin_for_unstamped_list(self):
        original_get_prices = pricing_sheet.get_latest_item_prices
        original_apply_expenses = pricing_sheet.apply_expenses
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_prices = lambda *args, **kwargs: {"ITEM-001": 150}
        pricing_sheet.apply_expenses = lambda *args, **kwargs: {
            "projected_unit": kwargs.get("base_unit") or 0,
            "projected_line": (kwargs.get("base_unit") or 0) * (kwargs.get("qty") or 0),
            "steps": [],
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(idx=1, item="ITEM-001", qty=2, buy_price=100, manual_sell_unit_price=0)
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_benchmark_policy = lambda: None
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_segmentation_modifiers = lambda: (None, None, "")
            sheet._resolve_agent_discount_context = lambda: {}
            sheet._is_restricted_agent_user = lambda: False
            sheet._inject_modifier_expenses = lambda expenses, *args, **kwargs: (expenses, None, None)
            sheet._summarize_pricing_components = lambda steps, qty: {"tier_unit": 0, "tier_total": 0, "zone_unit": 0, "zone_total": 0}
            sheet._apply_line_discount_and_commission = lambda *args, **kwargs: None
            sheet._build_breakdown_preview = lambda steps: ""

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.margin_source, "Unstamped Static List")
            self.assertEqual(row.margin_pct, 0)
        finally:
            pricing_sheet.get_latest_item_prices = original_get_prices
            pricing_sheet.apply_expenses = original_apply_expenses
            pricing_sheet.get_pricing_currency = original_get_currency

    def test_static_recalculate_uses_stamped_builder_margin(self):
        original_get_records = pricing_sheet.get_latest_item_price_records
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_price_records = lambda *args, **kwargs: {
            "ITEM-001": {
                "item_code": "ITEM-001",
                "price_list_rate": 120,
                "custom_pricing_builder": "PBU-00001",
                "custom_source_buying_price_list": "Buy USD",
                "custom_benchmark_rule_label": "Rule A",
                "custom_target_margin_percent": 15,
                "custom_final_margin_percent": 12.5,
                "custom_builder_customs_amount": 8,
                "custom_builder_price_overridden": 1,
            }
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(idx=1, item="ITEM-001", qty=1, manual_sell_unit_price=0, discount_percent=0)
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_segmentation_modifiers = lambda: (None, None, "")
            sheet._resolve_agent_discount_context = lambda: {"max_discount_percent": 100, "commission_rate": 0}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.margin_source, "Builder Stamp")
            self.assertEqual(row.pricing_builder, "PBU-00001")
            self.assertEqual(row.builder_source_buying_price_list, "Buy USD")
            self.assertEqual(row.resolved_benchmark_rule, "Rule A")
            self.assertEqual(row.target_margin_percent, 15)
            self.assertEqual(row.builder_margin_percent, 12.5)
            self.assertEqual(row.margin_pct, 12.5)
            self.assertEqual(row.customs_unit_amount, 8)
            self.assertEqual(row.customs_applied, 8)
            self.assertEqual(row.builder_price_overridden, 1)
        finally:
            pricing_sheet.get_latest_item_price_records = original_get_records
            pricing_sheet.get_pricing_currency = original_get_currency

    def test_static_manual_override_recalculates_actual_margin(self):
        original_get_records = pricing_sheet.get_latest_item_price_records
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_price_records = lambda *args, **kwargs: {
            "ITEM-001": {
                "item_code": "ITEM-001",
                "price_list_rate": 120,
                "custom_pricing_builder": "PBU-00001",
                "custom_target_margin_percent": 20,
                "custom_final_margin_percent": 20,
                "custom_benchmark_rule_max_discount_percent": 100,
                "custom_last_builder_buy_rate": 100,
                "custom_builder_expense_amount": 10,
                "custom_builder_customs_amount": 5,
                "custom_builder_margin_basis": "Base Price",
            }
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(idx=1, item="ITEM-001", qty=1, manual_sell_unit_price=140, discount_percent=0)
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_segmentation_modifiers = lambda: (None, None, "")
            sheet._resolve_agent_discount_context = lambda: {"max_discount_percent": 100, "commission_rate": 0}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.final_sell_unit_price, 140)
            self.assertEqual(row.margin_unit_amount, 25)
            self.assertEqual(row.margin_pct, 25)
            self.assertEqual(row.builder_margin_percent, 25)
            self.assertEqual(row.target_margin_percent, 20)
        finally:
            pricing_sheet.get_latest_item_price_records = original_get_records
            pricing_sheet.get_pricing_currency = original_get_currency

    def test_static_manual_override_can_show_negative_margin(self):
        original_get_records = pricing_sheet.get_latest_item_price_records
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_price_records = lambda *args, **kwargs: {
            "ITEM-001": {
                "item_code": "ITEM-001",
                "price_list_rate": 120,
                "custom_pricing_builder": "PBU-00001",
                "custom_target_margin_percent": 20,
                "custom_final_margin_percent": 20,
                "custom_benchmark_rule_max_discount_percent": 100,
                "custom_last_builder_buy_rate": 100,
                "custom_builder_expense_amount": 10,
                "custom_builder_customs_amount": 5,
                "custom_builder_margin_basis": "Base Price",
            }
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(idx=1, item="ITEM-001", qty=1, manual_sell_unit_price=110, discount_percent=0)
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_segmentation_modifiers = lambda: (None, None, "")
            sheet._resolve_agent_discount_context = lambda: {"max_discount_percent": 100, "commission_rate": 0}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.margin_unit_amount, -5)
            self.assertEqual(row.margin_pct, -5)
            self.assertEqual(row.builder_margin_percent, -5)
        finally:
            pricing_sheet.get_latest_item_price_records = original_get_records
            pricing_sheet.get_pricing_currency = original_get_currency

    def test_static_recalculate_applies_tier_and_territory_modifiers(self):
        original_get_prices = pricing_sheet.get_latest_item_prices
        original_get_currency = pricing_sheet.get_pricing_currency
        original_compute_step = pricing_sheet.compute_policy_adjustment_step
        pricing_sheet.get_latest_item_prices = lambda *args, **kwargs: {"ITEM-001": 100}
        pricing_sheet.get_pricing_currency = lambda: "USD"
        pricing_sheet.compute_policy_adjustment_step = _fake_policy_adjustment_step
        try:
            row = types.SimpleNamespace(
                idx=1,
                item="ITEM-001",
                qty=2,
                buy_price=80,
                manual_sell_unit_price=0,
                discount_percent=0,
            )
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet.tier = "Eco"
            sheet.crm_business_type = "Installation"
            sheet.crm_segment = "Individu"
            sheet.geography_territory = "Casablanca"
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_segmentation_modifiers = lambda: (
                {"amount": 10, "type": "Fixed", "label": "Tier: Eco"},
                {"amount": 5, "type": "Fixed", "label": "Zone: Casablanca"},
                "",
            )
            sheet._resolve_agent_discount_context = lambda: {}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.final_sell_unit_price, 115)
            self.assertEqual(row.tier_modifier_amount, 10)
            self.assertEqual(row.tier_modifier_total, 20)
            self.assertEqual(row.zone_modifier_amount, 5)
            self.assertEqual(row.zone_modifier_total, 10)
            self.assertEqual(sheet.total_expenses, 30)
        finally:
            pricing_sheet.get_latest_item_prices = original_get_prices
            pricing_sheet.get_pricing_currency = original_get_currency
            pricing_sheet.compute_policy_adjustment_step = original_compute_step

    def test_static_recalculate_uses_stamped_rule_max_discount(self):
        original_get_records = pricing_sheet.get_latest_item_price_records
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_price_records = lambda *args, **kwargs: {
            "ITEM-001": {
                "item_code": "ITEM-001",
                "price_list_rate": 120,
                "custom_pricing_builder": "PBU-00001",
                "custom_benchmark_is_fallback": 0,
                "custom_benchmark_rule_max_discount_percent": 7,
                "custom_fallback_max_discount_percent": 12,
            }
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(
                idx=1,
                item="ITEM-001",
                qty=1,
                buy_price=80,
                manual_sell_unit_price=0,
                discount_percent=6,
            )
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_agent_discount_context = lambda: {"max_discount_percent": 12, "commission_rate": 0}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.max_discount_percent_allowed, 7)
        finally:
            pricing_sheet.get_latest_item_price_records = original_get_records
            pricing_sheet.get_pricing_currency = original_get_currency

    def test_static_recalculate_uses_stamped_fallback_max_discount(self):
        original_get_records = pricing_sheet.get_latest_item_price_records
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_price_records = lambda *args, **kwargs: {
            "ITEM-001": {
                "item_code": "ITEM-001",
                "price_list_rate": 120,
                "custom_pricing_builder": "PBU-00001",
                "custom_benchmark_is_fallback": 1,
                "custom_benchmark_rule_max_discount_percent": 0,
                "custom_fallback_max_discount_percent": 8,
            }
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(
                idx=1,
                item="ITEM-001",
                qty=1,
                buy_price=80,
                manual_sell_unit_price=0,
                discount_percent=4,
            )
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_static_benchmark_policy = lambda: None
            sheet._resolve_agent_discount_context = lambda: {"max_discount_percent": 5, "commission_rate": 0}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.max_discount_percent_allowed, 8)
        finally:
            pricing_sheet.get_latest_item_price_records = original_get_records
            pricing_sheet.get_pricing_currency = original_get_currency

    def test_static_recalculate_uses_selected_policy_fallback_max_discount_without_stamp(self):
        original_get_records = pricing_sheet.get_latest_item_price_records
        original_get_currency = pricing_sheet.get_pricing_currency
        pricing_sheet.get_latest_item_price_records = lambda *args, **kwargs: {
            "ITEM-001": {
                "item_code": "ITEM-001",
                "price_list_rate": 120,
            }
        }
        pricing_sheet.get_pricing_currency = lambda: "USD"
        try:
            row = types.SimpleNamespace(
                idx=1,
                item="ITEM-001",
                qty=1,
                buy_price=0,
                manual_sell_unit_price=0,
                discount_percent=4,
            )
            sheet = pricing_sheet.PricingSheet()
            sheet.lines = [row]
            sheet.selected_price_list = "Retail Agent"
            sheet._resolve_static_benchmark_policy = lambda: _FakePolicy(
                "PBPOL-00001",
                fallback_max_discount_percent=5,
            )
            sheet._resolve_agent_discount_context = lambda: {"max_discount_percent": 0, "commission_rate": 0}
            sheet._is_restricted_agent_user = lambda: False

            sheet._recalculate_static({"selling_price_lists": ["Retail Agent"]}, 0)

            self.assertEqual(row.max_discount_percent_allowed, 5)
            self.assertEqual(sheet.applied_benchmark_policy, "PBPOL-00001")
        finally:
            pricing_sheet.get_latest_item_price_records = original_get_records
            pricing_sheet.get_pricing_currency = original_get_currency


class _FakePolicy(dict):
    def __init__(self, name, **values):
        super().__init__(**values)
        self.name = name


def _fake_policy_adjustment_step(**kwargs):
    return {
        "label": kwargs.get("label") or "Modifier",
        "type": kwargs.get("adjustment_type") or "Fixed",
        "applies_to": kwargs.get("adjustment_basis") or "Base Price",
        "scope": "Per Unit",
        "value": kwargs.get("value") or 0,
        "sequence": kwargs.get("sequence") or 0,
        "is_active": 1,
        "override_source": kwargs.get("override_source") or "",
    }


if __name__ == "__main__":
    unittest.main()
