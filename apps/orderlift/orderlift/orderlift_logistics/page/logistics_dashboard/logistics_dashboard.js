frappe.pages["logistics-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Container Planning"),
        single_column: true,
    });

    page.main.addClass("ld-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

// ─── Icons ───────────────────────────────────────────────────────────────────

const ICONS = {
    forecast: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="16" height="10" rx="2"/><path d="M6 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="2" y1="11" x2="18" y2="11"/></svg>`,
    container: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="18" height="12" rx="2"/><line x1="6" y1="4" x2="6" y2="16"/><line x1="10" y1="4" x2="10" y2="16"/><line x1="14" y1="4" x2="14" y2="16"/></svg>`,
    planning: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="2" width="14" height="16" rx="2"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/><line x1="7" y1="13" x2="11" y2="13"/></svg>`,
    ready: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r="0.6" fill="currentColor"/></svg>`,
    transit: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="7" width="14" height="9" rx="1"/><path d="M15 10h2l2 3v3h-4V10z"/><circle cx="5" cy="18" r="1.5" fill="currentColor" stroke="none"/><circle cx="15" cy="18" r="1.5" fill="currentColor" stroke="none"/></svg>`,
    plus: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/></svg>`,
    profile: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="16" height="16" rx="2"/><line x1="6" y1="6" x2="14" y2="6"/><line x1="6" y1="10" x2="10" y2="10"/><line x1="6" y1="14" x2="14" y2="14"/></svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r="0.6" fill="currentColor"/></svg>`,
    clock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="8"/><polyline points="10,5 10,10 13,13"/></svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="10" x2="16" y2="10"/><polyline points="11,5 16,10 11,15"/></svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,10 8,14 16,6"/></svg>`,
    route: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="4" cy="10" r="2"/><circle cx="16" cy="10" r="2"/><line x1="6" y1="10" x2="14" y2="10"/></svg>`,
};

// ─── Skeleton ────────────────────────────────────────────────────────────────

function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const today = frappe.datetime.str_to_user(frappe.datetime.now_date());

    page.main.html(`
        <div class="ld-wrapper">

            <!-- Hero -->
            <div class="ld-hero">
                <div class="ld-hero-left">
                    <div class="ld-hero-eyebrow">${__("Orderlift · Container Planning")}</div>
                    <div class="ld-hero-greeting">${greeting}</div>
                    <div class="ld-hero-sub">${today}</div>
                </div>
                <div class="ld-hero-right">
                    <div class="ld-hero-stat" id="ld-hero-planning">
                        <div class="ld-hero-stat-val">—</div>
                        <div class="ld-hero-stat-label">${__("Planning")}</div>
                    </div>
                    <div class="ld-hero-divider"></div>
                    <div class="ld-hero-stat" id="ld-hero-transit">
                        <div class="ld-hero-stat-val">—</div>
                        <div class="ld-hero-stat-label">${__("In Transit")}</div>
                    </div>
                    <div class="ld-hero-divider"></div>
                    <div class="ld-hero-stat" id="ld-hero-alerts">
                        <div class="ld-hero-stat-val">—</div>
                        <div class="ld-hero-stat-label">${__("Alerts")}</div>
                    </div>
                </div>
            </div>

            <!-- Shortcuts -->
            <div class="ld-shortcuts-grid">
                ${shortcut("plus", __("New Forecast Plan"), "/app/forecast-plans", "primary")}
                ${shortcut("forecast", __("Forecast Plans"), "/app/forecast-plans", "default")}
                ${shortcut("planning", __("Load Forecast Planner"), "/app/planning", "default")}
                ${shortcut("profile", __("Container Profiles"), "/app/container-profile", "default")}
            </div>

            <!-- KPI grid -->
            <div class="ld-kpi-grid" id="ld-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="ld-kpi ld-kpi--shimmer"></div>`).join("")}
            </div>

            <!-- Lower section: Container timeline + Alerts -->
            <div class="ld-lower">
                <div class="ld-card">
                    <div class="ld-card-header">
                        <div class="ld-card-title">
                            <span class="ld-card-icon">${ICONS.container}</span>
                            ${__("Container Timeline")}
                        </div>
                        <a href="/app/forecast-plans" class="ld-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="ld-timeline" class="ld-timeline-wrap">
                        <div class="ld-shimmer-block" style="height:260px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <div class="ld-card">
                    <div class="ld-card-header">
                        <div class="ld-card-title">
                            <span class="ld-card-icon">${ICONS.alert}</span>
                            ${__("Container Alerts")}
                        </div>
                    </div>
                    <div id="ld-alerts" class="ld-alerts-wrap">
                        <div class="ld-shimmer-block" style="height:200px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>
            </div>
        </div>
    `);

    page.main.find(".ld-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (!url) return;
        frappe.set_route(url.replace(/^\/app\//, "").split("/"));
    });
}

// ─── Data loading ────────────────────────────────────────────────────────────

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.logistics_dashboard.logistics_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {});
        renderKpis(page, data.kpis || {});
        renderTimeline(page, data.containers || []);
        renderAlerts(page, data.alerts || []);
    } catch (e) {
        renderHeroStats(page, {});
        renderKpis(page, {});
        renderTimeline(page, []);
        renderAlerts(page, []);
        console.warn("Logistics Dashboard: failed to load data", e);
    }
}

// ─── Hero stats ──────────────────────────────────────────────────────────────

function renderHeroStats(page, kpis) {
    page.main.find("#ld-hero-planning .ld-hero-stat-val").text(kpis.planning_count ?? "—");
    const transitVal = kpis.in_transit_count ?? "—";
    page.main.find("#ld-hero-transit .ld-hero-stat-val").text(transitVal);
    if (transitVal > 0) page.main.find("#ld-hero-transit .ld-hero-stat-val").addClass("ld-stat-warn");
    const alertCount = (kpis.planning_count || 0) + (kpis.in_transit_count || 0);
    page.main.find("#ld-hero-alerts .ld-hero-stat-val").text(alertCount > 0 ? alertCount : "—");
}

// ─── Shortcuts ───────────────────────────────────────────────────────────────

function shortcut(iconKey, label, url, variant) {
    return `<div class="ld-shortcut ld-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}">
        <span class="ld-shortcut-icon">${ICONS[iconKey] || ""}</span>
        <span class="ld-shortcut-label">${frappe.utils.escape_html(label)}</span>
    </div>`;
}

// ─── KPI cards ───────────────────────────────────────────────────────────────

function renderKpis(page, kpis) {
    const defs = [
        { icon: "forecast", label: __("Planning"), value: kpis.planning_count ?? "—", sub: __("containers being planned") },
        { icon: "ready", label: __("Confirmed"), value: kpis.ready_count ?? "—", sub: __("ready to load") },
        { icon: "container", label: __("Loading"), value: kpis.loading_count ?? "—", sub: __("in progress") },
        { icon: "transit", label: __("In Transit"), value: kpis.in_transit_count ?? "—", sub: __("shipped containers"), highlight: (kpis.in_transit_count || 0) > 0 ? "warn" : null },
        { icon: "container", label: __("Delivered"), value: kpis.delivered_count ?? "—", sub: __("completed shipments") },
        { icon: "profile", label: __("Container Profiles"), value: kpis.profiles_count ?? "—", sub: __("active profiles") },
    ];

    page.main.find("#ld-kpi-grid").html(defs.map((d) => `
        <div class="ld-kpi">
            <div class="ld-kpi-top"><span class="ld-kpi-icon">${ICONS[d.icon]}</span></div>
            <div class="ld-kpi-val ${d.highlight === "warn" ? "ld-stat-warn" : ""}">${d.value}</div>
            <div class="ld-kpi-lbl">${d.label}</div>
            <div class="ld-kpi-sub">${d.sub}</div>
        </div>
    `).join(""));
}

// ─── Container timeline ─────────────────────────────────────────────────────

function renderTimeline(page, containers) {
    const el = page.main.find("#ld-timeline");
    if (!containers.length) {
        el.html(`<div class="ld-empty">${ICONS.container}<p>${__("No containers yet. Create a Forecast Plan to start.")}</p></div>`);
        return;
    }

    const statusColors = {
        Planning: { bg: "#fff7ed", border: "#f97316", text: "#ea580c", dot: "#f97316" },
        Ready: { bg: "#ecfdf5", border: "#34d399", text: "#059669", dot: "#10b981" },
        Loading: { bg: "#eff6ff", border: "#93c5fd", text: "#2563eb", dot: "#3b82f6" },
        "In Transit": { bg: "#f5f3ff", border: "#c4b5fd", text: "#7c3aed", dot: "#8b5cf6" },
        Delivered: { bg: "#ecfdf5", border: "#6ee7b7", text: "#047857", dot: "#10b981" },
    };

    el.html(`
        <div class="ld-table-wrap">
            <table class="ld-table">
                <thead>
                    <tr>
                        <th>${__("Plan")}</th>
                        <th>${__("Status")}</th>
                        <th>${__("Route")}</th>
                        <th class="ld-right">${__("Volume")}</th>
                        <th class="ld-right">${__("Weight")}</th>
                        <th>${__("Departure")}</th>
                    </tr>
                </thead>
                <tbody>
                    ${containers.map(c => {
                        const sc = statusColors[c.status] || statusColors.Planning;
                        const route = (c.route_origin && c.route_destination)
                            ? `${frappe.utils.escape_html(c.route_origin)} → ${frappe.utils.escape_html(c.route_destination)}`
                            : "—";
                        const dep = c.departure_date ? frappe.datetime.str_to_user(c.departure_date) : "—";
                        const vol = c.total_volume_m3 ? `${Number(c.total_volume_m3).toFixed(1)} m³` : "—";
                        const wt = c.total_weight_kg ? `${Math.round(c.total_weight_kg).toLocaleString()} kg` : "—";
                        return `
                    <tr class="ld-row" data-route="planning/${encodeURIComponent(c.name)}">
                        <td>
                            <a class="ld-link" href="/app/planning/${encodeURIComponent(c.name)}">
                                ${frappe.utils.escape_html(c.plan_label || c.name)}
                            </a>
                            <div class="ld-ref">${frappe.utils.escape_html(c.name)}</div>
                        </td>
                        <td><span class="ld-badge" style="background:${sc.bg};color:${sc.text};border:1px solid ${sc.border}20"><span class="ld-badge-dot" style="background:${sc.dot}"></span>${c.status || "—"}</span></td>
                        <td class="ld-muted">${route}</td>
                        <td class="ld-right ld-mono">${vol}</td>
                        <td class="ld-right ld-mono">${wt}</td>
                        <td class="ld-muted">${dep}</td>
                    </tr>`;
                    }).join("")}
                </tbody>
            </table>
        </div>
    `);

    el.find(".ld-row").on("click", function (e) {
        if ($(e.target).is("a")) return;
        frappe.set_route($(this).data("route").split("/"));
    });
}

// ─── Alerts ──────────────────────────────────────────────────────────────────

function renderAlerts(page, alerts) {
    const el = page.main.find("#ld-alerts");
    if (!alerts.length) {
        el.html(`<div class="ld-empty">${ICONS.check}<p>${__("No container alerts.")}</p></div>`);
        return;
    }
    el.html(alerts.map(a => `
        <div class="ld-alert-item ld-alert-item--${a.level || "warn"}">
            <span class="ld-alert-ico">${ICONS.alert}</span>
            <div class="ld-alert-content">
                <div class="ld-alert-title">${frappe.utils.escape_html(a.title)}</div>
                <div class="ld-alert-body">${frappe.utils.escape_html(a.message)}</div>
                ${a.link ? `<a class="ld-alert-link" href="${frappe.utils.escape_html(a.link)}">${__("Review")} <span class="ld-alert-arrow">${ICONS.arrow}</span></a>` : ""}
            </div>
        </div>
    `).join(""));
}

// ─── Styles ──────────────────────────────────────────────────────────────────

function injectDashboardStyles() {
    if (document.getElementById("ld-styles")) return;
    const style = document.createElement("style");
    style.id = "ld-styles";
    style.textContent = `
.ld-root { background: var(--bg-color, #f4f6f9); }
.ld-wrapper { max-width: 1380px; margin: 0 auto; padding: 28px 32px 72px; }

/* Hero */
.ld-hero {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 24px;
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #d4f0f5);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04);
    position: relative; overflow: hidden;
}
.ld-hero::before {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(2,115,132,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.ld-hero-eyebrow {
    font-size: 11px; font-weight: 700; letter-spacing: 1px;
    text-transform: uppercase; color: #027384; margin-bottom: 6px;
}
.ld-hero-greeting {
    font-size: 26px; font-weight: 700; color: var(--heading-color, #1a1f2e); line-height: 1.2;
}
.ld-hero-sub { font-size: 13px; color: var(--text-muted, #8c95a6); margin-top: 4px; }

.ld-hero-right { display: flex; align-items: center; gap: 0; }
.ld-hero-stat { text-align: center; padding: 0 36px; }
.ld-hero-stat-val { font-size: 30px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; }
.ld-hero-stat-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: var(--text-muted, #8c95a6); margin-top: 5px; }
.ld-hero-divider { width: 1px; height: 40px; background: var(--border-color, #d4f0f5); }
.ld-stat-warn { color: #e11d48 !important; }

/* Shortcuts grid */
.ld-shortcuts-grid {
    display: grid; grid-template-columns: repeat(6, 1fr);
    gap: 10px; margin-bottom: 20px;
}
@media (max-width: 1100px) { .ld-shortcuts-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px)  { .ld-shortcuts-grid { grid-template-columns: repeat(2, 1fr); } }

.ld-shortcut {
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #d4f0f5);
    border-radius: 12px;
    padding: 16px 12px;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
    user-select: none;
}
.ld-shortcut:hover {
    border-color: #027384; box-shadow: 0 4px 16px rgba(2,115,132,0.12);
    transform: translateY(-2px);
}
.ld-shortcut--primary {
    background: #027384; border-color: #027384; color: #fff;
}
.ld-shortcut--primary .ld-shortcut-icon svg { stroke: #fff; }
.ld-shortcut--primary .ld-shortcut-label { color: #fff; }
.ld-shortcut--primary:hover { background: #015a6b; border-color: #015a6b; box-shadow: 0 4px 20px rgba(2,115,132,0.3); }

.ld-shortcut-icon { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; }
.ld-shortcut-icon svg { width: 22px; height: 22px; stroke: #4a8a8f; transition: stroke .15s; }
.ld-shortcut:hover .ld-shortcut-icon svg { stroke: #027384; }
.ld-shortcut--primary:hover .ld-shortcut-icon svg { stroke: #fff; }

.ld-shortcut-label {
    font-size: 11.5px; font-weight: 600; text-align: center; line-height: 1.3;
    color: var(--text-color, #334155);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
}

/* KPI grid */
.ld-kpi-grid {
    display: grid; grid-template-columns: repeat(6, 1fr);
    gap: 12px; margin-bottom: 24px;
}
@media (max-width: 1100px) { .ld-kpi-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px)  { .ld-kpi-grid { grid-template-columns: repeat(2, 1fr); } }

.ld-kpi {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #d4f0f5);
    border-radius: 12px;
    padding: 18px 18px 16px;
    transition: box-shadow 0.15s;
}
.ld-kpi:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }

.ld-kpi--shimmer {
    min-height: 110px;
    background: linear-gradient(90deg, #e8f7f8 25%, #d4f0f5 37%, #e8f7f8 63%);
    background-size: 400% 100%;
    animation: ld-shimmer 1.4s infinite;
}
@keyframes ld-shimmer { 0% { background-position: 100% 50%; } 100% { background-position: 0 50%; } }

.ld-kpi-top { margin-bottom: 10px; }
.ld-kpi-icon { display: inline-flex; width: 32px; height: 32px; border-radius: 8px; background: #e8f7f8; align-items: center; justify-content: center; }
.ld-kpi-icon svg { width: 16px; height: 16px; stroke: #027384; }
.ld-kpi-value { font-size: 28px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; margin-bottom: 4px; }
.ld-kpi-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted, #64748b); margin-bottom: 3px; }
.ld-kpi-sub   { font-size: 11.5px; color: var(--text-muted, #94a3b8); }

/* Lower grid */
.ld-lower { display: grid; grid-template-columns: 1fr 360px; gap: 16px; align-items: start; }
@media (max-width: 960px) { .ld-lower { grid-template-columns: 1fr; } }

/* Card */
.ld-card {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #d4f0f5);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.ld-card-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border-color, #f0fafc);
}
.ld-card-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e);
}
.ld-card-icon { display: inline-flex; }
.ld-card-icon svg { width: 15px; height: 15px; stroke: #027384; }

.ld-view-all {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; font-weight: 600; color: #027384; text-decoration: none;
    transition: gap 0.15s;
}
.ld-view-all:hover { gap: 7px; }
.ld-view-all svg { width: 13px; height: 13px; stroke: #027384; }

/* Table */
.ld-table-wrap { overflow-x: auto; }
.ld-table { width: 100%; border-collapse: collapse; }
.ld-table thead tr { background: #f0fafc; }
.ld-table th {
    text-align: left; padding: 9px 16px;
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted, #64748b);
    border-bottom: 1px solid var(--border-color, #d4f0f5);
    white-space: nowrap;
}
.ld-table td {
    padding: 11px 16px;
    border-bottom: 1px solid var(--border-color, #f0fafc);
    color: var(--text-color, #334155);
}
.ld-table tbody tr:last-child td { border-bottom: none; }
.ld-row { cursor: pointer; transition: background 0.1s; }
.ld-row:hover td { background: #f0fafc; }

.ld-link { font-weight: 600; color: #027384; text-decoration: none; }
.ld-link:hover { text-decoration: underline; }
.ld-ref { font-size: 10px; color: var(--text-muted, #94a3b8); font-family: var(--mono, monospace); }
.ld-muted  { color: var(--text-muted, #94a3b8); }
.ld-right  { text-align: right; }
.ld-mono   { font-variant-numeric: tabular-nums; font-weight: 600; }

.ld-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 9px; border-radius: 999px;
    font-size: 11px; font-weight: 600;
}
.ld-badge-dot { width: 6px; height: 6px; border-radius: 50%; }

/* Shimmer */
.ld-shimmer-block {
    background: linear-gradient(90deg, #e8f7f8 25%, #d4f0f5 37%, #e8f7f8 63%);
    background-size: 400% 100%;
    animation: ld-shimmer 1.4s infinite;
}

/* Alerts */
.ld-alerts-wrap { padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.ld-alert-item {
    display: flex; gap: 12px; padding: 14px 16px;
    border-radius: 10px; border: 1px solid;
}
.ld-alert-item--warn  { background: #fffbeb; border-color: #fde68a; }
.ld-alert-item--error { background: #fff1f2; border-color: #fecdd3; }
.ld-alert-ico { flex-shrink: 0; display: inline-flex; margin-top: 1px; }
.ld-alert-item--warn  .ld-alert-ico svg { width: 16px; height: 16px; stroke: #d97706; }
.ld-alert-item--error .ld-alert-ico svg { width: 16px; height: 16px; stroke: #dc2626; }
.ld-alert-title { font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e); margin-bottom: 3px; }
.ld-alert-body  { font-size: 12px; color: var(--text-muted, #64748b); line-height: 1.5; }
.ld-alert-link  {
    display: inline-flex; align-items: center; gap: 4px;
    margin-top: 8px; font-size: 12px; font-weight: 600; color: #027384; text-decoration: none;
}
.ld-alert-link:hover { text-decoration: underline; }

/* Empty */
.ld-empty {
    display: flex; flex-direction: column; align-items: center;
    padding: 48px 24px; text-align: center;
    color: var(--text-muted, #94a3b8); font-size: 13px; gap: 10px;
}
.ld-empty svg { width: 36px; height: 36px; stroke: #cbd5e1; }
    `;
    document.head.appendChild(style);
}
