async function refreshPortalPolicySummary(frm) {
    const rows = frm.doc.catalog_items || [];
    const enabledRows = rows.filter((row) => Number(row.enabled || 0) === 1);
    const itemCount = enabledRows.filter((row) => row.item_code).length;
    const bundleCount = enabledRows.filter((row) => row.product_bundle).length;
    const featuredCount = enabledRows.filter((row) => Number(row.featured || 0) === 1).length;

    let missingPrice = 0;
    if (frm.doc.portal_price_list && enabledRows.length) {
        const checks = await Promise.all(enabledRows.map(async (row) => {
            const itemCode = row.item_code || await getBundleItemCode(row.product_bundle);
            if (!itemCode) return false;
            const result = await frappe.db.get_value("Item Price", {
                item_code: itemCode,
                price_list: frm.doc.portal_price_list,
            }, "name");
            return !result.message?.name;
        }));
        missingPrice = checks.filter(Boolean).length;
    }

    const warning = missingPrice
        ? `<div class="text-warning" style="margin-top:8px;">${missingPrice} allowed product(s) have no price in ${frappe.utils.escape_html(frm.doc.portal_price_list)}.</div>`
        : "";

    frm.dashboard.set_headline(`
        <div style="display:flex; gap:14px; flex-wrap:wrap; align-items:center;">
            <span><strong>${enabledRows.length}</strong> enabled products</span>
            <span><strong>${itemCount}</strong> items</span>
            <span><strong>${bundleCount}</strong> bundles</span>
            <span><strong>${featuredCount}</strong> featured</span>
        </div>
        ${warning}
    `);
}

async function getBundleItemCode(bundleName) {
    if (!bundleName) return "";
    const result = await frappe.db.get_value("Product Bundle", bundleName, "new_item_code");
    return result.message?.new_item_code || "";
}

frappe.ui.form.on("Portal Customer Group Policy", {
    async refresh(frm) {
        await refreshPortalPolicySummary(frm);
        if (!frm.is_new() && frm.doc.customer_group) {
            frm.add_custom_button(__("Preview Portal Catalog"), () => {
                window.open(`/b2b-portal/catalog`, "_blank", "noopener");
            });

            frm.add_custom_button(__("Readiness Check"), async () => {
                const r = await frm.call("get_readiness_report");
                const report = r.message || {};
                frappe.msgprint({
                    title: report.ok ? __("Portal Ready") : __("Portal Readiness Issues"),
                    indicator: report.ok ? "green" : "orange",
                    message: report.ok
                        ? __(`Portal policy is ready. Enabled products: ${report.enabled_products || 0}. Featured: ${report.featured_products || 0}.`)
                        : `<ul style="padding-left:18px;">${(report.issues || []).map((issue) => `<li>${frappe.utils.escape_html(issue)}</li>`).join("")}</ul>`,
                });
            }, __("Allowed Products"));

            frm.add_custom_button(__("Bulk Add Products"), () => {
                openBulkAddDialog(frm);
            }, __("Allowed Products"));

            frm.add_custom_button(__("Bulk Add Bundles"), () => {
                openBulkAddDialog(frm, "bundle");
            }, __("Allowed Products"));

            frm.add_custom_button(__("Remove Disabled Rows"), async () => {
                const r = await frm.call("remove_disabled_rows");
                frappe.show_alert({ message: __(`Removed ${r.message.removed || 0} disabled row(s)`), indicator: "green" });
                await frm.reload_doc();
            }, __("Allowed Products"));
        }
    },

    async portal_price_list(frm) {
        await refreshPortalPolicySummary(frm);
    },
});

frappe.ui.form.on("Portal Customer Group Product", {
    async enabled(frm) { await refreshPortalPolicySummary(frm); },
    async item_code(frm) { await refreshPortalPolicySummary(frm); },
    async product_bundle(frm) { await refreshPortalPolicySummary(frm); },
    async featured(frm) { await refreshPortalPolicySummary(frm); },
});

function openBulkAddDialog(frm, targetType = "item") {
    const d = new frappe.ui.Dialog({
        title: targetType === "bundle" ? __("Bulk Add Bundles") : __("Bulk Add Products"),
        fields: [
            {
                fieldname: "filter_type",
                fieldtype: "Select",
                label: __(targetType === "bundle" ? "Bulk Add Bundles By" : "Bulk Add Products By"),
                options: "item_group\nbrand\ncodes",
                default: "item_group",
                reqd: 1,
            },
            {
                fieldname: "filter_value",
                fieldtype: "Data",
                label: __("Value"),
                reqd: 1,
                description: __("Enter an Item Group, Brand, or a comma/newline separated list of codes."),
            },
            {
                fieldname: "featured",
                fieldtype: "Check",
                label: __("Mark as Featured"),
            },
            {
                fieldname: "allow_quote",
                fieldtype: "Check",
                label: __("Allow Quote"),
                default: 1,
            },
        ],
        primary_action_label: targetType === "bundle" ? __("Add Bundles") : __("Add Products"),
        primary_action: async (values) => {
            const method = targetType === "bundle" ? "bulk_add_bundles" : "bulk_add_products";
            const r = await frm.call(method, values);
            d.hide();
            frappe.show_alert({ message: __(targetType === "bundle" ? `Added ${r.message.added || 0} bundle(s)` : `Added ${r.message.added || 0} product(s)`), indicator: "green" });
            await frm.reload_doc();
        },
    });
    d.show();
}
