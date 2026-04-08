frappe.ui.form.on("Portal Quote Request", {
    refresh(frm) {
        if (frm.is_new()) return;

        if (["Submitted", "Under Review"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Approve"), async () => {
                const values = await promptComment(__("Approve request"), __("Review comment"));
                if (!values) return;
                await frm.call("approve_request", { review_comment: values.review_comment || "" });
                await frm.reload_doc();
            });

            frm.add_custom_button(__("Reject"), async () => {
                const values = await promptComment(__("Reject request"), __("Review comment"), 1);
                if (!values) return;
                await frm.call("reject_request", { review_comment: values.review_comment || "" });
                await frm.reload_doc();
            });
        }

        if (["Submitted", "Under Review", "Approved"].includes(frm.doc.status) && !frm.doc.linked_quotation) {
            frm.add_custom_button(__("Create Quotation"), async () => {
                const r = await frm.call("create_quotation");
                const quotation = r.message;
                if (quotation) {
                    frappe.show_alert({ message: __("Quotation {0} created", [quotation]), indicator: "green" });
                    await frm.reload_doc();
                }
            }, __("Actions"));
        }
    },
});

function promptComment(title, label, required = 0) {
    return new Promise((resolve) => {
        const d = new frappe.ui.Dialog({
            title,
            fields: [{ fieldname: "review_comment", fieldtype: "Small Text", label, reqd: required }],
            primary_action_label: __("Submit"),
            primary_action(values) {
                d.hide();
                resolve(values);
            },
            secondary_action_label: __("Cancel"),
            secondary_action() {
                d.hide();
                resolve(null);
            },
        });
        d.show();
    });
}
