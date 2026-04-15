frappe.pages["forecast-plans"].on_page_load = function (wrapper) {
    wrapper.forecast_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Forecast Load Plans"),
        single_column: true,
    });

    renderForecastPlansPage(wrapper);
};

frappe.pages["forecast-plans"].on_page_show = function (wrapper) {
    if (wrapper._fpInitialised) loadPlansList(wrapper);
};

function renderForecastPlansPage(wrapper) {
    ensureFPFonts();
    injectFPStyles();
    wrapper._fpInitialised = true;

    wrapper.forecast_page.main.html(`
        <div class="fp-root">
            <div class="fp-topbar">
                <div class="fp-topbar-icon">
                    <svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="12" rx="2"></rect><path d="M2 11h20M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </div>
                <span class="fp-topbar-title">Forecast Load Plans</span>
                <div class="fp-topbar-space"></div>
                <button class="fp-btn-create" id="fpCreateBtn">
                    <svg viewBox="0 0 24 24" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    New Forecast Plan
                </button>
            </div>
            <div class="fp-summary-bar" id="fpSummary"></div>
            <div class="fp-filters">
                <div class="fp-filter-group">
                    <button class="fp-status-btn active" data-status="">All</button>
                    <button class="fp-status-btn" data-status="Planning">Planning</button>
                    <button class="fp-status-btn" data-status="Ready">Ready</button>
                    <button class="fp-status-btn" data-status="Loading">Loading</button>
                    <button class="fp-status-btn" data-status="In Transit">In Transit</button>
                    <button class="fp-status-btn" data-status="Delivered">Delivered</button>
                </div>
                <div class="fp-view-toggle">
                    <button class="fp-view-btn active" data-view="lanes">
                        <svg viewBox="0 0 24 24" width="13" height="13"><rect x="2" y="2" width="5" height="20" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="9.5" y="2" width="5" height="20" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="17" y="2" width="5" height="20" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                        Lanes
                    </button>
                    <button class="fp-view-btn" data-view="grid">
                        <svg viewBox="0 0 24 24" width="13" height="13"><rect x="3" y="3" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="14" y="3" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="3" y="14" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="14" y="14" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                        Grid
                    </button>
                </div>
            </div>
            <div class="fp-lanes" id="fpLanes"></div>
            <div class="fp-list" id="fpList"></div>
            <div class="fp-modal-overlay" id="fpModal">
                <div class="fp-modal">
                    <div class="fp-modal-title">New Forecast Load Plan</div>
                    <div class="fp-modal-body" id="fpModalBody"></div>
                    <div class="fp-modal-actions">
                        <button class="fp-btn-cancel" id="fpModalCancel">Cancel</button>
                        <button class="fp-btn-confirm" id="fpModalConfirm">Create & Open Planner</button>
                    </div>
                </div>
            </div>
        </div>
    `);

    bindFPEvents(wrapper);
    loadPlansList(wrapper);
}

function bindFPEvents(wrapper) {
    const root = wrapper.querySelector(".fp-root");

    root.querySelector("#fpCreateBtn").onclick = () => openCreateModal(wrapper);
    root.querySelector("#fpModalCancel").onclick = () => closeCreateModal(wrapper);
    root.querySelector("#fpModalConfirm").onclick = () => createAndOpen(wrapper);

    root.querySelectorAll(".fp-status-btn").forEach((btn) => {
        btn.onclick = () => {
            root.querySelectorAll(".fp-status-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            wrapper._fpStatusFilter = btn.dataset.status;
            loadPlansList(wrapper);
        };
    });

    root.querySelectorAll(".fp-view-btn").forEach((btn) => {
        btn.onclick = () => {
            root.querySelectorAll(".fp-view-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            wrapper._fpView = btn.dataset.view;
            loadPlansList(wrapper);
        };
    });

    // Card clicks - both lanes and grid
    root.addEventListener("click", (e) => {
        const laneCard = e.target.closest(".fp-card[data-name]");
        const gridCard = e.target.closest(".fp-plan-card[data-name]");
        const card = laneCard || gridCard;
        if (card) frappe.set_route("planning", card.dataset.name);
    });
}

function loadPlansList(wrapper) {
    const statusFilter = wrapper._fpStatusFilter || "";
    const view = wrapper._fpView || "lanes";
    const filters = {};
    if (statusFilter) filters.status = statusFilter;

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Forecast Load Plan",
            filters: filters,
            fields: [
                "name", "plan_label", "company", "container_profile",
                "route_origin", "route_destination",
                "flow_scope", "destination_zone", "departure_date",
                "deadline", "status", "total_weight_kg", "total_volume_m3",
                "creation",
            ],
            order_by: "departure_date asc, creation desc",
            limit_page_length: 200,
        },
        async: true,
        callback: (r) => {
            const plans = r.message || [];
            renderSummaryBar(wrapper, plans);
            if (view === "lanes") {
                renderKanbanLanes(wrapper, plans);
            } else {
                renderGridView(wrapper, plans);
            }
        },
    });
}

