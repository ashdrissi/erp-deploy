frappe.pages["logistics-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Logistics"),
        single_column: true,
    });

    page.main.addClass("ldb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    purchase: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="17" y2="6"/><polyline points="9,11 10,13 13,10"/></svg>`,
    supplier: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M7 17V9h6v8"/><path d="M7 6h.01M10 6h.01M13 6h.01"/></svg>`,
    receipt: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><polyline points="7,10 9,12 13,8"/></svg>`,
    request: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="12" height="16" rx="2"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/><line x1="7" y1="13" x2="11" y2="13"/></svg>`,
    transfer: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="7" x2="16" y2="7"/><polyline points="11,3 16,7 11,11"/><line x1="16" y1="13" x2="4" y2="13"/><polyline points="9,9 4,13 9,17"/></svg>`,
    delivery: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="7" width="14" height="9" rx="1"/><path d="M15 10h2l2 3v3h-4V10z"/><circle cx="5" cy="18" r="1.5" fill="currentColor" stroke="none"/><circle cx="15" cy="18" r="1.5" fill="currentColor" stroke="none"/></svg>`,
    cockpit: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="16" height="12" rx="2"/><path d="M6 17h8"/><path d="M6 9h8"/><path d="M10 9v6"/></svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r="0.6" fill="currentColor"/></svg>`,
    plus: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/></svg>`,
    clock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="8"/><polyline points="10,5 10,10 13,13"/></svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="10" x2="16" y2="10"/><polyline points="11,5 16,10 11,15"/></svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,10 8,14 16,6"/></svg>`,
};

