// Project SIG — Frappe form enhancements for ERPNext Project doctype
// S1: Apply QC Template button, Geocode Address button, QC status badge colouring
// S2: QC progress bar, open-in-map shortcut, QC item verification from form

frappe.ui.form.on("Project", {
    refresh(frm) {
        _render_qc_status_badge(frm);
        _render_project_status_bar(frm);
        _render_qc_progress(frm);
        _render_project_contracts(frm);
        _add_sig_buttons(frm);
    },

    custom_project_status(frm) {
        _render_project_status_bar(frm);
    },

    status(frm) {
        _render_project_status_bar(frm);
    },

    customer(frm) {
        _render_project_status_bar(frm);
    },

    custom_crm_business_type(frm) {
        _render_project_status_bar(frm);
    },

    custom_crm_segment(frm) {
        _render_project_status_bar(frm);
    },

    custom_qc_status(frm) {
        _render_qc_status_badge(frm);
        _render_project_status_bar(frm);
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

// ── Project Contracts tab ──────────────────────────────────────────────────

function _render_project_contracts(frm) {
    _ensure_project_contract_styles();
    const field = frm.get_field("custom_contracts_html");
    if (!field || !field.$wrapper) return;

    if (frm.is_new()) {
        field.$wrapper.html(`<div class="ol-project-contracts-empty">${__("Save the project before linking contracts.")}</div>`);
        return;
    }

    field.$wrapper.html(`<div class="ol-project-contracts-loading">${__("Loading contracts...")}</div>`);
    frappe.db.get_list("Contract", {
        filters: { document_type: "Project", document_name: frm.doc.name },
        fields: ["name", "party_type", "party_name", "status", "is_signed", "start_date", "end_date", "modified"],
        order_by: "modified desc",
        limit: 50,
    }).then((rows) => {
        field.$wrapper.html(_project_contracts_markup(frm, rows || []));
        _bind_project_contracts(frm, field.$wrapper);
    }).catch((error) => {
        console.error("Unable to load project contracts", error);
        field.$wrapper.html(`<div class="ol-project-contracts-empty text-danger">${__("Could not load contracts.")}</div>`);
    });
}

function _ensure_project_contract_styles() {
    if (document.getElementById("ol-project-contracts-style")) return;
    const style = document.createElement("style");
    style.id = "ol-project-contracts-style";
    style.textContent = `
        .ol-project-contracts { border: 1px solid #dfe6ee; border-radius: 12px; background: #fff; overflow: hidden; margin-top: 8px; }
        .ol-project-contracts-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 12px 14px; background: #f8fafc; border-bottom: 1px solid #e5edf5; }
        .ol-project-contracts-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .ol-project-contracts-table { margin: 0; }
        .ol-project-contracts-table th { background: #f8fafc; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: #64748b; }
        .ol-project-contracts-empty, .ol-project-contracts-loading { padding: 16px; color: #64748b; background: #f8fafc; border: 1px dashed #d8e2ee; border-radius: 10px; }
    `;
    document.head.appendChild(style);
}

function _project_contracts_markup(frm, rows) {
    const tableRows = rows.map((row) => `
        <tr>
            <td><a href="/app/contract/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
            <td>${frappe.utils.escape_html(row.status || (row.is_signed ? __("Signed") : __("Unsigned")))}</td>
            <td>${frappe.utils.escape_html(row.party_name || "-")}</td>
            <td>${frappe.utils.escape_html([row.start_date, row.end_date].filter(Boolean).join(" - ") || "-")}</td>
            <td><button type="button" class="btn btn-xs btn-default" data-open-contract="${frappe.utils.escape_html(row.name)}">${__("Open")}</button></td>
        </tr>
    `).join("");

    return `
        <div class="ol-project-contracts">
            <div class="ol-project-contracts-head">
                <div><strong>${rows.length}</strong> ${__("contract(s) linked to this project")}</div>
                <div class="ol-project-contracts-actions">
                    <button type="button" class="btn btn-xs btn-default" data-view-project-contracts="1">${__("View List")}</button>
                    <button type="button" class="btn btn-xs btn-primary" data-new-project-contract="1">${__("New Contract")}</button>
                </div>
            </div>
            ${rows.length ? `
                <div class="table-responsive">
                    <table class="table table-bordered table-hover ol-project-contracts-table">
                        <thead><tr><th>${__("Contract")}</th><th>${__("Status")}</th><th>${__("Party")}</th><th>${__("Period")}</th><th></th></tr></thead>
                        <tbody>${tableRows}</tbody>
                    </table>
                </div>
            ` : `<div class="ol-project-contracts-empty">${__("No contracts linked yet. Create one to attach it to this project.")}</div>`}
        </div>
    `;
}

function _bind_project_contracts(frm, wrapper) {
    wrapper.find("[data-open-contract]").on("click", function () {
        frappe.set_route("Form", "Contract", $(this).data("open-contract"));
    });
    wrapper.find("[data-view-project-contracts]").on("click", function () {
        frappe.route_options = { document_type: "Project", document_name: frm.doc.name };
        frappe.set_route("List", "Contract");
    });
    wrapper.find("[data-new-project-contract]").on("click", function () {
        frappe.route_options = {
            document_type: "Project",
            document_name: frm.doc.name,
            party_type: frm.doc.customer ? "Customer" : undefined,
            party_name: frm.doc.customer || undefined,
        };
        frappe.new_doc("Contract");
    });
}

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

let PROJECT_STATUS_COLORS = null;
let PROJECT_STATUS_COLORS_PROMISE = null;

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

function _render_project_status_bar(frm) {
    frm.page.inner_toolbar.find(".ol-project-status-bar").remove();
    if (!PROJECT_STATUS_COLORS) {
        _load_project_status_colors().then(() => _render_project_status_bar(frm));
    }

    const statusChips = [
        frm.doc.customer ? _project_customer_chip(frm.doc.customer) : _status_chip(__("Customer"), __("Not set"), "legacy"),
        _status_chip(__("Project Status"), frm.doc.custom_project_status || __("Not set"), "project"),
        _status_chip(__("ERP Status"), frm.doc.status || __("Not set"), "legacy"),
        _status_chip(__("Type"), frm.doc.custom_crm_business_type || __("Not set"), "type"),
        _status_chip(__("Segment"), frm.doc.custom_crm_segment || __("Not set"), "segment"),
    ];

    frm.page.inner_toolbar.prepend(`
        <div class="ol-project-status-bar" style="display:flex;gap:8px;flex-wrap:wrap;margin:0 0 8px;">
            ${statusChips.join("")}
        </div>
    `);
}

function _project_customer_chip(customer) {
    const href = `/app/customer/${encodeURIComponent(customer)}`;
    return `
        <a class="indicator-pill no-indicator-dot whitespace-nowrap green" href="${href}">
            <span>${frappe.utils.escape_html(customer)}</span>
        </a>
    `;
}

function _status_chip(label, value, tone) {
    const color = _project_chip_color(value, tone);
    const displayValue = value === __("Not set") ? `${label} ${__("not set")}` : value;
    return `
        <span class="indicator-pill no-indicator-dot whitespace-nowrap ${color}">
            <span>${frappe.utils.escape_html(displayValue)}</span>
        </span>
    `;
}

function _load_project_status_colors() {
    if (PROJECT_STATUS_COLORS) return Promise.resolve(PROJECT_STATUS_COLORS);
    if (!PROJECT_STATUS_COLORS_PROMISE) {
        PROJECT_STATUS_COLORS_PROMISE = frappe.call({
            method: "orderlift.orderlift_crm.api.status_control.get_status_control_data",
            args: { document_type: "Project" },
        }).then((res) => {
            PROJECT_STATUS_COLORS = {};
            ((res.message && res.message.statuses) || []).filter((row) => row.is_active).forEach((row) => {
                if (row.name) {
                    PROJECT_STATUS_COLORS[row.name] = _status_color_class(row.color);
                }
            });
            return PROJECT_STATUS_COLORS;
        }).catch((error) => {
            console.error("Unable to load Project status colors", error);
            PROJECT_STATUS_COLORS = {};
            return PROJECT_STATUS_COLORS;
        });
    }
    return PROJECT_STATUS_COLORS_PROMISE;
}

function _project_chip_color(value, tone) {
    const status = String(value || "").toLowerCase();

    if (!value || value === __("Not set")) return "gray";
    if (tone === "project" && PROJECT_STATUS_COLORS && PROJECT_STATUS_COLORS[value]) {
        return PROJECT_STATUS_COLORS[value];
    }
    if (tone === "type") {
        if (status.includes("installation")) return "purple";
        if (status.includes("distribution")) return "blue";
        if (status.includes("maintenance")) return "orange";
        return "gray";
    }
    if (tone === "segment") {
        if (status.includes("grossiste")) return "green";
        if (status.includes("revendeur")) return "blue";
        if (status.includes("installateur")) return "orange";
        if (status.includes("promoteur")) return "purple";
        return "gray";
    }
    if (tone === "qc") return QC_STATUS_COLORS[value] || "gray";
    if (["completed", "complete", "installed"].includes(status)) return "green";
    if (["cancelled", "closed", "blocked"].includes(status)) return "red";
    if (status === "open") return "blue";

    return tone === "project" ? "blue" : "gray";
}

function _status_color_class(color) {
    const clean = String(color || "").trim().toLowerCase();
    return ["gray", "blue", "green", "orange", "red", "purple"].includes(clean) ? clean : "blue";
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
            frappe.route_options = { project: frm.doc.name };
            frappe.set_route("project-map");
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