function renderSummaryBar(wrapper, plans) {
    const el = wrapper.querySelector("#fpSummary");
    if (!el) return;
    const totalVol = plans.reduce((s, p) => s + (p.total_volume_m3 || 0), 0);
    const totalWt = plans.reduce((s, p) => s + (p.total_weight_kg || 0), 0);
    const upcoming = plans.filter((p) => ["Planning", "Ready", "Loading"].includes(p.status)).length;
    const inTransit = plans.filter((p) => p.status === "In Transit").length;
    const delivered = plans.filter((p) => p.status === "Delivered").length;

    el.innerHTML = `
        <div class="fp-stat"><span class="fp-stat-val">${plans.length}</span><span class="fp-stat-lbl">Total</span></div>
        <div class="fp-stat"><span class="fp-stat-val">${upcoming}</span><span class="fp-stat-lbl">Upcoming</span></div>
        <div class="fp-stat"><span class="fp-stat-val">${inTransit}</span><span class="fp-stat-lbl">In Transit</span></div>
        <div class="fp-stat"><span class="fp-stat-val">${delivered}</span><span class="fp-stat-lbl">Delivered</span></div>
        <div class="fp-stat"><span class="fp-stat-val">${totalVol.toFixed(1)}</span><span class="fp-stat-lbl">m³ Total</span></div>
        <div class="fp-stat"><span class="fp-stat-val">${Math.round(totalWt).toLocaleString()}</span><span class="fp-stat-lbl">kg Total</span></div>
    `;
}

function renderKanbanLanes(wrapper, plans) {
    const lanesEl = wrapper.querySelector("#fpLanes");
    const listEl = wrapper.querySelector("#fpList");
    if (lanesEl) lanesEl.style.display = "";
    if (listEl) listEl.style.display = "none";

    const lanes = [
        { key: "Planning", icon: "📝", label: "Planning", color: "#FDE8BE", border: "#854F0B" },
        { key: "Ready", icon: "✅", label: "Confirmed", color: "#D8F2EA", border: "#0D6B50" },
        { key: "Loading", icon: "📦", label: "Loading", color: "#E0EFFC", border: "#1A5FA3" },
        { key: "In Transit", icon: "✈️", label: "In Transit", color: "#F0E6FF", border: "#6B3FA0" },
        { key: "Delivered", icon: "🏁", label: "Delivered", color: "#E8F5E9", border: "#2E7D32" },
    ];

    const byStatus = {};
    lanes.forEach((l) => (byStatus[l.key] = []));
    plans.forEach((p) => { if (byStatus[p.status]) byStatus[p.status].push(p); });

    if (!lanesEl) return;
    lanesEl.innerHTML = lanes.map((lane) => {
        const lanePlans = byStatus[lane.key] || [];
        return `
        <div class="fp-lane-col" data-status="${lane.key}">
            <div class="fp-lane-header" style="border-bottom-color:${lane.border}">
                <span class="fp-lane-icon">${lane.icon}</span>
                <span class="fp-lane-label">${lane.label}</span>
                <span class="fp-lane-count" style="background:${lane.color};color:${lane.border}">${lanePlans.length}</span>
            </div>
            <div class="fp-lane-body">
                ${lanePlans.length === 0
                    ? `<div class="fp-lane-empty">No containers</div>`
                    : lanePlans.map((p) => laneCardHtml(p, lane)).join("")
                }
            </div>
        </div>`;
    }).join("");
}

