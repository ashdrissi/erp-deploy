frappe.ui.form.on("Address", {
    after_save(frm) {
        const customer = (frm.doc.links || []).find(
            (row) => row.link_doctype === "Customer" && row.link_name
        )?.link_name;
        if (!customer) return;

        if (frappe.model.clear_doc) {
            frappe.model.clear_doc("Customer", customer);
        } else if (frappe.model.remove_from_locals) {
            frappe.model.remove_from_locals("Customer", customer);
        }

        frappe.after_ajax(() => {
            const route = frappe.get_route();
            if (route[0] === "Form" && route[1] === "Customer" && route[2] === customer && cur_frm) {
                cur_frm.reload_doc();
            }
        });
    },
});
