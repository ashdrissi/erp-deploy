(function () {
    const STOCK_SNAPSHOT_METHOD = "orderlift.orderlift_sales.utils.item_price_tools.get_transaction_stock_snapshot";

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

    const INTERNAL_ITEM_PRICE_FIELDS = ["price_list_rate", "rate"];

    const QUOTATION_ITEM_GRID_COLUMNS = [
        { fieldname: "item_code", columns: 2, sticky: 0 },
        { fieldname: "qty", columns: 1, sticky: 0 },
        { fieldname: "source_discounted_sell_rate", columns: 1, sticky: 0 },
        { fieldname: "amount", columns: 1, sticky: 0 },
        { fieldname: "source_max_discount_percent", columns: 1, sticky: 0 },
        { fieldname: "source_discount_percent", columns: 1, sticky: 0 },
        { fieldname: "source_discount_amount", columns: 1, sticky: 0 },
        { fieldname: "custom_pu_ttc", columns: 1, sticky: 0 },
        { fieldname: "custom_pt_ttc", columns: 1, sticky: 0 },
    ];

    const PRICE_OVERRIDE_ROLES = new Set(["Administrator", "System Manager", "Orderlift Admin", "Orderlift Business Admin"]);
    const MANUAL_PU_TTC_BY_ROW = new Map();
    const PRICE_SOURCE_BY_ROW = new Map();

    function canOverrideQuotationPricing() {
        const roles = frappe.user_roles || [];
        if (!roles.length && frappe.boot && frappe.boot.user && Array.isArray(frappe.boot.user.roles)) {
            return frappe.boot.user.roles.some(function (role) { return PRICE_OVERRIDE_ROLES.has(role); });
        }
        return roles.some(function (role) { return PRICE_OVERRIDE_ROLES.has(role); });
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
            scheduleItemTTCFieldsSync(frm);
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
            scheduleItemTTCFieldsSync(frm);
        },
    });

    frappe.ui.form.on("Quotation Item", {
        item_code(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        price_list_rate(frm) {
            scheduleItemTTCFieldsSync(frm);
        },
        source_gross_sell_rate(frm) {
            scheduleItemTTCFieldsSync(frm);
        },
        source_selling_price_list(frm) {
            scheduleItemTTCFieldsSync(frm);
        },
        source_discount_percent(frm, cdt, cdn) {
            if (frm.__orderlift_applying_quotation_price) return;
            rememberPriceSource(frappe.get_doc(cdt, cdn), "discount_percent");
            applyPricingDiscount(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
        },
        source_discount_amount(frm, cdt, cdn) {
            if (frm.__orderlift_applying_quotation_price) return;
            rememberPriceSource(frappe.get_doc(cdt, cdn), "discount_amount");
            applyDiscountAmount(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
        },
        qty(frm, cdt, cdn) {
            // Quantity only changes totals. Do not recalculate PU HT from the
            // rounded discount display, or manual prices drift by cents.
            syncItemTTCFields(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        rate(frm, cdt, cdn) {
            syncGrossRateIfNeeded(frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
        },
        source_discounted_sell_rate(frm, cdt, cdn) {
            if (frm.__orderlift_applying_quotation_price) return;
            rememberPriceSource(frappe.get_doc(cdt, cdn), "pu_ht");
            applyNetPriceFromOverride(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
            scheduleItemTTCFieldsSync(frm);
        },
        custom_pu_ttc(frm, cdt, cdn) {
            if (frm.__orderlift_applying_quotation_price) return;
            rememberPriceSource(frappe.get_doc(cdt, cdn), "pu_ttc");
            applyTTCPriceFromOverride(frm, frappe.get_doc(cdt, cdn));
            syncItemTTCFields(frm);
            scheduleItemTTCFieldsSync(frm);
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
        if (!frm || !frm.doc || Number(frm.doc.docstatus || 0) !== 0) return;
        const template = String(frm.doc.taxes_and_charges || "").trim();
        if (template) {
            // native ERPNext populates taxes and recalculates; sync TTC after
            setTimeout(function () { syncItemTTCFields(frm); }, 300);
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

    function applyOpportunityRouteOption(frm) {
        if (
            !frm || !frm.is_new || !frm.is_new() || !frm.fields_dict.opportunity
            || frm.doc.opportunity || frm.__orderlift_opportunity_route_applied
        ) return;
        const options = frappe.route_options || {};
        const opportunity = options.opportunity || "";
        if (!opportunity) return;
        frm.__orderlift_opportunity_route_applied = true;
        frm.set_value("opportunity", opportunity);
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

    function applyQuotationItemPricingLayout(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid) return;
        enforceQuotationItemGridColumns(frm);
        disableQuotationItemRowForms(frm);
        const isAdmin = canOverrideQuotationPricing();
        INTERNAL_ITEM_PRICE_FIELDS.forEach((fieldname) => {
            if (!grid.get_field || !grid.get_field(fieldname)) return;
            if (isAdmin) {
                grid.update_docfield_property(fieldname, "read_only", 0);
                grid.update_docfield_property(fieldname, "hidden", 0);
                grid.update_docfield_property(fieldname, "in_list_view", 1);
            } else {
                grid.update_docfield_property(fieldname, "read_only", 1);
                grid.update_docfield_property(fieldname, "hidden", 1);
                grid.update_docfield_property(fieldname, "in_list_view", 0);
            }
        });
        if (grid.get_field && grid.get_field("source_discounted_sell_rate")) {
            grid.update_docfield_property("source_discounted_sell_rate", "label", __("PU HT"));
            grid.update_docfield_property("source_discounted_sell_rate", "read_only", 0);
            grid.update_docfield_property("source_discounted_sell_rate", "hidden", 0);
            grid.update_docfield_property("source_discounted_sell_rate", "in_list_view", 1);
            grid.update_docfield_property("source_discounted_sell_rate", "precision", "2");
        }
        if (grid.get_field && grid.get_field("amount")) {
            grid.update_docfield_property("amount", "label", __("PT HT"));
            grid.update_docfield_property("amount", "read_only", 1);
            grid.update_docfield_property("amount", "hidden", 0);
            grid.update_docfield_property("amount", "in_list_view", 1);
        }
        if (grid.get_field && grid.get_field("source_discount_amount")) {
            grid.update_docfield_property("source_discount_amount", "label", __("Discount Amount HT"));
            grid.update_docfield_property("source_discount_amount", "read_only", 0);
            grid.update_docfield_property("source_discount_amount", "hidden", 0);
            grid.update_docfield_property("source_discount_amount", "in_list_view", 1);
            grid.update_docfield_property("source_discount_amount", "precision", "2");
        }
        if (grid.get_field && grid.get_field("custom_pu_ttc")) {
            grid.update_docfield_property("custom_pu_ttc", "label", __("PU TTC"));
            grid.update_docfield_property("custom_pu_ttc", "read_only", 0);
            grid.update_docfield_property("custom_pu_ttc", "hidden", 0);
            grid.update_docfield_property("custom_pu_ttc", "in_list_view", 1);
            grid.update_docfield_property("custom_pu_ttc", "precision", "2");
        }
        if (grid.get_field && grid.get_field("custom_pt_ttc")) {
            grid.update_docfield_property("custom_pt_ttc", "label", __("PT TTC"));
            grid.update_docfield_property("custom_pt_ttc", "read_only", 1);
            grid.update_docfield_property("custom_pt_ttc", "hidden", 0);
            grid.update_docfield_property("custom_pt_ttc", "in_list_view", 1);
            grid.update_docfield_property("custom_pt_ttc", "precision", "2");
        }
        if (grid.get_field && grid.get_field("source_max_discount_percent")) {
            grid.update_docfield_property("source_max_discount_percent", "label", __("Max Discount %"));
            grid.update_docfield_property("source_max_discount_percent", "hidden", 0);
            grid.update_docfield_property("source_max_discount_percent", "read_only", 1);
            grid.update_docfield_property("source_max_discount_percent", "in_list_view", 1);
        }
        if (grid.get_field && grid.get_field("source_margin_basis")) {
            grid.update_docfield_property("source_margin_basis", "label", __("Margin Basis"));
            grid.update_docfield_property("source_margin_basis", "hidden", 0);
            grid.update_docfield_property("source_margin_basis", "read_only", 1);
            grid.update_docfield_property("source_margin_basis", "in_list_view", 1);
        }
        if (grid.get_field && grid.get_field("source_margin_percent")) {
            grid.update_docfield_property("source_margin_percent", "label", __("Margin %"));
            grid.update_docfield_property("source_margin_percent", "hidden", 0);
            grid.update_docfield_property("source_margin_percent", "read_only", 1);
            grid.update_docfield_property("source_margin_percent", "in_list_view", 1);
        }
        if (grid.get_field && grid.get_field("source_discount_percent")) {
            grid.update_docfield_property("source_discount_percent", "label", __("Discount %"));
            grid.update_docfield_property("source_discount_percent", "hidden", 0);
            grid.update_docfield_property("source_discount_percent", "in_list_view", 1);
        }
        syncVisibleNetPriceFromRate(frm);
        grid.refresh();
        disableQuotationItemRowForms(frm);
    }

    function enforceQuotationItemGridColumns(frm) {
        const grid = frm && frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid) return;

        const gridViewSettings = frappe.model && frappe.model.user_settings
            ? (frappe.model.user_settings[frm.doctype] = frappe.model.user_settings[frm.doctype] || {})
            : null;
        if (gridViewSettings) {
            gridViewSettings.GridView = gridViewSettings.GridView || {};
            gridViewSettings.GridView[grid.doctype] = QUOTATION_ITEM_GRID_COLUMNS.map((column) => Object.assign({}, column));
        }

        (grid.docfields || []).forEach((df) => {
            if (!df || !df.fieldname) return;
            const column = QUOTATION_ITEM_GRID_COLUMNS.find((entry) => entry.fieldname === df.fieldname);
            if (column) {
                df.in_list_view = 1;
                df.columns = column.columns;
                df.sticky = column.sticky;
                if (["amount", "custom_pt_ttc"].includes(df.fieldname)) df.read_only = 1;
            } else {
                df.in_list_view = 0;
                df.columns = 0;
                df.sticky = 0;
            }
        });
        grid.visible_columns = [];
        grid.user_defined_columns = [];
    }

    function disableQuotationItemRowForms(frm) {
        const grid = frm && frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid) return;

        if (grid.df) grid.df.in_place_edit = 1;
        patchQuotationItemsGridRefresh(grid);
        applyInlineOnlyQuotationItemsGrid(grid);
    }

    function patchQuotationItemsGridRefresh(grid) {
        if (!grid || grid.__orderlift_inline_items_refresh_patched || typeof grid.refresh !== "function") return;
        const originalRefresh = grid.refresh.bind(grid);
        grid.refresh = function () {
            const result = originalRefresh.apply(grid, arguments);
            setTimeout(() => applyInlineOnlyQuotationItemsGrid(grid), 0);
            return result;
        };
        grid.__orderlift_inline_items_refresh_patched = true;
    }

    function applyInlineOnlyQuotationItemsGrid(grid) {
        if (!grid) return;
        if (grid.df) grid.df.in_place_edit = 1;
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
            if (gridRow.doc && gridRow.doc.doctype === "Quotation Item" && show !== false) {
                if (gridRow.grid && gridRow.grid.is_editable && gridRow.grid.is_editable() && typeof gridRow.toggle_editable_row === "function") {
                    gridRow.toggle_editable_row(true);
                }
                if (typeof callback === "function") callback();
                return gridRow;
            }
            return originalToggleView(show, callback);
        };
        if (gridRow.open_form_button) $(gridRow.open_form_button).closest(".col").hide();
        gridRow.__orderlift_inline_only_patched = true;
    }

    function ensureQuotationItemsGridStyles() {
        if (document.getElementById("orderlift-quotation-items-grid-style")) return;
        $("head").append(`
            <style id="orderlift-quotation-items-grid-style">
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

    function syncVisibleNetPriceFromRate(frm) {
        let changed = false;
        (frm.doc.items || []).forEach((row) => {
            if (!row || !("source_discounted_sell_rate" in row)) return;
            if (Number(row.source_discounted_sell_rate || 0)) return;
            const rate = Number(row.rate || 0);
            if (!rate) return;
            row.source_discounted_sell_rate = rate;
            changed = true;
        });
        if (changed) frm.refresh_field("items");
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

    function syncGrossRateIfNeeded(row) {
        if (!row || !("source_gross_sell_rate" in row)) return;
        if (Number(row.source_gross_sell_rate || 0)) return;
        frappe.model.set_value(row.doctype, row.name, "source_gross_sell_rate", Number(row.price_list_rate || row.rate || 0));
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
        return Boolean(grid && grid.get_field && grid.get_field("custom_current_company_stock_qty"));
    }

    function applyPricingDiscount(frm, row, options = {}) {
        if (!frm || !row) return;
        const gross = Number(row.source_gross_sell_rate || row.price_list_rate || row.rate || 0);
        if (!gross) return;
        const isAdmin = canOverrideQuotationPricing();
        const configuredMaxDiscount = Number(row.source_max_discount_percent || 0);
        const maxDiscount = isAdmin ? Infinity : configuredMaxDiscount;
        let discount = Number(row.source_discount_percent || 0);
        if (!Number.isFinite(discount) || discount < 0) discount = 0;
        if (!isAdmin && discount > maxDiscount) {
            discount = maxDiscount;
            if (!options.silent) {
                frappe.show_alert({
                    message: __("Discount capped at {0}% for {1}.", [maxDiscount.toFixed(1), row.item_code || row.item_name || row.name]),
                    indicator: "orange",
                });
            }
        }
        applyResolvedNetRate(frm, row, gross * (1 - discount / 100), { silent: true });
    }

    function applyDiscountAmount(frm, row) {
        if (!frm || !row) return;
        const gross = Number(row.source_gross_sell_rate || row.price_list_rate || row.rate || 0);
        if (!gross) return;
        const isAdmin = canOverrideQuotationPricing();
        const configuredMaxDiscount = Number(row.source_max_discount_percent || 0);
        const maxDiscount = isAdmin ? Infinity : configuredMaxDiscount;
        let discountAmount = Number(row.source_discount_amount || 0);
        if (!Number.isFinite(discountAmount) || discountAmount < 0) discountAmount = 0;
        const maxAmount = Number.isFinite(maxDiscount) ? gross * (maxDiscount / 100) : Infinity;
        if (!isAdmin && discountAmount > maxAmount) {
            discountAmount = maxAmount;
            frappe.show_alert({
                message: __("Discount amount capped at {0} for {1}.", [formatCurrency(maxAmount), row.item_code || row.item_name || row.name]),
                indicator: "orange",
            });
        }
        applyResolvedNetRate(frm, row, gross - discountAmount, { silent: true });
    }

    function applyNetPriceFromOverride(frm, row) {
        if (!frm || !row) return;
        const netRate = Number(row.source_discounted_sell_rate || 0);
        if (!netRate || netRate < 0) return;
        applyResolvedNetRate(frm, row, netRate);
    }

    function applyTTCPriceFromOverride(frm, row) {
        if (!frm || !row) return;
        const targetTTC = roundCurrency(row.custom_pu_ttc || 0);
        if (!targetTTC || targetTTC < 0) return;
        applyResolvedNetRate(frm, row, netRateFromTTC(targetTTC, quotationTotalTaxRate(frm)), { manualPuTtc: targetTTC });
    }

    function applyResolvedNetRate(frm, row, requestedNetRate, options = {}) {
        if (!frm || !row) return;
        const gross = Number(row.source_gross_sell_rate || row.price_list_rate || row.rate || requestedNetRate || 0);
        if (!gross) return;
        const isAdmin = canOverrideQuotationPricing();
        const configuredMaxDiscount = Number(row.source_max_discount_percent || 0);
        const maxDiscount = isAdmin ? Infinity : configuredMaxDiscount;
        let netRate = Number(requestedNetRate || 0);
        if (!Number.isFinite(netRate) || netRate < 0) netRate = 0;
        const floor = Number.isFinite(maxDiscount) ? roundCurrency(gross * (1 - maxDiscount / 100)) : 0;
        netRate = roundCurrency(netRate);
        if (!isAdmin && floor > 0 && netRate + 0.000001 < floor) {
            netRate = floor;
            if (!options.silent) {
                frappe.show_alert({
                    message: __("Net price raised to minimum {0} for {1}.", [formatCurrency(floor), row.item_code || row.item_name || row.name]),
                    indicator: "orange",
                });
            }
        }
        const qty = Number(row.qty || 1) || 1;
        const amount = roundCurrency(netRate * qty);
        const totalTaxRate = quotationTotalTaxRate(frm);
        const puTtc = roundCurrency(options.manualPuTtc || (netRate * (1 + totalTaxRate / 100)));
        const ptTtc = roundCurrency(puTtc * qty);
        const appliedTaxes = roundCurrency(ptTtc - amount);
        let discount = gross > 0 ? (1 - netRate / gross) * 100 : 0;
        discount = Math.max(0, discount);
        beginQuotationPriceMutation(frm);
        try {
            rememberManualPuTtc(row, options.manualPuTtc);
            row.rate = netRate;
            row.amount = amount;
            if ("source_discount_amount" in row) row.source_discount_amount = roundCurrency(Math.max(gross - netRate, 0));
            if ("source_discounted_sell_rate" in row) row.source_discounted_sell_rate = netRate;
            if ("custom_applied_taxes" in row) row.custom_applied_taxes = appliedTaxes;
            if ("custom_pu_ttc" in row) row.custom_pu_ttc = puTtc;
            if ("custom_pt_ttc" in row) row.custom_pt_ttc = ptTtc;
            if ("discount_percentage" in row) row.discount_percentage = discount;
            frappe.model.set_value(row.doctype, row.name, "source_discount_percent", discount);
            frappe.model.set_value(row.doctype, row.name, "rate", netRate);
            frappe.model.set_value(row.doctype, row.name, "amount", amount);
            if ("source_discount_amount" in row) frappe.model.set_value(row.doctype, row.name, "source_discount_amount", roundCurrency(Math.max(gross - netRate, 0)));
            if ("source_discounted_sell_rate" in row) frappe.model.set_value(row.doctype, row.name, "source_discounted_sell_rate", netRate);
            if ("custom_applied_taxes" in row) frappe.model.set_value(row.doctype, row.name, "custom_applied_taxes", appliedTaxes);
            if ("custom_pu_ttc" in row) frappe.model.set_value(row.doctype, row.name, "custom_pu_ttc", puTtc);
            if ("custom_pt_ttc" in row) frappe.model.set_value(row.doctype, row.name, "custom_pt_ttc", ptTtc);
            if (fieldExists(row.doctype, "source_commission_amount")) {
                frappe.model.set_value(row.doctype, row.name, "source_commission_amount", commissionFor(gross, qty, discount, configuredMaxDiscount, row.source_commission_rate));
            }
        } finally {
            endQuotationPriceMutation(frm);
        }
        frm.refresh_field("items");
        frm.dirty();
    }

    function rememberManualPuTtc(row, value) {
        if (!row || !row.name) return;
        if (!value) {
            MANUAL_PU_TTC_BY_ROW.delete(row.name);
            return;
        }
        MANUAL_PU_TTC_BY_ROW.set(row.name, roundCurrency(value));
        window.setTimeout(function () {
            MANUAL_PU_TTC_BY_ROW.delete(row.name);
        }, 2500);
    }

    function rememberPriceSource(row, source) {
        if (!row || !row.name || !source) return;
        PRICE_SOURCE_BY_ROW.set(row.name, source);
    }

    function beginQuotationPriceMutation(frm) {
        frm.__orderlift_applying_quotation_price = true;
    }

    function endQuotationPriceMutation(frm) {
        window.setTimeout(function () {
            frm.__orderlift_applying_quotation_price = false;
        }, 0);
    }

    function netRateFromTTC(targetTTC, taxRate) {
        const multiplier = 1 + (Number(taxRate || 0) / 100);
        if (!multiplier) return roundCurrency(targetTTC);
        const base = roundCurrency(Number(targetTTC || 0) / multiplier);
        let best = base;
        let bestDiff = Math.abs(roundCurrency(best * multiplier) - Number(targetTTC || 0));
        for (let cents = -3; cents <= 3; cents += 1) {
            const candidate = roundCurrency(base + (cents / 100));
            if (candidate < 0) continue;
            const diff = Math.abs(roundCurrency(candidate * multiplier) - Number(targetTTC || 0));
            if (diff < bestDiff) {
                best = candidate;
                bestDiff = diff;
            }
        }
        return best;
    }

    function formatCurrency(value) {
        if (frappe.format) return frappe.format(Number(value || 0), { fieldtype: "Currency" });
        return roundCurrency(value).toFixed(2);
    }

    function fieldExists(doctype, fieldname) {
        if (!frappe.meta || !frappe.meta.has_field) return true;
        return Boolean(frappe.meta.has_field(doctype, fieldname));
    }

    function commissionFor(rate, qty, discountPercent, maxDiscountPercent, commissionRate) {
        const grossTotal = Number(rate || 0) * (Number(qty || 1) || 1);
        const unusedDiscount = Math.max(Number(maxDiscountPercent || 0) - Number(discountPercent || 0), 0);
        return grossTotal * (unusedDiscount / 100) * (Number(commissionRate || 0) / 100);
    }

    function syncItemTTCFields(frm) {
        if (!frm || !frm.doc || !frm.doc.items) return;
        if (Number(frm.doc.docstatus || 0) !== 0) return;
        var totalTaxRate = quotationTotalTaxRate(frm);
        var changed = false;
        beginQuotationPriceMutation(frm);
        try {
            (frm.doc.items || []).forEach(function (row) {
                if (!row || !("custom_pu_ttc" in row)) return;
                var rate = Number(row.rate || 0);
                var qty = Number(row.qty || 1) || 1;
                var amount = roundCurrency(rate * qty);
                var manualPuTtc = MANUAL_PU_TTC_BY_ROW.get(row.name);
                var puTtc = roundCurrency(rate * (1 + totalTaxRate / 100));
                if (manualPuTtc && Math.abs(netRateFromTTC(manualPuTtc, totalTaxRate) - rate) < 0.02) {
                    puTtc = roundCurrency(manualPuTtc);
                }
                var ptTtc = roundCurrency(puTtc * qty);
                var taxAmount = roundCurrency(ptTtc - amount);
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

    function scheduleItemTTCFieldsSync(frm) {
        if (!frm || Number((frm.doc && frm.doc.docstatus) || 0) !== 0) return;
        [100, 500, 1200].forEach(function (delay) {
            window.setTimeout(function () {
                syncItemTTCFields(frm);
            }, delay);
        });
    }

    function roundCurrency(value) {
        return Math.round((Number(value) || 0) * 100) / 100;
    }

    function setItemFieldIfChanged(row, field, value) {
        if (!(field in row)) return false;
        if (Math.abs(Number(row[field] || 0) - Number(value || 0)) < 0.005) return false;
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