function renderGridView(wrapper, plans) {
    const lanesEl = wrapper.querySelector("#fpLanes");
    const listEl = wrapper.querySelector("#fpList");
    if (lanesEl) lanesEl.style.display = "none";
    if (listEl) listEl.style.display = "";

    if (!plans.length) {
        listEl.innerHTML = `
            <div class="fp-empty">
                <div class="fp-empty-icon">
                    <svg viewBox="0 0 24 24" width="48" height="48"><rect x="2" y="7" width="20" height="12" rx="2" fill="none" stroke="#C0BFB8" stroke-width="1.5"></rect><path d="M2 11h20" fill="none" stroke="#C0BFB8" stroke-width="1.5"></path></svg>
                </div>
                <div class="fp-empty-text">No forecast plans yet</div>
                <div class="fp-empty-sub">Create one to start planning container loads</div>
            </div>
        `;
        return;
    }
    listEl.innerHTML = plans.map((p) => planCardHtml(p)).join("");
}

function laneCardHtml(p, lane) {
    const route = (p.route_origin && p.route_destination)
        ? `${esc(p.route_origin)} → ${esc(p.route_destination)}`
        : "";
    const dep = p.departure_date ? frappe.datetime.str_to_user(p.departure_date) : "";
    const vol = (p.total_volume_m3 || 0).toFixed(1);
    const wt = Math.round(p.total_weight_kg || 0).toLocaleString();
    const pctVol = p.total_volume_m3 > 0 ? Math.min(100, Math.round((p.total_volume_m3 / 67.7) * 100)) : 0;

    return `
    <div class="fp-card" data-name="${esc(p.name)}">
        <div class="fp-card-top">
            <span class="fp-card-name">${esc(p.plan_label || p.name)}</span>
            <span class="fp-card-ref" style="color:${lane.border}">${esc(p.name)}</span>
        </div>
        ${route ? `<div class="fp-card-route">${route}</div>` : ""}
        <div class="fp-card-details">
            ${dep ? `<span class="fp-card-dep">📅 ${dep}</span>` : ""}
            <span class="fp-card-vol">📦 ${vol} m³</span>
            <span class="fp-card-wt">⚖️ ${wt} kg</span>
        </div>
        <div class="fp-card-bar"><div class="fp-card-bar-fill" style="width:${pctVol}%;background:${lane.border}"></div></div>
        <div class="fp-card-footer">
            <span class="fp-card-container">${esc(p.container_profile || "—")}</span>
            ${p.flow_scope ? `<span class="fp-card-flow">${esc(p.flow_scope)}</span>` : ""}
        </div>
    </div>`;
}

function esc(v) { return frappe.utils.escape_html(v || ""); }

