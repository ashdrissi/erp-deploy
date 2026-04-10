function getStatusBannerHtml(status) {
    const statusValue = String(status || "ok").toLowerCase();
    let cssClass = "ok";
    let icon = "✓";
    let label = "Analysis Complete";

    if (statusValue === "over_capacity") {
        cssClass = "danger";
        icon = "⚠";
        label = "Over Capacity — Container limits exceeded";
    } else if (statusValue === "incomplete_data") {
        cssClass = "warn";
        icon = "⚠";
        label = "Incomplete Data — Missing weight or volume information";
    } else if (statusValue === "no_container_found") {
        cssClass = "warn";
        icon = "⚠";
        label = "No Container Found — No suitable container available";
    } else if (statusValue === "cancelled") {
        cssClass = "danger";
        icon = "✕";
        label = "Cancelled — Analysis was cancelled or source deleted";
    }

    return `
        <div class="ol-sa-status-banner ${cssClass}">
            <span class="ol-sa-status-dot"></span>
            <span>${label}</span>
        </div>
    `;
}

frappe.ui.form.on("Shipment Analysis", {
    refresh(frm) {
        const statusBanner = getStatusBannerHtml(frm.doc.status);
        frm.set_intro(statusBanner, false);

        if (!frm.doc.__islocal) {
            if (frm.doc.source_type === "Container Load Plan" && frm.doc.source_name) {
                frm.add_custom_button(__("Open Load Plan"), () => {
                    frappe.set_route("Form", "Container Load Plan", frm.doc.source_name);
                });
            } else if (frm.doc.source_type === "Delivery Note" && frm.doc.source_name) {
                frm.add_custom_button(__("Open Delivery Note"), () => {
                    frappe.set_route("Form", "Delivery Note", frm.doc.source_name);
                });
            }

            frm.add_custom_button(__("Open Cockpit"), () => {
                frappe.set_route("Page", "logistics-hub-cockpit", {
                    container_load_plan: frm.doc.source_name,
                });
            });
        }
    },
});

// List view indicators
frappe.listview_settings["Shipment Analysis"] = {
    get_indicator(doc) {
        const status = String(doc.status || "ok").toLowerCase();

        if (status === "ok") {
            return [__("Healthy"), "green", `status,=,${status}`];
        } else if (status === "incomplete_data" || status === "no_container_found") {
            return [__(frappe.unscrub(status)), "orange", `status,=,${status}`];
        } else if (status === "over_capacity" || status === "cancelled") {
            return [__(frappe.unscrub(status)), "red", `status,=,${status}`];
        }

        return [__("Unknown"), "gray", ""];
    },
};
