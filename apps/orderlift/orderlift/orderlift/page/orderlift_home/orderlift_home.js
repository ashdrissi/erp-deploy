// ─── Orderlift — Home Dashboard (Control Tower) ───────────────────────────────
// Master landing page. Sections:
//   Hero · Module Gateways · Global KPI Strip · 3-col grid (Pricing / Stock / Sales)
//   Bottom: Live Alerts · Pending Actions · Recent Activity
// ─────────────────────────────────────────────────────────────────────────────

frappe.pages["orderlift-home"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Home"),
        single_column: true,
    });
    page.main.addClass("hdb-root");
    injectStyles();
    renderSkeleton(page);
    loadData(page);

    page.add_action_item(__("Refresh"), () => {
        loadData(page);
        frappe.show_alert({ message: __("Refreshed"), indicator: "green" });
    });
};

// ─── Icons ────────────────────────────────────────────────────────────────────

const IC = {
    pricing: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="15" x2="15" y2="5"/><circle cx="7" cy="7" r="2"/><circle cx="13" cy="13" r="2"/></svg>`,
    stock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M17 4L10 2 3 4v8l7 4 7-4V4z"/><line x1="10" y1="2" x2="10" y2="14"/><line x1="3" y1="7" x2="17" y2="7"/></svg>`,
    sales: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8l8-5 8 5v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8z"/><polyline points="8,19 8,12 12,12 12,19"/></svg>`,
    crm: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="7" r="4"/><path d="M16 17a7 7 0 0 0-14 0"/><circle cx="16" cy="14" r="3"/><line x1="16" y1="12" x2="16" y2="16"/><line x1="14" y1="14" x2="18" y2="14"/></svg>`,
    logistics: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="7" width="14" height="9" rx="1"/><path d="M15 10h2l2 3v3h-4V10z"/><circle cx="5" cy="18" r="1.5" fill="currentColor" stroke="none"/><circle cx="15" cy="18" r="1.5" fill="currentColor" stroke="none"/></svg>`,
    sav: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l.3-.3a2 2 0 0 0-2.8-2.8l-.5.1z"/><path d="M6 14l-4 4"/><path d="M14 6l-8 8 1.5 1.5L16 7.5 14 6z"/></svg>`,
    finance: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="16" height="12" rx="2"/><line x1="2" y1="8" x2="18" y2="8"/><line x1="6" y1="13" x2="10" y2="13"/></svg>`,
    hr: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="4"/><path d="M3 18a7 7 0 0 1 14 0"/></svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r=".7" fill="currentColor" stroke="none"/></svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,10 8,14 16,6"/></svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="10" x2="16" y2="10"/><polyline points="11,5 16,10 11,15"/></svg>`,
    clock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="8"/><polyline points="10,5 10,10 13,13"/></svg>`,
    order: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="17" y2="6"/><polyline points="9,11 10,13 13,10"/></svg>`,
    transfer: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="7" x2="16" y2="7"/><polyline points="11,3 16,7 11,11"/><line x1="16" y1="13" x2="4" y2="13"/><polyline points="9,9 4,13 9,17"/></svg>`,
    invoice: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><line x1="9" y1="9" x2="14" y2="9"/><line x1="9" y1="13" x2="14" y2="13"/></svg>`,
    ticket: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7a2 2 0 0 1 0-4h16a2 2 0 0 1 0 4"/><rect x="2" y="7" width="16" height="11" rx="1"/><line x1="7" y1="12" x2="13" y2="12"/></svg>`,
    settings: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="3"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.9 4.9l1.4 1.4M13.7 13.7l1.4 1.4M4.9 15.1l1.4-1.4M13.7 6.3l1.4-1.4"/></svg>`,
};

// ─── Module gateway definitions ───────────────────────────────────────────────