function planCardHtml(p) {
    const statusColors = {
        Planning: { bg: "#FDE8BE", text: "#854F0B" },
        Ready: { bg: "#D8F2EA", text: "#0D6B50" },
        Loading: { bg: "#E0EFFC", text: "#1A5FA3" },
        "In Transit": { bg: "#F0E6FF", text: "#6B3FA0" },
        Delivered: { bg: "#D8F2EA", text: "#0D6B50" },
        Cancelled: { bg: "#EEECEA", text: "#5F5E5A" },
        Converted: { bg: "#E0EFFC", text: "#1A5FA3" }, // backwards compat
    };
    const sc = statusColors[p.status] || statusColors.Planning;
    const depDate = p.departure_date ? frappe.datetime.str_to_user(p.departure_date) : "—";
    const deadlineDate = p.deadline ? frappe.datetime.str_to_user(p.deadline) : "";
    const vol = (p.total_volume_m3 || 0).toFixed(1);
    const wt = Math.round(p.total_weight_kg || 0).toLocaleString();
    const route = (p.route_origin && p.route_destination)
        ? `${frappe.utils.escape_html(p.route_origin)} → ${frappe.utils.escape_html(p.route_destination)}`
        : "";

    return `
        <div class="fp-plan-card" data-name="${frappe.utils.escape_html(p.name)}">
            <div class="fp-card-top">
                <div class="fp-card-label">${frappe.utils.escape_html(p.plan_label || p.name)}</div>
                <span class="fp-card-status" style="background:${sc.bg};color:${sc.text}">${frappe.utils.escape_html(p.status)}</span>
            </div>
            ${route ? `<div class="fp-card-route">${route}</div>` : ""}
            <div class="fp-card-meta">
                <span>${frappe.utils.escape_html(p.name)}</span>
                <span>${frappe.utils.escape_html(p.company || "")}</span>
                <span>${frappe.utils.escape_html(p.flow_scope || "")}</span>
            </div>
            <div class="fp-card-metrics">
                <div class="fp-card-metric"><strong>${vol}</strong> m3</div>
                <div class="fp-card-metric"><strong>${wt}</strong> kg</div>
                <div class="fp-card-metric">Dep: <strong>${depDate}</strong></div>
                ${deadlineDate ? `<div class="fp-card-metric">Due: <strong>${deadlineDate}</strong></div>` : ""}
            </div>
            <div class="fp-card-zone">${frappe.utils.escape_html(p.destination_zone || "")}</div>
        </div>
    `;
}

function openCreateModal(wrapper) {
    const body = wrapper.querySelector("#fpModalBody");
    body.innerHTML = "";
    wrapper._fpFields = {};

    const fields = [
        { key: "plan_label", label: "Plan Label", type: "text", required: true, placeholder: "e.g. Bangkok Export Apr W3" },
        { key: "company", label: "Company", type: "link", options: "Company", required: true },
        { key: "container_profile", label: "Container Profile", type: "link", options: "Container Profile" },
        { key: "route_origin", label: "Origin", type: "text", placeholder: "e.g. Bangkok, Shanghai" },
        { key: "route_destination", label: "Destination", type: "text", placeholder: "e.g. Casablanca, Paris" },
        { key: "flow_scope", label: "Flow Scope", type: "select", options: ["", "Inbound", "Domestic", "Outbound"] },
        { key: "shipping_responsibility", label: "Shipping Responsibility", type: "select", options: ["", "Orderlift", "Customer"] },
        { key: "destination_zone", label: "Destination Zone", type: "text", placeholder: "e.g. Casablanca Central" },
        { key: "departure_date", label: "Departure Date", type: "date" },
        { key: "deadline", label: "Deadline", type: "date" },
    ];

    fields.forEach((f) => {
        const row = document.createElement("div");
        row.className = "fp-field-row";

        const label = document.createElement("label");
        label.textContent = f.label + (f.required ? " *" : "");
        label.className = "fp-field-label";
        row.appendChild(label);

        let input;
        if (f.type === "select") {
            input = document.createElement("select");
            input.className = "fp-field-input";
            f.options.forEach((opt) => {
                const o = document.createElement("option");
                o.value = opt;
                o.textContent = opt || "— Select —";
                input.appendChild(o);
            });
        } else if (f.type === "link") {
            input = document.createElement("input");
            input.className = "fp-field-input";
            input.type = "text";
            input.placeholder = f.placeholder || f.options;
            input.dataset.linkDoctype = f.options;
            // Use frappe awesomebar-style autocomplete
            $(input).on("input", frappe.utils.debounce(function () {
                const val = this.value;
                if (val.length < 2) return;
                frappe.call({
                    method: "frappe.client.get_list",
                    args: { doctype: f.options, filters: { name: ["like", `%${val}%`] }, fields: ["name"], limit_page_length: 5 },
                    async: true,
                    callback: (r) => {
                        // Simple datalist
                        let dl = document.getElementById(`dl-${f.key}`);
                        if (!dl) {
                            dl = document.createElement("datalist");
                            dl.id = `dl-${f.key}`;
                            input.setAttribute("list", dl.id);
                            input.parentNode.appendChild(dl);
                        }
                        dl.innerHTML = (r.message || []).map((d) => `<option value="${frappe.utils.escape_html(d.name)}">`).join("");
                    },
                });
            }, 300));
        } else {
            input = document.createElement("input");
            input.className = "fp-field-input";
            input.type = f.type === "date" ? "date" : "text";
            if (f.placeholder) input.placeholder = f.placeholder;
        }

        wrapper._fpFields[f.key] = input;
        row.appendChild(input);
        body.appendChild(row);
    });

    wrapper.querySelector("#fpModal").classList.add("show");
}

