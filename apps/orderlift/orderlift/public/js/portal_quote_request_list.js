frappe.listview_settings["Portal Quote Request"] = {
    add_fields: ["status", "customer", "customer_group", "portal_user", "total_amount", "currency", "linked_quotation"],
    get_indicator(doc) {
        const map = {
            Draft: [__("Draft"), "gray", "status,=,Draft"],
            Submitted: [__("Submitted"), "orange", "status,=,Submitted"],
            "Under Review": [__("Under Review"), "blue", "status,=,Under Review"],
            Approved: [__("Approved"), "green", "status,=,Approved"],
            Rejected: [__("Rejected"), "red", "status,=,Rejected"],
            "Quotation Created": [__("Quotation Created"), "purple", "status,=,Quotation Created"],
        };
        return map[doc.status] || [__(doc.status || "Unknown"), "gray", `status,=,${doc.status || ""}`];
    },
    button: {
        show(doc) {
            return ["Submitted", "Under Review", "Approved"].includes(doc.status || "");
        },
        get_label(doc) {
            return doc.linked_quotation ? __("Open Quotation") : __("Review");
        },
        get_description(doc) {
            return doc.linked_quotation ? __("Open linked quotation") : __("Open request for approval");
        },
        action(doc) {
            if (doc.linked_quotation) {
                frappe.set_route("Form", "Quotation", doc.linked_quotation);
                return;
            }
            frappe.set_route("Form", "Portal Quote Request", doc.name);
        },
    },
    onload(listview) {
        listview.page.add_inner_button(__("Pending Review"), () => {
            listview.filter_area.add([["Portal Quote Request", "status", "in", ["Submitted", "Under Review", "Approved"]]]);
        });
    },
};
