(function () {
    const METHOD = "orderlift.orderlift_logistics.utils.material_request";
    const settings = frappe.listview_settings["Material Request"] || {};
    const existingOnload = settings.onload;

    settings.onload = function (listview) {
        if (typeof existingOnload === "function") existingOnload(listview);
        if (listview.__orderliftMakePurchaseOrderAdded) return;
        listview.__orderliftMakePurchaseOrderAdded = true;
        listview.page.add_inner_button(__("Create Purchase Order"), () => openDialog(listview));
    };

    frappe.listview_settings["Material Request"] = settings;

    async function openDialog(listview) {
        const selected = typeof listview.get_checked_items === "function" ? listview.get_checked_items() : [];
        const names = selected.map((row) => row.name).filter(Boolean);
        if (!names.length) {
            frappe.msgprint(__("Select at least one submitted Purchase Material Request."));
            return;
        }

        let preview;
        try {
            const response = await frappe.call({
                method: `${METHOD}.get_material_request_purchase_order_preview`,
                args: { material_requests: JSON.stringify(names) },
                freeze: true,
                freeze_message: __("Checking Material Requests..."),
            });
            preview = response.message || {};
        } catch (error) {
            frappe.msgprint(error?.message || __("Could not prepare the selected Material Requests."));
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Create One Purchase Order"),
            fields: [
                {
                    fieldname: "summary",
                    fieldtype: "HTML",
                    options: renderSummary(preview),
                },
                {
                    fieldname: "supplier",
                    fieldtype: "Link",
                    options: "Supplier",
                    label: __("Supplier"),
                    reqd: 1,
                },
                {
                    fieldname: "schedule_date",
                    fieldtype: "Date",
                    label: __("Required By"),
                    default: preview.schedule_date || frappe.datetime.nowdate(),
                    reqd: 1,
                },
            ],
            primary_action_label: __("Open Draft Purchase Order"),
            async primary_action(values) {
                dialog.disable_primary_action();
                try {
                    const response = await frappe.call({
                        method: `${METHOD}.make_purchase_order_from_material_requests`,
                        args: {
                            material_requests: JSON.stringify(names),
                            supplier: values.supplier,
                            schedule_date: values.schedule_date,
                        },
                        freeze: true,
                        freeze_message: __("Preparing Purchase Order..."),
                    });
                    const doc = response.message?.doc;
                    if (!doc) throw new Error(__("The Purchase Order could not be prepared."));
                    frappe.model.sync(doc);
                    dialog.hide();
                    frappe.set_route("Form", "Purchase Order", doc.name);
                } catch (error) {
                    frappe.msgprint(error?.message || __("Could not create the Purchase Order."));
                } finally {
                    dialog.enable_primary_action();
                }
            },
        });
        dialog.show();
    }

    function renderSummary(preview) {
        const requestCount = (preview.material_requests || []).length;
        const skippedCount = (preview.skipped_rows || []).length;
        return `<div class="alert alert-info">${__("{0} Material Request(s), {1} remaining item row(s), company {2}.", [requestCount, preview.eligible_rows || 0, preview.company || ""])}</div>${skippedCount ? `<p class="text-muted">${__("{0} fully ordered or invalid row(s) will be skipped.", [skippedCount])}</p>` : ""}`;
    }
})();
