frappe.pages["container-dashboard"].on_page_load = function (wrapper) {
    wrapper.dashboard_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Container Dashboard"),
        single_column: true,
    });
    renderDashboard(wrapper);
};

frappe.pages["container-dashboard"].on_page_show = function (wrapper) {
    if (wrapper._dashReady) loadDashboard(wrapper);
};

function renderDashboard(wrapper) {
    wrapper._dashReady = true;
    wrapper.dashboard_page.main.html(`<div class="cd-root"><div class="cd-loading">Loading...</div></div>`);
    injectDashboardStyles(wrapper);
    loadDashboard(wrapper);
}

function loadDashboard(wrapper) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Forecast Load Plan",
            filters: { status: ["not in", ["Cancelled"]] },
            fields: [
                "name", "plan_label", "company", "container_profile",
                "route_origin", "route_destination", "flow_scope",
                "destination_zone", "departure_date", "deadline",
                "status", "total_weight_kg", "total_volume_m3",
                "container_load_plan", "creation",
            ],
            order_by: "departure_date asc, creation desc",
            limit_page_length: 200,
        },
        async: true,
        callback: (r) => {
            const plans = r.message || [];
            renderLanes(wrapper, plans);
        },
    });
}

function renderLanes(wrapper, plans) {
    const lanes = [
        { key: "Planning", icon: "📝", label: "Planning", color: "#FDE8BE", border: "#854F0B" },
        { key: "Ready", icon: "✅", label: "Confirmed", color: "#D8F2EA", border: "#0D6B50" },
        { key: "Loading", icon: "📦", label: "Loading", color: "#E0EFFC", border: "#1A5FA3" },
        { key: "In Transit", icon: "✈️", label: "In Transit", color: "#F0E6FF", border: "#6B3FA0" },
        { key: "Delivered", icon: "🏁", label: "Delivered", color: "#E8F5E9", border: "#2E7D32" },
    ];

    const byStatus = {};
    lanes.forEach((l) => (byStatus[l.key] = []));
    plans.forEach((p) => {
        if (byStatus[p.status]) byStatus[p.status].push(p);
    });

    // Compute summary
    const totalVol = plans.reduce((s, p) => s + (p.total_volume_m3 || 0), 0);
    const totalWt = plans.reduce((s, p) => s + (p.total_weight_kg || 0), 0);
    const upcoming = plans.filter((p) => ["Planning", "Ready", "Loading"].includes(p.status));
    const inTransit = plans.filter((p) => p.status === "In Transit");

    const root = wrapper.querySelector(".cd-root");
    root.innerHTML = `
        <div class="cd-header">
            <div class="cd-header-top">
                <h1 class="cd-title">Container Timeline</h1>
                <div class="cd-summary">
                    <div class="cd-stat"><span class="cd-stat-val">${plans.length}</span><span class="cd-stat-lbl">Total</span></div>
                    <div class="cd-stat"><span class="cd-stat-val">${upcoming.length}</span><span class="cd-stat-lbl">Upcoming</span></div>
                    <div class="cd-stat"><span class="cd-stat-val">${inTransit.length}</span><span class="cd-stat-lbl">In Transit</span></div>
                    <div class="cd-stat"><span class="cd-stat-val">${totalVol.toFixed(1)}</span><span class="cd-stat-lbl">m³ Total</span></div>
                    <div class="cd-stat"><span class="cd-stat-val">${Math.round(totalWt).toLocaleString()}</span><span class="cd-stat-lbl">kg Total</span></div>
                </div>
            </div>
            <div class="cd-month-nav">
                <button class="cd-month-btn" data-action="prev-month">‹</button>
                <span class="cd-current-month" id="cdMonthLabel"></span>
                <button class="cd-month-btn" data-action="next-month">›</button>
                <button class="cd-month-btn cd-month-all active" data-action="all-months">All</button>
            </div>
        </div>
        <div class="cd-lanes-wrap" id="cdLanes">
            ${lanes.map((lane) => {
                const lanePlans = (byStatus[lane.key] || []);
                return `
                <div class="cd-lane" data-status="${lane.key}">
                    <div class="cd-lane-header" style="border-bottom-color:${lane.border}">
                        <span class="cd-lane-icon">${lane.icon}</span>
                        <span class="cd-lane-label">${lane.label}</span>
                        <span class="cd-lane-count" style="background:${lane.color};color:${lane.border}">${lanePlans.length}</span>
                    </div>
                    <div class="cd-lane-body">
                        ${lanePlans.length === 0
                            ? `<div class="cd-lane-empty">No containers</div>`
                            : lanePlans.map((p) => cardHtml(p, lane)).join("")
                        }
                    </div>
                </div>`;
            }).join("")}
        </div>
    `;

    // Bind events
    root.onclick = (e) => {
        const actionBtn = e.target.closest("[data-action]");
        if (actionBtn) {
            if (actionBtn.dataset.action === "prev-month") { /* filter logic */ }
            if (actionBtn.dataset.action === "next-month") { /* filter logic */ }
            if (actionBtn.dataset.action === "all-months") { /* filter logic */ }
            return;
        }
        const card = e.target.closest(".cd-card[data-name]");
        if (card) {
            frappe.set_route("planning", card.dataset.name);
        }
    };
}

