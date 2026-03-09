// ─── Pricing Dashboard ────────────────────────────────────────────────────────
// Premium landing page for the Orderlift Pricing module.
// Uses monochrome SVG icons (Lucide-style) and a clean modern design.
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

// ─── SVG icon library (Lucide-style, 20×20 viewport, stroke-based) ───────────

const ICONS = {
    sheet: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="2" width="14" height="16" rx="2"/>
        <line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/><line x1="7" y1="13" x2="10" y2="13"/>
    </svg>`,
    margin: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3,15 8,9 12,12 17,5"/>
        <polyline points="13,5 17,5 17,9"/>
    </svg>`,
    benchmark: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="10" cy="10" r="8"/>
        <circle cx="10" cy="10" r="3"/>
        <line x1="10" y1="2" x2="10" y2="4"/><line x1="10" y1="16" x2="10" y2="18"/>
        <line x1="2" y1="10" x2="4" y2="10"/><line x1="16" y1="10" x2="18" y2="10"/>
    </svg>`,
    customs: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="10" cy="10" rx="8" ry="5"/>
        <line x1="2" y1="10" x2="18" y2="10"/>
        <ellipse cx="10" cy="10" rx="3.5" ry="5"/>
    </svg>`,
    scenario: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="5" cy="5" r="2"/><circle cx="15" cy="5" r="2"/>
        <circle cx="5" cy="15" r="2"/><circle cx="15" cy="15" r="2"/>
        <line x1="7" y1="5" x2="13" y2="5"/>
        <line x1="5" y1="7" x2="5" y2="13"/>
        <line x1="7" y1="15" x2="13" y2="15"/>
        <line x1="15" y1="7" x2="15" y2="13"/>
    </svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 2L2 17h16L10 2z"/>
        <line x1="10" y1="9" x2="10" y2="12"/>
        <circle cx="10" cy="14.5" r="0.6" fill="currentColor"/>
    </svg>`,
    plus: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/>
    </svg>`,
    simulator: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="3" width="16" height="11" rx="2"/>
        <line x1="7" y1="17" x2="13" y2="17"/>
        <line x1="10" y1="14" x2="10" y2="17"/>
        <polyline points="5,11 8,7 11,9 15,4"/>
    </svg>`,
    builder: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="2" width="6" height="6" rx="1"/>
        <rect x="12" y="2" width="6" height="6" rx="1"/>
        <rect x="2" y="12" width="6" height="6" rx="1"/>
        <rect x="12" y="12" width="6" height="6" rx="1"/>
    </svg>`,
    list: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
        <line x1="3" y1="6" x2="17" y2="6"/>
        <line x1="3" y1="10" x2="17" y2="10"/>
        <line x1="3" y1="14" x2="13" y2="14"/>
    </svg>`,
    dim: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 2l7 4v8l-7 4-7-4V6z"/>
        <line x1="10" y1="2" x2="10" y2="18"/>
        <line x1="3" y1="6" x2="17" y2="14"/>
        <line x1="17" y1="6" x2="3" y2="14"/>
    </svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="4,10 8,14 16,6"/>
    </svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <line x1="4" y1="10" x2="16" y2="10"/>
        <polyline points="11,5 16,10 11,15"/>
    </svg>`,
    external: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 3H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/>
        <polyline points="13,3 17,3 17,7"/>
        <line x1="10" y1="10" x2="17" y2="3"/>
    </svg>`,
    clock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
        <circle cx="10" cy="10" r="8"/>
        <polyline points="10,5 10,10 13,13"/>
    </svg>`,
    user: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="10" cy="7" r="4"/>
        <path d="M2 18c0-4 3.6-7 8-7s8 3 8 7"/>
    </svg>`,
};

// ─── Skeleton layout ──────────────────────────────────────────────────────────

function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting =
        hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const today = frappe.datetime.str_to_user(frappe.datetime.now_date());

    page.main.html(`
        <div class="pdb-wrapper">

            <!-- ── Hero ── -->
            <div class="pdb-hero">
                <div class="pdb-hero-left">
                    <div class="pdb-hero-eyebrow">${__("Orderlift · Pricing Hub")}</div>
                    <div class="pdb-hero-greeting">${greeting}</div>
                    <div class="pdb-hero-sub">${today}</div>
                </div>
                <div class="pdb-hero-right">
                    <div class="pdb-hero-stat" id="pdb-hero-sheets">
                        <div class="pdb-hero-stat-val">—</div>
                        <div class="pdb-hero-stat-label">${__("Pricing Sheets")}</div>
                    </div>
                    <div class="pdb-hero-divider"></div>
                    <div class="pdb-hero-stat" id="pdb-hero-margin">
                        <div class="pdb-hero-stat-val">—</div>
                        <div class="pdb-hero-stat-label">${__("Avg Margin")}</div>
                    </div>
                    <div class="pdb-hero-divider"></div>
                    <div class="pdb-hero-stat" id="pdb-hero-alerts">
                        <div class="pdb-hero-stat-val">—</div>
                        <div class="pdb-hero-stat-label">${__("Alerts")}</div>
                    </div>
                </div>
            </div>

            <!-- ── Shortcuts ── -->
            <div class="pdb-shortcuts-grid">
                ${shortcut("plus", __("New Pricing Sheet"), "/app/pricing-sheet/new-pricing-sheet-1", "primary")}
                ${shortcut("simulator", __("Pricing Simulator"), "/app/pricing-simulator", "default")}
                ${shortcut("builder", __("Pricing Builder"), "/app/pricing-builder", "default")}
                ${shortcut("list", __("All Sheets"), "/app/pricing-sheet", "default")}
                ${shortcut("benchmark", __("Benchmark Policies"), "/app/pricing-benchmark-policy", "default")}
                ${shortcut("customs", __("Customs Policies"), "/app/pricing-customs-policy", "default")}
                ${shortcut("scenario", __("Scenarios"), "/app/pricing-scenario", "default")}
                ${shortcut("dim", __("Dimensioning Sets"), "/app/dimensioning-set", "default")}
            </div>

            <!-- ── KPI strip ── -->
            <div class="pdb-kpi-grid" id="pdb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="pdb-kpi pdb-kpi--shimmer"></div>`).join("")}
            </div>

            <!-- ── Lower grid ── -->
            <div class="pdb-lower">

                <!-- Recent sheets -->
                <div class="pdb-card">
                    <div class="pdb-card-header">
                        <div class="pdb-card-title">
                            <span class="pdb-card-icon">${ICONS.sheet}</span>
                            ${__("Recent Pricing Sheets")}
                        </div>
                        <a href="/app/pricing-sheet" class="pdb-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="pdb-recent-table" class="pdb-table-wrap">
                        <div class="pdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <!-- Alerts -->
                <div class="pdb-card">
                    <div class="pdb-card-header">
                        <div class="pdb-card-title">
                            <span class="pdb-card-icon">${ICONS.alert}</span>
                            ${__("Configuration Alerts")}
                        </div>
                    </div>
                    <div id="pdb-alerts" class="pdb-alerts-wrap">
                        <div class="pdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

            </div><!-- /.pdb-lower -->

        </div><!-- /.pdb-wrapper -->
    `);

    // Wire shortcut clicks
    page.main.find(".pdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (!url) return;
        frappe.set_route(url.replace(/^\/app\//, "").split("/"));
    });
}

// ─── Data loading ─────────────────────────────────────────────────────────────

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_dashboard.pricing_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {});
        renderKpis(page, data.kpis || {});
        renderRecentSheets(page, data.recent_sheets || []);
        renderAlerts(page, data.alerts || []);
    } catch (e) {
        renderHeroStats(page, {});
        renderKpis(page, {});
        renderRecentSheets(page, []);
        renderAlerts(page, []);
        console.warn("Pricing Dashboard: failed to load data", e);
    }
}

// ─── Hero stats ───────────────────────────────────────────────────────────────

function renderHeroStats(page, kpis) {
    page.main.find("#pdb-hero-sheets .pdb-hero-stat-val").text(kpis.total_sheets ?? "—");
    page.main.find("#pdb-hero-margin .pdb-hero-stat-val").text(
        kpis.avg_margin_pct != null ? `${Number(kpis.avg_margin_pct).toFixed(1)}%` : "—"
    );
    const alertCount = kpis.sheets_with_alerts ?? "—";
    const alertEl = page.main.find("#pdb-hero-alerts .pdb-hero-stat-val");
    alertEl.text(alertCount);
    if (alertCount > 0) alertEl.addClass("pdb-stat-warn");
}

// ─── Shortcut buttons ─────────────────────────────────────────────────────────

function shortcut(iconKey, label, url, variant) {
    return `
        <div class="pdb-shortcut pdb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}">
            <span class="pdb-shortcut-icon">${ICONS[iconKey] || ""}</span>
            <span class="pdb-shortcut-label">${frappe.utils.escape_html(label)}</span>
        </div>`;
}

// ─── KPI cards ────────────────────────────────────────────────────────────────

function renderKpis(page, kpis) {
    const defs = [
        {
            icon: "sheet",
            label: __("Total Sheets"),
            value: kpis.total_sheets ?? "—",
            sub: __("{0} this month", [kpis.sheets_this_month ?? 0]),
        },
        {
            icon: "margin",
            label: __("Avg Margin"),
            value: kpis.avg_margin_pct != null ? `${Number(kpis.avg_margin_pct).toFixed(1)}%` : "—",
            sub: __("across all sheets"),
            highlight: kpis.avg_margin_pct < 10 ? "warn" : null,
        },
        {
            icon: "benchmark",
            label: __("Benchmark Policies"),
            value: kpis.total_benchmark_policies ?? "—",
            sub: __("{0} sources", [kpis.benchmark_sources ?? 0]),
        },
        {
            icon: "customs",
            label: __("Customs Policies"),
            value: kpis.total_customs_policies ?? "—",
            sub: __("{0} rules", [kpis.customs_rules ?? 0]),
        },
        {
            icon: "scenario",
            label: __("Pricing Scenarios"),
            value: kpis.total_scenarios ?? "—",
            sub: __("{0} expense entries", [kpis.total_scenario_expenses ?? 0]),
        },
        {
            icon: "alert",
            label: __("Configuration Alerts"),
            value: kpis.sheets_with_alerts ?? "—",
            sub: __("sheets need attention"),
            highlight: (kpis.sheets_with_alerts ?? 0) > 0 ? "warn" : "ok",
        },
    ];

    const grid = page.main.find("#pdb-kpi-grid");
    grid.html(defs.map((d, i) => `
        <div class="pdb-kpi pdb-kpi--${d.highlight || "default"}" style="animation-delay:${i * 60}ms">
            <div class="pdb-kpi-header">
                <span class="pdb-kpi-icon">${ICONS[d.icon] || ""}</span>
            </div>
            <div class="pdb-kpi-value">${d.value}</div>
            <div class="pdb-kpi-label">${d.label}</div>
            <div class="pdb-kpi-sub">${d.sub}</div>
        </div>
    `).join(""));

    // Staggered fade-in
    grid.find(".pdb-kpi").each(function (i) {
        const $el = $(this);
        setTimeout(() => $el.addClass("pdb-kpi--in"), i * 60);
    });
}

// ─── Recent Sheets table ──────────────────────────────────────────────────────

function renderRecentSheets(page, rows) {
    const el = page.main.find("#pdb-recent-table");
    if (!rows.length) {
        el.html(`
            <div class="pdb-empty">
                <span class="pdb-empty-icon">${ICONS.sheet}</span>
                <p>${__("No pricing sheets yet.")}</p>
                <button class="btn btn-primary btn-sm" onclick="frappe.set_route('pricing-sheet','new-pricing-sheet-1')">
                    ${__("Create First Sheet")}
                </button>
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
                    <th class="pdb-right">${__("Total HT")}</th>
                    <th>${__("Modified")}</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map(r => `
                    <tr class="pdb-row" data-route="pricing-sheet/${encodeURIComponent(r.name)}">
                        <td>
                            <a class="pdb-tlink" href="/app/pricing-sheet/${encodeURIComponent(r.name)}">
                                ${frappe.utils.escape_html(r.sheet_name || r.name)}
                            </a>
                        </td>
                        <td class="pdb-muted">${frappe.utils.escape_html(r.customer || "—")}</td>
                        <td>${r.pricing_scenario
            ? `<span class="pdb-tag">${frappe.utils.escape_html(r.pricing_scenario)}</span>`
            : `<span class="pdb-muted">—</span>`}
                        </td>
                        <td class="pdb-right pdb-mono">
                            ${r.total_selling != null
            ? frappe.format(r.total_selling, { fieldtype: "Currency" })
            : `<span class="pdb-muted">—</span>`}
                        </td>
                        <td class="pdb-muted pdb-nowrap">
                            <span class="pdb-meta-row">
                                <span class="pdb-meta-icon">${ICONS.clock}</span>
                                ${frappe.datetime.prettyDate(r.modified)}
                            </span>
                        </td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `);

    el.find(".pdb-row").on("click", function (e) {
        if ($(e.target).is("a")) return;
        frappe.set_route($(this).data("route").split("/"));
    });
}

