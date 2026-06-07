const DEFAULT_MANUAL_TIER = "New";
const CUSTOMER_HIDDEN_TIER_FIELDS = ["manual_tier", "tier_last_calculated_on", "tier_source"];
const CUSTOMER_HIDDEN_LEGACY_FIELDS = [
    "custom_partner_campaign_section",
    "custom_partner_segment",
    "custom_partner_campaign",
    "custom_partner_campaign_target",
];

function hideCustomerTechnicalFields(frm) {
    [...CUSTOMER_HIDDEN_TIER_FIELDS, ...CUSTOMER_HIDDEN_LEGACY_FIELDS].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.set_df_property(fieldname, "hidden", 1);
            frm.set_df_property(fieldname, "read_only", 1);
        }
    });
}

function placePricingTierBelowSegmentation(frm, isDynamic) {
    const segmentationField = frm.fields_dict.enable_dynamic_segmentation;
    const tierField = frm.fields_dict.tier;
    if (!segmentationField || !tierField || !segmentationField.$wrapper || !tierField.$wrapper) {
        return;
    }

    tierField.$wrapper.detach().insertAfter(segmentationField.$wrapper);
    tierField.$wrapper.toggle(!isDynamic);
    if (frm.fields_dict.__orderlift_dynamic_tier_status) {
        frm.fields_dict.__orderlift_dynamic_tier_status.detach().insertAfter(segmentationField.$wrapper);
    }
}

function setCustomerPricingTierVisibility(frm, isDynamic) {
    if (!frm.fields_dict.tier) {
        return;
    }

    frm.toggle_display("tier", !isDynamic);
    frm.set_df_property("tier", "hidden", isDynamic ? 1 : 0);
    frm.set_df_property("tier", "read_only", isDynamic ? 1 : 0);
    frm.set_df_property("tier", "reqd", isDynamic ? 0 : 1);
    placePricingTierBelowSegmentation(frm, isDynamic);
}

function escapeHtml(value) {
    return frappe.utils.escape_html(String(value || ""));
}

function getDynamicTierStatusWrapper(frm) {
    const segmentationField = frm.fields_dict.enable_dynamic_segmentation;
    const tierField = frm.fields_dict.tier;
    if (!segmentationField?.$wrapper && !tierField?.$wrapper) {
        return null;
    }

    let wrapper = frm.fields_dict.__orderlift_dynamic_tier_status;
    if (!wrapper) {
        wrapper = $('<div class="orderlift-dynamic-tier-status" style="margin: 6px 0 12px;"></div>');
        wrapper.insertAfter(segmentationField?.$wrapper || tierField.$wrapper);
        frm.fields_dict.__orderlift_dynamic_tier_status = wrapper;
    }
    return wrapper;
}

function renderDynamicTierStatus(frm, result, loading = false) {
    const wrapper = getDynamicTierStatusWrapper(frm);
    if (!wrapper) {
        return;
    }

    const isDynamic = Number(frm.doc.enable_dynamic_segmentation || 0) === 1;
    if (!isDynamic) {
        wrapper.hide().empty();
        return;
    }

    if (loading) {
        wrapper.html(`<div class="text-muted small">${__("Calculating dynamic pricing tier...")}</div>`).show();
        return;
    }

    const status = result?.status || "missing_rule";
    const tier = result?.tier || "";
    const businessType = result?.business_type || "";
    const crmSegment = result?.crm_segment || "";
    const matchedRule = result?.matched_rule || "";
    const message = result?.message || __("No rules to calculate dynamic pricing tier.");
    const indicator = status === "matched" ? "green" : "orange";
    const contextLine = businessType || crmSegment
        ? `<div><strong>${__("Business Type / Segment")}:</strong> ${escapeHtml(businessType || __("missing"))} / ${escapeHtml(crmSegment || __("missing"))}</div>`
        : `<div><strong>${__("Missing Rule")}:</strong> ${__("CRM Business Type and CRM Segment are missing.")}</div>`;
    const ruleLine = matchedRule
        ? `<div><strong>${__("Matching Rule")}:</strong> ${escapeHtml(matchedRule)}</div>`
        : `<div><strong>${__("Matching Rule")}:</strong> ${__("No matching rule found.")}</div>`;
    const tierLine = tier ? `<div><strong>${__("Dynamic Tier")}:</strong> ${escapeHtml(tier)}</div>` : "";

    wrapper.html(`
        <div class="indicator ${indicator}" style="display:block;margin-bottom:4px;">${escapeHtml(message)}</div>
        <div class="small text-muted" style="line-height:1.5;">
            ${tierLine}
            ${contextLine}
            ${ruleLine}
        </div>
    `).show();
}

async function calculateDynamicPricingTier(frm) {
    if (frm.doctype !== "Customer" || Number(frm.doc.enable_dynamic_segmentation || 0) !== 1) {
        renderDynamicTierStatus(frm, null);
        return;
    }

    setCustomerPricingTierVisibility(frm, true);
    if (frm.is_new()) {
        renderDynamicTierStatus(frm, {
            status: "missing_customer",
            message: __("Save the customer before calculating a dynamic pricing tier."),
        });
        return;
    }

    renderDynamicTierStatus(frm, null, true);
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine.calculate_customer_dynamic_tier",
        args: { customer: frm.doc.name, apply: 1 },
    });
    const result = response.message || {};
    await frm.set_value("tier", result.tier || "");
    renderDynamicTierStatus(frm, result);
}

