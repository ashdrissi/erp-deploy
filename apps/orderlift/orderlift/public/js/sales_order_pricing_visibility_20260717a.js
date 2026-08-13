(function () {
    const NATIVE_UPLIFT_FIELDS = ["rate_with_margin", "margin_type", "margin_rate_or_amount"];
    const DUPLICATE_NATIVE_PRICE_FIELDS = ["price_list_rate", "discount_percentage", "discount_amount", "net_rate", "net_amount"];
    const DISPLAY_PERCENT_FIELDS = new Set(["source_max_discount_percent", "source_discount_percent", "source_commission_rate"]);
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
    function canViewProfitability() {
        return Boolean(frappe.boot?.orderlift_capabilities?.privileged_pricing);
    }

    function applyPricingVisibility(frm) {
        const grid = frm && frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.get_field) return;

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

        COMMERCIAL_PRICING_FIELDS.forEach(([fieldname, label, isCurrency]) => {
            const field = grid.get_field(fieldname);
            if (!field) return;
            grid.update_docfield_property(fieldname, "label", __(label));
            grid.update_docfield_property(fieldname, "hidden", 0);
            grid.update_docfield_property(fieldname, "in_list_view", 1);
            grid.update_docfield_property(fieldname, "read_only", 1);
            if (isCurrency) {
                grid.update_docfield_property(fieldname, "precision", "9");
                field.formatter = (value) => frappe.format(Number(value || 0), { fieldtype: "Currency", precision: 2 });
            } else if (DISPLAY_PERCENT_FIELDS.has(fieldname)) {
                grid.update_docfield_property(fieldname, "precision", "9");
                field.formatter = (value) => `${Number(value || 0).toFixed(2)}%`;
            }
        });

        ["source_selling_price_list", "custom_applied_taxes", "source_margin_basis"].forEach((fieldname) => {
            const field = grid.get_field(fieldname);
            if (!field) return;
            grid.update_docfield_property(fieldname, "hidden", 1);
            grid.update_docfield_property(fieldname, "in_list_view", 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
        });

        const visible = canViewProfitability();
        PROFITABILITY_FIELDS.forEach(([fieldname, label, isPercent]) => {
            const field = grid.get_field(fieldname);
            if (!field) return;
            grid.update_docfield_property(fieldname, "label", __(label));
            grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1);
            grid.update_docfield_property(fieldname, "in_list_view", visible ? 1 : 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
            grid.update_docfield_property(fieldname, "precision", "9");
            field.formatter = isPercent
                ? (value) => `${Number(value || 0).toFixed(2)}%`
                : (value) => frappe.format(Number(value || 0), { fieldtype: "Currency", precision: 2 });
        });
        const qty = grid.get_field("qty");
        if (qty) qty.formatter = (value) => Number(value || 0).toFixed(2);
        grid.refresh();
    }

    frappe.ui.form.on("Sales Order", {
        setup: applyPricingVisibility,
        onload_post_render: applyPricingVisibility,
        refresh: applyPricingVisibility,
    });
})();