// ─── Alerts panel ─────────────────────────────────────────────────────────────

function renderAlerts(page, alerts) {
    const el = page.main.find("#pdb-alerts");
    if (!alerts.length) {
        el.html(`
            <div class="pdb-alert-item pdb-alert-item--ok">
                <span class="pdb-alert-ico">${ICONS.check}</span>
                <div>
                    <div class="pdb-alert-title">${__("All clear")}</div>
                    <div class="pdb-alert-body">${__("No configuration issues detected.")}</div>
                </div>
            </div>`);
        return;
    }
    el.html(alerts.map(a => `
        <div class="pdb-alert-item pdb-alert-item--${a.level || "warn"}">
            <span class="pdb-alert-ico">${ICONS.alert}</span>
            <div class="pdb-alert-content">
                <div class="pdb-alert-title">${frappe.utils.escape_html(a.title)}</div>
                <div class="pdb-alert-body">${frappe.utils.escape_html(a.message)}</div>
                ${a.link
            ? `<a class="pdb-alert-link" href="${frappe.utils.escape_html(a.link)}">
                           ${__("Review")} <span class="pdb-alert-arrow">${ICONS.arrow}</span>
                       </a>`
            : ""}
            </div>
        </div>
    `).join(""));
}

// ─── Styles ───────────────────────────────────────────────────────────────────

