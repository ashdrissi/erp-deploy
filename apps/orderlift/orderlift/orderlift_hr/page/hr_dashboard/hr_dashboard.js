frappe.pages["hr-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("HR"),
        single_column: true,
    });
    page.main.addClass("hr-root hdb-root");
    injectStyles();
    renderSkeleton(page);
    loadDashboardData(page);
};

const ICONS = {
    users: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    department: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>`,
    leave: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
    attendance: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    payroll: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
    expense: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="13" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
    alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="1"/></svg>`,
    plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
    arrow: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`,
    check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    trophy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>`,
    book: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>`,
    activity: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
    cycle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>`,
};

function injectStyles() {
    if (document.getElementById("hdb-styles")) return;
    const css = `
    .hdb-greeting { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
    .hdb-greeting .hr-title { margin: 0; }
    .hdb-date {
        font-size: 13px; color: var(--hr-muted); font-weight: 500;
        background: var(--hr-card); border: 1px solid var(--hr-line);
        padding: 4px 10px; border-radius: 999px;
    }
    .hdb-shortcuts {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
        margin-bottom: 28px;
    }
    .hdb-shortcut {
        background: var(--hr-card);
        border: 1px solid var(--hr-line);
        border-radius: 12px;
        padding: 14px 16px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all .15s;
        color: var(--hr-text);
        font-weight: 600;
        font-size: 13px;
    }
    .hdb-shortcut:hover {
        border-color: var(--hr-primary);
        box-shadow: var(--hr-shadow-md);
        transform: translateY(-1px);
        color: var(--hr-primary-700);
    }
    .hdb-shortcut-icon {
        width: 36px; height: 36px;
        border-radius: 10px;
        background: var(--hr-primary-50);
        color: var(--hr-primary-700);
        display: inline-flex; align-items: center; justify-content: center;
        flex-shrink: 0;
    }
    .hdb-shortcut-icon svg { width: 18px; height: 18px; }
    .hdb-shortcut--primary {
        background: var(--hr-primary);
        color: #fff;
        border-color: var(--hr-primary);
        box-shadow: 0 6px 18px rgba(127, 86, 217, 0.22);
    }
    .hdb-shortcut--primary:hover { color: #fff; filter: brightness(1.06); }
    .hdb-shortcut--primary .hdb-shortcut-icon {
        background: rgba(255,255,255,0.16); color: #fff;
    }
    .hdb-grid-2 { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 18px; margin-bottom: 18px; }
    .hdb-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; margin-bottom: 18px; }
    @media (max-width: 980px) {
        .hdb-grid-2, .hdb-grid-3 { grid-template-columns: 1fr; }
    }
    .hdb-card-icon-wrap {
        width: 32px; height: 32px; border-radius: 8px;
        background: var(--hr-primary-50); color: var(--hr-primary-700);
        display: inline-flex; align-items: center; justify-content: center;
        flex-shrink: 0;
    }
    .hdb-card-icon-wrap svg { width: 16px; height: 16px; }
    .hdb-card-icon-wrap--green { background: var(--hr-green-50); color: var(--hr-green-700); }
    .hdb-card-icon-wrap--amber { background: var(--hr-amber-50); color: var(--hr-amber-700); }
    .hdb-card-icon-wrap--blue { background: var(--hr-blue-50); color: var(--hr-blue-600); }
    .hdb-card-icon-wrap--orange { background: var(--hr-orange-50); color: var(--hr-orange-600); }
    .hdb-card-title-row { display: flex; align-items: center; gap: 10px; }
    .hdb-view-all {
        font-size: 12px;
        color: var(--hr-primary-700);
        font-weight: 600;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .hdb-view-all:hover { color: var(--hr-primary); }
    .hdb-view-all svg { width: 12px; height: 12px; }
    .hdb-mini-list { display: flex; flex-direction: column; }
    .hdb-mini-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 12px 22px;
        border-bottom: 1px solid var(--hr-line-soft);
        text-decoration: none;
        color: var(--hr-text);
        transition: background .12s;
    }
    .hdb-mini-row:hover { background: var(--hr-primary-50); color: var(--hr-primary-700); text-decoration: none; }
    .hdb-mini-row:last-child { border-bottom: none; }
    .hdb-mini-label { font-weight: 600; font-size: 13px; color: var(--hr-dark); }
    .hdb-mini-meta { font-size: 11px; color: var(--hr-muted); }
    .hdb-alert-list { display: flex; flex-direction: column; gap: 10px; padding: 18px 22px; }
    .hdb-alert {
        display: block;
        border-radius: 12px;
        padding: 12px 14px;
        text-decoration: none;
        background: var(--hr-bg);
        border-left: 3px solid var(--hr-primary);
        transition: all .15s;
    }
    .hdb-alert:hover { background: var(--hr-primary-50); text-decoration: none; }
    .hdb-alert--warn { border-left-color: #DC6803; background: var(--hr-amber-50); }
    .hdb-alert--warn:hover { background: #FEF0C7; }
    .hdb-alert--info { border-left-color: var(--hr-blue-600); background: var(--hr-blue-50); }
    .hdb-alert-title { font-weight: 700; font-size: 13px; color: var(--hr-dark); margin-bottom: 2px; }
    .hdb-alert-message { font-size: 12px; color: var(--hr-muted); }
    .hdb-mix-grid {
        padding: 18px 22px;
        display: grid;
        grid-template-columns: 1fr;
        gap: 12px;
    }
    .hdb-mix-card {
        border: 1px solid var(--hr-line);
        background: var(--hr-bg);
        border-radius: 12px;
        padding: 12px 14px;
    }
    .hdb-mix-title {
        font-size: 11px; font-weight: 700;
        text-transform: uppercase; letter-spacing: .08em;
        color: var(--hr-muted);
        margin-bottom: 10px;
    }
    .hdb-mix-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: 6px 0;
        gap: 12px;
    }
    .hdb-mix-row + .hdb-mix-row { border-top: 1px solid var(--hr-line-soft); }
    .hdb-mix-row span { color: var(--hr-text); font-size: 13px; }
    .hdb-mix-row strong { color: var(--hr-dark); font-weight: 700; font-size: 13px; }
    .hdb-mix-bar {
        flex: 1;
        height: 5px;
        background: var(--hr-line);
        border-radius: 999px;
        overflow: hidden;
        max-width: 120px;
    }
    .hdb-mix-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--hr-primary-600) 0%, #B692F6 100%);
        border-radius: 999px;
    }
    .hdb-empty-card { padding: 32px 22px; text-align: center; color: var(--hr-muted); font-size: 13px; }
    .hdb-empty-card svg { width: 28px; height: 28px; color: #CBD5E1; margin-bottom: 8px; display: block; margin-left: auto; margin-right: auto; }

    .hdb-perf-card {
        background: linear-gradient(135deg, #EFF8FF 0%, #F4EBFF 100%);
        border: 1px solid var(--hr-line);
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 18px;
        position: relative;
        overflow: hidden;
    }
    .hdb-perf-card::before {
        content: "";
        position: absolute;
        right: -40px; top: -40px;
        width: 200px; height: 200px;
        background: radial-gradient(circle, rgba(127,86,217,0.12) 0%, transparent 70%);
        pointer-events: none;
    }
    .hdb-perf-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; position: relative; }
    .hdb-perf-title-block { flex: 1; }
    .hdb-perf-eyebrow {
        font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
        color: #1570EF; font-weight: 700; margin-bottom: 4px;
    }
    .hdb-perf-cycle-name { font-size: 18px; font-weight: 700; color: var(--hr-dark); letter-spacing: -0.01em; }
    .hdb-perf-cycle-dates { font-size: 12px; color: var(--hr-muted); margin-top: 4px; }
    .hdb-perf-cta {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 8px 14px; background: var(--hr-card);
        border: 1px solid var(--hr-line);
        border-radius: 10px;
        font-size: 12px; font-weight: 700;
        color: var(--hr-primary-700);
        text-decoration: none;
        transition: all .15s;
    }
    .hdb-perf-cta:hover { background: var(--hr-primary-50); text-decoration: none; }
    .hdb-perf-cta svg { width: 12px; height: 12px; }
    .hdb-perf-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 2fr;
        gap: 16px;
        position: relative;
    }
    @media (max-width: 980px) {
        .hdb-perf-grid { grid-template-columns: 1fr 1fr; }
        .hdb-perf-top { grid-column: 1 / -1; }
    }
    .hdb-perf-stat { background: var(--hr-card); border-radius: 12px; padding: 14px 16px; border: 1px solid var(--hr-line); }
    .hdb-perf-stat-label { font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--hr-muted); font-weight: 700; }
    .hdb-perf-stat-value { font-size: 24px; font-weight: 800; color: var(--hr-dark); margin-top: 4px; letter-spacing: -0.02em; }
    .hdb-perf-stat-hint { font-size: 11px; color: var(--hr-muted); margin-top: 4px; }
    .hdb-perf-top {
        background: var(--hr-card);
        border-radius: 12px;
        padding: 12px 14px;
        border: 1px solid var(--hr-line);
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .hdb-perf-top-label { font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--hr-muted); font-weight: 700; }
    .hdb-perf-top-list { display: flex; flex-direction: column; gap: 6px; }
    .hdb-perf-top-item {
        display: flex; align-items: center; gap: 10px;
        padding: 6px 8px;
        border-radius: 8px;
        background: var(--hr-bg);
    }
    .hdb-perf-top-rank {
        width: 22px; height: 22px;
        border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 11px; font-weight: 800;
        flex-shrink: 0;
    }
    .hdb-perf-rank-1 { background: linear-gradient(135deg, #FDE68A 0%, #F59E0B 100%); color: #78350F; }
    .hdb-perf-rank-2 { background: linear-gradient(135deg, #E5E7EB 0%, #94A3B8 100%); color: var(--hr-dark); }
    .hdb-perf-rank-3 { background: linear-gradient(135deg, #FED7AA 0%, #C2410C 100%); color: #fff; }
    .hdb-perf-top-name { flex: 1; font-size: 13px; font-weight: 600; color: var(--hr-dark); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .hdb-perf-top-score { font-weight: 800; color: var(--hr-primary-700); font-size: 14px; }

    .hdb-shimmer { padding: 36px 22px; text-align: center; color: var(--hr-muted); font-size: 12px; }
    `;
    const tag = document.createElement("style");
    tag.id = "hdb-styles";
    tag.textContent = css;
    document.head.appendChild(tag);
}

