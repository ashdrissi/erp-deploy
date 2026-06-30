// Project SIG — Frappe form enhancements for ERPNext Project doctype
// S1: Apply QC Template button, Geocode Address button, QC status badge colouring
// S2: QC progress bar, open-in-map shortcut, QC item verification from form

frappe.ui.form.on("Project", {
    refresh(frm) {
        _render_qc_status_badge(frm);
        _render_project_status_bar(frm);
        _render_qc_progress(frm);
        _render_project_contracts(frm);
        _render_project_documents(frm);
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

// ── Project Documents tab (opportunity / quotations / sales orders / …) ──────

function _render_project_documents(frm) {
    _ensure_project_documents_styles();
    const field = frm.get_field("custom_documents_html");
    if (!field || !field.$wrapper) return;

    if (frm.is_new()) {
        field.$wrapper.html(`<div class="ol-pdocs-empty">${__("Save the project to see its linked documents.")}</div>`);
        return;
    }

    field.$wrapper.html(`<div class="ol-pdocs-loading">${__("Loading linked documents…")}</div>`);
    frappe.call({
        method: "orderlift.orderlift_crm.api.pipeline.get_project_documents",
        args: { project: frm.doc.name },
    }).then((r) => {
        field.$wrapper.html(_project_documents_markup(r.message || {}));
        _bind_project_documents(frm, field.$wrapper);
    }).catch((error) => {
        console.error("Unable to load project documents", error);
        field.$wrapper.html(`<div class="ol-pdocs-empty text-danger">${__("Could not load linked documents.")}</div>`);
    });
}

function _pdoc_badge(doctype) {
    const map = {
        "Opportunity": ["OPP", "#6366f1"],
        "Quotation": ["QTN", "#0ea5e9"],
        "Sales Order": ["SO", "#16a34a"],
        "Material Request": ["MR", "#0891b2"],
        "Purchase Order": ["PO", "#a855f7"],
        "Purchase Receipt": ["PR", "#ca8a04"],
        "Purchase Invoice": ["PINV", "#be123c"],
        "Pick List": ["PICK", "#0369a1"],
        "Delivery Note": ["DN", "#f59e0b"],
        "Sales Invoice": ["INV", "#ef4444"],
        "Payment Entry": ["PAY", "#0d9488"],
        "Journal Entry": ["JE", "#475569"],
        "Stock Entry": ["SE", "#7c3aed"],
        "Work Order": ["WO", "#b45309"],
    };
    const entry = map[doctype] || ["DOC", "#64748b"];
    return `<span class="ol-pdocs-badge" style="background:${entry[1]}">${entry[0]}</span>`;
}

function _pdoc_status_class(status) {
    const s = String(status || "").toLowerCase();
    if (/(paid|completed|complete|ordered|delivered|closed|won|approved|submitted|received)/.test(s)) return "is-green";
    if (/(lost|cancel|rejected|return|overdue|unpaid|expired)/.test(s)) return "is-red";
    if (/(draft|open|to deliver|to receive|to bill|pending|replied|quoted|partial)/.test(s)) return "is-amber";
    return "is-gray";
}

function _project_documents_markup(data) {
    const opp = data.opportunity;
    const groups = data.groups || [];
    const total = data.total || 0;
    if (!opp && !groups.length) {
        return `<div class="ol-pdocs-empty">${__("No linked documents yet. Create a quotation, sales order or project from the opportunity to see them here.")}</div>`;
    }

    const oppCard = opp ? `
        <a class="ol-pdocs-opp" data-open-doc="Opportunity" data-open-name="${frappe.utils.escape_html(opp.name)}">
            ${_pdoc_badge("Opportunity")}
            <div class="ol-pdocs-opp-body">
                <span class="ol-pdocs-opp-label">${__("Source Opportunity")}</span>
                <strong>${frappe.utils.escape_html(opp.title || opp.name)}</strong>
                <small>${frappe.utils.escape_html(opp.name)}</small>
            </div>
            <div class="ol-pdocs-opp-meta">
                <span class="ol-pdocs-pill ${_pdoc_status_class(opp.status)}">${frappe.utils.escape_html(opp.status || "-")}</span>
                ${opp.amount ? `<span class="ol-pdocs-amount">${format_currency(opp.amount)}</span>` : ""}
            </div>
        </a>` : "";

    const groupCards = groups.map((g) => `
        <div class="ol-pdocs-group">
            <div class="ol-pdocs-group-head">
                ${_pdoc_badge(g.doctype)}
                <span class="ol-pdocs-group-title">${frappe.utils.escape_html(g.label)}</span>
                <span class="ol-pdocs-count">${g.items.length}</span>
            </div>
            <div class="ol-pdocs-list">
                ${g.items.map((it) => `
                    <a class="ol-pdocs-item" data-open-doc="${frappe.utils.escape_html(g.doctype)}" data-open-name="${frappe.utils.escape_html(it.name)}">
                        <span class="ol-pdocs-item-name">${frappe.utils.escape_html(it.name)}</span>
                        <span class="ol-pdocs-pill ${_pdoc_status_class(it.status)}">${frappe.utils.escape_html(it.status || "-")}</span>
                    </a>`).join("")}
            </div>
        </div>`).join("");

    return `
        <div class="ol-pdocs">
            <div class="ol-pdocs-head">
                <h4>${__("Linked Documents")}</h4>
                <span class="ol-pdocs-total">${total} ${__("linked")}</span>
            </div>
            ${oppCard}
            <div class="ol-pdocs-grid">${groupCards || `<div class="ol-pdocs-empty">${__("No sales documents linked yet.")}</div>`}</div>
        </div>`;
}

function _bind_project_documents(frm, wrapper) {
    wrapper.find("[data-open-doc]").on("click", function () {
        const dt = $(this).data("open-doc");
        const name = $(this).data("open-name");
        if (dt && name) frappe.set_route("Form", dt, String(name));
    });
}

function _ensure_project_documents_styles() {
    if (document.getElementById("ol-pdocs-style")) return;
    const style = document.createElement("style");
    style.id = "ol-pdocs-style";
    style.textContent = `
        .ol-pdocs { margin-top: 8px; }
        .ol-pdocs-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
        .ol-pdocs-head h4 { margin:0; font-size:15px; font-weight:700; color:#1f272e; }
        .ol-pdocs-total { font-size:11px; color:#64748b; background:#f1f5f9; padding:3px 10px; border-radius:999px; font-weight:600; }
        .ol-pdocs-empty, .ol-pdocs-loading { padding:18px; color:#64748b; background:#f8fafc; border:1px dashed #d8e2ee; border-radius:10px; text-align:center; }
        .ol-pdocs-badge { min-width:36px; height:24px; padding:0 6px; border-radius:7px; display:inline-flex; align-items:center; justify-content:center; font-size:9.5px; font-weight:800; color:#fff; letter-spacing:.03em; flex-shrink:0; }
        .ol-pdocs-opp { display:flex; align-items:center; gap:14px; padding:14px 16px; border:1px solid #e2e8f0; border-left:4px solid #6366f1; border-radius:12px; background:linear-gradient(180deg,#fbfbff,#ffffff); margin-bottom:16px; text-decoration:none; transition:box-shadow .15s,transform .15s; }
        .ol-pdocs-opp:hover { box-shadow:0 6px 18px rgba(99,102,241,.15); transform:translateY(-1px); text-decoration:none; }
        .ol-pdocs-opp-body { display:flex; flex-direction:column; flex:1; min-width:0; }
        .ol-pdocs-opp-body strong { color:#1f272e; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .ol-pdocs-opp-body small { color:#94a3b8; font-size:11px; }
        .ol-pdocs-opp-label { font-size:10px; text-transform:uppercase; letter-spacing:.07em; color:#6366f1; font-weight:700; }
        .ol-pdocs-opp-meta { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
        .ol-pdocs-amount { font-weight:700; color:#0f172a; font-size:13px; }
        .ol-pdocs-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px; }
        .ol-pdocs-group { border:1px solid #e6edf3; border-radius:12px; background:#fff; overflow:hidden; }
        .ol-pdocs-group-head { display:flex; align-items:center; gap:8px; padding:10px 12px; background:#f8fafc; border-bottom:1px solid #eef2f6; }
        .ol-pdocs-group-title { font-weight:700; font-size:12px; color:#334155; flex:1; }
        .ol-pdocs-count { background:#e2e8f0; color:#475569; border-radius:999px; padding:1px 9px; font-size:11px; font-weight:700; }
        .ol-pdocs-list { display:flex; flex-direction:column; }
        .ol-pdocs-item { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:9px 12px; border-bottom:1px solid #f1f5f9; text-decoration:none; transition:background .12s; }
        .ol-pdocs-item:last-child { border-bottom:0; }
        .ol-pdocs-item:hover { background:#f8fafc; text-decoration:none; }
        .ol-pdocs-item-name { font-size:12.5px; color:#1d4ed8; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .ol-pdocs-pill { font-size:10px; font-weight:700; padding:2px 8px; border-radius:999px; white-space:nowrap; }
        .ol-pdocs-pill.is-green { background:#dcfce7; color:#15803d; }
        .ol-pdocs-pill.is-red { background:#fee2e2; color:#b91c1c; }
        .ol-pdocs-pill.is-amber { background:#fef3c7; color:#b45309; }
        .ol-pdocs-pill.is-gray { background:#eef2f6; color:#475569; }
    `;
    document.head.appendChild(style);
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
    if (frm.$wrapper) frm.$wrapper.find(".ol-project-status-bar").remove();
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

    _ensure_project_status_bar_styles();
    _insert_project_status_bar(frm, `
        <div class="ol-project-status-bar ol-order-status-flow" role="list">
            ${statusChips.join("")}
        </div>
    `);
}

function _insert_project_status_bar(frm, html) {
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

function _ensure_project_status_bar_styles() {
    if (document.getElementById("ol-project-status-bar-style")) return;
    $("head").append(`
        <style id="ol-project-status-bar-style">
            .ol-project-status-bar.ol-order-status-flow {
                display: flex;
                align-items: center;
                gap: 5px;
                flex-wrap: wrap;
                padding: 6px;
                margin: 0 0 6px;
                border: 1px solid var(--border-color, #d8dee8);
                border-radius: 9px;
                background: linear-gradient(135deg, rgba(255,255,255,.96), rgba(248,250,252,.9));
            }
            .ol-project-status-bar .ol-order-status-step {
                position: relative;
                display: inline-flex;
                align-items: center;
                gap: 5px;
                min-height: 24px;
                max-width: 190px;
                padding: 3px 8px;
                border-radius: 999px;
                font-size: 11px;
                line-height: 1.2;
                font-weight: 600;
                text-decoration: none;
                white-space: nowrap;
            }
            .ol-project-status-bar .ol-order-status-step:not(:last-child)::after {
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
            .ol-project-status-bar .ol-status-step-icon,
            .ol-project-status-bar .ol-status-external {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                flex: 0 0 auto;
            }
            .ol-project-status-bar .ol-status-step-icon .icon,
            .ol-project-status-bar .ol-status-external .icon { stroke: currentColor; }
            .ol-project-status-bar .ol-status-step-text {
                min-width: 0;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .ol-project-status-bar .ol-status-blue { color: #0b5ed7; background: linear-gradient(135deg, #eef5ff, #f7fbff); }
            .ol-project-status-bar .ol-status-green { color: #0f8f72; background: linear-gradient(135deg, #e9f8f3, #f5fbf8); }
            .ol-project-status-bar .ol-status-orange { color: #d96b0b; background: linear-gradient(135deg, #fff3e8, #fff8f1); }
            .ol-project-status-bar .ol-status-purple { color: #7c3aed; background: linear-gradient(135deg, #f4efff, #fbf8ff); }
            .ol-project-status-bar .ol-status-red { color: #d92d20; background: linear-gradient(135deg, #fff1f0, #fff8f7); }
            .ol-project-status-bar .ol-status-gray { color: #475569; background: linear-gradient(135deg, #f1f5f9, #f8fafc); }
            .ol-project-status-bar .ol-status-link:hover { color: #08745e; text-decoration: none; filter: brightness(.98); }
            @media (max-width: 767px) {
                .ol-project-status-bar.ol-order-status-flow { gap: 4px; margin-bottom: 5px; }
                .ol-project-status-bar .ol-order-status-step { flex: 1 1 132px; justify-content: center; max-width: none; padding: 3px 7px; font-size: 10px; }
                .ol-project-status-bar .ol-order-status-step:not(:last-child)::after { display: none; }
            }
        </style>
    `);
}

function _project_customer_chip(customer) {
    const href = `/app/customer/${encodeURIComponent(customer)}`;
    const title = frappe.utils.escape_html(`${__("Customer")}: ${customer}`);
    return `
        <a class="ol-order-status-step ol-status-green ol-status-link" href="${href}" role="listitem" title="${title}" aria-label="${title}">
            <span class="ol-status-step-icon">${_project_status_icon("user")}</span>
            <span class="ol-status-step-text">${frappe.utils.escape_html(customer)}</span>
            <span class="ol-status-external">${_project_status_icon("external-link")}</span>
        </a>
    `;
}

function _status_chip(label, value, tone) {
    const color = _project_chip_color(value, tone);
    const displayValue = value === __("Not set") ? `${label} ${__("not set")}` : value;
    const title = frappe.utils.escape_html(`${label}: ${displayValue}`);
    return `
        <span class="ol-order-status-step ol-status-${color}" role="listitem" title="${title}" aria-label="${title}">
            <span class="ol-status-step-icon">${_project_status_icon(_project_status_icon_name(tone))}</span>
            <span class="ol-status-step-text">${frappe.utils.escape_html(displayValue)}</span>
        </span>
    `;
}

function _project_status_icon(icon) {
    if (frappe.utils && frappe.utils.icon) return frappe.utils.icon(icon, "sm");
    return "";
}

function _project_status_icon_name(tone) {
    if (tone === "project") return "check";
    if (tone === "type") return "truck";
    if (tone === "segment") return "tool";
    return "file";
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