const GATEWAYS = [
    { icon: "pricing", label: __("Pricing & Sales"), desc: __("Price sheets, policies, simulator"), url: "pricing-dashboard", color: "#6366f1" },
    { icon: "stock", label: __("Stock & Warehouses"), desc: __("Inventory, transfers, reorder queue"), url: "stock-dashboard", color: "#10b981" },
    { icon: "logistics", label: __("Logistics"), desc: __("Suppliers, purchase orders, delivery"), url: "logistics-dashboard", color: "#f59e0b" },
    { icon: "crm", label: __("CRM"), desc: __("Customers, pipeline, campaigns"), url: "crm-dashboard", color: "#3b82f6" },
    { icon: "sav", label: __("SAV / Field Service"), desc: __("Tickets, interventions, SLA"), url: "sav-dashboard", color: "#ec4899" },
    { icon: "finance", label: __("Finance"), desc: __("Invoices, payments, P&L"), url: "finance-dashboard", color: "#8b5cf6" },
    { icon: "hr", label: __("HR"), desc: __("Employees, leave, payroll"), url: "hr-dashboard", color: "#06b6d4" },
    { icon: "settings", label: __("Settings"), desc: __("Users, roles, company config"), url: "setup/company", color: "#64748b" },
];

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function renderSkeleton(page) {
    page.main.html(`
        <div class="hdb-wrap">

            <!-- Hero -->
            <div class="hdb-hero">
                <div class="hdb-hero-left">
                    <div class="hdb-greeting" id="hdb-greeting">${__("Good day")}</div>
                    <div class="hdb-hero-date" id="hdb-date">${__("Loading…")}</div>
                </div>
                <div class="hdb-hero-right" id="hdb-hero-stats">
                    <div class="hdb-hero-stat"><div class="hdb-hero-val hdb-shimmer-inline">—</div><div class="hdb-hero-lbl">${__("Sales / Month")}</div></div>
                    <div class="hdb-hero-stat"><div class="hdb-hero-val hdb-shimmer-inline">—</div><div class="hdb-hero-lbl">${__("Open Quotes")}</div></div>
                    <div class="hdb-hero-stat"><div class="hdb-hero-val hdb-shimmer-inline">—</div><div class="hdb-hero-lbl">${__("Alerts")}</div></div>
                </div>
            </div>

            <!-- Gateways -->
            <div class="hdb-gateways">
                ${GATEWAYS.map(g => gatewayCard(g)).join("")}
            </div>

            <!-- KPI strip -->
            <div class="hdb-kpi-strip" id="hdb-kpi-strip">
                ${[1, 2, 3, 4, 5, 6, 7].map(() => `<div class="hdb-kpi hdb-shimmer-kpi"></div>`).join("")}
            </div>

            <!-- 3-col module summaries -->
            <div class="hdb-module-grid">

                <!-- Pricing summary -->
                <div class="hdb-mcard hdb-mcard--pricing">
                    <div class="hdb-mc-hd">
                        <span class="hdb-mc-ico hdb-mc-ico--pricing">${IC.pricing}</span>
                        <div>
                            <div class="hdb-mc-title">${__("Pricing Engine")}</div>
                            <div class="hdb-mc-sub">${__("Policies · Sheets · Scenarios")}</div>
                        </div>
                        <a href="/app/pricing-dashboard" class="hdb-mc-link">${IC.arrow}</a>
                    </div>
                    <div id="hdb-pricing-body" class="hdb-mc-body">
                        <div class="hdb-shimmer-block" style="height:90px;margin:12px 16px;border-radius:8px;"></div>
                    </div>
                    <div class="hdb-mc-actions">
                        ${mcBtn(__("New Sheet"), "pricing-dashboard", "primary")}
                        ${mcBtn(__("Simulator"), "pricing-simulator", "ghost")}
                        ${mcBtn(__("Builder"), "pricing-builder", "ghost")}
                    </div>
                </div>

                <!-- Stock summary -->
                <div class="hdb-mcard hdb-mcard--stock">
                    <div class="hdb-mc-hd">
                        <span class="hdb-mc-ico hdb-mc-ico--stock">${IC.stock}</span>
                        <div>
                            <div class="hdb-mc-title">${__("Stock & Warehouses")}</div>
                            <div class="hdb-mc-sub">${__("Inventory · Transfers · Alerts")}</div>
                        </div>
                        <a href="/app/stock-dashboard" class="hdb-mc-link">${IC.arrow}</a>
                    </div>
                    <div id="hdb-stock-body" class="hdb-mc-body">
                        <div class="hdb-shimmer-block" style="height:90px;margin:12px 16px;border-radius:8px;"></div>
                    </div>
                    <div class="hdb-mc-actions">
                        ${mcBtn(__("Stock Entry"), "stock-entry/new-stock-entry-1", "primary")}
                        ${mcBtn(__("All Stock"), "stock/item", "ghost")}
                        ${mcBtn(__("Warehouses"), "stock/warehouse", "ghost")}
                    </div>
                </div>

                <!-- Sales summary -->
                <div class="hdb-mcard hdb-mcard--sales">
                    <div class="hdb-mc-hd">
                        <span class="hdb-mc-ico hdb-mc-ico--sales">${IC.sales}</span>
                        <div>
                            <div class="hdb-mc-title">${__("Sales & Finance")}</div>
                            <div class="hdb-mc-sub">${__("Orders · Invoices · Deliveries")}</div>
                        </div>
                        <a href="/app/selling/sales-order" class="hdb-mc-link">${IC.arrow}</a>
                    </div>
                    <div id="hdb-sales-body" class="hdb-mc-body">
                        <div class="hdb-shimmer-block" style="height:90px;margin:12px 16px;border-radius:8px;"></div>
                    </div>
                    <div class="hdb-mc-actions">
                        ${mcBtn(__("New Quotation"), "selling/quotation/new-quotation-1", "primary")}
                        ${mcBtn(__("Sales Orders"), "selling/sales-order", "ghost")}
                        ${mcBtn(__("Invoices"), "accounts/sales-invoice", "ghost")}
                    </div>
                </div>

            </div>

            <!-- Bottom grid: alerts · actions · activity -->
            <div class="hdb-bottom-grid">

                <!-- Alerts -->
                <div class="hdb-card">
                    <div class="hdb-card-hd">
                        <div class="hdb-card-title">${IC.alert} ${__("Live Alerts")}</div>
                        <span class="hdb-badge-live" id="hdb-alert-count"></span>
                    </div>
                    <div id="hdb-alerts" class="hdb-alerts-list">
                        <div class="hdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <!-- Pending actions -->
                <div class="hdb-card">
                    <div class="hdb-card-hd">
                        <div class="hdb-card-title">${IC.clock} ${__("Pending Actions")}</div>
                    </div>
                    <div id="hdb-actions" class="hdb-actions-list">
                        <div class="hdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <!-- Recent activity -->
                <div class="hdb-card">
                    <div class="hdb-card-hd">
                        <div class="hdb-card-title">${IC.clock} ${__("Recent Activity")}</div>
                    </div>
                    <div id="hdb-activity" class="hdb-activity-list">
                        <div class="hdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

            </div>

        </div>
    `);

    // Wire gateways
    page.main.find(".hdb-gateway").on("click", function () {
        const url = $(this).data("url");
        frappe.set_route(url.split("/"));
    });
    page.main.find(".hdb-mc-btn").on("click", function () {
        frappe.set_route($(this).data("url").split("/"));
    });
}

