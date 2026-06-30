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

    frappe.ui.form.on("Quotation", {
        setup(frm) {
            showOpportunityField(frm);
            hideNativeSourcePricingSheetField(frm);
            renderPricingSheetSourcePanel(frm);
            showTaxFields(frm);
            hideNativeDiscountAndTaxFields(frm);
            applyQuotationItemPricingLayout(frm);
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
        },
        refresh(frm) {
            showOpportunityField(frm);
            hideNativeSourcePricingSheetField(frm);
            renderPricingSheetSourcePanel(frm);
            showTaxFields(frm);
            applyOpportunityRouteOption(frm);
            hideNativeDiscountAndTaxFields(frm);
            applyQuotationItemPricingLayout(frm);
            setupOpportunityQuery(frm);
            setupTaxTemplateQuery(frm);
            addPricingSheetActionButtons(frm);
            addBulkQuantityButton(frm);
            addBulkQuantityGridButton(frm);
            scheduleQuotationStockSnapshotRefresh(frm);
        },
        items_add(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
        },
        items_remove(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
        },
        company(frm) {
            setupTaxTemplateQuery(frm);
            scheduleQuotationStockSnapshotRefresh(frm);
        },
        taxes_and_charges(frm) {
            applyTaxTemplateChange(frm);
        },
    });

    frappe.ui.form.on("Quotation Item", {
        item_code(frm) {
            scheduleQuotationStockSnapshotRefresh(frm);
        },
        source_discount_percent(frm, cdt, cdn) {
            applyPricingDiscount(frm, frappe.get_doc(cdt, cdn));
        },
        qty(frm, cdt, cdn) {
            applyPricingDiscount(frm, frappe.get_doc(cdt, cdn), { silent: true });
        },
        rate(frm, cdt, cdn) {
            syncGrossRateIfNeeded(frappe.get_doc(cdt, cdn));
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
        if (template) return;  // native ERPNext populates taxes from template
        // Cleared or emptied: zero-out taxes immediately
        frm.doc.taxes = [];
        frm.doc.total_taxes_and_charges = 0;
        frm.doc.base_total_taxes_and_charges = 0;
        frm.refresh_field("taxes");
        frm.refresh_field("total_taxes_and_charges");
        frm.refresh_field("base_total_taxes_and_charges");
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
        INTERNAL_ITEM_PRICE_FIELDS.forEach((fieldname) => {
            if (!grid.get_field || !grid.get_field(fieldname)) return;
            grid.update_docfield_property(fieldname, "read_only", 1);
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
        });
        if (grid.get_field && grid.get_field("source_discounted_sell_rate")) {
            grid.update_docfield_property("source_discounted_sell_rate", "label", __("Net Price HT"));
            grid.update_docfield_property("source_discounted_sell_rate", "read_only", 1);
            grid.update_docfield_property("source_discounted_sell_rate", "hidden", 0);
            grid.update_docfield_property("source_discounted_sell_rate", "in_list_view", 1);
        }
        syncVisibleNetPriceFromRate(frm);
        grid.refresh();
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
        frm.add_custom_button(__("Bulk Quantity"), () => openBulkQuantityDialog(frm), __("Items"));
    }

    function addBulkQuantityGridButton(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper) return;

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
            return;
        }

        const $wrapper = $(grid.wrapper);
        if ($wrapper.find("[data-orderlift-bulk-quantity]").length) return;

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
        if (!frm || !frm.fields_dict) return;
        if (!frm.fields_dict.custom_warehouse_stock_snapshot && !hasQuotationItemStockField(frm)) return;
        window.clearTimeout(frm.__orderlift_stock_snapshot_timer);
        frm.__orderlift_stock_snapshot_timer = window.setTimeout(() => refreshQuotationStockSnapshot(frm), 150);
    }

    async function refreshQuotationStockSnapshot(frm) {
        if (!frm || frm.__orderlift_refreshing_stock_snapshot) return;
        const itemCodes = quotationItemCodes(frm);
        if (!itemCodes.length) {
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
            setQuotationStockSnapshot(frm, payload.rows || [], payload.totals || {});
        } catch (error) {
            console.error("Orderlift Quotation stock snapshot failed", error);
        } finally {
            frm.__orderlift_refreshing_stock_snapshot = false;
        }
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
        if (frm.fields_dict.custom_warehouse_stock_snapshot) {
            frm.doc.custom_warehouse_stock_snapshot = (rows || []).map((row, index) => ({
                doctype: "Orderlift Transaction Warehouse Stock",
                parenttype: "Quotation",
                parentfield: "custom_warehouse_stock_snapshot",
                parent: frm.doc.name,
                idx: index + 1,
                item_code: row.item_code || "",
                item_name: row.item_name || "",
                warehouse: row.warehouse || "",
                actual_qty: Number(row.actual_qty || 0),
            }));
            frm.refresh_field("custom_warehouse_stock_snapshot");
        }
        if (hasQuotationItemStockField(frm)) {
            (frm.doc.items || []).forEach((row) => {
                const itemCode = String(row.item_code || "").trim();
                row.custom_current_company_stock_qty = Number((totals || {})[itemCode] || 0);
            });
            frm.refresh_field("items");
        }
    }

    function hasQuotationItemStockField(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        return Boolean(grid && grid.get_field && grid.get_field("custom_current_company_stock_qty"));
    }

    function applyPricingDiscount(frm, row, options = {}) {
        if (!frm || !row) return;
        const gross = Number(row.source_gross_sell_rate || row.price_list_rate || row.rate || 0);
        if (!gross) return;
        const maxDiscount = Number(row.source_max_discount_percent || 0);
        let discount = Number(row.source_discount_percent || 0);
        if (!Number.isFinite(discount) || discount < 0) discount = 0;
        if (discount > maxDiscount) {
            discount = maxDiscount;
            frappe.model.set_value(row.doctype, row.name, "source_discount_percent", discount);
            if (!options.silent) {
                frappe.show_alert({
                    message: __("Discount capped at {0}% for {1}.", [maxDiscount.toFixed(1), row.item_code || row.item_name || row.name]),
                    indicator: "orange",
                });
            }
        }
        const qty = Number(row.qty || 1) || 1;
        const netRate = gross * (1 - discount / 100);
        frappe.model.set_value(row.doctype, row.name, "discount_percentage", discount);
        frappe.model.set_value(row.doctype, row.name, "rate", netRate);
        frappe.model.set_value(row.doctype, row.name, "amount", netRate * qty);
        if ("source_discount_amount" in row) frappe.model.set_value(row.doctype, row.name, "source_discount_amount", gross - netRate);
        if ("source_discounted_sell_rate" in row) frappe.model.set_value(row.doctype, row.name, "source_discounted_sell_rate", netRate);
        if (fieldExists(row.doctype, "source_commission_amount")) {
            frappe.model.set_value(row.doctype, row.name, "source_commission_amount", commissionFor(gross, qty, discount, maxDiscount, row.source_commission_rate));
        }
        frm.refresh_field("items");
        frm.dirty();
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
})();
