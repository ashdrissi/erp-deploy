// Project SIG — Frappe form enhancements for ERPNext Project doctype
// S1: Apply QC Template button, Geocode Address button, QC status badge colouring
// S2: QC progress bar, open-in-map shortcut, QC item verification from form

frappe.ui.form.on("Project", {
    refresh(frm) {
        _render_qc_status_badge(frm);
        _render_qc_progress(frm);
        _add_sig_buttons(frm);
    },

    custom_qc_status(frm) {
        _render_qc_status_badge(frm);
        _render_qc_progress(frm);
    },

    custom_qc_template(frm) {
        if (frm.doc.custom_qc_template && !frm.is_new()) {
            frappe.confirm(
                __('Apply template "{0}"? Existing checklist will be replaced.', [frm.doc.custom_qc_template]),
                () => _do_apply_qc_template(frm)
            );
        }
    },
});

// ── Child table row change — auto-stamp verified_by / verified_on ──────────
frappe.ui.form.on("Installation QC Item", {
    is_verified(frm, cdt, cdn) {
        if (frm.is_new()) return;
        const row = locals[cdt][cdn];
        frappe.call({
            method: "orderlift.orderlift_sig.utils.project_qc.sync_qc_item_verification",
            args: {
                project_name: frm.doc.name,
                row_name: row.name,
                is_verified: row.is_verified ? 1 : 0,
            },
            callback(r) {
                if (r.exc) return;
                const { qc_status, verified, total } = r.message;
                frm.set_value("custom_qc_status", qc_status);
                _render_qc_progress_data(frm, verified, total, qc_status);
                frappe.show_alert({
                    message: __("QC: {0}/{1} verified — {2}", [verified, total, qc_status]),
                    indicator: qc_status === "Complete" ? "green"
                             : qc_status === "Blocked"  ? "red"
                             : "orange",
                });
            },
        });
    },
});

// ── QC Status badge ────────────────────────────────────────────────────────

const QC_STATUS_COLORS = {
    "Not Started": "gray",
    "In Progress":  "orange",
    "Complete":     "green",
    "Blocked":      "red",
};

function _render_qc_status_badge(frm) {
    const status = frm.doc.custom_qc_status;
    if (!status) return;
    frm.page.set_indicator(__(status), QC_STATUS_COLORS[status] || "gray");
}

// ── QC Progress bar ────────────────────────────────────────────────────────

function _render_qc_progress(frm) {
    const rows = frm.doc.custom_qc_checklist || [];
    const total = rows.length;
    if (!total) return;
    const verified = rows.filter(r => r.is_verified).length;
    _render_qc_progress_data(frm, verified, total, frm.doc.custom_qc_status);
}

function _render_qc_progress_data(frm, verified, total, status) {
    if (!total) return;
    const pct = Math.round((verified / total) * 100);
    const color = QC_STATUS_COLORS[status] || "gray";
    const barColor = color === "green" ? "#28a745"
                   : color === "red"   ? "#dc3545"
                   : color === "orange"? "#fd7e14"
                   : "#adb5bd";

    // Frappe dashboard section helper
    frm.dashboard.reset();
    frm.dashboard.add_progress(
        __("QC Progress — {0}/{1} verified ({2}%)", [verified, total, pct]),
        pct,
        barColor
    );
}

// ── SIG button group ───────────────────────────────────────────────────────

function _add_sig_buttons(frm) {
    if (frm.is_new()) return;

    // Apply QC Template
    frm.add_custom_button(__("Apply QC Template"), () => {
        if (!frm.doc.custom_qc_template) {
            frappe.msgprint(__("Please select a QC Template first."));
            return;
        }
        frappe.confirm(
            __('Apply template "{0}"? Existing checklist rows will be replaced.', [frm.doc.custom_qc_template]),
            () => _do_apply_qc_template(frm)
        );
    }, __("SIG"));

    // Geocode Address
    frm.add_custom_button(__("Geocode Address"), () => {
        const address = [frm.doc.custom_site_address, frm.doc.custom_city]
            .filter(Boolean).join(", ");
        if (!address) {
            frappe.msgprint(__("Please fill in Site Address or City before geocoding."));
            return;
        }
        _do_geocode(frm, address);
    }, __("SIG"));

    // Open in Map (only if geocoded)
    if (frm.doc.custom_latitude && frm.doc.custom_longitude) {
        frm.add_custom_button(__("Open in Map"), () => {
            window.open(
                `/project-map?project=${encodeURIComponent(frm.doc.name)}`,
                "_blank"
            );
        }, __("SIG"));
    }

    // Recalculate QC Status
    if ((frm.doc.custom_qc_checklist || []).length) {
        frm.add_custom_button(__("Recalculate QC"), () => {
            frappe.call({
                method: "orderlift.orderlift_sig.utils.project_qc.calculate_qc_status",
                args: { project_name: frm.doc.name },
                callback(r) {
                    if (!r.exc) {
                        frm.set_value("custom_qc_status", r.message);
                        frappe.show_alert({ message: __("QC status: {0}", [r.message]), indicator: "green" });
                    }
                },
            });
        }, __("SIG"));
    }
}

// ── Apply QC Template ──────────────────────────────────────────────────────

function _do_apply_qc_template(frm) {
    frappe.show_progress(__("Applying QC Template…"), 0, 100);
    frappe.call({
        method: "orderlift.orderlift_sig.utils.project_qc.apply_qc_template",
        args: {
            project_name: frm.doc.name,
            template_name: frm.doc.custom_qc_template,
        },
        callback(r) {
            frappe.hide_progress();
            if (r.exc) return;
            const { qc_status, total_items } = r.message;
            frappe.show_alert({
                message: __("Template applied — {0} items loaded. Status: {1}", [total_items, qc_status]),
                indicator: "green",
            });
            frm.reload_doc();
        },
    });
}

// ── Geocode via Nominatim (free OSM, no API key) ───────────────────────────

function _do_geocode(frm, address) {
    frm.set_value("custom_geocode_status", "Geocoding…");
    const url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
        + encodeURIComponent(address);

    fetch(url, { headers: { "Accept-Language": "en" } })
        .then(r => r.json())
        .then(results => {
            if (!results || !results.length) {
                frm.set_value("custom_geocode_status", "Not found");
                frappe.show_alert({ message: __("Address not found by geocoder."), indicator: "orange" });
                return;
            }
            const { lat, lon, display_name } = results[0];
            frm.set_value("custom_latitude",  parseFloat(lat));
            frm.set_value("custom_longitude", parseFloat(lon));
            frm.set_value("custom_geocode_status",
                "OK — " + display_name.substring(0, 80));
            frappe.show_alert({ message: __("Coordinates updated."), indicator: "green" });
            frm.save();
        })
        .catch(err => {
            frm.set_value("custom_geocode_status", "Error");
            frappe.show_alert({ message: __("Geocoding failed: {0}", [err.message]), indicator: "red" });
        });
}
