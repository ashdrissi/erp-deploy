frappe.pages["hr-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("HR"),
        single_column: true,
    });

    page.main.addClass("hdb-root");
    injectDashboardStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    employee: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="3.5"/><path d="M4 17c0-3.1 2.7-5.5 6-5.5s6 2.4 6 5.5"/></svg>`,
    leave: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2C6 6 4 8.5 4 12a6 6 0 0 0 12 0c0-3.5-2-6-6-10z"/></svg>`,
    attendance: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="14" height="13" rx="2"/><line x1="3" y1="8" x2="17" y2="8"/><polyline points="7,12 9,14 13,10"/></svg>`,
    payroll: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="14" height="12" rx="2"/><path d="M6 10h8"/><path d="M10 7v6"/></svg>`,
    expense: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h10l2 4-2 10H5L3 7l2-4z"/><path d="M7 7h6"/></svg>`,
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
        <div class="hdb-wrapper">
            <div class="hdb-hero">
                <div class="hdb-hero-left"><div class="hdb-hero-eyebrow">${__("Orderlift · People Hub")}</div><div class="hdb-hero-greeting">${greeting}</div><div class="hdb-hero-sub">${today}</div></div>
                <div class="hdb-hero-right">
                    <div class="hdb-hero-stat" id="hdb-hero-headcount"><div class="hdb-hero-stat-val">—</div><div class="hdb-hero-stat-label">${__("Active Employees")}</div></div>
                    <div class="hdb-hero-divider"></div>
                    <div class="hdb-hero-stat" id="hdb-hero-leave"><div class="hdb-hero-stat-val">—</div><div class="hdb-hero-stat-label">${__("Leave Pipeline")}</div></div>
                    <div class="hdb-hero-divider"></div>
                    <div class="hdb-hero-stat" id="hdb-hero-alerts"><div class="hdb-hero-stat-val">—</div><div class="hdb-hero-stat-label">${__("Alerts")}</div></div>
                </div>
            </div>

            <div class="hdb-shortcuts-grid">
                ${shortcutUrl("plus", __("New Employee"), "/desk/hr/employee/new-employee-1?sidebar=Main+Dashboard", "primary")}
                ${shortcutUrl("employee", __("Employees"), "/desk/hr/employee?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("leave", __("Leave Applications"), "/desk/hr/leave-application?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("attendance", __("Attendance"), "/desk/hr/attendance?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("payroll", __("Payroll"), "/desk/hr/payroll-entry?sidebar=Main+Dashboard", "default")}
                ${shortcutUrl("expense", __("Expense Claims"), "/desk/hr/expense-claim?sidebar=Main+Dashboard", "default")}
            </div>

            <div class="hdb-kpi-grid" id="hdb-kpi-grid">${Array.from({ length: 6 }, () => `<div class="hdb-kpi hdb-kpi--shimmer"></div>`).join("")}</div>

            <div class="hdb-lower">
                <div class="hdb-card"><div class="hdb-card-header"><div class="hdb-card-title"><span class="hdb-card-icon">${ICONS.employee}</span>${__("Recent HR Records")}</div><a href="/app/employee" class="hdb-view-all">${__("View all")} ${ICONS.arrow}</a></div><div id="hdb-recent-table" class="hdb-table-wrap"><div class="hdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div></div></div>
                <div class="hdb-card"><div class="hdb-card-header"><div class="hdb-card-title"><span class="hdb-card-icon">${ICONS.alert}</span>${__("HR Alerts")}</div></div><div id="hdb-alerts" class="hdb-alerts-wrap"><div class="hdb-shimmer-block" style="height:160px;margin:16px;border-radius:8px;"></div></div></div>
            </div>

            <div class="hdb-lower hdb-lower--secondary">
                <div class="hdb-card"><div class="hdb-card-header"><div class="hdb-card-title"><span class="hdb-card-icon">${ICONS.employee}</span>${__("Workforce Mix")}</div></div><div id="hdb-workforce-mix" class="hdb-metrics-wrap"><div class="hdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div></div>
                <div class="hdb-card"><div class="hdb-card-header"><div class="hdb-card-title"><span class="hdb-card-icon">${ICONS.leave}</span>${__("Leave Pipeline")}</div></div><div id="hdb-leave-pipeline" class="hdb-metrics-wrap"><div class="hdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div></div>
            </div>

            <div class="hdb-lower hdb-lower--secondary">
                <div class="hdb-card"><div class="hdb-card-header"><div class="hdb-card-title"><span class="hdb-card-icon">${ICONS.attendance}</span>${__("Upcoming Milestones")}</div></div><div id="hdb-milestones" class="hdb-metrics-wrap"><div class="hdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div></div></div>
            </div>
        </div>
    `);

    page.main.find(".hdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (url) window.location.href = url;
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({ method: "orderlift.orderlift_hr.page.hr_dashboard.hr_dashboard.get_dashboard_data" });
        const data = res.message || {};
        renderHeroStats(page, data.kpis || {}, data.alerts || []);
        renderKpis(page, data.kpis || {});
        renderRecentDocs(page, data.recent_docs || []);
        renderAlerts(page, data.alerts || []);
        renderWorkforceMix(page, data.workforce_mix || {});
        renderLeavePipeline(page, data.leave_pipeline || []);
        renderMilestones(page, data.upcoming_milestones || []);
    } catch (e) {
        renderHeroStats(page, {}, []); renderKpis(page, {}); renderRecentDocs(page, []); renderAlerts(page, []); renderWorkforceMix(page, {}); renderLeavePipeline(page, []); renderMilestones(page, []);
        console.warn("HR Dashboard: failed to load data", e);
    }
}

function renderHeroStats(page, kpis, alerts) {
    page.main.find("#hdb-hero-headcount .hdb-hero-stat-val").text(kpis.active_employees ?? "—");
    page.main.find("#hdb-hero-leave .hdb-hero-stat-val").text(kpis.leave_open ?? "—");
    const alertEl = page.main.find("#hdb-hero-alerts .hdb-hero-stat-val"); alertEl.text((alerts || []).length); if ((alerts || []).length > 0) alertEl.addClass("hdb-stat-warn");
}

function shortcutUrl(iconKey, label, url, variant) { return `<div class="hdb-shortcut hdb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}"><span class="hdb-shortcut-icon">${ICONS[iconKey] || ""}</span><span class="hdb-shortcut-label">${frappe.utils.escape_html(label)}</span></div>`; }

function renderKpis(page, kpis) {
    const defs = [
        { icon: "employee", label: __("Active Employees"), value: kpis.active_employees ?? "—", sub: __("current active workforce") },
        { icon: "employee", label: __("Departments"), value: kpis.departments ?? "—", sub: __("active departments") },
        { icon: "leave", label: __("Open Leave"), value: kpis.leave_open ?? "—", sub: __("open or approved leave") },
        { icon: "attendance", label: __("Attendance Today"), value: kpis.attendance_today ?? "—", sub: __("attendance records today") },
        { icon: "payroll", label: __("Salary Slips / Mo"), value: kpis.salary_slips_month ?? "—", sub: __("salary slips this month") },
        { icon: "expense", label: __("Open Expense Claims"), value: kpis.expense_claims_open ?? "—", sub: __("claims awaiting closure") },
    ];
    page.main.find("#hdb-kpi-grid").html(defs.map((d) => `<div class="hdb-kpi"><div class="hdb-kpi-top"><span class="hdb-kpi-icon">${ICONS[d.icon]}</span></div><div class="hdb-kpi-val">${d.value}</div><div class="hdb-kpi-lbl">${d.label}</div><div class="hdb-kpi-sub">${d.sub}</div></div>`).join(""));
}

function renderRecentDocs(page, rows) { if (!rows.length) { page.main.find("#hdb-recent-table").html(`<div class="hdb-empty">${__("No HR records yet.")}</div>`); return; } page.main.find("#hdb-recent-table").html(`<div class="hdb-mini-list">${rows.map((row) => `<a class="hdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}"><span class="hdb-mini-label">${frappe.utils.escape_html(row.label || "")}</span><span class="hdb-mini-meta">${frappe.utils.escape_html(row.meta || "")}</span></a>`).join("")}</div>`); }

function renderAlerts(page, alerts) { if (!alerts.length) { page.main.find("#hdb-alerts").html(`<div class="hdb-empty">${ICONS.check}<p>${__("No active HR alerts.")}</p></div>`); return; } page.main.find("#hdb-alerts").html(`<div class="hdb-alert-list">${alerts.map((a) => `<a class="hdb-alert hdb-alert--${a.level || "info"}" href="${frappe.utils.escape_html(a.link || "#")}"><div class="hdb-alert-title">${frappe.utils.escape_html(a.title || "")}</div><div class="hdb-alert-message">${frappe.utils.escape_html(a.message || "")}</div></a>`).join("")}</div>`); }

function renderWorkforceMix(page, mix) {
    const departments = mix.departments || [];
    const designations = mix.designations || [];
    const status = mix.status || [];
    if (!departments.length && !designations.length && !status.length) { page.main.find("#hdb-workforce-mix").html(`<div class="hdb-empty">${__("No workforce data yet.")}</div>`); return; }
    page.main.find("#hdb-workforce-mix").html(`<div class="hdb-stack-grid"><div class="hdb-stack-card"><div class="hdb-stack-title">${__("By Department")}</div>${departments.map((i) => `<div class="hdb-metric-row"><span>${frappe.utils.escape_html(i.label || "")}</span><strong>${i.value ?? 0}</strong></div>`).join("")}</div><div class="hdb-stack-card"><div class="hdb-stack-title">${__("By Designation")}</div>${designations.map((i) => `<div class="hdb-metric-row"><span>${frappe.utils.escape_html(i.label || "")}</span><strong>${i.value ?? 0}</strong></div>`).join("") || `<div class="hdb-empty-inline">${__("No designations")}</div>`}</div><div class="hdb-stack-card"><div class="hdb-stack-title">${__("By Status")}</div>${status.map((i) => `<div class="hdb-metric-row"><span>${frappe.utils.escape_html(i.label || "")}</span><strong>${i.value ?? 0}</strong></div>`).join("")}</div></div>`);
}

function renderLeavePipeline(page, rows) { if (!rows.length) { page.main.find("#hdb-leave-pipeline").html(`<div class="hdb-empty">${__("No leave workflow data yet.")}</div>`); return; } page.main.find("#hdb-leave-pipeline").html(`<div class="hdb-stack-grid"><div class="hdb-stack-card"><div class="hdb-stack-title">${__("By Status")}</div>${rows.map((i) => `<div class="hdb-metric-row"><span>${frappe.utils.escape_html(i.label || "")}</span><strong>${i.value ?? 0}</strong></div>`).join("")}</div></div>`); }

function renderMilestones(page, rows) { if (!rows.length) { page.main.find("#hdb-milestones").html(`<div class="hdb-empty">${__("No upcoming HR milestones yet.")}</div>`); return; } page.main.find("#hdb-milestones").html(`<div class="hdb-mini-list">${rows.map((row) => `<a class="hdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}"><span class="hdb-mini-label">${frappe.utils.escape_html(row.employee_name || "")}</span><span class="hdb-mini-meta">${frappe.utils.escape_html(row.date || "")} ${row.meta ? `· ${frappe.utils.escape_html(row.meta)}` : ""}</span></a>`).join("")}</div>`); }

function injectDashboardStyles() {
    if (document.getElementById("hdb-dashboard-styles")) return;
    const style = document.createElement("style"); style.id = "hdb-dashboard-styles"; style.textContent = `
        .hdb-root { background: linear-gradient(180deg, #f8fafc 0%, #ecfeff 100%); min-height: calc(100vh - 88px); }
        .hdb-wrapper { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .hdb-hero, .hdb-card, .hdb-shortcut, .hdb-kpi { background: rgba(255,255,255,0.88); border: 1px solid rgba(148,163,184,0.16); box-shadow: 0 18px 50px rgba(15,23,42,0.08); }
        .hdb-hero { border-radius: 24px; padding: 28px; display: flex; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
        .hdb-hero-eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
        .hdb-hero-greeting { font-size: 32px; font-weight: 700; color: #0f172a; }
        .hdb-hero-sub { color: #475569; margin-top: 6px; }
        .hdb-hero-right { display: flex; align-items: center; gap: 18px; }
        .hdb-hero-divider { width: 1px; align-self: stretch; background: rgba(148,163,184,0.2); }
        .hdb-hero-stat-val { font-size: 28px; font-weight: 700; color: #111827; text-align: center; }
        .hdb-hero-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; }
        .hdb-stat-warn { color: #c2410c; }
        .hdb-shortcuts-grid, .hdb-kpi-grid { display: grid; gap: 14px; margin-bottom: 20px; }
        .hdb-shortcuts-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .hdb-kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .hdb-shortcut, .hdb-kpi { border-radius: 18px; padding: 18px; cursor: pointer; }
        .hdb-shortcut { display: flex; align-items: center; gap: 12px; transition: transform .16s ease, box-shadow .16s ease; }
        .hdb-shortcut:hover { transform: translateY(-2px); box-shadow: 0 24px 60px rgba(15,23,42,0.12); }
        .hdb-shortcut--primary { background: linear-gradient(135deg, #0891b2, #0e7490); color: #fff; }
        .hdb-shortcut-icon svg, .hdb-kpi-icon svg, .hdb-card-icon svg { width: 20px; height: 20px; }
        .hdb-shortcut-label { font-weight: 600; }
        .hdb-kpi-top { margin-bottom: 12px; color: #475569; }
        .hdb-kpi-val { font-size: 28px; font-weight: 700; color: #0f172a; }
        .hdb-kpi-lbl { margin-top: 4px; font-weight: 600; color: #1e293b; }
        .hdb-kpi-sub { margin-top: 6px; font-size: 12px; color: #64748b; }
        .hdb-lower { display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }
        .hdb-lower--secondary { margin-top: 18px; grid-template-columns: 1fr 1fr; }
        .hdb-card { border-radius: 22px; overflow: hidden; }
        .hdb-card-header { padding: 18px 20px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .hdb-card-title { display: flex; align-items: center; gap: 10px; font-weight: 700; color: #0f172a; }
        .hdb-view-all { color: #0891b2; font-weight: 600; text-decoration: none; }
        .hdb-mini-list, .hdb-alert-list { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 10px; }
        .hdb-mini-row, .hdb-alert { display: block; border-radius: 14px; padding: 14px; text-decoration: none; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .hdb-mini-label, .hdb-alert-title { display: block; font-weight: 600; color: #111827; }
        .hdb-mini-meta, .hdb-alert-message { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
        .hdb-alert--warn { border-left: 4px solid #f59e0b; } .hdb-alert--info { border-left: 4px solid #3b82f6; }
        .hdb-empty { padding: 28px 18px; text-align: center; color: #64748b; }
        .hdb-empty-inline { padding: 8px 0; color: #64748b; font-size: 12px; }
        .hdb-stack-grid { padding: 0 16px 16px; display: grid; grid-template-columns: 1fr; gap: 12px; }
        .hdb-stack-card { border-radius: 14px; padding: 14px; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .hdb-stack-title { font-weight: 700; color: #111827; margin-bottom: 10px; }
        .hdb-metric-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(226,232,240,0.8); }
        .hdb-metric-row:last-child { border-bottom: 0; }
        .hdb-metric-row span { color: #475569; } .hdb-metric-row strong { color: #0f172a; }
        .hdb-kpi--shimmer, .hdb-shimmer-block { position: relative; overflow: hidden; background: rgba(255,255,255,0.7); }
        .hdb-kpi--shimmer::after, .hdb-shimmer-block::after { content: ""; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent); animation: hdbShimmer 1.5s infinite; }
        @keyframes hdbShimmer { 100% { transform: translateX(100%); } }
        @media (max-width: 980px) { .hdb-hero, .hdb-hero-right { flex-direction: column; align-items: flex-start; } .hdb-hero-right { width: 100%; } .hdb-hero-divider { display: none; } .hdb-lower, .hdb-lower--secondary { grid-template-columns: 1fr; } }
    `; document.head.appendChild(style);
}