function gatewayCard(g) {
    return `
        <div class="hdb-gateway" data-url="${g.url}" style="--gw-color:${g.color}">
            <span class="hdb-gw-ico">${IC[g.icon]}</span>
            <div class="hdb-gw-label">${frappe.utils.escape_html(g.label)}</div>
            <div class="hdb-gw-desc">${frappe.utils.escape_html(g.desc)}</div>
        </div>`;
}

function mcBtn(label, url, variant) {
    return `<button class="hdb-mc-btn hdb-mc-btn--${variant}" data-url="${url}">${frappe.utils.escape_html(label)}</button>`;
}

// ─── Data loading ─────────────────────────────────────────────────────────────

async function loadData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift.page.orderlift_home.orderlift_home.get_dashboard_data",
        });
        const d = res.message || {};
        renderHero(page, d.user || {}, d.kpis || {});
        renderKpis(page, d.kpis || {});
        renderPricingSummary(page, d.pricing_summary || {});
        renderStockSummary(page, d.stock_summary || {}, d.kpis || {});
        renderSalesSummary(page, d.sales_summary || {}, d.kpis || {});
        renderAlerts(page, d.alerts || []);
        renderPendingActions(page, d.pending_actions || []);
        renderActivity(page, d.recent_activity || []);
    } catch (e) {
        console.error("Home Dashboard: data load failed", e);
    }
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function renderHero(page, user, kpis) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const name = (user.full_name || "").split(" ")[0];
    page.main.find("#hdb-greeting").text(`${greeting}, ${name} 👋`);
    page.main.find("#hdb-date").text(user.today || "");

    const salesFmt = kpis.sales_month > 0 ? `${(kpis.sales_month / 1000).toFixed(1)}k` : "—";
    page.main.find("#hdb-hero-stats").html(`
        <div class="hdb-hero-stat">
            <div class="hdb-hero-val">${salesFmt}</div>
            <div class="hdb-hero-lbl">${__("Sales / Month")}</div>
        </div>
        <div class="hdb-hero-stat">
            <div class="hdb-hero-val">${kpis.open_quotes ?? "—"}</div>
            <div class="hdb-hero-lbl">${__("Open Quotes")}</div>
        </div>
        <div class="hdb-hero-stat">
            <div class="hdb-hero-val ${(kpis.stockouts || 0) > 0 ? "hdb-val-red" : ""}">${(kpis.stockouts || 0) + (kpis.open_tickets || 0)}</div>
            <div class="hdb-hero-lbl">${__("Alerts")}</div>
        </div>
    `);
}

