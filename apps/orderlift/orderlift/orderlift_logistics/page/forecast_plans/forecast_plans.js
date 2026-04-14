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
            <div class="fp-filters">
                <div class="fp-filter-group">
                    <button class="fp-status-btn active" data-status="">All</button>
                    <button class="fp-status-btn" data-status="Planning">Planning</button>
                    <button class="fp-status-btn" data-status="Ready">Ready</button>
                    <button class="fp-status-btn" data-status="Converted">Converted</button>
                </div>
            </div>
            <div class="fp-list" id="fpList">
                <div class="fp-loading">Loading...</div>
            </div>
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

    root.querySelector("#fpList").onclick = (e) => {
        const card = e.target.closest(".fp-plan-card[data-name]");
        if (!card) return;
        frappe.set_route("planning", card.dataset.name);
    };
}

function loadPlansList(wrapper) {
    const listEl = wrapper.querySelector("#fpList");
    const statusFilter = wrapper._fpStatusFilter || "";
    const filters = {};
    if (statusFilter) filters.status = statusFilter;

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Forecast Load Plan",
            filters: filters,
            fields: [
                "name", "plan_label", "company", "container_profile",
                "flow_scope", "destination_zone", "departure_date",
                "deadline", "status", "total_weight_kg", "total_volume_m3",
                "creation",
            ],
            order_by: "creation desc",
            limit_page_length: 50,
        },
        async: true,
        callback: (r) => {
            const plans = r.message || [];
            if (!plans.length) {
                listEl.innerHTML = `
                    <div class="fp-empty">
                        <div class="fp-empty-icon">
                            <svg viewBox="0 0 24 24" width="48" height="48"><rect x="2" y="7" width="20" height="12" rx="2" fill="none" stroke="#C0BFB8" stroke-width="1.5"></rect><path d="M2 11h20" fill="none" stroke="#C0BFB8" stroke-width="1.5"></path></svg>
                        </div>
                        <div class="fp-empty-text">No forecast plans yet</div>
                        <div class="fp-empty-sub">Create one to start planning container loads from quotes, orders, and shipments</div>
                    </div>
                `;
                return;
            }
            listEl.innerHTML = plans.map((p) => planCardHtml(p)).join("");
        },
    });
}

function planCardHtml(p) {
    const statusColors = {
        Planning: { bg: "#FDE8BE", text: "#854F0B" },
        Ready: { bg: "#D8F2EA", text: "#0D6B50" },
        Converted: { bg: "#E0EFFC", text: "#1A5FA3" },
        Cancelled: { bg: "#EEECEA", text: "#5F5E5A" },
    };
    const sc = statusColors[p.status] || statusColors.Planning;
    const depDate = p.departure_date ? frappe.datetime.str_to_user(p.departure_date) : "—";
    const deadlineDate = p.deadline ? frappe.datetime.str_to_user(p.deadline) : "";
    const vol = (p.total_volume_m3 || 0).toFixed(1);
    const wt = Math.round(p.total_weight_kg || 0).toLocaleString();

    return `
        <div class="fp-plan-card" data-name="${frappe.utils.escape_html(p.name)}">
            <div class="fp-card-top">
                <div class="fp-card-label">${frappe.utils.escape_html(p.plan_label || p.name)}</div>
                <span class="fp-card-status" style="background:${sc.bg};color:${sc.text}">${frappe.utils.escape_html(p.status)}</span>
            </div>
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
        { key: "flow_scope", label: "Flow Scope", type: "select", options: ["", "Inbound", "Domestic", "Outbound"] },
        { key: "shipping_responsibility", label: "Shipping Responsibility", type: "select", options: ["", "Orderlift", "Customer"] },
        { key: "destination_zone", label: "Destination Zone", type: "text", placeholder: "e.g. Bangkok, Central" },
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
            --bg: #F4F3F0; --surface: #FFFFFF; --accent: #C17F24; --accent-lt: #FDE8BE;
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

        .fp-btn-create{padding:8px 16px;background:var(--teal);color:white;border:none;border-radius:var(--r);font-size:12.5px;font-weight:500;display:flex;align-items:center;gap:6px;transition:opacity .15s;}
        .fp-btn-create:hover{opacity:.84;}
        .fp-btn-create svg{stroke:white;fill:none;stroke-width:2.5;}

        .fp-filters{padding:12px 24px;display:flex;gap:8px;}
        .fp-filter-group{display:flex;gap:4px;background:var(--surface);padding:3px;border-radius:var(--r);border:0.5px solid var(--border);}
        .fp-status-btn{padding:5px 14px;border-radius:6px;border:none;background:transparent;font-size:12px;font-weight:500;color:var(--muted);transition:all .13s;}
        .fp-status-btn.active{background:var(--text);color:white;}

        .fp-list{padding:0 24px 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;}

        .fp-plan-card{background:var(--surface);border:0.5px solid var(--border);border-radius:var(--r-lg);padding:16px;cursor:pointer;transition:all .15s;}
        .fp-plan-card:hover{border-color:var(--border-md);transform:translateY(-1px);box-shadow:0 3px 10px rgba(0,0,0,.06);}
        .fp-card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}
        .fp-card-label{font-size:14px;font-weight:600;color:var(--text);}
        .fp-card-status{padding:2px 8px;border-radius:20px;font-size:10px;font-weight:500;}
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
