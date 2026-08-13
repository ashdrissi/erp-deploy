frappe.ui.form.on("Stock Demand Plan", {
    refresh(frm) {
        if (frm.doc.sales_order) {
            frm.add_custom_button(__("Open Sales Order"), () => {
                frappe.set_route("Form", "Sales Order", frm.doc.sales_order);
            });
        }
        if (frm.doc.latest_pick_list) {
            frm.add_custom_button(__("Open Pick List"), () => {
                frappe.set_route("Form", "Pick List", frm.doc.latest_pick_list);
            });
        }
        const canRun = ["Stock Manager", "Orderlift Admin", "System Manager"].some((role) => frappe.user.has_role(role));
        if (!frm.is_new() && canRun) {
            frm.add_custom_button(__("Run Company Planning"), async () => {
                await frappe.call({
                    method: "orderlift.orderlift_logistics.stock_planning.recalculate_current_company",
                    freeze: true,
                    freeze_message: __("Recalculating confirmed demand..."),
                });
                await frm.reload_doc();
            });
        }
        const colors = {
            "Fully Reserved": "green",
            "Covered by Physical Stock": "green",
            "Covered by Incoming": "blue",
            "Waiting Incoming": "blue",
            "Not Due": "gray",
            "Incoming Late": "red",
            "Procurement Late": "red",
            Shortage: "red",
            "Replan Needed": "red",
        };
        frm.page.set_indicator(__(frm.doc.planning_status || "Not Due"), colors[frm.doc.planning_status] || "orange");
    },
});
