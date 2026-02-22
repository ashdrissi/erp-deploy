frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (frm.is_new()) return;

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
