from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestQuotationFormSimplify(unittest.TestCase):
    def test_quotation_hook_uses_versioned_local_file_without_query_string(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js"

        self.assertIn('"public/js/quotation_form_simplify_20260802a.js"', hooks)
        self.assertNotIn("quotation_form_simplify_20260802a.js?", hooks)
        self.assertTrue(script.is_file())

    def test_quotation_override_uses_server_boot_capability(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertIn("frappe.boot.orderlift_capabilities", script)
        self.assertIn("quotation_override", script)
        self.assertNotIn("PRICE_OVERRIDE_ROLES", script)

    def test_sales_order_creation_stays_native_erpnext_behavior(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()

        self.assertNotIn("SALES_ORDER_ACTION_CONTEXT_METHOD", script)
        self.assertNotIn("ensureSalesOrderCreateAction", script)
        self.assertNotIn('frm.add_custom_button(__("Sales Order")', script)
        self.assertNotIn("get_sales_order_creation_context", quotation_hooks)
        self.assertNotIn("quotation_sales_order_action_20260724", hooks)
        self.assertNotIn("orderlift-quotation-sales-order-action", script)
        self.assertNotIn('frm.add_custom_button(__("Create Sales Order")', script)
        self.assertNotIn("frm.page.set_primary_action", script)

    def test_optional_quotation_grid_fields_are_checked_without_grid_get_field(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertIn("function quotationGridHasField(grid, fieldname)", script)
        self.assertIn("(grid.docfields || []).some((field) => field.fieldname === fieldname)", script)
        self.assertIn("if (!quotationGridHasField(grid, fieldname)) return;", script)
        self.assertNotIn("if (!grid.get_field || !grid.get_field(fieldname)) return;", script)
        self.assertNotIn('if (grid.get_field && grid.get_field("source_price_list_sell_rate"))', script)

    def test_draft_quotation_has_deterministic_ttc_recalculation_action(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            "addRecalculateTTCGridButton",
            "recalculateQuotationTTC",
            'grid.add_custom_button(__("Recalculate TTC"), recalculate);',
            "frm.cscript.calculate_taxes_and_totals",
            "frappe.after_ajax",
            'data-orderlift-recalculate-ttc',
        ]:
            self.assertIn(token, script)
        self.assertNotIn("[100, 500, 1200]", script)

    def test_quotation_margin_fields_are_available_to_column_selector(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        hidden_block = pricing_setup.split("quotation_item_hidden_fields = [", 1)[1].split("]", 1)[0]
        visible_block = pricing_setup.split("quotation_item_visible_fields = [", 1)[1].split("]", 1)[0]

        self.assertNotIn('"source_margin_percent"', hidden_block)
        self.assertNotIn('"source_margin_basis"', hidden_block)
        self.assertIn('("source_margin_percent", "Actual Margin %")', visible_block)
        self.assertIn('("source_target_margin_percent", "Target Policy Margin %")', visible_block)
        self.assertIn('("source_margin_basis", "Margin Basis")', visible_block)

    def test_transaction_margin_fields_are_privileged_and_native_uplift_is_hidden(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()

        for doctype in ["Quotation Item", "Sales Order Item"]:
            self.assertIn(f'"{doctype}": [', pricing_setup)
        for fieldname in [
            "source_target_margin_percent",
            "source_margin_percent",
            "source_margin_basis",
            "source_base_buy_rate",
            "source_landed_cost",
        ]:
            self.assertIn(f'"fieldname": "{fieldname}"', pricing_setup)
            self.assertIn('"permlevel": 2', pricing_setup)

        sales_order_layout = pricing_setup.split("def ensure_sales_order_pricing_layout():", 1)[1]
        self.assertIn('"Sales Order",\n        ("customer_name", "customer", "tax_id"),\n        "is_subcontracted"', sales_order_layout)
        self.assertIn('_upsert_property_setter("Sales Order", "is_subcontracted", "hidden", "1", "Check")', sales_order_layout)
        for fieldname in ["rate_with_margin", "margin_type", "margin_rate_or_amount"]:
            self.assertIn(f'"{fieldname}"', sales_order_layout.split("sales_order_item_hidden_fields = [", 1)[1].split("]", 1)[0])
        sales_invoice_layout = pricing_setup.split("def ensure_sales_invoice_pricing_layout():", 1)[1]
        self.assertIn('"Sales Invoice",\n        ("customer_name", "customer", "tax_id"),\n        "custom_invoice_mode"', sales_invoice_layout)
        self.assertIn('_upsert_property_setter("Sales Invoice", "selected_selling_price_lists", "read_only", "1", "Check")', sales_invoice_layout)
        self.assertIn('"ignore_pricing_rule", "pricing_rules"', sales_invoice_layout)
        self.assertIn('_upsert_property_setter("Sales Invoice", fieldname, "hidden", "1", "Check")', sales_invoice_layout)
        self.assertIn('"Sales Invoice": [', pricing_setup)
        self.assertIn('"fieldname": "selected_selling_price_lists"', pricing_setup)

    def test_sales_invoice_customer_and_stock_cleanup_is_server_side(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()
        sales_invoice_layout = pricing_setup.split("def ensure_sales_invoice_pricing_layout():", 1)[1]

        self.assertIn('("tax_id", "Customer ICE / Tax ID")', pricing_setup)
        self.assertIn('("company_tax_id", "Company ICE / Tax ID")', pricing_setup)
        self.assertIn('_upsert_property_setter("Sales Invoice", "company_tax_id", "hidden", "1", "Check")', sales_invoice_layout)
        for fieldname in ["contact_mobile", "contact_email"]:
            self.assertIn(f'"{fieldname}"', sales_invoice_layout)
            self.assertIn('_upsert_property_setter("Sales Invoice", fieldname, "hidden", "0", "Check")', sales_invoice_layout)
        for fieldname in [
            "scan_barcode",
            "last_scanned_warehouse",
            "update_stock",
            "set_warehouse",
            "set_target_warehouse",
        ]:
            self.assertIn(f'"{fieldname}"', sales_invoice_layout)
        for fieldname in ["incoming_rate", "allow_zero_valuation_rate"]:
            self.assertIn(f'"{fieldname}"', sales_invoice_layout)
            self.assertIn('_upsert_property_setter("Sales Invoice Item", fieldname, "hidden", "1", "Check")', sales_invoice_layout)
        self.assertNotIn('"public/js/logistics_quantity_only_20260804a.js",\n    ],\n    "Purchase Invoice"', hooks)
        self.assertIn("orderlift.orderlift_sales.sales_invoice_hooks.prepare_non_stock_sales_invoice_items", hooks)
        self.assertIn('"public/js/sales_invoice_mode_20260812d.js"', hooks)

        hooks = (APP_ROOT / "hooks.py").read_text()
        self.assertIn("sales_order_pricing_visibility_20260803a.js", hooks)
        self.assertIn("orderlift.orderlift_sales.sales_order_pricing_hooks.copy_sales_invoice_pricing_context", hooks)

    def test_sales_order_grid_uses_quotation_decimal_display_pattern(self):
        script = (APP_ROOT / "public" / "js" / "sales_order_pricing_visibility_20260803a.js").read_text()

        for token in [
            "scheduleSalesOrderPrecisionDisplay",
            "applySalesOrderPrecisionDisplay",
            "applySalesOrderPrecisionGridRowDisplay",
            "displaySalesOrderInputNumber",
            "patchSalesOrderGridRefresh",
            "Number(value || 0).toFixed(2)",
        ]:
            self.assertIn(token, script)

    def test_sales_order_commercial_prices_follow_edit_permission(self):
        script = (APP_ROOT / "public" / "js" / "sales_order_pricing_visibility_20260803a.js").read_text()

        self.assertIn("function canViewCommercialPrices()", script)
        self.assertIn('canDoctypePermission("write") || canDoctypePermission("create")', script)
        self.assertIn("function applyDocumentPricingVisibility(frm)", script)
        self.assertIn('const COMMERCIAL_TABLE_FIELDS = ["taxes", "payment_schedule"]', script)
        self.assertIn('grid.update_docfield_property(fieldname, "hidden", commercialVisible ? 0 : 1)', script)
        self.assertIn('const visible = commercialVisible && canViewProfitability();', script)

    def test_quotation_item_grid_preserves_user_configured_columns(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            "configuredQuotationItemGridColumns",
            'frappe.get_user_settings(frm.doctype, "GridView")',
            "savedColumns",
            '"source_target_margin_percent"',
        ]:
            self.assertIn(token, script)
        self.assertNotIn("gridViewSettings.GridView[grid.doctype] =", script)

    def test_quotation_item_grid_keeps_last_data_field_full_width(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            "--orderlift-grid-cell-width",
            ".grid-static-col[data-fieldname]:last-child",
            "position: static",
            "min-width: max-content",
        ]:
            self.assertIn(token, script)
        self.assertNotIn('canViewQuotationMargins() ? "2100px" : "1820px"', script)

    def test_quotation_item_grid_uses_one_aligned_horizontal_scroll_layout(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            ".orderlift-inline-items-grid .form-grid-container.column-limit-reached",
            ".column-limit-reached .form-grid .grid-static-col[data-fieldname]",
            "justify-content: flex-start",
            "box-sizing: border-box",
            "--orderlift-grid-cell-width: 140px",
            "width: max-content",
        ]:
            self.assertIn(token, script)
        self.assertNotIn(
            ".orderlift-inline-items-grid {\n                    overflow-x: auto;",
            script,
        )

    def test_quotation_form_simplifier_is_wired_and_hides_only_discount_fields(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertIn('"Quotation": [', hooks)
        self.assertIn('"public/js/quotation_form_simplify_20260802a.js', hooks)
        for fieldname in [
            "additional_discount_section",
            "apply_discount_on",
            "coupon_code",
            "additional_discount_percentage",
            "discount_amount",
            "referral_sales_partner",
        ]:
            self.assertIn(fieldname, script)
        for token in [
            "showOpportunityField",
            "showTaxFields",
            "setupTaxTemplateQuery",
            "TAX_DETAIL_FIELDS",
            'frm.set_query("taxes_and_charges"',
            "filters.company = frm.doc.company",
            'frm.toggle_enable("opportunity", true)',
            'frm.set_df_property(fieldname, "hidden", 0)',
            'frm.toggle_display(fieldname, true)',
            'frm.refresh_field("opportunity")',
        ]:
            self.assertIn(token, script)

    def test_quotation_form_has_bulk_quantity_action_for_selected_items(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            "Bulk Quantity",
            "addBulkQuantityGridButton",
            "grid.add_custom_button",
            ".grid-add-multiple-rows",
            "data-orderlift-bulk-quantity",
            "getSelectedItemRows",
            "get_selected_children",
            "Apply Quantity to Selected Items",
            'frappe.model.set_value(row.doctype, row.name, "qty", qty)',
            'frm.refresh_field("items")',
        ]:
            self.assertIn(token, script)

    def test_quotation_form_has_selected_or_all_bulk_discount_with_override_report(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            "Bulk Discount",
            "addBulkDiscountGridButton",
            "openBulkDiscountDialog",
            "applyBulkDiscount",
            "selectedRows.length ? selectedRows : (frm.doc.items || [])",
            "discount > maxDiscount + 0.000001",
            "canOverrideQuotationPricing()",
            "Skipped below-cap rows",
            "Admin override applied above max",
            "applyResolvedRate",
            "syncItemTTCFields",
        ]:
            self.assertIn(token, script)

    def test_quotation_list_uses_id_first_columns(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_list_20260706a.js").read_text()

        self.assertIn('"Quotation": "public/js/quotation_list_20260706a.js"', hooks)
        for token in [
            "isReportView",
            'viewName === "report"',
            'constructor?.name === "ReportView"',
            'typeof listview?.build_row === "function"',
            "sanitizeQuotationReportFields",
            'sourceDoctype === "Quotation"',
            "Removed child-table columns from Quotation Report View",
            "useQuotationIdAsSubject",
            "configuredListColumns",
            "configuredListFields",
            "JSON.parse(listview.list_view_settings.fields)",
            'type: "Subject"',
            'fieldname: "name"',
            "fieldColumn(fieldname, field.label)",
            "orderlift-quotation-list",
            "orderlift-quotation-list-style",
            "existingOnload(listview)",
            "patchQuotationColumnSetup",
            "OPPORTUNITY_COLUMNS",
            "custom_opportunity_title",
            "custom_opportunity_owner",
            "ensureQuotationOpportunityColumns",
            "ensureQuotationReportOpportunityFields",
            "add_fields",
            "flex: 0 0 250px !important",
            "max-width: 250px !important",
            "min-width: 250px",
        ]:
            self.assertIn(token, script)
        self.assertNotIn("QUOTATION_LIST_FIELDS", script)
        self.assertNotIn("max-width: 220px", script)

    def test_quotation_opportunity_snapshot_and_other_charge_hooks_are_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()
        child_doctype = APP_ROOT / "orderlift_sales" / "doctype" / "orderlift_quotation_other_charge" / "orderlift_quotation_other_charge.json"
        master_doctype = APP_ROOT / "orderlift_sales" / "doctype" / "orderlift_other_charge" / "orderlift_other_charge.json"

        self.assertIn("sync_quotation_opportunity_snapshot", hooks)
        self.assertIn("sync_quotation_other_charges", hooks)
        self.assertLess(
            hooks.index("sync_quotation_other_charges"),
            hooks.index("sync_quotation_pricing_snapshot_fields"),
        )
        for token in [
            '"fieldname": "custom_opportunity_title"',
            '"fieldname": "custom_opportunity_owner"',
            '"fieldname": "custom_other_charges"',
            '"options": "Orderlift Quotation Other Charge"',
            '"fieldname": "custom_orderlift_other_charge"',
        ]:
            self.assertIn(token, pricing_setup)
        for token in [
            "def sync_quotation_opportunity_snapshot",
            "def sync_quotation_other_charges",
            "def get_other_charge_template",
            "charge.uom = uom",
            "charge.item_code = item_code",
            "charge.expected_unit_cost = expected_unit_cost",
            "charge.expected_cost = expected_cost",
            '"source_landed_cost": expected_unit_cost',
            "CAPABILITY_PRIVILEGED_PRICING",
            "previous_values",
            "template_changed",
            "custom_orderlift_other_charge",
            '"custom_presentation_role": "Print separately"',
        ]:
            self.assertIn(token, quotation_hooks)
        self.assertIn('"custom_orderlift_other_charge",', (APP_ROOT / "orderlift_sales" / "sales_order_pricing_hooks.py").read_text())
        self.assertIn('"custom_orderlift_other_charge",', (APP_ROOT / "orderlift_sales" / "utils" / "commercial_presentation.py").read_text())
        pricing_sheet = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()
        self.assertIn('row.item == "OTHER-CHARGES"', pricing_sheet)
        self.assertIn('item_data["custom_orderlift_other_charge"] = 1', pricing_sheet)
        for token in [
            "ensure_default_other_charges",
            '"Orderlift Other Charge"',
            '"Sales Order Item": [',
            '"Delivery Note Item": _commercial_presentation_item_fields',
            '"Sales Invoice Item": _commercial_presentation_item_fields',
        ]:
            self.assertIn(token, pricing_setup)
        for token in [
            "OTHER_CHARGE_TEMPLATE_METHOD",
            'fieldname: "other_charge"',
            'options: "Orderlift Other Charge"',
            "loadOtherChargeTemplate",
            'frappe.ui.form.on("Orderlift Quotation Other Charge",',
            "fillOtherChargeChildRow",
            "updateOtherChargeChildAmount",
            'fieldname: "expected_unit_cost"',
            'dialog.set_value("expected_unit_cost"',
            'frappe.model.set_value(cdt, cdn, "expected_cost"',
            "source_landed_cost: expectedUnitCost",
            'dialog.set_value("description"',
        ]:
            self.assertIn(token, script)
        self.assertIn('frm.add_child("custom_other_charges"', script)
        self.assertIn("other_charge: otherCharge", script)
        self.assertIn("custom_orderlift_other_charge", script)
        self.assertTrue(child_doctype.is_file())
        self.assertIn('"fieldname": "other_charge"', child_doctype.read_text())
        self.assertIn('"options": "Orderlift Other Charge"', child_doctype.read_text())
        self.assertIn('"istable": 1', child_doctype.read_text())
        self.assertIn('"fieldname": "expected_unit_cost"', child_doctype.read_text())
        self.assertIn('"fieldname": "expected_cost"', child_doctype.read_text())
        self.assertIn('"permlevel": 2', child_doctype.read_text())
        self.assertIn('"reqd": 1', child_doctype.read_text())
        self.assertTrue(master_doctype.is_file())
        self.assertIn('"name": "Orderlift Other Charge"', master_doctype.read_text())
        self.assertIn('"fieldname": "default_expected_unit_cost"', master_doctype.read_text())
        self.assertIn('"permlevel": 2', master_doctype.read_text())
        self.assertIn('permission.write = 1 if doctype == "Quotation" else 0', pricing_setup)
        self.assertIn("canViewQuotationMargins() ? [{", script)
        self.assertIn("dialog.disable_primary_action()", script)
        self.assertIn("dialog.enable_primary_action()", script)

    def test_opportunity_list_uses_id_first_with_min_width(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "opportunity_list_20260702b.js").read_text()

        self.assertIn('"Opportunity": "public/js/opportunity_list_20260702b.js"', hooks)
        for token in [
            "defaultOpportunityToReportView",
            'frappe.set_route("List", "Opportunity", "Report")',
            "isReportView",
            "useOpportunityIdAsSubject",
            "patchOpportunityColumnSetup",
            "orderlift-opportunity-list",
            "orderlift-opportunity-list-style",
            "existingOnload(listview)",
            "min-width: 250px",
            'subject.df = { fieldname: "name", label: __("ID") }',
        ]:
            self.assertIn(token, script)

    def test_opportunity_site_city_is_not_duplicate_city_standard_filter(self):
        fixture = (APP_ROOT / "fixtures" / "custom_field_crm_classification.json").read_text()

        self.assertIn('"fieldname": "custom_city"', fixture)
        self.assertIn('"label": "Site City"', fixture)
        self.assertIn('"in_standard_filter": 0', fixture)

    def test_quotation_party_defaults_are_loaded_from_customer(self):
        script = (APP_ROOT / "public" / "js" / "crm_classification_20260723a.js").read_text()
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()
        propagation = (APP_ROOT / "orderlift_crm" / "party_propagation.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()

        self.assertIn("syncTransactionPartyDefaults", script)
        self.assertIn('method: "orderlift.orderlift_crm.api.pipeline.get_party_defaults"', script)
        self.assertIn("customer_address", script)
        self.assertIn("contact_person", script)
        self.assertIn("shipping_address_name", script)
        self.assertIn('context["address_name"] = context.get("billing_address_name")', pipeline)
        self.assertIn('"billing_address_name": billing_address_name or ""', propagation)
        self.assertIn('"contact_name": contact_name or ""', propagation)
        self.assertIn('"orderlift.orderlift_sales.quotation_hooks.apply_quotation_party_defaults"', hooks)
        self.assertIn('"additional_info_section", "insert_after", anchor, "Data"', pricing_setup)

    def test_pricing_setup_adds_ttc_and_pricing_snapshot_fields(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        builder_js = (APP_ROOT / "orderlift_sales" / "page" / "pricing_sheet_builder" / "pricing_sheet_builder.js").read_text()
        builder_py = (APP_ROOT / "orderlift_sales" / "page" / "pricing_sheet_builder" / "pricing_sheet_builder.py").read_text()
        pricing_sheet_json = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.json").read_text()
        tax_utils = (APP_ROOT / "orderlift_sales" / "utils" / "tax_inclusive.py").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()

        for token in [
            '"fieldname": "custom_pu_ttc"',
            '"fieldname": "custom_pt_ttc"',
            '"fieldname": "custom_applied_taxes"',
            '"fieldname": "source_price_list_sell_rate"',
            '"source_discount_percent", "Remise %"',
            '"source_max_discount_percent", "Max Discount %"',
            '"source_commission_amount", "Commission Amount"',
            '"discount_percentage"',
            'ensure_quotation_pricing_layout()',
        ]:
            self.assertIn(token, pricing_setup)
        self.assertIn('"fieldname": "taxes_and_charges_template"', pricing_sheet_json)
        for token in ["custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc", "taxes_and_charges_template"]:
            self.assertIn(token, builder_js)
            self.assertIn(token, builder_py)
        for token in ["Applied Taxes", "PU TTC", "PT TTC"]:
            self.assertIn(token, builder_js)
        self.assertIn("def sync_pricing_sheet_item_tax_inclusive_fields", tax_utils)
        self.assertIn("def sync_quotation_item_tax_inclusive_fields", tax_utils)
        self.assertIn("def apply_quotation_sales_tax_template", tax_utils)
        self.assertIn("def quote_item_inclusive_totals", tax_utils)
        self.assertIn("def build_catalogue_ttc_price_map", tax_utils)
        self.assertIn("def company_default_sales_taxes_template", tax_utils)
        self.assertIn("def sales_tax_template_total_rate", tax_utils)
        self.assertIn("def _validate_sales_tax_template_company", tax_utils)
        self.assertIn("def _party_is_exempt_from_sales_tax", tax_utils)
        self.assertIn("exempt_from_sales_tax", tax_utils)
        self.assertIn("doc.taxes_and_charges = \"\"", tax_utils)
        self.assertIn("def _copy_sales_tax_template_rows", tax_utils)
        self.assertIn('frappe.get_doc("Sales Taxes and Charges Template", template_name)', tax_utils)
        self.assertIn('doc.append("taxes", values)', tax_utils)
        self.assertIn('_clear_tax_rows(doc)', tax_utils)
        self.assertIn("custom_default_sales_taxes_template", pricing_setup)
        self.assertIn("flt(value) * (1 + rate / 100.0)", tax_utils)
        self.assertIn('"orderlift.orderlift_sales.quotation_hooks.sync_quotation_pricing_snapshot_fields"', hooks)
        self.assertIn("get_quotation_ttc_print_context", hooks)
        self.assertIn("apply_quotation_sales_tax_template", quotation_hooks)
        self.assertIn("reprice_quotation_items_from_selected_price_lists", quotation_hooks)
        self.assertIn("apply_quotation_sales_tax_template(quotation)", (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text())
        self.assertIn('field === "taxes_and_charges_template"', builder_js)
        self.assertIn("filters.company = company", builder_js)

    def test_direct_quotation_commission_has_explicit_salesperson_context(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()
        quotation_script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertIn('"fieldname": "commission_sales_person"', pricing_setup)
        self.assertIn("resolve_quotation_commission_context", quotation_hooks)
        self.assertIn('row.source_sales_person = sales_person', quotation_hooks)
        self.assertIn("commission_sales_person(frm)", price_queries)
        self.assertIn("sales_person: frm.doc.commission_sales_person", price_queries)
        self.assertIn('setChildValue(row, "source_sales_person"', price_queries)
        self.assertIn('{ fieldname: "source_commission_rate", columns: 1, sticky: 0 }', quotation_script)
        self.assertIn('{ fieldname: "source_commission_amount", columns: 1, sticky: 0 }', quotation_script)
        for fieldname in ("commission_sales_person", "source_sales_person", "source_commission_rate", "source_commission_amount"):
            field_block = pricing_setup.split(f'"fieldname": "{fieldname}"', 1)[1].split("},", 1)[0]
            self.assertIn('"print_hide": 1', field_block)

    def test_quotation_commission_salesperson_ui_follows_role_matrix(self):
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()
        item_tools = (APP_ROOT / "orderlift_sales" / "utils" / "item_price_tools.py").read_text()
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        self.assertIn("get_quotation_commission_assignment_context", quotation_hooks)
        self.assertNotIn("Select a Commission Salesperson before submitting", quotation_hooks)
        self.assertIn("applyQuotationCommissionAssignment", price_queries)
        self.assertIn("can_edit_sales_person", price_queries)
        self.assertIn("No commission will be generated", price_queries)
        self.assertIn("!context.can_edit_sales_person", price_queries)
        self.assertIn('return "" if _can_select_any_commission_salesperson() else own_sales_person', item_tools)

    def test_commission_workflow_is_wired_to_customer_payment_events(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        calculator = (APP_ROOT / "sales" / "utils" / "commission_calculator.py").read_text()
        commission_controller = (
            APP_ROOT / "orderlift_sales" / "doctype" / "sales_commission" / "sales_commission.py"
        ).read_text()
        commission_form = (
            APP_ROOT / "orderlift_sales" / "doctype" / "sales_commission" / "sales_commission.js"
        ).read_text()

        self.assertIn("sync_commissions_from_payment_entry", hooks)
        self.assertIn("_sales_order_is_fully_billed", calculator)
        self.assertIn('self.status != "To Pay"', commission_controller)
        self.assertIn('frm.doc.status === "To Pay"', commission_form)
        self.assertNotIn("base_amount * (frm.doc.commission_rate / 100)", commission_form)

    def test_quotation_and_pricing_sheet_stock_snapshot_wiring(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        quotation_js = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()
        pricing_sheet_js = (APP_ROOT / "public" / "js" / "pricing_sheet_form_20260501_110.js").read_text()
        item_tools = (APP_ROOT / "orderlift_sales" / "utils" / "item_price_tools.py").read_text()
        stock_table = (APP_ROOT / "orderlift_sales" / "doctype" / "orderlift_transaction_warehouse_stock" / "orderlift_transaction_warehouse_stock.json").read_text()
        shared_table = (APP_ROOT / "orderlift_sales" / "doctype" / "orderlift_shared_company_stock" / "orderlift_shared_company_stock.json").read_text()
        sharing_utils = (APP_ROOT / "orderlift_sales" / "utils" / "price_list_sharing.py").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()

        for token in [
            '"fieldname": "custom_stock_snapshot_section"',
            '"fieldname": "custom_warehouse_stock_snapshot"',
            '"options": "Orderlift Transaction Warehouse Stock"',
            '"fieldname": "custom_shared_company_stock_section"',
            '"fieldname": "custom_shared_company_stock"',
            '"options": "Orderlift Shared Company Stock"',
            '"fieldname": "custom_current_company_stock_qty"',
            '"fieldname": "custom_available_after_so_qty"',
            '"fieldname": "custom_projected_available_qty"',
            '"description": "On hand minus open confirmed Sales Order demand: what physically remains for new orders."',
            '"description": "On hand minus what the stock planner would reserve today, plus safely usable incoming stock (same rules as the current Stock Planning Settings)."',
            "Qty: on hand. Available After SO: on hand minus open confirmed Sales Order demand. Projected Available: Available After SO plus expected incoming Purchase Order quantity.",
        ]:
            self.assertIn(token, pricing_setup)
        self.assertIn("def get_transaction_stock_snapshot", item_tools)
        self.assertIn("stock_warehouse_condition(\"w.name\", params)", item_tools)
        self.assertIn("_stock_snapshot_supplementary", item_tools)
        self.assertIn("_simulation_totals", item_tools)
        self.assertIn("_shared_company_snapshot", item_tools)
        self.assertIn("def _shared_company_stock_rows", item_tools)
        self.assertIn('"shared_rows": shared_rows', item_tools)
        self.assertIn("def resolve_shared_companies_from_price_lists", sharing_utils)
        self.assertIn("def resolve_shared_stock_companies", sharing_utils)
        self.assertIn("resolve_shared_stock_companies(doc)", quotation_hooks)
        self.assertIn("custom_shared_company_stock", quotation_hooks)
        self.assertIn('"available_after_so_qty"', stock_table)
        self.assertIn('"projected_available_qty"', stock_table)
        self.assertIn('"description": "On hand: current physical quantity in this warehouse."', stock_table)
        self.assertIn('"description": "On hand minus open confirmed Sales Order demand for this warehouse."', stock_table)
        self.assertIn('"description": "Available After SO plus the Purchase Order quantity expected into this warehouse."', stock_table)
        self.assertIn("Orderlift Transaction Warehouse Stock", stock_table)
        self.assertIn('"ignore_user_permissions": 1', stock_table)
        self.assertIn('"fieldname": "company"', shared_table)
        self.assertIn('"fieldname": "available_after_so_qty"', shared_table)
        self.assertIn('"fieldname": "projected_available_qty"', shared_table)
        self.assertIn("Orderlift Shared Company Stock", shared_table)
        for token in [
            "get_transaction_stock_snapshot",
            "company: frm.doc.company",
            "scheduleQuotationStockSnapshotRefresh",
            "custom_warehouse_stock_snapshot",
            "custom_current_company_stock_qty",
            "available_after_so_qty",
            "projected_available_qty",
            "item_totals",
            'frappe.model.clear_table(frm.doc, fieldname)',
            'frappe.model.add_child(frm.doc, "Orderlift Transaction Warehouse Stock", fieldname)',
            "syncQuotationStockSnapshotTable",
        ]:
            self.assertIn(token, quotation_js)
        self.assertNotIn("frm.doc.custom_warehouse_stock_snapshot = (rows || []).map(", quotation_js)
        for token in [
            "get_transaction_stock_snapshot",
            "company: frm.doc.custom_company",
            "schedulePricingSheetStockSnapshotRefresh",
            "custom_warehouse_stock_snapshot",
            "custom_shared_company_stock",
            "custom_current_company_stock_qty",
            "available_after_so_qty",
            "projected_available_qty",
            "item_totals",
            "selling_price_lists: JSON.stringify(sellingPriceLists)",
            'frappe.model.clear_table(frm.doc, fieldname)',
            'frappe.model.add_child(frm.doc, "Orderlift Transaction Warehouse Stock", fieldname)',
            'frappe.model.add_child(frm.doc, "Orderlift Shared Company Stock", fieldname)',
            "syncPricingSheetStockSnapshotTable",
            "syncSharedCompanyStockTable",
            "normalizeSharedCompanyStockRow",
            "orderlift.pricing-sheet.workspace-columns.v6",
        ]:
            self.assertIn(token, pricing_sheet_js)
        self.assertNotIn("frm.doc.custom_warehouse_stock_snapshot = (rows || []).map(", pricing_sheet_js)

    def test_sales_order_and_purchase_order_live_stock_overview_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        so_js = (APP_ROOT / "public" / "js" / "sales_order_stock_overview_20260817a.js").read_text()
        po_js = (APP_ROOT / "public" / "js" / "purchase_order_stock_overview_20260817a.js").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()

        self.assertIn('"public/js/sales_order_stock_overview_20260817a.js"', hooks)
        self.assertIn('"public/js/purchase_order_stock_overview_20260817a.js"', hooks)
        self.assertNotIn("populate_transaction_stock_snapshot", hooks)
        for token in (
            "refreshSalesOrderStockOverview",
            "get_transaction_stock_snapshot",
            "selling_price_lists: JSON.stringify(sellingPriceLists)",
            "buying_price_lists: JSON.stringify(buyingPriceLists)",
            "custom_warehouse_stock_snapshot",
            "custom_shared_company_stock",
            "frm.doc.__unsaved = 0",
            "Orderlift Shared Company Stock",
        ):
            self.assertIn(token, so_js)
        for token in (
            "refreshPurchaseOrderStockOverview",
            "get_transaction_stock_snapshot",
            "supplier: frm.doc.supplier",
            "buying_price_lists: JSON.stringify(buyingPriceLists)",
            "custom_warehouse_stock_snapshot",
            "custom_shared_company_stock",
            "frm.doc.__unsaved = 0",
            "Orderlift Shared Company Stock",
        ):
            self.assertIn(token, po_js)
        for token in (
            '"Purchase Order": [',
            '"fieldname": "custom_stock_snapshot_section"',
            '"fieldname": "custom_shared_company_stock"',
            '"label": "Supplier Company Stock"',
            '"label": "Stock (Company)"',
        ):
            self.assertIn(token, pricing_setup)

    def test_direct_quotation_discount_editing_is_wired(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        item_tools = (APP_ROOT / "orderlift_sales" / "utils" / "item_price_tools.py").read_text()
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        self.assertIn('async source_discount_percent(frm, cdt, cdn)', script)
        self.assertIn('async source_discount_amount(frm, cdt, cdn)', script)
        self.assertIn('async rate(frm, cdt, cdn)', script)
        self.assertIn("applyPricingDiscount", script)
        self.assertIn("canOverrideQuotationPricing", script)
        self.assertIn("async function applyResolvedRate", script)
        self.assertIn("await Promise.all(updates)", script)
        self.assertIn("applyDiscountAmount", script)
        self.assertIn("const amount = rate * qty", script)
        self.assertIn("const puTtc = rate * (1 + totalTaxRate / 100)", script)
        self.assertIn("const ptTtc = amount * (1 + totalTaxRate / 100)", script)
        self.assertIn("const appliedTaxes = ptTtc - amount", script)
        self.assertIn("const discount = rate >= listRate ? 0", script)
        self.assertIn("const discountAmount = rate >= listRate ? 0", script)
        self.assertIn('beginQuotationPriceMutation(frm)', script)
        self.assertIn('endQuotationPriceMutation(frm)', script)
        self.assertIn('Quantity changes totals without deriving PU HT from display text', script)
        self.assertNotIn('qty(frm, cdt, cdn) {\n            applyPricingDiscount', script)
        self.assertIn('changed = setItemFieldIfChanged(row, "amount", amount) || changed', script)
        self.assertIn('"Discount capped at {0}% for {1}."', script)
        self.assertIn('"Discount amount capped at {0} for {1}."', script)
        self.assertIn('"PU HT raised to minimum {0} for {1}."', script)
        self.assertIn("frappe.boot.orderlift_capabilities", script)
        self.assertIn('if (!isAdmin && discount > maxDiscount)', script)
        self.assertIn('if ("discount_percentage" in row) row.discount_percentage = discount', script)
        self.assertNotIn('frappe.model.set_value(row.doctype, row.name, "discount_percentage", discount)', script)
        self.assertIn('frappe.model.set_value(row.doctype, row.name, "rate", rate)', script)
        self.assertIn('frappe.model.set_value(row.doctype, row.name, "amount", amount)', script)
        self.assertNotIn("roundCurrency", script)
        self.assertNotIn("custom_pu_ttc(frm, cdt, cdn)", script)
        self.assertNotIn("source_gross_sell_rate(frm", script)
        self.assertNotIn("source_discounted_sell_rate(frm", script)
        self.assertIn('"fieldname": "source_max_discount_percent"', pricing_setup)
        self.assertIn('for fieldname in ("rate", "source_discount_percent", "source_discount_amount")', pricing_setup)
        self.assertIn("quotation_item_derived_fields", pricing_setup)
        self.assertIn('"custom_pu_ttc",', pricing_setup)
        self.assertIn("def ensure_canonical_pricing_precision", pricing_setup)
        self.assertIn('_upsert_property_setter(doctype, fieldname, "precision", "9", "Int")', pricing_setup)
        patches = (APP_ROOT / "patches.txt").read_text()
        precision_patch = (
            APP_ROOT / "patches" / "v1_0" / "widen_transaction_pricing_snapshot_precision.py"
        ).read_text()
        self.assertIn("orderlift.patches.v1_0.widen_transaction_pricing_snapshot_precision", patches)
        self.assertIn("DECIMAL(21,9) NOT NULL DEFAULT 0", precision_patch)
        self.assertIn('"source_discount_amount"', precision_patch)
        self.assertNotIn('"fieldname": "source_gross_sell_rate"', pricing_setup)
        self.assertNotIn('"fieldname": "source_discounted_sell_rate"', pricing_setup)
        self.assertIn('"source_pricing_sheet", "read_only", "0", "Check"', pricing_setup)
        self.assertIn('"price_list_rate"', pricing_setup)
        self.assertIn('"rate"', pricing_setup)
        self.assertIn('_upsert_property_setter("Quotation Item", fieldname, "read_only", "1", "Check")', pricing_setup)
        self.assertIn("INTERNAL_ITEM_PRICE_FIELDS", script)
        self.assertIn("applyQuotationItemPricingLayout", script)
        self.assertIn('grid.update_docfield_property(fieldname, "hidden", 1)', script)
        self.assertNotIn('grid.update_docfield_property(fieldname, "hidden", 0)', script)
        self.assertIn("QUOTATION_ITEM_GRID_COLUMNS", script)
        for token in [
            '{ fieldname: "source_price_list_sell_rate", columns: 1, sticky: 0 }',
            '{ fieldname: "rate", columns: 1, sticky: 0 }',
            '{ fieldname: "source_discount_percent", columns: 1, sticky: 0 }',
            '{ fieldname: "source_discount_amount", columns: 1, sticky: 0 }',
            '{ fieldname: "amount", columns: 1, sticky: 0 }',
            '{ fieldname: "custom_pu_ttc", columns: 1, sticky: 0 }',
            '{ fieldname: "custom_pt_ttc", columns: 1, sticky: 0 }',
            "enforceQuotationItemGridColumns",
            "configuredQuotationItemGridColumns",
            "grid.visible_columns = []",
            "df.in_list_view = 0",
            "df.columns = 0",
            "ensureQuotationItemsGridStyles",
            "applyQuotationPrecisionInputDisplay",
            "applyQuotationPrecisionGridRowDisplay",
            "displayQuotationInputNumber",
            "patchQuotationGridRowRender",
            "rawQuotationNumber",
            "displayQuotationNumber",
            "DISPLAY_NUMERIC_FIELDS",
            "scheduleItemTTCFieldsSync",
            "price_list_rate(frm)",
            "async rate(frm, cdt, cdn)",
            "recalculateQuotationTTC",
            "frappe.after_ajax(runLatest)",
            "frm.cscript.calculate_taxes_and_totals",
            'if (changed) frm.refresh_field("items")',
        ]:
            self.assertIn(token, script)
        self.assertLess(script.index('{ fieldname: "custom_pt_ttc"'), script.index('{ fieldname: "source_commission_rate"'))
        self.assertIn("return configured.concat(missingDefaults)", script)
        self.assertIn('grid.update_docfield_property("source_price_list_sell_rate", "label", __("PU List HT"))', script)
        self.assertIn('grid.update_docfield_property("rate", "label", __("PU HT"))', script)
        self.assertIn('grid.update_docfield_property("rate", "read_only", pricingEditable ? 0 : 1)', script)
        self.assertIn('grid.update_docfield_property("amount", "label", __("PT HT"))', script)
        self.assertIn('grid.update_docfield_property("source_discount_amount", "label", __("Remise PU HT"))', script)
        self.assertIn('grid.update_docfield_property("source_discount_percent", "label", __("Remise %"))', script)
        self.assertIn('function canViewQuotationMargins()', script)

        self.assertIn('applyQuotationMarginVisibility(grid)', script)
        self.assertIn('const visible = canViewQuotationMargins();', script)
        self.assertIn('grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1)', script)
        self.assertIn('grid.update_docfield_property("custom_pu_ttc", "read_only", 1)', script)
        self.assertIn('grid.update_docfield_property("amount", "read_only", 1)', script)
        self.assertIn('grid.update_docfield_property("custom_pt_ttc", "read_only", 1)', script)
        self.assertIn('["amount", "custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc"].includes(df.fieldname)', script)
        self.assertIn('grid.update_docfield_property("custom_pt_ttc", "precision", "9")', script)
        self.assertIn("disableQuotationItemRowForms", script)
        self.assertIn("patchQuotationItemsGridRefresh", script)
        self.assertIn("applyInlineOnlyQuotationItemsGrid", script)
        self.assertIn("patchQuotationItemGridRow", script)
        self.assertIn("grid.df.in_place_edit = isDraftQuotation(frm) ? 1 : 0", script)
        self.assertIn('wrapper.find(".btn-open-row").closest(".col").hide()', script)
        self.assertIn('gridRow.doc.doctype === "Quotation Item" && show !== false', script)
        self.assertIn("gridRow.toggle_editable_row(true)", script)
        self.assertIn('"max_discount_percent": _item_price_max_discount_percent(row)', item_tools)
        self.assertIn('row["commission_rate"] = commission_rate', item_tools)
        self.assertIn('def _current_agent_commission_rate', item_tools)
        self.assertIn('"source_max_discount_percent"', price_queries)
        self.assertIn('setChildValue(row, "source_max_discount_percent", maxDiscount)', price_queries)
        self.assertIn('setChildValue(row, "source_commission_rate", commissionRate)', price_queries)
        self.assertIn('setChildValue(row, "source_commission_amount", commissionAmount)', price_queries)
        self.assertIn('function commissionFor(actualUnitPrice, qty, discountPercent, maxDiscountPercent, commissionRate)', price_queries)
        self.assertIn('return actualRate * quantity * (unusedDiscount / 100) * (Number(commissionRate || 0) / 100);', price_queries)
        self.assertNotIn("upliftCommission", price_queries)
        self.assertNotIn("manualNetRate(row", price_queries)
        self.assertIn("isAdminOverride", price_queries)
        self.assertIn("beginQuotationPriceMutation(frm)", price_queries)
        self.assertIn("endQuotationPriceMutation(frm)", price_queries)
        self.assertIn('"source_commission_amount", commissionFor(rate, qty, discount, configuredMaxDiscount, row.source_commission_rate)', script)
        self.assertIn('return actualRate * quantity * (unusedDiscount / 100) * (Number(commissionRate || 0) / 100);', script)
        self.assertNotIn("upliftCommission", script)
        pricing_sheet = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()
        self.assertIn('item_data["source_max_discount_percent"] = flt(row.max_discount_percent_allowed)', pricing_sheet)
        self.assertIn('item_data["source_price_list_sell_rate"] = list_reference_rate', pricing_sheet)
        self.assertIn('item_data["source_discount_amount"] = flt(row.discount_amount_per_unit)', pricing_sheet)
        self.assertIn("def _build_grouped_max_discount_caps", pricing_sheet)
        self.assertIn('item["source_price_list_sell_rate"] = flt(group_total)', pricing_sheet)
        self.assertNotIn('item_data["source_gross_sell_rate"]', pricing_sheet)
        self.assertNotIn('item_data["source_discounted_sell_rate"]', pricing_sheet)

    def test_quotation_grid_is_stable_and_pricing_is_locked_after_submit(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()
        layout = script.split("function applyQuotationItemPricingLayout(frm)", 1)[1].split(
            "function enforceQuotationItemGridColumns(frm)", 1
        )[0]

        self.assertIn("function isDraftQuotation(frm)", script)
        self.assertIn("grid.__orderlift_pricing_layout_signature", layout)
        self.assertIn('grid.update_docfield_property("rate", "read_only", pricingEditable ? 0 : 1)', layout)
        self.assertIn(
            'grid.update_docfield_property("source_discount_percent", "read_only", pricingEditable ? 0 : 1)',
            layout,
        )
        self.assertIn(
            'grid.update_docfield_property("source_discount_amount", "read_only", pricingEditable ? 0 : 1)',
            layout,
        )
        self.assertNotIn("grid.refresh();", layout)
        self.assertIn("scheduleQuotationPrecisionFrame", script)
        self.assertNotIn("window.setTimeout(() => applyQuotationPrecisionInputDisplay(grid), 80)", script)
        self.assertNotIn("window.setTimeout(() => applyQuotationPrecisionInputDisplay(grid), 250)", script)
        self.assertNotIn("window.setTimeout(() => applyQuotationPrecisionGridRowDisplay(gridRow), 80)", script)
        self.assertGreaterEqual(script.count("if (!isDraftQuotation(frm)) return;"), 8)

    def test_selected_price_list_replaces_old_manual_price_snapshot(self):
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        self.assertIn("let netRate = 0;", price_queries)
        self.assertIn("netRate = rate * (1 - discount / 100);", price_queries)
        self.assertNotIn("manualNetRate(row", price_queries)

    def test_direct_quotation_discount_cap_is_enforced_on_server(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()
        price_scope = (APP_ROOT / "orderlift_sales" / "utils" / "price_list_scope.py").read_text()

        self.assertIn('"orderlift.orderlift_sales.quotation_hooks.validate_quotation_item_discount_caps"', hooks)
        self.assertIn("def validate_quotation_item_discount_caps", quotation_hooks)
        self.assertIn("def sync_quotation_item_price_input_fields", quotation_hooks)
        self.assertLess(
            quotation_hooks.index("sync_quotation_item_price_input_fields(doc)"),
            quotation_hooks.index("reprice_quotation_items_from_selected_price_lists(doc)"),
        )
        self.assertIn('for fieldname in ("rate", "source_discount_percent", "source_discount_amount")', quotation_hooks)
        self.assertIn('row.rate = current_rate', quotation_hooks)
        self.assertIn('row.amount = flt(current_rate * qty, row.precision("amount"))', quotation_hooks)
        self.assertIn('row.source_discount_amount = flt(', quotation_hooks)
        self.assertIn("can_override_quotation_pricing", quotation_hooks)
        self.assertIn('frappe.db.has_column("Quotation Item", "source_discount_percent")', quotation_hooks)
        self.assertIn('frappe.db.has_column("Quotation Item", "source_max_discount_percent")', quotation_hooks)
        self.assertIn("discount > max_discount", quotation_hooks)
        self.assertIn("Pricing Discount % cannot exceed", quotation_hooks)
        self.assertIn("def _validate_row_rate_against_policy_snapshot", quotation_hooks)
        self.assertIn("source_price_list_sell_rate", quotation_hooks)
        self.assertIn("below the pricing policy rate", quotation_hooks)
        self.assertNotIn("source_gross_sell_rate", quotation_hooks)
        self.assertNotIn("source_discounted_sell_rate", quotation_hooks)
        self.assertIn("QUOTATION_PRICE_OVERRIDE_ROLES", price_scope)
        self.assertIn("def can_override_quotation_pricing", price_scope)
        self.assertNotIn("if legacy_allowed:\n        return True", price_scope)
        self.assertIn("return role_capability_decision(", price_scope)

    def test_quotation_new_pricing_sheet_opens_builder(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertIn("addPricingSheetActionButtons", script)
        self.assertIn("openPricingSheetBuilderFromQuotation", script)
        self.assertIn('__("New Pricing Sheet") : __("Create Pricing Sheet from Quotation")', script)
        self.assertIn("create_pricing_sheet_from_quotation", script)
        self.assertIn("link_source_quotation", script)
        self.assertIn("source_quotation", script)
        self.assertIn('frappe.set_route("pricing-sheet-builder", sheet)', script)
        self.assertIn('frm.set_df_property("source_pricing_sheet", "only_select", 1)', script)
        self.assertIn('frm.set_df_property("source_pricing_sheet", "hidden", 1)', script)
        self.assertIn("renderPricingSheetSourcePanel", script)
        self.assertIn("Create Pricing Sheet from Quotation", script)
        self.assertIn("openLinkedPricingSheet", script)

    def test_opportunity_route_option_is_company_checked_before_apply(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertIn("async function applyOpportunityRouteOption", script)
        self.assertIn("function currentActiveCompany()", script)
        self.assertIn('frappe.db.get_value("Opportunity", opportunity, "company")', script)
        self.assertIn("opportunityCompany !== quotationCompany", script)
        self.assertIn("Cannot attach Opportunity", script)
        self.assertIn("delete options.opportunity", script)

    def test_quotation_supports_multiple_selling_price_lists(self):
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()
        quotation_hooks = (APP_ROOT / "orderlift_sales" / "quotation_hooks.py").read_text()
        price_guard = (APP_ROOT / "orderlift_sales" / "utils" / "price_list_usage_guard.py").read_text()
        item_tools = (APP_ROOT / "orderlift_sales" / "utils" / "item_price_tools.py").read_text()
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        self.assertIn('"fieldname": "selected_selling_price_lists"', pricing_setup)
        self.assertIn('"options": "Pricing Sheet Price List Selection"', pricing_setup)
        self.assertIn('"fieldname": "source_selling_price_list"', pricing_setup)
        self.assertIn('"Selling Price List Used"', pricing_setup)
        self.assertIn('"orderlift.orderlift_sales.quotation_hooks.sync_quotation_selling_price_lists"', hooks)
        self.assertIn('"orderlift.orderlift_sales.quotation_hooks.protect_source_pricing_sheet_link"', hooks)
        self.assertLess(
            hooks.index('"orderlift.company_scope.apply_company_scope"'),
            hooks.index('"orderlift.orderlift_sales.quotation_hooks.sync_quotation_selling_price_lists"'),
        )
        self.assertIn("def sync_quotation_selling_price_lists", quotation_hooks)
        self.assertIn("def _transaction_price_lists", price_guard)
        self.assertIn("def _quotation_price_lists", price_guard)
        self.assertIn('doc.selling_price_list = ""', price_guard)
        self.assertIn("def get_transaction_item_prices", item_tools)
        self.assertIn("def _resolve_transaction_item_prices", item_tools)
        self.assertIn("def _current_static_agent_selling_price_lists", item_tools)
        self.assertIn("def _valid_transaction_price_lists", item_tools)
        self.assertIn("custom_benchmark_is_fallback", item_tools)
        self.assertIn("validate_visible_price_list", quotation_hooks)
        self.assertIn("def _visible_selling_price_list", quotation_hooks)
        self.assertIn("def protect_source_pricing_sheet_link", quotation_hooks)
        self.assertIn("allow_source_pricing_sheet_update", quotation_hooks)
        self.assertIn("price_lists: JSON.stringify(priceLists)", price_queries)
        self.assertIn("quotationSelectedPriceLists", price_queries)
        self.assertIn("applyQuotationItemSourcePriceListQuery", price_queries)
        self.assertIn("source_selling_price_list", price_queries)
        self.assertIn("options.priceLists || quotationSelectedPriceLists", price_queries)
        self.assertIn("clearUnselectedQuotationPrimaryPriceList", price_queries)
        self.assertNotIn("syncQuotationSelectionRowsFromPrimary", price_queries)
        self.assertIn("resolveQuotationItemPrice", price_queries)
        self.assertIn("refreshQuotationItemPrices(frm);", price_queries)
        self.assertIn('if (Number(frm.doc.docstatus || 0) !== 0) return;', price_queries)
        self.assertIn('company: transactionCompany(frm)', price_queries)
        self.assertIn('function transactionCompany(frm)', price_queries)
        self.assertIn('filters.custom_company = company || "__no_company__"', price_queries)
        self.assertIn('if (!isDraftQuotation(frm)) return;', price_queries)
        self.assertIn('function isDraftQuotation(frm)', price_queries)
        self.assertIn('company=""', item_tools)
        self.assertIn('validate_visible_price_list(value, kind=kind, required=True, company=company)', item_tools)

    def test_quotation_price_list_refresh_reprices_net_rate(self):
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        for token in [
            "if (netRate + 0.000001 < floor) netRate = floor;",
            "if (!isAdminOverride && discount > maxDiscount) {",
            "netRate = rate * (1 - discount / 100);",
            'frappe.model.set_value(row.doctype, row.name, "rate", netRate)',
            'frappe.model.set_value(row.doctype, row.name, "amount", netRate * qty)',
            'setChildValue(row, "source_selling_price_list", payload.price_list || "")',
            'setChildValue(row, "source_price_list_sell_rate", rate)',
            'setChildValue(row, "source_discount_percent", discount)',
            'setChildValue(row, "source_discount_amount", Math.max(rate - netRate, 0))',
        ]:
            self.assertIn(token, price_queries)
        self.assertNotIn("manualNetRate(row", price_queries)
        self.assertNotIn("source_gross_sell_rate", price_queries)
        self.assertNotIn("source_discounted_sell_rate", price_queries)

    def test_printview_pdf_and_full_page_controls_are_hidden(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "orderlift_print_controls_20260703a.js").read_text()

        self.assertIn("orderlift_print_controls_20260703a.js", hooks)
        self.assertIn('frappe.get_route() : []) || []', script)
        self.assertIn("orderlift_print_controls_20260703a.js?v=20260718a", hooks)
        self.assertNotIn("PDF", script)
        for token in [
            "Full Page",
            "/printview",
            'route[0] === "print"',
            "hashchange",
            "MutationObserver",
            "orderlift-print-control-hidden",
            "display: none !important",
            'document.querySelectorAll("button, a, .btn")',
        ]:
            self.assertIn(token, script)

    def test_quotation_form_has_no_custom_print_or_pdf_shortcut_buttons(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertNotIn("download_pdf", script)
        self.assertNotIn("trigger_print", script)
        self.assertNotIn("ol-print-shortcut", script)

    def test_pricing_sheet_generation_reprices_and_stamps_source_list(self):
        pricing_sheet = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn("# Reprice with the current selected lists before copying snapshot values", pricing_sheet)
        self.assertIn("self.recalculate()", pricing_sheet)
        self.assertIn('item_data["source_selling_price_list"]', pricing_sheet)
        self.assertIn('getattr(row, "resolved_selling_price_list", "")', pricing_sheet)
        self.assertIn("list_reference_rate = flt(", pricing_sheet)
        self.assertIn('getattr(row, "static_list_price", 0)', pricing_sheet)
        self.assertIn('getattr(row, "projected_unit_price", 0)', pricing_sheet)
        self.assertIn('item_data["source_price_list_sell_rate"] = list_reference_rate', pricing_sheet)
        self.assertIn('item_data["source_discount_amount"] = flt(row.discount_amount_per_unit)', pricing_sheet)
        self.assertNotIn(
            'item_data["source_price_list_sell_rate"] = flt(row.sell_unit_price)',
            pricing_sheet,
            msg="The Quotation list reference must not be replaced by the discounted canonical sell rate.",
        )

    def test_orderlift_quotation_print_formats_include_ht_and_ttc_modes(self):
        html = (APP_ROOT / "print_formats" / "orderlift_quotation.html").read_text()
        sales_html = (APP_ROOT / "print_formats" / "orderlift_sales_document.html").read_text()
        purchase_html = (APP_ROOT / "print_formats" / "orderlift_purchase_document.html").read_text()
        updater = (APP_ROOT / "scripts" / "update_pf.py").read_text()
        helpers = (APP_ROOT / "utils" / "jinja_helpers.py").read_text()
        tax_inclusive = (APP_ROOT / "orderlift_sales" / "utils" / "tax_inclusive.py").read_text()

        for token in [
            "Orderlift Quotation",
            "name_prefix",
            "orderlift_price_display_mode",
            "orderlift_show_images",
            "orderlift_show_cover",
            "_MODES",
            "_DOC_CONFIG",
            "_COMPANIES",
            "template_suffix",
            "template_key",
            "_TEMPLATE_MAP",
            "_resolve_template_file",
            "Sans Images",
            "_handle_legacy",
            "custom_company",
            "_tr",
        ]:
            self.assertIn(token, updater)
        for token in [
            '("PU HT Without Details", "HT", False, True)',
            '("PU TTC Without Details", "TTC", False, True)',
            '("Prix Unitaire Without Details", "PRIX_UNITAIRE", False, True)',
        ]:
            self.assertIn(token, updater)
        for token in [
            "ol_print_ttc",
            "ol_simple_ttc",
            "PU HT",
            "PU TTC",
            "PT HT",
            "PT TTC",
            "Total",
            "TOTAL TTC",
            "Total HT",
            "get_quotation_ttc_print_context(doc)",
        ]:
            self.assertIn(token, html)
        for filename in (
            "orderlift_quotation.html",
            "orderlift_quotation_tr.html",
            "orderlift_sales_document.html",
            "orderlift_sales_document_tr.html",
            "orderlift_purchase_document.html",
            "orderlift_purchase_document_tr.html",
        ):
            template = (APP_ROOT / "print_formats" / filename).read_text()
            self.assertIn(
                '{{ _("PU") if ol_simple_ttc else (_("PU TTC") if ol_print_ttc else _("PU HT")) }}',
                template,
            )
            self.assertIn(
                '{{ _("PT") if ol_simple_ttc else (_("PT TTC") if ol_print_ttc else _("PT HT")) }}',
                template,
            )
            self.assertIn("item_ttc.get('unit_ht')", template)
            self.assertIn("item_ttc.get('unit')", template)
            self.assertIn("display_unit = unit_ttc if ol_print_ttc else unit_ht", template)
            self.assertNotIn('{{ _("Prix U HT") }}', template)
            self.assertNotIn('{{ _("Prix U TTC") }}', template)
        for token in [
            "get_ttc_print_context(doc)",
            "get_doc_print_title(doc.doctype)",
            "orderlift_show_images",
            "ol_show_images_bool",
        ]:
            self.assertIn(token, sales_html)
            self.assertIn(token, purchase_html)
        for token in [
            "def get_quotation_ttc_print_context",
            "def get_ttc_print_context",
            "def get_doc_print_title",
            '"qty": commercial_qty',
            '"rate": amount_ht / commercial_qty',
            '"custom_pu_ttc": amount_ttc / commercial_qty',
            '"custom_pt_ttc": amount_ttc',
            "quote_item_inclusive_totals(doc)",
            "rows_by_name",
            "total_ttc",
            "_DOC_PRINT_TITLES",
            "BON DE COMMANDE",
            "FACTURE DE VENTE",
            "RECEPTION DE MARCHANDISE",
            "DEVIS FOURNISSEUR",
        ]:
            self.assertIn(token, helpers)
        for token in [
            "sync_sales_order_tax_inclusive_fields",
            "sync_delivery_note_tax_inclusive_fields",
            "sync_sales_invoice_tax_inclusive_fields",
            "sync_purchase_order_tax_inclusive_fields",
            "sync_purchase_invoice_tax_inclusive_fields",
            "sync_purchase_receipt_tax_inclusive_fields",
            "sync_supplier_quotation_tax_inclusive_fields",
            "template_tax_rate",
            "_fallback_template_tax_rate(doc)",
        ]:
            self.assertIn(token, tax_inclusive)

    def test_customer_ice_tax_id_is_configured_and_printed_below_customer_name(self):
        setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        quotation_html = (APP_ROOT / "print_formats" / "orderlift_quotation.html").read_text()
        sales_html = (APP_ROOT / "print_formats" / "orderlift_sales_document.html").read_text()
        quotation_tr_html = (APP_ROOT / "print_formats" / "orderlift_quotation_tr.html").read_text()
        sales_tr_html = (APP_ROOT / "print_formats" / "orderlift_sales_document_tr.html").read_text()

        self.assertIn('"fieldname": "custom_customer_tax_id"', setup)
        self.assertIn('"label": "ICE / Tax ID"', setup)
        self.assertIn("ensure_tax_id_labels()", setup)

        for html, address_token in (
            (quotation_html, "party.address_lines"),
            (sales_html, "party.address_lines"),
            (quotation_tr_html, "doc.address_display"),
            (sales_tr_html, "doc.address_display"),
        ):
            customer_name_position = html.index('class="ol-info-client-name"')
            tax_id_position = html.index('{{ _("ICE / Tax ID") }}', customer_name_position)
            address_position = html.index(address_token, customer_name_position)
            self.assertLess(customer_name_position, tax_id_position)
            self.assertLess(tax_id_position, address_position)

    def test_draft_quotation_refreshes_party_ice_from_party_master(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        for token in [
            "syncCustomerTaxId(frm)",
            "partyTaxField(partyType)",
            'if (partyType === "Customer") return "tax_id";',
            'if (partyType === "Prospect" || partyType === "Lead") return "custom_tax_id";',
            "frappe.db.get_value(partyType, partyName, taxField)",
            'frm.set_value("custom_customer_tax_id", taxId)',
            "if (!isDraftQuotation(frm)) return;",
            "party_name(frm)",
            "quotation_to(frm)",
        ]:
            self.assertIn(token, script)

    def test_bulk_quantity_is_doctype_scoped_without_global_interval(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260802a.js").read_text()

        self.assertNotIn("quotation_bulk_quantity_20260602a.js", hooks)
        for token in [
            "data-orderlift-bulk-quantity",
            ".grid-add-multiple-rows",
            "__orderlift_bulk_quantity_button_added",
            "__orderlift_bulk_quantity_buttons_added",
            "frappe.model.set_value(row.doctype, row.name, \"qty\", qty)",
        ]:
            self.assertIn(token, script)
        self.assertNotIn("setInterval(attachBulkQuantityButton", script)

    def test_ttc_inclusive_hooks_are_wired_for_all_doctypes(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        for path in [
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_sales_order_tax_inclusive_fields",
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_delivery_note_tax_inclusive_fields",
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_sales_invoice_tax_inclusive_fields",
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_purchase_order_tax_inclusive_fields",
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_purchase_invoice_tax_inclusive_fields",
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_purchase_receipt_tax_inclusive_fields",
            "orderlift.orderlift_sales.utils.tax_inclusive.sync_supplier_quotation_tax_inclusive_fields",
        ]:
            self.assertIn(path, hooks, msg=f"Missing TTC sync hook for {path}")

    def test_generic_ttc_field_sync_js_covers_all_doctypes(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        js = (APP_ROOT / "public" / "js" / "generic_ttc_field_sync_20260805b.js").read_text()

        for doctype in [
            "Sales Order",
            "Delivery Note",
            "Sales Invoice",
            "Purchase Order",
            "Purchase Invoice",
            "Purchase Receipt",
            "Supplier Quotation",
        ]:
            self.assertIn(f'frappe.ui.form.on("{doctype}"', js, msg=f"Missing form handler for {doctype}")
            item_doctype = f"{doctype} Item"
            self.assertIn(f'frappe.ui.form.on("{item_doctype}"', js, msg=f"Missing item form handler for {item_doctype}")
        for token in [
            "syncDocTTCFields",
            "function docTotalTaxRate",
            "applySalesPrecisionDisplay",
            "custom_pu_ttc",
            "custom_applied_taxes",
            "custom_pt_ttc",
        ]:
            self.assertIn(token, js)
        self.assertNotIn("roundTTC", js)
        self.assertNotIn("< 0.005", js)
        self.assertIn("< 1e-9", js)
        self.assertIn("generic_ttc_field_sync_20260805b.js", hooks)
        self.assertNotIn("generic_ttc_field_sync_20260729b.js", hooks)
        self.assertNotIn("generic_ttc_field_sync_20260629a.js", hooks)

    def test_generic_ttc_refresh_does_not_dirty_saved_drafts(self):
        js = (APP_ROOT / "public" / "js" / "generic_ttc_field_sync_20260805b.js").read_text()

        purchase_order_refresh = js.split('frappe.ui.form.on("Purchase Order", {', 1)[1].split('frappe.ui.form.on("Purchase Order Item"', 1)[0]
        self.assertIn("if (frm.is_new())", purchase_order_refresh)
        self.assertIn("syncDocTTCFields(frm)", purchase_order_refresh)
        for doctype, item_doctype in (
            ("Sales Invoice", "Sales Invoice Item"),
            ("Purchase Invoice", "Purchase Invoice Item"),
            ("Purchase Receipt", "Purchase Receipt Item"),
            ("Delivery Note", "Delivery Note Item"),
        ):
            refresh_block = js.split(f'frappe.ui.form.on("{doctype}", {{', 1)[1].split(
                f'frappe.ui.form.on("{item_doctype}"', 1
            )[0]
            self.assertIn("if (frm.is_new())", refresh_block)
            self.assertIn("syncDocTTCFields(frm)", refresh_block)

    def test_purchase_order_packaging_snapshot_does_not_dirty_saved_drafts_on_refresh(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        js = (APP_ROOT / "public" / "js" / "purchase_order_pricing_alerts_20260813a.js").read_text()

        self.assertIn("purchase_order_pricing_alerts_20260813a.js", hooks)
        self.assertNotIn("purchase_order_pricing_alerts_20260728a.js", hooks)
        self.assertNotIn("purchase_order_pricing_alerts_20260729a.js", hooks)
        self.assertIn("function canMutatePackagingSnapshot(frm)", js)
        self.assertGreaterEqual(
            js.count("canMutatePackagingSnapshot(frm)"),
            6,
            msg="Refresh, scheduling, async resolution, and apply paths must all reject submitted POs.",
        )
        self.assertIn("Number(frm?.doc?.docstatus || 0) === 0", js)
        self.assertIn("refreshAllPackagingRows(frm, { immediate: true, onlyNewDraft: true })", js)
        self.assertIn("options.onlyNewDraft && !isNew", js)
        self.assertIn("Math.abs(Number(current || 0) - Number(value || 0)) <= 1e-9", js)
        self.assertNotIn("flt(resolution.get(\"volume_m3\" or 0), 3)", (APP_ROOT / "logistics" / "utils" / "purchase_order_packaging.py").read_text())


if __name__ == "__main__":
    unittest.main()
