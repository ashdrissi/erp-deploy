(function () {
    const STOCK_SNAPSHOT_METHOD = "orderlift.orderlift_sales.utils.item_price_tools.get_transaction_stock_snapshot";
    const OTHER_CHARGE_ITEM_METHOD = "orderlift.orderlift_sales.quotation_hooks.get_other_charge_item";
    const OTHER_CHARGE_TEMPLATE_METHOD = "orderlift.orderlift_sales.quotation_hooks.get_other_charge_template";
    const MANUAL_CHARGE_ITEM_CODES = new Set(["OTHER-CHARGES", "TRANSPORTATION-CHARGE"]);

    const HIDDEN_FIELDS = [
        "additional_discount_section",
        "apply_discount_on",
        "coupon_code",
        "additional_discount_percentage",
        "discount_amount",
        "base_discount_amount",
        "referral_sales_partner",
    ];

    const TAX_SUMMARY_FIELDS = [
        "taxes_section",
        "tax_category",
        "taxes_and_charges",
        "total_taxes_and_charges",
        "base_total_taxes_and_charges",
    ];

    const TAX_DETAIL_FIELDS = [
        "shipping_rule",
        "incoterm",
        "named_place",
        "taxes",
        "taxes_and_charges_calculation",
        "other_charges_calculation",
        "tax_breakup",
    ];

    const INTERNAL_ITEM_PRICE_FIELDS = ["price_list_rate"];
    const LEGACY_ITEM_PRICE_FIELDS = new Set(["source_gross_sell_rate", "source_discounted_sell_rate"]);
    const DISPLAY_CURRENCY_FIELDS = new Set([
        "source_price_list_sell_rate",
        "rate",
        "source_discount_amount",
        "amount",
        "source_commission_amount",
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
        "source_base_buy_rate",
        "source_landed_cost",
    ]);
    const DISPLAY_PERCENT_FIELDS = new Set([
        "source_max_discount_percent",
        "source_discount_percent",
        "source_commission_rate",
        "source_target_margin_percent",
        "source_margin_percent",
    ]);
    const DISPLAY_FLOAT_FIELDS = new Set([
        "qty",
        "custom_current_company_stock_qty",
    ]);
    const DISPLAY_NUMERIC_FIELDS = new Set([
        ...DISPLAY_CURRENCY_FIELDS,
        ...DISPLAY_PERCENT_FIELDS,
        ...DISPLAY_FLOAT_FIELDS,
    ]);

    const QUOTATION_ITEM_GRID_COLUMNS = [
        { fieldname: "item_code", columns: 2, sticky: 0 },
        { fieldname: "custom_presentation_role", columns: 2, sticky: 0 },
        { fieldname: "qty", columns: 1, sticky: 0 },
        { fieldname: "source_price_list_sell_rate", columns: 1, sticky: 0 },
        { fieldname: "rate", columns: 1, sticky: 0 },
        { fieldname: "source_max_discount_percent", columns: 1, sticky: 0 },
        { fieldname: "source_discount_percent", columns: 1, sticky: 0 },
        { fieldname: "source_discount_amount", columns: 1, sticky: 0 },
        { fieldname: "amount", columns: 1, sticky: 0 },
        { fieldname: "custom_pu_ttc", columns: 1, sticky: 0 },
        { fieldname: "custom_pt_ttc", columns: 1, sticky: 0 },
        { fieldname: "source_commission_rate", columns: 1, sticky: 0 },
        { fieldname: "source_commission_amount", columns: 1, sticky: 0 },
    ];

    function canOverrideQuotationPricing() {
        const capabilities = frappe.boot && frappe.boot.orderlift_capabilities;
        return Boolean(capabilities && capabilities.quotation_override);
    }

    function canViewQuotationMargins() {
        const capabilities = frappe.boot && frappe.boot.orderlift_capabilities;
        return Boolean(capabilities && capabilities.privileged_pricing);
    }

    function isDraftQuotation(frm) {
        return Boolean(frm && frm.doc && Number(frm.doc.docstatus || 0) === 0);
    }

    async function syncCustomerTaxId(frm) {
        if (!frm || !frm.doc || !frm.fields_dict || !frm.fields_dict.custom_customer_tax_id) return;
        if (!isDraftQuotation(frm)) return;

        const partyType = String(frm.doc.quotation_to || "").trim();
        const partyName = String(frm.doc.party_name || "").trim();
        const taxField = partyTaxField(partyType);
        let taxId = "";
        if (taxField && partyName) {
            try {
                const response = await frappe.db.get_value(partyType, partyName, taxField);
                if (
                    String(frm.doc.quotation_to || "").trim() !== partyType
                    || String(frm.doc.party_name || "").trim() !== partyName
                ) return;
                taxId = String((response.message || {})[taxField] || "").trim();
            } catch (error) {
                console.warn("Orderlift customer ICE / Tax ID refresh failed", error);
                return;
            }
        }

        if (String(frm.doc.custom_customer_tax_id || "").trim() === taxId) return;
        await frm.set_value("custom_customer_tax_id", taxId);
    }

    function partyTaxField(partyType) {
        if (partyType === "Customer") return "tax_id";
        if (partyType === "Prospect" || partyType === "Lead") return "custom_tax_id";
        return "";
    }

    frappe.ui.form.on("Quotation", {
        setup(frm) {
            showOpportunityField(frm);
            hideNativeSourcePricingSheetField(frm);
            renderPricingSheetSourcePanel(frm);
            showTaxFields(frm);
            hideNativeDiscountAndTaxFields(frm);
            applyQuotationItemPricingLayout(frm);
            disableQuotationItemRowForms(frm);
            setupOpportunityQuery(frm);
            setupTaxTemplateQuery(frm);
        },
        onload(frm) {
            applyOpportunityRouteOption(frm);
        },
        onload_post_render(frm) {
            showOpportunityField(frm);
            hideNativeSourcePricingSheetField(frm);
            renderPricingSheetSourcePanel(frm);
            showTaxFields(frm);
            applyQuotationItemPricingLayout(frm);
            disableQuotationItemRowForms(frm);
            scheduleQuotationStockSnapshotRefresh(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        refresh(frm) {
            showOpportunityField(frm);
            hideNativeSourcePricingSheetField(frm);
            renderPricingSheetSourcePanel(frm);
            showTaxFields(frm);
            applyOpportunityRouteOption(frm);
            hideNativeDiscountAndTaxFields(frm);
            applyQuotationItemPricingLayout(frm);
            disableQuotationItemRowForms(frm);
            setupOpportunityQuery(frm);
            setupTaxTemplateQuery(frm);
            addPricingSheetActionButtons(frm);
            addBulkQuantityButton(frm);
            addBulkQuantityGridButton(frm);
            addBulkDiscountButton(frm);
            addBulkDiscountGridButton(frm);
            addOtherChargeButton(frm);
            addOtherChargeGridButton(frm);
            addRecalculateTTCGridButton(frm);
            void syncCustomerTaxId(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        party_name(frm) {
            void syncCustomerTaxId(frm);
        },
        quotation_to(frm) {
            void syncCustomerTaxId(frm);
        },
        items_add(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        items_remove(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        company(frm) {
            setupTaxTemplateQuery(frm);
            scheduleQuotationStockSnapshotRefresh(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        taxes_and_charges(frm) {
            applyTaxTemplateChange(frm);
            scheduleItemTTCFieldsSync(frm, { reloadTaxTemplate: true });
        },
    });

    frappe.ui.form.on("Quotation Item", {
        item_code(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        price_list_rate(frm) {
            if (!isDraftQuotation(frm)) return;
            const row = frappe.get_doc(arguments[1], arguments[2]);
            if (isManualChargeRow(row)) applyManualChargeRate(frm, row, Number(row.price_list_rate || row.rate || 0));
            scheduleItemTTCFieldsSync(frm);
        },
        source_selling_price_list(frm) {
            if (!isDraftQuotation(frm)) return;
            scheduleItemTTCFieldsSync(frm);
        },
        async source_discount_percent(frm, cdt, cdn) {
            if (!isDraftQuotation(frm)) return;
            if (frm.__orderlift_applying_quotation_price) return;
            await applyPricingDiscount(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
        },
        async source_discount_amount(frm, cdt, cdn) {
            if (!isDraftQuotation(frm)) return;
            if (frm.__orderlift_applying_quotation_price) return;
            await applyDiscountAmount(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
        },
        qty(frm, cdt, cdn) {
            if (!isDraftQuotation(frm)) return;
            // Quantity changes totals without deriving PU HT from display text.
            refreshRowCommissionTotals(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        async rate(frm, cdt, cdn) {
            if (!isDraftQuotation(frm)) return;
            if (frm.__orderlift_applying_quotation_price) return;
            const row = frappe.get_doc(cdt, cdn);
            if (isManualChargeRow(row)) {
                await applyManualChargeRate(frm, row, Number(row.rate || 0));
                return;
            }
            await applyResolvedRate(frm, row, Number(row.rate || 0));
        },
    });

    function showOpportunityField(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.opportunity) return;
        const field = frm.get_field && frm.get_field("opportunity");
        frm.set_df_property("opportunity", "hidden", 0);
        frm.set_df_property("opportunity", "read_only", 0);
        frm.toggle_display("opportunity", true);
        if (frm.toggle_enable) frm.toggle_enable("opportunity", true);
        frm.refresh_field("opportunity");
        if (field && field.wrapper) $(field.wrapper).show();
        setTimeout(() => {
            const refreshedField = frm.get_field && frm.get_field("opportunity");
            if (refreshedField && refreshedField.wrapper) $(refreshedField.wrapper).show();
        }, 0);
    }

    function hideNativeSourcePricingSheetField(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.source_pricing_sheet) return;
        const field = frm.get_field && frm.get_field("source_pricing_sheet");
        frm.set_df_property("source_pricing_sheet", "hidden", 1);
        frm.set_df_property("source_pricing_sheet", "read_only", 1);
        frm.set_df_property("source_pricing_sheet", "only_select", 1);
        frm.toggle_display("source_pricing_sheet", false);
        if (frm.toggle_enable) frm.toggle_enable("source_pricing_sheet", false);
        frm.refresh_field("source_pricing_sheet");
        if (field && field.df) field.df.only_select = 1;
        if (field && field.wrapper) $(field.wrapper).hide();
    }

    function renderPricingSheetSourcePanel(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.source_pricing_sheet) return;
        const field = frm.get_field && frm.get_field("source_pricing_sheet");
        if (!field || !field.wrapper) return;
        const existing = $(field.wrapper).siblings(".orderlift-quotation-source-ps");
        if (existing.length) existing.remove();

        const linkedSheet = String(frm.doc.source_pricing_sheet || "").trim();
        const isNew = frm.is_new && frm.is_new();
        const title = __("Pricing Sheet Source");
        const body = linkedSheet
            ? __("Linked Pricing Sheet: {0}", [linkedSheet])
            : isNew
                ? __("Create a Pricing Sheet from this new Quotation context. The Pricing Sheet will be linked after the Quotation is saved and a sheet is created.")
                : __("No Pricing Sheet is linked. Create one from this Quotation without selecting an unrelated existing sheet.");
        const action = linkedSheet
            ? `<button type="button" class="btn btn-xs btn-default" data-open-linked-pricing-sheet>${frappe.utils.escape_html(__("Open Pricing Sheet"))}</button>`
            : `<button type="button" class="btn btn-xs btn-primary" data-create-pricing-sheet-from-quotation>${frappe.utils.escape_html(isNew ? __("New Pricing Sheet") : __("Create Pricing Sheet from Quotation"))}</button>`;

        const panel = $(`
            <div class="orderlift-quotation-source-ps" style="margin: 8px 0 14px; padding: 10px 12px; border: 1px solid var(--border-color, #d1d8dd); border-radius: 8px; background: var(--fg-color, #fff);">
                <div style="display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;">
                    <div>
                        <div style="font-weight:600;">${frappe.utils.escape_html(title)}</div>
                        <div class="text-muted small">${frappe.utils.escape_html(body)}</div>
                    </div>
                    <div>${action}</div>
                </div>
            </div>
        `);
        panel.find("[data-create-pricing-sheet-from-quotation]").on("click", () => openPricingSheetBuilderFromQuotation(frm));
        panel.find("[data-open-linked-pricing-sheet]").on("click", () => openLinkedPricingSheet(frm));
        $(field.wrapper).after(panel);
    }

    function addPricingSheetActionButtons(frm) {
        if (!frm || !frm.add_custom_button) return;
        if (frm.doc.source_pricing_sheet) {
            frm.add_custom_button(__("Open Pricing Sheet"), () => openLinkedPricingSheet(frm), __("Pricing"));
            return;
        }
        frm.add_custom_button(frm.is_new && frm.is_new() ? __("New Pricing Sheet") : __("Create Pricing Sheet from Quotation"), () => openPricingSheetBuilderFromQuotation(frm), __("Pricing"));
    }

    async function openPricingSheetBuilderFromQuotation(frm) {
        if (!frm) return;
        const needsSave = (frm.is_new && frm.is_new()) || (frm.is_dirty && frm.is_dirty());
        if (needsSave) {
            try {
                await frm.save();
            } catch (error) {
                frappe.msgprint({
                    title: __("Save Quotation First"),
                    message: error.message || __("Unable to save the Quotation before creating a Pricing Sheet."),
                    indicator: "red",
                });
                return;
            }
        }
        const quotationName = frm.doc.name && !(frm.is_new && frm.is_new()) ? frm.doc.name : "";
        if (!quotationName) {
            frappe.msgprint({
                title: __("Quotation Required"),
                message: __("Save the Quotation before creating a Pricing Sheet."),
                indicator: "orange",
            });
            return;
        }
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.create_pricing_sheet_from_quotation",
                args: { quotation: quotationName, link_source_quotation: 1 },
                freeze: true,
            });
            const sheet = (res.message || {}).pricing_sheet;
            if (sheet) {
                frappe.show_alert({ message: __("Pricing Sheet {0} created", [sheet]), indicator: "green" });
                frappe.set_route("pricing-sheet-builder", sheet);
            }
        } catch (error) {
            frappe.msgprint({
                title: __("Pricing Sheet Failed"),
                message: error.message || __("Unable to create the Pricing Sheet from this Quotation."),
                indicator: "red",
            });
        }
    }

    function openLinkedPricingSheet(frm) {
        const sheet = String(frm.doc.source_pricing_sheet || "").trim();
        if (!sheet) return;
        frappe.set_route("pricing-sheet-builder", sheet);
    }

    function showTaxFields(frm) {
        if (!frm || !frm.fields_dict) return;
        TAX_SUMMARY_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 0);
            frm.toggle_display(fieldname, true);
            frm.refresh_field(fieldname);
            const field = frm.get_field && frm.get_field(fieldname);
            if (field && field.wrapper) $(field.wrapper).show();
        });
        TAX_DETAIL_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 1);
            frm.toggle_display(fieldname, false);
        });
    }

    function setupTaxTemplateQuery(frm) {
        if (!frm || !frm.set_query || !frm.fields_dict || !frm.fields_dict.taxes_and_charges) return;
        frm.set_query("taxes_and_charges", () => {
            const filters = { disabled: 0 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
    }

    function applyTaxTemplateChange(frm) {
        if (!isDraftQuotation(frm)) return;
        const template = String(frm.doc.taxes_and_charges || "").trim();
        if (template) {
            // The native controller loads the selected template asynchronously.
            // scheduleItemTTCFieldsSync waits for that request before syncing TTC.
            return;
        }
        // Cleared or emptied: zero-out taxes immediately
        frappe.model.clear_table(frm.doc, "taxes");
        frm.doc.total_taxes_and_charges = 0;
        frm.doc.base_total_taxes_and_charges = 0;
        frm.doc.grand_total = Number(frm.doc.total || 0);
        frm.doc.rounded_total = Number(frm.doc.total || 0);
        frm.doc.rounding_adjustment = 0;
        (frm.doc.items || []).forEach(function (row) {
            if ("custom_applied_taxes" in row) row.custom_applied_taxes = 0;
            if ("custom_pu_ttc" in row) row.custom_pu_ttc = Number(row.rate || 0);
            if ("custom_pt_ttc" in row) row.custom_pt_ttc = Number(row.amount || 0);
        });
        frm.refresh_field("taxes");
        frm.refresh_field("total_taxes_and_charges");
        frm.refresh_field("base_total_taxes_and_charges");
        frm.refresh_field("grand_total");
        frm.refresh_field("rounded_total");
        frm.refresh_field("rounding_adjustment");
        frm.refresh_field("items");
    }

    function currentActiveCompany() {
        const ctx = (window.frappe && frappe.boot && frappe.boot.orderlift_company_access) || {};
        return ctx.current_company || "";
    }

    async function applyOpportunityRouteOption(frm) {
        if (
            !frm || !frm.is_new || !frm.is_new() || !frm.fields_dict.opportunity
            || frm.doc.opportunity || frm.__orderlift_opportunity_route_applied
        ) return;
        const options = frappe.route_options || {};
        const opportunity = options.opportunity || "";
        if (!opportunity) return;
        frm.__orderlift_opportunity_route_applied = true;
        const quotationCompany = frm.doc.company || currentActiveCompany();
        if (quotationCompany) {
            try {
                const response = await frappe.db.get_value("Opportunity", opportunity, "company");
                const opportunityCompany = ((response.message || {}).company || "").trim();
                if (opportunityCompany && opportunityCompany !== quotationCompany) {
                    delete options.opportunity;
                    frappe.show_alert({
                        message: __("Cannot attach Opportunity {0}: it belongs to {1}, not {2}.", [
                            opportunity,
                            opportunityCompany,
                            quotationCompany,
                        ]),
                        indicator: "orange",
                    });
                    return;
                }
            } catch (error) {
                console.warn("Orderlift unable to validate opportunity company route option", error);
                return;
            }
        }
        await frm.set_value("opportunity", opportunity);
    }

    function setupOpportunityQuery(frm) {
        if (!frm || !frm.set_query || !frm.fields_dict.opportunity) return;
        frm.set_query("opportunity", () => {
            const filters = { docstatus: ["<", 2] };
            const company = frm.doc.company || "";
            if (company) filters.company = company;
            return { filters };
        });
    }

    function setupSourcePricingSheetQuery(frm) {
        if (!frm || !frm.set_query || !frm.fields_dict.source_pricing_sheet) return;
        frm.set_query("source_pricing_sheet", () => {
            const filters = {};
            const company = frm.doc.company || "";
            if (company) filters.custom_company = company;
            if (frm.doc.opportunity) filters.opportunity = frm.doc.opportunity;
            return { filters };
        });
    }

    function hideNativeDiscountAndTaxFields(frm) {
        HIDDEN_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 1);
            frm.toggle_display(fieldname, false);
        });
    }

    function quotationGridHasField(grid, fieldname) {
        return Boolean(grid && (grid.docfields || []).some((field) => field.fieldname === fieldname));
    }

    function applyQuotationItemPricingLayout(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !Array.isArray(grid.grid_rows)) return;
        const pricingEditable = isDraftQuotation(frm);
        const layoutSignature = `${pricingEditable ? "draft" : "submitted"}:${canViewQuotationMargins() ? "margins" : "standard"}`;
        if (grid.__orderlift_pricing_layout_signature === layoutSignature) {
            disableQuotationItemRowForms(frm);
            scheduleQuotationPrecisionInputDisplay(grid);
            return;
        }
        enforceQuotationItemGridColumns(frm);
        disableQuotationItemRowForms(frm);
        INTERNAL_ITEM_PRICE_FIELDS.forEach((fieldname) => {
            if (!quotationGridHasField(grid, fieldname)) return;
            grid.update_docfield_property(fieldname, "read_only", 1);
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
        });
        if (quotationGridHasField(grid, "source_price_list_sell_rate")) {
            grid.update_docfield_property("source_price_list_sell_rate", "label", __("PU List HT"));
            grid.update_docfield_property("source_price_list_sell_rate", "read_only", 1);
            grid.update_docfield_property("source_price_list_sell_rate", "hidden", 0);
            grid.update_docfield_property("source_price_list_sell_rate", "in_list_view", 1);
            grid.update_docfield_property("source_price_list_sell_rate", "precision", "9");
        }
        if (quotationGridHasField(grid, "rate")) {
            grid.update_docfield_property("rate", "label", __("PU HT"));
            grid.update_docfield_property("rate", "read_only", pricingEditable ? 0 : 1);
            grid.update_docfield_property("rate", "hidden", 0);
            grid.update_docfield_property("rate", "in_list_view", 1);
            grid.update_docfield_property("rate", "precision", "9");
        }
        if (quotationGridHasField(grid, "amount")) {
            grid.update_docfield_property("amount", "label", __("PT HT"));
            grid.update_docfield_property("amount", "read_only", 1);
            grid.update_docfield_property("amount", "hidden", 0);
            grid.update_docfield_property("amount", "in_list_view", 1);
            grid.update_docfield_property("amount", "precision", "9");
        }
        if (quotationGridHasField(grid, "source_discount_amount")) {
            grid.update_docfield_property("source_discount_amount", "label", __("Remise PU HT"));
            grid.update_docfield_property("source_discount_amount", "read_only", pricingEditable ? 0 : 1);
            grid.update_docfield_property("source_discount_amount", "hidden", 0);
            grid.update_docfield_property("source_discount_amount", "in_list_view", 1);
            grid.update_docfield_property("source_discount_amount", "precision", "9");
        }
        if (quotationGridHasField(grid, "custom_applied_taxes")) {
            grid.update_docfield_property("custom_applied_taxes", "label", __("Taxes"));
            grid.update_docfield_property("custom_applied_taxes", "read_only", 1);
            grid.update_docfield_property("custom_applied_taxes", "hidden", 0);
            grid.update_docfield_property("custom_applied_taxes", "in_list_view", 0);
            grid.update_docfield_property("custom_applied_taxes", "precision", "9");
        }
        if (quotationGridHasField(grid, "custom_pu_ttc")) {
            grid.update_docfield_property("custom_pu_ttc", "label", __("PU TTC"));
            grid.update_docfield_property("custom_pu_ttc", "read_only", 1);
            grid.update_docfield_property("custom_pu_ttc", "hidden", 0);
            grid.update_docfield_property("custom_pu_ttc", "in_list_view", 1);
            grid.update_docfield_property("custom_pu_ttc", "precision", "9");
        }
        if (quotationGridHasField(grid, "custom_pt_ttc")) {
            grid.update_docfield_property("custom_pt_ttc", "label", __("PT TTC"));
            grid.update_docfield_property("custom_pt_ttc", "read_only", 1);
            grid.update_docfield_property("custom_pt_ttc", "hidden", 0);
            grid.update_docfield_property("custom_pt_ttc", "in_list_view", 1);
            grid.update_docfield_property("custom_pt_ttc", "precision", "9");
        }
        if (quotationGridHasField(grid, "source_max_discount_percent")) {
            grid.update_docfield_property("source_max_discount_percent", "label", __("Max Discount %"));
            grid.update_docfield_property("source_max_discount_percent", "hidden", 0);
            grid.update_docfield_property("source_max_discount_percent", "read_only", 1);
            grid.update_docfield_property("source_max_discount_percent", "in_list_view", 1);
        }
        applyQuotationMarginVisibility(grid);
        if (quotationGridHasField(grid, "source_discount_percent")) {
            grid.update_docfield_property("source_discount_percent", "label", __("Remise %"));
            grid.update_docfield_property("source_discount_percent", "hidden", 0);
            grid.update_docfield_property("source_discount_percent", "read_only", pricingEditable ? 0 : 1);
            grid.update_docfield_property("source_discount_percent", "in_list_view", 1);
        }
        if (quotationGridHasField(grid, "qty")) {
            grid.update_docfield_property("qty", "read_only", pricingEditable ? 0 : 1);
        }
        applyQuotationCurrencyFormatters(grid);
        hideLegacyQuotationPriceFields(grid);
        grid.__orderlift_pricing_layout_signature = layoutSignature;
        disableQuotationItemRowForms(frm);
        scheduleQuotationPrecisionInputDisplay(grid);
    }

    function enforceQuotationItemGridColumns(frm) {
        const grid = frm && frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid) return;

        const columns = configuredQuotationItemGridColumns(frm, grid);

        (grid.docfields || []).forEach((df) => {
            if (!df || !df.fieldname) return;
            const column = columns.find((entry) => entry.fieldname === df.fieldname);
            if (column) {
                df.in_list_view = 1;
                df.columns = column.columns;
                df.sticky = column.sticky;
                if (["amount", "custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc"].includes(df.fieldname)) df.read_only = 1;
            } else {
                df.in_list_view = 0;
                df.columns = 0;
                df.sticky = 0;
            }
        });
        grid.visible_columns = [];
        grid.user_defined_columns = [];
    }

    function configuredQuotationItemGridColumns(frm, grid) {
        const defaults = quotationItemGridColumns();
        if (!frappe.get_user_settings || !frm || !grid) return defaults;

        const gridViewSettings = frappe.get_user_settings(frm.doctype, "GridView") || {};
        const savedColumns = Array.isArray(gridViewSettings[grid.doctype])
            ? gridViewSettings[grid.doctype]
            : [];
        if (!savedColumns.length) return defaults;

        const validFieldnames = new Set((grid.docfields || []).map((df) => df && df.fieldname).filter(Boolean));
        const configured = savedColumns
            .map((column) => {
                if (!column || !LEGACY_ITEM_PRICE_FIELDS.has(column.fieldname)) return column;
                return Object.assign({}, column, { fieldname: "rate" });
            })
            .filter((column) => {
                const fieldname = column && column.fieldname;
                if (!fieldname || !validFieldnames.has(fieldname)) return false;
                if (INTERNAL_ITEM_PRICE_FIELDS.includes(fieldname)) return false;
                if (LEGACY_ITEM_PRICE_FIELDS.has(fieldname)) return false;
                if (
                    [
                        "source_target_margin_percent",
                        "source_margin_percent",
                        "source_margin_basis",
                        "source_base_buy_rate",
                        "source_landed_cost",
                    ].includes(fieldname)
                    && !canViewQuotationMargins()
                ) return false;
                return true;
            })
            .reduce((columns, column) => {
                if (columns.some((entry) => entry.fieldname === column.fieldname)) return columns;
                columns.push({
                    fieldname: column.fieldname,
                    columns: Math.min(Math.max(Number(column.columns) || 1, 1), 10),
                    sticky: Number(column.sticky || 0),
                });
                return columns;
            }, []);

        const configuredFieldnames = new Set(configured.map((column) => column.fieldname));
        const missingDefaults = defaults.filter((column) => !configuredFieldnames.has(column.fieldname));
        return configured.concat(missingDefaults);
    }

    function quotationItemGridColumns() {
        const columns = QUOTATION_ITEM_GRID_COLUMNS.map((column) => Object.assign({}, column));
        if (canViewQuotationMargins()) {
            columns.push({ fieldname: "source_target_margin_percent", columns: 1, sticky: 0 });
            columns.push({ fieldname: "source_margin_percent", columns: 1, sticky: 0 });
            columns.push({ fieldname: "source_base_buy_rate", columns: 1, sticky: 0 });
            columns.push({ fieldname: "source_landed_cost", columns: 1, sticky: 0 });
        }
        return columns;
    }

    function applyQuotationMarginVisibility(grid) {
        [
            ["source_target_margin_percent", "Target Policy Margin %"],
            ["source_margin_basis", "Margin Basis"],
            ["source_margin_percent", "Actual Margin %"],
            ["source_base_buy_rate", "Base Buy Rate"],
            ["source_landed_cost", "Loaded Cost"],
        ].forEach(([fieldname, label]) => {
            if (!quotationGridHasField(grid, fieldname)) return;
            const visible = canViewQuotationMargins();
            grid.update_docfield_property(fieldname, "label", __(label));
            grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1);
            grid.update_docfield_property(fieldname, "read_only", 1);
            const configured = Number((grid.get_field(fieldname) || {}).columns || 0) > 0;
            grid.update_docfield_property(
                fieldname,
                "in_list_view",
                visible && (fieldname !== "source_margin_basis" || configured) ? 1 : 0
            );
        });
    }

    function applyQuotationCurrencyFormatters(grid) {
        DISPLAY_CURRENCY_FIELDS.forEach((fieldname) => {
            const field = quotationGridHasField(grid, fieldname) ? grid.get_field(fieldname) : null;
            if (!field) return;
            grid.update_docfield_property(fieldname, "precision", "9");
            field.formatter = (value) => formatCurrency(value);
        });
        DISPLAY_PERCENT_FIELDS.forEach((fieldname) => {
            const field = quotationGridHasField(grid, fieldname) ? grid.get_field(fieldname) : null;
            if (!field) return;
            grid.update_docfield_property(fieldname, "precision", "9");
            field.formatter = (value) => `${Number(value || 0).toFixed(2)}%`;
        });
        DISPLAY_FLOAT_FIELDS.forEach((fieldname) => {
            const field = quotationGridHasField(grid, fieldname) ? grid.get_field(fieldname) : null;
            if (!field) return;
            field.formatter = (value) => displayQuotationNumber(value);
        });
    }

    function scheduleQuotationPrecisionInputDisplay(grid) {
        scheduleQuotationPrecisionFrame(
            grid,
            "__orderlift_precision_display_pending",
            () => applyQuotationPrecisionInputDisplay(grid)
        );
    }

    function scheduleQuotationPrecisionFrame(target, flag, callback) {
        if (!target || target[flag]) return;
        target[flag] = true;
        const run = () => {
            target[flag] = false;
            callback();
        };
        if (typeof window.requestAnimationFrame === "function") {
            window.requestAnimationFrame(run);
        } else {
            window.setTimeout(run, 0);
        }
    }

    function applyQuotationPrecisionInputDisplay(grid) {
        if (!grid || !grid.wrapper) return;
        (grid.grid_rows || []).forEach((gridRow) => applyQuotationPrecisionGridRowDisplay(gridRow));

        const $wrapper = $(grid.wrapper);
        DISPLAY_NUMERIC_FIELDS.forEach((fieldname) => {
            $wrapper.find(`[data-fieldname="${fieldname}"] input`).each((_, input) => {
                const row = quotationRowForInput(grid, input);
                if (!row) return;
                applyQuotationPrecisionInput(input, row, fieldname);
            });
        });
    }

    function applyQuotationPrecisionGridRowDisplay(gridRow) {
        if (!gridRow || !gridRow.doc) return;
        DISPLAY_NUMERIC_FIELDS.forEach((fieldname) => {
            const column = gridRow.columns && gridRow.columns[fieldname];
            if (column) {
                if (column.field_area) {
                    $(column.field_area).find("input").each((_, input) => {
                        applyQuotationPrecisionInput(input, gridRow.doc, fieldname);
                    });
                }
                if (column.static_area) {
                    applyQuotationPrecisionStatic($(column.static_area), gridRow.doc, fieldname);
                }
                if (column.field && column.field.$input) {
                    column.field.$input.each((_, input) => applyQuotationPrecisionInput(input, gridRow.doc, fieldname));
                }
            }
            if (gridRow.row) {
                const $cell = $(gridRow.row).find(`[data-fieldname="${fieldname}"]`);
                $cell.find("input").each((_, input) => applyQuotationPrecisionInput(input, gridRow.doc, fieldname));
                applyQuotationPrecisionStatic($cell.find(".static-area, .ellipsis"), gridRow.doc, fieldname);
            }
        });
    }

    function quotationRowForInput(grid, input) {
        const $input = $(input);
        const rowName = $input.closest(".grid-row").attr("data-name")
            || $input.closest("[data-name]").attr("data-name");
        if (rowName && typeof locals !== "undefined" && locals["Quotation Item"] && locals["Quotation Item"][rowName]) {
            return locals["Quotation Item"][rowName];
        }
        const element = input;
        return (grid.grid_rows || []).map((gridRow) => gridRow && gridRow.doc ? gridRow : null).find((gridRow) => {
            if (!gridRow) return false;
            const rawRowNode = gridRow.row || gridRow.wrapper;
            const rowNode = rawRowNode && rawRowNode.jquery ? rawRowNode[0] : rawRowNode;
            return rowNode && $.contains(rowNode, element);
        })?.doc;
    }

    function applyQuotationPrecisionInput(input, row, fieldname) {
        if (!input || !row) return;
        const $input = $(input);
        if (!$input.data("orderliftPrecisionDisplayBound")) {
            $input.data("orderliftPrecisionDisplayBound", 1);
            $input.on("focus.orderliftPrecisionDisplay", () => {
                input.dataset.orderliftUserEditing = "0";
                input.value = displayQuotationInputNumber(row[fieldname]);
                input.select();
            });
            $input.on("input.orderliftPrecisionDisplay", () => {
                input.dataset.orderliftUserEditing = "1";
            });
            $input.on("blur.orderliftPrecisionDisplay", () => {
                window.setTimeout(() => {
                    input.dataset.orderliftUserEditing = "0";
                    input.value = displayQuotationInputNumber(row[fieldname]);
                }, 0);
            });
        }
        if (document.activeElement !== input || input.dataset.orderliftUserEditing !== "1") {
            input.value = displayQuotationInputNumber(row[fieldname]);
        }
    }

    function applyQuotationPrecisionStatic($targets, row, fieldname) {
        if (!$targets || !$targets.length || !row) return;
        $targets.each((_, target) => {
            const $target = $(target);
            if ($target.find("input, select, textarea").length) return;
            if (DISPLAY_CURRENCY_FIELDS.has(fieldname)) {
                $target.html(formatCurrency(row[fieldname]));
            } else {
                $target.text(displayQuotationStaticNumber(row[fieldname], fieldname));
            }
        });
    }

    function rawQuotationNumber(value) {
        const number = Number(value || 0);
        if (!Number.isFinite(number)) return "0";
        return number.toFixed(9).replace(/\.?0+$/, "");
    }

    function displayQuotationInputNumber(value) {
        return Number(value || 0).toFixed(2);
    }

    function displayQuotationStaticNumber(value, fieldname) {
        const formatted = displayQuotationInputNumber(value);
        return DISPLAY_PERCENT_FIELDS.has(fieldname) ? `${formatted}%` : formatted;
    }

    function displayQuotationNumber(value) {
        return displayQuotationInputNumber(value);
    }

    function hideLegacyQuotationPriceFields(grid) {
        LEGACY_ITEM_PRICE_FIELDS.forEach((fieldname) => {
            if (!quotationGridHasField(grid, fieldname)) return;
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
        });
    }

    function disableQuotationItemRowForms(frm) {
        const grid = frm && frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid) return;

        if (grid.df) grid.df.in_place_edit = isDraftQuotation(frm) ? 1 : 0;
        patchQuotationItemsGridRefresh(grid);
        applyInlineOnlyQuotationItemsGrid(grid);
    }

    function patchQuotationItemsGridRefresh(grid) {
        if (!grid || grid.__orderlift_inline_items_refresh_patched || typeof grid.refresh !== "function") return;
        const originalRefresh = grid.refresh.bind(grid);
        grid.refresh = function () {
            const result = originalRefresh.apply(grid, arguments);
            setTimeout(() => {
                applyInlineOnlyQuotationItemsGrid(grid);
                applyQuotationPrecisionInputDisplay(grid);
            }, 0);
            return result;
        };
        grid.__orderlift_inline_items_refresh_patched = true;
    }

    function applyInlineOnlyQuotationItemsGrid(grid) {
        if (!grid) return;
        if (grid.df) grid.df.in_place_edit = isDraftQuotation(grid.frm) ? 1 : 0;
        if (grid.wrapper) {
            const wrapper = $(grid.wrapper);
            wrapper.addClass("orderlift-inline-items-grid");
            ensureQuotationItemsGridStyles();
            wrapper.find(".btn-open-row").closest(".col").hide();
        }
        (grid.grid_rows || []).forEach((gridRow) => patchQuotationItemGridRow(gridRow));
    }

    function patchQuotationItemGridRow(gridRow) {
        if (!gridRow || gridRow.__orderlift_inline_only_patched || typeof gridRow.toggle_view !== "function") return;
        const originalToggleView = gridRow.toggle_view.bind(gridRow);
        gridRow.toggle_view = function (show, callback) {
            if (
                gridRow.doc && gridRow.doc.doctype === "Quotation Item" && show !== false
                && isDraftQuotation(gridRow.grid && gridRow.grid.frm)
            ) {
                if (gridRow.grid && gridRow.grid.is_editable && gridRow.grid.is_editable() && typeof gridRow.toggle_editable_row === "function") {
                    gridRow.toggle_editable_row(true);
                }
                if (typeof callback === "function") callback();
                return gridRow;
            }
            return originalToggleView(show, callback);
        };
        if (gridRow.open_form_button) $(gridRow.open_form_button).closest(".col").hide();
        patchQuotationGridRowRender(gridRow);
        gridRow.__orderlift_inline_only_patched = true;
    }

    function patchQuotationGridRowRender(gridRow) {
        ["render", "refresh", "toggle_editable_row"].forEach((methodName) => {
            if (typeof gridRow[methodName] !== "function" || gridRow[`__orderlift_${methodName}_patched`]) return;
            const original = gridRow[methodName].bind(gridRow);
            gridRow[methodName] = function () {
                const result = original.apply(gridRow, arguments);
                scheduleQuotationPrecisionFrame(
                    gridRow,
                    "__orderlift_precision_display_pending",
                    () => applyQuotationPrecisionGridRowDisplay(gridRow)
                );
                return result;
            };
            gridRow[`__orderlift_${methodName}_patched`] = true;
        });
    }

    function ensureQuotationItemsGridStyles() {
        if (document.getElementById("orderlift-quotation-items-grid-style")) return;
        $("head").append(`
            <style id="orderlift-quotation-items-grid-style">
                .orderlift-inline-items-grid {
                    padding-bottom: 6px;
                }
                .orderlift-inline-items-grid .form-grid-container.column-limit-reached {
                    overflow-x: auto;
                    scrollbar-gutter: stable;
                }
                .orderlift-inline-items-grid .form-grid-container.column-limit-reached > .form-grid {
                    min-width: max-content;
                    width: max-content;
                }
                .orderlift-inline-items-grid .column-limit-reached .grid-heading-row .grid-row .data-row.row,
                .orderlift-inline-items-grid .column-limit-reached .grid-body .rows .grid-row .data-row.row {
                    justify-content: flex-start;
                    min-width: max-content;
                    width: max-content;
                }
                .orderlift-inline-items-grid .column-limit-reached .form-grid .grid-static-col[data-fieldname] {
                    --orderlift-grid-cell-width: 140px;
                    box-sizing: border-box;
                    flex: 0 0 var(--orderlift-grid-cell-width);
                    max-width: var(--orderlift-grid-cell-width);
                    min-width: var(--orderlift-grid-cell-width);
                    width: var(--orderlift-grid-cell-width);
                }
                .orderlift-inline-items-grid .column-limit-reached .form-grid .grid-static-col[data-fieldname="item_code"] {
                    --orderlift-grid-cell-width: 260px;
                }
                .orderlift-inline-items-grid .column-limit-reached .form-grid .grid-static-col[data-fieldname="qty"] {
                    --orderlift-grid-cell-width: 90px;
                }
                .orderlift-inline-items-grid .column-limit-reached .form-grid .grid-static-col[data-fieldname="source_discount_amount"] {
                    --orderlift-grid-cell-width: 170px;
                }
                .orderlift-inline-items-grid .column-limit-reached .form-grid .grid-row > .data-row.row > .grid-static-col[data-fieldname]:last-child {
                    flex: 0 0 var(--orderlift-grid-cell-width);
                    line-height: inherit;
                    max-width: var(--orderlift-grid-cell-width);
                    min-width: var(--orderlift-grid-cell-width);
                    position: static;
                    right: auto;
                    width: var(--orderlift-grid-cell-width);
                    z-index: auto;
                }
                .orderlift-inline-items-grid .column-limit-reached .grid-static-col[data-fieldname] .field-area,
                .orderlift-inline-items-grid .column-limit-reached .grid-static-col[data-fieldname] .control-input-wrapper,
                .orderlift-inline-items-grid .column-limit-reached .grid-static-col[data-fieldname] .form-control {
                    box-sizing: border-box;
                    max-width: 100%;
                    min-width: 0;
                    width: 100%;
                }
                .orderlift-inline-items-grid .grid-static-col {
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    min-height: 34px;
                }
                .orderlift-inline-items-grid .grid-static-col .static-area,
                .orderlift-inline-items-grid .grid-static-col .ellipsis,
                .orderlift-inline-items-grid .grid-static-col a {
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .orderlift-inline-items-grid .grid-heading-row .grid-static-col {
                    align-items: center;
                    line-height: 1.2;
                }
            </style>
        `);
    }

    function addOtherChargeButton(frm) {
        if (frm.__orderlift_other_charge_button_added || Number(frm.doc.docstatus || 0) > 0) return;
        frm.__orderlift_other_charge_button_added = true;
        frm.add_custom_button(__("Other Charges"), () => openOtherChargeDialog(frm), __("Items"));
    }

    function addOtherChargeGridButton(frm) {
        if (Number(frm.doc.docstatus || 0) > 0) return;
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper || grid.__orderlift_other_charge_button_added) return;

        if (typeof grid.add_custom_button === "function") {
            const $btn = grid.add_custom_button(__("Other Charges"), () => openOtherChargeDialog(frm), "top");
            if ($btn) $btn.attr("data-orderlift-other-charge", "1").addClass("btn-secondary");
            grid.__orderlift_other_charge_button_added = true;
            return;
        }

        const $target = $(grid.wrapper).find(".grid-custom-buttons, .grid-add-multiple-rows").first();
        if (!$target.length) return;
        const $button = $(`<button type="button" class="btn btn-xs btn-secondary" data-orderlift-other-charge="1">${__("Other Charges")}</button>`);
        $button.on("click", (event) => {
            event.preventDefault();
            openOtherChargeDialog(frm);
        });
        $target.prepend($button);
        grid.__orderlift_other_charge_button_added = true;
    }

    function addRecalculateTTCGridButton(frm) {
        if (!frm || !frm.doc || Number(frm.doc.docstatus || 0) !== 0) return;
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper || grid.__orderlift_recalculate_ttc_button_added) return;

        const recalculate = async () => {
            try {
                await recalculateQuotationTTC(frm, { reloadTaxTemplate: true, showAlert: true });
            } catch (error) {
                frappe.msgprint({
                    title: __("TTC Recalculation Failed"),
                    message: (error && error.message) || __("Unable to recalculate TTC values."),
                    indicator: "red",
                });
            }
        };

        if (typeof grid.add_custom_button === "function") {
            const $button = grid.add_custom_button(__("Recalculate TTC"), recalculate);
            if ($button) $button.attr("data-orderlift-recalculate-ttc", "1").addClass("btn-secondary");
            grid.__orderlift_recalculate_ttc_button_added = true;
            return;
        }

        const $target = $(grid.wrapper).find(".grid-buttons, .grid-add-multiple-rows").first();
        if (!$target.length) return;
        const $button = $(
            `<button type="button" class="btn btn-xs btn-secondary" data-orderlift-recalculate-ttc="1">${__("Recalculate TTC")}</button>`
        );
        $button.on("click", (event) => {
            event.preventDefault();
            void recalculate();
        });
        $target.prepend($button);
        grid.__orderlift_recalculate_ttc_button_added = true;
    }

    async function openOtherChargeDialog(frm) {
        const res = await frappe.call({
            method: OTHER_CHARGE_ITEM_METHOD,
            args: { company: frm.doc.company || "" },
            freeze: true,
        });
        const item = res.message || {};
        let dialog;
        dialog = new frappe.ui.Dialog({
            title: __("Add Other Charges"),
            fields: [
                {
                    fieldname: "other_charge",
                    fieldtype: "Link",
                    options: "Orderlift Other Charge",
                    label: __("Charge"),
                    reqd: 1,
                    get_query: () => ({ filters: { disabled: 0 } }),
                    onchange: () => void loadOtherChargeTemplate(frm, dialog).catch((error) => console.warn("Unable to load Other Charge template", error)),
                },
                {
                    fieldname: "description",
                    fieldtype: "Small Text",
                    label: __("Description"),
                    reqd: 1,
                },
                {
                    fieldname: "qty",
                    fieldtype: "Float",
                    label: __("Quantity"),
                    default: 1,
                    reqd: 1,
                },
                {
                    fieldname: "uom",
                    fieldtype: "Link",
                    options: "UOM",
                    label: __("UOM"),
                    default: item.uom || "",
                    reqd: 1,
                },
                {
                    fieldname: "unit_amount",
                    fieldtype: "Currency",
                    label: __("Unit Amount HT"),
                    default: 0,
                    reqd: 1,
                },
                ...(canViewQuotationMargins() ? [{
                    fieldname: "expected_unit_cost",
                    fieldtype: "Currency",
                    label: __("Expected Unit Cost HT"),
                    default: 0,
                    description: __("Theoretical direct cost used until Purchase Orders and Purchase Invoices provide real costs."),
                }] : []),
                {
                    fieldname: "item_code",
                    fieldtype: "Link",
                    options: "Item",
                    label: __("Item"),
                    default: item.item_code || "",
                    hidden: 1,
                },
            ],
            primary_action_label: __("Add Charge"),
            async primary_action(values) {
                dialog.disable_primary_action();
                try {
                    await addOtherChargeRow(frm, values, dialog, item);
                } finally {
                    dialog.enable_primary_action();
                }
            },
        });
        dialog.show();
    }

    async function loadOtherChargeTemplate(frm, dialog) {
        const otherCharge = String(dialog.get_value("other_charge") || "").trim();
        if (!otherCharge) return null;
        const res = await frappe.call({
            method: OTHER_CHARGE_TEMPLATE_METHOD,
            args: { other_charge: otherCharge, company: frm.doc.company || "" },
        });
        if (String(dialog.get_value("other_charge") || "").trim() !== otherCharge) return null;
        const charge = res.message || {};
        dialog.set_value("description", charge.description || otherCharge);
        dialog.set_value("uom", charge.uom || "");
        dialog.set_value("unit_amount", Number(charge.rate || 0));
        if (dialog.fields_dict.expected_unit_cost) dialog.set_value("expected_unit_cost", Number(charge.expected_unit_cost || 0));
        dialog.set_value("item_code", charge.item_code || "");
        return charge;
    }

    frappe.ui.form.on("Orderlift Quotation Other Charge", {
        other_charge(frm, cdt, cdn) {
            void fillOtherChargeChildRow(frm, cdt, cdn).catch((error) => console.warn("Unable to fill Other Charge row", error));
        },
        qty(frm, cdt, cdn) {
            updateOtherChargeChildAmount(frm, cdt, cdn);
        },
        rate(frm, cdt, cdn) {
            updateOtherChargeChildAmount(frm, cdt, cdn);
        },
        expected_unit_cost(frm, cdt, cdn) {
            updateOtherChargeChildAmount(frm, cdt, cdn);
        },
    });

    async function fillOtherChargeChildRow(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        const otherCharge = String((row && row.other_charge) || "").trim();
        if (!row || !otherCharge) return;
        const res = await frappe.call({
            method: OTHER_CHARGE_TEMPLATE_METHOD,
            args: { other_charge: otherCharge, company: frm.doc.company || "" },
        });
        if (String(((locals[cdt] && locals[cdt][cdn]) || {}).other_charge || "").trim() !== otherCharge) return;
        const charge = res.message || {};
        const updates = [];
        if (!row.description && charge.description) updates.push(frappe.model.set_value(cdt, cdn, "description", charge.description));
        if (!row.uom && charge.uom) updates.push(frappe.model.set_value(cdt, cdn, "uom", charge.uom));
        if (!Number(row.rate || 0) && Number(charge.rate || 0)) updates.push(frappe.model.set_value(cdt, cdn, "rate", Number(charge.rate || 0)));
        if (canViewQuotationMargins()) updates.push(frappe.model.set_value(cdt, cdn, "expected_unit_cost", Number(charge.expected_unit_cost || 0)));
        if (!row.item_code && charge.item_code) updates.push(frappe.model.set_value(cdt, cdn, "item_code", charge.item_code));
        if (updates.length) await Promise.all(updates);
        updateOtherChargeChildAmount(frm, cdt, cdn);
    }

    function updateOtherChargeChildAmount(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row) return;
        const qty = Number(row.qty || 0);
        const rate = Number(row.rate || 0);
        const amount = Number.isFinite(qty) && Number.isFinite(rate) ? qty * rate : 0;
        frappe.model.set_value(cdt, cdn, "amount", amount);
        if (canViewQuotationMargins()) {
            const expectedUnitCost = Number(row.expected_unit_cost || 0);
            const expectedCost = Number.isFinite(qty) && Number.isFinite(expectedUnitCost) ? qty * expectedUnitCost : 0;
            frappe.model.set_value(cdt, cdn, "expected_cost", expectedCost);
        }
    }

    async function addOtherChargeRow(frm, values, dialog, item) {
        if (values.other_charge && (!values.uom || !Number(values.unit_amount || 0) || !values.item_code)) {
            const charge = await loadOtherChargeTemplate(frm, dialog);
            values = { ...values, ...dialog.get_values(), item_code: (charge && charge.item_code) || values.item_code };
        }
        const qty = Number(values.qty || 0);
        const unitAmount = Number(values.unit_amount || 0);
        const expectedUnitCost = canViewQuotationMargins() ? Number(values.expected_unit_cost || 0) : 0;
        const otherCharge = String(values.other_charge || "").trim();
        const description = String(values.description || "").trim() || __("Other Charges");
        const uom = String(values.uom || (item || {}).uom || "").trim();
        const itemCode = String(values.item_code || item.item_code || "").trim();
        if (!otherCharge) {
            frappe.msgprint({ title: __("Charge Required"), message: __("Select a saved charge."), indicator: "red" });
            return;
        }
        if (!Number.isFinite(qty) || qty <= 0) {
            frappe.msgprint({ title: __("Invalid Quantity"), message: __("Enter a quantity greater than zero."), indicator: "red" });
            return;
        }
        if (!uom) {
            frappe.msgprint({ title: __("UOM Required"), message: __("Choose a UOM for the charge."), indicator: "red" });
            return;
        }
        if (!Number.isFinite(unitAmount) || unitAmount < 0) {
            frappe.msgprint({ title: __("Invalid Amount"), message: __("Enter an amount of zero or more."), indicator: "red" });
            return;
        }
        if (!Number.isFinite(expectedUnitCost) || expectedUnitCost < 0) {
            frappe.msgprint({ title: __("Invalid Expected Cost"), message: __("Enter an expected unit cost of zero or more."), indicator: "red" });
            return;
        }

        const amount = qty * unitAmount;
        const expectedCost = qty * expectedUnitCost;
        if (frm.fields_dict.custom_other_charges) {
            frm.add_child("custom_other_charges", {
                other_charge: otherCharge,
                description,
                qty,
                uom,
                rate: unitAmount,
                amount,
                ...(canViewQuotationMargins() ? { expected_unit_cost: expectedUnitCost, expected_cost: expectedCost } : {}),
                item_code: itemCode,
            });
            frm.refresh_field("custom_other_charges");
        }

        const row = frm.add_child("items", {
            item_code: itemCode,
            item_name: item.item_name || description,
            description,
            qty,
            stock_uom: item.uom || uom,
            uom,
            conversion_factor: 1,
            price_list_rate: unitAmount,
            base_price_list_rate: unitAmount,
            rate: unitAmount,
            base_rate: unitAmount,
            amount,
            base_amount: amount,
            net_rate: unitAmount,
            net_amount: amount,
            base_net_rate: unitAmount,
            base_net_amount: amount,
            discount_percentage: 0,
            source_price_list_sell_rate: unitAmount,
            source_discount_percent: 0,
            source_max_discount_percent: 0,
            source_discount_amount: 0,
            ...(canViewQuotationMargins() ? { source_landed_cost: expectedUnitCost } : {}),
            custom_presentation_role: "Print separately",
            custom_orderlift_other_charge: frm.fields_dict.custom_other_charges ? 1 : 0,
        });
        if (row && "ignore_pricing_rule" in row) row.ignore_pricing_rule = 1;
        dialog.hide();
        frm.refresh_field("items");
        syncItemTTCFields(frm);
        frm.dirty();
        frappe.show_alert({ message: __("Other charges added"), indicator: "green" });
    }

    function addBulkQuantityButton(frm) {
        if (frm.__orderlift_bulk_quantity_button_added) return;
        frm.__orderlift_bulk_quantity_button_added = true;
        frm.add_custom_button(__("Bulk Quantity"), () => openBulkQuantityDialog(frm), __("Items"));
    }

    function addBulkQuantityGridButton(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper) return;
        const $wrapper = $(grid.wrapper);
        if ($wrapper.find("[data-orderlift-bulk-quantity]").length || grid.__orderlift_bulk_quantity_buttons_added) return;

        // Try adding to the 'top' position which goes to grid_custom_buttons (appears with multi-select actions)
        if (typeof grid.add_custom_button === "function") {
            const $btn = grid.add_custom_button(__("Bulk Quantity"), () => {
                openBulkQuantityDialog(frm);
            }, "top");

            // Also add to bottom so it's visible if top isn't configured correctly in some versions
            const $btn_bottom = grid.add_custom_button(__("Bulk Quantity"), () => {
                openBulkQuantityDialog(frm);
            });

            if ($btn) $btn.attr("data-orderlift-bulk-quantity", "1").addClass("btn-secondary");
            if ($btn_bottom) $btn_bottom.attr("data-orderlift-bulk-quantity", "1").addClass("btn-secondary");
            grid.__orderlift_bulk_quantity_buttons_added = true;
            return;
        }

        let $target = $wrapper.find(".grid-custom-buttons").first();
        let insertBeforeTarget = false;
        if (!$target.length) {
            $target = $wrapper.find(".grid-add-multiple-rows").first();
            insertBeforeTarget = true;
        }
        if (!$target.length) return;

        const $button = $(
            `<button type="button" class="btn btn-xs btn-secondary" data-orderlift-bulk-quantity="1">${__("Bulk Quantity")}</button>`
        );
        $button.on("click", (event) => {
            event.preventDefault();
            openBulkQuantityDialog(frm);
        });
        if (insertBeforeTarget) {
            $button.insertBefore($target);
        } else {
            $target.prepend($button);
        }
        grid.__orderlift_bulk_quantity_buttons_added = true;
    }

    function openBulkQuantityDialog(frm) {
        const selectedRows = getSelectedItemRows(frm);
        if (!selectedRows.length) {
            frappe.msgprint({
                title: __("No Items Selected"),
                message: __("Select one or more rows in the Items table before applying a bulk quantity."),
                indicator: "orange",
            });
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Apply Quantity to Selected Items"),
            fields: [
                {
                    fieldname: "qty",
                    fieldtype: "Float",
                    label: __("Quantity"),
                    reqd: 1,
                    default: 1,
                    description: __("This will update {0} selected item row(s).", [selectedRows.length]),
                },
            ],
            primary_action_label: __("Apply Quantity"),
            primary_action(values) {
                const qty = Number(values.qty || 0);
                if (!Number.isFinite(qty) || qty <= 0) {
                    frappe.msgprint({
                        title: __("Invalid Quantity"),
                        message: __("Enter a quantity greater than zero."),
                        indicator: "red",
                    });
                    return;
                }

                applyBulkQuantity(frm, selectedRows, qty);
                dialog.hide();
            },
        });
        dialog.show();
    }

    function getSelectedItemRows(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (grid && typeof grid.get_selected_children === "function") {
            const rows = grid.get_selected_children() || [];
            if (rows.length) return rows;
        }

        let selectedNames = [];
        if (frm.get_selected) {
            const selected = frm.get_selected() || {};
            selectedNames = selected.items || [];
        }
        if (!selectedNames.length && grid && typeof grid.get_selected === "function") {
            selectedNames = grid.get_selected() || [];
        }

        if (!selectedNames.length) return [];
        return (frm.doc.items || []).filter((row) => selectedNames.includes(row.name));
    }

    function applyBulkQuantity(frm, rows, qty) {
        rows.forEach((row) => {
            frappe.model.set_value(row.doctype, row.name, "qty", qty);
        });
        frm.refresh_field("items");
        frm.dirty();
        frappe.show_alert({
            message: __("Updated quantity for {0} selected item row(s).", [rows.length]),
            indicator: "green",
        });
    }

    function addBulkDiscountButton(frm) {
        if (frm.__orderlift_bulk_discount_button_added || Number(frm.doc.docstatus || 0) !== 0) return;
        frm.__orderlift_bulk_discount_button_added = true;
        frm.add_custom_button(__("Bulk Discount"), () => openBulkDiscountDialog(frm), __("Items"));
    }

    function addBulkDiscountGridButton(frm) {
        if (Number(frm.doc.docstatus || 0) !== 0) return;
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper) return;
        const $wrapper = $(grid.wrapper);
        if ($wrapper.find("[data-orderlift-bulk-discount]").length || grid.__orderlift_bulk_discount_button_added) return;

        if (typeof grid.add_custom_button === "function") {
            const $button = grid.add_custom_button(__("Bulk Discount"), () => openBulkDiscountDialog(frm), "top");
            if ($button) $button.attr("data-orderlift-bulk-discount", "1").addClass("btn-secondary");
            grid.__orderlift_bulk_discount_button_added = true;
            return;
        }

        const $target = $wrapper.find(".grid-custom-buttons, .grid-add-multiple-rows").first();
        if (!$target.length) return;
        const $button = $(
            `<button type="button" class="btn btn-xs btn-secondary" data-orderlift-bulk-discount="1">${__("Bulk Discount")}</button>`
        );
        $button.on("click", (event) => {
            event.preventDefault();
            openBulkDiscountDialog(frm);
        });
        $target.prepend($button);
        grid.__orderlift_bulk_discount_button_added = true;
    }

    function openBulkDiscountDialog(frm) {
        const selectedRows = getSelectedItemRows(frm);
        const rows = selectedRows.length ? selectedRows : (frm.doc.items || []);
        if (!rows.length) {
            frappe.msgprint({
                title: __("No Items"),
                message: __("Add at least one item before applying a bulk discount."),
                indicator: "orange",
            });
            return;
        }

        const scope = selectedRows.length
            ? __("This will check {0} selected item row(s).", [rows.length])
            : __("No rows are selected, so this will check all {0} item row(s).", [rows.length]);
        const dialog = new frappe.ui.Dialog({
            title: __("Apply Discount to Items"),
            fields: [
                {
                    fieldname: "discount_percent",
                    fieldtype: "Percent",
                    label: __("Discount %"),
                    reqd: 1,
                    default: 0,
                    description: scope,
                },
            ],
            primary_action_label: __("Apply Discount"),
            async primary_action(values) {
                const discount = Number(values.discount_percent);
                if (!Number.isFinite(discount) || discount < 0 || discount > 100) {
                    frappe.msgprint({
                        title: __("Invalid Discount"),
                        message: __("Enter a discount from 0% to 100%."),
                        indicator: "red",
                    });
                    return;
                }
                dialog.get_primary_btn().prop("disabled", true);
                try {
                    await applyBulkDiscount(frm, rows, discount);
                    dialog.hide();
                } finally {
                    dialog.get_primary_btn().prop("disabled", false);
                }
            },
        });
        dialog.show();
    }

    async function applyBulkDiscount(frm, rows, discount) {
        const canOverride = canOverrideQuotationPricing();
        const applied = [];
        const skipped = [];
        const overrides = [];
        const missingRates = [];

        for (const row of rows) {
            const maxDiscount = Math.max(Number(row.source_max_discount_percent || 0), 0);
            const label = bulkDiscountRowLabel(row);
            if (!canOverride && discount > maxDiscount + 0.000001) {
                skipped.push(`${label} (${__("max {0}%", [displayQuotationNumber(maxDiscount)])})`);
                continue;
            }
            const listRate = quotationListRate(row);
            if (!listRate) {
                missingRates.push(label);
                continue;
            }
            if (canOverride && discount > maxDiscount + 0.000001) {
                overrides.push(`${label} (${__("max {0}%", [displayQuotationNumber(maxDiscount)])})`);
            }
            await applyResolvedRate(frm, row, listRate * (1 - discount / 100), { silent: true });
            applied.push(label);
        }

        syncItemTTCFields(frm);
        frm.refresh_field("items");
        frm.dirty();
        showBulkDiscountResult(discount, applied, skipped, overrides, missingRates);
    }

    function bulkDiscountRowLabel(row) {
        return String(row.item_code || row.item_name || row.name || __("Unnamed item"));
    }

    function showBulkDiscountResult(discount, applied, skipped, overrides, missingRates) {
        const sections = [
            `<p>${__("Applied {0}% to {1} row(s).", [displayQuotationNumber(discount), applied.length])}</p>`,
        ];
        if (skipped.length) sections.push(bulkDiscountResultList(__("Skipped below-cap rows"), skipped));
        if (overrides.length) sections.push(bulkDiscountResultList(__("Admin override applied above max"), overrides));
        if (missingRates.length) sections.push(bulkDiscountResultList(__("Skipped rows without a list price"), missingRates));
        frappe.msgprint({
            title: __("Bulk Discount Result"),
            message: sections.join(""),
            indicator: skipped.length || missingRates.length ? "orange" : "green",
        });
    }

    function bulkDiscountResultList(title, rows) {
        const items = rows.map((row) => `<li>${frappe.utils.escape_html(row)}</li>`).join("");
        return `<p><b>${frappe.utils.escape_html(title)}: ${rows.length}</b></p><ul>${items}</ul>`;
    }

    function scheduleQuotationStockSnapshotRefresh(frm) {
        // Disabled: the warehouse stock snapshot is now computed server-side at save
        // (orderlift_sales.quotation_hooks.populate_quotation_stock_snapshot). The old
        // client-side refresh rewrote a child table on form open and dirtied the form
        // in companies that had warehouse stock, hiding the Submit button. No-op now.
        return;
    }

    async function refreshQuotationStockSnapshot(frm) {
        if (!frm || frm.__orderlift_refreshing_stock_snapshot) return;
        const itemCodes = quotationItemCodes(frm);
        if (!itemCodes.length) {
            if (!shouldApplyStockSnapshot(frm)) return;
            setQuotationStockSnapshot(frm, [], {});
            return;
        }
        frm.__orderlift_refreshing_stock_snapshot = true;
        try {
            const response = await frappe.call({
                method: STOCK_SNAPSHOT_METHOD,
                args: { item_codes: JSON.stringify(itemCodes), company: frm.doc.company || "" },
            });
            const payload = response.message || {};
            if (!shouldApplyStockSnapshot(frm)) return;
            setQuotationStockSnapshot(frm, payload.rows || [], payload.totals || {});
        } catch (error) {
            console.error("Orderlift Quotation stock snapshot failed", error);
        } finally {
            frm.__orderlift_refreshing_stock_snapshot = false;
        }
    }

    function shouldApplyStockSnapshot(frm) {
        if (!frm || !frm.doc) return false;
        if (frm.is_new && frm.is_new()) return true;
        return Boolean(frm.doc.__unsaved);
    }

    function quotationItemCodes(frm) {
        const out = [];
        (frm.doc.items || []).forEach((row) => {
            const itemCode = String(row.item_code || "").trim();
            if (itemCode && !out.includes(itemCode)) out.push(itemCode);
        });
        return out;
    }

    function setQuotationStockSnapshot(frm, rows, totals) {
        const wasUnsaved = frm.doc && frm.doc.__unsaved;
        var tableChanged = false;
        var itemsChanged = false;
        if (frm.fields_dict.custom_warehouse_stock_snapshot) {
            tableChanged = syncQuotationStockSnapshotTable(frm, rows || []);
        }
        if (hasQuotationItemStockField(frm)) {
            (frm.doc.items || []).forEach((row) => {
                const itemCode = String(row.item_code || "").trim();
                const nextQty = Number((totals || {})[itemCode] || 0);
                if (Math.abs(Number(row.custom_current_company_stock_qty || 0) - nextQty) < 0.000001) return;
                row.custom_current_company_stock_qty = nextQty;
                itemsChanged = true;
            });
            if (itemsChanged) frm.refresh_field("items");
        }
        if ((tableChanged || itemsChanged) && !wasUnsaved && frm.doc) {
            frm.doc.__unsaved = 0;
            frm.wrapper && $(frm.wrapper).find(".indicator-pill.red, .indicator-pill.orange").remove();
        }
    }

    function syncQuotationStockSnapshotTable(frm, rows) {
        const fieldname = "custom_warehouse_stock_snapshot";
        const nextRows = (rows || []).map(normalizeStockSnapshotRow);
        if (stockSnapshotRowsMatch(frm.doc[fieldname] || [], nextRows)) return false;
        frappe.model.clear_table(frm.doc, fieldname);
        nextRows.forEach((values) => {
            const child = frappe.model.add_child(frm.doc, "Orderlift Transaction Warehouse Stock", fieldname);
            Object.assign(child, values);
        });
        frm.refresh_field(fieldname);
        return true;
    }

    function normalizeStockSnapshotRow(row) {
        return {
            item_code: row.item_code || "",
            item_name: row.item_name || "",
            warehouse: row.warehouse || "",
            actual_qty: Number(row.actual_qty || 0),
        };
    }

    function stockSnapshotRowsMatch(currentRows, nextRows) {
        const current = (currentRows || []).map(normalizeStockSnapshotRow);
        if (current.length !== nextRows.length) return false;
        return current.every((row, index) => {
            const next = nextRows[index] || {};
            return row.item_code === next.item_code
                && row.item_name === next.item_name
                && row.warehouse === next.warehouse
                && Math.abs(Number(row.actual_qty || 0) - Number(next.actual_qty || 0)) < 0.000001;
        });
    }

    function hasQuotationItemStockField(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        return quotationGridHasField(grid, "custom_current_company_stock_qty");
    }

    async function applyPricingDiscount(frm, row, options = {}) {
        if (!isDraftQuotation(frm)) return;
        if (!row) return;
        const listRate = quotationListRate(row);
        if (!listRate) return;
        const isAdmin = canOverrideQuotationPricing();
        const configuredMaxDiscount = Number(row.source_max_discount_percent || 0);
        const maxDiscount = isAdmin ? Infinity : configuredMaxDiscount;
        let discount = Number(row.source_discount_percent || 0);
        if (!Number.isFinite(discount) || discount < 0) discount = 0;
        if (!isAdmin && discount > maxDiscount) {
            discount = maxDiscount;
            if (!options.silent) {
                frappe.show_alert({
                    message: __("Discount capped at {0}% for {1}.", [maxDiscount.toFixed(2), row.item_code || row.item_name || row.name]),
                    indicator: "orange",
                });
            }
        }
        await applyResolvedRate(frm, row, listRate * (1 - discount / 100), { silent: true });
    }

    async function applyDiscountAmount(frm, row) {
        if (!isDraftQuotation(frm)) return;
        if (!row) return;
        const listRate = quotationListRate(row);
        if (!listRate) return;
        const isAdmin = canOverrideQuotationPricing();
        const configuredMaxDiscount = Number(row.source_max_discount_percent || 0);
        const maxDiscount = isAdmin ? Infinity : configuredMaxDiscount;
        let discountAmount = Number(row.source_discount_amount || 0);
        if (!Number.isFinite(discountAmount) || discountAmount < 0) discountAmount = 0;
        const maxAmount = Number.isFinite(maxDiscount) ? listRate * (maxDiscount / 100) : Infinity;
        if (!isAdmin && discountAmount > maxAmount) {
            discountAmount = maxAmount;
            frappe.show_alert({
                message: __("Discount amount capped at {0} for {1}.", [formatCurrency(maxAmount), row.item_code || row.item_name || row.name]),
                indicator: "orange",
            });
        }
        await applyResolvedRate(frm, row, listRate - discountAmount, { silent: true });
    }

    function isManualChargeRow(row) {
        return Boolean(row && MANUAL_CHARGE_ITEM_CODES.has(String(row.item_code || "").trim()));
    }

    async function applyManualChargeRate(frm, row, requestedRate) {
        if (!isDraftQuotation(frm)) return;
        if (!row) return;
        let rate = Number(requestedRate || 0);
        if (!Number.isFinite(rate) || rate < 0) rate = 0;
        const qty = Number(row.qty || 1) || 1;
        const amount = rate * qty;
        const totalTaxRate = quotationTotalTaxRate(frm);
        const puTtc = rate * (1 + totalTaxRate / 100);
        const ptTtc = amount * (1 + totalTaxRate / 100);
        const appliedTaxes = ptTtc - amount;
        beginQuotationPriceMutation(frm);
        try {
            const updates = [
                frappe.model.set_value(row.doctype, row.name, "price_list_rate", rate),
                frappe.model.set_value(row.doctype, row.name, "rate", rate),
                frappe.model.set_value(row.doctype, row.name, "amount", amount),
            ];
            if ("source_price_list_sell_rate" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "source_price_list_sell_rate", rate));
            if ("source_discount_percent" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "source_discount_percent", 0));
            if ("source_max_discount_percent" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "source_max_discount_percent", 100));
            if ("source_discount_amount" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "source_discount_amount", 0));
            if ("custom_applied_taxes" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "custom_applied_taxes", appliedTaxes));
            if ("custom_pu_ttc" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "custom_pu_ttc", puTtc));
            if ("custom_pt_ttc" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "custom_pt_ttc", ptTtc));
            await Promise.all(updates);
        } finally {
            endQuotationPriceMutation(frm);
        }
        frm.refresh_field("items");
        frm.dirty();
    }

    async function applyResolvedRate(frm, row, requestedRate, options = {}) {
        if (!isDraftQuotation(frm)) return;
        if (!row) return;
        const listRate = quotationListRate(row) || Number(requestedRate || 0);
        if (!listRate) return;
        const isAdmin = canOverrideQuotationPricing();
        const configuredMaxDiscount = Number(row.source_max_discount_percent || 0);
        const maxDiscount = isAdmin ? Infinity : configuredMaxDiscount;
        let rate = Number(requestedRate || 0);
        if (!Number.isFinite(rate) || rate < 0) rate = 0;
        const floor = Number.isFinite(maxDiscount) ? listRate * (1 - maxDiscount / 100) : 0;
        if (!isAdmin && floor > 0 && rate < floor) {
            rate = floor;
            if (!options.silent) {
                frappe.show_alert({
                    message: __("PU HT raised to minimum {0} for {1}.", [formatCurrency(floor), row.item_code || row.item_name || row.name]),
                    indicator: "orange",
                });
            }
        }
        const qty = Number(row.qty || 1) || 1;
        const amount = rate * qty;
        const totalTaxRate = quotationTotalTaxRate(frm);
        const puTtc = rate * (1 + totalTaxRate / 100);
        const ptTtc = amount * (1 + totalTaxRate / 100);
        const appliedTaxes = ptTtc - amount;
        const discount = rate >= listRate ? 0 : Math.max((1 - rate / listRate) * 100, 0);
        const discountAmount = rate >= listRate ? 0 : listRate - rate;
        beginQuotationPriceMutation(frm);
        try {
            row.rate = rate;
            row.amount = amount;
            if ("source_discount_amount" in row) row.source_discount_amount = discountAmount;
            if ("custom_applied_taxes" in row) row.custom_applied_taxes = appliedTaxes;
            if ("custom_pu_ttc" in row) row.custom_pu_ttc = puTtc;
            if ("custom_pt_ttc" in row) row.custom_pt_ttc = ptTtc;
            if ("discount_percentage" in row) row.discount_percentage = discount;
            const updates = [
                frappe.model.set_value(row.doctype, row.name, "source_discount_percent", discount),
                frappe.model.set_value(row.doctype, row.name, "rate", rate),
                frappe.model.set_value(row.doctype, row.name, "amount", amount),
            ];
            if ("source_discount_amount" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "source_discount_amount", discountAmount));
            if ("custom_applied_taxes" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "custom_applied_taxes", appliedTaxes));
            if ("custom_pu_ttc" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "custom_pu_ttc", puTtc));
            if ("custom_pt_ttc" in row) updates.push(frappe.model.set_value(row.doctype, row.name, "custom_pt_ttc", ptTtc));
            if (fieldExists(row.doctype, "source_commission_amount")) {
                updates.push(frappe.model.set_value(row.doctype, row.name, "source_commission_amount", commissionFor(rate, qty, discount, configuredMaxDiscount, row.source_commission_rate)));
            }
            await Promise.all(updates);
        } finally {
            endQuotationPriceMutation(frm);
        }
        frm.refresh_field("items");
        frm.dirty();
    }

    function refreshRowCommissionTotals(frm, row) {
        if (!isDraftQuotation(frm)) return;
        if (!row || isManualChargeRow(row)) return;
        const listRate = quotationListRate(row);
        const rate = Number(row.rate || 0);
        const qty = Number(row.qty || 1) || 1;
        if (!listRate) return;
        const discount = rate >= listRate ? 0 : Math.max((1 - rate / listRate) * 100, 0);
        if (fieldExists(row.doctype, "source_commission_amount")) {
            frappe.model.set_value(
                row.doctype,
                row.name,
                "source_commission_amount",
                commissionFor(rate, qty, discount, row.source_max_discount_percent, row.source_commission_rate)
            );
        }
    }

    function quotationListRate(row) {
        return Number(row.source_price_list_sell_rate || row.price_list_rate || 0);
    }

    function beginQuotationPriceMutation(frm) {
        frm.__orderlift_applying_quotation_price = true;
    }

    function endQuotationPriceMutation(frm) {
        window.setTimeout(function () {
            frm.__orderlift_applying_quotation_price = false;
        }, 0);
    }

    function formatCurrency(value) {
        if (frappe.format) return frappe.format(Number(value || 0), { fieldtype: "Currency", precision: 2 });
        return Number(value || 0).toFixed(2);
    }

    function fieldExists(doctype, fieldname) {
        if (!frappe.meta || !frappe.meta.has_field) return true;
        return Boolean(frappe.meta.has_field(doctype, fieldname));
    }

    function commissionFor(actualUnitPrice, qty, discountPercent, maxDiscountPercent, commissionRate) {
        const actualRate = Number(actualUnitPrice || 0);
        const quantity = Number(qty || 1) || 1;
        const unusedDiscount = Math.max(Number(maxDiscountPercent || 0) - Number(discountPercent || 0), 0);
        return actualRate * quantity * (unusedDiscount / 100) * (Number(commissionRate || 0) / 100);
    }

    function syncItemTTCFields(frm) {
        if (!isDraftQuotation(frm)) return;
        if (!frm.doc.items) return;
        var totalTaxRate = quotationTotalTaxRate(frm);
        var changed = false;
        beginQuotationPriceMutation(frm);
        try {
            (frm.doc.items || []).forEach(function (row) {
                if (!row || !("custom_pu_ttc" in row)) return;
                var rate = Number(row.rate || 0);
                var qty = Number(row.qty || 1) || 1;
                var amount = rate * qty;
                var puTtc = rate * (1 + totalTaxRate / 100);
                var ptTtc = amount * (1 + totalTaxRate / 100);
                var taxAmount = ptTtc - amount;
                // Only write when the value actually changes, so re-running this on
                // every refresh (incl. after save) does not perpetually re-dirty the
                // form due to float-precision differences vs the stored values.
                changed = setItemFieldIfChanged(row, "amount", amount) || changed;
                changed = setItemFieldIfChanged(row, "custom_applied_taxes", taxAmount) || changed;
                changed = setItemFieldIfChanged(row, "custom_pu_ttc", puTtc) || changed;
                changed = setItemFieldIfChanged(row, "custom_pt_ttc", ptTtc) || changed;
            });
        } finally {
            endQuotationPriceMutation(frm);
        }
        if (changed) frm.refresh_field("items");
    }

    async function recalculateQuotationTTC(frm, options = {}) {
        if (!isDraftQuotation(frm)) return false;

        const previous = frm.__orderlift_ttc_recalculation_queue || Promise.resolve();
        const scheduled = previous.catch(() => null).then(async () => {
            const template = String(frm.doc.taxes_and_charges || "").trim();
            const hasTaxes = Boolean((frm.doc.taxes || []).length);
            const shouldReloadTemplate = Boolean(template && (options.reloadTaxTemplate || !hasTaxes));

            if (
                shouldReloadTemplate
                && frm.cscript
                && typeof frm.cscript.taxes_and_charges === "function"
            ) {
                await Promise.resolve(frm.cscript.taxes_and_charges());
            }
            if (frm.cscript && typeof frm.cscript.calculate_taxes_and_totals === "function") {
                await Promise.resolve(frm.cscript.calculate_taxes_and_totals());
            }

            syncItemTTCFields(frm);
            ["items", "total", "net_total", "total_taxes_and_charges", "grand_total", "rounded_total"].forEach(
                (fieldname) => {
                    if (frm.fields_dict && frm.fields_dict[fieldname]) frm.refresh_field(fieldname);
                }
            );
            if (options.showAlert) {
                frappe.show_alert({ message: __("TTC values recalculated"), indicator: "green" });
            }
            return true;
        });
        frm.__orderlift_ttc_recalculation_queue = scheduled;
        return scheduled;
    }

    function scheduleItemTTCFieldsSync(frm, options = {}) {
        if (!isDraftQuotation(frm)) return;
        const revision = Number(frm.__orderlift_ttc_schedule_revision || 0) + 1;
        frm.__orderlift_ttc_schedule_revision = revision;
        const runLatest = function () {
            if (revision !== frm.__orderlift_ttc_schedule_revision) return;
            void recalculateQuotationTTC(frm, options);
        };
        if (typeof frappe.after_ajax === "function") {
            frappe.after_ajax(runLatest);
            return;
        }
        Promise.resolve().then(runLatest);
    }

    function setItemFieldIfChanged(row, field, value) {
        if (!(field in row)) return false;
        if (Math.abs(Number(row[field] || 0) - Number(value || 0)) < 1e-9) return false;
        frappe.model.set_value(row.doctype, row.name, field, value);
        return true;
    }

    function quotationTotalTaxRate(frm) {
        var taxes = frm.doc.taxes || [];
        var total = 0;
        taxes.forEach(function (t) {
            if (t.charge_type !== "Actual") {
                total += Number(t.rate || 0);
            }
        });
        return total;
    }
})();
