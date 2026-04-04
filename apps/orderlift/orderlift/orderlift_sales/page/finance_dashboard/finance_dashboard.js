frappe.pages["finance-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Finance"),
        single_column: true,
    });

    page.main.addClass("fdb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    receivable: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/><path d="M6 10h8"/><path d="M10 7v6"/></svg>`,
    payable: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/><path d="M6 10h8"/></svg>`,
    payment: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="14" height="12" rx="2"/><path d="M3 8h14"/><circle cx="7" cy="12" r="1" fill="currentColor" stroke="none"/></svg>`,
    ledger: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3h10a2 2 0 0 1 2 2v12H6a2 2 0 0 0-2 2V3z"/><path d="M6 7h8M6 10h8M6 13h5"/></svg>`,
    invoice: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/></svg>`,
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
        <div class="fdb-wrapper">
            <div class="fdb-hero">
                <div class="fdb-hero-left">
                    <div class="fdb-hero-eyebrow">${__("Orderlift · Finance Hub")}</div>
                    <div class="fdb-hero-greeting">${greeting}</div>
                    <div class="fdb-hero-sub">${today}</div>
                </div>
                <div class="fdb-hero-right">
                    <div class="fdb-hero-stat" id="fdb-hero-receivables"><div class="fdb-hero-stat-val">—</div><div class="fdb-hero-stat-label">${__("Overdue Receivables")}</div></div>
                    <div class="fdb-hero-divider"></div>
                    <div class="fdb-hero-stat" id="fdb-hero-payables"><div class="fdb-hero-stat-val">—</div><div class="fdb-hero-stat-label">${__("Overdue Payables")}</div></div>
                    <div class="fdb-hero-divider"></div>
                    <div class="fdb-hero-stat" id="fdb-hero-alerts"><div class="fdb-hero-stat-val">—</div><div class="fdb-hero-stat-label">${__("Alerts")}</div></div>
                </div>
            </div>

            <div class="fdb-shortcuts-grid">
                ${shortcutUrl("plus", __("New Sales Invoice"), "/desk/accounts/sales-invoice/new-sales-invoice-1?sidebar=Main+Dashboard", "primary")}
                ${shortcutUrl("payment", __("Payments"), "/desk/accounts/payment-entry?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("invoice", __("Purchase Invoices"), "/desk/accounts/purchase-invoice?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("ledger", __("Journal Entries"), "/desk/accounts/journal-entry?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("ledger", __("General Ledger"), "/desk/query-report/General%20Ledger?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("receivable", __("Sales Invoices"), "/desk/accounts/sales-invoice?sidebar=Main+Dashboard", "default")}
            </div>

            <div class="fdb-kpi-grid" id="fdb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="fdb-kpi fdb-kpi--shimmer"></div>`).join("")}
            </div>

            <div class="fdb-lower">
                <div class="fdb-card">
                    <div class="fdb-card-header">
                        <div class="fdb-card-title"><span class="fdb-card-icon">${ICONS.invoice}</span>${__("Recent Finance Documents")}</div>
                        <a href="/app/sales-invoice" class="fdb-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="fdb-recent-table" class="fdb-table-wrap"><div class="fdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="fdb-card">
                    <div class="fdb-card-header">
                        <div class="fdb-card-title"><span class="fdb-card-icon">${ICONS.alert}</span>${__("Finance Alerts")}</div>
                    </div>
                    <div id="fdb-alerts" class="fdb-alerts-wrap"><div class="fdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>

            <div class="fdb-lower fdb-lower--secondary">
                <div class="fdb-card">
                    <div class="fdb-card-header"><div class="fdb-card-title"><span class="fdb-card-icon">${ICONS.receivable}</span>${__("Due Horizon")}</div></div>
                    <div id="fdb-due-horizon" class="fdb-metrics-wrap"><div class="fdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
                <div class="fdb-card">
                    <div class="fdb-card-header"><div class="fdb-card-title"><span class="fdb-card-icon">${ICONS.ledger}</span>${__("Accounting Activity")}</div></div>
                    <div id="fdb-activity" class="fdb-metrics-wrap"><div class="fdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>

            <div class="fdb-lower fdb-lower--secondary">
                <div class="fdb-card">
                    <div class="fdb-card-header"><div class="fdb-card-title"><span class="fdb-card-icon">${ICONS.payment}</span>${__("Recent Collections & Payments")}</div></div>
                    <div id="fdb-cashflow" class="fdb-metrics-wrap"><div class="fdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>
        </div>
    `);

    page.main.find(".fdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (url) window.location.href = url;
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({ method: "orderlift.orderlift_sales.page.finance_dashboard.finance_dashboard.get_dashboard_data" });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {}, data.alerts || []);
        renderKpis(page, data.kpis || {});
        renderRecentDocs(page, data.recent_docs || []);
        renderAlerts(page, data.alerts || []);
        renderDueHorizon(page, data.due_horizon || []);
        renderActivity(page, data.accounting_activity || []);
        renderCashflow(page, data.cash_collections || []);
    } catch (e) {
        renderHeroStats(page, {}, []);
        renderKpis(page, {});
        renderRecentDocs(page, []);
        renderAlerts(page, []);
        renderDueHorizon(page, []);
        renderActivity(page, []);
        renderCashflow(page, []);
        console.warn("Finance Dashboard: failed to load data", e);
    }
}

function renderHeroStats(page, kpis, alerts) {
    page.main.find("#fdb-hero-receivables .fdb-hero-stat-val").text(formatCurrency(kpis.overdue_receivables || 0));
    page.main.find("#fdb-hero-payables .fdb-hero-stat-val").text(formatCurrency(kpis.overdue_payables || 0));
    const alertEl = page.main.find("#fdb-hero-alerts .fdb-hero-stat-val");
    alertEl.text((alerts || []).length);
    if ((alerts || []).length > 0) alertEl.addClass("fdb-stat-warn");
}

function shortcutUrl(iconKey, label, url, variant) {
    return `<div class="fdb-shortcut fdb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}"><span class="fdb-shortcut-icon">${ICONS[iconKey] || ""}</span><span class="fdb-shortcut-label">${frappe.utils.escape_html(label)}</span></div>`;
}

function renderKpis(page, kpis) {
    const defs = [
        { icon: "receivable", label: __("Sales Invoices"), value: kpis.sales_invoice_count ?? "—", sub: __("customer billing docs") },
        { icon: "payable", label: __("Purchase Invoices"), value: kpis.purchase_invoice_count ?? "—", sub: __("supplier liability docs") },
        { icon: "payment", label: __("Payments This Month"), value: kpis.payment_entries_month ?? "—", sub: __("validated payment entries") },
        { icon: "ledger", label: __("Journal Entries This Month"), value: kpis.journal_entries_month ?? "—", sub: __("manual accounting entries") },
        { icon: "ledger", label: __("GL Entries This Month"), value: kpis.gl_entries_month ?? "—", sub: __("posted ledger activity") },
    ];
    page.main.find("#fdb-kpi-grid").html(defs.map((d) => `<div class="fdb-kpi"><div class="fdb-kpi-top"><span class="fdb-kpi-icon">${ICONS[d.icon]}</span></div><div class="fdb-kpi-val">${d.value}</div><div class="fdb-kpi-lbl">${d.label}</div><div class="fdb-kpi-sub">${d.sub}</div></div>`).join(""));
}

function renderRecentDocs(page, rows) {
    if (!rows.length) { page.main.find("#fdb-recent-table").html(`<div class="fdb-empty">${__("No finance documents yet.")}</div>`); return; }
    page.main.find("#fdb-recent-table").html(`<div class="fdb-mini-list">${rows.map((row) => `<a class="fdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}"><span class="fdb-mini-label">${frappe.utils.escape_html(row.label || "")}</span><span class="fdb-mini-meta">${frappe.utils.escape_html(row.meta || "")}</span></a>`).join("")}</div>`);
}

function renderAlerts(page, alerts) {
    if (!alerts.length) { page.main.find("#fdb-alerts").html(`<div class="fdb-empty">${ICONS.check}<p>${__("No active finance alerts.")}</p></div>`); return; }
    page.main.find("#fdb-alerts").html(`<div class="fdb-alert-list">${alerts.map((a) => `<a class="fdb-alert fdb-alert--${a.level || "info"}" href="${frappe.utils.escape_html(a.link || "#")}"><div class="fdb-alert-title">${frappe.utils.escape_html(a.title || "")}</div><div class="fdb-alert-message">${frappe.utils.escape_html(a.message || "")}</div></a>`).join("")}</div>`);
}

function renderDueHorizon(page, rows) {
    if (!rows.length) { page.main.find("#fdb-due-horizon").html(`<div class="fdb-empty">${__("No outstanding due items.")}</div>`); return; }
    page.main.find("#fdb-due-horizon").html(`<div class="fdb-mini-list">${rows.map((row) => `<a class="fdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}"><span class="fdb-mini-label">${frappe.utils.escape_html(row.label || "")}</span><span class="fdb-mini-meta">${frappe.utils.escape_html(row.doctype_label || "")} · ${frappe.utils.escape_html(row.party || "")} · ${frappe.utils.escape_html(row.due_date || "")} · ${formatCurrency(row.amount || 0)}</span></a>`).join("")}</div>`);
}

function renderActivity(page, rows) {
    if (!rows.length) { page.main.find("#fdb-activity").html(`<div class="fdb-empty">${__("No accounting activity yet.")}</div>`); return; }
    page.main.find("#fdb-activity").html(`<div class="fdb-stack-grid"><div class="fdb-stack-card"><div class="fdb-stack-title">${__("By Voucher Type")}</div>${rows.map((item) => `<div class="fdb-metric-row"><span>${frappe.utils.escape_html(item.label || "")}</span><strong>${item.value ?? 0}</strong></div>`).join("")}</div></div>`);
}

function renderCashflow(page, rows) {
    if (!rows.length) { page.main.find("#fdb-cashflow").html(`<div class="fdb-empty">${__("No validated payment activity yet.")}</div>`); return; }
    page.main.find("#fdb-cashflow").html(`<div class="fdb-mini-list">${rows.map((row) => `<a class="fdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}"><span class="fdb-mini-label">${frappe.utils.escape_html(row.name || "")}</span><span class="fdb-mini-meta">${frappe.utils.escape_html(row.payment_type || "")} · ${frappe.utils.escape_html(row.party || "")} · ${frappe.utils.escape_html(row.reference_date || "")} · ${formatCurrency(row.paid_amount || 0)}</span></a>`).join("")}</div>`);
}

function formatCurrency(value) {
    return frappe.format(value || 0, { fieldtype: "Currency" }, { only_value: true });
}

function injectDashboardStyles() {
    if (document.getElementById("fdb-dashboard-styles")) return;
    const style = document.createElement("style");
    style.id = "fdb-dashboard-styles";
    style.textContent = `
        .fdb-root { background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); min-height: calc(100vh - 88px); }
        .fdb-wrapper { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .fdb-hero, .fdb-card, .fdb-shortcut, .fdb-kpi { background: rgba(255,255,255,0.88); border: 1px solid rgba(148,163,184,0.16); box-shadow: 0 18px 50px rgba(15,23,42,0.08); }
        .fdb-hero { border-radius: 24px; padding: 28px; display: flex; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
        .fdb-hero-eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
        .fdb-hero-greeting { font-size: 32px; font-weight: 700; color: #0f172a; }
        .fdb-hero-sub { color: #475569; margin-top: 6px; }
        .fdb-hero-right { display: flex; align-items: center; gap: 18px; }
        .fdb-hero-divider { width: 1px; align-self: stretch; background: rgba(148,163,184,0.2); }
        .fdb-hero-stat-val { font-size: 28px; font-weight: 700; color: #111827; text-align: center; }
        .fdb-hero-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; }
        .fdb-stat-warn { color: #c2410c; }
        .fdb-shortcuts-grid, .fdb-kpi-grid { display: grid; gap: 14px; margin-bottom: 20px; }
        .fdb-shortcuts-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .fdb-kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .fdb-shortcut, .fdb-kpi { border-radius: 18px; padding: 18px; cursor: pointer; }
        .fdb-shortcut { display: flex; align-items: center; gap: 12px; transition: transform .16s ease, box-shadow .16s ease; }
        .fdb-shortcut:hover { transform: translateY(-2px); box-shadow: 0 24px 60px rgba(15,23,42,0.12); }
        .fdb-shortcut--primary { background: linear-gradient(135deg, #4338ca, #3730a3); color: #fff; }
        .fdb-shortcut-icon svg, .fdb-kpi-icon svg, .fdb-card-icon svg { width: 20px; height: 20px; }
        .fdb-shortcut-label { font-weight: 600; }
        .fdb-kpi-top { margin-bottom: 12px; color: #475569; }
        .fdb-kpi-val { font-size: 28px; font-weight: 700; color: #0f172a; }
        .fdb-kpi-lbl { margin-top: 4px; font-weight: 600; color: #1e293b; }
        .fdb-kpi-sub { margin-top: 6px; font-size: 12px; color: #64748b; }
        .fdb-lower { display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }
        .fdb-lower--secondary { margin-top: 18px; grid-template-columns: 1fr 1fr; }
        .fdb-card { border-radius: 22px; overflow: hidden; }
        .fdb-card-header { padding: 18px 20px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .fdb-card-title { display: flex; align-items: center; gap: 10px; font-weight: 700; color: #0f172a; }
        .fdb-view-all { color: #4338ca; font-weight: 600; text-decoration: none; }
        .fdb-mini-list, .fdb-alert-list { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 10px; }
        .fdb-mini-row, .fdb-alert { display: block; border-radius: 14px; padding: 14px; text-decoration: none; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .fdb-mini-label, .fdb-alert-title { display: block; font-weight: 600; color: #111827; }
        .fdb-mini-meta, .fdb-alert-message { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
        .fdb-alert--warn { border-left: 4px solid #f59e0b; }
        .fdb-alert--info { border-left: 4px solid #3b82f6; }
        .fdb-empty { padding: 28px 18px; text-align: center; color: #64748b; }
        .fdb-stack-grid { padding: 0 16px 16px; display: grid; grid-template-columns: 1fr; gap: 12px; }
        .fdb-stack-card { border-radius: 14px; padding: 14px; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .fdb-stack-title { font-weight: 700; color: #111827; margin-bottom: 10px; }
        .fdb-metric-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(226,232,240,0.8); }
        .fdb-metric-row:last-child { border-bottom: 0; }
        .fdb-metric-row span { color: #475569; }
        .fdb-metric-row strong { color: #0f172a; }
        .fdb-kpi--shimmer, .fdb-shimmer-block { position: relative; overflow: hidden; background: rgba(255,255,255,0.7); }
        .fdb-kpi--shimmer::after, .fdb-shimmer-block::after { content: ""; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent); animation: fdbShimmer 1.5s infinite; }
        @keyframes fdbShimmer { 100% { transform: translateX(100%); } }
        @media (max-width: 980px) { .fdb-hero, .fdb-hero-right { flex-direction: column; align-items: flex-start; } .fdb-hero-right { width: 100%; } .fdb-hero-divider { display: none; } .fdb-lower, .fdb-lower--secondary { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
