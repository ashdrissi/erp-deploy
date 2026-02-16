frappe.ui.form.on("Pricing Sheet", {
    setup(frm) {
        frm.set_query("item", "lines", () => ({
            query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.stock_item_query",
        }));
    },

    refresh(frm) {
        frm.add_custom_button(__("Recalculate"), async () => {
            try {
                await frm.save();
                frappe.show_alert({
                    message: __("Pricing recalculated"),
                    indicator: "green",
                });
            } catch (e) {
                frappe.msgprint({
                    title: __("Recalculation Failed"),
                    message: __("Unable to save and recalculate this Pricing Sheet."),
                    indicator: "red",
                });
            }
        });

        if (!frm.is_new()) {
            frm.page.set_primary_action(__("Generate Quotation"), async () => {
                try {
                    if (frm.is_dirty()) {
                        await frm.save();
                    }
                    const r = await frm.call("generate_quotation");
                    const quotationName = r.message;
                    if (!quotationName) {
                        frappe.throw(__("Quotation was not created."));
                    }
                    frappe.show_alert({
                        message: __("Quotation {0} created", [quotationName]),
                        indicator: "green",
                    });
                    frappe.set_route("Form", "Quotation", quotationName);
                } catch (e) {
                    frappe.msgprint({
                        title: __("Generation Failed"),
                        message: e.message || __("Unable to generate Quotation."),
                        indicator: "red",
                    });
                }
            });
        }
    },
});

frappe.ui.form.on("Pricing Sheet Item", {
    item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            return;
        }

        frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_item_pricing_defaults",
            args: { item_code: row.item },
            callback: (r) => {
                const data = r.message || {};
                frappe.model.set_value(cdt, cdn, "material", data.material || "OTHER");
                frappe.model.set_value(cdt, cdn, "weight_kg", data.weight_kg || 0);
                if (!row.buy_price || row.buy_price <= 0) {
                    frappe.model.set_value(cdt, cdn, "buy_price", data.buy_price || 0);
                }
            },
        });
    },
});
