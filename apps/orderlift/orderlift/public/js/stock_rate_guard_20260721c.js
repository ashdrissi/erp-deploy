// Versioned asset: company-scoped rates and hidden zero-valuation bypass.
(function () {
    const CHILD_RATE_FIELDS = {
        "Stock Entry": [
            "basic_rate",
            "additional_cost",
            "landed_cost_voucher_amount",
            "valuation_rate",
            "allow_zero_valuation_rate",
            "set_basic_rate_manually",
            "basic_amount",
            "amount",
            "custom_suggested_rate",
            "custom_stock_rate_source_detail",
            "custom_rate_review_note",
            "custom_rate_reviewed_by",
            "custom_rate_reviewed_on",
        ],
        "Purchase Receipt": [
            "price_list_rate",
            "base_price_list_rate",
            "margin_rate_or_amount",
            "rate_with_margin",
            "discount_percentage",
            "discount_amount",
            "distributed_discount_amount",
            "base_rate_with_margin",
            "rate",
            "amount",
            "base_rate",
            "base_amount",
            "stock_uom_rate",
            "net_rate",
            "net_amount",
            "base_net_rate",
            "base_net_amount",
            "valuation_rate",
            "landed_cost_voucher_amount",
            "amount_difference_with_purchase_invoice",
            "allow_zero_valuation_rate",
            "custom_suggested_rate",
            "custom_stock_rate_source_detail",
            "custom_rate_review_note",
            "custom_rate_reviewed_by",
            "custom_rate_reviewed_on",
        ],
    };

    const PARENT_RATE_FIELDS = {
        "Stock Entry": [
            "get_stock_and_rate",
            "total_outgoing_value",
            "total_incoming_value",
            "value_difference",
            "additional_costs_section",
            "additional_costs",
            "total_additional_costs",
            "total_amount",
        ],
        "Purchase Receipt": [
            "currency_and_price_list",
            "buying_price_list",
            "price_list_currency",
            "plc_conversion_rate",
            "base_total",
            "base_net_total",
            "total",
            "net_total",
            "taxes",
            "totals",
            "base_total_taxes_and_charges",
            "total_taxes_and_charges",
            "totals_section",
            "grand_total",
            "rounded_total",
            "base_totals_section",
            "base_grand_total",
            "base_rounded_total",
            "base_discount_amount",
            "discount_amount",
        ],
    };

    const ALWAYS_HIDDEN_CHILD_FIELDS = ["allow_zero_valuation_rate"];

    function canManageRates() {
        const capabilities = frappe.boot && frappe.boot.orderlift_capabilities;
        return Boolean(capabilities && capabilities.stock_rate_access);
    }

    function configureRateVisibility(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (grid) {
            ALWAYS_HIDDEN_CHILD_FIELDS.forEach((fieldname) => {
                if (grid.get_field(fieldname)) grid.update_docfield_property(fieldname, "hidden", 1);
            });
        }
        if (canManageRates()) {
            if (grid) frm.refresh_field("items");
            return;
        }

        (PARENT_RATE_FIELDS[frm.doctype] || []).forEach((fieldname) => {
            if (frm.fields_dict[fieldname]) frm.set_df_property(fieldname, "hidden", 1);
        });

        if (!grid) return;
        (CHILD_RATE_FIELDS[frm.doctype] || []).forEach((fieldname) => {
            if (grid.get_field(fieldname)) grid.update_docfield_property(fieldname, "hidden", 1);
        });
        frm.refresh_field("items");
    }

    function showRateStatus(frm) {
        const status = frm.doc.custom_stock_rate_status;
        if (!status || status === "Not Required") return;
        const color = status === "Missing Rate" ? "orange" : status === "Provisional Rate" ? "blue" : "green";
        frm.dashboard.add_indicator(__(status), color);
    }

    function handleRefresh(frm) {
        configureRateVisibility(frm);
        showRateStatus(frm);
    }

    function preventMissingRateSubmit(frm) {
        if (frm.doc.custom_stock_rate_status !== "Missing Rate") return;
        frappe.validated = false;
        frappe.msgprint({
            title: __("Sent to Stock Rate Review"),
            indicator: "orange",
            message: __("Quantities are saved. A rate-capable user must complete the missing rates before this document can post stock."),
        });
    }

    function scheduleScopedStockRate(frm, cdt, cdn) {
        if (frm.doctype !== "Stock Entry" || frm.doc.purpose !== "Material Receipt") return;
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row || !row.item_code || !row.t_warehouse || row.s_warehouse || row.set_basic_rate_manually) return;

        frm.__orderliftRateTimers = frm.__orderliftRateTimers || {};
        clearTimeout(frm.__orderliftRateTimers[cdn]);
        frm.__orderliftRateTimers[cdn] = setTimeout(() => applyScopedStockRate(frm, cdt, cdn), 180);
    }

    async function applyScopedStockRate(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row || !row.item_code || row.set_basic_rate_manually) return;
        const requestId = `${row.item_code}:${row.t_warehouse}:${Date.now()}`;
        row.__orderliftRateRequestId = requestId;
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_logistics.utils.stock_rate_review.get_stock_entry_rate_suggestion",
                args: {
                    item_code: row.item_code,
                    company: frm.doc.company,
                    posting_date: frm.doc.posting_date,
                    uom: row.uom,
                    stock_uom: row.stock_uom,
                    conversion_factor: row.conversion_factor || 1,
                },
            });
            const current = locals[cdt] && locals[cdt][cdn];
            if (!current || current.__orderliftRateRequestId !== requestId || current.set_basic_rate_manually) return;
            const suggestion = response.message || {};
            const rate = Number(suggestion.rate || 0);
            const source = suggestion.source || (rate > 0 ? "Buying Price List" : "Missing");
            const status = rate > 0 ? "Provisional Rate" : "Missing Rate";
            if (Math.abs(Number(current.basic_rate || 0) - rate) > 0.000001) {
                await frappe.model.set_value(cdt, cdn, "basic_rate", rate);
            }
            await frappe.model.set_value(cdt, cdn, "custom_suggested_rate", rate);
            await frappe.model.set_value(cdt, cdn, "custom_stock_rate_source", source);
            await frappe.model.set_value(cdt, cdn, "custom_stock_rate_source_detail", suggestion.detail || "");
            await frappe.model.set_value(cdt, cdn, "custom_stock_rate_status", status);
            frm.set_value("custom_stock_rate_status", status);
        } catch (error) {
            console.error("Orderlift scoped stock rate lookup failed", error);
        }
    }

    ["Stock Entry", "Purchase Receipt"].forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            onload: configureRateVisibility,
            refresh: handleRefresh,
            before_submit: preventMissingRateSubmit,
            after_save(frm) {
                if (frm.doc.custom_stock_rate_status === "Missing Rate") {
                    frappe.show_alert({
                        message: __("Quantities saved and sent to Stock Rate Review."),
                        indicator: "orange",
                    });
                }
            },
        });
    });

    frappe.ui.form.on("Stock Entry Detail", {
        item_code: scheduleScopedStockRate,
        t_warehouse: scheduleScopedStockRate,
        uom: scheduleScopedStockRate,
        conversion_factor: scheduleScopedStockRate,
        basic_rate: scheduleScopedStockRate,
        set_basic_rate_manually: scheduleScopedStockRate,
    });
})();
