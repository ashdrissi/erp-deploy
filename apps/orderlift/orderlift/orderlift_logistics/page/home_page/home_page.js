// ─── Orderlift — Home Page (Control Tower) ────────────────────────────────────
// Placed in orderlift_logistics module — same pattern as stock-dashboard.
// URL: /app/home-page
// ─────────────────────────────────────────────────────────────────────────────

frappe.pages["home-page"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Home"),
        single_column: true,
    });
    page.main.addClass("hp-root");
    injectStyles();
    renderSkeleton(page);
    loadData(page);

    page.add_action_item(__("Refresh"), () => {
        loadData(page);
        frappe.show_alert({ message: __("Refreshed"), indicator: "green" });
    });
};

// ── Icons ─────────────────────────────────────────────────────────────────────
const IC = {
    pricing: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="15" x2="15" y2="5"/><circle cx="7" cy="7" r="2"/><circle cx="13" cy="13" r="2"/></svg>`,
    stock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M17 4L10 2 3 4v8l7 4 7-4V4z"/><line x1="10" y1="2" x2="10" y2="14"/><line x1="3" y1="7" x2="17" y2="7"/></svg>`,
    sales: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8l8-5 8 5v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8z"/><polyline points="8,19 8,12 12,12 12,19"/></svg>`,
    portal: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="8"/><path d="M2 10h16"/><path d="M10 2a13 13 0 0 1 0 16"/><path d="M10 2a13 13 0 0 0 0 16"/></svg>`,
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

// ── Gateway definitions ───────────────────────────────────────────────────────
const GATEWAYS = [
    { icon: "pricing", label: __("Pricing & Sales"), desc: __("Sheets · Policies · Simulator"), url: "pricing-dashboard" },
    { icon: "stock", label: __("Stock & Warehouses"), desc: __("Inventory · Transfers · Alerts"), url: "stock-dashboard" },
    { icon: "logistics", label: __("Container Planning"), desc: __("Forecasts · Planners · Routes"), url: "logistics-dashboard" },
    { icon: "crm", label: __("CRM"), desc: __("Customers · Pipeline · Leads"), url: "crm-dashboard" },
    { icon: "portal", label: __("B2B Portal"), desc: __("Policies · Requests · Catalog"), url: "b2b-portal-dashboard" },
    { icon: "sav", label: __("SAV / Field"), desc: __("Tickets · SLA · Interventions"), url: "sav-dashboard" },
    { icon: "finance", label: __("Finance"), desc: __("Invoices · Payments · P&L"), url: "finance-dashboard" },
    { icon: "hr", label: __("HR"), desc: __("Employees · Leave · Payroll"), url: "hr-dashboard" },
];

// ── Skeleton ──────────────────────────────────────────────────────────────────
function renderSkeleton(page) {
    page.main.html(`
		<div class="hp-wrap">
			<div class="hp-hero">
				<div>
					<div class="hp-greeting" id="hp-greeting">Loading…</div>
					<div class="hp-date" id="hp-date"></div>
				</div>
				<div class="hp-hero-stats" id="hp-hero-stats">
					${[1, 2, 3].map(() => `<div class="hp-hero-stat"><div class="hp-shimmer-i"></div><div class="hp-hero-lbl">…</div></div>`).join("")}
				</div>
			</div>

			<div class="hp-gateways">
				${GATEWAYS.map(g => `
					<div class="hp-gw" data-url="${g.url}">
						<span class="hp-gw-ico">${IC[g.icon]}</span>
						<div class="hp-gw-label">${g.label}</div>
						<div class="hp-gw-desc">${g.desc}</div>
					</div>`).join("")}
			</div>

			<div class="hp-kpi-strip" id="hp-kpis">
				${[1, 2, 3, 4, 5, 6].map(() => `<div class="hp-kpi hp-shimmer-kpi"></div>`).join("")}
			</div>

			<div class="hp-module-row">
				${moduleCard("pricing", __("Pricing Engine"), __("Policies · Sheets · Scenarios"), "pricing-dashboard", [
        ["pricing-dashboard", __("Dashboard"), "primary"],
        ["pricing-simulator", __("Simulator"), "ghost"],
        ["pricing-builder", __("Builder"), "ghost"],
    ], "hp-pricing-body")}
				${moduleCard("stock", __("Stock & Warehouses"), __("Inventory · Transfers · Reorder"), "stock-dashboard", [
        ["stock/stock-entry/new-stock-entry-1", __("New Entry"), "primary"],
        ["stock-dashboard", __("Dashboard"), "ghost"],
        ["stock/warehouse", __("Warehouses"), "ghost"],
    ], "hp-stock-body")}
				${moduleCard("sales", __("Sales & Orders"), __("Quotes · Orders · Deliveries"), "selling/sales-order", [
        ["selling/quotation/new-quotation-1", __("New Quote"), "primary"],
        ["selling/sales-order", __("Orders"), "ghost"],
        ["accounts/sales-invoice", __("Invoices"), "ghost"],
    ], "hp-sales-body")}
			</div>

			<div class="hp-bottom">
				<div class="hp-card">
					<div class="hp-card-hd"><span class="hp-card-ico">${IC.alert}</span>${__("Live Alerts")}<span class="hp-badge" id="hp-alert-badge"></span></div>
					<div id="hp-alerts"><div class="hp-shimmer-block" style="height:150px;margin:14px;border-radius:8px;"></div></div>
				</div>
				<div class="hp-card">
					<div class="hp-card-hd"><span class="hp-card-ico">${IC.clock}</span>${__("Pending Actions")}</div>
					<div id="hp-actions"><div class="hp-shimmer-block" style="height:150px;margin:14px;border-radius:8px;"></div></div>
				</div>
				<div class="hp-card">
					<div class="hp-card-hd"><span class="hp-card-ico">${IC.clock}</span>${__("Recent Activity")}</div>
					<div id="hp-activity"><div class="hp-shimmer-block" style="height:150px;margin:14px;border-radius:8px;"></div></div>
				</div>
			</div>
		</div>
	`);

    page.main.find(".hp-gw").on("click", function () {
        frappe.set_route($(this).data("url").split("/"));
    });
    page.main.find(".hp-mc-btn").on("click", function () {
        frappe.set_route($(this).data("url").split("/"));
    });
}

function moduleCard(ico, title, sub, link, btns, bodyId) {
    return `
		<div class="hp-mc">
			<div class="hp-mc-hd">
				<span class="hp-mc-ico">${IC[ico]}</span>
				<div><div class="hp-mc-title">${title}</div><div class="hp-mc-sub">${sub}</div></div>
				<a class="hp-mc-link" href="/app/${link}">${IC.arrow}</a>
			</div>
			<div id="${bodyId}" class="hp-mc-body"><div class="hp-shimmer-block" style="height:70px;margin:12px;border-radius:8px;"></div></div>
			<div class="hp-mc-btns">${btns.map(([url, label, v]) => `<button class="hp-mc-btn hp-mc-btn--${v}" data-url="${url}">${label}</button>`).join("")}</div>
		</div>`;
}

// ── Load data ─────────────────────────────────────────────────────────────────
async function loadData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.home_page.home_page.get_dashboard_data",
        });
        const d = res.message || {};
        renderHero(page, d.user || {}, d.kpis || {});
        renderKpis(page, d.kpis || {}, d.sales_summary || {});
        renderModuleSummaries(page, d);
        renderAlerts(page, d.alerts || []);
        renderActions(page, d.pending_actions || []);
        renderActivity(page, d.recent_activity || []);
    } catch (e) {
        console.error("Home Page load error:", e);
    }
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderHero(page, user, kpis) {
    const h = new Date().getHours();
    const greet = h < 12 ? __("Good morning") : h < 18 ? __("Good afternoon") : __("Good evening");
    const name = (user.full_name || "").split(" ")[0];
    page.main.find("#hp-greeting").text(`${greet}, ${name} 👋`);
    page.main.find("#hp-date").text(user.today || "");
    const salesK = kpis.sales_month > 0 ? `${(kpis.sales_month / 1000).toFixed(1)}k` : "0";
    const totalAlerts = (kpis.stockouts || 0) + (kpis.open_tickets || 0);
    page.main.find("#hp-hero-stats").html(`
		<div class="hp-hero-stat"><div class="hp-hero-val">${salesK}</div><div class="hp-hero-lbl">${__("Sales / Month")}</div></div>
		<div class="hp-hero-stat"><div class="hp-hero-val">${kpis.open_quotes ?? 0}</div><div class="hp-hero-lbl">${__("Open Quotes")}</div></div>
		<div class="hp-hero-stat"><div class="hp-hero-val ${totalAlerts > 0 ? "hp-red" : ""}">${totalAlerts}</div><div class="hp-hero-lbl">${__("Alerts")}</div></div>
	`);
}

function renderKpis(page, k, sales) {
    const defs = [
        { ico: "pricing", label: __("Pricing Sheets / Mo"), val: k.pricing_sheets_month ?? 0, badge: null },
        { ico: "sales", label: __("Orders / Month"), val: sales.orders_month ?? 0, badge: null },
        { ico: "invoice", label: __("Open Quotations"), val: k.open_quotes ?? 0, badge: null },
        { ico: "stock", label: __("Stock Units"), val: (k.total_stock || 0).toLocaleString(), badge: null },
        { ico: "alert", label: __("Stockouts"), val: k.stockouts ?? 0, badge: (k.stockouts || 0) > 0 ? "error" : null },
        { ico: "transfer", label: __("Pending Transfers"), val: k.pending_transfers ?? 0, badge: (k.pending_transfers || 0) > 0 ? "warn" : null },
        { ico: "ticket", label: __("Open SAV Tickets"), val: k.open_tickets ?? 0, badge: (k.open_tickets || 0) > 0 ? "info" : null },
    ];
    page.main.find("#hp-kpis").html(defs.map((d, i) => `
		<div class="hp-kpi hp-kpi--in" style="animation-delay:${i * 50}ms">
			<div class="hp-kpi-top">
				<span class="hp-kpi-ico">${IC[d.ico]}</span>
				${d.badge ? `<span class="hp-dot hp-dot--${d.badge}"></span>` : ""}
			</div>
			<div class="hp-kpi-val ${d.badge === "error" ? "hp-red" : d.badge === "warn" ? "hp-amber" : ""}">${d.val}</div>
			<div class="hp-kpi-lbl">${d.label}</div>
		</div>
	`).join(""));
}

function renderModuleSummaries(page, d) {
    const p = d.pricing_summary || {};
    const recentPricing = d.pricing_recent || [];
    const s = d.stock_summary || {};
    const sl = d.sales_summary || {};
    const k = d.kpis || {};

    page.main.find("#hp-pricing-body").html(renderPricingSummary(p, recentPricing));
    page.main.find("#hp-stock-body").html(statRow([
        [s.warehouses ?? "—", __("Warehouses")],
        [(k.total_stock || 0).toLocaleString(), __("Units")],
        [s.low_stock_items ?? "—", __("Low Stock"), (s.low_stock_items || 0) > 0 ? "warn" : null],
        [k.stockouts ?? "—", __("Stockouts"), (k.stockouts || 0) > 0 ? "error" : null],
    ]));
    page.main.find("#hp-sales-body").html(statRow([
        [sl.orders_month ?? "—", __("Orders")],
        [k.open_quotes ?? "—", __("Quotes")],
        [sl.invoices_overdue ?? "—", __("Overdue"), (sl.invoices_overdue || 0) > 0 ? "error" : null],
        [sl.deliveries_pending ?? "—", __("Deliveries"), (sl.deliveries_pending || 0) > 0 ? "warn" : null],
    ]));
}

function renderPricingSummary(pricing, recentItems) {
    const stats = statRow([
        [pricing.total_sheets ?? "—", __("Sheets")],
        [pricing.builders ?? "—", __("Builders")],
        [pricing.benchmark_policies ?? "—", __("Benchmark")],
        [pricing.customs_policies ?? "—", __("Customs")],
        [pricing.scenarios ?? "—", __("Scenarios")],
    ]);

    if (!recentItems.length) {
        return `${stats}<div class="hp-inline-empty">${__("No recent pricing documents yet.")}</div>`;
    }

    return `${stats}
        <div class="hp-mini-list">
            ${recentItems.map((item) => `
                <a class="hp-mini-row" href="${frappe.utils.escape_html(item.link || "#")}">
                    <span class="hp-mini-label">${frappe.utils.escape_html(item.label || "")}</span>
                    <span class="hp-mini-meta">${frappe.utils.escape_html(item.meta || "")}</span>
                </a>
            `).join("")}
        </div>`;
}

function statRow(items) {
    return `<div class="hp-stats">${items.map(([v, l, b]) => `
		<div class="hp-stat">
			<div class="hp-stat-val ${b === "error" ? "hp-red" : b === "warn" ? "hp-amber" : ""}">${v}</div>
			<div class="hp-stat-lbl">${l}</div>
		</div>`).join("")}</div>`;
}

function renderAlerts(page, alerts) {
    const badge = page.main.find("#hp-alert-badge");
    badge.text(alerts.length ? `${alerts.length}` : "").toggleClass("hp-badge--red", alerts.length > 0);
    if (!alerts.length) {
        page.main.find("#hp-alerts").html(`<div class="hp-empty">${IC.check}<p>${__("No active alerts.")}</p></div>`);
        return;
    }
    page.main.find("#hp-alerts").html(`<div class="hp-alert-list">${alerts.map(a => `
		<div class="hp-alert hp-alert--${a.level}">
			<span class="hp-alert-ico">${IC[a.icon] || IC.alert}</span>
			<div class="hp-alert-body">
				<div class="hp-alert-title">${frappe.utils.escape_html(a.title)}</div>
				<div class="hp-alert-sub">${frappe.utils.escape_html(a.sub || "")}</div>
			</div>
			${a.link ? `<a class="hp-alert-link" href="/app/${a.link}">${IC.arrow}</a>` : ""}
		</div>`).join("")}</div>`);
}

function renderActions(page, actions) {
    if (!actions.length) {
        page.main.find("#hp-actions").html(`<div class="hp-empty">${IC.check}<p>${__("All clear!")}</p></div>`);
        return;
    }
    page.main.find("#hp-actions").html(`<div class="hp-action-list">${actions.map(a => `
		<div class="hp-action-row">
			<div class="hp-action-title">${frappe.utils.escape_html(a.title)}</div>
			<div class="hp-action-right">
				<span class="hp-action-val">${a.value}</span>
				<a class="hp-action-btn" href="/app/${a.link}">${__("View")} ${IC.arrow}</a>
			</div>
		</div>`).join("")}</div>`);
}

function renderActivity(page, items) {
    if (!items.length) {
        page.main.find("#hp-activity").html(`<div class="hp-empty">${IC.clock}<p>${__("No recent activity.")}</p></div>`);
        return;
    }
    page.main.find("#hp-activity").html(`<div class="hp-act-list">${items.map(a => `
		<div class="hp-act-row">
			<span class="hp-act-ico">${IC[a.icon] || IC.order}</span>
			<div class="hp-act-info">
				<a class="hp-act-name" href="${frappe.utils.escape_html(a.link || "#")}">${frappe.utils.escape_html(a.title)}</a>
				<div class="hp-act-sub">${frappe.utils.escape_html(a.sub || "")}</div>
			</div>
			<div class="hp-act-right">
				${a.value ? `<span class="hp-act-val">${frappe.utils.escape_html(a.value)}</span>` : ""}
				<span class="hp-act-date">${frappe.datetime.prettyDate(a.date)}</span>
			</div>
		</div>`).join("")}</div>`);
}

// ── Styles ────────────────────────────────────────────────────────────────────
function injectStyles() {
    if (document.getElementById("hp-styles")) return;
    const s = document.createElement("style");
    s.id = "hp-styles";
    s.textContent = `
.hp-root { background: var(--bg-color, #f4f6f9); }
.hp-wrap { max-width: 1440px; margin: 0 auto; padding: 28px 32px 72px; display: flex; flex-direction: column; gap: 20px; }

/* Hero — light card like pricing-dashboard */
.hp-hero {
	display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 24px;
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #d4f0f5);
	border-radius: 16px;
	padding: 28px 36px;
	box-shadow: 0 1px 6px rgba(0,0,0,0.04);
	position: relative; overflow: hidden;
}
.hp-hero::before {
	content: ""; position: absolute; inset: 0;
	background: linear-gradient(135deg, rgba(2,115,132,0.04) 0%, transparent 60%);
	pointer-events: none;
}
.hp-greeting { font-size: 26px; font-weight: 700; color: var(--heading-color, #1a1f2e); line-height: 1.2; }
.hp-date     { font-size: 13px; color: var(--text-muted, #8c95a6); margin-top: 4px; }
.hp-hero-stats { display: flex; align-items: center; gap: 0; }
.hp-hero-stat  { text-align: center; padding: 0 36px; }
.hp-hero-val   { font-size: 30px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; }
.hp-hero-lbl   { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: var(--text-muted, #8c95a6); margin-top: 5px; white-space: nowrap; }
.hp-red        { color: #e11d48 !important; }
.hp-amber      { color: #d97706 !important; }
.hp-shimmer-i  { display: inline-block; width: 60px; height: 24px; border-radius: 6px; background: #e8f7f8; animation: hp-shimmer 1.4s infinite; }
.hp-hero-divider { width: 1px; height: 40px; background: var(--border-color, #d4f0f5); }

/* Gateways — unified, no per-card colors */
.hp-gateways {
	display: grid; grid-template-columns: repeat(8,1fr); gap: 10px;
}
@media(max-width:1200px){ .hp-gateways { grid-template-columns: repeat(4,1fr); } }
@media(max-width:600px) { .hp-gateways { grid-template-columns: repeat(2,1fr); } }
.hp-gw {
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #d4f0f5);
	border-radius: 12px;
	padding: 16px 12px;
	cursor: pointer;
	display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center;
	transition: border-color .15s, box-shadow .15s, transform .15s;
}
.hp-gw:hover {
	border-color: #027384;
	background: #e0f4f6;
	box-shadow: 0 4px 16px rgba(2,115,132,0.10);
	transform: translateY(-2px);
}
.hp-gw-ico  {
	width: 28px; height: 28px; border-radius: 7px;
	background: #e8f7f8;
	display: flex; align-items: center; justify-content: center;
	transition: background .15s;
}
.hp-gw:hover .hp-gw-ico { background: #e0f4f6; }
.hp-gw-ico svg { width: 18px; height: 18px; stroke: #4a8a8f; transition: stroke .15s; }
.hp-gw:hover .hp-gw-ico svg { stroke: #027384; }
.hp-gw-label { font-size: 11.5px; font-weight: 700; color: var(--heading-color, #1a1f2e); }
.hp-gw-desc  { font-size: 10px; color: var(--text-muted, #94a3b8); line-height: 1.3; }

/* KPI strip */
.hp-kpi-strip { display: grid; grid-template-columns: repeat(6,1fr); gap: 12px; }
@media(max-width:900px) { .hp-kpi-strip { grid-template-columns: repeat(3,1fr); } }
@media(max-width:600px) { .hp-kpi-strip { grid-template-columns: repeat(2,1fr); } }
.hp-kpi {
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #d4f0f5);
	border-radius: 12px;
	padding: 18px 18px 16px;
	opacity: 0; transform: translateY(10px);
	transition: opacity .3s, transform .3s, box-shadow .15s;
}
.hp-kpi--in { opacity: 1 !important; transform: none !important; }
.hp-kpi:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.hp-shimmer-kpi {
	opacity: 1 !important; transform: none !important; min-height: 110px;
	background: linear-gradient(90deg,#e8f7f8 25%,#e8ecf2 37%,#e8f7f8 63%);
	background-size: 400% 100%; animation: hp-shimmer 1.4s infinite;
}
.hp-kpi-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.hp-kpi-ico { display: inline-flex; width: 32px; height: 32px; background: #e8f7f8; border-radius: 8px; align-items: center; justify-content: center; }
.hp-kpi-ico svg { width: 16px; height: 16px; stroke: #027384; }
.hp-dot { width: 7px; height: 7px; border-radius: 50%; }
.hp-dot--error { background: #ef4444; }
.hp-dot--warn  { background: #f59e0b; }
.hp-dot--info  { background: #3b82f6; }
.hp-kpi-val { font-size: 28px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; margin-bottom: 4px; }
.hp-kpi-lbl { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted, #4a8a8f); margin-bottom: 3px; }

/* Module row */
.hp-module-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; }
@media(max-width:900px) { .hp-module-row { grid-template-columns: 1fr; } }
.hp-mc {
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #d4f0f5);
	border-radius: 14px;
	overflow: hidden;
	display: flex; flex-direction: column;
	box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.hp-mc-hd {
	display: flex; align-items: center; gap: 10px; padding: 14px 20px;
	border-bottom: 1px solid var(--border-color, #e8f7f8);
}
.hp-mc-ico {
	width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
	background: #e8f7f8;
	display: flex; align-items: center; justify-content: center;
}
.hp-mc-ico svg { width: 16px; height: 16px; stroke: #027384; }
.hp-mc-title { font-size: 12.5px; font-weight: 700; color: var(--heading-color, #1a1f2e); }
.hp-mc-sub   { font-size: 10.5px; color: var(--text-muted, #94a3b8); }
.hp-mc-link  { margin-left: auto; display: inline-flex; padding: 4px; border-radius: 6px; }
.hp-mc-link:hover { background: #e8f7f8; }
.hp-mc-link svg { width: 13px; height: 13px; stroke: #027384; }
.hp-mc-body  { flex: 1; }
.hp-stats    { display: grid; grid-template-columns: repeat(5,1fr); padding: 12px 14px; gap: 0; }
@media(max-width:1200px) { .hp-stats { grid-template-columns: repeat(3,1fr); } }
@media(max-width:600px) { .hp-stats { grid-template-columns: repeat(2,1fr); } }
.hp-stat     { text-align: center; padding: 8px 0; }
.hp-stat-val { font-size: 20px; font-weight: 800; color: var(--heading-color, #1a1f2e); line-height: 1; margin-bottom: 3px; }
.hp-stat-lbl { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; color: var(--text-muted, #94a3b8); }
.hp-inline-empty { padding: 0 14px 14px; font-size: 11px; color: var(--text-muted, #94a3b8); }
.hp-mini-list { padding: 0 12px 12px; display: grid; gap: 8px; }
.hp-mini-row {
	display: flex; justify-content: space-between; align-items: center; gap: 12px;
	padding: 10px 12px; border-radius: 10px; background: #f0fafc; border: 1px solid #eef2f7;
	text-decoration: none; transition: border-color .15s, transform .15s, background .15s;
}
.hp-mini-row:hover { border-color: #027384; background: #fff; transform: translateY(-1px); }
.hp-mini-label { font-size: 11.5px; font-weight: 700; color: var(--heading-color, #1a1f2e); }
.hp-mini-meta { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted, #94a3b8); white-space: nowrap; }
.hp-mc-btns { display: grid; grid-template-columns: repeat(3,1fr); padding: 0 12px 12px; gap: 8px; }
.hp-mc-btn {
	flex: 1; padding: 7px 8px; border-radius: 7px; font-size: 11px; font-weight: 600;
	cursor: pointer; border: 1px solid; transition: all .15s; text-align: center;
}
.hp-mc-btn--primary { background: #027384; border-color: #027384; color: #fff; }
.hp-mc-btn--primary:hover { filter: brightness(1.1); }
.hp-mc-btn--ghost   { background: var(--card-bg, #fff); border-color: var(--border-color, #d4f0f5); color: var(--text-color, #334155); }
.hp-mc-btn--ghost:hover { border-color: #027384;
	background: #e0f4f6; color: #027384; }

/* Bottom */
.hp-bottom { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; }
@media(max-width:900px) { .hp-bottom { grid-template-columns: 1fr; } }
.hp-card {
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #d4f0f5);
	border-radius: 14px;
	overflow: hidden;
	box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.hp-card-hd {
	display: flex; align-items: center; gap: 7px; padding: 13px 20px;
	border-bottom: 1px solid var(--border-color, #e8f7f8);
	font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e);
}
.hp-card-ico svg { width: 14px; height: 14px; stroke: #027384; }
.hp-badge {
	margin-left: auto; font-size: 11px; font-weight: 700; padding: 2px 8px;
	border-radius: 999px; background: #e8f7f8; color: #4a8a8f;
}
.hp-badge--red { background: #fee2e2; color: #dc2626; }

/* Alerts */
.hp-alert-list { padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.hp-alert {
	display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px;
	border-radius: 10px; border: 1px solid;
}
.hp-alert--error { background: #fff1f2; border-color: #fecdd3; }
.hp-alert--warn  { background: #fffbeb; border-color: #fde68a; }
.hp-alert--info  { background: #eff6ff; border-color: #bfdbfe; }
.hp-alert-ico { flex-shrink: 0; display: inline-flex; margin-top: 1px; }
.hp-alert--error .hp-alert-ico svg { width: 16px; height: 16px; stroke: #dc2626; }
.hp-alert--warn  .hp-alert-ico svg { width: 16px; height: 16px; stroke: #d97706; }
.hp-alert--info  .hp-alert-ico svg { width: 16px; height: 16px; stroke: #3b82f6; }
.hp-alert-body { flex: 1; min-width: 0; }
.hp-alert-title { font-size: 13px; font-weight: 700; color: var(--heading-color, #1a1f2e); margin-bottom: 3px; }
.hp-alert-sub   { font-size: 12px; color: var(--text-muted, #4a8a8f); line-height: 1.5; }
.hp-alert-link  { display: inline-flex; margin-left: auto; }
.hp-alert-link svg { width: 13px; height: 13px; stroke: #027384; }

/* Actions */
.hp-action-list { padding: 8px 20px; }
.hp-action-row  { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border-color, #f0fafc); }
.hp-action-row:last-child { border: none; }
.hp-action-title { font-size: 12px; font-weight: 600; color: var(--heading-color, #1a1f2e); }
.hp-action-right { display: flex; align-items: center; gap: 12px; }
.hp-action-val   { font-size: 18px; font-weight: 800; color: #027384; }
.hp-action-btn   { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; color: #027384; text-decoration: none; }
.hp-action-btn svg { width: 12px; height: 12px; stroke: #027384; }

/* Activity */
.hp-act-list { padding: 4px 0; }
.hp-act-row  { display: flex; align-items: center; gap: 10px; padding: 9px 20px; border-bottom: 1px solid var(--border-color, #f0fafc); }
.hp-act-row:last-child { border: none; }
.hp-act-ico  { display: inline-flex; flex-shrink: 0; }
.hp-act-ico svg { width: 14px; height: 14px; stroke: var(--text-muted, #94a3b8); }
.hp-act-info { flex: 1; min-width: 0; }
.hp-act-name { font-size: 12px; font-weight: 700; color: #027384; text-decoration: none; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hp-act-sub  { font-size: 11px; color: var(--text-muted, #94a3b8); }
.hp-act-right { text-align: right; flex-shrink: 0; }
.hp-act-val  { font-size: 11.5px; font-weight: 700; color: var(--heading-color, #1a1f2e); display: block; }
.hp-act-date { font-size: 10.5px; color: var(--text-muted, #94a3b8); }

/* Shared */
.hp-empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 28px 16px; color: var(--text-muted, #94a3b8); font-size: 12.5px; }
.hp-empty svg { width: 26px; height: 26px; stroke: #cbd5e1; }
.hp-shimmer-block {
	background: linear-gradient(90deg,#e8f7f8 25%,#e8ecf2 37%,#e8f7f8 63%);
	background-size: 400% 100%; animation: hp-shimmer 1.4s infinite;
}
@keyframes hp-shimmer { 0%{background-position:100% 50%} 100%{background-position:0 50%} }

[data-theme-mode="dark"] .hp-shimmer-block,
[data-theme-mode="dark"] .hp-shimmer-kpi {
	background: linear-gradient(90deg,#22263a 25%,#2a2f48 37%,#22263a 63%);
	background-size: 400% 100%; animation: hp-shimmer 1.4s infinite;
}
[data-theme-mode="dark"] .hp-alert--error { background: rgba(239,68,68,.08); border-color: rgba(239,68,68,.25); }
[data-theme-mode="dark"] .hp-alert--warn  { background: rgba(245,158,11,.08); border-color: rgba(245,158,11,.25); }
[data-theme-mode="dark"] .hp-alert--info  { background: rgba(59,130,246,.08); border-color: rgba(59,130,246,.25); }
    `;
    document.head.appendChild(s);
}
