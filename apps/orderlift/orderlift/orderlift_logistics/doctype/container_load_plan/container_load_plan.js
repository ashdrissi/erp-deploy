function utilizationColor(value) {
    const pct = Number(value || 0);
    if (pct >= 95) return "#d64545";
    if (pct >= 75) return "#f39c12";
    return "#2e9f57";
}

function renderCapacityDashboard(frm) {
    const weightPct = Number(frm.doc.weight_utilization_pct || 0);
    const volumePct = Number(frm.doc.volume_utilization_pct || 0);
    const weightColor = utilizationColor(weightPct);
    const volumeColor = utilizationColor(volumePct);

    const html = `
        <div class="container-capacity-card">
            <div class="container-capacity-title">Container Capacity Overview</div>
            <div class="container-capacity-row">
                <div class="container-capacity-label">Weight Capacity</div>
                <div class="container-capacity-value">${weightPct.toFixed(2)}%</div>
            </div>
            <div class="container-capacity-bar">
                <div class="container-capacity-bar-fill" style="width:${Math.min(weightPct, 100)}%;background:${weightColor};"></div>
            </div>
            <div class="container-capacity-subtext">${Number(frm.doc.total_weight_kg || 0).toFixed(3)} kg loaded</div>

            <div class="container-capacity-row" style="margin-top:12px;">
                <div class="container-capacity-label">Volume Capacity</div>
                <div class="container-capacity-value">${volumePct.toFixed(2)}%</div>
            </div>
            <div class="container-capacity-bar">
                <div class="container-capacity-bar-fill" style="width:${Math.min(volumePct, 100)}%;background:${volumeColor};"></div>
            </div>
            <div class="container-capacity-subtext">${Number(frm.doc.total_volume_m3 || 0).toFixed(3)} m3 loaded</div>

            <div class="container-capacity-footer">Limiting factor: <b>${frm.doc.limiting_factor || "n/a"}</b> | Status: <b>${frm.doc.analysis_status || "ok"}</b></div>
        </div>
    `;

    frm.fields_dict.capacity_dashboard_html.$wrapper.html(html);
}

function runLoadPlanAnalysis(frm) {
    return frappe.call({
        method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.run_load_plan_analysis",
        args: { load_plan_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Running container analysis..."),
    }).then(() => frm.reload_doc());
}

frappe.ui.form.on("Container Load Plan", {
    refresh(frm) {
        renderCapacityDashboard(frm);

        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Run Logistics Analysis"), () => {
                runLoadPlanAnalysis(frm);
            });

            frm.add_custom_button(__("Suggest Shipments"), async () => {
                const r = await frappe.call({
                    method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.suggest_shipments",
                    args: { load_plan_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Finding best shipment mix..."),
                });

                const selected = (r.message && r.message.selected) || [];
                if (!selected.length) {
                    frappe.show_alert({ message: __("No fitting shipment suggestions found"), indicator: "orange" });
                    return;
                }

                const dnList = selected.map((row) => row.delivery_note);
                await frappe.call({
                    method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments",
                    args: { load_plan_name: frm.doc.name, delivery_notes: dnList },
                    freeze: true,
                    freeze_message: __("Appending suggested shipments..."),
                });
                await frm.reload_doc();
                frappe.show_alert({ message: __("Suggested shipments added"), indicator: "green" });
            });
        }
    },

    container_profile: renderCapacityDashboard,
    shipments_add(frm) {
        renderCapacityDashboard(frm);
    },
    shipments_remove(frm) {
        renderCapacityDashboard(frm);
    },
});

frappe.ui.form.on("Load Plan Shipment", {
    delivery_note(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.delivery_note) return;
        frappe.db.get_value("Delivery Note", row.delivery_note, ["customer", "custom_total_weight_kg", "custom_total_volume_m3"]).then((r) => {
            const data = r.message || {};
            frappe.model.set_value(cdt, cdn, "customer", data.customer || "");
            frappe.model.set_value(cdt, cdn, "shipment_weight_kg", data.custom_total_weight_kg || 0);
            frappe.model.set_value(cdt, cdn, "shipment_volume_m3", data.custom_total_volume_m3 || 0);
            renderCapacityDashboard(frm);
        });
    },
    selected: renderCapacityDashboard,
});