function cardHtml(p, lane) {
    const route = (p.route_origin && p.route_destination)
        ? `${esc(p.route_origin)} → ${esc(p.route_destination)}`
        : "";
    const dep = p.departure_date ? frappe.datetime.str_to_user(p.departure_date) : "";
    const vol = (p.total_volume_m3 || 0).toFixed(1);
    const wt = Math.round(p.total_weight_kg || 0).toLocaleString();
    const pctVol = p.total_volume_m3 > 0 ? Math.min(100, Math.round((p.total_volume_m3 / 67.7) * 100)) : 0;

    return `
    <div class="cd-card" data-name="${esc(p.name)}">
        <div class="cd-card-top">
            <span class="cd-card-name">${esc(p.plan_label || p.name)}</span>
            <span class="cd-card-ref" style="color:${lane.border}">${esc(p.name)}</span>
        </div>
        ${route ? `<div class="cd-card-route">${route}</div>` : ""}
        <div class="cd-card-details">
            ${dep ? `<span class="cd-card-dep">📅 ${dep}</span>` : ""}
            <span class="cd-card-vol">📦 ${vol} m³</span>
            <span class="cd-card-wt">⚖️ ${wt} kg</span>
        </div>
        <div class="cd-card-bar">
            <div class="cd-card-bar-fill" style="width:${pctVol}%;background:${lane.border}"></div>
        </div>
        <div class="cd-card-footer">
            <span class="cd-card-container">${esc(p.container_profile || "—")}</span>
            ${p.flow_scope ? `<span class="cd-card-flow">${esc(p.flow_scope)}</span>` : ""}
        </div>
    </div>`;
}

function esc(v) { return frappe.utils.escape_html(v || ""); }

