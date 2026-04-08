frappe.ui.form.on("QC Checklist Template", {
    refresh(frm) {
        frm.add_custom_button(__("Duplicate Template"), () => {
            frappe.prompt(
                { label: __("New Template Name"), fieldname: "name", fieldtype: "Data", reqd: 1 },
                ({ name }) => {
                    frappe.call({
                        method: "orderlift.orderlift_sig.utils.project_qc.duplicate_qc_template",
                        args: { source_name: frm.doc.name, new_name: name },
                        callback(r) {
                            if (!r.exc) {
                                frappe.set_route("Form", "QC Checklist Template", r.message);
                            }
                        },
                    });
                },
                __("Duplicate Template"),
                __("Duplicate")
            );
        });
    },
});
