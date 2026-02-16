frappe.ui.form.on("Pricing Sheet", {
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
                    const quotation_name = r.message;

                    if (!quotation_name) {
                        frappe.throw(__("Quotation was not created."));
                    }

                    frappe.show_alert({
                        message: __("Quotation {0} created", [quotation_name]),
                        indicator: "green",
                    });
                    frappe.set_route("Form", "Quotation", quotation_name);
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
