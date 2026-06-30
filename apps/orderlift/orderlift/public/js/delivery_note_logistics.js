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
    if (frm.$wrapper) frm.$wrapper.find(".ol-scenario-info-bar").remove();

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
        <div class="ol-scenario-info-bar ol-order-status-flow ol-thin-scenario-bar" role="list">
            <span class="ol-order-status-step ${_dn_scenario_status_color(flow)}" role="listitem">
                <span class="ol-status-step-icon">${frappe.utils.escape_html(badge_icon)}</span>
                <span class="ol-status-step-text">${frappe.utils.escape_html(flow)}</span>
            </span>
            <span class="ol-order-status-step ${resp_class === "tag-customer" ? "ol-status-orange" : "ol-status-blue"}" role="listitem">
                <span class="ol-status-step-icon">${_dn_status_icon(resp_class === "tag-customer" ? "user" : "truck")}</span>
                <span class="ol-status-step-text">${frappe.utils.escape_html(responsibility)}</span>
            </span>
        </div>
    `;

    _ensure_dn_scenario_bar_styles();
    _insert_dn_scenario_bar(frm, html);
}

function _dn_scenario_status_color(flow) {
    if (flow === "Inbound") return "ol-status-blue";
    if (flow === "Domestic") return "ol-status-green";
    if (flow === "Outbound") return "ol-status-orange";
    return "ol-status-gray";
}

function _dn_status_icon(icon) {
    if (frappe.utils && frappe.utils.icon) return frappe.utils.icon(icon, "sm");
    return "";
}

function _insert_dn_scenario_bar(frm, html) {
    const bar = $(html);
    const wrapper = frm.$wrapper || (frm.wrapper ? $(frm.wrapper) : $());
    if (!wrapper.length) {
        frm.page.inner_toolbar.prepend(bar);
        return;
    }

    const tabs = wrapper.find(".form-tabs-list").first();
    if (tabs.length) {
        tabs.before(bar);
        return;
    }

    const formPage = wrapper.find(".form-page").first();
    if (formPage.length) {
        formPage.prepend(bar);
        return;
    }

    const formLayout = wrapper.find(".form-layout").first();
    if (formLayout.length) {
        formLayout.prepend(bar);
        return;
    }

    wrapper.prepend(bar);
}

function _ensure_dn_scenario_bar_styles() {
    if (document.getElementById("ol-thin-scenario-bar-style")) return;
    $("head").append(`
        <style id="ol-thin-scenario-bar-style">
            .ol-thin-scenario-bar.ol-order-status-flow {
                display: flex;
                align-items: center;
                gap: 5px;
                flex-wrap: wrap;
                padding: 6px;
                margin: 0 0 5px;
                border: 1px solid var(--border-color, #d8dee8);
                border-radius: 9px;
                background: linear-gradient(135deg, rgba(255,255,255,.96), rgba(248,250,252,.9));
            }
            .ol-thin-scenario-bar .ol-order-status-step {
                position: relative;
                display: inline-flex;
                align-items: center;
                gap: 5px;
                min-height: 24px;
                max-width: 180px;
                padding: 3px 8px;
                border-radius: 999px;
                font-size: 11px;
                line-height: 1.2;
                font-weight: 600;
                white-space: nowrap;
            }
            .ol-thin-scenario-bar .ol-order-status-step:not(:last-child)::after {
                content: "";
                position: absolute;
                left: calc(100% + 4px);
                top: 50%;
                width: 8px;
                height: 2px;
                transform: translateY(-50%);
                border-radius: 999px;
                background: currentColor;
                opacity: .38;
            }
            .ol-thin-scenario-bar .ol-status-step-icon { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; }
            .ol-thin-scenario-bar .ol-status-step-icon .icon { stroke: currentColor; }
            .ol-thin-scenario-bar .ol-status-step-text { overflow: hidden; text-overflow: ellipsis; }
            .ol-thin-scenario-bar .ol-status-blue { color: #0b5ed7; background: linear-gradient(135deg, #eef5ff, #f7fbff); }
            .ol-thin-scenario-bar .ol-status-green { color: #0f8f72; background: linear-gradient(135deg, #e9f8f3, #f5fbf8); }
            .ol-thin-scenario-bar .ol-status-orange { color: #d96b0b; background: linear-gradient(135deg, #fff3e8, #fff8f1); }
            .ol-thin-scenario-bar .ol-status-gray { color: #475569; background: linear-gradient(135deg, #f1f5f9, #f8fafc); }
            @media (max-width: 767px) {
                .ol-thin-scenario-bar.ol-order-status-flow { gap: 4px; }
                .ol-thin-scenario-bar .ol-order-status-step { flex: 1 1 132px; justify-content: center; max-width: none; padding: 3px 7px; font-size: 10px; }
                .ol-thin-scenario-bar .ol-order-status-step:not(:last-child)::after { display: none; }
            }
        </style>
    `);
}
