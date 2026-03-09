// ─── Pricing Dashboard ────────────────────────────────────────────────────────
// Premium landing page for the Orderlift Sales / Pricing module.
// Displays:
//   • Hero header with greeting & current date
//   • 6 KPI stat cards (live data from DB)
//   • Quick-action shortcut buttons (new sheet, simulator, policies…)
//   • Recent Pricing Sheets table (last 10)
//   • Alerts panel (sheets without benchmark / margin guardrail warnings)
// ─────────────────────────────────────────────────────────────────────────────

frappe.pages["pricing-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Pricing"),
        single_column: true,
    });

    page.main.addClass("pdb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

// ─── Skeleton layout ─────────────────────────────────────────────────────────

function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting =
        hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const user = frappe.session.user_fullname || frappe.session.user;
    const today = frappe.datetime.str_to_user(frappe.datetime.now_date());

    page.main.html(`
        <div class="pdb-wrapper">

            <!-- ── Hero ── -->
            <div class="pdb-hero">
                <div class="pdb-hero-left">
                    <div class="pdb-hero-greeting">${greeting}, <span class="pdb-hero-name">${frappe.utils.escape_html(user.split("@")[0])}</span> 👋</div>
                    <div class="pdb-hero-sub">${__("Pricing Hub")} · ${today}</div>
                    <div class="pdb-hero-tagline">${__("Manage pricing scenarios, sheets, policies and market benchmarks.")}</div>
                </div>
                <div class="pdb-hero-badge">
                    <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="32" cy="32" r="32" fill="url(#grad1)"/>
                        <path d="M20 44 L32 20 L44 44" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                        <path d="M24 36 H40" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
                        <circle cx="32" cy="20" r="3" fill="white"/>
                        <defs>
                            <linearGradient id="grad1" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
                                <stop stop-color="#6366f1"/>
                                <stop offset="1" stop-color="#8b5cf6"/>
                            </linearGradient>
                        </defs>
                    </svg>
                </div>
            </div>

            <!-- ── KPI cards ── -->
            <div class="pdb-kpi-grid" id="pdb-kpi-grid">
                ${kpiSkeleton(6)}
            </div>

            <!-- ── Shortcuts ── -->
            <div class="pdb-section-title">${__("Quick Actions")}</div>
            <div class="pdb-shortcuts">
                ${shortcut("➕", __("New Pricing Sheet"), "/app/pricing-sheet/new-pricing-sheet-1", "indigo")}
                ${shortcut("📊", __("Pricing Simulator"), "/app/pricing-simulator", "violet")}
                ${shortcut("🏗️", __("Pricing Builder"), "/app/pricing-builder", "sky")}
                ${shortcut("📋", __("All Pricing Sheets"), "/app/pricing-sheet", "blue")}
                ${shortcut("🎯", __("Benchmark Policies"), "/app/pricing-benchmark-policy", "emerald")}
                ${shortcut("🌍", __("Customs Policies"), "/app/pricing-customs-policy", "amber")}
                ${shortcut("⚙️", __("Pricing Scenarios"), "/app/pricing-scenario", "rose")}
                ${shortcut("📐", __("Dimensioning Sets"), "/app/dimensioning-set", "teal")}
            </div>

            <!-- ── Two-column lower area ── -->
            <div class="pdb-lower">
                <!-- Recent sheets -->
                <div class="pdb-panel pdb-panel--wide">
                    <div class="pdb-panel-head">
                        <div class="pdb-panel-title">
                            <span class="pdb-panel-icon">📄</span>
                            ${__("Recent Pricing Sheets")}
                        </div>
                        <a href="/app/pricing-sheet" class="pdb-panel-link">${__("View all")} →</a>
                    </div>
                    <div id="pdb-recent-table" class="pdb-table-wrap">
                        <div class="pdb-shimmer-table"></div>
                    </div>
                </div>

                <!-- Alerts panel -->
                <div class="pdb-panel pdb-panel--narrow">
                    <div class="pdb-panel-head">
                        <div class="pdb-panel-title">
                            <span class="pdb-panel-icon">⚠️</span>
                            ${__("Alerts & Insights")}
                        </div>
                    </div>
                    <div id="pdb-alerts" class="pdb-alerts-wrap">
                        <div class="pdb-shimmer-list"></div>
                    </div>
                </div>
            </div>

        </div><!-- /.pdb-wrapper -->
    `);

    // Wire shortcut clicks
    page.main.find(".pdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (url) frappe.set_route(url.replace("/app/", "").split("/"));
    });
}