function injectDashboardStyles() {
    if (document.getElementById("cd-styles")) return;
    const style = document.createElement("style");
    style.id = "cd-styles";
    style.textContent = `
        .cd-root {
            --cd-bg: #F4F3F0; --cd-surface: #FFFFFF;
            --cd-text: #1A1A1E; --cd-muted: #6B6A70; --cd-hint: #A0A0A8;
            --cd-border: rgba(0,0,0,0.09); --cd-r: 8px; --cd-r-lg: 12px;
            --cd-font: 'Outfit', -apple-system, sans-serif; --cd-mono: 'DM Mono', monospace;
            min-height: calc(100vh - 88px);
            background: var(--cd-bg);
            font-family: var(--cd-font);
            color: var(--cd-text);
        }
        .cd-root * { box-sizing: border-box; margin: 0; padding: 0; }
        .cd-root button { font-family: var(--cd-font); cursor: pointer; }

        .cd-header { background: var(--cd-surface); border-bottom: 0.5px solid var(--cd-border); padding: 0 24px; }
        .cd-header-top { display: flex; align-items: center; justify-content: space-between; padding: 12px 0 8px; }
        .cd-title { font-size: 20px; font-weight: 700; color: var(--cd-text); }
        .cd-summary { display: flex; gap: 20px; align-items: center; }
        .cd-stat { display: flex; flex-direction: column; align-items: center; min-width: 50px; }
        .cd-stat-val { font-size: 18px; font-weight: 700; color: var(--cd-text); line-height: 1.2; }
        .cd-stat-lbl { font-size: 9px; text-transform: uppercase; letter-spacing: .5px; color: var(--cd-hint); font-weight: 600; }

        .cd-month-nav { display: flex; align-items: center; gap: 6px; padding-bottom: 8px; }
        .cd-month-btn { padding: 4px 10px; border-radius: 4px; border: 0.5px solid var(--cd-border); background: transparent; font-size: 12px; color: var(--cd-muted); transition: all .13s; }
        .cd-month-btn:hover { background: var(--cd-bg); color: var(--cd-text); }
        .cd-month-btn.active { background: var(--cd-text); color: white; border-color: var(--cd-text); }
        .cd-current-month { font-size: 13px; font-weight: 600; color: var(--cd-text); min-width: 120px; text-align: center; }

        .cd-lanes-wrap { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; min-height: calc(100vh - 200px); }
        .cd-lane { display: flex; flex-direction: column; border-right: 0.5px solid var(--cd-border); }
        .cd-lane:last-child { border-right: none; }
        .cd-lane-header { display: flex; align-items: center; gap: 6px; padding: 10px 12px; border-bottom: 2px solid; background: var(--cd-surface); position: sticky; top: 0; z-index: 2; }
        .cd-lane-icon { font-size: 16px; }
        .cd-lane-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .3px; color: var(--cd-text); flex: 1; }
        .cd-lane-count { font-size: 10px; font-family: var(--cd-mono); font-weight: 600; padding: 1px 7px; border-radius: 10px; }
        .cd-lane-body { flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 8px; }
        .cd-lane-empty { text-align: center; padding: 20px 8px; color: var(--cd-hint); font-size: 11px; }

        .cd-card { background: var(--cd-surface); border: 0.5px solid var(--cd-border); border-radius: var(--cd-r-lg); padding: 12px; cursor: pointer; transition: all .15s; }
        .cd-card:hover { border-color: var(--cd-border); box-shadow: 0 4px 12px rgba(0,0,0,.08); transform: translateY(-2px); }
        .cd-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 6px; margin-bottom: 6px; }
        .cd-card-name { font-size: 13px; font-weight: 600; color: var(--cd-text); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cd-card-ref { font-size: 10px; font-family: var(--cd-mono); font-weight: 500; flex-shrink: 0; }
        .cd-card-route { font-size: 11px; font-family: var(--cd-mono); color: #0D6B50; font-weight: 500; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cd-card-details { display: flex; gap: 10px; font-size: 10.5px; color: var(--cd-muted); margin-bottom: 8px; flex-wrap: wrap; }
        .cd-card-dep { color: var(--cd-text); font-weight: 500; }
        .cd-card-bar { height: 3px; background: var(--cd-bg); border-radius: 2px; margin-bottom: 6px; overflow: hidden; }
        .cd-card-bar-fill { height: 100%; border-radius: 2px; }
        .cd-card-footer { display: flex; align-items: center; justify-content: space-between; font-size: 9.5px; color: var(--cd-hint); }
        .cd-card-flow { padding: 1px 5px; background: var(--cd-bg); border-radius: 3px; font-weight: 500; }
        .cd-loading { text-align: center; padding: 40px; color: var(--cd-muted); font-size: 13px; }

        @media (max-width: 1200px) {
            .cd-lanes-wrap { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 768px) {
            .cd-lanes-wrap { grid-template-columns: repeat(2, 1fr); }
            .cd-summary { gap: 10px; }
        }
    `;
    document.head.appendChild(style);
}
