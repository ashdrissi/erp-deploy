frappe.ui.form.on("Party Company Access Request", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.status !== "Pending") return;
        frm.add_custom_button(__("Approve"), () => review(frm, "approve_request"), __("Review"));
        frm.add_custom_button(__("Reject"), () => review(frm, "reject_request"), __("Review"));
    },
});

function review(frm, action) {
    const dialog = new frappe.ui.Dialog({
        title: action === "approve_request" ? __("Approve Company Access") : __("Reject Company Access"),
        fields: [{ fieldname: "review_comment", fieldtype: "Small Text", label: __("Review Comment") }],
        primary_action_label: action === "approve_request" ? __("Approve") : __("Reject"),
        primary_action: async (values) => {
            await frappe.call({
                method: `orderlift.orderlift_crm.doctype.party_company_access_request.party_company_access_request.${action}`,
                args: { name: frm.doc.name, review_comment: values.review_comment || "" },
                freeze: true,
            });
            dialog.hide();
            await frm.reload_doc();
        },
    });
    dialog.show();
}
