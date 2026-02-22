frappe.ui.form.on("Delivery Note", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Run Container Analysis"), async () => {
            const r = await frappe.call({
                method: "orderlift.logistics.utils.delivery_note_logistics.recompute_delivery_note_analysis",
                args: { delivery_note_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Running logistics analysis..."),
            });

            await frm.reload_doc();
            frappe.show_alert({
                message: __("Container analysis completed: {0}", [r.message.analysis]),
                indicator: "green",
            });
        });
    },
});
