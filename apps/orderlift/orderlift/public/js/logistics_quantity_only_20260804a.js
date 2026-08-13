(function () {
    if (window.__orderliftLogisticsQuantityOnly20260804aRegistered) return;
    window.__orderliftLogisticsQuantityOnly20260804aRegistered = true;

    const DOCTYPES = ["Purchase Receipt", "Delivery Note", "Pick List"];

    const PARENT_PRICE_FIELDS = {
        "Purchase Receipt": [
            "currency_and_price_list",
            "currency",
            "conversion_rate",
            "buying_price_list",
            "price_list_currency",
            "plc_conversion_rate",
            "base_total",
            "base_net_total",
            "total",
            "net_total",
            "taxes_charges_section",
            "tax_category",
            "taxes_and_charges",
            "taxes_section",
            "taxes",
            "totals",
            "base_taxes_and_charges_added",
            "base_taxes_and_charges_deducted",
            "base_total_taxes_and_charges",
            "taxes_and_charges_added",
            "taxes_and_charges_deducted",
            "total_taxes_and_charges",
            "totals_section",
            "grand_total",
            "disable_rounded_total",
            "rounded_total",
            "base_totals_section",
            "base_grand_total",
            "base_rounded_total",
            "section_break_42",
            "apply_discount_on",
            "base_discount_amount",
            "additional_discount_percentage",
            "discount_amount",
            "sec_tax_breakup",
            "other_charges_calculation",
            "item_wise_tax_details",
            "per_billed",
        ],
        "Delivery Note": [
            "currency_and_price_list",
            "currency",
            "conversion_rate",
            "selling_price_list",
            "price_list_currency",
            "plc_conversion_rate",
            "custom_commercial_total",
            "base_total",
            "base_net_total",
            "total",
            "net_total",
            "taxes_section",
            "tax_category",
            "taxes_and_charges",
            "taxes",
            "base_total_taxes_and_charges",
            "total_taxes_and_charges",
            "totals_section",
            "grand_total",
            "disable_rounded_total",
            "rounded_total",
            "base_totals_section",
            "base_grand_total",
            "base_rounded_total",
            "section_break_49",
            "apply_discount_on",
            "base_discount_amount",
            "additional_discount_percentage",
            "discount_amount",
            "sec_tax_breakup",
            "other_charges_calculation",
            "item_wise_tax_details",
            "per_billed",
            "sales_team_section_break",
            "amount_eligible_for_commission",
            "commission_rate",
            "total_commission",
            "print_without_amount",
        ],
        "Pick List": [],
    };

    const CHILD_PRICE_FIELDS = {
        "Purchase Receipt": [
            "rate_and_amount",
            "price_list_rate",
            "base_price_list_rate",
            "discount_and_margin_section",
            "margin_type",
            "margin_rate_or_amount",
            "rate_with_margin",
            "discount_percentage",
            "discount_amount",
            "distributed_discount_amount",
            "base_rate_with_margin",
            "rate",
            "amount",
            "custom_pu_ttc",
            "custom_applied_taxes",
            "custom_pt_ttc",
            "base_rate",
            "base_amount",
            "stock_uom_rate",
            "net_rate",
            "net_amount",
            "item_tax_template",
            "base_net_rate",
            "base_net_amount",
            "valuation_rate",
            "custom_stock_rate_status",
            "custom_stock_rate_source",
            "custom_stock_rate_source_detail",
            "custom_suggested_rate",
            "custom_rate_review_note",
            "custom_rate_reviewed_by",
            "custom_rate_reviewed_on",
            "sales_incoming_rate",
            "item_tax_amount",
            "landed_cost_voucher_amount",
            "amount_difference_with_purchase_invoice",
            "allow_zero_valuation_rate",
            "item_tax_rate",
        ],
        "Delivery Note": [
            "price_list_rate",
            "base_price_list_rate",
            "discount_and_margin",
            "margin_type",
            "margin_rate_or_amount",
            "rate_with_margin",
            "discount_percentage",
            "discount_amount",
            "distributed_discount_amount",
            "base_rate_with_margin",
            "rate",
            "amount",
            "custom_pu_ttc",
            "custom_applied_taxes",
            "custom_pt_ttc",
            "base_rate",
            "base_amount",
            "stock_uom_rate",
            "grant_commission",
            "net_rate",
            "net_amount",
            "item_tax_template",
            "base_net_rate",
            "base_net_amount",
            "incoming_rate",
            "allow_zero_valuation_rate",
            "item_tax_rate",
        ],
        "Pick List": [],
    };

    function applyQuantityOnlyLayout(frm) {
        (PARENT_PRICE_FIELDS[frm.doctype] || []).forEach((fieldname) => {
            if (!frm.fields_dict?.[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 1);
        });

        const grid = frm.fields_dict?.items?.grid || frm.fields_dict?.locations?.grid;
        if (!grid || !grid.get_field) return;
        (CHILD_PRICE_FIELDS[frm.doctype] || []).forEach((fieldname) => {
            if (!grid.get_field(fieldname)) return;
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
            grid.update_docfield_property(fieldname, "columns", 0);
        });
        grid.refresh();
    }

    DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            setup: applyQuantityOnlyLayout,
            onload_post_render: applyQuantityOnlyLayout,
            refresh: applyQuantityOnlyLayout,
        });
    });
})();