function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const today = frappe.datetime.str_to_user(frappe.datetime.now_date());

    page.main.html(`
        <div class="hr-wrap">
            <div class="hr-hero">
                <div>
                    <div class="hr-eyebrow">${__("Orderlift")} · ${__("People Hub")}</div>
                    <div class="hdb-greeting">
                        <h1 class="hr-title">${greeting}</h1>
                        <span class="hdb-date">${today}</span>
                    </div>
                    <div class="hr-sub">${__("Headcount, leave, payroll, performance and training at a glance.")}</div>
                </div>
            </div>

            <div class="hr-kpis" id="hdb-kpi-grid">
                ${Array.from({ length: 6 }, () => `<div class="hr-kpi"><div class="hdb-shimmer">${__("Loading…")}</div></div>`).join("")}
            </div>

            <div class="hdb-shortcuts">
                ${shortcutUrl("plus", __("New Employee"), "/app/employee/new?employee_name=", "primary")}
                ${shortcutUrl("users", __("Employees"), "/app/employee", "default")}
                ${shortcutUrl("leave", __("Leave"), "/app/leave-application", "default")}
                ${shortcutUrl("attendance", __("Attendance"), "/app/attendance", "default")}
                ${shortcutUrl("payroll", __("Payroll"), "/app/payroll-entry", "default")}
                ${shortcutUrl("trophy", __("Performance"), "/app/performance-leaderboard", "default")}
            </div>

            <div id="hdb-perf-block"></div>

            <div class="hdb-grid-2">
                <div class="hr-card">
                    <div class="hr-card-head">
                        <div class="hdb-card-title-row">
                            <div class="hdb-card-icon-wrap hdb-card-icon-wrap--blue">${ICONS.users}</div>
                            <div>
                                <div class="hr-card-title">${__("Recent HR Records")}</div>
                                <div class="hr-card-sub">${__("Latest employees, leave & expense activity")}</div>
                            </div>
                        </div>
                        <a href="/app/employee" class="hdb-view-all">${__("View all")} ${ICONS.arrow}</a>
                    </div>
                    <div id="hdb-recent-table"><div class="hdb-shimmer">${__("Loading…")}</div></div>
                </div>
                <div class="hr-card">
                    <div class="hr-card-head">
                        <div class="hdb-card-title-row">
                            <div class="hdb-card-icon-wrap hdb-card-icon-wrap--amber">${ICONS.alert}</div>
                            <div>
                                <div class="hr-card-title">${__("HR Alerts")}</div>
                                <div class="hr-card-sub">${__("Items that need follow-up")}</div>
                            </div>
                        </div>
                    </div>
                    <div id="hdb-alerts"><div class="hdb-shimmer">${__("Loading…")}</div></div>
                </div>
            </div>

            <div class="hdb-grid-3">
                <div class="hr-card">
                    <div class="hr-card-head">
                        <div class="hdb-card-title-row">
                            <div class="hdb-card-icon-wrap">${ICONS.department}</div>
                            <div>
                                <div class="hr-card-title">${__("Workforce Mix")}</div>
                                <div class="hr-card-sub">${__("Department, designation & status")}</div>
                            </div>
                        </div>
                    </div>
                    <div id="hdb-workforce-mix"><div class="hdb-shimmer">${__("Loading…")}</div></div>
                </div>
                <div class="hr-card">
                    <div class="hr-card-head">
                        <div class="hdb-card-title-row">
                            <div class="hdb-card-icon-wrap hdb-card-icon-wrap--blue">${ICONS.leave}</div>
                            <div>
                                <div class="hr-card-title">${__("Leave Pipeline")}</div>
                                <div class="hr-card-sub">${__("By status")}</div>
                            </div>
                        </div>
                    </div>
                    <div id="hdb-leave-pipeline"><div class="hdb-shimmer">${__("Loading…")}</div></div>
                </div>
                <div class="hr-card">
                    <div class="hr-card-head">
                        <div class="hdb-card-title-row">
                            <div class="hdb-card-icon-wrap hdb-card-icon-wrap--green">${ICONS.check}</div>
                            <div>
                                <div class="hr-card-title">${__("New Joiners")}</div>
                                <div class="hr-card-sub">${__("Last 30 days")}</div>
                            </div>
                        </div>
                    </div>
                    <div id="hdb-milestones"><div class="hdb-shimmer">${__("Loading…")}</div></div>
                </div>
            </div>
        </div>
    `);

    page.main.on("click", ".hdb-shortcut", function () {
        const url = $(this).data("url");
        if (url) window.location.href = url;
    });
}

