frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (frm.is_new()) return;

        // SIG — Create or open installation project
        _sig_project_button(frm);

        frm.add_custom_button(__("Forecast Container"), async () => {
            const r = await frappe.call({
                method: "orderlift.logistics.utils.delivery_note_logistics.forecast_sales_order_container",
                args: { sales_order_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Forecasting container recommendation..."),
            });

            const data = r.message || {};
            frappe.msgprint({
                title: __("Container Forecast"),
                indicator: data.status === "ok" ? "green" : "orange",
                message: `
                    <div>Total Weight: <b>${Number(data.total_weight_kg || 0).toFixed(3)} kg</b></div>
                    <div>Total Volume: <b>${Number(data.total_volume_m3 || 0).toFixed(3)} m3</b></div>
                    <div>Recommended Container: <b>${data.recommended_container || "Not found"}</b></div>
                    <div>Weight Utilization: <b>${Number(data.weight_utilization_pct || 0).toFixed(2)}%</b></div>
                    <div>Volume Utilization: <b>${Number(data.volume_utilization_pct || 0).toFixed(2)}%</b></div>
                    <div>Status: <b>${data.status || "n/a"}</b></div>
                `,
            });
        });
    },
});

// ── SIG: Create / Open Installation Project button ─────────────────────────

function _sig_project_button(frm) {
    const linked = frm.doc.custom_installation_project;

    if (linked) {
        // Project already exists — show shortcut to open it
        frm.add_custom_button(__("Open Installation Project"), () => {
            frappe.set_route("Form", "Project", linked);
        }, __("SIG"));
    } else {
        // Only offer creation on submitted SO
        if (frm.doc.docstatus !== 1) return;

        frm.add_custom_button(__("Create Installation Project"), () => {
            frappe.confirm(
                __("Create an installation project for Sales Order {0}?", [frm.doc.name]),
                () => {
                    frappe.call({
                        method: "orderlift.orderlift_sig.utils.project_status_guard.create_project_from_sales_order",
                        args: { sales_order_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Creating project…"),
                        callback(r) {
                            if (!r.exc && r.message) {
                                frm.reload_doc();
                                frappe.set_route("Form", "Project", r.message);
                            }
                        },
                    });
                }
            );
        }, __("SIG"));
    }
}
