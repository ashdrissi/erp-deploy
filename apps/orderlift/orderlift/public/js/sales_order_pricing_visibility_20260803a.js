(function () {
    const NATIVE_UPLIFT_FIELDS = ["rate_with_margin", "margin_type", "margin_rate_or_amount"];
    const DUPLICATE_NATIVE_PRICE_FIELDS = ["price_list_rate", "discount_percentage", "discount_amount", "net_rate", "net_amount"];
    const DISPLAY_CURRENCY_FIELDS = new Set([
        "source_price_list_sell_rate",
        "rate",
        "source_discount_amount",
        "amount",
        "source_commission_amount",
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
    const DISPLAY_FLOAT_FIELDS = new Set(["qty", "stock_qty", "conversion_factor"]);
    const DISPLAY_NUMERIC_FIELDS = new Set([
        ...DISPLAY_CURRENCY_FIELDS,
        ...DISPLAY_PERCENT_FIELDS,
        ...DISPLAY_FLOAT_FIELDS,
    ]);
    const COMMERCIAL_PRICING_FIELDS = [
        ["source_price_list_sell_rate", "PU List HT", true],
        ["rate", "PU HT", true],
        ["source_max_discount_percent", "Max Discount %", false],
        ["source_discount_percent", "Remise %", false],
        ["source_discount_amount", "Remise PU HT", true],
        ["amount", "PT HT", true],
        ["source_commission_rate", "Commission %", false],
        ["source_commission_amount", "Commission", true],
        ["custom_pu_ttc", "PU TTC", true],
        ["custom_pt_ttc", "PT TTC", true],
    ];
    const PROFITABILITY_FIELDS = [
        ["source_target_margin_percent", "Target Policy Margin %", true],
        ["source_margin_percent", "Actual Margin %", true],
        ["source_base_buy_rate", "Base Buy Rate", false],
        ["source_landed_cost", "Loaded Cost", false],
    ];
    const COMMERCIAL_PARENT_FIELDS = [
        "base_discount_amount",
        "base_grand_total",
        "base_in_words",
        "base_net_total",
        "base_rounded_total",
        "base_total",
        "base_total_taxes_and_charges",
        "discount_amount",
        "grand_total",
        "in_words",
        "net_total",
        "rounded_total",
        "total",
        "total_commission",
        "total_taxes_and_charges",
    ];
    const COMMERCIAL_TABLE_FIELDS = ["taxes", "payment_schedule"];

    function canViewProfitability() {
        return Boolean(frappe.boot?.orderlift_capabilities?.privileged_pricing);
    }

    function canViewCommercialPrices() {
        return canDoctypePermission("write") || canDoctypePermission("create");
    }

    function canDoctypePermission(permissionType) {
        if (frappe.model && typeof frappe.model.can_write === "function" && permissionType === "write") {
            return Boolean(frappe.model.can_write("Sales Order"));
        }
        if (frappe.model && typeof frappe.model.can_create === "function" && permissionType === "create") {
            return Boolean(frappe.model.can_create("Sales Order"));
        }
        if (frappe.perm && typeof frappe.perm.has_perm === "function") {
            return Boolean(frappe.perm.has_perm("Sales Order", 0, permissionType));
        }
        return false;
    }

    function canOverridePaymentTerms() {
        return Boolean(frappe.boot?.orderlift_capabilities?.quotation_override);
    }

    async function loadPaymentTermsPolicy(frm) {
        if (frm.__orderliftPaymentTermsPolicyLoading) return frm.__orderliftPaymentTermsPolicyLoading;
        frm.__orderliftPaymentTermsPolicyLoading = frappe.call({
            method: "orderlift.orderlift_sales.payment_terms_policy.get_sales_order_payment_terms_policy",
            args: { sales_order: frm.is_new() ? "" : frm.doc.name },
        }).then(async (response) => {
            const policy = response.message || {};
            frm.__orderliftPaymentTermsPolicy = {
                canOverride: Boolean(policy.can_override),
                allowedTemplates: policy.allowed_templates || [],
                defaultTemplate: policy.default_template || "",
            };
            applyPaymentTermsVisibility(frm);
            if (!policy.can_override && !frm.doc.payment_terms_template && policy.default_template && frm.is_new()) {
                await frm.set_value("payment_terms_template", policy.default_template);
            }
            return frm.__orderliftPaymentTermsPolicy;
        }).finally(() => {
            frm.__orderliftPaymentTermsPolicyLoading = null;
        });
        return frm.__orderliftPaymentTermsPolicyLoading;
    }

    function paymentTermsQuery(frm) {
        const policy = frm.__orderliftPaymentTermsPolicy;
        if (!policy || policy.canOverride) return {};
        return { filters: { name: ["in", policy.allowedTemplates.length ? policy.allowedTemplates : [""]] } };
    }

    function applyPaymentTermsVisibility(frm) {
        const canOverride = frm.__orderliftPaymentTermsPolicy?.canOverride ?? canOverridePaymentTerms();
        const grid = frm.fields_dict?.payment_schedule?.grid;
        frm.set_df_property("payment_schedule", "read_only", canOverride ? 0 : 1);
        if (!grid) return;
        grid.cannot_add_rows = !canOverride;
        grid.cannot_delete_rows = !canOverride;
        (grid.docfields || []).forEach((field) => {
            grid.update_docfield_property(field.fieldname, "read_only", canOverride ? (field.read_only || 0) : 1);
        });
        grid.refresh();
    }

    function applyPricingVisibility(frm) {
        applyDocumentPricingVisibility(frm);

        const grid = frm && frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.get_field) return;

        patchSalesOrderGridRefresh(grid);

        NATIVE_UPLIFT_FIELDS.forEach((fieldname) => {
            if (!grid.get_field(fieldname)) return;
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
        });

        DUPLICATE_NATIVE_PRICE_FIELDS.forEach((fieldname) => {
            if (!grid.get_field(fieldname)) return;
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
        });

        const commercialVisible = canViewCommercialPrices();
        COMMERCIAL_PRICING_FIELDS.forEach(([fieldname, label, isCurrency]) => {
            const field = grid.get_field(fieldname);
            if (!field) return;
            grid.update_docfield_property(fieldname, "label", __(label));
            grid.update_docfield_property(fieldname, "hidden", commercialVisible ? 0 : 1);
            grid.update_docfield_property(fieldname, "in_list_view", commercialVisible ? 1 : 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
            grid.update_docfield_property(fieldname, "precision", "9");
            field.formatter = isCurrency
                ? (value) => formatSalesOrderCurrency(value)
                : (value) => `${displaySalesOrderInputNumber(value)}%`;
        });

        ["source_selling_price_list", "custom_applied_taxes", "source_margin_basis"].forEach((fieldname) => {
            const field = grid.get_field(fieldname);
            if (!field) return;
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
        });

        const visible = commercialVisible && canViewProfitability();
        PROFITABILITY_FIELDS.forEach(([fieldname, label, isPercent]) => {
            const field = grid.get_field(fieldname);
            if (!field) return;
            grid.update_docfield_property(fieldname, "label", __(label));
            grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1);
            grid.update_docfield_property(fieldname, "in_list_view", visible ? 1 : 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
            grid.update_docfield_property(fieldname, "precision", "9");
            field.formatter = isPercent
                ? (value) => `${displaySalesOrderInputNumber(value)}%`
                : (value) => formatSalesOrderCurrency(value);
        });

        DISPLAY_FLOAT_FIELDS.forEach((fieldname) => {
            const field = grid.get_field(fieldname);
            if (field) field.formatter = (value) => displaySalesOrderInputNumber(value);
        });

        grid.refresh();
        scheduleSalesOrderPrecisionDisplay(grid);
    }

    function applyDocumentPricingVisibility(frm) {
        if (!frm || !frm.fields_dict) return;
        const commercialVisible = canViewCommercialPrices();
        COMMERCIAL_PARENT_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", commercialVisible ? 0 : 1);
        });
        COMMERCIAL_TABLE_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", commercialVisible ? 0 : 1);
        });
    }

    function patchSalesOrderGridRefresh(grid) {
        if (!grid || grid.__orderlift_sales_order_precision_patched || typeof grid.refresh !== "function") return;
        const originalRefresh = grid.refresh.bind(grid);
        grid.refresh = function () {
            const result = originalRefresh.apply(grid, arguments);
            scheduleSalesOrderPrecisionDisplay(grid);
            return result;
        };
        grid.__orderlift_sales_order_precision_patched = true;
    }

    function scheduleSalesOrderPrecisionDisplay(grid) {
        window.setTimeout(() => applySalesOrderPrecisionDisplay(grid), 0);
        window.setTimeout(() => applySalesOrderPrecisionDisplay(grid), 80);
        window.setTimeout(() => applySalesOrderPrecisionDisplay(grid), 250);
    }

    function applySalesOrderPrecisionDisplay(grid) {
        if (!grid || !grid.wrapper) return;
        (grid.grid_rows || []).forEach((gridRow) => applySalesOrderPrecisionGridRowDisplay(gridRow));

        const $wrapper = $(grid.wrapper);
        DISPLAY_NUMERIC_FIELDS.forEach((fieldname) => {
            $wrapper.find(`[data-fieldname="${fieldname}"] input`).each((_, input) => {
                const row = salesOrderRowForInput(grid, input);
                if (row) applySalesOrderPrecisionInput(input, row, fieldname);
            });
        });
    }

    function applySalesOrderPrecisionGridRowDisplay(gridRow) {
        if (!gridRow || !gridRow.doc) return;
        DISPLAY_NUMERIC_FIELDS.forEach((fieldname) => {
            const column = gridRow.columns && gridRow.columns[fieldname];
            if (column) {
                if (column.field_area) {
                    $(column.field_area).find("input").each((_, input) => {
                        applySalesOrderPrecisionInput(input, gridRow.doc, fieldname);
                    });
                }
                if (column.static_area) {
                    applySalesOrderPrecisionStatic($(column.static_area), gridRow.doc, fieldname);
                }
                if (column.field && column.field.$input) {
                    column.field.$input.each((_, input) => applySalesOrderPrecisionInput(input, gridRow.doc, fieldname));
                }
            }
            if (gridRow.row) {
                const $cell = $(gridRow.row).find(`[data-fieldname="${fieldname}"]`);
                $cell.find("input").each((_, input) => applySalesOrderPrecisionInput(input, gridRow.doc, fieldname));
                applySalesOrderPrecisionStatic($cell.find(".static-area, .ellipsis"), gridRow.doc, fieldname);
            }
        });
    }

    function salesOrderRowForInput(grid, input) {
        const $input = $(input);
        const rowName = $input.closest(".grid-row").attr("data-name") || $input.closest("[data-name]").attr("data-name");
        if (rowName && typeof locals !== "undefined" && locals["Sales Order Item"] && locals["Sales Order Item"][rowName]) {
            return locals["Sales Order Item"][rowName];
        }
        const element = input;
        return (grid.grid_rows || []).map((gridRow) => gridRow && gridRow.doc ? gridRow : null).find((gridRow) => {
            if (!gridRow) return false;
            const rawRowNode = gridRow.row || gridRow.wrapper;
            const rowNode = rawRowNode && rawRowNode.jquery ? rawRowNode[0] : rawRowNode;
            return rowNode && $.contains(rowNode, element);
        })?.doc;
    }

    function applySalesOrderPrecisionInput(input, row, fieldname) {
        if (!input || !row) return;
        const $input = $(input);
        if (!$input.data("orderliftPrecisionDisplayBound")) {
            $input.data("orderliftPrecisionDisplayBound", 1);
            $input.on("focus.orderliftPrecisionDisplay", () => {
                input.dataset.orderliftUserEditing = "0";
                input.value = displaySalesOrderInputNumber(row[fieldname]);
                input.select();
            });
            $input.on("input.orderliftPrecisionDisplay", () => {
                input.dataset.orderliftUserEditing = "1";
            });
            $input.on("blur.orderliftPrecisionDisplay", () => {
                window.setTimeout(() => {
                    input.dataset.orderliftUserEditing = "0";
                    input.value = displaySalesOrderInputNumber(row[fieldname]);
                }, 0);
            });
        }
        if (document.activeElement !== input || input.dataset.orderliftUserEditing !== "1") {
            input.value = displaySalesOrderInputNumber(row[fieldname]);
        }
    }

    function applySalesOrderPrecisionStatic($targets, row, fieldname) {
        if (!$targets || !$targets.length || !row) return;
        $targets.each((_, target) => {
            const $target = $(target);
            if ($target.find("input, select, textarea").length) return;
            if (DISPLAY_CURRENCY_FIELDS.has(fieldname)) {
                $target.html(formatSalesOrderCurrency(row[fieldname]));
            } else {
                const value = displaySalesOrderInputNumber(row[fieldname]);
                $target.text(DISPLAY_PERCENT_FIELDS.has(fieldname) ? `${value}%` : value);
            }
        });
    }

    function displaySalesOrderInputNumber(value) {
        return Number(value || 0).toFixed(2);
    }

    function formatSalesOrderCurrency(value) {
        if (frappe.format) return frappe.format(Number(value || 0), { fieldtype: "Currency", precision: 2 });
        return displaySalesOrderInputNumber(value);
    }

    frappe.ui.form.on("Sales Order", {
        setup(frm) {
            frm.set_query("payment_terms_template", () => paymentTermsQuery(frm));
            applyPricingVisibility(frm);
            loadPaymentTermsPolicy(frm);
        },
        onload_post_render(frm) {
            applyPricingVisibility(frm);
            applyPaymentTermsVisibility(frm);
        },
        refresh(frm) {
            applyPricingVisibility(frm);
            applyPaymentTermsVisibility(frm);
            loadPaymentTermsPolicy(frm);
        },
    });
})();
