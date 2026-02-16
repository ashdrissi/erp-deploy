function statusBadge(value) {
    const status = value || "";
    const map = {
        OK: "green",
        "Too Low": "orange",
        "Too High": "red",
        "No Benchmark": "gray",
    };
    const color = map[status] || "blue";
    return `<span class="indicator-pill ${color}">${__(status || "-")}</span>`;
}

frappe.ui.form.on("Pricing Sheet", {
    setup(frm) {
        const queryConfig = () => ({
            query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.stock_item_query",
        });

        frm.set_query("item", "lines", queryConfig);
        frm.set_query("item_code", "lines", queryConfig);

        frm.fields_dict.lines.grid.get_field("benchmark_status").formatter = (value) => statusBadge(value);
    },

    refresh(frm) {
        frm.add_custom_button(__("Recalculate"), async () => {
            try {
                await frm.save();
                frm.refresh_field("lines");
                frappe.show_alert({ message: __("Pricing recalculated"), indicator: "green" });
            } catch (e) {
                frappe.msgprint({
                    title: __("Recalculation Failed"),
                    message: __("Unable to save and recalculate this Pricing Sheet."),
                    indicator: "red",
                });
            }
        });

        frm.add_custom_button(__("Refresh Buy Prices"), async () => {
            if (frm.is_dirty()) {
                await frm.save();
            }
            await frm.call("refresh_buy_prices");
            await frm.reload_doc();
            frappe.show_alert({ message: __("Buy prices refreshed"), indicator: "green" });
        });

        frm.add_custom_button(__("Add from Bundle"), () => {
            const dialog = new frappe.ui.Dialog({
                title: __("Add from Bundle"),
                fields: [
                    {
                        label: __("Product Bundle"),
                        fieldname: "product_bundle",
                        fieldtype: "Link",
                        options: "Product Bundle",
                        reqd: 1,
                        default: frm.doc.product_bundle,
                    },
                    {
                        label: __("Multiplier"),
                        fieldname: "multiplier",
                        fieldtype: "Float",
                        default: 1,
                    },
                    {
                        label: __("Replace Existing Lines"),
                        fieldname: "replace_existing_lines",
                        fieldtype: "Check",
                        default: 0,
                    },
                    {
                        label: __("Default Show In Detail"),
                        fieldname: "default_show_in_detail",
                        fieldtype: "Check",
                        default: 1,
                    },
                    {
                        label: __("Default Display Group Source"),
                        fieldname: "default_display_group_source",
                        fieldtype: "Select",
                        options: "Bundle Name\nItem Group",
                        default: "Item Group",
                    },
                ],
                primary_action_label: __("Add"),
                primary_action: async (values) => {
                    if (frm.is_dirty()) {
                        await frm.save();
                    }
                    await frm.call("add_from_bundle", values);
                    dialog.hide();
                    await frm.reload_doc();
                    frappe.show_alert({ message: __("Bundle items imported"), indicator: "green" });
                },
            });
            dialog.show();
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
            args: {
                item_code: row.item,
                pricing_scenario: frm.doc.pricing_scenario,
            },
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
