function renderCapacityCard(frm) {
    const isActive = frm.doc.is_active ? "✓ Active" : "○ Inactive";
    const activeStatus = frm.doc.is_active ? "ok" : "warn";

    const html = `
        <div class="ol-profile-capacity-wrap">
            <div class="ol-profile-capacity-title">Container Capacity & Configuration</div>
            <div class="ol-profile-capacity-specs">
                <div class="ol-profile-spec-item">
                    <div class="ol-profile-spec-label">Max Weight</div>
                    <div class="ol-profile-spec-value">${Number(frm.doc.max_weight_kg || 0).toFixed(0)} kg</div>
                </div>
                <div class="ol-profile-spec-item">
                    <div class="ol-profile-spec-label">Max Volume</div>
                    <div class="ol-profile-spec-value">${Number(frm.doc.max_volume_m3 || 0).toFixed(1)} m³</div>
                </div>
            </div>
            <div class="ol-profile-capacity-specs">
                <div class="ol-profile-spec-item">
                    <div class="ol-profile-spec-label">Container Type</div>
                    <div class="ol-profile-spec-value">${frappe.utils.escape_html(frm.doc.container_type || "-")}</div>
                </div>
                <div class="ol-profile-spec-item">
                    <div class="ol-profile-spec-label">Status</div>
                    <div class="ol-profile-spec-value" style="color:#${activeStatus === 'ok' ? '1f6f3b' : '9a5f05'};">${isActive}</div>
                </div>
            </div>
        </div>
    `;

    frm.set_intro(html, false);
}

frappe.ui.form.on("Container Profile", {
    refresh(frm) {
        renderCapacityCard(frm);

        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("View Load Plans"), () => {
                frappe.route_options = {
                    container_profile: frm.doc.name,
                };
                frappe.set_route("List", "Container Load Plan");
            });
        }
    },

    max_weight_kg: renderCapacityCard,
    max_volume_m3: renderCapacityCard,
    is_active: renderCapacityCard,
    container_type: renderCapacityCard,
});
