frappe.ui.form.on("Delivery Note", {
    refresh(frm) {
        if (frm.is_new()) return;

        _render_dn_scenario_badge(frm);

        // "Run Container Analysis" button
        frm.add_custom_button(__("Run Container Analysis"), async () => {
            const r = await frappe.call({
                method: "orderlift.logistics.utils.delivery_note_logistics.recompute_delivery_note_analysis",
                args: { delivery_note_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Running logistics analysis..."),
            });

            await frm.reload_doc();
            frappe.show_alert({
                message: __("Container analysis completed: {0}", [r.message.analysis]),
                indicator: "green",
            });
        });

        // "Create Delivery Trip" button — domestic or outbound/orderlift only
        const flow = frm.doc.custom_flow_scope || "";
        const responsibility = frm.doc.custom_shipping_responsibility || "";
        const can_create_trip =
            frm.doc.docstatus === 1 &&
            !frm.doc.custom_logistics_locked &&
            (
                flow === "Domestic" ||
                (flow === "Outbound" && responsibility === "Orderlift")
            );

        if (can_create_trip) {
            frm.add_custom_button(
                __("Create Delivery Trip"),
                function () {
                    frappe.call({
                        method: "orderlift.logistics.utils.domestic_dispatch.create_delivery_trip_from_delivery_note",
                        args: { delivery_note_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Creating Delivery Trip..."),
                        callback: function (r) {
                            if (r.message) {
                                frappe.set_route("Form", "Delivery Trip", r.message.delivery_trip);
                            }
                        },
                    });
                },
                __("Actions")
            );
        }
    },
});

function _render_dn_scenario_badge(frm) {
    // Remove old
    frm.page.inner_toolbar.find(".ol-scenario-info-bar").remove();

    const flow = frm.doc.custom_flow_scope || "";
    const responsibility = frm.doc.custom_shipping_responsibility || "";

    if (!flow) return;

    const badge_class =
        flow === "Inbound" ? "badge-inbound" :
        flow === "Domestic" ? "badge-domestic" : "badge-outbound";

    const badge_icon =
        flow === "Inbound" ? "↓" :
        flow === "Domestic" ? "↔" : "↑";

    const resp_class = responsibility === "Customer" ? "tag-customer" : "tag-orderlift";

    const html = `
        <div class="ol-scenario-info-bar" style="margin:0; padding:6px 12px; border-bottom:none; border-radius:8px; margin-bottom:8px;">
            <span class="ol-scenario-badge ${badge_class}">
                <span class="badge-icon">${badge_icon}</span>
                ${flow}
            </span>
            <span class="ol-responsibility-tag ${resp_class}">
                ${responsibility}
            </span>
        </div>
    `;

    frm.page.inner_toolbar.prepend(html);
}
