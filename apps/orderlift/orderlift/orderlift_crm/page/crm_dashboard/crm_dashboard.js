frappe.pages["crm-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("CRM"),
        single_column: true,
    });

    page.main.addClass("cdb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    lead: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="6.5" r="3.5"/><path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6"/></svg>`,
    opportunity: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/></svg>`,
    customer: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M7 8h6M7 11h6M7 14h4"/></svg>`,
    contact: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="3.5"/><path d="M4 17c0-3.1 2.7-5.5 6-5.5s6 2.4 6 5.5"/></svg>`,
    quote: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/></svg>`,
    segment: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v16"/><path d="M2 10h16"/><circle cx="10" cy="10" r="7"/></svg>`,
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
        <div class="cdb-wrapper">
            <div class="cdb-hero">
                <div class="cdb-hero-left">
                    <div class="cdb-hero-eyebrow">${__("Orderlift · CRM Hub")}</div>
                    <div class="cdb-hero-greeting">${greeting}</div>
                    <div class="cdb-hero-sub">${today}</div>
                </div>
                <div class="cdb-hero-right">
                    <div class="cdb-hero-stat" id="cdb-hero-leads"><div class="cdb-hero-stat-val">—</div><div class="cdb-hero-stat-label">${__("Leads")}</div></div>
                    <div class="cdb-hero-divider"></div>
                    <div class="cdb-hero-stat" id="cdb-hero-opps"><div class="cdb-hero-stat-val">—</div><div class="cdb-hero-stat-label">${__("Opportunities")}</div></div>
                    <div class="cdb-hero-divider"></div>
                    <div class="cdb-hero-stat" id="cdb-hero-alerts"><div class="cdb-hero-stat-val">—</div><div class="cdb-hero-stat-label">${__("Alerts")}</div></div>
                </div>
            </div>

            <div class="cdb-shortcuts-grid">
                ${shortcut("plus", __("New Lead"), "/app/lead/new-lead-1", "primary")}
                ${shortcut("opportunity", __("Opportunities"), "/app/opportunity", "default")}
                ${shortcut("opportunity", __("Prospects"), "/app/prospect", "default")}
                ${shortcut("customer", __("Customers"), "/app/customer", "default")}
                ${shortcut("contact", __("Contacts"), "/app/contact", "default")}
                ${shortcut("quote", __("Quotations"), "/app/quotation", "default")}
                ${shortcut("segment", __("Segmentation"), "/app/customer-segmentation-engine", "default")}
            </div>

            <div class="cdb-kpi-grid" id="cdb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="cdb-kpi cdb-kpi--shimmer"></div>`).join("")}
            </div>

            <div class="cdb-lower">
                <div class="cdb-card">
                    <div class="cdb-card-header">
                        <div class="cdb-card-title"><span class="cdb-card-icon">${ICONS.customer}</span>${__("Recent CRM Records")}</div>
                        <a href="/app/customer" class="cdb-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="cdb-recent-table" class="cdb-table-wrap"><div class="cdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="cdb-card">
                    <div class="cdb-card-header">
                        <div class="cdb-card-title"><span class="cdb-card-icon">${ICONS.alert}</span>${__("CRM Alerts")}</div>
                    </div>
                    <div id="cdb-alerts" class="cdb-alerts-wrap"><div class="cdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>

            <div class="cdb-lower cdb-lower--secondary">
                <div class="cdb-card">
                    <div class="cdb-card-header">
                        <div class="cdb-card-title"><span class="cdb-card-icon">${ICONS.opportunity}</span>${__("Pipeline Breakdown")}</div>
                    </div>
                    <div id="cdb-pipeline" class="cdb-metrics-wrap"><div class="cdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="cdb-card">
                    <div class="cdb-card-header">
                        <div class="cdb-card-title"><span class="cdb-card-icon">${ICONS.segment}</span>${__("Customer Mix")}</div>
                    </div>
                    <div id="cdb-customer-mix" class="cdb-metrics-wrap"><div class="cdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>

            <div class="cdb-lower cdb-lower--secondary">
                <div class="cdb-card">
                    <div class="cdb-card-header">
                        <div class="cdb-card-title"><span class="cdb-card-icon">${ICONS.communication}</span>${__("Recent Communications")}</div>
                    </div>
                    <div id="cdb-communications" class="cdb-metrics-wrap"><div class="cdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>

                <div class="cdb-card">
                    <div class="cdb-card-header">
                        <div class="cdb-card-title"><span class="cdb-card-icon">${ICONS.calendar}</span>${__("Upcoming Schedule")}</div>
                    </div>
                    <div id="cdb-schedule" class="cdb-metrics-wrap"><div class="cdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div>
                </div>
            </div>
        </div>
    `);

    page.main.find(".cdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (!url) return;
        frappe.set_route(url.replace(/^\/app\//, "").split("/"));
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.page.crm_dashboard.crm_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {}, data.alerts || []);
        renderKpis(page, data.kpis || {});
        renderRecentDocs(page, data.recent_docs || []);
        renderAlerts(page, data.alerts || []);
        renderPipeline(page, data.pipeline || []);
        renderCustomerMix(page, data.customer_mix || {});
        renderCommunications(page, data.recent_communications || []);
        renderSchedule(page, data.upcoming_schedule || []);
    } catch (e) {
        renderHeroStats(page, {}, []);
        renderKpis(page, {});
        renderRecentDocs(page, []);
        renderAlerts(page, []);
        renderPipeline(page, []);
        renderCustomerMix(page, {});
        renderCommunications(page, []);
        renderSchedule(page, []);
        console.warn("CRM Dashboard: failed to load data", e);
    }
}

function renderHeroStats(page, kpis, alerts) {
    page.main.find("#cdb-hero-leads .cdb-hero-stat-val").text(kpis.leads_total ?? "—");
    page.main.find("#cdb-hero-opps .cdb-hero-stat-val").text(kpis.opportunities_total ?? "—");
    const alertEl = page.main.find("#cdb-hero-alerts .cdb-hero-stat-val");
    alertEl.text((alerts || []).length);
    if ((alerts || []).length > 0) alertEl.addClass("cdb-stat-warn");
}

function shortcut(iconKey, label, url, variant) {
    return `<div class="cdb-shortcut cdb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}"><span class="cdb-shortcut-icon">${ICONS[iconKey] || ""}</span><span class="cdb-shortcut-label">${frappe.utils.escape_html(label)}</span></div>`;
}

function renderKpis(page, kpis) {
    const defs = [
        { icon: "lead", label: __("Leads"), value: kpis.leads_total ?? "—", sub: __("raw inbound pipeline") },
        { icon: "opportunity", label: __("Opportunities"), value: kpis.opportunities_total ?? "—", sub: __("qualified deals") },
        { icon: "opportunity", label: __("Prospects"), value: kpis.prospects_total ?? "—", sub: __("prospect organizations") },
        { icon: "customer", label: __("Customers"), value: kpis.customers_total ?? "—", sub: __("active customer records") },
        { icon: "contact", label: __("Contacts"), value: kpis.contacts_total ?? "—", sub: __("contact coverage") },
        { icon: "quote", label: __("Quotes This Month"), value: kpis.quotations_month ?? "—", sub: __("commercial output") },
        { icon: "segment", label: __("Segmentation Engines"), value: kpis.segment_engines ?? "—", sub: __("tier automation rules") },
    ];

    page.main.find("#cdb-kpi-grid").html(defs.map((d) => `
        <div class="cdb-kpi">
            <div class="cdb-kpi-top"><span class="cdb-kpi-icon">${ICONS[d.icon]}</span></div>
            <div class="cdb-kpi-val">${d.value}</div>
            <div class="cdb-kpi-lbl">${d.label}</div>
            <div class="cdb-kpi-sub">${d.sub}</div>
        </div>
    `).join(""));
}

function renderRecentDocs(page, rows) {
    if (!rows.length) {
        page.main.find("#cdb-recent-table").html(`<div class="cdb-empty">${__("No recent CRM documents yet.")}</div>`);
        return;
    }

    page.main.find("#cdb-recent-table").html(`
        <div class="cdb-mini-list">
            ${rows.map((row) => `
                <a class="cdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="cdb-mini-label">${frappe.utils.escape_html(row.label || "")}</span>
                    <span class="cdb-mini-meta">${frappe.utils.escape_html(row.meta || "")}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function renderAlerts(page, alerts) {
    if (!alerts.length) {
        page.main.find("#cdb-alerts").html(`<div class="cdb-empty">${ICONS.check}<p>${__("No active CRM alerts.")}</p></div>`);
        return;
    }

    page.main.find("#cdb-alerts").html(`
        <div class="cdb-alert-list">
            ${alerts.map((a) => `
                <a class="cdb-alert cdb-alert--${a.level || "info"}" href="${frappe.utils.escape_html(a.link || "#")}">
                    <div class="cdb-alert-title">${frappe.utils.escape_html(a.title || "")}</div>
                    <div class="cdb-alert-message">${frappe.utils.escape_html(a.message || "")}</div>
                </a>
            `).join("")}
        </div>
    `);
}

function renderPipeline(page, sections) {
    if (!sections.length) {
        page.main.find("#cdb-pipeline").html(`<div class="cdb-empty">${__("No pipeline data yet.")}</div>`);
        return;
    }

    page.main.find("#cdb-pipeline").html(`
        <div class="cdb-stack-grid">
            ${sections.map((section) => `
                <div class="cdb-stack-card">
                    <div class="cdb-stack-title">${frappe.utils.escape_html(section.label || "")}</div>
                    ${(section.items || []).map((item) => `
                        <div class="cdb-metric-row">
                            <span>${frappe.utils.escape_html(item.label || "")}</span>
                            <strong>${item.value ?? 0}</strong>
                        </div>
                    `).join("") || `<div class="cdb-empty-inline">${__("No data")}</div>`}
                </div>
            `).join("")}
        </div>
    `);
}

function renderCustomerMix(page, mix) {
    const groups = mix.groups || [];
    const territories = mix.territories || [];
    if (!groups.length && !territories.length) {
        page.main.find("#cdb-customer-mix").html(`<div class="cdb-empty">${__("No customer mix data yet.")}</div>`);
        return;
    }

    page.main.find("#cdb-customer-mix").html(`
        <div class="cdb-stack-grid">
            <div class="cdb-stack-card">
                <div class="cdb-stack-title">${__("By Customer Group")}</div>
                ${groups.map((item) => `
                    <div class="cdb-metric-row">
                        <span>${frappe.utils.escape_html(item.label || "")}</span>
                        <strong>${item.value ?? 0}</strong>
                    </div>
                `).join("") || `<div class="cdb-empty-inline">${__("No groups")}</div>`}
            </div>
            <div class="cdb-stack-card">
                <div class="cdb-stack-title">${__("By Territory")}</div>
                ${territories.map((item) => `
                    <div class="cdb-metric-row">
                        <span>${frappe.utils.escape_html(item.label || "")}</span>
                        <strong>${item.value ?? 0}</strong>
                    </div>
                `).join("") || `<div class="cdb-empty-inline">${__("No territories")}</div>`}
            </div>
        </div>
    `);
}

function renderCommunications(page, rows) {
    if (!rows.length) {
        page.main.find("#cdb-communications").html(`<div class="cdb-empty">${__("No CRM-linked communications yet.")}</div>`);
        return;
    }

    page.main.find("#cdb-communications").html(`
        <div class="cdb-mini-list">
            ${rows.map((row) => `
                <a class="cdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="cdb-mini-label">${frappe.utils.escape_html(row.subject || "")}</span>
                    <span class="cdb-mini-meta">${frappe.utils.escape_html(row.reference || "")} ${row.meta ? `· ${frappe.utils.escape_html(row.meta)}` : ""}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function renderSchedule(page, rows) {
    if (!rows.length) {
        page.main.find("#cdb-schedule").html(`<div class="cdb-empty">${__("No upcoming CRM schedule yet.")}</div>`);
        return;
    }

    page.main.find("#cdb-schedule").html(`
        <div class="cdb-mini-list">
            ${rows.map((row) => `
                <a class="cdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="cdb-mini-label">${frappe.utils.escape_html(row.subject || "")}</span>
                    <span class="cdb-mini-meta">${frappe.utils.escape_html(row.starts_on || "")} ${row.reference ? `· ${frappe.utils.escape_html(row.reference)}` : ""}</span>
                </a>
            `).join("")}
        </div>
    `);
}

function injectDashboardStyles() {
    if (document.getElementById("cdb-dashboard-styles")) return;

    const style = document.createElement("style");
    style.id = "cdb-dashboard-styles";
    style.textContent = `
        .cdb-root { background: linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%); min-height: calc(100vh - 88px); }
        .cdb-wrapper { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .cdb-hero, .cdb-card, .cdb-shortcut, .cdb-kpi { background: rgba(255,255,255,0.88); border: 1px solid rgba(148,163,184,0.16); box-shadow: 0 18px 50px rgba(15,23,42,0.08); }
        .cdb-hero { border-radius: 24px; padding: 28px; display: flex; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
        .cdb-hero-eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
        .cdb-hero-greeting { font-size: 32px; font-weight: 700; color: #0f172a; }
        .cdb-hero-sub { color: #475569; margin-top: 6px; }
        .cdb-hero-right { display: flex; align-items: center; gap: 18px; }
        .cdb-hero-divider { width: 1px; align-self: stretch; background: rgba(148,163,184,0.2); }
        .cdb-hero-stat-val { font-size: 28px; font-weight: 700; color: #111827; text-align: center; }
        .cdb-hero-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; }
        .cdb-stat-warn { color: #c2410c; }
        .cdb-shortcuts-grid, .cdb-kpi-grid { display: grid; gap: 14px; margin-bottom: 20px; }
        .cdb-shortcuts-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .cdb-kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .cdb-shortcut, .cdb-kpi { border-radius: 18px; padding: 18px; cursor: pointer; }
        .cdb-shortcut { display: flex; align-items: center; gap: 12px; transition: transform .16s ease, box-shadow .16s ease; }
        .cdb-shortcut:hover { transform: translateY(-2px); box-shadow: 0 24px 60px rgba(15,23,42,0.12); }
        .cdb-shortcut--primary { background: linear-gradient(135deg, #1d4ed8, #1e40af); color: #fff; }
        .cdb-shortcut-icon svg, .cdb-kpi-icon svg, .cdb-card-icon svg { width: 20px; height: 20px; }
        .cdb-shortcut-label { font-weight: 600; }
        .cdb-kpi-top { margin-bottom: 12px; color: #475569; }
        .cdb-kpi-val { font-size: 28px; font-weight: 700; color: #0f172a; }
        .cdb-kpi-lbl { margin-top: 4px; font-weight: 600; color: #1e293b; }
        .cdb-kpi-sub { margin-top: 6px; font-size: 12px; color: #64748b; }
        .cdb-lower { display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }
        .cdb-lower--secondary { margin-top: 18px; grid-template-columns: 1fr 1fr; }
        .cdb-card { border-radius: 22px; overflow: hidden; }
        .cdb-card-header { padding: 18px 20px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .cdb-card-title { display: flex; align-items: center; gap: 10px; font-weight: 700; color: #0f172a; }
        .cdb-view-all { color: #2563eb; font-weight: 600; text-decoration: none; }
        .cdb-mini-list, .cdb-alert-list { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 10px; }
        .cdb-mini-row, .cdb-alert { display: block; border-radius: 14px; padding: 14px; text-decoration: none; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .cdb-mini-label, .cdb-alert-title { display: block; font-weight: 600; color: #111827; }
        .cdb-mini-meta, .cdb-alert-message { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
        .cdb-alert--warn { border-left: 4px solid #f59e0b; }
        .cdb-alert--info { border-left: 4px solid #3b82f6; }
        .cdb-empty { padding: 28px 18px; text-align: center; color: #64748b; }
        .cdb-empty-inline { padding: 8px 0; color: #64748b; font-size: 12px; }
        .cdb-empty svg { width: 18px; height: 18px; display: inline-block; margin-bottom: 10px; }
        .cdb-stack-grid { padding: 0 16px 16px; display: grid; grid-template-columns: 1fr; gap: 12px; }
        .cdb-stack-card { border-radius: 14px; padding: 14px; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .cdb-stack-title { font-weight: 700; color: #111827; margin-bottom: 10px; }
        .cdb-metric-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(226,232,240,0.8); }
        .cdb-metric-row:last-child { border-bottom: 0; }
        .cdb-metric-row span { color: #475569; }
        .cdb-metric-row strong { color: #0f172a; }
        .cdb-kpi--shimmer, .cdb-shimmer-block { position: relative; overflow: hidden; background: rgba(255,255,255,0.7); }
        .cdb-kpi--shimmer::after, .cdb-shimmer-block::after { content: ""; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent); animation: cdbShimmer 1.5s infinite; }
        @keyframes cdbShimmer { 100% { transform: translateX(100%); } }
        @media (max-width: 980px) { .cdb-hero, .cdb-hero-right { flex-direction: column; align-items: flex-start; } .cdb-hero-right { width: 100%; } .cdb-hero-divider { display: none; } .cdb-lower, .cdb-lower--secondary { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