function closeCreateModal(wrapper) {
    wrapper.querySelector("#fpModal").classList.remove("show");
}

function createAndOpen(wrapper) {
    const fields = wrapper._fpFields;
    const plan_label = fields.plan_label.value.trim();
    const company = fields.company.value.trim();

    if (!plan_label) { frappe.throw(__("Plan Label is required")); return; }
    if (!company) { frappe.throw(__("Company is required")); return; }

    const vals = {
        doctype: "Forecast Load Plan",
        plan_label: plan_label,
        company: company,
        container_profile: fields.container_profile.value.trim() || undefined,
        route_origin: fields.route_origin.value.trim() || undefined,
        route_destination: fields.route_destination.value.trim() || undefined,
        flow_scope: fields.flow_scope.value || undefined,
        shipping_responsibility: fields.shipping_responsibility.value || undefined,
        destination_zone: fields.destination_zone.value.trim() || undefined,
        departure_date: fields.departure_date.value || undefined,
        deadline: fields.deadline.value || undefined,
    };

    frappe.call({
        method: "frappe.client.insert",
        args: { doc: vals },
        async: true,
        callback: (r) => {
            if (r.message) {
                closeCreateModal(wrapper);
                frappe.set_route("planning", r.message.name);
            }
        },
    });
}

function ensureFPFonts() {
    if (document.getElementById("fp-font-outfit")) return;
    const link = document.createElement("link");
    link.id = "fp-font-outfit";
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(link);
}