function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const today = frappe.datetime.str_to_user(frappe.datetime.now_date());

    page.main.html(`
        <div class="ldb-wrapper">
            <div class="ldb-hero">
                <div class="ldb-hero-left">
                    <div class="ldb-hero-eyebrow">${__("Orderlift · Logistics Hub")}</div>
                    <div class="ldb-hero-greeting">${greeting}</div>
                    <div class="ldb-hero-sub">${today}</div>
                </div>
                <div class="ldb-hero-right">
                    <div class="ldb-hero-stat" id="ldb-hero-po"><div class="ldb-hero-stat-val">—</div><div class="ldb-hero-stat-label">${__("PO To Receive")}</div></div>
                    <div class="ldb-hero-divider"></div>
                    <div class="ldb-hero-stat" id="ldb-hero-mr"><div class="ldb-hero-stat-val">—</div><div class="ldb-hero-stat-label">${__("Material Requests")}</div></div>
                    <div class="ldb-hero-divider"></div>
                    <div class="ldb-hero-stat" id="ldb-hero-alerts"><div class="ldb-hero-stat-val">—</div><div class="ldb-hero-stat-label">${__("Alerts")}</div></div>
                </div>
            </div>

            <div class="ldb-shortcuts-grid">
                ${shortcut("plus", __("New Purchase Order"), "/app/purchase-order/new-purchase-order-1", "primary")}
                ${shortcut("request", __("Material Requests"), "/app/material-request", "default")}
                ${shortcut("receipt", __("Purchase Receipts"), "/app/purchase-receipt", "default")}
                ${shortcut("delivery", __("Delivery Notes"), "/app/delivery-note", "default")}
                ${shortcut("transfer", __("Stock Transfers"), "/app/stock-entry?stock_entry_type=Material+Transfer", "default")}
                ${shortcut("supplier", __("Suppliers"), "/app/supplier", "default")}
                ${shortcut("cockpit", __("Logistics Cockpit"), "/app/logistics-hub-cockpit", "default")}
                ${shortcut("cockpit", __("Load Plans"), "/app/container-load-plan", "default")}
            </div>

            <div class="ldb-kpi-grid" id="ldb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="ldb-kpi ldb-kpi--shimmer"></div>`).join("")}
            </div>

            <div class="ldb-lower">
                <div class="ldb-card">
                    <div class="ldb-card-header">
                        <div class="ldb-card-title"><span class="ldb-card-icon">${ICONS.clock}</span>${__("Recent Logistics Documents")}</div>
                        <a href="/app/purchase-order" class="ldb-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="ldb-recent-table" class="ldb-table-wrap"><div class="ldb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="ldb-card">
                    <div class="ldb-card-header">
                        <div class="ldb-card-title"><span class="ldb-card-icon">${ICONS.alert}</span>${__("Logistics Alerts")}</div>
                    </div>
                    <div id="ldb-alerts" class="ldb-alerts-wrap"><div class="ldb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>
        </div>
    `);

    page.main.find(".ldb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (!url) return;
        frappe.set_route(url.replace(/^\/app\//, "").split("/"));
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.logistics_dashboard.logistics_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {});
        renderKpis(page, data.kpis || {});
        renderRecentDocs(page, data.recent_docs || []);
        renderAlerts(page, data.alerts || []);
    } catch (e) {
        renderHeroStats(page, {});
        renderKpis(page, {});
        renderRecentDocs(page, []);
        renderAlerts(page, []);
        console.warn("Logistics Dashboard: failed to load data", e);
    }
}

function renderHeroStats(page, kpis) {
    page.main.find("#ldb-hero-po .ldb-hero-stat-val").text(kpis.purchase_orders_to_receive ?? "—");
    page.main.find("#ldb-hero-mr .ldb-hero-stat-val").text(kpis.submitted_material_requests ?? "—");
    const alertCount = [
        kpis.purchase_orders_to_receive || 0,
        kpis.draft_delivery_notes || 0,
        kpis.draft_transfers || 0,
    ].filter(Boolean).length;
    const alertEl = page.main.find("#ldb-hero-alerts .ldb-hero-stat-val");
    alertEl.text(alertCount);
    if (alertCount > 0) alertEl.addClass("ldb-stat-warn");
}

function shortcut(iconKey, label, url, variant) {
    return `<div class="ldb-shortcut ldb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}"><span class="ldb-shortcut-icon">${ICONS[iconKey] || ""}</span><span class="ldb-shortcut-label">${frappe.utils.escape_html(label)}</span></div>`;
}

function renderKpis(page, kpis) {
    const defs = [
        { icon: "supplier", label: __("Active Suppliers"), value: kpis.active_suppliers ?? "—", sub: __("vendor master records") },
        { icon: "request", label: __("Submitted Material Requests"), value: kpis.submitted_material_requests ?? "—", sub: __("awaiting procurement follow-up") },
        { icon: "purchase", label: __("PO To Receive"), value: kpis.purchase_orders_to_receive ?? "—", sub: __("approved supplier orders") },
        { icon: "receipt", label: __("Receipts This Month"), value: kpis.purchase_receipts_month ?? "—", sub: __("posted purchase receipts") },
        { icon: "delivery", label: __("Draft Delivery Notes"), value: kpis.draft_delivery_notes ?? "—", sub: __("outbound docs awaiting validation"), highlight: (kpis.draft_delivery_notes || 0) > 0 ? "warn" : null },
        { icon: "transfer", label: __("Draft Transfers"), value: kpis.draft_transfers ?? "—", sub: __("warehouse moves pending") , highlight: (kpis.draft_transfers || 0) > 0 ? "warn" : null },
    ];

    page.main.find("#ldb-kpi-grid").html(defs.map((d) => `
        <div class="ldb-kpi">
            <div class="ldb-kpi-top"><span class="ldb-kpi-icon">${ICONS[d.icon]}</span></div>
            <div class="ldb-kpi-val ${d.highlight === "warn" ? "ldb-stat-warn" : ""}">${d.value}</div>
            <div class="ldb-kpi-lbl">${d.label}</div>
            <div class="ldb-kpi-sub">${d.sub}</div>
        </div>
    `).join(""));
}

function renderRecentDocs(page, rows) {
    if (!rows.length) {
        page.main.find("#ldb-recent-table").html(`<div class="ldb-empty">${__("No recent logistics documents yet.")}</div>`);
        return;
    }

    page.main.find("#ldb-recent-table").html(`
        <div class="ldb-mini-list">
            ${rows.map((row) => `
                <a class="ldb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="ldb-mini-label">${frappe.utils.escape_html(row.label || "")}</span>
                    <span class="ldb-mini-meta">${frappe.utils.escape_html(row.meta || "")}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function renderAlerts(page, alerts) {
    if (!alerts.length) {
        page.main.find("#ldb-alerts").html(`<div class="ldb-empty">${ICONS.check}<p>${__("No active logistics alerts.")}</p></div>`);
        return;
    }

    page.main.find("#ldb-alerts").html(`
        <div class="ldb-alert-list">
            ${alerts.map((a) => `
                <a class="ldb-alert ldb-alert--${a.level || "info"}" href="${frappe.utils.escape_html(a.link || "#")}">
                    <div class="ldb-alert-title">${frappe.utils.escape_html(a.title || "")}</div>
                    <div class="ldb-alert-message">${frappe.utils.escape_html(a.message || "")}</div>
                </a>
            `).join("")}
        </div>
    `);
}

function injectDashboardStyles() {
    if (document.getElementById("ldb-dashboard-styles")) return;

    const style = document.createElement("style");
    style.id = "ldb-dashboard-styles";
    style.textContent = `
        .ldb-root { background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); min-height: calc(100vh - 88px); }
        .ldb-wrapper { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .ldb-hero, .ldb-card, .ldb-shortcut, .ldb-kpi { background: rgba(255,255,255,0.86); border: 1px solid rgba(148,163,184,0.16); box-shadow: 0 18px 50px rgba(15,23,42,0.08); }
        .ldb-hero { border-radius: 24px; padding: 28px; display: flex; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
        .ldb-hero-eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
        .ldb-hero-greeting { font-size: 32px; font-weight: 700; color: #0f172a; }
        .ldb-hero-sub { color: #475569; margin-top: 6px; }
        .ldb-hero-right { display: flex; align-items: center; gap: 18px; }
        .ldb-hero-divider { width: 1px; align-self: stretch; background: rgba(148,163,184,0.2); }
        .ldb-hero-stat-val { font-size: 28px; font-weight: 700; color: #111827; text-align: center; }
        .ldb-hero-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; }
        .ldb-stat-warn { color: #c2410c; }
        .ldb-shortcuts-grid, .ldb-kpi-grid { display: grid; gap: 14px; margin-bottom: 20px; }
        .ldb-shortcuts-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .ldb-kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .ldb-shortcut, .ldb-kpi { border-radius: 18px; padding: 18px; cursor: pointer; }
        .ldb-shortcut { display: flex; align-items: center; gap: 12px; transition: transform .16s ease, box-shadow .16s ease; }
        .ldb-shortcut:hover { transform: translateY(-2px); box-shadow: 0 24px 60px rgba(15,23,42,0.12); }
        .ldb-shortcut--primary { background: linear-gradient(135deg, #0f172a, #1e293b); color: #fff; }
        .ldb-shortcut-icon svg, .ldb-kpi-icon svg, .ldb-card-icon svg { width: 20px; height: 20px; }
        .ldb-shortcut-label { font-weight: 600; }
        .ldb-kpi-top { margin-bottom: 12px; color: #475569; }
        .ldb-kpi-val { font-size: 28px; font-weight: 700; color: #0f172a; }
        .ldb-kpi-lbl { margin-top: 4px; font-weight: 600; color: #1e293b; }
        .ldb-kpi-sub { margin-top: 6px; font-size: 12px; color: #64748b; }
        .ldb-lower { display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }
        .ldb-card { border-radius: 22px; overflow: hidden; }
        .ldb-card-header { padding: 18px 20px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .ldb-card-title { display: flex; align-items: center; gap: 10px; font-weight: 700; color: #0f172a; }
        .ldb-view-all { color: #4f46e5; font-weight: 600; text-decoration: none; }
        .ldb-mini-list, .ldb-alert-list { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 10px; }
        .ldb-mini-row, .ldb-alert { display: block; border-radius: 14px; padding: 14px; text-decoration: none; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .ldb-mini-label, .ldb-alert-title { display: block; font-weight: 600; color: #111827; }
        .ldb-mini-meta, .ldb-alert-message { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
        .ldb-alert--warn { border-left: 4px solid #f59e0b; }
        .ldb-alert--info { border-left: 4px solid #3b82f6; }
        .ldb-empty { padding: 28px 18px; text-align: center; color: #64748b; }
        .ldb-empty svg { width: 18px; height: 18px; display: inline-block; margin-bottom: 10px; }
        .ldb-kpi--shimmer, .ldb-shimmer-block { position: relative; overflow: hidden; background: rgba(255,255,255,0.7); }
        .ldb-kpi--shimmer::after, .ldb-shimmer-block::after { content: ""; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent); animation: ldbShimmer 1.5s infinite; }
        @keyframes ldbShimmer { 100% { transform: translateX(100%); } }
        @media (max-width: 980px) { .ldb-hero, .ldb-hero-right { flex-direction: column; align-items: flex-start; } .ldb-hero-right { width: 100%; } .ldb-hero-divider { display: none; } .ldb-lower { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