async function fetchPricingTiers() {
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_tier.pricing_tier.get_active_pricing_tiers",
    });
    const tiers = response.message || [];
    if (!tiers.includes(DEFAULT_MANUAL_TIER)) {
        tiers.unshift(DEFAULT_MANUAL_TIER);
    }
    return tiers;
}

async function applyPricingTierOptions(frm) {
    const options = ["", ...(await fetchPricingTiers())].join("\n");
    ["manual_tier", "tier"].forEach((fieldname) => {
        const field = frm.fields_dict[fieldname];
        if (field && field.df.fieldtype === "Select") {
            frm.set_df_property(fieldname, "options", options);
        }
    });
}

function applyPricingTierQueries(frm) {
    ["manual_tier", "tier"].forEach((fieldname) => {
        const field = frm.fields_dict[fieldname];
        if (field && field.df.fieldtype === "Link" && field.df.options === "Pricing Tier") {
            frm.set_query(fieldname, () => ({ filters: { is_active: 1 } }));
        }
    });
}

async function ensureManualTierDefault(frm) {
    if (Number(frm.doc.enable_dynamic_segmentation || 0) === 1 || frm.doc.manual_tier) {
        return;
    }
    await frm.set_value("manual_tier", DEFAULT_MANUAL_TIER);
}

async function refreshTierModeUI(frm) {
    const isProspect = frm.doctype === "Prospect";
    if (isProspect) {
        await applyPricingTierOptions(frm);
        if (frm.fields_dict.enable_dynamic_segmentation) {
            frm.set_value("enable_dynamic_segmentation", 0);
            frm.set_df_property("enable_dynamic_segmentation", "hidden", 1);
        }
        if (frm.fields_dict.tier) {
            frm.set_df_property("tier", "hidden", 1);
            frm.set_df_property("tier", "read_only", 1);
        }
        if (frm.fields_dict.manual_tier) {
            frm.set_df_property("manual_tier", "label", __("Tier"));
            frm.set_df_property("manual_tier", "hidden", 0);
            frm.set_df_property("manual_tier", "reqd", 1);
        }
        await ensureManualTierDefault(frm);
        if (frm.doc.manual_tier) {
            frm.set_value("tier", frm.doc.manual_tier);
        }
        return;
    }

    hideCustomerTechnicalFields(frm);
    const isDynamic = Number(frm.doc.enable_dynamic_segmentation || 0) === 1;

    frm.set_df_property("manual_tier", "reqd", 0);
    setCustomerPricingTierVisibility(frm, isDynamic);

    if (isDynamic) {
        frm.set_df_property("tier", "description", __("Tier is maintained by Dynamic Segmentation."));
        await calculateDynamicPricingTier(frm);
        return;
    }

    await ensureManualTierDefault(frm);
    frm.set_df_property("tier", "description", __("Tier is manually selected from active Pricing Tier records."));

    if (frm.doc.manual_tier) {
        frm.set_value("tier", frm.doc.manual_tier);
    }
    setCustomerPricingTierVisibility(frm, isDynamic);
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
    async setup(frm) {
        applyPricingTierQueries(frm);
        await applyPricingTierOptions(frm);
    },

    async refresh(frm) {
        await refreshTierModeUI(frm);
        setTimeout(() => refreshTierModeUI(frm), 100);
        addPortalActions(frm);
    },

    async customer_group(frm) {
        await refreshTierModeUI(frm);
    },

    async enable_dynamic_segmentation(frm) {
        const isDynamic = Number(frm.doc.enable_dynamic_segmentation || 0) === 1;
        setCustomerPricingTierVisibility(frm, isDynamic);
        if (isDynamic) {
            frm.set_value("manual_tier", "");
            await calculateDynamicPricingTier(frm);
        } else {
            await ensureManualTierDefault(frm);
        }
        await refreshTierModeUI(frm);
    },

    manual_tier(frm) {
        if (Number(frm.doc.enable_dynamic_segmentation || 0) === 0) {
            frm.set_value("tier", frm.doc.manual_tier || "");
        }
    },

    tier(frm) {
        if (Number(frm.doc.enable_dynamic_segmentation || 0) === 0) {
            frm.set_value("manual_tier", frm.doc.tier || DEFAULT_MANUAL_TIER);
        }
    },
});

frappe.ui.form.on("Prospect", {
    async setup(frm) {
        applyPricingTierQueries(frm);
        await applyPricingTierOptions(frm);
    },

    async refresh(frm) {
        await refreshTierModeUI(frm);
    },

    async customer_group(frm) {
        await refreshTierModeUI(frm);
    },

    manual_tier(frm) {
        frm.set_value("tier", frm.doc.manual_tier || "");
    },
});