async function loadDashboardData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.page.hr_dashboard.hr_dashboard.get_dashboard_data",
        });
        const data = res.message || {};
        renderKpis(page, data.kpis || {}, data.performance_summary, data.training_summary);
        renderPerformance(page, data.performance_summary);
        renderRecentDocs(page, data.recent_docs || []);
        renderAlerts(page, data.alerts || []);
        renderWorkforceMix(page, data.workforce_mix || {});
        renderLeavePipeline(page, data.leave_pipeline || []);
        renderMilestones(page, data.upcoming_milestones || []);
    } catch (e) {
        console.warn("HR Dashboard: failed to load data", e);
        renderKpis(page, {});
        renderRecentDocs(page, []);
        renderAlerts(page, []);
        renderWorkforceMix(page, {});
        renderLeavePipeline(page, []);
        renderMilestones(page, []);
    }
}

function shortcutUrl(iconKey, label, url, variant) {
    return `<div class="hdb-shortcut hdb-shortcut--${variant}" data-url="${frappe.utils.escape_html(url)}">
        <span class="hdb-shortcut-icon">${ICONS[iconKey] || ""}</span>
        <span>${frappe.utils.escape_html(label)}</span>
    </div>`;
}

function renderKpis(page, kpis, perfSummary, trainingSummary) {
    const perfMedian = perfSummary && perfSummary.median != null ? perfSummary.median : null;
    const defs = [
        {
            icon: "users",
            iconCls: "indigo",
            label: __("Active Employees"),
            value: kpis.active_employees ?? "—",
            hint: __("Current active workforce"),
        },
        {
            icon: "department",
            iconCls: "purple",
            label: __("Departments"),
            value: kpis.departments ?? "—",
            hint: __("Active departments"),
        },
        {
            icon: "leave",
            iconCls: "blue",
            label: __("Open Leave"),
            value: kpis.leave_open ?? "—",
            hint: __("Pending or approved"),
        },
        {
            icon: "attendance",
            iconCls: "green",
            label: __("Attendance Today"),
            value: kpis.attendance_today ?? "—",
            hint: __("Records logged today"),
        },
        {
            icon: "trophy",
            iconCls: "amber",
            label: __("Cycle Median"),
            value: perfMedian != null ? perfMedian.toFixed(1) : "—",
            hint: perfSummary ? __("Performance score") : __("No cycle yet"),
        },
        {
            icon: "book",
            iconCls: "orange",
            label: __("Training Completion"),
            value:
                trainingSummary && trainingSummary.completion_pct != null
                    ? `${trainingSummary.completion_pct}%`
                    : "—",
            hint: trainingSummary
                ? `${trainingSummary.modules || 0} ${__("modules")} · ${trainingSummary.programs || 0} ${__("programs")}`
                : __("No training data"),
        },
    ];
    page.main.find("#hdb-kpi-grid").html(
        defs
            .map(
                (d) => `
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--${d.iconCls}">${ICONS[d.icon] || ""}</div>
                    <div class="hr-kpi-label">${d.label}</div>
                    <div class="hr-kpi-value">${d.value}</div>
                    <div class="hr-kpi-hint">${d.hint}</div>
                </div>`,
            )
            .join(""),
    );
}

