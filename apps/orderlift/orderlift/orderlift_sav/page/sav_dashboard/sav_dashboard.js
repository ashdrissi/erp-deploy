frappe.pages["sav-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("SAV"),
        single_column: true,
    });

    page.main.addClass("svdb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    ticket: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V7z"/></svg>`,
    sla: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="8"/><path d="M10 5v5l3 2"/></svg>`,
    wrench: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 5.3a3 3 0 0 1-4 3.98L5 15l-2 1 1-2 5.72-5.72a3 3 0 0 1 3.98-4z"/></svg>`,
    customer: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="3.5"/><path d="M4 17c0-3.1 2.7-5.5 6-5.5s6 2.4 6 5.5"/></svg>`,
    communication: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h14v10H7l-4 3V5z"/><path d="M6 8h8M6 11h5"/></svg>`,
    calendar: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="14" height="13" rx="2"/><line x1="3" y1="8" x2="17" y2="8"/><line x1="7" y1="2.5" x2="7" y2="5.5"/><line x1="13" y1="2.5" x2="13" y2="5.5"/></svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r="0.6" fill="currentColor"/></svg>`,
    plus: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/></svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="10" x2="16" y2="10"/><polyline points="11,5 16,10 11,15"/></svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,10 8,14 16,6"/></svg>`,
};

