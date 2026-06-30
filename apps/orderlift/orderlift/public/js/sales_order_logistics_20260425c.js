let ORDERLIFT_SO_STATUS_NAMES = null;
let ORDERLIFT_SO_STATUS_COLORS = null;
let ORDERLIFT_SO_STATUS_NAMES_PROMISE = null;

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (frm.is_new()) return;

        _add_orderlift_print_shortcut(frm);
        _render_so_scenario_badge(frm);
        _render_so_status_bar(frm);
        _load_so_status_names().then(() => _render_so_status_bar(frm));

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

    custom_orderlift_order_status(frm) {
        _render_so_status_bar(frm);
    },
    custom_crm_business_type(frm) {
        _render_so_status_bar(frm);
    },
    custom_crm_segment(frm) {
        _render_so_status_bar(frm);
    },
    custom_installation_project(frm) {
        _render_so_status_bar(frm);
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

function _render_so_scenario_badge(frm) {
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
            <span class="ol-order-status-step ${_scenario_status_color(flow)}" role="listitem">
                <span class="ol-status-step-icon">${frappe.utils.escape_html(badge_icon)}</span>
                <span class="ol-status-step-text">${frappe.utils.escape_html(flow)}</span>
            </span>
            <span class="ol-order-status-step ${resp_class === "tag-customer" ? "ol-status-orange" : "ol-status-blue"}" role="listitem">
                <span class="ol-status-step-icon">${_order_status_icon(resp_class === "tag-customer" ? "user" : "truck")}</span>
                <span class="ol-status-step-text">${frappe.utils.escape_html(responsibility)}</span>
            </span>
        </div>
    `;

    _ensure_scenario_bar_styles();
    _insert_so_status_bar(frm, html);
}

function _scenario_status_color(flow) {
    if (flow === "Inbound") return "ol-status-blue";
    if (flow === "Domestic") return "ol-status-green";
    if (flow === "Outbound") return "ol-status-orange";
    return "ol-status-gray";
}

function _render_so_status_bar(frm) {
    frm.page.inner_toolbar.find(".ol-order-status-bar").remove();
    if (frm.$wrapper) frm.$wrapper.find(".ol-order-status-bar").remove();

    const chips = [
        _order_status_chip(__("Order Status"), _selected_so_status(frm), "custom", "check"),
        _order_status_chip(__("Type"), frm.doc.custom_crm_business_type || __("Not set"), "type", "truck"),
        _order_status_chip(__("Segment"), frm.doc.custom_crm_segment || __("Not set"), "segment", "tool"),
    ];
    if (frm.doc.custom_installation_project) {
        chips.push(_order_project_chip(__("Project"), frm.doc.custom_installation_project));
    }

    const html = `
        <div class="ol-order-status-bar ol-order-status-flow" role="list">
            ${chips.join("")}
        </div>
    `;
    _ensure_order_status_styles();
    _insert_so_status_bar(frm, html);
}

function _insert_so_status_bar(frm, html) {
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

function _selected_so_status(frm) {
    if (frm.doc.custom_orderlift_order_status) return frm.doc.custom_orderlift_order_status;
    if (frm.doc.status && ORDERLIFT_SO_STATUS_NAMES && ORDERLIFT_SO_STATUS_NAMES.has(frm.doc.status)) {
        return frm.doc.status;
    }
    return __("Not set");
}

function _load_so_status_names() {
    if (ORDERLIFT_SO_STATUS_NAMES) return Promise.resolve(ORDERLIFT_SO_STATUS_NAMES);
    if (!ORDERLIFT_SO_STATUS_NAMES_PROMISE) {
        ORDERLIFT_SO_STATUS_NAMES_PROMISE = frappe.call({
            method: "orderlift.orderlift_crm.api.status_control.get_status_control_data",
            args: { document_type: "Sales Order" },
        }).then((res) => {
            ORDERLIFT_SO_STATUS_COLORS = {};
            ORDERLIFT_SO_STATUS_NAMES = new Set();
            ((res.message && res.message.statuses) || []).filter((row) => row.is_active).forEach((row) => {
                if (row.name) {
                    ORDERLIFT_SO_STATUS_NAMES.add(row.name);
                    ORDERLIFT_SO_STATUS_COLORS[row.name] = _status_color_class(row.color);
                }
            });
            return ORDERLIFT_SO_STATUS_NAMES;
        }).catch((error) => {
            console.error("Unable to load Orderlift order statuses", error);
            ORDERLIFT_SO_STATUS_NAMES = new Set();
            ORDERLIFT_SO_STATUS_COLORS = {};
            return ORDERLIFT_SO_STATUS_NAMES;
        });
    }
    return ORDERLIFT_SO_STATUS_NAMES_PROMISE;
}

function _order_status_chip(label, value, tone, icon) {
    const color = _order_status_chip_color(value, tone);
    const displayValue = value === __("Not set") ? `${label} ${__("not set")}` : value;
    const title = frappe.utils.escape_html(`${label}: ${displayValue}`);
    return `
        <span class="ol-order-status-step ol-status-${color}" role="listitem" title="${title}" aria-label="${title}">
            <span class="ol-status-step-icon">${_order_status_icon(icon)}</span>
            ${_order_status_text(displayValue, tone)}
        </span>
    `;
}

function _order_status_text(displayValue, tone) {
    const clean = String(displayValue || "");
    if (tone === "custom" && clean.includes(" - ")) {
        const parts = clean.split(" - ");
        const status = parts.pop();
        const context = parts.join(" - ");
        return `
            <span class="ol-status-step-text ol-status-step-text-stack">
                <span>${frappe.utils.escape_html(context)}</span>
                <small>${frappe.utils.escape_html(status)}</small>
            </span>
        `;
    }
    return `<span class="ol-status-step-text">${frappe.utils.escape_html(clean)}</span>`;
}

function _order_project_chip(label, value) {
    const href = `/app/project/${encodeURIComponent(value)}`;
    const title = frappe.utils.escape_html(`${label}: ${value}`);
    return `
        <a class="ol-order-status-step ol-status-green ol-status-link" href="${href}" role="listitem" title="${title}" aria-label="${title}">
            <span class="ol-status-step-icon">${_order_status_icon("file")}</span>
            <span class="ol-status-step-text">${frappe.utils.escape_html(value)}</span>
            <span class="ol-status-external">${_order_status_icon("external-link")}</span>
        </a>
    `;
}

function _order_status_icon(icon) {
    if (frappe.utils && frappe.utils.icon) return frappe.utils.icon(icon, "sm");
    return "";
}

function _add_orderlift_print_shortcut(frm) {
    if (!frm || !frm.page || !frm.page.wrapper || !frm.doc || !frm.doc.name) return;

    const page = $(frm.page.wrapper);
    page.find(".ol-print-shortcut").remove();

    const actions = page.find(".page-actions").first();
    if (!actions.length) return;

    const title = frappe.utils.escape_html(__("Print"));
    const button = $(`
        <button type="button" class="btn btn-default btn-sm ol-print-shortcut" title="${title}" aria-label="${title}">
            ${_order_status_icon("printer")}
            <span class="hidden-xs">${title}</span>
        </button>
    `);
    button.on("click", () => {
        const url = `/printview?doctype=${encodeURIComponent(frm.doctype)}&name=${encodeURIComponent(frm.doc.name)}&trigger_print=1`;
        window.open(url, "_blank");
    });
    actions.prepend(button);
}

function _ensure_order_status_styles() {
    if (document.getElementById("ol-order-status-flow-style")) return;
    const css = `
        .ol-order-status-flow {
            display: flex;
            align-items: center;
            gap: 5px;
            flex-wrap: wrap;
            margin: 0 0 6px;
            padding: 6px;
            border: 1px solid var(--border-color, #d8dee8);
            border-radius: 9px;
            background: linear-gradient(135deg, rgba(255,255,255,.96), rgba(248,250,252,.9));
            box-shadow: none;
        }
        .ol-order-status-step {
            position: relative;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            min-height: 24px;
            max-width: 100%;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            line-height: 1.2;
            text-decoration: none;
            white-space: nowrap;
        }
        .ol-order-status-step:not(:last-child)::after {
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
        .ol-status-step-icon,
        .ol-status-external {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
        }
        .ol-status-step-icon .icon,
        .ol-status-external .icon {
            stroke: currentColor;
        }
        .ol-status-step-text {
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .ol-status-step-text-stack {
            display: flex;
            min-width: 0;
            flex-direction: column;
            gap: 1px;
        }
        .ol-status-step-text-stack small {
            color: currentColor;
            font-size: 9px;
            font-weight: 550;
            opacity: .86;
        }
        .ol-status-blue { color: #0b5ed7; background: linear-gradient(135deg, #eef5ff, #f7fbff); }
        .ol-status-green { color: #0f8f72; background: linear-gradient(135deg, #e9f8f3, #f5fbf8); }
        .ol-status-orange { color: #d96b0b; background: linear-gradient(135deg, #fff3e8, #fff8f1); }
        .ol-status-purple { color: #7c3aed; background: linear-gradient(135deg, #f4efff, #fbf8ff); }
        .ol-status-red { color: #d92d20; background: linear-gradient(135deg, #fff1f0, #fff8f7); }
        .ol-status-gray { color: #475569; background: linear-gradient(135deg, #f1f5f9, #f8fafc); }
        .ol-status-link:hover { color: #08745e; text-decoration: none; filter: brightness(.98); }
        .ol-print-shortcut {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            margin-right: 8px;
            min-height: 32px;
        }
        .ol-print-shortcut .icon { stroke: currentColor; }
        @media (max-width: 768px) {
            .ol-order-status-flow { gap: 4px; padding: 4px; }
            .ol-order-status-step { flex: 1 1 132px; justify-content: center; padding: 3px 7px; font-size: 10px; }
            .ol-order-status-step:not(:last-child)::after { display: none; }
        }
    `;
    $("head").append(`<style id="ol-order-status-flow-style">${css}</style>`);
}

function _ensure_scenario_bar_styles() {
    if (document.getElementById("ol-thin-scenario-bar-style")) return;
    $("head").append(`
        <style id="ol-thin-scenario-bar-style">
            .ol-thin-scenario-bar {
                display: flex;
                align-items: center;
                gap: 5px;
                flex-wrap: wrap;
                padding: 6px;
                margin: 0 0 5px;
            }
        </style>
    `);
}

function _order_status_chip_color(value, tone) {
    const status = (value || "").toLowerCase();

    if (!value || value === __("Not set")) return "gray";
    if (tone === "custom" && ORDERLIFT_SO_STATUS_COLORS && ORDERLIFT_SO_STATUS_COLORS[value]) {
        return ORDERLIFT_SO_STATUS_COLORS[value];
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
    if (status === "completed") return "green";
    if (["cancelled", "closed"].includes(status)) return "red";
    if (status.startsWith("to ")) return "orange";

    return tone === "custom" ? "blue" : "gray";
}

function _status_color_class(color) {
    const clean = String(color || "").trim().toLowerCase();
    return ["gray", "blue", "green", "orange", "red", "purple"].includes(clean) ? clean : "blue";
}