function renderPerformance(page, p) {
    const target = page.main.find("#hdb-perf-block");
    if (!p) {
        target.html("");
        return;
    }
    const dateLine =
        p.start_date && p.end_date
            ? `${frappe.datetime.str_to_user(p.start_date)} → ${frappe.datetime.str_to_user(p.end_date)}`
            : "";
    const median = p.median != null ? p.median.toFixed(1) : "—";
    const empCount = p.employees || 0;
    const metricCount = p.metrics || 0;
    const top = (p.top || []).slice(0, 3);
    const topHtml = top.length
        ? top
              .map(
                  (t, i) => `
                  <div class="hdb-perf-top-item">
                      <span class="hdb-perf-top-rank hdb-perf-rank-${i + 1}">${i + 1}</span>
                      <span class="hdb-perf-top-name">${frappe.utils.escape_html(t.name)}</span>
                      <span class="hdb-perf-top-score">${(t.score || 0).toFixed(1)}</span>
                  </div>`,
              )
              .join("")
        : `<div class="hdb-perf-top-item" style="justify-content:center;color:var(--hr-muted);font-size:12px;">${__("No snapshots yet")}</div>`;

    target.html(`
        <div class="hdb-perf-card">
            <div class="hdb-perf-head">
                <div class="hdb-perf-title-block">
                    <div class="hdb-perf-eyebrow">${__("Active Appraisal Cycle")}</div>
                    <div class="hdb-perf-cycle-name">${frappe.utils.escape_html(p.cycle_name)}</div>
                    ${dateLine ? `<div class="hdb-perf-cycle-dates">${frappe.utils.escape_html(dateLine)}</div>` : ""}
                </div>
                <a href="/app/performance-leaderboard" class="hdb-perf-cta">${__("Open Leaderboard")} ${ICONS.arrow}</a>
            </div>
            <div class="hdb-perf-grid">
                <div class="hdb-perf-stat">
                    <div class="hdb-perf-stat-label">${__("Employees")}</div>
                    <div class="hdb-perf-stat-value">${empCount || "—"}</div>
                    <div class="hdb-perf-stat-hint">${__("In this cycle")}</div>
                </div>
                <div class="hdb-perf-stat">
                    <div class="hdb-perf-stat-label">${__("Median")}</div>
                    <div class="hdb-perf-stat-value">${median}</div>
                    <div class="hdb-perf-stat-hint">${metricCount} ${__("metric snapshots")}</div>
                </div>
                <div class="hdb-perf-top">
                    <div class="hdb-perf-top-label">${__("Top performers")}</div>
                    <div class="hdb-perf-top-list">${topHtml}</div>
                </div>
            </div>
        </div>
    `);
}

