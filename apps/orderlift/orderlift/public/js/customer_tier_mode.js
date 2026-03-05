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

frappe.ui.form.on("Customer", {
    async refresh(frm) {
        await refreshTierModeUI(frm);
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
