(function () {
    const NATIVE_UPLIFT_FIELDS = ["rate_with_margin", "margin_type", "margin_rate_or_amount"];
    const PROFITABILITY_FIELDS = [
        ["source_target_margin_percent", "Target Policy Margin %"],
        ["source_margin_percent", "Actual Margin %"],
        ["source_margin_basis", "Margin Basis"],
        ["source_base_buy_rate", "Base Buy Rate"],
        ["source_landed_cost", "Loaded Cost"],
    ];
    const PROFITABILITY_ROLES = new Set([
        "Administrator",
        "System Manager",
        "Orderlift Admin",
        "Orderlift Business Admin",
        "Pricing Manager",
    ]);

    function canViewProfitability() {
        const roles = Array.isArray(frappe.user_roles) && frappe.user_roles.length
            ? frappe.user_roles
            : (((frappe.boot || {}).user || {}).roles || []);
        return roles.some((role) => PROFITABILITY_ROLES.has(role));
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

        const visible = canViewProfitability();
        PROFITABILITY_FIELDS.forEach(([fieldname, label]) => {
            if (!grid.get_field(fieldname)) return;
            grid.update_docfield_property(fieldname, "label", __(label));
            grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1);
            grid.update_docfield_property(fieldname, "in_list_view", visible ? 1 : 0);
            grid.update_docfield_property(fieldname, "read_only", 1);
        });
        grid.refresh();
    }

    frappe.ui.form.on("Sales Order", {
        setup: applyPricingVisibility,
        onload_post_render: applyPricingVisibility,
        refresh: applyPricingVisibility,
    });
})();