function injectDashboardStyles() {
    if (document.getElementById("pdb-styles")) return;
    const s = document.createElement("style");
    s.id = "pdb-styles";
    s.textContent = `
/* ── Root & wrapper ── */
.pdb-root { background: var(--bg-color, #f4f6f9); min-height: 100vh; }
.pdb-wrapper { max-width: 1380px; margin: 0 auto; padding: 28px 32px 72px; }

/* ── Hero ── */
.pdb-hero {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 24px;
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04);
    position: relative; overflow: hidden;
}
.pdb-hero::before {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(99,102,241,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.pdb-hero-eyebrow {
    font-size: 11px; font-weight: 700; letter-spacing: 1px;
    text-transform: uppercase; color: #6366f1; margin-bottom: 6px;
}
.pdb-hero-greeting {
    font-size: 26px; font-weight: 700; color: var(--heading-color, #1a1f2e); line-height: 1.2;
}
.pdb-hero-sub { font-size: 13px; color: var(--text-muted, #8c95a6); margin-top: 4px; }

.pdb-hero-right { display: flex; align-items: center; gap: 0; }
.pdb-hero-stat { text-align: center; padding: 0 36px; }
.pdb-hero-stat-val { font-size: 30px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; }
.pdb-hero-stat-val.pdb-stat-warn { color: #e11d48; }
.pdb-hero-stat-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: var(--text-muted, #8c95a6); margin-top: 5px; }
.pdb-hero-divider { width: 1px; height: 40px; background: var(--border-color, #e8ecf0); }

/* ── Shortcuts grid ── */
.pdb-shortcuts-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 10px;
    margin-bottom: 20px;
}
@media (max-width: 1100px) { .pdb-shortcuts-grid { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 640px)  { .pdb-shortcuts-grid { grid-template-columns: repeat(2, 1fr); } }

.pdb-shortcut {
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 12px;
    padding: 16px 12px;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
    user-select: none;
}
.pdb-shortcut:hover {
    border-color: #6366f1; box-shadow: 0 4px 16px rgba(99,102,241,0.15);
    transform: translateY(-2px);
}
.pdb-shortcut--primary {
    background: #6366f1; border-color: #6366f1; color: #fff;
}
.pdb-shortcut--primary .pdb-shortcut-icon svg { stroke: #fff; }
.pdb-shortcut--primary .pdb-shortcut-label { color: #fff; }
.pdb-shortcut--primary:hover { background: #4f46e5; border-color: #4f46e5; box-shadow: 0 4px 20px rgba(99,102,241,0.4); }

.pdb-shortcut-icon { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; }
.pdb-shortcut-icon svg { width: 22px; height: 22px; stroke: var(--text-muted, #64748b); }
.pdb-shortcut:hover .pdb-shortcut-icon svg { stroke: #6366f1; }
.pdb-shortcut--primary:hover .pdb-shortcut-icon svg { stroke: #fff; }

.pdb-shortcut-label {
    font-size: 11.5px; font-weight: 600; text-align: center; line-height: 1.3;
    color: var(--text-color, #334155);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
}

/* ── KPI strip ── */
.pdb-kpi-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
@media (max-width: 1100px) { .pdb-kpi-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px)  { .pdb-kpi-grid { grid-template-columns: repeat(2, 1fr); } }

.pdb-kpi {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 12px;
    padding: 18px 18px 16px;
    opacity: 0; transform: translateY(10px);
    transition: opacity 0.3s, transform 0.3s, box-shadow 0.15s;
}
.pdb-kpi--in { opacity: 1; transform: translateY(0); }
.pdb-kpi:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }

.pdb-kpi--shimmer { opacity: 1; transform: none; }
.pdb-kpi--warn { border-color: #fca5a5; background: #fff5f5; }
.pdb-kpi--ok   { border-color: #86efac; }

.pdb-kpi-header { margin-bottom: 10px; }
.pdb-kpi-icon { display: inline-flex; width: 32px; height: 32px; border-radius: 8px; background: #f1f5f9; align-items: center; justify-content: center; }
.pdb-kpi-icon svg { width: 16px; height: 16px; stroke: #6366f1; }
.pdb-kpi--warn .pdb-kpi-icon { background: #fee2e2; }
.pdb-kpi--warn .pdb-kpi-icon svg { stroke: #dc2626; }

.pdb-kpi-value { font-size: 28px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; margin-bottom: 4px; }
.pdb-kpi--warn .pdb-kpi-value { color: #dc2626; }
.pdb-kpi-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted, #64748b); margin-bottom: 3px; }
.pdb-kpi-sub   { font-size: 11.5px; color: var(--text-muted, #94a3b8); }

/* Shimmer */
.pdb-kpi--shimmer {
    background: linear-gradient(90deg, #f1f5f9 25%, #e8ecf2 37%, #f1f5f9 63%);
    background-size: 400% 100%;
    animation: pdb-shimmer 1.4s infinite;
    min-height: 110px;
}
.pdb-shimmer-block {
    background: linear-gradient(90deg, #f1f5f9 25%, #e8ecf2 37%, #f1f5f9 63%);
    background-size: 400% 100%;
    animation: pdb-shimmer 1.4s infinite;
}
@keyframes pdb-shimmer { 0% { background-position: 100% 50%; } 100% { background-position: 0 50%; } }

/* ── Lower two-column ── */
.pdb-lower { display: grid; grid-template-columns: 1fr 360px; gap: 16px; align-items: start; }
@media (max-width: 960px) { .pdb-lower { grid-template-columns: 1fr; } }

/* ── Card ── */
.pdb-card {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.pdb-card-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.pdb-card-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e);
}
.pdb-card-icon { display: inline-flex; align-items: center; }
.pdb-card-icon svg { width: 15px; height: 15px; stroke: #6366f1; }

.pdb-view-all {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; font-weight: 600; color: #6366f1; text-decoration: none;
    transition: gap 0.15s;
}
.pdb-view-all:hover { gap: 7px; }
.pdb-view-all svg { width: 13px; height: 13px; stroke: #6366f1; }

/* ── Table ── */
.pdb-table-wrap { overflow-x: auto; }
.pdb-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pdb-table thead tr { background: var(--subtle-bg, #f8fafc); }
.pdb-table th {
    text-align: left; padding: 9px 16px;
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted, #64748b);
    border-bottom: 1px solid var(--border-color, #e8ecf0);
    white-space: nowrap;
}
.pdb-table td {
    padding: 11px 16px;
    border-bottom: 1px solid var(--border-color, #f1f5f9);
    color: var(--text-color, #334155);
}
.pdb-table tbody tr:last-child td { border-bottom: none; }
.pdb-row { cursor: pointer; transition: background 0.1s; }
.pdb-row:hover td { background: #fafbff; }

.pdb-tlink { font-weight: 600; color: #6366f1; text-decoration: none; }
.pdb-tlink:hover { text-decoration: underline; }
.pdb-tag {
    display: inline-block; padding: 2px 9px;
    background: #f1f5f9; border-radius: 999px;
    font-size: 11.5px; font-weight: 600; color: #475569;
}
.pdb-muted  { color: var(--text-muted, #94a3b8); }
.pdb-nowrap { white-space: nowrap; }
.pdb-right  { text-align: right; }
.pdb-mono   { font-variant-numeric: tabular-nums; font-weight: 600; }

.pdb-meta-row { display: inline-flex; align-items: center; gap: 4px; }
.pdb-meta-row svg { width: 12px; height: 12px; stroke: var(--text-muted, #94a3b8); flex-shrink: 0; }

/* ── Alerts ── */
.pdb-alerts-wrap { padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.pdb-alert-item {
    display: flex; gap: 12px; padding: 14px 16px;
    border-radius: 10px; border: 1px solid;
}
.pdb-alert-item--warn  { background: #fffbeb; border-color: #fde68a; }
.pdb-alert-item--error { background: #fff1f2; border-color: #fecdd3; }
.pdb-alert-item--ok    { background: #f0fdf4; border-color: #bbf7d0; }

.pdb-alert-ico { flex-shrink: 0; display: inline-flex; margin-top: 1px; }
.pdb-alert--warn  .pdb-alert-ico svg, .pdb-alert-item--warn  .pdb-alert-ico svg { width: 16px; height: 16px; stroke: #d97706; }
.pdb-alert-item--error .pdb-alert-ico svg { width: 16px; height: 16px; stroke: #dc2626; }
.pdb-alert-item--ok    .pdb-alert-ico svg { width: 16px; height: 16px; stroke: #16a34a; }

.pdb-alert-title { font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e); margin-bottom: 3px; }
.pdb-alert-body  { font-size: 12px; color: var(--text-muted, #64748b); line-height: 1.5; }
.pdb-alert-link  {
    display: inline-flex; align-items: center; gap: 4px;
    margin-top: 8px; font-size: 12px; font-weight: 600; color: #6366f1; text-decoration: none;
}
.pdb-alert-link:hover { text-decoration: underline; }
.pdb-alert-arrow svg { width: 12px; height: 12px; stroke: #6366f1; }

/* ── Empty state ── */
.pdb-empty {
    display: flex; flex-direction: column; align-items: center;
    padding: 48px 24px; text-align: center;
    color: var(--text-muted, #94a3b8); font-size: 13px; gap: 10px;
}
.pdb-empty-icon { display: inline-flex; }
.pdb-empty-icon svg { width: 36px; height: 36px; stroke: #cbd5e1; }

/* ── Dark mode ── */
[data-theme-mode="dark"] .pdb-kpi--shimmer,
[data-theme-mode="dark"] .pdb-shimmer-block {
    background: linear-gradient(90deg, #22263a 25%, #2a2f48 37%, #22263a 63%);
    background-size: 400% 100%; animation: pdb-shimmer 1.4s infinite;
}
[data-theme-mode="dark"] .pdb-row:hover td { background: rgba(99,102,241,0.06); }
[data-theme-mode="dark"] .pdb-tag { background: #2a2f48; color: #94a3b8; }
    `;
    document.head.appendChild(s);
}