// ─── KPI strip ────────────────────────────────────────────────────────────────

function renderKpis(page, k) {
    const defs = [
        { icon: "sales", label: __("Orders / Month"), value: k.pricing_sheets_month ?? 0, badge: null },
        { icon: "invoice", label: __("Open Quotations"), value: k.open_quotes ?? 0, badge: null },
        { icon: "stock", label: __("Total Stock Units"), value: (k.total_stock || 0).toLocaleString(), badge: null },
        { icon: "alert", label: __("Stockouts"), value: k.stockouts ?? 0, badge: (k.stockouts || 0) > 0 ? "error" : null },
        { icon: "transfer", label: __("Pending Transfers"), value: k.pending_transfers ?? 0, badge: (k.pending_transfers || 0) > 0 ? "warn" : null },
        { icon: "pricing", label: __("Pricing Sheets / Mo"), value: k.pricing_sheets_month ?? 0, badge: null },
        { icon: "ticket", label: __("Open SAV Tickets"), value: k.open_tickets ?? 0, badge: (k.open_tickets || 0) > 0 ? "info" : null },
    ];

    const strip = page.main.find("#hdb-kpi-strip");
    strip.html(defs.map((d, i) => `
        <div class="hdb-kpi" style="animation-delay:${i * 60}ms">
            <div class="hdb-kpi-top">
                <span class="hdb-kpi-ico">${IC[d.icon]}</span>
                ${d.badge ? `<span class="hdb-kpi-dot hdb-kpi-dot--${d.badge}"></span>` : ""}
            </div>
            <div class="hdb-kpi-val ${d.badge === "error" ? "hdb-val-red" : d.badge === "warn" ? "hdb-val-amber" : ""}">${d.value}</div>
            <div class="hdb-kpi-lbl">${d.label}</div>
        </div>
    `).join(""));
    setTimeout(() => strip.find(".hdb-kpi").each(function (i) {
        setTimeout(() => $(this).addClass("hdb-kpi--in"), i * 60);
    }), 50);
}

// ─── Module summaries ─────────────────────────────────────────────────────────

function renderPricingSummary(page, p) {
    page.main.find("#hdb-pricing-body").html(`
        <div class="hdb-stat-row">
            ${mStat(p.total_sheets ?? "—", __("Total Sheets"))}
            ${mStat(p.benchmark_policies ?? "—", __("Benchmark Policies"))}
            ${mStat(p.customs_policies ?? "—", __("Customs Policies"))}
            ${mStat(p.scenarios ?? "—", __("Scenarios"))}
        </div>
    `);
}

