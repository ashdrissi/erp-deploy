frappe.pages["b2b-portal-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("B2B Portal"),
        single_column: true,
    });

    page.main.addClass("bpdb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    globe: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="8"/><path d="M2 10h16"/><path d="M10 2a13 13 0 0 1 0 16"/><path d="M10 2a13 13 0 0 0 0 16"/></svg>`,
    policy: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="12" height="14" rx="2"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/><line x1="7" y1="13" x2="11" y2="13"/></svg>`,
    request: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/></svg>`,
    users: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="8" r="3"/><circle cx="14" cy="9" r="2.5"/><path d="M2.5 17c0-2.8 2.2-5 4.5-5s4.5 2.2 4.5 5"/><path d="M11 17c.4-2 1.9-3.5 4-3.5 1.6 0 3 .9 3.7 2.3"/></svg>`,
    quote: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/></svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r="0.6" fill="currentColor"/></svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="10" x2="16" y2="10"/><polyline points="11,5 16,10 11,15"/></svg>`,
};

function renderSkeleton(page) {
    page.main.html(`
        <div class="bpdb-wrapper">
            <div class="bpdb-hero">
                <div class="bpdb-hero-left">
                    <div class="bpdb-hero-eyebrow">${__("Orderlift · B2B Portal Control")}</div>
                    <div class="bpdb-hero-title">${__("B2B Portal Operations")}</div>
                    <div class="bpdb-hero-sub">${__("Manage customer-group policies, visible products, invited users, and incoming quote requests.")}</div>
                </div>
                <div class="bpdb-hero-right">
                    <div class="bpdb-hero-stat" id="bpdb-hero-policies"><div class="bpdb-hero-stat-val">—</div><div class="bpdb-hero-stat-label">${__("Policies")}</div></div>
                    <div class="bpdb-hero-divider"></div>
                    <div class="bpdb-hero-stat" id="bpdb-hero-requests"><div class="bpdb-hero-stat-val">—</div><div class="bpdb-hero-stat-label">${__("Requests")}</div></div>
                    <div class="bpdb-hero-divider"></div>
                    <div class="bpdb-hero-stat" id="bpdb-hero-alerts"><div class="bpdb-hero-stat-val">—</div><div class="bpdb-hero-stat-label">${__("Alerts")}</div></div>
                </div>
            </div>

            <div class="bpdb-shortcuts-grid">
                ${shortcut("globe", __("Open Live Portal"), "/b2b-portal", "url")}
                ${shortcut("policy", __("Portal Policies"), "/app/portal-customer-group-policy", "url")}
                ${shortcut("request", __("Quote Requests"), "/app/portal-quote-request", "url")}
                ${shortcut("request", __("Review Board"), "/app/portal-review-board", "url")}
                ${shortcut("users", __("Customers"), "/app/customer", "url")}
                ${shortcut("users", __("Users"), "/app/user", "url")}
            </div>

            <div class="bpdb-kpi-grid" id="bpdb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="bpdb-kpi bpdb-kpi--shimmer"></div>`).join("")}
            </div>

            <div class="bpdb-lower">
                <div class="bpdb-card"><div class="bpdb-card-header"><div class="bpdb-card-title">${__("Recent Quote Requests")}</div></div><div id="bpdb-requests" class="bpdb-card-body"><div class="bpdb-shimmer-block"></div></div></div>
                <div class="bpdb-card"><div class="bpdb-card-header"><div class="bpdb-card-title">${__("Portal Alerts")}</div></div><div id="bpdb-alerts" class="bpdb-card-body"><div class="bpdb-shimmer-block"></div></div></div>
            </div>

            <div class="bpdb-lower bpdb-lower--secondary">
                <div class="bpdb-card"><div class="bpdb-card-header"><div class="bpdb-card-title">${__("Customer Group Coverage")}</div></div><div id="bpdb-coverage" class="bpdb-card-body"><div class="bpdb-shimmer-block"></div></div></div>
                <div class="bpdb-card"><div class="bpdb-card-header"><div class="bpdb-card-title">${__("Request Status")}</div></div><div id="bpdb-status" class="bpdb-card-body"><div class="bpdb-shimmer-block"></div></div></div>
            </div>
        </div>
    `);

    page.main.find(".bpdb-shortcut").on("click", function () {
        const value = $(this).data("value");
        if (value) {
            window.location.href = value;
        }
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({ method: "orderlift.orderlift_client_portal.page.b2b_portal_dashboard.b2b_portal_dashboard.get_dashboard_data" });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {}, data.alerts || []);
        renderKpis(page, data.kpis || {});
        renderRequests(page, data.recent_requests || []);
        renderAlerts(page, data.alerts || []);
        renderCoverage(page, data.group_coverage || []);
        renderStatus(page, data.request_status || []);
    } catch (e) {
        console.warn("B2B Portal Dashboard failed", e);
    }
}

function renderHeroStats(page, kpis, alerts) {
    page.main.find("#bpdb-hero-policies .bpdb-hero-stat-val").text(kpis.policies ?? 0);
    page.main.find("#bpdb-hero-requests .bpdb-hero-stat-val").text(kpis.requests_total ?? 0);
    page.main.find("#bpdb-hero-alerts .bpdb-hero-stat-val").text((alerts || []).length);
}

function renderKpis(page, kpis) {
    const defs = [
        { icon: ICONS.policy, label: __("Policies"), value: kpis.policies ?? 0, sub: __("customer-group policies") },
        { icon: ICONS.globe, label: __("Allowed Products"), value: kpis.products ?? 0, sub: __("visible portal products") },
        { icon: ICONS.users, label: __("Portal Users"), value: kpis.portal_users ?? 0, sub: __("users with portal role") },
        { icon: ICONS.request, label: __("All Requests"), value: kpis.requests_total ?? 0, sub: __("portal quotation requests") },
        { icon: ICONS.alert, label: __("Pending Review"), value: kpis.pending ?? 0, sub: __("requests awaiting internal action") },
        { icon: ICONS.quote, label: __("Quotation Created"), value: kpis.quoted ?? 0, sub: __("requests converted to quotations") },
    ];
    page.main.find("#bpdb-kpi-grid").html(defs.map((d) => `<div class="bpdb-kpi"><div class="bpdb-kpi-icon">${d.icon}</div><div class="bpdb-kpi-value">${d.value}</div><div class="bpdb-kpi-label">${d.label}</div><div class="bpdb-kpi-sub">${d.sub}</div></div>`).join(""));
}

function renderRequests(page, rows) {
    if (!rows.length) {
        page.main.find("#bpdb-requests").html(`<div class="bpdb-empty">${__("No portal requests yet.")}</div>`);
        return;
    }
    page.main.find("#bpdb-requests").html(rows.map((r) => `<a class="bpdb-row" href="/app/portal-quote-request/${frappe.utils.escape_html(r.name)}"><div><strong>${frappe.utils.escape_html(r.name)}</strong><div class="bpdb-meta">${frappe.utils.escape_html(r.customer || "")} · ${frappe.utils.escape_html(r.customer_group || "")} · ${frappe.utils.escape_html(r.status || "")}</div></div><div class="bpdb-amount">${frappe.format(r.total_amount || 0, {fieldtype:'Currency'}, {only_value:true})}</div></a>`).join(""));
}

function renderAlerts(page, rows) {
    if (!rows.length) {
        page.main.find("#bpdb-alerts").html(`<div class="bpdb-empty">${__("No active portal alerts.")}</div>`);
        return;
    }
    page.main.find("#bpdb-alerts").html(rows.map((r) => `<a class="bpdb-alert bpdb-alert--${frappe.utils.escape_html(r.level || 'info')}" href="${frappe.utils.escape_html(r.link || '#')}"><strong>${frappe.utils.escape_html(r.title || '')}</strong><span>${frappe.utils.escape_html(r.message || '')}</span></a>`).join(""));
}

function renderCoverage(page, rows) {
    if (!rows.length) {
        page.main.find("#bpdb-coverage").html(`<div class="bpdb-empty">${__("No customer group portal policies yet.")}</div>`);
        return;
    }
    page.main.find("#bpdb-coverage").html(rows.map((r) => `<div class="bpdb-metric-row"><span>${frappe.utils.escape_html(r.customer_group || '')}</span><strong>${r.product_count || 0}</strong><em>${frappe.utils.escape_html(r.portal_price_list || '')}</em></div>`).join(""));
}

function renderStatus(page, rows) {
    if (!rows.length) {
        page.main.find("#bpdb-status").html(`<div class="bpdb-empty">${__("No request status data yet.")}</div>`);
        return;
    }
    page.main.find("#bpdb-status").html(rows.map((r) => `<div class="bpdb-metric-row"><span>${frappe.utils.escape_html(r.label || '')}</span><strong>${r.value || 0}</strong></div>`).join(""));
}

function shortcut(icon, label, value, kind) {
    const encoded = frappe.utils.escape_html(String(value));
    return `<div class="bpdb-shortcut" data-kind="${kind}" data-value="${encoded}"><span class="bpdb-shortcut-icon">${icon}</span><span class="bpdb-shortcut-label">${frappe.utils.escape_html(label)}</span></div>`;
}

function injectDashboardStyles() {
    if (document.getElementById("bpdb-styles")) return;
    const style = document.createElement("style");
    style.id = "bpdb-styles";
    style.textContent = `
        .bpdb-root { background: linear-gradient(180deg, #f8fafc 0%, #f3e8ff 100%); min-height: calc(100vh - 88px); }
        .bpdb-wrapper { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .bpdb-hero,.bpdb-card,.bpdb-shortcut,.bpdb-kpi { background: rgba(255,255,255,.9); border: 1px solid rgba(148,163,184,.16); box-shadow: 0 18px 50px rgba(15,23,42,.08); }
        .bpdb-hero { border-radius: 24px; padding: 28px; display:flex; justify-content:space-between; gap:24px; margin-bottom:22px; }
        .bpdb-hero-eyebrow { font-size:12px; text-transform:uppercase; letter-spacing:.12em; color:#64748b; margin-bottom:8px; }
        .bpdb-hero-title { font-size:34px; font-weight:700; }
        .bpdb-hero-sub { margin-top:8px; color:#475569; max-width:700px; }
        .bpdb-hero-right { display:flex; gap:18px; align-items:center; }
        .bpdb-hero-divider { width:1px; align-self:stretch; background:rgba(148,163,184,.2); }
        .bpdb-hero-stat-val { font-size:28px; font-weight:700; text-align:center; }
        .bpdb-hero-stat-label { font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:.08em; }
        .bpdb-shortcuts-grid,.bpdb-kpi-grid { display:grid; gap:14px; margin-bottom:20px; }
        .bpdb-shortcuts-grid { grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); }
        .bpdb-kpi-grid { grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); }
        .bpdb-shortcut,.bpdb-kpi { border-radius:18px; padding:18px; cursor:pointer; }
        .bpdb-shortcut { display:flex; gap:12px; align-items:center; }
        .bpdb-shortcut:hover { transform: translateY(-2px); }
        .bpdb-shortcut-icon svg,.bpdb-kpi-icon svg { width:20px; height:20px; }
        .bpdb-shortcut-label { font-weight:600; }
        .bpdb-kpi-value { font-size:28px; font-weight:700; margin-top:10px; }
        .bpdb-kpi-label { margin-top:4px; font-weight:600; }
        .bpdb-kpi-sub { margin-top:6px; font-size:12px; color:#64748b; }
        .bpdb-lower { display:grid; grid-template-columns:1.15fr .85fr; gap:18px; }
        .bpdb-lower--secondary { margin-top:18px; grid-template-columns:1fr 1fr; }
        .bpdb-card { border-radius:22px; overflow:hidden; }
        .bpdb-card-header { padding:18px 20px 12px; display:flex; align-items:center; justify-content:space-between; }
        .bpdb-card-title { font-weight:700; font-size:18px; }
        .bpdb-card-body { padding:0 18px 18px; }
        .bpdb-row,.bpdb-alert,.bpdb-metric-row { display:flex; justify-content:space-between; gap:12px; padding:14px; border-radius:14px; margin-bottom:10px; background:#f8fafc; text-decoration:none; color:#0f172a; }
        .bpdb-row strong,.bpdb-alert strong { display:block; }
        .bpdb-meta,.bpdb-alert span,.bpdb-metric-row em { font-size:12px; color:#64748b; display:block; margin-top:4px; font-style:normal; }
        .bpdb-amount { font-weight:700; }
        .bpdb-alert--warn { border-left:4px solid #f59e0b; }
        .bpdb-alert--info { border-left:4px solid #3b82f6; }
        .bpdb-empty { padding:24px 8px; text-align:center; color:#64748b; }
        .bpdb-shimmer-block { height:180px; border-radius:8px; background:rgba(255,255,255,.7); position:relative; overflow:hidden; }
        .bpdb-shimmer-block::after { content:''; position:absolute; inset:0; transform:translateX(-100%); background:linear-gradient(90deg,transparent,rgba(255,255,255,.8),transparent); animation: bpdbShimmer 1.5s infinite; }
        @keyframes bpdbShimmer { 100% { transform: translateX(100%); } }
        @media (max-width: 980px) { .bpdb-hero,.bpdb-hero-right,.bpdb-lower,.bpdb-lower--secondary { display:block; } .bpdb-hero-right{ margin-top:18px; } .bpdb-card + .bpdb-card{ margin-top:18px; } }
    `;
    document.head.appendChild(style);
}