// ─── Data loading ─────────────────────────────────────────────────────────────

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_dashboard.pricing_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderKpis(page, data.kpis || {});
        renderRecentSheets(page, data.recent_sheets || []);
        renderAlerts(page, data.alerts || []);
    } catch (e) {
        // Fallback: render KPIs as zero, show empty states gracefully
        renderKpis(page, {});
        renderRecentSheets(page, []);
        renderAlerts(page, []);
        console.warn("Pricing Dashboard: failed to load data", e);
    }
}

// ─── KPI cards ───────────────────────────────────────────────────────────────

function kpiSkeleton(n) {
    return Array.from({ length: n }, () =>
        `<div class="pdb-kpi pdb-kpi--shimmer">
            <div class="pdb-shimmer pdb-shimmer--label"></div>
            <div class="pdb-shimmer pdb-shimmer--value"></div>
            <div class="pdb-shimmer pdb-shimmer--sub"></div>
        </div>`
    ).join("");
}

function renderKpis(page, kpis) {
    const grid = page.main.find("#pdb-kpi-grid");
    grid.html(`
        ${kpiCard({
        icon: "📄",
        label: __("Total Pricing Sheets"),
        value: kpis.total_sheets ?? "—",
        sub: __("{0} this month", [kpis.sheets_this_month ?? 0]),
        color: "indigo",
        trend: kpis.sheets_trend,
    })}
        ${kpiCard({
        icon: "💰",
        label: __("Avg Margin"),
        value: kpis.avg_margin_pct != null ? `${Number(kpis.avg_margin_pct).toFixed(1)}%` : "—",
        sub: __("across all active sheets"),
        color: kpis.avg_margin_pct >= 20 ? "emerald" : kpis.avg_margin_pct >= 10 ? "amber" : "rose",
        trend: null,
    })}
        ${kpiCard({
        icon: "🎯",
        label: __("Benchmark Policies"),
        value: kpis.total_benchmark_policies ?? "—",
        sub: __("{0} active sources", [kpis.benchmark_sources ?? 0]),
        color: "violet",
        trend: null,
    })}
        ${kpiCard({
        icon: "🌍",
        label: __("Customs Policies"),
        value: kpis.total_customs_policies ?? "—",
        sub: __("{0} rules configured", [kpis.customs_rules ?? 0]),
        color: "amber",
        trend: null,
    })}
        ${kpiCard({
        icon: "⚙️",
        label: __("Pricing Scenarios"),
        value: kpis.total_scenarios ?? "—",
        sub: __("{0} expense chains", [kpis.total_scenario_expenses ?? 0]),
        color: "sky",
        trend: null,
    })}
        ${kpiCard({
        icon: "⚠️",
        label: __("Sheets with Alerts"),
        value: kpis.sheets_with_alerts ?? "—",
        sub: __("missing benchmark or guardrail"),
        color: kpis.sheets_with_alerts > 0 ? "rose" : "emerald",
        trend: null,
    })}
    `);

    // Animate in
    grid.find(".pdb-kpi").each(function (i) {
        const $el = $(this);
        setTimeout(() => $el.addClass("pdb-kpi--visible"), i * 80);
    });

    // Click KPI cards to navigate
    grid.find(".pdb-kpi[data-url]").on("click", function () {
        const url = $(this).data("url");
        if (url) frappe.set_route(url.replace("/app/", "").split("/"));
    });
}

function kpiCard({ icon, label, value, sub, color, trend }) {
    const trendHtml = trend != null
        ? `<span class="pdb-kpi-trend pdb-kpi-trend--${trend >= 0 ? "up" : "down"}">${trend >= 0 ? "▲" : "▼"} ${Math.abs(trend)}%</span>`
        : "";
    return `
        <div class="pdb-kpi pdb-kpi--${color}">
            <div class="pdb-kpi-top">
                <span class="pdb-kpi-icon">${icon}</span>
                ${trendHtml}
            </div>
            <div class="pdb-kpi-value">${value}</div>
            <div class="pdb-kpi-label">${label}</div>
            <div class="pdb-kpi-sub">${sub}</div>
        </div>`;
}

// ─── Shortcut buttons ─────────────────────────────────────────────────────────

function shortcut(icon, label, url, color) {
    return `
        <div class="pdb-shortcut pdb-shortcut--${color}" data-url="${frappe.utils.escape_html(url)}" title="${frappe.utils.escape_html(label)}">
            <div class="pdb-shortcut-icon">${icon}</div>
            <div class="pdb-shortcut-label">${frappe.utils.escape_html(label)}</div>
        </div>`;
}

// ─── Recent Sheets table ─────────────────────────────────────────────────────