function renderStockSummary(page, s, k) {
    page.main.find("#hdb-stock-body").html(`
        <div class="hdb-stat-row">
            ${mStat(s.warehouses ?? "—", __("Warehouses"))}
            ${mStat((k.total_stock || 0).toLocaleString(), __("Units in Stock"))}
            ${mStat(s.low_stock_items ?? "—", __("Low Stock"), (s.low_stock_items || 0) > 0 ? "warn" : null)}
            ${mStat(k.stockouts ?? "—", __("Stockouts"), (k.stockouts || 0) > 0 ? "error" : null)}
        </div>
    `);
}

function renderSalesSummary(page, s, k) {
    page.main.find("#hdb-sales-body").html(`
        <div class="hdb-stat-row">
            ${mStat(s.orders_month ?? "—", __("Orders / Month"))}
            ${mStat(k.open_quotes ?? "—", __("Open Quotes"))}
            ${mStat(s.invoices_overdue ?? "—", __("Overdue Invoices"), (s.invoices_overdue || 0) > 0 ? "error" : null)}
            ${mStat(s.deliveries_pending ?? "—", __("Pending Deliveries"), (s.deliveries_pending || 0) > 0 ? "warn" : null)}
        </div>
    `);
}

function mStat(val, label, badge) {
    const cls = badge === "error" ? "hdb-val-red" : badge === "warn" ? "hdb-val-amber" : "";
    return `<div class="hdb-mstat">
        <div class="hdb-mstat-val ${cls}">${val}</div>
        <div class="hdb-mstat-lbl">${label}</div>
    </div>`;
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

function renderAlerts(page, alerts) {
    const badge = page.main.find("#hdb-alert-count");
    badge.text(alerts.length ? `${alerts.length} ${__("active")}` : "");
    badge.toggleClass("hdb-badge-live--red", alerts.length > 0);

    const el = page.main.find("#hdb-alerts");
    if (!alerts.length) {
        el.html(`<div class="hdb-empty">${IC.check}<p>${__("No active alerts.")}</p></div>`);
        return;
    }
    el.html(`<div class="hdb-alert-list">${alerts.map(a => `
        <div class="hdb-alert hdb-alert--${a.level}">
            <span class="hdb-alert-ico">${IC[a.icon] || IC.alert}</span>
            <div class="hdb-alert-body">
                <div class="hdb-alert-title">${frappe.utils.escape_html(a.title)}</div>
                <div class="hdb-alert-sub">${frappe.utils.escape_html(a.sub || "")}</div>
            </div>
            ${a.link ? `<a class="hdb-alert-arrow" href="/app/${a.link}">${IC.arrow}</a>` : ""}
        </div>
    `).join("")}</div>`);
}

// ─── Pending actions ──────────────────────────────────────────────────────────

function renderPendingActions(page, actions) {
    const el = page.main.find("#hdb-actions");
    if (!actions.length) {
        el.html(`<div class="hdb-empty">${IC.check}<p>${__("All clear!")}</p></div>`);
        return;
    }
    el.html(`<div class="hdb-action-list">${actions.map(a => `
        <div class="hdb-action-row">
            <div class="hdb-action-info">
                <div class="hdb-action-title">${frappe.utils.escape_html(a.title)}</div>
            </div>
            <div class="hdb-action-right">
                <span class="hdb-action-val">${a.value}</span>
                <a href="/app/${a.link}" class="hdb-action-btn">${__("View")} ${IC.arrow}</a>
            </div>
        </div>
    `).join("")}</div>`);
}

// ─── Recent activity ──────────────────────────────────────────────────────────

function renderActivity(page, items) {
    const el = page.main.find("#hdb-activity");
    if (!items.length) {
        el.html(`<div class="hdb-empty">${IC.clock}<p>${__("No recent activity.")}</p></div>`);
        return;
    }
    el.html(`<div class="hdb-act-list">${items.map(a => `
        <div class="hdb-act-row">
            <span class="hdb-act-ico">${IC[a.icon] || IC.order}</span>
            <div class="hdb-act-info">
                <a class="hdb-act-name" href="${frappe.utils.escape_html(a.link || "#")}">${frappe.utils.escape_html(a.title)}</a>
                <div class="hdb-act-sub">${frappe.utils.escape_html(a.sub || "")}</div>
            </div>
            <div class="hdb-act-right">
                ${a.value ? `<span class="hdb-act-val">${frappe.utils.escape_html(a.value)}</span>` : ""}
                <span class="hdb-act-date">${frappe.datetime.prettyDate(a.date)}</span>
            </div>
        </div>
    `).join("")}</div>`);
}

// ─── Styles ───────────────────────────────────────────────────────────────────

function injectStyles() {
    if (document.getElementById("hdb-styles")) return;
    const s = document.createElement("style");
    s.id = "hdb-styles";
    s.textContent = `
/* ── Root ── */
.hdb-root { background: var(--bg-color, #f4f6f9); }
.hdb-wrap { max-width: 1440px; margin: 0 auto; padding: 20px 28px 60px; display: flex; flex-direction: column; gap: 16px; }

/* ── Hero ── */
.hdb-hero {
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px;
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
    border-radius: 20px; padding: 28px 36px; color: #fff;
    box-shadow: 0 8px 32px rgba(99,102,241,.3);
}
.hdb-greeting { font-size: 22px; font-weight: 800; margin-bottom: 4px; }
.hdb-hero-date { font-size: 13px; color: rgba(255,255,255,.6); }
.hdb-hero-right { display: flex; gap: 28px; }
.hdb-hero-stat { text-align: center; }
.hdb-hero-val { font-size: 26px; font-weight: 800; line-height: 1; }
.hdb-hero-lbl { font-size: 11px; color: rgba(255,255,255,.6); margin-top: 4px; white-space: nowrap; }
.hdb-val-red   { color: #f87171 !important; }
.hdb-val-amber { color: #fbbf24 !important; }

/* ── Gateways ── */
.hdb-gateways {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 10px;
}
@media(max-width:1200px){ .hdb-gateways { grid-template-columns: repeat(4, 1fr); } }
@media(max-width:600px){ .hdb-gateways { grid-template-columns: repeat(2, 1fr); } }

.hdb-gateway {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 14px; padding: 16px 12px;
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    cursor: pointer; text-align: center;
    transition: transform .15s, box-shadow .15s, border-color .15s;
    border-top: 3px solid var(--gw-color, #6366f1);
}
.hdb-gateway:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,.1);
    border-color: var(--gw-color, #6366f1);
}
.hdb-gw-ico {
    width: 40px; height: 40px; border-radius: 12px;
    background: color-mix(in srgb, var(--gw-color, #6366f1) 12%, transparent);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.hdb-gw-ico svg { width: 18px; height: 18px; stroke: var(--gw-color, #6366f1); }
.hdb-gw-label { font-size: 12px; font-weight: 700; color: var(--heading-color, #1a1f2e); }
.hdb-gw-desc  { font-size: 10px; color: var(--text-muted, #94a3b8); line-height: 1.3; }

/* ── KPI strip ── */
.hdb-kpi-strip {
    display: grid; grid-template-columns: repeat(7, 1fr);
    gap: 10px;
}
@media(max-width:1100px){ .hdb-kpi-strip { grid-template-columns: repeat(4, 1fr); } }
@media(max-width:600px) { .hdb-kpi-strip { grid-template-columns: repeat(2, 1fr); } }

.hdb-kpi {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 12px; padding: 14px;
    opacity: 0; transform: translateY(10px);
    transition: opacity .3s, transform .3s;
}
.hdb-kpi--in { opacity: 1; transform: translateY(0); }
.hdb-shimmer-kpi {
    opacity: 1; transform: none; min-height: 90px;
    background: linear-gradient(90deg,#f1f5f9 25%,#e8ecf2 37%,#f1f5f9 63%);
    background-size: 400% 100%; animation: hdb-shimmer 1.4s infinite;
}
.hdb-kpi-top  { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.hdb-kpi-ico  { display: inline-flex; width: 28px; height: 28px; background: #f1f5f9; border-radius: 8px; align-items: center; justify-content: center; }
.hdb-kpi-ico svg { width: 14px; height: 14px; stroke: #6366f1; }
.hdb-kpi-dot  { width: 8px; height: 8px; border-radius: 50%; }
.hdb-kpi-dot--error { background: #ef4444; }
.hdb-kpi-dot--warn  { background: #f59e0b; }
.hdb-kpi-dot--info  { background: #3b82f6; }
.hdb-kpi-val  { font-size: 24px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; margin-bottom: 4px; }
.hdb-kpi-lbl  { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; color: var(--text-muted, #94a3b8); }

/* ── Module grid ── */
.hdb-module-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
}
@media(max-width:900px){ .hdb-module-grid { grid-template-columns: 1fr; } }

.hdb-mcard {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 14px; overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
    display: flex; flex-direction: column;
}
.hdb-mcard--pricing { border-top: 3px solid #6366f1; }
.hdb-mcard--stock   { border-top: 3px solid #10b981; }
.hdb-mcard--sales   { border-top: 3px solid #f59e0b; }

.hdb-mc-hd {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px; border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.hdb-mc-ico {
    width: 38px; height: 38px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.hdb-mc-ico svg { width: 18px; height: 18px; }
.hdb-mc-ico--pricing { background: #eef2ff; } .hdb-mc-ico--pricing svg { stroke: #6366f1; }
.hdb-mc-ico--stock   { background: #d1fae5; } .hdb-mc-ico--stock   svg { stroke: #10b981; }
.hdb-mc-ico--sales   { background: #fef3c7; } .hdb-mc-ico--sales   svg { stroke: #d97706; }

.hdb-mc-title { font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e); }
.hdb-mc-sub   { font-size: 11px; color: var(--text-muted, #94a3b8); }
.hdb-mc-link  { margin-left: auto; display: inline-flex; color: #6366f1; padding: 4px; border-radius: 6px; }
.hdb-mc-link svg { width: 14px; height: 14px; stroke: #6366f1; }
.hdb-mc-link:hover { background: #eef2ff; }

.hdb-mc-body  { flex: 1; }
.hdb-stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; padding: 12px 16px; }
.hdb-mstat    { text-align: center; padding: 8px 0; }
.hdb-mstat-val { font-size: 22px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; margin-bottom: 4px; }
.hdb-mstat-lbl { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; color: var(--text-muted, #94a3b8); }

.hdb-mc-actions {
    display: flex; gap: 8px; padding: 12px 16px;
    border-top: 1px solid var(--border-color, #f1f5f9);
}
.hdb-mc-btn {
    flex: 1; padding: 7px 10px; border-radius: 8px;
    font-size: 11.5px; font-weight: 600; text-align: center;
    cursor: pointer; border: 1px solid; transition: all .15s;
}
.hdb-mc-btn--primary { background: #6366f1; border-color: #6366f1; color: #fff; }
.hdb-mc-btn--primary:hover { background: #4f46e5; }
.hdb-mc-btn--ghost   { background: var(--card-bg, #fff); border-color: var(--border-color, #e8ecf0); color: var(--text-color, #334155); }
.hdb-mc-btn--ghost:hover { border-color: #6366f1; color: #6366f1; }

/* ── Bottom grid ── */
.hdb-bottom-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
}
@media(max-width:900px){ .hdb-bottom-grid { grid-template-columns: 1fr; } }

/* ── Card ── */
.hdb-card {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border-color, #e8ecf0);
    border-radius: 14px; overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
}
.hdb-card-hd {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 18px; border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.hdb-card-title {
    display: flex; align-items: center; gap: 7px;
    font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e);
}
.hdb-card-title svg { width: 14px; height: 14px; stroke: #6366f1; }
.hdb-badge-live {
    font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px;
    background: #f1f5f9; color: var(--text-muted, #64748b);
}
.hdb-badge-live--red { background: #fee2e2; color: #dc2626; }

/* ── Alerts ── */
.hdb-alert-list { padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
.hdb-alert {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 10px 12px; border-radius: 10px; border: 1px solid;
}
.hdb-alert--error { background: #fff5f5; border-color: #fecaca; }
.hdb-alert--warn  { background: #fffbeb; border-color: #fde68a; }
.hdb-alert--info  { background: #eff6ff; border-color: #bfdbfe; }
.hdb-alert-ico { display: inline-flex; flex-shrink: 0; margin-top: 1px; }
.hdb-alert--error .hdb-alert-ico svg { width: 14px; height: 14px; stroke: #dc2626; }
.hdb-alert--warn  .hdb-alert-ico svg { width: 14px; height: 14px; stroke: #d97706; }
.hdb-alert--info  .hdb-alert-ico svg { width: 14px; height: 14px; stroke: #3b82f6; }
.hdb-alert-body { flex: 1; min-width: 0; }
.hdb-alert-title { font-size: 12.5px; font-weight: 700; color: var(--heading-color, #1a1f2e); }
.hdb-alert-sub   { font-size: 11px; color: var(--text-muted, #94a3b8); }
.hdb-alert-arrow { display: inline-flex; color: #6366f1; margin-left: auto; flex-shrink: 0; padding-top: 2px; }
.hdb-alert-arrow svg { width: 13px; height: 13px; stroke: #6366f1; }

/* ── Pending actions ── */
.hdb-action-list { padding: 10px 16px; display: flex; flex-direction: column; gap: 2px; }
.hdb-action-row  { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border-color, #f8fafc); }
.hdb-action-row:last-child { border-bottom: none; }
.hdb-action-title { font-size: 12.5px; font-weight: 600; color: var(--heading-color, #1a1f2e); }
.hdb-action-right { display: flex; align-items: center; gap: 12px; }
.hdb-action-val   { font-size: 18px; font-weight: 800; color: #6366f1; }
.hdb-action-btn   {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; font-weight: 600; color: #6366f1; text-decoration: none;
    transition: gap .15s;
}
.hdb-action-btn:hover { gap: 7px; }
.hdb-action-btn svg { width: 12px; height: 12px; stroke: #6366f1; }

/* ── Recent activity ── */
.hdb-act-list { padding: 8px 0; }
.hdb-act-row  {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 16px; border-bottom: 1px solid var(--border-color, #f8fafc);
}
.hdb-act-row:last-child { border-bottom: none; }
.hdb-act-ico  { display: inline-flex; flex-shrink: 0; }
.hdb-act-ico svg { width: 14px; height: 14px; stroke: var(--text-muted, #94a3b8); }
.hdb-act-info { flex: 1; min-width: 0; }
.hdb-act-name { font-size: 12.5px; font-weight: 700; color: #6366f1; text-decoration: none; display: block; }
.hdb-act-name:hover { text-decoration: underline; }
.hdb-act-sub  { font-size: 11px; color: var(--text-muted, #94a3b8); }
.hdb-act-right { text-align: right; flex-shrink: 0; }
.hdb-act-val  { font-size: 12px; font-weight: 700; color: var(--heading-color, #1a1f2e); display: block; }
.hdb-act-date { font-size: 11px; color: var(--text-muted, #94a3b8); }

/* ── Utilities ── */
.hdb-empty {
    display: flex; flex-direction: column; align-items: center;
    padding: 32px 20px; color: var(--text-muted, #94a3b8); font-size: 13px; gap: 8px;
}
.hdb-empty svg { width: 28px; height: 28px; stroke: #cbd5e1; }
.hdb-shimmer-block {
    background: linear-gradient(90deg, #f1f5f9 25%, #e8ecf2 37%, #f1f5f9 63%);
    background-size: 400% 100%; animation: hdb-shimmer 1.4s infinite;
}
.hdb-shimmer-inline {
    display: inline-block; width: 50px; height: 20px; border-radius: 6px;
    background: rgba(255,255,255,.2); animation: hdb-shimmer 1.4s infinite;
}
@keyframes hdb-shimmer { 0%{background-position:100% 50%} 100%{background-position:0 50%} }

/* Dark mode */
[data-theme-mode="dark"] .hdb-shimmer-block {
    background: linear-gradient(90deg, #22263a 25%, #2a2f48 37%, #22263a 63%);
    background-size: 400% 100%; animation: hdb-shimmer 1.4s infinite;
}
[data-theme-mode="dark"] .hdb-alert--error { background: rgba(239,68,68,.08); border-color: rgba(239,68,68,.25); }
[data-theme-mode="dark"] .hdb-alert--warn  { background: rgba(245,158,11,.08); border-color: rgba(245,158,11,.25); }
[data-theme-mode="dark"] .hdb-alert--info  { background: rgba(59,130,246,.08); border-color: rgba(59,130,246,.25); }
    `;
    document.head.appendChild(s);
}