function renderRecentDocs(page, rows) {
    const target = page.main.find("#hdb-recent-table");
    if (!rows.length) {
        target.html(`<div class="hdb-empty-card">${ICONS.users}<div>${__("No HR records yet.")}</div></div>`);
        return;
    }
    target.html(
        `<div class="hdb-mini-list">${rows
            .map(
                (row) => `
                <a class="hdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="hdb-mini-label">${frappe.utils.escape_html(row.label || "")}</span>
                    <span class="hdb-mini-meta">${frappe.utils.escape_html(row.meta || "")}</span>
                </a>`,
            )
            .join("")}</div>`,
    );
}

function renderAlerts(page, alerts) {
    const target = page.main.find("#hdb-alerts");
    if (!alerts.length) {
        target.html(`<div class="hdb-empty-card">${ICONS.check}<div>${__("No active HR alerts.")}</div></div>`);
        return;
    }
    target.html(
        `<div class="hdb-alert-list">${alerts
            .map(
                (a) => `
                <a class="hdb-alert hdb-alert--${a.level || "info"}" href="${frappe.utils.escape_html(a.link || "#")}">
                    <div class="hdb-alert-title">${frappe.utils.escape_html(a.title || "")}</div>
                    <div class="hdb-alert-message">${frappe.utils.escape_html(a.message || "")}</div>
                </a>`,
            )
            .join("")}</div>`,
    );
}

