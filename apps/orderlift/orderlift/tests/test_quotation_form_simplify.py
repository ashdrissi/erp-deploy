from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestQuotationFormSimplify(unittest.TestCase):
    def test_draft_quotation_has_deterministic_ttc_recalculation_action(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

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
        self.assertIn('("source_margin_percent", "Margin %")', visible_block)
        self.assertIn('("source_margin_basis", "Margin Basis")', visible_block)

    def test_quotation_item_grid_preserves_user_configured_columns(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

        for token in [
            "configuredQuotationItemGridColumns",
            'frappe.get_user_settings(frm.doctype, "GridView")',
            "savedColumns",
            'fieldname === "source_margin_percent"',
        ]:
            self.assertIn(token, script)
        self.assertNotIn("gridViewSettings.GridView[grid.doctype] =", script)

    def test_quotation_item_grid_keeps_last_data_field_full_width(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

        for token in [
            "--orderlift-grid-cell-width",
            ".grid-static-col[data-fieldname]:last-child",
            "position: static",
            "min-width: max-content",
        ]:
            self.assertIn(token, script)
        self.assertNotIn('canViewQuotationMargins() ? "2100px" : "1820px"', script)

    def test_quotation_item_grid_uses_one_aligned_horizontal_scroll_layout(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

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
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

        self.assertIn('"Quotation": "public/js/quotation_form_simplify_20260707f.js', hooks)
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
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

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
            "flex: 0 0 250px !important",
            "max-width: 250px !important",
            "min-width: 250px",
        ]:
            self.assertIn(token, script)
        self.assertNotIn("QUOTATION_LIST_FIELDS", script)
        self.assertNotIn("max-width: 220px", script)

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
        script = (APP_ROOT / "public" / "js" / "crm_classification.js").read_text()
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()

        self.assertIn("syncTransactionPartyDefaults", script)
        self.assertIn('method: "orderlift.orderlift_crm.api.pipeline.get_party_defaults"', script)
        self.assertIn("customer_address", script)
        self.assertIn("contact_person", script)
        self.assertIn("shipping_address_name", script)
        self.assertIn('"address_name": address_name or ""', pipeline)
        self.assertIn('"contact_name": contact.get("name") or ""', pipeline)
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
        quotation_script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

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
        quotation_js = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()
        pricing_sheet_js = (APP_ROOT / "public" / "js" / "pricing_sheet_form_20260501_110.js").read_text()
        item_tools = (APP_ROOT / "orderlift_sales" / "utils" / "item_price_tools.py").read_text()
        stock_table = (APP_ROOT / "orderlift_sales" / "doctype" / "orderlift_transaction_warehouse_stock" / "orderlift_transaction_warehouse_stock.json").read_text()

        for token in [
            '"fieldname": "custom_stock_snapshot_section"',
            '"fieldname": "custom_warehouse_stock_snapshot"',
            '"options": "Orderlift Transaction Warehouse Stock"',
            '"fieldname": "custom_current_company_stock_qty"',
        ]:
            self.assertIn(token, pricing_setup)
        self.assertIn("def get_transaction_stock_snapshot", item_tools)
        self.assertIn("stock_warehouse_condition(\"w.name\", params)", item_tools)
        self.assertIn("Orderlift Transaction Warehouse Stock", stock_table)
        for token in [
            "get_transaction_stock_snapshot",
            "company: frm.doc.company",
            "scheduleQuotationStockSnapshotRefresh",
            "custom_warehouse_stock_snapshot",
            "custom_current_company_stock_qty",
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
            "custom_current_company_stock_qty",
            'frappe.model.clear_table(frm.doc, fieldname)',
            'frappe.model.add_child(frm.doc, "Orderlift Transaction Warehouse Stock", fieldname)',
            "syncPricingSheetStockSnapshotTable",
            "orderlift.pricing-sheet.workspace-columns.v6",
        ]:
            self.assertIn(token, pricing_sheet_js)
        self.assertNotIn("frm.doc.custom_warehouse_stock_snapshot = (rows || []).map(", pricing_sheet_js)

    def test_direct_quotation_discount_editing_is_wired(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()
        pricing_setup = (APP_ROOT / "sales" / "utils" / "pricing_setup.py").read_text()
        item_tools = (APP_ROOT / "orderlift_sales" / "utils" / "item_price_tools.py").read_text()
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        self.assertIn('source_discount_percent(frm, cdt, cdn)', script)
        self.assertIn("await frm.save()", script)
        self.assertIn('title: __("Save Quotation First")', script)
        self.assertIn("applyPricingDiscount", script)
        self.assertIn("canOverrideQuotationPricing", script)
        self.assertIn("applyNetPriceFromOverride", script)
        self.assertIn("source_discounted_sell_rate(frm, cdt, cdn)", script)
        self.assertIn("source_discount_amount(frm, cdt, cdn)", script)
        self.assertIn("custom_pu_ttc(frm, cdt, cdn)", script)
        self.assertIn("applyDiscountAmount", script)
        self.assertIn("applyTTCPriceFromOverride", script)
        self.assertIn("applyResolvedNetRate", script)
        self.assertIn("netRateFromTTC", script)
        self.assertIn("MANUAL_PU_TTC_BY_ROW", script)
        self.assertIn("rememberManualPuTtc", script)
        self.assertIn("manualPuTtc", script)
        self.assertIn('var amount = roundCurrency(rate * qty)', script)
        self.assertIn('var ptTtc = roundCurrency(puTtc * qty)', script)
        self.assertIn('var taxAmount = roundCurrency(ptTtc - amount)', script)
        self.assertIn('beginQuotationPriceMutation(frm)', script)
        self.assertIn('endQuotationPriceMutation(frm)', script)
        self.assertIn('Quantity only changes totals', script)
        self.assertNotIn('qty(frm, cdt, cdn) {\n            applyPricingDiscount', script)
        self.assertIn('changed = setItemFieldIfChanged(row, "amount", amount) || changed', script)
        self.assertIn('"Discount capped at {0}% for {1}."', script)
        self.assertIn('"Discount amount capped at {0} for {1}."', script)
        self.assertIn('"Net price raised to minimum {0} for {1}."', script)
        self.assertIn("PRICE_OVERRIDE_ROLES", script)
        self.assertIn('if (!isAdmin && discount > maxDiscount)', script)
        self.assertIn('if ("discount_percentage" in row) row.discount_percentage = discount', script)
        self.assertNotIn('frappe.model.set_value(row.doctype, row.name, "discount_percentage", discount)', script)
        self.assertIn('frappe.model.set_value(row.doctype, row.name, "rate", netRate)', script)
        self.assertIn('"fieldname": "source_max_discount_percent"', pricing_setup)
        self.assertIn('_upsert_property_setter("Quotation Item", "source_discount_percent", "read_only", "0", "Check")', pricing_setup)
        self.assertIn('for fieldname in ("source_discount_amount", "custom_pu_ttc")', pricing_setup)
        self.assertIn('_upsert_property_setter("Quotation Item", "source_gross_sell_rate", "read_only", "0", "Check")', pricing_setup)
        self.assertIn('_upsert_property_setter("Quotation Item", "source_discounted_sell_rate", "read_only", "1", "Check")', pricing_setup)
        self.assertIn("quotation_item_currency_precision_fields", pricing_setup)
        self.assertIn('_upsert_property_setter("Quotation Item", fieldname, "precision", "2", "Data")', pricing_setup)
        self.assertIn('_upsert_property_setter("Quotation Item", "amount", "label", "PT HT net", "Data")', pricing_setup)
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
            '{ fieldname: "source_gross_sell_rate", columns: 1, sticky: 0 }',
            '{ fieldname: "source_discount_percent", columns: 1, sticky: 0 }',
            '{ fieldname: "source_discount_amount", columns: 1, sticky: 0 }',
            '{ fieldname: "source_discounted_sell_rate", columns: 1, sticky: 0 }',
            '{ fieldname: "amount", columns: 1, sticky: 0 }',
            '{ fieldname: "custom_pu_ttc", columns: 1, sticky: 0 }',
            '{ fieldname: "custom_pt_ttc", columns: 1, sticky: 0 }',
            "enforceQuotationItemGridColumns",
            "configuredQuotationItemGridColumns",
            "grid.visible_columns = []",
            "df.in_list_view = 0",
            "df.columns = 0",
            "ensureQuotationItemsGridStyles",
            "scheduleItemTTCFieldsSync",
            "price_list_rate(frm)",
            "source_gross_sell_rate(frm)",
            "recalculateQuotationTTC",
            "frappe.after_ajax(runLatest)",
            "frm.cscript.calculate_taxes_and_totals",
            'if (changed) frm.refresh_field("items")',
        ]:
            self.assertIn(token, script)
        self.assertIn('grid.update_docfield_property("source_price_list_sell_rate", "label", __("PU List HT"))', script)
        self.assertIn('grid.update_docfield_property("source_gross_sell_rate", "label", __("PU HT"))', script)
        self.assertIn('grid.update_docfield_property("source_gross_sell_rate", "read_only", 0)', script)
        self.assertIn('grid.update_docfield_property("source_discounted_sell_rate", "label", __("PU HT net"))', script)
        self.assertIn('grid.update_docfield_property("source_discounted_sell_rate", "read_only", 1)', script)
        self.assertIn('grid.update_docfield_property("amount", "label", __("PT HT net"))', script)
        self.assertIn('grid.update_docfield_property("source_discount_amount", "label", __("Remise HT"))', script)
        self.assertIn('grid.update_docfield_property("source_discount_percent", "label", __("Remise %"))', script)
        self.assertIn('function canViewQuotationMargins()', script)

        self.assertIn('applyQuotationMarginVisibility(grid)', script)
        self.assertIn('const visible = canViewQuotationMargins();', script)
        self.assertIn('grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1)', script)
        self.assertIn('function applyGrossPriceOverride(frm, row)', script)
        self.assertIn('grid.update_docfield_property("custom_pu_ttc", "read_only", 0)', script)
        self.assertIn('grid.update_docfield_property("amount", "read_only", 1)', script)
        self.assertIn('grid.update_docfield_property("custom_pt_ttc", "read_only", 1)', script)
        self.assertIn('["source_discounted_sell_rate", "amount", "custom_pt_ttc"].includes(df.fieldname)', script)
        self.assertIn('grid.update_docfield_property("custom_pt_ttc", "precision", "2")', script)
        self.assertIn("netRate = roundCurrency(netRate)", script)
        self.assertIn("disableQuotationItemRowForms", script)
        self.assertIn("patchQuotationItemsGridRefresh", script)
        self.assertIn("applyInlineOnlyQuotationItemsGrid", script)
        self.assertIn("patchQuotationItemGridRow", script)
        self.assertIn("grid.df.in_place_edit = 1", script)
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
        self.assertIn('function commissionFor(priceListRate, qty, discountPercent, maxDiscountPercent, commissionRate, actualUnitPrice)', price_queries)
        self.assertIn('const upliftCommission = Math.max(actualRate - listRate, 0) * quantity * 0.2;', price_queries)
        self.assertNotIn("manualNetRate(row", price_queries)
        self.assertIn("isAdminOverride", price_queries)
        self.assertIn("beginQuotationPriceMutation(frm)", price_queries)
        self.assertIn("endQuotationPriceMutation(frm)", price_queries)
        self.assertIn('"source_commission_amount", commissionFor(gross, qty, discount, configuredMaxDiscount, row.source_commission_rate, netRate)', script)
        self.assertIn('const upliftCommission = Math.max(actualRate - listRate, 0) * quantity * 0.2;', script)
        pricing_sheet = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()
        self.assertIn('item_data["source_max_discount_percent"] = flt(row.max_discount_percent_allowed)', pricing_sheet)
        self.assertIn('item_data["source_price_list_sell_rate"] = flt(', pricing_sheet)
        self.assertIn("def _build_grouped_max_discount_caps", pricing_sheet)
        self.assertIn('item["source_price_list_sell_rate"] = flt(group_total)', pricing_sheet)
        self.assertIn('item["source_gross_sell_rate"] = flt(group_total)', pricing_sheet)
        self.assertIn('item["source_discounted_sell_rate"] = flt(group_total)', pricing_sheet)

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
        self.assertIn('row.source_discounted_sell_rate = flt(current_rate, row.precision("source_discounted_sell_rate"))', quotation_hooks)
        self.assertIn("can_override_quotation_pricing", quotation_hooks)
        self.assertIn('frappe.db.has_column("Quotation Item", "source_discount_percent")', quotation_hooks)
        self.assertIn('frappe.db.has_column("Quotation Item", "source_max_discount_percent")', quotation_hooks)
        self.assertIn("discount > max_discount", quotation_hooks)
        self.assertIn("Pricing Discount % cannot exceed", quotation_hooks)
        self.assertIn("def _validate_row_rate_against_policy_snapshot", quotation_hooks)
        self.assertIn("source_gross_sell_rate", quotation_hooks)
        self.assertIn("below the pricing policy net rate", quotation_hooks)
        self.assertIn("QUOTATION_PRICE_OVERRIDE_ROLES", price_scope)
        self.assertIn("def can_override_quotation_pricing", price_scope)
        self.assertNotIn("if legacy_allowed:\n        return True", price_scope)
        self.assertIn("return role_capability_decision(", price_scope)

    def test_quotation_new_pricing_sheet_opens_builder(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

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

    def test_quotation_price_list_refresh_reprices_net_rate(self):
        price_queries = (APP_ROOT / "public" / "js" / "price_list_type_queries_20260703c.js").read_text()

        for token in [
            "if (netRate + 0.000001 < floor) netRate = floor;",
            "if (!isAdminOverride && discount > maxDiscount) {",
            "netRate = rate * (1 - discount / 100);",
            'frappe.model.set_value(row.doctype, row.name, "rate", netRate)',
            'setChildValue(row, "source_discounted_sell_rate", netRate)',
            'setChildValue(row, "source_selling_price_list", payload.price_list || "")',
            'setChildValue(row, "source_price_list_sell_rate", rate)',
        ]:
            self.assertIn(token, price_queries)
        self.assertNotIn("manualNetRate(row", price_queries)

    def test_printview_pdf_and_full_page_controls_are_hidden(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "orderlift_print_controls_20260703a.js").read_text()

        self.assertIn("orderlift_print_controls_20260703a.js", hooks)
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
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

        self.assertNotIn("download_pdf", script)
        self.assertNotIn("trigger_print", script)
        self.assertNotIn("ol-print-shortcut", script)

    def test_pricing_sheet_generation_reprices_and_stamps_source_list(self):
        pricing_sheet = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()

        self.assertIn("# Reprice with the current selected lists before copying snapshot values", pricing_sheet)
        self.assertIn("self.recalculate()", pricing_sheet)
        self.assertIn('item_data["source_selling_price_list"]', pricing_sheet)
        self.assertIn('getattr(row, "resolved_selling_price_list", "")', pricing_sheet)

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
            "ol_print_ttc",
            "ol_simple_ttc",
            "Prix Unitaire",
            "Prix Unit. TTC",
            "Total",
            "TOTAL TTC",
            "Total HT",
            "get_quotation_ttc_print_context(doc)",
        ]:
            self.assertIn(token, html)
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

        for html in (quotation_html, sales_html, quotation_tr_html, sales_tr_html):
            customer_name_position = html.index('class="ol-info-client-name"')
            tax_id_position = html.index('{{ _("ICE / Tax ID") }}', customer_name_position)
            address_position = html.index("doc.address_display", customer_name_position)
            self.assertLess(customer_name_position, tax_id_position)
            self.assertLess(tax_id_position, address_position)

    def test_draft_quotation_refreshes_customer_ice_from_customer_master(self):
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

        for token in [
            "syncCustomerTaxId(frm)",
            'frappe.db.get_value("Customer", customer, "tax_id")',
            'frm.set_value("custom_customer_tax_id", taxId)',
            "Number(frm.doc.docstatus || 0) !== 0",
            "party_name(frm)",
            "quotation_to(frm)",
        ]:
            self.assertIn(token, script)

    def test_bulk_quantity_is_doctype_scoped_without_global_interval(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        script = (APP_ROOT / "public" / "js" / "quotation_form_simplify_20260707f.js").read_text()

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
        js = (APP_ROOT / "public" / "js" / "generic_ttc_field_sync_20260629a.js").read_text()

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
            "custom_pu_ttc",
            "custom_applied_taxes",
            "custom_pt_ttc",
        ]:
            self.assertIn(token, js)


if __name__ == "__main__":
    unittest.main()
