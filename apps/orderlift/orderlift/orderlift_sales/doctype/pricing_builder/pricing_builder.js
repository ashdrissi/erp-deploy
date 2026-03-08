frappe.ui.form.on("Pricing Builder", {
    refresh(frm) {
        frm.add_custom_button(__("Load Items & Calculate"), () => calculateBuilder(frm), __("Actions"));
        frm.add_custom_button(__("Publish Selected"), () => publishBuilder(frm, true), __("Actions"));
        frm.add_custom_button(__("Publish All"), () => publishBuilder(frm, false), __("Actions"));

        frm.set_query("item_group", () => ({ filters: {} }));
        frm.set_query("buying_price_list", "sourcing_rules", () => ({ filters: { buying: 1 } }));
        frm.set_query("pricing_scenario", "sourcing_rules", () => ({ filters: {} }));
        frm.set_query("customs_policy", "sourcing_rules", () => ({ filters: { is_active: 1 } }));
        frm.set_query("benchmark_policy", "sourcing_rules", () => ({ filters: { is_active: 1 } }));
    },
});

async function calculateBuilder(frm) {
    await frm.save();
    await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.calculate_builder_doc",
        args: { name: frm.doc.name },
        freeze: true,
        freeze_message: __("Calculating builder prices..."),
    });
    await frm.reload_doc();
}

async function publishBuilder(frm, selectedOnly) {
    if (!frm.doc.selling_price_list_name) {
        frappe.throw(__("Enter the Selling Price List Name before publishing."));
    }
    await frm.save();
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.publish_builder_doc",
        args: { name: frm.doc.name, selected_only: selectedOnly ? 1 : 0 },
        freeze: true,
        freeze_message: __("Publishing prices..."),
    });
    const out = response.message || {};
    frappe.show_alert({
        message: [
            __("Price List: {0}", [out.price_list || frm.doc.selling_price_list_name]),
            __("Created: {0}", [out.created || 0]),
            __("Updated: {0}", [out.updated || 0]),
            __("Skipped: {0}", [out.skipped || 0]),
        ].join(" | "),
        indicator: (out.errors || []).length ? "orange" : "green",
    }, 8);
    await frm.reload_doc();
}

frappe.ui.form.on("Pricing Builder Item", {
    override_selling_price(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const effectivePrice = flt(row.override_selling_price || 0) || flt(row.projected_price || 0);
        const buyPrice = flt(row.base_buy_price || 0);
        const marginPct = buyPrice > 0 ? ((effectivePrice - buyPrice) / buyPrice) * 100 : 0;
        frappe.model.set_value(cdt, cdn, "final_margin_pct", marginPct);
    },
});