function injectFPStyles() {
    if (document.getElementById("fp-styles")) return;
    const style = document.createElement("style");
    style.id = "fp-styles";
    style.textContent = `
        .fp-root {
            --bg: #F4F3F0; --surface: #FFFFFF; --accent: #027384; --accent-lt: #E0F4F6;
            --teal: #0D6B50; --teal-lt: #D8F2EA; --blue: #1A5FA3; --blue-lt: #E0EFFC;
            --border: rgba(0,0,0,0.09); --border-md: rgba(0,0,0,0.15);
            --text: #1A1A1E; --muted: #6B6A70; --hint: #A0A0A8;
            --r: 8px; --r-lg: 12px;
            --font: 'Outfit', sans-serif; --mono: 'DM Mono', monospace;
            min-height: calc(100vh - 88px);
            background: var(--bg);
            font-family: var(--font);
            color: var(--text);
        }
        .fp-root *{box-sizing:border-box;margin:0;padding:0;}
        .fp-root button{font-family:var(--font);cursor:pointer;}

        .fp-topbar{height:50px;background:var(--surface);border-bottom:0.5px solid var(--border-md);display:flex;align-items:center;padding:0 24px;gap:14px;}
        .fp-topbar-icon{width:30px;height:30px;background:var(--accent);border-radius:7px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
        .fp-topbar-icon svg{width:16px;height:16px;fill:none;stroke:white;stroke-width:2;}
        .fp-topbar-title{font-size:15px;font-weight:600;}
        .fp-topbar-space{flex:1;}

        .fp-btn-dashboard{padding:7px 14px;border-radius:var(--r);border:0.5px solid var(--border);background:transparent;font-size:12px;font-weight:500;color:var(--muted);display:flex;align-items:center;gap:6px;transition:all .15s;}
        .fp-btn-dashboard:hover{background:var(--bg);color:var(--text);border-color:var(--border-md);}
        .fp-btn-dashboard svg{stroke:currentColor;fill:none;stroke-width:2;}

        .fp-btn-create{padding:8px 16px;background:var(--teal);color:white;border:none;border-radius:var(--r);font-size:12.5px;font-weight:500;display:flex;align-items:center;gap:6px;transition:opacity .15s;}
        .fp-btn-create:hover{opacity:.84;}
        .fp-btn-create svg{stroke:white;fill:none;stroke-width:2.5;}

        .fp-filters{padding:8px 24px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
        .fp-filter-group{display:flex;gap:4px;background:var(--surface);padding:3px;border-radius:var(--r);border:0.5px solid var(--border);}
        .fp-status-btn{padding:5px 14px;border-radius:6px;border:none;background:transparent;font-size:12px;font-weight:500;color:var(--muted);transition:all .13s;}
        .fp-status-btn.active{background:var(--text);color:white;}

        /* View toggle */
        .fp-view-toggle{margin-left:auto;display:flex;gap:2px;background:var(--surface);padding:3px;border-radius:var(--r);border:0.5px solid var(--border);}
        .fp-view-btn{padding:4px 10px;border-radius:5px;border:none;background:transparent;font-size:11px;font-weight:500;color:var(--muted);transition:all .13s;display:flex;align-items:center;gap:4px;}
        .fp-view-btn:hover{color:var(--text);}
        .fp-view-btn.active{background:var(--text);color:white;}
        .fp-view-btn svg{stroke:currentColor;fill:none;stroke-width:1.5;}

        /* Summary bar */
        .fp-summary-bar{display:flex;gap:20px;padding:8px 24px;background:var(--surface);border-bottom:0.5px solid var(--border);justify-content:center;}
        .fp-stat{display:flex;flex-direction:column;align-items:center;min-width:50px;}
        .fp-stat-val{font-size:18px;font-weight:700;color:var(--text);line-height:1.2;}
        .fp-stat-lbl{font-size:9px;text-transform:uppercase;letter-spacing:.5px;color:var(--hint);font-weight:600;}

        /* Kanban lanes */
        .fp-lanes{display:grid;grid-template-columns:repeat(5,1fr);gap:0;padding:0 16px 16px;min-height:calc(100vh - 230px);}
        .fp-lane-col{display:flex;flex-direction:column;border-right:0.5px solid var(--border);}
        .fp-lane-col:last-child{border-right:none;}
        .fp-lane-header{display:flex;align-items:center;gap:6px;padding:10px 10px;border-bottom:2px solid;background:var(--surface);position:sticky;top:0;z-index:2;}
        .fp-lane-icon{font-size:16px;}
        .fp-lane-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;color:var(--text);flex:1;}
        .fp-lane-count{font-size:10px;font-family:var(--mono);font-weight:600;padding:1px 7px;border-radius:10px;}
        .fp-lane-body{flex:1;overflow-y:auto;padding:6px;display:flex;flex-direction:column;gap:6px;}
        .fp-lane-empty{text-align:center;padding:16px 8px;color:var(--hint);font-size:11px;}

        /* Lane cards */
        .fp-card{background:var(--surface);border:0.5px solid var(--border);border-radius:var(--r-lg);padding:10px;cursor:pointer;transition:all .15s;}
        .fp-card:hover{border-color:var(--border-md);box-shadow:0 4px 12px rgba(0,0,0,.08);transform:translateY(-2px);}
        .fp-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:6px;margin-bottom:5px;}
        .fp-card-name{font-size:12px;font-weight:600;color:var(--text);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .fp-card-ref{font-size:9.5px;font-family:var(--mono);font-weight:500;flex-shrink:0;}
        .fp-card-route{font-size:10.5px;font-family:var(--mono);color:#0D6B50;font-weight:500;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .fp-card-details{display:flex;gap:8px;font-size:10px;color:var(--muted);margin-bottom:6px;flex-wrap:wrap;}
        .fp-card-dep{color:var(--text);font-weight:500;}
        .fp-card-bar{height:3px;background:var(--bg);border-radius:2px;margin-bottom:5px;overflow:hidden;}
        .fp-card-bar-fill{height:100%;border-radius:2px;}
        .fp-card-footer{display:flex;align-items:center;justify-content:space-between;font-size:9px;color:var(--hint);}
        .fp-card-flow{padding:1px 4px;background:var(--bg);border-radius:3px;font-weight:500;}

        .fp-list{padding:0 24px 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;}

        .fp-plan-card{background:var(--surface);border:0.5px solid var(--border);border-radius:var(--r-lg);padding:16px;cursor:pointer;transition:all .15s;}
        .fp-plan-card:hover{border-color:var(--border-md);transform:translateY(-1px);box-shadow:0 3px 10px rgba(0,0,0,.06);}
        .fp-card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}
        .fp-card-label{font-size:14px;font-weight:600;color:var(--text);}
        .fp-card-status{padding:2px 8px;border-radius:20px;font-size:10px;font-weight:500;}
        .fp-card-route{font-family:var(--mono);font-size:12px;font-weight:500;color:var(--teal);margin-bottom:6px;}
        .fp-card-meta{display:flex;gap:12px;font-size:11px;color:var(--muted);margin-bottom:8px;font-family:var(--mono);}
        .fp-card-metrics{display:flex;gap:16px;font-size:11.5px;color:var(--muted);margin-bottom:4px;}
        .fp-card-metrics strong{color:var(--text);font-weight:600;}
        .fp-card-zone{font-size:11px;color:var(--hint);}

        .fp-empty{text-align:center;padding:60px 20px;grid-column:1/-1;}
        .fp-empty-icon{margin-bottom:12px;opacity:.5;}
        .fp-empty-text{font-size:16px;font-weight:600;color:var(--text);margin-bottom:4px;}
        .fp-empty-sub{font-size:13px;color:var(--muted);max-width:400px;margin:0 auto;}

        .fp-loading{text-align:center;padding:40px;color:var(--muted);font-size:13px;grid-column:1/-1;}

        .fp-modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1100;align-items:center;justify-content:center;}
        .fp-modal-overlay.show{display:flex;}
        .fp-modal{background:var(--surface);border-radius:var(--r-lg);padding:24px;width:440px;max-height:90vh;overflow-y:auto;border:0.5px solid var(--border-md);}
        .fp-modal-title{font-size:16px;font-weight:600;margin-bottom:16px;}
        .fp-modal-body{display:flex;flex-direction:column;gap:10px;margin-bottom:18px;}
        .fp-field-row{display:flex;flex-direction:column;gap:3px;}
        .fp-field-label{font-size:11px;font-weight:600;color:var(--hint);text-transform:uppercase;letter-spacing:.4px;}
        .fp-field-input{padding:8px 10px;border:0.5px solid var(--border-md);border-radius:6px;font-family:var(--font);font-size:13px;color:var(--text);background:var(--bg);outline:none;transition:border-color .15s;}
        .fp-field-input:focus{border-color:var(--accent);}
        .fp-modal-actions{display:flex;gap:8px;justify-content:flex-end;}
        .fp-btn-cancel{padding:8px 16px;border-radius:var(--r);border:0.5px solid var(--border);background:transparent;font-size:13px;color:var(--muted);}
        .fp-btn-cancel:hover{background:var(--bg);}
        .fp-btn-confirm{padding:8px 20px;border-radius:var(--r);border:none;background:var(--teal);font-size:13px;font-weight:500;color:white;}
        .fp-btn-confirm:hover{opacity:.85;}
    `;
    document.head.appendChild(style);
}