function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const today = frappe.datetime.str_to_user(frappe.datetime.now_date());

    page.main.html(`
        <div class="svdb-wrapper">
            <div class="svdb-hero">
                <div class="svdb-hero-left">
                    <div class="svdb-hero-eyebrow">${__("Orderlift · SAV Hub")}</div>
                    <div class="svdb-hero-greeting">${greeting}</div>
                    <div class="svdb-hero-sub">${today}</div>
                </div>
                <div class="svdb-hero-right">
                    <div class="svdb-hero-stat" id="svdb-hero-open"><div class="svdb-hero-stat-val">—</div><div class="svdb-hero-stat-label">${__("Open Tickets")}</div></div>
                    <div class="svdb-hero-divider"></div>
                    <div class="svdb-hero-stat" id="svdb-hero-sla"><div class="svdb-hero-stat-val">—</div><div class="svdb-hero-stat-label">${__("SLA Breach")}</div></div>
                    <div class="svdb-hero-divider"></div>
                    <div class="svdb-hero-stat" id="svdb-hero-alerts"><div class="svdb-hero-stat-val">—</div><div class="svdb-hero-stat-label">${__("Alerts")}</div></div>
                </div>
            </div>

            <div class="svdb-shortcuts-grid">
                ${shortcut("plus", __("New SAV Ticket"), "/app/sav-ticket/new-sav-ticket-1", "primary")}
                ${shortcut("ticket", __("All Tickets"), "/app/sav-ticket", "default")}
                ${shortcut("wrench", __("Technicians"), "/app/user", "default")}
                ${shortcut("customer", __("Customers"), "/app/customer", "default")}
            </div>

            <div class="svdb-kpi-grid" id="svdb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="svdb-kpi svdb-kpi--shimmer"></div>`).join("")}
            </div>

            <div class="svdb-lower">
                <div class="svdb-card">
                    <div class="svdb-card-header">
                        <div class="svdb-card-title"><span class="svdb-card-icon">${ICONS.ticket}</span>${__("Recent SAV Tickets")}</div>
                        <a href="/app/sav-ticket" class="svdb-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="svdb-recent-table" class="svdb-table-wrap"><div class="svdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="svdb-card">
                    <div class="svdb-card-header">
                        <div class="svdb-card-title"><span class="svdb-card-icon">${ICONS.alert}</span>${__("SAV Alerts")}</div>
                    </div>
                    <div id="svdb-alerts" class="svdb-alerts-wrap"><div class="svdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>

            <div class="svdb-lower svdb-lower--secondary">
                <div class="svdb-card">
                    <div class="svdb-card-header">
                        <div class="svdb-card-title"><span class="svdb-card-icon">${ICONS.ticket}</span>${__("Status & Priority")}</div>
                    </div>
                    <div id="svdb-status-breakdown" class="svdb-metrics-wrap"><div class="svdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="svdb-card">
                    <div class="svdb-card-header">
                        <div class="svdb-card-title"><span class="svdb-card-icon">${ICONS.wrench}</span>${__("Technician Load")}</div>
                    </div>
                    <div id="svdb-technician-load" class="svdb-metrics-wrap"><div class="svdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>

            <div class="svdb-lower svdb-lower--secondary">
                <div class="svdb-card">
                    <div class="svdb-card-header">
                        <div class="svdb-card-title"><span class="svdb-card-icon">${ICONS.calendar}</span>${__("Upcoming Interventions")}</div>
                    </div>
                    <div id="svdb-upcoming" class="svdb-metrics-wrap"><div class="svdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="svdb-card">
                    <div class="svdb-card-header">
                        <div class="svdb-card-title"><span class="svdb-card-icon">${ICONS.communication}</span>${__("Recent Communications")}</div>
                    </div>
                    <div id="svdb-communications" class="svdb-metrics-wrap"><div class="svdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>
        </div>
    `);

    page.main.find(".svdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (!url) return;
        frappe.set_route(url.replace(/^\/app\//, "").split("/"));
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_sav.page.sav_dashboard.sav_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {}, data.alerts || []);
        renderKpis(page, data.kpis || {});
        renderRecentTickets(page, data.recent_tickets || []);
        renderAlerts(page, data.alerts || []);
        renderStatusBreakdown(page, data.status_breakdown || {});
        renderTechnicianLoad(page, data.technician_load || []);
        renderUpcoming(page, data.upcoming_interventions || []);
        renderCommunications(page, data.recent_communications || []);
    } catch (e) {
        renderHeroStats(page, {}, []);
        renderKpis(page, {});
        renderRecentTickets(page, []);
        renderAlerts(page, []);
        renderStatusBreakdown(page, {});
        renderTechnicianLoad(page, []);
        renderUpcoming(page, []);
        renderCommunications(page, []);
        console.warn("SAV Dashboard: failed to load data", e);
    }
}

function renderHeroStats(page, kpis, alerts) {
    page.main.find("#svdb-hero-open .svdb-hero-stat-val").text(kpis.open_tickets ?? "—");
    page.main.find("#svdb-hero-sla .svdb-hero-stat-val").text(kpis.sla_breach_tickets ?? "—");
    const alertEl = page.main.find("#svdb-hero-alerts .svdb-hero-stat-val");
    alertEl.text((alerts || []).length);
    if ((alerts || []).length > 0) alertEl.addClass("svdb-stat-warn");
}

function shortcut(iconKey, label, url, variant) {
    return `<div class="svdb-shortcut svdb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}"><span class="svdb-shortcut-icon">${ICONS[iconKey] || ""}</span><span class="svdb-shortcut-label">${frappe.utils.escape_html(label)}</span></div>`;
}

function renderKpis(page, kpis) {
    const defs = [
        { icon: "ticket", label: __("Total Tickets"), value: kpis.total_tickets ?? "—", sub: __("all SAV incidents") },
        { icon: "wrench", label: __("Assigned"), value: kpis.assigned_tickets ?? "—", sub: __("waiting intervention") },
        { icon: "wrench", label: __("In Progress"), value: kpis.in_progress_tickets ?? "—", sub: __("active interventions") },
        { icon: "ticket", label: __("Resolved"), value: kpis.resolved_tickets ?? "—", sub: __("pending validation") },
        { icon: "check", label: __("Closed"), value: kpis.closed_tickets ?? "—", sub: __("fully completed") },
        { icon: "alert", label: __("Critical"), value: kpis.critical_tickets ?? "—", sub: __("highest priority incidents") },
    ];

    page.main.find("#svdb-kpi-grid").html(defs.map((d) => `
        <div class="svdb-kpi">
            <div class="svdb-kpi-top"><span class="svdb-kpi-icon">${ICONS[d.icon]}</span></div>
            <div class="svdb-kpi-val">${d.value}</div>
            <div class="svdb-kpi-lbl">${d.label}</div>
            <div class="svdb-kpi-sub">${d.sub}</div>
        </div>
    `).join(""));
}

function renderRecentTickets(page, rows) {
    if (!rows.length) {
        page.main.find("#svdb-recent-table").html(`<div class="svdb-empty">${__("No SAV tickets yet.")}</div>`);
        return;
    }

    page.main.find("#svdb-recent-table").html(`
        <div class="svdb-mini-list">
            ${rows.map((row) => `
                <a class="svdb-mini-row" href="/app/sav-ticket/${frappe.utils.escape_html(row.name || "")}">
                    <span class="svdb-mini-label">${frappe.utils.escape_html(row.name || "")}</span>
                    <span class="svdb-mini-meta">${frappe.utils.escape_html(row.customer || "")} · ${frappe.utils.escape_html(row.status || "")} · ${frappe.utils.escape_html(row.priority || "")}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function renderAlerts(page, alerts) {
    if (!alerts.length) {
        page.main.find("#svdb-alerts").html(`<div class="svdb-empty">${ICONS.check}<p>${__("No active SAV alerts.")}</p></div>`);
        return;
    }

    page.main.find("#svdb-alerts").html(`
        <div class="svdb-alert-list">
            ${alerts.map((a) => `
                <a class="svdb-alert svdb-alert--${a.level || "info"}" href="${frappe.utils.escape_html(a.link || "#")}">
                    <div class="svdb-alert-title">${frappe.utils.escape_html(a.title || "")}</div>
                    <div class="svdb-alert-message">${frappe.utils.escape_html(a.message || "")}</div>
                </a>
            `).join("")}
        </div>
    `);
}

function renderStatusBreakdown(page, breakdown) {
    const status = breakdown.status || [];
    const priority = breakdown.priority || [];
    if (!status.length && !priority.length) {
        page.main.find("#svdb-status-breakdown").html(`<div class="svdb-empty">${__("No SAV status data yet.")}</div>`);
        return;
    }

    page.main.find("#svdb-status-breakdown").html(`
        <div class="svdb-stack-grid">
            <div class="svdb-stack-card">
                <div class="svdb-stack-title">${__("By Status")}</div>
                ${status.map((item) => `<div class="svdb-metric-row"><span>${frappe.utils.escape_html(item.label || "")}</span><strong>${item.value ?? 0}</strong></div>`).join("") || `<div class="svdb-empty-inline">${__("No status data")}</div>`}
            </div>
            <div class="svdb-stack-card">
                <div class="svdb-stack-title">${__("By Priority")}</div>
                ${priority.map((item) => `<div class="svdb-metric-row"><span>${frappe.utils.escape_html(item.label || "")}</span><strong>${item.value ?? 0}</strong></div>`).join("") || `<div class="svdb-empty-inline">${__("No priority data")}</div>`}
            </div>
        </div>
    `);
}

function renderTechnicianLoad(page, rows) {
    if (!rows.length) {
        page.main.find("#svdb-technician-load").html(`<div class="svdb-empty">${__("No technician load yet.")}</div>`);
        return;
    }

    page.main.find("#svdb-technician-load").html(`
        <div class="svdb-stack-grid">
            <div class="svdb-stack-card">
                <div class="svdb-stack-title">${__("Open Load by Technician")}</div>
                ${rows.map((item) => `<div class="svdb-metric-row"><span>${frappe.utils.escape_html(item.label || "")}</span><strong>${item.value ?? 0}</strong></div>`).join("")}
            </div>
        </div>
    `);
}

function renderUpcoming(page, rows) {
    if (!rows.length) {
        page.main.find("#svdb-upcoming").html(`<div class="svdb-empty">${__("No upcoming interventions scheduled.")}</div>`);
        return;
    }

    page.main.find("#svdb-upcoming").html(`
        <div class="svdb-mini-list">
            ${rows.map((row) => `
                <a class="svdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="svdb-mini-label">${frappe.utils.escape_html(row.name || "")}</span>
                    <span class="svdb-mini-meta">${frappe.utils.escape_html(row.intervention_date || "")} · ${frappe.utils.escape_html(row.customer || "")} · ${frappe.utils.escape_html(row.assigned_technician || "")}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function renderCommunications(page, rows) {
    if (!rows.length) {
        page.main.find("#svdb-communications").html(`<div class="svdb-empty">${__("No SAV communications linked yet.")}</div>`);
        return;
    }

    page.main.find("#svdb-communications").html(`
        <div class="svdb-mini-list">
            ${rows.map((row) => `
                <a class="svdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="svdb-mini-label">${frappe.utils.escape_html(row.subject || "")}</span>
                    <span class="svdb-mini-meta">${frappe.utils.escape_html(row.ticket || "")} ${row.meta ? `· ${frappe.utils.escape_html(row.meta)}` : ""}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function injectDashboardStyles() {
    if (document.getElementById("svdb-dashboard-styles")) return;

    const style = document.createElement("style");
    style.id = "svdb-dashboard-styles";
    style.textContent = `
        .svdb-root { background: linear-gradient(180deg, #f8fafc 0%, #fdf2f8 100%); min-height: calc(100vh - 88px); }
        .svdb-wrapper { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .svdb-hero, .svdb-card, .svdb-shortcut, .svdb-kpi { background: rgba(255,255,255,0.88); border: 1px solid rgba(148,163,184,0.16); box-shadow: 0 18px 50px rgba(15,23,42,0.08); }
        .svdb-hero { border-radius: 24px; padding: 28px; display: flex; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
        .svdb-hero-eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
        .svdb-hero-greeting { font-size: 32px; font-weight: 700; color: #0f172a; }
        .svdb-hero-sub { color: #475569; margin-top: 6px; }
        .svdb-hero-right { display: flex; align-items: center; gap: 18px; }
        .svdb-hero-divider { width: 1px; align-self: stretch; background: rgba(148,163,184,0.2); }
        .svdb-hero-stat-val { font-size: 28px; font-weight: 700; color: #111827; text-align: center; }
        .svdb-hero-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; }
        .svdb-stat-warn { color: #c2410c; }
        .svdb-shortcuts-grid, .svdb-kpi-grid { display: grid; gap: 14px; margin-bottom: 20px; }
        .svdb-shortcuts-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .svdb-kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .svdb-shortcut, .svdb-kpi { border-radius: 18px; padding: 18px; cursor: pointer; }
        .svdb-shortcut { display: flex; align-items: center; gap: 12px; transition: transform .16s ease, box-shadow .16s ease; }
        .svdb-shortcut:hover { transform: translateY(-2px); box-shadow: 0 24px 60px rgba(15,23,42,0.12); }
        .svdb-shortcut--primary { background: linear-gradient(135deg, #be185d, #9d174d); color: #fff; }
        .svdb-shortcut-icon svg, .svdb-kpi-icon svg, .svdb-card-icon svg { width: 20px; height: 20px; }
        .svdb-shortcut-label { font-weight: 600; }
        .svdb-kpi-top { margin-bottom: 12px; color: #475569; }
        .svdb-kpi-val { font-size: 28px; font-weight: 700; color: #0f172a; }
        .svdb-kpi-lbl { margin-top: 4px; font-weight: 600; color: #1e293b; }
        .svdb-kpi-sub { margin-top: 6px; font-size: 12px; color: #64748b; }
        .svdb-lower { display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }
        .svdb-lower--secondary { margin-top: 18px; grid-template-columns: 1fr 1fr; }
        .svdb-card { border-radius: 22px; overflow: hidden; }
        .svdb-card-header { padding: 18px 20px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .svdb-card-title { display: flex; align-items: center; gap: 10px; font-weight: 700; color: #0f172a; }
        .svdb-view-all { color: #be185d; font-weight: 600; text-decoration: none; }
        .svdb-mini-list, .svdb-alert-list { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 10px; }
        .svdb-mini-row, .svdb-alert { display: block; border-radius: 14px; padding: 14px; text-decoration: none; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .svdb-mini-label, .svdb-alert-title { display: block; font-weight: 600; color: #111827; }
        .svdb-mini-meta, .svdb-alert-message { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
        .svdb-alert--warn, .svdb-alert--error { border-left: 4px solid #f59e0b; }
        .svdb-alert--info { border-left: 4px solid #3b82f6; }
        .svdb-empty { padding: 28px 18px; text-align: center; color: #64748b; }
        .svdb-empty-inline { padding: 8px 0; color: #64748b; font-size: 12px; }
        .svdb-empty svg { width: 18px; height: 18px; display: inline-block; margin-bottom: 10px; }
        .svdb-stack-grid { padding: 0 16px 16px; display: grid; grid-template-columns: 1fr; gap: 12px; }
        .svdb-stack-card { border-radius: 14px; padding: 14px; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .svdb-stack-title { font-weight: 700; color: #111827; margin-bottom: 10px; }
        .svdb-metric-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(226,232,240,0.8); }
        .svdb-metric-row:last-child { border-bottom: 0; }
        .svdb-metric-row span { color: #475569; }
        .svdb-metric-row strong { color: #0f172a; }
        .svdb-kpi--shimmer, .svdb-shimmer-block { position: relative; overflow: hidden; background: rgba(255,255,255,0.7); }
        .svdb-kpi--shimmer::after, .svdb-shimmer-block::after { content: ""; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent); animation: svdbShimmer 1.5s infinite; }
        @keyframes svdbShimmer { 100% { transform: translateX(100%); } }
        @media (max-width: 980px) { .svdb-hero, .svdb-hero-right { flex-direction: column; align-items: flex-start; } .svdb-hero-right { width: 100%; } .svdb-hero-divider { display: none; } .svdb-lower, .svdb-lower--secondary { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