function mixRow(item, max) {
    const pct = max > 0 ? Math.min(100, Math.round(((item.value || 0) / max) * 100)) : 0;
    return `<div class="hdb-mix-row">
        <span>${frappe.utils.escape_html(item.label || "")}</span>
        <div class="hdb-mix-bar"><div class="hdb-mix-bar-fill" style="width:${pct}%"></div></div>
        <strong>${item.value ?? 0}</strong>
    </div>`;
}

function renderWorkforceMix(page, mix) {
    const target = page.main.find("#hdb-workforce-mix");
    const departments = mix.departments || [];
    const designations = mix.designations || [];
    const status = mix.status || [];
    if (!departments.length && !designations.length && !status.length) {
        target.html(`<div class="hdb-empty-card">${__("No workforce data yet.")}</div>`);
        return;
    }
    const block = (title, items) => {
        if (!items.length) return "";
        const max = Math.max(...items.map((i) => i.value || 0));
        return `<div class="hdb-mix-card">
            <div class="hdb-mix-title">${title}</div>
            ${items.map((i) => mixRow(i, max)).join("")}
        </div>`;
    };
    target.html(`<div class="hdb-mix-grid">
        ${block(__("By Department"), departments)}
        ${block(__("By Designation"), designations)}
        ${block(__("By Status"), status)}
    </div>`);
}

function renderLeavePipeline(page, rows) {
    const target = page.main.find("#hdb-leave-pipeline");
    if (!rows.length) {
        target.html(`<div class="hdb-empty-card">${__("No leave workflow data yet.")}</div>`);
        return;
    }
    const max = Math.max(...rows.map((r) => r.value || 0));
    target.html(`<div class="hdb-mix-grid">
        <div class="hdb-mix-card">
            <div class="hdb-mix-title">${__("By Status")}</div>
            ${rows.map((i) => mixRow(i, max)).join("")}
        </div>
    </div>`);
}

function renderMilestones(page, rows) {
    const target = page.main.find("#hdb-milestones");
    if (!rows.length) {
        target.html(`<div class="hdb-empty-card">${__("No upcoming HR milestones.")}</div>`);
        return;
    }
    target.html(
        `<div class="hdb-mini-list">${rows
            .map(
                (row) => `
                <a class="hdb-mini-row" href="${frappe.utils.escape_html(row.link || "#")}">
                    <span class="hdb-mini-label">${frappe.utils.escape_html(row.employee_name || "")}</span>
                    <span class="hdb-mini-meta">${frappe.utils.escape_html(row.date || "")}${
                    row.meta ? ` · ${frappe.utils.escape_html(row.meta)}` : ""
                }</span>
                </a>`,
            )
            .join("")}</div>`,
    );
}