function renderRecentSheets(page, rows) {
    const el = page.main.find("#pdb-recent-table");
    if (!rows.length) {
        el.html(`<div class="pdb-empty">
            <div class="pdb-empty-icon">📄</div>
            <div>${__("No pricing sheets yet.")}</div>
            <a href="/app/pricing-sheet/new-pricing-sheet-1" class="btn btn-primary btn-sm pdb-mt">${__("Create First Sheet")}</a>
        </div>`);
        return;
    }

    el.html(`
        <table class="pdb-table">
            <thead>
                <tr>
                    <th>${__("Sheet")}</th>
                    <th>${__("Customer")}</th>
                    <th>${__("Scenario")}</th>
                    <th>${__("Total HT")}</th>
                    <th>${__("Modified")}</th>
                    <th>${__("By")}</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map(r => `
                    <tr class="pdb-row" data-href="/app/pricing-sheet/${encodeURIComponent(r.name)}">
                        <td><a class="pdb-tlink" href="/app/pricing-sheet/${encodeURIComponent(r.name)}">${frappe.utils.escape_html(r.sheet_name || r.name)}</a></td>
                        <td>${frappe.utils.escape_html(r.customer || "—")}</td>
                        <td>${r.pricing_scenario ? `<span class="pdb-pill">${frappe.utils.escape_html(r.pricing_scenario)}</span>` : "<span class='pdb-muted'>—</span>"}</td>
                        <td class="pdb-num">${r.total_selling != null ? frappe.format(r.total_selling, { fieldtype: "Currency" }) : "<span class='pdb-muted'>—</span>"}</td>
                        <td class="pdb-muted pdb-nowrap">${frappe.datetime.prettyDate(r.modified)}</td>
                        <td class="pdb-muted pdb-nowrap">${frappe.utils.escape_html((r.modified_by || "").split("@")[0])}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `);

    // Row click navigation
    el.find(".pdb-row").on("click", function (e) {
        if ($(e.target).is("a")) return;
        frappe.set_route("pricing-sheet", $(this).data("href").split("/").pop());
    });
}

// ─── Alerts panel ─────────────────────────────────────────────────────────────

function renderAlerts(page, alerts) {
    const el = page.main.find("#pdb-alerts");
    if (!alerts.length) {
        el.html(`<div class="pdb-alert pdb-alert--ok">
            <span class="pdb-alert-icon">✅</span>
            <div>
                <div class="pdb-alert-title">${__("All clear!")}</div>
                <div class="pdb-alert-desc">${__("No configuration issues detected.")}</div>
            </div>
        </div>`);
        return;
    }
    el.html(alerts.map(a => `
        <div class="pdb-alert pdb-alert--${a.level || "warn"}">
            <span class="pdb-alert-icon">${a.level === "error" ? "🔴" : "⚠️"}</span>
            <div>
                <div class="pdb-alert-title">${frappe.utils.escape_html(a.title)}</div>
                <div class="pdb-alert-desc">${frappe.utils.escape_html(a.message)}</div>
                ${a.link ? `<a class="pdb-alert-link" href="${frappe.utils.escape_html(a.link)}">${__("Fix →")}</a>` : ""}
            </div>
        </div>
    `).join(""));
}

// ─── Styles ───────────────────────────────────────────────────────────────────

function injectDashboardStyles() {
    if (document.getElementById("pdb-styles")) return;
    const style = document.createElement("style");
    style.id = "pdb-styles";
    style.textContent = `
/* ── Root ── */
.pdb-root { background: var(--bg-color, #f8f9fa); min-height: 100vh; }
.pdb-wrapper { max-width: 1400px; margin: 0 auto; padding: 24px 28px 60px; }

/* ── Hero ── */
.pdb-hero {
    display: flex; align-items: center; justify-content: space-between;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
    border-radius: 20px; padding: 36px 44px;
    margin-bottom: 28px; position: relative; overflow: hidden;
    box-shadow: 0 8px 40px rgba(99,102,241,0.35);
}
.pdb-hero::before {
    content: ""; position: absolute; top: -60px; right: -60px;
    width: 260px; height: 260px; border-radius: 50%;
    background: rgba(255,255,255,0.07);
}
.pdb-hero-greeting { font-size: 26px; font-weight: 700; color: #fff; line-height: 1.2; }
.pdb-hero-name { color: #e0e7ff; }
.pdb-hero-sub { font-size: 13px; color: rgba(255,255,255,0.7); margin-top: 4px; font-weight: 500; letter-spacing: 0.5px; }
.pdb-hero-tagline { font-size: 14px; color: rgba(255,255,255,0.85); margin-top: 12px; max-width: 420px; line-height: 1.6; }
.pdb-hero-badge { flex-shrink: 0; }
.pdb-hero-badge svg { width: 80px; height: 80px; filter: drop-shadow(0 8px 20px rgba(0,0,0,0.25)); }

/* ── KPI grid ── */
.pdb-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(195px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}

.pdb-kpi {
    background: var(--card-bg, #fff);
    border-radius: 16px;
    padding: 22px 22px 18px;
    position: relative; overflow: hidden;
    cursor: default;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.06);
    opacity: 0; transform: translateY(14px);
    transition: opacity 0.35s, transform 0.35s, box-shadow 0.2s;
}
.pdb-kpi--visible { opacity: 1; transform: translateY(0); }
.pdb-kpi:hover { box-shadow: 0 8px 28px rgba(0,0,0,0.12); transform: translateY(-2px); }

.pdb-kpi::after {
    content: ""; position: absolute; top: 0; left: 0;
    width: 4px; height: 100%; border-radius: 16px 0 0 16px;
}
.pdb-kpi--indigo::after { background: #6366f1; }
.pdb-kpi--violet::after { background: #8b5cf6; }
.pdb-kpi--emerald::after { background: #10b981; }
.pdb-kpi--amber::after  { background: #f59e0b; }
.pdb-kpi--sky::after    { background: #0ea5e9; }
.pdb-kpi--rose::after   { background: #f43f5e; }
.pdb-kpi--teal::after   { background: #14b8a6; }

.pdb-kpi-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.pdb-kpi-icon { font-size: 28px; line-height: 1; }
.pdb-kpi-trend { font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 999px; }
.pdb-kpi-trend--up   { background: #d1fae5; color: #065f46; }
.pdb-kpi-trend--down { background: #fee2e2; color: #991b1b; }
.pdb-kpi-value { font-size: 32px; font-weight: 800; color: var(--heading-color, #1e293b); line-height: 1; margin-bottom: 6px; }
.pdb-kpi-label { font-size: 12px; font-weight: 600; color: var(--text-muted, #64748b); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.pdb-kpi-sub { font-size: 12px; color: var(--text-muted, #94a3b8); }

/* Shimmer skeleton */
.pdb-kpi--shimmer { opacity: 1; transform: none; cursor: default; }
.pdb-kpi--shimmer::after { display: none; }
.pdb-shimmer {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 37%, #f0f0f0 63%);
    background-size: 400% 100%;
    animation: pdb-shimmer 1.4s infinite;
    border-radius: 6px;
}
.pdb-shimmer--label { height: 12px; width: 70%; margin-bottom: 10px; }
.pdb-shimmer--value { height: 32px; width: 50%; margin-bottom: 8px; }
.pdb-shimmer--sub   { height: 10px; width: 85%; }
@keyframes pdb-shimmer { 0% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }

/* ── Section title ── */
.pdb-section-title {
    font-size: 12px; font-weight: 700; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-muted, #64748b);
    margin-bottom: 14px; padding-left: 2px;
}

/* ── Shortcut buttons ── */
.pdb-shortcuts {
    display: flex; flex-wrap: wrap; gap: 12px;
    margin-bottom: 36px;
}
.pdb-shortcut {
    display: flex; align-items: center; gap: 10px;
    background: var(--card-bg, #fff);
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 12px;
    padding: 12px 18px;
    cursor: pointer;
    font-size: 14px; font-weight: 600;
    color: var(--text-color, #334155);
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    transition: all 0.15s;
    user-select: none;
}
.pdb-shortcut:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.12);
}
.pdb-shortcut-icon { font-size: 20px; line-height: 1; }
.pdb-shortcut--indigo:hover { background: #eef2ff; border-color: #6366f1; color: #4338ca; }
.pdb-shortcut--violet:hover { background: #f5f3ff; border-color: #8b5cf6; color: #6d28d9; }
.pdb-shortcut--sky:hover    { background: #f0f9ff; border-color: #0ea5e9; color: #0284c7; }
.pdb-shortcut--blue:hover   { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
.pdb-shortcut--emerald:hover{ background: #f0fdf4; border-color: #10b981; color: #065f46; }
.pdb-shortcut--amber:hover  { background: #fffbeb; border-color: #f59e0b; color: #92400e; }
.pdb-shortcut--rose:hover   { background: #fff1f2; border-color: #f43f5e; color: #9f1239; }
.pdb-shortcut--teal:hover   { background: #f0fdfa; border-color: #14b8a6; color: #0f766e; }

/* ── Lower two-column ── */
.pdb-lower {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 20px;
    align-items: start;
}
@media (max-width: 960px) { .pdb-lower { grid-template-columns: 1fr; } }

/* ── Panel ── */
.pdb-panel {
    background: var(--card-bg, #fff);
    border-radius: 16px;
    border: 1px solid rgba(0,0,0,0.07);
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    overflow: hidden;
}
.pdb-panel-head {
    display: flex; justify-content: space-between; align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.pdb-panel-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 14px; font-weight: 700; color: var(--heading-color, #1e293b);
}
.pdb-panel-icon { font-size: 18px; }
.pdb-panel-link { font-size: 12px; font-weight: 600; color: #6366f1; text-decoration: none; }
.pdb-panel-link:hover { text-decoration: underline; }

/* ── Table ── */
.pdb-table-wrap { overflow-x: auto; }
.pdb-table {
    width: 100%; border-collapse: collapse;
    font-size: 13px;
}
.pdb-table thead tr {
    background: var(--subtle-bg, #f8fafc);
}
.pdb-table th {
    text-align: left; padding: 10px 14px;
    font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted, #64748b);
    border-bottom: 1px solid var(--border-color, #e2e8f0);
    white-space: nowrap;
}
.pdb-table td {
    padding: 11px 14px;
    border-bottom: 1px solid var(--border-color, #f1f5f9);
    color: var(--text-color, #334155);
    vertical-align: middle;
}
.pdb-row { cursor: pointer; transition: background 0.12s; }
.pdb-row:hover td { background: var(--hover-bg, #f8faff); }
.pdb-tlink { color: #6366f1; font-weight: 600; text-decoration: none; }
.pdb-tlink:hover { text-decoration: underline; }
.pdb-pill {
    display: inline-block;
    background: #eef2ff; color: #4338ca;
    border-radius: 999px; font-size: 11px; font-weight: 600;
    padding: 2px 10px; white-space: nowrap;
}
.pdb-muted { color: var(--text-muted, #94a3b8); }
.pdb-nowrap { white-space: nowrap; }
.pdb-num { font-variant-numeric: tabular-nums; font-weight: 600; }

.pdb-shimmer-table {
    height: 220px; margin: 16px;
    background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 37%, #f0f0f0 63%);
    background-size: 400% 100%;
    animation: pdb-shimmer 1.4s infinite;
    border-radius: 10px;
}
.pdb-shimmer-list {
    height: 180px; margin: 16px;
    background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 37%, #f0f0f0 63%);
    background-size: 400% 100%;
    animation: pdb-shimmer 1.4s infinite;
    border-radius: 10px;
}

/* ── Alerts ── */
.pdb-alerts-wrap { padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.pdb-alert {
    display: flex; gap: 12px; align-items: flex-start;
    padding: 14px 16px; border-radius: 12px;
    font-size: 13px;
}
.pdb-alert--warn  { background: #fffbeb; border: 1px solid #fde68a; }
.pdb-alert--error { background: #fff1f2; border: 1px solid #fecdd3; }
.pdb-alert--ok    { background: #f0fdf4; border: 1px solid #bbf7d0; }
.pdb-alert-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.pdb-alert-title { font-weight: 700; color: var(--heading-color, #1e293b); margin-bottom: 3px; }
.pdb-alert-desc  { color: var(--text-muted, #64748b); font-size: 12px; line-height: 1.5; }
.pdb-alert-link  {
    display: inline-block; margin-top: 6px;
    font-size: 12px; font-weight: 600; color: #6366f1;
    text-decoration: none;
}
.pdb-alert-link:hover { text-decoration: underline; }

/* ── Empty state ── */
.pdb-empty {
    text-align: center; padding: 48px 24px;
    color: var(--text-muted, #94a3b8); font-size: 13px;
}
.pdb-empty-icon { font-size: 42px; margin-bottom: 12px; }
.pdb-mt { margin-top: 16px; }

/* ── Dark mode support ── */
[data-theme-mode="dark"] .pdb-hero { box-shadow: 0 8px 40px rgba(99,102,241,0.5); }
[data-theme-mode="dark"] .pdb-kpi,
[data-theme-mode="dark"] .pdb-shortcut,
[data-theme-mode="dark"] .pdb-panel { background: var(--card-bg); border-color: var(--border-color); }
[data-theme-mode="dark"] .pdb-shimmer,
[data-theme-mode="dark"] .pdb-shimmer-table,
[data-theme-mode="dark"] .pdb-shimmer-list {
    background: linear-gradient(90deg, #2a2a3e 25%, #313150 37%, #2a2a3e 63%);
    background-size: 400% 100%;
    animation: pdb-shimmer 1.4s infinite;
}
    `;
    document.head.appendChild(style);
}
