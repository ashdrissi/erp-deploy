async function fetchAllowedTiers(customerGroup) {
    if (!customerGroup) {
        return [];
    }

    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine.get_customer_group_tiers",
        args: { customer_group: customerGroup },
    });
    return response.message || [];
}

function applyManualTierOptions(frm, tiers) {
    const options = ["", ...(tiers || [])].join("\n");
    frm.set_df_property("manual_tier", "options", options);
}

async function refreshTierModeUI(frm) {
    const isDynamic = Number(frm.doc.enable_dynamic_segmentation || 0) === 1;

    frm.set_df_property("manual_tier", "hidden", isDynamic ? 1 : 0);
    frm.set_df_property("manual_tier", "reqd", isDynamic ? 0 : 1);
    frm.set_df_property("tier", "read_only", 1);

    if (isDynamic) {
        frm.set_df_property("tier", "description", __("Tier is maintained by Dynamic Segmentation."));
        return;
    }

    const tiers = await fetchAllowedTiers(frm.doc.customer_group);
    applyManualTierOptions(frm, tiers);
    frm.set_df_property("tier", "description", __("Tier is manually selected from allowed segmentation tiers."));

    if (frm.doc.manual_tier && !tiers.includes(frm.doc.manual_tier)) {
        frm.set_value("manual_tier", "");
    }
    if (frm.doc.manual_tier) {
        frm.set_value("tier", frm.doc.manual_tier);
    }
}

function addPortalActions(frm) {
    if (frm.is_new()) return;

    frm.add_custom_button(__("Portal Policies"), () => {
        frappe.set_route("List", "Portal Customer Group Policy", { customer_group: frm.doc.customer_group || undefined });
    }, __("B2B Portal"));

    frm.add_custom_button(__("Portal Requests"), () => {
        frappe.set_route("List", "Portal Quote Request", { customer: frm.doc.name });
    }, __("B2B Portal"));

    frm.add_custom_button(__("Invite Portal User"), () => {
        const d = new frappe.ui.Dialog({
            title: __("Invite Portal User"),
            fields: [
                { fieldname: "email", fieldtype: "Data", label: __("Email"), reqd: 1, options: "Email" },
                { fieldname: "first_name", fieldtype: "Data", label: __("First Name") },
                { fieldname: "last_name", fieldtype: "Data", label: __("Last Name") },
            ],
            primary_action_label: __("Invite"),
            primary_action(values) {
                frappe.call({
                    method: "orderlift.orderlift_client_portal.api.invite_portal_user",
                    args: {
                        email: values.email,
                        customer: frm.doc.name,
                        first_name: values.first_name,
                        last_name: values.last_name,
                    },
                    callback: () => {
                        d.hide();
                        frappe.show_alert({ message: __("Portal user invited"), indicator: "green" });
                        frm.reload_doc();
                    },
                });
            },
        });
        d.show();
    }, __("B2B Portal"));
}

frappe.ui.form.on("Customer", {
    async refresh(frm) {
        await refreshTierModeUI(frm);
        addPortalActions(frm);
    },

    async customer_group(frm) {
        await refreshTierModeUI(frm);
    },

    async enable_dynamic_segmentation(frm) {
        if (Number(frm.doc.enable_dynamic_segmentation || 0) === 1) {
            frm.set_value("manual_tier", "");
        }
        await refreshTierModeUI(frm);
    },

    manual_tier(frm) {
        if (Number(frm.doc.enable_dynamic_segmentation || 0) === 0) {
            frm.set_value("tier", frm.doc.manual_tier || "");
        }
    },
});
